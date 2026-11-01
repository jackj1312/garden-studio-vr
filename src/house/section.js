import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  Section slice, x-ray and the materials that carry both.
 *
 *  The slice is one clipping plane on every house material. The cut
 *  faces are capped without a stencil pass: with the slice on, the
 *  materials draw both faces, and a back face seen through the cut can
 *  only be the inside of a closed solid, so it is painted flat in the
 *  layer's section colour with the drawing's hatch (brick diagonal,
 *  block cross-hatch, concrete stipple, insulation wave, earth). The
 *  hatch is laid out in the plane's own coordinates (the view ray is
 *  carried to the plane per pixel), so it does not swim as you move.
 *  No extra draw calls, works in the headset, works on BatchedMesh.
 *  The contract asks for closed solids with outward normals for this.
 *
 *  X-ray: walls, linings, decks, roof coverings and the ground go
 *  translucent; structure stays solid and colour-coded (legend below).
 * ------------------------------------------------------------------ */

/* section colour + hatch per group (0 solid, 1 diagonal, 2 cross, 3 stipple, 4 wave, 5 earth) */
export const CAPS = {
  wall_outer: [0xb0533a, 1], wall_inner: [0xa9a9a2, 2], wall_insulation: [0xe8d36a, 4], wall_lining: [0xf2efe6, 0],
  wall_cavity: [0xffffff, 0], foundation: [0x8f8f8a, 3], slab_layer: [0x8f8f8a, 3], ground: [0x6b4f33, 5],
  steel: [0xc0312b, 0], timber_beam: [0xc8a26a, 1], joist: [0xc8a26a, 1], rafter: [0xc8a26a, 1], hip: [0xc8a26a, 1],
  valley: [0xc8a26a, 1], ridge: [0xc8a26a, 1], ceiling_joist: [0xc8a26a, 1], wall_plate: [0xc8a26a, 1],
  deck: [0xd9bf8c, 0], lintel: [0x2f6fd6, 0], roof_layer: [0x2a3640, 0], roof_cover: [0x7a3b2c, 1],
  window: [0xeeeeee, 0], door: [0xeeeeee, 0], rooflight: [0xeeeeee, 0], fitting: [0x6f7f7a, 0], drain: [0xe07b1a, 0],
  prop: [0xe0a52a, 0], scaffold: [0xe0a52a, 0], spoil: [0x6b4f33, 5],
};
/* by material name, where one group holds several materials (the slab's layers) */
const CAP_BY_MAT = {
  hardcore: [0x7d746a, 3], dpm: [0x1b1d22, 0], vcl: [0x3a4a5a, 0], pir: [0xe8d36a, 4], mineral_wool: [0xe6cf8a, 4], mesh_a142: [0x5a3a2a, 0],
  rebar: [0x5a3a2a, 0], screed: [0xbdb7ab, 3], concrete: [0x8f8f8a, 3], brick: [0xb0533a, 1], existing_brick: [0x9a4a35, 1],
  brick_porch: [0xa8583c, 1], block: [0xa9a9a2, 2], plaster: [0xf2efe6, 0], plasterboard: [0xf2efe6, 0], existing_partition: [0xcfc8b8, 2],
  timber: [0xc8a26a, 1], timber_existing: [0xb08c58, 1], timber_temp: [0xd8b878, 1], batten: [0xc8a26a, 1], chipboard: [0xd9bf8c, 0],
  steel: [0xc0312b, 0], lintel_galv: [0x2f6fd6, 0], earth: [0x6b4f33, 5], ground: [0x6b4f33, 5], ground_lawn: [0x6b4f33, 5],
  ground_paving: [0x6b4f33, 5], ground_gravel: [0x6b4f33, 5], tile: [0x7a3b2c, 1], existing_tile: [0x6a4a3c, 1], membrane: [0x2a3640, 0], felt: [0x2a3640, 0],
};

