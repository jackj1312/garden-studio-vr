import * as THREE from "three";
import { EXRLoader } from "three/addons/loaders/EXRLoader.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { SITE, STUDIO, STAGES, VARIANTS, TIMES, HALF, REAR, QUALITY, VR_PROFILE, BUILD } from "./config.js?v=a3c7fc9-1326";
import { buildMaterials } from "./materials.js?v=a3c7fc9-1326";
import { buildWorld } from "./world.js?v=a3c7fc9-1326";
import { installStudio, installGarden } from "./studio.js?v=a3c7fc9-1326";
import { installTrees, setTreeDetail, installPlanting, setPlantDetail } from "./vegetation.js?v=a3c7fc9-1326";
import { installSite } from "./site.js?v=a3c7fc9-1326";
import { createFade, attachControllerModels, attachHandModels, createShadowFollow, createBlobShadows, hapticPulse } from "./presence.js?v=a3c7fc9-1326";
import { createAmbience } from "./ambience.js?v=a3c7fc9-1326";
import { updateWind } from "./wind.js?v=a3c7fc9-1326";

const $ = id => document.getElementById(id);
const clamp01 = t => t < 0 ? 0 : t > 1 ? 1 : t;
const easeOut = t => 1 - Math.pow(1 - t, 3);

/* ------------------------------------------------------------------ *
 *  Renderer
 * ------------------------------------------------------------------ */
/* The tier is the product. ?q=basic | standard | premium */
const tierKey = (() => {
  const q = new URLSearchParams(location.search).get("q");
  return QUALITY[q] ? q : "standard";
})();
const tier = QUALITY[tierKey];
/* ?site=<name> walks a scanned real garden instead of the demo one */
const siteKey = new URLSearchParams(location.search).get("site");
const FOOTSTEP_HAPTICS = false;        // the hands are not the feet; a tick per step nags

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, tier.pixelRatio));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
renderer.toneMapping = THREE.AgXToneMapping;            // keeps greens green; ACES pushed them olive
renderer.toneMappingExposure = 0.95;
renderer.xr.enabled = true;
renderer.xr.setReferenceSpaceType("local-floor");
document.body.appendChild(renderer.domElement);

const maxAniso = renderer.capabilities.getMaxAnisotropy();

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.05, 300);
const player = new THREE.Group();
player.position.set(0, 0, -2.2);
player.add(camera);
scene.add(player);
const eyeHeight = 1.68;
camera.position.set(0, eyeHeight, 0);

const hemi = new THREE.HemisphereLight(0xbfd6e6, 0x5c5f4a, 0.18);
scene.add(hemi);
const haze = new THREE.FogExp2(0xdbe6f0, 0.012);
const sun = new THREE.DirectionalLight(0xfff4e0, 1.6);
sun.castShadow = true;
sun.shadow.mapSize.set(tier.shadowMap, tier.shadowMap);
sun.shadow.camera.left = -14; sun.shadow.camera.right = 14;
sun.shadow.camera.top = 14; sun.shadow.camera.bottom = -20;
sun.shadow.camera.far = 60;
sun.shadow.normalBias = 0.03;
sun.shadow.radius = 3.5;                                  // PCF disk; 1 is a hard edge
scene.add(sun);
scene.add(sun.target);

const fade = createFade(camera);
const shadowFollow = createShadowFollow(sun);
const ambience = createAmbience();
const grips = attachControllerModels(renderer, player);
attachHandModels(renderer, player);
const blobs = createBlobShadows(scene);
const _head = new THREE.Vector3(), _local = new THREE.Vector3();
const _lastHead = new THREE.Vector3(0, 0, -2.2);
let stepDist = 0;

/* ------------------------------------------------------------------ *
 *  World
 * ------------------------------------------------------------------ */
const mats = buildMaterials(Math.min(maxAniso, tier.anisotropy));
const world = buildWorld(scene, mats, tier);
const { stageGroups, obstacles, removals, practicals } = world;

let studioParts = 0, gardenParts = 0;
if (!siteKey) {                                  // a real site never shows the demo; don't fetch it
  installStudio(stageGroups, mats, n => { studioParts = n; });
  installGarden(world.existing, mats, n => { gardenParts = n; });
}
/* scanned trees: the headset and the basic tier get the collapsed
   version, everything else the full one */
let treeParts = 0;
let site = null, siteBounds = null;
if (siteKey) {
  // a real garden: the demo studio has no business appearing in it until a
  // proposal for this site exists
  world.anchor.visible = false;
  // the demo's words and studio-only controls don't belong on a real garden
  document.querySelector("#start h1").textContent = "Your garden";
  document.querySelector("#start h1 + p").textContent = "Your garden as it is today, modelled at true scale from its measured plan.";
  for (const id of ["scrub", "ticks", "play", "variantA", "variantB"]) { const el = $(id); if (el) el.style.display = "none"; }
  $("stageName").textContent = "As it is today"; $("stageNote").textContent = "Built from the measured plan. Nothing proposed yet."; $("meta").textContent = "";
  installSite(scene, world, player, siteKey).then(r => {
    site = r; siteBounds = r.meta.bounds || null;
    if (r.meta.name) { document.querySelector("#start h1").textContent = r.meta.name.split(" — ")[0]; document.title = r.meta.name; }
  })
    .catch(err => {
      console.error("site failed:", err);
      $("xrNote").textContent = `This garden failed to load (${err.message || err}). Reload to try again.`;
    });
} else {
  installTrees(world.existing, tierKey === "basic" ? "q" : "d", n => { treeParts = n; });
  installPlanting(world.existing, tierKey === "basic" ? "q" : "d", n => { treeParts += n; });
}

let grassMesh = null, grassFull = 0;
world.existing.traverse(o => { if (o.isInstancedMesh) { grassMesh = o; grassFull = o.count; } });

let variant = "A";
world.applyVariant(variant);

/* ------------------------------------------------------------------ *
 *  Image-based lighting, one environment per time of day
 * ------------------------------------------------------------------ */
