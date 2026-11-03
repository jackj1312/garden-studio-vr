/* Room planner: the optional 3D preview of one room (three.js r185). Loaded only when "Show 3D preview" is pressed
 * (Jack, 1 Nov: plan first, before any 3D time is spent). Deliberately light: proportioned boxes and cylinders in the
 * item's colours, the room's wall colour and floor finish, windows and doors as openings. No models, no textures from
 * disk, no shadows; it renders only when something changes. Walls between the camera and the room fade out. */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { bbox, dot2, sub2, add2, scale2, len2, norm2, segDist, hexToRgb, mix } from "./util.js?v=p8";
import { sizeM, shapeOf, mountOf, partColour, roomWalls, roomFloor } from "./data.js?v=p8";
import { mainPart } from "./plan.js?v=p8";
import {createFurnitureModels} from '../furnish/models.js';
import {wallFaces} from './shared.mjs';

const UNIT = new THREE.BoxGeometry(1, 1, 1);
const CYL = new THREE.CylinderGeometry(0.5, 0.5, 1, 20);
const CONE = new THREE.CylinderGeometry(0.32, 0.5, 1, 20, 1, true);
const SPH = new THREE.SphereGeometry(0.5, 16, 12);

export class Preview3D {
  constructor(container, { db, onSelect }) {
    this.db = db; this.onSelect = onSelect; this.el = container;
    const r = this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    r.setPixelRatio(Math.min(devicePixelRatio, 1.75));
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.toneMapping = THREE.NeutralToneMapping;
    container.append(r.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.05, 80);
    this.controls = new OrbitControls(this.camera, r.domElement);
    this.controls.enableDamping = true; this.controls.maxPolarAngle = Math.PI * 0.49; this.controls.minDistance = 1.2; this.controls.maxDistance = 22;
    this.controls.addEventListener("change", () => this.request());
    this.scene.add(new THREE.HemisphereLight(0xfffaf0, 0xb8ad9c, 2.4));
    this.scene.add(new THREE.AmbientLight(0xffffff, 0.5));
    const sun = new THREE.DirectionalLight(0xfff1dd, 1.5); sun.position.set(-4, 8, -3); this.scene.add(sun);
    this.room = new THREE.Group(); this.items = new THREE.Group(); this.scene.add(this.room, this.items);
    this.mats = new Map();
    this.ray = new THREE.Raycaster();
    let down = null;
    r.domElement.addEventListener("pointerdown", e => { down = [e.clientX, e.clientY]; });
    r.domElement.addEventListener("pointerup", e => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5) return;
      const b = r.domElement.getBoundingClientRect();
      this.ray.setFromCamera(new THREE.Vector2(((e.clientX - b.left) / b.width) * 2 - 1, -((e.clientY - b.top) / b.height) * 2 + 1), this.camera);
      const hit = this.ray.intersectObjects(this.items.children.filter(o=>!o.userData.helper), true)[0];
      const runtime=this.furniture?.pick(this.ray.ray,hit?.distance ?? Infinity);
      if(runtime) { this.onSelect?.(runtime.id); return; }
      let o = hit?.object; while (o && !o.userData.itemId) o = o.parent;
      this.onSelect?.(o?.userData.itemId || null);
    });
    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
  }
  dispose() { this.furniture?.dispose(); this.renderer.dispose(); this.renderer.domElement.remove(); this.disposed = true; }
  resize() {
    const w = this.el.clientWidth || 1, h = this.el.clientHeight || 1;
    this.renderer.setSize(w, h, false); this.camera.aspect = w / h; this.camera.updateProjectionMatrix(); this.request();
  }
  request() { if (this.raf || this.disposed) return; this.raf = requestAnimationFrame(() => { this.raf = 0; this.frame(); }); }
  frame() {
    if (this.controls.update()) this.request();
    /* fade the walls between the camera and the room */
    const cam = this.camera.position;
    for (const w of this.walls || []) {
      const toCam = [cam.x - w.userData.mid[0], cam.z - w.userData.mid[1]];
      const facing = dot2(toCam, w.userData.out) > 0.2;
      for (const m of w.userData.mats) { m.opacity = facing ? 0.12 : 1; m.transparent = facing; m.depthWrite = !facing; }
    }
    this.renderer.render(this.scene, this.camera);
  }
  mat(hex, o = {}) {
    const key = hex + JSON.stringify(o);
    if (!this.mats.has(key) || o.unique) {
      const m = new THREE.MeshStandardMaterial({ color: new THREE.Color(hex), roughness: o.rough ?? 0.85, metalness: o.metal ?? 0,
        transparent: !!o.opacity, opacity: o.opacity ?? 1, emissive: o.emissive ? new THREE.Color(o.emissive) : undefined, emissiveIntensity: o.ei ?? 0 });
      if (o.unique) return m;
      this.mats.set(key, m);
    }
    return this.mats.get(key);
  }

  /* ---------------------------------------------------------------- the room shell */
  show(state, roomId, selected) {
    const first = this.roomId !== roomId || this.vkey !== state.vkey;
    if ((!state.runtime || this.modelVersion!==state.house.elements) && this.furniture) {this.furniture.dispose();this.furniture=null;}
    if(state.runtime && !this.furniture) {
      this.modelVersion=state.house.elements;
      this.furniture=createFurnitureModels({THREE,scene:this.scene,site:this.db.site,version:this.modelVersion,variants:state.variants,catalogue:this.db.kit,onChange:()=>this.request()});
    }
    this.state = state; this.roomId = roomId; this.vkey = state.vkey;
    this.buildShell();
    this.buildItems(selected);
    if(this.furniture) this.furniture.set(state.layoutItems,{room:roomId}).catch(e=>{
      const label=this.el.querySelector('.three-label'); if(label) label.textContent='Room model unavailable · '+e.message;
    });
    if (first) this.frameCamera();
    this.request();
  }
  frameCamera() {
    const r = this.state.house.roomById.get(this.roomId), b = bbox(r.polygon), f = r.floor;
    const span = Math.max(b.w, b.d);
    this.controls.target.set(b.cx, f + 0.8, b.cz);
    const dist = (span * 1.3 + 2.4) / Math.min(1, this.camera.aspect * 1.15), dir = new THREE.Vector3(0.35, 0.95, 0.75).normalize();   // from the road side, high
    this.camera.position.set(b.cx + dir.x * dist, f + 0.8 + dir.y * dist, b.cz + dir.z * dist);
    this.controls.update();
  }
  buildShell() {
    disposeGroup(this.room);
    const st = this.state, H = st.house, room = H.roomById.get(this.roomId), db = this.db;
    const poly = room.polygon, f = room.floor, ht = Math.min(room.height || 2.4, 3.2);
    /* floor with a light pattern drawn on a canvas */
    const fl = roomFloor(db, st, room);
    const shape = new THREE.Shape(poly.map(([x, z]) => new THREE.Vector2(x, -z)));
    const g = new THREE.ShapeGeometry(shape); g.rotateX(-Math.PI / 2);
    const uv = g.attributes.uv, pos = g.attributes.position;
    for (let i = 0; i < uv.count; i++) uv.setXY(i, pos.getX(i), pos.getZ(i));
    const tex = floorTexture(fl);
    const fm = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.75 });
    const floor = new THREE.Mesh(g, fm); floor.position.y = f; this.room.add(floor);
    /* walls: one slab outside each edge of the room polygon, cut where an opening sits on that edge */
    const wc = roomWalls(db, st, room), acc = st.rooms.get(room.id)?.accent;
    const area = signedArea(poly);
    this.walls = [];
    for (let i = 0; i < poly.length; i++) {
      const a = poly[i], b = poly[(i + 1) % poly.length], L = len2(sub2(b, a));
      if (L < 0.03) continue;
      const t = norm2(sub2(b, a)), out = area > 0 ? [t[1], -t[0]] : [-t[1], t[0]];
      /* make sure "out" points away from the room */
      const mid = scale2(add2(a, b), 0.5);
      const outN = insideTest(add2(mid, scale2(out, 0.05)), poly) ? scale2(out, -1) : out;
      const cuts = [];
      for (const o of H.openings) {
        if (o.storey !== room.storey) continue;
        if (Math.abs(dot2(o.t, t)) < 0.95) continue;
        const dMid = segDist(scale2(add2(o.p0, o.p1), 0.5), a, b);
        if (dMid > o.T / 2 + 0.12) continue;
        let u0 = dot2(sub2(o.p0, a), t), u1 = dot2(sub2(o.p1, a), t); if (u0 > u1) [u0, u1] = [u1, u0];
        u0 = Math.max(0, u0); u1 = Math.min(L, u1);
        if (u1 - u0 < 0.05) continue;
        cuts.push({ u0, u1, y0: Math.max(0, o.sill - f), y1: Math.min(ht, o.head - f), o });
      }
      const colour = acc && acc.edge === i ? acc.hex : wc.hex;
      const wm = this.mat(colour, { unique: true, rough: 0.95 });
      const grp = new THREE.Group(); grp.userData = { mid, out: outN, mats: [wm] };
      const painted=wallFaces(st,room.id,i).filter(face=>face.a && st.wallColours?.[face.id]).map(face=>{
        const ends=[face.a,face.b].map(p=>dot2(sub2(p,a),t)).sort((x,y)=>x-y);
        const mat=this.mat(st.wallColours[face.id],{unique:true,rough:.95});grp.userData.mats.push(mat);
        return {from:Math.max(0,ends[0]),to:Math.min(L,ends[1]),mat,bottom:Math.max(0,face.bottom-f),top:Math.min(ht,face.top-f)};
      });
      const thick = 0.1, cx = (u, y, w, hh) => {
        const breaks=(low,high,values)=>[low,...new Set(values.filter(v=>v>low+.0001 && v<high-.0001).sort((a,b)=>a-b)),high];
        const us=breaks(u,u+w,painted.flatMap(p=>[p.from,p.to])),ys=breaks(y,y+hh,painted.flatMap(p=>[p.bottom,p.top]));
        for(let j=1;j<us.length;j++) for(let k=1;k<ys.length;k++) {
          const z=(us[j-1]+us[j])/2, elev=(ys[k-1]+ys[k])/2, mat=painted.find(p=>p.from<=z && p.to>=z && p.bottom<=elev && p.top>=elev)?.mat;
          const p=add2(a,scale2(t,z)), q=add2(p,scale2(outN,thick/2)), m=new THREE.Mesh(UNIT,mat||wm);
          m.scale.set(us[j]-us[j-1],ys[k]-ys[k-1],thick); m.position.set(q[0],f+elev,q[1]);
          m.rotation.y=Math.atan2(-t[1],t[0]);grp.add(m);
        }
      };
      cuts.sort((p, q) => p.u0 - q.u0);
      let u = 0;
      for (const c of cuts) {
        if (c.u0 > u) cx(u, 0, c.u0 - u, ht);
        if (c.y0 > 0.01) cx(c.u0, 0, c.u1 - c.u0, c.y0);
        if (c.y1 < ht - 0.01) cx(c.u0, c.y1, c.u1 - c.u0, ht - c.y1);
        this.openingDressing(grp, c, a, t, outN, f);
        u = Math.max(u, c.u1);
      }
      if (u < L) cx(u, 0, L - u, ht);
      /* skirting */
      const skm = this.mat("#F2EFEA", { unique: true }), sk = new THREE.Mesh(UNIT, skm);
      const sp = add2(mid, scale2(outN, -0.008)); sk.scale.set(L, 0.145, 0.016); sk.position.set(sp[0], f + 0.072, sp[1]); sk.rotation.y = Math.atan2(-t[1], t[0]);
      grp.userData.mats.push(skm);
      grp.add(sk);
      this.room.add(grp); this.walls.push(grp);
    }
  }
  openingDressing(grp, c, a, t, outN, f) {
    const w = c.u1 - c.u0, hh = c.y1 - c.y0, p = add2(a, scale2(t, (c.u0 + c.u1) / 2)), rotY = Math.atan2(-t[1], t[0]);
    if (c.o.kind === "window") {
      const glass = new THREE.Mesh(UNIT, this.mat("#BFD3DC", { opacity: 0.35, rough: 0.1, unique: true }));
      const q = add2(p, scale2(outN, 0.05)); glass.scale.set(w, hh, 0.01); glass.position.set(q[0], f + c.y0 + hh / 2, q[1]); glass.rotation.y = rotY; grp.add(glass);
      grp.userData.mats.push(glass.material);
      const fm = this.mat("#F4F3EF", { unique: true }); grp.userData.mats.push(fm);
      const bars = [[0, hh / 2, w, 0.05], [0, -hh / 2, w, 0.05], [-w / 2, 0, 0.05, hh], [w / 2, 0, 0.05, hh]];
      for (let i = 1; i < (c.o.lights || 1); i++) bars.push([-w / 2 + (w * i) / c.o.lights, 0, 0.045, hh]);
      for (const [ox, oy, bw, bh] of bars) {
        const m = new THREE.Mesh(UNIT, fm), qq = add2(q, scale2(t, ox));
        m.scale.set(bw, bh, 0.06); m.position.set(qq[0], f + c.y0 + hh / 2 + oy, qq[1]); m.rotation.y = rotY; grp.add(m);
      }
      /* window board */
      const wb = new THREE.Mesh(UNIT, fm), qb = add2(p, scale2(outN, -0.02));
      wb.scale.set(w + 0.06, 0.025, 0.08); wb.position.set(qb[0], f + c.y0, qb[1]); wb.rotation.y = rotY; grp.add(wb);
    } else if (c.o.kind === "bifold") {
      const glass = new THREE.Mesh(UNIT, this.mat("#BFD3DC", { opacity: 0.3, rough: 0.1, unique: true }));
      const q = add2(p, scale2(outN, 0.05)); glass.scale.set(w, hh, 0.02); glass.position.set(q[0], f + c.y0 + hh / 2, q[1]); glass.rotation.y = rotY; grp.add(glass);
      grp.userData.mats.push(glass.material);
    } else {
      /* door leaf, drawn open on its swing */
      for (const l of c.o.leaves) {
        if (!l.radius) continue;
        const v = sub2(l.open, l.hinge), m = new THREE.Mesh(UNIT, this.mat("#F2EFEA"));
        const mid = add2(l.hinge, scale2(v, 0.5));
        m.scale.set(l.radius, Math.min(hh, 2.0), 0.04); m.position.set(mid[0], f + Math.min(hh, 2.0) / 2, mid[1]);
        m.rotation.y = Math.atan2(-v[1], v[0]);
        this.room.add(m);
      }
    }
  }

  /* ---------------------------------------------------------------- items as simple shapes */
  buildItems(selected) {
    disposeGroup(this.items, false);
    for (const L of this.lamps || []) this.scene.remove(L);
    this.lamps = [];
    const st = this.state, room = st.house.roomById.get(this.roomId);
    let lampCount = 0;
    for (const it of st.items.values()) {
      if (it.room !== this.roomId || !it.size_mm[0]) continue;
      if(it.shared) {
        if(it.id===selected) {
          const [w,d,h]=sizeM(it), p=it.position_m;
          const geo=new THREE.BoxGeometry(w,h,d), lines=new THREE.EdgesGeometry(geo);geo.dispose();
          const box=new THREE.LineSegments(lines,new THREE.LineBasicMaterial({color:0x377bb2}));
          box.position.set(p[0],p[1]+h/2,p[2]);box.rotation.y=it.yaw_deg*Math.PI/180;box.userData.helper=true;this.items.add(box);
        }
        if(it.lampOn && lampCount<6 && it.category==='lighting') {
          const lamp=new THREE.PointLight(0xffd9a0,2.2,5,1.6);
          lamp.position.set(it.position_m[0],it.position_m[1]+it.size_mm[2]/1000*.75,it.position_m[2]);this.scene.add(lamp);this.lamps.push(lamp);lampCount++;
        }
        continue;
      }
      const g = this.itemMesh(it);
      g.userData.itemId = it.id;
      g.position.set(it.position_m[0], it.position_m[1], it.position_m[2]);
      g.rotation.y = (it.yaw_deg || 0) * Math.PI / 180;
      if (mountOf(this.db, it) === "ceiling") g.position.y = Math.min(it.position_m[1], room.ceiling) - it.size_mm[2] / 1000;
      this.items.add(g);
      if (it.id === selected) {
        const box = new THREE.BoxHelper(g, 0x2f7fd0); box.userData.helper = true; this.items.add(box);
      }
      if (it.lampOn && lampCount < 6 && /lamp|light|pendant/.test(shapeOf(this.db, it) + it.category)) {
        const L = new THREE.PointLight(0xffd9a0, 2.2, 5, 1.6);
        L.position.set(it.position_m[0], (mountOf(this.db, it) === "ceiling" ? g.position.y : it.position_m[1] + it.size_mm[2] / 1000 * 0.85), it.position_m[2]);
        this.scene.add(L); this.lamps.push(L); lampCount++;
      }
    }
  }
  itemMesh(it) {
    const db = this.db, st = this.state, [W, D, Hh] = sizeM(it), H = Math.max(Hh, 0.01), shape = shapeOf(db, it);
    const c = p => partColour(db, st, it, p, "#C9C2B6").hex;
    const main = c(mainPart(it)), g = new THREE.Group();
    const lit = it.lampOn;
    const box = (w, h, d, x, y, z, hex, o) => { const m = new THREE.Mesh(UNIT, this.mat(hex, o)); m.scale.set(Math.max(w, 0.005), Math.max(h, 0.005), Math.max(d, 0.005)); m.position.set(x, y, z); g.add(m); return m; };
    const cyl = (r, h, x, y, z, hex, o, geo = CYL) => { const m = new THREE.Mesh(geo, this.mat(hex, o)); m.scale.set(r * 2, h, r * 2); m.position.set(x, y, z); g.add(m); return m; };
    const legs = (w, d, h, hex, r = 0.02) => { for (const sx of [-1, 1]) for (const sz of [-1, 1]) cyl(r, h, sx * (w / 2 - r * 2), h / 2, sz * (d / 2 - r * 2), hex); };
    const wood = c("legs") !== main ? c("legs") : "#9C7A55";
    switch (shape) {
      case "sofa": case "armchair": {
        const arm = Math.min(0.16, W * 0.1), back = Math.min(0.22, D * 0.25), seat = H * 0.55;
        box(W, seat - 0.1, D, 0, 0.1 + (seat - 0.1) / 2, 0, main);
        box(W - 2 * arm, H - seat, back, 0, seat + (H - seat) / 2, D / 2 - back / 2, main);
        for (const sx of [-1, 1]) box(arm, H * 0.75 - 0.1, D, sx * (W / 2 - arm / 2), 0.1 + (H * 0.75 - 0.1) / 2, 0, main);
        legs(W, D, 0.1, wood, 0.018);
        break;
      }
      case "bed": {
        box(W, 0.3, D, 0, 0.15, 0, c("frame") || main);
        box(W - 0.05, 0.22, D - 0.1, 0, 0.41, -0.04, "#F6F4EF");
        box(W - 0.02, 0.06, D * 0.62, 0, 0.53, -D * 0.18, c("bedding") || "#F3F1EC");
        for (const sx of [-1, 1]) box((W - 0.2) / 2, 0.12, 0.3, sx * (W / 4), 0.58, D / 2 - 0.3, "#FBFAF7");
        box(W, H, 0.08, 0, H / 2, D / 2 - 0.04, c("frame") || main);
        break;
      }
      case "table": case "bench": case "desk": {
        const round = /round|bistro/i.test(it.type) || Math.abs(W - D) < 0.02 && /table/.test(it.type);
        if (round) cyl(W / 2, 0.035, 0, H - 0.018, 0, main); else box(W, 0.035, D, 0, H - 0.018, 0, main);
        if (round) cyl(0.04, H - 0.035, 0, (H - 0.035) / 2, 0, wood); else legs(W, D, H - 0.035, c("legs") || main, 0.025);
        break;
      }
      case "chair": case "stool": {
        const sh = shape === "stool" ? H : Math.min(0.47, H * 0.5);
        box(W - 0.02, 0.05, D - 0.06, 0, sh, 0, c("seat") || main);
        legs(W - 0.04, D - 0.08, sh, c("legs") || c("frame") || "#3a3a3a", 0.015);
        if (shape === "chair") box(W - 0.04, H - sh, 0.04, 0, sh + (H - sh) / 2, D / 2 - 0.05, c("frame") || main);
        break;
      }
      case "cabinet": case "tall_cabinet": case "wall_cabinet": case "shelving": case "kitchen_unit": {
        const front = c("front") || main, top = c("worktop") || c("top");
        const isTop = shape === "kitchen_unit" && H < 1.2;
        const ch = isTop ? H - 0.03 : H;
        box(W, ch - (shape === "kitchen_unit" ? 0.1 : 0), D - 0.02, 0, (shape === "kitchen_unit" ? 0.1 : 0) + (ch - (shape === "kitchen_unit" ? 0.1 : 0)) / 2, 0.01, front);
        if (shape === "kitchen_unit") box(W, 0.1, D - 0.08, 0, 0.05, 0.04, "#3a3a3a");
        if (isTop) box(W, 0.03, D, 0, H - 0.015, 0, top || "#EEECE8", { rough: 0.35 });
        /* door split lines */
        const n = Math.max(1, Math.round(W / 0.5));
        for (let i = 1; i < n; i++) box(0.004, ch * 0.9, 0.004, -W / 2 + (W * i) / n, ch / 2 + (shape === "kitchen_unit" ? 0.05 : 0), -D / 2 + 0.008, mix(front, "#000000", 0.35));
        if (shape === "shelving") for (let i = 1; i < 5; i++) box(W, 0.02, D, 0, (H * i) / 5, 0, main);
        break;
      }
      case "rug": box(W, Math.min(H, 0.012), D, 0, 0.006, 0, c("rug") || main); break;
      case "cushion": box(W, H, D, 0, H / 2, 0, main, { rough: 1 }); break;
      case "throw": box(Math.min(W, 0.6), 0.05, Math.min(D, 0.45), 0, 0.025, 0, main, { rough: 1 }); break;   // shown folded: it drapes in the build
      case "floor_lamp": case "table_lamp": {
        const r = Math.min(W, D) / 2, shadeH = Math.min(0.35, H * 0.4);
        cyl(r * 0.5, 0.03, 0, 0.015, 0, c("metal") || "#2a2a2a");
        cyl(shape === "table_lamp" ? r * 0.45 : 0.012, H - shadeH, 0, (H - shadeH) / 2, 0, shape === "table_lamp" ? (c("ceramic") || main) : (c("metal") || "#2a2a2a"));
        cyl(r, shadeH, 0, H - shadeH / 2, 0, c("shade") || "#E2D9C9", lit ? { emissive: "#FFD9A0", ei: 1.2 } : {}, CONE);
        break;
      }
      case "pendant": case "flush": case "downlights": {
        if (W > D * 2.5) { box(W, Math.min(H, 0.06), D, 0, H - 0.03, 0, main, lit ? { emissive: "#FFD9A0", ei: 1 } : {}); break; }
        const r = Math.max(Math.min(W, D) / 2, 0.04), sh = Math.min(H, Math.max(0.05, r * 0.7));
        if (H > sh + 0.02) cyl(0.004, H - sh, 0, sh + (H - sh) / 2, 0, "#222");
        cyl(r, sh, 0, sh / 2, 0, c("shade") || main, lit ? { emissive: "#FFD9A0", ei: 1.2 } : {}, shape === "pendant" ? CONE : CYL);
        break;
      }
      case "wall_light": box(W, H, D, 0, H / 2, 0, main, lit ? { emissive: "#FFD9A0", ei: 1 } : {}); break;
      case "plant": {
        const r = Math.min(W, D) / 2, pot = Math.min(0.45, H * 0.35);
        cyl(r * 0.55, pot, 0, pot / 2, 0, c("ceramic") || "#E9E2D6");
        const leaf = this.mat("#5F7A4E");
        for (let i = 0; i < 5; i++) {
          const m = new THREE.Mesh(SPH, leaf), a = (i / 5) * Math.PI * 2, rr = r * (i ? 0.45 : 0);
          const s = r * (i ? 0.9 : 1.1); m.scale.set(s, (H - pot) * (i ? 0.6 : 0.8), s);
          m.position.set(Math.cos(a) * rr, pot + (H - pot) * (i ? 0.45 : 0.55), Math.sin(a) * rr); g.add(m);
        }
        break;
      }
      case "curtains": {
        const fab = c("fabric") || c("all") || "#E2D9C9";
        if (/blind/i.test(it.type)) { box(W, H * 0.35, 0.03, 0, H * 0.82, 0, fab, { rough: 1 }); break; }
        for (const sx of [-1, 1]) box(W * 0.2, H, Math.max(D * 0.6, 0.05), sx * (W / 2 - W * 0.1), H / 2, 0, fab, { rough: 1 });
        cyl(0.012, W, 0, H, -D * 0.1, c("metal") || "#222").rotation.z = Math.PI / 2;
        break;
      }
      case "frame": case "mirror": {
        box(W, H, Math.max(D, 0.02), 0, H / 2, 0, c("frame") || main);
        box(W * 0.86, H * 0.86, 0.005, 0, H / 2, -Math.max(D, 0.02) / 2 - 0.002, shape === "mirror" ? "#C9D3D8" : artColour(it.id), shape === "mirror" ? { rough: 0.05, metal: 0.9 } : {});
        break;
      }
      case "tv": box(W, H, Math.max(D, 0.03), 0, H / 2, 0, "#111214", { rough: 0.3 }); break;
      case "radiator": box(W, H, Math.max(D, 0.05), 0, H / 2, 0, c("metal") || c("all") || "#F1F0EA", { rough: 0.5 }); break;
      case "wc": {
        box(W * 0.9, H, D * 0.28, 0, H / 2, D / 2 - D * 0.14, "#F5F5F2", { rough: 0.3 });
        const m = cyl(0.5, 0.4, 0, 0.2, -D * 0.12, "#F5F5F2", { rough: 0.3 }); m.scale.set(W * 0.85, 0.4, D * 0.7);
        break;
      }
      case "basin": box(W, 0.15, D, 0, H - 0.075, 0, "#F5F5F2", { rough: 0.3 }); box(W * 0.9, H - 0.15, D * 0.8, 0, (H - 0.15) / 2, 0.02, /vanity/.test(it.type) ? (c("body") || "#B8936A") : "#F5F5F2"); break;
      case "shower": {
        box(W, 0.04, D, 0, 0.02, 0, "#F5F5F2", { rough: 0.3 });
        const gl = { opacity: 0.25, rough: 0.05, unique: false };
        box(W, H, 0.01, 0, H / 2, -D / 2, "#BFD3DC", gl); box(0.01, H, D, -W / 2, H / 2, 0, "#BFD3DC", gl);
        break;
      }
      case "bath": box(W, H, D, 0, H / 2, 0, c("body") || "#F5F5F2"); box(W - 0.1, 0.02, D - 0.1, 0, H + 0.005, 0, "#E8EEF0"); break;
      default:
        if (/vase|bowl|candle|pot|jug|kettle|lamp/i.test(it.type)) cyl(Math.min(W, D) / 2, H, 0, H / 2, 0, main);
        else box(W, H, D, 0, H / 2, 0, main);
    }
    return g;
  }
}

