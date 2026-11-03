import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { EXRLoader } from "three/addons/loaders/EXRLoader.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { createFade, attachControllerModels, hapticPulse } from "../presence.js?v=f383e46-1642";
import { createModel, progress } from "./model.js?v=h18";
import { buildBVH } from "./bvh.js?v=h15";
import { createSection, XRAY } from "./section.js?v=h11";
import { createMeasure } from "./measure.js?v=h11";
import { createWalker, BODY } from "./walk.js?v=h34";
import { createEditor } from "./edits.js?v=h15";
import { checkRules } from "./rules.js?v=h11";
import { modeFromURL, PLAIN_GROUP, PLAIN_CATEGORY, TAB_LABEL } from "./modes.js?v=h22";
import { createMarks, KINDS as MARK_KINDS } from "../marks.js?v=h31";
import { createVRBoard, renderBoardDOM, createCard, createBoardTab } from "./board.js?v=h15";
import { createDoors, isLeaf } from "./doors.js?v=h15";
import { createPerf } from "./perf.js?v=h15";
import { createCull } from "./cull.js?v=h33";
import { wallFrame, layerSpans, CATALOGUE, setTiles } from "./geom.js?v=h11";
import { moveWall, addWall, addOpening, swapFixture } from "./editops.js?v=h11";
import { loadRegs, isVerified, extensionText, INSPECTION_POINTS } from "./regs.js?v=h15";
import { createRequests, createRecorder } from "./requests.js?v=h11";
import { MotionBlurPass, createXRBlur } from "./motionblur.js?v=h22";

/* ------------------------------------------------------------------ *
 *  Build-stage viewer: a house extension built stage by stage from
 *  the plans, walkable at true scale on a laptop, a phone or a Quest 3.
 *
 *  house.html?site=<name>&version=<id>&mode=customer|review|builder|inspector|architect
 *  Data (src/house/CONTRACT.md): versions.json lists the versions; each
 *  has a GLB of parts carrying the contract's extras, a stages sidecar
 *  (stages, section planes, spawn points) and an elements file (the
 *  parametric design edits act on). regs.json holds the regulations.
 *
 *  What you PICK fills the BOARD (the right controller's laser and its
 *  trigger in the headset, a click on a screen) and the board holds it
 *  until you pick something else: a clipboard in your left hand in the
 *  headset (turn the wrist up; Y minimises it to a tab on the wrist), a
 *  side panel on a screen. Tabs: plans, spec, regs, build notes, change
 *  requests, tools. Doors open, you can fly, and the Heights tool reads
 *  ceilings and beams against your own eye height.
 * ------------------------------------------------------------------ */

const $ = id => document.getElementById(id);
const clamp01 = t => t < 0 ? 0 : t > 1 ? 1 : t;
const easeOut = t => 1 - Math.pow(1 - t, 3);
const params = new URLSearchParams(location.search);
const SITE = (params.get("site") || "house").replace(/[^a-z0-9_-]/gi, "");
const BASE = `assets/sites/${SITE}/`;
const MODE = modeFromURL();
/* review (Jack's studio review) is the homeowner mode plus the marking tool: it looks and behaves as "customer"
   everywhere (MODE.as), and only the marking code asks for MODE.marks */
document.documentElement.dataset.mode = MODE.as;
if (MODE.marks) document.documentElement.dataset.review = "1";
const CUST = MODE.as === "customer";
const IS_TOUCH = matchMedia("(pointer: coarse)").matches;
/* Homeowner mode, simplified (Jack, 1 Nov, round 6c): Before / After and Fly only. Before = the proposal's stage 1
   (the house before the works), After = its last stage (finished, with the garden). Walking, teleport, snap turn,
   fly, opening a door by pointing at it, and the Height check stay; no stage list, board tabs or tools. */
const SIMPLE = CUST;

/* ------------------------------------------------------------------ *
 *  Renderer, scene, light
 * ------------------------------------------------------------------ */
const IS_QUEST = /OculusBrowser|Quest/i.test(navigator.userAgent);
/* phones and tablets get the headset's light assets and no screen post (Jack, 1 Nov: "unusably laggy on my phone": a phone
   was loading the full GLB, the 4k sky, 2048 shadows, GTAO at pixel ratio 2 and preloading the second version) */
const IS_PHONE = !IS_QUEST && (/Android|iPhone|iPad|Mobile/i.test(navigator.userAgent) || (matchMedia("(pointer: coarse)").matches && Math.min(screen.width, screen.height) < 900));
const LITE = IS_QUEST || IS_PHONE;
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(devicePixelRatio, IS_PHONE ? 1.25 : 2));
renderer.setSize(innerWidth, innerHeight);
renderer.localClippingEnabled = true;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.NeutralToneMapping;         // Khronos PBR Neutral: keeps the brick and tile colours sampled from Jack's frames
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;             // soft via shadow.radius (PCFSoftShadowMap is deprecated in r185)
renderer.shadowMap.autoUpdate = false;                    // the house only changes when the stage does: re-render the shadow then
renderer.xr.enabled = true;
renderer.xr.setReferenceSpaceType("local-floor");
document.body.appendChild(renderer.domElement);
const MAX_ANISO = renderer.capabilities.getMaxAnisotropy();

/* ------------------------------------------------------------------ *
 *  The look (renders/house-build/VIEWER-LOOK.md): the garden's midday
 *  sky as image-based light and background, the garden's FILMED sun
 *  (azimuth -138, elevation 22), soft shadows fitted to the house,
 *  ambient occlusion from the materials' ORM maps plus GTAO on a screen.
 * ------------------------------------------------------------------ */
/* The sun (PLAN S7/S8). Compass bearing from north (house +x = north, +z = east) and elevation, as spec_v1 "lighting":
   afternoon = Hailsham, 23 Sep, 16:00 BST: bearing 234 (south-west), elevation 25, 5000 K: the spec's interior sun, which comes
   in through the rear glazing and lays bright patches on the kitchen-diner floor; filmed = the garden's solved sun (site.json
   azimuthDeg -138, elevationDeg 22 = bearing 138, south-east, from Jack's own shadows, CORRECTIONS-LOG 14): the street front is lit,
   for the matched front views. ?sun=filmed picks it. Everything that sets the look is in this one block: revert it to go back. */
const sunVec = (bearing, el) => { const b = THREE.MathUtils.degToRad(bearing), e = THREE.MathUtils.degToRad(el); return new THREE.Vector3(Math.cos(e) * Math.cos(b), Math.sin(e), Math.cos(e) * Math.sin(b)); };
const SUNS = { afternoon: { dir: sunVec(234, 25), colour: 0xffe4ce }, filmed: { dir: sunVec(138, 22), colour: 0xffeedd } };
const SUN_KEY = SUNS[params.get("sun")] ? params.get("sun") : "afternoon";
const LOOK = {
  hdri: "assets/hdri/kloofendal_43d_clear_puresky_2k.exr",
  sky: LITE ? "assets/hdri/sky_midday_2k.jpg" : "assets/hdri/sky_midday_4k.jpg",
  sunDir: SUNS[SUN_KEY].dir.clone().normalize(), sunColour: SUNS[SUN_KEY].colour,      // TO the sun, viewer frame
  sunIntensity: 9.0,                         // against a fill of about a fifth of it: sunlit floor about 4 x its shade, as the Airbnb frames
  envIntensity: 0.28,                        // the blue sky map: reflections and a little sky; it was the whole fill (0.85) and made every interior blue-grey
  hemi: 0.55, hemiSky: 0xfff7ec, hemiGround: 0xd9bf9c,      // a warm fill (oak floor bounce below, warm white above): shadows are never blue
  bounce: 0.3, bounceColour: 0xffeedd,       // the floor's bounce on every downward face, so ceilings read warm white, not slate
  exposureLite: 1.0,                         // phones and the headset: one fixed exposure, no per-frame cast (a cast costs about 1 ms on a laptop; unmeasured on a headset, PLAN S10)
  exposureIn: 1.5, exposureOut: 0.6,         // eye adaptation: the sun is about 9 against an indoor fill of about 1, so a camera with a roof over it exposes for the room (shaded walls cream, a sunlit patch bright, not blown), one in the open for the sun (brick and gravel keep their colour). Khronos Neutral tone mapping holds colour to 0.8 and compresses above.
};
renderer.toneMappingExposure = LOOK.exposureOut;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xbcd0e2);            // until the sky arrives: a sky colour, never grey
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;   // stand-in until the EXR is in
scene.environmentIntensity = LOOK.envIntensity;
const hemi = new THREE.HemisphereLight(LOOK.hemiSky, LOOK.hemiGround, LOOK.hemi);
scene.add(hemi);
const bounce = new THREE.DirectionalLight(LOOK.bounceColour, LOOK.bounce);       // from below, pointing up, no shadow
bounce.position.set(0, -1, 0);
scene.add(bounce);
const sun = new THREE.DirectionalLight(LOOK.sunColour, LOOK.sunIntensity);
sun.castShadow = true;
sun.shadow.mapSize.set(LITE ? 1024 : 2048, LITE ? 1024 : 2048);
sun.shadow.bias = -0.0005;
sun.shadow.normalBias = 0.02;
sun.shadow.radius = LITE ? 1.5 : 3.5;
scene.add(sun, sun.target);
const sky = new THREE.Mesh(new THREE.SphereGeometry(300, 48, 24),
  new THREE.MeshBasicMaterial({ side: THREE.BackSide, toneMapped: false, depthWrite: false, fog: false, color: 0xffffff }));
/* drawn AFTER everything opaque (depth-tested, not written): only the pixels the house and garden leave are shaded.
   Drawn first, as it was, every pixel was shaded twice (round 6c, the Quest frame rate) */
sky.renderOrder = 20; sky.frustumCulled = false; sky.visible = false;
scene.add(sky);

/* fit the sun's shadow box tightly round the house (+ a margin for the garden shadows) */
function fitSun(bounds) {
  const c = bounds.getCenter(new THREE.Vector3()), r = bounds.getBoundingSphere(new THREE.Sphere()).radius + 2;
  sun.target.position.copy(c);
  sun.position.copy(c).addScaledVector(LOOK.sunDir, r * 2);
  Object.assign(sun.shadow.camera, { left: -r, right: r, top: r, bottom: -r, near: 0.5, far: r * 4 });
  sun.shadow.camera.updateProjectionMatrix();
  renderer.shadowMap.needsUpdate = true;
}

/* the sky: the EXR lights the scene (its sun disc clamped out: the DirectionalLight IS the sun), the JPEG is
   what you see; both turned about the vertical so the sky's own sun sits where the filmed sun is */
function loadSky() {
  if (LITE) return loadSkyLight();
  new EXRLoader().setDataType(THREE.FloatType).load(LOOK.hdri, tex => {
    const { data, width, height } = tex.image;
    let best = -1, bi = 0, sum = 0, n = 0;
    for (let i = 0; i < data.length; i += 4) { const l = data[i] + data[i + 1] + data[i + 2]; if (l > best) { best = l; bi = i / 4; } sum += l; n++; }
    const cap = (sum / n) * 12;
    for (let i = 0; i < data.length; i += 4) { const l = data[i] + data[i + 1] + data[i + 2]; if (l > cap) { const k = cap / l; data[i] *= k; data[i + 1] *= k; data[i + 2] *= k; } }
    tex.needsUpdate = true;
    const u = ((bi % width) + 0.5) / width;
    const skySunAz = (u - 0.5) * Math.PI * 2;                     // equirect longitude of the sky's sun
    const wantAz = Math.atan2(LOOK.sunDir.z, LOOK.sunDir.x);
    const yaw = skySunAz - wantAz;
    tex.mapping = THREE.EquirectangularReflectionMapping;
    scene.environment = pmrem.fromEquirectangular(tex).texture;
    scene.environmentRotation.set(0, yaw, 0);
    tex.dispose();
    new THREE.TextureLoader().load(LOOK.sky, jpg => {
      jpg.colorSpace = THREE.SRGBColorSpace;
      jpg.wrapS = THREE.RepeatWrapping; jpg.repeat.x = -1; jpg.offset.x = 1;     // inside-out sphere
      jpg.anisotropy = Math.min(MAX_ANISO, 8);
      sky.material.map = jpg; sky.material.needsUpdate = true;
      sky.rotation.y = yaw; sky.visible = true;
      scene.background = null;
    });
  }, undefined, err => console.warn("house: sky failed, keeping the room light", err));
}
/* the headset: no float EXR decode and no 2k prefilter at load. The sky JPEG is the background, and the lighting
   comes from it shrunk to 256 x 128 first (a prefilter of that costs a few ms), done after the first frame. */
function loadSkyLight() {
  /* (the headset and phones take the same LOOK: hemi / env / sun above; the old 0.45 hemisphere lit a blue sky. Not yet measured on a headset: PLAN S10) */
  new THREE.TextureLoader().load(LOOK.sky, jpg => {
    jpg.colorSpace = THREE.SRGBColorSpace;
    jpg.wrapS = THREE.RepeatWrapping; jpg.repeat.x = -1; jpg.offset.x = 1;
    sky.material.map = jpg; sky.material.needsUpdate = true; sky.visible = true; scene.background = null;
    requestAnimationFrame(() => setTimeout(() => {
      const cv = document.createElement("canvas"); cv.width = 256; cv.height = 128;
      cv.getContext("2d").drawImage(jpg.image, 0, 0, 256, 128);
      const small = new THREE.CanvasTexture(cv);
      small.colorSpace = THREE.SRGBColorSpace; small.mapping = THREE.EquirectangularReflectionMapping;
      scene.environment = pmrem.fromEquirectangular(small).texture;
      small.dispose();
    }, 50));
  });
}
loadSky();

const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.03, 400);
const player = new THREE.Group();            // the rig: feet on the floor, the camera rides in it
player.add(camera);
scene.add(player);
const EYE = 1.65;                            // the DESKTOP walk's eye height; in the headset the real head height is used, nothing added
const fade = createFade(camera);
/* eye adaptation (see LOOK.exposureIn / exposureOut): is there a roof, ceiling or floor over the camera within 6 m? Foliage does not count (a tree is shade, not a room). Checked 5 times a second. */
const _upRay = new THREE.Raycaster(), _camPos = new THREE.Vector3(), SHADE = /leaves|branches|VertexPlant|hedge|conifer|foliage|ivy/i;
_upRay.ray.direction.set(0, 1, 0); _upRay.far = 6; _upRay.layers.enableAll();      // (cull.js moves a batch with nothing in view off the camera's layer: the probe must still see its ceiling)
let exposureNow = LOOK.exposureOut, coverAt = 0;
function adaptExposure(dt, snap = false) {
  if (LITE) { renderer.toneMappingExposure = LOOK.exposureLite; return; }
  if (!V) return;
  const t = performance.now();
  if (snap || t - coverAt > 200) {
    coverAt = t;
    _upRay.ray.origin.copy(camera.getWorldPosition(_camPos));
    const covered = _upRay.intersectObject(V.model.root, true).some(h => h.object.visible && !SHADE.test(h.object.name || "") && !h.object.isSprite);
    adaptExposure.target = covered ? LOOK.exposureIn : LOOK.exposureOut;
  }
  const want = adaptExposure.target ?? LOOK.exposureOut;
  exposureNow = snap ? want : exposureNow + (want - exposureNow) * Math.min(1, dt * 4);
  renderer.toneMappingExposure = exposureNow;
}
attachControllerModels(renderer, player);
/* a simulated headset for desktop tests (?xrsim=1 or __house.sim.start()): fake controllers drive the same VR code */
const SIM = { on: false };
const inVR = () => renderer.xr.isPresenting || SIM.on;
/* the frame log and HUD (perf.js); it POSTs to /house/perf from the headset (or with ?perf=1) */
const perf = createPerf({ renderer, site: SITE, scene, inXR: inVR, info: () => ({
  mode: MODE.key, version: V?.def.id, stage: Math.round(stageValue * 100) / 100, xr: renderer.xr.isPresenting, sim: SIM.on,
  board: inVR() ? boardState() : "screen", boardTab, tool, flying, hovering, loading: loadingNow,
  head_y: +camera.getWorldPosition(new THREE.Vector3()).y.toFixed(3), rig_y: +player.position.y.toFixed(3),
  eye_above_floor: inVR() ? +eyeAndFloor().eye.toFixed(3) : EYE, eye_raw: inVR() ? +rawEye().toFixed(3) : null,
  floor_offset: +floorOffset.toFixed(3), person_m: personHeight, vr_quality: vrQuality,
  passes: passBreakdown(),
  board_draws: vrBoard.stats.bodyDraws, board_max_ms: +vrBoard.stats.maxBodyMs.toFixed(1),
}) });
camera.add(perf.hud);
/* what the draw calls are made of: per eye in the headset (WebGLRenderer draws each eye separately, so XR calls are
   twice these), house and setting batches live now, the overlays shown, and whether a shadow pass ran since the last
   summary (the sun's shadow only re-renders on a stage change) */
let shadowPasses = 0;
function passBreakdown() {
  if (!V) return null;
  const live = { house: 0, setting: 0, edited: 0 };
  for (const o of V.model.root.children) { if (o.isBatchedMesh && o.visible) live.house++; }
  for (const o of V.model.root.getObjectByName("setting")?.children || []) if (o.visible) live.setting++;
  for (const o of V.model.root.getObjectByName("edited")?.children || []) if (o.visible) live.edited++;
  const over = [["sky", sky], ["board", vrBoard.mesh], ["hud", perf.hud], ["laser", laser], ["laser dot", laserDot], ["hover", hover], ["pick fill", hl.fill], ["pick edges", hl.edges], ["scale figure", scaleCue], ["heights label", heightLabel], ["card", card.mesh], ["vignette", vignette]]
    .filter(([, o]) => o && o.visible && (o.parent === scene || o.parent?.visible !== false)).map(([n]) => n);
  const cs = V.cull?.state, hid = V.cull ? V.model.root.children.filter(o => o.isBatchedMesh && o._cull?.hidden).length : 0;
  const out = { eyes: renderer.xr.isPresenting ? 2 : 1, ...live, overlays: over, shadow_passes: shadowPasses, shadows: renderer.shadowMap.enabled, cull: V.cull ? { active: cs.active, why: cs.why || null, cells: cs.cells.length, empty_batches_skipped: hid } : null };
  shadowPasses = 0;
  return out;
}

const orbit = new OrbitControls(camera, renderer.domElement);
orbit.enableDamping = true;
orbit.dampingFactor = 0.12;
orbit.maxPolarAngle = Math.PI * 0.495;
orbit.screenSpacePanning = true;

/* desktop / phone post: GTAO at a small radius makes wall junctions, joists and rafters read; the headset
   renders straight (WebXR's own framebuffer; the ORM ambient occlusion carries it there) */
let composer = null, gtao = null, blurPass = null;
const xrBlur = createXRBlur(renderer, player);     // the headset's motion blur (src/house/motionblur.js)
/* the rule (Jack, 1 Nov): motion blur must never take the Quest below a steady 72 fps. While it is drawing, every
   36 frames are timed against the frames without it; if they average slower than 68 fps (and slower than without
   it), the offscreen copy drops a step (70 % -> 60 % -> 50 % of the eye buffer); at 50 % and still slow, Comfort
   switches itself to the vignette for this session and says so. Each judgement goes to the frame log. */
const blurGov = { last: 0, n: 0, sum: 0, dn: 0, dsum: 0 };
function blurGovernor(now, blurred) {
  const dtMs = blurGov.last ? now - blurGov.last : 0;
  blurGov.last = now;
  if (!dtMs || dtMs > 100) return;                         // a hitch from loading or a version swap is not the blur
  if (!blurred) { blurGov.dn++; blurGov.dsum += dtMs; if (blurGov.dn > 720) { blurGov.dn /= 2; blurGov.dsum /= 2; } return; }
  blurGov.n++; blurGov.sum += dtMs;
  if (blurGov.n < 36) return;
  const avg = blurGov.sum / blurGov.n, base = blurGov.dn ? blurGov.dsum / blurGov.dn : 1000 / 72;
  blurGov.n = blurGov.sum = 0;
  const slow = avg > 1000 / 68 && avg > base + 0.7;
  perf.note({ event: "motion blur fps", fps: +(1000 / avg).toFixed(1), fps_without: +(1000 / base).toFixed(1), scale: xrBlur.state.scale, slow });
  if (!slow) return;
  if (xrBlur.state.scale > 0.51) { xrBlur.state.scale = Math.round((xrBlur.state.scale - 0.1) * 10) / 10; return; }
  setComfort("vignette");
  showCard("Comfort", [`Motion blur ran at ${(1000 / avg).toFixed(0)} fps on this headset, under the 72 fps it must hold, so Comfort is now the vignette for this visit.`, "Comfort on your left wrist switches it back."], null, 10);
}
if (!LITE) {
  composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(innerWidth * renderer.getPixelRatio(), innerHeight * renderer.getPixelRatio(),
    { type: THREE.HalfFloatType, samples: 4 }));
  composer.addPass(new RenderPass(scene, camera));
  gtao = new GTAOPass(scene, camera, innerWidth, innerHeight);
  gtao.output = GTAOPass.OUTPUT.Default;
  gtao.updateGtaoMaterial({ radius: 0.4, distanceExponent: 1.2, thickness: 0.5, scale: 1.0, samples: 16 });
  /* GTAO's depth / normal pass skips points and lines but drew SPRITES (the marks' labels, the scale figure's tags) as
     solid quads, which came out as black boxes over every label (r7b). Sprites are left out of it too. */
  gtao._overrideVisibility = function () {
    const cache = this._visibilityCache;
    this.scene.traverse(o => { if ((o.isPoints || o.isLine || o.isLine2 || o.isSprite) && o.visible) { o.visible = false; cache.push(o); } });
  };
  composer.addPass(gtao);
  /* homeowner / review: camera motion blur on turns and fast moves (Comfort: blur; src/house/motionblur.js) */
  if (SIMPLE) { blurPass = new MotionBlurPass(camera); composer.addPass(blurPass); }
  composer.addPass(new OutputPass());
}

/* ------------------------------------------------------------------ *
 *  State
 * ------------------------------------------------------------------ */
const versions = new Map();                  // id -> {def, sidecar, model, bvh, editor, rules}
let V = null, manifest = null, lastProposal = null, regs = null, materialsJson = null;
let stageValue = 1, stageN = 1, playing = false, tween = null, stageDirty = true;
let tool = "info";                            // info | measure | addwall
let xray = false, walk = false, showSpec = false;
/* "Seated" (+45 cm) was removed in round 6c: the Height check now sets the eyes to the person's STANDING eye height
   whether they sit or stand (Jack uses both). Kept as a constant so old code paths read it as off. */
const seated = false;
let flying = false, landing = null;           // fly mode (VR: right grip held + right stick; desktop: F) and the ease back down
let hovering = false;                         // VR: the grip let go mid-air, holding the height until the left grip lands
let boardMin = false;                         // the VR board minimised to a tab on the left wrist (Y)
/* the Height check (round 6c: the Quest logged eyes 1.14-1.24 m above the floor for a 1.854 m man standing): the
   person's height (remembered), and the rig lift that puts the eyes at height x 0.936 */
const store = { get: (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch (_) { return d; } },
                set: (k, v) => { try { localStorage.setItem(k, String(v)); } catch (_) {} } };
/* Jack, 1 Nov: "set the height so the walkthrough is at 4ft, because that feels more scaled to me when I'm walking
   through; I tested it a couple of times." The default person height is 4 ft (1.219 m), applied automatically at the
   start of every VR session (every mode), still adjustable (wrist Height -/+ 1 in, board Tools) and remembered. The
   storage key was bumped (v2) so values left from earlier tests (1.854) give way to the 4 ft default once. */
const DEFAULT_PERSON = 1.219;
const HEIGHT_KEY = "house-person-height-v2";
let personHeight = Math.min(2.3, Math.max(1.0, parseFloat(store.get(HEIGHT_KEY, String(DEFAULT_PERSON))) || DEFAULT_PERSON));
let floorOffset = 0;                          // metres added to the rig by the Height check (this session)
const rigLift = () => floorOffset;
let scaleCue = null;                          // the 1.80 m figure and 1 m post
let target = null;                            // {part, point, source, at}: what the board is about
let boardTab = MODE.tabs[0];
const section = createSection(() => [...versions.values()].flatMap(v => v.model ? [...v.model.sets.values()] : []));
const measure = createMeasure(scene);
const walker = createWalker(() => V.bvh, () => V.model.masks.solid);
const requests = createRequests({ site: SITE, getVersion: () => V?.def.id, mode: MODE.key });
const recorder = createRecorder();
const inspections = new Map();                // inspection point id -> {checks: {key: {status, note, at}}}
const yawPitch = { yaw: 0, pitch: 0 };
const feet = new THREE.Vector3();
let wallDraft = null;                         // first point of an add-wall
let attachEdits = MODE.edit;

/* ------------------------------------------------------------------ *
 *  Loading
 * ------------------------------------------------------------------ */
let loadLabel = "", loadingNow = false;
const setLoad = (f, text) => {
  $("loadBar").style.width = `${Math.round(f * 100)}%`;
  if (text) { $("loadText").textContent = text; loadLabel = text; }
  if (renderer.xr.isPresenting) {                          // the page's bar is invisible in the headset
    if (f >= 1) card.hide(); else showCard("Loading…", [loadLabel], f);
  }
};
const fetchJSON = async url => {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
};

async function loadVersion(id, quiet = false) {
  if (versions.get(id)?.model) return versions.get(id);
  if (versions.get(id)?.loading) return versions.get(id).loading;
  const def = manifest.versions.find(v => v.id === id);
  const job = (async () => {
    const show = !quiet, t0 = performance.now();
    let entryFile = null;
    if (show) loadingNow = true;
    if (show) { $("loading").hidden = false; setLoad(0.05, `Loading ${def.name}…`); }
    const [sidecar, elements] = await Promise.all([
      fetchJSON(BASE + def.stages),
      def.elements ? fetchJSON(BASE + def.elements).catch(() => null) : null,
    ]);
    /* the headset loads a version's small-texture GLB when the generator wrote one (CONTRACT.md: glb_quest), and
       its meshopt-compressed twin (glb_quest_meshopt: EXT_meshopt_compression + KHR_mesh_quantization) first, falling
       back to glb_quest if that fails to decode. ?glb=quest | meshopt forces either on a desktop (tests). */
    const want = params.get("glb") || (LITE ? "meshopt" : "full");
    const questGlb = want !== "full" && def.glb_quest;
    const tries = [...(want === "meshopt" && def.glb_quest_meshopt ? [def.glb_quest_meshopt] : []), questGlb || def.glb];
    const load = file => new Promise((res, rej) => new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).load(BASE + file, res,
      xhr => show && xhr.total && setLoad(0.08 + 0.72 * xhr.loaded / xhr.total, `Loading the model · ${(xhr.loaded / 1e6).toFixed(1)} MB`), rej));
    let gltf = null;
    for (const file of tries) {
      try { gltf = await load(file); entryFile = file; break; }
      catch (err) { console.warn(`house: ${file} failed (${err?.message || err}); trying the next`); perf.note({ event: "glb failed", file, error: String(err?.message || err).slice(0, 200) }); if (file === tries[tries.length - 1]) throw err; }
    }
    if (show) setLoad(0.82, "Sorting parts into stages…");
    if (LITE && !questGlb) await shrinkTextures(gltf.scene, 512);
    prepareForBatching(gltf.scene);
    await new Promise(r => setTimeout(r));
    const model = createModel({ gltf, sidecar, elements, section, materials: materialsJson, onBuildProgress: f => show && setLoad(0.82 + 0.12 * f) });
    model.root.visible = false;
    scene.add(model.root);
    const entry = { def, sidecar, model, bvh: buildBVH(model.parts), rules: [] };
    entry.editor = createEditor({ site: SITE, version: id, elements, onChange: (cur, ids) => onEdit(entry, cur, ids) });
    entry.doors = createDoors({ model, bvh: entry.bvh, roomAt: model.roomAt, table: entry.editor.current() });
    /* room visibility (cull.js, PLAN S10): only on a stage where the cells' walls all stand, no slice, no x-ray, no storey hidden; ?cull=0 turns it off */
    entry.cull = params.get("cull") === "0" ? null : createCull({ model, scene, getBvh: () => entry.bvh, canCull: () => !entry.edited && !section.active && !xray && stageValue >= entry.sidecar.stages.length - 1e-3 && Object.values(storeyState).every(Boolean) });
    perf.note({ event: "gl caps", multi_draw: renderer.extensions.has("WEBGL_multi_draw"), max_textures: renderer.capabilities.maxTextures, note: "without multi_draw every instance of a batch is its own draw call" });
    if (entry.cull) perf.note({ event: "room culling", version: id, cells: entry.cull.cells.length, portals: entry.cull.portals, exclusive_parts: entry.cull.exclusive, shared_parts: entry.cull.shared });
    if (entry.doors.derived.length) console.info(`house: ${entry.doors.derived.length} of ${entry.doors.count} doors have no hinge extras; hinges derived`, entry.doors.derived);
    for (const s of model.sets.values()) {
      s.current = xray ? s.xray : s.normal;
      for (const t of s.targets) t.material = s.current;
      for (const k of ["map", "normalMap", "aoMap", "roughnessMap", "metalnessMap"]) if (s.normal[k]) s.normal[k].anisotropy = Math.min(MAX_ANISO, 8);
    }
    versions.set(id, entry);
    model.applyStage(sidecar.stages.length, true);        // compile with everything visible: no hitch on the first stage change
    /* the shaders compile in parallel where the browser can (KHR_parallel_shader_compile), not in one blocking call */
    if (show) { setLoad(0.97, "Preparing the materials…"); model.root.visible = true; await renderer.compileAsync(scene, camera); model.root.visible = false; loadingNow = false; setLoad(1, "Ready"); $("loading").hidden = true; }
    entry.file = entryFile;
    perf.note({ event: "version loaded", version: id, file: entryFile, ms: Math.round(performance.now() - t0), bvh_ms: Math.round(entry.bvh.ms), parts: model.parts.length, triangles: entry.bvh.triangles });
    return entry;
  })();
  versions.set(id, { def, loading: job });
  return job;
}

/* batching (model.js normaliseGeometry) keeps position, normal and one UV set, "uv". Two things rendered the furniture
   near-black (CORRECTIONS-LOG 234): maps reading another UV set (glTF texCoord 1, the spec items' textures), so that set
   moves into uv and the maps point at it; and materials from models with vertex colours (COLOR_0: vertexColors on), whose
   colours the batch drops, so the shader multiplied by black. Batches tint per instance anyway, so vertexColors goes off. */
