import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  Element geometry, regenerated in the browser from an element's
 *  parameters (CONTRACT.md, "Elements"). The same algorithm as
 *  tools/house/make_fixture.py, so a wall rebuilt here after an edit
 *  matches the one the Blender generator baked: split the wall face
 *  at every opening edge and lift line, drop the cells inside an
 *  opening, extrude each kept cell through each layer's thickness.
 *  Output is world-space geometry (viewer frame: +Y up, metres) with
 *  the extras a baked node would have carried.
 * ------------------------------------------------------------------ */

export const CATALOGUE = {
  "door.bifold.3":     { label: "Bifold door, 3 panes", frame: 0.07, depth: 0.07, panes: 3, frameMat: "frame_grey", glass: true },
  "door.front.solid":  { label: "Solid front door", frame: 0.06, depth: 0.06, panes: 1, frameMat: "frame_white", glass: false },
  "window.casement.2": { label: "Casement window, 2 lights", frame: 0.06, depth: 0.07, panes: 2, frameMat: "frame_white", glass: true },
};

const LAYER_META = ["stage_in", "stage_out", "seq", "seq_out", "category", "group", "label", "plain_label", "drawing", "conf", "collide"];

/* wall frame: a along the centre line, n = (-dz, dx) across (layer 0 on the +n face) */
export function wallFrame(p) {
  const dx = p.end[0] - p.start[0], dz = p.end[1] - p.start[1];
  const L = Math.hypot(dx, dz);
  const d = new THREE.Vector3(dx / L, 0, dz / L);
  const n = new THREE.Vector3(-d.z, 0, d.x);
  return { o: new THREE.Vector3(p.start[0], 0, p.start[1]), d, n, L };
}

export function layerSpans(layers) {
  const T = layers.reduce((s, l) => s + l.thickness, 0);
  let c = T / 2;
  const spans = layers.map(l => { const s = [c - l.thickness, c]; c -= l.thickness; return s; });
  return { spans, T };
}

/* cells of the wall face in (u, y): [{lift, u0, u1, y0, y1}] and the number of lifts */
export function wallCells(L, base, height, openings, lifts = []) {
  const top = base + height;
  const clampU = v => Math.max(0, Math.min(L, v)), clampY = v => Math.max(base, Math.min(top, v));
  const uniq = a => [...new Set(a.map(v => Math.round(v * 1e6) / 1e6))].sort((a, b) => a - b);
  const inner = lifts.filter(y => y > base && y < top);
  const us = uniq([0, L, ...openings.flatMap(o => [clampU(o.offset), clampU(o.offset + o.width)])]);
  const ys = uniq([base, top, ...inner, ...openings.flatMap(o => [clampY(o.sill), clampY(o.head)])]);
  const liftLines = [base, ...inner, top];
  const out = [];
  for (let i = 0; i < us.length - 1; i++) for (let j = 0; j < ys.length - 1; j++) {
    const u0 = us[i], u1 = us[i + 1], y0 = ys[j], y1 = ys[j + 1];
    if (u1 - u0 < 1e-6 || y1 - y0 < 1e-6) continue;
    const um = (u0 + u1) / 2, ym = (y0 + y1) / 2;
    if (openings.some(o => o.offset < um && um < o.offset + o.width && o.sill < ym && ym < o.head)) continue;
    let lift = 0;
    for (let k = 0; k < liftLines.length - 1; k++) if (liftLines[k] <= ym + 1e-9) lift = k;
    out.push({ lift, u0, u1, y0, y1 });
  }
  return { cells: out, lifts: liftLines.length - 1 };
}

/* the recommended seq of a lift of a layer (CONTRACT.md): lifts rise in order across the wall */
export function wallSeq(meta, lift, nlifts, li, nlayers) {
  const span = meta.seq_span ?? 0.85;
  return Math.round((meta.seq + span * (lift + 0.3 * li / Math.max(1, nlayers)) / nlifts) * 1e4) / 1e4;
}

/* the real tile size of each material (assets/sites/<site>/materials.json), so a rebuilt wall gets the same
   UVs as a baked one: metres / tile, and on wall faces v = (height + 0.032) / tile_v + v_joint (a bed joint
   on the dpc). Set once by the viewer. */
let TILES = {};
export function setTiles(materials) { TILES = materials || {}; }
const tileOf = name => { const t = TILES[name]; return t ? { tu: t.tile[0], tv: t.tile[1], vj: t.v_joint || 0 } : { tu: 1, tv: 1, vj: 0 }; };

