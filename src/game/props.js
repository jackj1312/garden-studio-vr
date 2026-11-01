import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

/* ------------------------------------------------------------------ *
 *  Toy furniture. The house model has walls, doors and windows but no
 *  furniture, so the game brings a few chunky pieces of its own for the
 *  targets to hide behind and pop up from: a sofa, coffee table and TV
 *  unit in the living room, worktops, a fridge and a table you can
 *  crawl under (toy mode) in the kitchen, beds and toy boxes upstairs.
 *  Placed inside the room outlines, clear of the doors' swings.
 *
 *  Each box is also a part for the BVH (same shape as the house's
 *  parts). `block` parts are walk-only blockers for full size (a table
 *  you cannot walk through, but a toy can walk under).
 * ------------------------------------------------------------------ */

const PAL = {
  sofa: 0x3d7dd8, cushion: 0xffc93c, wood: 0xc98b4e, white: 0xf4efe6, worktop: 0x6b7480, red: 0xe8483b,
  green: 0x41b86a, purple: 0x8e5bd6, rug: 0xff8a5c, fridge: 0xdfe6ec, pillow: 0xffffff, duvet: 0x5cc7d6, duvet2: 0xff7eb6,
};

/* [x0, x1] x [z0, z1] in plan, y0..y1 high; colour key; options */
const F = 2.6755;
const LAYOUT = [
  // living room (party wall at x 0.165, living door near the front on the east wall)
  { room: "living", box: [0.22, 1.12, -1.35, -3.35, 0, 0.45], c: "sofa" },
  { room: "living", box: [0.22, 0.46, -1.35, -3.35, 0.45, 0.88], c: "sofa" },
  { room: "living", box: [0.22, 1.12, -1.18, -1.35, 0, 0.62], c: "sofa" },
  { room: "living", box: [0.22, 1.12, -3.35, -3.52, 0, 0.62], c: "sofa" },
  { room: "living", box: [0.5, 1.08, -1.45, -2.3, 0.45, 0.56], c: "cushion", noCollide: true },
  { room: "living", box: [0.5, 1.08, -2.4, -3.25, 0.45, 0.56], c: "cushion", noCollide: true },
  { room: "living", box: [1.75, 2.45, -1.95, -2.75, 0.36, 0.42], c: "wood", legs: true },
  { room: "living", box: [1.75, 2.45, -1.95, -2.75, 0, 0.42], block: true },
  { room: "living", box: [3.1, 3.5, -2.2, -3.8, 0, 0.5], c: "white" },
  { room: "living", box: [3.18, 3.26, -2.5, -3.5, 0.5, 1.1], c: "worktop" },            // the telly
  { room: "living", box: [1.3, 2.9, -1.6, -3.1, 0, 0.012], c: "rug", noCollide: true, flat: true },
  { room: "living", box: [2.6, 3.05, -0.55, -1.0, 0, 0.42], c: "red" },                  // toy box
  // kitchen (worktops on the east wall under the windows, an L along the back, a fridge in the front corner)
  { room: "kitchen", box: [8.06, 8.66, -1.3, -1.92, 0, 1.82], c: "fridge" },
  { room: "kitchen", box: [8.06, 8.66, -1.95, -5.49, 0, 0.88], c: "white" },
  { room: "kitchen", box: [8.02, 8.66, -1.95, -5.49, 0.88, 0.93], c: "worktop" },
  { room: "kitchen", box: [6.75, 8.06, -4.9, -5.49, 0, 0.88], c: "white" },
  { room: "kitchen", box: [6.75, 8.06, -4.86, -5.49, 0.88, 0.93], c: "worktop" },
  { room: "kitchen", box: [6.55, 7.55, -2.65, -3.65, 0.71, 0.75], c: "wood", legs: true },
  { room: "kitchen", box: [6.55, 7.55, -2.65, -3.65, 0, 0.75], block: true },
  { room: "kitchen", box: [6.25, 6.6, -2.95, -3.35, 0, 0.45], c: "red" },               // stool
  { room: "kitchen", box: [7.5, 7.85, -2.95, -3.35, 0, 0.45], c: "red" },
  // hall
  { room: "hall", box: [4.95, 5.3, -0.45, -1.05, 0, 0.5], c: "wood" },                   // shoe bench
  // upstairs
  { room: "bed1", box: [0.2, 2.2, -1.6, -3.1, F, F + 0.5], c: "duvet" },
  { room: "bed1", box: [0.2, 0.3, -1.55, -3.15, F, F + 1.05], c: "wood" },
  { room: "bed1", box: [0.35, 0.75, -1.75, -2.95, F + 0.5, F + 0.62], c: "pillow", noCollide: true },
  { room: "bed1", box: [2.7, 3.1, -3.6, -4.2, F, F + 0.45], c: "purple" },
  { room: "bed2", box: [6.7, 8.6, 0.0, 1.3, F, F + 0.5], c: "duvet2" },
  { room: "bed2", box: [8.5, 8.62, -0.05, 1.35, F, F + 1.0], c: "wood" },
  { room: "bed2", box: [7.95, 8.4, 0.2, 1.1, F + 0.5, F + 0.62], c: "pillow", noCollide: true },
  { room: "bed2", box: [5.75, 6.15, 1.6, 2.1, F, F + 0.45], c: "green" },
  { room: "bed3", box: [7.0, 8.6, -3.85, -5.25, F, F + 0.5], c: "duvet" },
  { room: "bed3", box: [8.5, 8.62, -3.8, -5.3, F, F + 1.0], c: "wood" },
  { room: "bed3", box: [5.75, 6.5, -4.9, -5.4, F, F + 0.85], c: "white" },               // chest of drawers
];

