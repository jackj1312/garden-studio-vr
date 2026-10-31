import * as THREE from "three";
import { hapticPulse } from "./presence.js?v=f383e46-1642";

/* ------------------------------------------------------------------ *
 *  Reference view: the client's own photos, around you, in the garden.
 *
 *  Toggle it and the photos taken nearest to where you stand, looking
 *  the way you are looking, float on an arc about 2 m away — the best
 *  match large in the middle, the next ones smaller to each side. The
 *  grip steps through tabs (the next 7 by rank, then the close-ups,
 *  then round again); the trigger on a photo enlarges it.
 *
 *  Data: assets/sites/<site>/refs.json (exported by the capture tools)
 *  {"refs": [{"file", "kind", "date", "pos": [x,y,z] | null,
 *             "dir": [dx,dy,dz] | null, "w", "h", ...}]} in viewer
 *  coordinates. Textures load per tab and the rest are released, so
 *  the headset only ever holds the seven it is showing.
 * ------------------------------------------------------------------ */

const PER_TAB = 7;
const RADIUS = 2.0;                         // metres from the eyes
const SLOT_H = [1.2, 0.75, 0.75, 0.6, 0.6, 0.5, 0.5];   // centre, then right/left pairs outwards
const GAP = THREE.MathUtils.degToRad(2.5);
const TURN_PER_M = 2.0;                     // ranking: 1 radian of heading costs as much as 2 m of distance (180° ≈ 6 m)
const RERANK_MOVE = 1.0, RERANK_TURN = THREE.MathUtils.degToRad(30), RERANK_DWELL = 0.6;
const ACCENT = "#f2d36b", ACCENT_HEX = 0xf2d36b;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function roundRect(c, x, y, w, h, r) {
  c.beginPath();
  c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
}
const niceDate = d => (d && d.length === 8) ? `${+d.slice(6)} ${MONTHS[+d.slice(4, 6) - 1] || "?"} ${d.slice(0, 4)}` : "";

