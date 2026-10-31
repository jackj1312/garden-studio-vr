import * as THREE from "three";
import { hapticPulse } from "./presence.js?v=3a8191b-1626";

/* ------------------------------------------------------------------ *
 *  Marking: draw on the ground the way you draw the Quest's Guardian.
 *
 *  Point the right controller at the ground, hold the trigger and walk
 *  or sweep: a bright ribbon follows the cursor. Two kinds of mark —
 *  a correction ("this is wrong here") and a proposal (a new bed, a
 *  path, a studio footprint). A stroke that ends within 25 cm of where
 *  it began closes into a shape and shows its area and perimeter.
 *
 *  Every stroke is saved in PLAN coordinates (plan x = viewer x,
 *  plan y = -viewer z, metres) to assets/sites/<site>/marks.json via
 *  POST /marks?site=<site> (tools/https-serve.py), so a mark made in
 *  the headset can come straight back into the plan and the next build.
 * ------------------------------------------------------------------ */

export const KINDS = {
  correction: { label: "Correction", hex: 0xff5a1f, css: "#ff5a1f", note: "this is wrong here" },
  proposal:   { label: "Proposal",   hex: 0x1fd8ff, css: "#1fd8ff", note: "a proposed change" },
};
const KIND_ORDER = ["correction", "proposal"];

const SAMPLE = 0.05;          // a point every 5 cm of cursor travel
const CLOSE_DIST = 0.25;      // ends this near its start: a closed shape
const MIN_CLOSE_LEN = 0.75;   // ...but not a tap or a tiny wiggle
const MAX_REACH = 30;         // metres along the ray
const HALF_W = 0.04;          // ribbon half-width at the ground
const LIFT = 0.015;           // ribbon base above the surface it was drawn on
const HEIGHT = 0.03;          // ribbon top above its base

const r3 = v => Math.round(v * 1000) / 1000;

function ribbonGeometry(pts, closed, hex) {
  const n = pts.length;
  if (n < 2) return null;
  const pos = new Float32Array(n * 4 * 3), col = new Float32Array(n * 4 * 3);
  const c = new THREE.Color(hex), lo = c.clone().multiplyScalar(0.55), hi = c.clone().lerp(new THREE.Color(1, 1, 1), 0.18);
  for (let i = 0; i < n; i++) {
    const p = pts[i];
    const a = closed ? pts[(i - 1 + n) % n] : pts[Math.max(0, i - 1)];
    const b = closed ? pts[(i + 1) % n] : pts[Math.min(n - 1, i + 1)];
    let tx = b.x - a.x, tz = b.z - a.z;
    const l = Math.hypot(tx, tz) || 1; tx /= l; tz /= l;
    const nx = -tz, nz = tx, y0 = p.y + LIFT, y1 = y0 + HEIGHT;
    const ring = [[-HALF_W, y0, lo], [-HALF_W * 0.55, y1, hi], [HALF_W * 0.55, y1, hi], [HALF_W, y0, lo]];
    ring.forEach(([o, y, cc], k) => {
      const j = (i * 4 + k) * 3;
      pos[j] = p.x + nx * o; pos[j + 1] = y; pos[j + 2] = p.z + nz * o;
      col[j] = cc.r; col[j + 1] = cc.g; col[j + 2] = cc.b;
    });
  }
  const segs = closed ? n : n - 1, idx = [];
  for (let s = 0; s < segs; s++) {
    const i = s, j = (s + 1) % n;
    for (let k = 0; k < 3; k++) {
      const a = i * 4 + k, b = a + 1, cI = j * 4 + k, d = cI + 1;
      idx.push(a, cI, b, b, cI, d);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.setAttribute("color", new THREE.BufferAttribute(col, 3));
  g.setIndex(idx);
  g.computeBoundingSphere();
  return g;
}

function planLength(pts, closed) {
  let L = 0;
  for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].z - pts[i - 1].z);
  if (closed && pts.length > 2) L += Math.hypot(pts[0].x - pts[pts.length - 1].x, pts[0].z - pts[pts.length - 1].z);
  return L;
}
function planArea(pts) {           // shoelace in plan coordinates (x, -z)
  let A = 0;
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i], q = pts[(i + 1) % pts.length];
    A += p.x * (-q.z) - q.x * (-p.z);
  }
  return Math.abs(A) / 2;
}

