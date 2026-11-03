/* Room planner data: the signed-off spec (read-only), the catalogue, the house's walls / openings / doors / stairs
 * (read live from the elements file of each spec version), and the planner state = spec + replayed changes.
 * Frame: spec SCHEMA.md (x along the front towards the north flank, z = minus depth, y up; yaw 0 faces -z). */
import { pointInPoly, footprint, axes, bbox, norm2, sub2, add2, scale2, dot2, rot, len2, polyArea } from "./util.js?v=p8";

const SITE_ROOT = site => `assets/sites/${site}/`;
const bust = () => `?t=${Date.now()}`;
async function getJSON(url, fresh = false) {
  const r = await fetch(url + (fresh ? bust() : ""), { cache: fresh ? "no-store" : "default" });
  if (!r.ok) throw Object.assign(new Error(`${url}: ${r.status}`),{status:r.status});
  return r.json();
}

export async function loadAll(site) {
  const root = SITE_ROOT(site);
  const specSite = site === 'house-wip' ? 'house' : site;
  const specName="spec_v1.json";
  const [manifest,doors,kit]=await Promise.all([
    getJSON(root+"versions.json",true),
    getJSON(`assets/planner/${specSite}/doors.json`,true).catch(()=>({versions:{}})),
    getJSON('tools/library/kit/catalogue.json'),
  ]);
  const release=/^[0-9a-f]{20}$/.test(manifest.furnish_release||'')?manifest.furnish_release:null;
  let specRoot=release?root+'releases/'+release+'/':root,spec;
  try {spec=await getJSON(specRoot+'spec/'+specName,true);}
  catch(error) {
    if(release || site===specSite || ![403,404].includes(error.status))throw error;
    specRoot=SITE_ROOT(specSite);spec=await getJSON(specRoot+'spec/'+specName,true);
  }
  const catalogue=await getJSON(specRoot+'spec/catalogue_v1.json',true);
  const versions = {}, elements = {};
  await Promise.all(Object.entries(spec.versions).map(async ([key, sv]) => {
    const file=manifest.versions.find(v=>v.id===sv.elements)?.elements || `${sv.elements}_elements.json`;
    const el=await getJSON(root+file,true);
    elements[key]=el;
    versions[key] = buildHouse(key, sv, el, doors.versions?.[key], spec);
  }));
  const finishes = Object.fromEntries(spec.finishes.map(f => [f.id, f]));
  const entries = new Map(catalogue.entries.map(e => [e.id, e]));
  return { site, specSite, specName, spec, catalogue, entries, kit, finishes, versions, elements, doors };
}