function prepareForBatching(root) {
  const SLOTS = ["map", "normalMap", "roughnessMap", "metalnessMap", "aoMap", "emissiveMap", "alphaMap", "bumpMap"];
  const moved = new Map();                    // material -> the set its maps read (shared materials are remapped once)
  root.traverse(o => {
    if (!o.isMesh) return;
    for (const m of Array.isArray(o.material) ? o.material : [o.material]) {
      if (!m) continue;
      if (!moved.has(m)) {
        if (m.vertexColors && m.map) { m.vertexColors = false; m.needsUpdate = true; }   // textured only: the plants' green IS their vertex colour (row 296)
        const ch = SLOTS.map(s => m[s]?.channel).find(c => c > 0) || 0;
        for (const s of SLOTS) if (ch && m[s] && m[s].channel === ch) { m[s] = m[s].clone(); m[s].channel = 0; m[s].needsUpdate = true; }
        moved.set(m, ch);
      }
      const ch = moved.get(m);
      if (ch && o.geometry.attributes["uv" + ch]) o.geometry.setAttribute("uv", o.geometry.attributes["uv" + ch]);
    }
  });
}

/* the headset's GPU memory: ~120 WebP textures at 1024 px are ~700 MB once uploaded; at 512 px a quarter
   of that. Until the KTX2 step (VIEWER-LOOK.md), halve them on the Quest as they load. */
async function shrinkTextures(root, max) {
  const seen = new Set(), jobs = [];
  root.traverse(o => {
    if (!o.isMesh) return;
    for (const m of [].concat(o.material)) for (const k of ["map", "normalMap", "aoMap", "roughnessMap", "metalnessMap", "alphaMap"]) {
      const t = m[k], img = t?.image;
      if (!t || seen.has(t) || !img || !(img.width > max)) continue;
      seen.add(t);
      const h = Math.round(img.height * max / img.width);
      jobs.push(createImageBitmap(img, { resizeWidth: max, resizeHeight: h, resizeQuality: "high" })
        .then(bmp => { t.image = bmp; t.needsUpdate = true; }).catch(() => {}));
    }
  });
  await Promise.all(jobs);
}

/* the headset keeps ONE version in memory: the one being left is freed (geometry, materials, textures) */
const KEEP_ONE = LITE;
function dropVersion(entry) {
  if (!entry?.model) return;
  entry.model.dispose();
  for (const g of edgeGeo.values()) g.dispose();
  edgeGeo.clear();
  versions.delete(entry.def.id);
  perf.note({ event: "version freed", version: entry.def.id });
}
async function useVersion(id) {
  perf.tag("version load");
  const entry = await loadVersion(id);
  if (V && V !== entry) { V.model.root.visible = false; if (KEEP_ONE || renderer.xr.isPresenting) dropVersion(V); }
  V = entry;
  V.model.root.visible = true;
  if (renderer.xr.isPresenting && VRQ[vrQuality].lean) leanMaterials(true);
  for (const [s, on] of Object.entries(storeyState)) V.model.storeyShown[s] = on;
  markDoorsHidden();
  stageN = V.sidecar.stages.length;
  stageValue = Math.min(stageValue, stageN);
  fitSun(V.model.bounds);
  if (MODE.edit && !V.resumed) { V.resumed = true; const n = V.editor.resume(); if (n) toast(`${n} saved edit${n > 1 ? "s" : ""} restored`); }
  /* the As-built toggle starts as versions.json says (as_built_default: {"<mode>": true}); nothing else forces it,
     so a build sequence starts from the drawing of the house before the works (round 6: the 2022 front, no porch) */
  if (!V.asBuiltSet) { V.asBuiltSet = true; V.model.setAsBuilt(!!V.def.as_built_default?.[MODE.as] && V.model.hasAsBuilt); }
  setTarget(null);
  measure.clear();
  section.off();
  buildStageUI();
  buildSectionUI();
  setStage(stageValue, true);
  $("versionSel").value = id;
  if (V.def.kind === "proposal") lastProposal = id;
  $("before").setAttribute("aria-pressed", String(id === manifest.as_built_now));
  $("after").setAttribute("aria-pressed", String(id === lastProposal && id !== manifest.as_built_now));
  $("after").disabled = !lastProposal;
  $("asBuilt").hidden = !V.model.hasAsBuilt;
  $("asBuilt").setAttribute("aria-pressed", String(V.model.asBuilt));
  $("versionDesc").textContent = CUST
    ? (V.def.customer_description || (V.def.description || "").replace(/\s*\((?:BDS|drawings?)?[^)]*\d{4}[^)]*\)/gi, "").replace(/\b\d{4}\.\w+(\s*\/\s*\w+)*/g, "").trim())
    : V.def.description || "";
  history.replaceState(null, "", `?${new URLSearchParams({ ...Object.fromEntries(params), version: id })}`);
  runRules();
  marks?.refreshVisibility();
  gotoMenu.close();
  if (SIMPLE && !IS_QUEST) setTimeout(() => { try { places(); } catch (err) { console.warn("house: go to", err); } }, 0);   // the screen's Go to list
  requests.list().then(refreshBoard).catch(() => {});
  if (MODE.inspect) loadInspections();
  refreshBoard();
}

/* ------------------------------------------------------------------ *
 *  Stages
 * ------------------------------------------------------------------ */
const stageIndex = v => Math.min(stageN, Math.max(1, Math.ceil(v - 1e-6)));
const stageText = st => MODE.stageText === "customer" ? (st.customer_note || st.note) : st.note;
/* homeowners get plain titles: the stages JSON's customer_title when it has one, else a plain phrase for the trade name */
const CUSTOMER_TITLES = [
  [/house before|as built now|as it is/i, "Your house today"], [/strip|demoli/i, "Making space: old parts come out"],
  [/setting out|dig/i, "Marking out and digging"], [/trench|foundation|drain/i, "Foundations and drains"],
  [/substructure|to dpc/i, "Walls up to floor level"], [/slab|oversite/i, "The new ground floor is laid"],
  [/walls? to first|ground[- ]floor walls/i, "The downstairs walls go up"], [/steel/i, "Steel beams go in"],
  [/joist|deck/i, "The upstairs floor goes in"], [/walls? to plate|first[- ]storey walls|upstairs walls/i, "The upstairs walls go up"],
  [/roof structure|rafter/i, "The roof frame goes up"], [/felt|tiles|weathertight|windows|doors/i, "Roof on, windows and doors in"],
  [/first fix/i, "Pipes and wires go in"], [/plaster/i, "Plastering"], [/second fix|kitchen|decorat/i, "Kitchen, bathroom and decorating"],
  [/external|landscap|patio/i, "Outside: patio and garden"], [/finish|complete/i, "Finished"],
];
const stageTitle = st => !st ? "" : !CUST ? st.name
  : (st.customer_title || st.customer_name || CUSTOMER_TITLES.find(([rx]) => rx.test(st.name))?.[1] || st.name);
const stageName = n => stageTitle(V.sidecar.stages[n - 1]) || `stage ${n}`;
/* key stages for homeowners: the stages JSON's key_stage groups, else six even steps */
function keyStages() {
  const st = V.sidecar.stages, out = [];
  if (st.some(s => s.key_stage)) {
    st.forEach((s, i) => {
      const k = s.key_stage || out[out.length - 1]?.name || stageTitle(s);
      if (!out.length || out[out.length - 1].name !== k) out.push({ name: k, stages: [] });
      out[out.length - 1].stages.push(i + 1);
    });
    return out;
  }
  if (st.length === 12) return [["Today", [1]], ["Clearing and digging", [2, 3]], ["Foundations and the floor", [4, 5]],
    ["Walls, steels and the upstairs floor", [6, 7, 8, 9]], ["Roof, windows and doors", [10, 11]], ["Finished", [12]]]
    .map(([name, stages]) => ({ name, stages }));
  const n = Math.min(6, st.length), per = st.length / n;
  return [...Array(n)].map((_, k) => {
    const stages = []; for (let i = Math.round(k * per); i < Math.round((k + 1) * per); i++) stages.push(i + 1);
    return { name: stageTitle(st[stages[stages.length - 1] - 1]), stages };
  });
}
let showAllStages = false;
function setStage(v, force = false) {
  stageValue = Math.min(stageN, Math.max(1, v));
  stageDirty = true;
  if (force) applyStageNow();
}
function applyStageNow() {
  if (!V) return;
  perf.tag("stage");
  V.model.applyStage(stageValue, false);
  V.doors?.restage();
  const m = V.model.masks;
  for (const p of V.model.parts) m.structural[p.index] = m.visible[p.index] && p.set?.cls ? 1 : 0;
  stageDirty = false;
  renderer.shadowMap.needsUpdate = true;
  const i = stageIndex(stageValue), st = V.sidecar.stages[i - 1];
  const frac = stageValue - (i - 1);
  const building = stageN > 1 && frac < 0.999 && i > 1;
  $("stageName").textContent = stageN > 1 ? `${i} · ${stageTitle(st)}` : stageTitle(st);
  $("stageNote").textContent = stageText(st);
  $("stageState").textContent = stageN > 1 ? (building ? `building · ${Math.round(frac * 100)}%` : `stage ${i} of ${stageN} complete`) : "";
  $("scrub").value = String(stageValue);
  for (const b of document.querySelectorAll("#ticks button")) b.setAttribute("aria-pressed", String(+b.dataset.stage === i));
  for (const li of document.querySelectorAll("#stageList li[data-stage]")) li.classList.toggle("on", +li.dataset.stage === i);
  for (const li of document.querySelectorAll("#stageList li[data-key]")) li.classList.toggle("on", li.dataset.key.split(",").map(Number).includes(i));
  for (const li of document.querySelectorAll("#stageList li[data-point]")) li.classList.toggle("on", pointFor(i)?.id === li.dataset.point);
  if (target && !V.model.masks.visible[target.part.index]) setTarget(null);
  updateHighlight();
  boardDirty = true;
}
const nextStage = () => goToStage(Math.floor(stageValue + 1e-6) + 1);
const prevStage = () => goToStage(Math.ceil(stageValue - 1e-6) - 1);
function goToStage(n) {
  playing = false; updatePlay();
  tween = { from: stageValue, to: Math.min(stageN, Math.max(1, n)), t: 0, dur: Math.min(2.4, 0.7 + 0.5 * Math.abs(n - stageValue)) };
}
function togglePlay() {
  playing = !playing; tween = null;
  if (playing && stageValue >= stageN - 0.001) setStage(1, true);
  updatePlay();
}
function updatePlay() { $("play").textContent = playing ? "Pause" : "Play build"; boardDirty = true; }

/* building-control inspection points come from the regulations dataset, tagged with the DATASET's stage numbers
   (its own 12-stage list). A stages JSON stage says which of those it is with "regs_stage" (a number or a list);
   without that, a 12-stage sequence is taken as the dataset's own numbering. The viewer never hard-codes it. */
const regsStagesOf = n => {
  const st = V?.sidecar.stages[n - 1];
  if (st?.regs_stage != null) return [].concat(st.regs_stage);
  return stageN === 12 ? [n] : [];
};
const viewerStagesFor = pt => {
  if (pt.stages && !pt.dataset_stages) return pt.stages;
  const out = [];
  for (let n = 1; n <= stageN; n++) if (regsStagesOf(n).some(d => pt.dataset_stages.includes(d))) out.push(n);
  return out;
};
const inspectionPoints = () => (V?.sidecar.inspection_points || regs?.points || INSPECTION_POINTS).map(p => ({ ...p, stages: viewerStagesFor(p) }));
const pointFor = n => inspectionPoints().find(p => p.stages.includes(n) && p.id !== "IP-PLANS") || inspectionPoints().find(p => p.stages.includes(n));

function buildStageUI() {
  const st = V.sidecar.stages;
  $("scrub").max = String(st.length);
  $("stagebar").classList.toggle("single", st.length < 2);
  const ticks = $("ticks");
  ticks.textContent = "";
  st.forEach((s, i) => {
    const b = document.createElement("button");
    b.textContent = String(i + 1); b.title = stageTitle(s); b.dataset.stage = String(i + 1);
    b.addEventListener("click", () => goToStage(i + 1));
    ticks.appendChild(b);
  });
  const list = $("stageList");
  list.textContent = "";
  if (MODE.stageList === "inspection") return buildInspectionList();
  if (CUST && !showAllStages) {
    keyStages().forEach((k, ki) => {
      const li = document.createElement("li");
      li.dataset.key = k.stages.join(",");
      li.innerHTML = `<button><span class="n">${ki + 1}</span><span class="t"></span></button><p></p><div class="subs"></div>`;
      li.querySelector(".t").textContent = k.name;
      li.querySelector("p").textContent = stageText(st[k.stages[k.stages.length - 1] - 1]);
      li.querySelector("button").addEventListener("click", () => goToStage(k.stages[k.stages.length - 1]));
      if (k.stages.length > 1) for (const n of k.stages) {
        const b = document.createElement("button");
        b.className = "sub"; b.textContent = stageTitle(st[n - 1]);
        b.addEventListener("click", () => goToStage(n));
        li.querySelector(".subs").appendChild(b);
      }
      list.appendChild(li);
    });
    const more = document.createElement("li");
    more.innerHTML = `<button class="all">All ${st.length} stages ▸</button>`;
    more.querySelector("button").addEventListener("click", () => { showAllStages = true; buildStageUI(); applyStageNow(); });
    list.appendChild(more);
    return;
  }
  if (CUST) {
    const back = document.createElement("li");
    back.innerHTML = `<button class="all">◂ The 6 key steps</button>`;
    back.querySelector("button").addEventListener("click", () => { showAllStages = false; buildStageUI(); applyStageNow(); });
    list.appendChild(back);
  }
  st.forEach((s, i) => {
    const li = document.createElement("li");
    li.dataset.stage = String(i + 1);
    li.innerHTML = `<button><span class="n">${i + 1}</span><span class="t"></span></button><p></p>`;
    li.querySelector(".t").textContent = stageTitle(s);
    li.querySelector("p").textContent = stageText(s);
    li.querySelector("button").addEventListener("click", () => goToStage(i + 1));
    list.appendChild(li);
  });
}

/* ------------------------------------------------------------------ *
 *  Inspector: the checklist per inspection point
 * ------------------------------------------------------------------ */
const checkKey = (ruleId, elementId) => elementId ? `${ruleId}@${elementId}` : ruleId;
async function loadInspections() {
  for (const p of inspectionPoints()) inspections.set(p.id, await requests.loadInspection(p.id));
  buildInspectionList(); refreshBoard();
}
async function markCheck(pointId, key, status, note) {
  const rec = inspections.get(pointId) || { checks: {} };
  rec.checks = rec.checks || {};
  const old = rec.checks[key] || {};
  rec.checks[key] = { ...old, status: status ?? old.status ?? null, note: note ?? old.note ?? "", at: new Date().toISOString(), stage: stageIndex(stageValue) };
  inspections.set(pointId, rec);
  const where = await requests.saveInspection(pointId, { point: pointId, checks: rec.checks });
  toast(`${key}: ${rec.checks[key].status || "noted"} · saved to ${where}`);
  buildInspectionList(); refreshBoard();
}
function buildInspectionList() {
  if (MODE.stageList !== "inspection" || !V) return;
  const list = $("stageList");
  list.textContent = "";
  for (const pt of inspectionPoints()) {
    const li = document.createElement("li");
    li.dataset.point = pt.id;
    const rules = regs?.forInspection(pt.id) || [];
    const rec = inspections.get(pt.id)?.checks || {};
    const done = rules.filter(r => rec[r.id]?.status).length;
    li.innerHTML = `<button><span class="n"></span><span class="t"></span></button><div class="pt"></div>`;
    li.querySelector(".n").textContent = `${done}/${rules.length}`;
    li.querySelector(".t").textContent = `${pt.id.startsWith("IP-") ? pt.id + " · " : ""}${pt.name}${pt.stages.length ? ` · stage ${pt.stages.join(", ")}` : ""}`;
    li.querySelector("button").addEventListener("click", () => { if (pt.stages.length) goToStage(pt.stages[pt.stages.length - 1]); else li.classList.toggle("on"); });
    const box = li.querySelector(".pt");
    const p = document.createElement("p"); p.textContent = pt.description || pt.note || ""; box.appendChild(p);
    for (const r of rules) {
      const row = document.createElement("div");
      row.className = "chk";
      const st = rec[r.id]?.status;
      row.innerHTML = `<span class="rt"></span><span class="rb"></span><input type="text" placeholder="note" aria-label="Note">`;
      row.querySelector(".rt").textContent = `${isVerified(r) ? "" : "UNVERIFIED · "}${r.title} — ${r.document}, ${r.clause}${r.applies_to_extension === true ? "" : ` (extension: ${extensionText(r)})`}`;
      if (!isVerified(r)) row.querySelector(".rt").classList.add("unv");
      for (const s of ["checked", "pass", "fail"]) {
        const b = document.createElement("button");
        b.textContent = s; b.setAttribute("aria-pressed", String(st === s)); b.dataset.s = s;
        b.addEventListener("click", () => markCheck(pt.id, r.id, s));
        row.querySelector(".rb").appendChild(b);
      }
      const inp = row.querySelector("input");
      inp.value = rec[r.id]?.note || "";
      inp.addEventListener("change", () => markCheck(pt.id, r.id, null, inp.value));
      box.appendChild(row);
    }
    list.appendChild(li);
  }
  for (const li of list.querySelectorAll("li[data-point]")) li.classList.toggle("on", pointFor(stageIndex(stageValue))?.id === li.dataset.point);
}

/* ------------------------------------------------------------------ *
 *  Section, x-ray, storeys, as-built
 * ------------------------------------------------------------------ */
function sectionDefs() {
  const b = V.model.bounds, c = b.getCenter(new THREE.Vector3());
  return [
    ...(V.sidecar.sections || []),
    { name: "Free ↔", origin: c.toArray(), normal: [1, 0, 0], free: true },
    { name: "Free ↕", origin: c.toArray(), normal: [0, 0, -1], free: true },
    { name: "Plan cut", origin: [c.x, 1.2, c.z], normal: [0, -1, 0], free: true },
  ];
}
function buildSectionUI() {
  const sel = $("sectionSel");
  sel.textContent = "";
  sel.add(new Option("No slice", ""));
  for (const d of sectionDefs()) sel.add(new Option(d.note ? `${d.name} — ${d.note}` : d.name, d.name));
  $("sectionCtl").classList.add("off");
}
function setSection(name) {
  const d = name && sectionDefs().find(s => s.name === name);
  if (!d) { section.off(); $("sectionCtl").classList.add("off"); $("sectionSel").value = ""; }
  else {
    section.set(d);
    const size = V.model.bounds.getSize(new THREE.Vector3()).length() / 2 + 1;
    $("sectionOffset").min = String(-size); $("sectionOffset").max = String(size); $("sectionOffset").value = "0";
    $("sectionCtl").classList.remove("off");
    $("sectionSel").value = d.name;
    updateOffsetLabel();
  }
  boardDirty = true; updateHelp();
}
function nudgeSection(m) { section.setOffset(section.state.offset + m); $("sectionOffset").value = String(section.state.offset); updateOffsetLabel(); }
function updateOffsetLabel() { $("offsetLabel").textContent = `${Math.round(section.state.offset * 1000)} mm`; }

function setXray(on) {
  xray = on;
  for (const v of versions.values()) if (v.model) for (const set of v.model.sets.values()) {
    set.current = on ? set.xray : set.normal;
    for (const t of set.targets) { t.material = set.current; if (t.isBatchedMesh) t.sortObjects = !!set.current.transparent; }
  }
  $("xray").setAttribute("aria-pressed", String(on));
  renderer.shadowMap.needsUpdate = true;
  $("legend").hidden = !on || MODE.xray !== "full";
  boardDirty = true;
}
const storeyState = { site: true, ground: true, first: true, roof: true };
function setStorey(s, on) {
  storeyState[s] = on;
  renderer.shadowMap.needsUpdate = true;
  for (const v of versions.values()) if (v.model) v.model.setStorey(s, on);
  for (const b of document.querySelectorAll(`[data-storey="${s}"]`)) b.setAttribute("aria-pressed", String(!on));
  stageDirty = true; boardDirty = true;
}
function toggleAsBuilt() {
  V.model.setAsBuilt(!V.model.asBuilt);
  $("asBuilt").setAttribute("aria-pressed", String(V.model.asBuilt));
  stageDirty = true; boardDirty = true;
  toast(V.model.asBuilt ? "As built: site records replace the drawn parts they differ from" : "As drawn");
}

/* ------------------------------------------------------------------ *
 *  Picking, the target, its highlight
 * ------------------------------------------------------------------ */
function pickRay(ray) {
  if (!V) return null;
  const m = V.model.masks;
  const cast = mask => {
    /* an open (or opening) door is not where its BVH triangles are (they are at rest): look past them, then try
       the open leaves' own boxes where they have swung to */
    let h = null;
    const skipped = [];
    for (let k = 0; k < 4; k++) {
      h = V.bvh.raycast(ray, 60, mask, section.active);
      const p = h && V.model.parts[h.part];
      if (!p?.pose) break;
      skipped.push(p.index); mask[p.index] = 0; h = null;
    }
    for (const i of skipped) mask[i] = 1;
    h = h && { ...h, point: h.point.clone(), normal: h.normal.clone() };
    const d = V.doors?.pick(ray, h ? h.distance : 60);
    return d || h;
  };
  if (xray) {                                   // through the glass walls to the structure first
    const h = cast(m.structural);
    if (h) return h;
  }
  return cast(m.visible);
}
const partOf = hit => hit ? V.model.parts[hit.part] : null;

const hl = {
  fill: new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({
    color: 0xffd23f, transparent: true, opacity: 0.28, depthWrite: false, toneMapped: false,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 })),
  edges: new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({
    color: 0xffd23f, transparent: true, opacity: 0.85, depthTest: false, toneMapped: false })),
};
hl.fill.renderOrder = 950; hl.edges.renderOrder = 951;
hl.fill.matrixAutoUpdate = hl.edges.matrixAutoUpdate = false;
hl.fill.visible = hl.edges.visible = false;
scene.add(hl.fill, hl.edges);
const edgeGeo = new Map();
/* the edges of a big part (a whole ground, a long wall) cost tens of ms to find on the Quest: above this many
   indices the picked part shows its fill only */
