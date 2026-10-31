import * as THREE from "three";
import { gltf } from "./studio.js?v=28d436e-0920";
import { BUILD } from "./config.js?v=28d436e-0920";

/* ------------------------------------------------------------------ *
 *  A real site. `?site=<name>` loads assets/sites/<name>/site.glb — a
 *  photogrammetry mesh of the client's actual garden, aligned and
 *  scaled in Blender — in place of the fictional garden. The scan's
 *  texture already carries the light it was shot in, so it is drawn
 *  unlit: shading it again would double the shadows. Everything
 *  modelled (the studio, new planting) still sits in the same world
 *  and takes the sky and sun as before.
 *
 *  site.json beside it: { "start": {"x":0,"z":0,"yaw":0}, "name": "…" }
 * ------------------------------------------------------------------ */
export async function installSite(scene, world, player, name) {
  const base = `assets/sites/${name}`;
  let meta = {};
  try { meta = await (await fetch(`${base}/site.json?v=${BUILD}`)).json(); } catch (_) {}

  world.existing.visible = false;            // the fictional garden steps aside
  world.obstacles.length = 0;                // the scan has no collision yet; walk freely

  const g = await new Promise((res, rej) => gltf().load(`${base}/site.glb?v=${BUILD}`, res, undefined, rej));
  const root = g.scene;
  root.name = `Site:${name}`;
  let tris = 0;
  root.traverse(o => {
    if (!o.isMesh) return;
    const src = o.material;
    const m = new THREE.MeshBasicMaterial({ map: src.map || null, color: src.map ? 0xffffff : 0x9a9a9a });
    if (m.map) { m.map.colorSpace = THREE.SRGBColorSpace; m.map.anisotropy = 8; }
    m.side = THREE.DoubleSide;
    o.material = m;
    o.receiveShadow = true;                  // modelled things still drop a shadow onto it
    o.castShadow = false;
    tris += (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3;
  });
  scene.add(root);

  if (meta.start) {
    player.position.set(meta.start.x ?? 0, 0, meta.start.z ?? 0);
    player.rotation.y = THREE.MathUtils.degToRad(meta.start.yaw ?? 0);
  }
  console.info(`site ${name}: ${Math.round(tris).toLocaleString()} triangles`);
  return { root, meta, triangles: tris };
}
