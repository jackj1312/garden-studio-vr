import * as THREE from "three";
import { Pass, FullScreenQuad } from "three/addons/postprocessing/Pass.js";

/* ------------------------------------------------------------------ *
 *  Camera motion blur (Jack, 1 Nov: "motion blur instead of the dark
 *  comfort vignette, like in the Architecture & Design video" — that
 *  app's Unreal camera motion blur smears the frame along the screen
 *  motion on fast orbits and turns, most at the edges).
 *
 *  One shader for every place it runs. For each pixel it rebuilds the
 *  view ray, puts a point on it at a fixed distance (2.5 m: no depth
 *  buffer is needed, which keeps it cheap and lets it run in the
 *  headset), projects that point with LAST frame's camera and smears
 *  the colour along the difference (8 taps). A turn therefore blurs
 *  sideways, walking forward blurs outwards from the centre, and a
 *  still camera costs one texture read.
 *
 *  Screen: a pass in the existing composer (after GTAO, before the
 *  tone-mapping OutputPass); all camera motion counts.
 *  Headset (three r185 has no post-processing in WebXR): only while
 *  you turn or move on the sticks, each eye is drawn into an offscreen
 *  target at 70 % of the eye-buffer size, then this shader writes the
 *  full-size eye buffer from it, smearing only the outer part of each
 *  eye (the middle stays sharp). Only the rig's movement counts, never
 *  your real head movement (blurring that is what makes people ill).
 *  At rest the headset renders exactly as before, at no cost.
 * ------------------------------------------------------------------ */