/* The sky is the biggest thing in a headset's view and a 2k equirect is
   a third of the panel's pixel density. So lighting comes from the 2k
   EXR, but what you SEE is a 4k tone-mapped JPEG on a sphere, drawn
   last so it only fills pixels nothing else covered. */
const skyTex = new Map();
const sky = new THREE.Mesh(
  new THREE.SphereGeometry(220, 48, 24),
  new THREE.MeshBasicMaterial({ side: THREE.BackSide, toneMapped: false, depthWrite: false, fog: false })
);
sky.renderOrder = 1000;
sky.frustumCulled = false;
scene.add(sky);

function applySky(key) {
  const t = TIMES[key];
  if (!t?.sky) return;
  if (!skyTex.has(key)) {
    const tex = new THREE.TextureLoader().load(`${t.sky}?v=${BUILD}`);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.wrapS = THREE.RepeatWrapping;
    tex.repeat.x = -1;             // inside-out sphere; mirror about the centre keeps +X at +X
    tex.offset.x = 1;
    tex.anisotropy = Math.min(maxAniso, 8);
    skyTex.set(key, tex);
  }
  sky.material.map = skyTex.get(key);
  sky.material.color.setHex(t.skyTint ?? 0xffffff);   // night: deep blue, never grey
  sky.material.needsUpdate = true;
}

const pmrem = new THREE.PMREMGenerator(renderer);
pmrem.compileEquirectangularShader();
const hdrCache = new Map();
let timeKey = "midday";

function applyTime(key) {
  const t = TIMES[key];
  if (!t) return;
  timeKey = key;
  ambience.setTime(key);
  sun.target.position.set(0, 0, REAR / 2);
  if (sunDirs.has(key)) placeSun(sunDirs.get(key));
  else sun.position.set(t.sun.x, t.sun.y, t.sun.z);
  sun.color.setHex(t.colour);
  sun.intensity = t.intensity;
  hemi.intensity = t.hemi;
  renderer.toneMappingExposure = t.exposure;
  if (!arMode) {
    haze.color.setHex(t.haze.colour);
    haze.density = t.haze.density;
    scene.fog = haze;
  }
  for (const p of practicals) {
    if (p.light) { p.light.intensity = t.practicals ? p.max : 0; p.light.visible = !!t.practicals; }
    if (p.emissive) p.emissive.material.emissiveIntensity = t.practicals ? 1.6 : 0.05;
  }
  for (const b of timeButtons) b.setAttribute("aria-pressed", String(b.dataset.time === key));
  uiDirty = true;

  applySky(key);
  if (hdrCache.has(key)) {
    scene.environment = hdrCache.get(key);
    scene.environmentIntensity = t.envIntensity * (envScale.get(key) ?? 1);
    return;
  }
  new EXRLoader().setDataType(THREE.FloatType).load(`${t.hdri}?v=${BUILD}`, tex => {
    tex.mapping = THREE.EquirectangularReflectionMapping;
    alignSunToSky(tex, key);
    const env = pmrem.fromEquirectangular(tex).texture;
    tex.dispose();
    hdrCache.set(key, env);
    if (timeKey === key) {
      scene.environment = env;
      scene.environmentIntensity = t.envIntensity * (envScale.get(key) ?? 1);
    }
  });
}

/* The shadow should fall where the sky says the sun is. Rather than
   guess a direction per HDRI, find its brightest texel and point the
   sun from there. Works for any sky we ever load. */
const sunDirs = new Map();
const envScale = new Map();
function alignSunToSky(tex, key) {
  const { data, width, height } = tex.image;
  let best = -1, bi = 0, sum = 0, n = 0;
  const step = 4 * 3;                                   // every third pixel is plenty
  for (let i = 0; i < data.length; i += step) {
    const l = data[i] + data[i + 1] + data[i + 2];
    if (l > best) { best = l; bi = i / 4; }
    sum += l; n++;
  }
  /* The sun disc is in the EXR. Left in, PMREM bakes it into the
     environment and the shade gets sunlight a second time (and every
     glossy surface shows two suns). Clamp it out: the DirectionalLight
     is the sun. */
  const cap = (sum / n) * 12;
  let removed = 0;
  for (let i = 0; i < data.length; i += 4) {
    const l = data[i] + data[i + 1] + data[i + 2];
    if (l > cap) { const k = cap / l; removed += l - cap; data[i] *= k; data[i + 1] *= k; data[i + 2] *= k; }
  }
  sum -= removed / 3;
  tex.needsUpdate = true;
  /* Skies differ wildly in absolute level (a sunset EXR can be several
     times brighter overall than a clear noon one), and white cladding
     blows out under the bright ones. Normalise so every sky lights the
     scene to the same mean; the time-of-day `envIntensity` then means
     what it says. */
  const mean = sum / (3 * n);
  envScale.set(key, Math.min(3, Math.max(0.15, 0.28 / Math.max(1e-4, mean))));
  console.info(`sky ${key}: mean ${mean.toFixed(3)} -> env x${envScale.get(key).toFixed(2)}`);
  const px = bi % width, py = Math.floor(bi / width);
  const u = (px + 0.5) / width, v = (py + 0.5) / height;
  const phi = (u - 0.5) * Math.PI * 2;
  let theta = (v - 0.5) * Math.PI;
  const dir = new THREE.Vector3(Math.cos(theta) * Math.cos(phi), Math.sin(theta), Math.cos(theta) * Math.sin(phi));
  if (dir.y < 0.05) dir.y = Math.abs(dir.y) + 0.05;    // whichever way the rows ran, the sun is up
  dir.normalize();
  sunDirs.set(key, dir);
  if (timeKey === key) placeSun(dir);
}
function placeSun(dir) {
  const target = sun.target.position;
  sun.position.copy(target).addScaledVector(dir, 22);
}

/* ------------------------------------------------------------------ *
 *  Stage animation
 * ------------------------------------------------------------------ */
const animated = [];

