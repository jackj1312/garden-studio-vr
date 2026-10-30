import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { COLOURS } from "./config.js";

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

export function installStudio(stageGroups, mats, onReady) {
  const flat = (colour, extra = {}) =>
    new THREE.MeshStandardMaterial({ color: colour, roughness: 0.75, metalness: 0, ...extra });

  const M = {
    clad:     flat(0xc9c5bb, { roughness: 0.52 }),
    trim:     flat(0xdedacf, { roughness: 0.45 }),
    inner:    flat(0xe9e6de, { roughness: 0.7 }),
    timber:   flat(COLOURS.timber, { roughness: 0.82 }),
    metal:    flat(0x33363b, { roughness: 0.34, metalness: 0.55 }),
    frameDark:flat(0x26292d, { roughness: 0.3, metalness: 0.8 }),
    worktop:  flat(0x2b2e31, { roughness: 0.3 }),
    fitout:   flat(0xe4e0d6, { roughness: 0.55 }),
    steel:    flat(0xb9bcc0, { roughness: 0.22, metalness: 0.9 }),
    glass:    new THREE.MeshStandardMaterial({
                color: 0xaecad6, roughness: 0.05, metalness: 0.1,
                transparent: true, opacity: 0.28, envMapIntensity: 2.6,
                side: THREE.DoubleSide
              })
  };

  /* Longest match wins, so Fit_worktop beats Fit_. */
  const RULES = [
    ["_glass", M.glass],
    ["Fit_worktop", M.worktop], ["Fit_splashback", M.trim],
    ["Fit_sink", M.steel], ["Fit_tap", M.steel],
    ["Fit_floor", () => mats.concrete], ["Fit_", M.fitout],
    ["Deck_", () => mats.deck],
    ["Slab", () => mats.concrete],
    ["Frame_", M.timber],
    ["Clad_", M.clad],
    ["Trim_", M.trim], ["Fascia_", M.trim],
    ["Roof", M.metal], ["Gutter", M.metal], ["Downpipe", M.metal],
    ["_head", M.frameDark], ["_sill", M.frameDark], ["_jamb", M.frameDark],
    ["_handle", M.steel],
    ["Wall_", M.inner]
  ].sort((a, b) => b[0].length - a[0].length);

  function materialFor(name) {
    for (const [key, m] of RULES) {
      if (name.includes(key)) return typeof m === "function" ? m() : m;
    }
    return M.inner;
  }

  new GLTFLoader().load("assets/models/studio.glb", gltf => {
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
        stageGroups[stageIndex].add(child);
        placed++;
      }
    }
    onReady(placed);
  });
}
