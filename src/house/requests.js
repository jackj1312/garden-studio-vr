/* ------------------------------------------------------------------ *
 *  Change requests and inspection records: the notes people leave in
 *  the model for Jack (and an agent) to act on, and the inspector's
 *  pass / fail checklist. Both go to the server section of
 *  tools/https-serve.py (/house/requests, /house/inspections); on a
 *  plain static server (no endpoints) they are kept in this browser
 *  and can be downloaded. Formats: CONTRACT.md sections 10 and 11.
 *  Voice notes are recorded with MediaRecorder (works in the Quest
 *  browser) and transcribed on the Mac by the same hook as the garden's
 *  marks (tools/transcribe.py).
 * ------------------------------------------------------------------ */

const newId = () => `cr${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;

export function createRequests({ site, getVersion, mode, readOnly=false }) {
  const q = v => `site=${encodeURIComponent(site)}&version=${encodeURIComponent(v)}`;
  const localKey = v => `house-requests:${site}:${v}`;
  const cache = new Map();             // version -> [request]
  let online = null;                   // unknown until the first call

  const readLocal = v => { try { return JSON.parse(localStorage.getItem(localKey(v)) || "[]"); } catch (_) { return []; } };
  const writeLocal = (v, list) => { try { localStorage.setItem(localKey(v), JSON.stringify(list)); } catch (_) {} };

  async function list(v = getVersion()) {
    if(readOnly)return [];
    let server = [];
    try {
      const r = await fetch(`house/requests?${q(v)}`, { cache: "no-store" });
      if (r.ok && (r.headers.get("content-type") || "").includes("json")) { server = (await r.json()).requests || []; online = true; }
      else online = false;
    } catch (_) { online = false; }
    const ids = new Set(server.map(x => x.id));
    const all = [...server, ...readLocal(v).filter(x => !ids.has(x.id))];
    cache.set(v, all);
    return all;
  }

  /* {elements:[ids], point:[x,y,z], note, edits?, stage, author?} -> the saved request */
  async function submit(req) {
    if(readOnly)throw Error('Latest house preview is read-only');
    const v = getVersion();
    const full = { contract: 1, id: req.id || newId(), created: new Date().toISOString(), mode, version: v,
                   author: req.author || localStorage.getItem("house-author") || null, status: "open", ...req };
    let saved = false;
    try {
      const r = await fetch(`house/requests?${q(v)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(full) });
      saved = r.ok; online = r.ok;
    } catch (_) { online = false; }
    if (!saved) { const l = readLocal(v).filter(x => x.id !== full.id); l.push(full); writeLocal(v, l); }
    const c = cache.get(v) || [];
    cache.set(v, [...c.filter(x => x.id !== full.id), full]);
    return { request: full, saved: saved ? "server" : "this browser" };
  }

  async function uploadAudio(id, blob) {
    if(readOnly)throw Error('Latest house preview is read-only');
    const v = getVersion();
    try {
      const r = await fetch(`house/requests/audio?${q(v)}&id=${encodeURIComponent(id)}`,
        { method: "POST", headers: { "Content-Type": blob.type.split(";")[0] || "audio/webm" }, body: blob });
      if (r.ok) return (await r.json()).file;
    } catch (_) {}
    return null;
  }

  function forElement(id, v = getVersion()) { return (cache.get(v) || []).filter(r => (r.elements || []).includes(id)); }
  function download(v = getVersion()) {
    if(readOnly)return;
    const blob = new Blob([JSON.stringify({ contract: 1, site, version: v, requests: cache.get(v) || readLocal(v) }, null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `${site}_${v}_change_requests.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  /* ---------- inspections: one checklist file per inspection point ---------- */
  const inspKey = (v, stage) => `house-inspection:${site}:${v}:${stage}`;
  async function loadInspection(stage, v = getVersion()) {
    if(readOnly)return {checks:{}};
    try {
      const r = await fetch(`house/inspections?${q(v)}&stage=${encodeURIComponent(stage)}`, { cache: "no-store" });
      if (r.ok && (r.headers.get("content-type") || "").includes("json")) return await r.json();
    } catch (_) {}
    try { return JSON.parse(localStorage.getItem(inspKey(v, stage)) || "null") || { checks: {} }; } catch (_) { return { checks: {} }; }
  }
  async function saveInspection(stage, data, v = getVersion()) {
    if(readOnly)throw Error('Latest house preview is read-only');
    const body = { contract: 1, ...data, inspector: localStorage.getItem("house-author") || null };
    try { localStorage.setItem(inspKey(v, stage), JSON.stringify(body)); } catch (_) {}
    try {
      const r = await fetch(`house/inspections?${q(v)}&stage=${encodeURIComponent(stage)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      return r.ok ? "server" : "this browser";
    } catch (_) { return "this browser"; }
  }

  return { list, submit, uploadAudio, forElement, download, loadInspection, saveInspection, newId, get online() { return online; } };
}

/* hold-to-talk / press-to-toggle voice recorder */
export function createRecorder() {
  let rec = null, chunks = [], stream = null;
  return {
    get recording() { return !!rec; },
    async start() {
      if (rec) return;
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const type = ["audio/webm", "audio/mp4", "audio/ogg"].find(t => MediaRecorder.isTypeSupported?.(t)) || "";
      rec = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
      chunks = [];
      rec.ondataavailable = e => e.data.size && chunks.push(e.data);
      rec.start();
    },
    stop() {
      return new Promise(res => {
        if (!rec) return res(null);
        rec.onstop = () => {
          const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
          stream.getTracks().forEach(t => t.stop());
          rec = null; stream = null;
          res(blob.size ? blob : null);
        };
        rec.stop();
      });
    },
  };
}