/* Rebuilt once the Blender model has been slotted into the stage
   groups, since most of what animates arrives with it. */
function buildStageAnimation() {
  animated.length = 0;
  stageGroups.forEach((g, gi) => {
    g.children.forEach((m, i, arr) => {
      animated.push({
        mesh: m, group: gi,
        delay: arr.length > 1 ? (i / arr.length) * 0.55 : 0,
        span: 0.45,
        baseY: m.position.y,
        baseScale: m.scale.clone()
      });
    });
  });
}

const removalState = removals.map(m => ({
  mesh: m, at: m.userData.removeAt, baseY: m.position.y, baseScale: m.scale.clone()
}));

let stageValue = 1, lastStageIdx = -1;

function applyStage(v) {
  for (const a of animated) {
    if (a.group === 3 && v > 5.95) { a.mesh.visible = false; continue; }   // frame is inside the walls once clad
    const p = clamp01(v - a.group);
    const local = easeOut(clamp01((p - a.delay) / a.span));
    a.mesh.visible = local > 0.001;
    if (!a.mesh.visible) continue;
    a.mesh.scale.set(
      a.baseScale.x * (0.92 + 0.08 * local),
      a.baseScale.y * local,
      a.baseScale.z * (0.92 + 0.08 * local)
    );
    a.mesh.position.y = a.baseY - (1 - local) * 0.22;
  }
  for (const r of removalState) {
    const out = easeOut(clamp01(v - (r.at - 1)));
    r.mesh.visible = out < 0.999;
    if (!r.mesh.visible) continue;
    r.mesh.scale.set(r.baseScale.x, r.baseScale.y * (1 - out), r.baseScale.z);
    r.mesh.position.y = r.baseY - out * 0.3;
  }
  const idx = Math.min(5, Math.max(0, Math.round(v) - 1));
  if (idx !== lastStageIdx) {
    lastStageIdx = idx;
    $("stageName").textContent = STAGES[idx].name;
    $("stageNote").textContent = STAGES[idx].note;
    for (const b of tickButtons) b.setAttribute("aria-pressed", String(+b.dataset.stage === idx + 1));
    uiDirty = true;
  }
}

/* ------------------------------------------------------------------ *
 *  Collision
 * ------------------------------------------------------------------ */
const PLAYER_R = 0.32;
function resolve(x, z, fromX = x, fromZ = z) {
  for (const o of obstacles) {
    if (stageValue + 0.001 < o.from) continue;
    if (o.kind === "circle") {
      const dx = x - o.cx, dz = z - o.cz;
      const d = Math.hypot(dx, dz), min = o.r + PLAYER_R;
      if (d < min && d > 1e-5) { x = o.cx + (dx / d) * min; z = o.cz + (dz / d) * min; }
      continue;
    }
    const c = Math.cos(-o.rot), s = Math.sin(-o.rot);
    const px = x - o.cx, pz = z - o.cz;
    let lx = px * c - pz * s, lz = px * s + pz * c;
    const ex = o.hw + PLAYER_R, ez = o.hd + PLAYER_R;
    const fx = fromX - o.cx, fz = fromZ - o.cz;
    const flx = fx * c - fz * s, flz = fx * s + fz * c;
    if (Math.abs(flx) < ex && Math.abs(flz) < ez) continue;      // already inside: never eject
    if (Math.abs(lx) < ex && Math.abs(lz) < ez) {
      const ox = ex - Math.abs(lx), oz = ez - Math.abs(lz);
      if (ox < oz) lx = Math.sign(lx || 1) * ex; else lz = Math.sign(lz || 1) * ez;
      const c2 = Math.cos(o.rot), s2 = Math.sin(o.rot);
      x = o.cx + (lx * c2 - lz * s2);
      z = o.cz + (lx * s2 + lz * c2);
    }
  }
  if (siteBounds) {                                // a real site walks to its own edges
    x = Math.min(siteBounds.x1, Math.max(siteBounds.x0, x));
    z = Math.min(siteBounds.z1, Math.max(siteBounds.z0, z));
    return [x, z];
  }
  x = Math.min(HALF - PLAYER_R, Math.max(-HALF + PLAYER_R, x));
  z = Math.min(SITE.house.depth + 12, Math.max(REAR + PLAYER_R, z));
  return [x, z];
}

/* ------------------------------------------------------------------ *
 *  Comfort vignette
 * ------------------------------------------------------------------ */
const vigCanvas = document.createElement("canvas");
vigCanvas.width = vigCanvas.height = 256;
{
  const c = vigCanvas.getContext("2d");
  const g = c.createRadialGradient(128, 128, 44, 128, 128, 128);
  g.addColorStop(0, "rgba(0,0,0,0)");
  g.addColorStop(0.5, "rgba(0,0,0,0)");
  g.addColorStop(1, "rgba(0,0,0,0.95)");
  c.fillStyle = g;
  c.fillRect(0, 0, 256, 256);
}
const vignette = new THREE.Mesh(
  new THREE.PlaneGeometry(1.5, 1.5),
  new THREE.MeshBasicMaterial({
    map: new THREE.CanvasTexture(vigCanvas), transparent: true, opacity: 0,
    depthTest: false, depthWrite: false, toneMapped: false
  })
);
vignette.position.z = -1.0;
vignette.scale.setScalar(3.2);
vignette.renderOrder = 999;
camera.add(vignette);

/* ------------------------------------------------------------------ *
 *  Wrist panel
 * ------------------------------------------------------------------ */
const PW = 512, PH = 372;
const panelCanvas = document.createElement("canvas");
panelCanvas.width = PW; panelCanvas.height = PH;
const pctx = panelCanvas.getContext("2d");
const panelTex = new THREE.CanvasTexture(panelCanvas);
panelTex.colorSpace = THREE.SRGBColorSpace;
const panel = new THREE.Mesh(
  new THREE.PlaneGeometry(0.26, 0.189),
  new THREE.MeshBasicMaterial({ map: panelTex, transparent: true, toneMapped: false, depthTest: false, opacity: 0 })
);
panel.renderOrder = 900;
panel.position.set(0.02, 0.05, -0.08);
panel.rotation.set(-Math.PI / 3.1, 0, 0);
panel.visible = false;

