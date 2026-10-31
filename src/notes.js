import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  A note on a mark: say what's wrong, or type it.
 *
 *  In the headset a panel floats in front of you with a big "Hold to
 *  talk" button, a keyboard you type on with the controller ray and
 *  trigger, the text so far, and Save / Skip. Holding A also talks.
 *  On a flat screen a small note box does the same job.
 *
 *  Voice: getUserMedia + MediaRecorder (audio only, mic asked for once
 *  and kept). The clip goes to POST /marks/audio?site=&id= and the
 *  server transcribes it in the background (tools/transcribe.py); the
 *  marks module polls for the text and shows it when it lands.
 * ------------------------------------------------------------------ */

const CW = 1024, CH = 800;                  // canvas pixels
const PW = 0.9;                             // panel width in metres
const KIND_CSS = { correction: "#ff5a1f", proposal: "#1fd8ff" };

function roundRect(c, x, y, w, h, r) {
  c.beginPath();
  c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
}

/* the keyboard, in canvas pixels */
const KEYS = [];
{
  const KW = 92, KH = 85, G = 6, X0 = 25;
  const row = (chars, y, x0) => [...chars].forEach((ch, i) => KEYS.push({ x: x0 + i * (KW + G), y, w: KW, h: KH, label: ch.toUpperCase(), act: ch }));
  row("1234567890", 300, X0);
  row("qwertyuiop", 393, X0);
  row("asdfghjkl", 486, X0 + 49);
  row("zxcvbnm", 579, X0 + 98);
  KEYS.push({ x: X0 + 98 + 7 * (KW + G), y: 579, w: 2 * KW + G, h: KH, label: "⌫", act: "back" });
  let x = X0;
  for (const ch of [",", ".", "?"]) { KEYS.push({ x, y: 672, w: KW, h: KH, label: ch, act: ch }); x += KW + G; }
  KEYS.push({ x, y: 672, w: 488, h: KH, label: "space", act: " " }); x += 488 + G;
  for (const ch of ["'", "-"]) { KEYS.push({ x, y: 672, w: KW, h: KH, label: ch, act: ch }); x += KW + G; }
  KEYS.push({ x: 25, y: 205, w: 470, h: 80, label: "Hold to talk", act: "talk" });
  KEYS.push({ x: 510, y: 205, w: 220, h: 80, label: "Skip", act: "skip" });
  KEYS.push({ x: 745, y: 205, w: 254, h: 80, label: "Save", act: "save" });
}

