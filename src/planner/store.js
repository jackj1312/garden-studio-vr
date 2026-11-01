/* Room planner change list. Every edit is saved at once as one change:
 *   server mode: POST /spec/changes?site=<site> (tools/https-serve.py; one file per change + a running list);
 *   device mode: when that server cannot be reached (e.g. a plain static server), changes stay in this browser's
 *                localStorage and are uploaded the next time the studio server answers.
 * Undo / redo work on unsent changes only (status active <-> undone). "Send to build" turns every active change into
 * one batch file (spec/changes/batch-<stamp>.json); sent changes stay applied and can no longer be undone.
 * The spec file itself is never written. */
import { uid } from "./util.js?v=p7";

const LS = site => `planner:${site}:changes:v1`;
const lsGet = k => { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch { return null; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch { return false; } };

export class ChangeStore {
  constructor(site) {
    this.site = site;
    this.changes = [];          // every change, in order, each with status active | undone | discarded | sent
    this.batches = [];
    this.mode = "connecting";   // server | device
    this.listeners = new Set();
    this.lastError = null;
  }
  on(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  emit(reason) { for (const fn of this.listeners) fn(reason); }
  url() { return `/spec/changes?site=${encodeURIComponent(this.site)}`; }

  async load() {
    const local = lsGet(LS(this.site)) || { changes: [] };
    try {
      const r = await fetch(this.url(), { cache: "no-store" });
      if (!r.ok) throw new Error(`studio server: ${r.status}`);
      const j = await r.json();
      if (!Array.isArray(j.changes)) throw new Error("studio server: bad reply");
      this.mode = "server";
      this.changes = j.changes;
      this.batches = j.batches || [];
      this.baseSpec = j.base_spec;
      /* changes made on this device while the server was away: upload them now, in order */
      const pending = (local.changes || []).filter(c => c.unsynced);
      for (const c of pending) {
        if (this.changes.some(x => x.id === c.id)) continue;
        const { unsynced, status, ...body } = c;
        await this.post({ action: "add", change: body });
        if (status !== "active") await this.post({ action: "status", ids: [c.id], status });
        this.changes.push({ ...body, status });
      }
      if (pending.length) { lsSet(LS(this.site), { changes: [] }); this.emit("uploaded:" + pending.length); }
    } catch (e) {
      this.lastError = String(e.message || e);
      this.mode = "device";
      this.changes = local.changes || [];
      this.batches = local.batches || [];
    }
    this.emit("load");
    return this;
  }
  saveLocal() { if (!lsSet(LS(this.site), { changes: this.changes, batches: this.batches })) this.lastError = "this browser would not store the changes"; }
  async post(body) {
    const r = await fetch(this.url(), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || `studio server: ${r.status}`);
    return j;
  }
  async safePost(body) {
    if (this.mode !== "server") { this.saveLocal(); return false; }
    try { await this.post(body); return true; }
    catch (e) {
      this.lastError = String(e.message || e);
      this.mode = "device";
      for (const c of this.changes) if (c.status !== "sent") c.unsynced = true;
      this.saveLocal();
      this.emit("offline");
      return false;
    }
  }

  get active() { return this.changes.filter(c => c.status === "active"); }
  get undone() { return this.changes.filter(c => c.status === "undone"); }
  get sent() { return this.changes.filter(c => c.status === "sent"); }
  get applied() { return this.changes.filter(c => c.status === "active" || c.status === "sent"); }
  canUndo() { return this.active.length > 0; }
  canRedo() { return this.undone.length > 0; }

  /* a new edit: saved immediately; anything that was undone can no longer be redone */
  async add(change) {
    const c = { id: uid("c"), at: new Date().toISOString(), site: this.site, ...change, status: "active" };
    const drop = this.undone.map(x => x.id);
    for (const x of this.changes) if (drop.includes(x.id)) x.status = "discarded";
    if (this.mode !== "server") c.unsynced = true;
    this.changes.push(c);
    this.emit("add");
    if (drop.length) await this.safePost({ action: "status", ids: drop, status: "discarded" });
    const { status, unsynced, ...body } = c;
    await this.safePost({ action: "add", change: body });
    if (this.mode !== "server") this.saveLocal();
    return c;
  }
  async undo() {
    const c = this.active.at(-1); if (!c) return null;
    c.status = "undone"; this.emit("undo");
    await this.safePost({ action: "status", ids: [c.id], status: "undone" });
    if (this.mode !== "server") this.saveLocal();
    return c;
  }
  async redo() {
    const u = this.undone; const c = u[0]; if (!c) return null;   // the earliest undone comes back first
    c.status = "active";
    /* keep the list in replay order: move it after the last active change */
    this.changes.splice(this.changes.indexOf(c), 1);
    const lastActive = this.changes.findLastIndex(x => x.status === "active" || x.status === "sent");
    this.changes.splice(lastActive + 1, 0, c);
    this.emit("redo");
    await this.safePost({ action: "status", ids: [c.id], status: "active" });
    if (this.mode !== "server") this.saveLocal();
    return c;
  }
  async send(note) {
    if (this.mode !== "server") throw new Error("The studio server is not reachable from this device, so the batch cannot be written. Your changes are safe on this device; open the planner from the studio address (https, port 8443) and press Send again.");
    const j = await this.post({ action: "send", note });
    const name = j.file.split("/").pop();
    for (const c of this.active) { c.status = "sent"; c.batch = name; }
    this.batches.push({ file: name, made: new Date().toISOString(), count: j.count });
    this.emit("send");
    return j;
  }
  /* pick up edits made on another device (phone / Quest) */
  async refresh() {
    if (this.mode !== "server") return false;
    try {
      const r = await fetch(this.url(), { cache: "no-store" });
      if (!r.ok) return false;
      const j = await r.json();
      const sig = a => a.map(c => c.id + c.status).join();
      if (sig(j.changes) === sig(this.changes)) return false;
      this.changes = j.changes; this.batches = j.batches || [];
      this.emit("refresh");
      return true;
    } catch { return false; }
  }
}
