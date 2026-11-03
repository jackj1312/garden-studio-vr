import * as THREE from "three";
import { hapticPulse } from "./presence.js?v=f383e46-1642";
import { buildCollision } from "./surface.js?v=f383e46-1642";
import { createNotes } from "./notes.js?v=h31";   // h22: inXR + Delete (the house review); the garden is unchanged by it

/* ------------------------------------------------------------------ *
 *  Marking: draw on the garden the way you draw the Quest's Guardian.
 *
 *  Point the right controller at anything — the ground, a wall, the
 *  fence, a roof — hold the trigger and sweep: a bright ribbon follows
 *  the surface. Two kinds of mark: a correction ("this is wrong here")
 *  and a proposal (a new bed, a path, a studio footprint). A stroke
 *  that ends within 25 cm of where it began closes into a shape and
 *  shows its area and perimeter. Each finished mark opens a note:
 *  say what's wrong (hold to talk) or type it.
 *
 *  Saved to assets/sites/<site>/marks.json via POST /marks?site=<site>
 *  (tools/https-serve.py). "points" are PLAN coordinates (plan x =
 *  viewer x, plan y = -viewer z, metres); "points3d" and "normals" are
 *  the surface points in viewer coordinates; "surface" is the material
 *  the stroke mostly lay on (FG_brick_gltf: a wall).
 *
 *  Other viewers (the house, src/house/viewer.js ?mode=review) pass:
 *  raycast(ray, far) -> {point, normal, surface, tag} for their own ray
 *  tree (tag: what was hit, e.g. a part name: counted per stroke and
 *  saved, most first, as extra[tagField]), meta() -> fields stamped on a new stroke (version,
 *  view, stage...), annotate(stroke) -> fields added when it ends,
 *  visible(stroke) -> shown now or not (marks of another version stay
 *  in the file but hidden), inXR() (a simulated headset counts),
 *  onChange() (a list to redraw), hint {draw, note} texts and
 *  seeThrough: false (a faint ghost through walls, and labels only
 *  within LABEL_NEAR of the eye, so a house full of marks stays calm).
 *  Those extra fields are saved beside the garden's and kept on load.
 * ------------------------------------------------------------------ */

export const KINDS = {
  correction: { label: "Correction", hex: 0xff5a1f, css: "#ff5a1f" },
  proposal:   { label: "Proposal",   hex: 0x1fd8ff, css: "#1fd8ff" },
};
const KIND_ORDER = ["correction", "proposal"];

const SAMPLE = 0.05;          // a point every 5 cm of cursor travel
const CLOSE_DIST = 0.25;      // ends this near its start: a closed shape
const MIN_CLOSE_LEN = 0.75;   // ...but not a tap or a tiny wiggle
const MAX_REACH = 30;         // metres along the ray
const HALF_W = 0.04;          // ribbon half-width
const LIFT = 0.015;           // ribbon base off the surface, along its normal
const HEIGHT = 0.03;          // ribbon thickness, along the normal
const POLL_MS = 4000;         // while a voice note is being transcribed
const POLL_FOR = 5 * 60 * 1000;
const LABEL_NEAR = 7;         // seeThrough: false: labels show within this many metres of the eye

const UP = new THREE.Vector3(0, 1, 0);
const r3 = v => Math.round(v * 1000) / 1000;

