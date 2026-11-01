import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { buildBVH } from "../house/bvh.js";
import { createWalker } from "../house/walk.js";
import { loadHouse } from "./house.js";
import { buildProps } from "./props.js";
import { createSpotFinder } from "./spots.js";
import { createTargetKit, createTargets } from "./targets.js";
import { createBlaster, createEffects } from "./blaster.js";
import { createPanel } from "./panel.js";
import { audioUnlock, sfx, setListener, setMuted } from "./audio.js";
import { LEVELS, DIFFICULTY, POINTS, ROUND_SECONDS } from "./levels.js";
import { addScore, topScores, loadSettings, saveSettings } from "./scores.js";

/* ------------------------------------------------------------------ *
 *  HOUSE BLASTER — a foam-dart target game in 23 Battle Road.
 *
 *  A separate page (game.html) that reads the house from
 *  assets/sites/house-preview/ and borrows the viewer's BVH and walk
 *  code (src/house/bvh.js, walk.js) without changing them.
 *
 *  Phases: loading → menu → countdown → playing (⇄ paused) → results.
 *  Toy mode: the rig is scaled down (TOY), so the house towers over
 *  you; the walker then runs in a world scaled up by 1/TOY (a thin
 *  wrapper round the BVH), so the viewer's walk code moves a toy-sized
 *  body: it can't climb a stair riser or walk off the sofa — the
 *  teleport hops you up and down.
 * ------------------------------------------------------------------ */

const params = new URLSearchParams(location.search);
const IS_QUEST = /OculusBrowser|Quest/i.test(navigator.userAgent);
const TOY = 0.13;                                 // toy mode: you are 13 % of your size (a 1.6 m head → 21 cm)
const TOY_TARGET = 0.42;                          // and the targets shrink to toys your size
const $ = id => document.getElementById(id);

const S = loadSettings();
if (params.get("toy")) S.toy = params.get("toy") === "1";
if (params.get("room") && LEVELS.some(l => l.id === params.get("room"))) S.room = params.get("room");
setMuted(!!S.muted);

/* ------------------------------------------------------------------ *
 *  Renderer, scene, rig
 * ------------------------------------------------------------------ */
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance", preserveDrawingBuffer: !!params.get("shots") });
renderer.setPixelRatio(Math.min(devicePixelRatio, IS_QUEST ? 1 : 1.5));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.xr.enabled = true;
renderer.xr.setReferenceSpaceType("local-floor");
renderer.xr.setFoveation(1);
$("stage").appendChild(renderer.domElement);

const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.55;
scene.add(new THREE.HemisphereLight(0xe4f3ff, 0x8d7d68, 1.15));
const sun = new THREE.DirectionalLight(0xfff1dc, 1.7);
sun.position.set(-6.9, 3.75, 6.2);
scene.add(sun);
{ // a bright toy-box sky
  const g = new THREE.SphereGeometry(250, 24, 12);
  const col = [], top = new THREE.Color(0x4fa3ff), mid = new THREE.Color(0xbfe3ff), low = new THREE.Color(0xdfeecb), c = new THREE.Color();
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) { const y = p.getY(i) / 250; c.copy(y > 0 ? mid.clone().lerp(top, Math.pow(y, 0.6)) : mid.clone().lerp(low, Math.min(1, -y * 4))); col.push(c.r, c.g, c.b); }
  g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
  const sky = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide, depthWrite: false, fog: false, toneMapped: false }));
  sky.renderOrder = -1;
  scene.add(sky);
}

const camera = new THREE.PerspectiveCamera(72, innerWidth / innerHeight, 0.04, 400);
const rig = new THREE.Group();
rig.name = "rig";
rig.add(camera);
scene.add(rig);
addEventListener("resize", () => { camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });

/* ------------------------------------------------------------------ *
 *  State
 * ------------------------------------------------------------------ */
let house = null, bvh = null, partsAll = [];
let maskRay = null, maskWalkFull = null, maskWalkToy = null;
const spotCache = new Map();
const feet = new THREE.Vector3();
const look = { yaw: 0, pitch: 0 };
const G = {
  phase: "loading", level: LEVELS.find(l => l.id === S.room) || LEVELS[1], spots: null,
  score: 0, hits: 0, shots: 0, combo: 0, mult: 1, bestCombo: 0, lastHit: -99,
  time: ROUND_SECONDS, elapsed: 0, countdown: 0, spawnClock: 0, starClock: 0, wave: 1,
  player: 0, turn: [], lastPlace: 0, paused: false, fireCool: 0,
};
const SIM = { on: false, eye: 1.55, aimAt: null, holds: [] };
const inVR = () => renderer.xr.isPresenting || SIM.on;
const scaleNow = () => S.toy ? TOY : 1;
const targetScale = () => S.toy ? TOY_TARGET : 1;

/* ------------------------------------------------------------------ *
 *  Walking: the viewer's walker at full size, and the same walker in a
 *  world scaled up by 1/TOY for toy mode
 * ------------------------------------------------------------------ */
const walkFull = createWalker(() => bvh, () => maskWalkFull);
const K = 1 / TOY;
const toyBVH = (() => {
  const r2 = new THREE.Ray();
  const out = { distance: 0, point: new THREE.Vector3(), normal: new THREE.Vector3(), part: -1, front: true };
  return {
    raycast(ray, far, mask, plane, front) {
      r2.origin.copy(ray.origin).multiplyScalar(1 / K); r2.direction.copy(ray.direction);
      const h = bvh.raycast(r2, far / K, mask, null, front);
      if (!h) return null;
      out.distance = h.distance * K; out.point.copy(h.point).multiplyScalar(K); out.normal.copy(h.normal); out.part = h.part; out.front = h.front;
      return out;
    },
  };
})();
const walkToy = createWalker(() => toyBVH, () => maskWalkToy);
const tmpP = new THREE.Vector3();
function walkMove(delta) {
  if (!S.toy) { walkFull.move(feet, delta); return; }
  tmpP.copy(feet).multiplyScalar(K); walkToy.move(tmpP, delta.clone().multiplyScalar(K)); feet.copy(tmpP).multiplyScalar(1 / K);
}
function settleAt(x, z, dt) {
  const p = new THREE.Vector3(x, feet.y, z);
  if (!S.toy) { walkFull.settle(p, dt); feet.y = p.y; return; }
  p.multiplyScalar(K); walkToy.settle(p, dt); feet.y = p.y / K;
}
function freeAt(p) { return S.toy ? walkToy.free(p.clone().multiplyScalar(K)) : walkFull.free(p); }

/* ------------------------------------------------------------------ *
 *  Targets, blaster, effects, panels
 * ------------------------------------------------------------------ */
const kit = createTargetKit();
const targets = createTargets(scene, kit);
const fx = createEffects(scene);
const blaster = createBlaster();
const spotFinder = createSpotFinder(() => bvh, () => maskRay);

/* the off hand: a friendly mitten */
const mitten = new THREE.Mesh(new THREE.SphereGeometry(0.035, 12, 10), new THREE.MeshStandardMaterial({ color: 0x8e5bd6, roughness: 0.6 }));
mitten.scale.set(1, 0.8, 1.3);

const panels = {
  menu: createPanel(1024, 980, 0.95),
  results: createPanel(1024, 900, 0.95),
  count: createPanel(512, 256, 0.5),
  hud: createPanel(512, 112, 0.36),
};
for (const p of Object.values(panels)) rig.add(p.mesh);
panels.count.mesh.renderOrder = 30;
panels.count.mesh.material.depthTest = false;
panels.hud.mesh.material.depthTest = false;
panels.hud.mesh.renderOrder = 25;

/* ------------------------------------------------------------------ *
 *  Loading
 * ------------------------------------------------------------------ */
