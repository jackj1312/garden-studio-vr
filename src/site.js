import * as THREE from "three";
import { gltf, mergeByMaterial } from "./studio.js?v=a3c7fc9-1326";
import { makeGrass } from "./materials.js?v=a3c7fc9-1326";
import { BUILD } from "./config.js?v=a3c7fc9-1326";

/* ------------------------------------------------------------------ *
 *  A real site. `?site=<name>` loads assets/sites/<name>/site.glb — a
 *  photogrammetry mesh of the client's actual garden, aligned and
 *  scaled in Blender — in place of the fictional garden. The scan's
 *  texture already carries the light it was shot in, so it is drawn
 *  unlit: shading it again would double the shadows. Everything
 *  modelled (the studio, new planting) still sits in the same world
 *  and takes the sky and sun as before.
 *
 *  site.json beside it: { "start": {"x":0,"z":0,"yaw":0}, "name": "…",
 *  "glb": "model.glb", "lit": true }  — lit: a modelled site, drawn with
 *  its own materials under the scene's sun and sky, not a scan
 * ------------------------------------------------------------------ */
export async function installSite(scene, world, player, name) {
  const base = `assets/sites/${name}`;
  let meta = {};
  try { meta = await (await fetch(`${base}/site.json?v=${BUILD}`)).json(); } catch (_) {}

  world.existing.visible = false;            // the fictional garden steps aside
  world.obstacles.length = 0;                // the demo garden's collision does not apply here
  for (const o of meta.obstacles || []) {     // the site's own: boxes and circles in viewer coordinates
    world.obstacles.push(o.r ? { kind: "circle", cx: o.x, cz: o.z, r: o.r, from: 1 }
                             : { kind: "box", cx: o.x, cz: o.z, hw: o.hw, hd: o.hd, rot: 0, from: 1 });
  }

  // the headset gets the lighter cut when the site has one
  const isQuest = /OculusBrowser|Quest/i.test(navigator.userAgent);
  const file = (isQuest && meta.glbQuest) || meta.glb || "site.glb";
  if (isQuest && meta.grassPerM2Quest) meta.grassPerM2 = meta.grassPerM2Quest;
  const g = await new Promise((res, rej) => gltf().load(`${base}/${file}?v=${BUILD}`, res, undefined, rej));
  const root = g.scene;
  root.name = `Site:${name}`;
  let tris = 0;
  root.traverse(o => {
    if (!o.isMesh) return;
    tris += (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3;
    if (meta.lit) {
      /* a modelled site: keep its materials, light it like everything else */
      const m = o.material;
      if (m.map) { m.map.anisotropy = isQuest ? 2 : 8; }
      if (m.alphaTest > 0 || /leaves|leaf/i.test(m.name)) {
        // cut-out leaves: sorted by depth like solids, so a merged canopy never flickers
        m.alphaTest = Math.max(m.alphaTest, 0.5);
        m.transparent = false; m.depthWrite = true; m.alphaToCoverage = true;
        m.side = THREE.DoubleSide;
      } else if (!/VertexPlant|glass/i.test(m.name) && !m.transparent) {
        m.side = THREE.FrontSide;                  // Blender exports everything double-sided
      }
      o.castShadow = !m.transparent;
      o.receiveShadow = true;
      m.envMapIntensity = 0.9;
      return;
    }
    /* a scan: its texture already carries the light it was shot in, so draw it unlit */
    const src = o.material;
    const m = new THREE.MeshBasicMaterial({ map: src.map || null, color: src.map ? 0xffffff : 0x9a9a9a });
    if (m.map) { m.map.colorSpace = THREE.SRGBColorSpace; m.map.anisotropy = 8; }
    m.side = THREE.DoubleSide;
    o.material = m;
    o.receiveShadow = true;                  // modelled things still drop a shadow onto it
    o.castShadow = false;
  });
  if (meta.lit) {
    // hundreds of small parts: one draw call per material instead
    const ground = new THREE.Mesh(new THREE.CircleGeometry(160, 48).rotateX(-Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: 0x4b4a3c, roughness: 1 }));
    ground.position.y = -0.08;
    ground.receiveShadow = true;
    scene.add(ground);
    const holder = new THREE.Group();
    holder.name = root.name;
    // grass on the lawn's real shape: rasterise the lawn triangles to a 10 cm grid
    const lawnTris = [];
    root.updateWorldMatrix(true, true);
    root.traverse(o => {
      if (!o.isMesh || !/lawn/i.test(o.material.name)) return;
      const p = o.geometry.attributes.position, idx = o.geometry.index;
      const v = i => new THREE.Vector3().fromBufferAttribute(p, i).applyMatrix4(o.matrixWorld);
      const n = idx ? idx.count : p.count;
      for (let t = 0; t < n; t += 3) {
        const a = v(idx ? idx.getX(t) : t), b = v(idx ? idx.getX(t + 1) : t + 1), c = v(idx ? idx.getX(t + 2) : t + 2);
        if (Math.abs((b.x - a.x) * (c.z - a.z) - (c.x - a.x) * (b.z - a.z)) > 1e-6) lawnTris.push([a, b, c]);
      }
    });
    if (lawnTris.length) {
      const box = new THREE.Box3();
      lawnTris.forEach(t => t.forEach(p => box.expandByPoint(p)));
      const cell = 0.1, W = Math.ceil((box.max.x - box.min.x) / cell), D = Math.ceil((box.max.z - box.min.z) / cell);
      const grid = new Uint8Array(W * D);
      let area = 0;
      for (const [a, b, c] of lawnTris) {
        area += Math.abs((b.x - a.x) * (c.z - a.z) - (c.x - a.x) * (b.z - a.z)) / 2;
        const x0 = Math.floor((Math.min(a.x, b.x, c.x) - box.min.x) / cell), x1 = Math.ceil((Math.max(a.x, b.x, c.x) - box.min.x) / cell);
        const z0 = Math.floor((Math.min(a.z, b.z, c.z) - box.min.z) / cell), z1 = Math.ceil((Math.max(a.z, b.z, c.z) - box.min.z) / cell);
        for (let i = x0; i < x1; i++) for (let j = z0; j < z1; j++) {
          const px = box.min.x + (i + 0.5) * cell, pz = box.min.z + (j + 0.5) * cell;
          const d1 = (px - b.x) * (a.z - b.z) - (a.x - b.x) * (pz - b.z);
          const d2 = (px - c.x) * (b.z - c.z) - (b.x - c.x) * (pz - c.z);
          const d3 = (px - a.x) * (c.z - a.z) - (c.x - a.x) * (pz - a.z);
          if (!((d1 < 0 || d2 < 0 || d3 < 0) && (d1 > 0 || d2 > 0 || d3 > 0))) grid[j * W + i] = 1;
        }
      }
      const accept = (x, z) => {
        const i = Math.floor((x - box.min.x) / cell), j = Math.floor((z - box.min.z) / cell);
        return i >= 0 && j >= 0 && i < W && j < D && grid[j * W + i] === 1;
      };
      const perM2 = meta.grassPerM2 ?? 260;
      const grass = makeGrass({ count: Math.round(area * perM2), width: box.max.x - box.min.x, length: box.max.z - box.min.z,
        centreX: (box.min.x + box.max.x) / 2, centreZ: (box.min.z + box.max.z) / 2, accept });
      grass.name = "Site_grass";
      scene.add(grass);
      console.info(`site lawn ${area.toFixed(1)} m², ${grass.count} grass tufts`);
    }
    mergeByMaterial([root], holder);
    holder.traverse(o => { if (o.isMesh) { o.castShadow = !o.material.transparent; o.receiveShadow = true; } });
    scene.add(holder);
    if (meta.start) {
      player.position.set(meta.start.x ?? 0, 0, meta.start.z ?? 0);
      player.rotation.y = THREE.MathUtils.degToRad(meta.start.yaw ?? 0);
    }
    console.info(`site ${name}: ${Math.round(tris).toLocaleString()} triangles (modelled, lit)`);
    return { root: holder, meta, triangles: tris };
  }
  scene.add(root);

  if (meta.start) {
    player.position.set(meta.start.x ?? 0, 0, meta.start.z ?? 0);
    player.rotation.y = THREE.MathUtils.degToRad(meta.start.yaw ?? 0);
  }
  console.info(`site ${name}: ${Math.round(tris).toLocaleString()} triangles`);
  return { root, meta, triangles: tris };
}
