import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  The frame log: what the headset really does, measured on it.
 *
 *  Every frame: its interval (rAF to rAF, which in the headset is the
 *  compositor's pace), the CPU time of our own work, and what was going
 *  on (board drawn, stage moving, a version loading, doors swinging).
 *  A frame longer than 50 ms is logged with those tags.
 *  The HUD (right stick click in the headset, H on a keyboard, or the
 *  Tools tab) shows fps, the worst frame, draw calls, triangles and
 *  textures from renderer.info, redrawn twice a second.
 *  Every 10 s a summary is POSTed to /house/perf (tools/https-serve.py
 *  appends it to renders/house-build/perf/<site>-<date>.jsonl), so the
 *  Quest's numbers can be read on the Mac. A plain static server has no
 *  such endpoint: after three failures it stops trying.
 * ------------------------------------------------------------------ */

const LONG_MS = 50;

export function createPerf({ renderer, site, scene, info, inXR = () => renderer.xr.isPresenting, post = true }) {
  const frames = [];                          // intervals since the last summary (ms)
  const works = [];                           // our CPU time per frame (ms)
  let longFrames = [], last = 0, fails = 0, lastPost = performance.now(), sec = { n: 0, worst: 0, t0: performance.now() };
  let fps = 0, worst1s = 0, worst10s = 0, tags = new Set();
  const notes = [];                           // one-off events (version loaded in N ms, BVH N ms)

  /* the HUD: a small canvas in the top left of the view (headset) or a DOM box (screen) */
  const cv = document.createElement("canvas");
  cv.width = 720; cv.height = 196;
  const c = cv.getContext("2d");
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace; tex.generateMipmaps = false; tex.minFilter = THREE.LinearFilter;
  const hud = new THREE.Mesh(new THREE.PlaneGeometry(0.26, 0.26 * 196 / 720),
    new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthTest: false, toneMapped: false }));
  hud.position.set(-0.2, 0.15, -0.55);
  hud.renderOrder = 997; hud.visible = false;
  const dom = document.createElement("pre");
  dom.id = "perfHud";
  dom.hidden = true;
  document.body.appendChild(dom);
  let on = false, lastHud = 0;

  function texMB() {
    /* the GPU bytes of every texture the renderer has uploaded is not exposed; estimate it from the images of the
       textures reachable from the scene's materials (RGBA 4 bytes, +1/3 for mips) */
    const seen = new Set();
    let bytes = 0;
    const add = t => {
      if (!t || seen.has(t)) return;
      seen.add(t);
      const img = t.image, w = img?.width || img?.videoWidth || 0, h = img?.height || img?.videoHeight || 0;
      bytes += w * h * 4 * (t.generateMipmaps === false ? 1 : 1.33) * (img?.depth || 1);
    };
    scene.traverse(o => {
      if (!o.material) return;
      for (const m of [].concat(o.material)) for (const k of ["map", "normalMap", "aoMap", "roughnessMap", "metalnessMap", "alphaMap", "emissiveMap"]) add(m[k]);
    });
    add(scene.environment);
    return { textures_sampled: seen.size, tex_mb: Math.round(bytes / 1e5) / 10 };
  }

  function drawHud(i) {
    const r = renderer.info;
    const lines = [`${fps.toFixed(0)} fps · worst ${worst1s.toFixed(0)} ms (10 s: ${worst10s.toFixed(0)})`,
      `calls ${r.render.calls} · tris ${(r.render.triangles / 1000).toFixed(0)}k`,
      `textures ${r.memory.textures} · geometries ${r.memory.geometries}`,
      `${i.version || ""} · stage ${i.stage ?? ""}${i.xr ? " · XR" : ""}${i.board ? ` · board ${i.board}` : ""}`];
    c.clearRect(0, 0, 720, 196);
    c.fillStyle = "rgba(10,12,11,0.82)"; c.beginPath(); c.roundRect(2, 2, 716, 192, 16); c.fill();
    c.font = "600 30px ui-monospace, Menlo, monospace"; c.fillStyle = fps < 60 ? "#ef9a5e" : "#a9e0b4";
    c.fillText(lines[0], 18, 44);
    c.font = "26px ui-monospace, Menlo, monospace"; c.fillStyle = "#e8e9e2";
    lines.slice(1).forEach((l, i) => c.fillText(l, 18, 86 + i * 38));
    tex.needsUpdate = true;
    dom.textContent = lines.join("\n");
  }

  function summary(ctx) {
    const sorted = frames.slice().sort((a, b) => a - b), q = f => sorted.length ? +sorted[Math.min(sorted.length - 1, Math.floor(f * sorted.length))].toFixed(1) : null;
    const w = works.slice().sort((a, b) => a - b), wq = f => w.length ? +w[Math.min(w.length - 1, Math.floor(f * w.length))].toFixed(2) : null;
    const r = renderer.info;
    const mem = performance.memory ? { js_heap_mb: Math.round(performance.memory.usedJSHeapSize / 1e6), js_limit_mb: Math.round(performance.memory.jsHeapSizeLimit / 1e6) } : {};
    return {
      t: new Date().toISOString(), ua: navigator.userAgent.slice(0, 160), ...ctx,
      frames: frames.length, fps: frames.length ? +(1000 * frames.length / frames.reduce((a, b) => a + b, 0)).toFixed(1) : null,
      frame_ms: { p50: q(0.5), p95: q(0.95), p99: q(0.99), worst: q(1) }, work_ms: { p50: wq(0.5), p95: wq(0.95), worst: wq(1) },
      calls: r.render.calls, triangles: r.render.triangles, textures: r.memory.textures, geometries: r.memory.geometries,
      programs: r.programs?.length ?? null, ...texMB(), ...mem,
      long_frames: longFrames.slice(0, 40), notes: notes.splice(0),
    };
  }
  async function send(ctx) {
    const body = summary(ctx);
    frames.length = 0; works.length = 0; longFrames = []; worst10s = 0;
    if (!post || fails >= 3) return body;
    try {
      const r = await fetch(`house/perf?site=${encodeURIComponent(site)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!r.ok) fails++; else fails = 0;
    } catch (_) { fails++; }
    return body;
  }

  return {
    hud, dom,
    get on() { return on; },
    toggle(v = !on) { on = v; hud.visible = on && inXR(); dom.hidden = !on || inXR(); lastHud = 0; },
    /* what is going on this frame (shown with a long frame) */
    tag(t) { tags.add(t); },
    note(n) { notes.push({ t: new Date().toISOString(), ...n }); if (notes.length > 50) notes.shift(); },
    /* once a frame, at the top of the loop: now = rAF time; work = the previous frame's own CPU ms */
    frame(now, work, sending) {
      if (last) {
        const dt = now - last;
        frames.push(dt); works.push(work);
        if (frames.length > 5000) { frames.shift(); works.shift(); }
        sec.n++; sec.worst = Math.max(sec.worst, dt); worst10s = Math.max(worst10s, dt);
        if (dt > LONG_MS && longFrames.length < 200) longFrames.push({ at: new Date().toISOString(), ms: +dt.toFixed(1), work_ms: +work.toFixed(1), during: [...tags] });
      }
      last = now; tags = new Set();
      if (now - sec.t0 >= 1000) { fps = sec.n * 1000 / (now - sec.t0); worst1s = sec.worst; sec = { n: 0, worst: 0, t0: now }; }
      if (on && now - lastHud > 500) { lastHud = now; hud.visible = inXR(); dom.hidden = inXR(); drawHud(info()); }
      if (sending && now - lastPost > 10000) { lastPost = now; send(info()); }
    },
    summary: () => summary(info()),
    send: () => send(info()),
  };
}
