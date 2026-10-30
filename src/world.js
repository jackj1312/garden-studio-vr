import * as THREE from "three";
import { SITE, STUDIO, HALF, REAR, VARIANTS, COLOURS } from "./config.js";
import { boxGeo, groundGeo, makeGrass } from "./materials.js";

/* ------------------------------------------------------------------ *
 *  Helpers. y is always the bottom of the thing, which is how you
 *  actually think about a building.
 * ------------------------------------------------------------------ */
function block(parent, mat, w, h, d, x, y, z, opts = {}) {
  const tile = opts.tile ?? mat.userData.tile ?? 1;
  const m = new THREE.Mesh(boxGeo(w, h, d, tile, opts.uvOffset), mat);
  m.position.set(x, y + h / 2, z);
  if (opts.ry) m.rotation.y = opts.ry;
  m.castShadow = opts.shadow !== false;
  m.receiveShadow = true;
  parent.add(m);
  return m;
}

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
    timber:   flat(COLOURS.timber, { roughness: 0.85 }),
    roofing:  flat(COLOURS.roofing, { roughness: 0.5, metalness: 0.25 }),
    trim:     flat(COLOURS.trim, { roughness: 0.6 }),
    darkTrim: flat(COLOURS.darkTrim, { roughness: 0.45, metalness: 0.2 }),
    soil:     flat(COLOURS.soil, { roughness: 1 }),
    trunk:    flat(COLOURS.trunk, { roughness: 1 }),
    foliage:  flat(COLOURS.foliage, { roughness: 1, flatShading: true }),
    foliage2: flat(COLOURS.foliage2, { roughness: 1, flatShading: true }),
    hedge:    flat(COLOURS.hedge, { roughness: 1 }),
    fitout:   flat(COLOURS.fitout, { roughness: 0.55 }),
    worktop:  flat(COLOURS.worktop, { roughness: 0.35 }),
    glass:    new THREE.MeshStandardMaterial({
                color: COLOURS.glass, roughness: 0.06, metalness: 0.1,
                transparent: true, opacity: 0.32, envMapIntensity: 2.4
              })
  };

  /* ================================================================ *
   *  EXISTING
   * ================================================================ */
  const existing = new THREE.Group();
  existing.name = "EXISTING";
  scene.add(existing);

  // wider ground so the horizon is not a cliff edge
  const apron = new THREE.Mesh(groundGeo(140, 140, mats.grass.userData.tile * 2.5), mats.grass);
  apron.position.y = -0.03;
  apron.receiveShadow = true;
  existing.add(apron);

  const lawn = new THREE.Mesh(
    groundGeo(SITE.garden.width, SITE.garden.length, mats.grass.userData.tile), mats.grass);
  lawn.position.set(0, 0, REAR / 2);
  lawn.receiveShadow = true;
  existing.add(lawn);

  /* ---- house: brick, with reveals, sills and a gutter ---- */
  const house = new THREE.Group();
  existing.add(house);
  const hD = SITE.house.depth, hH = SITE.house.height;
  block(house, mats.brick, SITE.garden.width, hH, hD, 0, 0, hD / 2);

  const win = (w, h, x, y, kind = "glass") => {
    block(house, M.darkTrim, w + 0.1, h + 0.1, 0.1, x, y - 0.05, -0.04);   // frame
    block(house, M[kind], w, h, 0.06, x, y, -0.07);                        // glazing, recessed
    block(house, M.trim, w + 0.16, 0.05, 0.14, x, y - 0.05, -0.06);        // sill
  };
  win(1.6, 1.25, -2.4, 1.0);
  win(2.2, 1.45,  2.1, 0.9);
  win(1.3, 1.2,  -2.0, 3.6);
  win(1.3, 1.2,   2.0, 3.6);
  block(house, M.darkTrim, 1.0, 2.1, 0.12, 0, 0, -0.05);                   // back door
  block(house, M.trim, 1.16, 0.12, 0.2, 0, 2.1, -0.06);                    // door head

  block(house, M.trim, SITE.garden.width + 0.3, 0.22, 0.22, 0, SITE.house.eaves, -0.12);  // fascia
  block(house, M.darkTrim, SITE.garden.width + 0.2, 0.12, 0.12, 0, SITE.house.eaves - 0.16, -0.2); // gutter
  block(house, M.darkTrim, 0.1, SITE.house.eaves - 0.16, 0.1, HALF - 0.45, 0, -0.18);     // downpipe
  block(house, M.roofing, SITE.garden.width + 0.4, 0.3, hD + 0.3, 0, hH, hD / 2);
  blockBox(0, hD / 2, SITE.garden.width / 2, hD / 2);

  /* ---- boundaries: posts, gravel board, boards, cap rail ---- */
  function fenceRun(x1, z1, x2, z2) {
    const len = Math.hypot(x2 - x1, z2 - z1);
    const ry = Math.atan2(x2 - x1, z2 - z1);
    const g = new THREE.Group();
    g.position.set((x1 + x2) / 2, 0, (z1 + z2) / 2);
    g.rotation.y = ry;
    existing.add(g);
    block(g, mats.fence, 0.05, SITE.fence.height - 0.3, len, 0, 0.25, 0);     // boards
    block(g, M.timber, 0.09, 0.25, len, 0, 0, 0);                             // gravel board
    block(g, M.timber, 0.1, 0.06, len, 0, SITE.fence.height - 0.05, 0);       // cap rail
    const n = Math.max(2, Math.round(len / SITE.fence.postSpacing));
    for (let i = 0; i <= n; i++) {
      block(g, M.timber, 0.1, SITE.fence.height + 0.06, 0.1, 0, 0, -len / 2 + (len * i) / n);
    }
  }
  fenceRun(-HALF, 0, -HALF, REAR);
  fenceRun( HALF, 0,  HALF, REAR);
  fenceRun(-HALF, REAR, HALF, REAR);
  blockBox(-HALF, REAR / 2, 0.14, SITE.garden.length / 2);
  blockBox( HALF, REAR / 2, 0.14, SITE.garden.length / 2);
  blockBox(0, REAR, SITE.garden.width / 2, 0.14);

  /* ---- hard landscaping ---- */
  const patio = new THREE.Mesh(
    groundGeo(SITE.garden.width - SITE.patio.inset * 2, SITE.patio.depth, mats.paving.userData.tile),
    mats.paving);
  patio.position.set(0, 0.02, -SITE.patio.depth / 2);
  patio.receiveShadow = true;
  existing.add(patio);

  const pathLen = SITE.garden.length - SITE.patio.depth;
  const path = new THREE.Mesh(groundGeo(SITE.path.width, pathLen, mats.paving.userData.tile), mats.paving);
  path.position.set(-HALF + SITE.path.offsetFromWest, 0.015, -SITE.patio.depth - pathLen / 2);
  path.receiveShadow = true;
  existing.add(path);

  /* ---- hedge: three offset masses so it is not a green brick ---- */
  const hedge = new THREE.Group();
  existing.add(hedge);
  for (let i = 0; i < 3; i++) {
    const w = (SITE.garden.width - 0.3) / 3;
    block(hedge, M.hedge, w + 0.12, SITE.hedge.height - i % 2 * 0.12, SITE.hedge.depth,
      -SITE.garden.width / 2 + 0.15 + w * (i + 0.5), 0, REAR + SITE.hedge.depth / 2 + 0.1);
  }
  hedge.userData.removeAt = 2;
  removals.push(hedge);

  /* ---- shed ---- */
  const shed = new THREE.Group();
  existing.add(shed);
  const S = SITE.shed;
  block(shed, mats.fence, S.w, S.h, S.d, S.x, 0, S.z);
  block(shed, M.roofing, S.w + 0.2, 0.1, S.d + 0.2, S.x, S.h, S.z);
  block(shed, M.darkTrim, 0.7, 1.75, 0.06, S.x, 0, S.z + S.d / 2 + 0.02);
  blockBox(S.x, S.z, S.w / 2, S.d / 2);

  /* ---- trees ---- */
  for (const t of SITE.trees) {
    const g = new THREE.Group();
    existing.add(g);
    block(g, M.trunk, 0.26, t.height * 0.5, 0.26, t.x, 0, t.z);
    for (let i = 0; i < 2; i++) {
      const b = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.1, t.crown * 1.1, 5), M.trunk);
      b.position.set(t.x + (i ? 0.3 : -0.3), t.height * 0.55, t.z + (i ? -0.2 : 0.25));
      b.rotation.z = (i ? -1 : 1) * 0.5;
      b.castShadow = true;
      g.add(b);
    }
    for (let i = 0; i < 5; i++) {
      const r = t.crown * (0.55 + Math.random() * 0.4);
      const c = new THREE.Mesh(new THREE.IcosahedronGeometry(r, 1), i % 2 ? M.foliage : M.foliage2);
      c.position.set(
        t.x + (Math.random() - 0.5) * t.crown * 1.3,
        t.height * 0.55 + r * 0.5 + Math.random() * t.crown * 0.7,
        t.z + (Math.random() - 0.5) * t.crown * 1.3
      );
      c.castShadow = true;
      g.add(c);
    }
    blockCircle(t.x, t.z, 0.45);
  }

  /* ---- bin store ---- */
  block(existing, M.timber, 1.4, 1.1, 0.8, HALF - 1.1, 0, -1.2);
  blockBox(HALF - 1.1, -1.2, 0.7, 0.4);

  /* ---- grass tufts, kept off the hard surfaces ---- */
  const grass = makeGrass({
    count: quality.grass,
    width: SITE.garden.width - 0.3,
    length: SITE.garden.length - SITE.patio.depth - 0.4,
    centreZ: -SITE.patio.depth - (SITE.garden.length - SITE.patio.depth) / 2,
    avoid: [
      { x: -HALF + SITE.path.offsetFromWest, hw: SITE.path.width / 2 + 0.1, z: -7, hd: 7 },
      { x: S.x, hw: S.w / 2 + 0.2, z: S.z, hd: S.d / 2 + 0.2 }
    ]
  });
  existing.add(grass);

  /* ================================================================ *
   *  THE STUDIO
   * ================================================================ */
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
  const hw = T.w / 2, hd = T.d / 2;
  const fl = T.floorLevel;
  const wt = T.wallThickness;

  /* -- stage 2: cleared ground -- */
  {
    const g = stageGroups[1];
    const strip = new THREE.Mesh(groundGeo(T.w + 1.2, T.d + 1.2, 1.5), M.soil);
    strip.position.y = 0.02;
    strip.receiveShadow = true;
    g.add(strip);
  }

  /* -- stages 3 to 6 come from the Blender master model, loaded as a
        GLB and slotted into these groups. Everything below is the part
        that stays procedural: planting, paths and the practical lights,
        none of which belong in a building model. -- */
  {
    const g = stageGroups[5];
    const hd = T.d / 2;

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

  // the studio only becomes solid once it has walls
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
