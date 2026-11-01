import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  The board: plans, spec, regs, build notes and change requests for
 *  whatever you are looking at, held in your left hand like a clip
 *  board (VR) or docked as a side panel (desktop / phone). One content
 *  model drives both:
 *
 *    { title, subtitle, accent, tabs: [{id, label}], active,
 *      blocks: [ {type:"text", text, dim, bold, size, status}
 *              | {type:"buttons", items:[{id, label, press, on, danger}]}
 *              | {type:"image", draw(ctx, w, h), height, caption} ],
 *      strip: { title, frac, buttons:[…] } }            (VR only)
 *
 *  Headset readability: a 1024 x 1440 canvas on a 0.24 x 0.34 m board
 *  held ~40 cm away is close to the Quest 3's native pixel density;
 *  body text is never under 30 px on the canvas (~14 px equivalent).
 * ------------------------------------------------------------------ */

/* split text into lines that fit maxW on canvas context c. Cached: the board lays out every block of every page
   on each redraw, and a Regs tab is ~2,000 words of measureText */
const wrapCache = new Map(), wordW = new Map();
/* a word's width in the current font, measured once (measureText costs ~40 us a call in a browser tab, more on
   the Quest; a line is the sum of its words and spaces) */
const widthOf = (c, w) => { const k = `${c.font}|${w}`; let v = wordW.get(k); if (v === undefined) { v = c.measureText(w).width; if (wordW.size > 20000) wordW.clear(); wordW.set(k, v); } return v; };
export const wrapped = (c, text, maxW, maxLines = 99) => wrapCache.has(`${c.font}|${maxW}|${maxLines}|${text}`);
export function wrap(c, text, maxW, maxLines = 99) {
  const key = `${c.font}|${maxW}|${maxLines}|${text}`;
  const hit = wrapCache.get(key);
  if (hit) return hit;
  const words = String(text || "").split(/\s+/), lines = [], sp = widthOf(c, " ");
  let line = "", lw = 0;
  for (const w of words) {
    const ww = widthOf(c, w);
    if (line && lw + sp + ww > maxW) { lines.push(line); line = w; lw = ww; }
    else { line = line ? line + " " + w : w; lw = line === w ? ww : lw + sp + ww; }
    if (lines.length >= maxLines) break;
  }
  if (line && lines.length < maxLines) lines.push(line);
  if (lines.length === maxLines && c.measureText(lines[maxLines - 1]).width > maxW - 20)
    lines[maxLines - 1] = lines[maxLines - 1].replace(/\s*\S+$/, "") + "…";
  if (wrapCache.size > 4000) wrapCache.clear();
  wrapCache.set(key, lines);
  return lines;
}

/* nothing on the headset board is drawn smaller than this (canvas px on a 1024-wide, 0.24 m board) */
const MIN_PX = 30;

const STATUS = { pass: "#79c48a", fail: "#ef6b5e", warn: "#e2b04f", unknown: "#e2b04f", unverified: "#ef9a5e" };

function rr(c, x, y, w, h, r) {
  c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
}
const labelOf = it => String(typeof it.label === "function" ? it.label() : it.label);

/* a canvas texture for a board: no mipmaps (the board is read at about its own pixel density, and a mip chain
   would be rebuilt on every upload) */
function boardTexture(cv) {
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.generateMipmaps = false;
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  return tex;
}

/* ------------------------------------------------------------------ *
 *  The VR board. Round 6 (the headset freeze): the canvas is redrawn
 *  ONLY when what it shows changes (a key of its text, labels and
 *  states), never because the laser moved: the cursor dot and the
 *  hover box are small meshes on top of it. The stage strip (which
 *  moves every frame while the build plays) is its own small canvas,
 *  redrawn at most 10 times a second. Text wrapping is cached.
 * ------------------------------------------------------------------ */