export function createNotes({ scene, camera, renderer, siteKey }) {
  /* ---------------- headset panel ---------------- */
  const canvas = document.createElement("canvas");
  canvas.width = CW; canvas.height = CH;
  const ctx = canvas.getContext("2d");
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const panel = new THREE.Mesh(new THREE.PlaneGeometry(PW, PW * CH / CW),
    new THREE.MeshBasicMaterial({ map: tex, transparent: true, toneMapped: false, fog: false, depthTest: false }));
  panel.renderOrder = 1020;
  panel.visible = false;
  scene.add(panel);

  /* ---------------- desktop box ---------------- */
  const box = document.getElementById("noteBox");
  const boxText = document.getElementById("noteText");
  const boxRec = document.getElementById("noteRec");
  const boxTitle = box?.querySelector("[data-title]");
  const boxStatus = box?.querySelector("[data-status]");

  let stroke = null, cb = null, text = "", status = "", hover = null, dirty = true;
  let recording = null, recStart = 0, recBlink = 0;
  let micStream = null, canUpload = !!siteKey;

  const isOpen = () => !!stroke;
  const headset = () => renderer.xr.isPresenting;

  function wrap(str, max) {
    const words = str.split(" "), lines = [];
    let line = "";
    for (const w of words) {
      if ((line + " " + w).trim().length > max) { lines.push(line); line = w; }
      else line = (line + " " + w).trim();
    }
    lines.push(line);
    return lines;
  }

  function draw() {
    const k = KIND_CSS[stroke?.kind] || "#ffffff";
    ctx.clearRect(0, 0, CW, CH);
    ctx.fillStyle = "rgba(14,16,14,0.94)"; roundRect(ctx, 2, 2, CW - 4, CH - 4, 28); ctx.fill();
    ctx.fillStyle = k; roundRect(ctx, 2, 2, 18, CH - 4, 9); ctx.fill();
    ctx.textBaseline = "middle";
    ctx.fillStyle = k; ctx.font = "700 40px system-ui, sans-serif"; ctx.textAlign = "left";
    ctx.fillText(`NOTE · ${stroke?.kind === "proposal" ? "Proposal" : "Correction"}`, 40, 46);
    ctx.fillStyle = "#b9bcb2"; ctx.font = "28px system-ui, sans-serif"; ctx.textAlign = "right";
    ctx.fillText(status || "trigger types · hold A to talk", CW - 28, 46);
    // the text so far
    ctx.fillStyle = "rgba(255,255,255,0.07)"; roundRect(ctx, 25, 80, CW - 50, 110, 16); ctx.fill();
    ctx.textAlign = "left"; ctx.font = "36px system-ui, sans-serif";
    const shown = text || "";
    let lines = wrap(shown + (Math.floor(recBlink * 2) % 2 ? "" : "|"), 48);
    if (lines.length > 2) lines = ["…" + lines[lines.length - 2], lines[lines.length - 1]];
    ctx.fillStyle = shown ? "#f4f3ee" : "#7d8177";
    if (!shown) ctx.fillText("What's wrong here, or what's proposed?", 50, 135);
    else lines.forEach((l, i) => ctx.fillText(l, 50, 115 + i * 44));
    // keys
    for (const key of KEYS) {
      const on = hover === key;
      let fill = on ? "rgba(255,255,255,0.28)" : "rgba(255,255,255,0.1)", ink = "#eef0e8", label = key.label;
      if (key.act === "talk") {
        fill = recording ? "#d8342b" : on ? "#3b8f55" : "#2d6e41";
        label = recording ? `● Recording ${Math.floor((performance.now() - recStart) / 1000)} s · let go to stop` : "● Hold to talk";
      }
      if (key.act === "save") { fill = on ? "#9cc98a" : "#7aa86a"; ink = "#11140f"; }
      ctx.fillStyle = fill; roundRect(ctx, key.x, key.y, key.w, key.h, 14); ctx.fill();
      ctx.fillStyle = ink; ctx.textAlign = "center";
      ctx.font = key.act === "talk" || key.act === "save" || key.act === "skip" ? "600 34px system-ui, sans-serif" : "600 38px system-ui, sans-serif";
      if (key.act === "talk" && recording) ctx.font = "600 27px system-ui, sans-serif";
      ctx.fillText(label, key.x + key.w / 2, key.y + key.h / 2 + 2);
    }
    tex.needsUpdate = true;
    dirty = false;
    if (box) {
      boxStatus.textContent = status;
      boxRec.textContent = recording ? "■ Stop" : "● Record";
      boxRec.classList.toggle("rec", !!recording);
    }
  }

  function place() {
    const h = new THREE.Vector3(), f = new THREE.Vector3();
    camera.getWorldPosition(h);
    camera.getWorldDirection(f);
    f.y = 0; if (f.lengthSq() < 1e-6) f.set(0, 0, -1); f.normalize();
    panel.position.set(h.x + f.x * 0.85, h.y - 0.22, h.z + f.z * 0.85);
    panel.lookAt(h.x, h.y - 0.05, h.z);
    panel.updateMatrixWorld(true);
  }

  function open(s, callbacks) {
    if (stroke && stroke !== s) finish(text !== (stroke.note || ""));   // keep what was typed on the last one
    stroke = s; cb = callbacks;
    text = s.note || "";
    status = s.note_status === "awaiting transcription" ? "transcribing your voice note…" : "";
    hover = null;
    if (headset()) { place(); panel.visible = true; }
    else if (box) {
      box.hidden = false;
      boxTitle.textContent = `Note · ${s.kind === "proposal" ? "Proposal" : "Correction"}`;
      boxTitle.style.color = KIND_CSS[s.kind];
      boxText.value = text;
      setTimeout(() => boxText.focus(), 0);
    }
    draw();
  }
  function close() {
    if (recording) stopRecording(false);
    stroke = null; cb = null; panel.visible = false;
    if (box) { box.hidden = true; boxText.blur(); }
  }
  /* save=true writes the text into the stroke */
  function finish(save) {
    if (!stroke) return;
    const s = stroke, c = cb;
    if (save) {
      const t = (headset() || !box ? text : boxText.value).trim().slice(0, 500);
      if (t !== (s.note || "")) {
        s.note = t || null;                    // an edited transcript counts as typed
        s.note_status = t ? "typed" : (s.audio ? s.note_status : null);
        c?.changed(s);
      }
    }
    close();
  }

  /* the server's transcript arrived for this stroke */
  function refresh(s) {
    if (stroke !== s) return;
    if (s.note && (!text || status.startsWith("transcribing"))) { text = s.note; if (box && !headset()) boxText.value = text; }
    status = s.note_status === "transcribed" ? "transcribed" : status;
    dirty = true;
    if (!headset()) draw();
  }

  /* ---------------- voice ---------------- */
  async function startRecording() {
    if (recording || !stroke) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      status = "no microphone in this browser"; dirty = true; draw(); return;
    }
    const s = stroke;
    try {
      if (!micStream) { status = "asking for the microphone…"; draw(); micStream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    } catch (err) {
      status = "microphone blocked"; console.warn("notes: microphone", err); draw(); return;
    }
    if (stroke !== s) return;
    const type = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"].find(t => MediaRecorder.isTypeSupported?.(t));
    const rec = new MediaRecorder(micStream, type ? { mimeType: type } : undefined);
    const chunks = [];
    rec.ondataavailable = e => { if (e.data?.size) chunks.push(e.data); };
    rec.onstop = () => {
      const keep = rec._keep;
      const secs = (performance.now() - recStart) / 1000;
      if (!keep) return;
      if (secs < 0.4 || !chunks.length) { status = "too short — hold while you talk"; dirty = true; draw(); return; }
      upload(s, new Blob(chunks, { type: (rec.mimeType || type || "audio/webm") }));
    };
    rec.start(250);
    recording = rec; recStart = performance.now();
    status = "listening…"; dirty = true; draw();
  }
  function stopRecording(keep = true) {
    if (!recording) return;
    const rec = recording; recording = null;
    rec._keep = keep;
    try { rec.stop(); } catch (_) {}
    status = keep ? "uploading…" : ""; dirty = true; draw();
  }
  async function upload(s, blob) {
    if (!canUpload) { status = "voice not saved: no site"; dirty = true; if (stroke === s) draw(); return; }
    const ctype = (blob.type || "audio/webm").split(";")[0];
    try {
      const r = await fetch(`marks/audio?site=${encodeURIComponent(siteKey)}&id=${encodeURIComponent(s.id)}`,
        { method: "POST", headers: { "Content-Type": ctype }, body: blob });
      if (r.status === 501 || r.status === 405 || r.status === 404) {
        canUpload = false; status = "voice not saved: this server has no /marks/audio";
        console.warn("notes: server has no /marks/audio; run tools/https-serve.py");
      } else if (!r.ok) status = `voice not saved (${r.status})`;
      else {
        const res = await r.json();
        s.audio = res.file; s.note_status = res.note_status || "awaiting transcription";
        status = s.note_status === "transcribed" ? "transcribed" : "voice saved · transcribing…";
        cb?.changed(s);
      }
    } catch (err) {
      status = "voice not saved (offline)"; console.warn("notes: upload", err);
    }
    dirty = true;
    if (stroke === s) draw();
  }

  /* ---------------- headset input ---------------- */
  const _uv = new THREE.Vector2();
  let triggerWas = false;
  function keyAt(uv) {
    const x = uv.x * CW, y = (1 - uv.y) * CH;
    return KEYS.find(k => x >= k.x && x <= k.x + k.w && y >= k.y && y <= k.y + k.h) || null;
  }
  function press(key) {
    if (!key) return;
    if (key.act === "save") { finish(true); return; }
    if (key.act === "skip") { finish(false); return; }
    if (key.act === "talk") { startRecording(); return; }
    if (key.act === "back") text = text.slice(0, -1);
    else if (text.length < 500) text += key.act;
    if (status && !recording && !status.startsWith("transcribing")) status = "";
    dirty = true;
  }
  /* returns the hit distance along the ray, or null */
  function updateXR(raycaster, trigger, controller) {
    if (!stroke || !panel.visible) { triggerWas = trigger; return null; }
    const hit = raycaster.intersectObject(panel, false)[0];
    const key = hit ? keyAt(_uv.copy(hit.uv)) : null;
    if (key !== hover) { hover = key; dirty = true; }
    if (trigger && !triggerWas && key) {
      press(key);
      try { controller?.userData?.source?.gamepad?.hapticActuators?.[0]?.pulse?.(0.25, 12); } catch (_) {}
    }
    if (!trigger && triggerWas && recording) stopRecording(true);   // "hold to talk" let go
    triggerWas = trigger;
    return hit ? hit.distance : null;
  }

  /* ---------------- desktop input ---------------- */
  if (box) {
    boxText.addEventListener("keydown", e => {
      e.stopPropagation();                   // typing W must not walk
      if (e.key === "Enter") { e.preventDefault(); finish(true); }
      else if (e.key === "Escape") { e.preventDefault(); finish(false); }
    });
    boxText.addEventListener("keyup", e => e.stopPropagation());
    boxText.addEventListener("input", () => { text = boxText.value; });
    boxRec.addEventListener("click", () => { recording ? stopRecording(true) : startRecording(); });
    document.getElementById("noteSave").addEventListener("click", () => finish(true));
    document.getElementById("noteSkip").addEventListener("click", () => finish(false));
  }

  return {
    get isOpen() { return isOpen(); },
    get stroke() { return stroke; },
    get text() { return text; },
    get status() { return status; },
    get recording() { return !!recording; },
    open, refresh, updateXR,
    save: () => finish(true), skip: () => finish(false),
    /* stroke removed (undo): drop the panel without saving */
    forget(s) { if (stroke === s) close(); },
    /* the A button: hold to talk */
    talk(down) { if (!stroke) return; if (down) startRecording(); else stopRecording(true); },
    /* for tests: upload a clip as if it had been recorded */
    uploadBlob(blob) { if (stroke) upload(stroke, blob); },
    update(dt) {
      if (!stroke) return;
      recBlink += dt;
      if (recording && performance.now() - recStart > 60000) stopRecording(true);   // a minute is plenty
      if (panel.visible && (dirty || recording || Math.floor(recBlink * 2) !== Math.floor((recBlink - dt) * 2))) draw();
    },
  };
}
