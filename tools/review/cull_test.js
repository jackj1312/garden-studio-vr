/* Room-culling proof harness (PLAN S10). Load in the page opened with ?capture=1 :
 *     await import("/tools/review/cull_test.js")
 * then   window.__cullTest(window.__cullCams(seed, perRoom, yaws), w, h, fov)
 * Every camera is rendered twice from the same pose, culling off then on (the same page, the same model, shadows
 * re-rendered each time), and the two pictures compared pixel by pixel (a pixel counts when any channel differs by
 * more than 2 of 255). Returns {tot, bad, sumpx, maxd, list}. __cullIds(cam) lists the PARTS that the culled picture lost.
 * __cullProfile() returns calls / triangles per pass (main and shadow) with culling off and on, per room. */
const h = window.__house, C = h.cull, { renderer, scene, camera } = h;
const inPoly = (poly, x, z) => { let ins = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, zi] = poly[i], [xj, zj] = poly[j]; if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) ins = !ins; } return ins; };

window.__cullCams = (seed = 12345, perRoom = 2, yaws = 6) => {
  let s = seed; const rn = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  const cams = [];
  for (const r of C.R) {
    let n = 0, tries = 0;
    while (n < perRoom && tries++ < 200) {
      const x = r.x0 + rn() * (r.x1 - r.x0), z = r.z0 + rn() * (r.z1 - r.z0);
      if (!inPoly(r.poly, x, z)) continue; n++;
      for (let k = 0; k < yaws; k++) cams.push({ room: r.name, x, z, y: r.floor, yawDeg: k * 360 / yaws + rn() * 20, pitchDeg: (rn() - 0.5) * 40, eye: 1.0 + rn() * 0.9 });
    }
  }
  for (let i = 0; i < 14; i++) { const x = -6 + rn() * 20, z = -12 + rn() * 24; if (C.R.some(r => inPoly(r.poly, x, z))) continue; for (let k = 0; k < 6; k++) cams.push({ room: "outside", x, z, yawDeg: k * 60, pitchDeg: (rn() - 0.5) * 30, eye: 1.6 }); }
  for (let i = 0; i < 4; i++) for (let k = 0; k < 4; k++) cams.push({ room: "aerial", x: 1 + rn() * 8, z: -5 + rn() * 6, yawDeg: k * 90, pitchDeg: -25, eye: 7 });
  /* standing in every portal (doorway, window, gap), looking along and across it */
  for (const p of C.portalList()) {
    const c = p.ctr, fl = c[1] < 2.4 ? 0 : 2.6755;
    for (let k = 0; k < 4; k++) cams.push({ room: "portal", x: c[0], z: c[2], y: fl, yawDeg: k * 90 + rn() * 40, pitchDeg: (rn() - 0.5) * 20, eye: Math.max(0.5, Math.min(1.7, c[1] - fl)) });
  }
  return cams;
};

const cv = document.createElement("canvas"), ctx = cv.getContext("2d", { willReadFrequently: true });
/* captureAt renders with a shadow update (which draws every batch); the picture compared is a second render with the shadow map
   as it is, as in a frame of the headset, so the batches with nothing to draw are really skipped */
const grab = (cam, w, hh, fov) => { h.captureAt({ ...cam, w, h: hh, fov }); renderer.shadowMap.needsUpdate = false; renderer.render(scene, camera); cv.width = w; cv.height = hh; ctx.drawImage(renderer.domElement, 0, 0, w, hh); return ctx.getImageData(0, 0, w, hh).data; };
window.__cullTest = (cams, w = 480, hh = 270, fov = 60) => {
  const bad = []; let maxd = 0, sumpx = 0;
  for (const cam of cams) {
    C.enabled = false; const a = grab(cam, w, hh, fov); C.enabled = true; const b = grab(cam, w, hh, fov);
    let n = 0, m = 0;
    for (let i = 0; i < a.length; i += 4) { const d = Math.max(Math.abs(a[i] - b[i]), Math.abs(a[i + 1] - b[i + 1]), Math.abs(a[i + 2] - b[i + 2])); if (d > 2) n++; if (d > m) m = d; }
    sumpx += n; if (m > maxd) maxd = m;
    if (n > 0) bad.push({ room: cam.room, x: +cam.x.toFixed(2), z: +cam.z.toFixed(2), yaw: Math.round(cam.yawDeg), pitch: Math.round(cam.pitchDeg), eye: +cam.eye.toFixed(2), px: n, max: m, cells: C.state.cells.join("|") });
  }
  return { tot: cams.length, bad: bad.length, sumpx, maxd, pixels_per_picture: w * hh, list: bad.slice(0, 12) };
};

window.__cullProfile = () => {
  renderer.info.autoReset = false;
  const one = shadow => { renderer.info.reset(); renderer.shadowMap.needsUpdate = shadow; renderer.render(scene, camera); const i = renderer.info.render; return { calls: i.calls, tris: i.triangles }; };
  const rows = [];
  for (const r of C.R) {
    let cx = 0, cz = 0; r.poly.forEach(([x, z]) => { cx += x; cz += z; }); cx /= r.poly.length; cz /= r.poly.length;
    const row = { room: r.name };
    for (const [k, en] of [["off", false], ["on", true]]) {
      let mc = 0, mt = 0, sc = 0, st = 0;
      for (let y = 0; y < 4; y++) {
        C.enabled = en; h.captureAt({ x: cx, z: cz, y: r.floor, yawDeg: y * 90, w: 240, h: 135, fov: 90 });
        const m = one(false), w = one(true); mc += m.calls; mt += m.tris; sc += w.calls - m.calls; st += w.tris - m.tris;
      }
      row[k] = { main_calls: Math.round(mc / 4), main_tris: Math.round(mt / 4), shadow_calls: Math.round(sc / 4), shadow_tris: Math.round(st / 4) };
    }
    rows.push(row);
  }
  C.enabled = true;
  return rows;
};