function roundRect(c, x, y, w, h, r) {
  c.beginPath();
  c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
}

function makeLabel(text, css) {
  const cv = document.createElement("canvas");
  cv.width = 512; cv.height = 128;
  const c = cv.getContext("2d");
  c.font = "600 54px system-ui, sans-serif";
  const w = Math.min(500, c.measureText(text).width + 64);
  const x = (512 - w) / 2;
  c.fillStyle = "rgba(14,16,14,0.88)"; roundRect(c, x, 14, w, 100, 22); c.fill();
  c.fillStyle = css; roundRect(c, x, 14, 14, 100, 7); c.fill();
  c.fillStyle = "#f4f3ee"; c.textAlign = "center"; c.textBaseline = "middle";
  c.fillText(text, 256 + 7, 66);
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, toneMapped: false, fog: false, depthTest: false, transparent: true }));
  s.scale.set(0.72, 0.18, 1);
  s.renderOrder = 960;
  return s;
}

export function createMarks({ scene, camera, renderer, siteKey }) {
  const ribbonMat = new THREE.MeshBasicMaterial({
    vertexColors: true, toneMapped: false, fog: false, side: THREE.DoubleSide,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
  });
  /* a faint copy drawn over everything: keeps a line readable through
     the grass tufts and behind a hedge */
  const ghostMat = new THREE.MeshBasicMaterial({
    vertexColors: true, toneMapped: false, fog: false, side: THREE.DoubleSide,
    transparent: true, opacity: 0.3, depthTest: false, depthWrite: false,
  });

  const group = new THREE.Group();
  group.name = "Marks";
  scene.add(group);

  /* cursor: a glowing ring on the ground, like the Guardian's */
  const cursor = new THREE.Group();
  const ringMat = new THREE.MeshBasicMaterial({ color: KINDS.correction.hex, toneMapped: false, fog: false, transparent: true, opacity: 0.95, depthTest: false, depthWrite: false, side: THREE.DoubleSide });
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.075, 0.105, 48).rotateX(-Math.PI / 2), ringMat);
  const dot = new THREE.Mesh(new THREE.CircleGeometry(0.022, 20).rotateX(-Math.PI / 2), ringMat);
  ring.renderOrder = dot.renderOrder = 970;
  cursor.add(ring, dot);
  cursor.visible = false;
  scene.add(cursor);

  /* the ray from the controller to the cursor */
  const rayGeo = new THREE.BufferGeometry().setAttribute("position", new THREE.BufferAttribute(new Float32Array(6), 3));
  const rayMat = new THREE.LineBasicMaterial({ color: KINDS.correction.hex, toneMapped: false, fog: false, transparent: true, opacity: 0.75 });
  const ray = new THREE.Line(rayGeo, rayMat);
  ray.frustumCulled = false;
  ray.visible = false;
  scene.add(ray);

  /* in-headset hint, riding on the right controller */
  const HW = 512, HH = 176;
  const hintCanvas = document.createElement("canvas");
  hintCanvas.width = HW; hintCanvas.height = HH;
  const hctx = hintCanvas.getContext("2d");
  const hintTex = new THREE.CanvasTexture(hintCanvas);
  hintTex.colorSpace = THREE.SRGBColorSpace;
  const hint = new THREE.Mesh(new THREE.PlaneGeometry(0.17, 0.17 * HH / HW),
    new THREE.MeshBasicMaterial({ map: hintTex, transparent: true, toneMapped: false, fog: false, depthTest: false }));
  hint.renderOrder = 980;
  hint.position.set(0, 0.06, 0.02);
  hint.rotation.x = -0.75;               // face up and back towards the eyes, like a phone in the hand
  hint.visible = false;

  const domHint = document.getElementById("markHint");

  let active = false, kind = "correction", status = siteKey ? "" : "demo: not saved";
  let canSave = !!siteKey;
  const strokes = [];
  let live = null;                       // the stroke being drawn
  const raycaster = new THREE.Raycaster();
  const floor = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  let groundMeshes = [];
  const _o = new THREE.Vector3(), _d = new THREE.Vector3(), _q = new THREE.Quaternion(), _hit = new THREE.Vector3();
  let t = 0, cursorBase = 1;

  function drawHint() {
    const k = KINDS[kind];
    hctx.clearRect(0, 0, HW, HH);
    hctx.fillStyle = "rgba(14,16,14,0.9)"; roundRect(hctx, 2, 2, HW - 4, HH - 4, 20); hctx.fill();
    hctx.fillStyle = k.css; roundRect(hctx, 2, 2, 16, HH - 4, 8); hctx.fill();
    hctx.fillStyle = k.css; hctx.font = "700 46px system-ui, sans-serif";
    hctx.fillText(`MARK · ${k.label}`, 36, 58);
    hctx.fillStyle = "#e6e7e0"; hctx.font = "26px system-ui, sans-serif";
    hctx.fillText(`Trigger draw · Grip undo · A kind · ${siteKey ? "B" : "L-stick"} done`, 36, 104);
    hctx.fillStyle = "#a7ab9e"; hctx.font = "24px system-ui, sans-serif";
    hctx.fillText(`${strokes.length} mark${strokes.length === 1 ? "" : "s"}${status ? " · " + status : ""}`, 36, 146);
    hintTex.needsUpdate = true;
    if (domHint) {
      domHint.hidden = !active;
      domHint.style.setProperty("--mark", k.css);
      domHint.querySelector("[data-kind]").textContent = k.label;
      domHint.querySelector("[data-status]").textContent =
        `${strokes.length} mark${strokes.length === 1 ? "" : "s"}${status ? " · " + status : ""}`;
    }
  }

  function setColours() {
    ringMat.color.setHex(KINDS[kind].hex);
    rayMat.color.setHex(KINDS[kind].hex);
  }

  /* where a ray meets the ground: the site's own flat surfaces (lawn,
     paving, kerbs — a few thousand triangles), else the y = 0 plane */
  function castGround() {
    if (groundMeshes.length) {
      const h = raycaster.intersectObjects(groundMeshes, false)[0];
      if (h && h.distance <= MAX_REACH) return _hit.copy(h.point);
    }
    if (!raycaster.ray.intersectPlane(floor, _hit)) return null;
    return raycaster.ray.origin.distanceTo(_hit) <= MAX_REACH ? _hit : null;
  }
  function groundY(x, z) {
    if (!groundMeshes.length) return 0;
    raycaster.set(_o.set(x, 3, z), _d.set(0, -1, 0));
    const h = raycaster.intersectObjects(groundMeshes, false)[0];
    return h ? h.point.y : 0;
  }

  function showCursor(p) {
    if (!p) { cursor.visible = false; return; }
    cursor.visible = true;
    cursor.position.set(p.x, p.y + 0.012, p.z);
    // near the start of a long enough stroke: the ring turns white and grows — let go to close it
    const closing = live && live.pts.length > 2 && planLength(live.pts, false) > MIN_CLOSE_LEN &&
      Math.hypot(p.x - live.pts[0].x, p.z - live.pts[0].z) <= CLOSE_DIST;
    ringMat.color.setHex(closing ? 0xffffff : KINDS[kind].hex);
    cursorBase = closing ? 1.5 : 1;
    cursor.scale.setScalar(cursorBase * (1 + 0.07 * Math.sin(t * 6)));
  }

  function buildMesh(s) {
    const g = ribbonGeometry(s.pts, s.closed, KINDS[s.kind].hex);
    if (!s.mesh) {
      s.mesh = new THREE.Mesh(g || new THREE.BufferGeometry(), ribbonMat);
      s.ghost = new THREE.Mesh(s.mesh.geometry, ghostMat);
      s.mesh.renderOrder = 5; s.ghost.renderOrder = 950;
      group.add(s.mesh, s.ghost);
    } else {
      s.mesh.geometry.dispose();
      s.mesh.geometry = s.ghost.geometry = g || new THREE.BufferGeometry();
    }
  }

  function addLabel(s) {
    if (s.label) { s.label.material.map.dispose(); s.label.material.dispose(); s.label.removeFromParent(); }
    const text = s.closed ? `${s.area.toFixed(1)} m² · ${s.length.toFixed(1)} m` : `${s.length.toFixed(1)} m`;
    s.label = makeLabel(text, KINDS[s.kind].css);
    let at;
    if (s.closed) {
      at = new THREE.Vector3();
      for (const p of s.pts) at.add(p);
      at.divideScalar(s.pts.length);
    } else at = s.pts[s.pts.length - 1].clone();
    s.label.position.set(at.x, at.y + 0.45, at.z);
    group.add(s.label);
  }

  function finish(s) {
    const n = s.pts.length;
    s.length = planLength(s.pts, false);
    s.closed = n >= 3 && s.length > MIN_CLOSE_LEN &&
      Math.hypot(s.pts[n - 1].x - s.pts[0].x, s.pts[n - 1].z - s.pts[0].z) <= CLOSE_DIST;
    if (s.closed) s.length = planLength(s.pts, true);
    s.area = s.closed ? planArea(s.pts) : null;
    buildMesh(s);
    addLabel(s);
  }

  function disposeStroke(s) {
    s.mesh?.geometry.dispose();
    s.mesh?.removeFromParent(); s.ghost?.removeFromParent();
    if (s.label) { s.label.material.map.dispose(); s.label.material.dispose(); s.label.removeFromParent(); }
  }

  function begin(p) {
    live = { id: `m${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`, kind, closed: false,
             pts: [p.clone()], created: new Date().toISOString(), since: 0 };
    buildMesh(live);
  }
  /* returns true when a point was added */
  function extend(p) {
    const last = live.pts[live.pts.length - 1];
    const d = Math.hypot(p.x - last.x, p.z - last.z);
    if (d < SAMPLE) return false;
    // a fast sweep: fill in at 5 cm so the line stays evenly sampled
    const steps = Math.min(200, Math.max(1, Math.round(d / SAMPLE)));
    for (let i = 1; i <= steps; i++) {
      const f = i / steps;
      live.pts.push(new THREE.Vector3(last.x + (p.x - last.x) * f, last.y + (p.y - last.y) * f, last.z + (p.z - last.z) * f));
    }
    live.since += d;
    buildMesh(live);
    return true;
  }
  function end() {
    const s = live; live = null;
    if (!s) return null;
    if (s.pts.length < 2 || planLength(s.pts, false) < 0.1) { disposeStroke(s); return null; }
    finish(s);
    strokes.push(s);
    save();
    drawHint();
    return s;
  }

  /* ---------------- saving ---------------- */
  const toJSON = () => ({
    site: siteKey || null,
    strokes: strokes.map(s => ({
      id: s.id, kind: s.kind, closed: s.closed,
      points: s.pts.map(p => [r3(p.x), r3(-p.z)]),
      length_m: Math.round(s.length * 100) / 100,
      area_m2: s.area == null ? null : Math.round(s.area * 100) / 100,
      created: s.created,
    })),
  });
  let saving = null, again = false;
  async function save() {
    if (!canSave) { drawHint(); return; }
    if (saving) { again = true; return; }
    status = "saving…"; drawHint();
    saving = (async () => {
      try {
        const r = await fetch(`marks?site=${encodeURIComponent(siteKey)}`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(toJSON()),
        });
        if (r.ok) status = "saved";
        else if (r.status === 501 || r.status === 405 || r.status === 404) {
          canSave = false; status = "not saved: this server has no /marks";
          console.warn("marks: server has no /marks endpoint; run tools/https-serve.py to save");
        } else status = `not saved (${r.status})`;
      } catch (err) {
        status = "not saved (offline)";
        console.warn("marks: save failed", err);
      }
    })();
    await saving;
    saving = null;
    drawHint();
    if (again) { again = false; save(); }
  }

  async function load() {
    if (!siteKey) return;
    try {
      const r = await fetch(`assets/sites/${encodeURIComponent(siteKey)}/marks.json?t=${Date.now()}`, { cache: "no-store" });
      if (!r.ok) return;
      const data = await r.json();
      for (const st of data.strokes || []) {
        if (!KINDS[st.kind] || !Array.isArray(st.points) || st.points.length < 2) continue;
        const pts = st.points.map(([x, y]) => new THREE.Vector3(x, groundY(x, -y), -y));
        const s = { id: st.id, kind: st.kind, pts, created: st.created };
        finish(s);
        if (st.closed && !s.closed) { s.closed = true; s.length = planLength(pts, true); s.area = planArea(pts); buildMesh(s); addLabel(s); }
        strokes.push(s);
      }
      if (strokes.length) console.info(`marks: ${strokes.length} loaded for ${siteKey}`);
      drawHint();
    } catch (err) {
      console.warn("marks: could not read marks.json", err);
    }
  }

  /* ---------------- modes ---------------- */
  function setActive(on) {
    active = !!on;
    if (!active) { if (live) end(); cursor.visible = false; ray.visible = false; }
    hint.visible = active;
    if (active && !renderer.xr.isPresenting && document.pointerLockElement) document.exitPointerLock();
    drawHint();
  }
  function cycleKind() {
    kind = KIND_ORDER[(KIND_ORDER.indexOf(kind) + 1) % KIND_ORDER.length];
    setColours(); drawHint();
  }
  function undo() {
    if (live) { disposeStroke(live); live = null; return; }
    const s = strokes.pop();
    if (!s) return;
    disposeStroke(s);
    save();
    drawHint();
  }

  /* ---------------- headset ---------------- */
  /* call every frame while presenting and in Mark mode */
  function updateXR(controller, trigger) {
    if (!active || !controller) { ray.visible = false; return; }
    controller.getWorldPosition(_o);
    _d.set(0, 0, -1).applyQuaternion(controller.getWorldQuaternion(_q));
    raycaster.set(_o, _d);
    const p = castGround();
    const a = rayGeo.attributes.position;
    a.setXYZ(0, _o.x, _o.y, _o.z);
    if (p) a.setXYZ(1, p.x, p.y + 0.012, p.z);
    else a.setXYZ(1, _o.x + _d.x * 3, _o.y + _d.y * 3, _o.z + _d.z * 3);
    a.needsUpdate = true;
    ray.visible = true;
    if (trigger && p) {
      if (!live) { begin(p); hapticPulse([controller], 0.4, 20); }
      else if (extend(p) && live.since > 0.5) { live.since = 0; hapticPulse([controller], 0.12, 8); }
    } else if (!trigger && live) {
      const s = end();
      if (s) hapticPulse([controller], s.closed ? 0.8 : 0.4, s.closed ? 60 : 25);
    }
    showCursor(p);
  }

  /* ---------------- desktop ---------------- */
  const canvas = renderer.domElement;
  const ndc = new THREE.Vector2();
  function pickAt(e) {
    const r = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    camera.updateMatrixWorld();
    raycaster.setFromCamera(ndc, camera);
    return castGround();
  }
  canvas.addEventListener("pointerdown", e => {
    if (!active || renderer.xr.isPresenting || e.button !== 0) return;
    const p = pickAt(e);
    if (!p) return;
    e.preventDefault();
    try { canvas.setPointerCapture(e.pointerId); } catch (_) {}
    begin(p);
    showCursor(p);
  });
  canvas.addEventListener("pointermove", e => {
    if (!active || renderer.xr.isPresenting) return;
    const p = pickAt(e);
    if (live && p) extend(p);
    showCursor(p);
  });
  const up = e => {
    if (!live || renderer.xr.isPresenting) return;
    try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}
    end();
  };
  canvas.addEventListener("pointerup", up);
  canvas.addEventListener("pointercancel", up);
  addEventListener("keydown", e => {
    if (e.repeat || renderer.xr.isPresenting || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    if (e.code === "KeyM") setActive(!active);
    else if (active && e.code === "KeyK") cycleKind();
    else if (active && e.code === "KeyZ") undo();
  });

  drawHint();
  return {
    get active() { return active; },
    get kind() { return kind; },
    get drawing() { return !!live; },
    get status() { return status; },
    strokes,
    setActive, toggle: () => setActive(!active), cycleKind, undo, updateXR, load, save, toJSON,
    attachHint(controller) { controller.add(hint); },
    /* the site's flat surfaces, for the cursor and for laying loaded marks back on the ground */
    setGround(root) {
      groundMeshes = [];
      root?.traverse(o => {
        if (!o.isMesh || o.isInstancedMesh) return;
        const g = o.geometry;
        if (!g.boundingBox) g.computeBoundingBox();
        const b = g.boundingBox.clone().applyMatrix4(o.matrixWorld);
        const tris = (g.index ? g.index.count : g.attributes.position.count) / 3;
        if (b.max.y < 0.2 && b.min.y > -0.3 && tris < 50000) groundMeshes.push(o);
      });
    },
    update(dt) {
      t += dt;
      if (!renderer.xr.isPresenting) ray.visible = false;
      if (cursor.visible) cursor.scale.setScalar(cursorBase * (1 + 0.07 * Math.sin(t * 6)));
    },
  };
}