export const XRAY = {
  steel:    { hex: 0xd23a2a, label: "Steel", groups: ["steel"] },
  timber:   { hex: 0xc8a26a, label: "Timber", groups: ["timber_beam", "joist", "rafter", "hip", "valley", "ridge", "ceiling_joist", "wall_plate"] },
  lintel:   { hex: 0x2f6fd6, label: "Lintels", groups: ["lintel"] },
  concrete: { hex: 0x9a9a96, label: "Concrete", groups: ["foundation"], mats: ["concrete"] },
  drain:    { hex: 0xe07b1a, label: "Drains", groups: ["drain"] },
  temp:     { hex: 0xf2c230, label: "Temporary works", groups: ["prop", "scaffold"] },
};
export function xrayClass(group, matName) {
  for (const [k, c] of Object.entries(XRAY)) {
    if (c.groups.includes(group)) return k;
    if (c.mats && c.mats.includes(matName)) return k;
  }
  return null;
}

/* shared by every house material */
export const capUniforms = {
  uCapPlane: { value: new THREE.Vector4(0, 0, 1, 0) },
  uCapOn: { value: 0 },
};

const CAP_VERT_PARS = "varying vec3 vCapWorld;\n";
const CAP_VERT = `
  {
    vec4 cw = vec4( transformed, 1.0 );
    #ifdef USE_BATCHING
      cw = batchingMatrix * cw;
    #endif
    #ifdef USE_INSTANCING
      cw = instanceMatrix * cw;
    #endif
    vCapWorld = ( modelMatrix * cw ).xyz;
  }
`;
const CAP_FRAG_PARS = `
varying vec3 vCapWorld;
uniform vec4 uCapPlane;
uniform float uCapOn;
uniform vec3 uCapColor;
uniform float uCapPattern;
float capLine( float x, float w ) {             // anti-aliased line every 1.0 in x, w wide
  float f = abs( fract( x ) - 0.5 );
  float aa = fwidth( x ) * 1.2;
  return 1.0 - smoothstep( w * 0.5 - aa, w * 0.5 + aa, 0.5 - f );
}
float capHash( vec2 p ) { return fract( sin( dot( p, vec2( 127.1, 311.7 ) ) ) * 43758.5453 ); }
float capInk( vec2 q, float pat ) {
  if ( pat < 0.5 ) return 0.0;
  if ( pat < 1.5 ) return capLine( ( q.x + q.y ) / 0.045, 0.16 );
  if ( pat < 2.5 ) return max( capLine( ( q.x + q.y ) / 0.06, 0.12 ), capLine( ( q.x - q.y ) / 0.06, 0.12 ) );
  if ( pat < 3.5 ) {
    vec2 c = floor( q / 0.018 ); vec2 f = fract( q / 0.018 ) - 0.5;
    float r = capHash( c );
    return r > 0.55 ? 1.0 - smoothstep( 0.12, 0.2, length( f - ( vec2( capHash( c + 7.0 ), capHash( c + 3.0 ) ) - 0.5 ) * 0.5 ) ) : 0.0;
  }
  if ( pat < 4.5 ) return capLine( ( q.y + 0.012 * abs( fract( q.x / 0.03 ) * 2.0 - 1.0 ) ) / 0.024, 0.18 );
  return capLine( ( q.x + q.y ) / 0.12, 0.08 ) * step( 0.5, fract( ( q.x - q.y ) / 0.08 ) );
}
`;
const CAP_FRAG = `
  if ( uCapOn > 0.5 && ! gl_FrontFacing ) {
    vec3 rd = normalize( vCapWorld - cameraPosition );
    float dn = dot( uCapPlane.xyz, rd );
    vec3 P = vCapWorld;
    if ( abs( dn ) > 1e-4 ) P = cameraPosition + rd * ( - ( dot( uCapPlane.xyz, cameraPosition ) + uCapPlane.w ) / dn );
    vec3 n = uCapPlane.xyz;
    vec3 a = abs( n.y ) < 0.9 ? vec3( 0.0, 1.0, 0.0 ) : vec3( 1.0, 0.0, 0.0 );
    vec3 u = normalize( cross( a, n ) ), v = cross( n, u );
    vec2 q = vec2( dot( P, u ), dot( P, v ) );
    float ink = capInk( q, uCapPattern );
    gl_FragColor = vec4( mix( uCapColor, uCapColor * 0.28, ink ), 1.0 );
  }
`;