/* boxes in a local frame (o, U, W, V) -> one indexed, flat-shaded BufferGeometry in world space, with UVs:
   a = along, b = height, c = across */
class BoxBuilder {
  constructor(o, U, W, V, material) {
    this.o = o; this.U = U; this.W = W; this.V = V; this.pos = []; this.nrm = []; this.uv = []; this.idx = [];
    this.t = tileOf(material);
  }
  at(a, b, c) {
    return new THREE.Vector3().copy(this.o).addScaledVector(this.U, a).addScaledVector(this.W, b).addScaledVector(this.V, c);
  }
  box(a0, a1, b0, b1, c0, c1) {
    const P = (a, b, c) => this.at(a ? a1 : a0, b ? b1 : b0, c ? c1 : c0);
    const faces = [
      [[0,0,0],[0,0,1],[0,1,1],[0,1,0]], [[1,0,0],[1,1,0],[1,1,1],[1,0,1]],
      [[0,0,0],[1,0,0],[1,0,1],[0,0,1]], [[0,1,0],[0,1,1],[1,1,1],[1,1,0]],
      [[0,0,0],[0,1,0],[1,1,0],[1,0,0]], [[0,0,1],[1,0,1],[1,1,1],[0,1,1]],
    ];
    const centre = P(0, 0, 0).add(P(1, 1, 1)).multiplyScalar(0.5);
    const { tu, tv, vj } = this.t;
    const L = (a, b, c) => [a ? a1 : a0, b ? b1 : b0, c ? c1 : c0];
    faces.forEach((f, fi) => {
      const v = f.map(k => P(...k));
      const loc = f.map(k => L(...k));
      /* faces 0-1 are the ends (normal along a), 2-3 top and bottom, 4-5 the wall faces */
      const uvs = loc.map(([a, b, c]) => fi < 2 ? [c / tu, (b + 0.032) / tv + vj] : fi < 4 ? [a / tu, c / tv] : [a / tu, (b + 0.032) / tv + vj]);
      const nrm = new THREE.Vector3().subVectors(v[1], v[0]).cross(new THREE.Vector3().subVectors(v[2], v[0])).normalize();
      const out = new THREE.Vector3().addVectors(v[0], v[2]).multiplyScalar(0.5).sub(centre);
      if (nrm.dot(out) < 0) { v.reverse(); uvs.reverse(); nrm.negate(); }       // outward, whatever the frame's handedness
      const s = this.pos.length / 3;
      v.forEach((p, i) => { this.pos.push(p.x, p.y, p.z); this.nrm.push(nrm.x, nrm.y, nrm.z); this.uv.push(uvs[i][0], uvs[i][1]); });
      this.idx.push(s, s + 1, s + 2, s, s + 2, s + 3);
    });
  }
  geometry() {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(this.pos, 3));
    g.setAttribute("normal", new THREE.Float32BufferAttribute(this.nrm, 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute(this.uv, 2));
    g.setIndex(this.idx);
    g.computeBoundingBox(); g.computeBoundingSphere();
    return g;
  }
}
const UP = new THREE.Vector3(0, 1, 0);

/* parts of a wall element: [{name, geometry, material, props}] */
export function wallParts(wall, openings) {
  const p = wall.params;
  const { o, d, n, L } = wallFrame(p);
  const { cells, lifts } = wallCells(L, p.base, p.height, openings.map(x => x.params), p.lifts || []);
  const { spans } = layerSpans(p.layers);
  const out = [];
  /* a stripped leaf (params.only_layers: ["brick", "plaster"] …) keeps just those layers */
  const keep = layer => !p.only_layers || p.only_layers.some(n => n === layer.material || layer.group === `wall_${n}`
    || (n === "brick" && layer.group === "wall_outer") || (n === "plaster" && layer.group === "wall_lining") || (n === "cavity" && layer.group === "wall_cavity"));
  p.layers.forEach((layer, li) => {
    if (layer.void || !keep(layer)) return;
    const lm = { ...wall.meta };
    for (const k of LAYER_META) if (k in layer) lm[k] = layer[k];
    const [c0, c1] = spans[li];
    for (let lift = 0; lift < lifts; lift++) {
      const cs = cells.filter(c => c.lift === lift);
      if (!cs.length) continue;
      const b = new BoxBuilder(o, d, UP, n, layer.material);
      for (const c of cs) b.box(c.u0, c.u1, c.y0, c.y1, c0, c1);
      const seq = "seq" in layer ? layer.seq : wallSeq(wall.meta, lift, lifts, li, p.layers.length);
      out.push({
        name: `${wall.id}_L${li}_${layer.group}_lift${lift}`, geometry: b.geometry(), material: layer.material,
        props: { ...lm, layer: li, lift, seq, element: wall.id, element_label: wall.meta.label },
      });
    }
  });
  return out;
}