export function createVRBoard() {
  const W = 1024, H = 1440, SH = 240;                    // the strip: the bottom 240 px of the board
  const BW = 0.24, BH = BW * H / W;
  const cv = document.createElement("canvas");
  cv.width = W; cv.height = H;
  const c = cv.getContext("2d");
  const tex = boardTexture(cv);
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(BW, BH),
    new THREE.MeshBasicMaterial({ map: tex, transparent: true, toneMapped: false, depthTest: false, opacity: 0 }));
  mesh.renderOrder = 900;
  /* held in the left hand: in front of the controller, tipped towards the face when the wrist turns up */
  mesh.position.set(0.03, 0.1, -0.12);
  mesh.rotation.set(-Math.PI / 3.2, 0, 0);
  mesh.visible = false;
  /* the strip */
  const scv = document.createElement("canvas");
  scv.width = W; scv.height = SH;
  const sc = scv.getContext("2d");
  const stex = boardTexture(scv);
  const strip = new THREE.Mesh(new THREE.PlaneGeometry(BW, BW * SH / W),
    new THREE.MeshBasicMaterial({ map: stex, transparent: true, toneMapped: false, depthTest: false, opacity: 0 }));
  strip.position.set(0, -BH / 2 + BW * SH / W / 2, 0.0004);
  strip.renderOrder = 901;
  mesh.add(strip);
  /* the laser's cursor and the box round what it would press: meshes, so pointing never redraws the canvas */
  const dot = new THREE.Mesh(new THREE.CircleGeometry(0.0035, 20), new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, toneMapped: false, transparent: true }));
  dot.renderOrder = 903; dot.visible = false; mesh.add(dot);
  const hover = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.16, depthTest: false, toneMapped: false }));
  hover.renderOrder = 902; hover.visible = false; mesh.add(hover);
  const toLocal = (x, y) => [(x / W - 0.5) * BW, (0.5 - y / H) * BH];

  let hits = [], stripHits = [], content = null, page = 0, pages = 1;
  const pending = [];                                    // drawn canvases whose upload is due on the NEXT frame
  let bodyKey = "", drawnKey = null, stripKey = "", stripDrawn = null, lastBody = -1e9, lastStrip = -1e9;
  const stats = { bodyDraws: 0, stripDraws: 0, lastBodyMs: 0, lastStripMs: 0, maxBodyMs: 0 };

  /* what the body shows, as a string: redraw only when it changes */
  function keyOf(ct) {
    if (!ct) return "none";
    const parts = [ct.title, ct.subtitle, ct.accent, ct.active, (ct.tabs || []).map(t => t.id).join(","), page];
    for (const b of ct.blocks || []) {
      if (b.type === "text") parts.push(`t${b.size || ""}${b.bold ? "b" : ""}${b.dim ? "d" : ""}${b.status || ""}${b.max || ""}:${b.text}`);
      else if (b.type === "buttons") parts.push("B" + b.items.map(it => `${labelOf(it)}${it.on?.() ? "*" : ""}`).join("|"));
      else if (b.type === "image") parts.push(`I${b.key || b.caption || ""}`);
    }
    return parts.join("\u0001");
  }
  const stripKeyOf = s => s ? `${s.title}|${s.frac.toFixed(3)}|${s.buttons.map(it => `${labelOf(it)}${it.on?.() ? "*" : ""}`).join("|")}` : "";

  /* wrap the blocks' text (cached) and ready their pictures, stopping after `budget` ms; true when all is ready */
  function prepare(budget) {
    if (!content) return true;
    const t0 = performance.now();
    for (const b of content.blocks || []) {
      if (b.type === "text") {
        const sz = Math.max(MIN_PX, b.size || 32);
        c.font = `${b.bold ? "600 " : ""}${sz}px system-ui, sans-serif`;
        if (wrapped(c, b.text, W - 100, b.max || 8)) continue;
        wrap(c, b.text, W - 100, b.max || 8);
      } else if (b.type === "image" && b.prepare && !b.prepare(W - 100, b.height || 420)) return false;
      if (performance.now() - t0 > budget) return false;
    }
    return true;
  }

  function drawBody() {
    const t0 = performance.now();
    c.clearRect(0, 0, W, H);
    c.fillStyle = "rgba(14,16,15,0.96)"; rr(c, 3, 3, W - 6, H - 6, 30); c.fill();
    c.strokeStyle = "rgba(255,255,255,0.18)"; c.lineWidth = 3; c.stroke();
    hits = [];
    drawnKey = bodyKey;
    if (!content) { pending.push(tex); return; }
    const accent = content.accent || "#f2d36b";
    c.fillStyle = accent; rr(c, 3, 3, 16, H - 6, 8); c.fill();
    // minimise (the Y button does the same)
    c.fillStyle = "rgba(255,255,255,0.1)"; rr(c, W - 118, 18, 96, 70, 16); c.fill();
    c.fillStyle = "#f0f1ea"; c.fillRect(W - 92, 52, 44, 7);
    hits.push({ x: W - 118, y: 18, w: 96, h: 70, minimise: true });
    // title
    c.fillStyle = "#f6f5ef"; c.font = "700 46px system-ui, sans-serif";
    let y = 70;
    for (const l of wrap(c, content.title || "", W - 190, 2)) { c.fillText(l, 44, y); y += 54; }
    if (content.subtitle) { c.fillStyle = "#b9bdb1"; c.font = "32px system-ui, sans-serif"; c.fillText(content.subtitle.slice(0, 52), 44, y); y += 44; }
    // tabs
    const tabs = content.tabs || [];
    const tw = (W - 70) / Math.max(1, tabs.length);
    y += 6;
    tabs.forEach((t, i) => {
      const x = 40 + i * tw, on = t.id === content.active;
      c.fillStyle = on ? accent : "rgba(255,255,255,0.08)";
      rr(c, x, y, tw - 8, 70, 14); c.fill();
      c.fillStyle = on ? "#111" : "#e8e9e2"; c.font = "700 28px system-ui, sans-serif"; c.textAlign = "center";
      c.fillText(t.label.toUpperCase(), x + (tw - 8) / 2, y + 46);
      c.textAlign = "left";
      hits.push({ x, y, w: tw - 8, h: 70, tab: t.id });
    });
    y += 92;
    // body, paged
    const top = y, bottom = H - SH - 20;
    const blocks = content.blocks || [];
    const layout = [];          // [{block, page, y0}]
    let py = top, pg = 0;
    const heightOf = b => {
      if (b.type === "text") { const sz = Math.max(MIN_PX, b.size || 32); c.font = `${b.bold ? "600 " : ""}${sz}px system-ui, sans-serif`; return wrap(c, b.text, W - 100, b.max || 8).length * (sz + 10) + 10; }
      if (b.type === "buttons") return Math.ceil(b.items.length / (b.cols || 3)) * 92;
      if (b.type === "image") return (b.height || 420) + (b.caption ? 44 : 0) + 10;
      return 0;
    };
    for (const b of blocks) {
      const h = heightOf(b);
      if (py + h > bottom && py > top) { pg++; py = top; }
      layout.push({ b, page: pg, y0: py });
      py += h;
    }
    pages = pg + 1;
    page = Math.min(page, pages - 1);
    for (const { b, page: p, y0 } of layout) {
      if (p !== page) continue;
      let yy = y0;
      if (b.type === "text") {
        const size = Math.max(MIN_PX, b.size || 32);
        c.font = `${b.bold ? "600 " : ""}${size}px system-ui, sans-serif`;
        c.fillStyle = b.status ? STATUS[b.status] || "#e8e9e2" : b.dim ? "#aeb2a7" : "#ecede6";
        for (const l of wrap(c, b.text, W - 100, b.max || 8)) { c.fillText(l, 50, yy + size); yy += size + 10; }
      } else if (b.type === "buttons") {
        const cols = b.cols || 3, bw = (W - 100 - (cols - 1) * 14) / cols;
        b.items.forEach((it, i) => {
          const x = 50 + (i % cols) * (bw + 14), by = yy + Math.floor(i / cols) * 92;
          const on = it.on?.();
          c.fillStyle = on ? accent : it.danger ? "rgba(216,52,43,0.42)" : "rgba(255,255,255,0.1)";
          rr(c, x, by, bw, 78, 16); c.fill();
          c.fillStyle = on ? "#111" : "#f0f1ea"; c.font = "600 30px system-ui, sans-serif"; c.textAlign = "center";
          c.fillText(labelOf(it).slice(0, 20), x + bw / 2, by + 50);
          c.textAlign = "left";
          hits.push({ x, y: by, w: bw, h: 78, button: it });
        });
      } else if (b.type === "image") {
        const ih = b.height || 420;
        c.save(); c.translate(50, yy); rr(c, 0, 0, W - 100, ih, 12); c.clip();
        c.fillStyle = "#f4f2ea"; c.fillRect(0, 0, W - 100, ih);
        try { b.draw(c, W - 100, ih); } catch (err) { console.warn(err); }
        c.restore();
        if (b.caption) { c.fillStyle = "#aeb2a7"; c.font = `${MIN_PX}px system-ui, sans-serif`; c.fillText(b.caption.slice(0, 60), 50, yy + ih + 36); }
      }
    }
    if (pages > 1) {
      c.fillStyle = "rgba(255,255,255,0.1)"; rr(c, W - 290, bottom - 64, 240, 60, 14); c.fill();
      c.fillStyle = "#f0f1ea"; c.font = "600 28px system-ui, sans-serif"; c.textAlign = "center";
      c.fillText(`more ▸ ${page + 1}/${pages}`, W - 170, bottom - 24); c.textAlign = "left";
      hits.push({ x: W - 290, y: bottom - 64, w: 240, h: 60, page: true });
    }
    pending.push(tex);
    const ms = performance.now() - t0;
    stats.bodyDraws++; stats.lastBodyMs = ms; stats.maxBodyMs = Math.max(stats.maxBodyMs, ms);
  }

  // strip: stage and play, always there
  function drawStrip() {
    const t0 = performance.now();
    stripDrawn = stripKey;
    sc.clearRect(0, 0, W, SH);
    stripHits = [];
    const s = content?.strip;
    if (s) {
      const sy = 50, oy = H - SH;                            // strip canvas y -> board canvas y
      sc.fillStyle = "rgba(14,16,15,0.96)"; rr(sc, 3, 0, W - 6, SH - 3, 26); sc.fill();
      sc.fillStyle = "rgba(255,255,255,0.06)"; rr(sc, 30, sy - 40, W - 60, 216, 20); sc.fill();
      sc.fillStyle = "#ecede6"; sc.font = "600 32px system-ui, sans-serif"; sc.fillText(s.title.slice(0, 46), 50, sy);
      const SX = 50, SW = W - 100;
      sc.fillStyle = "rgba(255,255,255,0.14)"; rr(sc, SX, sy + 22, SW, 16, 8); sc.fill();
      sc.fillStyle = "#7aa86a"; rr(sc, SX, sy + 22, Math.max(16, SW * s.frac), 16, 8); sc.fill();
      sc.beginPath(); sc.arc(SX + SW * s.frac, sy + 30, 22, 0, Math.PI * 2); sc.fillStyle = "#f0f1ea"; sc.fill();
      stripHits.push({ x: SX, y: oy + sy, w: SW, h: 60, scrub: { x: SX, w: SW } });
      const n = s.buttons.length, bw = (W - 100 - (n - 1) * 14) / n;
      s.buttons.forEach((it, i) => {
        const x = 50 + i * (bw + 14), by = sy + 70, on = it.on?.();
        sc.fillStyle = on ? "#7aa86a" : "rgba(255,255,255,0.1)"; rr(sc, x, by, bw, 74, 16); sc.fill();
        sc.fillStyle = on ? "#111" : "#f0f1ea"; sc.font = "600 30px system-ui, sans-serif"; sc.textAlign = "center";
        sc.fillText(labelOf(it), x + bw / 2, by + 48); sc.textAlign = "left";
        stripHits.push({ x, y: oy + by, w: bw, h: 74, button: it });
      });
    }
    pending.push(stex);
    stats.stripDraws++; stats.lastStripMs = performance.now() - t0;
  }

  return {
    mesh, strip, stats,
    set(next) { content = next; bodyKey = keyOf(next); stripKey = stripKeyOf(next?.strip); },
    get content() { return content; },
    redraw() { drawnKey = null; stripDrawn = null; },
    /* one step of work a frame, at most: upload what the last frame drew, or draw what changed. Hidden, the board
       is still kept current (at most every 400 ms) and its texture uploaded with `upload` (renderer.initTexture),
       so raising the board finds it drawn AND on the GPU: opening it costs nothing (round 6: the freeze).
       Returns "upload", "draw" or false. */
    update(now = performance.now(), visible = mesh.visible, upload = null) {
      strip.material.opacity = mesh.material.opacity;
      if (pending.length) { const t = pending.shift(); t.needsUpdate = true; if (!visible && upload) upload(t); return "upload"; }
      if (bodyKey !== drawnKey && (visible || now - lastBody > 400)) {
        if (!prepare(4)) return "prepare";                  // the text is wrapped a few ms a frame before it is drawn
        drawBody(); lastBody = now; return "draw";
      }
      if (stripKey !== stripDrawn && now - lastStrip > (visible ? 100 : 400)) { drawStrip(); lastStrip = now; return "draw"; }
      return false;
    },
    textures: [tex, stex],
    get pending() { return bodyKey !== drawnKey || stripKey !== stripDrawn; },
    /* the laser on the board: uv in canvas space (y down), or null */
    setCursor(uv) {
      dot.visible = !!uv;
      if (!uv) { hover.visible = false; return; }
      const [x, y] = toLocal(uv.x * W, uv.y * H);
      dot.position.set(x, y, 0.0008);
      const h = this.hit(uv);
      hover.visible = !!h && !h.scrub;
      if (hover.visible) {
        const [cx, cy] = toLocal(h.x + h.w / 2, h.y + h.h / 2);
        hover.position.set(cx, cy, 0.0006);
        hover.scale.set(h.w / W * BW, h.h / H * BH, 1);
      }
    },
    nextPage() { page = (page + 1) % pages; bodyKey = keyOf(content); },
    resetPage() { if (page) { page = 0; bodyKey = keyOf(content); } },
    /* uv in canvas space, y down */
    hit(uv) {
      const x = uv.x * W, y = uv.y * H;
      for (const h of y >= H - SH ? stripHits : hits) if (x >= h.x && x <= h.x + h.w && y >= h.y && y <= h.y + h.h) {
        if (h.scrub) return { ...h, scrub: Math.min(1, Math.max(0, (x - h.scrub.x) / h.scrub.w)) };
        return h;
      }
      return null;
    },
    draw() { drawBody(); drawStrip(); for (const t of pending.splice(0)) t.needsUpdate = true; },     // for tests: force a draw while hidden
    canvas: cv, stripCanvas: scv,
  };
}

