import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  Room visibility (portal culling) for the batched house, and a faster
 *  per-instance frustum cull. PLAN S10.
 *
 *  The picture never changes: an instance is skipped only when no sight line
 *  from the camera can reach it. The cells are the spec rooms (type "room":
 *  polygon + floor) plus "outside"; the portals are the openings (doors,
 *  windows, archways: wall + offset + width + sill + head) and the stairwell
 *  (rooms of two storeys that overlap in plan). From the room the eye is in,
 *  a neighbouring cell is entered only through a portal that is inside the
 *  view frustum, and its frustum is narrowed to the portal's edges, so a
 *  room behind a wall is never drawn. Every part has a set of cells it is
 *  drawn for:
 *    - a part wholly inside one room's air (furniture, floor finish, fittings):
 *      that room only;
 *    - everything else (walls, slabs, roof, doors, windows, the ground, the
 *      garden and street): every room whose plan it touches (+30 cm) AND outside.
 *  Collision and picking use the BVH and the part masks, never this. The shadow
 *  pass is not culled by room (onBeforeShadow keeps three's own loop), so the
 *  shadow map is the same. Culling switches itself off (draw everything) when
 *  the picture could see through a wall that the cells assume is there: a stage
 *  before the last, the slice, x-ray, a hidden storey. Nothing here is specific to
 *  one house: the cells and portals come from the version's element table.
 * ------------------------------------------------------------------ */

const OUT_PAD = 0.3;                     // a part within this of a room's plan belongs to it
const EYE_PAD = 0.3;                     // an eye this close to a room's plan is in it too
const SLACK = 0.15;                      // frustum planes are pushed out by this (eye offsets, rounding)
const MAX_DEPTH = 6;
const NEAR_PORTAL = 0.6;                 // an eye this near a portal does not narrow the view through it

const inPoly = (poly, x, z) => {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) inside = !inside;
  }
  return inside;
};
const segX = (ax, az, bx, bz, cx, cz, dx, dz) => {
  const d1x = bx - ax, d1z = bz - az, d2x = dx - cx, d2z = dz - cz, den = d1x * d2z - d1z * d2x;
  if (Math.abs(den) < 1e-12) return false;
  const t = ((cx - ax) * d2z - (cz - az) * d2x) / den, u = ((cx - ax) * d1z - (cz - az) * d1x) / den;
  return t >= 0 && t <= 1 && u >= 0 && u <= 1;
};
function rectTouchesPoly(x0, z0, x1, z1, poly) {
  for (const [x, z] of poly) if (x >= x0 && x <= x1 && z >= z0 && z <= z1) return true;
  for (const [x, z] of [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]) if (inPoly(poly, x, z)) return true;
  const R = [[x0, z0, x1, z0], [x1, z0, x1, z1], [x1, z1, x0, z1], [x0, z1, x0, z0]];
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) for (const r of R) if (segX(poly[j][0], poly[j][1], poly[i][0], poly[i][1], r[0], r[1], r[2], r[3])) return true;
  return false;
}

