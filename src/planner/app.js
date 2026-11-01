/* Room planner (planner.html): review and edit the signed-off design spec, room by room.
 * Opens on the 2D plan; the 3D preview loads only when asked for. Every edit becomes one change in the change list
 * (store.js); "Send to build" writes the batch the next spec version is made from. The spec itself is read-only. */
import { h, clear, r3, mm, normDeg, rot, add2, sub2, scale2, dot2, len2, segDist, pointInPoly, labelPoint, centroid, moveWords, axes, cap, uid } from "./util.js?v=p7";
import { loadAll, computeState, entryOf, slotOf, sizeM, carriedBy, partColour, roomWalls, roomFloor, mountOf } from "./data.js?v=p7";
import { ChangeStore } from "./store.js?v=p7";
import { PlanView } from "./plan.js?v=p7";
import { checkRoom, fitsAt } from "./checks.js?v=p7";
import { renderOverview, renderRoom, renderItem, openCatalogue, openChanges } from "./panel.js?v=p7";

const SITE = new URLSearchParams(location.search).get("site") || "house";
const $ = id => document.getElementById(id);
const label = it => `${it.type} (#${it.num})`;
const clone = o => JSON.parse(JSON.stringify(o));
const pose = it => ({ position_m: it.position_m.slice(), yaw_deg: it.yaw_deg || 0, room: it.room });

class App {
  constructor() {
    this.vkey = "after"; this.storey = "ground"; this.roomId = null; this.selected = null;
    this.ui = { wallStyle: "Contemporary", three: false };
    this.warnings = new Map(); this.roomWarn = new Map();
  }
  async start() {
    this.applyTheme(localStorage.getItem("planner:theme"));
    const insp = $("inspector");
    insp.append(h("div.sec", null, h("p.muted", { text: "Loading the spec and the house plan…" })));
    try { this.db = await loadAll(SITE); }
    catch (e) { clear(insp).append(h("div.sec", null, h("h2", { text: "Could not load the spec" }), h("p.small", { text: String(e.message || e) }))); return; }
    this.store = new ChangeStore(SITE);
    this.store.on(r => { if (r === "offline") this.toast("Lost the studio server: changes now stay on this device until it is back."); if (String(r).startsWith("uploaded")) this.toast(`Uploaded ${r.split(":")[1]} change(s) made on this device.`); });
    await this.store.load();
    this.plan = new PlanView($("plan"), { db: this.db, onSelect: id => this.select(id), onOpenRoom: (r, it) => this.openRoom(r, it), onCommit: c => this.commitDrag(c) });
    this.bindUI();
    this.fromHash();
    this.recompute(); this.render();
    window.addEventListener("hashchange", () => { if (this._settingHash) return; this.fromHash(); this.recompute(); this.render(); });
    setInterval(async () => { if (document.visibilityState === "visible" && await this.store.refresh()) this.afterChange(true); }, 15000);
    document.addEventListener("visibilitychange", async () => { if (document.visibilityState === "visible" && await this.store.refresh()) this.afterChange(true); });
    window.planner = this;      // for checks from the console
  }

  /* ---------------------------------------------------------------- state */
  recompute() {
    this.state = computeState(this.db, this.vkey, this.store.applied);
    this.roomWarn = new Map();
    this.warnings = this.roomId ? this.warningsFor(this.roomId) : new Map();
    if (this.selected && !this.state.items.has(this.selected)) this.selected = null;
  }
  warningsFor(roomId) {
    if (!this.roomWarn.has(roomId)) this.roomWarn.set(roomId, checkRoom(this.db, this.state, roomId));
    return this.roomWarn.get(roomId);
  }
  get house() { return this.state.house; }
  get room() { return this.roomId ? this.house.roomById.get(this.roomId) : null; }

