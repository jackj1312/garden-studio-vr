import * as THREE from "three";

/* ------------------------------------------------------------------ *
 *  Tape measure: two points, snapped to the model's real corners and
 *  edges (the part's own feature edges at 20°, not the triangle
 *  diagonals), shown as a line with the length in millimetres.
 *  Snap reach grows with distance: 12 px on a screen, ~1.5% of the
 *  range in the headset. Magenta = corner, cyan = edge, white = face.
 * ------------------------------------------------------------------ */

const COL = { vertex: 0xff3df5, edge: 0x2fe0ff, face: 0xffffff };

function labelSprite(text) {
  const cv = document.createElement("canvas");
  cv.width = 256; cv.height = 96;
  const c = cv.getContext("2d");
  c.fillStyle = "rgba(14,16,14,0.9)";
  c.beginPath(); c.roundRect(4, 14, 248, 68, 18); c.fill();
  c.fillStyle = "#ffffff"; c.font = "600 40px system-ui, sans-serif"; c.textAlign = "center"; c.textBaseline = "middle";
  c.fillText(text, 128, 49);
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true, toneMapped: false }));
  s.renderOrder = 990;
  s.scale.set(0.36, 0.135, 1);
  return s;
}

export function createMeasure(scene) {
  const group = new THREE.Group();
  group.name = "measure";
  scene.add(group);
  const edgeCache = new Map();                // geometry uuid -> Float32Array of local edge segments
  const marker = new THREE.Mesh(new THREE.SphereGeometry(0.018, 16, 10),
    new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, toneMapped: false }));
  marker.renderOrder = 991;
  marker.visible = false;
  scene.add(marker);
  const done = [];                            // finished measurements
  let first = null, live = null;

  function edgesOf(part) {
    const key = part.geometry.uuid;
    if (!edgeCache.has(key)) edgeCache.set(key, new THREE.EdgesGeometry(part.geometry, 20).attributes.position.array);
    return edgeCache.get(key);
  }

  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3(), best = new THREE.Vector3();
  const seg = new THREE.Line3();
  /* snap a BVH hit on `part`: reach in metres */
  function snap(point, part, reach) {
    const e = edgesOf(part), m = part.matrix0;
    let bd = reach, kind = "face";
    best.copy(point);
    for (let i = 0; i < e.length; i += 6) {           // corners first
      a.set(e[i], e[i + 1], e[i + 2]).applyMatrix4(m);
      b.set(e[i + 3], e[i + 4], e[i + 5]).applyMatrix4(m);
      for (const v of [a, b]) {
        const d = v.distanceTo(point);
        if (d < bd) { bd = d; best.copy(v); kind = "vertex"; }
      }
    }
    if (kind === "face") {
      bd = reach * 0.7;
      for (let i = 0; i < e.length; i += 6) {
        a.set(e[i], e[i + 1], e[i + 2]).applyMatrix4(m);
        b.set(e[i + 3], e[i + 4], e[i + 5]).applyMatrix4(m);
        seg.set(a, b);
        seg.closestPointToPoint(point, true, c);
        const d = c.distanceTo(point);
        if (d < bd) { bd = d; best.copy(c); kind = "edge"; }
      }
    }
    return { point: best.clone(), kind };
  }

  function makeLine(p, q) {
    const g = new THREE.BufferGeometry().setFromPoints([p, q]);
    const line = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0xffd23f, depthTest: false, toneMapped: false }));
    line.renderOrder = 989;
    return line;
  }
  function endDot(p, kind) {
    const s = marker.clone();
    s.material = marker.material.clone();
    s.material.color.setHex(COL[kind]);
    s.position.copy(p); s.visible = true;
    return s;
  }
  const mm = d => `${Math.round(d * 1000).toLocaleString()} mm`;

  return {
    group,
    get count() { return done.length; },
    get pending() { return !!first; },
    /* hover: show where a click would land */
    hover(hit, part, reach) {
      if (!hit || !part) { marker.visible = false; if (live) { live.removeFromParent(); live = null; } return null; }
      const s = snap(hit.point, part, reach);
      marker.position.copy(s.point);
      marker.material.color.setHex(COL[s.kind]);
      marker.visible = true;
      if (first) {
        if (!live) { live = makeLine(first.point, s.point); group.add(live); }
        live.geometry.setFromPoints([first.point, s.point]);
      }
      return s;
    },
    /* a click / trigger: first point, then the second finishes a measurement */
    click(hit, part, reach) {
      if (!hit || !part) return null;
      const s = snap(hit.point, part, reach);
      if (!first) { first = s; first.dot = endDot(s.point, s.kind); group.add(first.dot); return { started: true }; }
      if (live) { live.removeFromParent(); live = null; }
      const d = first.point.distanceTo(s.point);
      const g = new THREE.Group();
      g.add(first.dot, endDot(s.point, s.kind), makeLine(first.point, s.point));
      const lab = labelSprite(mm(d));
      lab.position.copy(first.point).add(s.point).multiplyScalar(0.5).add(new THREE.Vector3(0, 0.08, 0));
      g.add(lab);
      group.add(g);
      const dy = Math.abs(first.point.y - s.point.y), dh = Math.hypot(first.point.x - s.point.x, first.point.z - s.point.z);
      const m = { from: first.point.toArray(), to: s.point.toArray(), mm: Math.round(d * 1000),
                  horizontal_mm: Math.round(dh * 1000), vertical_mm: Math.round(dy * 1000), group: g };
      done.push(m);
      first = null;
      return m;
    },
    last() { return done[done.length - 1] || null; },
    clear() {
      for (const m of done) m.group.removeFromParent();
      done.length = 0;
      if (first) { first.dot.removeFromParent(); first = null; }
      if (live) { live.removeFromParent(); live = null; }
      marker.visible = false;
    },
    hideMarker() { marker.visible = false; },
    /* labels face the viewer at a readable size */
    update(camera) {
      const cp = camera.getWorldPosition(new THREE.Vector3());
      for (const m of done) for (const o of m.group.children) if (o.isSprite) {
        const d = o.position.distanceTo(cp);
        o.scale.set(0.36 * Math.max(0.6, d / 2.5), 0.135 * Math.max(0.6, d / 2.5), 1);
      }
    },
  };
}
