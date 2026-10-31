export const BUILD = "bfdad1a-0843";   // stamped by tools/stamp-build.py

/* ------------------------------------------------------------------ *
 *  Everything site-specific lives here. When the survey scan lands,
 *  this is the only file that has to change.
 *
 *  Metres throughout. Origin is the back door threshold, +X east,
 *  -Z down the garden, +Y up.
 * ------------------------------------------------------------------ */

export const SITE = {
  garden: { width: 8, length: 14 },
  house:  { depth: 8, height: 6.4, eaves: 5.6 },
  fence:  { height: 1.8, postSpacing: 1.9 },
  patio:  { depth: 3, inset: 0.2 },
  path:   { width: 0.9, offsetFromWest: 0.75 },
  hedge:  { depth: 1.0, height: 1.5 },
  shed:   { w: 2.0, d: 1.5, h: 1.9, x: -2.8, z: -12.0 },
  trees: [
    { x: -2.9, z: -9.4, height: 4.6, crown: 1.6 },
    { x:  3.0, z: -5.6, height: 3.6, crown: 1.3 }
  ],
  /* Which way is north decides where the good light comes from. Assumed
     for now — confirm on site, because it drives the whole glazing plan. */
  northIsTowards: "-Z"
};

export const HALF = SITE.garden.width / 2;
export const REAR = -SITE.garden.length;

/* ------------------------------------------------------------------ *
 *  The studio — a working tattoo studio, not a shed.
 *
 *  2.5 m is the hard ceiling: permitted development caps an outbuilding
 *  at that height when it sits within 2 m of a boundary. Everything
 *  below is designed down to fit under it.
 * ------------------------------------------------------------------ */
export const STUDIO = {
  w: 4.5,            // external, east-west
  d: 3.5,            // external, north-south
  wallThickness: 0.12,
  floorLevel: 0.15,  // top of slab
  wallHeight: 2.26,  // to underside of roof at the front
  ridge: 2.5,        // absolute maximum
  fallToRear: 0.22,  // mono-pitch sheds water to the back

  slab: { oversail: 0.2, thickness: 0.2 },

  /* Glazing. The clerestory is the important one: high north light is
     what a tattooist actually wants over the station — even, no glare on
     skin or stencil — and at high level it also solves being overlooked
     at the boundary, in one move. */
  openings: {
    door:       { w: 0.9,  h: 2.1,  x:  1.35, face: "south" },
    sideLight:  { w: 1.6,  h: 2.1,  x: -0.75, face: "south" },
    clerestory: { w: 2.6,  h: 0.45, x:  0.0,  sill: 1.6, face: "north" },
    gableVent:  { w: 0.5,  h: 0.5,  z: -0.6,  sill: 1.5, face: "west", obscured: true }
  },

  /* Fit-out, laid out so the artist can work both sides of the client.
     900 mm clear each side of the bed is the dimension that matters. */
  fitout: {
    bed:       { w: 1.9, d: 0.7, h: 0.62, x: 0.25, z: 0.1 },
    worktop:   { w: 0.6, d: 2.4, h: 0.9,  x: -1.65, z: 0.0 },  // hygiene run, west wall
    sink:      { w: 0.5, d: 0.4, x: -1.65, z: -0.75 },
    trolley:   { w: 0.45, d: 0.4, h: 0.8, x: 0.25, z: -1.05 },
    stool:     { r: 0.2, h: 0.55, x: 0.25, z: 1.0 },
    clientSeat:{ w: 0.6, d: 0.6, h: 0.42, x: 1.5, z: -0.9 },
    shelves:   { w: 0.35, d: 1.2, h: 1.8, x: 1.9, z: 0.6 }
  }
};

/* ------------------------------------------------------------------ *
 *  The three dials
 * ------------------------------------------------------------------ */
export const STAGES = [
  { name: "As it is today",  note: "The garden as it stands. Nothing proposed." },
  { name: "Cleared",         note: "Hedge out, slabs lifted, footprint stripped back." },
  { name: "Base",            note: "Slab poured, service trench run to the house." },
  { name: "Frame",           note: "Sole plates, studs and roof structure up." },
  { name: "Clad and roofed", note: "Cladding, roof, glazed door and clerestory in." },
  { name: "Finished",        note: "Fit-out, deck, path, planting and lighting." }
];

export const VARIANTS = {
  A: { label: "Corner",      x: 1.35,  z: REAR + 2.45, ry: 0 },
  B: { label: "Along fence", x: HALF - 2.2, z: REAR + 5.2, ry: Math.PI / 2 }
};

/* Times of day. Baked sky plus a matching sun — a moving sun would cost
   more than it is worth, and five good ones read better than a slider. */
/* Per time of day. `hemi` is the sky-fill light; `haze` is exponential fog
   that gives distance its aerial perspective — the single cheapest thing
   that separates a render from a model (see BENCHMARKS.md). */