const setLoad = (f, text) => { $("loadBar").style.width = `${Math.round(f * 100)}%`; if (text) $("loadText").textContent = text; };
async function boot() {
  try {
    house = await loadHouse({ onProgress: setLoad, preferVersion: params.get("version") });
  } catch (err) {
    $("loadText").textContent = `Couldn't load the house: ${err.message}`;
    console.error(err);
    return;
  }
  scene.add(house.group);
  const props = buildProps(house.parts.length);
  scene.add(props.group);
  partsAll = [...house.parts, ...props.parts];
  setLoad(0.9, "Hiding the robots…");
  await new Promise(r => setTimeout(r));
  bvh = buildBVH(partsAll);
  const n = partsAll.length;
  maskRay = new Uint8Array(n); maskWalkFull = new Uint8Array(n); maskWalkToy = new Uint8Array(n);
  for (const p of partsAll) {
    maskRay[p.index] = p.block ? 0 : 1;
    maskWalkFull[p.index] = p.collide && !p.leg ? 1 : 0;
    maskWalkToy[p.index] = p.collide && !p.block ? 1 : 0;
  }
  setLoad(0.96, "Warming up the blaster…");
  placeAtStart(G.level);
  renderer.compile(scene, camera);
  setLoad(1, "Ready!");
  $("loading").hidden = true;
  G.phase = "menu";
  renderMenuDOM();
  showMenu();
  console.info(`game: house ${house.def.id} · ${house.parts.length} parts · ${house.group.children.length} batches · BVH ${bvh.triangles} tris`);
  dispatchEvent(new Event("game-ready"));
  if (params.get("xrsim")) sim.start();
  if (params.get("autostart")) startRound();
}

function spotsFor(level) {
  if (!spotCache.has(level.id)) spotCache.set(level.id, spotFinder.find(level, house));
  return spotCache.get(level.id);
}

function placeAtStart(level) {
  feet.set(...level.start);
  const f = walkFull.floorAt(feet.x, feet.y + 0.3, feet.z, 3);
  if (f !== null) feet.y = f;
  const dx = level.look[0] - feet.x, dz = level.look[2] - feet.z;
  look.yaw = Math.atan2(-dx, -dz);
  look.pitch = 0;
  applyRig();
}

/* the rig: at the feet, turned by yaw, scaled for toy mode; the camera at eye height (desktop / sim) */
function applyRig() {
  const s = scaleNow();
  rig.scale.setScalar(s);
  rig.rotation.set(0, look.yaw, 0);
  const lift = renderer.xr.isPresenting ? S.heightOffset + (S.seated ? 0.45 : 0) : 0;
  rig.position.set(feet.x, feet.y + lift * s, feet.z);
  if (!renderer.xr.isPresenting) {
    camera.position.set(0, (SIM.on ? SIM.eye : 1.55) + (SIM.on ? 0 : S.heightOffset), 0);
    camera.rotation.set(look.pitch, 0, 0, "YXZ");
  }
  const near = S.toy ? 0.006 : 0.04;
  if (camera.near !== near) { camera.near = near; camera.updateProjectionMatrix(); }
}

/* ------------------------------------------------------------------ *
 *  Hands (headset): which controller holds the blaster
 * ------------------------------------------------------------------ */
const ctrls = [0, 1].map(i => {
  const c = renderer.xr.getController(i);
  c.addEventListener("connected", e => { c.userData.source = e.data; c.userData.hand = e.data.handedness; dressHands(); });
  c.addEventListener("disconnected", () => { c.userData.source = null; c.userData.hand = null; dressHands(); });
  rig.add(c);
  return c;
});
let simCtrls = [];
const allCtrls = () => SIM.on ? simCtrls : ctrls;
const handCtrl = side => allCtrls().find(c => c.userData.hand === side);
const gunHand = () => S.hand === "left" ? "left" : "right";
const offHand = () => gunHand() === "right" ? "left" : "right";
function dressHands() {
  const gun = handCtrl(gunHand()), off = handCtrl(offHand());
  if (gun) gun.add(blaster.group); else if (!inVR()) camera.add(blaster.group);
  if (off) off.add(mitten);
  if (inVR()) { blaster.group.position.set(0, 0, 0); blaster.group.rotation.set(0, 0, 0); }
}
function desktopBlaster() {
  camera.add(blaster.group);
  blaster.group.position.set(0.17, -0.2, -0.36);
  blaster.group.rotation.set(0.05, 0.06, 0);
}
desktopBlaster();
const pads = {};
function pad(side) { return handCtrl(side)?.userData.source?.gamepad || null; }
function pressed(side, i) { const g = pad(side); return !!g?.buttons[i]?.pressed; }
function edge(side, i) {
  const k = `${side}${i}`, now = pressed(side, i), was = !!pads[k];
  pads[k] = now; return now && !was;
}
function axes(side) { const g = pad(side); if (!g) return [0, 0]; const a = g.axes; return a.length >= 4 ? [a[2], a[3]] : [a[0] || 0, a[1] || 0]; }
function haptic(side, intensity, ms) {
  const g = pad(side);
  const h = g?.hapticActuators?.[0] || g?.vibrationActuator;
  try { if (h?.pulse) h.pulse(intensity, ms); else if (h?.playEffect) h.playEffect("dual-rumble", { duration: ms, strongMagnitude: intensity, weakMagnitude: intensity }); } catch (_) {}
}

/* ------------------------------------------------------------------ *
 *  Firing and darts
 * ------------------------------------------------------------------ */
const _o = new THREE.Vector3(), _d = new THREE.Vector3(), _q = new THREE.Quaternion(), _v = new THREE.Vector3(), _w = new THREE.Vector3();
const ray = new THREE.Ray();
function headPos(out = new THREE.Vector3()) { return camera.getWorldPosition(out); }
function headDir(out = new THREE.Vector3()) { return camera.getWorldDirection(out); }

function fire(origin, dir) {
  if (G.fireCool > 0) return;
  G.fireCool = 0.16;
  const D = DIFFICULTY[S.difficulty] || DIFFICULTY.easy;
  // aim help: a gentle nudge toward a target within ~7°
  if (S.aimHelp) {
    let best = null, bestA = THREE.MathUtils.degToRad(D.assist > 1.4 ? 8 : 6);
    for (const t of targets.active()) {
      _v.subVectors(t.centre, origin); const dist = _v.length(); _v.divideScalar(dist);
      const a = Math.acos(THREE.MathUtils.clamp(_v.dot(dir), -1, 1));
      if (a < bestA && spotFinder.visible(origin, t.centre, t.radius)) { best = _v.clone(); bestA = a; }
    }
    if (best) dir = dir.clone().lerp(best, 0.75).normalize();
  }
  const s = scaleNow();
  fx.fire(origin, dir, S.toy ? 6.5 : 17, s);
  blaster.recoil();
  sfx.fire();
  haptic(gunHand(), 0.55, 45);
  if (G.phase === "playing") G.shots++;
}

function aimFromBlaster() {
  blaster.muzzlePoint.getWorldPosition(_o);
  blaster.muzzlePoint.getWorldQuaternion(_q);
  _d.set(0, 0, -1).applyQuaternion(_q).normalize();
  return { origin: _o.clone(), dir: _d.clone() };
}

/* desktop: the dart leaves the muzzle and flies to what the crosshair (or the cursor) is on */
function fireDesktop(ndc = null) {
  const rc = new THREE.Raycaster();
  rc.setFromCamera(ndc || new THREE.Vector2(0, 0), camera);
  const h = bvh.raycast(rc.ray, 60, maskRay);
  const aimPoint = rc.ray.at(h ? h.distance : 30, new THREE.Vector3());
  for (const t of targets.active()) {                       // the cursor over a target: aim at it, even past the wall behind
    const d = rc.ray.distanceToPoint(t.centre);
    if (d < t.radius * 1.2 && rc.ray.origin.distanceTo(t.centre) < (h ? h.distance + 0.3 : 60)) aimPoint.copy(t.centre);
  }
  blaster.muzzlePoint.getWorldPosition(_o);
  fire(_o.clone(), aimPoint.sub(_o).normalize());
}

function segSphere(p0, d, len, c, r) {
  _w.subVectors(p0, c);
  const b = _w.dot(d), cc = _w.lengthSq() - r * r;
  const disc = b * b - cc;
  if (disc < 0) return -1;
  const t = -b - Math.sqrt(disc);
  if (t >= 0 && t <= len) return t;
  return cc < 0 ? 0 : -1;                                  // starting inside the sphere
}

