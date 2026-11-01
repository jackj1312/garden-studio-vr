import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

/* ------------------------------------------------------------------ *
 *  The house, read-only, for the game.
 *
 *  Loads a version from assets/sites/house-preview/ (as built now,
 *  falling back to the approved scheme), shows it "as built" (site
 *  records replace the drawn parts they differ from, as the viewer's
 *  As-built toggle does), swings every door leaf open on its hinge,
 *  and merges the whole thing into one mesh per material: the game
 *  never changes the house, so ~60 draw calls instead of ~900.
 *
 *  Returns the parts in the shape src/house/bvh.js wants (geometry,
 *  matrix0, index, noRay) plus rooms, doorways and windows from the
 *  elements file, all in the viewer frame (+Y up, metres, y 0 = the
 *  ground-floor finished floor level).
 * ------------------------------------------------------------------ */

const BASE = "assets/sites/house-preview/";
const FOLIAGE = /leaves|branches|VertexPlant|foliage|hedge/i;

const fetchJSON = async url => { const r = await fetch(url, { cache: "no-cache" }); if (!r.ok) throw new Error(`${url}: ${r.status}`); return r.json(); };

/* a quantized attribute (a meshopt GLB) as plain floats, so every geometry of a merge has the same types */
function floats(a, itemSize) {
  if (!a) return null;
  if (a.array instanceof Float32Array && !a.normalized && !a.isInterleavedBufferAttribute && a.itemSize === itemSize) return a;
  const out = new Float32Array(a.count * itemSize);
  for (let i = 0; i < a.count; i++) for (let c = 0; c < itemSize; c++) out[i * itemSize + c] = a.getComponent(i, c);
  return new THREE.BufferAttribute(out, itemSize);
}

/* the GLB's physical materials (KHR_materials_specular / ior) as plain standard ones: cheaper on the Quest */
function toStandard(m) {
  const s = new THREE.MeshStandardMaterial({
    name: m.name, color: m.color, map: m.map, normalMap: m.normalMap, roughnessMap: m.roughnessMap, metalnessMap: m.metalnessMap,
    aoMap: m.aoMap, emissive: m.emissive, emissiveMap: m.emissiveMap, roughness: m.roughness, metalness: m.metalness,
    transparent: m.transparent, opacity: m.opacity, alphaTest: m.alphaTest, alphaMap: m.alphaMap,
  });
  if (m.normalScale) s.normalScale.copy(m.normalScale);
  const foliage = FOLIAGE.test(m.name || "");
  s.side = foliage ? THREE.DoubleSide : THREE.FrontSide;    // the house's parts are closed solids (CONTRACT §3)
  if (foliage && s.transparent) { s.transparent = false; s.alphaTest = Math.max(0.5, s.alphaTest || 0); }
  if (/glass/i.test(m.name || "") && !s.transparent) { s.transparent = true; s.opacity = Math.min(s.opacity, 0.35); }
  if (s.transparent) s.depthWrite = false;
  return s;
}

/* the open pose of every door leaf: a turn of swing_deg about the vertical through its hinge (+ = counter-clockwise
   seen from above); leaves of one door_group without their own hinge borrow the group's */
function openDoors(root) {
  const hinges = new Map();
  root.traverse(o => { const u = o.userData; if (u?.door_leaf && u.hinge && u.door_group) hinges.set(u.door_group, u); });
  const pivot = new THREE.Matrix4(), turn = new THREE.Matrix4(), back = new THREE.Matrix4();
  const leaves = [];
  root.traverse(o => { if (o.userData?.door_leaf) leaves.push(o); });
  for (const o of leaves) {
    const u = o.userData.hinge ? o.userData : hinges.get(o.userData.door_group);
    if (!u?.hinge || !u.swing_deg) continue;
    const h = new THREE.Vector3().fromArray(u.hinge);
    o.updateMatrixWorld(true);
    pivot.makeTranslation(h.x, h.y, h.z);
    turn.makeRotationY(THREE.MathUtils.degToRad(u.swing_deg) * 0.92);   // a touch short of the wall
    back.makeTranslation(-h.x, -h.y, -h.z);
    const m = new THREE.Matrix4().multiplyMatrices(pivot, turn).multiply(back).multiply(o.matrixWorld);
    o.userData._openMatrix = m;
  }
}