/* ---------------------------------------------------------------- the house (walls, openings, rooms) per version */
export function buildHouse(key, sv, elFile, doorData, spec) {
  const E = elFile.elements;
  const byId = new Map(E.map(e => [e.id, e]));
  const replaced = new Set(E.filter(e => e.layer === "as_built").flatMap(e => e.replaces || []));
  const final = e => (e.meta?.stage_out === null || e.meta?.stage_out === undefined) && !replaced.has(e.id);

  const walls = [];
  for (const e of E) {
    if (e.type !== "wall" || !final(e)) continue;
    const p = e.params, T = (p.layers || []).reduce((t, l) => t + l.thickness, 0);
    const d = sub2(p.end, p.start), L = len2(d);
    if (L < 0.02 || T <= 0) continue;
    const t = norm2(d), n = [-t[1], t[0]];
    walls.push({ id: e.id, storey: e.meta?.storey || "ground", a: p.start, b: p.end, t, n, L, T, base: p.base, top: p.base + p.height,
                 label: e.meta?.plain_label || e.meta?.label || e.id, neighbour: /N21|No\.?21/i.test(e.id + (e.meta?.label || "")) });
  }
  const wallById = new Map(walls.map(w => [w.id, w]));
  const rooms = sv.rooms.map(r => {
    const ceil = typeof r.ceiling_y === "number" ? r.ceiling_y : parseFloat(r.ceiling_y) || 2.43;
    const floor = r.floor_y ?? (r.storey === "first" ? 2.6755 : 0);
    return { ...r, floor, ceiling: ceil > floor + 1.5 ? ceil : floor + ceil, height: (ceil > floor + 1.5 ? ceil - floor : ceil),
             area: r.area_m2 ?? polyArea(r.polygon) };
  });
  const roomAt = (x, z, storey) => rooms.find(r => r.storey === storey && pointInPoly([x, z], r.polygon)) || null;

  /* openings with their fixture (door / window / bi-fold) */
  const fixtureOf = new Map();
  for (const e of E) if (e.type === "fixture" && final(e) && e.params?.opening) fixtureOf.set(e.params.opening, e);
  const dw = new Map((sv.doors_windows || []).map(d => [d.opening, d]));
  const openings = [];
  for (const e of E) {
    if (e.type !== "opening" || !final(e)) continue;
    const w = wallById.get(e.params.host);
    if (!w) continue;
    const q = e.params, fx = fixtureOf.get(e.id), cat = fx?.params?.catalogue || "";
    const kind = /bifold/.test(cat) ? "bifold" : (e.meta?.group === "door" || /door/.test(cat)) ? "door" : "window";
    const p0 = add2(w.a, scale2(w.t, q.offset)), p1 = add2(w.a, scale2(w.t, q.offset + q.width));
    const info = dw.get(e.id) || (fx && (sv.doors_windows || []).find(d => d.id === fx.id)) || null;
    const o = { id: e.id, fixture: fx?.id || null, kind, wall: w.id, storey: w.storey, p0, p1, t: w.t, n: w.n, T: w.T,
                width: q.width, sill: q.sill, head: q.head, lights: fx?.params?.lights || 1,
                label: info?.label || e.meta?.plain_label || e.id, external: !!info?.external, info, leaves: [] };
    /* an opening with no door fixture left in this version is a doorway without a leaf (or a duplicate of one) */
    if (kind !== "window" && fx) o.leaves = doorLeaves(o, doorData?.leaves?.[o.fixture], roomAt);
    if (!fx && kind === "window") continue;     // a window opening whose window is gone in this version: drawn as wall
    if (!fx) o.kind = "doorway";
    openings.push(o);
  }

  /* stairs: flights as tread rectangles */
  const stairs = [];
  for (const e of E) {
    if (e.type !== "stair" || !final(e)) continue;
    const p = e.params;
    for (const fl of p.flights || [p]) {
      const dir = norm2(fl.direction), side = [-dir[1], dir[0]], hw = fl.width / 2, n = fl.risers;
      const treads = [];
      for (let k = 0; k < n; k++) {
        const s0 = add2(fl.start, scale2(dir, k * fl.going)), s1 = add2(fl.start, scale2(dir, (k + 1) * fl.going));
        treads.push([add2(s0, scale2(side, -hw)), add2(s0, scale2(side, hw)), add2(s1, scale2(side, hw)), add2(s1, scale2(side, -hw))]);
      }
      stairs.push({ id: e.id, base: fl.base, rise: p.rise, treads, dir, start: fl.start, width: fl.width, going: fl.going, risers: n,
                    up: fl.base + n * p.rise });
    }
    if (p.half_landing) stairs.push({ id: e.id + "-landing", landing: true, poly: p.half_landing.poly, base: p.half_landing.z });
  }
  const fixtures = (sv.drawn_fixtures || []).filter(f => !/stack|stair|balustrade/i.test(f.element)).map(f => ({
    id: f.element, poly: [[f.box_min[0], f.box_min[2]], [f.box_max[0], f.box_min[2]], [f.box_max[0], f.box_max[2]], [f.box_min[0], f.box_max[2]]],
    y0: f.box_min[1], y1: f.box_max[1], finish: f.finish }));

  const storeys = ["ground", "first"].filter(st => rooms.some(r => r.storey === st));
  const ffl = { ground: 0, first: rooms.find(r => r.storey === "first")?.floor ?? 2.6755 };
  const extent = {};
  for (const st of storeys) {
    const pts = rooms.filter(r => r.storey === st).flatMap(r => r.polygon);
    const b = bbox(pts);
    extent[st] = { x0: b.x0 - 0.45, z0: b.z0 - 0.45, x1: b.x1 + 0.45, z1: b.z1 + 0.45 };
  }
  const numbers = new Map(sv.items.map((it, i) => [it.id, i + 1]));
  return { key, name: key === "before" ? "Before" : "After", description: sv.description, elements: sv.elements,
           rooms, walls, openings, stairs, fixtures, storeys, ffl, extent, roomAt, baseItems: sv.items, numbers,
           roomById: new Map(rooms.map(r => [r.id, r])) };
}

