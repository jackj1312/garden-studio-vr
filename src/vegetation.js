import * as THREE from "three";
import { addWind } from "./wind.js?v=a6c6ab9-0950";
import { gltf } from "./studio.js?v=a6c6ab9-0950";
import { BUILD, SITE } from "./config.js?v=a6c6ab9-0950";

/* ------------------------------------------------------------------ *
 *  Scanned vegetation.
 *
 *  Poly Haven's photogrammetry plants (CC0) replace the drawn leaf
 *  cards. Each plant ships as a GLB with up to three parts, named
 *  <id>_trunk, <id>_branches and <id>_leaves (shrubs and perennials
 *  have a single part). The leaves get a material that lets light
 *  through them and that reads as a volume rather than a bag of
 *  separate cards:
 *
 *  - translucency: sunlight arriving from behind a leaf lights its
 *    front, scaled by how directly it comes through. This is the
 *    single biggest difference between a rendered tree and a game one.
 *  - canopy normals: each leaf's normal is bent towards the direction
 *    from the canopy centre, so the canopy shades like a solid shape
 *    with leaf detail on it, instead of every leaf being lit at random.
 *  - wind, alpha-tested shadows (dappled light under the tree).
 * ------------------------------------------------------------------ */

const sunUniforms = { uTranslucency: { value: 0.55 } };

export function leafMaterial(base, { translucency = 0.55, wind } = {}) {
  const m = base.clone();
  m.side = THREE.DoubleSide;
  m.transparent = false;
  m.alphaTest = 0.5;
  m.alphaToCoverage = true;                                // free with MSAA; ends the leaf sparkle
  m.depthWrite = true;
  m.roughness = Math.max(m.roughness, 0.7);
  m.envMapIntensity = 0.9;
  if (m.map) { m.map.anisotropy = 8; m.map.colorSpace = THREE.SRGBColorSpace; }
  m.onBeforeCompile = shader => {
    shader.uniforms.uTranslucency = { value: translucency };
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\nuniform float uTranslucency;")
      // a back face must keep its bent normal, or every leaf seen from behind flips to speckle
      .replace("float faceDirection = gl_FrontFacing ? 1.0 : - 1.0;", "float faceDirection = 1.0;")
      .replace("#include <lights_fragment_end>", `#include <lights_fragment_end>
        #if NUM_DIR_LIGHTS > 0
        {
          // light through the leaf: strongest when the sun is behind it. directLight
          // holds the sun after the directional loop, shadow already applied, so leaves
          // in the shade of the canopy do not glow.
          vec3 ld = directionalLights[0].direction;
          float through = pow(max(0.0, dot(-geometryNormal, ld)), 1.4);
          reflectedLight.directDiffuse += diffuseColor.rgb * vec3(1.0, 1.05, 0.55) * directLight.color * uTranslucency * through;
        }
        #endif`);
    m.userData.shader = shader;
  };
  m.customProgramCacheKey = () => `leaf-${translucency}`;
  if (wind) addWind(m, wind);
  return m;
}

/* Bend vertex normals towards the direction from the canopy centre.
   Mix 0 keeps the scan's normals, 1 makes a lit sphere; 0.6 reads as a
   tree in daylight. */
export function bendNormals(geometry, amount = 0.6) {
  geometry.computeBoundingSphere();
  const c = geometry.boundingSphere.center;
  const pos = geometry.attributes.position;
  const nrm = geometry.attributes.normal;
  const v = new THREE.Vector3(), n = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).sub(c).normalize();
    n.fromBufferAttribute(nrm, i);
    n.lerp(v, amount).normalize();
    nrm.setXYZ(i, n.x, n.y, n.z);
  }
  nrm.needsUpdate = true;
}

/* Low plants: lean every normal towards straight up, so a mound shades
   like a mound and the top catches the sky. */
export function bendNormalsUp(geometry, amount = 0.4) {
  const nrm = geometry.attributes.normal;
  const n = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);
  for (let i = 0; i < nrm.count; i++) {
    n.fromBufferAttribute(nrm, i).lerp(up, amount).normalize();
    nrm.setXYZ(i, n.x, n.y, n.z);
  }
  nrm.needsUpdate = true;
}