const HIT = {
  scrub: { x: 24, y: 112, w: 464, h: 54 },
  play:  { x: 24, y: 242, w: 150, h: 48 },
  varA:  { x: 190, y: 242, w: 142, h: 48 },
  varB:  { x: 346, y: 242, w: 142, h: 48 },
};
const timeKeys = Object.keys(TIMES);
const timeHit = timeKeys.map((_, i) => ({ x: 24 + i * 94, y: 300, w: 86, h: 48 }));
const tickHit = [];
for (let i = 0; i < 6; i++) tickHit.push({ x: 24 + i * 78, y: 182, w: 68, h: 44 });

let uiDirty = true, cursorUV = null;

function roundRect(c, x, y, w, h, r) {
  c.beginPath();
  c.moveTo(x + r, y);
  c.arcTo(x + w, y, x + w, y + h, r);
  c.arcTo(x + w, y + h, x, y + h, r);
  c.arcTo(x, y + h, x, y, r);
  c.arcTo(x, y, x + w, y, r);
  c.closePath();
}
const inHit = (uv, r) =>
  uv.x * PW >= r.x && uv.x * PW <= r.x + r.w && uv.y * PH >= r.y && uv.y * PH <= r.y + r.h;

function drawPanel() {
  pctx.clearRect(0, 0, PW, PH);
  pctx.fillStyle = "rgba(16,18,16,0.93)";
  pctx.strokeStyle = "rgba(255,255,255,0.16)";
  pctx.lineWidth = 2;
  roundRect(pctx, 2, 2, PW - 4, PH - 4, 18); pctx.fill(); pctx.stroke();

  const idx = Math.min(5, Math.max(0, Math.round(stageValue) - 1));
  pctx.fillStyle = "#f2f1ea";
  pctx.font = "600 33px system-ui, sans-serif";
  pctx.fillText(STAGES[idx].name, 24, 54);
  pctx.fillStyle = "#a7ab9e";
  pctx.font = "21px system-ui, sans-serif";
  pctx.fillText(STAGES[idx].note.slice(0, 46), 24, 86);

  const s = HIT.scrub;
  pctx.fillStyle = "rgba(255,255,255,0.12)";
  roundRect(pctx, s.x, s.y + 20, s.w, 12, 6); pctx.fill();
  const frac = (stageValue - 1) / 5;
  pctx.fillStyle = "#7aa86a";
  roundRect(pctx, s.x, s.y + 20, Math.max(12, s.w * frac), 12, 6); pctx.fill();
  pctx.beginPath();
  pctx.arc(s.x + s.w * frac, s.y + 26, 15, 0, Math.PI * 2);
  pctx.fillStyle = "#eef0e8"; pctx.fill();

  for (let i = 0; i < 6; i++) {
    const t = tickHit[i], on = i === idx;
    pctx.fillStyle = on ? "#7aa86a" : "rgba(255,255,255,0.08)";
    roundRect(pctx, t.x, t.y, t.w, t.h, 10); pctx.fill();
    pctx.fillStyle = on ? "#11140f" : "#d8dad1";
    pctx.font = "600 24px system-ui, sans-serif";
    pctx.textAlign = "center";
    pctx.fillText(String(i + 1), t.x + t.w / 2, t.y + 30);
    pctx.textAlign = "left";
  }

  const btn = (r, label, on) => {
    pctx.fillStyle = on ? "#7aa86a" : "rgba(255,255,255,0.08)";
    roundRect(pctx, r.x, r.y, r.w, r.h, 12); pctx.fill();
    pctx.fillStyle = on ? "#11140f" : "#e4e6dd";
    pctx.font = "600 22px system-ui, sans-serif";
    pctx.textAlign = "center";
    pctx.fillText(label, r.x + r.w / 2, r.y + 32);
    pctx.textAlign = "left";
  };
  btn(HIT.play, playing ? "Pause" : "Play build", playing);
  btn(HIT.varA, VARIANTS.A.label, variant === "A");
  btn(HIT.varB, VARIANTS.B.label, variant === "B");
  timeKeys.forEach((k, i) => btn(timeHit[i], TIMES[k].short || TIMES[k].label, timeKey === k));

  if (cursorUV) {
    pctx.beginPath();
    pctx.arc(cursorUV.x * PW, cursorUV.y * PH, 9, 0, Math.PI * 2);
    pctx.fillStyle = "rgba(255,255,255,0.85)"; pctx.fill();
  }
  panelTex.needsUpdate = true;
  uiDirty = false;
}

/* ------------------------------------------------------------------ *
 *  Controllers
 * ------------------------------------------------------------------ */
const controllers = [renderer.xr.getController(0), renderer.xr.getController(1)];
let rayLine = null;
const hands = { left: null, right: null };
const rayGeom = new THREE.BufferGeometry()
  .setFromPoints([new THREE.Vector3(), new THREE.Vector3(0, 0, -1)]);

controllers.forEach(c => {
  player.add(c);
  c.addEventListener("connected", e => {
    const h = e.data.handedness;
    c.userData.hand = h;
    c.userData.source = e.data;
    hands[h] = c;
    if (h === "left") { c.add(panel); }
    if (h === "right") {
      rayLine = new THREE.Line(rayGeom,
        new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.45 }));
      rayLine.scale.z = 1.3;
      rayLine.visible = false;
      c.add(rayLine);
    }
  });
  c.addEventListener("disconnected", () => {
    if (c.userData.hand === "left") panel.visible = false;
    hands[c.userData.hand] = null;
  });
});

const raycaster = new THREE.Raycaster();
let triggerWasDown = false, dragging = false;

