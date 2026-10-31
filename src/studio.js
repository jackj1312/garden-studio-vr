import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/addons/loaders/DRACOLoader.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { COLOURS, BUILD } from "./config.js?v=a6c6ab9-0950";
import { addWind } from "./wind.js?v=a6c6ab9-0950";
import { foliageMaterial, cardCluster, samplePoints } from "./foliage.js?v=a6c6ab9-0950";

/* ------------------------------------------------------------------ *
 *  The studio comes from the Blender master model.
 *
 *  Geometry only — glTF cannot carry Blender's procedural materials, so
 *  the master supplies the shapes (bevelled edges, cladding boards with
 *  real shadow gaps, window reveals, the timber frame) and three.js
 *  supplies the surfaces. When the lightmap bake lands it arrives as a
 *  texture on these same meshes, and nothing here has to change.
 * ------------------------------------------------------------------ */

const STAGE_NODES = {
  STAGE_03: 2,   // slab and service trench
  STAGE_04: 3,   // timber frame
  STAGE_05: 4,   // clad, roofed and glazed
  STAGE_06: 5    // fit-out and deck
};

/* Draco cuts the garden from 7.9 MB to 1.2 MB, which matters a great
   deal when the client is a headset on someone's home wifi. */
/* The baked lightmap. It carries bounced light and contact shadow that
   real-time lighting cannot afford on a headset, and it costs nothing
   at runtime. Only the built surfaces were baked — ground, trees and
   shrubs were excluded, so they must not receive it or they will show
   another object's patch of the atlas. */
let lightmap = null;
function bakedLight() {
  if (!lightmap) {
    lightmap = new THREE.TextureLoader().load(`assets/models/lightmap.jpg?v=${BUILD}`);
    lightmap.flipY = false;                       // glTF UV convention
    lightmap.channel = 1;                         // read uv1, not uv0
    lightmap.colorSpace = THREE.SRGBColorSpace;
  }
  return lightmap;
}

function applyBakedLight(mat, intensity = 1.0) {
  mat.lightMap = bakedLight();
  mat.lightMapIntensity = intensity;
  mat.envMapIntensity = 0.45;        // the bake already carries the sky; do not count it twice
  return mat;
}
/* textured materials are shared with procedural meshes whose uv1 is not
   in the atlas, so the GLB gets its own lit copies */
const litCopies = new Map();
function litCopy(mat) {
  if (!litCopies.has(mat)) litCopies.set(mat, applyBakedLight(mat.clone(), 1.0));
  return litCopies.get(mat);
}


/* ------------------------------------------------------------------ *
 *  Draw calls are the budget that bites first on a Quest. The Blender
 *  export is one mesh per object — 185 of them — and each costs a draw
 *  call twice over once shadows are on. Merging everything that shares
 *  a material into one mesh takes the garden from 62 calls to about 10
 *  and the studio from 123 to a handful per stage, with no visual change.
 *  Geometry is baked into the target group's space, so the studio still
 *  moves with its anchor.
 * ------------------------------------------------------------------ */