const TAPS = 8;
const VERT = /* glsl */`void main() { gl_Position = vec4(position.xy, 0.0, 1.0); }`;
const FRAG = /* glsl */`
uniform sampler2D tColor;
uniform vec2 uOut;            // output size in pixels (what gl_FragCoord counts)
uniform int uEyes;
uniform vec4 uRect[2];        // each eye's rectangle in output pixels
uniform mat4 uInvVP[2];       // this frame: clip -> world
uniform mat4 uPrevVP[2];      // last frame: world -> clip
uniform vec3 uCam[2];         // this frame's eye position
uniform float uAmount;        // fade (0..1) x shutter (frames of exposure)
uniform float uMaxLen;        // the longest smear, as a fraction of the eye's width
uniform vec2 uEdge;           // the smear grows from radius uEdge.x to uEdge.y (eye-centred, ndc): the middle stays sharp
uniform float uSideways;      // 1: horizontal smear only (screens)
uniform float uDepth;
void main() {
  vec2 fc = gl_FragCoord.xy;
  bool right = uEyes > 1 && fc.x >= uRect[1].x;
  vec4 r = right ? uRect[1] : uRect[0];
  vec2 l = (fc - r.xy) / r.zw;
  vec2 ndc = l * 2.0 - 1.0;
  vec4 f = (right ? uInvVP[1] : uInvVP[0]) * vec4(ndc, 1.0, 1.0);
  vec3 cam = right ? uCam[1] : uCam[0];
  vec3 dir = normalize(f.xyz / f.w - cam);
  vec4 p = (right ? uPrevVP[1] : uPrevVP[0]) * vec4(cam + dir * uDepth, 1.0);
  vec2 v = p.w > 0.0 ? (ndc - p.xy / p.w) * 0.5 * uAmount : vec2(0.0);
  float len = length(v * vec2(1.0, r.w / r.z));
  if (len > uMaxLen) v *= uMaxLen / len;
  v *= smoothstep(uEdge.x, uEdge.y, length(ndc));
  v.y *= 1.0 - uSideways;
  vec4 c;
  if (length(v * r.zw) < 0.75) c = texture2D(tColor, fc / uOut);
  else {
    c = vec4(0.0);
    for (int i = 0; i < ${TAPS}; i++) {
      vec2 q = clamp(l + v * ((float(i) + 0.5) / ${TAPS}.0 - 0.5), vec2(0.001), vec2(0.999));
      c += texture2D(tColor, (r.xy + q * r.zw) / uOut);
    }
    c /= ${TAPS}.0;
  }
  gl_FragColor = c;
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

function makeMaterial() {
  return new THREE.ShaderMaterial({
    name: "CameraMotionBlur",
    uniforms: {
      tColor: { value: null }, uOut: { value: new THREE.Vector2(1, 1) }, uEyes: { value: 1 },
      uRect: { value: [new THREE.Vector4(), new THREE.Vector4()] },
      uInvVP: { value: [new THREE.Matrix4(), new THREE.Matrix4()] },
      uPrevVP: { value: [new THREE.Matrix4(), new THREE.Matrix4()] },
      uCam: { value: [new THREE.Vector3(), new THREE.Vector3()] },
      uAmount: { value: 0 }, uMaxLen: { value: 0.02 }, uEdge: { value: new THREE.Vector2(0.7, 1.15) }, uSideways: { value: 0 }, uDepth: { value: 2.5 },
    },
    vertexShader: VERT, fragmentShader: FRAG, depthTest: false, depthWrite: false,
  });
}

const _m = new THREE.Matrix4(), _m2 = new THREE.Matrix4();
/* set eye i's matrices: invVP from this frame's camera; prevVP from last frame's world matrix */
function setEye(u, i, cam, prevWorld) {
  u.uInvVP.value[i].multiplyMatrices(cam.matrixWorld, cam.projectionMatrixInverse);
  u.uPrevVP.value[i].multiplyMatrices(cam.projectionMatrix, _m.copy(prevWorld).invert());
  u.uCam.value[i].setFromMatrixPosition(cam.matrixWorld);
}

/* the screen: a composer pass. The camera's own motion between frames drives it; `amount` (0..1) fades it in / out. */
export class MotionBlurPass extends Pass {
  constructor(camera) {
    super();
    this.camera = camera;
    this.material = makeMaterial();
    /* round 7d (Jack: "way too much"): a light sideways smear at the edges only, a third of the r7c strength */
    this.material.uniforms.uMaxLen.value = 0.016;
    this.material.uniforms.uEdge.value.set(0.55, 1.1);
    this.material.uniforms.uSideways.value = 1;
    this.quad = new FullScreenQuad(this.material);
    this.prev = new THREE.Matrix4();
    this.hasPrev = false;
    this.amount = 0;           // set by the viewer each frame (fade x shutter)
    this.needsSwap = true;
  }
  /* a jump (teleport, Go to, a new view): no smear from it */
  reset() { this.hasPrev = false; }
  render(renderer, writeBuffer, readBuffer) {
    const u = this.material.uniforms;
    this.camera.updateMatrixWorld();
    if (!this.hasPrev) { this.prev.copy(this.camera.matrixWorld); this.hasPrev = true; }
    const on = this.amount > 0.001;
    u.tColor.value = readBuffer.texture;
    u.uOut.value.set(readBuffer.width, readBuffer.height);
    u.uEyes.value = 1;
    u.uRect.value[0].set(0, 0, readBuffer.width, readBuffer.height);
    setEye(u, 0, this.camera, this.prev);
    u.uAmount.value = on ? this.amount : 0;
    this.prev.copy(this.camera.matrixWorld);
    renderer.setRenderTarget(this.renderToScreen ? null : writeBuffer);
    this.quad.render(renderer);
  }
  dispose() { this.material.dispose(); this.quad.dispose(); }
}

/* the headset (and the simulated headset): draw each eye offscreen, then blur into the real eye buffer.
   rig: the player group (its movement is the only motion that counts). */
export function createXRBlur(renderer, rig) {
  const material = makeMaterial();
  /* round 7d: the middle 70 % of each eye stays sharp; a third of the r7c strength */
  material.uniforms.uEdge.value.set(0.7, 1.1);
  material.uniforms.uMaxLen.value = 0.024;
  const tri = new THREE.BufferGeometry();
  tri.setAttribute("position", new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
  const quad = new THREE.Mesh(tri, material);
  quad.frustumCulled = false;
  const quadScene = new THREE.Scene();
  quadScene.add(quad);
  const ortho = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  let target = null;
  const proxies = [new THREE.PerspectiveCamera(), new THREE.PerspectiveCamera()];
  for (const c of proxies) { c.matrixAutoUpdate = false; c.matrixWorldAutoUpdate = false; }
  const prevRig = new THREE.Matrix4(), rigInv = new THREE.Matrix4();
  let hasPrev = false;
  const size = new THREE.Vector2();
  const state = { scale: 0.7, samples: 4, half: false, lastMs: 0, used: false };

  function ensureTarget(w, h) {
    const tw = Math.max(16, Math.round(w * state.scale)), th = Math.max(16, Math.round(h * state.scale));
    if (target && target.width === tw && target.height === th && target.samples === state.samples && (target.texture.type === THREE.HalfFloatType) === state.half) return target;
    target?.dispose();
    /* 8-bit sRGB (half the memory traffic of half-float on the Quest's tiled GPU; sRGB storage keeps the darks from
       banding); this pass applies the tone mapping when it writes the eye buffer */
    target = new THREE.WebGLRenderTarget(tw, th, { type: state.half ? THREE.HalfFloatType : THREE.UnsignedByteType,
      colorSpace: state.half ? THREE.NoColorSpace : THREE.SRGBColorSpace, samples: state.samples, depthBuffer: true });
    target.texture.minFilter = target.texture.magFilter = THREE.LinearFilter;
    target.texture.generateMipmaps = false;
    return target;
  }

  return {
    state, material,
    /* call every frame (also when not blurring), after the rig has moved: keeps last frame's rig */
    track() { prevRig.copy(rig.matrixWorld); hasPrev = true; },
    reset() { hasPrev = false; },
    /* render scene + camera with the blur at strength `amount` (0..1 fade x shutter).
       Returns false when it did not draw (the caller renders normally). */
    render(scene, camera, amount) {
      if (!hasPrev || amount <= 0.001) return false;
      const xr = renderer.xr, presenting = xr.isPresenting;
      rig.updateMatrixWorld(true);
      const rigNow = rig.matrixWorld.clone();
      rigInv.copy(rigNow).invert();
      /* the eyes: the headset's views, or (simulated headset / screen) the one camera over the whole canvas */
      let eyes;
      if (presenting) {
        xr.updateCamera(camera);
        eyes = xr.getCamera().cameras.map(c => ({ cam: c, vp: c.viewport }));
      } else {
        camera.updateMatrixWorld(true);
        renderer.getDrawingBufferSize(size);
        eyes = [{ cam: camera, vp: new THREE.Vector4(0, 0, size.x, size.y) }];
      }
      if (!eyes.length) return false;
      const outTarget = renderer.getRenderTarget();         // the XR framebuffer's target (null on a screen)
      /* the eye buffer can be wider than the eyes' viewports (side by side): size the copy from the viewports */
      const fw = Math.max(...eyes.map(e => e.vp.x + e.vp.z)), fh = Math.max(...eyes.map(e => e.vp.y + e.vp.w));
      const rt = ensureTarget(fw, fh);
      const t0 = performance.now();
      const autoClear = renderer.autoClear;
      renderer.setRenderTarget(rt);
      renderer.clear();
      renderer.autoClear = false;
      xr.enabled = false;
      const u = material.uniforms;
      eyes.forEach((e, i) => {
        const p = proxies[i], c = e.cam;
        p.projectionMatrix.copy(c.projectionMatrix); p.projectionMatrixInverse.copy(c.projectionMatrixInverse);
        p.matrixWorld.copy(c.matrixWorld); p.matrixWorldInverse.copy(c.matrixWorld).invert();
        p.near = c.near; p.far = c.far;
        p.layers.mask = c.layers.mask;
        rt.viewport.set(e.vp.x * state.scale, e.vp.y * state.scale, e.vp.z * state.scale, e.vp.w * state.scale);
        renderer.setRenderTarget(rt);
        renderer.render(scene, p);
        /* last frame's eye = last frame's rig x this frame's head pose in the rig (real head motion does not count) */
        _m.multiplyMatrices(prevRig, _m2.multiplyMatrices(rigInv, c.matrixWorld));
        setEye(u, i, c, _m);
        u.uRect.value[i].set(e.vp.x, e.vp.y, e.vp.z, e.vp.w);
      });
      rt.viewport.set(0, 0, rt.width, rt.height);
      xr.enabled = true;
      renderer.autoClear = autoClear;
      u.tColor.value = rt.texture;
      u.uOut.value.set(fw, fh);
      u.uEyes.value = eyes.length;
      u.uAmount.value = amount;
      renderer.setRenderTarget(outTarget);
      /* in the headset this draws the triangle once per eye (each eye's viewport); on a screen once */
      renderer.render(quadScene, presenting ? camera : ortho);
      state.lastMs = performance.now() - t0; state.used = true;
      return true;
    },
    dispose() { target?.dispose(); material.dispose(); tri.dispose(); },
  };
}