const _pn = new THREE.Vector3(), _ph = new THREE.Vector3(), _pp = new THREE.Vector3(), _pq = new THREE.Quaternion();
let panelWanted = false, panelPinned = false;
function updatePanelVisibility() {
  if (!hands.left) return;
  panel.getWorldPosition(_pp);
  camera.getWorldPosition(_ph);
  _pn.set(0, 0, 1).applyQuaternion(panel.getWorldQuaternion(_pq));
  const facing = _pn.dot(_ph.sub(_pp).normalize()) > 0.45;   // wrist turned to you, like checking a watch
  panelWanted = facing || panelPinned;
  panel.material.opacity += ((panelWanted ? 1 : 0) - panel.material.opacity) * 0.25;
  panel.visible = panel.material.opacity > 0.03;
}

function updatePointer() {
  updatePanelVisibility();
  const right = hands.right;
  if (rayLine) rayLine.visible = false;
  if (!right || !panel.visible || !panelWanted) { cursorUV = null; return; }
  const origin = new THREE.Vector3(), dir = new THREE.Vector3(0, 0, -1);
  right.getWorldPosition(origin);
  dir.applyQuaternion(right.getWorldQuaternion(new THREE.Quaternion()));
  raycaster.set(origin, dir);
  const hit = raycaster.intersectObject(panel, false)[0];
  if (rayLine) rayLine.visible = !!hit;
  const gp = right.userData.source?.gamepad;
  const trigger = !!gp?.buttons?.[0]?.pressed;

  if (!hit) {
    if (cursorUV) uiDirty = true;
    cursorUV = null;
    if (arMode && trigger && !triggerWasDown) placeFromController(right);
    triggerWasDown = trigger; dragging = false;
    return;
  }
  cursorUV = { x: hit.uv.x, y: 1 - hit.uv.y };
  uiDirty = true;
  const uv = cursorUV;
  const pressed = trigger && !triggerWasDown;

  if (pressed && inHit(uv, HIT.scrub)) dragging = true;
  if (dragging && trigger) {
    setStage(1 + clamp01((uv.x * PW - HIT.scrub.x) / HIT.scrub.w) * 5);
    playing = false; tween = null;
  }
  if (!trigger) dragging = false;
  if (pressed) {
    if (inHit(uv, HIT.play)) togglePlay();
    else if (inHit(uv, HIT.varA)) setVariant("A");
    else if (inHit(uv, HIT.varB)) setVariant("B");
    else {
      let done = false;
      timeKeys.forEach((k, i) => { if (!done && inHit(uv, timeHit[i])) { applyTime(k); done = true; } });
      if (!done) for (let i = 0; i < 6; i++) if (inHit(uv, tickHit[i])) { goToStage(i + 1); break; }
    }
  }
  triggerWasDown = trigger;
}

/* ------------------------------------------------------------------ *
 *  Locomotion
 * ------------------------------------------------------------------ */
const SPEED = 1.4;
const SNAP = Math.PI / 6;
let snapLatch = false, speedNow = 0;
const forward = new THREE.Vector3(), rightVec = new THREE.Vector3(), moveVec = new THREE.Vector3();

const axesOf = c => {
  const gp = c?.userData.source?.gamepad;
  if (!gp?.axes) return [0, 0];
  const a = gp.axes;
  return a.length >= 4 ? [a[2], a[3]] : [a[0] || 0, a[1] || 0];
};
const dead = v => Math.abs(v) < 0.14 ? 0 : (v - Math.sign(v) * 0.14) / 0.86;

/* Nobody should have to aim a laser at a 2 cm handle. A = next stage,
   B = previous, Y = play/pause, X = pin the panel open. */
const btnWas = { a: false, b: false, x: false, y: false };
function faceButtons() {
  const r = hands.right?.userData.source?.gamepad?.buttons, l = hands.left?.userData.source?.gamepad?.buttons;
  const a = !!r?.[4]?.pressed, b = !!r?.[5]?.pressed, x = !!l?.[4]?.pressed, y = !!l?.[5]?.pressed;
  if (!siteKey) {                                 // stages belong to the demo studio
    if (a && !btnWas.a) { goToStage(Math.min(6, Math.round(stageValue) + 1)); hapticPulse([hands.right], 0.5, 30); }
    if (b && !btnWas.b) { goToStage(Math.max(1, Math.round(stageValue) - 1)); hapticPulse([hands.right], 0.5, 30); }
    if (y && !btnWas.y) { togglePlay(); hapticPulse([hands.left], 0.5, 30); }
  }
  if (x && !btnWas.x) { panelPinned = !panelPinned; hapticPulse([hands.left], 0.3, 20); }
  btnWas.a = a; btnWas.b = b; btnWas.x = x; btnWas.y = y;
}

function rotateAroundHead(angle) {
  const head = new THREE.Vector3();
  camera.getWorldPosition(head);
  const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), angle);
  player.position.sub(head).applyQuaternion(q).add(head);
  player.quaternion.premultiply(q);
}

function xrLocomotion(dt) {
  const [lx, ly] = axesOf(hands.left).map(dead);
  const [rx] = axesOf(hands.right).map(dead);

  if (Math.abs(rx) > 0.65) {
    if (!snapLatch) { rotateAroundHead(-Math.sign(rx) * SNAP); snapLatch = true; hapticPulse([hands.right], 0.3, 15); }
  } else if (Math.abs(rx) < 0.3) snapLatch = false;
  faceButtons();

  if (lx === 0 && ly === 0) { speedNow = 0; return; }
  camera.getWorldDirection(forward);
  forward.y = 0;
  if (forward.lengthSq() < 1e-6) return;
  forward.normalize();
  rightVec.set(forward.z, 0, -forward.x);
  moveVec.set(0, 0, 0).addScaledVector(forward, -ly).addScaledVector(rightVec, -lx);
  if (moveVec.lengthSq() > 1) moveVec.normalize();
  speedNow = moveVec.length();

  const head = new THREE.Vector3();
  camera.getWorldPosition(head);
  const [cx, cz] = resolve(head.x + moveVec.x * SPEED * dt, head.z + moveVec.z * SPEED * dt, head.x, head.z);
  player.position.x += cx - head.x;
  player.position.z += cz - head.z;
}