const EDGE_MAX = 30000;
const partMatrix = (p, m) => { if (p.batch) p.batch.getMatrixAt(p.instanceId, m); else if (p.mesh) m.copy(p.mesh.matrix); return m; };
function updateHighlight() {
  const p = target?.part;
  if (!p) { hl.fill.visible = hl.edges.visible = false; return; }
  hl.fill.geometry = p.geometry;
  const big = p.geometry.index && p.geometry.index.count > EDGE_MAX;
  if (!big && !edgeGeo.has(p.geometry.uuid)) edgeGeo.set(p.geometry.uuid, new THREE.EdgesGeometry(p.geometry, 20));
  if (!big) hl.edges.geometry = edgeGeo.get(p.geometry.uuid);
  const m = partMatrix(p, new THREE.Matrix4());
  hl.fill.matrix.copy(m); hl.edges.matrix.copy(m);
  hl.fill.matrixWorldNeedsUpdate = hl.edges.matrixWorldNeedsUpdate = true;
  hl.fill.visible = p.now.visible;
  hl.edges.visible = p.now.visible && !big;
}
/* the part under the right laser (the headset) or the mouse (a screen): a lighter fill, no edges, nothing computed */
const hover = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial({
  color: 0xffffff, transparent: true, opacity: 0.16, depthWrite: false, toneMapped: false,
  polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
hover.renderOrder = 949; hover.matrixAutoUpdate = false; hover.visible = false;
scene.add(hover);
let hoverPart = null;
function setHover(p) {
  if (p && (p.context || p.group === "ground" || p === target?.part || !p.now.visible)) p = null;
  if (p === hoverPart && !(p && p.pose)) return;
  hoverPart = p;
  hover.visible = !!p;
  if (!p) return;
  hover.geometry = p.geometry;
  partMatrix(p, hover.matrix);
  hover.matrixWorldNeedsUpdate = true;
}
/* the board holds what was PICKED (a click, or the right trigger) until another pick or a pick of nothing */
function setTarget(part, point = null, source = "click", hit = null) {
  target = part ? { part, point: point?.clone() || null, source, at: performance.now(), heights: hit ? heightInfo(hit) : null } : null;
  if (part) vrBoard.resetPage();
  if (hoverPart === part) setHover(null);
  updateHighlight();
  refreshBoard();
}

/* ------------------------------------------------------------------ *
 *  Board content: what the part is, from the data, for this mode
 * ------------------------------------------------------------------ */
const area = poly => Math.abs(poly.reduce((s, [x, z], i) => { const [x2, z2] = poly[(i + 1) % poly.length]; return s + x * z2 - x2 * z; }, 0)) / 2;
const elOf = p => p && V.editor.get(p.element);
const T = (text, o = {}) => ({ type: "text", text, ...o });
const B = (items, cols = 3) => ({ type: "buttons", items, cols });

/* the owner's loft conversion (extras loft / no_regs): not on the drawings, so no regulations are mapped to it */
const noRegs = p => !!(p.ud.no_regs || p.ud.loft);
const LOFT_TEXT = "Converted by the owner, not on the drawings: measured by scan / to come from scan. No regulations are mapped to it.";
/* "measured from photos" counts as scaled: an estimate, never checkable as a drawn dimension */
const confText = c => c === "measured from photos" ? "measured from photos (treated as scaled)" : c || "—";
function specBlocks(p) {
  const u = p.ud;
  const out = [T(u.label || p.name, { bold: true })];
  if (u.element_label && u.element_label !== u.label) out.push(T(u.element_label));
  out.push(T(`Drawing: ${u.drawing || "—"} · ${confText(u.conf)}`, { dim: true }));
  out.push(T(`${p.category}${p.category === "temporary" ? " — typical, not from the drawings" : ""} · ${p.group} · ${p.storey}`, { dim: true }));
  if (p.asBuilt) out.push(T("AS BUILT record: differs from the drawing", { status: "warn" }));
  if (noRegs(p)) out.push(T(LOFT_TEXT, { status: "warn", size: 28 }));
  const rs = regs && !noRegs(p) ? regs.flat(regs.forPart(p, elOf(p), partFacts(p))) : [];
  if (rs.length) {                                   // the builder's rule tags: "this lintel must…"
    const top = rs.filter(r => r.applies_to_extension !== false && r.check_type !== "evidence" && r.part !== "Procedure")
      .sort((a, b) => (a.check_type === "numeric" ? 0 : 1) - (b.check_type === "numeric" ? 0 : 1)).slice(0, 4);
    out.push(T(`Must meet (${rs.length}): ${top.map(r => `${r.part === "Procedure" ? "" : `Part ${r.part} `}${r.title}${regs.valueText(r) && r.check_type === "numeric" ? ` (${regs.valueText(r).slice(0, 60)})` : ""}${isVerified(r) ? "" : " — unverified"}`).join(" · ")}${rs.length > top.length ? " · more on Regs" : ""}`, { dim: true, size: 28, max: 6 }));
  }
  out.push(T(`Element ${p.element}${u.layer !== undefined ? ` · layer ${u.layer}` : ""}${u.lift !== undefined ? ` · lift ${u.lift}` : ""}`, { dim: true, size: 26 }));
  return out;
}
function aboutBlocks(p) {
  const el = elOf(p), room = target.point ? V.model.roomAt(target.point.x, target.point.y, target.point.z) : null;
  const out = [T(PLAIN_CATEGORY[p.category] || "")];
  out.push(T(p.stage_in > 1 ? `It goes in at stage ${p.stage_in}: ${stageName(p.stage_in)}.` : "It is there before the works start.", { dim: true }));
  if (p.stage_out) out.push(T(`It comes out at stage ${p.stage_out}: ${stageName(p.stage_out)}.`, { dim: true }));
  if (room) out.push(T(`Room: ${room.params.name}, ${area(room.params.polygon).toFixed(1)} m². ${room.meta?.plain_label || ""}`));
  out.push(B([{ id: "spec", label: showSpec ? "Hide builder's spec" : "Show builder's spec", press: () => { showSpec = !showSpec; refreshBoard(); } }], 1));
  if (showSpec) out.push(...specBlocks(p).filter(b => !/^Element |^Must meet/.test(b.text || "")).map(b => ({ ...b, size: Math.min(b.size || 30, 28), dim: true })));
  return out;
}
function buildBlocks(p) {
  const el = elOf(p), cur = V.editor.current();
  const st = V.sidecar.stages[p.stage_in - 1];
  const out = [];
  if (p.stage_in > 1) { out.push(T(`Stage ${p.stage_in}: ${stageTitle(st)}`, { bold: true })); out.push(T(stageText(st || {}) || "")); }
  else out.push(T("There before the works (stage 1).", { bold: true }));
  out.push(T(`Order within the stage: ${Math.round(p.seq * 100)}%`, { dim: true }));
  if (p.stage_out) out.push(T(`Removed at stage ${p.stage_out}: ${stageName(p.stage_out)}`, { status: "warn" }));
  if (el?.bears_on?.length) out.push(T(`Bears on: ${el.bears_on.map(id => `${id} (${cur.get(id)?.meta?.group || cur.get(id)?.type || "?"})`).join(", ")}`));
  const carried = [...cur.values()].filter(e => !e.removed && (e.bears_on || []).includes(p.element));
  if (carried.length) out.push(T(`Carries: ${carried.map(e => `${e.id} (${e.meta?.group || e.type})`).join(", ")}`));
  if (MODE.inspect) out.push(T("Captured photos / scans of the build: none yet (overlay hook: captures.json, CONTRACT.md §13)", { dim: true, size: 26 }));
  return out;
}
/* what the regs mapping needs to know about a part beyond its extras: the room it is in, how far it is from a
   boundary line (fences, the boundary wall, the party wall), and whether it is glazing low enough to be critical */
let boundaryRects = null, boundaryFor = null;
function boundaries() {
  if (boundaryFor === V) return boundaryRects;
  boundaryFor = V;
  /* boundary features: anything labelled as on / along a boundary (fences, the boundary wall) and the party wall
     (a wall element with construction "party") */
  boundaryRects = V.model.parts.filter(q => (/boundary/i.test(q.ud.label || "") && /wall|fence|board/i.test(`${q.ud.label || ""} ${q.name}`))
      || V.editor.get(q.element)?.params?.construction === "party")
    .map(q => ({ x0: q.bbox.min.x, x1: q.bbox.max.x, z0: q.bbox.min.z, z1: q.bbox.max.z, id: q.element }));
  return boundaryRects;
}
function boundaryDistance(p) {
  let best = Infinity, which = null;
  const b = p.bbox;
  for (const r of boundaries()) {
    if (r.id === p.element) continue;
    /* to the boundary LINE: the centre of a thin boundary feature (a fence's boards, a wall's centre line) */
    const thinX = r.x1 - r.x0 < r.z1 - r.z0;
    const lx = (r.x0 + r.x1) / 2, lz = (r.z0 + r.z1) / 2;
    const along = thinX ? Math.max(0, r.z0 - b.max.z, b.min.z - r.z1) : Math.max(0, r.x0 - b.max.x, b.min.x - r.x1);
    const across = thinX ? Math.max(0, lx - b.max.x, b.min.x - lx) : Math.max(0, lz - b.max.z, b.min.z - lz);
    const d = Math.hypot(along, across);
    if (d < best) { best = d; which = r.id; }
  }
  return { d: best, id: which };
}
function partFacts(p) {
  const el = elOf(p), cur = V.editor.current();
  const pt = target?.part === p && target.point ? target.point : p.bbox.getCenter(new THREE.Vector3());
  const room = V.model.roomAt(pt.x, pt.y, pt.z)?.params.name || null;
  const bd = boundaryDistance(p);
  const op = el?.type === "opening" ? el : el?.params?.opening ? cur.get(el.params.opening) : null;
  const ffl = V.sidecar.storeys?.[p.storey] ?? 0;
  const glazed = /window|glaz|bi-fold|french|glass/i.test(`${p.ud.label || ""} ${p.materialName}`) || p.group === "window";
  const low_glazing = !!op && glazed && (op.params.sill - ffl) < 0.8;
  return { room, near_boundary: bd.d <= 1.0, boundary: bd, low_glazing, opening: op, ffl };
}

const CHECKED_BY_MODEL = new Set(["K-T1.1", "K-2RG", "K-1.11", "B-2.10a"]);
const RULE_OF_LIVE = { "stair-rise-going": ["K-T1.1", "K-2RG"], "stair-headroom": ["K-1.11"], "removed-wall-load": ["A-S1-A1"], "escape-window": ["B-2.10a"] };
function checkTypeText(r, p) {
  const conf = p.ud.conf;
  if (r.check_type === "judgement") return "Engineer / inspector judgement — never passed by the model";
  if (r.check_type === "evidence") return `Evidence needed: ${(r.evidence || []).join("; ") || "—"}`;
  if (r.check_type === "presence") return `Must be there: ${(r.evidence || []).join("; ") || "checked on site"}`;
  if (CHECKED_BY_MODEL.has(r.id)) return "Numeric — the model runs a live check on this (see above)";
  if (r.machine_checkable && conf === "exact") return "Numeric — this part is dimensioned on the drawing, so the value can be checked from it";
  if (r.machine_checkable) return `Numeric — this part's size is ${conf || "not stated"} in the model, so the model cannot confirm it: measure on the drawing or on site`;
  return "Numeric — measured on site or from the design";
}
function liabilityBlocks(compact = false) {
  const m = regs?.meta || {};
  const out = [];
  if (m.product_liability || m.liability) out.push(T(m.product_liability || m.liability, { size: compact ? 30 : 31, max: 14, status: "warn" }));
  if (m.not_for_construction) out.push(T(m.not_for_construction, { size: 30, bold: true, max: 6 }));
  return out;
}
function regsBlocks(p) {
  const el = elOf(p), f = partFacts(p);
  const out = [...liabilityBlocks()];
  if (noRegs(p)) out.push(T(LOFT_TEXT, { status: "warn", size: 30 }));
  const groups = (regs && !noRegs(p) ? regs.forPart(p, el, f) : []).sort((a, b) => (b.entry.prompt ? 1 : 0) - (a.entry.prompt ? 1 : 0));   // the part-specific prompts first
  const live = V.rules.filter(r => r.elementId === p.element || (f.opening && r.elementId === f.opening.id));
  if (live.length) {
    out.push(T("Live checks the model ran on this part", { bold: true }));
    for (const r of live) out.push(T(`${r.status === "unknown" ? "NOT MEASURED" : r.status.toUpperCase()} — ${r.message}`, { status: r.status, size: 30 }), T(r.clause, { dim: true, size: 28 }));
  }
  if (f.boundary.d < 5) out.push(T(`About ${f.boundary.d.toFixed(2)} m from the boundary (${f.boundary.id}; measured in the model, not from the site plan).`, { dim: true, size: 28 }));
  const total = regs ? regs.flat(groups).length : 0;
  if (!total) out.push(T("No regulations mapped to this part (regs_map.json).", { dim: true }));
  else out.push(T(`${total} rule${total === 1 ? "" : "s"} to look at on this part`, { bold: true }));
  const pt = pointFor(stageIndex(stageValue));
  const seen = new Set();
  for (const g of groups) {
    const rs = g.rules.filter(r => !seen.has(r.id));
    rs.forEach(r => seen.add(r.id));
    if (!rs.length && !g.entry.prompt) continue;
    out.push(T(`Why: ${g.entry.why}`, { dim: true, size: 28 }));
    if (g.entry.prompt) out.push(T(g.entry.prompt, { size: 30, status: "warn" }));
    for (const r of rs) {
      const ok = isVerified(r);
      out.push(T(r.title, { bold: true }));
      if (!ok) out.push(T("UNVERIFIED — placeholder. Do not rely on this rule or its values.", { status: "unverified", size: 30 }));
      out.push(T(`${r.document}, ${r.clause} · applies to an extension: ${extensionText(r)}${r.status === "future" ? " · FUTURE CHANGE, not yet in force" : ""}`, { dim: true, size: 28, status: r.applies_to_extension === false ? "warn" : undefined }));
      if (r.plain_english) out.push(T(r.plain_english, { size: 30 }));
      const val = regs.valueText(r);
      if (val) out.push(T(`Value: ${val}`, { size: 30, status: ok ? undefined : "unverified" }));
      out.push(T(checkTypeText(r, p), { size: 28, dim: r.check_type === "numeric" }));
      if (r.edition_and_amendments || r.verified_on) out.push(T(`Edition: ${(r.edition_and_amendments || "—").slice(0, 220)} · verified ${r.verified_on || "—"}`, { dim: true, size: 26, max: 3 }));
      if (r.quote) out.push(T(`“${r.quote.length > 160 ? r.quote.slice(0, 157) + "…" : r.quote}”${r.source_url ? ` — ${(u => u.length > 48 ? u.slice(0, 47) + "…" : u)(r.source_url.replace(/^https?:\/\//, ""))}` : ""}`, { dim: true, size: 26, max: 4 }));
      if (MODE.inspect) {
        const ptId = (r.inspection_ids || []).find(i => i !== "NONE") || pt?.id || "general";
        const key = checkKey(r.id, p.element);
        const cur = inspections.get(ptId)?.checks?.[key]?.status;
        out.push(B(["checked", "pass", "fail"].map(s => ({ id: s, label: s, on: () => cur === s, danger: s === "fail",
          press: () => markCheck(ptId, key, s) })), 3));
      }
    }
  }
  const roomRules = regs ? regs.forRoom(f.room) : [];
  if (roomRules.length) {
    const rr = regs.flat(roomRules).filter(r => !seen.has(r.id));
    if (rr.length) out.push(T(`In this room (${f.room}): ${rr.map(r => r.title).join(" · ")}`, { dim: true, size: 28, max: 8 }));
  }
  return out;
}

/* PLANS: the element on a plan drawn from the model (a crop of the real sheet when sheets.json has one).
   Neither is ever drawn from scratch inside a board redraw: a sheet crop is cut and shrunk to board size off the
   main thread (createImageBitmap) the first time it is asked for, and a model plan is drawn once into its own
   small canvas per part and edit state; the board then only copies the small picture. */
const sheetImages = new Map(), cropBitmaps = new Map(), planCache = new Map();
let sheets = null;
const CROP_W = 924;
function sheetCrop(p) {
  const c = sheets?.crops?.[p.element];
  if (!c) return null;
  const sh = sheets.sheets.find(s => s.drawing === c.drawing);
  if (!sh) return null;
  const key = `${p.element}|${sh.image}`;
  if (!cropBitmaps.has(key)) {
    cropBitmaps.set(key, null);
    if (!sheetImages.has(sh.image)) {
      const img = new Image();
      img.decoding = "async";
      img.src = BASE + sh.image;
      sheetImages.set(sh.image, img.decode().then(() => img));
    }
    const [sx, sy, sw, shh] = c.rect, k = Math.min(1, CROP_W / sw);
    sheetImages.get(sh.image).then(img => createImageBitmap(img, sx, sy, sw, shh, { resizeWidth: Math.round(sw * k), resizeHeight: Math.round(shh * k), resizeQuality: "medium" }))
      .then(bmp => { cropBitmaps.set(key, bmp); refreshBoard(); }).catch(err => console.warn("house: sheet crop", err));
  }
  return { bmp: cropBitmaps.get(key), drawing: c.drawing, key };
}
function planBlock(p) {
  const crop = sheetCrop(p);
  if (crop?.bmp) {
    return { type: "image", height: 560, key: crop.key, caption: `${crop.drawing} (drawing crop)`, draw(ctx, w, h) {
      const b = crop.bmp, k = Math.min(w / b.width, h / b.height);
      ctx.drawImage(b, (w - b.width * k) / 2, (h - b.height * k) / 2, b.width * k, b.height * k);
    } };
  }
  const storey = p.storey === "roof" ? "first" : p.storey === "site" ? "ground" : p.storey;
  const key = `${V.def.id}|${p.index}|${storey}|${V.editor.edits.length}`;
  return { type: "image", height: 600, key, caption: `Plan from the model · ${storey} floor · drawing ref: ${p.ud.drawing || "—"}`,
           /* the storey's base plan on one frame (the heavy part, once per storey), the part's picture on a later one */
           prepare: (w, h) => {
             if (planCache.has(`${key}|${w}x${h}`)) return true;
             const bk = `${V.def.id}|${storey}|${V.editor.edits.length}|${w}x${h}`;
             if (!planBases.has(bk)) { planBase(storey, w, h); return false; }
             return true;
           },
           draw: (ctx, w, h) => {
             let cv = planCache.get(`${key}|${w}x${h}`);
             if (!cv) {
               cv = document.createElement("canvas"); cv.width = w; cv.height = h;
               const c2 = cv.getContext("2d"); c2.fillStyle = "#f4f2ea"; c2.fillRect(0, 0, w, h);
               drawPlan(c2, w, h, p, storey);
               if (planCache.size > 24) planCache.delete(planCache.keys().next().value);
               planCache.set(`${key}|${w}x${h}`, cv);
             }
             ctx.drawImage(cv, 0, 0);
           } };
}
/* the plan of a storey from the model (rooms, walls, openings, the section lines, a scale bar), drawn ONCE per
   storey and edit state into its own canvas; a part's plan is that picture plus the part in red */
const planBases = new Map();
function planBase(storey, w, h) {
  const key = `${V.def.id}|${storey}|${V.editor.edits.length}|${w}x${h}`;
  if (planBases.has(key)) return planBases.get(key);
  const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
  const ctx = cv.getContext("2d");
  ctx.fillStyle = "#f4f2ea"; ctx.fillRect(0, 0, w, h);
  const cur = V.editor.current();
  const walls = [], rooms = [];
  for (const e of cur.values()) {
    if (e.removed) continue;
    if (e.type === "wall" && (e.meta?.storey === storey || (storey === "ground" && e.meta?.storey === "site"))) walls.push(e);
    else if (e.type === "room" && e.params.storey === storey) rooms.push(e);
  }
  const box = new THREE.Box2();
  const polys = walls.map(e => {
    const { o, d, n, L } = wallFrame(e.params), Tk = layerSpans(e.params.layers).T / 2;
    const at = (u, v) => [o.x + d.x * u + n.x * v, o.z + d.z * u + n.z * v];
    const pts = [at(0, Tk), at(L, Tk), at(L, -Tk), at(0, -Tk)];
    pts.forEach(q => box.expandByPoint(new THREE.Vector2(q[0], q[1])));
    const ops = (e.openings || []).map(id => cur.get(id)).filter(x => x && !x.removed)
      .map(x => [at(x.params.offset, Tk + 0.01), at(x.params.offset + x.params.width, Tk + 0.01), at(x.params.offset + x.params.width, -Tk - 0.01), at(x.params.offset, -Tk - 0.01)]);
    return { e, pts, ops };
  });
  if (box.isEmpty()) box.set(new THREE.Vector2(-5, -5), new THREE.Vector2(5, 5));
  const size = box.getSize(new THREE.Vector2()), pad = 34;
  const k = Math.min((w - 2 * pad) / Math.max(size.x, 0.5), (h - 2 * pad) / Math.max(size.y, 0.5));
  const X = x => pad + (x - box.min.x) * k + ((w - 2 * pad) - size.x * k) / 2;
  const Y = z => pad + (z - box.min.y) * k + ((h - 2 * pad) - size.y * k) / 2;
  const poly = (c2, pts, fill, stroke) => { c2.beginPath(); pts.forEach(([x, z], i) => i ? c2.lineTo(X(x), Y(z)) : c2.moveTo(X(x), Y(z))); c2.closePath(); if (fill) { c2.fillStyle = fill; c2.fill(); } if (stroke) { c2.strokeStyle = stroke; c2.stroke(); } };
  ctx.lineWidth = 2;
  ctx.fillStyle = "rgba(120,170,200,0.12)";
  for (const r of rooms) poly(ctx, r.params.polygon, "rgba(120,170,200,0.12)", null);
  ctx.fillStyle = "#56606a"; ctx.font = `${Math.round(Math.max(16, w / 34))}px system-ui, sans-serif`; ctx.textAlign = "center";
  for (const r of rooms) {
    const c = r.params.polygon.reduce((a, q) => [a[0] + q[0] / r.params.polygon.length, a[1] + q[1] / r.params.polygon.length], [0, 0]);
    ctx.fillText(r.params.name, X(c[0]), Y(c[1]));
  }
  ctx.textAlign = "left";
  for (const { pts, ops } of polys) { poly(ctx, pts, "#5f6266", "#2a2c2e"); for (const o of ops) poly(ctx, o, "#f4f2ea", null); }
  // section lines from the sidecar
  ctx.setLineDash([10, 6]); ctx.strokeStyle = "#3f6f8a"; ctx.lineWidth = 2; ctx.fillStyle = "#3f6f8a"; ctx.font = `600 ${Math.round(Math.max(16, w / 34))}px system-ui, sans-serif`;
  for (const s of V.sidecar.sections || []) {
    const [ox, , oz] = s.origin, [nx, ny, nz] = s.normal;
    if (Math.abs(ny) > 0.5) continue;
    const tx = -nz, tz = nx, L = Math.max(size.x, size.y);
    ctx.beginPath(); ctx.moveTo(X(ox - tx * L), Y(oz - tz * L)); ctx.lineTo(X(ox + tx * L), Y(oz + tz * L)); ctx.stroke();
    const lx = Math.min(w - 50, Math.max(10, X(ox + tx * size.x * 0.45))), ly = Math.min(h - 10, Math.max(24, Y(oz + tz * size.y * 0.45)));
    ctx.fillText(s.name, lx, ly);
  }
  ctx.setLineDash([]);
  // 1 m scale bar
  ctx.fillStyle = "#2a2c2e"; ctx.fillRect(pad, h - 18, k, 5); ctx.font = `${Math.round(Math.max(14, w / 40))}px system-ui, sans-serif`; ctx.fillText("1 m", pad + k + 6, h - 12);
  const base = { cv, X, Y, k, poly, polys };
  if (planBases.size > 8) planBases.delete(planBases.keys().next().value);
  planBases.set(key, base);
  return base;
}
function drawPlan(ctx, w, h, p, storey) {
  const base = planBase(storey, w, h), { X, Y, k } = base;
  ctx.drawImage(base.cv, 0, 0);
  const host = V.editor.current().get(p.element)?.params?.host;
  ctx.lineWidth = 2;
  for (const { e, pts } of base.polys) if (e.id === p.element || host === e.id) base.poly(ctx, pts, "#e2553a", "#2a2c2e");
  // the part's own footprint
  const bb = p.bbox;
  ctx.strokeStyle = "#e2553a"; ctx.lineWidth = 4; ctx.setLineDash([]);
  ctx.strokeRect(X(bb.min.x), Y(bb.min.z), Math.max(3, (bb.max.x - bb.min.x) * k), Math.max(3, (bb.max.z - bb.min.z) * k));
}

function notesBlocks(p) {
  const out = [];
  const list = p ? requests.forElement(p.element) : [];
  out.push(T(p ? `${list.length} change request${list.length === 1 ? "" : "s"} on ${p.element}` : "Change requests: point at something first", { bold: true }));
  for (const r of list.slice(-4).reverse()) out.push(T(`${r.created?.slice(0, 16).replace("T", " ")} · ${r.mode}: ${r.note || (r.audio ? "voice note (transcribing…)" : "—")}${r.edits?.length ? ` · ${r.edits.length} edits attached` : ""}`, { size: 28, dim: !r.note }));
  out.push(B([
    { id: "rec", label: () => recorder.recording ? "■ Stop & send" : "● Voice note", on: () => recorder.recording, press: toggleVoiceNote },
    ...(MODE.edit ? [{ id: "att", label: () => attachEdits ? "Edits: attached" : "Edits: not attached", on: () => attachEdits, press: () => { attachEdits = !attachEdits; refreshBoard(); } }] : []),
  ], 2));
  if (!inVR()) out.push({ type: "html", node: noteComposer() });
  return out;
}
let composerNode = null;
function noteComposer() {
  if (!composerNode) {
    composerNode = document.createElement("div");
    composerNode.className = "composer";
    composerNode.innerHTML = `<textarea rows="3" maxlength="2000" placeholder="What should change here? (sent to the architect)"></textarea>
      <div class="btns"><input type="text" class="author" placeholder="Your name" maxlength="60"><button class="primary">Send note</button></div>`;
    const ta = composerNode.querySelector("textarea"), au = composerNode.querySelector(".author");
    au.value = localStorage.getItem("house-author") || "";
    au.addEventListener("change", () => { try { localStorage.setItem("house-author", au.value); } catch (_) {} });
    composerNode.querySelector("button").addEventListener("click", async () => {
      if (!ta.value.trim()) return;
      await sendRequest({ note: ta.value.trim() });
      ta.value = "";
    });
  }
  return composerNode;
}
async function sendRequest(extra) {
  const p = target?.part;
  const req = {
    elements: p ? [p.element] : [], parts: p ? [p.name] : [],
    point: target?.point ? target.point.toArray().map(v => Math.round(v * 1000) / 1000) : null,
    stage: stageIndex(stageValue), stage_value: Math.round(stageValue * 100) / 100,
    camera: camera.getWorldPosition(new THREE.Vector3()).toArray().map(v => Math.round(v * 1000) / 1000),
    edits: attachEdits && MODE.edit ? V.editor.edits : [],
    rules: MODE.rules ? V.rules.filter(r => r.status !== "pass") : [],
    ...extra,
  };
  const { request, saved } = await requests.submit(req);
  toast(`Note sent (${saved})`);
  refreshBoard();
  return request;
}
async function toggleVoiceNote() {
  try {
    if (!recorder.recording) { await recorder.start(); toast("Recording… press again to send"); refreshBoard(); return; }
    const blob = await recorder.stop();
    if (!blob) return;
    const id = requests.newId();
    const file = await requests.uploadAudio(id, blob);
    await sendRequest({ id, note: "", audio: file, note_status: file ? "awaiting transcription" : "audio not uploaded (no server)" });
  } catch (err) { toast(`Microphone: ${err.message}`); }
}

function toolsBlocks() {
  const out = [];
  const tools = [
    { id: "info", label: "Info", on: () => tool === "info", press: () => setTool("info") },
    ...(MODE.measure ? [{ id: "meas", label: "Measure", on: () => tool === "measure", press: () => setTool("measure") },
                        { id: "mclr", label: "Clear tape", press: () => measure.clear() }] : []),
    { id: "xray", label: MODE.xray === "full" ? "X-ray" : "See inside", on: () => xray, press: () => setXray(!xray) },
    { id: "roof", label: MODE.hide === "full" ? "Hide roof" : "Lift roof", on: () => !storeyState.roof, press: () => setStorey("roof", !storeyState.roof) },
    { id: "first", label: MODE.hide === "full" ? "Hide 1st" : "Lift 1st floor", on: () => !storeyState.first, press: () => setStorey("first", !storeyState.first) },
  ];
  out.push(B(tools, 3));
  if (MODE.section) out.push(B([
    { id: "sec", label: () => section.state.on ? `Slice ${section.state.name}` : "Slice ▸", on: () => section.state.on,
      press: () => { const names = [null, ...sectionDefs().map(d => d.name)]; setSection(names[(names.indexOf(section.state.on ? section.state.name : null) + 1) % names.length]); } },
    { id: "sm", label: "Cut −100", press: () => nudgeSection(-0.1) },
    { id: "sp", label: "Cut +100", press: () => nudgeSection(0.1) },
    { id: "sf", label: "Flip cut", press: () => section.flip() },
  ], 4));
  const vs = manifest?.versions || [];
  out.push(B([
    ...(vs.length > 1 ? [{ id: "ver", label: () => `${(V?.def.name || "").slice(0, 12)} ▸`, press: () => useVersion(vs[(vs.findIndex(v => v.id === V.def.id) + 1) % vs.length].id) }] : []),
    ...(manifest?.as_built_now ? [{ id: "bef", label: "Before", on: () => V?.def.id === manifest.as_built_now, press: () => useVersion(manifest.as_built_now) },
                                  { id: "aft", label: "After", on: () => V?.def.id === lastProposal, press: () => lastProposal && useVersion(lastProposal) }] : []),
    ...(V?.model.hasAsBuilt ? [{ id: "ab", label: "As built", on: () => V.model.asBuilt, press: toggleAsBuilt }] : []),
    { id: "go", label: "Go to ▸", press: () => { spawnIdx = (spawnIdx + 1) % Math.max(1, spawnDefs().length); spawnAt(spawnDefs()[spawnIdx]?.name); } },
  ], 3));
  out.push(B([
    { id: "doors", label: () => V?.doors?.anyOpen ? "Close all doors" : "Open all doors", on: () => !!V?.doors?.anyOpen, press: () => setAllDoors(!V.doors.anyOpen) },
    { id: "hidedoors", label: () => doorsHidden ? "Show doors" : "Hide doors", on: () => doorsHidden, press: () => setDoorsHidden(!doorsHidden) },
    { id: "furnish", label: () => unfurnished ? "Unfurnished" : "Furnished", on: () => unfurnished, press: () => setUnfurnished(!unfurnished) },
    { id: "hts", label: "Heights", on: () => tool === "heights", press: () => setTool(tool === "heights" ? "info" : "heights") },
    { id: "cue", label: "Scale figure", on: () => !!scaleCue?.visible, press: toggleScaleCue },
    { id: "fly", label: () => inVR() ? (hovering ? "Land (L grip)" : "Fly: R grip") : flying ? "Flying (F)" : "Fly (F)", on: () => flying || hovering, press: () => {
        if (!inVR()) setFly(!flying);
        else if (hovering || flying) { flying = hovering = false; startLanding(feetUnderHead()); }
        else showCard("Fly", ["Hold the RIGHT grip and steer with the right stick: forward / back where the controller points (point up to climb), left / right sideways, push harder to go faster.", "Let go: you hover there (the left stick still walks on the air). LEFT grip: down to the floor beneath."], null, 10); } },
    { id: "hud", label: "Frame HUD", on: () => perf.on, press: () => { perf.toggle(); refreshBoard(); } },
    { id: "fast", label: () => fastWalk ? "Fast walk: on" : "Fast walk", on: () => fastWalk, press: () => setFastWalk(!fastWalk) },
  ], 3));
  /* the Height check: your height, then press while standing up straight */
  out.push(T(`Height check — your height ${heightText(personHeight)}${inVR() ? `, eyes now ${eyeAndFloor().eye.toFixed(2)} m above the floor` : ""}${floorOffset ? ` · floor corrected by ${floorOffset >= 0 ? "+" : "−"}${Math.abs(floorOffset).toFixed(2)} m` : ""}`, { bold: true, size: 30 }));
  out.push(B([
    { id: "hchk", label: "Height check", on: () => !!floorOffset, press: heightCheck },
    { id: "hrst", label: "Reset floor", press: heightReset },
    ...(inVR() ? [{ id: "hm", label: "Height −1 cm", press: () => setPersonHeight(personHeight - 0.01) },
                  { id: "hp", label: "Height +1 cm", press: () => setPersonHeight(personHeight + 0.01) },
                  { id: "hmi", label: "−1 inch", press: () => setPersonHeight(personHeight - 0.0254) },
                  { id: "hpi", label: "+1 inch", press: () => setPersonHeight(personHeight + 0.0254) }]
                : [{ id: "hset", label: "Set my height", press: askHeight }]),
    { id: "vq", label: () => `VR: ${VRQ[vrQuality].label}`, press: cycleQuality },
  ], 3));
  if (MODE.edit) {
    const t = editTarget(target?.part);
    out.push(T(t ? `Edit: ${t.el.id} (${t.el.type})${t.opening ? ` · opening ${Math.round(t.opening.params.width * 1000)} wide` : ""}` : "Edit: point at a wall, opening or fixture", { bold: true, size: 30 }));
    out.push(B([
      { id: "erm", label: () => t?.el.removed ? "Restore" : "Remove", danger: true, press: () => editRemoveToggle() },
      { id: "wm", label: "Wall −100", press: () => editMoveWall(-0.1) },
      { id: "wp", label: "Wall +100", press: () => editMoveWall(0.1) },
      { id: "aw", label: () => tool === "addwall" ? (wallDraft ? "…2nd point" : "…1st point") : "Add wall", on: () => tool === "addwall", press: () => setTool(tool === "addwall" ? "info" : "addwall") },
      { id: "ad", label: "Add door", press: () => editAddOpening("door.front.solid") },
      { id: "awn", label: "Add window", press: () => editAddOpening("window.casement.2") },
      { id: "ol", label: "◀ Opening", press: () => editOpening(-0.1, 0) },
      { id: "or", label: "Opening ▶", press: () => editOpening(0.1, 0) },
      { id: "sw", label: "Swap fixture", press: editSwap },
      { id: "ow", label: "Wider", press: () => editOpening(0, 0.1) },
      { id: "on", label: "Narrower", press: () => editOpening(0, -0.1) },
      { id: "undo", label: "Undo", press: () => V.editor.undo() },
    ], 3));
    out.push(B([{ id: "redo", label: "Redo", press: () => V.editor.redo() },
                { id: "regs", label: () => $("rulesSummary").textContent, press: () => { boardTab = "regs"; refreshBoard(); } }], 2));
  }
  return out;
}

let boardDirty = true;
function boardContent() {
  if (!V) return null;
  const p = target?.part;
  const i = stageIndex(stageValue);
  const tabs = MODE.tabs.map(id => ({ id, label: TAB_LABEL[id] }));
  let title, subtitle, accent = "#f2d36b";
  if (p) {
    const plain = p.ud.plain_label || elOf(p)?.meta?.plain_label || PLAIN_GROUP[p.group] || p.group;
    title = MODE.infoText === "plain" ? plain : (p.ud.label || p.name);
    subtitle = CUST ? `${{ existing: "Part of your house now", demolition: "Comes out during the works", temporary: "Temporary, during the works", new: "New", finish: "Finishing work" }[p.category] || ""}`
      : `${p.element} · ${p.group} · ${p.category}`;
    accent = { demolition: "#ef6b5e", temporary: "#f2c230", existing: "#b9bdb1", finish: "#9fd0a8" }[p.category] || "#f2d36b";
  } else {
    title = inVR() ? "Point at any part" : "Click any part";
    subtitle = CUST ? V.def.name : `${V.def.name} · ${MODE.label}`;
  }
  let blocks;
  const need = id => !p && ["about", "spec", "build", "regs", "plans"].includes(id);
  if (need(boardTab)) blocks = [T(inVR() ? "Point the right controller at a wall, beam, joist or door and pull the trigger: this board fills in and keeps it until you pick something else." : "Click a part to see it here.", { dim: true })];
  else blocks = { about: () => aboutBlocks(p), spec: () => specBlocks(p), build: () => buildBlocks(p), regs: () => regsBlocks(p),
                  plans: () => [planBlock(p)], notes: () => notesBlocks(p), tools: toolsBlocks }[boardTab]();
  if (p && boardTab === "spec" && blocks[0]?.text === title) blocks.shift();      // the title already is the spec text
  if (p && boardTab !== "tools" && boardTab !== "notes") {
    if (target.heights?.underside) blocks.unshift(T(target.heights.text, { bold: true, size: 32, status: "warn" }));
    const d = V.doors?.doorOf(p);
    if (d) {
      const sw = V.doors.swingInfo(d);
      if (!CUST || sw.note) blocks.unshift(T(`${sw.leaves > 1 ? `${sw.leaves} leaves · ` : ""}${sw.slide ? "folds / slides" : `opens ${Math.abs(sw.deg ?? 90)}°`}${sw.conf ? ` · swing ${confText(sw.conf)}` : ""}${sw.note ? ` — ${sw.note}` : ""}`, { dim: true, size: 28, max: 4 }));
      blocks.unshift(B([{ id: "door", label: () => V.doors.isOpen(d) ? "Close this door" : "Open this door", on: () => V.doors.isOpen(d), press: () => toggleDoor(p) }], 1));
    }
  }
  return {
    title, subtitle, accent, tabs, active: boardTab, blocks,
    strip: {
      title: `${i}/${stageN} · ${stageTitle(V.sidecar.stages[i - 1])}`,
      frac: stageN > 1 ? (stageValue - 1) / (stageN - 1) : 1,
      buttons: [{ id: "prev", label: "◀ Stage", press: prevStage }, { id: "play", label: () => playing ? "Pause" : "Play", on: () => playing, press: togglePlay },
                { id: "next", label: "Stage ▶", press: nextStage }, { id: "tool", label: () => TOOL_LABEL[tool] || "Info", on: () => tool !== "info", press: cycleTool }],
    },
  };
}
function refreshBoard() { boardDirty = true; }
/* the board's content is rebuilt when something on it changed. In the headset: at most every 120 ms (a playing
   build changes the stage every frame), and not at all while the board is minimised (it is rebuilt on restore);
   the canvas is drawn on a LATER frame than the content is built (vrBoard.update), so no frame does both. */
let lastFlush = 0;
function flushBoard(now = performance.now(), force = false) {
  if (!boardDirty) return false;
  if (SIMPLE) { boardDirty = false; $("board").hidden = true; return false; }      // homeowners have no board
  if (inVR() && !force && (boardMin || now - lastFlush < 120)) return false;
  boardDirty = false; lastFlush = now;
  const t0 = performance.now();
  const c = boardContent();
  vrBoard.set(c);
  if (!inVR()) {
    const show = !!target || boardTab === "tools" || boardTab === "notes";
    renderBoardDOM($("board"), show ? c : null, id => { boardTab = id; vrBoard.resetPage(); refreshBoard(); });
  }
  const ms = performance.now() - t0;
  if (ms > 8) perf.tag(`board content ${Math.round(ms)} ms`);
  return true;
}

/* ------------------------------------------------------------------ *
 *  Editing (architect) and the rules
 * ------------------------------------------------------------------ */
function editTarget(p) {
  if (!p || !V) return null;
  const el = V.editor.get(p.element);
  if (!el) return null;
  if (el.type === "opening") return { el, opening: el };
  if (el.params?.opening) return { el, opening: V.editor.get(el.params.opening) };
  return { el, opening: null };
}
function editRemoveToggle() {
  const t = editTarget(target?.part);
  if (!t) return toast("Point at something to remove first");
  if (t.el.removed) V.editor.restore(t.el.id); else V.editor.remove(t.el.id);
}
function editOpening(dOffset, dWidth) {
  const t = editTarget(target?.part);
  if (!t?.opening) return toast("Point at a door, window, lintel or opening first");
  const o = t.opening, host = V.editor.get(o.params.host);
  const L = Math.hypot(host.params.end[0] - host.params.start[0], host.params.end[1] - host.params.start[1]);
  let width = Math.max(0.3, o.params.width + dWidth);
  let offset = o.params.offset + dOffset - dWidth / 2;
  offset = Math.max(0.1, Math.min(L - 0.1 - width, offset));
  width = Math.min(width, L - 0.2);
  V.editor.set(o.id, { offset: Math.round(offset * 1000) / 1000, width: Math.round(width * 1000) / 1000 });
}
function wallOf(p) {
  const el = elOf(p);
  if (!el) return null;
  if (el.type === "wall") return el;
  const op = el.type === "opening" ? el : el.params?.opening && V.editor.get(el.params.opening);
  return op ? V.editor.get(op.params.host) : null;
}
function editMoveWall(d) {
  const w = wallOf(target?.part);
  if (!w) return toast("Point at a wall first");
  const ops = moveWall(V.editor, w.id, d);
  toast(`Moved ${w.id} ${Math.round(d * 1000)} mm (${ops.length - 1} connected wall${ops.length === 2 ? "" : "s"} followed)`);
}
function editAddOpening(catalogue) {
  const w = wallOf(target?.part);
  if (!w || !target.point) return toast("Point at the wall where the opening goes");
  const { o, d } = wallFrame(w.params);
  const u = (target.point.x - o.x) * d.x + (target.point.z - o.z) * d.z;
  const ffl = V.sidecar.storeys?.[w.meta?.storey] ?? w.params.base;          // doors start at the floor, not the footing
  const win = catalogue.startsWith("window");
  const id = addOpening(V.editor, w.id, u, { catalogue, width: win ? 1.2 : 0.9, sill: win ? ffl + 0.9 : ffl, head: ffl + 2.1 });
  toast(`Added ${id} in ${w.id}`);
}
function editSwap() {
  const el = elOf(target?.part);
  const f = el?.type === "fixture" ? el : el && [...V.editor.current().values()].find(e => e.type === "fixture" && e.params.opening === (el.type === "opening" ? el.id : el.params?.opening));
  if (!f) return toast("Point at a door or window first");
  const next = swapFixture(V.editor, f.id);
  toast(next ? `${f.id} → ${CATALOGUE[next].label}` : "Nothing else in the catalogue for that");
}
function onEdit(entry, current, ids) {
  const keepEl = target?.part?.element, keepPoint = target?.point;
  entry.model.applyElements(current, ids);
  entry.edited = true;                         // a wall may have moved: the room culling's cells and portals are stale, so it stays off for this version (cull.js)
  entry.bvh = buildBVH(entry.model.parts);
  entry.doors = createDoors({ model: entry.model, bvh: entry.bvh, roomAt: entry.model.roomAt, table: current });   // rebuilt leaves open too (hinges derived)
  stageDirty = true;
  applyStageNow();
  if (keepEl) {
    const ps = (entry.model.byElement.get(keepEl) || []).filter(p => !p.hidden);
    target = ps[0] ? { part: ps[0], point: keepPoint, source: "click", at: performance.now() } : null;
    updateHighlight();
  }
  $("undo").disabled = !entry.editor.canUndo; $("redo").disabled = !entry.editor.canRedo;
  $("editCount").textContent = `${entry.editor.edits.length} edit${entry.editor.edits.length === 1 ? "" : "s"}`;
  runRules(true);
  refreshBoard();
}
function runRules(announce = false) {
  if (!MODE.rules || !V) { if (V) V.rules = []; return; }
  const mask = V.model.finalMask();
  const ray = new THREE.Ray();
  const ctx = {
    ffl: storey => V.sidecar.storeys?.[storey] ?? 0,
    clearanceAbove(x, y, z) {
      ray.origin.set(x, y, z); ray.direction.set(0, 1, 0);
      const h = V.bvh.raycast(ray, 12, mask);
      return h ? h.distance : Infinity;
    },
  };
  const res = checkRules(V.editor.current(), ctx);
  V.rules = res;
  const fails = res.filter(r => r.status === "fail").length, warns = res.filter(r => r.status === "warn").length;
  const unknown = res.filter(r => r.status === "unknown").length, passes = res.filter(r => r.status === "pass").length;
  const total = regs?.rules.length || 0;
  const people = Math.max(0, total - CHECKED_BY_MODEL.size);
  /* never a bare "all pass": say what was checked, what was not, and that it is guidance */
  $("rulesSummary").textContent = `Model checks: ${res.length} run · ${passes} pass · ${fails} fail${unknown ? ` · ${unknown} not measured` : ""}${warns ? ` · ${warns} to check` : ""}`;
  $("rulesSummary").title = `${people} of ${total} rules are judgement, evidence or not modelled: a person checks them. Guidance, not approval.`;
  $("rulesSummary").dataset.status = fails ? "fail" : (warns || unknown) ? "warn" : "info";
  $("rulesLiability").textContent = regs?.meta?.product_liability || regs?.meta?.liability || "";
  $("rulesHead").textContent = `The model ran ${res.length} live checks on ${CHECKED_BY_MODEL.size} rules. ${people} of the ${total} rules in the dataset are judgement, evidence or not modelled: a person checks them. Guidance, not approval.`;
  const ul = $("rulesList");
  ul.textContent = "";
  for (const r of res) {
    const li = document.createElement("li");
    li.dataset.status = r.status;
    li.innerHTML = `<b></b><span></span><small></small>`;
    li.querySelector("b").textContent = r.status.toUpperCase();
    li.querySelector("span").textContent = `${r.elementId}: ${r.message}`;
    li.querySelector("small").textContent = r.clause;
    ul.appendChild(li);
  }
  if (announce && fails && renderer.xr.isPresenting) { boardTab = "regs"; hapticPulse(controllers, 0.6, 60); }
}
function downloadEdits() {
  const blob = new Blob([JSON.stringify(V.editor.toJSON(), null, 1)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${SITE}_${V.def.id}_edits.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

/* ------------------------------------------------------------------ *
 *  Desktop / phone pointer
 * ------------------------------------------------------------------ */
const pointer = { down: null, moved: 0 };
const ndc = new THREE.Vector2();
const rc = new THREE.Raycaster();
function screenRay(x, y) {
  ndc.set((x / innerWidth) * 2 - 1, -(y / innerHeight) * 2 + 1);
  rc.setFromCamera(ndc, camera);
  return rc.ray.clone();
}
const screenReach = hit => Math.max(0.012, hit.distance * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * 2 * 12 / innerHeight);

/* ------------------------------------------------------------------ *
 *  Mouse-look (round 7d, Jack 1 Nov: "to look around it should be just
 *  moving the mouse"). Walking on a computer with a mouse: one click
 *  into the view captures the mouse (Pointer Lock); then moving it
 *  turns and looks (no inverted Y), W A S D walk, a centre crosshair
 *  aims, and a left click acts on what is under it: a door opens or
 *  shuts, a floor or the ground is jumped to (homeowner / review), the
 *  other modes pick / measure as their tool says; in Mark mode the held
 *  button draws along the crosshair. Esc frees the mouse for the
 *  buttons. Touch screens, the overview, and a browser that refuses the
 *  capture keep drag-to-look.
 * ------------------------------------------------------------------ */
const LOOK_SENS = 0.0022;                       // radians per mouse count (about 0.13 deg)
const locked = () => document.pointerLockElement === renderer.domElement;
let lockRefused = false, lockWanted = false;
const lookEligible = e => walk && !inVR() && !IS_TOUCH && (!e || e.pointerType === "mouse") && !lockRefused;
function captureMouse() {
  lockWanted = true;
  try {
    const p = renderer.domElement.requestPointerLock({ unadjustedMovement: false });
    if (p?.catch) p.catch(err => lockFailed(err));
  } catch (err) { lockFailed(err); }
}
/* a refusal: browsers also refuse a re-capture within about a second of Esc, so a browser that has captured before
   only gets a "click again"; one that refuses twice and never captured falls back to drag-to-look for the visit */
let lockOk = false, lockFails = 0;
function lockFailed(err) {
  if (lockRefused) return;
  lockWanted = false;
  console.info("house: pointer lock refused", err?.message || err);
  if (lockOk || ++lockFails < 2) { toast("Click the view again to look around with the mouse (or drag to look)"); return; }
  lockRefused = true;
  toast("This browser would not capture the mouse: drag to look around instead");
  updateLookUI(); updateHelp();
}
document.addEventListener("pointerlockerror", () => lockFailed("pointerlockerror"));
document.addEventListener("pointerlockchange", () => {
  if (!locked()) { lockWanted = false; pointer.down = null; setHover(null); }
  else { blurPass?.reset(); lockOk = true; lockFails = 0; }
  updateLookUI();
});
function freeMouse() { if (locked()) document.exitPointerLock(); }
function updateLookUI() {
  const on = locked();
  $("crosshair").hidden = !on;
  $("lookHint").hidden = on || !lookEligible() || !$("start").hidden || !!marks?.noteOpen || !V;
}
/* the crosshair's ray (the screen's centre) or the cursor's */
const centreRay = () => { rc.setFromCamera(ndc.set(0, 0), camera); return rc.ray.clone(); };
const eventRay = e => locked() ? centreRay() : screenRay(e.clientX, e.clientY);
/* a click under the crosshair: homeowner / review jump to a floor spot (walls, roofs, worktops refused), else act() */
function lockedClick() {
  const h = pickRay(centreRay());
  if (SIMPLE) {
    const p = partOf(h), d = p && V.doors?.doorOf(p);
    if (d) { toggleDoor(p); return; }
    const spot = h ? walkableSpot(h) : null;
    if (spot) teleportTo(spot, null, "click teleport");
    else if (h) toast("Not a place to stand: aim at a floor or the ground");
    return;
  }
  act(h, h ? screenReach(h) : 0);
}
/* the crosshair's colour tells what a click would do (homeowner / review): yellow a door, green a floor */
let crossTick = 0;
function updateCrosshair(dt) {
  if (!locked() || !V || (crossTick += dt) < 0.08) return;
  crossTick = 0;
  const el = $("crosshair");
  if (marks?.active) { el.className = ""; return; }
  const h = pickRay(centreRay()), p = partOf(h), d = p && V.doors?.doorOf(p);
  setHover(SIMPLE ? (d ? p : null) : p);
  if (!SIMPLE && tool === "heights") showHeights(h);
  el.className = d ? "door" : SIMPLE && h && walkableSpot(h) ? "floor" : "";
}

/* ------------------------------------------------------------------ *
 *  Thumb sticks (round 7d, Jack 1 Nov): phones and tablets, homeowner
 *  and review. LEFT half of the lower screen = move (forward / back /
 *  strafe, speed by how far you push, Fast respected), RIGHT half =
 *  look (turn and pitch, rate by push, eased). Each stick rests faintly
 *  in its corner and jumps to where the thumb lands, springing back on
 *  release; both work at once (multi-touch). A tap anywhere else acts
 *  like a click (a door, a jump to the floor, or draws in Mark mode);
 *  dragging outside the stick zones still looks around.
 * ------------------------------------------------------------------ */
const STICKS = IS_TOUCH && SIMPLE;
const STICK_R = 52;                              // thumb travel in px for a full push
const touchMove = { x: 0, y: 0 }, touchLook = { x: 0, y: 0 }, lookVel = { yaw: 0, pitch: 0 };
const LOOK_RATE = { yaw: 2.2, pitch: 1.3, ease: 0.12 };   // rad/s at full push; eased over 0.12 s
const sticks = { L: { el: $("stickL"), id: null, cx: 0, cy: 0, v: touchMove }, R: { el: $("stickR"), id: null, cx: 0, cy: 0, v: touchLook } };
const safe = (() => { const d = document.createElement("div");
  d.style.cssText = "position:fixed;visibility:hidden;padding:env(safe-area-inset-top,0px) env(safe-area-inset-right,0px) env(safe-area-inset-bottom,0px) env(safe-area-inset-left,0px)";
  document.body.appendChild(d); return () => { const c = getComputedStyle(d); return { t: parseFloat(c.paddingTop) || 0, r: parseFloat(c.paddingRight) || 0, b: parseFloat(c.paddingBottom) || 0, l: parseFloat(c.paddingLeft) || 0 }; }; })();
function stickRest(k) {
  const sa = safe(), m = 30 + 64;
  return k === "L" ? [sa.l + m, innerHeight - sa.b - m] : [innerWidth - sa.r - m, innerHeight - sa.b - m];
}
function placeStick(k, x, y, kx = 0, ky = 0) {
  const st = sticks[k];
  st.el.style.left = `${x}px`; st.el.style.top = `${y}px`;
  st.el.querySelector("i").style.transform = `translate(${kx}px, ${ky}px)`;
}
function layoutSticks() {
  const on = STICKS && walk && !inVR() && !!V && $("start").hidden && !marks?.active;   // marking: the finger draws instead
  document.body.classList.toggle("touch-sticks", STICKS);
  for (const k of ["L", "R"]) { sticks[k].el.hidden = !on; if (on && sticks[k].id === null) { const [x, y] = stickRest(k); placeStick(k, x, y); } }
}
/* which stick a touch at (x, y) starts: the lower 58 % of the screen, split in halves; null elsewhere */
function stickZone(x, y) {
  if (!STICKS || !walk || inVR() || marks?.active || y < innerHeight * 0.42) return null;
  const bar = $("baBar").getBoundingClientRect();
  if (x >= bar.left && x <= bar.right && y >= bar.top && y <= bar.bottom) return null;
  return x < innerWidth / 2 ? "L" : "R";
}
renderer.domElement.addEventListener("pointerdown", e => {
  if (e.pointerType !== "touch") return;
  const k = stickZone(e.clientX, e.clientY);
  if (!k || sticks[k].id !== null) return;
  e.stopImmediatePropagation(); e.preventDefault();
  const st = sticks[k];
  st.id = e.pointerId; st.cx = e.clientX; st.cy = e.clientY; st.v.x = st.v.y = 0; st.t0 = performance.now(); st.travel = 0;
  st.el.classList.add("active"); placeStick(k, st.cx, st.cy);
  try { renderer.domElement.setPointerCapture(e.pointerId); } catch (_) {}
});
const stickOf = id => sticks.L.id === id ? "L" : sticks.R.id === id ? "R" : null;
addEventListener("pointermove", e => {
  const k = stickOf(e.pointerId);
  if (!k) return;
  e.stopImmediatePropagation();
  const st = sticks[k];
  let dx = e.clientX - st.cx, dy = e.clientY - st.cy;
  const d = Math.hypot(dx, dy);
  st.travel = Math.max(st.travel, d);
  if (d > STICK_R) { dx *= STICK_R / d; dy *= STICK_R / d; }
  const dead = 0.12, m = Math.min(1, d / STICK_R), mm = m < dead ? 0 : (m - dead) / (1 - dead);
  st.v.x = d ? dx / Math.min(d, STICK_R) * mm : 0; st.v.y = d ? dy / Math.min(d, STICK_R) * mm : 0;
  placeStick(k, st.cx, st.cy, dx, dy);
}, true);
const stickUp = e => {
  const k = stickOf(e.pointerId);
  if (!k) return;
  e.stopImmediatePropagation();
  const st = sticks[k];
  st.id = null; st.v.x = st.v.y = 0;
  st.el.classList.remove("active");
  /* a quick tap in a stick's zone (no push) still acts: a door opens, or you jump to the floor you tapped */
  if (e.type === "pointerup" && st.travel < 10 && performance.now() - st.t0 < 280 && V) {
    const h = pickRay(screenRay(st.cx, st.cy));
    act(h, h ? screenReach(h) : 0);
  }
  placeStick(k, st.cx, st.cy, 0, 0);                        // the knob springs back (CSS), then the stick goes home
  setTimeout(() => { if (st.id === null) { const [x, y] = stickRest(k); placeStick(k, x, y); } }, 200);
};
addEventListener("pointerup", stickUp, true);
addEventListener("pointercancel", stickUp, true);
/* the right stick turns and pitches the view (eased; a light curve keeps small pushes fine) */
function touchLookStep(dt) {
  const k = Math.min(1, dt / LOOK_RATE.ease);
  const wantYaw = -Math.sign(touchLook.x) * touchLook.x * touchLook.x * LOOK_RATE.yaw;
  const wantPitch = -Math.sign(touchLook.y) * touchLook.y * touchLook.y * LOOK_RATE.pitch;
  lookVel.yaw += (wantYaw - lookVel.yaw) * k; lookVel.pitch += (wantPitch - lookVel.pitch) * k;
  if (Math.abs(lookVel.yaw) < 1e-4 && !wantYaw) lookVel.yaw = 0;
  if (Math.abs(lookVel.pitch) < 1e-4 && !wantPitch) lookVel.pitch = 0;
  yawPitch.yaw += lookVel.yaw * dt;
  yawPitch.pitch = Math.max(-1.3, Math.min(1.3, yawPitch.pitch + lookVel.pitch * dt));
}

renderer.domElement.addEventListener("pointerdown", e => {
  if (inVR()) return;
  if (!locked() && lookEligible(e) && e.button === 0) {      // the capture click: it only captures, it does not act or draw
    e.stopImmediatePropagation();
    pointer.down = { x: e.clientX, y: e.clientY, yaw: yawPitch.yaw, pitch: yawPitch.pitch, id: e.pointerId, capture: true };
    pointer.moved = 0;
    captureMouse();
    return;
  }
  if (locked()) {
    if (e.button !== 0) return;
    if (marks?.active) return;                                // marks.js draws along the crosshair
    lockedClick();
    return;
  }
  if (marks?.active && e.button === 0) return;               // review, marking: the left button draws (right-drag still looks)
  pointer.down = { x: e.clientX, y: e.clientY, yaw: yawPitch.yaw, pitch: yawPitch.pitch, id: e.pointerId, marking: !!marks?.active };
  pointer.moved = 0;
});
if (MODE.marks) renderer.domElement.addEventListener("contextmenu", e => e.preventDefault());
addEventListener("pointermove", e => {
  if (locked()) {                                             // mouse-look: the mouse turns and looks
    if (inVR()) return;
    const mx = Math.max(-250, Math.min(250, e.movementX || 0)), my = Math.max(-250, Math.min(250, e.movementY || 0));
    yawPitch.yaw -= mx * LOOK_SENS;
    yawPitch.pitch = Math.max(-1.3, Math.min(1.3, yawPitch.pitch - my * LOOK_SENS));
    return;
  }
  if (pointer.down && pointer.down.id === e.pointerId) {
    pointer.moved = Math.max(pointer.moved, Math.hypot(e.clientX - pointer.down.x, e.clientY - pointer.down.y));
    if (walk && !renderer.xr.isPresenting) {         // drag to look (touch, or no mouse capture)
      yawPitch.yaw = pointer.down.yaw + (e.clientX - pointer.down.x) * 0.005;
      yawPitch.pitch = Math.max(-1.3, Math.min(1.3, pointer.down.pitch + (e.clientY - pointer.down.y) * 0.005));
    }
  }
  if (!V || e.target !== renderer.domElement || inVR()) return;
  if (marks?.active) { setHover(null); return; }
  if (!pointer.down) {
    const h = pickRay(screenRay(e.clientX, e.clientY));
    if (tool === "measure" || tool === "addwall") measure.hover(h, partOf(h), h ? screenReach(h) : 0);
    else setHover(IS_TOUCH ? null : SIMPLE ? (V.doors?.doorOf(partOf(h)) ? partOf(h) : null) : partOf(h));
    if (tool === "heights") showHeights(h);
  }
});
addEventListener("pointerup", e => {
  const d = pointer.down;
  pointer.down = null;
  if (locked() || d?.capture) return;
  if (!d || e.target !== renderer.domElement || pointer.moved > 6 || !V || d.marking || marks?.active) return;
  const h = pickRay(eventRay(e));
  act(h, h ? screenReach(h) : 0);
});
/* one click / trigger, whatever the tool */
function act(h, reach) {
  if (SIMPLE) {                                   // homeowners: a door opens, nothing else is picked
    const p = partOf(h);
    if (p && V.doors?.doorOf(p)) toggleDoor(p);
    else if (h && walk) {                           // click / tap a floor or the ground: jump there (walls, roofs, worktops refused)
      const spot = walkableSpot(h);
      if (spot) teleportTo(spot, null, "tap teleport");
    }
    return null;
  }
  if (tool === "measure") {
    const m = measure.click(h, partOf(h), reach);
    if (m && m.mm !== undefined) toast(`${m.mm.toLocaleString()} mm  (horizontal ${m.horizontal_mm.toLocaleString()}, vertical ${m.vertical_mm.toLocaleString()})`);
    $("measureClear").disabled = !measure.count && !measure.pending;
    return m;
  }
  if (tool === "addwall") {
    if (!h) return;
    const s = measure.hover(h, partOf(h), reach)?.point || h.point;
    if (!wallDraft) { wallDraft = s.clone(); toast("Add wall: now the other end"); refreshBoard(); return; }
    const p = partOf(h);
    const id = addWall(V.editor, [wallDraft.x, wallDraft.z], [s.x, s.z], { base: Math.min(wallDraft.y, s.y), stage: Math.max(2, stageIndex(stageValue)), storey: p?.storey === "first" ? "first" : "ground" });
    toast(`Added ${id}`);
    wallDraft = null; setTool("info");
    return;
  }
  if (!h) { setTarget(null); return; }
  const p = partOf(h);
  // a second tap on the same floor in walk mode (phone, homeowner) walks you there
  if (walk && (IS_TOUCH || CUST) && h.normal.y > 0.7 && p.collide && target?.part === p) { glideTo(h.point); return; }
  // walking (or in the headset), a door you pick swings open or shut; in the overview it is only picked
  if ((walk || inVR()) && V.doors?.doorOf(p)) toggleDoor(p);
  setTarget(p, h.point, "click", h);
}
function toggleDoor(p) {
  const open = V.doors.toggle(p);
  if (open === null) toast("That door is not in yet at this stage");
  else { hapticPulse([hands.right], 0.4, 25); refreshBoard(); }
  return open;
}
/* "Hide doors" (Jack, 1 Nov): every door leaf and its glass out of sight and out of the walk, frames and linings kept;
   it carries across versions and Before/After until pressed again */
let doorsHidden = false;
/* Furnished / Unfurnished (round 8, Jack 2 Nov: "build it in a way I can switch between furnished and unfurnished so
   I can see all the other details more clearly for review"; SIGNOFF.md, decision of 2 Nov). Unfurnished hides the
   LOOSE layer: furniture, soft furnishings, decor, plants and the lived-in details, i.e. every node whose glTF extras
   carry `furnishing: true`; for builds made before that extra existed, a part whose spec item (spec_id in the spec's
   versions.*.items) is in one of those categories, or whose spec_kind already names one. Fixed fittings stay: joinery,
   sanitaryware, radiators, lighting, appliances, switches and sockets, doors, windows, finishes; the garden setting
   stays. The same mechanism as "No doors": p.viewHidden, so a hidden part is not drawn, not picked, and neither
   blocks walking nor a teleport (applyStage drops it from the visible and solid masks). Remembered per device. */
const LOOSE = new Set(["furniture", "soft_furnishing", "decor", "plant"]);
let specCategory = new Map();                    // spec item id -> category (furniture, joinery, lighting...)
let unfurnished = store.get("house-unfurnished-v1", "0") === "1";
const isLoose = p => p.ud.furnishing === true || p.ud.lived_in === true || LOOSE.has(p.ud.spec_kind)
  || LOOSE.has(p.ud.spec_category) || (p.ud.spec_id != null && LOOSE.has(specCategory.get(p.ud.spec_id)));
function markDoorsHidden() {                      // (both rules: the door leaves when "No doors", the loose layer when Unfurnished)
  if (!V) return;
  let n = 0;
  for (const p of V.model.parts) {
    const loose = unfurnished && isLoose(p);
    if (loose) n++;
    p.viewHidden = (doorsHidden && isLeaf(p)) || loose;
  }
  V.looseHidden = n;
}
/* items, not mesh nodes: one sofa is several glTF nodes (lessons F1 / log row 197) */
function looseCount() { return V ? new Set(V.model.parts.filter(isLoose).map(p => p.ud.spec_id || p.element || p.name)).size : 0; }
function setUnfurnished(on) {
  unfurnished = !!on;
  store.set("house-unfurnished-v1", unfurnished ? "1" : "0");
  markDoorsHidden();
  if (V) applyStageNow();
  if (target && target.part.viewHidden) setTarget(null);
  if (hoverPart?.viewHidden) setHover(null);
  const n = looseCount();
  perf.note({ event: "furnished", on: !unfurnished, loose_parts: n });
  toast(unfurnished ? (n ? `Unfurnished: ${n} loose item${n === 1 ? "" : "s"} hidden (furniture, soft furnishings, decor, plants)` : "Unfurnished: this build has no loose furniture yet")
    : "Furnished");
  furnishButtons();
  baPanel.userData.draw();
  refreshBoard();
}
function furnishButtons() {
  const b = $("baFurnish");
  if (b) { b.textContent = unfurnished ? "Unfurnished" : "Furnished"; b.setAttribute("aria-pressed", String(unfurnished)); }
}
function setDoorsHidden(on) {
  doorsHidden = on;
  markDoorsHidden();
  if (V) applyStageNow();
  toast(on ? "Doors hidden" : "Doors back");
  baPanel.userData.draw();
  refreshBoard();
}

function setAllDoors(open) {
  const n = V.doors.setAll(open);
  toast(n ? `${open ? "Opening" : "Closing"} ${n} door${n === 1 ? "" : "s"}` : "No doors in at this stage");
  $("doorsAll").textContent = open && n ? "Close doors" : "Open doors";
  refreshBoard();
}

/* ------------------------------------------------------------------ *
 *  Walk mode (desktop / phone) and overview
 * ------------------------------------------------------------------ */
const keys = new Set();
addEventListener("keydown", e => {
  if (/INPUT|TEXTAREA|SELECT/.test(e.target?.tagName)) return;
  keys.add(e.code);
  if (SIMPLE) {                                   // homeowners: walk, fly, Before / After, the frame HUD
    if (e.code === "KeyV") { if (flying) setFly(false); setWalk(!walk); }
    if (e.code === "KeyF" || e.code === "Space") { e.preventDefault(); setFly(!flying); }
    if (e.code === "KeyH") perf.toggle();
    if (e.code === "KeyB") beforeAfter(false);
    if (e.code === "KeyN") beforeAfter(true);
    if (e.code === "KeyG") setFastWalk(!fastWalk);
    if (e.code === "Escape" && marks?.active && !marks.noteOpen) marks.setActive(false);
    return;
  }
  if (e.code === "KeyG") setFastWalk(!fastWalk);
  if (e.code === "Space") { e.preventDefault(); togglePlay(); }
  if (e.code === "BracketRight" || e.code === "Period") nextStage();
  if (e.code === "BracketLeft" || e.code === "Comma") prevStage();
  if (e.code === "KeyX") setXray(!xray);
  if (e.code === "KeyM" && MODE.measure) setTool(tool === "measure" ? "info" : "measure");
  if (e.code === "KeyV") { if (flying) setFly(false); setWalk(!walk); }
  if (e.code === "KeyF") setFly(!flying);
  if (e.code === "KeyH") perf.toggle();
  if (e.code === "KeyO" && V?.doors) setAllDoors(!V.doors.anyOpen);
  if (e.code === "Escape") { setTarget(null); wallDraft = null; if (tool !== "info") { measure.clear(); setTool("info"); } }
  if (MODE.edit && (e.metaKey || e.ctrlKey) && e.code === "KeyZ") { e.preventDefault(); e.shiftKey ? V.editor.redo() : V.editor.undo(); }
});
addEventListener("keyup", e => keys.delete(e.code));

const TOOL_LABEL = { info: "Info", measure: "Measuring", heights: "Heights", addwall: "Add wall" };
function setTool(t) {
  tool = t;
  if (t !== "addwall") wallDraft = null;
  if (t !== "measure" && t !== "addwall") measure.hideMarker();
  if (t !== "heights") showHeights(null);
  $("toolMeasure").setAttribute("aria-pressed", String(t === "measure"));
  $("toolHeights").setAttribute("aria-pressed", String(t === "heights"));
  refreshBoard(); updateHelp();
}
/* the strip's tool button: Info → Measure → Heights → Info */
function cycleTool() { setTool(tool === "info" ? (MODE.measure ? "measure" : "heights") : tool === "measure" ? "heights" : "info"); }

/* homeowners arrive where the whole front of the house fits in view, on the line of the front path */
function establishingSpawn() {
  const house = new THREE.Box3();
  for (const p of V.model.parts) if (p.storey !== "site" && p.group !== "ground" && !/N21|No\.?21/i.test(p.element) && p.category !== "temporary") house.union(p.bbox);
  if (house.isEmpty()) return null;
  const path = (V.sidecar.spawns || []).find(s => /front/i.test(s.name));
  const cx = path ? path.position[0] : (house.min.x + house.max.x) / 2;
  const width = house.max.x - house.min.x, height = house.max.y - Math.max(house.min.y, -0.5);
  const aspect = innerWidth > 0 && innerHeight > 0 ? innerWidth / innerHeight : 1.6;          // a page opened in a hidden tab has no size yet
  const vfov = THREE.MathUtils.degToRad(70), hfov = 2 * Math.atan(Math.tan(vfov / 2) * aspect);   // a portrait phone needs to stand further back
  const d = Math.min(20, Math.max(width / 2 / Math.tan(hfov / 2) * 1.1, height / Math.tan(vfov / 2) * 0.9, 6));
  /* not behind a tree: try spots along the same line, left and right, and keep the first whose view of the middle
     of the front isn't crossed (in plan) by a tall piece of the setting (trees, the shed) */
  const tall = V.model.parts.filter(p => p.context && p.bbox.max.y - p.bbox.min.y > 2 && p.bbox.max.y > 1.6);
  const aim = new THREE.Vector2((house.min.x + house.max.x) / 2, house.max.z);
  const blocked = (x, z) => tall.some(p => {
    const b = p.bbox, seg = 24;
    for (let i = 1; i < seg; i++) {
      const t = i / seg, px = x + (aim.x - x) * t, pz = z + (aim.y - z) * t;
      if (px > b.min.x && px < b.max.x && pz > b.min.z && pz < b.max.z) return true;
    }
    return false;
  });
  const z = house.max.z + d;
  const x = [0, 2, -2, 4, -4, 6, -6, 8].map(o => cx + o).find(x => !blocked(x, z)) ?? cx;
  const pos = new THREE.Vector3(x, path ? path.position[1] : 0, z);
  const yaw = Math.atan2(-(aim.x - x), -(aim.y - z));        // face the middle of the front
  return { name: "Front of the house", position: pos.toArray(), yawDeg: THREE.MathUtils.radToDeg(yaw), pitchDeg: 6 };
}
let establishing = null;
const spawnDefs = () => {
  const list = V?.sidecar.spawns || [];
  if (!CUST || !V) return list;
  if (!establishing || establishing.for !== V) establishing = { for: V, spawn: establishingSpawn() };
  return establishing.spawn ? [establishing.spawn, ...list] : list;
};
let spawnIdx = 0;
function spawnAt(name) {
  const s = spawnDefs().find(s => s.name === name) || spawnDefs()[0];
  if (!s) return;
  feet.fromArray(s.position);
  yawPitch.yaw = THREE.MathUtils.degToRad(s.yawDeg || 0);
  yawPitch.pitch = s.pitchDeg ? THREE.MathUtils.degToRad(s.pitchDeg) : -0.05;
  if (renderer.xr.isPresenting) {
    fade.black(); fade.to(0, 0.6);
    player.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), yawPitch.yaw);
    player.updateMatrixWorld(true);
    const head = camera.getWorldPosition(new THREE.Vector3());
    player.position.x += feet.x - head.x; player.position.z += feet.z - head.z; player.position.y = feet.y + rigLift();
  } else if (!walk) setWalk(true);
  walker.settle(feet, 1);
}
function setWalk(on) {
  if (renderer.xr.isPresenting) return;
  walk = on;
  orbit.enabled = !on;
  if (on) {
    if (!feet.lengthSq()) feet.fromArray(spawnDefs()[0]?.position || [0, 0, 8]);
    player.position.copy(feet);
    camera.position.set(0, EYE, 0);
    camera.fov = 70;
  } else {
    player.position.set(0, 0, 0); player.quaternion.identity();
    camera.fov = 50;
    const c = V.model.bounds.getCenter(new THREE.Vector3());
    orbit.target.copy(c);
    camera.position.copy(feet).add(new THREE.Vector3(0, EYE + 4, 0)).addScaledVector(new THREE.Vector3(Math.sin(yawPitch.yaw), 0, Math.cos(yawPitch.yaw)), 6);
    camera.rotation.set(0, 0, 0);
    orbit.update();
  }
  if (!on) freeMouse();
  camera.updateProjectionMatrix();
  $("walk").setAttribute("aria-pressed", String(on));
  $("walk").textContent = on ? "Overview" : "Walk";
  updateHelp();
}
function overviewDefault() {
  const b = V.model.bounds, c = b.getCenter(new THREE.Vector3()), s = b.getSize(new THREE.Vector3()).length();
  orbit.target.copy(c);
  const fit = Math.max(1, 1.25 / camera.aspect);                     // a portrait phone needs to stand further back
  camera.position.copy(c).add(new THREE.Vector3(0.55, 0.45, 0.75).normalize().multiplyScalar(s * 1.05 * fit));
  orbit.update();
}
let glide = null;
function glideTo(p) { glide = { from: feet.clone(), to: new THREE.Vector3(p.x, p.y, p.z), t: 0 }; }

function desktopWalk(dt) {
  camera.rotation.set(yawPitch.pitch, yawPitch.yaw, 0, "YXZ");          // yaw 0 looks along -z (sidecar yawDeg)
  let f = 0, s = 0;
  if (keys.has("KeyW") || keys.has("ArrowUp")) f += 1;
  if (keys.has("KeyS") || keys.has("ArrowDown")) f -= 1;
  if (keys.has("KeyA") || keys.has("ArrowLeft")) s -= 1;
  if (keys.has("KeyD") || keys.has("ArrowRight")) s += 1;
  f -= touchMove.y; s += touchMove.x;              // the left thumb stick (phones): speed by how far it is pushed
  if (flying) {                                    // fly: no collision, Q / E down / up, Shift fast
    const v = (keys.has("ShiftLeft") ? FLY.fast : FLY.desk) * dt, yw = yawPitch.yaw;
    feet.x += (-Math.sin(yw) * f + Math.cos(yw) * s) * v;
    feet.z += (-Math.cos(yw) * f - Math.sin(yw) * s) * v;
    if (keys.has("KeyE")) feet.y += v;
    if (keys.has("KeyQ")) feet.y -= v;
    player.position.copy(feet);
    camera.position.set(0, EYE, 0);
    return;
  }
  if (landing) { stepLanding(dt, feet); player.position.copy(feet); camera.position.set(0, EYE, 0); return; }
  walkBoost = (f || s) && fastWalk ? Math.min(1, walkBoost + dt / FAST.ramp) : 0;      // Fast eases in; letting go stops at once
  const speed = deskWalkSpeed(keys.has("ShiftLeft") || keys.has("ShiftRight")) * dt;
  if (f || s) {
    glide = null;
    const yw = yawPitch.yaw;
    const d = new THREE.Vector3(-Math.sin(yw) * f + Math.cos(yw) * s, 0, -Math.cos(yw) * f - Math.sin(yw) * s);
    if (d.lengthSq() > 1) d.normalize();
    walker.move(feet, d.multiplyScalar(speed));
  } else if (glide) {
    glide.t += dt / Math.max(0.4, glide.from.distanceTo(glide.to) / (fastWalk ? 3.2 : 1.6));
    const goal = new THREE.Vector3().lerpVectors(glide.from, glide.to, easeOut(clamp01(glide.t)));
    walker.move(feet, goal.sub(feet).setY(0));
    if (glide.t >= 1) glide = null;
  }
  walker.settle(feet, dt);
  player.position.copy(feet);
  camera.position.set(0, EYE, 0);
}

/* ------------------------------------------------------------------ *
 *  Fly mode: round the site quickly, no collision. Headset: hold the
 *  right grip and you fly where the right controller points (1.5 m/s,
 *  up to 10 m/s with the right stick pushed forward; pull it back to
 *  reverse). Desktop: F, then WASD + Q / E. On release you ease down
 *  to the floor or ground beneath, nudged out of a wall if you let go
 *  inside one.
 * ------------------------------------------------------------------ */
const FLY = { base: 1.5, max: 10, desk: 4, fast: 10, land: 0.6 };
function setFly(on) {
  if (inVR()) return;
  if (on && !walk) setWalk(true);
  if (on === flying) return;
  flying = on;
  if (!on) startLanding(feet);
  $("fly").setAttribute("aria-pressed", String(flying));
  toast(on ? "Flying: W A S D, Q / E down / up, Shift faster · F to land" : "Landing");
  refreshBoard(); updateHelp();
}
/* feet: where the flight ended (the feet under the head). Sets `landing`: from -> to over FLY.land seconds */
function startLanding(from) {
  const ground = V?.sidecar.storeys?.site ?? 0;
  const to = walker.landing(from, ground);
  landing = { from: from.clone(), to, t: 0, dur: Math.max(0.3, Math.min(1.2, FLY.land * Math.sqrt(Math.abs(from.y - to.y) / 2 + 0.2))) };
  perf.tag("landing");
}
/* advance the landing; moves `pos` (feet) and returns true while it runs */
function stepLanding(dt, pos) {
  landing.t += dt / landing.dur;
  const k = easeOut(clamp01(landing.t));
  pos.lerpVectors(landing.from, landing.to, k);
  if (landing.t >= 1) landing = null;
  return !!landing;
}

/* ------------------------------------------------------------------ *
 *  Heights: what a ceiling, a beam or a lintel really is above the
 *  floor, and above YOUR eyes (the scale check, round 6). The Heights
 *  tool reads whatever the laser / mouse is on; a picked underside
 *  carries the same line on the board.
 * ------------------------------------------------------------------ */
const UNDERSIDE_NAME = { steel: "steel beam", timber_beam: "beam", lintel: "lintel", ceiling_joist: "ceiling", wall_lining: "ceiling",
  deck: "underside of the floor", joist: "joist", rafter: "rafter", roof_layer: "roof", roof_cover: "roof", rooflight: "rooflight" };
function eyeAndFloor() {
  const head = camera.getWorldPosition(new THREE.Vector3());
  const myFloor = inVR() ? player.position.y - rigLift() : feet.y;
  return { head, myFloor, eye: head.y - myFloor };
}
function heightInfo(h) {
  if (!h || !V) return null;
  const p = partOf(h), { head, eye, myFloor } = eyeAndFloor();
  const pt = h.point;
  if (h.normal.y < -0.5) {                                 // an underside: its height above the floor below it
    const f = walker.floorAt(pt.x, pt.y - BODY.step - 0.02, pt.z, 12);
    const above = f === null ? null : pt.y - f, clr = pt.y - head.y;
    const name = UNDERSIDE_NAME[p?.group] || "underside";
    const txt = `${name[0].toUpperCase()}${name.slice(1)} ${above === null ? "—" : `${above.toFixed(2)} m`} above the floor · ${Math.abs(clr).toFixed(2)} m ${clr >= 0 ? "above" : "below"} your eyes`;
    return { underside: true, above, clearance: clr, eye, text: txt, short: [`${name} ${above === null ? "—" : above.toFixed(2) + " m"}`, `${clr >= 0 ? "+" : "−"}${Math.abs(clr).toFixed(2)} m from your eyes`] };
  }
  const f = h.normal.y > 0.5 ? null : walker.floorAt(pt.x + h.normal.x * 0.05, pt.y, pt.z + h.normal.z * 0.05, 12);
  const base = h.normal.y > 0.5 ? myFloor : f;
  const up = base === null ? null : pt.y - base;
  return { underside: false, above: up, clearance: pt.y - head.y, eye,
           text: `${up === null ? "—" : `${up.toFixed(2)} m`} above ${h.normal.y > 0.5 ? "your floor" : "the floor"} · your eyes ${eye.toFixed(2)} m`,
           short: [`${up === null ? "—" : up.toFixed(2) + " m"} up`, `eyes ${eye.toFixed(2)} m`] };
}
/* a small label at the laser / mouse point, redrawn only when its text changes */
const heightLabel = (() => {
  const cv = document.createElement("canvas"); cv.width = 384; cv.height = 128;
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.generateMipmaps = false; tex.minFilter = THREE.LinearFilter;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true, toneMapped: false }));
  s.renderOrder = 992; s.visible = false; s.center.set(0.5, -0.15);
  s.userData = { cv, tex, text: "" };
  scene.add(s);
  return s;
})();
function showHeights(h) {
  const info = h && heightInfo(h);
  if (!info) { heightLabel.visible = false; return; }
  const text = info.short.join("|");
  const { cv, tex } = heightLabel.userData;
  if (text !== heightLabel.userData.text) {
    heightLabel.userData.text = text;
    const c = cv.getContext("2d");
    c.clearRect(0, 0, 384, 128);
    c.fillStyle = "rgba(14,16,14,0.9)"; c.beginPath(); c.roundRect(4, 4, 376, 120, 20); c.fill();
    c.fillStyle = "#ffd23f"; c.font = "600 44px system-ui, sans-serif"; c.textAlign = "center"; c.fillText(info.short[0], 192, 54);
    c.fillStyle = "#f4f3ee"; c.font = "34px system-ui, sans-serif"; c.fillText(info.short[1], 192, 102);
    tex.needsUpdate = true;
  }
  heightLabel.position.copy(h.point);
  const d = h.point.distanceTo(camera.getWorldPosition(new THREE.Vector3()));
  const k = 0.45 * Math.max(0.6, d / 2.2);                 // about 12 degrees wide wherever it is
  heightLabel.scale.set(k, k / 3, 1);
  heightLabel.visible = true;
}

/* ------------------------------------------------------------------ *
 *  Height check: stand up straight and press. The eyes should be at
 *  the person's height x 0.936; the difference from what the headset
 *  reports goes on the rig ("floor corrected by +0.50 m"). A Quest
 *  whose floor is set too high, or someone sitting, otherwise sees the
 *  house half a metre too tall. The height is remembered (cm or ft/in).
 * ------------------------------------------------------------------ */
const EYE_RATIO = 0.936;

/* VR quality (round 6c): the eye-buffer scale and the shadows, set when you enter VR (a WebXR session cannot change
   its buffer size). Foveation is always at its strongest (1). If a session averages under 64 fps after 20 s, the
   next one starts a step lower, and the card says so. Remembered per browser. */
const VRQ = {
  sharp: { label: "Sharp", scale: 1.0, shadows: true },
  balanced: { label: "Balanced", scale: 0.9, shadows: true },
  fast: { label: "Fast", scale: 0.8, shadows: false, lean: true },
};
/* "lean" materials for the Fast tier: colour + ambient occlusion kept, the normal / roughness / metalness maps set
   aside (three texture reads and the tangent maths per pixel), put back when the session ends */
function leanMaterials(on) {
  for (const v of versions.values()) if (v.model) for (const set of v.model.sets.values()) {
    const m = set.normal;
    if (on && !m.userData.lean) { m.userData.lean = { normalMap: m.normalMap, roughnessMap: m.roughnessMap, metalnessMap: m.metalnessMap }; m.normalMap = m.roughnessMap = m.metalnessMap = null; m.needsUpdate = true; }
    else if (!on && m.userData.lean) { Object.assign(m, m.userData.lean); delete m.userData.lean; m.needsUpdate = true; }
  }
}
let vrQuality = VRQ[store.get("house-vr-quality", "balanced")] ? store.get("house-vr-quality", "balanced") : "balanced";
function cycleQuality() {
  const k = Object.keys(VRQ);
  vrQuality = k[(k.indexOf(vrQuality) + 1) % k.length];
  store.set("house-vr-quality", vrQuality);
  toast(`VR quality: ${VRQ[vrQuality].label} (${Math.round(VRQ[vrQuality].scale * 100)} % resolution${VRQ[vrQuality].shadows ? "" : ", no shadows, plain surfaces"})${renderer.xr.isPresenting ? " — from the next time you enter VR" : ""}`);
  refreshBoard();
}
const xrFps = { since: 0, frames: 0, judged: false };
function judgeXrFps(now) {
  if (!renderer.xr.isPresenting || xrFps.judged) return;
  if (!xrFps.since) { xrFps.since = now; xrFps.frames = 0; return; }
  xrFps.frames++;
  if (now - xrFps.since < 20000) return;
  xrFps.judged = true;
  const fps = xrFps.frames * 1000 / (now - xrFps.since);
  perf.note({ event: "xr fps judged", fps: +fps.toFixed(1), quality: vrQuality });
  if (fps < 64 && vrQuality !== "fast") {
    const next = vrQuality === "sharp" ? "balanced" : "fast";
    store.set("house-vr-quality", next); vrQuality = next;
    showCard("Frame rate", [`This headset ran at ${fps.toFixed(0)} fps here. Next time you enter VR it starts at "${VRQ[next].label}" (${Math.round(VRQ[next].scale * 100)} % resolution${VRQ[next].shadows ? "" : ", no shadows"}).`, "Board → Tools → VR to change it."], null, 10);
  }
}
const ftIn = m => { const i = Math.round(m / 0.0254); return `${Math.floor(i / 12)} ft ${i % 12}`; };
const heightText = m => `${Math.round(m * 100)} cm (${ftIn(m)})`;
/* Jack's words: "Height set to 4 ft; change it under Height" (whole feet without "0 in"; other heights as 5 ft 7 in) */
const ftInWords = m => { const i = Math.round(m / 0.0254); return i % 12 ? `${Math.floor(i / 12)} ft ${i % 12} in` : `${i / 12} ft`; };
/* "185", "185 cm", "1.854", "6'1", "6 ft 1", "6' 1\"" -> metres, or null */
function parseHeight(t) {
  const s = String(t || "").trim().toLowerCase();
  const fi = s.match(/^(\d)\s*(?:'|ft|feet|foot)\s*(\d{1,2})?\s*(?:"|in|inches)?$/);
  if (fi) return (+fi[1] * 12 + (+fi[2] || 0)) * 0.0254;
  const n = parseFloat(s);
  if (!isFinite(n)) return null;
  const m = /cm/.test(s) || n > 3 ? n / 100 : n;
  return m >= 1.0 && m <= 2.3 ? m : null;
}
function setPersonHeight(m) {
  personHeight = Math.min(2.3, Math.max(1.0, Math.round(m * 1000) / 1000));
  store.set(HEIGHT_KEY, personHeight);
  if (inVR() && floorOffset) heightCheck({ quiet: true });     // already corrected: follow the new height at once
  baPanel.userData.draw();
  refreshBoard();
}
/* the eye height the headset reports above the floor you stand on, without our lift */
const rawEye = () => camera.getWorldPosition(new THREE.Vector3()).y - player.position.y;
function heightCheck(opts = {}) {
  if (!inVR()) { toast("Height check works in the headset: stand up straight, then press it on the board"); return; }
  const quiet = !!opts.quiet || !!opts.auto;
  const raw = rawEye(), want = personHeight * EYE_RATIO;
  const before = floorOffset;
  floorOffset = Math.max(-0.8, Math.min(1.0, want - raw));
  player.position.y += floorOffset - before;
  lowEyeSince = 0;
  const msg = `Floor corrected by ${floorOffset >= 0 ? "+" : "−"}${Math.abs(floorOffset).toFixed(2)} m (eyes ${raw.toFixed(2)} → ${want.toFixed(2)} m for ${heightText(personHeight)})`;
  toast(msg);
  if (!quiet) showCard("Height check", [msg, Math.abs(floorOffset) > 0.3 ? "Sitting, or the Quest's floor was off: you now see the house from your standing eye height. Press again if you change posture; Reset puts it back." : "That was close already."], null, 7);
  perf.note({ event: "height check", person_m: personHeight, raw_eye: +raw.toFixed(3), offset: +floorOffset.toFixed(3), auto: !!opts.auto, quiet: !!opts.quiet });
  if (!opts.auto) hapticPulse([hands.left, hands.right], 0.5, 40);
  baPanel.userData.draw();
  refreshBoard();
}
function heightReset() {
  player.position.y -= floorOffset; floorOffset = 0;
  perf.note({ event: "height reset" });
  toast("Floor correction reset: the Quest's own floor"); refreshBoard();
}
function askHeight() {                          // desktop: type it in any unit
  const t = prompt("Your height (e.g. 185 cm, 1.854 m or 6 ft 1)", heightText(personHeight));
  if (t === null) return;
  const m = parseHeight(t);
  if (m) { setPersonHeight(m); toast(`Height ${heightText(m)}: eyes at about ${(m * EYE_RATIO).toFixed(2)} m`); } else toast(`Could not read "${t}" as a height`);
}
/* standing, with the eyes under 1.35 m for 10 s: say so once (and again after a reset) */
let lowEyeSince = 0, lowEyeWarned = false;
function watchEyeHeight(now) {
  if (flying || hovering || landing || lowEyeWarned || floorOffset || heightOffer) { lowEyeSince = 0; return; }
  const eye = eyeAndFloor().eye;
  if (eye >= 1.35) { lowEyeSince = 0; return; }
  if (!lowEyeSince) lowEyeSince = now;
  else if (now - lowEyeSince > 10000) {
    lowEyeWarned = true;
    showCard("Height check", ["You look seated or your Quest floor is low: press Height check.", `Your eyes read ${eye.toFixed(2)} m above the floor; at ${heightText(personHeight)} standing they should be about ${(personHeight * EYE_RATIO).toFixed(2)} m.`, SIMPLE ? "Press Height on your left wrist: sitting or standing, it puts your eyes at your standing height. (Shown once.)" : "Board → Tools → Height check: sitting or standing, it puts your eyes at your standing height. (Shown once.)"], null, 12);
    perf.note({ event: "low eye warning", eye: +eye.toFixed(3) });
  }
}

/* the scale cue: a plain 1.80 m figure and a 1 m post in 100 mm bands, put down in front of you */
function makeScaleCue() {
  const g = new THREE.Group();
  g.name = "scale cue";
  const grey = new THREE.MeshStandardMaterial({ color: 0x8b9096, roughness: 0.8 });
  const add = (geo, x, y, z, m = grey) => { const o = new THREE.Mesh(geo, m); o.position.set(x, y, z); o.castShadow = true; g.add(o); return o; };
  add(new THREE.CapsuleGeometry(0.065, 0.74, 4, 10), -0.1, 0.435, 0);           // legs: 0 to 0.87
  add(new THREE.CapsuleGeometry(0.065, 0.74, 4, 10), 0.1, 0.435, 0);
  add(new THREE.CapsuleGeometry(0.17, 0.42, 4, 12), 0, 1.21, 0);                // body: 0.87 to 1.55
  add(new THREE.CapsuleGeometry(0.05, 0.56, 4, 8), -0.25, 1.17, 0);             // arms
  add(new THREE.CapsuleGeometry(0.05, 0.56, 4, 8), 0.25, 1.17, 0);
  add(new THREE.SphereGeometry(0.1, 16, 12), 0, 1.70, 0);                       // head: top at 1.80
  const red = new THREE.MeshStandardMaterial({ color: 0xc23b2e, roughness: 0.7 }), white = new THREE.MeshStandardMaterial({ color: 0xf2f0ea, roughness: 0.7 });
  for (let i = 0; i < 10; i++) add(new THREE.BoxGeometry(0.05, 0.1, 0.05), 0.55, 0.05 + i * 0.1, 0, i % 2 ? white : red);
  const lab = (text, y, x) => {
    const cv = document.createElement("canvas"); cv.width = 192; cv.height = 64;
    const c = cv.getContext("2d"); c.fillStyle = "rgba(14,16,14,0.85)"; c.beginPath(); c.roundRect(2, 2, 188, 60, 14); c.fill();
    c.fillStyle = "#fff"; c.font = "600 36px system-ui, sans-serif"; c.textAlign = "center"; c.fillText(text, 96, 44);
    const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace;
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, depthTest: true, toneMapped: false }));
    sp.scale.set(0.24, 0.08, 1); sp.position.set(x, y, 0); g.add(sp);
  };
  lab("1.80 m", 1.92, 0); lab("1 m", 1.1, 0.55);
  scene.add(g);
  return g;
}
function toggleScaleCue() {
  if (!scaleCue) scaleCue = makeScaleCue();
  else if (scaleCue.visible) { scaleCue.visible = false; refreshBoard(); return; }
  const head = camera.getWorldPosition(new THREE.Vector3());
  const fwd = camera.getWorldDirection(new THREE.Vector3()).setY(0);
  if (fwd.lengthSq() < 1e-6) fwd.set(0, 0, -1);
  fwd.normalize();
  const at = (walk || inVR()) ? head.clone().addScaledVector(fwd, 1.6) : (target?.point?.clone() || orbit.target.clone());
  const f = walker.floorAt(at.x, (walk || inVR()) ? eyeAndFloor().myFloor : at.y + 0.5, at.z, 12);
  scaleCue.position.set(at.x, f ?? eyeAndFloor().myFloor, at.z);
  scaleCue.rotation.y = Math.atan2(-fwd.x, -fwd.z) + Math.PI;               // facing you
  scaleCue.visible = true;
  renderer.shadowMap.needsUpdate = true;
  toast("Scale figure: 1.80 m tall, beside a 1 m post in 100 mm bands");
  refreshBoard();
}

/* ------------------------------------------------------------------ *
 *  VR: the board in the left hand, the right laser, locomotion, fly
 * ------------------------------------------------------------------ */
const vrBoard = createVRBoard();
const wristTab = createBoardTab();
/* homeowners and the studio review: a small panel on the back of the left wrist instead of the board (round 7, Jack
   1 Nov): Before | After | Height / No doors | Go to | Fast / -1 in | +1 in | Mark (review only). Three columns so
   every label stays big enough to read in the headset (40 px on a 15 cm panel: about 9 mm letters). */
let heightOffer = false;
/* round 7c (Jack, 1 Nov): Turn (smooth / snap) and Comfort (blur / vignette / off) added: four rows of three */
/* round 8: Furnished / Unfurnished next to No doors */
const WRIST_ROWS = [["before", "after", "height"], ["doors", "furnish", "goto"], ["fast", "turn", "comfort"], ["hdown", "hup", MODE.marks ? "mark" : null]];
const baPanel = (() => {
  const CWD = 210, RH = 150, X0 = 14, Y0 = 16, COLS = 3, ROWS = WRIST_ROWS.length;
  const W = X0 * 2 + COLS * CWD - 12, Hh = Y0 * 2 + ROWS * RH - 12;
  const cv = document.createElement("canvas"); cv.width = W; cv.height = Hh;
  const c = cv.getContext("2d");
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.generateMipmaps = false; tex.minFilter = THREE.LinearFilter;
  const PW = 0.2 * W / 860;                                   // the same pixel size as the round-6c panel
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(PW, PW * Hh / W),
    new THREE.MeshBasicMaterial({ map: tex, transparent: true, toneMapped: false, depthTest: false, side: THREE.DoubleSide }));
  mesh.renderOrder = 905; mesh.visible = false;
  mesh.position.set(0, 0.05, 0.075); mesh.rotation.set(-Math.PI / 2.6, 0, 0);          // on the back of the left wrist
  const LABEL = { before: "Before", after: "After", height: "Height", doors: "No doors", goto: "Go to", fast: "Fast",
                  hdown: "−1 in", hup: "+1 in", mark: "Mark", turn: "Turn", comfort: "Comfort", furnish: "Furniture" };
  const isOn = id => id === "after" ? afterShown() : id === "before" ? !afterShown() : id === "doors" ? doorsHidden : id === "furnish" ? unfurnished
    : id === "height" ? !!floorOffset : id === "fast" ? fastWalk : id === "goto" ? gotoMenu.isOpen : id === "mark" ? !!marks?.active : false;
  const sub = id => id === "height" ? ftInWords(personHeight) : id === "mark" && marks?.active ? MARK_KINDS[marks.kind].label
    : id === "fast" ? (fastWalk ? "on" : "") : id === "furnish" ? (unfurnished ? "hidden" : "shown") : id === "turn" ? turnMode : id === "comfort" ? COMFORT_LABEL[comfort] : "";
  let hov = null, key = "";
  const draw = () => {
    const k = `${afterShown()}|${hov}|${floorOffset}|${doorsHidden}|${fastWalk}|${gotoMenu.isOpen}|${marks?.active}|${marks?.kind}|${personHeight}|${turnMode}|${comfort}|${unfurnished}`;
    if (k === key) return; key = k;
    c.clearRect(0, 0, W, Hh);
    c.fillStyle = "rgba(14,16,15,0.92)"; c.beginPath(); c.roundRect(3, 3, W - 6, Hh - 6, 28); c.fill();
    WRIST_ROWS.forEach((row, r) => row.forEach((id, col) => {
      if (!id) return;
      const x = X0 + col * CWD, y = Y0 + r * RH, on = isOn(id), here = hov === id;
      const onFill = id === "mark" ? MARK_KINDS[marks?.kind || "correction"].css : "#f2d36b";
      c.fillStyle = on ? onFill : here ? "rgba(255,255,255,0.24)" : "rgba(255,255,255,0.1)";
      c.beginPath(); c.roundRect(x, y, CWD - 12, RH - 12, 22); c.fill();
      if (here && on) { c.strokeStyle = "#ffffff"; c.lineWidth = 5; c.stroke(); }
      c.fillStyle = on ? "#111" : "#f4f3ee"; c.textAlign = "center"; c.textBaseline = "middle";
      const s2 = sub(id);
      c.font = "700 40px system-ui, sans-serif"; c.fillText(LABEL[id], x + (CWD - 12) / 2, y + (RH - 12) / 2 + (s2 ? -16 : 2));
      if (s2) { c.font = "600 30px system-ui, sans-serif"; c.fillText(s2, x + (CWD - 12) / 2, y + (RH - 12) / 2 + 26); }
    }));
    tex.needsUpdate = true;
  };
  /* uv from the raycast (v up) -> the button id, or null */
  const at = uv => {
    if (!uv) return null;
    const col = Math.floor((uv.x * W - X0) / CWD), row = Math.floor(((1 - uv.y) * Hh - Y0) / RH);
    return WRIST_ROWS[row]?.[col] || null;
  };
  mesh.userData = {
    hover(uv) { const h = at(uv); if (h !== hov) { hov = h; draw(); } },
    press(uv) {
      const id = typeof uv === "string" ? uv : at(uv);
      if (!id) return null;
      if (id === "height") heightCheck();
      else if (id === "doors") setDoorsHidden(!doorsHidden);
      else if (id === "furnish") setUnfurnished(!unfurnished);
      else if (id === "goto") gotoMenu.toggle();
      else if (id === "fast") setFastWalk(!fastWalk);
      else if (id === "hdown") setPersonHeight(personHeight - 0.0254);
      else if (id === "hup") setPersonHeight(personHeight + 0.0254);
      else if (id === "mark") marks?.toggle();
      else if (id === "turn") setTurnMode(turnMode === "smooth" ? "snap" : "smooth");
      else if (id === "comfort") setComfort(COMFORT[(COMFORT.indexOf(comfort) + 1) % COMFORT.length]);
      else beforeAfter(id === "after");
      draw();
      return id;
    },
    /* the world point of a button's centre (the simulated headset aims at it) */
    point(id) {
      const r = WRIST_ROWS.findIndex(row => row.includes(id)), col = WRIST_ROWS[r].indexOf(id);
      const u = (X0 + col * CWD + (CWD - 12) / 2) / W, v = (Y0 + r * RH + (RH - 12) / 2) / Hh;
      mesh.updateMatrixWorld(true);
      return mesh.localToWorld(new THREE.Vector3((u - 0.5) * PW, (0.5 - v) * PW * Hh / W, 0));
    },
    draw, rows: WRIST_ROWS,
  };
  return mesh;
})();
const afterShown = () => !!V && stageIndex(stageValue) >= stageN && V.def.kind === "proposal";

/* ------------------------------------------------------------------ *
 *  Fast walk (Jack, 1 Nov: "a faster walking toggle (this is also
 *  needed for the customer)"): the wrist's Fast, G on a screen, the
 *  board's Tools tab. Walking speed (the stick, the hover walk, a
 *  screen's W A S D and click-to-walk) doubles: 1.4 -> 3 m/s in the
 *  headset (homeowners 0.9 -> 3), easing up over 0.6 s after the stick
 *  is pushed and stopping at once when it is let go (no slide). Fly
 *  speeds do not change. Remembered for the session.
 * ------------------------------------------------------------------ */
/* ------------------------------------------------------------------ *
 *  Turning and comfort (round 7c, Jack 1 Nov). Homeowner and review:
 *  the right stick turns SMOOTHLY (75 deg/s at full push, scaled by the
 *  push, easing in and out over 0.15 s); "Turn" on the wrist switches
 *  to the old 30 deg snap. COMFORT while turning or moving on the
 *  sticks: "blur" (camera motion blur, src/house/motionblur.js; the
 *  default), "vignette" (the dark ring, as before) or "off". Both are
 *  remembered for the session. Builder, inspector and architect keep
 *  snap turning and the vignette.
 * ------------------------------------------------------------------ */
const TURN = { rate: THREE.MathUtils.degToRad(75), ease: 0.15 };
const COMFORT = ["blur", "vignette", "off"];
const sessGet = (k, d, ok) => { try { const v = sessionStorage.getItem(k); return ok(v) ? v : d; } catch (_) { return d; } };
const sessSet = (k, v) => { try { sessionStorage.setItem(k, v); } catch (_) {} };
let turnMode = SIMPLE ? sessGet("house-turn", "smooth", v => v === "smooth" || v === "snap") : "snap";
let comfort = SIMPLE ? sessGet("house-comfort", "blur", v => COMFORT.includes(v)) : "vignette";
let turnVel = 0;                                // rad/s of the smooth turn now (eased)
let blurFade = 0;                               // 0..1: the motion blur fading in while you move, out when you stop
/* round 7d (Jack: "I don't like the blur, it's way too much"): a third of the r7c strength, only on genuinely fast
   turns (normal looking and walking stay sharp), edges only, quick fades */
const BLUR = { fade: 0.08, xrShutter: 0.33, deskShutter: 0.25, turnMin: 2.0, xrTurnFrac: 0.8, flyMin: 6 };
const COMFORT_LABEL = { blur: "subtle blur", vignette: "vignette", off: "off" };
/* the screen's Comfort button (phones get the short form so the bar stays one or two rows) */
function comfortButton() {
  const b = $("baComfort"); if (!b) return;
  b.textContent = IS_TOUCH ? { blur: "Subtle blur", vignette: "Vignette", off: "Comfort off" }[comfort] : `Comfort: ${COMFORT_LABEL[comfort]}`;
}
function setTurnMode(m) {
  turnMode = m; turnVel = 0; sessSet("house-turn", m);
  perf.note({ event: "turn mode", mode: m });
  toast(m === "smooth" ? "Turning: smooth (right stick)" : "Turning: snap, 30° steps");
  baPanel.userData.draw();
}
function setComfort(m) {
  comfort = m; sessSet("house-comfort", m);
  perf.note({ event: "comfort", mode: m });
  toast(m === "blur" ? "Comfort: subtle blur on fast turns" : m === "vignette" ? "Comfort: dark vignette while you turn or move" : "Comfort: off");
  comfortButton();
  baPanel.userData.draw();
}
const FAST = { vr: 3.0, ramp: 0.6, desk: 2 };
let fastWalk = (() => { try { return sessionStorage.getItem("house-fast-walk") === "1"; } catch (_) { return false; } })();
let walkBoost = 0;                              // 0..1: how far the fast speed has eased in since the stick was pushed
const smooth = t => t * t * (3 - 2 * t);
function setFastWalk(on) {
  fastWalk = !!on;
  try { sessionStorage.setItem("house-fast-walk", fastWalk ? "1" : "0"); } catch (_) {}
  for (const id of ["baFast", "fastWalk"]) $(id)?.setAttribute("aria-pressed", String(fastWalk));
  perf.note({ event: "fast walk", on: fastWalk });
  toast(fastWalk ? `Fast walk on: ${inVR() ? `${Math.max(FAST.vr, MODE.vr.speed * 2).toFixed(1)} m/s` : "twice the speed"} (fly speeds unchanged)` : "Fast walk off");
  baPanel.userData.draw();
  refreshBoard();
}
const vrWalkSpeed = () => {
  const base = MODE.vr.speed;
  return fastWalk ? base + (Math.max(FAST.vr, base * 2) - base) * smooth(walkBoost) : base;
};
const deskWalkSpeed = shift => {
  const base = shift ? 2.6 : 1.4;
  return fastWalk ? base * (1 + (FAST.desk - 1) * smooth(walkBoost)) : base;
};

/* ------------------------------------------------------------------ *
 *  Teleport on the trigger (homeowner and review modes; Jack, 1 Nov):
 *  point the right controller at a floor or the ground and click the
 *  trigger. A ring shows where you would land; walls, roofs, the tops
 *  of furniture and walls, and spots with no headroom are refused (the
 *  laser dot turns red and the controller buzzes once). A door still
 *  opens, a wrist button still presses, and in Mark mode the trigger
 *  draws instead. The stick-forward teleport stays as well.
 * ------------------------------------------------------------------ */
const NOT_FLOOR = new Set(["roof_cover", "roof_layer", "rafter", "hip", "valley", "ridge", "rooflight", "ceiling_joist", "wall_plate",
  "lintel", "steel", "timber_beam", "window", "door", "scaffold", "prop", "spoil"]);
const _up = new THREE.Ray();
function standable(pt, outside) {
  /* headroom: nothing solid within 1.5 m above (not under a table, a stair or a low roof) */
  _up.origin.set(pt.x, pt.y + 0.05, pt.z); _up.direction.set(0, 1, 0);
  if (V.bvh.raycast(_up, 1.5, V.model.masks.solid)) return false;
  return walker.free(pt);
}
let spotMemo = null;                            // the laser rests on one spot for many frames: the answer is kept
function walkableSpot(h) {
  if (!V || !h || h.door || h.normal.y < 0.7) return null;
  if (spotMemo && spotMemo.v === V && spotMemo.part === h.part && spotMemo.at.distanceToSquared(h.point) < 0.0025) return spotMemo.res;
  const res = walkableSpotNow(h);
  spotMemo = { v: V, part: h.part, at: h.point.clone(), res };
  return res;
}
function walkableSpotNow(h) {
  const p = partOf(h);
  if (!p || !p.collide || p.storey === "roof" || NOT_FLOOR.has(p.group) || /^wall/.test(p.group || "")) return null;
  const st = V.sidecar.storeys || {}, site = st.site ?? 0;
  const outside = !!p.context || p.group === "ground" || p.storey === "site";
  if (outside) { if (h.point.y < site - 2.5 || h.point.y > site + 1.5) return null; }
  else {                                          // on a storey's floor (a stair tread or a worktop is not a place to land)
    const levels = ["ground", "first"].map(k => st[k]).filter(v => v != null);
    if (!levels.length || Math.min(...levels.map(l => Math.abs(h.point.y - l))) > 0.45) return null;
  }
  const pt = h.point.clone();
  if (standable(pt, outside)) return pt;
  for (let r = 0.15; r <= 0.46; r += 0.15) for (let i = 0; i < 8; i++) {      // a step off the wall you aimed at the foot of
    const a = i / 8 * Math.PI * 2, x = pt.x + Math.cos(a) * r, z = pt.z + Math.sin(a) * r;
    const f = walker.floorAt(x, pt.y, z, 0.15);
    if (f === null || Math.abs(f - pt.y) > 0.1) continue;
    const q = new THREE.Vector3(x, f, z);
    if (standable(q, outside)) return q;
  }
  return null;
}
const headYaw = () => { const d = camera.getWorldDirection(new THREE.Vector3()); return Math.atan2(-d.x, -d.z); };
/* put the feet at `to` (a short fade in the headset); yaw (radians, 0 = looking along -z) turns you to face that way */
function teleportTo(to, yaw = null, why = "teleport") {
  perf.tag(why);
  xrBlur.reset(); blurPass?.reset();
  if (inVR()) {
    fade.black(); fade.to(0, 0.35);
    flying = hovering = false; landing = null; tpAim = null; tpRing.visible = false;
    if (yaw !== null) rotateAroundHead(yaw - headYaw());
    const head = camera.getWorldPosition(new THREE.Vector3());
    player.position.x += to.x - head.x; player.position.z += to.z - head.z; player.position.y = to.y + rigLift();
  } else {
    glide = null; landing = null;
    if (flying) { flying = false; $("fly").setAttribute("aria-pressed", "false"); $("baFly").setAttribute("aria-pressed", "false"); }
    if (!walk) setWalk(true);
    feet.copy(to);
    if (yaw !== null) { yawPitch.yaw = yaw; yawPitch.pitch = -0.05; }
    player.position.copy(feet);
  }
}
const trigRing = new THREE.Mesh(tpRingGeo(), new THREE.MeshBasicMaterial({ color: 0x9fe08a, transparent: true, opacity: 0.85, toneMapped: false, depthTest: false }));
trigRing.renderOrder = 971; trigRing.visible = false;
scene.add(trigRing);
function tpRingGeo() { return new THREE.RingGeometry(0.16, 0.21, 40).rotateX(-Math.PI / 2); }

/* ------------------------------------------------------------------ *
 *  Go to (Jack, 1 Nov): a menu of the rooms by their plain names, per
 *  storey, and the places outside (Road, Front path, Drive, Porch,
 *  Back garden). Each jumps to a standing point clear of furniture,
 *  facing the main view: the spec's named camera for that room where
 *  there is one (spec_v*.json cameras, matched to Before / After),
 *  else the free spot nearest the room's middle, facing the longest
 *  clear view. Rooms come from the version on screen, so a room that
 *  only exists After is only offered After. Headset: the wrist's
 *  Go to opens a panel in front of you; point and pull the trigger;
 *  the trigger anywhere else, or Go to again, closes it. Screen: the
 *  "Go to" list on the bottom bar.
 * ------------------------------------------------------------------ */
let specCameras = [], specWalk = null;
const ROOM_NAME = [
  [/kitchen.*(living|dining)|open plan/i, "Kitchen-diner"], [/^living/i, "Living room"], [/^sitting/i, "Sitting room"],
  [/bedroom\s*(\d)/i, m => `Bedroom ${m[1]}`], [/en-?suite/i, "En-suite"], [/bathroom/i, "Bathroom"], [/cloaks.*w\.?c/i, "Downstairs WC"],
  [/cloaks lobby/i, "Cloaks lobby"], [/^cloaks/i, "Cloaks"], [/utility/i, "Utility"], [/conservatory/i, "Conservatory"],
  [/landing/i, "Landing"], [/^hall/i, "Hall"], [/^kitchen/i, "Kitchen"], [/^store/i, "Store"], [/^lobby/i, "Lobby"],
];
const SKIP_ROOM = /^cpd|cupboard|porch/i;                   // cupboards are not places; the porch is listed outside
function plainRoomName(name) {
  for (const [rx, out] of ROOM_NAME) { const m = String(name).match(rx); if (m) return typeof out === "function" ? out(m) : out; }
  const s = String(name).replace(/\s*\(.*\)\s*/g, "").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : name;
}
const yawTo = (from, to) => Math.atan2(-(to.x - from.x), -(to.z - from.z));
const viewOf = () => V?.def.kind === "proposal" ? "after" : "before";
function inPoly(poly, x, z) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) inside = !inside;
  }
  return inside;
}
/* the longest clear horizontal view from eye height at feet `pt` (16 directions) */
function bestView(pt) {
  const r = new THREE.Ray(new THREE.Vector3(pt.x, pt.y + 1.5, pt.z), new THREE.Vector3());
  let best = 0, yaw = 0;
  for (let i = 0; i < 16; i++) {
    const a = i / 16 * Math.PI * 2;
    r.direction.set(-Math.sin(a), 0, -Math.cos(a));
    const h = V.bvh.raycast(r, 40, V.model.masks.solid);
    const d = h ? h.distance : 40;
    if (d > best) { best = d; yaw = a; }
  }
  return yaw;
}
/* feet from a spec camera's eye: the floor under it, nudged clear of a wall */
function feetFromEye(eye, floorY) {
  const f = walker.floorAt(eye[0], (floorY ?? eye[1] - 1.5) + 0.2, eye[2], 1.2);
  if (f === null) return null;
  const pt = new THREE.Vector3(eye[0], f, eye[2]);
  if (walker.free(pt)) return pt;
  const l = walker.landing(pt.clone().setY(f + 0.05), f);
  return Math.abs(l.y - f) < 0.2 && l.distanceTo(pt) < 1.0 ? l : null;
}
function roomStandPoint(el) {
  const poly = el.params.polygon, fy = el.params.floor;
  let cx = 0, cz = 0; for (const [x, z] of poly) { cx += x / poly.length; cz += z / poly.length; }
  const xs = poly.map(q => q[0]), zs = poly.map(q => q[1]);
  const cands = [];
  for (let x = Math.min(...xs) + 0.3; x <= Math.max(...xs) - 0.3; x += 0.25)
    for (let z = Math.min(...zs) + 0.3; z <= Math.max(...zs) - 0.3; z += 0.25)
      if (inPoly(poly, x, z)) cands.push([Math.hypot(x - cx, z - cz), x, z]);
  if (inPoly(poly, cx, cz)) cands.push([0, cx, cz]);
  cands.sort((a, b) => a[0] - b[0]);
  for (const [, x, z] of cands.slice(0, 160)) {
    const f = walker.floorAt(x, fy + 0.3, z, 0.6);
    if (f === null || Math.abs(f - fy) > 0.3) continue;
    const pt = new THREE.Vector3(x, f, z);
    if (standable(pt, false)) return pt;
  }
  return null;
}
let placesCache = null;
function places() {
  if (!V) return [];
  const ck = `${V.def.id}|${viewOf()}|${specCameras.length}|${stageIndex(stageValue)}`;
  if (placesCache?.key === ck) return placesCache.list;
  const t0 = performance.now(), view = viewOf(), list = [];
  const cams = specCameras.filter(c => Array.isArray(c.eye_m) && (!c.versions || c.versions.includes(view)));
  const rooms = [...V.editor.current().values()].filter(e => e.type === "room" && !e.removed && e.params?.polygon?.length >= 3);
  const seen = new Set();
  for (const el of rooms) {
    if (SKIP_ROOM.test(el.params.name)) continue;
    let name = plainRoomName(el.params.name);
    if (seen.has(name)) name = `${name} (${el.params.name})`;
    seen.add(name);
    const cam = cams.find(c => { const e = c.eye_m; return Math.abs(e[1] - 1.5 - el.params.floor) < 0.6 && inPoly(el.params.polygon, e[0], e[2]); });
    let pt = cam && feetFromEye(cam.eye_m, el.params.floor), yaw = null, from = "camera " + cam?.id;
    if (pt) yaw = cam.target_m ? yawTo(pt, { x: cam.target_m[0], z: cam.target_m[2] }) : null;
    else { pt = roomStandPoint(el); from = "room"; if (pt) yaw = bestView(pt); }
    if (!pt) { console.info(`house: Go to: no clear standing point in ${el.id}`); continue; }
    list.push({ name, group: el.params.storey === "first" ? "First floor" : "Ground floor", feet: pt, yaw, from, room: el.id });
  }
  /* outside: the road, the front path, the drive (the front court), the porch, the back garden */
  const site = V.sidecar.storeys?.site ?? 0;
  const spawn = rx => (V.sidecar.spawns || []).find(s => rx.test(s.name));
  const walkPt = name => (specWalk?.[view] || specWalk?.after || []).find(([n]) => n === name)?.[1];
  /* the middle of the house front (the viewer frame's z = 0 is the outside face of the main front wall; the front
     path's spawn is on the line of the door); the model's bounds reach into the street, so they are not used */
  const front = { x: spawn(/front path/i)?.position[0] ?? 4.3, z: 0 };
  const out = [
    ["Road", () => { const p = walkPt("street") || [front.x, site, front.z + 20]; return { eye: [p[0], p[1] + 1.5, p[2]], look: front }; }],
    ["Front path", () => { const s = spawn(/front path/i); if (s) return { feet: s.position, yawDeg: s.yawDeg }; const p = walkPt("path"); return p && { eye: [p[0], p[1] + 1.5, p[2]], look: front }; }],
    ["Drive", () => { const p = walkPt("court"); return p && { eye: [p[0], p[1] + 1.5, p[2]] }; }],         // the front court; faces its longest view
    ["Porch", () => { const c = cams.find(c => /porch inside/i.test(c.name)) || cams.find(c => c.id === "C-PORCH");
                      const s = spawn(/porch/i);
                      return c ? { eye: c.eye_m, target: c.target_m, fallback: s } : s && { feet: s.position, yawDeg: s.yawDeg }; }],
    ["Back garden", () => { const c = cams.find(c => c.id === "C-EXT-REAR") || cams.find(c => /back garden/i.test(c.name));
                            if (c) return { eye: c.eye_m, target: c.target_m, ground: true };
                            const s = spawn(/garden/i); return s && { feet: s.position, yawDeg: s.yawDeg }; }],
  ];
  for (const [name, get] of out) {
    let g = null; try { g = get(); } catch (_) {}
    if (!g) continue;
    let pt = null, yaw = null;
    const fromSpawn = s => { const f = walker.floorAt(s.position[0], s.position[1] + 0.3, s.position[2], 1); return f === null ? null : new THREE.Vector3(s.position[0], f, s.position[2]); };
    if (g.eye) {
      const f = walker.floorAt(g.eye[0], g.eye[1], g.eye[2], 4);
      if (f !== null) { pt = new THREE.Vector3(g.eye[0], f, g.eye[2]); if (!walker.free(pt)) pt = feetFromEye(g.eye, f); }
      if (pt) yaw = g.target ? yawTo(pt, { x: g.target[0], z: g.target[2] }) : g.look ? yawTo(pt, g.look) : bestView(pt);
      if (!pt && g.fallback) { pt = fromSpawn(g.fallback); yaw = THREE.MathUtils.degToRad(g.fallback.yawDeg || 0); }
    } else if (g.feet) { pt = fromSpawn({ position: g.feet }); yaw = THREE.MathUtils.degToRad(g.yawDeg || 0); }
    if (pt) list.push({ name, group: "Outside", feet: pt, yaw, from: g.eye ? "spec" : "spawn" });
  }
  const order = { Outside: 0, "Ground floor": 1, "First floor": 2 };
  list.sort((a, b) => order[a.group] - order[b.group]);
  placesCache = { key: ck, list };
  perf.note({ event: "go to places", version: V.def.id, view, n: list.length, ms: Math.round(performance.now() - t0) });
  fillGotoSelect();
  return list;
}
function goToPlace(pl) {
  if (!pl) return;
  gotoMenu.close();
  teleportTo(pl.feet, pl.yaw, "go to");
  toast(`${pl.name}${pl.group === "Outside" ? "" : ` · ${pl.group.toLowerCase()}`}`);
}
function fillGotoSelect() {
  const sel = $("baGoto");
  if (!sel || !placesCache) return;
  sel.textContent = "";
  sel.add(new Option("Go to…", ""));
  let og = null;
  placesCache.list.forEach((pl, i) => {
    if (!og || og.label !== pl.group) { og = document.createElement("optgroup"); og.label = pl.group; sel.appendChild(og); }
    og.appendChild(new Option(pl.name, String(i)));
  });
}
const gotoMenu = (() => {
  const W = 1024, Hc = 1024, COLS = 3, BW = 300, BH = 74, GX = 14, X0 = 34;
  const cv = document.createElement("canvas"); cv.width = W; cv.height = Hc;
  const c = cv.getContext("2d");
  const tex = new THREE.CanvasTexture(cv); tex.colorSpace = THREE.SRGBColorSpace; tex.generateMipmaps = false; tex.minFilter = THREE.LinearFilter;
  const PWm = 0.56;
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(PWm, PWm * Hc / W),
    new THREE.MeshBasicMaterial({ map: tex, transparent: true, toneMapped: false, depthTest: false }));
  mesh.renderOrder = 1010; mesh.visible = false;
  scene.add(mesh);
  let boxes = [], hov = -1, list = [], open = false, used = 0;
  function draw() {
    c.clearRect(0, 0, W, Hc);
    c.fillStyle = "rgba(14,16,15,0.95)"; c.beginPath(); c.roundRect(4, 4, W - 8, used - 8, 30); c.fill();
    c.textBaseline = "middle"; c.textAlign = "left";
    c.fillStyle = "#f6f5ef"; c.font = "700 46px system-ui, sans-serif"; c.fillText("Go to", X0, 56);
    c.fillStyle = "#b9bcb2"; c.font = "28px system-ui, sans-serif"; c.textAlign = "right";
    c.fillText(afterShown() ? "After · the finished house" : "Before · today", W - X0, 56);
    for (const b of boxes) {
      if (b.head) { c.textAlign = "left"; c.fillStyle = "#f2d36b"; c.font = "700 32px system-ui, sans-serif"; c.fillText(b.head, X0, b.y + 22); continue; }
      const on = b.i === hov;
      c.fillStyle = on ? "#f2d36b" : "rgba(255,255,255,0.11)";
      c.beginPath(); c.roundRect(b.x, b.y, b.w, b.h, 16); c.fill();
      c.fillStyle = on ? "#111" : "#f4f3ee"; c.textAlign = "center"; c.font = "600 34px system-ui, sans-serif";
      let t = b.label; while (c.measureText(t).width > b.w - 20 && t.length > 4) t = t.slice(0, -2) + "…";
      c.fillText(t, b.x + b.w / 2, b.y + b.h / 2 + 2);
    }
    tex.needsUpdate = true;
  }
  function layout() {
    list = places();
    boxes = []; let y = 100, group = null, col = 0;
    list.forEach((pl, i) => {
      if (pl.group !== group) { if (group !== null) y += BH + GX; group = pl.group; col = 0; boxes.push({ head: group, y }); y += 48; }
      else if (col === COLS) { col = 0; y += BH + GX; }
      boxes.push({ i, label: pl.name, x: X0 + col * (BW + GX), y, w: BW, h: BH });
      col++;
    });
    if (!list.length) boxes.push({ head: "No places found in this version", y });
    used = Math.min(Hc, y + BH + 34);
  }
  function place() {
    const head = camera.getWorldPosition(new THREE.Vector3());
    const f = camera.getWorldDirection(new THREE.Vector3()).setY(0);
    if (f.lengthSq() < 1e-6) f.set(0, 0, -1);
    f.normalize();
    mesh.position.set(head.x + f.x * 0.75, head.y - 0.12, head.z + f.z * 0.75);
    mesh.lookAt(head.x, head.y - 0.05, head.z);
    /* the empty canvas below the last row is not part of the panel */
    mesh.updateMatrixWorld(true);
  }
  const at = uv => { const x = uv.x * W, y = (1 - uv.y) * Hc; return boxes.find(b => !b.head && x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h)?.i ?? -1; };
  return {
    mesh,
    get isOpen() { return open; },
    get list() { return list; },
    open() { layout(); hov = -1; draw(); if (inVR()) { place(); mesh.visible = true; } open = true; perf.tag("go to menu"); baPanel.userData.draw(); },
    close() { if (!open) return; open = false; mesh.visible = false; baPanel.userData.draw(); },
    toggle() { this.isOpen ? this.close() : this.open(); },
    /* the right laser: returns the hit distance when it is on the panel */
    ray(raycaster, tDown) {
      if (!open || !mesh.visible) return null;
      const h = raycaster.intersectObject(mesh, false)[0];
      if (!h || (1 - h.uv.y) * Hc > used) { if (hov !== -1) { hov = -1; draw(); } return null; }
      const i = at(h.uv);
      if (i !== hov) { hov = i; draw(); }
      if (tDown && i >= 0) goToPlace(list[i]);
      return h.distance;
    },
    /* the world point of place i (tests) */
    point(i) { const b = boxes.find(b => b.i === i); mesh.updateMatrixWorld(true); return b && mesh.localToWorld(new THREE.Vector3(((b.x + b.w / 2) / W - 0.5) * PWm, (0.5 - (b.y + b.h / 2) / Hc) * PWm, 0)); },
  };
})();

