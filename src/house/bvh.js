import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  One triangle soup of the whole house, at rest positions, with a
 *  bounding-volume tree over it (the same plain BVH as src/surface.js)
 *  and a part index per triangle, so a single tree answers every ray:
 *  the spec pick, the tape measure and the walk collision. Each ray
 *  takes a per-part mask (what is built, shown, solid NOW) and an
 *  optional section plane, so a wall that is not built yet, a hidden
 *  storey or the half cut away by the slice never catches a ray.
 *  Rebuilt only when an edit changes geometry.
 * ------------------------------------------------------------------ */

const LEAF = 8;

export function buildBVH(allParts) {
  const t0 = performance.now();
  const parts = allParts.filter(p => !p.noRay);
  let total = 0;
  for (const p of parts) {
    const g = p.geometry;
    p._tris = (g.index ? g.index.count : g.attributes.position.count) / 3;
    total += p._tris;
  }
  const tri = new Float32Array(total * 9);
  const owner = new Uint32Array(total);
  const v = new THREE.Vector3();
  let k = 0;
  for (const p of parts) {
    const pos = p.geometry.attributes.position, idx = p.geometry.index;
    for (let t = 0; t < p._tris; t++) {
      for (let c = 0; c < 3; c++) {
        v.fromBufferAttribute(pos, idx ? idx.getX(t * 3 + c) : t * 3 + c).applyMatrix4(p.matrix0);
        tri[k * 9 + c * 3] = v.x; tri[k * 9 + c * 3 + 1] = v.y; tri[k * 9 + c * 3 + 2] = v.z;
      }
      owner[k++] = p.index;
    }
  }
  const cen = new Float32Array(total * 3);
  for (let i = 0; i < total; i++) for (let a = 0; a < 3; a++)
    cen[i * 3 + a] = (tri[i * 9 + a] + tri[i * 9 + 3 + a] + tri[i * 9 + 6 + a]) / 3;
  const order = new Uint32Array(total);
  for (let i = 0; i < total; i++) order[i] = i;
  const maxNodes = 2 * total + 1;
  const box = new Float32Array(maxNodes * 6);
  const left = new Int32Array(maxNodes), right = new Int32Array(maxNodes);
  const start = new Int32Array(maxNodes), count = new Int32Array(maxNodes);
  let nodes = 0;

  function build(s, e) {
    const id = nodes++;
    let x0 = Infinity, y0 = Infinity, z0 = Infinity, x1 = -Infinity, y1 = -Infinity, z1 = -Infinity;
    let cx0 = Infinity, cy0 = Infinity, cz0 = Infinity, cx1 = -Infinity, cy1 = -Infinity, cz1 = -Infinity;
    for (let i = s; i < e; i++) {
      const t = order[i];
      for (let c = 0; c < 9; c += 3) {
        const px = tri[t * 9 + c], py = tri[t * 9 + c + 1], pz = tri[t * 9 + c + 2];
        if (px < x0) x0 = px; if (px > x1) x1 = px;
        if (py < y0) y0 = py; if (py > y1) y1 = py;
        if (pz < z0) z0 = pz; if (pz > z1) z1 = pz;
      }
      const qx = cen[t * 3], qy = cen[t * 3 + 1], qz = cen[t * 3 + 2];
      if (qx < cx0) cx0 = qx; if (qx > cx1) cx1 = qx;
      if (qy < cy0) cy0 = qy; if (qy > cy1) cy1 = qy;
      if (qz < cz0) cz0 = qz; if (qz > cz1) cz1 = qz;
    }
    box[id * 6] = x0; box[id * 6 + 1] = y0; box[id * 6 + 2] = z0;
    box[id * 6 + 3] = x1; box[id * 6 + 4] = y1; box[id * 6 + 5] = z1;
    if (e - s <= LEAF) { left[id] = -1; start[id] = s; count[id] = e - s; return id; }
    const ex = cx1 - cx0, ey = cy1 - cy0, ez = cz1 - cz0;
    const axis = ex >= ey && ex >= ez ? 0 : ey >= ez ? 1 : 2;
    const mid = axis === 0 ? (cx0 + cx1) / 2 : axis === 1 ? (cy0 + cy1) / 2 : (cz0 + cz1) / 2;
    let i = s, j = e - 1;
    while (i <= j) {
      if (cen[order[i] * 3 + axis] < mid) i++;
      else { const tmp = order[i]; order[i] = order[j]; order[j] = tmp; j--; }
    }
    if (i === s || i === e) i = (s + e) >> 1;
    left[id] = build(s, i);
    right[id] = build(i, e);
    count[id] = 0;
    return id;
  }
  if (total) build(0, total);

  const stack = new Int32Array(512);
  const hit = { distance: 0, point: new THREE.Vector3(), normal: new THREE.Vector3(), part: -1, tri: -1, front: true };

  /* nearest hit whose part has mask[part] != 0 and (with a plane) lies on its kept side. With `front`, back faces
     are skipped: the contract's parts are closed solids with outward normals, so a back face is only ever seen from
     INSIDE a solid (a ray starting in a slab, a tread or a beam) — the walk's floor ray ignores those. The returned
     normal always faces the ray; `hit.front` says which side of the triangle was hit. */
  function raycast(ray, far, mask, plane = null, front = false) {
    if (!total) return null;
    const ox = ray.origin.x, oy = ray.origin.y, oz = ray.origin.z;
    const dx = ray.direction.x, dy = ray.direction.y, dz = ray.direction.z;
    const ix = 1 / dx, iy = 1 / dy, iz = 1 / dz;
    const pnx = plane ? plane.normal.x : 0, pny = plane ? plane.normal.y : 0, pnz = plane ? plane.normal.z : 0, pc = plane ? plane.constant : 0;
    let best = far, bestTri = -1, bestFront = true, sp = 0;
    stack[sp++] = 0;
    while (sp) {
      const id = stack[--sp];
      const b = id * 6;
      let t1 = (box[b] - ox) * ix, t2 = (box[b + 3] - ox) * ix;
      let tmin = Math.min(t1, t2), tmax = Math.max(t1, t2);
      t1 = (box[b + 1] - oy) * iy; t2 = (box[b + 4] - oy) * iy;
      tmin = Math.max(tmin, Math.min(t1, t2)); tmax = Math.min(tmax, Math.max(t1, t2));
      t1 = (box[b + 2] - oz) * iz; t2 = (box[b + 5] - oz) * iz;
      tmin = Math.max(tmin, Math.min(t1, t2)); tmax = Math.min(tmax, Math.max(t1, t2));
      if (!(tmax >= Math.max(tmin, 0)) || tmin > best) continue;
      if (left[id] === -1) {
        for (let i = start[id], e = i + count[id]; i < e; i++) {
          const t = order[i];
          if (mask && !mask[owner[t]]) continue;
          const p = t * 9;
          const ax = tri[p], ay = tri[p + 1], az = tri[p + 2];
          const e1x = tri[p + 3] - ax, e1y = tri[p + 4] - ay, e1z = tri[p + 5] - az;
          const e2x = tri[p + 6] - ax, e2y = tri[p + 7] - ay, e2z = tri[p + 8] - az;
          const px = dy * e2z - dz * e2y, py = dz * e2x - dx * e2z, pz = dx * e2y - dy * e2x;
          const det = e1x * px + e1y * py + e1z * pz;
          if (Math.abs(det) < 1e-12 || (front && det < 0)) continue;
          const inv = 1 / det;
          const sx = ox - ax, sy = oy - ay, sz = oz - az;
          const u = (sx * px + sy * py + sz * pz) * inv;
          if (u < 0 || u > 1) continue;
          const qx = sy * e1z - sz * e1y, qy = sz * e1x - sx * e1z, qz = sx * e1y - sy * e1x;
          const w = (dx * qx + dy * qy + dz * qz) * inv;
          if (w < 0 || u + w > 1) continue;
          const d = (e2x * qx + e2y * qy + e2z * qz) * inv;
          if (!(d > 1e-4 && d < best)) continue;
          if (plane && pnx * (ox + dx * d) + pny * (oy + dy * d) + pnz * (oz + dz * d) + pc < 0) continue;   // sliced away
          best = d; bestTri = t; bestFront = det > 0;
        }
      } else if (sp < 510) {
        stack[sp++] = left[id];
        stack[sp++] = right[id];
      }
    }
    if (bestTri < 0) return null;
    const p = bestTri * 9;
    const e1 = new THREE.Vector3(tri[p + 3] - tri[p], tri[p + 4] - tri[p + 1], tri[p + 5] - tri[p + 2]);
    const e2 = new THREE.Vector3(tri[p + 6] - tri[p], tri[p + 7] - tri[p + 1], tri[p + 8] - tri[p + 2]);
    hit.normal.crossVectors(e1, e2).normalize();
    if (hit.normal.x * dx + hit.normal.y * dy + hit.normal.z * dz > 0) hit.normal.negate();
    hit.distance = best;
    hit.point.set(ox + dx * best, oy + dy * best, oz + dz * best);
    hit.part = owner[bestTri];
    hit.tri = bestTri;
    hit.front = bestFront;
    return hit;
  }

  function triangle(t, out = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()]) {
    for (let c = 0; c < 3; c++) out[c].set(tri[t * 9 + c * 3], tri[t * 9 + c * 3 + 1], tri[t * 9 + c * 3 + 2]);
    return out;
  }

  const ms = performance.now() - t0;
  console.info(`house: BVH ${total.toLocaleString()} triangles, ${nodes} nodes, ${ms.toFixed(0)} ms`);
  return { raycast, triangle, triangles: total, nodes, ms };
}