export function createRefs({ scene, camera, renderer, siteKey, onActive }) {
  const base = siteKey ? `assets/sites/${siteKey}` : null;
  let data = null, loading = null, failed = "";
  let active = false, ranked = [], closeups = [], tabs = [], tab = 0;
  let enlarged = null, hovered = null;
  const rankPos = new THREE.Vector3(), rankDir = new THREE.Vector3(0, 0, -1);
  let dwell = 0;

  const unitPlane = new THREE.PlaneGeometry(1, 1);
  const root = new THREE.Group();
  root.name = "References";
  root.visible = false;
  scene.add(root);

  /* the garden dims a little behind the photos so they read clearly:
     one transparent sphere around the head, drawn after everything solid */
  const dim = new THREE.Mesh(new THREE.SphereGeometry(3.2, 24, 12),
    new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.42, side: THREE.BackSide,
                                  depthWrite: false, fog: false, toneMapped: false }));
  dim.renderOrder = 1001;                   // after the sky (1000), before the photos' labels
  dim.visible = false;
  dim.frustumCulled = false;
  scene.add(dim);

  /* an arrow on the ground where the top photo was taken, pointing the way the camera looked */
  const arrowShape = new THREE.Shape();
  arrowShape.moveTo(-0.06, -0.25); arrowShape.lineTo(0.06, -0.25); arrowShape.lineTo(0.06, 0.05);
  arrowShape.lineTo(0.16, 0.05); arrowShape.lineTo(0, 0.3); arrowShape.lineTo(-0.16, 0.05);
  arrowShape.lineTo(-0.06, 0.05); arrowShape.closePath();
  const arrow = new THREE.Mesh(new THREE.ShapeGeometry(arrowShape).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: ACCENT_HEX, toneMapped: false, fog: false, transparent: true, opacity: 0.95,
                                  depthTest: false, depthWrite: false, side: THREE.DoubleSide }));
  arrow.renderOrder = 1005;
  arrow.visible = false;
  scene.add(arrow);

  /* pointer ray for the headset */
  const rayGeo = new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(new Float32Array(6), 3));
  const ray = new THREE.Line(rayGeo, new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.6, toneMapped: false, fog: false }));
  ray.frustumCulled = false;
  ray.visible = false;
  scene.add(ray);

  /* ---------------- panels (seven, reused) ---------------- */
  const panels = [];
  for (let i = 0; i < PER_TAB; i++) {
    const g = new THREE.Group();
    const frameMat = new THREE.MeshBasicMaterial({ color: 0x101210, toneMapped: false, fog: false, depthTest: false });
    const frame = new THREE.Mesh(unitPlane, frameMat);
    frame.position.z = -0.004;
    const photoMat = new THREE.MeshBasicMaterial({ color: 0x2a2d2a, toneMapped: false, fog: false, depthTest: false });
    const photo = new THREE.Mesh(unitPlane, photoMat);
    const lc = document.createElement("canvas");
    lc.width = 640; lc.height = 64;
    const labelTex = new THREE.CanvasTexture(lc);
    labelTex.colorSpace = THREE.SRGBColorSpace;
    const label = new THREE.Mesh(unitPlane, new THREE.MeshBasicMaterial({ map: labelTex, transparent: true, toneMapped: false, fog: false, depthTest: false }));
    /* drawn over the garden (a fence 1 m away must not hide a photo), frame first, then photo, then label;
       they still write depth, so the dimming sphere behind them leaves them clear */
    frame.renderOrder = 1002; photo.renderOrder = 1003; label.renderOrder = 1004;
    g.add(frame, photo, label);
    g.visible = false;
    root.add(g);
    photo.userData.panel = i;
    panels.push({ g, frame, photo, label, lc, labelTex, ref: null, w: 1, h: 1 });
  }

  /* ---------------- textures, per tab ---------------- */
  const texByFile = new Map();              // file -> THREE.Texture, only for the tab on show
  const pending = new Set();
  const useBitmaps = typeof createImageBitmap !== "undefined";
  const bitmapLoader = useBitmaps ? new THREE.ImageBitmapLoader().setOptions({ imageOrientation: "flipY", premultiplyAlpha: "none" }) : null;
  const imageLoader = new THREE.TextureLoader();
  const wanted = () => new Set(panels.filter(p => p.g.visible && p.ref).map(p => p.ref.file));

  function release(file) {
    const t = texByFile.get(file);
    if (!t) return;
    texByFile.delete(file);
    t.dispose();
    if (t.image && typeof t.image.close === "function") t.image.close();
  }
  function applyTex(p) {
    const t = p.ref && texByFile.get(p.ref.file);
    p.photo.material.map = t || null;
    p.photo.material.color.setHex(t ? 0xffffff : 0x2a2d2a);
    p.photo.material.needsUpdate = true;
  }
  function fetchTex(file) {
    if (texByFile.has(file) || pending.has(file)) return;
    pending.add(file);
    const done = tex => {
      pending.delete(file);
      if (!wanted().has(file) || !active) {          // moved on before it arrived
        tex.dispose(); if (tex.image?.close) tex.image.close();
        return;
      }
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.anisotropy = 4;
      texByFile.set(file, tex);
      for (const p of panels) if (p.ref?.file === file) applyTex(p);
    };
    const fail = err => { pending.delete(file); console.warn("refs: could not load", file, err); };
    const url = `${base}/${file}`;
    if (bitmapLoader) bitmapLoader.load(url, bmp => { const t = new THREE.Texture(bmp); t.needsUpdate = true; done(t); }, undefined, fail);
    else imageLoader.load(url, done, undefined, fail);
  }
  function syncTextures() {
    const want = wanted();
    for (const f of [...texByFile.keys()]) if (!want.has(f)) release(f);
    for (const p of panels) { applyTex(p); if (p.g.visible && p.ref) fetchTex(p.ref.file); }
  }

  /* ---------------- hint ---------------- */
  const HW = 512, HH = 176;
  const hintCanvas = document.createElement("canvas");
  hintCanvas.width = HW; hintCanvas.height = HH;
  const hctx = hintCanvas.getContext("2d");
  const hintTex = new THREE.CanvasTexture(hintCanvas);
  hintTex.colorSpace = THREE.SRGBColorSpace;
  const hint = new THREE.Mesh(new THREE.PlaneGeometry(0.17, 0.17 * HH / HW),
    new THREE.MeshBasicMaterial({ map: hintTex, transparent: true, toneMapped: false, fog: false, depthTest: false }));
  hint.renderOrder = 1010;
  hint.position.set(0, 0.06, 0.02);
  hint.rotation.x = -0.75;
  hint.visible = false;
  const domHint = document.getElementById("refHint");

  const tabName = i => !tabs.length ? "" : tabs[i].closeups ? "close-ups" : i === 0 ? "nearest" : "further";
  function drawHint() {
    const tabText = failed ? failed : !data ? "loading…" : tabs.length ? `${tab + 1} / ${tabs.length} · ${tabName(tab)}` : "no photos";
    hctx.clearRect(0, 0, HW, HH);
    hctx.fillStyle = "rgba(14,16,14,0.9)"; roundRect(hctx, 2, 2, HW - 4, HH - 4, 20); hctx.fill();
    hctx.fillStyle = ACCENT; roundRect(hctx, 2, 2, 16, HH - 4, 8); hctx.fill();
    hctx.fillStyle = ACCENT; hctx.font = "700 44px system-ui, sans-serif";
    hctx.fillText("REFERENCE", 36, 56);
    hctx.fillStyle = "#f4f3ee"; hctx.font = "600 34px system-ui, sans-serif";
    hctx.fillText(tabText, 36, 104);
    hctx.fillStyle = "#b9bcb2"; hctx.font = "24px system-ui, sans-serif";
    hctx.fillText(enlarged ? "Trigger: back to all" : "Grip next · A back · Trigger enlarge · Y done", 36, 148);
    hintTex.needsUpdate = true;
    if (domHint) {
      domHint.hidden = !active;
      domHint.querySelector("[data-tab]").textContent = tabText;
    }
  }

  /* ---------------- ranking and layout ---------------- */
  const _h = new THREE.Vector3(), _f = new THREE.Vector3();
  function head() {
    camera.getWorldPosition(_h);
    camera.getWorldDirection(_f);
    _f.y = 0;
    if (_f.lengthSq() < 1e-6) _f.set(0, 0, -1);
    _f.normalize();
  }

  function rank() {
    head();
    rankPos.copy(_h); rankDir.copy(_f);
    const scored = [];
    closeups = [];
    for (const r of data.refs) {
      if (!r.pos) { closeups.push({ r, dist: null }); continue; }
      const dist = Math.hypot(r.pos[0] - _h.x, r.pos[2] - _h.z);
      let turn = Math.PI / 2;
      if (r.dir) {
        const l = Math.hypot(r.dir[0], r.dir[2]);
        if (l > 0.05) turn = Math.acos(Math.max(-1, Math.min(1, (r.dir[0] * _f.x + r.dir[2] * _f.z) / l)));
      }
      scored.push({ r, dist, score: dist + TURN_PER_M * turn });
    }
    scored.sort((a, b) => a.score - b.score);
    ranked = scored;
    tabs = [];
    for (let i = 0; i < ranked.length; i += PER_TAB) tabs.push({ items: ranked.slice(i, i + PER_TAB) });
    for (let i = 0; i < closeups.length; i += PER_TAB) tabs.push({ items: closeups.slice(i, i + PER_TAB), closeups: true });
    dwell = 0;
  }

  function writeLabel(p, item) {
    const c = p.lc.getContext("2d");
    c.clearRect(0, 0, 640, 64);
    c.fillStyle = "rgba(14,16,14,0.82)"; roundRect(c, 0, 4, 640, 56, 14); c.fill();
    c.fillStyle = "#f4f3ee"; c.font = "600 30px system-ui, sans-serif"; c.textBaseline = "middle"; c.textAlign = "center";
    const where = item.dist == null ? "close-up" : item.dist < 0.3 ? "taken right here" : `taken ${item.dist.toFixed(1)} m from here`;
    const kind = item.r.kind === "walk" ? "walk video" : item.r.kind;
    c.fillText(`${niceDate(item.r.date)} · ${kind} · ${where}`, 320, 33);
    p.labelTex.needsUpdate = true;
  }

  /* centre the tab on where the head is now looking */
  function layout() {
    head();
    const items = tabs[tab]?.items || [];
    const eye = Math.max(1.1, _h.y);
    let right = 0, left = 0;                 // angle used so far on each side
    const yaw0 = Math.atan2(-_f.x, -_f.z);   // rotation about Y that turns -Z onto the gaze
    panels.forEach((p, i) => {
      const item = items[i];
      p.g.visible = !!item;
      p.ref = item ? item.r : null;
      if (!item) return;
      const h = SLOT_H[i], aspect = (item.r.w || 4) / (item.r.h || 3);
      let w = h * aspect;
      if (w > 2.1) { w = 2.1; }              // a wide panorama stays within the arc
      const hh = w / aspect;
      const half = Math.atan2(w / 2, RADIUS);
      let a;
      if (i === 0) { a = 0; right = left = half; }
      else if (i % 2 === 1) { a = -(right + GAP + half); right += GAP + 2 * half; }
      else { a = left + GAP + half; left += GAP + 2 * half; }
      const yaw = yaw0 + a;
      p.g.position.set(_h.x - Math.sin(yaw) * RADIUS, eye, _h.z - Math.cos(yaw) * RADIUS);
      p.g.rotation.set(0, yaw, 0);          // the plane's front (+Z) faces back at the eyes
      p.g.scale.setScalar(1);
      p.w = w; p.h = hh;
      p.photo.scale.set(w, hh, 1);
      p.frame.scale.set(w + 0.03, hh + 0.03, 1);
      p.label.scale.set(Math.max(0.42, Math.min(0.75, w)), Math.max(0.42, Math.min(0.75, w)) / 10, 1);
      p.label.position.set(0, -hh / 2 - 0.06, 0);
      p.label.visible = true;
      writeLabel(p, item);
    });
    // where the best photo was taken
    const top = items[0];
    if (top && top.r.pos && top.r.dir) {
      arrow.visible = true;
      arrow.position.set(top.r.pos[0], 0.03, top.r.pos[2]);
      arrow.rotation.set(0, Math.atan2(-top.r.dir[0], -top.r.dir[2]), 0);
    } else arrow.visible = false;
    enlarged = null; setHover(null);
    root.updateMatrixWorld(true);            // aimable at once, not only after the next frame
    syncTextures();
    drawHint();
  }

  /* ---------------- enlarge ---------------- */
  function enlarge(i) {
    const p = panels[i];
    if (!p?.g.visible) return;
    head();
    enlarged = i;
    panels.forEach((q, j) => { if (j !== i) q.g.visible = false; });
    const maxH = 1.7, maxW = 2.6;
    let s = maxH / p.h;
    if (p.w * s > maxW) s = maxW / p.w;
    const yaw = Math.atan2(-_f.x, -_f.z);
    p.g.position.set(_h.x + _f.x * 1.6, Math.max(1.2, _h.y), _h.z + _f.z * 1.6);
    p.g.rotation.set(0, yaw, 0);
    p.g.scale.setScalar(s);
    p.label.visible = true;
    root.updateMatrixWorld(true);
    setHover(null);
    drawHint();
  }
  function shrink() { if (enlarged != null) layout(); }

  function setHover(i) {
    if (hovered === i) return;
    if (hovered != null) panels[hovered].frame.material.color.setHex(0x101210);
    hovered = i;
    if (i != null) panels[i].frame.material.color.setHex(ACCENT_HEX);
  }

  /* ---------------- modes ---------------- */
  async function ensureData() {
    if (data || !base) return !!data;
    if (!loading) loading = fetch(`${base}/refs.json`, { cache: "no-store" })
      .then(r => { if (!r.ok) throw new Error(`refs.json ${r.status}`); return r.json(); })
      .then(d => { data = { refs: (d.refs || []).filter(r => r && r.file) }; })
      .catch(err => { failed = "no reference photos for this site"; console.warn("refs:", err.message || err); });
    await loading;
    return !!data;
  }

  async function setActive(on) {
    on = !!on && !!base;
    if (on === active) return;
    active = on;
    root.visible = dim.visible = hint.visible = active;
    if (!active) {
      arrow.visible = ray.visible = false;
      panels.forEach(p => { p.g.visible = false; });
      syncTextures();                         // releases every texture
      enlarged = null; setHover(null);
      drawHint();
      onActive?.(false);
      return;
    }
    onActive?.(true);
    if (!renderer.xr.isPresenting && document.pointerLockElement) { /* keep mouse-look: clicks aim with the crosshair */ }
    drawHint();
    if (!(await ensureData()) || !active) { drawHint(); return; }
    rank(); tab = 0; layout();
  }
  function step(d) {
    if (!active || !tabs.length) return;
    tab = (tab + d + tabs.length) % tabs.length;
    if (tab === 0) rank();                    // back to the start: re-rank from where you are now
    layout();
  }

  /* ---------------- headset ---------------- */
  const raycaster = new THREE.Raycaster();
  const _o = new THREE.Vector3(), _d = new THREE.Vector3(), _q = new THREE.Quaternion();
  const photos = () => panels.filter(p => p.g.visible).map(p => p.photo);
  let triggerWas = false;
  function updateXR(controller, trigger) {
    if (!active || !controller) { ray.visible = false; triggerWas = trigger; return; }
    controller.getWorldPosition(_o);
    _d.set(0, 0, -1).applyQuaternion(controller.getWorldQuaternion(_q));
    raycaster.set(_o, _d);
    const hit = raycaster.intersectObjects(photos(), false)[0];
    const a = rayGeo.attributes.position;
    const len = hit ? hit.distance : 3;
    a.setXYZ(0, _o.x, _o.y, _o.z);
    a.setXYZ(1, _o.x + _d.x * len, _o.y + _d.y * len, _o.z + _d.z * len);
    a.needsUpdate = true;
    ray.visible = true;
    setHover(hit && enlarged == null ? hit.object.userData.panel : null);
    if (trigger && !triggerWas) {
      if (enlarged != null) shrink();
      else if (hit) { enlarge(hit.object.userData.panel); hapticPulse([controller], 0.4, 25); }
    }
    triggerWas = trigger;
  }

  /* ---------------- desktop ---------------- */
  const canvas = renderer.domElement;
  const ndc = new THREE.Vector2();
  canvas.addEventListener("click", e => {
    if (!active || renderer.xr.isPresenting || !tabs.length) return;
    if (enlarged != null) { shrink(); return; }
    if (document.pointerLockElement === canvas) ndc.set(0, 0);   // mouse-look: aim with the centre of the view
    else {
      const r = canvas.getBoundingClientRect();
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    }
    camera.updateMatrixWorld();
    raycaster.setFromCamera(ndc, camera);
    const hit = raycaster.intersectObjects(photos(), false)[0];
    if (hit) enlarge(hit.object.userData.panel);
  });
  addEventListener("keydown", e => {
    if (e.repeat || renderer.xr.isPresenting || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    if (e.code === "KeyR" && base) setActive(!active);
    else if (active && e.code === "Tab") { e.preventDefault(); step(e.shiftKey ? -1 : 1); }
  });

  drawHint();
  return {
    get active() { return active; },
    get tab() { return tab; },
    get tabs() { return tabs; },
    get enlarged() { return enlarged; },
    get shown() { return panels.filter(p => p.g.visible).map(p => p.ref.file); },
    get textures() { return [...texByFile.keys()]; },
    setActive, toggle: () => setActive(!active), next: () => step(1), prev: () => step(-1),
    enlarge, shrink, updateXR,
    attachHint(controller) { controller.add(hint); },
    /* every frame: keep the dimming round the head; re-rank on a real move or turn */
    update(dt) {
      if (!renderer.xr.isPresenting) ray.visible = false;
      if (!active) return;
      camera.getWorldPosition(dim.position);
      if (!tabs.length || enlarged != null || tab !== 0) return;   // never reshuffle a tab you chose
      head();
      if (Math.hypot(_h.x - rankPos.x, _h.z - rankPos.z) > RERANK_MOVE) { rank(); layout(); return; }
      if (Math.acos(Math.max(-1, Math.min(1, _f.dot(rankDir)))) > RERANK_TURN) {
        dwell += dt;
        if (dwell > RERANK_DWELL) { rank(); layout(); }
      } else dwell = 0;
    },
  };
}
