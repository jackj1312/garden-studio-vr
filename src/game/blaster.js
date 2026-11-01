import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

/* ------------------------------------------------------------------ *
 *  The toy foam blaster (chunky, bright, plainly a toy), its darts,
 *  the paint splats they leave, confetti and the floating "+25" score
 *  pops. The blaster carries a little screen on its back with the
 *  score and the time, so you never need to look anywhere else.
 *
 *  Axes: the barrel points down -Z from the grip, as a controller's
 *  target-ray space does, so it can sit straight in a controller.
 * ------------------------------------------------------------------ */

export function createBlaster() {
  const g = new THREE.Group();
  g.name = "blaster";
  const orange = new THREE.MeshStandardMaterial({ color: 0xff7a1a, roughness: 0.55 });
  const blue = new THREE.MeshStandardMaterial({ color: 0x2f7cf6, roughness: 0.5 });
  const yellow = new THREE.MeshStandardMaterial({ color: 0xffd23f, roughness: 0.5 });
  const grey = new THREE.MeshStandardMaterial({ color: 0x3a3f47, roughness: 0.7 });
  const body = new THREE.Mesh(new RoundedBoxGeometry(0.07, 0.085, 0.24, 3, 0.025), orange);
  body.position.set(0, 0.035, -0.08);
  const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.024, 0.024, 0.16, 14).rotateX(Math.PI / 2), blue);
  barrel.position.set(0, 0.045, -0.27);
  const muzzle = new THREE.Mesh(new THREE.TorusGeometry(0.026, 0.009, 8, 16), yellow);
  muzzle.position.set(0, 0.045, -0.35);
  const drum = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.06, 6).rotateX(Math.PI / 2), blue);
  drum.position.set(0, 0.09, -0.12);
  const grip = new THREE.Mesh(new RoundedBoxGeometry(0.045, 0.11, 0.055, 2, 0.018), yellow);
  grip.position.set(0, -0.035, 0.0); grip.rotation.x = -0.25;
  const guard = new THREE.Mesh(new THREE.TorusGeometry(0.03, 0.007, 6, 12, Math.PI), grey);
  guard.position.set(0, -0.01, -0.055); guard.rotation.set(0, Math.PI / 2, Math.PI);
  const trigger = new THREE.Mesh(new RoundedBoxGeometry(0.012, 0.03, 0.012, 1, 0.004), grey);
  trigger.position.set(0, -0.012, -0.05);
  const sight = new THREE.Mesh(new RoundedBoxGeometry(0.012, 0.02, 0.03, 1, 0.005), yellow);
  sight.position.set(0, 0.088, -0.27);
  // the screen on the back: score + time
  const sc = document.createElement("canvas"); sc.width = 256; sc.height = 128;
  const tex = new THREE.CanvasTexture(sc); tex.colorSpace = THREE.SRGBColorSpace;
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.075, 0.0375), new THREE.MeshBasicMaterial({ map: tex, toneMapped: false }));
  screen.position.set(0, 0.093, 0.03); screen.rotation.x = -1.05;
  const bezel = new THREE.Mesh(new RoundedBoxGeometry(0.085, 0.012, 0.05, 1, 0.004), grey);
  bezel.position.set(0, 0.083, 0.028); bezel.rotation.x = -1.05 + Math.PI / 2 - Math.PI / 2;
  bezel.rotation.x = 0.52;
  g.add(body, barrel, muzzle, drum, grip, guard, trigger, sight, bezel, screen);
  // the laser for menus
  const laserGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, -1)]);
  const laser = new THREE.Line(laserGeo, new THREE.LineBasicMaterial({ color: 0xffe066, transparent: true, opacity: 0.85 }));
  laser.position.set(0, 0.045, -0.36);
  laser.visible = false;
  g.add(laser);
  const muzzlePoint = new THREE.Object3D(); muzzlePoint.position.set(0, 0.045, -0.37); g.add(muzzlePoint);

  let last = "";
  function drawScreen(score, secs, combo) {
    const key = `${score}|${secs}|${combo}`;
    if (key === last) return;
    last = key;
    const c = sc.getContext("2d");
    c.fillStyle = "#0f2a1c"; c.fillRect(0, 0, 256, 128);
    c.fillStyle = "#7dffb0"; c.font = "bold 54px ui-monospace, Menlo, monospace"; c.textBaseline = "middle";
    c.textAlign = "left"; c.fillText(String(score).padStart(4, "0"), 12, 46);
    c.textAlign = "right"; c.fillStyle = secs <= 10 ? "#ff8080" : "#7dffb0"; c.fillText(secs >= 0 ? `${secs}` : "--", 244, 46);
    c.font = "bold 34px ui-monospace, Menlo, monospace"; c.textAlign = "left"; c.fillStyle = combo > 1 ? "#ffe066" : "#3f7a5a";
    c.fillText(combo > 1 ? `COMBO x${combo}` : "SCORE   TIME", 12, 100);
    tex.needsUpdate = true;
  }
  drawScreen(0, -1, 1);
  let kick = 0;
  function update(dt) {
    kick = Math.max(0, kick - dt * 8);
    body.position.z = -0.08 + kick * 0.02; barrel.position.z = -0.27 + kick * 0.03;
    trigger.position.z = -0.05 + kick * 0.008;
  }
  return { group: g, laser, muzzlePoint, drawScreen, update, recoil: () => { kick = 1; } };
}

