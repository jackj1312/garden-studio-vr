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

export function buildWorld(scene, mats) {
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
    count: 14000,
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

  /* -- stage 3: slab and service trench -- */
  {
    const g = stageGroups[2];
    const sl = T.slab;
    block(g, mats.concrete, T.w + sl.oversail, sl.thickness, T.d + sl.oversail, 0, fl - sl.thickness, 0);
    block(g, M.soil, 0.35, 0.12, 3.2, 0, 0, hd + 1.7);
  }

  /* -- stage 4: frame -- */
  {
    const g = stageGroups[3];
    const wh = T.wallHeight;
    for (const z of [-hd, hd]) block(g, M.timber, T.w, 0.1, 0.1, 0, fl, z);
    for (const x of [-hw, hw]) block(g, M.timber, 0.1, 0.1, T.d, x, fl, 0);
    for (const x of [-hw, hw]) for (const z of [-hd, hd])
      block(g, M.timber, 0.12, wh, 0.12, x, fl, z);
    for (let i = 1; i < 7; i++) {
      const x = -hw + (T.w * i) / 7;
      block(g, M.timber, 0.07, wh, 0.07, x, fl, -hd);
      block(g, M.timber, 0.07, wh, 0.07, x, fl, hd);
    }
    for (const z of [-hd, hd]) block(g, M.timber, T.w, 0.14, 0.12, 0, fl + wh, z);
    for (let i = 0; i <= 8; i++) {
      const x = -hw + (T.w * i) / 8;
      block(g, M.timber, 0.07, 0.16, T.d, x, fl + wh + 0.14, 0);
    }
  }

  /* -- stage 5: clad, roofed and glazed -- */
  {
    const g = stageGroups[4];
    const wh = T.wallHeight;
    const o = T.openings;

    // solid walls
    block(g, mats.cladding, wt, wh, T.d, -hw + wt / 2, fl, 0);                 // west
    block(g, mats.cladding, wt, wh, T.d,  hw - wt / 2, fl, 0);                 // east
    // north wall, split around the clerestory
    block(g, mats.cladding, T.w - wt * 2, o.clerestory.sill, wt, 0, fl, -hd + wt / 2);
    block(g, mats.cladding, T.w - wt * 2, wh - o.clerestory.sill - o.clerestory.h, wt,
      0, fl + o.clerestory.sill + o.clerestory.h, -hd + wt / 2);
    const cSide = (T.w - wt * 2 - o.clerestory.w) / 2;
    for (const s of [-1, 1])
      block(g, mats.cladding, cSide, o.clerestory.h, wt,
        s * (o.clerestory.w / 2 + cSide / 2), fl + o.clerestory.sill, -hd + wt / 2);

    // south wall around the door and side light
    const southSolid = [
      { x: -hw + wt / 2 + 0.35, w: 0.7 },
      { x: 0.35, w: 0.6 },
      { x: hw - wt / 2 - 0.25, w: 0.5 }
    ];
    for (const p of southSolid) block(g, mats.cladding, p.w, wh, wt, p.x, fl, hd - wt / 2);
    block(g, mats.cladding, T.w - wt * 2, wh - o.door.h - 0.06, wt, 0, fl + o.door.h + 0.06, hd - wt / 2);

    // corner trims — the correct detail for a boarded cladding, and the
    // thing that stops the corners reading as a mitre that does not exist
    for (const sx of [-1, 1]) {
      block(g, M.trim, 0.06, wh, 0.09, sx * (hw + 0.025), fl, hd - 0.06, { shadow: false });
      block(g, M.trim, 0.09, wh, 0.06, sx * (hw - 0.06), fl, hd + 0.015, { shadow: false });
      block(g, M.trim, 0.06, wh, 0.09, sx * (hw + 0.025), fl, -hd + 0.06, { shadow: false });
    }

    // glazing: door, side light, clerestory, gable vent
    const glaze = (w, h, x, y, z, depth = 0.05) => {
      block(g, M.darkTrim, w + 0.1, h + 0.1, depth + 0.04, x, y - 0.05, z);
      block(g, M.glass, w, h, depth, x, y, z, { shadow: false });
    };
    glaze(o.door.w, o.door.h, o.door.x, fl, hd - wt / 2);
    glaze(o.sideLight.w, o.sideLight.h, o.sideLight.x, fl, hd - wt / 2);
    glaze(o.clerestory.w, o.clerestory.h, o.clerestory.x, fl + o.clerestory.sill, -hd + wt / 2);
    block(g, M.darkTrim, 0.06, o.door.h + 0.08, 0.08, o.door.x - o.door.w / 2, fl, hd - 0.02);

    // mono-pitch roof, falling to the rear, with a real eaves detail
    const roof = new THREE.Group();
    g.add(roof);
    const rl = Math.hypot(T.d + 0.5, T.fallToRear);
    const deck = new THREE.Mesh(boxGeo(T.w + 0.4, 0.1, rl, 1), M.roofing);
    deck.position.set(0, fl + wh + 0.28 - T.fallToRear / 2, -0.05);
    deck.rotation.x = Math.atan2(T.fallToRear, T.d + 0.5);
    deck.castShadow = true; deck.receiveShadow = true;
    roof.add(deck);
    block(g, M.trim, T.w + 0.44, 0.16, 0.08, 0, fl + wh + 0.2, hd + 0.26);        // front fascia
    block(g, M.darkTrim, T.w + 0.44, 0.09, 0.09, 0, fl + wh + 0.12, hd + 0.3);    // gutter
    block(g, M.trim, 0.08, 0.16, T.d + 0.5, hw + 0.2, fl + wh + 0.04, -0.05);     // side fascia
    block(g, M.trim, 0.08, 0.16, T.d + 0.5, -hw - 0.2, fl + wh + 0.04, -0.05);
  }

  /* -- stage 6: fit-out, deck, planting, light -- */
  {
    const g = stageGroups[5];
    const F = T.fitout;

    const deck = new THREE.Mesh(groundGeo(T.w + 0.6, 1.8, mats.deck.userData.tile), mats.deck);
    deck.position.set(0, fl - 0.03, hd + 0.9);
    deck.receiveShadow = true;
    g.add(deck);
    block(g, mats.deck, T.w + 0.6, 0.12, 0.08, 0, fl - 0.15, hd + 1.8);

    const spur = new THREE.Mesh(groundGeo(1.0, 2.6, mats.paving.userData.tile), mats.paving);
    spur.position.set(-T.w / 2 + 0.4, 0.02, hd + 3.1);
    spur.receiveShadow = true;
    g.add(spur);

    // interior floor so it does not read as a hollow shell
    const floor = new THREE.Mesh(groundGeo(T.w - wt * 2, T.d - wt * 2, 2.0), M.fitout);
    floor.position.set(0, fl + 0.005, 0);
    floor.receiveShadow = true;
    g.add(floor);

    // hygiene run — worktop, splashback, sink, under-counter storage
    block(g, M.fitout, F.worktop.w, F.worktop.h - 0.04, F.worktop.d, F.worktop.x, fl, F.worktop.z);
    block(g, M.worktop, F.worktop.w + 0.04, 0.04, F.worktop.d, F.worktop.x, fl + F.worktop.h - 0.04, F.worktop.z);
    block(g, M.trim, 0.02, 0.5, F.worktop.d, F.worktop.x - F.worktop.w / 2 - 0.02, fl + F.worktop.h, F.worktop.z);
    block(g, M.worktop, F.sink.w, 0.08, F.sink.d, F.sink.x, fl + F.worktop.h - 0.1, F.sink.z);
    block(g, M.darkTrim, 0.04, 0.3, 0.04, F.sink.x - 0.15, fl + F.worktop.h, F.sink.z - 0.14);

    // the station
    block(g, M.darkTrim, F.bed.w, 0.18, F.bed.d, F.bed.x, fl + F.bed.h - 0.18, F.bed.z);
    block(g, M.darkTrim, 0.12, F.bed.h - 0.18, 0.12, F.bed.x, fl, F.bed.z);
    block(g, M.darkTrim, 0.8, 0.06, 0.5, F.bed.x, fl + 0.04, F.bed.z);
    block(g, M.fitout, F.trolley.w, F.trolley.h, F.trolley.d, F.trolley.x, fl, F.trolley.z);
    const stool = new THREE.Mesh(new THREE.CylinderGeometry(F.stool.r, F.stool.r * 0.8, 0.08, 16), M.darkTrim);
    stool.position.set(F.stool.x, fl + F.stool.h, F.stool.z);
    stool.castShadow = true;
    g.add(stool);
    block(g, M.darkTrim, 0.08, F.stool.h, 0.08, F.stool.x, fl, F.stool.z);
    block(g, M.fitout, F.clientSeat.w, F.clientSeat.h, F.clientSeat.d, F.clientSeat.x, fl, F.clientSeat.z);
    block(g, M.fitout, F.shelves.w, F.shelves.h, F.shelves.d, F.shelves.x, fl, F.shelves.z);

    // planting either side of the deck
    for (const [x, z, r] of [[-2.9, 1.2, 0.55], [-2.4, 2.5, 0.4], [2.9, 1.5, 0.5], [2.4, 2.9, 0.38]]) {
      const b = new THREE.Mesh(new THREE.IcosahedronGeometry(r, 1), Math.random() > 0.5 ? M.foliage : M.foliage2);
      b.position.set(x, r * 0.8, z + hd);
      b.castShadow = true;
      g.add(b);
    }

    // practicals — these come on at dusk
    const porch = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.2, 0.08),
      new THREE.MeshStandardMaterial({ color: COLOURS.lampWarm, emissive: COLOURS.lampWarm, emissiveIntensity: 1 }));
    porch.position.set(o_x(T), fl + 2.05, hd + 0.08);
    g.add(porch);
    const porchLight = new THREE.PointLight(0xffc98a, 0, 6, 2);
    porchLight.position.set(o_x(T), fl + 1.95, hd + 0.3);
    g.add(porchLight);
    const interior = new THREE.PointLight(0xfff0d4, 0, 7, 2);
    interior.position.set(0, fl + 2.0, 0);
    g.add(interior);
    practicals.push({ light: porchLight, max: 3.5 }, { light: interior, max: 4.5 }, { emissive: porch });
  }

  function o_x(t) { return t.openings.door.x - t.openings.door.w / 2 - 0.28; }

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