function patch(mat, capHex, pattern) {
  const own = { uCapColor: { value: new THREE.Color(capHex) }, uCapPattern: { value: pattern } };
  mat.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, capUniforms, own);
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\n" + CAP_VERT_PARS)
      .replace("#include <project_vertex>", "#include <project_vertex>\n" + CAP_VERT);
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", "#include <common>\n" + CAP_FRAG_PARS)
      .replace("#include <tonemapping_fragment>", CAP_FRAG + "\n#include <tonemapping_fragment>");
  };
  mat.customProgramCacheKey = () => "house-cap";
  mat.userData.cap = own;
  return mat;
}

/* {normal, xray, cls}: the material a batch draws with, and its x-ray twin */
export function makeMaterialSet(source, group) {
  const name = source.name || "";
  const [capHex, pattern] = CAP_BY_MAT[name] || CAPS[group] || [0x999999, 0];
  const normal = source.clone();
  normal.name = name;
  if (normal.transparent) normal.depthWrite = false;
  if (normal.aoMap) normal.aoMapIntensity = 1.0;
  patch(normal, capHex, pattern);
  const cls = xrayClass(group, name);
  let xray;
  if (cls) {
    const c = XRAY[cls].hex;
    xray = new THREE.MeshStandardMaterial({ name: name + "_xray", color: c, roughness: 0.55, metalness: 0.05,
      emissive: new THREE.Color(c).multiplyScalar(0.28) });
  } else {
    xray = new THREE.MeshStandardMaterial({ name: name + "_xray", color: normal.color?.clone() || new THREE.Color(0xcccccc),
      roughness: 0.9, transparent: true, opacity: group === "ground" ? 0.06 : 0.13, depthWrite: false });
  }
  patch(xray, capHex, pattern);
  return { normal, xray, cls, group, name, targets: new Set() };
}

/* the slice itself */
export function createSection(materialSets) {
  const plane = new THREE.Plane(new THREE.Vector3(0, 0, -1), 0);
  const state = { on: false, name: null, origin: new THREE.Vector3(), normal: new THREE.Vector3(0, 0, -1), offset: 0, flip: false, range: 10 };
  const planes = [plane];

  function sync() {
    const n = state.normal.clone().normalize().multiplyScalar(state.flip ? -1 : 1);
    const at = state.origin.clone().addScaledVector(state.normal.clone().normalize(), state.offset);
    plane.setFromNormalAndCoplanarPoint(n, at);
    capUniforms.uCapPlane.value.set(plane.normal.x, plane.normal.y, plane.normal.z, plane.constant);
  }
  function setOn(on) {
    if (on === state.on) return;
    state.on = on;
    capUniforms.uCapOn.value = on ? 1 : 0;
    for (const set of materialSets()) for (const m of [set.normal, set.xray]) {
      m.clippingPlanes = on ? planes : null;
      m.side = on ? THREE.DoubleSide : (m.userData.baseSide ?? THREE.FrontSide);
      m.needsUpdate = true;
    }
  }
  return {
    state, plane,
    /* {name, origin:[x,y,z], normal:[x,y,z]} from the sidecar, or a free one */
    set(def) {
      state.name = def.name;
      state.origin.fromArray(def.origin);
      state.normal.fromArray(def.normal).normalize();
      state.offset = 0;
      sync(); setOn(true);
    },
    off() { state.name = null; setOn(false); },
    setOffset(m) { state.offset = m; sync(); },
    flip() { state.flip = !state.flip; sync(); },
    /* a new material set made after the slice was turned on */
    adopt(set) {
      for (const m of [set.normal, set.xray]) {
        m.userData.baseSide = m.side;
        if (state.on) { m.clippingPlanes = planes; m.side = THREE.DoubleSide; m.needsUpdate = true; }
      }
    },
    /* the kept side, for rays */
    get active() { return state.on ? plane : null; },
  };
}
