import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

/* ------------------------------------------------------------------ *
 *  The targets: balloons, spinning discs, cheeky robots and the bonus
 *  gold star. Each is a small pooled group made of shared geometry and
 *  a handful of shared materials (cheap on the Quest). A target has a
 *  short life: it pops in, does its thing, and leaves if nobody hits
 *  it. Hit spheres are a little bigger than the target (aim help).
 *
 *  Behaviours
 *    balloon  rises from a floor or ledge spot, or floats in the air,
 *             bobbing; drifts up and away when its time is up
 *    disc     flips up on its stand and spins (edge-on = harder)
 *    robot    peeks round a door frame (from the far side), or springs
 *             up on a worktop / the sofa / a bed; waves, blinks, faces you
 *    star     zips across the room between two places; +50 and +3 s
 * ------------------------------------------------------------------ */

const ease = t => 1 - Math.pow(1 - t, 3);
const back = t => { const c = 1.9; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); };
const BALLOON_COLOURS = [0xff4d6d, 0xffb703, 0x3a86ff, 0x8338ec, 0x06d6a0, 0xff7b00];

function discTexture() {
  const c = document.createElement("canvas"); c.width = c.height = 256;
  const g = c.getContext("2d");
  const rings = ["#ff3b3b", "#ffffff", "#2f7cf6", "#ffffff", "#ff3b3b", "#ffd23f"];
  rings.forEach((col, i) => { g.fillStyle = col; g.beginPath(); g.arc(128, 128, 128 - i * 21, 0, Math.PI * 2); g.fill(); });
  g.fillStyle = "#1d1d1d";                                // a smiley in the bull's-eye
  g.beginPath(); g.arc(116, 120, 4, 0, Math.PI * 2); g.arc(140, 120, 4, 0, Math.PI * 2); g.fill();
  g.lineWidth = 4; g.strokeStyle = "#1d1d1d"; g.beginPath(); g.arc(128, 128, 12, 0.2 * Math.PI, 0.8 * Math.PI); g.stroke();
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

function starShape(r0, r1, n = 5) {
  const s = new THREE.Shape();
  for (let i = 0; i <= n * 2; i++) {
    const a = i / (n * 2) * Math.PI * 2 + Math.PI / 2, r = i % 2 ? r1 : r0;
    i ? s.lineTo(Math.cos(a) * r, Math.sin(a) * r) : s.moveTo(Math.cos(a) * r, Math.sin(a) * r);
  }
  return s;
}

export function createTargetKit() {
  const M = {
    balloon: BALLOON_COLOURS.map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.25, metalness: 0.05 })),
    string: new THREE.LineBasicMaterial({ color: 0xffffff }),
    disc: new THREE.MeshStandardMaterial({ map: discTexture(), roughness: 0.6 }),
    rim: new THREE.MeshStandardMaterial({ color: 0xffd23f, roughness: 0.5 }),
    stand: new THREE.MeshStandardMaterial({ color: 0x555b66, roughness: 0.6 }),
    robotBody: new THREE.MeshStandardMaterial({ color: 0x2ec4b6, roughness: 0.45, metalness: 0.1 }),
    robotHead: new THREE.MeshStandardMaterial({ color: 0xe9eef3, roughness: 0.4, metalness: 0.15 }),
    robotFace: new THREE.MeshStandardMaterial({ color: 0x223040, roughness: 0.3 }),
    eye: new THREE.MeshBasicMaterial({ color: 0x9ff7ff }),
    pupil: new THREE.MeshBasicMaterial({ color: 0x0b1a22 }),
    bulb: new THREE.MeshStandardMaterial({ color: 0xff4d6d, emissive: 0xff2244, emissiveIntensity: 1.2 }),
    cheek: new THREE.MeshBasicMaterial({ color: 0xff8fab }),
    star: new THREE.MeshStandardMaterial({ color: 0xffd23f, emissive: 0xffa400, emissiveIntensity: 0.9, roughness: 0.3, metalness: 0.3 }),
    halo: new THREE.MeshBasicMaterial({ color: 0xfff1a8, transparent: true, opacity: 0.35, depthWrite: false }),
  };
  const pts = [];
  for (let i = 0; i <= 12; i++) {
    const t = i / 12, y = -0.16 + t * 0.34;
    const r = Math.sin(Math.pow(t, 0.8) * Math.PI) * 0.13 * (t < 0.15 ? 0.7 + t * 2 : 1);
    pts.push(new THREE.Vector2(Math.max(0.004, r), y));
  }
  const G = {
    balloon: new THREE.LatheGeometry(pts, 14),
    knot: new THREE.ConeGeometry(0.018, 0.03, 6).translate(0, -0.175, 0),
    disc: new THREE.CylinderGeometry(0.2, 0.2, 0.025, 28).rotateX(Math.PI / 2),
    discFace: new THREE.CircleGeometry(0.195, 28),
    post: new THREE.CylinderGeometry(0.014, 0.014, 0.3, 6).translate(0, 0.15, 0),
    base: new THREE.CylinderGeometry(0.09, 0.11, 0.03, 12).translate(0, 0.015, 0),
    rBody: new RoundedBoxGeometry(0.32, 0.3, 0.22, 3, 0.06),
    rHead: new RoundedBoxGeometry(0.36, 0.27, 0.26, 3, 0.08),
    rFace: new RoundedBoxGeometry(0.29, 0.18, 0.02, 2, 0.008),
    eye: new THREE.SphereGeometry(0.042, 12, 8),
    pupil: new THREE.SphereGeometry(0.02, 8, 6),
    antenna: new THREE.CylinderGeometry(0.008, 0.008, 0.12, 5).translate(0, 0.06, 0),
    bulb: new THREE.SphereGeometry(0.032, 10, 8),
    arm: new THREE.CapsuleGeometry(0.03, 0.14, 3, 6).translate(0, -0.08, 0),
    leg: new THREE.CapsuleGeometry(0.035, 0.08, 3, 6),
    cheek: new THREE.CircleGeometry(0.02, 10),
    star: new THREE.ExtrudeGeometry(starShape(0.17, 0.075), { depth: 0.05, bevelEnabled: true, bevelThickness: 0.015, bevelSize: 0.012, bevelSegments: 2 }).translate(0, 0, -0.025),
    halo: new THREE.CircleGeometry(0.26, 24),
  };

  function balloon() {
    const g = new THREE.Group();
    const body = new THREE.Mesh(G.balloon, M.balloon[0]);
    const knot = new THREE.Mesh(G.knot, M.balloon[0]);
    const sp = new Float32Array(8 * 3);
    const sg = new THREE.BufferGeometry(); sg.setAttribute("position", new THREE.BufferAttribute(sp, 3));
    const string = new THREE.Line(sg, M.string);
    string.frustumCulled = false;
    g.add(body, knot, string);
    g.userData = { body, knot, string, sp };
    return g;
  }
  function disc() {
    const g = new THREE.Group();
    const spin = new THREE.Group(); spin.position.y = 0.3 + 0.2;
    const rim = new THREE.Mesh(G.disc, M.rim);
    const f1 = new THREE.Mesh(G.discFace, M.disc); f1.position.z = 0.0135;
    const f2 = new THREE.Mesh(G.discFace, M.disc); f2.position.z = -0.0135; f2.rotation.y = Math.PI;
    spin.add(rim, f1, f2);
    g.add(new THREE.Mesh(G.post, M.stand), new THREE.Mesh(G.base, M.stand), spin);
    g.userData = { spin };
    return g;
  }
  function robot() {
    const g = new THREE.Group();
    const bob = new THREE.Group(); g.add(bob);
    const body = new THREE.Mesh(G.rBody, M.robotBody); body.position.y = 0.27;
    const head = new THREE.Group(); head.position.y = 0.57;
    head.add(new THREE.Mesh(G.rHead, M.robotHead));
    const face = new THREE.Mesh(G.rFace, M.robotFace); face.position.z = 0.125; head.add(face);
    const eyes = [];
    for (const x of [-0.065, 0.065]) {
      const e = new THREE.Mesh(G.eye, M.eye); e.position.set(x, 0.01, 0.13); e.scale.z = 0.5;
      const p = new THREE.Mesh(G.pupil, M.pupil); p.position.set(0, 0, 0.03); e.add(p);
      head.add(e); eyes.push(e);
    }
    for (const x of [-0.12, 0.12]) { const c = new THREE.Mesh(G.cheek, M.cheek); c.position.set(x, -0.05, 0.137); head.add(c); }
    const ant = new THREE.Mesh(G.antenna, M.stand); ant.position.y = 0.13; head.add(ant);
    const bulb = new THREE.Mesh(G.bulb, M.bulb); bulb.position.y = 0.26; head.add(bulb);
    const armL = new THREE.Mesh(G.arm, M.robotBody); armL.position.set(-0.19, 0.38, 0);
    const armR = new THREE.Mesh(G.arm, M.robotBody); armR.position.set(0.19, 0.38, 0);
    const legL = new THREE.Mesh(G.leg, M.stand); legL.position.set(-0.08, 0.07, 0);
    const legR = new THREE.Mesh(G.leg, M.stand); legR.position.set(0.08, 0.07, 0);
    bob.add(body, head, armL, armR, legL, legR);
    g.userData = { bob, head, eyes, armL, armR, bulb };
    return g;
  }
  function star() {
    const g = new THREE.Group();
    const s = new THREE.Mesh(G.star, M.star);
    const h = new THREE.Mesh(G.halo, M.halo); h.renderOrder = 3;
    g.add(s, h);
    g.userData = { s, h };
    return g;
  }
  return { balloon, disc, robot, star, M };
}

