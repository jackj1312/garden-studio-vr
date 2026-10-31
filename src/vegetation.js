import * as THREE from "three";
import { addWind } from "./wind.js?v=fc49489-0903";
import { gltf } from "./studio.js?v=fc49489-0903";
import { BUILD, SITE } from "./config.js?v=fc49489-0903";

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
  m.depthWrite = true;
  m.roughness = Math.max(m.roughness, 0.7);
  m.envMapIntensity = 0.6;
  if (m.map) { m.map.anisotropy = 8; m.map.colorSpace = THREE.SRGBColorSpace; }
  const prior = m.onBeforeCompile;
  m.onBeforeCompile = shader => {
    shader.uniforms.uTranslucency = { value: translucency };
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\nuniform float uTranslucency;")
      .replace("#include <lights_fragment_end>", `#include <lights_fragment_end>
        #if NUM_DIR_LIGHTS > 0
        {
          // light through the leaf: strongest when the sun is behind it
          vec3 ld = directionalLights[0].direction;
          float through = pow(max(0.0, dot(-geometryNormal, ld)), 1.4);
          float rim = pow(1.0 - max(0.0, dot(geometryNormal, geometryViewDir)), 2.0) * 0.35;
          reflectedLight.directDiffuse += diffuseColor.rgb * directionalLights[0].color * uTranslucency * (through + rim);
        }
        #endif`);
    material_shader_hook(shader);
    if (prior) prior(shader);
  };
  function material_shader_hook(shader) { m.userData.shader = shader; }
  m.customProgramCacheKey = () => `leaf-${translucency}-${wind ? wind.strength : 0}`;
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
const TREE_FILES = { q: "assets/models/veg/island_tree_02_q.glb", d: "assets/models/veg/island_tree_02_d.glb" };
const treeCache = new Map();
let treeGroup = null, treeDetail = null;

function loadTree(detail) {
  if (treeCache.has(detail)) return treeCache.get(detail);
  const p = new Promise((resolve, reject) => {
    gltf().load(`${TREE_FILES[detail]}?v=${BUILD}`, g => resolve(preparePlant(g.scene, {
      id: "island_tree_02", translucency: 0.5, bend: 0.55,
      wind: { strength: 0.025, speed: 0.8, height: 3.4 }
    })), undefined, reject);
  });
  treeCache.set(detail, p);
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
  const proto = await loadTree(detail);
  if (detail === treeDetail) return;                       // a later call won
  treeDetail = detail;
  treeGroup.clear();
  const scanHeight = 3.41;                                  // island_tree_02 as scanned
  SITE.trees.forEach((t, i) => {
    const tree = proto.clone(true);
    const s = t.height / scanHeight;
    tree.scale.setScalar(s);
    tree.position.set(t.x, -0.02, t.z);
    tree.rotation.y = i * 2.1 + 0.6;
    treeGroup.add(tree);
  });
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
                 "periwinkle_plant", "celandine_01", "moss_01"];
const PLANT_FILES = { q: "assets/models/veg/plants_q.glb", d: "assets/models/veg/plants_d.glb" };
const plantCache = new Map();
let plantGroup = null, plantDetail = null, plantInfo = null;

function seeded(seed) {
  let s = seed >>> 0;
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
}

function loadPlants(detail) {
  if (plantCache.has(detail)) return plantCache.get(detail);
  const p = new Promise((resolve, reject) => {
    gltf().load(`${PLANT_FILES[detail]}?v=${BUILD}`, g => {
      const species = {};
      g.scene.traverse(o => {
        if (!o.isMesh) return;
        o.geometry.computeBoundingBox();
        o.material = leafMaterial(o.material, { translucency: 0.45, wind: { strength: 0.02, speed: 1.1, height: 0.8 } });
        // three.js strips the dot from Blender's ".001" suffix, so match on the prefix
        const key = SPECIES.find(n => o.name.startsWith(n));
        if (key) species[key] = o; else console.warn("unexpected plant mesh", o.name);
      });
      resolve(species);
    }, undefined, reject);
  });
  plantCache.set(detail, p);
  return p;
}

/* Each scan has its own size, so a species is placed by the height it
   should stand at, not by a raw scale. Rows: back (tall, by the fence),
   middle, front (low, spilling over the edge). */
const ROLE = {
  back:   [["shrub_02", 1.1, 1.5], ["periwinkle_plant", 0.55, 0.75], ["fern_02", 0.55, 0.7]],
  middle: [["fern_02", 0.45, 0.6], ["shrub_03", 0.45, 0.6], ["periwinkle_plant", 0.4, 0.55], ["shrub_04", 0.35, 0.5]],
  front:  [["grass_medium_02", 0.35, 0.5], ["celandine_01", 0.18, 0.26], ["grass_medium_01", 0.3, 0.4], ["shrub_01", 0.3, 0.42]]
};
function pick(rnd, role) {
  const [name, h0, h1] = ROLE[role][Math.floor(rnd() * ROLE[role].length)];
  const info = plantInfo?.[name];
  const target = h0 + rnd() * (h1 - h0);
  return { name, scale: info ? target / info.height : 1 };
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
    for (let z = z0; z > z1; z -= 0.55 + rnd() * 0.25) {
      const back = xFence + dir * (0.18 + rnd() * 0.12);
      const mid  = xFence + dir * (BW * 0.5 + (rnd() - 0.5) * 0.2);
      const front = xFence + dir * (BW - 0.12 - rnd() * 0.15);
      let c = pick(rnd, "back");  drop(c.name, back, z, c.scale);
      c = pick(rnd, "middle");    drop(c.name, mid, z + 0.25, c.scale);
      c = pick(rnd, "front");     drop(c.name, front, z - 0.1, c.scale);
      if (rnd() < 0.5) { c = pick(rnd, "front"); drop(c.name, front - dir * 0.25, z + 0.3, c.scale); }
    }
  };
  bed(-HALF + 0.08, +1);
  bed(HALF - 0.08, -1);
  // rear bed, in front of the back fence
  for (let x = -HALF + 0.5; x < HALF - 0.4; x += 0.6 + rnd() * 0.3) {
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
  if (!plantInfo) plantInfo = await (await fetch(`assets/models/veg/plants.json?v=${BUILD}`)).json();
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
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.frustumCulled = true;
    plantGroup.add(mesh);
    n += list.length;
  }
  return n;
}