/* a soft blob for the paint splats (white, tinted per splat) */
function splatTexture() {
  const c = document.createElement("canvas"); c.width = c.height = 128;
  const g = c.getContext("2d");
  g.fillStyle = "#fff";
  g.beginPath(); g.arc(64, 64, 34, 0, Math.PI * 2); g.fill();
  for (let i = 0; i < 11; i++) {
    const a = Math.random() * Math.PI * 2, r = 30 + Math.random() * 22, s = 6 + Math.random() * 12;
    g.beginPath(); g.arc(64 + Math.cos(a) * r, 64 + Math.sin(a) * r, s, 0, Math.PI * 2); g.fill();
    g.beginPath(); g.moveTo(64, 64); g.lineTo(64 + Math.cos(a - 0.2) * r, 64 + Math.sin(a - 0.2) * r); g.lineTo(64 + Math.cos(a + 0.2) * r, 64 + Math.sin(a + 0.2) * r); g.fill();
  }
  const t = new THREE.CanvasTexture(c); return t;
}
const SPLAT_COLOURS = [0xff4d6d, 0xffb703, 0x3a86ff, 0x8338ec, 0x06d6a0, 0xff7b00, 0xf72585];
const CONFETTI = [0xff4d6d, 0xffd23f, 0x3a86ff, 0x8338ec, 0x06d6a0, 0xffffff];

