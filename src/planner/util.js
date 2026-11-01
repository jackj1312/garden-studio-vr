/* Room planner: small shared helpers (DOM, geometry, formatting). No dependencies. */

export const SVGNS = "http://www.w3.org/2000/svg";

/* h("div.cls#id", {attrs}, children...) */
export function h(tag, attrs, ...kids) {
  const [t, ...rest] = tag.split(/(?=[.#])/);
  const e = document.createElement(t || "div");
  for (const r of rest) r[0] === "." ? e.classList.add(r.slice(1)) : (e.id = r.slice(1));
  setAttrs(e, attrs);
  append(e, kids);
  return e;
}
export function s(tag, attrs, ...kids) {
  const e = document.createElementNS(SVGNS, tag);
  setAttrs(e, attrs);
  append(e, kids);
  return e;
}
function setAttrs(e, attrs) {
  if (!attrs) return;
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") e.setAttribute("class", v);
    else if (k === "style" && typeof v === "object") Object.assign(e.style, v);
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
    else if (k === "text") e.textContent = v;
    else if (k === "html") e.innerHTML = v;
    else if (k in e && !(e instanceof SVGElement) && k !== "list") { try { e[k] = v; } catch { e.setAttribute(k, v); } }
    else e.setAttribute(k, v === true ? "" : v);
  }
}
function append(e, kids) {
  for (const k of kids.flat(Infinity)) {
    if (k === null || k === undefined || k === false) continue;
    e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
}
export const clear = e => { while (e.firstChild) e.removeChild(e.firstChild); return e; };

/* ---- numbers ---- */
export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export const r3 = v => Math.round(v * 1000) / 1000;
export const mm = m => Math.round(m * 1000);
export const fmtSize = s => s.map(v => Math.round(v)).join(" × ");
export const D2R = Math.PI / 180;
export const normDeg = d => { let x = ((d % 360) + 360) % 360; if (x > 180) x -= 360; return Math.round(x * 100) / 100; };
export const uid = (p = "c") => p + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

/* ---- colour ---- */
export function hexToRgb(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || ""); if (!m) return [200, 200, 200];
  const n = parseInt(m[1], 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
export const rgbToHex = ([r, g, b]) => "#" + [r, g, b].map(v => clamp(Math.round(v), 0, 255).toString(16).padStart(2, "0")).join("").toUpperCase();
export const mix = (a, b, t) => { const A = hexToRgb(a), B = hexToRgb(b); return rgbToHex(A.map((v, i) => v + (B[i] - v) * t)); };
export const luminance = hex => { const [r, g, b] = hexToRgb(hex); return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255; };

/* ---- plan geometry: points are [x, z] in metres (viewer frame) ---- */
export function pointInPoly([x, z], poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if ((zi > z) !== (zj > z) && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) inside = !inside;
  }
  return inside;
}
export function polyArea(poly) { let a = 0; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) a += (poly[j][0] + poly[i][0]) * (poly[j][1] - poly[i][1]); return Math.abs(a / 2); }
export function bbox(points) {
  let x0 = Infinity, z0 = Infinity, x1 = -Infinity, z1 = -Infinity;
  for (const [x, z] of points) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); z0 = Math.min(z0, z); z1 = Math.max(z1, z); }
  return { x0, z0, x1, z1, w: x1 - x0, d: z1 - z0, cx: (x0 + x1) / 2, cz: (z0 + z1) / 2 };
}
export function centroid(poly) {
  let a = 0, cx = 0, cz = 0;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const f = poly[j][0] * poly[i][1] - poly[i][0] * poly[j][1];
    a += f; cx += (poly[j][0] + poly[i][0]) * f; cz += (poly[j][1] + poly[i][1]) * f;
  }
  if (Math.abs(a) < 1e-9) { const b = bbox(poly); return [b.cx, b.cz]; }
  return [cx / (3 * a), cz / (3 * a)];
}
/* a point well inside a (possibly concave) polygon, for labels */
export function labelPoint(poly) {
  const c = centroid(poly);
  if (pointInPoly(c, poly)) return c;
  const b = bbox(poly); let best = c, bestD = -1;
  for (let i = 1; i < 12; i++) for (let j = 1; j < 12; j++) {
    const p = [b.x0 + (b.w * i) / 12, b.z0 + (b.d * j) / 12];
    if (!pointInPoly(p, poly)) continue;
    const d = Math.min(...poly.map((q, k) => segDist(p, q, poly[(k + 1) % poly.length])));
    if (d > bestD) { bestD = d; best = p; }
  }
  return best;
}
export function segDist(p, a, b) {
  const dx = b[0] - a[0], dz = b[1] - a[1], L2 = dx * dx + dz * dz;
  const t = L2 ? clamp(((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / L2, 0, 1) : 0;
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dz));
}
/* item axes from yaw (spec frame): width axis u = (cos, -sin), front f = (-sin, -cos) */
export function axes(yawDeg) {
  const y = yawDeg * D2R, c = Math.cos(y), sn = Math.sin(y);
  return { u: [c, -sn], f: [-sn, -c] };
}
/* footprint corners of a W x D box centred at (x, z) */
export function footprint(x, z, W, D, yawDeg) {
  const { u, f } = axes(yawDeg), hw = W / 2, hd = D / 2;
  return [[-hw, -hd], [hw, -hd], [hw, hd], [-hw, hd]].map(([a, b]) => [x + u[0] * a - f[0] * b, z + u[1] * a - f[1] * b]);
}
/* convex polygons overlap (separating axis); returns the penetration depth (0 = apart) */
export function convexOverlap(A, B) {
  let min = Infinity;
  for (const P of [A, B]) for (let i = 0; i < P.length; i++) {
    const a = P[i], b = P[(i + 1) % P.length], nx = -(b[1] - a[1]), nz = b[0] - a[0], L = Math.hypot(nx, nz) || 1;
    const ax = [nx / L, nz / L];
    const pa = A.map(p => p[0] * ax[0] + p[1] * ax[1]), pb = B.map(p => p[0] * ax[0] + p[1] * ax[1]);
    const o = Math.min(Math.max(...pa), Math.max(...pb)) - Math.max(Math.min(...pa), Math.min(...pb));
    if (o <= 0) return 0;
    min = Math.min(min, o);
  }
  return min;
}
/* fraction of a convex polygon's sample points that lie inside a polygon */
export function insideFraction(P, poly, tol = 0.01) {
  const pts = [];
  for (let i = 0; i < P.length; i++) {
    const a = P[i], b = P[(i + 1) % P.length];
    for (let k = 0; k < 4; k++) pts.push([a[0] + ((b[0] - a[0]) * k) / 4, a[1] + ((b[1] - a[1]) * k) / 4]);
  }
  let n = 0;
  for (const p of pts) if (pointInPoly(p, poly) || Math.min(...poly.map((q, k) => segDist(p, q, poly[(k + 1) % poly.length]))) < tol) n++;
  return n / pts.length;
}
export const rot = ([x, z], deg) => { const t = deg * D2R, c = Math.cos(t), sn = Math.sin(t); return [x * c + z * sn, -x * sn + z * c]; };
export const add2 = (a, b) => [a[0] + b[0], a[1] + b[1]];
export const sub2 = (a, b) => [a[0] - b[0], a[1] - b[1]];
export const scale2 = (a, k) => [a[0] * k, a[1] * k];
export const dot2 = (a, b) => a[0] * b[0] + a[1] * b[1];
export const len2 = a => Math.hypot(a[0], a[1]);
export const norm2 = a => { const L = len2(a) || 1; return [a[0] / L, a[1] / L]; };

/* plain words for a move in this house's frame: +x towards the north flank, -z towards the garden */
export function moveWords(dx, dz) {
  const parts = [];
  if (Math.abs(dz) >= 0.005) parts.push(`${mm(Math.abs(dz))} mm towards the ${dz < 0 ? "garden" : "road"}`);
  if (Math.abs(dx) >= 0.005) parts.push(`${mm(Math.abs(dx))} mm ${dx > 0 ? "north (away from No. 21)" : "south (towards No. 21)"}`);
  return parts.join(" and ") || "in place";
}
export function compassOf(nx, nz) {  /* outward normal of a wall -> which side of the room it is */
  if (Math.abs(nz) >= Math.abs(nx)) return nz < 0 ? "garden side (west)" : "road side (east)";
  return nx > 0 ? "north side" : "south side (No. 21)";
}
export const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
export const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
export const cap = t => (t ? t[0].toUpperCase() + t.slice(1) : t);