/* minimised, the board is a small tab on the left wrist: point the right laser at it and pull the trigger */
export function createBoardTab() {
  const cv = document.createElement("canvas");
  cv.width = 256; cv.height = 104;
  const c = cv.getContext("2d");
  c.fillStyle = "rgba(14,16,15,0.92)"; rr(c, 4, 4, 248, 96, 22); c.fill();
  c.strokeStyle = "#f2d36b"; c.lineWidth = 5; c.stroke();
  c.fillStyle = "#f6f5ef"; c.font = "700 44px system-ui, sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
  c.fillText("Board ▴", 128, 54);
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(0.075, 0.075 * 104 / 256),
    new THREE.MeshBasicMaterial({ map: boardTexture(cv), transparent: true, toneMapped: false, depthTest: false, side: THREE.DoubleSide }));
  mesh.renderOrder = 905;                                // two-sided: the laser finds it however the wrist is turned
  /* on the back of the left wrist, facing up and back towards you */
  mesh.position.set(0, 0.035, 0.07);
  mesh.rotation.set(-Math.PI / 2.6, 0, 0);
  mesh.visible = false;
  return mesh;
}

/* the same content as a DOM side panel */
export function renderBoardDOM(root, content, onTab) {
  root.hidden = !content;
  if (!content) return;
  root.querySelector("h2").textContent = content.title || "";
  root.querySelector(".sub").textContent = content.subtitle || "";
  root.style.setProperty("--board-accent", content.accent || "#f2d36b");
  const tabs = root.querySelector(".tabs");
  tabs.textContent = "";
  for (const t of content.tabs || []) {
    const b = document.createElement("button");
    b.textContent = t.label; b.setAttribute("role", "tab");
    b.setAttribute("aria-selected", String(t.id === content.active));
    b.addEventListener("click", () => onTab(t.id));
    tabs.appendChild(b);
  }
  const body = root.querySelector(".body");
  body.textContent = "";
  for (const b of content.blocks || []) {
    if (b.type === "text") {
      const p = document.createElement("p");
      p.textContent = b.text;
      if (b.dim) p.classList.add("dim");
      if (b.bold) p.classList.add("b");
      if (b.status) p.dataset.status = b.status;
      body.appendChild(p);
    } else if (b.type === "buttons") {
      const g = document.createElement("div");
      g.className = "btns";
      for (const it of b.items) {
        const bt = document.createElement("button");
        bt.textContent = typeof it.label === "function" ? it.label() : it.label;
        if (it.on?.()) bt.setAttribute("aria-pressed", "true");
        if (it.danger) bt.classList.add("danger");
        bt.addEventListener("click", () => it.press());
        g.appendChild(bt);
      }
      body.appendChild(g);
    } else if (b.type === "image") {
      const cv = document.createElement("canvas");
      const w = 640, h = Math.round(640 * (b.height || 420) / 924);
      cv.width = w; cv.height = h;
      const ctx = cv.getContext("2d");
      ctx.fillStyle = "#f4f2ea"; ctx.fillRect(0, 0, w, h);
      try { b.draw(ctx, w, h); } catch (err) { console.warn(err); }
      body.appendChild(cv);
      if (b.caption) { const p = document.createElement("p"); p.className = "dim"; p.textContent = b.caption; body.appendChild(p); }
    } else if (b.type === "html") {
      body.appendChild(b.node);
    }
  }
}

