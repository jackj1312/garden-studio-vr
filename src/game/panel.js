import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  Panels for the headset: a canvas on a plane, drawn only when what
 *  it shows changes, with buttons you point the blaster at and pull
 *  the trigger. Layout is in canvas pixels; `widthM` is the panel's
 *  width in metres (in the rig, so toy mode shrinks it with you).
 * ------------------------------------------------------------------ */

const FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif";

export function createPanel(w, h, widthM) {
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, toneMapped: false, depthTest: true });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(widthM, widthM * h / w), mat);
  mesh.renderOrder = 20;
  mesh.visible = false;
  const g = c.getContext("2d");
  let buttons = [], hover = null, drawFn = null;

  function rr(x, y, ww, hh, r) { g.beginPath(); g.roundRect(x, y, ww, hh, r); }
  const api = {
    mesh, g, w, h,
    get buttons() { return buttons; },
    /* fn(ui) draws with ui.bg / ui.text / ui.button; called again on hover changes */
    draw(fn) { drawFn = fn || drawFn; buttons = []; g.clearRect(0, 0, w, h); drawFn(api); tex.needsUpdate = true; },
    bg(col = "rgba(22,28,48,0.92)") { rr(4, 4, w - 8, h - 8, 36); g.fillStyle = col; g.fill(); g.lineWidth = 6; g.strokeStyle = "#ffd23f"; g.stroke(); },
    text(t, x, y, size = 40, col = "#fff", align = "center", weight = 800) {
      g.font = `${weight} ${size}px ${FONT}`; g.textAlign = align; g.textBaseline = "middle"; g.fillStyle = col; g.fillText(t, x, y);
    },
    button(id, label, x, y, ww, hh, { on = false, col = "#2f7cf6", size = 36, disabled = false } = {}) {
      const hv = hover === id && !disabled;
      rr(x, y, ww, hh, 22);
      g.fillStyle = disabled ? "#3b4256" : on ? "#ff7a1a" : col; g.fill();
      if (hv) { g.lineWidth = 8; g.strokeStyle = "#fff"; g.stroke(); }
      api.text(label, x + ww / 2, y + hh / 2 + 2, size, disabled ? "#8890a6" : "#fff");
      if (!disabled) buttons.push({ id, x, y, w: ww, h: hh });
    },
    /* uv (0..1, from a raycast) -> button id */
    at(uv) {
      if (!uv) return null;
      const px = uv.x * w, py = (1 - uv.y) * h;
      return buttons.find(b => px >= b.x && px <= b.x + b.w && py >= b.y && py <= b.y + b.h)?.id || null;
    },
    setHover(id) { if (id !== hover) { hover = id; if (drawFn && mesh.visible) api.draw(); } },
    show(on) { mesh.visible = on; if (!on) hover = null; },
  };
  return api;
}