/* ------------------------------------------------------------------ *
 *  Marking (review mode only; Jack, 1 Nov: "a mode for me that has the
 *  same functions as the customer walkthrough but also has the marking
 *  tool we made"). src/marks.js on the house: the house BVH is the
 *  surface (walls, floors, ceilings, fittings, the garden), each mark
 *  carries the version, Before / After, the stage, the elements it lay
 *  on and the room, and goes to assets/sites/<site>/marks.json through
 *  POST /marks (tools/https-serve.py). Marks of the other version stay
 *  in the file but are hidden.
 * ------------------------------------------------------------------ */
const safeSurface = s => String(s || "surface").replace(/[^A-Za-z0-9_. -]/g, "_").slice(0, 80) || "surface";
const r3v = v => v.toArray().map(x => Math.round(x * 1000) / 1000);
let markCardShown = false;
const marks = MODE.marks ? createMarks({
  scene, camera, renderer, siteKey: SITE, inXR: inVR, seeThrough: false, tagField: "parts", lockAim: true,
  hint: { draw: "Trigger draw · X kind · Y undo · Mark on the wrist: done", note: "Trigger types · hold A to talk · Delete removes it" },
  raycast(ray, far) {
    const h = pickRay(ray);
    if (!h || h.distance > far) return null;
    const p = partOf(h);
    return { point: h.point, normal: h.normal, surface: safeSurface(p?.materialName || p?.group), tag: p?.name ?? null };
  },
  meta: () => ({
    version: V?.def.id || null, version_name: V?.def.name || null, view: viewOf(), stage: stageIndex(stageValue),
    stage_name: V ? stageName(stageIndex(stageValue)) : null, mode: MODE.key,
    camera: r3v(camera.getWorldPosition(new THREE.Vector3())),
  }),
  /* the parts the stroke lay on (most first) -> their elements, the room it was drawn in, the storey, plain words */
  annotate(s) {
    const byName = new Map(V.model.parts.map(p => [p.name, p]));
    const parts = (s.extra?.parts || []).map(n => byName.get(n)).filter(Boolean);
    const p0 = parts[0];
    const mid = s.closed ? s.pts.reduce((a, q) => a.add(q), new THREE.Vector3()).divideScalar(s.pts.length) : s.pts[Math.floor(s.pts.length / 2)].clone();
    const n = s.nrm.reduce((a, q) => a.add(q), new THREE.Vector3());
    if (n.lengthSq() > 1e-6) mid.addScaledVector(n.normalize(), 0.3);           // off the wall, into the room it was drawn from
    /* the room the mark is in; a stroke over a stair or across a doorway falls back to the room you stood in */
    const eye = s.extra?.camera;
    const room = V.model.roomAt(mid.x, mid.y + 0.05, mid.z) || V.model.roomAt(mid.x, mid.y - 1.2, mid.z)
      || (eye ? V.model.roomAt(eye[0], eye[1] - 1.0, eye[2]) : null);
    return {
      elements: [...new Set(parts.map(p => p.element).filter(Boolean))].slice(0, 12),
      room: room ? plainRoomName(room.params.name) : null, storey: room?.params.storey || p0?.storey || null,
      element_label: p0 ? (p0.ud.label || p0.ud.plain_label || elOf(p0)?.meta?.plain_label || PLAIN_GROUP[p0.group] || p0.group || null) : null,
    };
  },
  visible: s => !s.extra?.version || !V || s.extra.version === V.def.id,
  onActive: on => { if (on) markModeOn(); },
  onChange: () => { marksListDirty = true; baPanel.userData.draw(); },
}) : null;
function markModeOn() {
  gotoMenu.close(); setHover(null); trigRing.visible = false;
  if (!inVR() && !walk) setWalk(true);
  $("baMark")?.setAttribute("aria-pressed", "true");
  if (inVR() && !markCardShown) {
    markCardShown = true;
    showCard("Mark", ["Hold the trigger and sweep across any wall, floor, ceiling, fitting or the garden; end near the start for a shape (its area shows).",
      "A note opens: type with the trigger, or hold A and talk. X: Correction / Proposal. Y: undo. Point at a label + trigger to edit or Delete.",
      "Teleport and doors are off while marking; Mark on the wrist again ends it."], null, 14);
  }
}
let marksListDirty = true;
function renderMarksList() {
  marksListDirty = false;
  const box = $("marksPanel");
  if (!box || !marks) return;
  const on = marks.active && !inVR();
  box.hidden = !on;
  $("baMark")?.setAttribute("aria-pressed", String(marks.active));
  if (!on) return;
  const here = marks.strokes.filter(s => marks.isShown(s)), other = marks.strokes.length - here.length;
  box.querySelector("[data-head]").textContent = `${here.length} mark${here.length === 1 ? "" : "s"} · ${V?.def.name || ""}${other ? ` · ${other} on the other version` : ""}`;
  box.querySelector("[data-status]").textContent = marks.status || "";
  const ul = box.querySelector("ol");
  ul.textContent = "";
  if (!here.length) { const li = document.createElement("li"); li.className = "empty"; li.style.borderLeftColor = "transparent"; li.textContent = "No marks on this version yet: drag across a wall, floor, ceiling or the garden to draw one."; ul.appendChild(li); }
  for (const s of here.slice().reverse()) {
    const li = document.createElement("li");
    li.style.setProperty("--k", MARK_KINDS[s.kind].css);
    const x = s.extra || {};
    li.innerHTML = `<div class="mt"><b></b><span class="meta"></span></div><p></p><div class="mb"><button data-a="note">Note</button><button data-a="go">Look</button><button data-a="del" class="danger">Delete</button></div>`;
    li.querySelector("b").textContent = `${MARK_KINDS[s.kind].label} · ${s.closed ? `${s.area.toFixed(1)} m² · ` : ""}${s.length.toFixed(1)} m`;
    li.querySelector(".meta").textContent = [x.room, x.element_label && x.element_label.length < 60 ? x.element_label : null, (x.elements || [])[0]].filter(Boolean).join(" · ");
    li.querySelector("p").textContent = s.note || (s.note_status === "awaiting transcription" ? "voice note · transcribing…" : "no note yet");
    li.querySelector("[data-a=note]").addEventListener("click", () => marks.openNote(s));
    li.querySelector("[data-a=go]").addEventListener("click", () => lookAtMark(s));
    li.querySelector("[data-a=del]").addEventListener("click", () => marks.remove(s));
    ul.appendChild(li);
  }
}
/* a screen: stand 2.2 m back from a mark along its surface normal and look at it */
function lookAtMark(s) {
  const c = s.pts.reduce((a, q) => a.add(q), new THREE.Vector3()).divideScalar(s.pts.length);
  const n = s.nrm.reduce((a, q) => a.add(q), new THREE.Vector3()).normalize();
  const flat = new THREE.Vector3(n.x, 0, n.z);
  const back = flat.lengthSq() > 0.05 ? flat.normalize() : new THREE.Vector3(Math.sin(yawPitch.yaw), 0, Math.cos(yawPitch.yaw));
  const at = c.clone().addScaledVector(back, 2.2);
  const f = walker.floorAt(at.x, c.y + 0.5, at.z, 4);
  const to = new THREE.Vector3(at.x, f ?? c.y, at.z);
  teleportTo(to, yawTo(to, c));
  const eyeY = to.y + (inVR() ? 1.5 : EYE);
  if (!inVR()) yawPitch.pitch = Math.max(-1.2, Math.min(1.2, Math.atan2(c.y - eyeY, to.distanceTo(new THREE.Vector3(c.x, to.y, c.z)))));
}
/* Before = the house as it is today (the as-built version; Jack, 1 Nov: "Today, as it really is"), falling back to the
   proposal's first stage when a site has no as-built version; After = the proposal's last stage (finished, with the garden) */