function updateDarts(dt) {
  const D = DIFFICULTY[S.difficulty] || DIFFICULTY.easy;
  const assist = S.aimHelp ? D.assist : 1;
  for (const d of fx.darts) {
    if (d.state !== "fly") continue;
    d.t += dt;
    const g = S.toy ? 1.6 : 3.2;
    d.vel.y -= g * dt;
    const p0 = d.obj.position;
    const step = d.vel.length() * dt;
    const dir = _d.copy(d.vel).normalize();
    let best = step, hitT = null, wall = null;
    for (const t of targets.active()) {
      const k = segSphere(p0, dir, step, t.centre, t.radius * assist);
      if (k >= 0 && k <= best) { best = k; hitT = t; }
    }
    ray.origin.copy(p0); ray.direction.copy(dir);
    const h = bvh.raycast(ray, best + 1e-4, maskRay);
    if (h && h.distance <= best) { best = h.distance; hitT = null; wall = { point: h.point.clone(), normal: h.normal.clone() }; }
    if (hitT) { hitTarget(hitT); d.state = "free"; d.obj.visible = false; continue; }
    if (wall) {
      fx.stick(d, wall.point, wall.normal);
      fx.splat(wall.point, wall.normal, (S.toy ? 0.05 : 0.17));
      sfx.splat(wall.point);
      continue;
    }
    p0.addScaledVector(dir, step);
    d.obj.lookAt(_v.copy(p0).sub(dir));
    if (d.t > 3) { d.state = "free"; d.obj.visible = false; }
  }
}

const TYPE_COLOUR = { balloon: "#ff8fab", disc: "#7dd3fc", robot: "#7dffb0", star: "#ffe066" };
function hitTarget(t) {
  targets.hit(t);
  if (G.phase !== "playing") return;
  const c = t.centre.clone();
  const sinceLast = G.elapsed - G.lastHit;
  G.combo = sinceLast <= 3 ? G.combo + 1 : 1;
  G.lastHit = G.elapsed;
  G.bestCombo = Math.max(G.bestCombo, G.combo);
  const mult = G.combo >= 12 ? 5 : G.combo >= 8 ? 4 : G.combo >= 5 ? 3 : G.combo >= 3 ? 2 : 1;
  const pts = POINTS[t.type] * mult;
  G.score += pts; G.hits++;
  const ts = targetScale();
  fx.burst(c, ts, t.type === "star" ? 70 : 42);
  fx.pop(c, `+${pts}`, TYPE_COLOUR[t.type], ts * (t.type === "star" ? 1.4 : 1));
  if (t.type === "balloon") sfx.pop(c);
  else if (t.type === "disc") sfx.ding(c, 1 + Math.random() * 0.1);
  else if (t.type === "robot") { sfx.boing(c); setTimeout(() => sfx.boop(c), 140); }
  else if (t.type === "star") { sfx.star(c); G.time += 3; setTimeout(() => fx.pop(c.clone().add(new THREE.Vector3(0, 0.25 * ts, 0)), "+3 sec!", "#ffffff", ts * 1.1), 250); }
  if (mult > G.mult) { sfx.combo(mult); setTimeout(() => fx.pop(c.clone().add(new THREE.Vector3(0, 0.35 * ts, 0)), `COMBO x${mult}!`, "#ffd23f", ts * 1.5), 120); }
  G.mult = mult;
  haptic(gunHand(), 0.9, 90);
}

/* ------------------------------------------------------------------ *
 *  Spawning
 * ------------------------------------------------------------------ */
const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = (Math.random() * (i + 1)) | 0; [a[i], a[j]] = [a[j], a[i]]; } return a; };
const UP = new THREE.Vector3(0, 1, 0);
function sample(list, n) { if (list.length <= n) return shuffle(list.slice()); const out = new Set(); while (out.size < n) out.add(list[(Math.random() * list.length) | 0]); return [...out]; }

function okPlace(centre, head, gaze, front, minD, maxD) {
  const dist = centre.distanceTo(head), flat = Math.hypot(centre.x - head.x, centre.z - head.z);
  if (dist < minD || dist > maxD || flat < minD * 0.8) return false;
  if (front) {
    _v.subVectors(centre, head); _v.y = 0; _v.normalize();
    if (_v.dot(gaze) < Math.cos(THREE.MathUtils.degToRad(62))) return false;
  }
  for (const o of targets.active()) if (o.centre.distanceTo(centre) < 0.55 * targetScale() + 0.1) return false;
  return true;
}

/* a robot peeking round a doorway, from the side of the wall away from you */
function peekPlan(spot, head, ts) {
  const side = Math.sign(_v.subVectors(head, spot.p).dot(spot.normal)) || 1;
  const far = spot.p.clone().addScaledVector(spot.normal, -side * (0.32 * ts + 0.12));
  const fl = spotFinder.cast(far.clone().add(new THREE.Vector3(0, 0.6, 0)), new THREE.Vector3(0, -1, 0), 1.0);
  if (!fl || Math.abs(fl.point.y - spot.p.y) > 0.12 || fl.normal.y < 0.8) return null;
  far.y = fl.point.y;
  for (const j of shuffle([1, -1])) {
    const show = far.clone().addScaledVector(spot.tangent, j * Math.max(0, spot.width / 2 - 0.14 * ts));
    const hide = far.clone().addScaledVector(spot.tangent, j * (spot.width / 2 + 0.32 * ts));
    const mid = new THREE.Vector3(0, 0.35 * ts, 0);
    const span = hide.distanceTo(show);
    const blocked = spotFinder.cast(show.clone().add(mid), hide.clone().sub(show).normalize(), span + 0.12 * ts);
    if (blocked) continue;
    if (!spotFinder.clearRing(show, 0.35 * ts, 0.13 * ts)) continue;
    return { show, hide, lean: j, centre: show.clone().addScaledVector(UP, 0.45 * ts) };
  }
  return null;
}

function trySpawn(kind = null) {
  const sp = G.spots;
  if (!sp) return false;
  const head = headPos(), gaze = headDir(); gaze.y = 0; gaze.normalize();
  const ts = targetScale(), s = scaleNow();
  const minD = S.toy ? 0.4 : 1.6, maxD = (G.level.far || 7.5) * (S.toy ? 0.75 : 1);
  const D = DIFFICULTY[S.difficulty] || DIFFICULTY.easy;
  const f = Math.min(1, G.elapsed / ROUND_SECONDS);
  const speed = G.level.speed * (1 + 0.08 * (G.wave - 1));
  const life = THREE.MathUtils.lerp(D.life[0], D.life[1], f) / speed;
  const r = Math.random();
  const type = kind || (r < 0.38 ? "balloon" : r < 0.64 ? "disc" : "robot");
  for (const front of [true, false]) {
    if (type === "robot") {
      if (sp.door.length && Math.random() < 0.65) {
        for (const spot of sample(sp.door, 12)) {
          const plan = peekPlan(spot, head, ts);
          if (!plan || !okPlace(plan.centre, head, gaze, front, minD, maxD) || !spotFinder.visible(head, plan.centre, 0.12)) continue;
          targets.spawn({ type, mode: "peek", p: plan.show, life: life + 0.6, scale: ts, door: { show: plan.show, hide: plan.hide, lean: plan.lean } });
          sfx.boop(plan.centre); return true;
        }
      }
      for (const spot of sample([...sp.ledge, ...sp.ledge, ...sp.floor], 40)) {
        const c = spot.p.clone().addScaledVector(UP, 0.45 * ts);
        if (!okPlace(c, head, gaze, front, minD, maxD) || !spotFinder.visible(head, c, 0.15 * ts)) continue;
        targets.spawn({ type, mode: "pop", p: spot.p.clone(), life, scale: ts });
        sfx.boop(c); return true;
      }
    } else if (type === "disc") {
      for (const spot of sample([...sp.ledge, ...sp.ledge, ...sp.floor], 40)) {
        const c = spot.p.clone().addScaledVector(UP, 0.5 * ts);
        if (!okPlace(c, head, gaze, front, minD, maxD) || !spotFinder.visible(head, c, 0.15 * ts)) continue;
        targets.spawn({ type, mode: "stand", p: spot.p.clone(), life, scale: ts, spin: 0.9 + Math.random() * 1.2 * speed });
        sfx.spawn(c); return true;
      }
    } else {
      const pool = [...sp.air.map(a => ({ a, float: true })), ...sp.window.map(a => ({ a, float: true, win: true })), ...sp.floor.concat(sp.ledge).map(a => ({ a, float: false }))];
      for (const { a, float, win } of sample(pool, 45)) {
        const p = a.p.clone();
        if (win) p.y += 0;
        else if (float) p.y += S.toy ? 0.18 + Math.random() * 0.35 : 1.1 + Math.random() * 0.55;
        else p.y += 0.22 * ts;
        if (!okPlace(p, head, gaze, front, minD, maxD) || !spotFinder.visible(head, p, 0.15 * ts)) continue;
        const up = spotFinder.freeDistance(p, UP, 3);
        targets.spawn({ type: "balloon", mode: float ? "float" : "rise", p, life, scale: ts, ceiling: p.y + Math.max(0, Math.min(S.toy ? 0.5 : 1.1, up - 0.3 * ts)) });
        sfx.spawn(p); return true;
      }
    }
  }
  // nowhere listed can be seen from here: float a balloon in the open space in front of you
  for (let k = 0; k < 6; k++) {
    const dir = gaze.clone().applyAxisAngle(UP, (Math.random() - 0.5) * 1.4);
    const free = spotFinder.freeDistance(head, dir, 6);
    if (free < (S.toy ? 0.4 : 1.6)) continue;
    const p = head.clone().addScaledVector(dir, free * (0.45 + Math.random() * 0.2));
    p.y -= (S.toy ? 0.04 : 0.2) + Math.random() * 0.2 * s;
    if (!okPlace(p, head, gaze, false, minD * 0.8, 99)) continue;
    targets.spawn({ type: "balloon", mode: "float", p, life, scale: ts, ceiling: p.y });
    sfx.spawn(p); return true;
  }
  return false;
}

