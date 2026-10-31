import * as THREE from "three";
import { SITE, STUDIO, HALF, REAR, VARIANTS, COLOURS } from "./config.js?v=9ebc8b7-0213";
import { groundGeo, makeGrass } from "./materials.js?v=9ebc8b7-0213";

/* ------------------------------------------------------------------ *
 *  What stays procedural.
 *
 *  The house, fences, paving, shed and trees now come from the Blender
 *  master as garden.glb. What is left here is the ground, the grass,
 *  the hedge that stage 2 removes, and the planting and lights around
 *  the studio — none of which belong in a building model, and all of
 *  which want tuning at runtime.
 *
 *  Collision lives here too, because the viewer owns movement.
 * ------------------------------------------------------------------ */

const flat = (colour, extra = {}) =>
  new THREE.MeshStandardMaterial({ color: colour, roughness: 0.75, metalness: 0, ...extra });

export function buildWorld(scene, mats, quality) {
  const obstacles = [];
  const removals = [];
  const practicals = [];

  const blockBox = (cx, cz, hw, hd, rot = 0, from = 1) =>
    obstacles.push({ kind: "box", cx, cz, hw, hd, rot, from });
  const blockCircle = (cx, cz, r, from = 1) =>
    obstacles.push({ kind: "circle", cx, cz, r, from });

  const M = {
    hedge:    flat(COLOURS.hedge, { roughness: 1, flatShading: true }),
    foliage:  flat(COLOURS.foliage, { roughness: 1, flatShading: true }),
    foliage2: flat(COLOURS.foliage2, { roughness: 1, flatShading: true })
  };

  const existing = new THREE.Group();
  existing.name = "EXISTING";
  scene.add(existing);

  const apron = new THREE.Mesh(groundGeo(140, 140, mats.grass.userData.tile * 2.5), mats.grass);
  apron.position.y = -0.03;
  apron.receiveShadow = true;
  existing.add(apron);

  /* a dead-flat lawn is the single biggest tell that a ground is a plane;
     a couple of centimetres of undulation is enough to stop the eye reading it */
  const lawnGeo = groundGeo(SITE.garden.width, SITE.garden.length, mats.grass.userData.tile, 40, 70);
  {
    const p = lawnGeo.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), z = p.getZ(i);
      const edge = Math.min(1, (HALF - Math.abs(x)) / 0.6);      // flatten towards the fences
      const h = (Math.sin(x * 1.7) * Math.cos(z * 1.1) * 0.014 + Math.sin(x * 4.3 + z * 3.1) * 0.007) * Math.max(0, edge);
      p.setY(i, h);
    }
    lawnGeo.computeVertexNormals();
  }
  const lawn = new THREE.Mesh(lawnGeo, mats.grass);
  lawn.position.set(0, 0, REAR / 2);
  lawn.receiveShadow = true;
  existing.add(lawn);

  /* bare-earth borders along the fences, the way a tended garden has them */
  const soil = flat(COLOURS.soil, { roughness: 1 });
  const BW = 0.42, bedLen = SITE.garden.length - SITE.patio.depth - 0.3;
  for (const sx of [-1, 1]) {
    const b = new THREE.Mesh(groundGeo(BW, bedLen, 1.0), soil);
    b.position.set(sx * (HALF - BW / 2 - 0.06), 0.009, -SITE.patio.depth - bedLen / 2);
    b.receiveShadow = true;
    existing.add(b);
  }
  const rearBed = new THREE.Mesh(groundGeo(SITE.garden.width - 0.24, BW, 1.0), soil);
  rearBed.position.set(0, 0.009, REAR + BW / 2 + 0.06);
  rearBed.receiveShadow = true;
  existing.add(rearBed);

  /* the hedge is the thing stage 2 takes away */
  const hedge = new THREE.Group();
  existing.add(hedge);
  for (let i = 0; i < 3; i++) {
    const w = (SITE.garden.width - 0.3) / 3;
    const h = SITE.hedge.height - (i % 2) * 0.12;
    const m = new THREE.Mesh(new THREE.BoxGeometry(w + 0.12, h, SITE.hedge.depth), M.hedge);
    m.position.set(-SITE.garden.width / 2 + 0.15 + w * (i + 0.5), h / 2, REAR + SITE.hedge.depth / 2 + 0.1);
    m.castShadow = true;
    m.receiveShadow = true;
    hedge.add(m);
  }
  hedge.userData.removeAt = 2;
  removals.push(hedge);

  /* collision, matching the geometry that arrives in garden.glb */
  blockBox(0, SITE.house.depth / 2, SITE.garden.width / 2, SITE.house.depth / 2);
  blockBox(-HALF, REAR / 2, 0.14, SITE.garden.length / 2);
  blockBox( HALF, REAR / 2, 0.14, SITE.garden.length / 2);
  blockBox(0, REAR, SITE.garden.width / 2, 0.14);
  blockBox(SITE.shed.x, SITE.shed.z, SITE.shed.w / 2, SITE.shed.d / 2);
  blockBox(HALF - 1.1, -1.2, 0.7, 0.45);
  for (const t of SITE.trees) blockCircle(t.x, t.z, 0.45);

  const grass = makeGrass({
    count: quality.grass,
    width: SITE.garden.width - 0.3,
    length: SITE.garden.length - SITE.patio.depth - 0.4,
    centreZ: -SITE.patio.depth - (SITE.garden.length - SITE.patio.depth) / 2,
    avoid: [
      { x: -HALF + SITE.path.offsetFromWest, hw: SITE.path.width / 2 + 0.15, z: -7, hd: 7 },
      { x: SITE.shed.x, hw: SITE.shed.w / 2 + 0.2, z: SITE.shed.z, hd: SITE.shed.d / 2 + 0.2 },
      { x: -HALF + 0.27, hw: 0.3, z: -7, hd: 7 },
      { x:  HALF - 0.27, hw: 0.3, z: -7, hd: 7 },
      { x: 0, hw: HALF, z: REAR + 0.3, hd: 0.32 }
    ]
  });
  existing.add(grass);

  /* ---- studio anchor and stage groups ---- */
  const anchor = new THREE.Group();
  anchor.name = "STUDIO_ANCHOR";
  scene.add(anchor);

  const stageGroups = [];
  for (let i = 0; i < 6; i++) {
    const g = new THREE.Group();
    g.name = `STAGE_${String(i + 1).padStart(2, "0")}`;
    anchor.add(g);
    stageGroups.push(g);
  }

  const T = STUDIO;
  const fl = T.floorLevel;
  const hd = T.d / 2;

  {
    const strip = new THREE.Mesh(groundGeo(T.w + 1.2, T.d + 1.2, 1.5), flat(COLOURS.soil, { roughness: 1 }));
    strip.position.y = 0.02;
    strip.receiveShadow = true;
    stageGroups[1].add(strip);
  }

  {
    const g = stageGroups[5];

    const spur = new THREE.Mesh(groundGeo(1.0, 2.6, mats.paving.userData.tile), mats.paving);
    spur.position.set(-T.w / 2 + 0.4, 0.02, hd + 3.1);
    spur.receiveShadow = true;
    g.add(spur);

    for (const [x, z, r] of [[-2.9, 1.2, 0.55], [-2.4, 2.5, 0.4], [2.9, 1.5, 0.5], [2.4, 2.9, 0.38]]) {
      const b = new THREE.Mesh(new THREE.IcosahedronGeometry(r, 1), Math.random() > 0.5 ? M.foliage : M.foliage2);
      b.position.set(x, r * 0.8, z + hd);
      b.castShadow = true;
      g.add(b);
    }

    const lampX = T.openings.door.x - T.openings.door.w / 2 - 0.28;
    const porch = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.2, 0.08),
      new THREE.MeshStandardMaterial({ color: COLOURS.lampWarm, emissive: COLOURS.lampWarm, emissiveIntensity: 1 }));
    porch.position.set(lampX, fl + 2.05, hd + 0.08);
    g.add(porch);
    const porchLight = new THREE.PointLight(0xffc98a, 0, 6, 2);
    porchLight.position.set(lampX, fl + 1.95, hd + 0.3);
    g.add(porchLight);
    const interior = new THREE.PointLight(0xfff0d4, 0, 7, 2);
    interior.position.set(0, fl + 2.0, 0);
    g.add(interior);
    practicals.push({ light: porchLight, max: 3.5 }, { light: interior, max: 4.5 }, { emissive: porch });
  }

  blockBox(0, 0, T.w / 2 + 0.1, T.d / 2 + 0.1, 0, 5);
  const studioObstacle = obstacles[obstacles.length - 1];

  function applyVariant(key) {
    const v = VARIANTS[key];
    anchor.position.set(v.x, 0, v.z);
    anchor.rotation.y = v.ry;
    studioObstacle.cx = v.x;
    studioObstacle.cz = v.z;
    studioObstacle.rot = v.ry;
  }

  return { existing, anchor, stageGroups, obstacles, removals, practicals, applyVariant };
}