/* Prepare a loaded plant: find its parts by name, give the leaves the
   leaf material, make everything cast and receive shadows. Returns the
   root with userData.parts for callers that want to swap LODs. */
export function preparePlant(root, { id, translucency, bend = 0.6, wind = { strength: 0.03, speed: 0.9, height: 4 } } = {}) {
  const parts = {};
  root.traverse(o => {
    if (!o.isMesh) return;
    o.castShadow = true;
    o.receiveShadow = true;
    const name = o.name.toLowerCase();
    const isLeaf = name.includes("leaves") || name.includes("leaf") || (!name.includes("trunk") && !name.includes("branch"));
    if (isLeaf) {
      if (bend > 0) bendNormals(o.geometry, bend);
      o.material = leafMaterial(o.material, { translucency, wind });
      parts.leaves = o;
    } else {
      o.material.side = THREE.FrontSide;
      if (o.material.map) o.material.map.anisotropy = 8;
      parts[name.includes("trunk") ? "trunk" : "branches"] = o;
    }
  });
  root.userData.parts = parts;
  root.userData.id = id;
  return root;
}

/* ------------------------------------------------------------------ *
 *  The garden's trees. Two detail levels of the same scan:
 *    q — Quest: ~85k triangles a tree, leaves collapsed to 8%
 *    d — desktop: ~250k, leaves at 30%
 *  Both look the same from two metres; the difference is the silhouette
 *  of the nearest leaves. The headset gets q, desktop gets d, and either
 *  can be swapped in later without reloading the scene.
 * ------------------------------------------------------------------ */
const TREES = {
  island_tree_02: { scanHeight: 3.41, windHeight: 3.4 },
  island_tree_01: { scanHeight: 5.03, windHeight: 5.0 }
};
const treeCache = new Map();
let treeGroup = null, treeDetail = null;

function loadTree(species, detail) {
  const key = `${species}:${detail}`;
  if (treeCache.has(key)) return treeCache.get(key);
  const p = new Promise((resolve, reject) => {
    gltf().load(`assets/models/veg/${species}_${detail}.glb?v=${BUILD}`, g => resolve(preparePlant(g.scene, {
      id: species, translucency: 0.5, bend: 0.55,
      wind: { strength: 0.025, speed: 0.8, height: TREES[species].windHeight }
    })), undefined, reject);
  });
  treeCache.set(key, p);
  return p;
}

export function installTrees(parent, detail, onReady) {
  treeGroup = new THREE.Group();
  treeGroup.name = "Trees";
  parent.add(treeGroup);
  return setTreeDetail(detail).then(() => onReady?.(SITE.trees.length));
}

export async function setTreeDetail(detail) {
  if (!treeGroup || detail === treeDetail) return;
  const [olive, big] = await Promise.all([loadTree("island_tree_02", detail), loadTree("island_tree_01", "q")]);
  if (detail === treeDetail) return;                       // a later call won
  treeDetail = detail;
  treeGroup.clear();
  const place = (proto, species, t, yaw) => {
    const tree = proto.clone(true);
    tree.scale.setScalar(t.height / TREES[species].scanHeight);
    tree.position.set(t.x, -0.02, t.z);
    tree.rotation.y = yaw;
    treeGroup.add(tree);
  };
  // one olive as the feature, the bigger scan as the second garden tree, so they are not twins
  place(olive, "island_tree_02", SITE.trees[1], 0.6);
  place(big, "island_tree_01", SITE.trees[0], 2.7);
  // the neighbours' trees: always the Quest version, the haze does the rest
  SITE.neighbourTrees.forEach((t, i) => place(big, "island_tree_01", t, i * 1.9));
}

/* ------------------------------------------------------------------ *
 *  Planting. The benchmark film has no bare soil: every bed is three
 *  layers deep. Ten scanned species, each drawn as ONE instanced mesh
 *  (one draw call a species, whatever the count), laid out by a seeded
 *  generator so the garden is the same every visit.
 *    back row   shrubs, 0.8–1.3 m, against the fence
 *    middle     ferns and periwinkle
 *    front      meadow grasses and celandine spilling onto the edge
 * ------------------------------------------------------------------ */