/* a card floating in front of you: the first-minute how-to, and loading progress */
export function createCard() {
  const W = 1024, H = 640;
  const cv = document.createElement("canvas");
  cv.width = W; cv.height = H;
  const c = cv.getContext("2d");
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(0.8, 0.5),
    new THREE.MeshBasicMaterial({ map: tex, transparent: true, toneMapped: false, depthTest: false }));
  mesh.renderOrder = 990;
  mesh.visible = false;
  return {
    mesh,
    show(title, lines, frac = null) {
      c.clearRect(0, 0, W, H);
      c.fillStyle = "rgba(14,16,15,0.95)"; rr(c, 4, 4, W - 8, H - 8, 30); c.fill();
      c.fillStyle = "#f6f5ef"; c.font = "700 50px system-ui, sans-serif"; c.fillText(title, 50, 84);
      let y = 150;
      c.font = "36px system-ui, sans-serif"; c.fillStyle = "#e6e7e0";
      for (const ln of lines) for (const l of wrap(c, ln, W - 100, 3)) { if (y > H - 60) break; c.fillText(l, 50, y); y += 50; }
      if (frac !== null) {
        c.fillStyle = "rgba(255,255,255,0.15)"; rr(c, 50, H - 80, W - 100, 22, 11); c.fill();
        c.fillStyle = "#7aa86a"; rr(c, 50, H - 80, Math.max(22, (W - 100) * frac), 22, 11); c.fill();
      }
      tex.needsUpdate = true;
      mesh.visible = true;
    },
    hide() { mesh.visible = false; },
  };
}