export function buildProps(firstPartIndex) {
  const byColour = new Map();
  const parts = [];
  const tmp = new THREE.Matrix4();
  const add = (key, geo) => { if (!byColour.has(key)) byColour.set(key, []); byColour.get(key).push(geo); };
  const part = (x0, x1, y0, y1, z0, z1, extra) => {
    const g = new THREE.BoxGeometry(x1 - x0, y1 - y0, Math.abs(z1 - z0));
    const m = tmp.clone().makeTranslation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
    parts.push({ index: firstPartIndex + parts.length, name: "prop", geometry: g, matrix0: m, noRay: false, collide: true, prop: true, ...extra });
  };
  for (const it of LAYOUT) {
    const [x0, x1, za, zb, y0, y1] = it.box;
    const z0 = Math.max(za, zb), z1 = Math.min(za, zb);
    const w = x1 - x0, h = y1 - y0, d = z0 - z1;
    if (it.block) { part(x0, x1, y0, y1, z1, z0, { block: true }); continue; }
    if (it.legs) {
      const top = y1 - y0;
      const r = Math.min(0.03, top / 2);
      const tg = new RoundedBoxGeometry(w, top, d, 2, r);
      tg.translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
      add(it.c, tg);
      part(x0, x1, y0, y1, z1, z0, {});
      for (const [lx, lz] of [[x0 + 0.06, z1 + 0.06], [x1 - 0.06, z1 + 0.06], [x0 + 0.06, z0 - 0.06], [x1 - 0.06, z0 - 0.06]]) {
        const lg = new THREE.CylinderGeometry(0.03, 0.03, y0, 8);
        lg.translate(lx, y0 / 2, lz);
        add(it.c, lg);
        part(lx - 0.03, lx + 0.03, 0, y0, lz - 0.03, lz + 0.03, { leg: true });
      }
      continue;
    }
    const r = it.flat ? 0.004 : Math.min(0.05, w / 4, h / 4, d / 4);
    const g = new RoundedBoxGeometry(w, h, d, it.flat ? 1 : 3, r);
    g.translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
    add(it.c, g);
    if (!it.noCollide) part(x0, x1, y0, y1, z1, z0, {});
    else if (!it.flat) part(x0, x1, y0, y1, z1, z0, { collide: false });
  }
  const group = new THREE.Group();
  group.name = "props";
  for (const [key, list] of byColour) {
    const merged = mergeGeometries(list.map(g => g.index ? g.toNonIndexed() : g), false);
    const mat = new THREE.MeshStandardMaterial({ color: PAL[key], roughness: key === "worktop" ? 0.45 : 0.75, metalness: 0 });
    const mesh = new THREE.Mesh(merged, mat);
    mesh.matrixAutoUpdate = false;
    group.add(mesh);
  }
  return { group, parts };
}
