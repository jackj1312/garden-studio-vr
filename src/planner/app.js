/* Room planner (planner.html): review and edit the signed-off design spec, room by room.
 * Opens on the 2D plan; the 3D preview loads only when asked for. Every edit becomes one change in the change list
 * (store.js); "Send to build" writes the batch the next spec version is made from. The spec itself is read-only. */
import { h, clear, r3, mm, normDeg, rot, add2, sub2, scale2, dot2, len2, segDist, pointInPoly, labelPoint, centroid, moveWords, axes, cap, uid } from "./util.js?v=p8";
import { loadAll, entryOf, slotOf, sizeM, carriedBy, mountOf } from "./data.js?v=p8";
import { ChangeStore } from "./store.js?v=p8";
import { PlanView } from "./plan.js?v=p8";
import { checkRoom, fitsAt } from "./checks.js?v=p8";
import { renderOverview, renderRoom, renderItem, openCatalogue, openChanges } from "./panel.js?v=p8";
import { plannerEntry, projectRoomState, wallFaces } from './shared.mjs';
import { FurnitureLayout } from '../furnish/layout.mjs';
import { buildRoomContext, fineMove, snapPlacement, assessDesign, validateFurnishDelta, moveGroup } from '../furnish/placement.mjs';

const params = new URLSearchParams(globalThis.location?.search || '');
const SITE = params.get("site") || "house-wip";
const $ = id => document.getElementById(id);
const label = it => `${it.type} (#${it.num})`;
const clone = o => JSON.parse(JSON.stringify(o));
const pose = it => ({ position_m: it.position_m.slice(), yaw_deg: it.yaw_deg || 0, room: it.room });

export class App {
  constructor() {
    this.vkey = "after"; this.storey = "ground"; this.roomId = null; this.selected = null;
    this.ui = { wallStyle: "Contemporary", three: false };
    this.warnings = new Map(); this.roomWarn = new Map();
    this.sessions = new Map(); this.editOrder=[]; this.redoOrder=[];
  }
  async start() {
    this.applyTheme(localStorage.getItem("planner:theme"));
    const insp = $("inspector");
    insp.append(h("div.sec", null, h("p.muted", { text: "Loading the spec and the house plan…" })));
    try { this.db = await loadAll(SITE); }
    catch (e) { clear(insp).append(h("div.sec", null, h("h2", { text: "Could not load the spec" }), h("p.small", { text: String(e.message || e) }))); return; }
    for (const raw of this.db.kit.items) this.db.entries.set(raw.id, plannerEntry(raw));
    this.store = new ChangeStore(this.db.specSite);
    this.store.on(r => { if (r === "offline") this.toast("Lost the studio server: changes now stay on this device until it is back."); if (String(r).startsWith("uploaded")) this.toast(`Uploaded ${r.split(":")[1]} change(s) made on this device.`); });
    await this.store.load();
    this.plan = new PlanView($("plan"), { db: this.db, onSelect: id => this.select(id), onOpenRoom: (r, it) => this.openRoom(r, it), onCommit: c => this.commitDrag(c),
      wallId:()=>this.ui.wallId,pickWall:id=>{this.ui.wallId=id;this.select(null);},
      onPose:(it,position,yaw,free)=>this.assessPose(it,position,yaw,free), onDrop:row=>this.putFurniture(row), onBlocked:r=>this.toast(r) });
    this.plan.o.placeAt=p=>{if (!this.pendingEntry) return false; const {entry,room}=this.pendingEntry; this.placeEntry(entry,room,p); return true;};
    this.bindUI();
    this.fromHash();
    await this.loadFurniture();
    this.recompute(); this.render();
    window.addEventListener("hashchange", async () => { if (this._settingHash) return; this.fromHash(); await this.loadFurniture(); this.recompute(); this.render(); });
    const refresh = async () => {
      if (document.visibilityState !== 'visible' || this.plan.drag) return;
      const shared=this.session;
      try {
        if (shared?.ready && !shared.layout.dirty && !shared.layout.saving) await shared.layout.refresh();
        else if (shared && !shared.ready) await this.loadFurniture(true);
      } catch(e) { if (shared) shared.message=e.message; }
      if (await this.store.refresh()) this.afterChange(true);
    };
    setInterval(refresh,15000); document.addEventListener('visibilitychange',refresh);
    window.planner = this;      // for checks from the console
  }