function trySpawnStar() {
  const sp = G.spots;
  if (!sp) return false;
  const head = headPos(), ts = targetScale();
  const pts = sample([...sp.air, ...sp.floor], 40).map(a => a.p.clone().addScaledVector(UP, S.toy ? 0.25 + Math.random() * 0.3 : 1.2 + Math.random() * 0.5))
    .filter(p => p.distanceTo(head) > (S.toy ? 0.4 : 1.4) && spotFinder.visible(head, p, 0.1));
  for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
    const d = pts[i].distanceTo(pts[j]);
    if (d < (S.toy ? 0.8 : 2.0) || d > (S.toy ? 3 : 6)) continue;
    const mid = pts[i].clone().lerp(pts[j], 0.5);
    if (!spotFinder.visible(head, mid, 0.1) || !spotFinder.visible(pts[i], pts[j], 0.05)) continue;
    targets.spawn({ type: "star", mode: "zip", p: pts[i], path: [pts[i], pts[j]], life: 3.8 / G.level.speed, scale: ts });
    sfx.star(pts[i]);
    return true;
  }
  return false;
}

/* ------------------------------------------------------------------ *
 *  Round flow
 * ------------------------------------------------------------------ */
function currentName() { return S.turns ? (S.players[G.player] || `Player ${G.player + 1}`) : (S.players[0] || "Player 1"); }

function startRound(opts = {}) {
  audioUnlock();
  if (opts.level) { G.level = opts.level; S.room = opts.level.id; saveSettings(S); }
  G.spots = spotsFor(G.level);
  targets.clear(); fx.clear();
  Object.assign(G, { score: 0, hits: 0, shots: 0, combo: 0, mult: 1, bestCombo: 0, lastHit: -99, time: ROUND_SECONDS, elapsed: 0,
    countdown: 3, spawnClock: 0.4, starClock: 12 + Math.random() * 6, paused: false, phase: "countdown" });
  placeAtStart(G.level);
  hideAllPanels();
  $("menu").hidden = true; $("results").hidden = true; $("pause").hidden = true;
  $("hud").hidden = inVR(); $("cross").hidden = inVR();
  lastBeep = 4;
  if (!inVR() && !params.get("nolock")) renderer.domElement.requestPointerLock?.()?.catch?.(() => {});
}
let lastBeep = 4;

function endRound() {
  G.phase = "results";
  for (const t of targets.active()) { t.state = "out"; t.out = 0; }
  sfx.fanfare();
  const name = currentName();
  G.lastPlace = addScore({ name, score: G.score, room: G.level.id, toy: S.toy, difficulty: S.difficulty, hits: G.hits, shots: G.shots });
  if (S.turns) { G.turn[G.player] = { name, score: G.score }; }
  if (document.pointerLockElement) document.exitPointerLock();
  showResults();
}

function nextRoom() {
  const i = LEVELS.indexOf(G.level);
  G.wave++;
  startRound({ level: LEVELS[(i + 1) % LEVELS.length] });
}

function togglePause(on = !G.paused) {
  if (G.phase !== "playing" && G.phase !== "countdown") return;
  G.paused = on;
  if (inVR()) { if (on) showMenu(true); else hideAllPanels(); }
  else { $("pause").hidden = !on; if (!on && !params.get("nolock")) renderer.domElement.requestPointerLock?.()?.catch?.(() => {}); }
}

/* ------------------------------------------------------------------ *
 *  Panels in the headset
 * ------------------------------------------------------------------ */
function hideAllPanels() { for (const p of Object.values(panels)) p.show(false); }
function placePanel(p, dist, dy) {
  // in front of the head, in the rig's own frame (toy mode shrinks panels with you)
  const hp = camera.position.clone();
  const e = new THREE.Euler().setFromQuaternion(camera.quaternion, "YXZ");
  const fwd = new THREE.Vector3(-Math.sin(e.y), 0, -Math.cos(e.y));
  const eyeY = renderer.xr.isPresenting ? hp.y : camera.position.y;
  p.mesh.position.copy(hp).addScaledVector(fwd, dist); p.mesh.position.y = eyeY + dy;
  p.mesh.rotation.set(0, e.y, 0);
  p.mesh.lookAt(rig.localToWorld(new THREE.Vector3(hp.x, p.mesh.position.y, hp.z)));
  p.mesh.rotation.set(0, e.y, 0);
}

function drawMenu(ui) {
  const W = ui.w;
  ui.bg();
  ui.text(G.paused ? "PAUSED" : "HOUSE BLASTER", W / 2, 70, 66, "#ffd23f", "center", 900);
  ui.text(G.paused ? "Pick a room to restart, or carry on" : "Pick a room, then press START", W / 2, 128, 30, "#cfd8ff", "center", 600);
  LEVELS.forEach((l, i) => {
    const col = i % 3, row = (i / 3) | 0;
    ui.button(`room:${l.id}`, `${l.emoji} ${l.name}`, 40 + col * 318, 170 + row * 98, 300, 82, { on: G.level.id === l.id, size: 32 });
  });
  const y = 390;
  ui.button("toy", S.toy ? "🧸 Toy mode: ON" : "🧸 Toy mode: off", 40, y, 460, 80, { on: S.toy, col: "#8e5bd6" });
  ui.button("turns", S.turns ? "👥 2 players (turns)" : "👤 1 player", 524, y, 460, 80, { on: S.turns, col: "#8e5bd6" });
  ui.button("diff", `⚡ ${DIFFICULTY[S.difficulty].label}`, 40, y + 96, 300, 80, { col: "#3b4a6b" });
  ui.button("aim", S.aimHelp ? "🎯 Aim help: on" : "🎯 Aim help: off", 362, y + 96, 300, 80, { on: S.aimHelp, col: "#3b4a6b", size: 30 });
  ui.button("hand", S.hand === "left" ? "✋ Left-handed" : "✋ Right-handed", 684, y + 96, 300, 80, { col: "#3b4a6b", size: 30 });
  ui.text(`Height ${S.heightOffset >= 0 ? "+" : ""}${Math.round(S.heightOffset * 100)} cm`, 190, y + 232, 34, "#fff");
  ui.button("h-", "−", 40, y + 270, 140, 76, { col: "#3b4a6b", size: 48 });
  ui.button("h+", "+", 200, y + 270, 140, 76, { col: "#3b4a6b", size: 48 });
  ui.button("seated", S.seated ? "🪑 Seated: on" : "🪑 Seated: off", 362, y + 270, 300, 76, { on: S.seated, col: "#3b4a6b", size: 30 });
  ui.button("sound", S.muted ? "🔇 Sound off" : "🔊 Sound on", 684, y + 270, 300, 76, { col: "#3b4a6b", size: 30 });
  if (G.paused) {
    ui.button("resume", "▶ CARRY ON", 40, 790, 600, 130, { col: "#06a77d", size: 52 });
    ui.button("exit", "Exit VR", 664, 790, 320, 130, { col: "#b23a48", size: 36 });
  } else {
    ui.button("start", `▶ START${S.turns ? ` — ${S.players[G.player] || "Player 1"}` : ""}`, 40, 790, 600, 130, { col: "#06a77d", size: 50 });
    ui.button("exit", "Exit VR", 664, 790, 320, 130, { col: "#b23a48", size: 36 });
  }
}