/* every door leaf: hinge, the closed free end, the open end and the swing (degrees, + = counter-clockwise from above) */
function doorLeaves(o, data, roomAt) {
  const mid = scale2(add2(o.p0, o.p1), 0.5);
  if (o.kind === "bifold") {
    return [{ bifold: true, hinge: o.p0, free: o.p1, open: o.p0, swing: 0, radius: 0, source: data ? "glb" : "derived",
              side: sideInto(o, roomAt) }];
  }
  const leaves = [];
  if (data && data.length) {
    const n = data.length, lw = o.width / n;
    for (const l of data) {
      const h = l.hinge, near0 = len2(sub2(h, o.p0)) <= len2(sub2(h, o.p1));
      const hingeP = near0 ? o.p0 : o.p1, dirIn = near0 ? o.t : scale2(o.t, -1);
      const off = dot2(sub2(h, hingeP), o.n);              // the frame plane (across the wall)
      const hp = add2(hingeP, scale2(o.n, off));
      const free = add2(hp, scale2(dirIn, lw));
      const open = add2(hp, rot(scale2(dirIn, lw), l.swing_deg));
      leaves.push({ hinge: hp, free, open, swing: l.swing_deg, radius: lw, source: l.source || "glb" });
    }
    return leaves;
  }
  /* derived: hinge at the jamb nearer a wall end, opens 90 degrees into the room that is not a hall / landing */
  const k = sideInto(o, roomAt);
  const hinge = o.p0, v = scale2(o.t, o.width);
  const plus = rot(v, 90), sw = dot2(plus, scale2(o.n, k)) > 0 ? 90 : -90;
  return [{ hinge, free: o.p1, open: add2(hinge, rot(v, sw)), swing: sw, radius: o.width, source: "derived" }];
  function sideInto(o2, ra) {
    const sc = kk => {
      const q = add2(mid, scale2(o2.n, kk * (o2.T / 2 + 0.45)));
      const r = ra(q[0], q[1], o2.storey);
      return (r && !/hall|landing|porch/i.test(r.name) ? 2 : 0) + (r ? 1 : 0);
    };
    return sc(1) >= sc(-1) ? 1 : -1;
  }
}

/* ---------------------------------------------------------------- planner state: spec + changes, replayed */
const clone = o => JSON.parse(JSON.stringify(o));

export function computeState(db, vkey, changes) {
  const house = db.versions[vkey];
  const items = new Map();
  for (const it of house.baseItems) {
    const c = clone(it);
    c.num = house.numbers.get(it.id);
    c.catalogue = db.catalogue.spec_items?.[vkey]?.[it.id] || null;
    c.lampOn = false;
    items.set(c.id, c);
  }
  const rooms = new Map();                // room id -> overrides {walls, accent, floor, fronts, island_fronts, worktop}
  const notes = new Map();                // target key ("item:ID" / "room:ID") -> [{text, at, change}]
  let nextNum = Math.max(0, ...house.numbers.values()) + 1;
  const usedNums = new Set(house.numbers.values());
  const applied = [];
  for (const ch of changes) {
    if (ch.version !== vkey) continue;
    if (ch.status !== "active" && ch.status !== "sent") continue;
    apply(ch);
    applied.push(ch);
  }
  function setPose(id, pose) { const it = items.get(id); if (!it) return; if (pose.position_m) it.position_m = pose.position_m.slice(); if (pose.yaw_deg !== undefined) it.yaw_deg = pose.yaw_deg; if (pose.room) it.room = pose.room; }
  function apply(ch) {
    const a = ch.after || {};
    switch (ch.op) {
      case "item.move":
        setPose(ch.target.item, a);
        for (const c of a.carried || []) setPose(c.id, c);
        break;
      case "item.delete":
        for (const id of [ch.target.item, ...(a.carried_ids || [])]) items.delete(id);
        break;
      case "item.add":
        for (const it of a.items || [a.item]) {
          if (!it) continue;
          const c = clone(it);
          if (!c.num || usedNums.has(c.num)) c.num = nextNum;      // two devices can pick the same next number
          usedNums.add(c.num); nextNum = Math.max(nextNum, c.num + 1); c.added = true; items.set(c.id, c);
        }
        break;
      case "item.swap": {
        const it = items.get(ch.target.item); if (!it) break;
        Object.assign(it, clone(a.fields)); it.swapped = true;
        break;
      }
      case "item.finish": {
        const it = items.get(ch.target.item); if (!it) break;
        it.materials = { ...(it.materials || {}), [a.part]: a.value };
        break;
      }
      case "item.lamp": { const it = items.get(ch.target.item); if (it) it.lampOn = !!a.on; break; }
      case "room.walls": case "room.accent": case "room.floor": case "room.fronts": case "room.island_fronts": case "room.worktop": {
        const r = rooms.get(ch.target.room) || {}; r[ch.op.slice(5)] = a.value; rooms.set(ch.target.room, r); break;
      }
      case "room.lamps": for (const id of a.ids || []) { const it = items.get(id); if (it) it.lampOn = !!a.on; } break;
      case "note": {
        const k = ch.target.item ? "item:" + ch.target.item : "room:" + ch.target.room;
        (notes.get(k) || notes.set(k, []).get(k)).push({ text: a.text, at: ch.at, change: ch.id });
        break;
      }
    }
  }
  return { vkey, house, items, rooms, notes, nextNum, applied };
}