  /* ---------------------------------------------------------------- state */
  recompute() {
    this.state = projectRoomState(this.db, this.vkey, this.store.applied, this.session);
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
  get session() { return this.sessions.get(this.vkey); }
  async loadFurniture(retry=false) {
    const key=this.vkey, version=this.db.versions[key].elements;
    if (!retry && this.sessions.has(key)) return this.sessions.get(key).loading;
    const s=this.sessions.get(key) || {ready:false, version, message:''};
    this.sessions.set(key,s);
    if (s.loading) return s.loading;
    s.layout ??= new FurnitureLayout({site:SITE,version,onChange:()=>{
      if (s.ready && this.session===s && this.state) this.afterChange();
    }});
    s.loading=(async()=>{
      try {
        const read=async name=>{const r=await fetch(`assets/sites/${SITE}/furnish/${version}/${name}.json`);if(!r.ok) throw Error('Room '+name+' unavailable ('+r.status+').');return r.json();};
        const [variants,seed]=await Promise.all([read('variants'),read('seed'),s.layout.load()]);
        const context=buildRoomContext({site:SITE,version,spec:this.db.spec,elements:this.db.elements[key],doors:this.db.doors,
          catalogue:this.db.kit,floorCatalogue:this.db.catalogue,variants,seed});
        for(const id of seed.appliedChangeIds || []) this.store.imported.add(id);
        s.moveReceipts = seed.moveReceipts || [];
        s.context=context; s.variants=variants; s.ready=true; s.message='';
      } catch(e) { s.message='Shared layout unavailable. '+e.message; }
      finally { s.loading=null; }
    })();
    return s.loading;
  }

  /* ---------------------------------------------------------------- navigation */
  fromHash() {
    const p = location.hash.replace(/^#/, "").split("/");
    const requested=new URLSearchParams(location.search).get('version');
    const byVersion=Object.entries(this.db.versions).find(([k,v])=>k===requested || v.elements===requested)?.[0];
    if (p[0] === "before" || p[0] === "after") this.vkey = p[0]; else if (byVersion) this.vkey=byVersion;
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
    this.pendingEntry=null;
    this.roomId = roomId; this.storey = this.house.roomById.get(roomId).storey; this.selected = itemId;
    this.warnings = this.warningsFor(roomId);
    this.setHash(); this.render();
  }
  back() { this.pendingEntry=null; this.roomId = null; this.selected = null; this.setHash(); this.render(); }
  select(id, scroll = false) {
    this.selected = id;
    this.render(true);
    if (scroll) $("inspector").scrollTop = 0;
  }
  async setVersion(v) {
    if (v === this.vkey) return;
    const keepRoom = this.roomId && this.db.versions[v].roomById.has(this.roomId) ? this.roomId : null;
    this.vkey = v; await this.loadFurniture(); if (this.vkey !== v) return;
    const url=new URL(location.href); url.searchParams.set('version',this.db.versions[v].elements); history.replaceState(null,'',url);
    this.recompute();
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
    $("hint").textContent = this.pendingEntry?'Tap a position for '+this.pendingEntry.entry.name+' · Esc cancels':room ? "Drag to move · handle to turn · arrows fine-adjust" : "Tap a room to open it";
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
    const shared=this.session, layout=shared?.layout;
    $("undoBtn").disabled = !(layout?.canUndo || s.canUndo(this.vkey)); $("redoBtn").disabled = !(layout?.canRedo || s.canRedo(this.vkey));
    $("sendBtn").disabled = !n;
    const c = $("conn"); c.className = s.mode;
    const status=layout?.conflict?'Another device saved · local draft kept':shared?.message || (layout?.dirty?'Unsaved room layout':s.mode==='server'?'Saved to the studio':'On this device');
    c.querySelector("span").textContent = status; c.title=status;
    $("saveLayout").disabled = !shared?.ready || !layout?.dirty || layout.saving || layout.conflict;
    $("reloadLayout").hidden = !layout?.conflict;
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
        const { Preview3D } = await import("./view3d.js?v=p8");
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
  changeFurniture(work) {
    const s=this.session;
    if (!s?.ready) { this.toast(s?.message || 'Load this room layout before editing.'); return false; }
    try {
      if(work(s.layout)===false)return false;
      this.editOrder.push({key:this.vkey, lane:'layout'}); this.redoOrder=[];
      this.afterChange(); return true;
    } catch(e) { this.toast(e.message); return false; }
  }
  assessPose(it, position, yaw, free=false) {
    if (!it.shared || !this.session?.ready) return null;
    const {context,layout}=this.session, row={...it.shared,position:[...position],rotation:yaw};
    const room=this.house.roomAt(position[0],position[2],this.house.roomById.get(it.room)?.storey);
    row.room=room?.id || it.room;
    if (row.host.type==='floor'||row.host.type==='ceiling') row.host={type:row.host.type,id:row.host.type+'/'+row.room};
    const snapped=snapPlacement(context,layout.items,row,{free});
    return {row:snapped,...assessDesign(context,layout.items,snapped)};
  }
  putFurniture(row) {
    const {context,layout}=this.session, check=assessDesign(context,layout.items,row);
    if (!check.ok) { this.toast(check.reasons[0]); this.render(true); return false; }
    this.selected=row.id; return this.changeFurniture(s=>s.put(row));
  }
  placeEntry(entry,room,point=null) {
    const session=this.session;
    if (!session?.ready) { this.toast(session?.message || 'The shared layout is still loading.'); return; }
    const {context,layout}=session, center=labelPoint(room.polygon), hostType=entry.host;
    const id='P-'+crypto.randomUUID();
    const base={id,catalogueId:entry.id,variant:entry.id,kind:entry.kind,style:entry.style,room:room.id,size:entry.size_m.slice(),rotation:0};
    const points=[];
    if (hostType==='wall') {
      const faces=wallFaces(this.state,room.id).filter(f=>f.a).sort((a,b)=>len2(sub2(b.b,b.a))-len2(sub2(a.b,a.a)));
      for (const f of faces) for (const t of [.5,.25,.75]) {
        const mid=point || add2(f.a,scale2(sub2(f.b,f.a),t));
        points.push({p:mid,host:f, y:room.floor+Math.max(.05,(room.ceiling-room.floor-base.size[2])*.5),rot:Math.atan2(-f.normal[0],-f.normal[1])*180/Math.PI});
      }
    } else if (hostType==='surface') {
      const supports=[...layout.items.filter(o=>o.room===room.id && o.host.type==='floor').map(o=>({id:o.id,p:[o.position[0],o.position[2]],y:o.position[1]+o.size[2]})),
        ...context.hosts.filter(o=>o.room===room.id && o.type==='surface' && o.bounds).map(o=>({id:o.id,p:[(o.bounds[0][0]+o.bounds[1][0])/2,(o.bounds[0][2]+o.bounds[1][2])/2],y:o.bounds[1][1]}))];
      const origin=point||center;
      supports.sort((a,b)=>len2(sub2(a.p,origin))-len2(sub2(b.p,origin)));
      for(const s of supports) points.push({p:point||s.p,y:s.y,host:{type:'surface',id:s.id}});
    } else {
      const host={type:hostType,id:hostType+'/'+room.id}, y=hostType==='ceiling'?room.ceiling-base.size[2]:room.floor;
      if (point) points.push({p:point,host,y});
      else {
        const xs=room.polygon.map(p=>p[0]), zs=room.polygon.map(p=>p[1]);
        for(let x=Math.min(...xs)+.1;x<=Math.max(...xs);x+=.26) for(let z=Math.min(...zs)+.1;z<=Math.max(...zs);z+=.26)
          if(pointInPoly([x,z],room.polygon)) points.push({p:[r3(x),r3(z)],host,y});
        points.sort((a,b)=>len2(sub2(a.p,center))-len2(sub2(b.p,center)));
        points.unshift({p:center,host,y});
      }
    }
    if(!points.length)points.push({p:point||center,host:{type:'free',id:'room/'+room.id},y:room.floor});
    let reason='Choose a suitable host in this room.';
    for (const {p,host,y,rot=0} of points) {
      const row=snapPlacement(context,layout.items,{...base,host:{type:host.type,id:host.id},position:[p[0],y,p[1]],rotation:rot},{free:false});
      const check=assessDesign(context,layout.items,row);
      if (check.ok) { this.pendingEntry=null; return this.putFurniture(row); }
      reason=check.reasons[0] || reason;
    }
    this.pendingEntry={entry,room}; this.toast(reason+' Tap another spot in the room.'); this.render(true);
  }
  async saveLayout() {
    const s=this.session;
    if (!s?.ready) return;
    try { await s.layout.save(); s.message=''; this.toast('Layout saved for '+this.house.name+'.'); }
    catch(e) { s.message=e.message; this.toast('Your room draft is still here. '+e.message); }
    this.renderTop();
  }
  async commit(change) {
    const it=this.state.items.get(change.target?.item);
    if (it?.shared) {
      if (change.op==='item.move') {
        const pose=this.assessPose(it,change.after.position_m,change.after.yaw_deg,true);
        if (!pose.ok) { this.toast(pose.reasons[0]); this.render(true); return; }
        return this.putFurniture(pose.row);
      }
      if (change.op==='item.delete') return this.changeFurniture(s=>s.remove(it.id));
      if (change.op==='item.finish') return this.changeFurniture(s=>s.put({...it.shared,finishes:{...it.shared.finishes,[change.after.part]:change.after.value.hex}}));
      if (change.op==='item.lamp') return this.changeFurniture(s=>s.put({...it.shared,lampOn:change.after.on}));
    }
    if (!this.session?.ready && (/^item\.(move|swap|add|delete)$/.test(change.op) || ['room.walls','room.accent','room.floor'].includes(change.op))) {
      this.toast(this.session?.message || 'Load the shared room layout before editing.'); return;
    }
    const c = await this.store.add({ version: this.vkey, room: change.room || this.roomId, ...change });
    this.editOrder.push({key:this.vkey,lane:'spec',id:c.id}); this.redoOrder=[];
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
    if (it.shared) return this.copyFurniture(it);
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
  copyFurniture(it) {
    const session=this.session, all=session.layout.items, group=[it.shared];
    for (let i=0;i<group.length;i++) for (const o of all)
      if (['surface','item'].includes(o.host.type) && o.host.id===group[i].id && !group.some(p=>p.id===o.id)) group.push(o);
    const ids=new Map(group.map(o=>[o.id,'P-'+crypto.randomUUID()]));
    const [w,d]=it.shared.size;
    let why='No space to duplicate this item.';
    for(const [dx,dz] of [[w+.03,0],[-w-.03,0],[0,d+.03],[0,-d-.03],[w+.03,d+.03],[-w-.03,-d-.03]]) {
      const source=it.shared;
      const shifted=moveGroup(all,{...source,position:[r3(source.position[0]+dx),source.position[1],r3(source.position[2]+dz)]});
      const copied=shifted.map(o=>({...o,id:ids.get(o.id),host:{...o.host,id:ids.get(o.host.id)||o.host.id}}));
      const before={items:all,wallColours:session.layout.wallColours,roomFloors:session.layout.roomFloors};
      try { validateFurnishDelta(session.context,before,{...before,items:[...all,...copied]}); }
      catch(e) {why=e.message;continue;}
      this.selected=copied[0].id; return this.changeFurniture(s=>s.putMany(copied));
    }
    this.toast(why);
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
    if (entry.kit) return this.placeEntry(entry,room);
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
  swapCandidate(it,entry) {
    const {layout,context}=this.session;
    const row={...it.shared,catalogueId:entry.id,variant:entry.id,kind:entry.kind,style:entry.style,size:entry.size_m.slice(),
      position:this.swapPose(it,entry),finishes:{}};
    const candidate=snapPlacement(context,layout.items,row,{free:true});
    return {row:candidate,...assessDesign(context,layout.items,candidate)};
  }
  swap(it, entry, sizeOverride) {
    if (it.shared) {
      if (!entry.kit) { this.toast('Choose a Studio kit model for this item.'); return; }
      const change=this.swapCandidate(it,entry);
      if(!change.ok) {this.toast(change.reasons[0]);return;}
      return this.putFurniture(change.row);
    }
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
    const shared=lights.filter(l=>l.shared);
    if(shared.length) this.changeFurniture(s=>s.putMany(shared.map(l=>({...l.shared,lampOn:on})),'Room lamps'));
    lights=lights.filter(l=>!l.shared); if(!lights.length)return;
    return this.commit({ op: "room.lamps", target: { room: room.id }, summary: `All ${lights.length} lights in the ${room.name} ${on ? "on" : "off"}`,
      before: { states: lights.map(l => [l.id, !!l.lampOn]) }, after: { ids: lights.map(l => l.id), on } });
  }
  setRoom(room, field, value) {
    if (field==='floor') return this.changeFurniture(s=>s.setFloor(room.id,value?.id || null));
    if (field==='walls') return this.changeFurniture(s=>s.setWalls([...new Set(wallFaces(this.state,room.id).map(f=>f.id))],value?.hex || null));
    const cur = this.state.rooms.get(room.id)?.[field] ?? null;
    const words = { walls: "Walls", accent: "Accent wall", floor: "Floor", fronts: "Kitchen fronts", island_fronts: "Island fronts", worktop: "Worktops" }[field];
    const summary = value ? `${words} of the ${room.name}: ${value.name}${value.hex ? " (" + value.hex + ")" : ""}` : `${words} of the ${room.name}: removed`;
    return this.commit({ op: "room." + field, target: { room: room.id }, summary, before: { value: cur }, after: { value } });
  }
  addNote(target, text) {
    const what = target.item ? label(this.state.items.get(target.item)) : `the ${this.house.roomById.get(target.room).name}`;
    return this.commit({ op: "note", target, summary: `Note on ${what}: “${text.slice(0, 80)}${text.length > 80 ? "…" : ""}”`, before: null, after: { text } });
  }
  async history(redo=false) {
    const s=this.session?.layout, order=redo?this.redoOrder:this.editOrder, other=redo?this.editOrder:this.redoOrder;
    const i=order.findLastIndex(c=>c.key===this.vkey), event=order[i];
    const roomOp=redo?'canRedo':'canUndo', op=redo?'redo':'undo';
    if ((event?.lane==='layout' || !event) && s?.[roomOp]) {
      s[op](); if(event) order.splice(i,1); other.push({key:this.vkey,lane:'layout'}); this.afterChange(); return;
    }
    const c=await this.store[op](this.vkey);
    if(c) { if(event) order.splice(i,1); other.push({key:this.vkey,lane:'spec',id:c.id}); this.toast(c.summary); this.afterChange(); }
  }
  undo() { return this.history(); }
  redo() { return this.history(true); }

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
    if(entry?.kit && (!cur || cur.shared)) {
      const point=scale2(add2(w.p0,w.p1),.5);
      if(cur) return this.swap(cur,entry);
      return this.placeEntry(entry,room,point);
    }
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
    $("saveLayout").onclick=()=>this.saveLayout();
    $("reloadLayout").onclick=async()=>{ if (!window.confirm('Discard this local room draft and load the studio layout?')) return;
      try { await this.session.layout.load({discardDraft:true}); this.session.message=''; this.afterChange(); } catch(e){this.toast(e.message);} };
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
      if (e.key === "Escape") { if (this.pendingEntry) {this.pendingEntry=null;this.render(true);} else if (this.selected) this.select(null); else if (this.roomId) this.back(); return; }
      const it = this.selected && this.state.items.get(this.selected);
      if (!it || !this.room) return;
      const fine=it.shared && fineMove(it.shared,e.key,e.shiftKey);
      if(fine){e.preventDefault();this.putFurniture(fine);return;}
      const step = e.shiftKey ? 0.001 : 0.01;
      const k = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
      if (k) { e.preventDefault(); this.nudge(it, k[0], k[1]); return; }
      if (e.key === "r" || e.key === "R") this.rotateBy(it, e.shiftKey ? 90 : -90);
      else if (e.key === "[") this.rotateBy(it, 15);
      else if (e.key === "]") this.rotateBy(it, -15);
      else if (e.key.toLowerCase() === "q") this.rotateBy(it, 15);
      else if (e.key.toLowerCase() === "e") this.rotateBy(it, -15);
      else if (e.key === "d" || e.key === "D") this.duplicate(it);
      else if (e.key === "Delete" || e.key === "Backspace") { e.preventDefault(); this.remove(it); }
    });
  }
}

if (globalThis.document) new App().start();