/* one live target (pooled objects are reused) */
export function createTargets(scene, kit) {
  const pools = { balloon: [], disc: [], robot: [], star: [] };
  const live = [];
  const tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3();

  function take(type) {
    const free = pools[type].find(o => !o.visible);
    if (free) return free;
    const o = kit[type]();
    o.visible = false;
    scene.add(o);
    pools[type].push(o);
    return o;
  }

  /* spec: {type, mode, p (Vector3), floor, life, scale, door?, path?, colour?, look (player head getter)} */
  function spawn(spec) {
    const obj = take(spec.type);
    obj.visible = true;
    obj.position.copy(spec.p);
    obj.rotation.set(0, 0, 0);
    obj.scale.setScalar(0.001);
    const t = { ...spec, obj, age: 0, state: "in", out: 0, hitAt: 0, centre: new THREE.Vector3(), radius: 0.2 * spec.scale, seed: Math.random() * 10 };
    if (spec.type === "balloon") {
      const m = kit.M.balloon[(Math.random() * kit.M.balloon.length) | 0];
      obj.userData.body.material = m; obj.userData.knot.material = m;
      t.radius = 0.16 * spec.scale;
      t.base = spec.p.clone();
      t.rise = spec.mode === "rise" ? 0 : 1;
      t.ceiling = spec.ceiling ?? spec.p.y + 1.2;
    }
    if (spec.type === "robot" && spec.mode === "peek") {
      const d = spec.door;
      t.hidePos = d.hide.clone(); t.showPos = d.show.clone();
      obj.position.copy(t.hidePos);
      obj.scale.setScalar(spec.scale);
      t.radius = 0.24 * spec.scale;
    }
    if (spec.type === "robot" && spec.mode !== "peek") t.radius = 0.25 * spec.scale;
    if (spec.type === "star") { t.radius = 0.22 * spec.scale; t.from = spec.path[0].clone(); t.to = spec.path[1].clone(); }
    if (spec.type === "disc") t.radius = 0.22 * spec.scale;
    live.push(t);
    centreOf(t);
    return t;
  }

  function centreOf(t) {
    const o = t.obj, s = t.scale;
    if (t.type === "balloon") return t.centre.copy(o.position).add(tmp.set(0, 0.02 * s, 0));
    if (t.type === "disc") return t.centre.copy(o.position).add(tmp.set(0, 0.5 * s * o.scale.y / Math.max(1e-3, s), 0));
    if (t.type === "robot") return t.centre.copy(o.position).add(tmp.set(0, 0.45 * s, 0));
    return t.centre.copy(o.position);
  }

  function update(dt, head, time) {
    for (let i = live.length - 1; i >= 0; i--) {
      const t = live[i], o = t.obj, s = t.scale, u = o.userData;
      t.age += dt;
      if (t.state === "in" && t.age > t.life) { t.state = "out"; t.out = 0; }
      if (t.state === "hit") {
        t.out += dt;
        const k = t.out / 0.32;
        if (t.type === "robot") { o.rotation.y += dt * 22; o.scale.setScalar(s * Math.max(0.001, 1 + 0.3 * Math.sin(k * Math.PI) - k)); }
        else o.scale.setScalar(s * Math.max(0.001, (1 + 0.5 * k) * (1 - k)));
        if (k >= 1) { o.visible = false; live.splice(i, 1); }
        continue;
      }
      const leaving = t.state === "out";
      if (leaving) t.out += dt;
      const appear = Math.min(1, t.age / 0.35);
      if (t.type === "balloon") {
        let sc = back(appear);
        if (leaving) { sc *= Math.max(0, 1 - t.out / 0.8); t.base.y += dt * 1.2 * s; }
        else if (t.rise < 1) t.base.y = Math.min(t.ceiling, t.base.y + dt * 0.22 * s);
        o.scale.setScalar(Math.max(0.001, s * sc));
        o.position.set(t.base.x + Math.sin(time * 1.3 + t.seed) * 0.05 * s, t.base.y + Math.sin(time * 2.1 + t.seed) * 0.04 * s, t.base.z + Math.cos(time * 1.1 + t.seed) * 0.05 * s);
        o.rotation.z = Math.sin(time * 1.7 + t.seed) * 0.12;
        const sp = u.sp;                                     // the string wiggles below
        for (let k = 0; k < 8; k++) { const f = k / 7; sp[k * 3] = Math.sin(time * 3 + f * 4 + t.seed) * 0.02 * f; sp[k * 3 + 1] = -0.19 - f * 0.32; sp[k * 3 + 2] = Math.cos(time * 2.5 + f * 3 + t.seed) * 0.02 * f; }
        u.string.geometry.attributes.position.needsUpdate = true;
        if (leaving && t.out > 0.8) { o.visible = false; live.splice(i, 1); }
      } else if (t.type === "disc") {
        let k = ease(appear);
        if (leaving) k = Math.max(0, 1 - t.out / 0.4);
        o.scale.set(s, Math.max(0.001, s * k), s);
        u.spin.rotation.y += dt * (t.spin || 1.4);
        u.spin.rotation.x = 0;
        if (leaving && t.out > 0.4) { o.visible = false; live.splice(i, 1); }
      } else if (t.type === "robot") {
        tmp.subVectors(head, o.position); tmp.y = 0;
        const yaw = Math.atan2(tmp.x, tmp.z);
        o.rotation.y += ((yaw - o.rotation.y + Math.PI * 3) % (Math.PI * 2) - Math.PI) * Math.min(1, dt * 8);
        u.armR.rotation.z = 2.4 + Math.sin(time * 9 + t.seed) * 0.5;          // waving
        u.armL.rotation.z = -0.25 + Math.sin(time * 4 + t.seed) * 0.15;
        u.bob.position.y = Math.abs(Math.sin(time * 6 + t.seed)) * 0.025;
        u.head.rotation.z = Math.sin(time * 3 + t.seed) * 0.15;
        const blink = (time + t.seed) % 3 < 0.12 ? 0.1 : 1;
        for (const e of u.eyes) e.scale.y = blink;
        u.bulb.scale.setScalar(1 + 0.25 * Math.sin(time * 10));
        if (t.mode === "peek") {
          const k = leaving ? Math.max(0, 1 - t.out / 0.3) : ease(appear);
          o.position.lerpVectors(t.hidePos, t.showPos, k);
          o.rotation.z = (1 - k) * 0.25 * Math.sign(t.door.lean || 1);
          if (leaving && t.out > 0.3) { o.visible = false; live.splice(i, 1); }
        } else {
          const k = leaving ? Math.max(0, 1 - t.out / 0.3) : back(appear);
          o.scale.set(s, Math.max(0.001, s * k), s);
          if (leaving && t.out > 0.3) { o.visible = false; live.splice(i, 1); }
        }
      } else if (t.type === "star") {
        const k = Math.min(1, t.age / t.life);
        o.position.lerpVectors(t.from, t.to, k);
        o.position.y += Math.sin(k * Math.PI * 3) * 0.15 * s;
        u.s.rotation.y += dt * 6;
        o.lookAt(tmp2.copy(head));
        u.h.scale.setScalar(1 + 0.15 * Math.sin(time * 12));
        o.scale.setScalar(s * back(appear) * (k > 0.92 ? Math.max(0.001, (1 - k) / 0.08) : 1));
        if (k >= 1) { o.visible = false; live.splice(i, 1); }
      }
      centreOf(t);
    }
  }

  function hit(t) { t.state = "hit"; t.out = 0; t.hitAt = t.age; }
  function clear() { for (const t of live) t.obj.visible = false; live.length = 0; }
  const active = () => live.filter(t => t.state !== "hit");

  return { spawn, update, hit, clear, live, active, centreOf };
}