async function beforeAfter(after) {
  const today = !after && manifest.as_built_now;
  const want = today ? manifest.as_built_now : lastProposal;
  if (want && V?.def.id !== want) await useVersion(want);
  if (inVR()) { fade.black(); fade.to(0, 0.5); }
  playing = false; tween = null;
  setStage(after || today ? stageN : 1, true);
  $("baBefore").setAttribute("aria-pressed", String(!after)); $("baAfter").setAttribute("aria-pressed", String(after));
  baPanel.userData.draw();
  if (!inVR()) toast(after ? "After: the finished extension and the garden" : manifest.as_built_now ? "Before: your house as it is today" : "Before: the house before the works");
}
const card = createCard();
scene.add(card.mesh);
let cardUntil = 0;
function showCard(title, lines, frac = null, seconds = 0) {
  card.show(title, lines, frac);
  const head = camera.getWorldPosition(new THREE.Vector3());
  const fwd = camera.getWorldDirection(new THREE.Vector3()).setY(0);
  if (fwd.lengthSq() < 1e-6) fwd.set(0, 0, -1);
  card.mesh.position.copy(head).addScaledVector(fwd.normalize(), 1.3).add(new THREE.Vector3(0, -0.1, 0));
  card.mesh.lookAt(head);
  cardUntil = seconds ? performance.now() + seconds * 1000 : 0;
}
/* the button map (README "Controls", Jack's row 159): RIGHT trigger picks / presses / opens a door, A / B stages,
   right grip HELD = fly steered by the right stick (let go = hover), right stick otherwise turns (left / right) and
   teleports (push forward, release), right stick click = frame HUD; LEFT: grip = land (eased down to the floor
   beneath), Y minimises / restores the board, X pins it, left stick walks (on the air while hovering; flips the
   board's tabs while you look at it), left stick click = clear the tape while measuring, else the board's next page */