export function createCull({ model, scene, getBvh = () => null, canCull = () => true, enabled = true }) {
  const rooms = [...model.table.values()].filter(e => e.type === "room" && e.params?.polygon?.length >= 3);
  const NC = rooms.length + 1, OUTSIDE = rooms.length;
  if (rooms.length < 2 || NC > 30) return null;
  const R = rooms.map(e => {
    const poly = e.params.polygon, xs = poly.map(p => p[0]), zs = poly.map(p => p[1]);
    return { id: e.id, name: e.params.name || e.id, poly, floor: e.params.floor || 0, storey: e.params.storey, x0: Math.min(...xs), x1: Math.max(...xs), z0: Math.min(...zs), z1: Math.max(...zs) };
  });

  /* ---- the cell a point is in (strict), as model.roomAt does ---- */
  function cellAt(x, y, z) {
    let best = -1;
    for (let i = 0; i < R.length; i++) {
      const r = R[i];
      if (y < r.floor - 0.35 || y > r.floor + 2.7 || x < r.x0 || x > r.x1 || z < r.z0 || z > r.z1) continue;
      if (inPoly(r.poly, x, z) && (best < 0 || r.floor > R[best].floor)) best = i;
    }
    return best < 0 ? OUTSIDE : best;
  }
  function eyeCells(x, y, z) {
    let bits = 0, strict = false;
    const c = cellAt(x, y, z);
    if (c !== OUTSIDE) { bits |= 1 << c; strict = true; }
    for (let i = 0; i < R.length; i++) {            // a room whose plan the eye is within EYE_PAD of
      const r = R[i];
      if (y < r.floor - 0.35 || y > r.floor + 2.7) continue;
      if (rectTouchesPoly(x - EYE_PAD, z - EYE_PAD, x + EYE_PAD, z + EYE_PAD, r.poly)) bits |= 1 << i;
    }
    if (!strict) bits |= 1 << OUTSIDE;
    return bits;
  }

  /* ---- portals ---- */
  const portals = [];                                  // {a, b, c: [4 corners x,y,z], ctr}
  const addPortal = (a, b, corners) => {
    if (a === b) return;
    const ctr = [0, 1, 2].map(k => corners.reduce((s, p) => s + p[k], 0) / 4);
    portals.push({ a, b, corners, ctr });
  };
  for (const el of model.table.values()) {
    if (el.type !== "opening") continue;
    const w = model.table.get(el.params.host);
    if (!w || w.type !== "wall" || !w.params.start) continue;
    const [sx, sz] = w.params.start, [ex, ez] = w.params.end, len = Math.hypot(ex - sx, ez - sz);
    if (len < 1e-6) continue;
    const dx = (ex - sx) / len, dz = (ez - sz) / len, nx = -dz, nz = dx;
    const t0 = el.params.offset - 0.05, t1 = el.params.offset + el.params.width + 0.05;
    const y0 = (el.params.sill ?? 0) - 0.05, y1 = (el.params.head ?? 2.1) + 0.05;       // sill and head are heights above the datum, not above the storey
    const ax = sx + dx * t0, az = sz + dz * t0, bx = sx + dx * t1, bz = sz + dz * t1;
    const ym = (y0 + y1) / 2, mx = (ax + bx) / 2, mz = (az + bz) / 2;
    const side = sgn => { for (const d of [0.25, 0.5]) { const c = cellAt(mx + nx * d * sgn, ym, mz + nz * d * sgn); if (c !== OUTSIDE) return c; } return OUTSIDE; };
    addPortal(side(1), side(-1), [[ax, y0, az], [bx, y0, bz], [bx, y1, bz], [ax, y1, az]]);
  }
  let portalsOf = null;
  const indexPortals = () => { portalsOf = Array.from({ length: NC }, () => []); for (const p of portals) { portalsOf[p.a].push(p); portalsOf[p.b].push(p); } };
  indexPortals();

  /* holes in the walls that no opening element names (a knocked-through wall, an archway, a gap between wall pieces):
     along every room's plan edge, short horizontal rays cross the wall's thickness; a column where no wall-group part
     is hit is open, and a run of open columns is a portal to whatever cell is on the other side. Run once, at the first
     frame the culling is active (the last stage), so the visible parts are the finished ones. */
  const holes = { done: false, ms: 0, rays: 0, found: 0 };
  function findHoles() {
    holes.done = true;
    const bvh = getBvh();
    if (!bvh) return;
    const t0 = performance.now();
    const wall = new Uint8Array(model.parts.length);
    for (const p of model.parts) wall[p.index] = p.now.visible && /^wall|^foundation/.test(p.group) ? 1 : 0;
    const ray = new THREE.Ray(), STEP = 0.1, HS = [0.4, 1.1, 1.8];
    for (let ri = 0; ri < R.length; ri++) {
      const r = R[ri], poly = r.poly;
      for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const [ax, az] = poly[j], [bx, bz] = poly[i], len = Math.hypot(bx - ax, bz - az);
        if (len < 0.2) continue;
        const dx = (bx - ax) / len, dz = (bz - az) / len;
        let nx = -dz, nz = dx;
        if (inPoly(poly, (ax + bx) / 2 + nx * 0.1, (az + bz) / 2 + nz * 0.1)) { nx = -nx; nz = -nz; }
        let run = null;
        const flush = () => {
          if (!run) return;
          const t0r = Math.max(0, run.t0 - STEP), t1r = Math.min(len, run.t1 + STEP), y0 = Math.max(r.floor, run.y0 - 0.35), y1 = Math.min(r.floor + 2.6, run.y1 + 0.35);
          const mx = ax + dx * (t0r + t1r) / 2, mz = az + dz * (t0r + t1r) / 2, ym = (y0 + y1) / 2;
          let b = OUTSIDE;
          for (const d of [0.35, 0.7]) { const c = cellAt(mx + nx * d, ym, mz + nz * d); if (c !== OUTSIDE) { b = c; break; } }
          const c0 = [ax + dx * t0r, y0, az + dz * t0r], c1 = [ax + dx * t1r, y0, az + dz * t1r];
          addPortal(ri, b, [c0, c1, [c1[0], y1, c1[2]], [c0[0], y1, c0[2]]]); holes.found++;
          run = null;
        };
        for (let t = STEP / 2; t < len; t += STEP) {
          let y0 = 1e9, y1 = -1e9;
          for (const hh of HS) {
            ray.origin.set(ax + dx * t - nx * 0.02, r.floor + hh, az + dz * t - nz * 0.02); ray.direction.set(nx, 0, nz);
            holes.rays++;
            if (!bvh.raycast(ray, 0.7, wall)) { y0 = Math.min(y0, r.floor + hh); y1 = Math.max(y1, r.floor + hh); }
          }
          if (y1 < y0) { flush(); continue; }
          if (run) { run.t1 = t; run.y0 = Math.min(run.y0, y0); run.y1 = Math.max(run.y1, y1); } else run = { t0: t, t1: t, y0, y1 };
        }
        flush();
      }
    }
    /* the stairwell and any other void in a slab: rooms of different storeys that overlap in plan are joined where a
       vertical ray from just under the upper floor, through the slab, meets no floor / ceiling / joist part */
    const slab = new Uint8Array(model.parts.length);
    for (const p of model.parts) slab[p.index] = p.now.visible && /^slab|^joist|^ceiling_joist|^deck|^finish_skin|^timber_beam|^steel/.test(p.group) ? 1 : 0;
    const pairs = new Map();                            // "lo,hi" -> AABB of the open samples
    for (let i = 0; i < R.length; i++) {
      const lo = R[i];
      for (let x = lo.x0; x <= lo.x1 + 1e-6; x += 0.15) for (let z = lo.z0; z <= lo.z1 + 1e-6; z += 0.15) {
        if (!inPoly(lo.poly, x, z)) continue;
        let top = null;                                  // the nearest storey above: the slab to look through
        for (const hi of R) if (hi.floor > lo.floor + 1 && (!top || hi.floor < top)) top = hi.floor;
        if (top === null) continue;
        ray.origin.set(x, lo.floor + 1.0, z); ray.direction.set(0, 1, 0); holes.rays++;
        if (bvh.raycast(ray, top + 0.6 - (lo.floor + 1.0), slab)) continue;          // a ceiling is there
        for (let j = 0; j < R.length; j++) {
          const hi = R[j];
          if (hi.floor !== top || !rectTouchesPoly(x - 0.5, z - 0.5, x + 0.5, z + 0.5, hi.poly)) continue;
          const k = i + "," + j, a = pairs.get(k) || { i, j, y: hi.floor, x0: 1e9, x1: -1e9, z0: 1e9, z1: -1e9 };
          a.x0 = Math.min(a.x0, x); a.x1 = Math.max(a.x1, x); a.z0 = Math.min(a.z0, z); a.z1 = Math.max(a.z1, z); pairs.set(k, a);
        }
      }
    }
    const pd = 0.3;
    for (const a of pairs.values()) { addPortal(a.i, a.j, [[a.x0 - pd, a.y, a.z0 - pd], [a.x1 + pd, a.y, a.z0 - pd], [a.x1 + pd, a.y, a.z1 + pd], [a.x0 - pd, a.y, a.z1 + pd]]); holes.found++; }
    indexPortals();
    holes.ms = performance.now() - t0;
  }

  /* ---- cells of each part ---- */
  const bitsByBatch = new Map();                       // BatchedMesh -> Int32Array(instance -> cell bits)
  const ALL = (1 << NC) - 1;
  let exclusive = 0, shared = 0;
  const _bb = new THREE.Box3();
  function classify() {
    for (const p of model.parts) {
      if (!p.batch) continue;
      let arr = bitsByBatch.get(p.batch);
      if (!arr) { arr = new Int32Array(p.batch.maxInstanceCount).fill(ALL); bitsByBatch.set(p.batch, arr); }
      const b = p.bbox;
      let bits = 0;
      for (let i = 0; i < R.length && !bits; i++) {              // wholly inside one room's air
        const r = R[i];
        if (b.min.y < r.floor - 0.03 || b.max.y > r.floor + 2.55) continue;
        if (b.min.x < r.x0 || b.max.x > r.x1 || b.min.z < r.z0 || b.max.z > r.z1) continue;
        if (inPoly(r.poly, b.min.x, b.min.z) && inPoly(r.poly, b.max.x, b.min.z) && inPoly(r.poly, b.max.x, b.max.z) && inPoly(r.poly, b.min.x, b.max.z)) bits = 1 << i;
      }
      if (bits) exclusive++;
      else {
        shared++;
        bits = 1 << OUTSIDE;
        for (let i = 0; i < R.length; i++) {
          const r = R[i];
          if (b.max.y < r.floor - 0.6) continue;
          if (b.max.x < r.x0 - OUT_PAD || b.min.x > r.x1 + OUT_PAD || b.max.z < r.z0 - OUT_PAD || b.min.z > r.z1 + OUT_PAD) continue;
          if (rectTouchesPoly(b.min.x - OUT_PAD, b.min.z - OUT_PAD, b.max.x + OUT_PAD, b.max.z + OUT_PAD, r.poly)) bits |= 1 << i;
        }
      }
      arr[p.instanceId] = bits;
    }
  }
  classify();

  /* ---- visibility from the camera ---- */
  const state = { enabled, native: false, active: false, bits: -1, free: null, sets: null, cells: [], why: "", frames: 0, last: new Float32Array(128), lastN: 0 };
  const _f = new THREE.Frustum(), _m = new THREE.Matrix4(), _inv = new THREE.Matrix4(), _e = new THREE.Vector3();
  const planesOf = cam => {
    _inv.copy(cam.matrixWorld).invert();
    _m.multiplyMatrices(cam.projectionMatrix, _inv);
    _f.setFromProjectionMatrix(_m, cam.coordinateSystem, cam.reversedDepth);
    return _f.planes.map(pl => [pl.normal.x, pl.normal.y, pl.normal.z, pl.constant + SLACK]);
  };
  const outside = (corners, planes) => {
    for (const pl of planes) {
      let out = true;
      for (const c of corners) if (pl[0] * c[0] + pl[1] * c[1] + pl[2] * c[2] + pl[3] >= 0) { out = false; break; }
      if (out) return true;
    }
    return false;
  };
  function wedge(eye, corners, ctr) {
    const pls = [];
    for (let i = 0; i < 4; i++) {
      const a = corners[i], b = corners[(i + 1) % 4];
      const ux = a[0] - eye[0], uy = a[1] - eye[1], uz = a[2] - eye[2], vx = b[0] - eye[0], vy = b[1] - eye[1], vz = b[2] - eye[2];
      let nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      const l = Math.hypot(nx, ny, nz);
      if (l < 1e-9) continue;
      nx /= l; ny /= l; nz /= l;
      if (nx * (ctr[0] - eye[0]) + ny * (ctr[1] - eye[1]) + nz * (ctr[2] - eye[2]) < 0) { nx = -nx; ny = -ny; nz = -nz; }
      pls.push([nx, ny, nz, -(nx * eye[0] + ny * eye[1] + nz * eye[2]) + SLACK]);
    }
    return pls;
  }
  const nearRect = (eye, p) => {                      // is the eye within NEAR_PORTAL of the portal's box
    let mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
    for (const c of p.corners) for (let k = 0; k < 3; k++) { mn[k] = Math.min(mn[k], c[k]); mx[k] = Math.max(mx[k], c[k]); }
    for (let k = 0; k < 3; k++) if (eye[k] < mn[k] - NEAR_PORTAL || eye[k] > mx[k] + NEAR_PORTAL) return false;
    return true;
  };
  /* wedges: the planes of the portals crossed so far (empty: the cell is seen with the whole view). Every cell keeps the
     list of wedge sets it was reached by; an instance of that cell is drawn only if it is inside one of them. */
  const MAX_SETS = 8;
  function visit(c, planes, wedges, eye, depth, path, out) {
    out.bits |= 1 << c;
    if (!wedges.length) out.free[c] = 1;
    else if (!out.free[c]) { if (out.sets[c].length >= MAX_SETS) out.free[c] = 1; else out.sets[c].push(wedges); }
    if (depth >= MAX_DEPTH) return;
    for (const p of portalsOf[c]) {
      const o = p.a === c ? p.b : p.a;
      if (path & (1 << o)) continue;
      if (outside(p.corners, planes)) continue;
      if (nearRect(eye, p)) visit(o, planes, wedges, eye, depth + 1, path | (1 << c), out);
      else { const w = wedge(eye, p.corners, p.ctr); visit(o, planes.concat(w), wedges.concat(w), eye, depth + 1, path | (1 << c), out); }
    }
  }
  function compute(cams) {
    const out = { bits: 0, free: new Uint8Array(NC), sets: Array.from({ length: NC }, () => []) };
    for (const cam of cams) {
      _e.setFromMatrixPosition(cam.matrixWorld);
      const eye = [_e.x, _e.y, _e.z], planes = planesOf(cam), start = eyeCells(eye[0], eye[1], eye[2]);
      for (let c = 0; c < NC; c++) if (start & (1 << c)) visit(c, planes, [], eye, 0, 0, out);
    }
    state.free = out.free;
    state.sets = out.sets.map(list => list.map(w => { const a = new Float32Array(w.length * 4); w.forEach((pl, i) => a.set(pl, i * 4)); return a; }));
    return out.bits;
  }
  /* is a sphere (centre, radius) inside the wedge of any visible cell its instance belongs to */
  function seen(b, cx, cy, cz, r) {
    let m = b & state.bits;
    while (m) {
      const lb = m & -m, c = 31 - Math.clz32(lb);
      m ^= lb;
      if (state.free[c]) return true;
      const list = state.sets[c];
      for (let s = 0; s < list.length; s++) {
        const a = list[s];
        let ok = true;
        for (let k = 0; k < a.length; k += 4) if (a[k] * cx + a[k + 1] * cy + a[k + 2] * cz + a[k + 3] < -r) { ok = false; break; }
        if (ok) return true;
      }
    }
    return false;
  }

  const IDENT = new THREE.Matrix4(), sig = new Float32Array(128);
  const HIDDEN_LAYER = 30;
  const proto = THREE.BatchedMesh.prototype, orig = proto.onBeforeRender;
  const hooked = [], fr = new THREE.Frustum(), _mm = new THREE.Matrix4(), _sp = new THREE.Sphere();
  let dirty = 0;

  const frustumPlanes = cam => {                       // the batch's own frame is the world frame (checked: identity)
    _mm.multiplyMatrices(cam.projectionMatrix, cam.matrixWorldInverse);
    fr.setFromProjectionMatrix(_mm, cam.coordinateSystem, cam.reversedDepth);
    const a = new Float64Array(24);
    fr.planes.forEach((q, i) => { a[i * 4] = q.normal.x; a[i * 4 + 1] = q.normal.y; a[i * 4 + 2] = q.normal.z; a[i * 4 + 3] = q.constant; });
    return a;
  };
  /* the draw list of one batch for one eye: every active instance that is in a visible cell, inside that cell's wedge and inside the eye's frustum */
  function build(mesh, pl, buf) {
    const L = mesh._cull, bits = L.bits, cache = L.cache, valid = L.valid, info = mesh._instanceInfo, geo = mesh._geometryInfo;
    const act = state.active, vis = act ? state.bits : -1, bpe = L.bpe, starts = buf.starts, counts = buf.counts, ind = buf.ind;
    let n = 0,changed = false;
    for (let i = 0, l = info.length; i < l; i++) {
      const ii = info[i];
      if (!ii.visible || !ii.active || !(bits[i] & vis)) continue;
      const o = i * 4;
      if (!valid[i]) {
        mesh.getMatrixAt(i, _mm);
        mesh.getBoundingSphereAt(ii.geometryIndex, _sp).applyMatrix4(_mm);
        cache[o] = _sp.center.x; cache[o + 1] = _sp.center.y; cache[o + 2] = _sp.center.z; cache[o + 3] = _sp.radius; valid[i] = 1;
      }
      const cx = cache[o], cy = cache[o + 1], cz = cache[o + 2], r = -cache[o + 3];
      let culled = false;
      for (let k = 0; k < 24; k += 4) if (pl[k] * cx + pl[k + 1] * cy + pl[k + 2] * cz + pl[k + 3] < r) { culled = true; break; }
      if (culled) continue;
      if (act && !seen(bits[i], cx, cy, cz, -r)) continue;
      const g = geo[ii.geometryIndex];
      const start=g.start*bpe;
      if(ind[n]!==i||starts[n]!==start||counts[n]!==g.count)changed=true;
      starts[n]=start;counts[n]=g.count;ind[n]=i;n++;
    }
    if(changed||n!==buf.n)buf.stamp++;
    buf.n=n;
    return n;
  }
  const newBuf = L => ({ starts: new Int32Array(L.max), counts: new Int32Array(L.max), ind: new L.indCtor(L.max), n: 0, stamp: 0 });

  /* once per render (scene.onBeforeRender, after the XR eyes are placed): the cells, then every batch's list for every eye;
     a batch with nothing to draw in any eye is moved off the camera's layers for this render (no program set-up, no call).
     The shadow pass draws the whole house (onBeforeShadow below), so while a shadow update is pending nothing is hidden. */
  const looseCells=new WeakMap();
  const byRoom=new Map(R.map((r,i)=>[r.id,[r,1<<i]]));
  function looseCell(mesh){
    const version=mesh.instanceMatrix.version,cached=looseCells.get(mesh);
    if(cached?.version===version)return cached.bits;
    const room=byRoom.get(mesh.userData.furnishItems?.[0]?.room);
    let bits=0;
    if(room && mesh.matrixWorld.equals(IDENT)){
      const [r,bit]=room,{center:p,radius}=mesh.boundingSphere;
      if(p.y-radius>=r.floor-.03&&p.y+radius<=r.floor+2.55&&inPoly(r.poly,p.x,p.z)){
        // A dragged item may be anywhere, including across a concave room edge.
        const contained=r.poly.every(([x,z],i)=>{
          const b=r.poly[(i+1)%r.poly.length],dx=b[0]-x,dz=b[1]-z;
          const t=Math.max(0,Math.min(1,((p.x-x)*dx+(p.z-z)*dz)/(dx*dx+dz*dz||1)));
          return Math.hypot(p.x-x-dx*t,p.z-z-dz*t)>radius+.03;
        });
        if(contained)bits=bit;
      }
    }
    looseCells.set(mesh,{version,bits});return bits;
  }
  function cullFurniture(group,shadowNow){
    if(!group?.visible)return;
    for(const mesh of group.children){
      if(!mesh.visible||!mesh.boundingSphere||!mesh.isInstancedMesh)continue;
      const bit=state.active&&!shadowNow&&group.userData.portalCull!==false?looseCell(mesh):0;
      const {center:p,radius}=mesh.boundingSphere;
      mesh.layers.set(bit&&!seen(bit,p.x,p.y,p.z,radius)?HIDDEN_LAYER:0);
    }
  }
  function update(camera, renderer) {
    const cams = camera.isArrayCamera && camera.cameras.length ? camera.cameras : [camera];
    let n = 0, same = state.lastN === cams.length * 32;
    for (const cam of cams) {
      cam.matrixWorld.elements.forEach((v, k) => { if (k < 16) sig[n++] = v; });
      cam.projectionMatrix.elements.forEach(v => { sig[n++] = v; });
    }
    for (let k = 0; k < n && same; k++) if (sig[k] !== state.last[k]) same = false;
    const why = !state.enabled ? "off" : !model.root.matrixWorld.equals(IDENT) ? "house root is moved (planes are in world space)" : !canCull() ? "view could see through walls (stage, slice, x-ray or hidden storey)" : "";
    const cellsStale = !(same && why === state.why && state.frames > 0);
    if (cellsStale) {
      state.last.set(sig.subarray(0, n)); state.lastN = n; state.frames++;
      state.why = why;
      if (why) { state.active = false; state.bits = -1; state.cells = []; }
      else {
        if (!holes.done) findHoles();
        state.active = true;
        state.bits = compute(cams) | 0;
        state.cells = [];
        for (let c = 0; c < NC; c++) if (state.bits & (1 << c)) state.cells.push(c === OUTSIDE ? "outside" : R[c].name);
      }
    }
    const shadowNow = renderer?.shadowMap.enabled && renderer.shadowMap.needsUpdate;
    cullFurniture(scene.children.find(o=>o.userData.furnishRuntime),shadowNow);
    let vis = 0;
    for (const m of hooked) vis = (vis * 31 + (m.visible ? 1 : 0) + (m._cull.hidden ? 2 : 0)) | 0;
    if (!cellsStale && dirty === state.dirtySeen && vis === state.visSeen && !!shadowNow === state.shadowSeen && state.cams.length === cams.length && state.cams.every((c, i) => c === cams[i])) return state;
    state.dirtySeen = dirty; state.visSeen = vis; state.shadowSeen = !!shadowNow; state.cams = cams; state.ver++;
    const pls = cams.map(frustumPlanes), native = state.native || !model.root.matrixWorld.equals(IDENT);
    for (const mesh of hooked) {
      const L = mesh._cull;
      if (native || !mesh.visible && !L.hidden || mesh.sortObjects) { L.ver = -1; if (L.hidden) { mesh.layers.mask = L.layerMask; L.hidden = false; } continue; }
      let any = false;
      for (let e = 0; e < cams.length; e++) { const buf = L.bufs[e] || (L.bufs[e] = newBuf(L)); if (build(mesh, pls[e], buf)) any = true; }
      L.ver = state.ver;
      const hide = !any && !shadowNow;
      if (hide !== L.hidden) { if (hide) { L.layerMask = mesh.layers.mask; mesh.layers.set(HIDDEN_LAYER); } else mesh.layers.mask = L.layerMask; L.hidden = hide; }
    }
    return state;
  }
  state.lastN = -1; state.dirtySeen = -1; state.visSeen = 0; state.shadowSeen = false; state.cams = []; state.ver = 0;

  function hook(mesh) {
    const bits = bitsByBatch.get(mesh);
    if (!bits) return;
    const max = mesh.maxInstanceCount, L = mesh._cull = { bits, max, cache: new Float32Array(max * 4), valid: new Uint8Array(max), bufs: [], ver: -1, hidden: false, layerMask: mesh.layers.mask, up: null, upStamp: -1,
      indCtor: mesh._indirectTexture.image.data.constructor, bpe: (mesh.geometry.getIndex()?.array.BYTES_PER_ELEMENT) || 1 };
    const setM = mesh.setMatrixAt, setV = mesh.setVisibleAt;
    mesh.setMatrixAt = function (i, m) { L.valid[i] = 0; dirty++; return setM.call(this, i, m); };
    mesh.setVisibleAt = function (i, v) { dirty++; return setV.call(this, i, v); };
    mesh.onBeforeShadow = function (renderer, object, camera, shadowCamera, geometry, depthMaterial) { L.up=null;orig.call(this, renderer, null, shadowCamera, geometry, depthMaterial); };
    mesh.onBeforeRender = function (renderer, scene2, camera, geometry, material) {
      const e = state.cams.indexOf(camera);
      if (camera.isArrayCamera || this.sortObjects || state.native || material.wireframe || (e >= 0 && L.ver !== state.ver) || !this.matrixWorld.equals(IDENT)) {
        L.up=null;orig.call(this, renderer, scene2, camera, geometry, material);
        if (state.active && this.sortObjects && !state.native) {          // glass: three's list, then the cell test
          const ind = this._indirectTexture.image.data, st = this._multiDrawStarts, ct = this._multiDrawCounts, v = state.bits;
          let w = 0;
          for (let k = 0, n = this._multiDrawCount; k < n; k++) { const id = ind[k]; if (bits[id] & v) { st[w] = st[k]; ct[w] = ct[k]; ind[w] = id; w++; } }
          this._multiDrawCount = w;
        }
        return;
      }
      let buf;
      if (e >= 0) buf = L.bufs[e];
      else { buf = L.bufs[9] || (L.bufs[9] = newBuf(L)); build(this, frustumPlanes(camera), buf); }       // a camera update() did not see
      if(L.up!==buf||L.upStamp!==buf.stamp){
        this._multiDrawStarts.set(buf.starts.subarray(0,buf.n));this._multiDrawCounts.set(buf.counts.subarray(0,buf.n));
        this._indirectTexture.image.data.set(buf.ind.subarray(0,buf.n));this._indirectTexture.needsUpdate=true;
        L.up=buf;L.upStamp=buf.stamp;
      }
      this._multiDrawCount=buf.n;
      this._visibilityChanged = false;
    };
    hooked.push(mesh);
  }
  for (const b of bitsByBatch.keys()) hook(b);

  return {
    state, update, holes, prepare() { if (!holes.done && state.enabled && canCull()) { model.root.updateMatrixWorld(true); findHoles(); } }, cells: R.map(r => r.name), get portals() { return portals.length; }, portalList: () => portals, exclusive, shared,
    get enabled() { return state.enabled; }, set enabled(v) { state.enabled = !!v; state.frames = 0; },
    portalInfo: () => portals.map(p => [p.a === OUTSIDE ? "outside" : R[p.a].name, p.b === OUTSIDE ? "outside" : R[p.b].name]),
    bitsByBatch, R, OUTSIDE,
  };
}
