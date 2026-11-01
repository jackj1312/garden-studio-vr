import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  Where targets may appear in a level, found with the house's BVH.
 *
 *  A grid over the level's rooms is dropped straight down from below
 *  the ceiling; whatever flat face it lands on first is a spot:
 *    floor   the floor itself (clear of walls by 28 cm, 1 m headroom)
 *    ledge   something to stand a target on: a worktop, the sofa, a
 *            bed, a stair tread, a window sill outside (20 cm-1.9 m up,
 *            wide enough, clear above)
 *    air     open floor with room to float a balloon at head height
 *  plus, from the elements file:
 *    window  just inside (or outside, in the garden) each window
 *    door    each doorway, for robots peeking round the frame
 *  Nothing is ever inside a wall: every spot is a real surface the ray
 *  reached, checked clear around it. Line of sight from the player is
 *  checked when a target is placed (visible()).
 * ------------------------------------------------------------------ */

export function inPoly(x, z, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) inside = !inside;
  }
  return inside;
}

const DIRS8 = [...Array(8)].map((_, i) => new THREE.Vector3(Math.cos(i * Math.PI / 4), 0, Math.sin(i * Math.PI / 4)));

export function createSpotFinder(getBVH, rayMask) {
  const ray = new THREE.Ray();
  const v = new THREE.Vector3();

  function cast(o, d, far) { ray.origin.copy(o); ray.direction.copy(d); return getBVH().raycast(ray, far, rayMask()); }
  function clearRing(p, h, r) {
    const o = v.set(p.x, p.y + h, p.z).clone();
    for (const d of DIRS8) if (cast(o, d, r)) return false;
    return true;
  }
  function headroom(p, need) { return !cast(new THREE.Vector3(p.x, p.y + 0.03, p.z), new THREE.Vector3(0, 1, 0), need); }

  /* can `from` see `to`? (the target's own centre; a little slack so the target's surface doesn't count) */
  function visible(from, to, slack = 0.15) {
    const d = v.subVectors(to, from).length();
    if (d < 1e-3) return true;
    ray.origin.copy(from); ray.direction.copy(v).divideScalar(d);
    return !getBVH().raycast(ray, Math.max(0.01, d - slack), rayMask());
  }

  /* how far you can see from `from` along `dir` (up to far) */
  function freeDistance(from, dir, far) { const h = cast(from, dir, far); return h ? h.distance : far; }

  function find(level, house) {
    const zones = [];
    const want = new Set(level.rooms.map(n => n.toLowerCase()));
    for (const r of house.rooms) if (want.has(String(r.name).toLowerCase())) zones.push({ poly: r.poly, floor: r.floor, storey: r.storey });
    for (const e of level.extra || []) zones.push(e);
    const out = { floor: [], ledge: [], air: [], window: [], door: [], zones };
    const down = new Vector3Down();
    for (const z of zones) {
      const xs = z.poly.map(p => p[0]), zs = z.poly.map(p => p[1]);
      const step = z.outside ? 0.45 : 0.3;
      const x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs);
      for (let x = x0 + step / 2; x < x1; x += step) for (let zz = z0 + step / 2; zz < z1; zz += step) {
        const jx = x + (Math.random() - 0.5) * step * 0.4, jz = zz + (Math.random() - 0.5) * step * 0.4;
        if (!inPoly(jx, jz, z.poly)) continue;
        const top = z.floor + (z.outside ? 2.3 : 2.05);
        const hit = cast(new THREE.Vector3(jx, top, jz), down, top - z.floor + 0.8);
        if (!hit || hit.normal.y < 0.8) continue;
        const p = hit.point.clone();
        const h = p.y - z.floor;
        const flat = Math.abs(h) < (z.outside ? 0.45 : 0.12);
        if (flat) {
          if (!clearRing(p, 0.3, 0.28) || !headroom(p, 1.0)) continue;
          const s = { p, floor: z.floor, kind: "floor", outside: !!z.outside };
          out.floor.push(s);
          if (clearRing(p, 1.45, 0.42) && headroom(p, z.outside ? 2.2 : 1.9)) out.air.push({ ...s, kind: "air" });
        } else if (h > 0.18 && h < 1.9) {
          if (!clearRing(p, 0.22, 0.16) || !headroom(p, 0.55)) continue;
          // wide enough: the surface carries on 10 cm each way
          let wide = true;
          for (const [dx, dz] of [[0.1, 0], [-0.1, 0], [0, 0.1], [0, -0.1]]) {
            const hh = cast(new THREE.Vector3(p.x + dx, p.y + 0.3, p.z + dz), down, 0.4);
            if (!hh || Math.abs(hh.point.y - p.y) > 0.04) { wide = false; break; }
          }
          if (wide) out.ledge.push({ p, floor: z.floor, kind: "ledge", h, outside: !!z.outside });
        }
      }
    }
    // windows and doorways that belong to this level's zones
    const nearZone = (x, z, pad) => zones.find(zn => inPoly(x, z, zn.poly) || [[pad, 0], [-pad, 0], [0, pad], [0, -pad]].some(([a, b]) => inPoly(x + a, z + b, zn.poly)));
    for (const o of house.openings) {
      const zn = nearZone(o.centre.x, o.centre.z, 0.45);
      if (!zn) continue;
      if (o.kind === "window") {
        for (const sgn of [1, -1]) {
          const q = o.centre.clone().addScaledVector(o.normal, sgn * 0.45);
          const inside = zones.find(z2 => inPoly(q.x, q.z, z2.poly));
          if (!inside) continue;
          q.y = o.floor + Math.min(o.sill + 0.35, o.head - 0.25);
          if (!clearRing(q, 0, 0.2)) continue;
          out.window.push({ p: q, floor: o.floor, kind: "window", normal: o.normal.clone().multiplyScalar(sgn), outside: !!inside.outside });
          break;
        }
      } else if (!zn.outside) {
        out.door.push({ p: o.centre.clone(), floor: o.floor, kind: "door", normal: o.normal.clone(), tangent: o.tangent.clone(), width: o.width });
      }
    }
    console.info(`game: ${level.id} spots`, Object.fromEntries(Object.entries(out).filter(([k]) => k !== "zones").map(([k, a]) => [k, a.length])));
    return out;
  }

  return { find, visible, freeDistance, clearRing, cast };
}

class Vector3Down extends THREE.Vector3 { constructor() { super(0, -1, 0); } }