export const TIMES = {
  morning: {
    label: "Morning", short: "Morn",
    hdri: "assets/hdri/kloofendal_misty_morning_puresky_2k.exr",
    sky:  "assets/hdri/sky_morning_4k.jpg",
    sun: { x: 10, y: 6, z: 4 }, colour: 0xfff1dc, intensity: 1.2,
    exposure: 1.12, envIntensity: 1.0, practicals: false,
    hemi: 0.6, haze: { colour: 0xe4eaee, density: 0.013 }
  },
  midday: {
    label: "Midday", short: "Noon",
    hdri: "assets/hdri/kloofendal_43d_clear_puresky_2k.exr",
    sky:  "assets/hdri/sky_midday_4k.jpg",
    sun: { x: -6, y: 14, z: 6 }, colour: 0xfff6e8, intensity: 2.2,
    exposure: 1.14, envIntensity: 1.0, practicals: false,
    hemi: 0.7, haze: { colour: 0xdbe6f0, density: 0.012 }
  },
  golden: {
    label: "Golden hour", short: "Gold",
    hdri: "assets/hdri/qwantani_sunset_puresky_2k.exr",
    sky:  "assets/hdri/sky_golden_4k.jpg",
    sun: { x: -12, y: 4, z: 3 }, colour: 0xffc48a, intensity: 1.1,
    exposure: 0.98, envIntensity: 1.0, practicals: false,
    hemi: 0.4, haze: { colour: 0xe6c9a6, density: 0.011 }
  },
  dusk: {
    label: "Dusk", short: "Dusk",
    hdri: "assets/hdri/evening_road_01_puresky_2k.exr",
    sky:  "assets/hdri/sky_dusk_4k.jpg",
    sun: { x: -13, y: 2.4, z: 2 }, colour: 0xffb070, intensity: 1.1,
    exposure: 1.05, envIntensity: 0.9, practicals: true,
    hemi: 0.32, haze: { colour: 0x9aa2b6, density: 0.010 }
  },
  night: {
    label: "Night", short: "Night",
    hdri: "assets/hdri/dikhololo_night_2k.exr",
    sky:  "assets/hdri/sky_night_4k.jpg",
    sun: { x: 4, y: 9, z: -6 }, colour: 0x8c9ccc, intensity: 0.12,
    exposure: 0.9, envIntensity: 0.8, practicals: true,
    hemi: 0.12, haze: { colour: 0x0a0e16, density: 0.014 }
  }
};

/* ------------------------------------------------------------------ *
 *  Materials. tile is the real-world size one texture square covers,
 *  which is what keeps texel density honest across the whole scene.
 * ------------------------------------------------------------------ */
export const MATERIALS = {
  cladding: { dir: "exterior_wall_cladding_03", tile: 1.4, roughness: 0.85 },
  deck:     { dir: "wood_floor_deck",           tile: 1.6, roughness: 0.7, tint: 0xa89a86 },   // the scan is orange; real decking greys
  concrete: { dir: "brushed_concrete",          tile: 2.0, roughness: 0.9 },
  grass:    { dir: "grass_ground",              tile: 1.6, roughness: 1.0, tint: 0x8fae63 },
  brick:    { dir: "red_brick",                 tile: 1.8, roughness: 0.95 },
  paving:   { dir: "square_brick_paving",       tile: 1.5, roughness: 0.85 },
  fence:    { dir: "weathered_plank_siding",    tile: 1.2, roughness: 0.9, tint: 0xb59878 }
};

/* Flat colours for the parts that do not warrant a texture download. */
export const COLOURS = {
  timber:    0xc0a070,
  roofing:   0x3a3d42,
  trim:      0xcac5ba,
  darkTrim:  0x2e3134,
  soil:      0x4e4034,
  foliage:   0x4f7336,
  foliage2:  0x5f8445,
  trunk:     0x5a4a38,
  glass:     0x223038,
  fitout:    0xe4e0d6,
  worktop:   0x2b2e31,
  lampWarm:  0xffd9a0,
  hedge:     0x44632f
};

/* ------------------------------------------------------------------ *
 *  Quality tiers
 *
 *  These are the price points, not debug switches. One codebase serves
 *  all of them; a client buys a tier and gets the same scene rendered
 *  to a different standard. The VR profile is applied on top of
 *  whichever tier is active, because 90 Hz in the headset is a promise
 *  that outranks any of them.
 * ------------------------------------------------------------------ */
export const QUALITY = {
  basic: {
    label: "Basic",
    shadowMap: 1024, anisotropy: 4, grass: 2500,
    ao: false, bloom: false, pixelRatio: 1.25
  },
  standard: {
    label: "Standard",
    shadowMap: 2048, anisotropy: 8, grass: 14000,
    ao: false, bloom: true, pixelRatio: 1.75
  },
  /* Premium turns on screen-space ambient occlusion, which costs roughly
     three quarters of the frame rate on integrated graphics — it needs a
     discrete GPU. It is also a stopgap: baked lighting does the same job
     better and for free at runtime, and will replace it. */
  premium: {
    label: "Premium",
    shadowMap: 4096, anisotropy: 16, grass: 30000,
    ao: true, aoQuality: "Medium", bloom: true, pixelRatio: 1.25
  }
};

/* Applied over the top of the chosen tier whenever a headset session
   is running. Nothing here is negotiable: dropped frames make people
   ill, and nobody buys a walkthrough that made them ill. */
export const VR_PROFILE = {
  shadowMap: 1024, ao: false, bloom: false, grassScale: 0.35
};