function openingFrame(opening, host) {
  const { o, d, n, L } = wallFrame(host.params);
  const { spans, T } = layerSpans(host.params.layers);
  return { o, d, n, L, spans, T };
}

export function lintelParts(lintel, opening, host) {
  const { o, d, n, spans } = openingFrame(opening, host);
  const q = opening.params, b = lintel.params.bearing;
  const layers = host.params.layers;
  const cHi = spans[0][1];
  const cLo = Math.min(...spans.filter((_, i) => layers[i].group !== "wall_lining").map(s => s[0]));
  const bb = new BoxBuilder(o, d, UP, n, lintel.params.material || "lintel_galv");
  bb.box(q.offset - b, q.offset + q.width + b, q.head, q.head + lintel.params.depth, cLo, cHi);
  return [{ name: lintel.id, geometry: bb.geometry(), material: lintel.params.material || "lintel_galv",
            props: { ...lintel.meta, element: lintel.id } }];
}

export function fixtureParts(fixture, opening, host) {
  const cat = CATALOGUE[fixture.params.catalogue];
  if (!cat || !opening) return [];
  const { o, d, n } = openingFrame(opening, host);
  const q = opening.params, f = cat.frame, dep = cat.depth, c = fixture.params.plane || 0;
  const u0 = q.offset, u1 = q.offset + q.width, y0 = q.sill, y1 = q.head;
  const fr = new BoxBuilder(o, d, UP, n, cat.frameMat);
  fr.box(u0, u1, y1 - f, y1, c - dep / 2, c + dep / 2);
  fr.box(u0, u1, y0, y0 + f * 0.6, c - dep / 2, c + dep / 2);
  for (let i = 0; i <= cat.panes; i++) {
    const x = u0 + (u1 - u0 - f) * i / cat.panes;
    fr.box(x, x + f, y0 + f * 0.6, y1 - f, c - dep / 2, c + dep / 2);
  }
  const lf = new BoxBuilder(o, d, UP, n, cat.glass ? "glass" : cat.frameMat);
  lf.box(u0 + f, u1 - f, y0 + f * 0.6, y1 - f, c - 0.006, c + 0.006);
  return [
    { name: `${fixture.id}_frame`, geometry: fr.geometry(), material: cat.frameMat, props: { ...fixture.meta, element: fixture.id, part: "frame" } },
    { name: `${fixture.id}_leaf`, geometry: lf.geometry(), material: cat.glass ? "glass" : cat.frameMat, props: { ...fixture.meta, element: fixture.id, part: "leaf" } },
  ];
}

/* everything an element regenerates to, given the current element table (a Map id -> element) */
export function regenerate(el, table) {
  if (el.type === "wall") {
    const ops = (el.openings || []).map(id => table.get(id)).filter(x => x && !x.removed);
    return wallParts(el, ops);
  }
  if (el.type === "lintel") {
    const op = table.get(el.params.opening), host = op && table.get(op.params.host);
    return op && host ? lintelParts(el, op, host) : [];
  }
  if (el.type === "fixture" && el.params.opening) {
    const op = table.get(el.params.opening), host = op && table.get(op.params.host);
    return op && host ? fixtureParts(el, op, host) : [];
  }
  return null;            // not parametric here: keep the baked geometry
}

/* which elements must be rebuilt when one changes (the wall hosting an opening, its lintel, its fixture) */
export function dependents(id, table) {
  const el = table.get(id);
  const out = new Set([id]);
  if (!el) return out;
  if (el.type === "opening") {
    out.add(el.params.host);
    for (const e of table.values()) if (e.params?.opening === id) out.add(e.id);
  }
  if (el.type === "wall") for (const oid of el.openings || []) {
    out.add(oid);
    for (const e of table.values()) if (e.params?.opening === oid) out.add(e.id);
  }
  return out;
}
