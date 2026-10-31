import * as THREE from "three";
import { XRControllerModelFactory } from "three/addons/webxr/XRControllerModelFactory.js";
import { XRHandModelFactory } from "three/addons/webxr/XRHandModelFactory.js";

/* ------------------------------------------------------------------ *
 *  Presence: the things that make a headset scene feel like a place
 *  rather than a picture, none of which show up in a screenshot.
 * ------------------------------------------------------------------ */

/* A fade to black on the camera. Snapping instantly from the room into
   the garden is jarring; a second of black with a soft fade-in reads as
   arriving somewhere. Also covers stage jumps if we ever want it to. */
export function createFade(camera) {
  const mat = new THREE.MeshBasicMaterial({
    color: 0x000000, transparent: true, opacity: 0,
    depthTest: false, depthWrite: false, toneMapped: false
  });
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(6, 6), mat);
  quad.position.z = -0.45;
  quad.renderOrder = 1000;
  quad.visible = false;
  camera.add(quad);

  let target = 0, rate = 1;
  return {
    black() { mat.opacity = 1; target = 1; quad.visible = true; },
    to(opacity, seconds = 0.8) {
      target = opacity;
      rate = 1 / Math.max(0.05, seconds);
      quad.visible = true;
    },
    update(dt) {
      if (!quad.visible) return;
      const d = target - mat.opacity;
      const step = rate * dt;
      mat.opacity = Math.abs(d) <= step ? target : mat.opacity + Math.sign(d) * step;
      if (target === 0 && mat.opacity <= 0.001) { mat.opacity = 0; quad.visible = false; }
    }
  };
}

/* Real controller models in place of grey boxes. Your hands are the one
   thing you look at constantly in VR, and a box where a controller
   should be undercuts everything else. Profiles are fetched from the
   WebXR input-profiles CDN on first connect; if that fails the grips
   stay empty rather than breaking the session. */
export function attachControllerModels(renderer, player) {
  const factory = new XRControllerModelFactory();
  const grips = [];
  for (let i = 0; i < 2; i++) {
    const grip = renderer.xr.getControllerGrip(i);
    try {
      grip.add(factory.createControllerModel(grip));
    } catch (err) {
      console.warn("controller model unavailable:", err);
    }
    player.add(grip);
    grips.push(grip);
  }
  return grips;
}

/* The shadow camera follows the player. One fixed 28 m frustum across a
   1024 map is ~2.7 cm per texel: blobby everywhere. A tighter frustum
   that travels with you keeps the shadow of the fence post at your feet
   crisp, which is what you actually look at. Snapping the target to the
   texel grid stops the edges crawling as you walk. */
export function createShadowFollow(sun, { desktopExtent = 14, vrExtent = 9 } = {}) {
  const offset = new THREE.Vector3();
  const head = new THREE.Vector3();
  let extent = desktopExtent;

  function setExtent(e) {
    extent = e;
    const c = sun.shadow.camera;
    c.left = -e; c.right = e; c.top = e; c.bottom = -e;
    c.updateProjectionMatrix();
  }
  setExtent(desktopExtent);

  return {
    setVR(on) { setExtent(on ? vrExtent : desktopExtent); },
    update(camera) {
      camera.getWorldPosition(head);
      offset.copy(sun.position).sub(sun.target.position);
      const texel = (extent * 2) / sun.shadow.mapSize.x;
      const tx = Math.round(head.x / texel) * texel;
      const tz = Math.round(head.z / texel) * texel;
      sun.target.position.set(tx, 0, tz);
      sun.position.copy(sun.target.position).add(offset);
    }
  };
}


/* Tracked hands, when the headset offers them. Seeing your own hands is
   the body-ownership half of presence; controllers alone are a tool,
   hands are you. The mesh model is skinned to the 25 tracked joints. */
export function attachHandModels(renderer, player) {
  const factory = new XRHandModelFactory();
  const hands = [];
  for (let i = 0; i < 2; i++) {
    const hand = renderer.xr.getHand(i);
    try {
      hand.add(factory.createHandModel(hand, "mesh"));
    } catch (err) {
      console.warn("hand model unavailable:", err);
    }
    player.add(hand);
    hands.push(hand);
  }
  return hands;
}

/* Soft contact shadows under the player and each hand. The feet are not
   tracked, so this is a blob at the head's floor position; it is what
   stops you feeling like a floating camera. */
function blobTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const x = c.getContext("2d");
  const g = x.createRadialGradient(64, 64, 4, 64, 64, 62);
  g.addColorStop(0, "rgba(0,0,0,0.55)");
  g.addColorStop(0.55, "rgba(0,0,0,0.28)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  x.fillStyle = g;
  x.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}

export function createBlobShadows(scene) {
  const tex = blobTexture();
  const make = size => {
    const m = new THREE.Mesh(
      new THREE.PlaneGeometry(size, size).rotateX(-Math.PI / 2),
      new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, toneMapped: false })
    );
    m.renderOrder = 5;
    m.visible = false;
    scene.add(m);
    return m;
  };
  const body = make(0.75);
  const handBlobs = [make(0.32), make(0.32)];
  const p = new THREE.Vector3();
  return {
    update(camera, grips, presenting) {
      camera.getWorldPosition(p);
      body.position.set(p.x, 0.012, p.z);
      body.visible = true;
      grips.forEach((g, i) => {
        const b = handBlobs[i];
        if (!presenting || !g.visible) { b.visible = false; return; }
        g.getWorldPosition(p);
        const h = Math.max(0, Math.min(1.6, p.y));
        b.position.set(p.x, 0.014, p.z);
        b.material.opacity = 0.9 * (1 - h / 1.8);
        const s = 0.6 + h * 0.5;
        b.scale.set(s, 1, s);
        b.visible = b.material.opacity > 0.05;
      });
    }
  };
}

/* A short buzz on both controllers. Zero cost, and the cheapest way to
   make the world feel like it answers back. */
export function hapticPulse(controllers, intensity = 0.3, ms = 40) {
  for (const c of controllers) {
    const gp = c?.userData?.source?.gamepad;
    const act = gp?.hapticActuators?.[0];
    try { act?.pulse?.(intensity, ms); } catch (_) {}
  }
}
