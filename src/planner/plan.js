import {floorRecipe} from '../furnish/floor-recipe.mjs';
/* Room planner: the top-down plan (SVG, world units = metres; screen x = x, screen y = z, so the road is at the bottom
 * and the garden at the top, as on the architect's plans). Overview = a whole storey, tap a room to open it.
 * Room view = that room large, items draggable with snapping (50 mm grid, walls, other items), a rotate handle,
 * keyboard nudges; other rooms are dimmed. */
import { s, clear, clamp, mm, r3, bbox, labelPoint, pointInPoly, axes, add2, sub2, scale2, dot2, rot, len2, normDeg, mix, D2R } from "./util.js?v=p8";
import { sizeM, itemFootprint, shapeOf, mountOf, slotOf, partColour, roomWalls, roomFloor, carriedBy, entryOf } from "./data.js?v=p8";
import { wallFaces } from './shared.mjs';
import { swingPolys } from "./checks.js?v=p8";

const GRID = 0.05;
const MOUNT_ORDER = { floor: 1, surface: 2, wall: 3, window: 4, ceiling: 5 };

export class PlanView {
  constructor(svg, opts) {
    this.svg = svg; this.o = opts; this.db = opts.db;
    this.vb = { x: 0, y: 0, w: 10, h: 10 };
    this.pointers = new Map();
    this.snapOn = true;
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    this.root = s("g", { class: "world" });
    svg.append(this.root);
    this.bind();
    new ResizeObserver(() => { if (this.state) { this.applyVB(); this.renderLabelsSoon(); } }).observe(svg);
  }

  /* ---------------------------------------------------------------- public */
  show({ state, storey, mode, roomId, selected, warnings, keepView }) {
    const changedView = this.mode !== mode || this.roomId !== roomId || this.storey !== storey || this.state?.vkey !== state.vkey;
    Object.assign(this, { state, storey, mode, roomId, selected, warnings: warnings || new Map() });
    if (changedView && !keepView) this.fit();
    this.render();
  }
  fit() {
    const H = this.state.house;
    let b;
    if (this.mode === "room" && this.roomId) {
      const r = H.roomById.get(this.roomId);
      const pb = bbox(r.polygon);
      const pad = Math.max(0.35, Math.max(pb.w, pb.d) * 0.08);
      b = { x0: pb.x0 - pad, z0: pb.z0 - pad, x1: pb.x1 + pad, z1: pb.z1 + pad };
    } else b = H.extent[this.storey];
    this.vb = { x: b.x0, y: b.z0, w: b.x1 - b.x0, h: b.z1 - b.z0 };
    /* leave room under the floating tool cards */
    const rect = this.svg.getBoundingClientRect();
    if (rect.width && rect.height) {
      const top = rect.width < 760 ? 120 : 64, kk = Math.max(this.vb.w / rect.width, this.vb.h / (rect.height - top));
      this.vb.y -= top * kk; this.vb.h += top * kk;
    }
    this.home = { ...this.vb };
    this.applyVB();
  }
  zoomBy(f) { const c = [this.vb.x + this.vb.w / 2, this.vb.y + this.vb.h / 2]; this.zoomAt(c, f); this.renderLabelsSoon(); }
  applyVB() { const v = this.vb; this.svg.setAttribute("viewBox", `${v.x} ${v.y} ${v.w} ${v.h}`); }
  /* metres per screen pixel */
  k() {
    const r = this.svg.getBoundingClientRect();
    if (!r.width || !r.height) return 0.01;
    return Math.max(this.vb.w / r.width, this.vb.h / r.height);
  }
  toWorld(ev) {
    const pt = this.svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
    const m = this.svg.getScreenCTM(); if (!m) return [0, 0];
    const p = pt.matrixTransform(m.inverse()); return [p.x, p.y];
  }