function floorTexture(fl) {
  const cv = document.createElement("canvas"); cv.width = cv.height = 512;
  const x = cv.getContext("2d"), [r, g, b] = hexToRgb(fl.hex);
  x.fillStyle = fl.hex; x.fillRect(0, 0, 512, 512);
  const pat = fl.pattern || "planks", u = fl.unit_mm || [190, 1900];
  const px = 512 / 2;                                   // the texture covers 2 m
  const shade = k => `rgb(${r * k | 0},${g * k | 0},${b * k | 0})`;
  if (pat === "planks") {
    const w = (u[0] / 1000) * px, L = (u[1] / 1000) * px;
    for (let i = 0; i * w < 512; i++) {
      const off = ((i * 0.37) % 1) * L;
      for (let j = -1; j * L < 512 + L; j++) {
        x.fillStyle = shade(0.9 + ((i * 7 + j * 3) % 5) * 0.04); x.fillRect(i * w, j * L + off, w - 1, L - 1);
      }
    }
  } else if (pat === "herringbone") {
    const w = (u[0] / 1000) * px, L = (u[1] / 1000) * px;
    x.save(); x.translate(256, 256); x.rotate(Math.PI / 4);
    for (let i = -14; i < 14; i++) for (let j = -14; j < 14; j++) {
      x.fillStyle = shade(0.9 + (((i + j) % 4) + 4) % 4 * 0.04);
      if ((i + j) % 2) x.fillRect(i * L * 0.5, j * w * 2, L - 1, w - 1); else x.fillRect(i * L * 0.5, j * w * 2 + w, w - 1, L - 1);
    }
    x.restore();
  } else if (pat === "tiles" || pat === "pattern") {
    const w = (u[0] / 1000) * px, hh = (u[1] / 1000) * px;
    x.strokeStyle = shade(0.8); x.lineWidth = 2;
    for (let i = 0; i * w <= 512; i++) for (let j = 0; j * hh <= 512; j++) {
      x.fillStyle = shade(0.95 + ((i * 3 + j * 5) % 4) * 0.02); x.fillRect(i * w, j * hh, w, hh); x.strokeRect(i * w, j * hh, w, hh);
      if (pat === "pattern") { x.fillStyle = shade(0.75); x.beginPath(); x.arc(i * w + w / 2, j * hh + hh / 2, w * 0.25, 0, 7); x.fill(); }
    }
  } else {
    for (let i = 0; i < 2500; i++) { x.fillStyle = shade(0.92 + Math.random() * 0.12); x.fillRect(Math.random() * 512, Math.random() * 512, 2, 2); }
  }
  const t = new THREE.CanvasTexture(cv); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(0.5, 0.5); t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
const ART = ["#C9B79C", "#8FA3A8", "#B5694B", "#D8CEBF", "#6E7F6A", "#3E4A57"];
const artColour = id => ART[[...id].reduce((a, ch) => a + ch.charCodeAt(0), 0) % ART.length];
function signedArea(p) { let a = 0; for (let i = 0; i < p.length; i++) { const q = p[i], r = p[(i + 1) % p.length]; a += q[0] * r[1] - r[0] * q[1]; } return a / 2; }
function insideTest([x, z], poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if ((zi > z) !== (zj > z) && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) inside = !inside;
  }
  return inside;
}
function disposeGroup(g, geo = true) {
  for (const c of [...g.children]) {
    c.traverse(o => { if (o.userData?.helper) {o.geometry?.dispose();o.material?.dispose();} if (o.isMesh && o.geometry !== UNIT && o.geometry !== CYL && o.geometry !== CONE && o.geometry !== SPH && geo) { o.geometry.dispose(); if (o.material?.map) o.material.map.dispose(); } });
    g.remove(c);
  }
}