function ribbonGeometry(pts, nrm, closed, hex) {
  const n = pts.length;
  if (n < 2) return null;
  const pos = new Float32Array(n * 4 * 3), col = new Float32Array(n * 4 * 3);
  const c = new THREE.Color(hex), lo = c.clone().multiplyScalar(0.55), hi = c.clone().lerp(new THREE.Color(1, 1, 1), 0.18);
  const t = new THREE.Vector3(), side = new THREE.Vector3(), base = new THREE.Vector3(), top = new THREE.Vector3(), v = new THREE.Vector3();
  for (let i = 0; i < n; i++) {
    const p = pts[i], nn = nrm[i];
    const a = closed ? pts[(i - 1 + n) % n] : pts[Math.max(0, i - 1)];
    const b = closed ? pts[(i + 1) % n] : pts[Math.min(n - 1, i + 1)];
    t.subVectors(b, a);
    side.crossVectors(t, nn);
    if (side.lengthSq() < 1e-10) side.set(1, 0, 0).cross(nn);         // along the normal: any perpendicular
    side.normalize();
    base.copy(p).addScaledVector(nn, LIFT);
    top.copy(base).addScaledVector(nn, HEIGHT);
    const ring = [[base, -HALF_W, lo], [top, -HALF_W * 0.55, hi], [top, HALF_W * 0.55, hi], [base, HALF_W, lo]];
    ring.forEach(([o, s, cc], k) => {
      v.copy(o).addScaledVector(side, s);
      const j = (i * 4 + k) * 3;
      pos[j] = v.x; pos[j + 1] = v.y; pos[j + 2] = v.z;
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

function length3(pts, closed) {
  let L = 0;
  for (let i = 1; i < pts.length; i++) L += pts[i].distanceTo(pts[i - 1]);
  if (closed && pts.length > 2) L += pts[0].distanceTo(pts[pts.length - 1]);
  return L;
}
/* area of a closed 3D polygon (Newell): on the ground it is the plan area, on a wall the wall area */
function area3(pts) {
  let x = 0, y = 0, z = 0;
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i], q = pts[(i + 1) % pts.length];
    x += (p.y - q.y) * (p.z + q.z); y += (p.z - q.z) * (p.x + q.x); z += (p.x - q.x) * (p.y + q.y);
  }
  return Math.hypot(x, y, z) / 2;
}

function roundRect(c, x, y, w, h, r) {
  c.beginPath();
  c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
}
const shorten = (s, n) => s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;

function makeLabel(line1, line2, css) {
  const H = line2 ? 196 : 128;
  const cv = document.createElement("canvas");
  cv.width = 512; cv.height = H;
  const c = cv.getContext("2d");
  c.font = "600 54px system-ui, sans-serif";
  let w = c.measureText(line1).width;
  if (line2) { c.font = "38px system-ui, sans-serif"; w = Math.max(w, c.measureText(line2).width); }
  w = Math.min(500, w + 64);
  const x = (512 - w) / 2;
  c.fillStyle = "rgba(14,16,14,0.88)"; roundRect(c, x, 14, w, H - 28, 22); c.fill();
  c.fillStyle = css; roundRect(c, x, 14, 14, H - 28, 7); c.fill();
  c.textAlign = "center"; c.textBaseline = "middle";
  c.fillStyle = "#f4f3ee"; c.font = "600 54px system-ui, sans-serif";
  c.fillText(line1, 256 + 7, 66);
  if (line2) { c.fillStyle = "#d6d8cf"; c.font = "38px system-ui, sans-serif"; c.fillText(line2, 256 + 7, 132); }
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, toneMapped: false, fog: false, depthTest: false, transparent: true }));
  s.scale.set(0.72, 0.72 * H / 512, 1);
  s.renderOrder = 960;
  return s;
}

/* the fields every stroke has; anything else a viewer stamps on (meta / annotate) rides along in s.extra */
const CORE = new Set(["id", "kind", "closed", "points", "points3d", "normals", "surface", "length_m", "area_m2", "created", "note", "audio", "note_status"]);

function aimController(controller, ray, rotation) {
  controller.getWorldPosition(ray.origin);
  ray.direction.set(0, 0, -1).applyQuaternion(controller.getWorldQuaternion(rotation));
}

/* The studio's right trigger owns exactly one gesture until release. Garden tools use the
   same controller ray as review marks, with a different destination for the stroke. */
export function createEditorStroke() {
  const ray = new THREE.Ray(), rotation = new THREE.Quaternion();
  let held = false, drawing = false, startY = 0;
  return {
    get drawing() { return drawing; },
    skip(trigger) { held = !!trigger; },
    cancel(consumer) { if (drawing) consumer.cancel(); drawing = held = false; },
    frame(controller, trigger, consumer) {
      if (!controller) { if (drawing) consumer.cancel(); drawing = held = false; return null; }
      aimController(controller, ray, rotation);
      const h = consumer.project(ray);
      if (trigger && !held && h) { startY = ray.direction.y; consumer.begin(h); drawing = true; }
      else if (trigger && drawing && h) { h.verticalDelta = (ray.direction.y - startY) * 2; consumer.move(h); }
      else if (!trigger && drawing) { if (h) { h.verticalDelta = (ray.direction.y - startY) * 2; consumer.move(h); } drawing = false; consumer.end(); }
      if(!trigger&&!drawing&&h)consumer.hover?.(h);
      held = trigger;
      return h;
    },
  };
}