  /* ---------------------------------------------------------------- navigation */
  fromHash() {
    const p = location.hash.replace(/^#/, "").split("/");
    if (p[0] === "before" || p[0] === "after") this.vkey = p[0];
    const H = this.db.versions[this.vkey];
    if (p[1] === "room" && p[2] && H.roomById.has(decodeURIComponent(p[2]))) { this.roomId = decodeURIComponent(p[2]); this.storey = H.roomById.get(this.roomId).storey; }
    else { this.roomId = null; if (p[1] === "first" || p[1] === "ground") this.storey = p[1]; }
    this.selected = null;
  }
  setHash() {
    this._settingHash = true;
    location.hash = this.roomId ? `${this.vkey}/room/${encodeURIComponent(this.roomId)}` : `${this.vkey}/${this.storey}`;
    setTimeout(() => (this._settingHash = false), 0);
  }
  openRoom(roomId, itemId = null) {
    this.roomId = roomId; this.storey = this.house.roomById.get(roomId).storey; this.selected = itemId;
    this.warnings = this.warningsFor(roomId);
    this.setHash(); this.render();
  }
  back() { this.roomId = null; this.selected = null; this.setHash(); this.render(); }
  select(id, scroll = false) {
    this.selected = id;
    this.render(true);
    if (scroll) $("inspector").scrollTop = 0;
  }
  setVersion(v) {
    if (v === this.vkey) return;
    const keepRoom = this.roomId && this.db.versions[v].roomById.has(this.roomId) ? this.roomId : null;
    this.vkey = v; this.recompute();
    this.roomId = keepRoom; this.selected = null;
    if (!this.house.storeys.includes(this.storey)) this.storey = "ground";
    this.warnings = this.roomId ? this.warningsFor(this.roomId) : new Map();
    this.setHash(); this.render();
  }
  setStorey(s) { this.storey = s; this.roomId = null; this.selected = null; this.setHash(); this.render(); }

  /* ---------------------------------------------------------------- render */
  render(keepView = false) {
    const H = this.house, room = this.room;
    for (const b of $("verSeg").children) b.setAttribute("aria-pressed", String(b.dataset.v === this.vkey));
    for (const b of $("storeySeg").children) { b.setAttribute("aria-pressed", String(b.dataset.s === this.storey)); b.hidden = !H.storeys.includes(b.dataset.s); }
    $("roomCard").hidden = !room; $("roomTools").hidden = !room;
    $("roomTitle").textContent = room ? cap(room.name) : "";
    $("hint").textContent = room ? "Drag to move · handle to turn · double-tap empty floor to re-fit" : "Tap a room to open it";
    $("main").classList.toggle("nosel", !room);
    this.plan.show({ state: this.state, storey: this.storey, mode: room ? "room" : "overview", roomId: this.roomId, selected: this.selected, warnings: this.warnings, keepView });
    this.refreshPanel();
    this.renderTop();
    if (this.ui.three) this.update3D();
  }
  refreshPanel() {
    const el = $("inspector"), st = this.scrollKeep(el);
    const it = this.selected && this.state.items.get(this.selected);
    if (it && this.room) renderItem(this, el, it);
    else if (this.room) renderRoom(this, el, this.room);
    else renderOverview(this, el);
    st();
  }
  scrollKeep(el) { const key = (this.selected || "") + (this.roomId || ""), top = el.scrollTop, same = this._panelKey === key; this._panelKey = key; return () => { if (same) el.scrollTop = top; else el.scrollTop = 0; }; }
  renderTop() {
    const s = this.store, n = s.active.length;
    $("changeCount").textContent = n; $("changeCount").classList.toggle("zero", !n);
    $("undoBtn").disabled = !s.canUndo(); $("redoBtn").disabled = !s.canRedo();
    $("sendBtn").disabled = !n;
    const c = $("conn"); c.className = s.mode;
    c.querySelector("span").textContent = s.mode === "server" ? "Saved to the studio" : "On this device only";
    c.title = s.mode === "server" ? "Every change is written to the studio's change list as you go" : `The studio server is not reachable (${s.lastError || ""}). Changes are kept in this browser and uploaded when it is.`;
  }
  async afterChange(remote) {
    this.recompute();
    this.render(true);
    if (remote) this.toast("Updated with changes from another device.");
  }
  toast(text) {
    const t = h("div.toast", { text, role: "status" }); document.body.append(t);
    setTimeout(() => t.remove(), 3200);
  }
  applyTheme(t) {
    if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
  }

  /* ---------------------------------------------------------------- 3D (only when asked for) */
  async toggle3D() {
    this.ui.three = !this.ui.three;
    $("threeBtn").setAttribute("aria-pressed", String(this.ui.three));
    $("threeBtn").innerHTML = `<span class="wide-only">${this.ui.three ? "Hide" : "Show"} </span>3D<span class="wide-only"> preview</span>`;
    $("threePane").hidden = !this.ui.three;
    $("main").classList.toggle("with3d", this.ui.three);
    if (this.ui.three && !this.view3d) {
      $("threeEmpty").textContent = "Loading the 3D preview…";
      try {
        const { Preview3D } = await import("./view3d.js?v=p7");
        this.view3d = new Preview3D($("threePane"), { db: this.db, onSelect: id => { if (id) this.select(id); } });
      } catch (e) { $("threeEmpty").textContent = "The 3D preview could not load (it needs the internet for three.js): " + (e.message || e); return; }
    }
    this.plan.fit(); this.render();
  }
  update3D() {
    if (!this.view3d) return;
    $("threeEmpty").hidden = !!this.room;
    $("threeEmpty").textContent = "Open a room to see it in 3D.";
    this.view3d.renderer.domElement.style.visibility = this.room ? "visible" : "hidden";
    if (this.room) this.view3d.show(this.state, this.roomId, this.selected);
  }

  /* ---------------------------------------------------------------- recording changes */
  async commit(change) {
    const c = await this.store.add({ version: this.vkey, room: change.room || this.roomId, ...change });
    this.afterChange();
    return c;
  }
  commitDrag(d) {
    const it = d.it;
    if (d.kind === "move") {
      const dx = d.to[0] - d.from[0], dz = d.to[2] - d.from[2];
      const moved = d.room !== it.room ? ` into ${this.house.roomById.get(d.room)?.name}` : "";
      return this.commit({ op: "item.move", target: { item: it.id },
        summary: `Moved ${label(it)} ${moveWords(dx, dz)}${moved}${d.carried.length ? ` (with the ${d.carried.length} thing${d.carried.length === 1 ? "" : "s"} on it)` : ""}`,
        before: { ...pose(it), carried: d.carried.map(c => ({ id: c.id, position_m: c.from, yaw_deg: c.yaw, room: it.room })) },
        after: { position_m: d.to, yaw_deg: it.yaw_deg || 0, room: d.room, carried: d.carried.map(c => ({ id: c.id, position_m: c.to, yaw_deg: c.yaw, room: c.room })) } });
    }
    if (d.kind === "rotate") return this.turnTo(it, d.to, d.carried);
  }
  turnTo(it, yaw, carried) {
    const c = [it.position_m[0], it.position_m[2]], dy = yaw - (it.yaw_deg || 0);
    carried = carried || carriedBy(this.db, this.state, it).map(ch => {
      const rel = rot([ch.position_m[0] - c[0], ch.position_m[2] - c[1]], dy);
      return { id: ch.id, from: ch.position_m.slice(), to: [r3(c[0] + rel[0]), ch.position_m[1], r3(c[1] + rel[1])], yawFrom: ch.yaw_deg || 0, yaw: normDeg((ch.yaw_deg || 0) + dy) };
    });
    return this.commit({ op: "item.move", target: { item: it.id },
      summary: `Turned ${label(it)} ${Math.abs(Math.round(normDeg(dy)))}° ${normDeg(dy) > 0 ? "anticlockwise" : "clockwise"} (now faces ${Math.round(normDeg(yaw))}°)`,
      before: { ...pose(it), carried: carried.map(ch => ({ id: ch.id, position_m: ch.from, yaw_deg: ch.yawFrom })) },
      after: { position_m: it.position_m.slice(), yaw_deg: normDeg(yaw), room: it.room, carried: carried.map(ch => ({ id: ch.id, position_m: ch.to, yaw_deg: ch.yaw })) } });
  }
  rotateBy(it, d) { return this.turnTo(it, normDeg((it.yaw_deg || 0) + d)); }
  nudge(it, dx, dz) {
    const carried = carriedBy(this.db, this.state, it);
    const to = [r3(it.position_m[0] + dx), it.position_m[1], r3(it.position_m[2] + dz)];
    return this.commit({ op: "item.move", target: { item: it.id }, summary: `Nudged ${label(it)} ${moveWords(dx, dz)}`,
      before: { ...pose(it), carried: carried.map(c => ({ id: c.id, position_m: c.position_m.slice(), yaw_deg: c.yaw_deg || 0 })) },
      after: { position_m: to, yaw_deg: it.yaw_deg || 0, room: it.room, carried: carried.map(c => ({ id: c.id, position_m: [r3(c.position_m[0] + dx), c.position_m[1], r3(c.position_m[2] + dz)], yaw_deg: c.yaw_deg || 0 })) } });
  }
  remove(it) {
    const carried = carriedBy(this.db, this.state, it);
    this.selected = null;
    return this.commit({ op: "item.delete", target: { item: it.id },
      summary: `Removed ${label(it)}${carried.length ? ` and the ${carried.length} thing${carried.length === 1 ? "" : "s"} on it (${carried.map(c => "#" + c.num).join(", ")})` : ""}`,
      before: { item: clone(it), carried: carried.map(clone) }, after: { carried_ids: carried.map(c => c.id) } });
  }
  newId(room) { return ("N-" + room.id.replace(/^R-/, "").slice(0, 14) + "-" + uid("").slice(-6)).replace(/[^A-Za-z0-9_-]/g, ""); }
  duplicate(it) {
    const room = this.house.roomById.get(it.room), [W] = sizeM(it), { u } = axes(it.yaw_deg || 0);
    const carried = carriedBy(this.db, this.state, it);
    let off = scale2(u, W + 0.05);
    let num = this.state.nextNum;
    const make = (src, offset, extra = {}) => ({ ...clone(src), id: this.newId(room), num: num++, position_m: [r3(src.position_m[0] + offset[0]), src.position_m[1], r3(src.position_m[2] + offset[1])],
      provenance: "proposed", status: "added in the planner", evidence: `copy of #${src.num} ${src.type}`, in_both_versions: false, ...extra });
    const e = entryOf(this.db, it) || { size_mm: it.size_mm, mount: mountOf(this.db, it), slot: slotOf(this.db, it) };
    for (const tryOff of [off, scale2(off, -1), [0, 0]]) {
      const p = [it.position_m[0] + tryOff[0], it.position_m[1], it.position_m[2] + tryOff[1]];
      if (fitsAt(this.db, this.state, it, e, p).ok) { off = tryOff; break; }
      if (tryOff[0] === 0 && tryOff[1] === 0) { const f = this.freeSpot(room, e, it); off = sub2(f, [it.position_m[0], it.position_m[2]]); }
    }
    const items = [make(it, off), ...carried.map(c => make(c, off))];
    this.selected = items[0].id;
    return this.commit({ op: "item.add", target: { item: items[0].id }, summary: `Duplicated ${label(it)} as #${items[0].num}${carried.length ? ` with the ${carried.length} thing(s) on it` : ""}`,
      before: null, after: { items } });
  }
  /* where a new piece can go: nearest free floor to the room's middle */
  freeSpot(room, entry, base) {
    const c = labelPoint(room.polygon), cands = [];
    const xs = room.polygon.map(p => p[0]), zs = room.polygon.map(p => p[1]);
    for (let x = Math.min(...xs); x <= Math.max(...xs); x += 0.1) for (let z = Math.min(...zs); z <= Math.max(...zs); z += 0.1) {
      if (pointInPoly([x, z], room.polygon)) cands.push([x, z, Math.hypot(x - c[0], z - c[1])]);
    }
    cands.sort((a, b) => a[2] - b[2]);
    const fake = { ...(base || {}), id: "__new__", room: room.id, position_m: [c[0], room.floor, c[1]], yaw_deg: base?.yaw_deg || 0, size_mm: entry.size_mm };
    for (const [x, z] of cands.slice(0, 600)) {
      if (fitsAt(this.db, this.state, fake, entry, [x, fake.position_m[1], z]).ok) return [r3(Math.round(x / 0.05) * 0.05), r3(Math.round(z / 0.05) * 0.05)];
    }
    return c;
  }
  itemFromEntry(entry, room, extra = {}) {
    const parts = {};
    for (const [p, v] of Object.entries(entry.parts || {})) parts[p] = v;
    return { id: this.newId(room), room: room.id, category: entry.category, type: entry.name.replace(/^Poly Haven /, ""), catalogue: entry.id,
             asset: entry.source.source === "polyhaven" ? { ...entry.source, fit: "uniform" } : entry.source.source === "parametric" ? { source: "parametric", kind: entry.shape } : entry.asset || entry.source,
             size_mm: entry.size_mm.slice(), position_m: [0, room.floor, 0], yaw_deg: 0, materials: Object.keys(parts).length ? parts : { all: "as asset" },
             provenance: "proposed", status: "added in the planner", evidence: "added in the planner from the catalogue", in_both_versions: false,
             num: this.state.nextNum, ...extra };
  }
  addEntry(entry, room) {
    const it = this.itemFromEntry(entry, room);
    const [W, D, H] = entry.size_mm.map(v => v / 1000);
    if (entry.mount === "window") { const w = this.windowsOf(room)[0]; if (w) return this.setDressing(room, w, entry); }
    if (entry.mount === "ceiling") { const c = labelPoint(room.polygon); it.position_m = [r3(c[0]), r3(room.ceiling), r3(c[1])]; }
    else if (entry.mount === "wall") {
      const wall = this.longestWall(room);
      const y = { art: 1.5 - H / 2, mirror: 1.5 - H / 2, wall_light: 1.6, tv: 1.1, radiator: 0.15, kitchen_wall_units: 1.45, mirror_cabinet: 1.2, hooks: 1.6, towel_rail: 0.3 }[entry.slot] ?? 1.2;
      const p = add2(wall.mid, scale2(wall.inward, D / 2 + 0.005));
      it.position_m = [r3(p[0]), r3(room.floor + Math.max(0, y)), r3(p[1])];
      it.yaw_deg = normDeg(Math.atan2(-wall.inward[0], -wall.inward[1]) * 180 / Math.PI);
    } else if (entry.mount === "surface") {
      const sup = [...this.state.items.values()].filter(o => o.room === room.id && mountOf(this.db, o) === "floor" && /table|cabinet|kitchen_unit|bench/.test(entryOf(this.db, o)?.shape || "") && o.size_mm[2] > 300 && o.size_mm[2] < 1200)
        .sort((a, b) => b.size_mm[0] * b.size_mm[1] - a.size_mm[0] * a.size_mm[1])[0];
      if (sup) it.position_m = [sup.position_m[0], r3(sup.position_m[1] + sup.size_mm[2] / 1000), sup.position_m[2]];
      else { const f = this.freeSpot(room, entry); it.position_m = [f[0], room.floor, f[1]]; }
    } else { const f = this.freeSpot(room, entry); it.position_m = [f[0], room.floor, f[1]]; }
    this.selected = it.id;
    return this.commit({ op: "item.add", target: { item: it.id }, summary: `Added ${it.type} (#${it.num}) to the ${room.name}`, before: null, after: { items: [it] } });
  }
  longestWall(room) {
    let best = null;
    const P = room.polygon;
    for (let i = 0; i < P.length; i++) {
      const a = P[i], b = P[(i + 1) % P.length], L = len2(sub2(b, a)), mid = scale2(add2(a, b), 0.5);
      if (this.house.openings.some(o => o.storey === room.storey && segDist(scale2(add2(o.p0, o.p1), 0.5), a, b) < o.T / 2 + 0.15 && len2(sub2(scale2(add2(o.p0, o.p1), 0.5), mid)) < 0.6)) continue;
      const t = [(b[0] - a[0]) / L, (b[1] - a[1]) / L];
      let n = [t[1], -t[0]]; if (!pointInPoly(add2(mid, scale2(n, 0.05)), P)) n = [-n[0], -n[1]];
      if (!best || L > best.L) best = { L, mid, inward: n };
    }
    return best || { L: 1, mid: labelPoint(P), inward: [0, 1] };
  }
  swapPose(it, entry) {
    const m = mountOf(this.db, it);
    if (m === "ceiling" || m === "surface") return it.position_m.slice();
    const { f } = axes(it.yaw_deg || 0), D0 = it.size_mm[1] / 1000, D1 = entry.size_mm[1] / 1000;
    const back = add2([it.position_m[0], it.position_m[2]], scale2(f, -D0 / 2));
    const c = add2(back, scale2(f, D1 / 2));
    return [r3(c[0]), it.position_m[1], r3(c[1])];
  }
  swapFields(it, entry, sizeOverride) {
    const parts = { ...(entry.parts || {}) };
    return { catalogue: entry.id, type: entry.name.replace(/^Poly Haven /, ""), category: entry.category, size_mm: sizeOverride || entry.size_mm.slice(),
             asset: entry.source.source === "polyhaven" ? { ...entry.source, fit: "uniform" } : entry.asset || { source: "parametric", kind: entry.shape },
             materials: Object.keys(parts).length ? parts : { all: "as asset" }, position_m: this.swapPose(it, { size_mm: sizeOverride || entry.size_mm }),
             provenance: entry.signed_off ? it.provenance : "proposed", status: entry.signed_off ? "back to the signed-off piece" : "swapped in the planner",
             evidence: `swapped in the planner (was ${it.type}, ${it.size_mm.join("x")} mm)` };
  }
  swap(it, entry, sizeOverride) {
    const after = this.swapFields(it, entry, sizeOverride);
    const before = Object.fromEntries(Object.keys(after).map(k => [k, clone(it[k] ?? null)]));
    return this.commit({ op: "item.swap", target: { item: it.id }, summary: `Changed ${label(it)} for ${after.type} (${entry.styles.join("/")})`,
      before: { fields: before }, after: { fields: after, entry: entry.id } });
  }
  setFinish(it, part, value) {
    const old = it.materials?.[part] ?? null;
    return this.commit({ op: "item.finish", target: { item: it.id }, summary: `${cap(part === "all" ? "colour" : part)} of ${label(it)}: ${value.name}`,
      before: { part, value: old }, after: { part, value } });
  }
  toggleLamp(it) {
    return this.commit({ op: "item.lamp", target: { item: it.id }, summary: `${label(it)} switched ${it.lampOn ? "off" : "on"}`, before: { on: !!it.lampOn }, after: { on: !it.lampOn } });
  }
  setLamps(room, lights, on) {
    return this.commit({ op: "room.lamps", target: { room: room.id }, summary: `All ${lights.length} lights in the ${room.name} ${on ? "on" : "off"}`,
      before: { states: lights.map(l => [l.id, !!l.lampOn]) }, after: { ids: lights.map(l => l.id), on } });
  }
  setRoom(room, field, value) {
    const cur = this.state.rooms.get(room.id)?.[field] ?? null;
    const words = { walls: "Walls", accent: "Accent wall", floor: "Floor", fronts: "Kitchen fronts", island_fronts: "Island fronts", worktop: "Worktops" }[field];
    const summary = value ? `${words} of the ${room.name}: ${value.name}${value.hex ? " (" + value.hex + ")" : ""}` : `${words} of the ${room.name}: removed`;
    return this.commit({ op: "room." + field, target: { room: room.id }, summary, before: { value: cur }, after: { value } });
  }
  addNote(target, text) {
    const what = target.item ? label(this.state.items.get(target.item)) : `the ${this.house.roomById.get(target.room).name}`;
    return this.commit({ op: "note", target, summary: `Note on ${what}: “${text.slice(0, 80)}${text.length > 80 ? "…" : ""}”`, before: null, after: { text } });
  }
  async undo() { const c = await this.store.undo(); if (c) { this.toast("Undone: " + c.summary); this.afterChange(); } }
  async redo() { const c = await this.store.redo(); if (c) { this.toast("Redone: " + c.summary); this.afterChange(); } }

  /* ---------------------------------------------------------------- windows and their dressings */
  inside(p, poly) { return pointInPoly(p, poly); }
  windowsOf(room) {
    return this.house.openings.filter(o => o.storey === room.storey && o.kind === "window").filter(o => {
      const mid = scale2(add2(o.p0, o.p1), 0.5);
      return room.polygon.some((a, i) => segDist(mid, a, room.polygon[(i + 1) % room.polygon.length]) < o.T / 2 + 0.15)
        && (pointInPoly(add2(mid, scale2(o.n, o.T / 2 + 0.15)), room.polygon) || pointInPoly(add2(mid, scale2(o.n, -(o.T / 2 + 0.15))), room.polygon));
    });
  }
  dressingOf(room, w) {
    return [...this.state.items.values()].find(it => it.room === room.id && slotOf(this.db, it) === "window_dressing"
      && segDist([it.position_m[0], it.position_m[2]], w.p0, w.p1) < w.T / 2 + 0.35) || null;
  }
  setDressing(room, w, entry) {
    const cur = this.dressingOf(room, w);
    const isBlind = entry && /blind|shutter|venetian/i.test(entry.name);
    const width = Math.round((w.width + (isBlind ? 0 : 0.3)) * 1000);
    const height = Math.round(((isBlind ? w.head - w.sill : w.head + 0.2 - room.floor - 0.01)) * 1000);
    const size = entry ? [width, entry.size_mm[1], /café/i.test(entry.name) ? Math.round(height / 2) : height] : null;
    if (!entry && cur) return this.remove(cur);
    if (!entry) return;
    if (cur) {
      const fields = this.swapFields(cur, entry, size);
      fields.position_m = [cur.position_m[0], r3(isBlind ? w.sill : room.floor + 0.01), cur.position_m[2]];
      const before = Object.fromEntries(Object.keys(fields).map(k => [k, clone(cur[k] ?? null)]));
      return this.commit({ op: "item.swap", target: { item: cur.id }, summary: `${cap(w.label)}: ${cur.type} changed for ${entry.name}`, before: { fields: before }, after: { fields, entry: entry.id } });
    }
    const mid = scale2(add2(w.p0, w.p1), 0.5);
    let n = w.n; if (!pointInPoly(add2(mid, scale2(n, w.T / 2 + 0.15)), room.polygon)) n = scale2(n, -1);
    const D = entry.size_mm[1] / 1000, p = add2(mid, scale2(n, w.T / 2 + D / 2 + (isBlind ? -w.T / 2 + 0.03 : 0.02)));
    const it = this.itemFromEntry(entry, room, { size_mm: size, position_m: [r3(p[0]), r3(isBlind ? w.sill : room.floor + 0.01), r3(p[1])],
      yaw_deg: normDeg(Math.atan2(-n[0], -n[1]) * 180 / Math.PI) });
    return this.commit({ op: "item.add", target: { item: it.id }, summary: `${cap(w.label)}: added ${entry.name} (#${it.num})`, before: null, after: { items: [it] } });
  }

  /* ---------------------------------------------------------------- controls */
  bindUI() {
    $("verSeg").addEventListener("click", e => { const b = e.target.closest("button"); if (b) this.setVersion(b.dataset.v); });
    $("storeySeg").addEventListener("click", e => { const b = e.target.closest("button"); if (b) this.setStorey(b.dataset.s); });
    $("backBtn").onclick = () => this.back();
    $("zoomIn").onclick = () => this.plan.zoomBy(0.75);
    $("zoomOut").onclick = () => this.plan.zoomBy(1.33);
    $("zoomFit").onclick = () => { this.plan.fit(); this.plan.render(); };
    $("snapBtn").onclick = () => { this.plan.snapOn = !this.plan.snapOn; $("snapBtn").setAttribute("aria-pressed", String(this.plan.snapOn)); $("snapBtn").textContent = this.plan.snapOn ? "Snap on" : "Snap off"; };
    $("addBtn").onclick = () => this.room && openCatalogue(this, this.room);
    $("threeBtn").onclick = () => this.toggle3D();
    $("undoBtn").onclick = () => this.undo();
    $("redoBtn").onclick = () => this.redo();
    $("changesBtn").onclick = () => openChanges(this);
    $("sendBtn").onclick = () => openChanges(this, true);
    $("themeBtn").onclick = () => {
      const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      const next = cur === "dark" ? "light" : "dark";
      try { localStorage.setItem("planner:theme", next); } catch {}
      this.applyTheme(next); this.render(true);
    };
    window.addEventListener("keydown", e => {
      if (e.target.closest("input, textarea, select") || document.querySelector(".modal")) { if (e.key === "Escape") document.querySelector(".modal")?.remove(); return; }
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? this.redo() : this.undo(); return; }
      if (mod && e.key.toLowerCase() === "y") { e.preventDefault(); this.redo(); return; }
      if (e.key === "Escape") { if (this.selected) this.select(null); else if (this.roomId) this.back(); return; }
      const it = this.selected && this.state.items.get(this.selected);
      if (!it || !this.room) return;
      const step = e.shiftKey ? 0.01 : 0.05;
      const k = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
      if (k) { e.preventDefault(); this.nudge(it, k[0], k[1]); return; }
      if (e.key === "r" || e.key === "R") this.rotateBy(it, e.shiftKey ? 90 : -90);
      else if (e.key === "[") this.rotateBy(it, 15);
      else if (e.key === "]") this.rotateBy(it, -15);
      else if (e.key === "d" || e.key === "D") this.duplicate(it);
      else if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); this.remove(it); }
    });
  }
}

new App().start();
