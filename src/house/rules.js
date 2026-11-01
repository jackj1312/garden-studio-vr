/* ------------------------------------------------------------------ *
 *  Building Regulations checks: the hook the full rules engine plugs
 *  into. After any edit the viewer calls
 *
 *      checkRules(elements, ctx) -> [{ elementId, rule, clause, status, message }]
 *
 *  elements: the CURRENT element table (Map or array; removed ones
 *  carry removed: true). ctx (optional) gives geometry queries:
 *      ctx.clearanceAbove(x, y, z) -> metres to the underside of the
 *      first solid thing above that point in the finished proposal,
 *      or Infinity.
 *  status: "pass" | "fail" | "warn" | "unknown". Each rule is one
 *  entry in RULES, so the research agent's full set slots in as more
 *  entries without touching the viewer. These three are real AD
 *  numbers but a stub, not compliance advice.
 * ------------------------------------------------------------------ */

const mm = m => `${Math.round(m * 1000)} mm`;

export const RULES = [
  {
    id: "stair-rise-going",
    clause: "Approved Document K (2013 incorporating 2013 amendments), para 1.3, Table 1.1 (+ note: 2R + G) — private stair",
    applies: el => el.type === "stair",
    check(el) {
      const { rise, going } = el.params;
      const out = [];
      out.push(rise <= 0.220
        ? { status: "pass", message: `Rise ${mm(rise)} ≤ 220 mm` }
        : { status: "fail", message: `Rise ${mm(rise)} is more than the 220 mm maximum` });
      out.push(going >= 0.220
        ? { status: "pass", message: `Going ${mm(going)} ≥ 220 mm` }
        : { status: "fail", message: `Going ${mm(going)} is less than the 220 mm minimum` });
      const g2r = 2 * rise + going;
      out.push(g2r >= 0.55 && g2r <= 0.70
        ? { status: "pass", message: `2R + G = ${mm(g2r)}, within 550–700 mm` }
        : { status: "fail", message: `2R + G = ${mm(g2r)}, outside 550–700 mm` });
      return out;
    },
  },
  {
    id: "stair-headroom",
    clause: "Approved Document K, para 1.11, Diagram 1.3 — 2.0 m headroom over the flight",
    applies: el => el.type === "stair",
    check(el, all, ctx) {
      if (!ctx?.clearanceAbove) return [{ status: "unknown", message: "Headroom not measured (no geometry)" }];
      const p = el.params;
      /* a dog-leg stair lists its flights; a straight one is one flight from its own params */
      const flights = (p.flights?.length ? p.flights : [p]).map(f => ({ ...f, rise: f.rise ?? p.rise, going: f.going ?? p.going }));
      if (flights.some(f => !f.start || !f.direction || f.width == null || f.base == null))
        return [{ status: "unknown", message: "Headroom not measured: the stair element has no start / direction / width / base (CONTRACT.md §5)" }];
      let worst = Infinity, at = null;
      flights.forEach((f, fi) => {
        const [dx, dz] = f.direction, nx = -dz, nz = dx;
        /* nosing k (k = 1 … risers-1) is the front edge of tread k: (k-1) goings from the flight's first riser,
           k rises up. Sampled 30 mm onto the tread so the ray clears the riser above. */
        for (let k = 1; k < f.risers; k++) {
          for (const s of [-0.4, 0, 0.4]) {
            const along = (k - 1) * f.going + 0.03;
            const x = f.start[0] + dx * along + nx * s * f.width;
            const z = f.start[1] + dz * along + nz * s * f.width;
            const y = f.base + k * f.rise + 0.01;
            const c = ctx.clearanceAbove(x, y, z);
            if (c < worst) { worst = c; at = `${flights.length > 1 ? `flight ${fi + 1}, ` : ""}nosing ${k}`; }
          }
        }
      });
      if (!isFinite(worst)) return [{ status: "pass", message: "Nothing over the flight" }];
      const conf = el.meta?.conf || "?";
      if (worst >= 2.0 && worst < 2.1 && conf !== "exact")      // a thin margin on scaled geometry is not a pass
        return [{ status: "warn", message: `Least headroom ${mm(worst)} (${at}): only ${mm(worst - 2.0)} over 2000 mm, on ${conf} geometry — measure on site` }];
      return [worst >= 2.0
        ? { status: "pass", message: `Least headroom ${mm(worst)} (${at}) ≥ 2000 mm, measured to the finished proposal's structure` }
        : { status: "fail", message: `Headroom ${mm(worst)} at ${at} is under 2000 mm` }];
    },
  },
  {
    id: "removed-wall-load",
    clause: "Approved Document A, requirement A1 (loading) — structural alteration",
    applies: el => el.type === "wall" && el.removed,
    check(el, all) {
      const carried = all.filter(e => !e.removed && (e.bears_on || []).includes(el.id));
      if (!carried.length) return [{ status: "warn", message: "Wall removed: nothing in the data bears on it, but confirm it is not load-bearing" }];
      const what = carried.map(e => `${e.id} (${e.meta?.group || e.type})`).join(", ");
      return [{ status: "fail", message: `Possibly load-bearing: ${what} bear on it. Needs a structural engineer's design.` }];
    },
  },
];

/* the escape window (an element id ending -EE, CONTRACT.md): AD B para 2.10(a). The sill is read from the opening;
   the clear opening is only estimated from the frame (the opening light is not drawn), so it is never a plain pass */
RULES.push({
  id: "escape-window",
  clause: "Approved Document B Vol 1 (2019 + 2020/2022 amdts), para 2.10(a)",
  applies: el => el.type === "opening" && /-EE$/.test(el.id),
  check(el, all, ctx) {
    const q = el.params, ffl = ctx.ffl?.(el.meta?.storey) ?? 0;
    const sillMm = Math.round((q.sill - ffl) * 1000), conf = el.meta?.conf || "?";
    const out = [sillMm <= 1100
      ? { status: conf === "exact" ? "pass" : "warn", message: `Bottom of the opening ${sillMm} mm above the floor (≤ 1100)${conf === "exact" ? "" : `, but the sill is ${conf}: ${1100 - sillMm} mm margin — confirm on site`}` }
      : { status: "fail", message: `Bottom of the opening ${sillMm} mm above the floor: over the 1100 mm limit` }];
    const fx = all.find(e => e.type === "fixture" && e.params?.opening === el.id);
    const lights = fx?.params?.lights || 1, fr = 0.06;
    const w = (q.width - (lights + 1) * fr) / lights, h = (q.head - q.sill) - 2 * fr;
    const area = w * h;
    out.push({ status: "warn", message: `Clear opening estimated from the frame: one of ${lights} lights ≈ ${Math.round(w * 1000)} x ${Math.round(h * 1000)} mm ≈ ${area.toFixed(2)} m² `
      + `(needs ≥ 0.33 m², ≥ 450 x 450). The opening casement is not drawn: confirm with the window maker` });
    return out;
  },
});

export function checkRules(elements, ctx = {}) {
  const all = elements instanceof Map ? [...elements.values()] : elements;
  const out = [];
  for (const rule of RULES) for (const el of all) {
    if (el.removed && rule.id !== "removed-wall-load") continue;
    if (!rule.applies(el)) continue;
    let res;
    try { res = rule.check(el, all, ctx); }
    catch (err) { res = [{ status: "unknown", message: `Rule error: ${err.message}` }]; }
    for (const r of res) out.push({ elementId: el.id, rule: rule.id, clause: rule.clause, ...r });
  }
  return out;
}