function drawResults(ui) {
  const W = ui.w;
  ui.bg();
  ui.text("TIME'S UP!", W / 2, 70, 64, "#ffd23f", "center", 900);
  ui.text(`${currentName()} · ${G.level.emoji} ${G.level.name}${S.toy ? " · 🧸" : ""}`, W / 2, 128, 32, "#cfd8ff", "center", 600);
  ui.text(String(G.score), W / 2, 230, 130, "#ffffff", "center", 900);
  const acc = G.shots ? Math.round(100 * G.hits / G.shots) : 0;
  ui.text(`${G.hits} hits · ${acc}% on target · best combo ${G.bestCombo}`, W / 2, 320, 32, "#cfd8ff", "center", 600);
  if (G.lastPlace === 1) ui.text("🏆 NEW HIGH SCORE! 🏆", W / 2, 378, 44, "#ffd23f");
  else if (G.lastPlace) ui.text(`#${G.lastPlace} on the ${G.level.name} board`, W / 2, 378, 36, "#7dffb0");
  let y = 430;
  if (S.turns && G.turn.filter(Boolean).length === 2 && G.player === 1) {
    const [a, b] = G.turn;
    const win = a.score === b.score ? "It's a draw!" : `${a.score > b.score ? a.name : b.name} wins!`;
    ui.text(`${a.name} ${a.score}  ·  ${b.name} ${b.score}`, W / 2, y + 10, 38, "#fff");
    ui.text(win, W / 2, y + 62, 46, "#ffd23f", "center", 900);
    y += 110;
  }
  ui.text(`${G.level.name} — top scores`, W / 2, y + 20, 30, "#9fb0d8", "center", 700);
  topScores(G.level.id, 4).forEach((e, i) => ui.text(`${i + 1}. ${e.name} — ${e.score}${e.toy ? " 🧸" : ""}`, W / 2, y + 62 + i * 40, 30, "#fff", "center", 600));
  const by = 760;
  if (S.turns && G.player === 0) {
    ui.button("nextPlayer", `▶ ${S.players[1] || "Player 2"}'s go!`, 40, by, 620, 110, { col: "#06a77d", size: 44 });
    ui.button("menu", "Menu", 684, by, 300, 110, { col: "#3b4a6b" });
  } else {
    ui.button("again", "↻ Again", 40, by, 300, 110, { col: "#06a77d", size: 42 });
    ui.button("next", "Next room ▶", 362, by, 300, 110, { col: "#2f7cf6", size: 38 });
    ui.button("menu", "Menu", 684, by, 300, 110, { col: "#3b4a6b" });
  }
}

function showMenu(paused = false) {
  if (!inVR()) { if (!paused) { $("menu").hidden = false; renderMenuDOM(); } return; }
  hideAllPanels();
  panels.menu.draw(drawMenu);
  placePanel(panels.menu, 0.95, -0.12);
  panels.menu.show(true);
}
function showResults() {
  if (!inVR()) { renderResultsDOM(); $("results").hidden = false; $("hud").hidden = true; $("cross").hidden = true; return; }
  hideAllPanels();
  panels.results.draw(drawResults);
  placePanel(panels.results, 0.95, -0.1);
  panels.results.show(true);
}

function press(id) {
  sfx.click();
  if (id.startsWith("room:")) { G.level = LEVELS.find(l => l.id === id.slice(5)); S.room = G.level.id; saveSettings(S); if (G.paused) { G.player = G.player; startRound({ level: G.level }); return; } }
  else if (id === "toy") { S.toy = !S.toy; applyRig(); }
  else if (id === "turns") { S.turns = !S.turns; G.player = 0; G.turn = []; }
  else if (id === "diff") { const k = Object.keys(DIFFICULTY); S.difficulty = k[(k.indexOf(S.difficulty) + 1) % k.length]; }
  else if (id === "aim") S.aimHelp = !S.aimHelp;
  else if (id === "hand") { S.hand = S.hand === "left" ? "right" : "left"; dressHands(); }
  else if (id === "h-") S.heightOffset = Math.max(-0.6, +(S.heightOffset - 0.05).toFixed(2));
  else if (id === "h+") S.heightOffset = Math.min(0.8, +(S.heightOffset + 0.05).toFixed(2));
  else if (id === "seated") S.seated = !S.seated;
  else if (id === "sound") { S.muted = !S.muted; setMuted(S.muted); }
  else if (id === "start") { saveSettings(S); if (!S.turns) G.player = 0; startRound(); return; }
  else if (id === "resume") { togglePause(false); return; }
  else if (id === "exit") { renderer.xr.getSession()?.end(); if (SIM.on) sim.stop(); return; }
  else if (id === "again") { if (S.turns) { G.player = 0; G.turn = []; } startRound(); return; }
  else if (id === "next") { if (S.turns) { G.player = 0; G.turn = []; } nextRoom(); return; }
  else if (id === "nextPlayer") { G.player = 1; startRound(); return; }
  else if (id === "menu") { G.phase = "menu"; G.paused = false; if (S.turns) { G.player = 0; G.turn = []; } targets.clear(); showMenu(); return; }
  saveSettings(S);
  applyRig();
  if (panels.menu.mesh.visible) panels.menu.draw(drawMenu);
}

/* ------------------------------------------------------------------ *
 *  Headset input
 * ------------------------------------------------------------------ */
let snapLatch = false, teleAim = false, teleTarget = null;
const arcPts = new Float32Array(40 * 3);
const arcGeo = new THREE.BufferGeometry(); arcGeo.setAttribute("position", new THREE.BufferAttribute(arcPts, 3));
const arc = new THREE.Line(arcGeo, new THREE.LineBasicMaterial({ color: 0x7dffb0 }));
arc.frustumCulled = false; arc.visible = false; scene.add(arc);
const ring = new THREE.Mesh(new THREE.RingGeometry(0.18, 0.25, 32).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0x7dffb0, transparent: true, opacity: 0.85, depthWrite: false }));
ring.visible = false; scene.add(ring);
const raycaster = new THREE.Raycaster();

function vrInput(dt) {
  const gun = gunHand(), off = offHand();
  const menuOpen = panels.menu.mesh.visible || panels.results.mesh.visible;
  // menu: Y / B (or the menu button) pauses
  if (edge("left", 5) || edge("right", 5) || edge("left", 12)) {
    if (G.phase === "playing" || G.phase === "countdown") togglePause();
    else if (G.phase === "results") press("menu");
  }
  // laser at panels
  const { origin, dir } = aimFromBlaster();
  blaster.laser.visible = menuOpen;
  const triggerEdge = edge(gun, 0);
  if (menuOpen) {
    raycaster.set(origin, dir);
    const vis = [panels.menu, panels.results].filter(p => p.mesh.visible);
    const hits = raycaster.intersectObjects(vis.map(p => p.mesh), false);
    const h = hits[0];
    const panel = h && vis.find(p => p.mesh === h.object);
    const id = panel ? panel.at(h.uv) : null;
    for (const p of vis) p.setHover(p === panel ? id : null);
    blaster.laser.scale.z = (h ? h.distance : 3 * scaleNow()) / scaleNow();
    if (triggerEdge && id) { press(id); haptic(gun, 0.4, 30); }
  } else if (G.phase === "playing" && !G.paused && pressed(gun, 0)) {
    if (triggerEdge || G.fireCool <= -0.12) fire(origin, dir);    // hold to keep firing, a little slower
  } else if (triggerEdge && G.phase !== "playing") fire(origin, dir);   // free shots in the countdown
  // walking: the off-hand stick, toward where the head looks
  const [lx, ly] = axes(off);
  if (Math.hypot(lx, ly) > 0.15 && !G.paused) {
    const e = new THREE.Euler().setFromQuaternion(camera.getWorldQuaternion(_q), "YXZ");
    const speed = (S.toy ? 0.7 : 2.0) * dt;
    const f = new THREE.Vector3(-Math.sin(e.y), 0, -Math.cos(e.y)), r = new THREE.Vector3(Math.cos(e.y), 0, -Math.sin(e.y));
    const delta = f.multiplyScalar(-ly * speed).addScaledVector(r, lx * speed);
    const head = headPos();
    const off0 = new THREE.Vector3(head.x - feet.x, 0, head.z - feet.z);
    const hf = feet.clone().add(off0);                     // move the body where the head is, keep the offset
    feet.copy(hf);
    walkMove(delta);
    feet.sub(off0);
  }
  // the blaster-hand stick: snap turn left / right, push forward to aim a teleport, let go to jump there
  const [rx, ry] = axes(gun);
  if (Math.abs(rx) > 0.7 && !snapLatch && !teleAim) {
    snapLatch = true;
    const head = headPos();
    const ang = -Math.sign(rx) * THREE.MathUtils.degToRad(30);
    const off0 = new THREE.Vector3(head.x - feet.x, 0, head.z - feet.z);
    const rot = off0.clone().applyAxisAngle(UP, ang);
    feet.add(off0.sub(rot));
    look.yaw += ang;
    sfx.tick();
  } else if (Math.abs(rx) < 0.3) snapLatch = false;
  if (ry < -0.7 && !menuOpen) { teleAim = true; teleTarget = aimTeleport(origin, dir); }
  else if (teleAim && ry > -0.3) {
    teleAim = false; arc.visible = false; ring.visible = false;
    if (teleTarget) {
      const head = headPos();
      feet.set(teleTarget.x - (head.x - feet.x), teleTarget.y, teleTarget.z - (head.z - feet.z));
      sfx.tick(); haptic(gun, 0.3, 30);
    }
    teleTarget = null;
  }
}