const heightLine = where => `Height set to ${ftInWords(personHeight)}; change it under Height${where}.`;
const howTo = () => SIMPLE
  ? [heightLine(" on your left wrist (−1 in / +1 in)"),
     `LEFT WRIST (point the right controller, trigger): Before | After | Height | No doors | Furniture | Go to | Fast | Turn | Comfort${MODE.marks ? " | Mark" : ""}. B / A: Before / After.`,
     "TRIGGER on a floor: jump there; on a door: open it. Left stick walks, right stick turns smoothly (Turn: snap). Hold RIGHT grip + right stick to fly; LEFT grip lands."]
  : [`${heightLine(" (Board → Tools)")} LEFT wrist up for the board (X pins, Y minimises). RIGHT controller + trigger picks: the board keeps it.`,
     "A / B: next / previous stage. Left stick walks, right stick turns; push it forward to teleport. Trigger on a door opens it.",
     "FLY: hold the RIGHT grip and steer with the right stick (point up to climb, push harder = faster); let go to hover; LEFT grip lands. Right stick click: frame HUD."];
const controllers = [renderer.xr.getController(0), renderer.xr.getController(1)];
const hands = { left: null, right: null };
const laser = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(0, 0, -1)]),
  new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.7, toneMapped: false }));
laser.visible = false;
/* where the laser lands: a small dot that keeps its apparent size */
const laserDot = new THREE.Mesh(new THREE.SphereGeometry(0.012, 12, 8), new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, toneMapped: false, transparent: true, opacity: 0.9 }));
laserDot.renderOrder = 993; laserDot.visible = false;
scene.add(laserDot);
const tpRing = new THREE.Mesh(new THREE.RingGeometry(0.18, 0.24, 40).rotateX(-Math.PI / 2),
  new THREE.MeshBasicMaterial({ color: 0x7aa86a, transparent: true, opacity: 0.9, toneMapped: false, depthTest: false }));