export async function loadHouse({ onProgress = () => {}, preferVersion = null } = {}) {
  const manifest = await fetchJSON(BASE + "versions.json");
  const order = [preferVersion, manifest.as_built_now || "as_built_now", "approved_2b"].filter(Boolean);
  let def = null, gltf = null, elements = null, sidecar = null;
  for (const id of order) {
    def = manifest.versions.find(v => v.id === id);
    if (!def) continue;
    const file = def.glb_quest || def.glb;
    try {
      gltf = await new Promise((res, rej) => new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).load(BASE + file, res,
        x => x.total && onProgress(0.05 + 0.75 * x.loaded / x.total, `Loading the house · ${(x.loaded / 1e6).toFixed(1)} MB`), rej));
      [elements, sidecar] = await Promise.all([fetchJSON(BASE + def.elements).catch(() => null), fetchJSON(BASE + def.stages).catch(() => null)]);
      break;
    } catch (err) { console.warn(`game: ${file} failed (${err?.message || err}); trying the next`); gltf = null; }
  }
  if (!gltf) throw new Error("The house model could not be loaded");
  onProgress(0.82, "Building the rooms…");
  await new Promise(r => setTimeout(r));

  const els = elements?.elements || [];
  const table = new Map(els.map(e => [e.id, e]));
  const replaced = new Set(els.filter(e => e.layer === "as_built").flatMap(e => e.replaces || []));

  const root = gltf.scene;
  root.updateMatrixWorld(true);
  openDoors(root);

  const lastStage = sidecar?.stages?.length || 1;
  const readExtras = o => { for (let x = o; x; x = x.parent) if (x.userData && x.userData.stage_in !== undefined) return x.userData; return null; };
  const matCache = new Map();
  const buckets = new Map();               // standard material -> [geometry in world space]
  const parts = [];
  root.traverse(o => {
    if (!o.isMesh) return;
    const ud = readExtras(o) || {};
    const stageIn = Number(ud.stage_in) || 1, so = ud.stage_out;
    const stageOut = so === null || so === undefined || so === 0 || so === -1 ? null : Number(so);
    if (stageIn > lastStage || (stageOut !== null && stageOut <= lastStage)) return;    // not there in the house as it stands
    if (replaced.has(ud.element)) return;                                                 // a drawn part the site records replace
    const src = Array.isArray(o.material) ? o.material[0] : o.material;
    if (!matCache.has(src)) matCache.set(src, toStandard(src));
    const mat = matCache.get(src);
    const g0 = o.geometry;
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", floats(g0.attributes.position, 3));
    if (g0.attributes.normal) g.setAttribute("normal", floats(g0.attributes.normal, 3));
    g.setAttribute("uv", floats(g0.attributes.uv, 2) || new THREE.Float32BufferAttribute(new Float32Array(g0.attributes.position.count * 2), 2));
    g.setIndex(g0.index ? g0.index : [...Array(g0.attributes.position.count).keys()]);
    if (!g.attributes.normal) g.computeVertexNormals();
    const m = readExtras(o)?.door_leaf && o.userData._openMatrix ? o.userData._openMatrix
      : o.parent?.userData?._openMatrix ? o.parent.userData._openMatrix.clone().multiply(o.matrix) : o.matrixWorld;
    const part = {
      index: parts.length, name: o.name, ud, geometry: g, matrix0: m.clone(),
      noRay: FOLIAGE.test(src.name || ""), collide: !!ud.collide, glass: /glass/i.test(src.name || "") || ud.part === "glass",
      context: !!ud.context, group: ud.group || "fitting", storey: ud.storey || "ground", element: ud.element || o.name,
    };
    parts.push(part);
    const wg = g.clone().applyMatrix4(m);
    if (!buckets.has(mat)) buckets.set(mat, []);
    buckets.get(mat).push(wg);
  });

  const group = new THREE.Group();
  group.name = "house";
  for (const [mat, list] of buckets) {
    const merged = mergeGeometries(list, false);
    for (const g of list) g.dispose();
    if (!merged) continue;
    merged.computeBoundingSphere();
    const mesh = new THREE.Mesh(merged, mat);
    mesh.matrixAutoUpdate = false;
    if (mat.transparent || mat.alphaTest > 0) mesh.renderOrder = 2;
    group.add(mesh);
  }

  /* rooms (x, z polygons), doorways and windows from the elements file (openings on walls that stand today) */
  const rooms = els.filter(e => e.type === "room").map(e => ({
    id: e.id, name: e.params.name, storey: e.params.storey, floor: e.params.floor, poly: e.params.polygon,
  }));
  const openings = [];
  for (const e of els) {
    if (e.type !== "opening" || /^O-N21/.test(e.id)) continue;
    const host = table.get(e.params.host);
    if (!host || replaced.has(host.id) || replaced.has(e.id)) continue;
    const s = host.params.start, en = host.params.end;
    const dx = en[0] - s[0], dz = en[1] - s[1], L = Math.hypot(dx, dz);
    const t = new THREE.Vector3(dx / L, 0, dz / L);
    const along = e.params.offset + e.params.width / 2;
    const storeyFloor = e.meta.storey === "first" ? (sidecar?.storeys?.first ?? 2.6755) : 0;
    const sill = e.params.sill >= storeyFloor - 0.01 && storeyFloor > 0 ? e.params.sill - storeyFloor : e.params.sill;
    openings.push({
      id: e.id, kind: e.meta.group === "door" ? "door" : "window",
      centre: new THREE.Vector3(s[0] + t.x * along, storeyFloor, s[1] + t.z * along),
      tangent: t, normal: new THREE.Vector3(-t.z, 0, t.x), width: e.params.width,
      floor: storeyFloor, sill, head: e.params.head - (e.params.head > storeyFloor + 0.5 && storeyFloor > 0 ? storeyFloor : 0),
    });
  }

  const box = new THREE.Box3();
  for (const p of parts) if (!p.context) { p.geometry.computeBoundingBox(); box.union(p.geometry.boundingBox.clone().applyMatrix4(p.matrix0)); }
  return { def, group, parts, rooms, openings, spawns: sidecar?.spawns || [], storeys: sidecar?.storeys || { ground: 0, first: 2.6755 }, bounds: box };
}