const SPECIES = ["shrub_01", "shrub_02", "shrub_03", "shrub_04", "fern_02", "grass_medium_01", "grass_medium_02",
                 "periwinkle_plant", "celandine_01", "moss_01",
                 // built in Blender from vertex-coloured geometry: the UK border palette no scan library has
                 "lavender", "salvia", "stipa", "allium", "box_ball"];
const PLANT_FILES = { q: "assets/models/veg/plants_q.glb", d: "assets/models/veg/plants_d.glb" };
const PERENNIALS = "assets/models/veg/perennials.glb";
const plantCache = new Map();
let plantGroup = null, plantDetail = null, plantInfo = null;

function seeded(seed) {
  let s = seed >>> 0;
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
}

function loadGLB(url) {
  return new Promise((resolve, reject) => gltf().load(`${url}?v=${BUILD}`, resolve, undefined, reject));
}

function loadPlants(detail) {
  if (plantCache.has(detail)) return plantCache.get(detail);
  const p = Promise.all([loadGLB(PLANT_FILES[detail]), loadGLB(PERENNIALS)]).then(scenes => {
    const species = {};
    for (const g of scenes) {
      g.scene.traverse(o => {
        if (!o.isMesh) return;
        o.geometry.computeBoundingBox();
        const bb = o.geometry.boundingBox;
        const height = bb.max.y - bb.min.y, radius = Math.max(bb.max.x - bb.min.x, bb.max.z - bb.min.z) / 2;
        bendNormalsUp(o.geometry, 0.4);
        const built = !o.material.map;                         // the vertex-coloured perennials: no texture, pale in full sun
        o.material = leafMaterial(o.material, { translucency: built ? 0.22 : 0.45, wind: { strength: 0.02, speed: 1.1, height: Math.max(0.2, height) } });
        if (built) { o.material.color.setScalar(0.72); o.material.roughness = 0.85; o.material.envMapIntensity = 0.5; }
        // three.js strips the dot from Blender's ".001" suffix, so match on the prefix
        const key = SPECIES.find(n => o.name.startsWith(n));
        if (!key) { console.warn("unexpected plant mesh", o.name); return; }
        species[key] = o;
        plantInfo[key] ??= { height, radius };               // the built perennials are not in plants.json
      });
    }
    return species;
  });
  plantCache.set(detail, p);
  return p;
}

/* Each scan has its own size, so a species is placed by the height it
   should stand at, not by a raw scale. Rows: back (tall, by the fence),
   middle, front (low, spilling over the edge). */
/* The palette from the benchmark film and from Jack's own planting plan
   (lavender edge, salvias, grasses): perennials in drifts, scans as the
   structural shrubs and the shade layer. */
const ROLE = {
  back:   [["shrub_02", 1.1, 1.5], ["box_ball", 0.6, 0.8], ["allium", 0.75, 0.95], ["salvia", 0.55, 0.7], ["periwinkle_plant", 0.55, 0.75]],
  middle: [["salvia", 0.45, 0.6], ["stipa", 0.4, 0.55], ["allium", 0.7, 0.9], ["fern_02", 0.45, 0.6], ["box_ball", 0.45, 0.6], ["shrub_03", 0.45, 0.6]],
  front:  [["lavender", 0.4, 0.5], ["lavender", 0.4, 0.5], ["stipa", 0.35, 0.45], ["grass_medium_02", 0.35, 0.5], ["celandine_01", 0.18, 0.26]]
};
const MAX_RADIUS = { back: 0.75, middle: 0.55, front: 0.45 };   // scans sprawl; keep them in the bed
function pick(rnd, role) {
  const [name, h0, h1] = ROLE[role][Math.floor(rnd() * ROLE[role].length)];
  const info = plantInfo?.[name];
  const target = h0 + rnd() * (h1 - h0);
  let scale = info ? target / info.height : 1;
  if (info) scale = Math.min(scale, MAX_RADIUS[role] / info.radius);
  return { name, scale };
}