tpRing.renderOrder = 970; tpRing.visible = false;
scene.add(tpRing);
function attachHand(c, handedness, source) {
  c.userData.hand = handedness; c.userData.source = source;
  hands[handedness] = c;
  if (handedness === "left") { c.add(vrBoard.mesh); c.add(wristTab); c.add(baPanel); }
  if (handedness === "right") { c.add(laser); marks?.attachHint(c); }
}
controllers.forEach(c => {
  player.add(c);
  c.addEventListener("connected", e => attachHand(c, e.data.handedness, e.data));
  c.addEventListener("disconnected", () => { hands[c.userData.hand] = null; });
});

const btnWas = {};
const pressed = (k, now) => { const p = now && !btnWas[k]; btnWas[k] = now; return p; };
let boardPinned = false, dragScrub = false, snapLatch = false, tabLatch = false, tpAim = null, speedNow = 0;
let autoHeightAt = 0, talkA = false;          // the Height check due at the start of a session; A held to talk on a mark's note
const _q = new THREE.Quaternion(), _ray = new THREE.Ray();
const boardRaycaster = new THREE.Raycaster();

function controllerRay(c) {
  c.getWorldPosition(_ray.origin);
  _ray.direction.set(0, 0, -1).applyQuaternion(c.getWorldQuaternion(_q));
  return _ray;
}
function headRay() {
  camera.getWorldPosition(_ray.origin);
  camera.getWorldDirection(_ray.direction);
  return _ray;
}
function boardFacing() {
  if (!hands.left) return false;
  const bp = vrBoard.mesh.getWorldPosition(new THREE.Vector3()), hp = camera.getWorldPosition(new THREE.Vector3());
  const n = new THREE.Vector3(0, 0, 1).applyQuaternion(vrBoard.mesh.getWorldQuaternion(_q));
  return n.dot(hp.sub(bp).normalize()) > 0.45;            // turned towards you, like reading a clipboard
}
function setBoardMin(on) {
  boardMin = on;
  if (on) { vrBoard.setCursor(null); boardPinned = false; }
  else refreshBoard();                                     // rebuilt on the next frames (it was not kept current while minimised)
  hapticPulse([hands.left], 0.3, 20);
}
const boardState = () => boardMin ? "minimised" : vrBoard.mesh.visible ? (boardPinned ? "pinned" : "raised") : "down";

/* the feet under the head (the headset's own height is the eye; the rig's y is the floor) */
const feetUnderHead = () => { const h = camera.getWorldPosition(new THREE.Vector3()); return new THREE.Vector3(h.x, player.position.y - rigLift(), h.z); };

function vrFrame(dt, now) {
  const R = hands.right, L = hands.left;
  const rb = R?.userData.source?.gamepad?.buttons || [], lb = L?.userData.source?.gamepad?.buttons || [];
  const ra = R?.userData.source?.gamepad?.axes || [], la = L?.userData.source?.gamepad?.axes || [];
  const stick = a => a.length >= 4 ? [a[2], a[3]] : [a[0] || 0, a[1] || 0];
  const dead = v => Math.abs(v) < 0.15 ? 0 : (v - Math.sign(v) * 0.15) / 0.85;

  const raised = !SIMPLE && !boardMin && (boardPinned || boardFacing());
  vrBoard.mesh.material.opacity += ((raised ? 1 : 0) - vrBoard.mesh.material.opacity) * 0.25;
  vrBoard.mesh.visible = !!L && vrBoard.mesh.material.opacity > 0.03;
  wristTab.visible = !SIMPLE && !!L && boardMin;
  baPanel.visible = SIMPLE && !!L;
  if (vrBoard.mesh.visible) perf.tag("board open");
  /* the person's height (4 ft by default, Jack 1 Nov) applied once the head pose has arrived: no button needed */
  if (autoHeightAt && now > autoHeightAt && rawEye() > 0.3) { autoHeightAt = 0; heightOffer = false; heightCheck({ auto: true }); }
  // looking at the board? then the left stick flips its tabs instead of walking
  let lookingAtBoard = false;
  if (vrBoard.mesh.visible) { boardRaycaster.ray.copy(headRay()); lookingAtBoard = boardRaycaster.intersectObject(vrBoard.mesh, false).length > 0; }

  // buttons: A next stage, B previous, Y minimise / restore the board, X pin it, left grip LANDS (from flying or
  // hovering), left stick click clears the tape while measuring (else the board's next page), right stick click the
  // frame HUD; the right grip (held) flies, steered by the right stick (Jack, row 159)
  if (SIMPLE) {                                     // homeowners: A sets the height while offered, then A / B = After / Before
    const aNow = !!rb[4]?.pressed;
    if (marks && (marks.noteOpen || talkA)) {        // review: a mark's note is open, so A is hold-to-talk
      if (aNow && !btnWas.a) { marks.talk(true); talkA = true; hapticPulse([R], 0.5, 30); }
      else if (!aNow && btnWas.a && talkA) { marks.talk(false); talkA = false; }
      btnWas.a = aNow;
    } else if (pressed("a", aNow)) { if (heightOffer) { heightOffer = false; card.hide(); cardUntil = 0; heightCheck(); } else beforeAfter(true); hapticPulse([R], 0.5, 30); }
    if (pressed("b", !!rb[5]?.pressed)) { beforeAfter(false); hapticPulse([R], 0.5, 30); }
    if (marks?.active) {                              // review, marking: X = Correction / Proposal, Y = undo the last mark
      if (pressed("x", !!lb[4]?.pressed)) { marks.cycleKind(); baPanel.userData.draw(); hapticPulse([L], 0.35, 20); }
      if (pressed("y", !!lb[5]?.pressed)) { marks.undo(); hapticPulse([L], 0.5, 40); }
    }
  } else {
  if (pressed("a", !!rb[4]?.pressed)) { nextStage(); hapticPulse([R], 0.5, 30); }
  if (pressed("b", !!rb[5]?.pressed)) { prevStage(); hapticPulse([R], 0.5, 30); }
  }
  if (!SIMPLE && pressed("y", !!lb[5]?.pressed)) setBoardMin(!boardMin);
  if (!SIMPLE && pressed("x", !!lb[4]?.pressed)) { if (boardMin) setBoardMin(false); boardPinned = !boardPinned; hapticPulse([L], 0.3, 20); }
  if (pressed("lg", !!lb[1]?.pressed) && (flying || hovering)) { flying = hovering = false; startLanding(feetUnderHead()); hapticPulse([L], 0.4, 30); }
  if (pressed("ls", !!lb[3]?.pressed)) {
    if ((tool === "measure" || tool === "addwall") && (measure.count || measure.pending)) { measure.clear(); hapticPulse([L], 0.3, 20); }
    else vrBoard.nextPage();
  }
  if (pressed("rs", !!rb[3]?.pressed)) { perf.toggle(); hapticPulse([R], 0.3, 20); refreshBoard(); }
  const grip = !!R && !!rb[1]?.pressed;

  const [rx, ry] = stick(ra).map(dead);
  // right stick left / right: turn (not while the grip steers a flight). Smooth: the push sets the speed (75 deg/s
  // full), reached and let go of over TURN.ease s; snap: 30 deg steps (builder / inspector / architect, or Turn: snap)
  if (turnMode === "smooth") {
    const want = !grip && Math.abs(ry) < 0.6 ? -rx * TURN.rate : 0;
    const acc = TURN.rate / TURN.ease * dt;
    turnVel += Math.max(-acc, Math.min(acc, want - turnVel));
    if (Math.abs(turnVel) < 1e-3 && !want) turnVel = 0;
    if (turnVel) rotateAroundHead(turnVel * dt);
  } else if (!grip && Math.abs(rx) > 0.65 && Math.abs(ry) < 0.5) {
    if (!snapLatch) { rotateAroundHead(-Math.sign(rx) * Math.PI / 6); snapLatch = true; hapticPulse([R], 0.3, 15); }
  } else if (Math.abs(rx) < 0.3) snapLatch = false;

  speedNow = Math.abs(turnVel) / TURN.rate;
  if (grip) {
    /* fly: the right stick steers while the grip is held. Forward / back go along where the right controller points
       (its pitch too: point up and push forward to climb), left / right strafe level, and the harder you push the
       faster (1.5 up to 10 m/s). No collision. Let go of the grip and you HOVER where you are; the left grip lands. */
    if (!flying) { flying = true; hovering = false; landing = null; tpAim = null; tpRing.visible = false; perf.tag("fly"); }
    const mag = Math.min(1, Math.hypot(rx, ry));
    flySpeed = mag > 0 ? FLY.base + (FLY.max - FLY.base) * mag * mag : 0;
    if (mag > 0) {
      const fwd = controllerRay(R).direction.clone();
      const side = new THREE.Vector3(-fwd.z, 0, fwd.x);
      if (side.lengthSq() < 1e-6) side.set(1, 0, 0);
      const v = fwd.multiplyScalar(-ry).addScaledVector(side.normalize(), rx);
      if (v.lengthSq() > 1e-9) player.position.addScaledVector(v.normalize(), (FLY.base + (FLY.max - FLY.base) * mag * mag) * dt);
      speedNow = Math.max(speedNow, 1);
    }
  } else if (flying) { flying = false; hovering = true; }   // let go: hold the position (Jack: no easing down)
  if (landing) {
    const f = feetUnderHead(), before = f.clone();
    stepLanding(dt, f);
    player.position.x += f.x - before.x; player.position.z += f.z - before.z; player.position.y = f.y + rigLift();
  }
  const free = !flying && !hovering && !landing;
  watchEyeHeight(now); judgeXrFps(now);

  // right stick forward: aim a teleport, release to go (from a hover too: it lands you there)
  if (!grip && !landing && R && ry < -0.6) {
    const h = V.bvh.raycast(controllerRay(R), 25, V.model.masks.solid, null);
    tpAim = h && h.normal.y > 0.7 ? h.point.clone() : null;
    tpRing.visible = !!tpAim;
    if (tpAim) tpRing.position.copy(tpAim).add(new THREE.Vector3(0, 0.02, 0));
  } else if (tpAim) {
    const head = camera.getWorldPosition(new THREE.Vector3());
    fade.black(); fade.to(0, 0.35);
    player.position.x += tpAim.x - head.x; player.position.z += tpAim.z - head.z; player.position.y = tpAim.y + rigLift();
    tpAim = null; tpRing.visible = false; hovering = false;
  }

  // left stick: with the board raised and looked at, left / right flips tabs; otherwise it walks
  const [lx, ly] = stick(la).map(dead);
  if (raised && lookingAtBoard) {
    if (Math.abs(lx) > 0.7) {
      if (!tabLatch) { const t = MODE.tabs; boardTab = t[(t.indexOf(boardTab) + (lx > 0 ? 1 : t.length - 1)) % t.length]; vrBoard.resetPage(); refreshBoard(); tabLatch = true; hapticPulse([L], 0.25, 15); }
    } else if (Math.abs(lx) < 0.3) tabLatch = false;
  } else if ((free || (hovering && !landing)) && (lx || ly)) {
    const fwd = camera.getWorldDirection(new THREE.Vector3()).setY(0).normalize();
    const right = new THREE.Vector3(-fwd.z, 0, fwd.x);
    const mv = new THREE.Vector3().addScaledVector(fwd, -ly).addScaledVector(right, lx);
    if (mv.lengthSq() > 1) mv.normalize();
    speedNow = Math.max(speedNow, mv.length() * (fastWalk ? 1.25 : 1));
    walkBoost = fastWalk ? Math.min(1, walkBoost + dt / FAST.ramp) : 0;     // Fast eases in; letting go stops at once
    const sp = vrWalkSpeed();
    if (hovering) player.position.addScaledVector(mv, sp * dt);   // hovering: walk on the air at that height
    else {
      const f = feetUnderHead(), before = f.clone();
      walker.move(f, mv.multiplyScalar(sp * dt));
      player.position.x += f.x - before.x; player.position.z += f.z - before.z;
    }
  } else walkBoost = 0;
  if (free) {   // floor under the head: step up the slab and the stair, never through the floor (walk.js)
    const f = feetUnderHead();
    walker.settle(f, dt);
    player.position.y = f.y + rigLift();
  }

  // the right laser: the board first, then its minimised tab, then the house
  laser.visible = false; laserDot.visible = false;
  if (!R) { setHover(null); return; }
  laser.visible = true;
  const trig = !!rb[0]?.pressed;
  const tDown = pressed("trig", trig);
  if (card.mesh.visible && !loadingNow && (tDown || (cardUntil && now > cardUntil))) { card.hide(); cardUntil = 0; heightOffer = false; if (tDown && !marks?.active) { marks?.updateXR(null, trig); return; } }   // marking: the first pull already draws
  laserDot.material.color.setHex(0xffffff);
  trigRing.visible = false;
  if (baPanel.visible && !marks?.drawing) {          // homeowners / review: the wrist panel
    boardRaycaster.ray.copy(controllerRay(R));
    const ph = boardRaycaster.intersectObject(baPanel, false)[0];
    baPanel.userData.hover(ph ? ph.uv : null);
    if (ph) {
      setHover(null); laser.scale.z = ph.distance;
      if (tDown) { baPanel.userData.press(ph.uv); hapticPulse([R], 0.4, 20); }
      marks?.updateXR(null, trig);                      // the trigger was the panel's: no stroke starts from it
      return;
    }
  }
  if (gotoMenu.isOpen) {                              // Go to: point at a place and pull the trigger; the trigger elsewhere closes it
    boardRaycaster.ray.copy(controllerRay(R));
    const d = gotoMenu.ray(boardRaycaster, tDown);
    setHover(null);
    if (d !== null) { laser.scale.z = d; if (tDown) hapticPulse([R], 0.4, 25); return; }
    if (tDown) { gotoMenu.close(); hapticPulse([R], 0.2, 10); return; }
  }
  if (marks?.active) {                                // review, marking: the trigger draws (src/marks.js has its own ray and cursor)
    laser.visible = false; setHover(null); showHeights(null);
    marks.updateXR(R, trig);
    return;
  }
  if (vrBoard.mesh.visible && vrBoard.mesh.material.opacity > 0.5) {
    boardRaycaster.ray.copy(controllerRay(R));
    const bh = boardRaycaster.intersectObject(vrBoard.mesh, false)[0];
    if (bh) {
      setHover(null); showHeights(null);
      const uv = { x: bh.uv.x, y: 1 - bh.uv.y };
      vrBoard.setCursor(uv);
      laser.scale.z = bh.distance;
      const hit = vrBoard.hit(uv);
      if (tDown && hit?.scrub !== undefined) dragScrub = true;
      if (dragScrub && trig && hit?.scrub !== undefined) { playing = false; tween = null; setStage(1 + hit.scrub * (stageN - 1)); }
      if (!trig) dragScrub = false;
      if (tDown && hit && hit.scrub === undefined) {
        if (hit.tab) { boardTab = hit.tab; vrBoard.resetPage(); }
        else if (hit.page) vrBoard.nextPage();
        else if (hit.minimise) setBoardMin(true);
        else hit.button?.press();
        refreshBoard(); hapticPulse([R], 0.4, 20);
      }
      return;
    }
    vrBoard.setCursor(null);
  }
  if (wristTab.visible) {
    boardRaycaster.ray.copy(controllerRay(R));
    const th = boardRaycaster.intersectObject(wristTab, false)[0];
    wristTab.scale.setScalar(th ? 1.18 : 1);
    if (th) {
      setHover(null); laser.scale.z = th.distance;
      if (tDown) { setBoardMin(false); hapticPulse([R], 0.4, 20); }
      return;
    }
  }
  dragScrub = false;
  const h = pickRay(controllerRay(R));
  laser.scale.z = h ? h.distance : 8;
  if (h) {
    laserDot.position.copy(h.point); laserDot.visible = true;
    laserDot.scale.setScalar(Math.max(0.6, h.distance / 2));
  }
  const reach = h ? Math.max(0.02, h.distance * 0.015) : 0;
  if (SIMPLE) {                                       // homeowners / review: a door opens; a floor or the ground: jump there
    const p = partOf(h), d = p && V.doors?.doorOf(p);
    setHover(d ? p : null);
    const spot = !d && h && !tpAim ? walkableSpot(h) : null;
    if (spot) { trigRing.position.copy(spot).add(new THREE.Vector3(0, 0.02, 0)); trigRing.visible = true; }
    else if (h && !d) laserDot.material.color.setHex(0xff6a5c);      // not a place to stand: the dot is red
    if (tDown) {
      if (d) { toggleDoor(p); hapticPulse([R], 0.4, 25); }
      else if (spot) { teleportTo(spot); trigRing.visible = false; hapticPulse([R], 0.3, 15); }
      else hapticPulse([R], 0.15, 8);                    // refused: a short tick
    }
    return;
  }
  if (tool === "measure" || tool === "addwall") { measure.hover(h, partOf(h), reach); setHover(null); }
  else setHover(partOf(h));
  showHeights(tool === "heights" ? h : null);
  if (tDown) {
    if (tool === "info" || tool === "heights") {
      const p = partOf(h);
      if (!p) setTarget(null);                             // a pick of nothing clears the board
      else { if (V.doors?.doorOf(p)) toggleDoor(p); setTarget(p, h.point, "laser", h); }
      hapticPulse([R], 0.4, 25);
    } else { const m = act(h, reach); if (m?.mm !== undefined) toast(`${m.mm} mm`); hapticPulse([R], 0.5, 25); }
  }
}
function rotateAroundHead(angle) {
  const head = camera.getWorldPosition(new THREE.Vector3());
  const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), angle);
  player.position.sub(head).applyQuaternion(q).add(head);
  player.quaternion.premultiply(q);
}

/* comfort vignette while moving on the stick (stronger for homeowners) */
const vigC = document.createElement("canvas");
vigC.width = vigC.height = 256;
{ const c = vigC.getContext("2d"), g = c.createRadialGradient(128, 128, 44, 128, 128, 128);
  g.addColorStop(0, "rgba(0,0,0,0)"); g.addColorStop(0.5, "rgba(0,0,0,0)"); g.addColorStop(1, "rgba(0,0,0,0.95)");
  c.fillStyle = g; c.fillRect(0, 0, 256, 256); }
const vignette = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 1.5), new THREE.MeshBasicMaterial({
  map: new THREE.CanvasTexture(vigC), transparent: true, opacity: 0, depthTest: false, depthWrite: false, toneMapped: false }));
vignette.position.z = -1; vignette.scale.setScalar(3.2); vignette.renderOrder = 999;
camera.add(vignette);

async function enterVR() {
  if (!navigator.xr) return;
  freeMouse();
  try {
    const session = await navigator.xr.requestSession("immersive-vr", { optionalFeatures: ["local-floor", "bounded-floor", "hand-tracking"] });
    const q = VRQ[vrQuality];
    renderer.xr.setFramebufferScaleFactor(q.scale);         // before setSession: the eye buffer is made with it
    if (renderer.shadowMap.enabled !== q.shadows) { renderer.shadowMap.enabled = q.shadows; sun.castShadow = q.shadows; renderer.shadowMap.needsUpdate = true; }
    leanMaterials(!!q.lean);
    xrFps.since = 0; xrFps.judged = false;
    if (!walk) { const s = spawnDefs().find(s => s.name === MODE.start.spawn) || spawnDefs()[0]; if (s) { feet.fromArray(s.position); yawPitch.yaw = THREE.MathUtils.degToRad(s.yawDeg || 0); } }
    orbit.enabled = false;
    player.position.copy(feet);
    player.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), yawPitch.yaw);
    camera.position.set(0, 0, 0); camera.rotation.set(0, 0, 0);
    await renderer.xr.setSession(session);
    flying = false; hovering = false; landing = null; boardMin = false;
    floorOffset = 0; lowEyeSince = 0; lowEyeWarned = false;
    perf.note({ event: "xr start", reference_space: "local-floor", seated, eye_offset_added: 0, quality: vrQuality, scale: q.scale, shadows: q.shadows, foveation: 1 });
    // the frame budget: no post, one 1024 shadow map that only re-renders when the stage changes
    renderer.xr.setFoveation(1);                            // strongest fixed foveation: the edges of the lens are shaded coarsely
    fade.black(); fade.to(0, 1.2);
    $("start").hidden = true;
    document.body.classList.add("in-vr");
    /* homeowners: the card stays until A sets the height (or the trigger dismisses it) */
    heightOffer = SIMPLE;
    autoHeightAt = performance.now() + 700;                 // 4 ft (or the stored height) applied once the head pose is in
    setTimeout(() => showCard(SIMPLE ? "Welcome" : "How it works", howTo(), null, SIMPLE ? 0 : 16), 900);
    refreshBoard();
    session.addEventListener("end", () => {
      document.body.classList.remove("in-vr");
      perf.hud.visible = false; flying = false; hovering = false; landing = null; autoHeightAt = 0; gotoMenu.close(); marksListDirty = true;
      leanMaterials(false);
      if (!renderer.shadowMap.enabled) { renderer.shadowMap.enabled = true; sun.castShadow = true; renderer.shadowMap.needsUpdate = true; }
      const head = camera.getWorldPosition(new THREE.Vector3());
      feet.set(head.x, player.position.y, head.z);
      player.quaternion.identity();
      walk = false; setWalk(true); refreshBoard();
    });
  } catch (err) {
    $("xrNote").textContent = `Could not start VR: ${err.message}`;
  }
}

/* ------------------------------------------------------------------ *
 *  UI wiring
 * ------------------------------------------------------------------ */
let toastTimer = null;
function toast(text) {
  const t = $("toast");
  t.textContent = text; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 3500);
}
function updateHelp() {
  if (CUST) {
    $("help").textContent = IS_TOUCH ? `Left thumb moves · right thumb looks · tap a door to open it, or the floor to jump there · Go to a room${MODE.marks ? " · Mark, then draw with a finger" : ""}`
      : lockRefused ? `Before / After (B / N) · drag to look around · W A S D or click the ground to walk (G fast, Shift faster) · click a door to open it · F to fly (Q / E down / up) · Go to a room${MODE.marks ? " · M mark" : ""}`
      : `Click the view, then move the mouse to look (Esc frees it) · W A S D walk (G fast, Shift faster) · click: open a door or jump to the floor under the crosshair · F or Space fly (Q / E down / up) · B / N Before / After${MODE.marks ? " · M mark, hold the click to draw" : ""}`;
    $("baHelp").textContent = $("help").textContent;
    return;
  }
  const parts = [];
  if (walk) parts.push(IS_TOUCH ? "drag to look · tap a floor twice to walk there" : lockRefused ? "W A S D walk · drag to look · Shift faster" : "click the view, then move the mouse to look (Esc frees it) · W A S D walk · Shift faster");
  else parts.push(IS_TOUCH ? "drag to turn · pinch to zoom · two fingers to pan" : "drag to turn · right-drag to pan · scroll to zoom");
  parts.push(tool === "measure" ? "click two points to measure · snaps to corners (pink) and edges (blue) · M done"
    : tool === "addwall" ? "click the two ends of the new wall · Esc cancels"
    : (IS_TOUCH ? "tap a part for info" : "click a part: its spec, regs, build notes and plan appear on the board"));
  if (tool === "heights") parts.push("point at a ceiling or beam: its height above the floor and above your eyes");
  if (!IS_TOUCH) parts.push(flying ? "flying: W A S D, Q / E down / up · F lands" : "[ ] stages · Space play · X x-ray · V walk · F fly · O doors · H frame HUD");
  if (section.state.on) parts.push("the slider moves the cut");
  parts.push("VR: left wrist up for the board (Y hides it) · point the right controller + trigger to pick or open a door · A/B stages · hold right grip to fly");
  $("help").textContent = parts.join("  ·  ");
}