const keys = new Set();
let yaw = 0, pitch = 0, locked = false;
addEventListener("keydown", e => { keys.add(e.code); if (e.code === "Space") e.preventDefault(); });
addEventListener("keyup", e => keys.delete(e.code));
const grabPointer = () => {
  if (renderer.xr.isPresenting) return;
  try { renderer.domElement.requestPointerLock?.()?.catch?.(() => {}); } catch (_) {}
};
renderer.domElement.addEventListener("click", grabPointer);
document.addEventListener("pointerlockchange", () => {
  locked = document.pointerLockElement === renderer.domElement;
});
document.addEventListener("mousemove", e => {
  if (!locked) return;
  yaw -= e.movementX * 0.0022;
  pitch = Math.max(-1.2, Math.min(1.2, pitch - e.movementY * 0.0022));
});

function desktopLocomotion(dt) {
  camera.rotation.set(pitch, yaw, 0, "YXZ");
  camera.position.y = eyeHeight;
  let f = 0, s = 0;
  if (keys.has("KeyW") || keys.has("ArrowUp")) f += 1;
  if (keys.has("KeyS") || keys.has("ArrowDown")) f -= 1;
  if (keys.has("KeyA") || keys.has("ArrowLeft")) s -= 1;
  if (keys.has("KeyD") || keys.has("ArrowRight")) s += 1;
  if (!f && !s) { speedNow = 0; return; }
  moveVec.set(Math.sin(yaw) * -f + Math.cos(yaw) * s, 0, Math.cos(yaw) * -f + Math.sin(yaw) * -s);
  if (moveVec.lengthSq() > 1) moveVec.normalize();
  speedNow = moveVec.length();
  const [cx, cz] = resolve(
    player.position.x + moveVec.x * SPEED * dt,
    player.position.z + moveVec.z * SPEED * dt,
    player.position.x, player.position.z
  );
  player.position.x = cx;
  player.position.z = cz;
}

/* ------------------------------------------------------------------ *
 *  Controls
 * ------------------------------------------------------------------ */
const scrub = $("scrub");
const tickButtons = [];
STAGES.forEach((st, i) => {
  const b = document.createElement("button");
  b.textContent = String(i + 1);
  b.title = st.name;
  b.dataset.stage = String(i + 1);
  b.setAttribute("aria-pressed", "false");
  b.addEventListener("click", () => goToStage(i + 1));
  $("ticks").appendChild(b);
  tickButtons.push(b);
});

const timeButtons = [];
for (const [key, t] of Object.entries(TIMES)) {
  const b = document.createElement("button");
  b.textContent = t.label;
  b.dataset.time = key;
  b.setAttribute("aria-pressed", "false");
  b.addEventListener("click", () => applyTime(key));
  $("times").appendChild(b);
  timeButtons.push(b);
}

let playing = false, tween = null;

function setStage(v) {
  stageValue = Math.min(6, Math.max(1, v));
  applyStage(stageValue);
  scrub.value = String(stageValue);
}
function goToStage(n) {
  playing = false;
  tween = { from: stageValue, to: n, t: 0, dur: 1.1 };
  uiDirty = true;
}
function togglePlay() {
  playing = !playing;
  tween = null;
  if (playing && stageValue >= 5.99) setStage(1);
  $("play").textContent = playing ? "Pause" : "Play build";
  uiDirty = true;
}
function setVariant(v) {
  variant = v;
  world.applyVariant(v);
  $("variantA").setAttribute("aria-pressed", String(v === "A"));
  $("variantB").setAttribute("aria-pressed", String(v === "B"));
  uiDirty = true;
}

scrub.addEventListener("input", () => { playing = false; tween = null; setStage(parseFloat(scrub.value)); });
$("play").addEventListener("click", togglePlay);
$("variantA").textContent = VARIANTS.A.label;
$("variantB").textContent = VARIANTS.B.label;
$("variantA").addEventListener("click", () => setVariant("A"));
$("variantB").addEventListener("click", () => setVariant("B"));

/* ------------------------------------------------------------------ *
 *  Post-processing — flat screens only.
 *  WebXR renders stereo through its own framebuffer, which the
 *  composer cannot drive, so in the headset we render straight.
 * ------------------------------------------------------------------ */
const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(
  window.innerWidth * renderer.getPixelRatio(), window.innerHeight * renderer.getPixelRatio(),
  { type: THREE.HalfFloatType, samples: 4 }));             // without this the desktop path has no anti-aliasing at all
composer.addPass(new RenderPass(scene, camera));

/* Ambient occlusion is doing the job that bounced light would do if we
   had any. It is the single biggest reason a rendered frame stops
   looking like it is floating — contact darkening where surfaces meet.
   Real baked GI will replace most of this; until then it carries it. */
let gtao = null;
if (tier.ao) {
  gtao = new GTAOPass(scene, camera, window.innerWidth, window.innerHeight);
  gtao.output = GTAOPass.OUTPUT.Default;
  gtao.updateGtaoMaterial({
    radius: 0.45,
    distanceExponent: 1.2,
    thickness: 0.6,
    scale: 1.1,
    samples: tier.aoQuality === "High" ? 32 : 16
  });
  composer.addPass(gtao);
}

let bloom = null;
if (tier.bloom) {
  bloom = new UnrealBloomPass(
    new THREE.Vector2(window.innerWidth, window.innerHeight), 0.18, 0.7, 1.0);
  composer.addPass(bloom);
}
composer.addPass(new OutputPass());

/* ------------------------------------------------------------------ *
 *  VR session
 * ------------------------------------------------------------------ */
