/* Live checks in the room view (soft warnings, never blocking):
 *   overlap      two floor-standing pieces occupy the same floor;
 *   door         a piece sits in a door leaf's swing;
 *   outside      a piece sticks out of its room;
 *   clearance    not enough free floor in front of doors / drawers to open them (wall or another piece in the way);
 *   floating     something meant to sit on a surface has nothing under it.
 * fitsAt() runs the same tests for a candidate swap at the item's place. */
import { convexOverlap, insideFraction, pointInPoly, footprint, axes, add2, scale2, mm } from "./util.js?v=p7";
import { sizeM, itemFootprint, mountOf, slotOf, entryOf, shapeOf } from "./data.js?v=p7";

const SOLID_SKIP = new Set(["rug", "cushion", "throw", "towels", "window_dressing", "fixed", "downlights", "pendant", "ceiling_light",
                            "art", "mirror", "wall_light", "tv", "kitchen_small", "vase", "bowl", "books", "candles", "photo_frame",
                            "hooks", "mirror_cabinet", "towel_rail", "table_lamp", "plant_small", "clock", "kitchen_wall_units"]);
/* what opens at the front, and how much floor it needs (m) */
function frontNeed(slot, it) {
  const [W, D] = sizeM(it), t = (it.type || "").toLowerCase();
  if (slot === "wardrobe") return /sliding|rail|built-in/.test(t) ? 0 : Math.min(W / 2, 0.6) + 0.05;
  if (slot === "chest" || slot === "bedside" || slot === "desk") return /drawer|chest|dresser|bedside/.test(t + slot) ? D * 0.85 : 0;
  if (slot === "kitchen_unit") return /tall|housing|broom|fridge/.test(t) ? 0.65 : /dishwasher/.test(t) ? 0.65 : 0.55;
  if (slot === "island") return 0.55;
  if (slot === "bookcase" && /cupboard|door/.test(t)) return Math.min(W / 2, 0.5);
  if (slot === "appliance" && /wash|dryer|oven/.test(t)) return 0.6;
  return 0;
}
const isFloorSolid = (db, it, room) => {
  const slot = slotOf(db, it), m = mountOf(db, it);
  if (SOLID_SKIP.has(slot) || m === "ceiling" || m === "wall" || m === "window") return false;
  const y = it.position_m[1] - (room?.floor ?? 0);
  if (y > 0.3) return false;                  // on a surface or wall-hung
  return it.size_mm[2] > 120;
};

/* a chair pushed under a table, a basket on a bookcase's bottom shelf: not a clash */
const UNDER = new Set(["table", "kitchen_unit", "cabinet", "bench", "desk"]);
function tucked(db, a, b) {
  const sa = shapeOf(db, a), sb = shapeOf(db, b);
  if ((sa === "chair" || sa === "stool") && UNDER.has(sb)) return true;
  if ((sb === "chair" || sb === "stool") && UNDER.has(sa)) return true;
  const [small, big] = a.size_mm[0] * a.size_mm[1] < b.size_mm[0] * b.size_mm[1] ? [a, b] : [b, a];
  if (small.size_mm[2] < big.size_mm[2] * 0.5 && insideFraction(itemFootprint(small), itemFootprint(big), 0.02) > 0.99) return true;
  return false;
}

/* door swing sectors of a storey, as convex polygons */
export function swingPolys(house, storey) {
  const out = [];
  for (const o of house.openings) {
    if (o.storey !== storey) continue;
    for (const l of o.leaves) {
      if (l.bifold || !l.radius) continue;
      const pts = [l.hinge];
      const a = Math.atan2(l.free[1] - l.hinge[1], l.free[0] - l.hinge[0]);
      const steps = 6;
      for (let k = 0; k <= steps; k++) {
        const t = (-l.swing * Math.PI / 180) * (k / steps);   // rot() convention: +deg = (x cos + z sin, -x sin + z cos)
        pts.push([l.hinge[0] + l.radius * Math.cos(a + t), l.hinge[1] + l.radius * Math.sin(a + t)]);
      }
      out.push({ opening: o, leaf: l, poly: pts });
    }
  }
  return out;
}

