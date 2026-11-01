import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  Doors that open. Every door leaf of a version swings on its hinge
 *  (or slides, or folds) over 0.6 s when you point at it and pull the
 *  trigger, or all at once from the board. A closed leaf blocks the
 *  walk; an open one does not (the model's `passable` flag takes it
 *  out of the solid mask). A leaf only opens at stages where it is
 *  built.
 *
 *  The generator writes on each leaf node (CONTRACT.md section 3):
 *    part: "leaf", door_leaf: true, hinge: [x, y, z] (viewer frame, a
 *    point on the hinge axis), hinge_axis: [0, 1, 0], swing_deg (the
 *    open angle, signed: + = counter-clockwise seen from above),
 *    optional slide: [x, y, z], door_group (leaves of one door share
 *    it), leaf_index, swing_conf / swing_note (shown on the board).
 *    A leaf with a hinge AND a slide (a bi-fold leaf) turns on its
 *    hinge and is carried by the slide: pose = T(slide k) R(swing k).
 *    A door's glass (part "leaf_glass", door_leaf: true) moves with its
 *    leaf; it borrows the leaf's hinge when it has none of its own.
 *    Window glass is part "glass" and never a door.
 *  A leaf without them gets a DERIVED hinge (reported in `derived`):
 *  the vertical edge of its box on the side nearer a wall corner,
 *  swung 90 degrees into the room (not the hall or landing; inside
 *  rather than out), and a bi-fold folds to 15 % of its width there.
 * ------------------------------------------------------------------ */

const DUR = 0.6;
const ease = t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
const UP = new THREE.Vector3(0, 1, 0);

/* is this part a door leaf? */
export const isLeaf = p => p.ud.part !== "glass" && (p.ud.door_leaf === true || (p.ud.part === "leaf" && p.group === "door") || (p.group === "door" && /_leaf$/i.test(p.name)));