/* In the headset the tier gives way to the frame budget. */
function applyVRProfile(on) {
  setTreeDetail(on || tierKey === "basic" ? "q" : "d");
  setPlantDetail(on || tierKey === "basic" ? "q" : "d");
  shadowFollow.setVR(on);
  const size = on ? VR_PROFILE.shadowMap : tier.shadowMap;
  sun.shadow.mapSize.set(size, size);
  sun.shadow.map?.dispose();
  sun.shadow.map = null;
  if (grassMesh) grassMesh.count = on ? Math.floor(grassFull * VR_PROFILE.grassScale) : grassFull;
}

/* ------------------------------------------------------------------ *
 *  Passthrough
 *
 *  The hardest thing to make convincing is the existing garden. In
 *  passthrough we do not have to: the garden is the real one, seen
 *  through the headset, and only the proposed building is drawn. That
 *  removes the realism problem rather than solving it.
 * ------------------------------------------------------------------ */
const shadowCatcher = new THREE.Mesh(
  new THREE.PlaneGeometry(40, 40).rotateX(-Math.PI / 2),
  new THREE.ShadowMaterial({ opacity: 0.32 })
);
shadowCatcher.receiveShadow = true;
shadowCatcher.visible = false;
scene.add(shadowCatcher);

let arMode = false;
let arSupported = false;
let savedBackground = null;

function setARMode(on) {
  arMode = on;
  if (on) {
    savedBackground = scene.background;
    scene.background = null;              // let the cameras through
    sky.visible = false;
    world.existing.visible = false;       // the real garden replaces ours
    shadowCatcher.visible = true;
    sun.intensity = 1.1;                  // real light is doing most of the work
    hemi.intensity = 0.35;
    scene.fog = null;                     // no haze over a real room
    /* drop the studio a few metres ahead, roughly where someone would
       stand to look at it; the trigger moves it after that */
    world.anchor.position.set(0, 0, -4.5);
    world.anchor.rotation.y = 0;
  } else {
    scene.background = savedBackground;
    sky.visible = true;
    world.existing.visible = !siteKey;
    shadowCatcher.visible = false;
    applyTime(timeKey);
    setVariant(variant);
  }
}

/* place the studio where the right controller points at the floor */
const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const hitPoint = new THREE.Vector3();
function placeFromController(controller) {
  const origin = new THREE.Vector3(), dir = new THREE.Vector3(0, 0, -1);
  controller.getWorldPosition(origin);
  dir.applyQuaternion(controller.getWorldQuaternion(new THREE.Quaternion()));
  raycaster.set(origin, dir);
  if (!raycaster.ray.intersectPlane(floorPlane, hitPoint)) return false;
  if (hitPoint.distanceTo(origin) > 25) return false;
  world.anchor.position.set(hitPoint.x, 0, hitPoint.z);
  return true;
}

/* In passthrough the sticks adjust the proposal, never the viewer: the
   real garden must not move. Right stick turns the building in 15°
   steps, left stick nudges it. */
let arSnapLatch = false;
function arPlacementControls(dt) {
  const [lx, ly] = axesOf(hands.left).map(dead);
  const [rx] = axesOf(hands.right).map(dead);
  if (Math.abs(rx) > 0.65) {
    if (!arSnapLatch) { world.anchor.rotation.y -= Math.sign(rx) * Math.PI / 12; arSnapLatch = true; hapticPulse(controllers, 0.25, 15); }
  } else if (Math.abs(rx) < 0.3) arSnapLatch = false;
  if (lx || ly) {
    camera.getWorldDirection(forward); forward.y = 0; forward.normalize();
    rightVec.set(forward.z, 0, -forward.x);
    world.anchor.position.addScaledVector(forward, -ly * 0.8 * dt).addScaledVector(rightVec, -lx * 0.8 * dt);
  }
  speedNow = 0;
}

async function enterAR() {
  if (!navigator.xr) return;
  try {
    const session = await navigator.xr.requestSession("immersive-ar", {
      requiredFeatures: ["local-floor"],
      optionalFeatures: ["hit-test", "anchors", "plane-detection", "depth-sensing"]
    });
    await renderer.xr.setSession(session);
    applyVRProfile(true);
    renderer.xr.setFoveation(0.4);
    setARMode(true);
    $("start").hidden = true;
    $("hud").classList.add("hidden");
    session.addEventListener("end", () => {
      applyVRProfile(false);
      setARMode(false);
      $("hud").classList.remove("hidden");
    });
  } catch (err) {
    $("xrNote").textContent = `Could not start passthrough: ${err.message}`;
  }
}

async function enterVR() {
  if (!navigator.xr) return;
  try {
    const session = await navigator.xr.requestSession("immersive-vr", {
      optionalFeatures: ["local-floor", "bounded-floor", "hand-tracking"]
    });
    await renderer.xr.setSession(session);
    fade.black();
    fade.to(0, 1.6);
    ambience.start();
    applyVRProfile(true);
    renderer.xr.setFoveation(0.4);              // three.js defaults to maximum, which smears the periphery on grass
    renderer.xr.setFramebufferScaleFactor(1.0);
    $("start").hidden = true;
    $("hud").classList.add("hidden");
    session.addEventListener("end", () => {
      applyVRProfile(false);                 // back to the desktop assets, shadows and grass
      sun.shadow.mapSize.set(tier.shadowMap, tier.shadowMap);
      sun.shadow.map?.dispose();
      sun.shadow.map = null;
      $("hud").classList.remove("hidden");
    });
  } catch (err) {
    $("xrNote").textContent = `Could not start VR: ${err.message}`;
  }
}
$("vr").addEventListener("click", enterVR);
$("ar").addEventListener("click", enterAR);
$("startAR").addEventListener("click", enterAR);
$("startVR").addEventListener("click", enterVR);
$("startDesktop").addEventListener("click", () => {
  ambience.start();
  $("start").hidden = true;
  $("hud").classList.remove("hidden");
  grabPointer();
});

if (navigator.xr) {
  navigator.xr.isSessionSupported("immersive-vr").then(ok => {
    if (!ok) $("xrNote").textContent =
      "This browser has WebXR but no headset session available. Open the same link in the Quest browser.";
  }).catch(() => {});
  navigator.xr.isSessionSupported("immersive-ar").then(ok => {
    arSupported = ok;
    if (!ok) { $("ar").disabled = true; $("startAR").disabled = true; }
  }).catch(() => {});
} else {
  $("xrNote").textContent = "No WebXR here. Open this link in the Quest browser to walk it in VR.";
}

