import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  A collision copy of the site for the marking ray: every wall, roof,
 *  fence, kerb and patch of ground in one flat triangle list with a
 *  small bounding-volume tree over it, so one ray costs microseconds
 *  even on the Quest. Tree canopies and the built plants are left out
 *  (over a million triangles of leaves): a ray through a bed lands on
 *  the soil beneath it, which is where a mark belongs anyway.
 *  No dependency: about a hundred lines of plain BVH.
 * ------------------------------------------------------------------ */

const SKIP = /island_tree.*(leaves|branches)|VertexPlant/i;
const LEAF = 8;

export function buildCollision(root, { skip = SKIP } = {}) {
  const t0 = performance.now();
  const names = [], nameIdx = new Map();
  const parts = [];
  let total = 0;
  root.updateWorldMatrix(true, true);
  root.traverse(o => {
    if (!o.isMesh || o.isInstancedMesh || o.isSkinnedMesh) return;
    const mname = o.material?.name || o.name || "mesh";
    if (skip.test(mname)) return;
    const pos = o.geometry.attributes.position;
    if (!pos) return;
    const n = (o.geometry.index ? o.geometry.index.count : pos.count) / 3;
    if (!nameIdx.has(mname)) { nameIdx.set(mname, names.length); names.push(mname); }
    parts.push({ o, n, m: nameIdx.get(mname) });
    total += n;
  });
  const tri = new Float32Array(total * 9);
  const mat = new Uint16Array(total);
  const v = new THREE.Vector3();
  let k = 0;
  for (const { o, n, m } of parts) {
    const pos = o.geometry.attributes.position, idx = o.geometry.index;
    for (let t = 0; t < n; t++) {
      for (let c = 0; c < 3; c++) {
        v.fromBufferAttribute(pos, idx ? idx.getX(t * 3 + c) : t * 3 + c).applyMatrix4(o.matrixWorld);
        tri[k * 9 + c * 3] = v.x; tri[k * 9 + c * 3 + 1] = v.y; tri[k * 9 + c * 3 + 2] = v.z;
      }
      mat[k] = m; k++;
    }
  }

  /* centroids and the build */
  const cen = new Float32Array(total * 3);
  for (let i = 0; i < total; i++) for (let a = 0; a < 3; a++)
    cen[i * 3 + a] = (tri[i * 9 + a] + tri[i * 9 + 3 + a] + tri[i * 9 + 6 + a]) / 3;
  const order = new Uint32Array(total);
  for (let i = 0; i < total; i++) order[i] = i;
  const maxNodes = 2 * total + 1;            // worst case: a leaf per triangle
  const box = new Float32Array(maxNodes * 6);
  const left = new Int32Array(maxNodes), right = new Int32Array(maxNodes);
  const start = new Int32Array(maxNodes), count = new Int32Array(maxNodes);
  let nodes = 0;

  /* split about the middle of the centroids' extent on the longest axis; O(n log n) */
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

  /* ---------- the ray ---------- */
  const stack = new Int32Array(512);
  const hit = { distance: 0, point: new THREE.Vector3(), normal: new THREE.Vector3(), surface: "" };
  function raycast(ray, far = 30) {
    if (!total) return null;
    const ox = ray.origin.x, oy = ray.origin.y, oz = ray.origin.z;
    const dx = ray.direction.x, dy = ray.direction.y, dz = ray.direction.z;
    const ix = 1 / dx, iy = 1 / dy, iz = 1 / dz;
    let best = far, bestTri = -1, sp = 0;
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
      if (!(tmax >= Math.max(tmin, 0)) || tmin > best) continue;   // NaN-safe
      if (left[id] === -1) {
        for (let i = start[id], e = i + count[id]; i < e; i++) {
          const t = order[i], p = t * 9;
          // Möller–Trumbore, both faces
          const ax = tri[p], ay = tri[p + 1], az = tri[p + 2];
          const e1x = tri[p + 3] - ax, e1y = tri[p + 4] - ay, e1z = tri[p + 5] - az;
          const e2x = tri[p + 6] - ax, e2y = tri[p + 7] - ay, e2z = tri[p + 8] - az;
          const px = dy * e2z - dz * e2y, py = dz * e2x - dx * e2z, pz = dx * e2y - dy * e2x;
          const det = e1x * px + e1y * py + e1z * pz;
          if (Math.abs(det) < 1e-12) continue;
          const inv = 1 / det;
          const sx = ox - ax, sy = oy - ay, sz = oz - az;
          const u = (sx * px + sy * py + sz * pz) * inv;
          if (u < 0 || u > 1) continue;
          const qx = sy * e1z - sz * e1y, qy = sz * e1x - sx * e1z, qz = sx * e1y - sy * e1x;
          const w = (dx * qx + dy * qy + dz * qz) * inv;
          if (w < 0 || u + w > 1) continue;
          const d = (e2x * qx + e2y * qy + e2z * qz) * inv;
          if (d > 1e-4 && d < best) { best = d; bestTri = t; }
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
    if (hit.normal.x * dx + hit.normal.y * dy + hit.normal.z * dz > 0) hit.normal.negate();   // face the viewer
    hit.distance = best;
    hit.point.set(ox + dx * best, oy + dy * best, oz + dz * best);
    hit.surface = names[mat[bestTri]];
    return hit;
  }

  const ms = performance.now() - t0;
  console.info(`marks: collision copy ${total.toLocaleString()} triangles, ${nodes} nodes, ${ms.toFixed(0)} ms`);
  return { raycast, triangles: total, nodes, ms };
}