  /* ---------------------------------------------------------------- drawing */
  render() {
    const st = this.state, H = st.house, db = this.db, storey = this.storey, k = this.k();
    clear(this.root);
    const L = n => this.root.appendChild(s("g", { class: "layer-" + n }));
    const gRooms = L("rooms"), gBands = L("bands"), gStairs = L("stairs"), gFix = L("fixtures"), gItems = L("items"),
          gWalls = L("walls"), gOpen = L("openings"), gBadges = L("badges"), gLabels = L("labels"), gGuides = L("guides"), gFaces = L("wall-faces"), gSel = L("sel");
    this.layers = { gItems, gBadges, gGuides, gSel, gLabels };
    const rooms = H.rooms.filter(r => r.storey === storey);
    const focus = this.mode === "room" ? this.roomId : null;

    /* rooms: floor tint + the wall colour as an inner band */
    for (const r of rooms) {
      const fl = roomFloor(db, st, r), wc = roomWalls(db, st, r);
      const dim = focus && r.id !== focus;
      const pts = r.polygon.map(p => p.join(",")).join(" ");
      const recipe=floorRecipe(fl),pat='photo-'+r.id;
      if(recipe.photo)gRooms.append(s('pattern',{id:pat,patternUnits:'userSpaceOnUse',width:recipe.repeat[0],height:recipe.repeat[1]},s('image',{href:new URL('../../tools/library/kit/maps/'+recipe.source,import.meta.url).href,width:recipe.repeat[0],height:recipe.repeat[1]})));
      gRooms.append(s("polygon", { points: pts, class: "room" + (dim ? " dim" : "") + (focus === r.id ? " focus" : ""), "data-room": r.id,
        style: `--floor:${fl.hex};${recipe.photo?"fill:url(#"+pat+")":""}` }, s("title", { text: `${r.name} · ${r.area.toFixed(1)} m²` })));
      if (!dim) {
        gBands.append(s("polygon", { points: pts, class: "band", style: `stroke:${wc.hex}`, "stroke-width": this.mode === "room" ? 7 : 3 }));
        for (const f of wallFaces(st,r.id)) {
          if(focus===r.id&&f.a&&f.b)gFaces.append(s('line',{x1:f.a[0],y1:f.a[1],x2:f.b[0],y2:f.b[1],stroke:this.o.wallId?.()===f.id?'#26cfea':'transparent','stroke-width':10,'vector-effect':'non-scaling-stroke','pointer-events':'stroke','data-face':f.id}));
          const colour=st.wallColours?.[f.id];
          if (f.a && colour) gBands.append(s('line',{x1:f.a[0],y1:f.a[1],x2:f.b[0],y2:f.b[1],class:'band accent',style:'stroke:'+colour,'stroke-width':this.mode==='room'?9:4}));
        }
        const acc = st.rooms.get(r.id)?.accent;
        if (acc && acc.edge !== undefined && r.polygon[acc.edge]) {
          const a = r.polygon[acc.edge], b = r.polygon[(acc.edge + 1) % r.polygon.length];
          gBands.append(s("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], class: "band accent", style: `stroke:${acc.hex}`, "stroke-width": this.mode === "room" ? 9 : 4 }));
        }
      }
    }
    /* stairs */
    for (const sTr of H.stairs) {
      const upper = storey !== "ground";
      if (sTr.landing) { gStairs.append(s("polygon", { points: sTr.poly.map(p => p.join(",")).join(" "), class: "stair" + (upper ? " upper" : "") })); continue; }
      for (const t of sTr.treads) gStairs.append(s("polygon", { points: t.map(p => p.join(",")).join(" "), class: "stair" + (upper ? " upper" : "") }));
      if (!upper && sTr.base < 0.1) {
        const a = sTr.start, b = add2(a, scale2(sTr.dir, sTr.going * (sTr.risers - 0.5)));
        gStairs.append(s("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], class: "stair-arrow", "marker-end": "url(#arrow)" }));
      }
    }
    /* drawn fixtures (chimney breasts, piers) at this storey */
    const fy = H.ffl[storey];
    for (const fx of H.fixtures) if (fx.y0 < fy + 2.2 && fx.y1 > fy + 0.3) gFix.append(s("polygon", { points: fx.poly.map(p => p.join(",")).join(" "), class: "fixture" }, s("title", { text: fx.id })));

    /* walls with their openings cut out */
    const byWall = new Map();
    for (const o of H.openings) if (o.storey === storey) (byWall.get(o.wall) || byWall.set(o.wall, []).get(o.wall)).push(o);
    for (const w of H.walls) {
      if (w.storey !== storey) continue;
      const ops = (byWall.get(w.id) || []).map(o => [dot2(sub2(o.p0, w.a), w.t), dot2(sub2(o.p1, w.a), w.t)].sort((a, b) => a - b)).sort((a, b) => a[0] - b[0]);
      let u = 0;
      const segs = [];
      for (const [u0, u1] of ops) { if (u0 > u + 0.001) segs.push([u, u0]); u = Math.max(u, u1); }
      if (w.L > u + 0.001) segs.push([u, w.L]);
      for (const [u0, u1] of segs) {
        const a = add2(w.a, scale2(w.t, u0)), b = add2(w.a, scale2(w.t, u1)), hn = scale2(w.n, w.T / 2);
        const q = [add2(a, hn), add2(b, hn), sub2(b, hn), sub2(a, hn)];
        gWalls.append(s("polygon", { points: q.map(p => p.join(",")).join(" "), class: "wall" + (w.neighbour ? " neighbour" : "") }));
      }
    }
    /* openings: windows (frame lines + glass), doors (leaf + swing arc), bi-folds (zig-zag) */
    for (const o of H.openings) {
      if (o.storey !== storey) continue;
      const hn = scale2(o.n, o.T / 2);
      if (o.kind === "window") {
        const q = [add2(o.p0, hn), add2(o.p1, hn), sub2(o.p1, hn), sub2(o.p0, hn)];
        gOpen.append(s("polygon", { points: q.map(p => p.join(",")).join(" "), class: "win-frame" }, s("title", { text: o.label })));
        for (const f of [-0.12, 0.12]) {
          const a = add2(o.p0, scale2(o.n, f * o.T)), b = add2(o.p1, scale2(o.n, f * o.T));
          gOpen.append(s("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], class: "win-glass" }));
        }
        continue;
      }
      gOpen.append(s("line", { x1: add2(o.p0, hn)[0], y1: add2(o.p0, hn)[1], x2: sub2(o.p0, hn)[0], y2: sub2(o.p0, hn)[1], class: "jamb" }));
      gOpen.append(s("line", { x1: add2(o.p1, hn)[0], y1: add2(o.p1, hn)[1], x2: sub2(o.p1, hn)[0], y2: sub2(o.p1, hn)[1], class: "jamb" }));
      for (const l of o.leaves) {
        if (l.bifold) {
          const n = 4, side = l.side || 1, pts = [];
          for (let i = 0; i <= n; i++) pts.push(add2(add2(o.p0, scale2(o.t, (o.width * i) / n)), scale2(o.n, side * (i % 2 ? 0.16 : 0) + side * o.T / 2)));
          gOpen.append(s("polyline", { points: pts.map(p => p.join(",")).join(" "), class: "leaf bifold" }, s("title", { text: o.label + " (bi-fold)" })));
          continue;
        }
        const sw = swingPolys({ openings: [{ ...o, leaves: [l] }] }, storey)[0];
        if (sw) gOpen.append(s("polyline", { points: sw.poly.slice(1).map(p => p.join(",")).join(" "), class: "swing" + (l.source === "derived" ? " derived" : "") }));
        gOpen.append(s("line", { x1: l.hinge[0], y1: l.hinge[1], x2: l.open[0], y2: l.open[1], class: "leaf" }, s("title", { text: o.label + (l.source === "derived" ? " (swing derived)" : "") })));
      }
    }

    /* items */
    const items = [...st.items.values()].filter(it => H.roomById.get(it.room)?.storey === storey && it.size_mm[0] > 0);
    items.sort((a, b) => (MOUNT_ORDER[mountOf(db, a)] - MOUNT_ORDER[mountOf(db, b)]) || (shapeOf(db, a) === "rug" ? -1 : shapeOf(db, b) === "rug" ? 1 : 0)
      || (b.size_mm[0] * b.size_mm[1] - a.size_mm[0] * a.size_mm[1]));
    this.itemEls = new Map();
    for (const it of items) {
      const mine = !focus || it.room === focus;
      const g = this.itemGroup(it, mine);
      gItems.append(g);
      this.itemEls.set(it.id, g);
    }
    this.renderBadges(items, focus, k);
    this.renderLabels(rooms, k);
    this.renderSelection();
  }

  itemGroup(it, mine) {
    const db = this.db, st = this.state;
    const [W, D] = sizeM(it), shape = shapeOf(db, it), mount = mountOf(db, it);
    const col = partColour(db, st, it, mainPart(it), "#C9C2B6").hex;
    const warn = this.warnings.get(it.id);
    const cls = ["it", "m-" + mount, "sh-" + shape, mine ? "mine" : "other", warn ? "warn" : "", it.id === this.selected ? "selected" : ""].filter(Boolean).join(" ");
    const g = s("g", { class: cls, "data-id": it.id, transform: tf(it), style: `--c:${col}` });
    for (const e of symbol(shape, W, D, it)) g.append(e);
    g.append(s("title", { text: `#${it.num} ${it.type}${warn ? "\n⚠ " + warn.map(w => w.text).join("\n⚠ ") : ""}` }));
    return g;
  }

  renderBadges(items, focus, k) {
    const g = this.layers.gBadges; clear(g);
    const big = this.mode === "room";
    for (const it of items) {
      if (focus && it.room !== focus) continue;
      const small = it.size_mm[0] * it.size_mm[1] < 0.12e6 || mountOf(this.db, it) !== "floor";
      const r = (big ? (small ? 8.5 : 10.5) : small ? 5.5 : 7.5) * k;
      const p = badgePos(it, this.db);
      const warn = this.warnings.get(it.id);
      const b = s("g", { class: "badge" + (small ? " s" : "") + (warn ? " warn" : "") + (it.id === this.selected ? " selected" : "") + (it.added ? " added" : "") + (it.swapped ? " swapped" : ""), "data-id": it.id, transform: `translate(${p[0]} ${p[1]})` });
      b.append(s("circle", { r }), s("text", { y: r * 0.36, "font-size": r * 1.0, text: String(it.num) }));
      if (warn && big) b.append(s("circle", { class: "warn-dot", cx: r * 0.8, cy: -r * 0.8, r: r * 0.38 }));
      g.append(b);
    }
  }
  renderLabels(rooms, k) {
    const g = this.layers.gLabels; clear(g);
    const big = this.mode !== "room";
    for (const r of rooms) {
      if (this.mode === "room" && r.id === this.roomId) continue;
      const p = labelPoint(r.polygon), fs = (big ? 12.5 : 11) * k;
      const name = shortName(r.name);
      const t = s("text", { x: p[0], y: p[1], "font-size": fs, "stroke-width": 3 * k, class: "rl" + (this.mode === "room" ? " dim" : "") }, name);
      g.append(t);
      if (big) g.append(s("text", { x: p[0], y: p[1] + fs * 1.15, "font-size": fs * 0.82, "stroke-width": 3 * k, class: "ra", text: `${r.area.toFixed(1)} m²` }));
    }
  }
  renderLabelsSoon() {
    clearTimeout(this._lt);
    this._lt = setTimeout(() => { if (this.state) this.render(); }, 140);
  }

  renderSelection() {
    const g = this.layers.gSel; clear(g);
    const it = this.selected && this.state.items.get(this.selected);
    if (!it || this.mode !== "room" || it.room !== this.roomId) return;
    const k = this.k(), [W, D] = sizeM(it);
    const fp = itemFootprint(it, [Math.max(W, 0.06), Math.max(D, 0.06)]);
    g.append(s("polygon", { points: fp.map(p => p.join(",")).join(" "), class: "sel-box" }));
    const { f } = axes(it.yaw_deg || 0), c = [it.position_m[0], it.position_m[2]];
    const hp = add2(c, scale2(f, Math.max(D, 0.06) / 2 + 26 * k));
    const ep = add2(c, scale2(f, Math.max(D, 0.06) / 2));
    g.append(s("line", { x1: ep[0], y1: ep[1], x2: hp[0], y2: hp[1], class: "rot-stem" }));
    g.append(s("circle", { cx: hp[0], cy: hp[1], r: 9 * k, class: "rot-handle", "data-rot": it.id }, s("title", { text: "Drag to turn (15° steps)" })));
    /* the front edge, so it is clear which way the piece faces */
    const { u } = axes(it.yaw_deg || 0);
    const a = add2(ep, scale2(u, -Math.max(W, 0.06) / 2)), b = add2(ep, scale2(u, Math.max(W, 0.06) / 2));
    g.append(s("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], class: "front-edge" }));
  }

  /* ---------------------------------------------------------------- interaction */
  bind() {
    const svg = this.svg;
    svg.addEventListener("wheel", ev => {
      ev.preventDefault();
      const f = Math.exp(clamp(ev.deltaY, -60, 60) * (ev.ctrlKey ? 0.012 : 0.0025));
      this.zoomAt(this.toWorld(ev), f);
      this.renderLabelsSoon();
    }, { passive: false });
    svg.addEventListener("pointerdown", ev => this.down(ev));
    svg.addEventListener("pointermove", ev => this.move(ev));
    svg.addEventListener("pointerup", ev => this.up(ev));
    svg.addEventListener("pointercancel", ev => this.up(ev, true));
    svg.addEventListener("dblclick", ev => { if (this.mode === "room" && !ev.target.closest(".it")) { this.fit(); this.render(); } });
  }
  zoomAt([x, y], f) {
    const v = this.vb, home = this.home || v;
    const nw = clamp(v.w * f, home.w * 0.08, home.w * 3), nf = nw / v.w;
    this.vb = { x: x - (x - v.x) * nf, y: y - (y - v.y) * nf, w: v.w * nf, h: v.h * nf };
    this.applyVB();
  }
  down(ev) {
    this.svg.setPointerCapture?.(ev.pointerId);
    const w = this.toWorld(ev);
    this.pointers.set(ev.pointerId, { x: ev.clientX, y: ev.clientY, w });
    if (this.pointers.size === 2) { const first=this.drag; this.drag=null; this.pinch=this.pinchStart(first); return; }
    const rotEl = ev.target.closest("[data-rot]");
    const itEl = ev.target.closest(".it.mine, .badge");
    const roomEl = ev.target.closest("[data-room]");
    if (this.mode==='room' && !rotEl && this.o.placeAt?.(w)) {this.drag=null;ev.preventDefault();return;}
    if(ev.target.dataset.face){this.o.pickWall(ev.target.dataset.face);ev.preventDefault();return;}
    if (this.mode === "room" && rotEl) {
      const it = this.state.items.get(rotEl.dataset.rot);
      this.drag = { kind: "rotate", it, start: w, yaw0: it.yaw_deg || 0, carried: carriedBy(this.db, this.state, it).map(c => ({ it: c, p0: c.position_m.slice(), y0: c.yaw_deg || 0 })) };
      ev.preventDefault(); return;
    }
    if (this.mode === "room" && itEl) {
      const it = this.state.items.get(itEl.dataset.id);
      if (it && it.room === this.roomId) {
        this.o.onSelect?.(it.id);
        this.drag = { kind: "item", it, start: w, p0: it.position_m.slice(), moved: false,
                      carried: carriedBy(this.db, this.state, it).map(c => ({ it: c, p0: c.position_m.slice(), y0: c.yaw_deg || 0 })) };
        ev.preventDefault(); return;
      }
    }
    this.drag = { kind: "pan", start: w, sx: ev.clientX, sy: ev.clientY, vb0: { ...this.vb }, room: roomEl?.dataset.room || null, item: itEl?.dataset.id || null, moved: false };
  }
  pinchStart(first) {
    const [a, b] = [...this.pointers.values()];
    return { d0: Math.hypot(a.x - b.x, a.y - b.y), vb0: { ...this.vb }, mid: [(a.w[0] + b.w[0]) / 2, (a.w[1] + b.w[1]) / 2],
      it:first?.it?.shared?first.it:null, angle:Math.atan2(b.y-a.y,b.x-a.x) };
  }
  move(ev) {
    const p = this.pointers.get(ev.pointerId);
    if (!p) { this.hover(ev); return; }
    p.x = ev.clientX; p.y = ev.clientY;
    if (this.pinch && this.pointers.size === 2) {
      const [a, b] = [...this.pointers.values()], d = Math.hypot(a.x - b.x, a.y - b.y) || 1;
      const gesture=this.pinch;
      if(gesture.it) {
        const delta=normDeg((gesture.angle-Math.atan2(b.y-a.y,b.x-a.x))/D2R);
        if(Math.abs(delta)<2 && !gesture.pose)return;
        const it=gesture.it;gesture.pose=this.o.onPose(it,it.position_m,normDeg(it.yaw_deg+delta),true);
        this.preview(it,gesture.pose.row.position,gesture.pose.row.rotation);
        this.itemEls.get(it.id)?.classList.toggle('blocked',!gesture.pose.ok);return;
      }
      this.vb = { ...this.pinch.vb0 }; this.zoomAt(this.pinch.mid, this.pinch.d0 / d); return;
    }
    const d = this.drag; if (!d) return;
    const w = this.toWorld(ev);
    if (d.kind === "pan") {
      const r = this.svg.getBoundingClientRect(), kk = Math.max(d.vb0.w / r.width, d.vb0.h / r.height);
      const dx = (ev.clientX - d.sx) * kk, dy = (ev.clientY - d.sy) * kk;
      if (Math.hypot(ev.clientX - d.sx, ev.clientY - d.sy) > 5) d.moved = true;
      if (d.moved) { this.vb = { ...d.vb0, x: d.vb0.x - dx, y: d.vb0.y - dy }; this.applyVB(); }
      return;
    }
    if (d.kind === "item") {
      const kpx = this.k();
      if (!d.moved && len2(sub2(w, d.start)) < 4 * kpx) return;
      d.moved = true;
      let nx = d.p0[0] + (w[0] - d.start[0]), nz = d.p0[2] + (w[1] - d.start[1]);
      const snapped = this.snapOn && !ev.altKey && !ev.shiftKey ? this.snap(d.it, nx, nz) : { x: nx, z: nz, guides: [] };
      d.cur = [snapped.x, snapped.z];
      if (d.it.shared) {
        d.pose=this.o.onPose(d.it,[nx,d.p0[1],nz],d.it.yaw_deg||0,ev.shiftKey||ev.altKey||!this.snapOn);
        const {position,rotation}=d.pose.row;
        this.preview(d.it,position,rotation); this.itemEls.get(d.it.id)?.classList.toggle('blocked',!d.pose.ok);
        for (const ch of d.carried) this.preview(ch.it,[ch.p0[0]+position[0]-d.p0[0],ch.p0[1]+position[1]-d.p0[1],ch.p0[2]+position[2]-d.p0[2]],ch.y0);
        return;
      }
      this.drawGuides(snapped.guides);
      this.preview(d.it, [snapped.x, d.p0[1], snapped.z], d.it.yaw_deg || 0);
      for (const c of d.carried) this.preview(c.it, [c.p0[0] + snapped.x - d.p0[0], c.p0[1], c.p0[2] + snapped.z - d.p0[2]], c.y0);
      return;
    }
    if (d.kind === "rotate") {
      const c = [d.it.position_m[0], d.it.position_m[2]], v = sub2(w, c);
      let yaw = Math.atan2(-v[0], -v[1]) / D2R;
      yaw = ev.shiftKey ? Math.round(yaw) : Math.round(yaw / 15) * 15;
      d.cur = normDeg(yaw);
      if (d.it.shared) d.pose=this.o.onPose(d.it,d.it.position_m,d.cur,true);
      const dy = d.cur - d.yaw0;
      this.preview(d.it, d.it.position_m, d.cur);
      if(d.pose) this.itemEls.get(d.it.id)?.classList.toggle('blocked',!d.pose.ok);
      for (const ch of d.carried) {
        const rel = rot([ch.p0[0] - c[0], ch.p0[2] - c[1]], dy);
        this.preview(ch.it, [c[0] + rel[0], ch.p0[1], c[1] + rel[1]], normDeg(ch.y0 + dy));
      }
    }
  }
  up(ev, cancel) {
    this.pointers.delete(ev.pointerId);
    if (this.pinch) {
      if (this.pointers.size<2) {
        const pose=this.pinch.pose;this.pinch=null;
        if (pose && !cancel && pose.ok) this.o.onDrop(pose.row);
        else {if(pose && !cancel)this.o.onBlocked(pose.reasons[0]);this.render();}
      }
      this.drag=null;return;
    }
    const d = this.drag; this.drag = null;
    if (!d) return;
    this.drawGuides([]);
    if (cancel) { this.render(); return; }
    if(d.pose) {
      if(d.pose.ok) this.o.onDrop(d.pose.row);
      else { this.o.onBlocked(d.pose.reasons[0]); this.render(); }
      return;
    }
    if (d.kind === "pan") {
      if (d.moved) { this.renderLabelsSoon(); return; }
      if (d.item && this.mode !== "room") { const it = this.state.items.get(d.item); if (it) this.o.onOpenRoom?.(it.room, it.id); return; }
      if (d.room) {
        if (this.mode !== "room") this.o.onOpenRoom?.(d.room);
        else if (d.room !== this.roomId) this.o.onOpenRoom?.(d.room);
        else this.o.onSelect?.(null);
      } else if (this.mode === "room") this.o.onSelect?.(null);
      return;
    }
    if (d.kind === "item" && d.moved && d.cur) {
      const to = [r3(d.cur[0]), d.p0[1], r3(d.cur[1])];
      const newRoom = this.state.house.roomAt(to[0], to[2], this.storey)?.id || d.it.room;
      this.o.onCommit?.({ kind: "move", it: d.it, from: d.p0, to, room: newRoom,
        carried: d.carried.map(c => ({ id: c.it.id, from: c.p0, to: [r3(c.p0[0] + to[0] - d.p0[0]), c.p0[1], r3(c.p0[2] + to[2] - d.p0[2])], yaw: c.y0, room: newRoom })) });
      return;
    }
    if (d.kind === "rotate" && d.cur !== undefined && d.cur !== d.yaw0) {
      const c = [d.it.position_m[0], d.it.position_m[2]], dy = d.cur - d.yaw0;
      this.o.onCommit?.({ kind: "rotate", it: d.it, from: d.yaw0, to: d.cur,
        carried: d.carried.map(ch => { const rel = rot([ch.p0[0] - c[0], ch.p0[2] - c[1]], dy);
          return { id: ch.it.id, from: ch.p0, to: [r3(c[0] + rel[0]), ch.p0[1], r3(c[1] + rel[1])], yawFrom: ch.y0, yaw: normDeg(ch.y0 + dy) }; }) });
      return;
    }
    this.render();
  }
  hover(ev) {
    if (this.mode === "room") return;
    const r = ev.target.closest?.("[data-room]");
    for (const e of this.root.querySelectorAll(".room.hover")) e.classList.remove("hover");
    if (r) r.classList.add("hover");
  }
  preview(it, pos, yaw) {
    const g = this.itemEls?.get(it.id); if (!g) return;
    g.setAttribute("transform", tf({ position_m: pos, yaw_deg: yaw }));
    const b = this.layers.gBadges.querySelector(`[data-id="${CSS.escape(it.id)}"]`);
    if (b) { const p = badgePos({ ...it, position_m: pos, yaw_deg: yaw }, this.db); b.setAttribute("transform", `translate(${p[0]} ${p[1]})`); }
    clear(this.layers.gSel);
  }
  drawGuides(guides) {
    const g = this.layers?.gGuides; if (!g) return; clear(g);
    const v = this.vb;
    for (const gd of guides) {
      if (gd.x !== undefined) g.append(s("line", { x1: gd.x, y1: v.y, x2: gd.x, y2: v.y + v.h, class: "guide" + (gd.wall ? " wall" : "") }));
      else g.append(s("line", { x1: v.x, y1: gd.z, x2: v.x + v.w, y2: gd.z, class: "guide" + (gd.wall ? " wall" : "") }));
    }
  }

  /* snapping: walls first, then other pieces' edges, then the 50 mm grid (per axis); only for square-on pieces */
  snap(it, x, z) {
    const yaw = normDeg(it.yaw_deg || 0), [W, D] = sizeM(it);
    const square = Math.abs(yaw % 90) < 0.01;
    const guides = [];
    if (!square) return { x: Math.round(x / GRID) * GRID, z: Math.round(z / GRID) * GRID, guides };
    const swap = Math.abs(Math.abs(yaw) - 90) < 0.01;
    const hx = (swap ? D : W) / 2, hz = (swap ? W : D) / 2;
    const thr = clamp(12 * this.k(), 0.02, 0.15);
    const room = this.state.house.roomById.get(this.roomId);
    const xs = [], zs = [];
    for (let i = 0; i < room.polygon.length; i++) {
      const a = room.polygon[i], b = room.polygon[(i + 1) % room.polygon.length];
      if (Math.abs(a[0] - b[0]) < 0.005) xs.push({ v: a[0], lo: Math.min(a[1], b[1]), hi: Math.max(a[1], b[1]), wall: true });
      if (Math.abs(a[1] - b[1]) < 0.005) zs.push({ v: a[1], lo: Math.min(a[0], b[0]), hi: Math.max(a[0], b[0]), wall: true });
    }
    const skip = new Set([it.id, ...carriedBy(this.db, this.state, it).map(c => c.id)]);
    const myMount = mountOf(this.db, it);
    for (const o of this.state.items.values()) {
      if (skip.has(o.id) || o.room !== this.roomId || mountOf(this.db, o) !== myMount || shapeOf(this.db, o) === "rug") continue;
      if (!o.size_mm[0]) continue;
      const fp = itemFootprint(o), b = bbox(fp);
      xs.push({ v: b.x0, lo: b.z0, hi: b.z1 }, { v: b.x1, lo: b.z0, hi: b.z1 }, { v: b.cx, lo: b.z0, hi: b.z1, centre: true });
      zs.push({ v: b.z0, lo: b.x0, hi: b.x1 }, { v: b.z1, lo: b.x0, hi: b.x1 }, { v: b.cz, lo: b.x0, hi: b.x1, centre: true });
    }
    const pick = (c, h, lines, near) => {
      let best = null;
      for (const L of lines) {
        const cands = L.centre ? [[c, L.v]] : [[c - h, L.v], [c + h, L.v]];
        for (const [edge, v] of cands) {
          const dd = Math.abs(edge - v);
          if (dd < thr && (!best || dd < best.d)) best = { d: dd, shift: v - edge, line: L };
        }
      }
      return best;
    };
    const bx = pick(x, hx, xs), bz = pick(z, hz, zs);
    let nx = bx ? x + bx.shift : Math.round((x - hx) / GRID) * GRID + hx;
    let nz = bz ? z + bz.shift : Math.round((z - hz) / GRID) * GRID + hz;
    if (bx) guides.push({ x: bx.line.v, wall: !!bx.line.wall });
    if (bz) guides.push({ z: bz.line.v, wall: !!bz.line.wall });
    return { x: nx, z: nz, guides };
  }
}

/* ---------------------------------------------------------------- symbols (local frame: width along x, front at y = -D/2) */
function tf(it) { return `translate(${it.position_m[0]} ${it.position_m[2]}) rotate(${-(it.yaw_deg || 0)})`; }
function badgePos(it, db) {
  const [W, D] = sizeM(it), { f } = axes(it.yaw_deg || 0), m = mountOf(db, it);
  /* wall pieces: pull the number into the room so it does not sit on the wall line */
  const off = m === "wall" || m === "window" ? D / 2 + 0.12 : 0;
  return add2([it.position_m[0], it.position_m[2]], scale2(f, off));
}
export function mainPart(it) {
  const m = it.materials || {};
  for (const p of ["upholstery", "front", "body", "frame", "top", "all", "fabric", "shade"]) if (m[p]) return p;
  return Object.keys(m)[0] || "all";
}
const R = (x, y, w, h, cls, extra) => s("rect", { x, y, width: Math.max(w, 0.001), height: Math.max(h, 0.001), class: cls, ...extra });
function symbol(shape, W, D, it) {
  const x0 = -W / 2, y0 = -D / 2, t = (it.type || "").toLowerCase();
  const round = /round|disc|globe|drum|bowl|dia\b/.test(t) && Math.abs(W - D) < 0.05;
  const out = [];
  switch (shape) {
    case "sofa": case "armchair": {
      const arm = Math.min(0.16, W * 0.1), back = Math.min(0.22, D * 0.25);
      out.push(R(x0, y0, W, D, "body", { rx: 0.05 }));
      out.push(R(x0 + arm, D / 2 - back, W - 2 * arm, back, "line-in"));
      out.push(R(x0, y0 + 0.02, arm, D - 0.02, "line-in", { rx: 0.03 }), R(W / 2 - arm, y0 + 0.02, arm, D - 0.02, "line-in", { rx: 0.03 }));
      const seats = shape === "armchair" ? 1 : W > 1.8 ? 3 : 2;
      for (let i = 1; i < seats; i++) { const x = x0 + arm + ((W - 2 * arm) * i) / seats; out.push(s("line", { x1: x, y1: y0 + 0.03, x2: x, y2: D / 2 - back, class: "line-in" })); }
      break;
    }
    case "bed": {
      out.push(R(x0, y0, W, D, "body", { rx: 0.03 }));
      out.push(R(x0, D / 2 - 0.07, W, 0.07, "line-in dark"));
      const pw = (W - 0.18) / 2;
      out.push(R(x0 + 0.06, D / 2 - 0.42, pw, 0.3, "line-in", { rx: 0.06 }), R(0.03, D / 2 - 0.42, pw, 0.3, "line-in", { rx: 0.06 }));
      out.push(s("path", { d: `M ${x0} ${D / 2 - 0.62} L ${W / 2} ${D / 2 - 0.62}`, class: "line-in" }));
      out.push(s("path", { d: `M ${x0 + 0.05} ${y0 + D * 0.32} Q 0 ${y0 + D * 0.27} ${W / 2 - 0.05} ${y0 + D * 0.32}`, class: "line-in" }));
      break;
    }
    case "table": case "bench": {
      if (round || /round|bistro|circular/.test(t)) out.push(s("ellipse", { cx: 0, cy: 0, rx: W / 2, ry: D / 2, class: "body" }));
      else out.push(R(x0, y0, W, D, "body", { rx: 0.02 }));
      break;
    }
    case "chair": case "stool": {
      if (shape === "stool" || round) out.push(s("circle", { cx: 0, cy: 0, r: Math.min(W, D) / 2, class: "body" }));
      else {
        out.push(R(x0 + 0.02, y0, W - 0.04, D - 0.06, "body", { rx: 0.04 }));
        out.push(R(x0, D / 2 - 0.08, W, 0.08, "line-in dark", { rx: 0.03 }));
      }
      break;
    }
    case "cabinet": case "tall_cabinet": case "kitchen_unit": case "wall_cabinet": case "shelving": {
      out.push(R(x0, y0, W, D, "body"));
      out.push(s("line", { x1: x0, y1: y0 + 0.012, x2: W / 2, y2: y0 + 0.012, class: "front-line" }));
      if (shape === "tall_cabinet" || /tall|housing|broom|fridge/.test(t)) out.push(s("path", { d: `M ${x0} ${y0} L ${W / 2} ${D / 2} M ${W / 2} ${y0} L ${x0} ${D / 2}`, class: "line-in" }));
      if (shape === "wall_cabinet") out.push(s("path", { d: `M ${x0} ${y0} L ${W / 2} ${D / 2}`, class: "line-in" }));
      if (/sink/.test(t)) out.push(R(-0.2, y0 + 0.08, 0.4, 0.38, "line-in", { rx: 0.05 }));
      if (/hob|oven/.test(t)) for (const [cx, cz] of [[-0.18, -0.08], [0.18, -0.08], [-0.18, 0.13], [0.18, 0.13]]) out.push(s("circle", { cx, cy: cz, r: 0.08, class: "line-in" }));
      if (/island/.test(t)) out.push(R(x0 + 0.03, y0 + 0.03, W - 0.06, D - 0.06, "line-in"));
      if (shape === "shelving") for (let i = 1; i < 4; i++) out.push(s("line", { x1: x0 + (W * i) / 4, y1: y0, x2: x0 + (W * i) / 4, y2: D / 2, class: "line-in" }));
      break;
    }
    case "rug": out.push(R(x0, y0, W, D, "rug")); out.push(R(x0 + 0.06, y0 + 0.06, Math.max(0.01, W - 0.12), Math.max(0.01, D - 0.12), "rug-in")); break;
    case "cushion": case "throw": out.push(R(x0, y0, W, D, "soft", { rx: 0.03 })); break;
    case "floor_lamp": case "table_lamp": {
      const r = Math.min(W, D) / 2;
      out.push(s("circle", { cx: 0, cy: 0, r, class: "body lamp" }), s("path", { d: `M ${-r * 0.6} 0 L ${r * 0.6} 0 M 0 ${-r * 0.6} L 0 ${r * 0.6}`, class: "line-in" }));
      break;
    }
    case "pendant": case "flush": case "downlights": case "wall_light": {
      if (W > D * 2.5) out.push(R(x0, y0, W, D, "ceiling"));   // no rx: a dashed rounded rect with non-scaling stroke breaks Chromium's painting
      else { const r = Math.max(Math.min(W, D) / 2, 0.05); out.push(s("circle", { cx: 0, cy: 0, r, class: "ceiling" }), s("path", { d: `M ${-r * 0.7} ${-r * 0.7} L ${r * 0.7} ${r * 0.7} M ${r * 0.7} ${-r * 0.7} L ${-r * 0.7} ${r * 0.7}`, class: "ceiling-x" })); }
      break;
    }
    case "plant": {
      const r = Math.min(W, D) / 2;
      out.push(s("circle", { cx: 0, cy: 0, r, class: "plant" }));
      for (let i = 0; i < 6; i++) { const a = (i / 6) * Math.PI * 2; out.push(s("line", { x1: 0, y1: 0, x2: Math.cos(a) * r * 0.85, y2: Math.sin(a) * r * 0.85, class: "plant-in" })); }
      break;
    }
    case "curtains": {
      const n = Math.max(3, Math.round(W / 0.12));
      let d = `M ${x0} ${D / 2}`;
      for (let i = 0; i < n; i++) { const xa = x0 + (W * (i + 0.5)) / n, xb = x0 + (W * (i + 1)) / n; d += ` Q ${xa} ${D / 2 - Math.min(0.09, D) * (i % 2 ? 1 : -0.2)} ${xb} ${D / 2}`; }
      out.push(R(x0, y0, W, D, "hit"), s("path", { d, class: "curtain" }));
      break;
    }
    case "frame": case "mirror": case "tv": case "radiator":
      out.push(R(x0, y0, W, Math.max(D, 0.02), shape === "tv" ? "body dark" : "body thin"));
      if (shape === "radiator") for (let i = 1; i < 8; i++) out.push(s("line", { x1: x0 + (W * i) / 8, y1: y0, x2: x0 + (W * i) / 8, y2: D / 2, class: "line-in" }));
      break;
    case "wc": out.push(R(x0 + W * 0.05, D / 2 - D * 0.28, W * 0.9, D * 0.28, "body"), s("ellipse", { cx: 0, cy: y0 + D * 0.36, rx: W * 0.42, ry: D * 0.34, class: "body" })); break;
    case "basin": out.push(R(x0, y0, W, D, "body", { rx: 0.03 }), s("ellipse", { cx: 0, cy: -0.02, rx: W * 0.36, ry: D * 0.3, class: "line-in" })); break;
    case "shower": out.push(R(x0, y0, W, D, "body"), s("path", { d: `M ${x0} ${y0} L ${W / 2} ${D / 2} M ${W / 2} ${y0} L ${x0} ${D / 2}`, class: "line-in" }), s("circle", { cx: 0, cy: 0, r: 0.04, class: "line-in" })); break;
    case "bath": out.push(R(x0, y0, W, D, "body", { rx: 0.06 }), R(x0 + 0.06, y0 + 0.06, W - 0.12, D - 0.12, "line-in", { rx: 0.15 })); break;
    case "books": case "small": default:
      if (round) out.push(s("circle", { cx: 0, cy: 0, r: W / 2, class: "body" }));
      else out.push(R(x0, y0, W, D, "body", { rx: Math.min(0.02, W / 4) }));
  }
  return out;
}
const shortName = n => n.replace(/\s*\((?:front|rear|ex\.|vaulted|under stairs|open plan|uPVC[^)]*)[^)]*\)/i, "").replace(/^cpd/, "cupboard");