$("scrub").addEventListener("input", () => { playing = false; tween = null; updatePlay(); setStage(parseFloat($("scrub").value)); });
$("play").addEventListener("click", togglePlay);
$("prev").addEventListener("click", prevStage);
$("next").addEventListener("click", nextStage);
$("xray").addEventListener("click", () => setXray(!xray));
$("toolMeasure").addEventListener("click", () => setTool(tool === "measure" ? "info" : "measure"));
$("toolHeights").addEventListener("click", () => setTool(tool === "heights" ? "info" : "heights"));
$("doorsAll").addEventListener("click", () => V?.doors && setAllDoors(!V.doors.anyOpen));
$("fly").addEventListener("click", () => setFly(!flying));
$("scaleCue").addEventListener("click", toggleScaleCue);
$("baBefore").addEventListener("click", () => beforeAfter(false));
$("baAfter").addEventListener("click", () => beforeAfter(true));
$("baFly").addEventListener("click", () => { setFly(!flying); $("baFly").setAttribute("aria-pressed", String(flying)); });
$("baFast").addEventListener("click", () => setFastWalk(!fastWalk));
$("baFurnish")?.addEventListener("click", () => setUnfurnished(!unfurnished));
$("baComfort")?.addEventListener("click", () => setComfort(COMFORT[(COMFORT.indexOf(comfort) + 1) % COMFORT.length]));
$("fastWalk").addEventListener("click", () => setFastWalk(!fastWalk));
$("baGoto").addEventListener("change", e => { const pl = placesCache?.list[+e.target.value]; e.target.value = ""; e.target.blur(); if (pl) goToPlace(pl); });
$("baMark").addEventListener("click", () => marks?.toggle());
$("marksDone")?.addEventListener("click", () => marks?.setActive(false));
$("measureClear").addEventListener("click", () => { measure.clear(); $("measureClear").disabled = true; });
$("walk").addEventListener("click", () => setWalk(!walk));
$("sectionSel").addEventListener("change", e => setSection(e.target.value));
$("sectionOffset").addEventListener("input", e => { section.setOffset(parseFloat(e.target.value)); updateOffsetLabel(); });
$("sectionFlip").addEventListener("click", () => section.flip());
for (const b of document.querySelectorAll("[data-storey]")) b.addEventListener("click", () => setStorey(b.dataset.storey, !storeyState[b.dataset.storey]));
$("boardClose").addEventListener("click", () => { setTarget(null); if (boardTab === "tools" || boardTab === "notes") { boardTab = MODE.tabs[0]; refreshBoard(); } });
$("undo").addEventListener("click", () => V.editor.undo());
$("redo").addEventListener("click", () => V.editor.redo());
$("saveEdits").addEventListener("click", downloadEdits);
$("loadEdits").addEventListener("change", async e => {
  const f = e.target.files[0]; if (!f) return;
  try { V.editor.load(JSON.parse(await f.text())); toast(`Loaded ${f.name}`); } catch (err) { toast(`Could not read ${f.name}: ${err.message}`); }
  e.target.value = "";
});
$("resetEdits").addEventListener("click", () => { if (confirm("Drop every edit and go back to the drawn design?")) V.editor.reset(); });
$("rulesSummary").addEventListener("click", () => { $("rules").hidden = !$("rules").hidden; });
$("vr").addEventListener("click", enterVR);
$("versionSel").addEventListener("change", e => useVersion(e.target.value));
$("before").addEventListener("click", () => useVersion(manifest.as_built_now));
$("after").addEventListener("click", () => lastProposal && useVersion(lastProposal));
$("asBuilt").addEventListener("click", toggleAsBuilt);
$("toolsTab").addEventListener("click", () => { boardTab = "tools"; refreshBoard(); });
$("notesTab").addEventListener("click", () => { boardTab = "notes"; refreshBoard(); });
$("startVR").addEventListener("click", enterVR);
$("startDesktop").addEventListener("click", () => { $("start").hidden = true; });
$("spawnSel").addEventListener("change", e => { if (e.target.value) spawnAt(e.target.value); e.target.value = ""; });
$("stageListToggle").addEventListener("click", () => document.body.classList.toggle("list-open"));
$("toGarden").addEventListener("click", () => { spawnAt("Garden"); toast("The new extension is at the back. Use the stages to watch it go up."); });
$("menuToggle").addEventListener("click", () => document.body.classList.toggle("top-open"));
$("stageName").addEventListener("click", () => document.body.classList.toggle("note-open"));

function layoutPanels() {                    // the panels sit under the toolbar, however many rows it wraps to
  document.documentElement.style.setProperty("--top-h", `${Math.round($("top").getBoundingClientRect().bottom + 8)}px`);
}
new ResizeObserver(layoutPanels).observe($("top"));
addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  composer?.setSize(innerWidth, innerHeight);
});

/* ------------------------------------------------------------------ *
 *  Boot
 * ------------------------------------------------------------------ */
async function boot() {
  $("modeLabel").textContent = MODE.label;
  try {
    manifest = await fetchJSON(BASE + "versions.json");
  } catch (err) {
    $("xrNote").textContent = `No house data for "${SITE}" (${err.message}).`;
    return;
  }
  let mats;
  let spec;
  [regs, sheets, mats, spec] = await Promise.all([loadRegs(BASE), fetchJSON(BASE + "sheets.json").catch(() => null), fetchJSON(BASE + "materials.json").catch(() => null),
    /* Go to's named cameras: the site's own spec; a preview copy of a site (<site>-wip / -preview / -fixture) has none, so
       it reads the spec of the site it previews */
    fetchJSON(BASE + (manifest.spec || "spec/spec_v1.json")).catch(() => {
      const m = SITE.match(/^(.+)-(wip|preview|fixture)$/);
      return m ? fetchJSON(`assets/sites/${m[1]}/spec/spec_v1.json`).catch(() => null) : null;
    })]);
  /* Furnished / Unfurnished: the spec's item categories (the fallback for builds without the furnishing extra) */
  specCategory = new Map(Object.values(spec?.versions || {}).flatMap(v => (v.items || []).map(it => [it.id, it.category])));
  specCameras = Array.isArray(spec?.cameras) ? spec.cameras : [];        // Go to: the spec's named cameras (eye_m / target_m, viewer frame)
  specWalk = spec?.walkthrough || null;
  setTiles(mats?.materials);                           // rebuilt walls get the baked walls' UVs
  materialsJson = mats?.materials || null;             // ... and the GLB material their name maps to (glb_material)
  document.title = `${manifest.name} · build stages`;
  $("title").textContent = manifest.name;
  const vs = $("versionSel");
  for (const v of manifest.versions) vs.add(new Option(v.name, v.id));
  $("versions").hidden = manifest.versions.length < 2;
  $("before").hidden = $("after").hidden = !manifest.as_built_now;
  const want = params.get("version");
  lastProposal = manifest.versions.find(v => v.id === (want || manifest.default) && v.kind === "proposal")?.id
    || manifest.versions.find(v => v.kind === "proposal")?.id || null;
  await useVersion(manifest.versions.some(v => v.id === want) ? want : (manifest.default || manifest.versions[0].id));
  for (const s of spawnDefs()) $("spawnSel").add(new Option(s.name, s.name));
  setStage(MODE.start.stage === "last" ? stageN : MODE.start.stage, true);
  overviewDefault();
  if (MODE.start.walk) spawnAt(CUST ? "Front of the house" : MODE.start.spawn);
  if (SIMPLE) { $("baBefore").setAttribute("aria-pressed", String(!afterShown())); $("baAfter").setAttribute("aria-pressed", String(afterShown())); }
  $("baFast").setAttribute("aria-pressed", String(fastWalk)); $("fastWalk").setAttribute("aria-pressed", String(fastWalk));
  comfortButton();
  furnishButtons();
  if (marks) { await marks.load(); marks.refreshVisibility(); }
  setXray(false);
  const lg = $("legend");
  for (const c of Object.values(XRAY)) {
    const s = document.createElement("span");
    s.innerHTML = `<i style="background:#${c.hex.toString(16).padStart(6, "0")}"></i>`;
    s.append(c.label);
    lg.appendChild(s);
  }
  updateHelp();
  $("startDesktop").disabled = false;
  console.info(`house: ${V.model.parts.length} parts · house ${V.model.drawCalls()} batches + setting ${V.model.settingCalls()} · ${V.bvh.triangles} ray triangles · mode ${MODE.key}`);
  /* make the Before / After switch instant on a laptop; the Quest loads a version only when asked (memory) */
  if (!LITE && manifest.as_built_now && manifest.as_built_now !== V.def.id && !params.get("test") && !params.get("capture")) loadVersion(manifest.as_built_now, true).catch(err => console.warn(err));
  /* the headset's own panels: their shaders compiled and textures on the GPU now, not on the frame they first show */
  for (const o of [vrBoard.mesh, wristTab, card.mesh, perf.hud, laserDot, hover, baPanel, gotoMenu.mesh, trigRing]) { renderer.compile(o, camera, scene); o.traverse(m => m.material?.map && renderer.initTexture(m.material.map)); }
  dispatchEvent(new Event("house-ready"));
  /* ?test=walk: climb and descend every stair, and walk each storey's rooms, in every version and stage */
  if (params.get("test") === "walk") import("./walktest.js?v=h15").then(m => m.runWalkTest(window.__house)).catch(err => console.error("walk test", err));
}
if (navigator.xr) {
  navigator.xr.isSessionSupported("immersive-vr").then(ok => {
    $("startVR").disabled = !ok; $("vr").hidden = !ok;
    if (!ok) $("xrNote").textContent = "No headset here: open the same link in the Quest browser (https) to walk it in VR.";
  }).catch(() => {});
} else { $("startVR").disabled = true; $("vr").hidden = true; $("xrNote").textContent = "No WebXR in this browser. On the Quest, open https://<mac-ip>:8443/house.html"; }
boot();

/* ------------------------------------------------------------------ *
 *  The simulated headset (tests only): two fake controllers with
 *  xr-standard gamepads drive vrFrame exactly as the Quest's do; the
 *  camera stands at a fixed eye height in the rig, as local-floor
 *  puts it. sim.wrist(true) turns the left wrist up (the board faces
 *  you), sim.aim(point) points the right laser, sim.press("trigger").
 * ------------------------------------------------------------------ */
const BTN = { trigger: 0, grip: 1, stick: 3, a: 4, x: 4, b: 5, y: 5 };
const sim = {
  eye: 1.74, wristUp: false, aimAt: null, holds: [],
  start(eye = 1.74) {
    if (SIM.on) return;
    sim.eye = eye;
    const pad = () => ({ buttons: [...Array(6)].map(() => ({ pressed: false, value: 0 })), axes: [0, 0, 0, 0] });
    for (const hand of ["left", "right"]) { const c = new THREE.Group(); player.add(c); attachHand(c, hand, { handedness: hand, gamepad: pad() }); }
    if (walk) setWalk(false);
    SIM.on = true; orbit.enabled = false;
    player.position.copy(feet); player.quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), yawPitch.yaw);
    camera.position.set(0, sim.eye, 0); camera.rotation.set(yawPitch.pitch, 0, 0); camera.fov = 90; camera.updateProjectionMatrix();
    document.body.classList.add("in-vr");
    floorOffset = 0; autoHeightAt = performance.now() + 100;    // as a real session: the person's height applied at once
    showCard(SIMPLE ? "Welcome" : "How it works", howTo(), null, SIMPLE ? 0 : 16);   // the same first card as enterVR
    marksListDirty = true;
    refreshBoard();
  },
  /* the world point of a wrist button / a Go to entry (aim the right laser at it) */
  wristPoint: id => baPanel.userData.point(id),
  gotoPoint: i => gotoMenu.point(i),
  pad: hand => hands[hand]?.userData.source.gamepad,
  /* hold a button for n frames (one frame = a press) */
  press(name, hand = ["x", "y"].includes(name) ? "left" : "right", frames = 2) { sim.holds.push({ hand, i: BTN[name], frames }); },
  hold(name, on, hand = name === "grip" ? "right" : "right") { const b = sim.pad(hand).buttons[BTN[name]]; b.pressed = on; b.value = on ? 1 : 0; },
  stick(hand, x, y) { const a = sim.pad(hand).axes; a[2] = x; a[3] = y; },
  wrist(up) { sim.wristUp = up; },
  aim(point) { sim.aimAt = point ? new THREE.Vector3().copy(point) : null; },
  /* the world point of the board at canvas uv (x, y down) */
  boardPoint(u, v) { vrBoard.mesh.updateMatrixWorld(true); return vrBoard.mesh.localToWorld(new THREE.Vector3((u - 0.5) * 0.24, (0.5 - v) * 0.24 * 1440 / 1024, 0)); },
  tabPoint() { wristTab.updateMatrixWorld(true); return wristTab.getWorldPosition(new THREE.Vector3()); },
};
function simPose() {
  const L = hands.left, R = hands.right;
  player.updateMatrixWorld(true);
  const cam = camera.getWorldPosition(new THREE.Vector3()), cq = camera.getWorldQuaternion(new THREE.Quaternion());
  const fwd = new THREE.Vector3(0, 0, -1).applyQuaternion(cq), up = new THREE.Vector3(0, 1, 0).applyQuaternion(cq), right = new THREE.Vector3(1, 0, 0).applyQuaternion(cq);
  const pq = player.getWorldQuaternion(new THREE.Quaternion()).invert();
  const place = (c, pos, q) => { c.position.copy(player.worldToLocal(pos.clone())); c.quaternion.copy(pq).multiply(q); c.updateMatrixWorld(true); };
  if (L) {
    if (sim.wristUp) {         // the board square to the eyes, 38 cm away and a little low and left
      const bq = cq.clone(), bl = vrBoard.mesh;
      const lq = bq.clone().multiply(bl.quaternion.clone().invert());
      const bp = cam.clone().addScaledVector(fwd, 0.38).addScaledVector(up, -0.1).addScaledVector(right, -0.04);
      place(L, bp.sub(bl.position.clone().applyQuaternion(lq)), lq);
    } else {                   // held low in front, pointing ahead, palm down: the board faces the floor, the wrist tab faces up
      const yawQ = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.atan2(-fwd.x, -fwd.z));
      const flat = new THREE.Vector3(fwd.x, 0, fwd.z).normalize(), side = new THREE.Vector3(-flat.z, 0, flat.x);
      place(L, cam.clone().addScaledVector(flat, 0.32).add(new THREE.Vector3(0, -0.5, 0)).addScaledVector(side, -0.16), yawQ);
    }
  }
  if (R) {
    const rp = cam.clone().addScaledVector(right, 0.18).addScaledVector(up, -0.3).addScaledVector(fwd, 0.25);
    const goal = sim.aimAt || rp.clone().addScaledVector(fwd, 5);
    const m = new THREE.Matrix4().lookAt(rp, goal, new THREE.Vector3(0, 1, 0));
    place(R, rp, new THREE.Quaternion().setFromRotationMatrix(m));
  }
  for (const h of sim.holds) { const b = sim.pad(h.hand)?.buttons[h.i]; if (b) { b.pressed = h.frames > 1; b.value = b.pressed ? 1 : 0; } h.frames--; }
  sim.holds = sim.holds.filter(h => h.frames > 0);
}
if (params.get("xrsim")) addEventListener("house-ready", () => sim.start(), { once: true });

/* ------------------------------------------------------------------ *
 *  Loop
 * ------------------------------------------------------------------ */
let renderMs = 0;
/* the screen camera's own motion this frame: a turn or a move fast enough to blur; a jump (teleport, Go to) resets */
const camPrev = { m: new THREE.Matrix4(), has: false };
const _cq0 = new THREE.Quaternion(), _cq1 = new THREE.Quaternion(), _cp0 = new THREE.Vector3(), _cp1 = new THREE.Vector3(), _cs = new THREE.Vector3();
function camMotion(dt) {
  camera.updateMatrixWorld(true);
  if (!camPrev.has) { camPrev.m.copy(camera.matrixWorld); camPrev.has = true; return { fast: false, moving: false }; }
  camPrev.m.decompose(_cp0, _cq0, _cs); camera.matrixWorld.decompose(_cp1, _cq1, _cs);
  camPrev.m.copy(camera.matrixWorld);
  const ang = _cq0.angleTo(_cq1), dist = _cp0.distanceTo(_cp1);
  if (ang > 0.5 || dist > 1.0) { blurPass?.reset(); return { fast: false, moving: false }; }
  const w = ang / Math.max(dt, 1e-3), v = dist / Math.max(dt, 1e-3);
  /* fast: above about 115 deg/s of turning or a 6 m/s flight (looking about and walking stay sharp);
     moving: enough for the screen's vignette when Comfort is vignette */
  return { fast: w > BLUR.turnMin || v > BLUR.flyMin, moving: w > 0.8 || v > 1.0 };
}
let last = performance.now(), workPrev = 0, lookUiTick = 0, deskMoving = false, flySpeed = 0;
renderer.info.autoReset = false;               // the composer renders several passes a frame: count them all, reset once
const SEND_PERF = IS_QUEST || params.has("perf");
function loop(fakeNow) {
  const now = fakeNow ?? performance.now();
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  if (renderer.shadowMap.needsUpdate && renderer.shadowMap.enabled) shadowPasses++;
  perf.frame(now, workPrev, SEND_PERF || renderer.xr.isPresenting);
  renderer.info.reset();
  if (!V) { renderer.render(scene, camera); workPrev = performance.now() - now; return; }
  if (playing) {
    const next = stageValue + dt / 2.6;             // about 2.6 s a stage
    if (next >= stageN) { setStage(stageN); playing = false; updatePlay(); } else setStage(next);
  } else if (tween) {
    tween.t += dt / tween.dur;
    setStage(tween.from + (tween.to - tween.from) * easeOut(clamp01(tween.t)));
    if (tween.t >= 1) tween = null;
  }
  if (stageDirty) applyStageNow();
  else V.cull?.prepare();                      // the wall holes are found once, on the first frame at the last stage (not on the first frame in the headset)
  if (V.doors?.moving) { V.doors.update(dt); perf.tag("doors"); if (hoverPart?.pose) { const h = hoverPart; hoverPart = null; setHover(h); } }
  if (inVR()) { if (SIM.on) simPose(); vrFrame(dt, now); }
  else if (walk) desktopWalk(dt);
  else orbit.update();
  if (target && (playing || tween || target.part.pose)) updateHighlight();
  measure.update(camera);
  if (marks) { marks.update(dt); if (marksListDirty) renderMarksList(); }
  /* mouse-look: the crosshair's colour, the capture hint; a mark's note box needs the mouse back to type and press Save */
  if (!inVR()) {
    if (STICKS && walk) touchLookStep(dt);
    updateCrosshair(dt);
    if (marks?.noteOpen && locked()) freeMouse();
    if ((lookUiTick += dt) > 0.25) { lookUiTick = 0; updateLookUI(); layoutSticks(); }
  }
  /* the board: content on one frame, its canvas on a later one (never both in one frame) */
  if (!flushBoard(now) && inVR()) {
    const t0 = performance.now();
    const step = vrBoard.update(now, vrBoard.mesh.visible, t => renderer.initTexture(t));
    if (step) { const ms = performance.now() - t0; if (ms > 4) perf.tag(`board ${step} ${Math.round(ms)} ms`); }
  }
  fade.update(dt);
  adaptExposure(dt);
  const vt = !inVR() && SIMPLE && comfort === "vignette" && deskMoving ? 0.45
    : inVR() && comfort === "vignette" && speedNow > 0.05 ? (MODE.vr.locomotion === "teleport" && !flying ? 0.75 : 0.5) + (fastWalk && walkBoost > 0.3 && !flying ? 0.1 : 0) : 0;
  vignette.material.opacity += (vt - vignette.material.opacity) * Math.min(1, dt * 8);
  vignette.visible = vignette.material.opacity > 0.01;
  /* the headset draws with no post-processing; the simulated headset does the same, so its pictures match the Quest's
     (the desktop GTAO pass drew the marks' label sprites as black quads in ?xrsim=1; the headset never runs it) */
  /* motion blur (homeowner / review, Comfort: blur): fades in over 0.15 s while you turn or move, out when you stop */
  /* the headset: a near-full smooth turn (or a fast flight); a screen: a fast mouse / thumb turn. Walking never blurs. */
  const deskMove = !inVR() ? camMotion(dt) : null;
  const moving = comfort === "blur" && (inVR() ? Math.abs(turnVel) > BLUR.xrTurnFrac * TURN.rate || (flying && flySpeed > BLUR.flyMin) : deskMove.fast);
  blurFade = Math.max(0, Math.min(1, blurFade + (moving ? 1 : -1) * dt / BLUR.fade));
  deskMoving = !inVR() && deskMove.moving;
  if (renderer.xr.isPresenting || SIM.on || !composer) {
    const t0 = performance.now();
    const blurred = inVR() && blurFade > 0.001 && xrBlur.render(scene, camera, blurFade * BLUR.xrShutter);
    if (!blurred) renderer.render(scene, camera);
    if (inVR()) { xrBlur.track(); if (blurred) perf.tag("motion blur"); }
    renderMs = performance.now() - t0;
    if (renderer.xr.isPresenting) blurGovernor(now, blurred);
  } else {
    if (blurPass) blurPass.amount = blurFade * BLUR.deskShutter;
    composer.render();
  }
  workPrev = performance.now() - now;
}
scene.onBeforeRender = (r, sc, cam) => { V?.cull?.update(cam, r); };      // after xr.updateCamera: the eyes are this frame
renderer.setAnimationLoop(() => loop());

/* a hook for tests from the console; not a user-facing API */
window.__house = {
  THREE, scene, camera, renderer, player, orbit, measure, section, walker, feet, yawPitch, vrBoard, requests, regs: () => regs,
  get V() { return V; }, get stage() { return stageValue; }, get tool() { return tool; }, get target() { return target; },
  get walk() { return walk; }, get xray() { return xray; }, get boardTab() { return boardTab; }, set boardTab(t) { boardTab = t; refreshBoard(); },
  MODE, inspections,
  setStage: v => setStage(v, true), goToStage, useVersion, setSection, setXray, setStorey, setTool, setWalk, spawnAt, toggleAsBuilt,
  pickRay, setTarget, act, editOpening, editRemoveToggle, editMoveWall, editAddOpening, editSwap, sendRequest, markCheck, runRules, screenRay, progress,
  boardContent, shrinkTextures, partFacts, keyStages, establishingSpawn, flushBoard: () => { boardDirty = true; flushBoard(performance.now(), true); },
  /* run n frames by hand (a hidden test page gets no animation frames) */
  step(n = 1, ms = 1000 / 72) { for (let i = 0; i < n; i++) loop(last + ms); },
  heightCheck, heightReset, setPersonHeight, parseHeight, rawEye, passBreakdown, get floorOffset() { return floorOffset; }, get personHeight() { return personHeight; },
  beforeAfter, baPanel, get heightOffer() { return heightOffer; }, SIMPLE,
  marks, gotoMenu, places, goToPlace, teleportTo, walkableSpot, setFastWalk, get fastWalk() { return fastWalk; }, vrWalkSpeed, get walkBoost() { return walkBoost; },
  setTurnMode, setComfort, get turnMode() { return turnMode; }, get comfort() { return comfort; }, get turnVel() { return turnVel; },
  get blurFade() { return blurFade; }, xrBlur, blurGovernor, sticks, touchMove, touchLook, layoutSticks, get locked() { return locked(); }, lockedClick, blurPass: () => blurPass, get renderMs() { return renderMs; }, vignette,
  specCameras: () => specCameras, lookAtMark, get autoHeightAt() { return autoHeightAt; }, howTo, showCard, card,
  sim, hands, perf, heightInfo, get cull() { return V?.cull; }, showHeights, setHover, toggleScaleCue, setFly, setAllDoors, setDoorsHidden, toggleDoor, loadVersion, versions, BODY, inVR, wristTab,
  get flying() { return flying; }, get hovering() { return hovering; }, get landing() { return landing; }, get boardMin() { return boardMin; }, get hoverPart() { return hoverPart; },
  get seated() { return seated; }, get doorsHidden() { return doorsHidden; }, setUnfurnished, get unfurnished() { return unfurnished; }, isLoose, looseCount, baPanel, get stageN() { return stageN; }, manifest: () => manifest, dropVersion,
  stats() { renderer.render(scene, camera); const i = renderer.info.render; return { calls: i.calls, triangles: i.triangles, houseBatches: V.model.drawCalls(), houseBatchesLive: V.model.liveCalls(), settingBatches: V.model.settingCalls(), parts: V.model.parts.length }; },
};

/* ------------------------------------------------------------------ *
 *  The capture harness (?capture=1; PLAN S8, CORRECTIONS-LOG 237).
 *  A hidden browser pane gets no animation frames, so a capture cannot go through the loop: captureAt sets the feet,
 *  sets camera.rotation DIRECTLY (yawPitch alone does nothing without the loop), renders once and returns a JPEG data
 *  URL. tools/review/sweep_driver.js runs the sweep; tools/review/sweep_tools.py rejects a set unless every direction's
 *  hash differs and every eye point is inside its room polygon (or inside the site, outside).
 *  ids:true returns the PART picture of the same view instead: every part flat-coloured with its index + 1 (24-bit),
 *  nothing drawn magenta, no anti-aliasing (an unsmoothed render target), so the machine pass knows exactly which part
 *  (and so which material) every pixel is: raw construction or a hole inside a room. partTable() maps index -> part.
 * ------------------------------------------------------------------ */
if (params.get("capture") === "1") {
  const fnv = s => { let h = 0x811c9dc5; for (let i = 0; i < s.length; i += 7) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0).toString(16); };
  const cap = { w: 0, h: 0, rt: null, cv: null };
  const idMat = new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false, fog: false });
  const _c = new THREE.Color();
  function render(post, w, h) {
    if (cap.w !== w || cap.h !== h) { renderer.setPixelRatio(1); renderer.setSize(w, h, false); composer?.setSize(w, h); cap.w = w; cap.h = h; }
    renderer.shadowMap.needsUpdate = true;
    if (post && composer) { blurPass?.reset(); if (blurPass) blurPass.amount = 0; composer.render(); } else renderer.render(scene, camera);
  }
  function renderIds(w, h) {
    const parts = V.model.parts.filter(p => p.batch), swaps = [];
    for (const p of parts) { const n = p.index + 1; p.batch.setColorAt(p.instanceId, _c.setRGB(((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255, THREE.LinearSRGBColorSpace)); }
    scene.traverse(o => { if ((o.isBatchedMesh || o.isMesh) && o !== sky && o.visible && o.material && !Array.isArray(o.material)) { swaps.push([o, o.material]); o.material = idMat; } });
    if (!cap.rt || cap.rt.width !== w || cap.rt.height !== h) { cap.rt?.dispose(); cap.rt = new THREE.WebGLRenderTarget(w, h, { samples: 0, type: THREE.UnsignedByteType, magFilter: THREE.NearestFilter, minFilter: THREE.NearestFilter }); }
    const bg = scene.background, skyVis = sky.visible, shadows = renderer.shadowMap.enabled, cc = renderer.getClearColor(new THREE.Color()), ca = renderer.getClearAlpha();
    scene.background = null; sky.visible = false; renderer.shadowMap.enabled = false; renderer.setClearColor(0xff00ff, 1);
    renderer.setRenderTarget(cap.rt); renderer.render(scene, camera); renderer.setRenderTarget(null);
    const buf = new Uint8Array(w * h * 4); renderer.readRenderTargetPixels(cap.rt, 0, 0, w, h, buf);
    for (const [o, m] of swaps) o.material = m;
    for (const p of parts) p.batch.setColorAt(p.instanceId, _c.setRGB(1, 1, 1, THREE.LinearSRGBColorSpace));
    scene.background = bg; sky.visible = skyVis; renderer.shadowMap.enabled = shadows; renderer.setClearColor(cc, ca);
    cap.cv ||= document.createElement("canvas"); cap.cv.width = w; cap.cv.height = h;
    const ctx = cap.cv.getContext("2d"), img = ctx.createImageData(w, h);
    for (let y = 0; y < h; y++) img.data.set(buf.subarray((h - 1 - y) * w * 4, (h - y) * w * 4), y * w * 4);
    ctx.putImageData(img, 0, 0);
    return cap.cv.toDataURL("image/png");
  }
  Object.assign(window.__house, {
    furnished(on) { if (on !== undefined) setUnfurnished(!on); return !unfurnished; },
    captureState: () => ({ ready: !!V && sky.visible, sky: sky.visible, version: V?.def.id, parts: V?.model.parts.length, furnished: !unfurnished, stage: stageValue, stageN, walk }),
    /* part index -> [element, material, group, storey, spec_id, label, bbox min x y z, max x y z (cm)] for the machine pass */
    partTable: () => V.model.parts.map(p => [p.index, p.element, p.materialName, p.group, p.storey, p.ud.spec_id || "", String(p.ud.label || p.name || "").slice(0, 60),
      ...[p.bbox.min, p.bbox.max].flatMap(v => [v.x, v.y, v.z].map(n => Math.round(n * 100)))]),
    /* x, z: feet in the house frame (m); y: the floor under them (null: found by a ray from just above the ground); eye: eye height above the feet */
    captureAt({ x, z, y = null, yawDeg = 0, pitchDeg = 0, eye = 1.6, fov = 60, w = 480, h = 270, quality = 0.82, post = false, ids = false } = {}) {
      if (!V) throw new Error("captureAt: no version loaded");
      if (!walk) setWalk(true);
      if (stageDirty) applyStageNow();
      const t0 = performance.now();
      const floor = y ?? walker.floorAt(x, -0.45, z, 4) ?? -0.231;
      feet.set(x, floor, z);
      yawPitch.yaw = THREE.MathUtils.degToRad(yawDeg); yawPitch.pitch = THREE.MathUtils.degToRad(pitchDeg);
      player.position.copy(feet); player.quaternion.identity();
      camera.position.set(0, eye, 0);
      camera.rotation.set(yawPitch.pitch, yawPitch.yaw, 0, "YXZ");
      camera.fov = fov; camera.aspect = w / h; camera.updateProjectionMatrix();
      player.updateMatrixWorld(true);
      adaptExposure(0, true);
      let url;
      if (ids) url = renderIds(w, h);
      else { render(post, w, h); url = renderer.domElement.toDataURL("image/jpeg", quality); }
      return { url, hash: fnv(url), eye: [+feet.x.toFixed(3), +(feet.y + eye).toFixed(3), +feet.z.toFixed(3)], yawDeg, pitchDeg, ms: Math.round(performance.now() - t0) };
    },
  });
}
