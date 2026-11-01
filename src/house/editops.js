import { CATALOGUE, wallFrame, layerSpans } from "./geom.js?v=h11";

/* ------------------------------------------------------------------ *
 *  Architect edits, as operations on the edit layer (edits.js):
 *  move a wall (its connected walls follow), add a wall, add / move /
 *  resize / remove an opening, swap a fixture. Each returns the ops it
 *  pushed; the viewer rebuilds geometry and re-runs the rules.
 *  Walls are regenerated from their parameters; slabs, roofs, joists
 *  that sat on a moved wall are NOT re-planned (the rules flag what
 *  bears on what) — that is the generator's job from a change request.
 * ------------------------------------------------------------------ */

const r3 = v => Math.round(v * 1000) / 1000;
const TOL = 0.02;

/* walls whose start or end lies on wall W's footprint (centre line ± half thickness, within its length) */
export function connectedEnds(W, table) {
  const { o, d, n, L } = wallFrame(W.params);
  const { T } = layerSpans(W.params.layers);
  const out = [];
  for (const e of table.values()) {
    if (e.type !== "wall" || e.id === W.id || e.removed) continue;
    if (Math.abs((e.params.base ?? 0) - (W.params.base ?? 0)) > 0.6 && Math.abs(e.params.height - W.params.height) > 0.6) continue;
    const Te = layerSpans(e.params.layers).T;          // a wall butting the END of W stops at W's end face
    for (const end of ["start", "end"]) {
      const p = e.params[end];
      const rx = p[0] - o.x, rz = p[1] - o.z;
      const u = rx * d.x + rz * d.z, v = rx * n.x + rz * n.z;
      if (u > -Te / 2 - TOL && u < L + Te / 2 + TOL && Math.abs(v) <= T / 2 + TOL) out.push({ id: e.id, end });
    }
  }
  return out;
}

/* move wall `id` by `dist` metres along its normal n; connected ends follow. One undo step. */
export function moveWall(editor, id, dist) {
  const table = editor.current();
  const W = table.get(id);
  if (!W || W.type !== "wall") return [];
  const { n } = wallFrame(W.params);
  const mv = p => [r3(p[0] + n.x * dist), r3(p[1] + n.z * dist)];
  const ops = [{ op: "set", id, params: { start: mv(W.params.start), end: mv(W.params.end) } }];
  // the same wall on the other storey usually moves with it: keep their centre lines together
  for (const c of connectedEnds(W, table)) {
    const e = table.get(c.id);
    ops.push({ op: "set", id: c.id, params: { [c.end]: mv(e.params[c.end]) } });
  }
  for (const e of table.values()) {
    if (e.type !== "wall" || e.id === id || e.removed) continue;
    const same = ["start", "end"].every(k => Math.hypot(e.params[k][0] - W.params[k][0], e.params[k][1] - W.params[k][1]) < TOL);
    if (same && editor.linkStoreys !== false) {
      ops.push({ op: "set", id: e.id, params: { start: mv(e.params.start), end: mv(e.params.end) } });
      for (const c of connectedEnds(e, table)) {
        if (ops.some(o => o.id === c.id && o.params[c.end])) continue;
        ops.push({ op: "set", id: c.id, params: { [c.end]: mv(table.get(c.id).params[c.end]) } });
      }
    }
  }
  editor.batch(ops, `move ${id} ${Math.round(dist * 1000)} mm`);
  return ops;
}

/* a new wall between two plan points, copying a template wall's layers or a partition stack */
export const PARTITION = [
  { group: "wall_lining", thickness: 0.0125, material: "plasterboard", label: "12.5mm plasterboard, skimmed" },
  { group: "wall_inner", thickness: 0.075, material: "timber", label: "75x50 C16 studs at 400 c/c, mineral wool infill" },
  { group: "wall_lining", thickness: 0.0125, material: "plasterboard", label: "12.5mm plasterboard, skimmed" },
];
export function addWall(editor, a, b, { base = 0.15, height = 2.4, layers = PARTITION, stage = 12, storey = "ground", label } = {}) {
  const id = `W-new-${Date.now().toString(36)}`;
  editor.add({
    id, type: "wall", openings: [],
    params: { start: [r3(a[0]), r3(a[1])], end: [r3(b[0]), r3(b[1])], base: r3(base), height: r3(height), layers, lifts: [] },
    meta: { stage_in: stage, stage_out: null, seq: 0.1, category: "new", group: layers[0].group, storey,
            label: label || "PROPOSED (edit): new wall — architect's change, not on the drawings", plain_label: "A new wall (proposed change)",
            drawing: "edit", conf: "assumed", collide: true },
  });
  return id;
}

/* a new opening in a wall at distance `u` along it (centre), with a fixture from the catalogue */
export function addOpening(editor, wallId, u, { width = 0.9, sill = null, head = null, catalogue = "door.front.solid" } = {}) {
  const W = editor.get(wallId);
  if (!W) return null;
  const L = wallFrame(W.params).L;
  const base = W.params.base;
  const s = sill ?? (catalogue.startsWith("window") ? base + 1.0 : Math.max(base, base + 0.0));
  const h = head ?? Math.min(base + W.params.height - 0.2, s + (catalogue.startsWith("window") ? 1.1 : 2.1));
  const offset = Math.max(0.1, Math.min(L - width - 0.1, u - width / 2));
  const t = Date.now().toString(36);
  const oid = `O-new-${t}`, lid = `L-new-${t}`, fid = `F-new-${t}`;
  const meta = (group, label, extra = {}) => ({ stage_in: W.meta.stage_in, stage_out: null, seq: 0.6, category: "new", group,
    storey: W.meta.storey, label, drawing: "edit", conf: "assumed", collide: false, ...extra });
  editor.batch([
    { op: "add", element: { id: oid, type: "opening", params: { host: wallId, offset: r3(offset), width: r3(width), sill: r3(s), head: r3(h) },
                            meta: meta(catalogue.startsWith("window") ? "window" : "door", "PROPOSED (edit): new opening") } },
    { op: "add", element: { id: lid, type: "lintel", params: { opening: oid, bearing: 0.15, depth: 0.15 },
                            meta: meta("lintel", "PROPOSED (edit): lintel to suit — size by engineer / manufacturer", { seq: 0.62 }) } },
    { op: "add", element: { id: fid, type: "fixture", params: { catalogue, opening: oid, plane: 0 },
                            meta: meta(catalogue.startsWith("window") ? "window" : "door", `PROPOSED (edit): ${CATALOGUE[catalogue]?.label || catalogue}`,
                                       { stage_in: Math.max(W.meta.stage_in, 11), seq: 0.8 }) } },
  ], `add opening in ${wallId}`);
  return oid;
}

/* next catalogue item of the same kind (doors cycle doors, windows cycle windows) */
export function swapFixture(editor, fixtureId) {
  const F = editor.get(fixtureId);
  if (!F || F.type !== "fixture" || !CATALOGUE[F.params.catalogue]) return null;
  const kind = F.params.catalogue.split(".")[0];
  const same = Object.keys(CATALOGUE).filter(k => k.startsWith(kind + "."));
  const next = same[(same.indexOf(F.params.catalogue) + 1) % same.length];
  if (next === F.params.catalogue) return null;
  editor.set(fixtureId, { catalogue: next });
  return next;
}
