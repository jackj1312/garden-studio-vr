import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  Walking at true scale through what is built NOW.
 *
 *  Collision is the collide:true parts of the current stage (the
 *  model's `solid` mask): a wall not built yet doesn't stop you, a
 *  demolished one stops stopping you once it has come out; a closed
 *  door stops you, an open one doesn't. Body: an 18 cm radius (a person turning slightly sideways; was 25 cm, CORRECTIONS-LOG 298), probed
 *  by horizontal rays at knee, waist, chest and head height; the move
 *  slides along whatever it meets.
 *
 *  Feet: a ray down from step height finds the floor, so a 150 mm slab
 *  edge or a 220 mm stair riser is stepped up. The floor under you is
 *  read across a FOOTPRINT, not one point: the centre first, and when
 *  the centre is over a gap (the 115 mm between the top nosing and the
 *  landing at 23 Battle Road, a joint between two slabs) the nearest
 *  floor under the footprint carries you. A drop of more than 60 cm
 *  (a trench, a stairwell, the edge of an unfinished deck) is refused
 *  when you walk; when the head steps there in the headset you only go
 *  down once the whole footprint is over the drop; with nothing at all
 *  under you, you stay on the last good floor (round 6: the feet used
 *  to sink to the ground at y 0 whenever the floor ray found nothing,
 *  and fell 2.4 m through the gap at the stair top).
 * ------------------------------------------------------------------ */

/* foot: the sole (a 12 cm ring: you stand on the highest floor under it, so a gap narrower than ~24 cm — the
   stair-top gap, a doorway with no floor of its own — is stepped over); edge: the 22 cm ring that keeps you on a
   floor edge until you are clearly over a drop */
export const BODY = { radius: 0.18, step: 0.36, dropGuard: 0.6, foot: 0.12, edge: 0.22, heights: [0.5, 1.0, 1.45, 1.8] };
const DIRS = [...Array(8)].map((_, i) => new THREE.Vector3(Math.cos(i * Math.PI / 4), 0, Math.sin(i * Math.PI / 4)));
const SOLE = DIRS.map(d => [d.x * BODY.foot, d.z * BODY.foot]);
const EDGE = DIRS.map(d => [d.x * BODY.edge, d.z * BODY.edge]);

export function createWalker(getBVH, getMask, getFloorMask = getMask, proposal = null) {
  const ray = new THREE.Ray();
  const dir = new THREE.Vector3(), n = new THREE.Vector3(), rem = new THREE.Vector3();

  /* body probes along d. Going DOWN a stair the head is over the lower tread by the time it gets there, so the
     chest and head probes are measured from the lower of the feet and the floor a body radius ahead (else the
     stairwell's edge above the flight stops you, as it did at 23 Battle Road with the 1.8 m probe) */
  function castH(pos, d, far) {
    const bvh = getBVH(), mask = getMask();
    let best = null;
    const ahead = floorRay(pos.x + d.x * BODY.radius, pos.y, pos.z + d.z * BODY.radius, BODY.dropGuard);
    const low = ahead !== null && ahead < pos.y ? ahead : pos.y;
    for (const h of BODY.heights) {
      ray.origin.set(pos.x, (h > 1.2 ? low : pos.y) + h, pos.z);
      ray.direction.copy(d);
      const house = bvh.raycast(ray, far, mask);
      const added = proposal?.barrier(ray, far);
      const hit = added && (!house || added.distance < house.distance) ? added : house;
      if (hit && Math.abs(hit.normal.y) < 0.7 && (!best || hit.distance < best.distance))
        best = { distance: hit.distance, normal: hit.normal.clone() };
    }
    return best;
  }

  /* the first walkable floor under (x, z) from step height above feet y: a near-flat FRONT face (the top of
     something). Back faces (the inside of a tread or slab the ray starts in) are skipped by the tree; a steep
     face (a stringer's sloped top, a roof) is looked past. null = nothing within reach. */
  function floorRay(x, y, z, reach) {
    const level = proposal?.height(x, z);
    if (level != null && !proposal.indoors(x,y,z) && y < Math.max(level, proposal.base(x, z) ?? level) + 1.2)
      return level <= y + BODY.step + .005 && level >= y - reach ? level : null;
    const bvh = getBVH(), mask = getFloorMask();
    ray.origin.set(x, y + BODY.step, z);
    ray.direction.set(0, -1, 0);
    let left = BODY.step + reach;
    for (let k = 0; k < 4 && left > 0; k++) {
      const hit = bvh.raycast(ray, left, mask, null, true);
      if (!hit) return null;
      if (hit.normal.y >= 0.5) return hit.point.y;
      left -= hit.distance + 1e-3;
      ray.origin.y = hit.point.y - 1e-3;
    }
    return null;
  }

  /* the floor under the centre (x, z) for feet at y, or null (kept for the rules and the tools) */
  function floorAt(x, y, z, reach = 8) { return floorRay(x, y, z, reach); }

  /* the floor that carries feet at (x, y, z): the highest floor under the sole (centre + 12 cm ring) when it is
     within the drop guard; else the floor under the 22 cm edge ring nearest the feet; else the centre's (a real
     drop: the whole footprint is over it) or null (nothing at all) */
  function supportAt(x, y, z, reach = 8) {
    const c = floorRay(x, y, z, reach);
    let best = c !== null && c >= y - BODY.dropGuard ? c : null;
    if (best === null || best < y - 0.02) {                   // the centre is lower than the feet: is it a gap or a step down?
      for (const [dx, dz] of SOLE) {
        const f = floorRay(x + dx, y, z + dz, BODY.dropGuard + 0.05);
        if (f !== null && f >= y - BODY.dropGuard && (best === null || f > best)) best = f;
      }
    }
    if (best !== null) return best;
    for (const [dx, dz] of EDGE) {
      const f = floorRay(x + dx, y, z + dz, BODY.dropGuard + 0.05);
      if (f !== null && f >= y - BODY.dropGuard && (best === null || Math.abs(f - y) < Math.abs(best - y))) best = f;
    }
    return best !== null ? best : c;
  }

  /* move feet `pos` (Vector3, modified) by horizontal `delta`; returns pos */
  function move(pos, delta) {
    const start = pos.clone();
    const floor0 = supportAt(pos.x, pos.y, pos.z);
    rem.copy(delta);
    for (let it = 0; it < 3; it++) {
      const len = rem.length();
      if (len < 1e-6) break;
      dir.copy(rem).divideScalar(len);
      const hit = castH(pos, dir, len + BODY.radius);
      if (!hit) { pos.add(rem); break; }
      const allowed = Math.max(0, hit.distance - BODY.radius);
      pos.addScaledVector(dir, allowed);
      rem.multiplyScalar(1 - allowed / len);
      n.set(hit.normal.x, 0, hit.normal.z).normalize();
      rem.addScaledVector(n, -rem.dot(n));           // slide along the face
    }
    // push out of anything closer than the body radius (corners, thin posts)
    for (const d of DIRS) {
      const h = castH(pos, d, BODY.radius);
      if (h && h.distance < BODY.radius) pos.addScaledVector(d, -(BODY.radius - h.distance) * 0.9);
    }
    // floor: step up; refuse a big drop, and refuse walking off the edge of everything
    const f = supportAt(pos.x, pos.y, pos.z);
    if (floor0 !== null && (f === null || f < floor0 - BODY.dropGuard)) { pos.copy(start); return pos; }
    return pos;
  }

  /* vertical settle each frame: onto the floor that carries the feet; nothing under them = stay put */
  function settle(pos, dt) {
    const f = supportAt(pos.x, pos.y, pos.z);
    if (f === null) return pos;                                // past the edge of everything: keep the last good floor
    if (f > pos.y) pos.y = f;                                   // step up at once (no sinking into the stair)
    else pos.y += (f - pos.y) * Math.min(1, dt * 9);            // a short drop eases down
    return pos;
  }

  /* clear of every wall by the body radius at (feet) pos? */
  function free(pos) {
    for (const d of DIRS) { const h = castH(pos, d, BODY.radius); if (h && h.distance < BODY.radius * 0.98) return false; }
    return true;
  }

  /* where a flight ends: the floor under the feet from any height (reach 80 m), nudged out of a wall when the
     release was inside one (rings out to 2 m), else the ground. Returns the new feet {x, y, z} (not applied). */
  function landing(pos, ground = 0) {
    const at = (x, z) => { const f = floorRay(x, pos.y, z, 80); return f === null ? null : new THREE.Vector3(x, f, z); };
    const here = at(pos.x, pos.z);
    if (here && free(here)) return here;
    for (let r = 0.15; r <= 2.0; r += 0.15) {
      for (let i = 0; i < 16; i++) {
        const a = i / 16 * Math.PI * 2;
        const p = at(pos.x + Math.cos(a) * r, pos.z + Math.sin(a) * r);
        if (p && free(p)) return p;
      }
    }
    return here || new THREE.Vector3(pos.x, Math.min(pos.y, ground), pos.z);
  }

  return { move, settle, floorAt, supportAt, free, landing, castH };
}
