/* ------------------------------------------------------------------ *
 *  The regulations dataset: what each part must meet, for the REGS tab,
 *  the inspector's checklists and the builder's rule tags.
 *
 *  assets/sites/<site>/regs.json      the research dataset's rules
 *    (+ inspection_ids), its meta, the product liability wording and
 *    the inspection points with the DATASET stages their rules carry.
 *  assets/sites/<site>/regs_map.json  which rules attach to which
 *    parts, hand-curated and reviewable (tools/house/build_regs.py):
 *    entries {id, when, rules, why, prompt}. `when` tests what the part
 *    IS: type, group, category, storey, material, element / label
 *    regex, room regex, near_boundary, low_glazing; "not_<key>" negates.
 *
 *  A rule with no verified_on, or a status saying UNVERIFIED, is a
 *  placeholder: always shown with that warning, its values never
 *  presented as real. (The fixture's regs.json is all placeholders.)
 * ------------------------------------------------------------------ */

/* used only when a site's regs.json has no inspection points of its own */
export const INSPECTION_POINTS = [
  { id: "commencement", name: "Commencement", dataset_stages: [2], description: "Notice given before work starts." },
  { id: "excavation", name: "Excavation", dataset_stages: [3], description: "Trenches open, before any concrete." },
  { id: "foundations", name: "Foundations", dataset_stages: [4], description: "Trench fill poured to the right level." },
  { id: "drains", name: "Drains", dataset_stages: [4], description: "Drains laid and tested before they are covered." },
  { id: "oversite_dpc", name: "Oversite and DPC", dataset_stages: [5, 6], description: "Hardcore, DPM, insulation and the DPC." },
  { id: "structure_preplaster", name: "Structure / pre-plaster", dataset_stages: [7, 8, 9, 10, 11], description: "Before they are covered." },
  { id: "completion", name: "Completion", dataset_stages: [12], description: "Final inspection and certificates." },
];

export const isVerified = r => !!r?.verified_on && !/UNVERIFIED/i.test(String(r.status || ""));
export const extensionText = r => r.applies_to_extension === true ? "yes" : r.applies_to_extension === false ? "no"
  : `conditional${r.applies_to?.conditions ? ` — ${r.applies_to.conditions}` : ""}`;

const asList = v => Array.isArray(v) ? v : v == null ? [] : [v];

export async function loadRegs(base) {
  const get = async f => { try { const r = await fetch(base + f, { cache: "no-cache" }); return r.ok ? await r.json() : null; } catch (_) { return null; } };
  const [data, map] = await Promise.all([get("regs.json"), get("regs_map.json")]);
  const rules = data?.rules || [];
  const byId = new Map(rules.map(r => [r.id, r]));
  const meta = data?.meta || {};
  const points = (data?.inspection_points?.length ? data.inspection_points : INSPECTION_POINTS)
    .map(p => ({ ...p, dataset_stages: p.dataset_stages || p.stages || [] }));
  for (const r of rules) {                               // older files: one inspection point string
    if (!r.inspection_ids) r.inspection_ids = asList(r.inspection_point).map(s => (String(s).match(/^(IP-[A-Z]+)/) || [])[1] || s);
  }
  const entries = map?.entries || [];
  const notApplicable = new Map((map?.not_applicable || []).map(x => [x.id, x.reason]));

  const rxCache = new Map();
  /* facts: {part, element, room (name), near_boundary (bool), low_glazing (bool)} */
  function test(key, want, f) {
    const p = f.part, el = f.element;
    const rx = v => rxCache.get(v) || rxCache.set(v, new RegExp(v, "i")).get(v);       // compiled once, not per part per entry
    switch (key) {
      case "type": return asList(want).includes(el?.type);
      case "group": return asList(want).includes(p?.group);
      case "category": return asList(want).includes(p?.category);
      case "storey": return asList(want).includes(p?.storey);
      case "material": return asList(want).includes(p?.materialName);
      case "element": return asList(want).some(v => rx(v).test(p?.element || ""));
      case "label": return asList(want).some(v => rx(v).test(p?.ud?.label || ""));
      case "room": return !!f.room && asList(want).some(v => rx(v).test(f.room));
      case "near_boundary": return f.near_boundary !== undefined && f.near_boundary === want;
      case "low_glazing": return f.low_glazing === want;
      default: return false;
    }
  }
  function matches(when, f) {
    for (const [k, v] of Object.entries(when || {})) {
      if (k.startsWith("not_")) { if (test(k.slice(4), v, f)) return false; }
      else if (!test(k, v, f)) return false;
    }
    return true;
  }

  /* the rules for a part, grouped by why they apply: [{entry, rules:[...]}]; room entries are left out (forRoom) */
  function forPart(part, element, facts = {}) {
    const f = { part, element, ...facts };
    const out = [];
    const own = (element?.regs || part?.ud?.regs || []).map(id => byId.get(id)).filter(Boolean);
    if (own.length) out.push({ entry: { id: "element", why: "named on this element" }, rules: own });
    for (const e of entries) {
      if (e.when?.room) continue;
      if (matches(e.when, f)) out.push({ entry: e, rules: e.rules.map(id => byId.get(id)).filter(Boolean) });
    }
    if (!entries.length) {                                // fixture format: applies_to is a list of group / type keys
      const keys = new Set([part?.group, element?.type, part && `category:${part.category}`, part?.element].filter(Boolean));
      const rs = rules.filter(r => asList(r.applies_to).some(k => typeof k === "string" && keys.has(k)));
      if (rs.length) out.push({ entry: { id: "applies_to", why: "the rule's applies_to" }, rules: rs });
    }
    return out;
  }
  const flat = groups => { const m = new Map(); for (const g of groups) for (const r of g.rules) m.set(r.id, r); return [...m.values()]; };
  function forRoom(room) {
    if (!room) return [];
    return entries.filter(e => e.when?.room && matches(e.when, { room }))
      .map(e => ({ entry: e, rules: e.rules.map(id => byId.get(id)).filter(Boolean) }));
  }
  const project = () => (map?.project || []).map(id => byId.get(id)).filter(Boolean);
  const forInspection = pid => rules.filter(r => r.inspection_ids.includes(pid) || r.inspection_point === pid);

  /* parameters -> a short readable value */
  function valueText(r) {
    const p = r.parameters;
    if (p == null || (typeof p === "object" && !Object.keys(p).length)) return "";
    const fmt = v => typeof v === "object" ? JSON.stringify(v).replace(/[{}"]/g, "").replace(/,/g, ", ").replace(/:/g, ": ") : String(v);
    const txt = typeof p === "string" ? p : Object.entries(p).map(([k, v]) => `${k.replace(/_/g, " ")} ${fmt(v)}`).join(" · ");
    return isVerified(r) ? txt : `UNVERIFIED placeholder — ${txt}`;
  }
  return { rules, byId, meta, points, forPart, flat, forRoom, project, forInspection, valueText, notApplicable,
           get mapped() { return entries.length > 0; } };
}
