/* The sweep driver (PLAN S8): run in the page of the viewer opened with ?capture=1.
 *
 *   const m = await import("/tools/review/sweep_driver.js");
 *   m.start(window.__house, await (await fetch("/renders/.../plan.json")).json());   // returns at once; poll window.__sweep
 *
 * For each furnished state (furnished first), each standing point, each eye height: the 12 level directions (yaw steps of
 * 30 degrees) plus up (+35) and down (-35) at the point's look yaw, posted to the capture server (tools/review/capture_server.py)
 * as one batch. In a room every frame also posts the PART picture of the same view (ids.png: each part flat-coloured with its
 * index + 1, nothing drawn magenta) and the part table (parts.json) for the machine pass. A frame whose picture repeats
 * another direction's at the same point is counted in window.__sweep.dupes (CORRECTIONS-LOG 237): the sweep goes on, the
 * checker rejects the set. A point the walker says is blocked (inside furniture or a hedge) is nudged up to 0.6 m, never
 * moved out of its room (the checker tests the polygon again); doorways are never nudged. Nothing is specific to one house. */
const pad = (n, k = 3) => String(Math.round(n)).padStart(k, "0");
const b64 = s => btoa(unescape(encodeURIComponent(s)));
const post = (dir, files) => fetch("/save", { method: "POST", body: JSON.stringify({ dir, files }) }).then(r => r.json());
const OFFS = [[0, 0], [0.3, 0], [-0.3, 0], [0, 0.3], [0, -0.3], [0.45, 0.45], [-0.45, 0.45], [0.45, -0.45], [-0.45, -0.45], [0.6, 0], [-0.6, 0], [0, 0.6], [0, -0.6]];

export function start(h, plan, opts = {}) {
  const S = window.__sweep = { space: plan.space, version: plan.version, total: 0, done: 0, dupes: [], errors: [], moved: [], blocked: [], finished: false, t0: Date.now(), ms_render: 0, ms_total: 0, frames: 0 };
  S.promise = run(h, plan, opts, S).then(() => { S.finished = true; S.ms_total = Date.now() - S.t0; }, e => { S.errors.push(String(e && e.stack || e)); S.finished = true; });
  return S;
}

async function run(h, plan, opts, S) {
  const dir = opts.dir || `renders/house-build/first-build/round-1/sweep/${plan.space}/${plan.version}`;
  const states = opts.states || [true, false];
  const eyes = plan.eyes, perPoint = plan.yaws.length + 2;
  S.total = states.length * plan.points.length * eyes.length * perPoint;
  const meta = { space: plan.space, version: plan.version, states: {}, params: { w: plan.w, h: plan.h, fov: plan.fov } };
  if (plan.kind === "room") await post(dir, { "parts.json": b64(JSON.stringify(h.partTable())) });
  await new Promise(r => setTimeout(r, 300));
  for (const furnished of states) {
    h.furnished(furnished);
    const sk = furnished ? "f" : "u";
    meta.states[sk] = {};
    for (const p of plan.points) {
      let x = p.x, z = p.z, y = p.y;
      if (!String(p.tag).startsWith("door") && !String(p.tag).startsWith("gate")) {
        const fy = y ?? h.walker.floorAt(x, -0.45, z, 4) ?? -0.231;
        let ok = false;
        for (const [dx, dz] of OFFS) {
          h.feet.set(p.x + dx, fy, p.z + dz);
          if (h.walker.free(h.feet) && (!plan.polygon || insidePoly(p.x + dx, p.z + dz, plan.polygon, 0.3))) { x = p.x + dx; z = p.z + dz; ok = true; if (dx || dz) S.moved.push(`${sk}:${p.id}:${dx},${dz}`); break; }
        }
        if (!ok) { S.blocked.push(`${sk}:${p.id}`); }
      }
      meta.states[sk][p.id] = { x, z, y: y ?? null, tag: p.tag, look: p.look };
      for (let ei = 0; ei < eyes.length; ei++) {
        const eye = eyes[ei], files = {}, seen = new Map();
        const withIds = plan.kind === "room";
        const shots = [...plan.yaws.map(yw => [pad(yw), yw, 0]), ["up", p.look, plan.up_deg], ["dn", p.look, plan.down_deg]];
        for (const [tag, yaw, pitch] of shots) {
          const base = { x, z, y, yawDeg: yaw, pitchDeg: pitch, eye, w: plan.w, h: plan.h, fov: plan.fov };
          const r = h.captureAt(base);
          const name = `${p.id}_e${pad(eye * 100)}_${sk}_${tag}`;
          files[name + ".jpg"] = r.url; S.ms_render += r.ms; S.frames++;
          if (seen.has(r.hash)) S.dupes.push(`${name} == ${seen.get(r.hash)}`); else seen.set(r.hash, name);
          if (withIds) files[name + ".id.png"] = h.captureAt({ ...base, ids: true }).url;
          files[`${p.id}_e${pad(eye * 100)}_${sk}.pos.json`] = b64(JSON.stringify({ eye: r.eye, x, z, y: y ?? null, furnished }));
        }
        const res = await post(dir, files);
        if (res.error) S.errors.push(`${p.id} ${sk} ${eye}: ${res.error}`);
        S.done += perPoint;
      }
    }
  }
  await post(dir, { "meta.json": b64(JSON.stringify(meta)) });
}

function insidePoly(x, z, poly, margin) {
  let c = false, best = 1e9;
  for (let i = 0; i < poly.length; i++) {
    const [x1, z1] = poly[i], [x2, z2] = poly[(i + 1) % poly.length];
    if ((z1 > z) !== (z2 > z) && x < (x2 - x1) * (z - z1) / (z2 - z1) + x1) c = !c;
    const dx = x2 - x1, dz = z2 - z1, t = Math.max(0, Math.min(1, ((x - x1) * dx + (z - z1) * dz) / (dx * dx + dz * dz || 1)));
    best = Math.min(best, Math.hypot(x - (x1 + t * dx), z - (z1 + t * dz)));
  }
  return c && best >= margin;
}