export function createDoors({ model, bvh, roomAt, table }) {
  const leaves = model.parts.filter(isLeaf);
  const doors = new Map();                   // door_group -> {id, leaves: [{part, kind, hinge, axis, angle, slide, fold}], t, target}
  const derived = [];
  const ray = new THREE.Ray();

  /* free distance from p along d at mid height, against what is solid when the house is finished */
  const finalMask = model.finalMask();
  function free(p, d, far = 3) {
    ray.origin.copy(p); ray.direction.copy(d);
    const h = bvh.raycast(ray, far, finalMask);
    return h ? h.distance : far;
  }
  const covered = p => { ray.origin.copy(p); ray.direction.set(0, 1, 0); return !!bvh.raycast(ray, 4, finalMask); };

  function derive(p) {
    const b = p.bbox, c = b.getCenter(new THREE.Vector3()), s = b.getSize(new THREE.Vector3());
    const alongX = s.x >= s.z;                                   // the leaf's width runs along x or z
    const t = alongX ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 0, 1);
    const n = alongX ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(1, 0, 0);
    const w = alongX ? s.x : s.z, half = w / 2, th = (alongX ? s.z : s.x) / 2;
    const mid = c.clone(); mid.y = b.min.y + Math.min(1.0, s.y / 2);
    /* which side it opens to: a room that is not the hall / landing, under a roof, with room for the leaf */
    const side = [1, -1].map(k => {
      const q = mid.clone().addScaledVector(n, k * (th + 0.45));
      const room = roomAt?.(q.x, b.min.y + 0.05, q.z)?.params?.name || "";
      return { k, score: (room && !/hall|landing|porch/i.test(room) ? 2 : 0) + (covered(q) ? 1 : 0) + Math.min(1, free(mid.clone().addScaledVector(n, k * (th + 0.02)), n.clone().multiplyScalar(k)) / w) * 0.5, room };
    }).sort((a, b2) => b2.score - a.score)[0];
    const inward = n.clone().multiplyScalar(side.k);
    /* which end is hinged: the one nearer a wall corner (the door then opens back against that wall) */
    const probe = mid.clone().addScaledVector(inward, th + 0.3);
    const dA = free(probe.clone().addScaledVector(t, -half), t.clone().negate());
    const dB = free(probe.clone().addScaledVector(t, half), t);
    const e = dA <= dB ? -1 : 1;
    const hinge = c.clone().addScaledVector(t, e * half); hinge.y = b.min.y;
    const free_end = t.clone().multiplyScalar(-e);                 // hinge -> free end
    const sign = new THREE.Vector3().crossVectors(UP, free_end).dot(inward) > 0 ? 1 : -1;
    const bifold = /bi-?fold/i.test(`${p.name} ${p.ud.label || ""} ${table?.get(p.element)?.params?.catalogue || ""}`);
    derived.push({ part: p.name, hinge: hinge.toArray().map(v => +v.toFixed(3)), swing_deg: bifold ? null : 90 * sign, fold: bifold, into: side.room || (side.k > 0 ? "+n" : "-n") });
    return bifold ? { kind: "fold", hinge, t, keep: 0.15 } : { kind: "swing", hinge, axis: UP.clone(), angle: THREE.MathUtils.degToRad(90 * sign) };
  }

  /* a leaf's own extras: a hinge + swing (with an optional slide carrying it), a slide alone, or nothing */
  const own = u => {
    const slide = Array.isArray(u.slide) ? new THREE.Vector3().fromArray(u.slide) : null;
    if (Array.isArray(u.hinge) && u.swing_deg !== undefined) return { kind: "swing", hinge: new THREE.Vector3().fromArray(u.hinge),
      axis: new THREE.Vector3().fromArray(u.hinge_axis || [0, 1, 0]).normalize(), angle: THREE.MathUtils.degToRad(Number(u.swing_deg) || 0), slide };
    return slide ? { kind: "slide", slide } : null;
  };
  const leafKey = p => `${p.ud.door_group || p.element}|${p.ud.leaf_index ?? 0}`;
  const byLeaf = new Map();
  for (const p of leaves) if (p.ud.part !== "leaf_glass" && own(p.ud)) byLeaf.set(leafKey(p), own(p.ud));
  for (const p of leaves) {
    const u = p.ud;
    const how = own(u) || byLeaf.get(leafKey(p)) || derive(p);
    const id = u.door_group || p.element;
    if (!doors.has(id)) doors.set(id, { id, leaves: [], t: 0, target: 0 });
    doors.get(id).leaves.push({ part: p, ...how });
    p.collide = true;                       // a closed leaf blocks the walk, whatever its extras say
    p.pose = null;
  }
  const byPart = new Map();
  for (const d of doors.values()) for (const l of d.leaves) byPart.set(l.part, d);

  const _m = new THREE.Matrix4(), _a = new THREE.Matrix4(), _b = new THREE.Matrix4();
  function poseOf(l, k) {
    if (k <= 0) return null;
    if (l.kind === "slide") return _m.makeTranslation(l.slide.x * k, l.slide.y * k, l.slide.z * k).clone();
    if (l.kind === "swing" && l.slide) {                     // a bi-fold leaf: turned on its hinge, carried along by the slide
      _m.makeRotationAxis(l.axis, l.angle * k);
      const R = _a.makeTranslation(l.hinge.x, l.hinge.y, l.hinge.z).multiply(_m).multiply(_b.makeTranslation(-l.hinge.x, -l.hinge.y, -l.hinge.z));
      return new THREE.Matrix4().makeTranslation(l.slide.x * k, l.slide.y * k, l.slide.z * k).multiply(R);
    }
    if (l.kind === "fold") {                                   // squeeze the leaf stack towards its hinge end
      const s = 1 - (1 - l.keep) * k;
      const S = new THREE.Matrix4().makeScale(l.t.x ? s : 1, 1, l.t.z ? s : 1);
      return _a.makeTranslation(l.hinge.x, l.hinge.y, l.hinge.z).multiply(S).multiply(_b.makeTranslation(-l.hinge.x, -l.hinge.y, -l.hinge.z)).clone();
    }
    _m.makeRotationAxis(l.axis, l.angle * k);
    return _a.makeTranslation(l.hinge.x, l.hinge.y, l.hinge.z).multiply(_m).multiply(_b.makeTranslation(-l.hinge.x, -l.hinge.y, -l.hinge.z)).clone();
  }
  function place(d) {
    const k = ease(d.t);
    for (const l of d.leaves) {
      l.part.pose = poseOf(l, k);
      l.part.passable = d.t > 0.35;            // open far enough to walk through
      model.repose(l.part);
    }
  }
  const moving = new Set();
  const built = d => d.leaves.some(l => l.part.now.present && !l.part.hidden);

  function set(d, open) {
    if (!d || !built(d)) return false;
    d.target = open ? 1 : 0;
    if (d.t !== d.target) moving.add(d);
    return true;
  }
  return {
    doors, derived, count: doors.size,
    doorOf: p => p && byPart.get(p) || null,
    /* what the generator says about a door's swing (swing_conf, swing_note), for the board */
    swingInfo(d) { const u = d.leaves.find(l => l.part.ud.swing_conf || l.part.ud.swing_note)?.part.ud || d.leaves[0].part.ud;
      return { deg: u.swing_deg, conf: u.swing_conf || null, note: u.swing_note || null, leaves: new Set(d.leaves.map(l => l.part.ud.leaf_index ?? 0)).size, slide: d.leaves.some(l => l.slide) }; },
    isOpen: d => d.target > 0.5,
    toggle(p) { const d = byPart.get(p); return set(d, !(d?.target > 0.5)) ? d.target > 0.5 : null; },
    setAll(open) { let n = 0; for (const d of doors.values()) if (set(d, open)) n++; return n; },
    /* at once, no animation (tests) */
    snapAll(open) { let n = 0; for (const d of doors.values()) if (built(d)) { d.t = d.target = open ? 1 : 0; moving.delete(d); place(d); n++; } return n; },
    get anyOpen() { for (const d of doors.values()) if (d.target > 0.5) return true; return false; },
    get moving() { return moving.size > 0; },
    /* every frame: animate the doors on their way (cheap: a handful of matrices) */
    update(dt) {
      for (const d of moving) {
        d.t = d.target > d.t ? Math.min(d.target, d.t + dt / DUR) : Math.max(d.target, d.t - dt / DUR);
        place(d);
        if (d.t === d.target) moving.delete(d);
      }
    },
    /* after a stage change: a leaf that is not built yet is shut (and re-posed when the batch matrices were reset) */
    restage() {
      for (const d of doors.values()) {
        if (!built(d) && d.t > 0) { d.t = d.target = 0; moving.delete(d); }
        place(d);
      }
    },
    /* the open leaves' current boxes, for picking a door that has swung away from its BVH (rest) triangles */
    pick(rayIn, far) {
      let best = null;
      const inv = new THREE.Matrix4(), r = new THREE.Ray(), pt = new THREE.Vector3();
      for (const d of doors.values()) if (d.t > 0) for (const l of d.leaves) {
        const p = l.part;
        if (!p.now.visible || !p.pose) continue;
        inv.copy(p.pose).invert();
        r.copy(rayIn).applyMatrix4(inv);
        const box = p.bbox;
        if (!r.intersectBox(box, pt)) continue;
        pt.applyMatrix4(p.pose);
        const dist = pt.distanceTo(rayIn.origin);
        if (dist < far && (!best || dist < best.distance)) best = { distance: dist, point: pt.clone(), part: p.index, normal: new THREE.Vector3().copy(rayIn.direction).negate(), door: true };
      }
      return best;
    },
  };
}