/* One bed is a rectangle; rows run along its long axis. */
function layoutBeds() {
  const HALF = SITE.garden.width / 2, REAR = -SITE.garden.length;
  const BW = SITE.bedDepth;
  const z0 = -SITE.patio.depth - 0.5, z1 = REAR + BW + 0.3;
  const rnd = seeded(1312);
  const out = [];                                         // { species, x, z, yaw, scale }
  const drop = (species, x, z, scale) => out.push({ species, x, z, yaw: rnd() * Math.PI * 2, scale });
  const bed = (xFence, dir) => {                          // dir: +1 bed grows towards +x
    let drift = { back: null, middle: null, front: null }, left = { back: 0, middle: 0, front: 0 };
    const next = role => {                                 // the same plant 3–6 times, then another: drifts, not a tapestry
      if (left[role] <= 0) { drift[role] = pick(rnd, role); left[role] = 3 + Math.floor(rnd() * 4); }
      left[role]--;
      return { name: drift[role].name, scale: drift[role].scale * (0.9 + rnd() * 0.2) };
    };
    for (let z = z0; z > z1; z -= 0.32 + rnd() * 0.12) {
      const back = xFence + dir * (0.18 + rnd() * 0.12);
      const mid  = xFence + dir * (BW * 0.5 + (rnd() - 0.5) * 0.2);
      const front = xFence + dir * (BW - 0.12 - rnd() * 0.15);
      let c = next("back");   drop(c.name, back, z, c.scale);
      c = next("middle");     drop(c.name, mid, z + 0.15, c.scale);
      c = next("front");      drop(c.name, front, z - 0.05, c.scale);
    }
  };
  bed(-HALF + 0.08, +1);
  bed(HALF - 0.08, -1);
  // rear bed, in front of the back fence
  for (let x = -HALF + 0.5; x < HALF - 0.4; x += 0.38 + rnd() * 0.15) {
    let c = pick(rnd, "back");   drop(c.name, x, REAR + 0.3 + rnd() * 0.15, c.scale);
    c = pick(rnd, "middle");     drop(c.name, x + 0.2, REAR + BW * 0.6 + rnd() * 0.2, c.scale);
    if (rnd() < 0.7) { c = pick(rnd, "front"); drop(c.name, x + 0.35, REAR + BW - 0.1, c.scale); }
  }
  return out;
}

export function installPlanting(parent, detail, onReady) {
  plantGroup = new THREE.Group();
  plantGroup.name = "Planting";
  parent.add(plantGroup);
  return setPlantDetail(detail).then(n => onReady?.(n));
}

export async function setPlantDetail(detail) {
  if (!plantGroup || detail === plantDetail) return 0;
  if (!plantInfo) plantInfo = await (await fetch(`assets/models/veg/plants.json?v=${BUILD}`)).json().catch(() => ({}));
  const species = await loadPlants(detail);
  if (detail === plantDetail) return 0;
  plantDetail = detail;
  plantGroup.clear();
  const items = layoutBeds();
  const byName = {};
  for (const it of items) (byName[it.species] ??= []).push(it);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), p = new THREE.Vector3(), s = new THREE.Vector3();
  let n = 0;
  for (const [name, list] of Object.entries(byName)) {
    const src = species[name];
    if (!src) { console.warn("no scanned plant named", name); continue; }
    const mesh = new THREE.InstancedMesh(src.geometry, src.material, list.length);
    mesh.name = name;
    list.forEach((it, i) => {
      q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), it.yaw);
      p.set(it.x, -0.01, it.z);
      s.setScalar(it.scale);
      m.compose(p, q, s);
      mesh.setMatrixAt(i, m);
    });
    mesh.instanceMatrix.needsUpdate = true;
    // no two plants of a species the same colour: a little hue drift, a little less saturation
    const col = new THREE.Color();
    list.forEach((it, i) => {
      col.setHSL(0.28 + (((it.yaw * 7.3) % 1) - 0.5) * 0.05, 0.42, 0.52 + (((it.yaw * 3.1) % 1) - 0.5) * 0.12);
      mesh.setColorAt(i, col);
    });
    mesh.instanceColor.needsUpdate = true;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.frustumCulled = true;
    plantGroup.add(mesh);
    n += list.length;
  }
  return n;
}
