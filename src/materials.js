import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { MATERIALS, BUILD } from "./config.js?v=4d52a60-0926";
import { addWind } from "./wind.js?v=4d52a60-0926";

/* ------------------------------------------------------------------ *
 *  Texture loading
 * ------------------------------------------------------------------ */
const loader = new THREE.TextureLoader();

function load(path, { srgb = false, aniso = 8 } = {}) {
  const t = loader.load(`${path}?v=${BUILD}`);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = aniso;
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/* One material per entry in MATERIALS. Tiling is handled in the
   geometry's UVs rather than on the texture, so a single material
   instance can be shared by objects of wildly different sizes without
   the texture stretching on any of them. */
export function buildMaterials(maxAniso = 8) {
  const out = {};
  for (const [name, def] of Object.entries(MATERIALS)) {
    const base = `assets/textures/${def.dir}`;
    out[name] = new THREE.MeshStandardMaterial({
      map:          load(`${base}/diffuse.jpg`, { srgb: true, aniso: maxAniso }),
      normalMap:    load(`${base}/normal.jpg`,  { aniso: maxAniso }),
      roughnessMap: load(`${base}/rough.jpg`,   { aniso: maxAniso }),
      aoMap:        load(`${base}/ao.jpg`,      { aniso: maxAniso }),
      roughness:    def.roughness,
      metalness:    0,
      aoMapIntensity: 0.85,
      /* the scan is dry ground; colour multiplies the map, which is the
         cheapest way to push a photographed surface where you need it */
      color:        def.tint ?? 0xffffff
    });
    out[name].userData.tile = def.tile;
  }
  return out;
}

/* ------------------------------------------------------------------ *
 *  Geometry with honest texel density
 *
 *  A BoxGeometry gives every face UVs from 0 to 1 regardless of how big
 *  that face is, so a 4.5 m wall and a 100 mm post would each get one
 *  tile of texture. These rewrite the UVs in real-world units, which is
 *  most of the difference between "textured" and "convincing".
 * ------------------------------------------------------------------ */
const FACE_DIMS = (w, h, d) => [
  [d, h], [d, h],   // +X, -X
  [w, d], [w, d],   // +Y, -Y
  [w, h], [w, h]    // +Z, -Z
];

export function boxGeo(w, h, d, tile = 1, offset = [0, 0]) {
  const g = new THREE.BoxGeometry(w, h, d);
  const uv = g.attributes.uv;
  const dims = FACE_DIMS(w, h, d);
  for (let i = 0; i < uv.count; i++) {
    const [du, dv] = dims[Math.floor(i / 4)];
    uv.setXY(i, uv.getX(i) * (du / tile) + offset[0], uv.getY(i) * (dv / tile) + offset[1]);
  }
  uv.needsUpdate = true;
  g.setAttribute("uv1", uv.clone());
  return g;
}

export function groundGeo(w, d, tile = 1, segX = 1, segY = 1) {
  const g = new THREE.PlaneGeometry(w, d, segX, segY);
  const uv = g.attributes.uv;
  for (let i = 0; i < uv.count; i++) {
    uv.setXY(i, uv.getX(i) * (w / tile), uv.getY(i) * (d / tile));
  }
  uv.needsUpdate = true;
  g.setAttribute("uv1", uv.clone());
  g.rotateX(-Math.PI / 2);
  return g;
}

/* ------------------------------------------------------------------ *
 *  Grass
 *
 *  A tiled lawn texture reads as a flat green carpet from standing
 *  height. Scattering crossed alpha cards over it is what makes the
 *  ground look like it has depth when you are actually stood on it.
 * ------------------------------------------------------------------ */
function grassBladeTexture() {
  const c = document.createElement("canvas");
  c.width = 128; c.height = 128;
  const x = c.getContext("2d");
  x.clearRect(0, 0, 128, 128);
  for (let i = 0; i < 10; i++) {
    const base = 8 + i * 12 + Math.random() * 6;
    const tipX = base + (Math.random() - 0.5) * 26;
    const topY = 10 + Math.random() * 34;
    const wBlade = 4 + Math.random() * 3;
    const g = x.createLinearGradient(0, topY, 0, 128);
    const dry = Math.random() < 0.18;
    g.addColorStop(0, dry ? `hsl(${52 + Math.random() * 10}, 48%, ${56 + Math.random() * 8}%)`
                          : `hsl(${84 + Math.random() * 16}, 46%, ${52 + Math.random() * 12}%)`);
    g.addColorStop(1, `hsl(${92 + Math.random() * 10}, 40%, 26%)`);
    x.fillStyle = g;
    x.beginPath();
    x.moveTo(base - wBlade, 128);
    x.quadraticCurveTo(base - wBlade * 0.4, (128 + topY) / 2, tipX, topY);
    x.quadraticCurveTo(base + wBlade * 0.4, (128 + topY) / 2, base + wBlade, 128);
    x.closePath();
    x.fill();
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export function makeGrass({ count, width, length, centreZ, avoid = [] }) {
  const tex = grassBladeTexture();
  const blade = new THREE.PlaneGeometry(0.26, 0.2).translate(0, 0.1, 0);
  const crossed = mergeGeometries([blade, blade.clone().rotateY(Math.PI / 2)]);

  const bladeMat = addWind(new THREE.MeshStandardMaterial({
    map: tex, transparent: false, alphaTest: 0.4, alphaToCoverage: true,   // alpha from the canvas, not the green
    side: THREE.DoubleSide, roughness: 1, metalness: 0
  }), { strength: 0.035, speed: 1.4, height: 0.2 });
  const mesh = new THREE.InstancedMesh(crossed, bladeMat, count);
  mesh.castShadow = false;
  mesh.receiveShadow = true;
  mesh.frustumCulled = false;

  const m = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const pos = new THREE.Vector3();
  const scl = new THREE.Vector3();
  const tint = new THREE.Color();
  let placed = 0;
  let guard = 0;

  while (placed < count && guard++ < count * 6) {
    const x = (Math.random() - 0.5) * width;
    const z = centreZ + (Math.random() - 0.5) * length;
    if (avoid.some(a => Math.abs(x - a.x) < a.hw && Math.abs(z - a.z) < a.hd)) continue;
    const s = 0.75 + Math.random() * 0.75;
    pos.set(x, 0, z);
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.random() * Math.PI);
    scl.set(s, s * (0.8 + Math.random() * 0.6), s);
    m.compose(pos, q, scl);
    mesh.setMatrixAt(placed, m);
    tint.setHSL(0.24 + (Math.random() - 0.5) * 0.04, 0.45 + Math.random() * 0.2, 0.42 + Math.random() * 0.16);
    mesh.setColorAt(placed, tint);
    placed++;
  }
  mesh.count = placed;
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  return mesh;
}