export function createMarks({ scene, camera, renderer, siteKey, onActive, raycast = null, meta = null, annotate = null,
                              visible = null, inXR = null, onChange = null, hint: hintText = null, seeThrough = true, tagField = "elements",
                              lockAim = false }) {
  const xr = inXR || (() => renderer.xr.isPresenting);
  const shown = s => !visible || visible(s);
  const changed = () => { try { onChange?.(); } catch (err) { console.warn("marks: onChange", err); } };
  const ribbonMat = new THREE.MeshBasicMaterial({
    vertexColors: true, toneMapped: false, fog: false, side: THREE.DoubleSide,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
  });
  /* a faint copy drawn over everything: keeps a line readable through
     the grass tufts and behind a hedge */
  const ghostMat = new THREE.MeshBasicMaterial({
    vertexColors: true, toneMapped: false, fog: false, side: THREE.DoubleSide,
    transparent: true, opacity: seeThrough ? 0.3 : 0.1, depthTest: false, depthWrite: false,
  });

  const group = new THREE.Group();
  group.name = "Marks";
  scene.add(group);
  const notes = createNotes({ scene, camera, renderer, siteKey, inXR: xr });

  /* cursor: a glowing ring lying on whatever the ray hits, like the Guardian's */
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
  raycaster.camera = camera;             // sprites (the labels) need it
  const floor = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  let collision = null;
  const _o = new THREE.Vector3(), _d = new THREE.Vector3(), _q = new THREE.Quaternion();
  const surf = { point: new THREE.Vector3(), normal: new THREE.Vector3(0, 1, 0), surface: "ground" };
  let t = 0, cursorBase = 1, triggerWas = false, hoverLabel = null, labelTick = 0;

  function drawHint() {
    const k = KINDS[kind];
    hctx.clearRect(0, 0, HW, HH);
    hctx.fillStyle = "rgba(14,16,14,0.9)"; roundRect(hctx, 2, 2, HW - 4, HH - 4, 20); hctx.fill();
    hctx.fillStyle = k.css; roundRect(hctx, 2, 2, 16, HH - 4, 8); hctx.fill();
    hctx.fillStyle = k.css; hctx.font = "700 46px system-ui, sans-serif";
    hctx.fillText(`MARK · ${k.label}`, 36, 58);
    hctx.fillStyle = "#e6e7e0"; hctx.font = "26px system-ui, sans-serif";
    hctx.fillText(notes.isOpen ? (hintText?.note || "Trigger types · hold A (or the button) to talk")
      : (hintText?.draw || `Trigger draw · Grip undo · A kind · ${siteKey ? "B" : "L-stick"} done`), 36, 104);
    hctx.fillStyle = "#a7ab9e"; hctx.font = "24px system-ui, sans-serif";
    const n = strokes.filter(shown).length;
    hctx.fillText(`${n} mark${n === 1 ? "" : "s"}${status ? " · " + status : ""} · point at a label to edit its note`.slice(0, 60), 36, 146);
    hintTex.needsUpdate = true;
    if (domHint) {
      domHint.hidden = !active;
      domHint.style.setProperty("--mark", k.css);
      domHint.querySelector("[data-kind]").textContent = k.label;
      const n = strokes.filter(shown).length;
      domHint.querySelector("[data-status]").textContent =
        `${n} mark${n === 1 ? "" : "s"}${status ? " · " + status : ""}`;
    }
  }

  function setColours() {
    ringMat.color.setHex(KINDS[kind].hex);
    rayMat.color.setHex(KINDS[kind].hex);
  }

  /* where the ray meets the site: walls, roofs, fences, kerbs, ground (the
     collision copy), else the y = 0 plane */
  function castSurface() {
    if (raycast) {                          // the viewer's own ray tree (the house BVH); nothing hit = nothing to draw on
      const h = raycast(raycaster.ray, MAX_REACH);
      if (!h) return null;
      surf.point.copy(h.point); surf.normal.copy(h.normal); surf.surface = h.surface || "surface"; surf.tag = h.tag ?? null;
      return surf;
    }
    surf.tag = null;
    const h = collision?.raycast(raycaster.ray, MAX_REACH);
    if (h) {
      surf.point.copy(h.point); surf.normal.copy(h.normal); surf.surface = h.surface;
      return surf;
    }
    if (!raycaster.ray.intersectPlane(floor, surf.point)) return null;
    if (raycaster.ray.origin.distanceTo(surf.point) > MAX_REACH) return null;
    surf.normal.copy(UP); surf.surface = "ground";
    return surf;
  }
  function groundY(x, z) {
    if (!collision) return 0;
    raycaster.set(_o.set(x, 3, z), _d.set(0, -1, 0));
    const h = collision.raycast(raycaster.ray, 6);
    return h ? h.point.y : 0;
  }

  function showCursor(h) {
    if (!h) { cursor.visible = false; return; }
    cursor.visible = true;
    cursor.position.copy(h.point).addScaledVector(h.normal, 0.012);
    cursor.quaternion.setFromUnitVectors(UP, h.normal);
    // near the start of a long enough stroke: the ring turns white and grows — let go to close it
    const closing = live && live.pts.length > 2 && length3(live.pts, false) > MIN_CLOSE_LEN &&
      h.point.distanceTo(live.pts[0]) <= CLOSE_DIST;
    ringMat.color.setHex(closing ? 0xffffff : KINDS[kind].hex);
    cursorBase = closing ? 1.5 : 1;
    cursor.scale.setScalar(cursorBase * (1 + 0.07 * Math.sin(t * 6)));
  }

  function buildMesh(s) {
    const g = ribbonGeometry(s.pts, s.nrm, s.closed, KINDS[s.kind].hex);
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

  function dropLabel(s) {
    if (!s.label) return;
    s.label.material.map.dispose(); s.label.material.dispose(); s.label.removeFromParent();
    s.label = null;
  }
  function addLabel(s) {
    dropLabel(s);
    const line1 = s.closed ? `${s.area.toFixed(1)} m² · ${s.length.toFixed(1)} m` : `${s.length.toFixed(1)} m`;
    const line2 = s.note ? shorten(s.note, 28)
      : s.note_status === "awaiting transcription" ? "voice note · transcribing…" : "";
    s.label = makeLabel(line1, line2, KINDS[s.kind].css);
    s.label.userData.stroke = s;
    s.label.visible = shown(s);
    const at = new THREE.Vector3(), n = new THREE.Vector3();
    if (s.closed) for (const p of s.pts) at.add(p);
    else at.copy(s.pts[s.pts.length - 1]);
    if (s.closed) at.divideScalar(s.pts.length);
    for (const v of s.nrm) n.add(v);
    if (n.lengthSq() < 1e-6) n.copy(UP);
    n.normalize();
    s.label.position.copy(at).addScaledVector(n, 0.3).addScaledVector(UP, 0.15);
    group.add(s.label);
  }

  function finish(s) {
    const n = s.pts.length;
    s.closed = n >= 3 && length3(s.pts, false) > MIN_CLOSE_LEN && s.pts[n - 1].distanceTo(s.pts[0]) <= CLOSE_DIST;
    s.length = length3(s.pts, s.closed);
    s.area = s.closed ? area3(s.pts) : null;
    if (!s.surface) {
      let best = "ground", bc = 0;
      for (const [k, c] of s.surfCount || []) if (c > bc) { best = k; bc = c; }
      s.surface = best;
    }
    if (s.tagCount?.size) {                 // what the stroke lay on, most first (the house: element ids)
      s.extra = s.extra || {};
      s.extra[tagField] = [...s.tagCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([k]) => k);
    }
    buildMesh(s);
    addLabel(s);
    setShown(s);
  }
  function setShown(s) {
    const on = shown(s);
    if (s.mesh) s.mesh.visible = on;
    if (s.ghost) s.ghost.visible = on;
    if (s.label) s.label.visible = on && near(s);
  }
  const _eye = new THREE.Vector3();
  function near(s) {
    if (seeThrough || !s.label) return true;
    camera.getWorldPosition(_eye);
    return s.label.position.distanceToSquared(_eye) < LABEL_NEAR * LABEL_NEAR;
  }

  function disposeStroke(s) {
    s.mesh?.geometry.dispose();
    s.mesh?.removeFromParent(); s.ghost?.removeFromParent();
    dropLabel(s);
  }

  function begin(h) {
    live = { id: `m${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`, kind, closed: false,
             pts: [h.point.clone()], nrm: [h.normal.clone()], surfCount: new Map([[h.surface, 1]]),
             tagCount: h.tag != null ? new Map([[h.tag, 1]]) : null,
             created: new Date().toISOString(), since: 0, note: null, audio: null, note_status: null,
             extra: meta ? { ...meta() } : null };
    buildMesh(live);
  }
  /* returns true when a point was added */
  function extend(h) {
    const last = live.pts[live.pts.length - 1], lastN = live.nrm[live.nrm.length - 1];
    const d = h.point.distanceTo(last);
    if (d < SAMPLE) return false;
    // a sweep across one surface: fill in at 5 cm so the line stays evenly sampled.
    // A jump to another surface (a corner, or the ray leaving a wall) is a single segment.
    const sameFace = h.normal.dot(lastN) > 0.9 && d < 1.0;
    const steps = sameFace ? Math.min(200, Math.max(1, Math.round(d / SAMPLE))) : 1;
    for (let i = 1; i <= steps; i++) {
      const f = i / steps;
      live.pts.push(new THREE.Vector3().lerpVectors(last, h.point, f));
      live.nrm.push(i === steps ? h.normal.clone() : new THREE.Vector3().lerpVectors(lastN, h.normal, f).normalize());
    }
    live.surfCount.set(h.surface, (live.surfCount.get(h.surface) || 0) + steps);
    if (h.tag != null) { live.tagCount = live.tagCount || new Map(); live.tagCount.set(h.tag, (live.tagCount.get(h.tag) || 0) + steps); }
    live.since += d;
    buildMesh(live);
    return true;
  }
  function end() {
    const s = live; live = null;
    if (!s) return null;
    if (s.pts.length < 2 || length3(s.pts, false) < 0.1) { disposeStroke(s); return null; }
    finish(s);
    if (annotate) { try { s.extra = { ...(s.extra || {}), ...annotate(s) }; } catch (err) { console.warn("marks: annotate", err); } }
    strokes.push(s);
    save();
    drawHint();
    openNote(s);
    changed();
    return s;
  }

  /* ---------------- notes ---------------- */
  const noteCallbacks = {
    changed(s) {
      if (!strokes.includes(s)) return;
      addLabel(s);
      save();
      if (s.note_status === "awaiting transcription") watchTranscripts();
      drawHint();
      changed();
    },
    /* the note panel's Delete (only offered where the viewer lists marks) */
    remove: onChange ? s => remove(s) : null,
  };
  function openNote(s) { notes.open(s, noteCallbacks); drawHint(); }

  /* poll marks.json while a voice note is being transcribed on the server */
  let pollTimer = null, pollSince = 0;
  function watchTranscripts() {
    pollSince = Date.now();
    if (pollTimer || !siteKey) return;
    pollTimer = setInterval(pollOnce, POLL_MS);
  }
  async function pollOnce() {
    const pending = strokes.filter(s => s.note_status === "awaiting transcription");
    if (!pending.length || Date.now() - pollSince > POLL_FOR) { clearInterval(pollTimer); pollTimer = null; return; }
    try {
      const r = await fetch(`assets/sites/${encodeURIComponent(siteKey)}/marks.json?t=${Date.now()}`, { cache: "no-store" });
      if (!r.ok) return;
      const data = await r.json();
      const byId = new Map((data.strokes || []).map(s => [s.id, s]));
      for (const s of pending) {
        const f = byId.get(s.id);
        if (f && f.note_status === "transcribed" && f.note) {
          s.note = f.note; s.note_status = "transcribed";
          addLabel(s);
          notes.refresh(s);
          changed();
          console.info(`marks: transcript for ${s.id}: ${f.note}`);
        }
      }
    } catch (_) { /* try again next tick */ }
  }

  /* labels you can point at to reopen a note */
  function pickLabel() {
    const labels = strokes.filter(shown).map(s => s.label).filter(l => l?.visible);
    if (!labels.length) return null;
    const h = raycaster.intersectObjects(labels, false)[0];
    return h ? h : null;
  }
  function setHoverLabel(l) {
    if (hoverLabel === l) return;
    if (hoverLabel) hoverLabel.scale.multiplyScalar(1 / 1.12);
    hoverLabel = l;
    if (l) l.scale.multiplyScalar(1.12);
  }

  /* ---------------- saving ---------------- */
  const toJSON = () => ({
    site: siteKey || null,
    strokes: strokes.map(s => ({
      id: s.id, kind: s.kind, closed: s.closed,
      points: s.pts.map(p => [r3(p.x), r3(-p.z)]),
      points3d: s.pts.map(p => [r3(p.x), r3(p.y), r3(p.z)]),
      normals: s.nrm.map(n => [r3(n.x), r3(n.y), r3(n.z)]),
      surface: s.surface || "ground",
      length_m: Math.round(s.length * 100) / 100,
      area_m2: s.area == null ? null : Math.round(s.area * 100) / 100,
      created: s.created,
      note: s.note || null,
      audio: s.audio || null,
      note_status: s.note_status || null,
      ...(s.extra || {}),
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
    changed();
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
        const has3d = Array.isArray(st.points3d) && st.points3d.length === st.points.length;
        const pts = has3d ? st.points3d.map(([x, y, z]) => new THREE.Vector3(x, y, z))
                          : st.points.map(([x, y]) => new THREE.Vector3(x, groundY(x, -y), -y));   // older, ground-only marks
        const nrm = has3d && Array.isArray(st.normals) && st.normals.length === pts.length
          ? st.normals.map(([x, y, z]) => new THREE.Vector3(x, y, z).normalize()) : pts.map(() => UP.clone());
        const extra = {};
        for (const [k, v] of Object.entries(st)) if (!CORE.has(k)) extra[k] = v;
        const s = { id: st.id, kind: st.kind, pts, nrm, created: st.created, surface: st.surface || "ground",
                    note: st.note || null, audio: st.audio || null, note_status: st.note_status || null,
                    extra: Object.keys(extra).length ? extra : null };
        finish(s);
        if (st.closed && !s.closed) { s.closed = true; s.length = length3(pts, true); s.area = area3(pts); buildMesh(s); addLabel(s); }
        strokes.push(s);
      }
      if (strokes.length) console.info(`marks: ${strokes.length} loaded for ${siteKey}`);
      if (strokes.some(s => s.note_status === "awaiting transcription")) watchTranscripts();
      drawHint();
      changed();
    } catch (err) {
      console.warn("marks: could not read marks.json", err);
    }
  }

  /* ---------------- modes ---------------- */
  function setActive(on) {
    const was = active;
    active = !!on;
    if (active && !was) onActive?.(true);
    if (!active) { if (live) end(); if (notes.isOpen) notes.save(); cursor.visible = false; ray.visible = false; setHoverLabel(null); }
    hint.visible = active;
    if (active && !xr() && document.pointerLockElement && !lockAim) document.exitPointerLock();
    drawHint();
    changed();
  }
  function cycleKind() {
    kind = KIND_ORDER[(KIND_ORDER.indexOf(kind) + 1) % KIND_ORDER.length];
    setColours(); drawHint();
  }
  function undo() {
    if (live) { disposeStroke(live); live = null; return; }
    let i = strokes.length - 1;
    while (i >= 0 && !shown(strokes[i])) i--;          // the last mark you can see (not one on another version)
    if (i >= 0) remove(strokes[i]);
  }
  function remove(s) {
    const i = strokes.indexOf(s);
    if (i < 0) return false;
    strokes.splice(i, 1);
    notes.forget(s);
    if (hoverLabel === s.label) hoverLabel = null;
    disposeStroke(s);
    save();
    drawHint();
    changed();
    return true;
  }
  /* the viewer's filter changed (another version on screen): show / hide each mark */
  function refreshVisibility() {
    for (const s of strokes) setShown(s);
    if (hoverLabel && !hoverLabel.visible) setHoverLabel(null);
    drawHint();
    changed();
  }

  /* ---------------- headset ---------------- */
  function drawRay(len) {
    const a = rayGeo.attributes.position;
    a.setXYZ(0, _o.x, _o.y, _o.z);
    a.setXYZ(1, _o.x + _d.x * len, _o.y + _d.y * len, _o.z + _d.z * len);
    a.needsUpdate = true;
    ray.visible = true;
  }
  /* call every frame while presenting and in Mark mode */
  function updateXR(controller, trigger) {
    if (!active || !controller) { ray.visible = false; triggerWas = trigger; return; }
    aimController(controller, raycaster.ray, _q);
    _o.copy(raycaster.ray.origin); _d.copy(raycaster.ray.direction);
    const pressed = trigger && !triggerWas;
    triggerWas = trigger;

    if (notes.isOpen) {                       // the note panel has the trigger
      const d = notes.updateXR(raycaster, trigger, controller);
      drawRay(d ?? 2); cursor.visible = false; setHoverLabel(null);
      if (!notes.isOpen) drawHint();
      return;
    }
    if (!live) {                              // pointing at a label: its note
      const lh = pickLabel();
      setHoverLabel(lh?.object || null);
      if (lh) {
        drawRay(lh.distance); cursor.visible = false;
        if (pressed) { openNote(lh.object.userData.stroke); hapticPulse([controller], 0.3, 15); }
        return;
      }
    }
    const h = castSurface();
    drawRay(h ? h.point.distanceTo(_o) : 3);
    if (trigger && h) {
      if (!live) { if (pressed) { begin(h); hapticPulse([controller], 0.4, 20); } }
      else if (extend(h) && live.since > 0.5) { live.since = 0; hapticPulse([controller], 0.12, 8); }
    } else if (!trigger && live) {
      const s = end();
      if (s) hapticPulse([controller], s.closed ? 0.8 : 0.4, s.closed ? 60 : 25);
    }
    showCursor(h);
  }

  /* ---------------- desktop ---------------- */
  const canvas = renderer.domElement;
  const ndc = new THREE.Vector2();
  /* lockAim (the house viewer's mouse-look): with the mouse captured, the stroke follows the centre crosshair */
  function aimAt(e) {
    const r = canvas.getBoundingClientRect();
    if (lockAim && document.pointerLockElement === canvas) ndc.set(0, 0);
    else ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    camera.updateMatrixWorld();
    raycaster.setFromCamera(ndc, camera);
  }
  canvas.addEventListener("pointerdown", e => {
    if (!active || xr() || e.button !== 0) return;
    aimAt(e);
    const lh = pickLabel();
    if (lh) { e.preventDefault(); openNote(lh.object.userData.stroke); return; }
    const h = castSurface();
    if (!h) return;
    e.preventDefault();
    try { canvas.setPointerCapture(e.pointerId); } catch (_) {}
    begin(h);
    showCursor(h);
  });
  canvas.addEventListener("pointermove", e => {
    if (!active || xr()) return;
    aimAt(e);
    if (!live) setHoverLabel(pickLabel()?.object || null);
    const h = castSurface();
    if (live && h) extend(h);
    showCursor(h);
  });
  const up = e => {
    if (!live || xr()) return;
    try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}
    end();
  };
  canvas.addEventListener("pointerup", up);
  canvas.addEventListener("pointercancel", up);
  addEventListener("keydown", e => {
    if (e.repeat || xr() || e.metaKey || e.ctrlKey || e.altKey) return;
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
    get noteOpen() { return notes.isOpen; },
    get collision() { return collision; },
    strokes, notes,
    setActive, toggle: () => setActive(!active), cycleKind, undo, remove, refreshVisibility, isShown: shown, updateXR, load, save, toJSON, openNote,
    /* the A button while a note is open: hold to talk */
    talk(down) { notes.talk(down); drawHint(); },
    attachHint(controller) { controller.add(hint); },
    /* the site's surfaces, for the ray and for laying older marks back on the ground */
    setGround(root) { collision = root ? buildCollision(root) : null; },
    update(dt) {
      t += dt;
      notes.update(dt);
      if (!xr()) ray.visible = false;
      if (cursor.visible) cursor.scale.setScalar(cursorBase * (1 + 0.07 * Math.sin(t * 6)));
      if (!seeThrough && (labelTick += dt) > 0.25) { labelTick = 0; for (const s of strokes) if (s.label) s.label.visible = shown(s) && near(s); }
    },
  };
}