function aimTeleport(origin, dir) {
  const s = scaleNow();
  const v = dir.clone().multiplyScalar(S.toy ? 2.6 : 7.5), g = S.toy ? 5.5 : 9.8;
  const p = origin.clone();
  let hit = null, n = 0;
  for (let i = 0; i < 40; i++) {
    arcPts[i * 3] = p.x; arcPts[i * 3 + 1] = p.y; arcPts[i * 3 + 2] = p.z; n = i + 1;
    const dt = S.toy ? 0.03 : 0.045;
    const nv = v.clone(); nv.y -= g * dt;
    const step = nv.clone().multiplyScalar(dt);
    const len = step.length();
    ray.origin.copy(p); ray.direction.copy(step).divideScalar(len);
    const h = bvh.raycast(ray, len, maskRay);
    if (h) { hit = { point: h.point.clone(), normal: h.normal.clone() }; arcPts[(i + 1) * 3] = h.point.x; arcPts[(i + 1) * 3 + 1] = h.point.y; arcPts[(i + 1) * 3 + 2] = h.point.z; n = i + 2; break; }
    p.add(step); v.copy(nv);
  }
  for (let i = n; i < 40; i++) { arcPts[i * 3] = arcPts[(n - 1) * 3]; arcPts[i * 3 + 1] = arcPts[(n - 1) * 3 + 1]; arcPts[i * 3 + 2] = arcPts[(n - 1) * 3 + 2]; }
  arcGeo.attributes.position.needsUpdate = true;
  arc.visible = true;
  const ok = hit && hit.normal.y > 0.7 && freeAt(hit.point);
  arc.material.color.setHex(ok ? 0x7dffb0 : 0xff6b6b);
  ring.visible = !!hit;
  if (hit) { ring.position.copy(hit.point).addScaledVector(hit.normal, 0.01); ring.scale.setScalar(S.toy ? TOY * 1.4 : 1); ring.material.color.setHex(ok ? 0x7dffb0 : 0xff6b6b); }
  return ok ? hit.point : null;
}

/* ------------------------------------------------------------------ *
 *  Desktop input
 * ------------------------------------------------------------------ */
const keys = new Set();
addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") return;
  keys.add(e.code);
  if (e.code === "Space" && G.phase === "playing" && !G.paused && !inVR()) { fireDesktop(); e.preventDefault(); }
  if ((e.code === "KeyP" || e.code === "Escape") && (G.phase === "playing" || G.phase === "countdown") && !inVR()) togglePause();
  if (e.code === "KeyQ" || e.code === "KeyE") look.yaw += (e.code === "KeyQ" ? 1 : -1) * Math.PI / 6;
});
addEventListener("keyup", e => keys.delete(e.code));
document.addEventListener("pointerlockchange", () => {
  if (!document.pointerLockElement && G.phase === "playing" && !G.paused && !inVR()) togglePause(true);
});
renderer.domElement.addEventListener("mousemove", e => {
  if (document.pointerLockElement !== renderer.domElement) return;
  look.yaw -= e.movementX * 0.0022;
  look.pitch = THREE.MathUtils.clamp(look.pitch - e.movementY * 0.0022, -1.4, 1.4);
});
renderer.domElement.addEventListener("mousedown", e => {
  if (inVR() || G.paused) return;
  audioUnlock();
  if (G.phase !== "playing" && G.phase !== "countdown") return;
  if (document.pointerLockElement === renderer.domElement) { fireDesktop(); return; }
  const r = renderer.domElement.getBoundingClientRect();
  fireDesktop(new THREE.Vector2((e.clientX - r.left) / r.width * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1));
  if (!params.get("nolock")) renderer.domElement.requestPointerLock?.()?.catch?.(() => {});
});

function desktopInput(dt) {
  if (G.paused) return;
  const turn = (keys.has("ArrowLeft") ? 1 : 0) - (keys.has("ArrowRight") ? 1 : 0);
  look.yaw += turn * dt * 1.8;
  const pitch = (keys.has("ArrowUp") ? 1 : 0) - (keys.has("ArrowDown") ? 1 : 0);
  look.pitch = THREE.MathUtils.clamp(look.pitch + pitch * dt * 1.2, -1.4, 1.4);
  const fw = (keys.has("KeyW") ? 1 : 0) - (keys.has("KeyS") ? 1 : 0);
  const st = (keys.has("KeyD") ? 1 : 0) - (keys.has("KeyA") ? 1 : 0);
  if (fw || st) {
    const speed = (S.toy ? 0.6 : 2.2) * dt * (keys.has("ShiftLeft") ? 1.6 : 1);
    const f = new THREE.Vector3(-Math.sin(look.yaw), 0, -Math.cos(look.yaw)), r = new THREE.Vector3(Math.cos(look.yaw), 0, -Math.sin(look.yaw));
    walkMove(f.multiplyScalar(fw * speed).addScaledVector(r, st * speed));
  }
}

/* ------------------------------------------------------------------ *
 *  The frame
 * ------------------------------------------------------------------ */
let lastT = performance.now(), hudKey = "";
const fps = { n: 0, t: 0, value: 0 };
function frame(now) {
  const dt = Math.min(0.05, (now - lastT) / 1000 || 0.016);
  lastT = now;
  fps.n++; fps.t += dt; if (fps.t > 1) { fps.value = Math.round(fps.n / fps.t); fps.n = 0; fps.t = 0; }
  const time = now / 1000;
  if (G.phase === "loading") { renderer.render(scene, camera); return; }
  G.fireCool -= dt;
  if (SIM.on) simPose();
  if (inVR()) vrInput(dt); else desktopInput(dt);
  // feet settle on the floor under the head
  const head = headPos();
  if (!G.paused) settleAt(inVR() ? head.x : feet.x, inVR() ? head.z : feet.z, dt);
  applyRig();

  if ((G.phase === "countdown" || G.phase === "playing") && !G.paused && G.countdown > -0.6) {
    G.countdown -= dt;
    const n = Math.max(0, Math.ceil(G.countdown));
    if (n !== lastBeep) { lastBeep = n; sfx.beep(n === 0); drawCount(n > 0 ? String(n) : "GO!"); }
    if (G.countdown <= 0 && G.phase === "countdown") G.phase = "playing";
    if (G.countdown <= -0.6) { panels.count.show(false); $("big").hidden = true; }
  }
  if (G.phase === "countdown") {
    // waiting for GO
  } else if (G.phase === "playing" && !G.paused) {
    G.elapsed += dt;
    G.time -= dt;
    const D = DIFFICULTY[S.difficulty] || DIFFICULTY.easy;
    const f = Math.min(1, G.elapsed / ROUND_SECONDS);
    const speed = G.level.speed * (1 + 0.08 * (G.wave - 1));
    G.spawnClock -= dt;
    const max = Math.round(THREE.MathUtils.lerp(D.max[0], D.max[1], f));
    if (G.spawnClock <= 0) {
      if (targets.active().length < max) trySpawn();
      G.spawnClock = THREE.MathUtils.lerp(D.interval[0], D.interval[1], f) / speed * (0.7 + Math.random() * 0.6);
    }
    G.starClock -= dt;
    if (G.starClock <= 0) { trySpawnStar(); G.starClock = 11 + Math.random() * 7; }
    if (G.elapsed - G.lastHit > 3 && G.combo) { G.combo = 0; G.mult = 1; }
    const secs = Math.ceil(G.time);
    if (secs <= 5 && secs > 0 && secs !== lastBeep) { lastBeep = secs; sfx.tick(); }
    if (G.time <= 0) { G.time = 0; endRound(); }
  }
  if (!G.paused) { targets.update(dt, head, time); updateDarts(dt); }
  fx.update(dt);
  blaster.update(dt);
  const secs = G.phase === "playing" || G.phase === "countdown" ? Math.ceil(G.time) : -1;
  blaster.drawScreen(G.score, secs, G.mult);
  updateHUD(secs);
  const fwd = headDir(), upv = new THREE.Vector3(0, 1, 0).applyQuaternion(camera.getWorldQuaternion(_q));
  setListener(head, fwd, upv);
  renderer.render(scene, camera);
}

