import * as THREE from "three";
import { SITE, STUDIO, HALF, REAR, VARIANTS, COLOURS } from "./config.js?v=355b2bb-0907";
import { groundGeo, makeGrass } from "./materials.js?v=355b2bb-0907";
import { foliageMaterial, cardCluster, boxPoints, spherePoints } from "./foliage.js?v=355b2bb-0907";

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
  const BW = SITE.bedDepth, bedLen = SITE.garden.length - SITE.patio.depth - 0.3;
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
  const shrubMat = foliageMaterial({ tint: 0xd6e2c2, strength: 0.025, speed: 1.1, height: 1.6 });
  {
    const centre = new THREE.Vector3(0, SITE.hedge.height * 0.52, REAR + SITE.hedge.depth / 2 + 0.12);
    const size = new THREE.Vector3(SITE.garden.width - 0.4, SITE.hedge.height * 0.9, SITE.hedge.depth * 0.9);
    const core = new THREE.Mesh(new THREE.BoxGeometry(size.x - 0.2, size.y - 0.2, size.z - 0.3), M.hedge);
    core.position.copy(centre);
    core.receiveShadow = true;
    hedge.add(core);
    hedge.add(cardCluster(boxPoints(centre, size, 300), { size: 0.5, material: shrubMat, shadow: false }));
  }
  hedge.userData.removeAt = 2;
  removals.push(hedge);

  /* a dark plane just under the slabs turns the bright joint lines into shadow lines */
  const joint = flat(0x2a2622, { roughness: 1 });
  const patioJoint = new THREE.Mesh(groundGeo(SITE.garden.width - SITE.patio.inset * 2, SITE.patio.depth, 1), joint);
  patioJoint.position.set(0, 0.004, -SITE.patio.depth / 2);
  existing.add(patioJoint);
  const pathJoint = new THREE.Mesh(groundGeo(SITE.path.width + 0.04, SITE.garden.length - SITE.patio.depth, 1), joint);
  pathJoint.position.set(-HALF + SITE.path.offsetFromWest, 0.004, -SITE.patio.depth - (SITE.garden.length - SITE.patio.depth) / 2);
  existing.add(pathJoint);

  /* neighbours: the fence is not the edge of the world. Rear elevations
     either side and across the back, plus trees over the fence, are what
     a real terrace garden sees, and what privacy questions are about. */
  {
    const roof = flat(0x3a3d42, { roughness: 0.6 });
    const farBrick = mats.brick.clone(); farBrick.color.setHex(0x7d6a60); farBrick.envMapIntensity = 0.6;
    const win = flat(0x141a20, { roughness: 0.15, metalness: 0.3 });
    const house = (x, z, w, d, h, facing) => {
      const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), farBrick);
      b.position.set(x, h / 2, z); b.castShadow = b.receiveShadow = true; existing.add(b);
      const r = new THREE.Mesh(new THREE.BoxGeometry(w + 0.5, 0.35, d + 0.4), roof);
      r.position.set(x, h + 0.17, z); r.castShadow = true; existing.add(r);
      for (const [wx, wy] of [[-w / 4, 1.1], [w / 4, 1.1], [-w / 4, 3.7], [w / 4, 3.7]]) {
        const g = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 1.2), win);
        g.position.set(x + wx, wy + 0.6, z + facing * (d / 2 + 0.02));
        g.rotation.y = facing > 0 ? 0 : Math.PI;
        existing.add(g);
      }
    };
    house(-SITE.garden.width, SITE.house.depth / 2, SITE.garden.width, SITE.house.depth, SITE.house.height - 0.3, -1);
    house( SITE.garden.width, SITE.house.depth / 2, SITE.garden.width, SITE.house.depth, SITE.house.height + 0.2, -1);
    for (const x of [-SITE.garden.width, 0, SITE.garden.width]) {
      house(x + 0.8, REAR - 18, 7.5, 8, 6.2 + (x === 0 ? 0.4 : 0), 1);
    }
    const far = foliageMaterial({ tint: 0xa9bb90, strength: 0.05, speed: 0.8, height: 7 });
    const bark = flat(0x4a3a2c, { roughness: 1 });
    for (const [x, z, r, h] of [[-5.5, REAR - 3.5, 2.4, 5.2], [1.5, REAR - 5, 2.9, 6.2], [7, REAR - 2.5, 2.0, 4.6], [-9, -6, 2.2, 5.0], [9.5, -9, 2.6, 5.6]]) {
      existing.add(cardCluster(spherePoints(new THREE.Vector3(x, h, z), r, 110), { size: 1.3, material: far, shadow: false }));
      const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.2, h, 7), bark);
      trunk.position.set(x, h / 2, z); existing.add(trunk);
    }
  }

  /* planting comes from vegetation.js (scanned species, instanced).
     Nobody walks through a border, so each bed is solid to the player. */
  {
    const BW = SITE.bedDepth, bedLen = SITE.garden.length - SITE.patio.depth - 0.3;
    for (const sx of [-1, 1]) blockBox(sx * (HALF - BW / 2 - 0.06), -SITE.patio.depth - bedLen / 2, BW / 2, bedLen / 2);
    blockBox(0, REAR + BW / 2 + 0.06, SITE.garden.width / 2 - 0.12, BW / 2);
  }

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
      g.add(cardCluster(spherePoints(new THREE.Vector3(x, r * 0.75, z + hd), r, 70, 0.8), { size: r * 0.55, material: shrubMat }));
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

  /* the studio is only solid once it has walls — and it has a door. Four
     wall segments in anchor space, re-placed whenever the variant moves. */
  const hw = T.w / 2, dr = T.openings.door;
  const leftEnd = dr.x - dr.w / 2 - 0.08, rightStart = dr.x + dr.w / 2 + 0.08;
  const wallLocal = [
    { lx: 0, lz: -hd + 0.06, hw: hw, hd: 0.1 },
    { lx: -hw + 0.06, lz: 0, hw: 0.1, hd: hd },
    { lx:  hw - 0.06, lz: 0, hw: 0.1, hd: hd },
    { lx: (-hw + leftEnd) / 2, lz: hd - 0.06, hw: (leftEnd + hw) / 2, hd: 0.1 },
    { lx: (rightStart + hw) / 2, lz: hd - 0.06, hw: (hw - rightStart) / 2, hd: 0.1 }
  ];
  const wallObs = wallLocal.map(() => { blockBox(0, 0, 1, 1, 0, 5); return obstacles[obstacles.length - 1]; });
  const _p = new THREE.Vector3(), _up = new THREE.Vector3(0, 1, 0);

  function applyVariant(key) {
    const v = VARIANTS[key];
    anchor.position.set(v.x, 0, v.z);
    anchor.rotation.y = v.ry;
    wallLocal.forEach((w, i) => {
      _p.set(w.lx, 0, w.lz).applyAxisAngle(_up, v.ry);
      const o = wallObs[i];
      o.cx = v.x + _p.x; o.cz = v.z + _p.z; o.hw = w.hw; o.hd = w.hd; o.rot = v.ry;
    });
  }

  return { existing, anchor, stageGroups, obstacles, removals, practicals, applyVariant };
}