export function createEffects(scene) {
  /* darts */
  const dartGeo = new THREE.CylinderGeometry(0.011, 0.011, 0.065, 8).rotateX(Math.PI / 2);
  const tipGeo = new THREE.SphereGeometry(0.014, 8, 6).translate(0, 0, -0.038);
  const dartMats = [0x2f7cf6, 0x06d6a0, 0xff4d6d].map(c => new THREE.MeshStandardMaterial({ color: c, roughness: 0.8 }));
  const tipMat = new THREE.MeshStandardMaterial({ color: 0xff7a1a, roughness: 0.6 });
  const darts = [];
  for (let i = 0; i < 18; i++) {
    const d = new THREE.Group();
    d.add(new THREE.Mesh(dartGeo, dartMats[i % 3]), new THREE.Mesh(tipGeo, tipMat));
    d.visible = false; scene.add(d);
    darts.push({ obj: d, vel: new THREE.Vector3(), state: "free", t: 0, scale: 1 });
  }
  function fire(from, dir, speed, scale) {
    const d = darts.find(x => x.state === "free") || darts.reduce((a, b) => a.t > b.t ? a : b);
    d.state = "fly"; d.t = 0; d.scale = scale;
    d.obj.position.copy(from); d.obj.scale.setScalar(scale);
    d.vel.copy(dir).multiplyScalar(speed);
    d.obj.visible = true;
    d.obj.lookAt(from.clone().sub(dir));
    return d;
  }
  function stick(d, at, normal) {
    d.state = "stuck"; d.t = 0;
    d.obj.position.copy(at).addScaledVector(normal, 0.03 * d.scale);
  }

  /* splats */
  const splatTex = [splatTexture(), splatTexture(), splatTexture()];
  const splatGeo = new THREE.PlaneGeometry(1, 1);
  const splats = [];
  for (let i = 0; i < 24; i++) {
    const m = new THREE.Mesh(splatGeo, new THREE.MeshBasicMaterial({ map: splatTex[i % 3], transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4, toneMapped: false }));
    m.visible = false; m.renderOrder = 1; scene.add(m);
    splats.push({ m, t: 0, life: 0 });
  }
  let si = 0;
  const up = new THREE.Vector3(0, 1, 0), q = new THREE.Quaternion();
  function splat(at, normal, size) {
    const s = splats[si++ % splats.length];
    s.m.position.copy(at).addScaledVector(normal, 0.004);
    q.setFromUnitVectors(new THREE.Vector3(0, 0, 1), normal);
    s.m.quaternion.copy(q);
    s.m.rotateZ(Math.random() * Math.PI * 2);
    s.m.scale.setScalar(size * (0.8 + Math.random() * 0.5));
    s.m.material.color.setHex(SPLAT_COLOURS[(Math.random() * SPLAT_COLOURS.length) | 0]);
    s.m.material.opacity = 0.95;
    s.m.visible = true; s.t = 0; s.life = 4.5;
  }

  /* confetti: one instanced mesh */
  const N = 260;
  const conf = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.03, 0.018), new THREE.MeshBasicMaterial({ side: THREE.DoubleSide, toneMapped: false }), N);
  conf.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  conf.frustumCulled = false;
  const cp = new Float32Array(N * 3), cv = new Float32Array(N * 3), cl = new Float32Array(N), cs = new Float32Array(N), cr = new Float32Array(N * 2);
  const col = new THREE.Color(), m4 = new THREE.Matrix4(), e = new THREE.Euler(), qq = new THREE.Quaternion(), pos = new THREE.Vector3(), scl = new THREE.Vector3();
  const zero = new THREE.Matrix4().makeScale(0, 0, 0);
  for (let i = 0; i < N; i++) { conf.setMatrixAt(i, zero); conf.setColorAt(i, col.setHex(CONFETTI[i % CONFETTI.length])); }
  scene.add(conf);
  let ci = 0, confAlive = 0;
  function burst(at, scale, n = 40, colourHex = null) {
    for (let k = 0; k < n; k++) {
      const i = ci++ % N;
      cp[i * 3] = at.x; cp[i * 3 + 1] = at.y; cp[i * 3 + 2] = at.z;
      const a = Math.random() * Math.PI * 2, u = Math.random() * 2 - 1, sp = (1.2 + Math.random() * 2.2) * Math.max(0.35, scale);
      const r = Math.sqrt(1 - u * u);
      cv[i * 3] = Math.cos(a) * r * sp; cv[i * 3 + 1] = Math.abs(u) * sp + 1.2 * Math.max(0.35, scale); cv[i * 3 + 2] = Math.sin(a) * r * sp;
      cl[i] = 0.9 + Math.random() * 0.6; cs[i] = scale; cr[i * 2] = Math.random() * 6; cr[i * 2 + 1] = Math.random() * 6;
      conf.setColorAt(i, col.setHex(colourHex && Math.random() < 0.5 ? colourHex : CONFETTI[(Math.random() * CONFETTI.length) | 0]));
    }
    conf.instanceColor.needsUpdate = true;
    confAlive = 1.6;
  }

  /* score pops: sprites with a canvas each */
  const pops = [];
  for (let i = 0; i < 8; i++) {
    const c = document.createElement("canvas"); c.width = 256; c.height = 128;
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, toneMapped: false }));
    sp.visible = false; sp.renderOrder = 10; scene.add(sp);
    pops.push({ sp, c, tex, t: 0, base: new THREE.Vector3(), size: 1 });
  }
  let pi = 0;
  function pop(at, text, colour = "#ffffff", size = 1) {
    const p = pops[pi++ % pops.length];
    const g = p.c.getContext("2d");
    g.clearRect(0, 0, 256, 128);
    g.font = "900 64px system-ui, -apple-system, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle";
    g.lineWidth = 12; g.strokeStyle = "rgba(20,20,40,0.85)"; g.strokeText(text, 128, 64);
    g.fillStyle = colour; g.fillText(text, 128, 64);
    p.tex.needsUpdate = true;
    p.base.copy(at); p.t = 0; p.size = size;
    p.sp.visible = true;
  }

  function update(dt) {
    for (const d of darts) {
      if (d.state === "stuck") { d.t += dt; if (d.t > 1.4) { d.state = "free"; d.obj.visible = false; } }
    }
    for (const s of splats) {
      if (!s.m.visible) continue;
      s.t += dt;
      if (s.t > s.life - 1.5) s.m.material.opacity = Math.max(0, 0.95 * (s.life - s.t) / 1.5);
      if (s.t >= s.life) s.m.visible = false;
    }
    if (confAlive > 0) {
      confAlive -= dt;
      for (let i = 0; i < N; i++) {
        if (cl[i] <= 0) continue;
        cl[i] -= dt;
        if (cl[i] <= 0) { conf.setMatrixAt(i, zero); continue; }
        const s = cs[i];
        cv[i * 3 + 1] -= 4.5 * Math.max(0.35, s) * dt;
        cv[i * 3] *= 0.97; cv[i * 3 + 2] *= 0.97; if (cv[i * 3 + 1] < -1.2 * s) cv[i * 3 + 1] = -1.2 * s;
        cp[i * 3] += cv[i * 3] * dt; cp[i * 3 + 1] += cv[i * 3 + 1] * dt; cp[i * 3 + 2] += cv[i * 3 + 2] * dt;
        cr[i * 2] += dt * 9; cr[i * 2 + 1] += dt * 7;
        pos.set(cp[i * 3], cp[i * 3 + 1], cp[i * 3 + 2]);
        qq.setFromEuler(e.set(cr[i * 2], cr[i * 2 + 1], 0));
        scl.setScalar(Math.max(0.35, s) * Math.min(1, cl[i] * 3));
        conf.setMatrixAt(i, m4.compose(pos, qq, scl));
      }
      conf.instanceMatrix.needsUpdate = true;
    }
    for (const p of pops) {
      if (!p.sp.visible) continue;
      p.t += dt;
      const k = p.t / 0.95;
      p.sp.position.copy(p.base); p.sp.position.y += k * 0.45 * p.size;
      const s = p.size * (k < 0.15 ? k / 0.15 : 1) * 0.42;
      p.sp.scale.set(s, s / 2, 1);
      p.sp.material.opacity = k > 0.6 ? Math.max(0, (1 - k) / 0.4) : 1;
      if (k >= 1) p.sp.visible = false;
    }
  }
  function clear() {
    for (const d of darts) { d.state = "free"; d.obj.visible = false; }
    for (const s of splats) s.m.visible = false;
  }
  return { darts, fire, stick, splat, burst, pop, update, clear };
}