function drawCount(text) {
  if (inVR()) {
    panels.count.draw(ui => { ui.g.clearRect(0, 0, ui.w, ui.h); ui.text(text, ui.w / 2, ui.h / 2, 190, text === "GO!" ? "#7dffb0" : "#ffd23f", "center", 900); ui.g.lineWidth = 8; ui.g.strokeStyle = "#1b2140"; ui.g.strokeText(text, ui.w / 2, ui.h / 2); });
    placePanel(panels.count, 1.3, 0.05);
    panels.count.show(true);
  } else { $("big").textContent = text; $("big").hidden = false; }
}

function updateHUD(secs) {
  const playing = G.phase === "playing" || G.phase === "countdown";
  const key = `${G.score}|${secs}|${G.mult}|${G.combo}|${playing}|${S.turns ? G.player : ""}`;
  if (key === hudKey) { if (inVR() && panels.hud.mesh.visible) followHud(); return; }
  hudKey = key;
  if (!inVR()) {
    $("hudScore").textContent = G.score;
    $("hudTime").textContent = secs >= 0 ? secs : "–";
    $("hudTime").classList.toggle("low", secs >= 0 && secs <= 10);
    $("hudCombo").textContent = G.mult > 1 ? `COMBO x${G.mult}` : G.combo > 1 ? `${G.combo} in a row` : "";
    $("hudName").textContent = S.turns ? currentName() : `${G.level.emoji} ${G.level.name}`;
    return;
  }
  panels.hud.show(playing && !G.paused);
  if (!playing) return;
  panels.hud.draw(ui => {
    ui.g.clearRect(0, 0, ui.w, ui.h);
    ui.g.fillStyle = "rgba(22,28,48,0.72)"; ui.g.beginPath(); ui.g.roundRect(4, 4, ui.w - 8, ui.h - 8, 30); ui.g.fill();
    ui.text(`⭐ ${G.score}`, 24, ui.h / 2, 50, "#fff", "left", 900);
    ui.text(`⏱ ${Math.max(0, secs)}`, ui.w - 24, ui.h / 2, 50, secs <= 10 ? "#ff8080" : "#fff", "right", 900);
    if (G.mult > 1) ui.text(`x${G.mult}`, ui.w / 2 + 20, ui.h / 2, 46, "#ffd23f", "center", 900);
  });
  followHud();
}
/* the score strip follows your view lazily, a little below your eyes */
let hudYaw = null;
function followHud() {
  const e = new THREE.Euler().setFromQuaternion(camera.quaternion, "YXZ");
  if (hudYaw === null || Math.abs(((e.y - hudYaw + Math.PI * 3) % (Math.PI * 2)) - Math.PI) > 0.5) hudYaw = e.y;
  else hudYaw += (((e.y - hudYaw + Math.PI * 3) % (Math.PI * 2)) - Math.PI) * 0.04;
  const hp = camera.position, d = 1.1;
  panels.hud.mesh.position.set(hp.x - Math.sin(hudYaw) * d, hp.y - 0.42, hp.z - Math.cos(hudYaw) * d);
  panels.hud.mesh.rotation.set(-0.35, hudYaw, 0, "YXZ");
}

/* ------------------------------------------------------------------ *
 *  The page (desktop menus)
 * ------------------------------------------------------------------ */
