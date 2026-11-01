/* ------------------------------------------------------------------ *
 *  The walk test (house.html?test=walk): before a release, every stair
 *  is climbed and descended in every version and at every stage where
 *  it is walkable, and each storey's rooms are walked in a loop with
 *  the doors open (CORRECTIONS-LOG round 6: Jack fell through at the
 *  top of the stair every time; nothing had ever walked it).
 *
 *  Two ways of moving, because the headset has both: "stick" walks
 *  with walker.move + settle (collision, the drop guard), "head" moves
 *  the feet straight along the path and only settles, as a step of the
 *  real head in the room does. A climb passes when every waypoint is
 *  reached, the feet end on the top floor (±30 mm) and no frame drops
 *  more than 250 mm (a fall) or below the stair's base. A room loop
 *  passes when the walker follows the free path a floor grid finds,
 *  room to room, without being stopped or dropping off its storey.
 *  The result: window.__walkTest, the console, and a box on the page.
 * ------------------------------------------------------------------ */

const DT = 1 / 72, SPEED = 1.4;

export async function runWalkTest(H) {
  const { THREE } = H;
  const box = document.createElement("pre");
  box.id = "testOut";
  document.body.appendChild(box);
  const lines = [];
  const say = t => { lines.push(t); box.textContent = lines.join("\n"); console.info(`walk test: ${t}`); };
  const out = { started: new Date().toISOString(), pass: true, versions: [] };
  const t0 = performance.now();
  say("Walk test: every stair up and down in every version and stage; each storey's rooms in a loop.");
  const tick = () => new Promise(r => setTimeout(r));

  /* walk the feet along waypoints; returns {ok, reason, maxDrop, minY, end, frames} */
  function follow(feet, pts, mode, floorMin, tol = 0.06) {
    const W = H.walker;
    let maxDrop = 0, minY = feet.y, frames = 0;
    W.settle(feet, 1);
    for (let i = 0; i < pts.length; i++) {
      const goal = pts[i];
      let best = Infinity, since = 0;
      for (;;) {
        const d = new THREE.Vector3(goal.x - feet.x, 0, goal.z - feet.z), len = d.length();
        if (len < tol) break;
        if (len < best - 0.01) { best = len; since = 0; } else if (++since > 150) return { ok: false, reason: `stuck at (${feet.x.toFixed(2)}, ${feet.y.toFixed(3)}, ${feet.z.toFixed(2)}) on the way to waypoint ${i + 1}/${pts.length}`, maxDrop, minY, end: feet.clone(), frames };
        d.multiplyScalar(Math.min(len, SPEED * DT) / len);
        const y0 = feet.y;
        if (mode === "stick") W.move(feet, d); else feet.add(d);
        W.settle(feet, DT);
        maxDrop = Math.max(maxDrop, y0 - feet.y); minY = Math.min(minY, feet.y);
        if (++frames > 72 * 120) return { ok: false, reason: "timed out", maxDrop, minY, end: feet.clone(), frames };
        if (feet.y < floorMin - 0.05) return { ok: false, reason: `fell to y ${feet.y.toFixed(3)} at (${feet.x.toFixed(2)}, ${feet.z.toFixed(2)})`, maxDrop, minY, end: feet.clone(), frames };
        if (y0 - feet.y > 0.25) return { ok: false, reason: `dropped ${(y0 - feet.y).toFixed(2)} m in one frame at (${feet.x.toFixed(2)}, ${feet.z.toFixed(2)})`, maxDrop, minY, end: feet.clone(), frames };
      }
    }
    for (let k = 0; k < 36; k++) W.settle(feet, DT);           // half a second standing still at the end
    return { ok: true, maxDrop, minY, end: feet.clone(), frames };
  }

  /* the climbing line of a stair element: before the first riser, along each flight's centre, over each landing */
  function stairPath(st) {
    const P = st.params, v = (p, y = 0) => new THREE.Vector3(p[0], y, p[1]);
    const fl = P.flights?.length ? P.flights : [{ start: P.start, direction: P.direction, base: P.base, risers: P.risers, going: P.going }];
    const pts = [];
    const d0 = v(fl[0].direction).normalize();
    const start = v(fl[0].start, fl[0].base ?? P.base).addScaledVector(d0, -0.6);
    fl.forEach((f, i) => {
      const d = v(f.direction).normalize(), s = v(f.start), g = f.going ?? P.going, n = f.risers ?? P.risers;
      if (i === 0) pts.push(s.clone().addScaledVector(d, -0.3));
      if (i < fl.length - 1) {
        const nx = fl[i + 1], dn = v(nx.direction).normalize();
        pts.push(s.clone().addScaledVector(d, (n - 1) * g + 0.35), v(nx.start).addScaledVector(dn, -0.35));
      } else pts.push(s.clone().addScaledVector(d, (n - 1) * g + 0.7));
    });
    return { start, pts, base: P.base ?? fl[0].base ?? 0, top: (P.base ?? 0) + P.risers * P.rise };
  }

  /* a floor grid of a storey: cells where a body stands at the storey's level, clear of walls */
  function grid(rooms, ffl) {
    const W = H.walker, B = H.BODY, C = 0.15;
    let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
    for (const r of rooms) for (const [x, z] of r.params.polygon) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); z0 = Math.min(z0, z); z1 = Math.max(z1, z); }
    x0 -= 0.3; z0 -= 0.3; x1 += 0.3; z1 += 0.3;
    const nx = Math.ceil((x1 - x0) / C), nz = Math.ceil((z1 - z0) / C);
    const ok = new Uint8Array(nx * nz), yAt = new Float32Array(nx * nz);
    const dirs = [new THREE.Vector3(1, 0, 0), new THREE.Vector3(-1, 0, 0), new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 0, -1)];
    const p = new THREE.Vector3();
    for (let i = 0; i < nx; i++) for (let k = 0; k < nz; k++) {
      const x = x0 + (i + 0.5) * C, z = z0 + (k + 0.5) * C;
      const f = W.supportAt(x, ffl, z, 0.25);             // the footprint, as the walk reads it (doorways have no floor of their own)
      if (f === null || f < ffl - 0.12 || f > ffl + 0.2) continue;
      p.set(x, f, z);
      if (!W.free(p) || dirs.some(d => { const h = W.castH(p, d, B.radius + 0.03); return h && h.distance < B.radius + 0.03; })) continue;
      ok[i * nz + k] = 1; yAt[i * nz + k] = f;
    }
    /* connected pieces of free floor: the loop runs in the piece holding most rooms */
    const comp = new Int32Array(nx * nz).fill(-1);
    let nc = 0;
    for (let s0 = 0; s0 < nx * nz; s0++) {
      if (!ok[s0] || comp[s0] >= 0) continue;
      const q = [s0]; comp[s0] = nc;
      for (let h = 0; h < q.length; h++) {
        const c = q[h], i = Math.floor(c / nz), k = c % nz;
        for (const [di, dk] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          const ii = i + di, kk = k + dk, n = ii * nz + kk;
          if (ii < 0 || kk < 0 || ii >= nx || kk >= nz || !ok[n] || comp[n] >= 0) continue;
          comp[n] = nc; q.push(n);
        }
      }
      nc++;
    }
    const cell = (x, z) => [Math.floor((x - x0) / C), Math.floor((z - z0) / C)];
    const centre = (i, k) => new THREE.Vector3(x0 + (i + 0.5) * C, 0, z0 + (k + 0.5) * C);
    return { nx, nz, ok, yAt, cell, centre, C, comp };
  }
  const inPoly = (poly, x, z) => { let ins = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, zi] = poly[i], [xj, zj] = poly[j]; if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) ins = !ins; } return ins; };
  function standCell(G, room, main = -1) {
    const poly = room.params.polygon;
    const c = poly.reduce((a, q) => [a[0] + q[0] / poly.length, a[1] + q[1] / poly.length], [0, 0]);
    let best = null, bd = Infinity;
    for (let i = 0; i < G.nx; i++) for (let k = 0; k < G.nz; k++) {
      if (!G.ok[i * G.nz + k] || (main >= 0 && G.comp[i * G.nz + k] !== main)) continue;
      const q = G.centre(i, k);
      if (!inPoly(poly, q.x, q.z)) continue;
      // prefer cells with free neighbours (the middle of the free floor, not a corner)
      let nb = 0; for (let a = -2; a <= 2; a++) for (let b = -2; b <= 2; b++) { const ii = i + a, kk = k + b; if (ii >= 0 && kk >= 0 && ii < G.nx && kk < G.nz && G.ok[ii * G.nz + kk]) nb++; }
      const d = Math.hypot(q.x - c[0], q.z - c[1]) - nb * 0.05;
      if (d < bd) { bd = d; best = [i, k]; }
    }
    return best;
  }
  function bfs(G, a, b) {
    const N = G.nx * G.nz, prev = new Int32Array(N).fill(-1), start = a[0] * G.nz + a[1], goal = b[0] * G.nz + b[1];
    const q = [start]; prev[start] = start;
    for (let h = 0; h < q.length; h++) {
      const c = q[h];
      if (c === goal) break;
      const i = Math.floor(c / G.nz), k = c % G.nz;
      for (const [di, dk] of [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]]) {
        const ii = i + di, kk = k + dk;
        if (ii < 0 || kk < 0 || ii >= G.nx || kk >= G.nz) continue;
        const n = ii * G.nz + kk;
        if (!G.ok[n] || prev[n] !== -1) continue;
        if (di && dk && !(G.ok[(i + di) * G.nz + k] && G.ok[i * G.nz + k + dk])) continue;
        prev[n] = c; q.push(n);
      }
    }
    if (prev[goal] === -1) return null;
    const path = [];
    for (let c = goal; c !== start; c = prev[c]) path.push(c);
    path.reverse();
    return path.map(c => G.centre(Math.floor(c / G.nz), c % G.nz));
  }

  async function roomLoop(V, storey) {
    const rooms = [...V.editor.current().values()].filter(e => e.type === "room" && !e.removed && (e.params.storey === storey));
    if (rooms.length < 2) return { storey, skipped: `${rooms.length} room(s)` };
    const ffl = V.sidecar.storeys?.[storey] ?? rooms[0].params.floor;
    const G = grid(rooms, ffl);
    /* the piece of floor most rooms stand in; each room's standing cell is taken in it when it can be */
    const votes = new Map();
    for (const r of rooms) { const c = standCell(G, r); if (c) { const k = G.comp[c[0] * G.nz + c[1]]; votes.set(k, (votes.get(k) || 0) + 1); } }
    const main = [...votes.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? -1;
    const stands = rooms.map(r => ({ r, c: standCell(G, r, main) || standCell(G, r) }));
    const noFloor = stands.filter(s => !s.c).map(s => s.r.params.name);
    let todo = stands.filter(s => s.c);
    if (!todo.length) return { storey, ok: false, reason: "no free floor in any room" };
    const first = todo.shift(), order = [first], unreachable = [];
    let at = first;
    while (todo.length) {                                 // nearest reachable room next
      let best = null;
      for (const s of todo) { const p = bfs(G, at.c, s.c); if (p && (!best || p.length < best.p.length)) best = { s, p }; }
      if (!best) { unreachable.push(...todo.map(s => s.r.params.name)); break; }
      order.push(best.s); todo = todo.filter(s => s !== best.s); at = best.s;
    }
    order.push(first);                                    // and back: a loop
    const feet = G.centre(...first.c); feet.y = ffl;
    let walked = 0, fails = [];
    for (let i = 1; i < order.length; i++) {
      const path = bfs(G, order[i - 1].c, order[i].c);
      if (!path) continue;
      const res = follow(feet, path, "stick", ffl - 0.3, 0.09);
      walked += path.length * G.C;
      if (!res.ok) { fails.push(`${order[i - 1].r.params.name} → ${order[i].r.params.name}: ${res.reason}`); feet.copy(G.centre(...order[i].c)); feet.y = ffl; }
      if (feet.y > ffl + 0.45 || feet.y < ffl - 0.15) fails.push(`${order[i].r.params.name}: feet at ${feet.y.toFixed(3)}, storey ${ffl}`);
      await tick();
    }
    return { storey, ok: !fails.length, rooms: order.slice(0, -1).map(s => s.r.params.name), walked_m: +walked.toFixed(1), unreachable, no_free_floor: noFloor, fails };
  }

  for (const def of H.manifest().versions) {
    await H.useVersion(def.id);
    const V = H.V, N = V.sidecar.stages.length;
    const res = { id: def.id, stages: N, stairs: [], rooms: [] };
    const stairs = [...V.editor.current().values()].filter(e => e.type === "stair" && !e.removed);
    say(`\n${def.id}: ${N} stage${N > 1 ? "s" : ""}, ${stairs.length} stair${stairs.length === 1 ? "" : "s"}, ${V.doors.count} doors (${V.doors.derived.length} with derived hinges)`);
    for (let s = 1; s <= N; s++) {
      H.setStage(s);
      for (const st of stairs) {
        const parts = V.model.byElement.get(st.id) || [];
        const topParts = st.params.top_floor ? V.model.byElement.get(st.params.top_floor) || [] : [];
        const walkable = parts.length && parts.every(p => p.now.solid || !p.collide) && parts.some(p => p.now.solid) && (!topParts.length || topParts.some(p => p.now.solid));
        if (!walkable) { res.stairs.push({ stair: st.id, stage: s, skipped: "not walkable at this stage" }); continue; }
        const path = stairPath(st);
        const row = { stair: st.id, stage: s };
        /* the floors at the foot and the head of the stair must be there for a walk to mean anything */
        const foot = H.walker.floorAt(path.start.x, path.base, path.start.z, 0.3), headPt = path.pts[path.pts.length - 1];
        const head = H.walker.floorAt(headPt.x, path.top, headPt.z, 0.3);
        if (foot === null || Math.abs(foot - path.base) > 0.03 || head === null || Math.abs(head - path.top) > 0.03) {
          const what = foot === null || Math.abs(foot - path.base) > 0.03 ? `foot (floor ${foot === null ? "none" : foot.toFixed(3)} at y ${path.base})` : `head (floor ${head === null ? "none" : head.toFixed(3)} at y ${path.top.toFixed(4)})`;
          const gone = (V.model.parts.filter(p => p.collide && p.stage_out && p.stage_out <= s && p.bbox.min.x <= path.start.x + 0.01 && p.bbox.max.x >= path.start.x - 0.01 && p.bbox.min.z <= path.start.z + 0.01 && p.bbox.max.z >= path.start.z - 0.01 && Math.abs(p.bbox.max.y - path.base) < 0.05).map(p => p.name));
          row.skipped = `no floor at the stair's ${what}${gone.length ? `: ${gone.join(", ")} is out at this stage` : ""}`;
          res.stairs.push(row);
          say(`  stage ${s} ${st.id}: skipped, ${row.skipped}`);
          continue;
        }
        for (const mode of ["stick", "head"]) {
          const up = follow(path.start.clone(), path.pts, mode, path.base);
          const upOk = up.ok && Math.abs(up.end.y - path.top) < 0.03;
          const back = [...path.pts].reverse().slice(1).concat([path.start]);
          const top = path.pts[path.pts.length - 1].clone(); top.y = path.top;
          const down = follow(top, back, mode, path.base);
          const downOk = down.ok && Math.abs(down.end.y - path.base) < 0.03;
          row[mode] = { up: upOk ? "pass" : `FAIL ${up.reason || `ended at y ${up.end.y.toFixed(3)}, top floor ${path.top.toFixed(4)}`}`,
                        down: downOk ? "pass" : `FAIL ${down.reason || `ended at y ${down.end.y.toFixed(3)}, base ${path.base}`}`,
                        top_y: +up.end.y.toFixed(4), max_drop_down: +down.maxDrop.toFixed(3) };
          if (!upOk || !downOk) out.pass = false;
        }
        res.stairs.push(row);
        say(`  stage ${s} ${st.id}: stick up ${row.stick.up}, down ${row.stick.down} · head up ${row.head.up}, down ${row.head.down} (top y ${row.stick.top_y})`);
        await tick();
      }
    }
    for (const s of [...new Set([1, N])]) {
      H.setStage(s);
      V.doors.snapAll(true);
      for (const storey of ["ground", "first"]) {
        const r = await roomLoop(V, storey);
        r.stage = s;
        res.rooms.push(r);
        if (r.ok === false) out.pass = false;
        say(`  stage ${s} ${storey} rooms: ${r.skipped ? `skipped (${r.skipped})` : `${r.ok ? "pass" : "FAIL"} · ${r.rooms?.length || 0} rooms, ${r.walked_m ?? 0} m walked${r.unreachable?.length ? ` · not reachable on the grid: ${r.unreachable.join(", ")}` : ""}${r.no_free_floor?.length ? ` · no free floor: ${r.no_free_floor.join(", ")}` : ""}${r.fails?.length ? ` · ${r.fails.join(" | ")}` : ""}`}`);
      }
      V.doors.snapAll(false);
    }
    out.versions.push(res);
  }
  out.seconds = Math.round((performance.now() - t0) / 100) / 10;
  say(`\n${out.pass ? "PASS" : "FAIL"} · ${out.seconds} s`);
  window.__walkTest = out;
  return out;
}