/* ---------------------------------------------------------------- per-item helpers */
export const SLOT_OF_KIND = {};   // filled from the catalogue at start (entry.slot by spec item)
export function entryOf(db, it) { return (it.catalogue && db.entries.get(it.catalogue)) || null; }
export function slotOf(db, it) { return entryOf(db, it)?.slot || "fixed"; }
export function shapeOf(db, it) { return entryOf(db, it)?.shape || "box"; }
export function mountOf(db, it) { return entryOf(db, it)?.mount || "floor"; }
export function sizeM(it) { return [it.size_mm[0] / 1000, it.size_mm[1] / 1000, it.size_mm[2] / 1000]; }
export function itemFootprint(it, sizeOverride) {
  const [W, D] = sizeOverride || sizeM(it);
  return footprint(it.position_m[0], it.position_m[2], Math.max(W, 0.02), Math.max(D, 0.02), it.yaw_deg || 0);
}
export function storeyOfItem(state, it) { return state.house.roomById.get(it.room)?.storey || (it.position_m[1] > 2 ? "first" : "ground"); }

/* finish id or colour -> {hex, name} */
export function resolveColour(db, v, fallback = "#C9C2B6") {
  if (!v) return { hex: fallback, name: "" };
  if (typeof v === "object" && v.hex) return { hex: v.hex, name: v.name || v.hex };
  if (typeof v === "string") {
    if (/^#[0-9a-f]{6}$/i.test(v)) return { hex: v, name: v };
    const id = (v.match(/^[A-Z0-9][A-Z0-9-]+/) || [])[0];
    const f = id && db.finishes[id];
    if (f) return { hex: f.colour_srgb, name: f.name, id: f.id };
  }
  return { hex: fallback, name: typeof v === "string" ? v : "" };
}
export function partColour(db, state, it, part, fallback) {
  const m = it.materials || {};
  const v = m[part] ?? (part !== "all" ? m.all : undefined);
  const e = entryOf(db, it);
  const room = state.rooms.get(it.room) || {};
  const slot = e?.slot;
  if ((slot === "kitchen_unit" || slot === "kitchen_wall_units") && part === "front" && room.fronts) return room.fronts;
  if (slot === "island" && part === "front" && room.island_fronts) return room.island_fronts;
  if ((slot === "kitchen_unit" || slot === "island") && (part === "worktop" || part === "top") && room.worktop) return room.worktop;
  if (v && v !== "as asset") {
    const c = resolveColour(db, v, fallback);
    if (c.name === c.hex) {                    /* a bare colour: name it from the catalogue's options when it is one of them */
      const o = (e?.options?.[part] || Object.values(e?.options || {}).flat()).find(x => x.hex.toLowerCase() === c.hex.toLowerCase());
      if (o) c.name = o.name;
    }
    return c;
  }
  const ph = e?.part_hex?.[part] || (e && Object.values(e.part_hex || {}).find(Boolean));
  return { hex: ph || fallback, name: "" };
}
/* the room's current wall / floor */
export function roomWalls(db, state, room) {
  const o = state.rooms.get(room.id) || {};
  return o.walls || resolveColour(db, room.finishes?.walls, "#ECE6DC");
}
export function roomFloor(db, state, room) {
  const o = state.rooms.get(room.id) || {};
  if (o.floor) return o.floor;
  const id = (String(room.finishes?.floor || "").match(/^[A-Z0-9][A-Z0-9-]+/) || [])[0];
  const f = db.catalogue.floors.find(x => x.id === id);
  const fin = db.finishes[id];
  return f ? { ...f, hex: f.hex } : { id, name: fin?.name || "floor", hex: fin?.colour_srgb || "#B48C64", pattern: "planks", unit_mm: [190, 1900] };
}

/* which items sit on another (cushions on a sofa, a lamp on a side table): carried when the support moves */
export function carriedBy(db, state, parent) {
  if(parent.shared) {
    const ids=new Set([parent.id]), children=[], rows=[...state.items.values()];
    for(const id of ids) for(const row of rows) {
      if (!row.shared || !['surface','item'].includes(row.shared.host.type) || row.shared.host.id!==id || ids.has(row.id)) continue;
      ids.add(row.id); children.push(row);
    }
    return children;
  }
  const [W, D, H] = sizeM(parent), py = parent.position_m[1], top = py + H;
  const pf = itemFootprint(parent, [W + 0.1, D + 0.1]);
  const out = [];
  for (const it of state.items.values()) {
    if (it.id === parent.id || it.room !== parent.room) continue;
    const m = mountOf(db, it);
    if (m === "ceiling" || m === "wall" || m === "window") continue;
    const y = it.position_m[1];
    if (y < py + 0.05 || y > top + 0.03) continue;
    const [w, d] = sizeM(it);
    if (w * d > W * D * 0.9 && !["throw", "cushion"].includes(slotOf(db, it))) continue;   // a throw drapes wider than the sofa
    if (!pointInPoly([it.position_m[0], it.position_m[2]], pf)) continue;
    out.push(it);
  }
  return out;
}
export { axes, footprint };