function renderMenuDOM() {
  const rooms = $("rooms");
  rooms.innerHTML = "";
  for (const l of LEVELS) {
    const b = document.createElement("button");
    b.className = "room"; b.type = "button";
    b.setAttribute("aria-pressed", String(G.level.id === l.id));
    b.innerHTML = `<span class="emoji">${l.emoji}</span><span>${l.name}</span>`;
    b.addEventListener("click", () => { G.level = l; S.room = l.id; saveSettings(S); renderMenuDOM(); sfx.click(); });
    rooms.appendChild(b);
  }
  $("p1").value = S.players[0]; $("p2").value = S.players[1];
  $("turns").checked = S.turns; $("p2row").hidden = !S.turns;
  $("toy").checked = S.toy; $("aimHelp").checked = S.aimHelp; $("muted").checked = S.muted;
  $("difficulty").value = S.difficulty; $("seated").checked = S.seated; $("hand").value = S.hand;
  $("heightVal").textContent = `${S.heightOffset >= 0 ? "+" : ""}${Math.round(S.heightOffset * 100)} cm`;
  renderBoard($("board"), G.level.id);
}
function renderBoard(el, room) {
  const list = topScores(room, 10);
  el.innerHTML = list.length ? list.map((e, i) => `<li><span class="rank">${i + 1}</span><span class="who">${esc(e.name)}${e.toy ? " 🧸" : ""}</span><span class="pts">${e.score}</span></li>`).join("")
    : `<li class="empty">No scores yet in the ${esc(LEVELS.find(l => l.id === room)?.name || "")}. Be the first!</li>`;
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function readMenuDOM() {
  S.players = [$("p1").value.trim() || "Player 1", $("p2").value.trim() || "Player 2"];
  S.turns = $("turns").checked; S.toy = $("toy").checked; S.aimHelp = $("aimHelp").checked; S.muted = $("muted").checked;
  S.difficulty = $("difficulty").value; S.seated = $("seated").checked; S.hand = $("hand").value;
  setMuted(S.muted);
  saveSettings(S);
}
for (const id of ["p1", "p2", "turns", "toy", "aimHelp", "muted", "difficulty", "seated", "hand"]) $(id).addEventListener("change", () => { readMenuDOM(); renderMenuDOM(); applyRig(); });
$("hMinus").addEventListener("click", () => { S.heightOffset = Math.max(-0.6, +(S.heightOffset - 0.05).toFixed(2)); saveSettings(S); renderMenuDOM(); });
$("hPlus").addEventListener("click", () => { S.heightOffset = Math.min(0.8, +(S.heightOffset + 0.05).toFixed(2)); saveSettings(S); renderMenuDOM(); });
$("playScreen").addEventListener("click", () => { readMenuDOM(); G.player = 0; G.turn = []; startRound(); });
$("resume").addEventListener("click", () => togglePause(false));
$("quit").addEventListener("click", () => { G.paused = false; G.phase = "menu"; targets.clear(); $("pause").hidden = true; $("hud").hidden = true; $("cross").hidden = true; showMenu(); });

function renderResultsDOM() {
  const acc = G.shots ? Math.round(100 * G.hits / G.shots) : 0;
  $("resWho").textContent = `${currentName()} · ${G.level.emoji} ${G.level.name}${S.toy ? " · 🧸 toy mode" : ""}`;
  $("resScore").textContent = G.score;
  $("resStats").textContent = `${G.hits} hits · ${acc}% on target · best combo ${G.bestCombo}`;
  $("resPlace").textContent = G.lastPlace === 1 ? "🏆 New high score!" : G.lastPlace ? `#${G.lastPlace} on the ${G.level.name} board` : "";
  const both = S.turns && G.player === 1 && G.turn.filter(Boolean).length === 2;
  $("resVs").hidden = !both;
  if (both) {
    const [a, b] = G.turn;
    $("resVs").textContent = `${a.name} ${a.score} · ${b.name} ${b.score} — ${a.score === b.score ? "a draw!" : `${a.score > b.score ? a.name : b.name} wins!`}`;
  }
  renderBoard($("resBoard"), G.level.id);
  const turnNext = S.turns && G.player === 0;
  $("resNextPlayer").hidden = !turnNext;
  $("resNextPlayer").textContent = `▶ ${S.players[1] || "Player 2"}'s go!`;
  $("resAgain").hidden = turnNext; $("resNext").hidden = turnNext;
}
$("resAgain").addEventListener("click", () => { if (S.turns) { G.player = 0; G.turn = []; } startRound(); });
$("resNext").addEventListener("click", () => { if (S.turns) { G.player = 0; G.turn = []; } nextRoom(); });
$("resNextPlayer").addEventListener("click", () => { G.player = 1; startRound(); });
$("resMenu").addEventListener("click", () => { G.phase = "menu"; if (S.turns) { G.player = 0; G.turn = []; } $("results").hidden = true; targets.clear(); showMenu(); });

/* ------------------------------------------------------------------ *
 *  WebXR
 * ------------------------------------------------------------------ */
async function enterVR() {
  readMenuDOM();
  audioUnlock();
  try {
    const session = await navigator.xr.requestSession("immersive-vr", { optionalFeatures: ["local-floor", "bounded-floor", "hand-tracking"] });
    await renderer.xr.setSession(session);
    try { if (session.supportedFrameRates?.includes?.(72) || session.supportedFrameRates) session.updateTargetFrameRate?.(72); } catch (_) {}
    $("menu").hidden = true; $("results").hidden = true; $("hud").hidden = true; $("big").hidden = true; $("cross").hidden = true;
    camera.remove(blaster.group);
    dressHands();
    G.phase = "menu"; G.paused = false;
    placeAtStart(G.level);
    setTimeout(() => showMenu(), 300);
    session.addEventListener("end", () => {
      hideAllPanels(); arc.visible = false; ring.visible = false;
      desktopBlaster(); blaster.laser.visible = false;
      G.phase = "menu"; G.paused = false; targets.clear();
      camera.position.set(0, 1.55, 0); camera.fov = 72; camera.updateProjectionMatrix();
      showMenu();
    });
  } catch (err) { alert(`Couldn't start VR: ${err.message}`); }
}
if (navigator.xr) {
  navigator.xr.isSessionSupported("immersive-vr").then(ok => {
    $("playVR").disabled = !ok;
    if (!ok) $("vrNote").textContent = "VR isn't available in this browser. On the Quest, open this page in the Quest browser.";
    else $("vrNote").textContent = "";
  }).catch(() => { $("playVR").disabled = true; });
} else { $("playVR").disabled = true; $("vrNote").textContent = location.protocol !== "https:" && !/localhost|127\.0\.0\.1/.test(location.hostname) ? "VR needs https (the headset server on :8443)." : "VR isn't available in this browser — play on screen below."; }
$("playVR").addEventListener("click", enterVR);

/* ------------------------------------------------------------------ *
 *  The simulated headset (tests): fake controllers with xr-standard
 *  gamepads drive vrInput exactly as the Quest's do.
 * ------------------------------------------------------------------ */
const BTN = { trigger: 0, grip: 1, stick: 3, a: 4, x: 4, b: 5, y: 5 };
const sim = {
  start(eye = 1.55) {
    if (SIM.on) return;
    SIM.eye = eye;
    const mk = hand => { const c = new THREE.Group(); c.userData.hand = hand; c.userData.source = { handedness: hand, gamepad: { buttons: [...Array(6)].map(() => ({ pressed: false, value: 0 })), axes: [0, 0, 0, 0] } }; rig.add(c); return c; };
    simCtrls = [mk("left"), mk("right")];
    SIM.on = true;
    camera.remove(blaster.group);
    dressHands();
    camera.fov = 90; camera.updateProjectionMatrix();
    $("menu").hidden = true; $("hud").hidden = true;
    applyRig();
    showMenu();
  },
  stop() {
    SIM.on = false; for (const c of simCtrls) rig.remove(c); simCtrls = [];
    hideAllPanels(); desktopBlaster(); camera.fov = 72; camera.updateProjectionMatrix(); G.phase = "menu"; showMenu();
  },
  pad: hand => handCtrl(hand)?.userData.source.gamepad,
  press(name, hand = ["x", "y"].includes(name) ? "left" : gunHand(), frames = 2) { SIM.holds.push({ hand, i: BTN[name], frames }); },
  stick(hand, x, y) { const a = sim.pad(hand).axes; a[2] = x; a[3] = y; },
  aim(point) { SIM.aimAt = point ? new THREE.Vector3().copy(point) : null; },
  look(yaw, pitch = 0) { look.yaw = yaw; look.pitch = pitch; },
  /* world point of a panel button (aim the laser at it) */
  buttonPoint(panel, id) {
    const p = panels[panel], b = p.buttons.find(x => x.id === id);
    if (!b) return null;
    p.mesh.updateMatrixWorld(true);
    const wM = p.mesh.geometry.parameters.width, hM = p.mesh.geometry.parameters.height;
    return p.mesh.localToWorld(new THREE.Vector3(((b.x + b.w / 2) / p.w - 0.5) * wM, (0.5 - (b.y + b.h / 2) / p.h) * hM, 0));
  },
};
function simPose() {
  rig.updateMatrixWorld(true);
  const cam = camera.getWorldPosition(new THREE.Vector3()), cq = camera.getWorldQuaternion(new THREE.Quaternion());
  const fwd = new THREE.Vector3(0, 0, -1).applyQuaternion(cq), up = new THREE.Vector3(0, 1, 0).applyQuaternion(cq), right = new THREE.Vector3(1, 0, 0).applyQuaternion(cq);
  const s = scaleNow();
  const place = (c, pos, q) => { c.position.copy(rig.worldToLocal(pos.clone())); c.quaternion.copy(rig.getWorldQuaternion(new THREE.Quaternion()).invert()).multiply(q); c.updateMatrixWorld(true); };
  const R = handCtrl(gunHand()), L = handCtrl(offHand());
  const side = gunHand() === "right" ? 1 : -1;
  if (R) {
    const rp = cam.clone().addScaledVector(right, 0.17 * s * side).addScaledVector(up, -0.2 * s).addScaledVector(fwd, 0.22 * s);
    const goal = SIM.aimAt || rp.clone().addScaledVector(fwd, 5);
    // aim so the MUZZLE ray (offset from the controller origin) passes through the goal
    const m = new THREE.Matrix4().lookAt(rp, goal, new THREE.Vector3(0, 1, 0));
    const q = new THREE.Quaternion().setFromRotationMatrix(m);
    place(R, rp.clone().addScaledVector(new THREE.Vector3(0, 1, 0).applyQuaternion(q), -0.045 * s), q);
  }
  if (L) place(L, cam.clone().addScaledVector(right, -0.2 * s * side).addScaledVector(up, -0.35 * s).addScaledVector(fwd, 0.25 * s), cq);
  for (const h of SIM.holds) { const b = sim.pad(h.hand)?.buttons[h.i]; if (b) { b.pressed = h.frames > 1; b.value = b.pressed ? 1 : 0; } h.frames--; }
  SIM.holds = SIM.holds.filter(h => h.frames > 0);
}

/* tests and tinkering from the console */
window.__game = {
  G, S, sim, startRound: () => startRound(), endRound, press, trySpawn, trySpawnStar, targets, fx, panels, LEVELS,
  fps: () => fps.value, info: () => renderer.info.render, feet, look, camera, rig, scene, renderer,
  spots: () => G.spots, setLevel: id => { G.level = LEVELS.find(l => l.id === id); S.room = id; placeAtStart(G.level); },
  setToy: on => { S.toy = on; applyRig(); }, hitNearest: () => { const t = targets.active()[0]; if (t) hitTarget(t); return t?.type; },
  aimAt: t => { const head = headPos(); const d = t.clone().sub(head); look.yaw = Math.atan2(-d.x, -d.z); look.pitch = Math.atan2(d.y, Math.hypot(d.x, d.z)); applyRig(); },
  fireDesktop, enterVR,
};

renderer.setAnimationLoop(frame);
boot();