export function checkRoom(db, state, roomId) {
  const room = state.house.roomById.get(roomId);
  const warn = new Map();
  if (!room) return warn;
  const push = (id, w) => (warn.get(id) || warn.set(id, []).get(id)).push(w);
  const all = [...state.items.values()].filter(it => state.house.roomById.get(it.room)?.storey === room.storey);
  const mine = all.filter(it => it.room === roomId);
  const solids = all.filter(it => isFloorSolid(db, it, state.house.roomById.get(it.room)));
  const swings = swingPolys(state.house, room.storey);
  for (const it of mine) {
    if (!it.size_mm[0] || !it.size_mm[1]) continue;
    const fp = itemFootprint(it);
    const solid = isFloorSolid(db, it, room);
    const slot = slotOf(db, it);
    /* outside the room */
    const mnt = mountOf(db, it);
    if (!["window_dressing", "fixed", "cushion", "throw", "towels"].includes(slot)) {
      const f = insideFraction(itemFootprint(it, sizeM(it).map((v, i) => (i < 2 ? Math.max(0.02, v - 0.04) : v))), room.polygon, 0.03);
      const limit = mnt === "wall" || mnt === "surface" ? 0.5 : 0.999;      // wall pieces sit on the wall line
      if (f < limit) push(it.id, { kind: "outside", text: f < 0.5 ? "Mostly outside the room" : "Sticks out of the room (through a wall)" });
    }
    if (solid) {
      for (const o of solids) {
        if (o.id === it.id || tucked(db, it, o)) continue;
        const d = convexOverlap(fp, itemFootprint(o));
        if (d > 0.015) push(it.id, { kind: "overlap", text: `Overlaps #${o.num} ${o.type} by ${mm(d)} mm`, other: o.id });
      }
      for (const sw of swings) {
        const d = convexOverlap(fp, sw.poly);
        if (d > 0.02) push(it.id, { kind: "door", text: `In the swing of the ${sw.opening.label}`, opening: sw.opening.id });
      }
    }
    const need = frontNeed(slot, it);
    if (need > 0) {
      const [W, D] = sizeM(it), { f } = axes(it.yaw_deg || 0);
      const c = add2([it.position_m[0], it.position_m[2]], scale2(f, D / 2 + need / 2 + 0.005));
      const zone = footprint(c[0], c[1], Math.max(0.05, W - 0.06), need - 0.01, it.yaw_deg || 0);
      const freeOfWall = insideFraction(zone, room.polygon, 0.0);
      const blockers = solids.filter(o => o.id !== it.id && !(/corner/i.test(it.type) && slotOf(db, o) === "kitchen_unit") && convexOverlap(zone, itemFootprint(o)) > 0.02);
      if (freeOfWall < 0.5) push(it.id, { kind: "clearance", text: "Faces the wall: its front would open into it (the facing in the spec looks reversed)" });
      else if (freeOfWall < 0.999) push(it.id, { kind: "clearance", text: `Too close to a wall: its ${/drawer|chest|bedside/.test(slot + it.type) ? "drawers" : "doors"} need ${mm(need)} mm clear in front` });
      else if (blockers.length) push(it.id, { kind: "clearance", text: `#${blockers[0].num} ${blockers[0].type} is in front: ${/drawer|chest|bedside/.test(slot + it.type) ? "drawers" : "doors"} need ${mm(need)} mm clear` });
    }
    /* floating: a surface piece with nothing under it */
    const m = mountOf(db, it), y = it.position_m[1] - room.floor;
    if (m === "surface" && y > 0.06) {
      const p = [it.position_m[0], it.position_m[2]];
      const y0 = it.position_m[1];
      const support = all.some(o => o.id !== it.id && o.position_m[1] < y0 - 0.02 && o.position_m[1] + o.size_mm[2] / 1000 > y0 - 0.06
          && pointInPoly(p, itemFootprint(o, sizeM(o).map((v, i) => (i < 2 ? v + 0.12 : v)))))
        || (state.house.fixtures || []).some(fx => pointInPoly(p, fx.poly) && fx.y1 > y0 - 0.1)
        || state.house.openings.some(o => o.kind === "window" && o.storey === room.storey && Math.abs(o.sill - y0) < 0.08
          && Math.min(...[o.p0, o.p1].map(q => Math.hypot(q[0] - p[0], q[1] - p[1]))) < o.width + 0.2)
        || (it.type || "").match(/sill|shelf|sofa|bed|rail|oven|hook/i);
      if (!support) push(it.id, { kind: "floating", text: "Nothing under it at this height (it would float)" });
    }
  }
  return warn;
}

/* could this catalogue entry stand where `it` is? */
export function fitsAt(db, state, it, entry, pose) {
  const room = state.house.roomById.get(it.room);
  if (!room) return { ok: true, why: [] };
  const W = entry.size_mm[0] / 1000, D = entry.size_mm[1] / 1000, H = entry.size_mm[2] / 1000;
  const p = pose || it.position_m, yaw = it.yaw_deg || 0;
  const fp = footprint(p[0], p[2], Math.max(W - 0.02, 0.02), Math.max(D - 0.02, 0.02), yaw);
  const why = [];
  if (!["window_dressing", "cushion", "throw", "towels"].includes(entry.slot) && insideFraction(fp, room.polygon, 0.03) < (entry.mount === "wall" ? 0.5 : 0.999)) why.push("too big for the room here");
  const floorSolid = !SOLID_SKIP.has(entry.slot) && entry.mount === "floor";
  if (floorSolid) {
    const carried = new Set();
    for (const o of state.items.values()) {
      if (o.id === it.id || o.room === undefined) continue;
      const orm = state.house.roomById.get(o.room);
      if (orm?.storey !== room.storey || !isFloorSolid(db, o, orm)) continue;
      if (carried.has(o.id)) continue;
      if (convexOverlap(fp, itemFootprint(o)) > 0.015) { why.push(`hits #${o.num} ${o.type}`); break; }
    }
    for (const sw of swingPolys(state.house, room.storey)) if (convexOverlap(fp, sw.poly) > 0.02) { why.push(`blocks the ${sw.opening.label}`); break; }
  }
  if (entry.mount === "surface" && it.position_m[1] - room.floor > 0.06) {
    const sup = [...state.items.values()].find(o => o.id !== it.id && Math.abs(o.position_m[1] + o.size_mm[2] / 1000 - it.position_m[1]) < 0.06
      && pointInPoly([p[0], p[2]], itemFootprint(o, sizeM(o).map((v, i) => (i < 2 ? v + 0.04 : v)))));
    if (sup) {
      const [sw, sd] = sizeM(sup);
      if (W > sw + 0.05 || D > sd + 0.05) why.push(`bigger than the #${sup.num} ${sup.type} it stands on`);
    }
  }
  if (H > room.height + 0.01 && entry.mount === "floor") why.push(`taller (${entry.size_mm[2]} mm) than the ceiling`);
  return { ok: why.length === 0, why };
}
export { entryOf };