const _inv = new THREE.Matrix4();
function mergeByMaterial(roots, target) {
  target.updateWorldMatrix(true, false);
  _inv.copy(target.matrixWorld).invert();
  const buckets = new Map();
  for (const root of roots) {
    root.updateWorldMatrix(true, true);
    root.traverse(o => {
      if (!o.isMesh) return;
      const g = o.geometry.clone();
      g.applyMatrix4(new THREE.Matrix4().multiplyMatrices(_inv, o.matrixWorld));
      if (!g.attributes.normal) g.computeVertexNormals();
      if (!g.attributes.uv) g.setAttribute("uv", new THREE.BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
      if (!g.attributes.uv1) g.setAttribute("uv1", g.attributes.uv);
      for (const name of Object.keys(g.attributes)) {
        if (!["position", "normal", "uv", "uv1"].includes(name)) g.deleteAttribute(name);
      }
      if (!buckets.has(o.material)) buckets.set(o.material, []);
      buckets.get(o.material).push(g);
    });
  }
  let made = 0;
  for (const [mat, geos] of buckets) {
    const allIndexed = geos.every(g => g.index);
    const parts = allIndexed ? geos : geos.map(g => g.index ? g.toNonIndexed() : g);
    const merged = mergeGeometries(parts, false);
    if (!merged) { console.warn("merge failed for a material; leaving its parts unmerged"); continue; }
    const m = new THREE.Mesh(merged, mat);
    m.castShadow = true;
    m.receiveShadow = true;
    m.name = `merged_${made}`;
    target.add(m);
    made++;
  }
  for (const root of roots) root.removeFromParent();
  return made;
}

let loader = null;
export function gltf() {
  if (!loader) {
    const draco = new DRACOLoader();
    draco.setDecoderPath("https://cdn.jsdelivr.net/npm/three@0.185.0/examples/jsm/libs/draco/");
    loader = new GLTFLoader().setDRACOLoader(draco);
  }
  return loader;
}

export function installStudio(stageGroups, mats, onReady) {
  const flat = (colour, extra = {}) =>
    new THREE.MeshStandardMaterial({ color: colour, roughness: 0.75, metalness: 0, ...extra });

  const M = {
    clad:     flat(0xc9c5bb, { roughness: 0.52 }),
    trim:     flat(0xdedacf, { roughness: 0.45 }),
    inner:    flat(0xe9e6de, { roughness: 0.7 }),
    ceiling:  flat(0xf2efe8, { roughness: 0.8, envMapIntensity: 0.9 }),
    timber:   flat(COLOURS.timber, { roughness: 0.82 }),
    metal:    flat(0x33363b, { roughness: 0.34, metalness: 0.55 }),
    frameDark:flat(0x26292d, { roughness: 0.3, metalness: 0.8 }),
    worktop:  flat(0x2b2e31, { roughness: 0.3 }),
    fitout:   flat(0xe4e0d6, { roughness: 0.55 }),
    steel:    flat(0xb9bcc0, { roughness: 0.22, metalness: 0.9 }),
    glass:    new THREE.MeshStandardMaterial({
                color: 0x0a0d10, roughness: 0.03, metalness: 0.05,
                transparent: true, opacity: 0.5, envMapIntensity: 1.2,
                side: THREE.DoubleSide
              })
  };
  for (const k of ["inner", "fitout", "worktop"]) { M[k].envMapIntensity = 0.7; M[k].lightMapIntensity = 1.35; }

  for (const [k, m] of Object.entries(M)) if (k !== "glass" && k !== "ceiling") applyBakedLight(m, 1.0);
  for (const k of ["inner", "fitout", "worktop"]) { M[k].envMapIntensity = 0.7; M[k].lightMapIntensity = 1.35; }

  /* Longest match wins, so Fit_worktop beats Fit_. */
  const RULES = [
    ["_glass", M.glass],
    ["Fit_worktop", M.worktop], ["Fit_splashback", M.trim],
    ["Fit_sink", M.steel], ["Fit_tap", M.steel],
    ["Fit_floor", () => litCopy(mats.concrete)], ["Fit_", M.fitout],
    ["Deck_", () => litCopy(mats.deck)],
    ["Slab", () => litCopy(mats.concrete)],
    ["Frame_", M.timber],
    ["Clad_", M.clad],
    ["Trim_", M.trim], ["Fascia_", M.trim],
    ["Roof", M.metal], ["Gutter", M.metal], ["Downpipe", M.metal],
    ["_head", M.frameDark], ["_sill", M.frameDark], ["_jamb", M.frameDark],
    ["_handle", M.steel],
    ["Ceiling", M.ceiling],            // added after the bake; lit by sky until the next one
    ["Frame_header", M.timber], ["Frame_trimmer", M.timber],
    ["Wall_", M.inner]
  ].sort((a, b) => b[0].length - a[0].length);

  function materialFor(name) {
    for (const [key, m] of RULES) {
      if (name.includes(key)) return typeof m === "function" ? m() : m;
    }
    return M.inner;
  }

  gltf().load(`assets/models/studio.glb?v=${BUILD}`, gltf => {
    let placed = 0;
    for (const [nodeName, stageIndex] of Object.entries(STAGE_NODES)) {
      const node = gltf.scene.getObjectByName(nodeName);
      if (!node) continue;
      for (const child of [...node.children]) {
        child.traverse(o => {
          if (!o.isMesh) return;
          o.material = materialFor(o.name);
          o.castShadow = true;
          o.receiveShadow = true;
          /* the bake will want a second UV set; the export has one set,
             so point uv1 at it now rather than discovering it later */
          if (o.geometry.attributes.uv && !o.geometry.attributes.uv1) {
            o.geometry.setAttribute("uv1", o.geometry.attributes.uv);
          }
        });
        child.userData.fromGLB = true;
        stageGroups[stageIndex].add(child);
        placed++;
      }
    }
    for (const [nodeName, stageIndex] of Object.entries(STAGE_NODES)) {
      const g = stageGroups[stageIndex];
      const imported = g.children.filter(c => c.userData.fromGLB);
      if (imported.length) mergeByMaterial(imported, g);
    }
    onReady(placed);
  });
}


/* ------------------------------------------------------------------ *
 *  The garden: house, fences, paving, shed and trees, all from the
 *  same master model. The viewer keeps the ground, the grass and the
 *  hedge, because those want tuning per quality tier.
 * ------------------------------------------------------------------ */
export function installGarden(parent, mats, onReady) {
  const flat = (colour, extra = {}) =>
    new THREE.MeshStandardMaterial({ color: colour, roughness: 0.8, metalness: 0, ...extra });

  const G = {
    bark:    flat(0x4a3a2c, { roughness: 0.95 }),
    leaf:    addWind(flat(0x2f5520, { roughness: 0.78 }), { strength: 0.06, speed: 0.9, height: 5.0 }),
    trim:    flat(0xdedacf, { roughness: 0.45 }),
    dark:    flat(0x26292d, { roughness: 0.3, metalness: 0.8 }),
    roof:    flat(0x33363b, { roughness: 0.35, metalness: 0.5 }),
    glass:   new THREE.MeshStandardMaterial({
               color: 0x0a0d10, roughness: 0.04, metalness: 0.05,
               transparent: true, opacity: 0.55, envMapIntensity: 1.2
             })
  };
  const treeLeaf = foliageMaterial({ tint: 0xe2ecd0, strength: 0.06, speed: 0.9, height: 5.5 });
  const shrubLeaf = foliageMaterial({ tint: 0xd6e2c2, strength: 0.03, speed: 1.1, height: 1.4 });

  for (const [k, m] of Object.entries(G)) {
    if (k === "leaf" || k === "bark" || k === "glass") continue;
    applyBakedLight(m, 1.0);
  }

  const RULES = [
    ["_leaves", G.leaf], ["Shrub_", G.leaf],
    ["Tree_", G.bark],
    ["_glass", G.glass],
    ["House_mass", () => litCopy(mats.brick)],
    ["House_roof", G.roof], ["House_gutter", G.roof], ["House_downpipe", G.roof],
    ["House_fascia", G.trim],
    ["House_bin", () => litCopy(mats.fence)],
    ["House_door", G.dark],
    ["_reveal", G.trim], ["_sill", G.trim], ["_mullion", G.dark], ["_frame", G.dark],
    ["Patio_", () => litCopy(mats.paving)], ["Path_", () => litCopy(mats.paving)],
    ["Fence_", () => litCopy(mats.fence)], ["Shed_", () => litCopy(mats.fence)]
  ].sort((a, b) => b[0].length - a[0].length);

  const materialFor = name => {
    for (const [key, m] of RULES) {
      if (name.includes(key)) return typeof m === "function" ? m() : m;
    }
    return G.trim;
  };

  gltf().load(`assets/models/garden.glb?v=${BUILD}`, g => {
    let n = 0;
    const treePts = [], shrubPts = [];
    for (const child of [...g.scene.children]) {
      const nm = child.name || "";
      if (nm.startsWith("Tree_")) continue;                 // scanned trees stand here now (vegetation.js)
      if (nm.startsWith("Shrub_")) {
        shrubPts.push(...samplePoints(child, 6, parent));
        continue;
      }
      child.traverse(o => {
        if (!o.isMesh) return;
        o.material = materialFor(o.name);
        o.castShadow = true;
        o.receiveShadow = true;
        if (o.geometry.attributes.uv && !o.geometry.attributes.uv1) {
          o.geometry.setAttribute("uv1", o.geometry.attributes.uv);
        }
        n++;
      });
      parent.add(child);
      child.userData.fromGLB = true;
    }
    const imported = parent.children.filter(c => c.userData.fromGLB);
    if (imported.length) mergeByMaterial(imported, parent);
    if (treePts.length) parent.add(cardCluster(treePts, { size: 1.0, material: treeLeaf }));
    if (shrubPts.length) parent.add(cardCluster(shrubPts, { size: 0.42, material: shrubLeaf }));
    onReady(n + treePts.length + shrubPts.length);
  });
}