/* ------------------------------------------------------------------ *
 *  Loading, resize, loop
 * ------------------------------------------------------------------ */
THREE.DefaultLoadingManager.onProgress = (_u, loaded, total) => {
  $("loadBar").style.width = `${Math.round((loaded / total) * 100)}%`;
};
THREE.DefaultLoadingManager.onLoad = () => {
  /* Every stage is made visible once and compiled up front. Without this
     the first time a stage appears the shaders compile mid-frame and the
     whole thing hitches — which is survivable when scrubbing by hand and
     ruinous during a timed sequence. */
  buildStageAnimation();
  for (const a of animated) a.mesh.visible = true;
  for (const r of removalState) r.mesh.visible = true;
  renderer.compile(scene, camera);
  applyStage(stageValue);

  console.info(`studio: ${studioParts} parts, garden: ${gardenParts} parts from the Blender master | ${renderer.info.render.triangles.toLocaleString()} triangles drawn`);
  $("loading").hidden = true;
  $("startDesktop").disabled = false;
  $("startVR").disabled = false;
  $("startAR").disabled = !arSupported;
};

addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
});

applyTime("midday");
for (const k of ["dusk"]) {                       // the rest load on first use; five EXRs up front is a Quest hitch
  const t = TIMES[k];
  new EXRLoader().setDataType(THREE.FloatType).load(`${t.hdri}?v=${BUILD}`, tex => {
    tex.mapping = THREE.EquirectangularReflectionMapping;
    alignSunToSky(tex, k);
    hdrCache.set(k, pmrem.fromEquirectangular(tex).texture);
    tex.dispose();
  });
}
setStage(1);

/* a hook for testing from the console: move the viewer, read the frame
   cost, drive the dials. Not a user-facing API. */
window.__garden = {
  player, camera, renderer, scene, composer,
  setStage, goToStage, setVariant, applyTime,
  get yaw() { return yaw; }, set yaw(v) { yaw = v; },
  get pitch() { return pitch; }, set pitch(v) { pitch = v; },
  get stage() { return stageValue; },
  get variant() { return variant; },
  get time() { return timeKey; },
  look(x, y, z, yawDeg, pitchDeg = 0) {
    player.position.set(x, 0, z);
    yaw = THREE.MathUtils.degToRad(yawDeg);
    pitch = THREE.MathUtils.degToRad(pitchDeg);
    camera.position.y = y;
  },
  stats() {
    const i = renderer.info.render;
    return { triangles: i.triangles, calls: i.calls, geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures };
  }
};
$("meta").textContent = siteKey ? tier.label : `${STUDIO.w} × ${STUDIO.d} m · ${STUDIO.ridge} m to the ridge · ${tier.label}`;

let lastFrame = performance.now();
renderer.setAnimationLoop(() => {
  const now = performance.now();
  const dt = Math.min(0.05, (now - lastFrame) / 1000);
  lastFrame = now;

  if (playing) {
    const next = stageValue + dt;          // five stages over roughly 30 seconds
    if (next >= 6) { setStage(6); playing = false; $("play").textContent = "Play build"; uiDirty = true; }
    else setStage(next);
  } else if (tween) {
    tween.t += dt / tween.dur;
    setStage(tween.from + (tween.to - tween.from) * easeOut(clamp01(tween.t)));
    if (tween.t >= 1) tween = null;
  }

  if (renderer.xr.isPresenting) {
    if (arMode) arPlacementControls(dt); else xrLocomotion(dt);
    updatePointer();
    if (uiDirty) drawPanel();
  } else {
    desktopLocomotion(dt);
  }

  shadowFollow.update(camera);
  camera.getWorldPosition(sky.position);               // the sky sits at infinity: no parallax between the eyes
  blobs.update(camera, grips, renderer.xr.isPresenting);
  fade.update(dt);

  // footsteps from actual head travel, so physical walking counts too
  camera.getWorldPosition(_head);
  const travelled = Math.hypot(_head.x - _lastHead.x, _head.z - _lastHead.z);
  _lastHead.copy(_head);
  if (travelled < 0.5) stepDist += travelled;      // ignore teleport-sized jumps
  if (stepDist > 0.72) {
    stepDist = 0;
    ambience.step();
    if (renderer.xr.isPresenting && FOOTSTEP_HAPTICS) hapticPulse(controllers, 0.22, 35);
  }
  updateWind(now / 1000);
  if (ambience.started) {
    camera.getWorldPosition(_head);
    world.anchor.worldToLocal(_local.copy(_head));
    const walls = stageValue >= 4.99;
    ambience.setInside(walls && Math.abs(_local.x) < STUDIO.w / 2 && Math.abs(_local.z) < STUDIO.d / 2);
    ambience.update(dt);
  }
  // the slab is a 120 mm step up; stand on it, and on the deck in front
  {
    camera.getWorldPosition(_head);
    world.anchor.worldToLocal(_local.copy(_head));
    const onSlab = !siteKey && stageValue >= 2.99 && Math.abs(_local.x) < STUDIO.w / 2 + 0.3
      && _local.z > -STUDIO.d / 2 && _local.z < STUDIO.d / 2 + 1.8;
    const floorY = onSlab ? STUDIO.floorLevel - 0.02 : 0;
    player.position.y += (floorY - player.position.y) * Math.min(1, dt * 5);
  }

  const target = renderer.xr.isPresenting && !arMode && speedNow > 0.05 ? 0.5 : 0;
  vignette.material.opacity += (target - vignette.material.opacity) * Math.min(1, dt * 8);
  vignette.visible = vignette.material.opacity > 0.01;

  if (renderer.xr.isPresenting) renderer.render(scene, camera);
  else composer.render();
});
