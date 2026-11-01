/* ------------------------------------------------------------------ *
 *  The edit layer: a list of operations on top of the drawn design.
 *
 *  The drawn design (house_<v>_elements.json from the generator) is
 *  never changed. Edits are a diff, replayed in order:
 *    { op: "remove", id }                      take an element out
 *    { op: "set", id, params: {...} }          change some parameters
 *    { op: "add", element: {...} }             a new element (walls, fixtures, …; schema in CONTRACT.md)
 *    { op: "batch", label, ops: [...] }        several of the above as one undo step
 *  Restore = undo, or a "set" with removed:false. Undo / redo are a
 *  cursor over the list. Saved per site + version in localStorage and
 *  as a downloadable JSON file ({site, version, base, edits}) that can
 *  be loaded back; a server endpoint can replace the file later
 *  without changing this format.
 * ------------------------------------------------------------------ */

const clone = o => JSON.parse(JSON.stringify(o));

export function createEditor({ site, version, elements, onChange }) {
  const base = new Map((elements?.elements || []).map(e => [e.id, e]));
  let edits = [], cursor = 0;                 // edits[0..cursor) are applied
  const key = `house-edits:${site}:${version}`;

  /* The table after the edits, built once per change and shared: READ-ONLY for every caller. It used to be
     rebuilt (every element deep-cloned) on each call, and get(id) called it: 5.6 ms a call on a laptop for the
     approved scheme's 1660 elements, and the board's boundary scan made one call per part (2005) the first time a
     part was shown: 6.1 s on a laptop, far longer on the Quest — the headset freeze (CORRECTIONS-LOG, round 6).
     Now only the elements an edit touches are copied (copy on write). */
  let cache = null;
  function current() {
    if (cache) return cache;
    const t = new Map(base), own = new Set();
    const mine = id => { if (!own.has(id) && t.has(id)) { t.set(id, clone(t.get(id))); own.add(id); } return t.get(id); };
    const flat = [];
    for (const e of edits.slice(0, cursor)) { if (e.op === "batch") flat.push(...e.ops); else flat.push(e); }
    for (const e of flat) {
      if (e.op === "remove") { const el = mine(e.id); if (el) el.removed = true; }
      else if (e.op === "restore") { const el = mine(e.id); if (el) el.removed = false; }
      else if (e.op === "set") { const el = mine(e.id); if (el) Object.assign(el.params, clone(e.params)); }
      else if (e.op === "add") {
        t.set(e.element.id, clone(e.element)); own.add(e.element.id);
        const host = e.element.type === "opening" && mine(e.element.params.host);
        if (host) (host.openings = host.openings || []).push(e.element.id);
      }
    }
    // an opening, lintel or fixture goes with its wall
    for (const el of t.values()) {
      if (el.type === "opening" && t.get(el.params.host)?.removed && !el.removed) mine(el.id).removed = true;
    }
    for (const el of t.values()) {
      if (el.params?.opening && t.get(el.params.opening)?.removed && !el.removed) mine(el.id).removed = true;
    }
    return (cache = t);
  }
  const changed = () => { cache = null; };

  /* ids an edit touches, for the model to rebuild */
  const touches = e => e.op === "batch" ? e.ops.flatMap(touches)
    : e.op === "add" ? [e.element.id, e.element.params?.host].filter(Boolean) : [e.id];

  function persist() {
    try { localStorage.setItem(key, JSON.stringify({ edits, cursor })); } catch (_) {}
  }
  function push(e) {
    edits = edits.slice(0, cursor);
    edits.push({ ...e, at: new Date().toISOString() });
    cursor = edits.length;
    persist(); changed();
    onChange?.(current(), touches(e), e);
  }
  function load(saved) {
    const before = current();
    edits = saved.edits || []; cursor = Math.min(saved.cursor ?? edits.length, edits.length);
    persist(); changed();
    const ids = new Set([...before.keys(), ...current().keys()]);
    onChange?.(current(), [...ids], null);
  }

  return {
    get edits() { return edits.slice(0, cursor); },
    get canUndo() { return cursor > 0; },
    get canRedo() { return cursor < edits.length; },
    current,
    get(id) { return current().get(id); },
    remove(id) { push({ op: "remove", id }); },
    restore(id) { push({ op: "restore", id }); },
    set(id, params) { push({ op: "set", id, params }); },
    add(element) { push({ op: "add", element }); },
    /* several operations as ONE undo step (a wall move drags its neighbours) */
    batch(ops, label) { if (ops.length) push({ op: "batch", label, ops }); },
    undo() { if (!cursor) return; cursor--; persist(); changed(); onChange?.(current(), touches(edits[cursor]), null); },
    redo() { if (cursor >= edits.length) return; cursor++; persist(); changed(); onChange?.(current(), touches(edits[cursor - 1]), null); },
    /* restore what was saved in this browser */
    resume() {
      try {
        const s = JSON.parse(localStorage.getItem(key) || "null");
        if (s && s.edits?.length) { load(s); return s.edits.length; }
      } catch (_) {}
      return 0;
    },
    toJSON() { return { contract: 1, site, version, saved: new Date().toISOString(), edits: edits.slice(0, cursor) }; },
    load,
    reset() { load({ edits: [], cursor: 0 }); },
  };
}
