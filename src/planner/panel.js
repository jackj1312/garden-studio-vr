/* Room planner: the inspector (item panel, room panel, floor overview), the catalogue picker and the change list.
 * Every control calls an action on `app` (app.js), which records a change; nothing here edits the state directly. */
import { h, clear, fmtSize, esc, cap, compassOf, len2, sub2, norm2, segDist, add2, scale2, luminance } from "./util.js?v=p7";
import { entryOf, slotOf, sizeM, partColour, roomWalls, roomFloor, resolveColour, mountOf } from "./data.js?v=p7";
import { fitsAt } from "./checks.js?v=p7";

const STYLES = ["Modern", "Contemporary", "Country", "Scandi"];
const PART_LABEL = { all: "Colour", upholstery: "Fabric", legs: "Legs", frame: "Frame", top: "Top", body: "Body", front: "Fronts",
                     worktop: "Worktop", shade: "Shade", fabric: "Fabric", metal: "Metal", wood: "Wood", ceramic: "Base", bedding: "Bedding",
                     throw: "Throw", rug: "Rug", rail: "Rail", hooks: "Hooks", seat: "Seat" };
const GENERIC = {
  wood: [["Natural oak", "#B8936A"], ["Pale oak", "#D7BE98"], ["Smoked oak", "#6E5440"], ["Walnut", "#5C4033"], ["White painted", "#F2F0EA"], ["Painted sage", "#A3AE95"], ["Black", "#2B2B2B"]],
  metal: [["Matt black", "#1E1E1E"], ["Brushed brass", "#B08D57"], ["Chrome", "#C8CCCF"], ["Bronze", "#6B5236"], ["White", "#F2F2F0"]],
  fabric: [["Natural linen", "#E2D9C9"], ["Oatmeal", "#D8CEBF"], ["Cream", "#EFE8DA"], ["Sage", "#9BA58B"], ["Terracotta", "#B5694B"], ["Charcoal", "#4A4C4E"], ["Navy", "#2E3A55"], ["Ochre", "#C99A3B"]],
};
const partFamily = p => /leg|frame|top|body|wood|rail|board/.test(p) ? "wood" : /metal|hook|handle/.test(p) ? "metal" : "fabric";
let styleTab = "All";
let catState = { q: "", group: null, style: "All" };

/* ================================================================ overview (no room open) */
export function renderOverview(app, el) {
  clear(el);
  const st = app.state, H = st.house, db = app.db;
  const rooms = H.rooms.filter(r => r.storey === app.storey);
  const warnCount = id => app.warningsFor(id).size;
  el.append(
    h("div.sec", null,
      h("h2", { text: `${H.name}: ${app.storey === "ground" ? "ground" : "first"} floor` }),
      h("p.muted.small", { text: H.key === "before" ? "The house today, furnished as in the signed-off spec (typical, not surveyed)." : "The approved scheme, finished and furnished as signed off on 1 November." }),
      h("p.small", { html: "Tap a room to open it full screen. In a room you can <b>drag</b> pieces, <b>turn</b> them, swap them for something else that fits, change wall colours, floors, kitchen fronts, curtains and lights, and leave notes. Every change is saved at once; nothing goes to the build until you press <b>Send to build</b>." })),
    h("div.sec", null, h("h3", { text: "Rooms" }),
      h("div.list.rooms-list", null, rooms.map(r => {
        const n = [...st.items.values()].filter(it => it.room === r.id).length, w = warnCount(r.id);
        return h("button.opt", { onclick: () => app.openRoom(r.id) },
          h("span.dot", { style: { background: roomWalls(db, st, r).hex } }),
          h("span", null, h("div.nm", { text: cap(r.name) }), h("div.sub", { text: `${r.area.toFixed(1)} m² · ${n} item${n === 1 ? "" : "s"}${r.change && r.change !== "unchanged" ? " · " + r.change : ""}` })),
          h("span.tag", { html: w ? `<span class="chip warn">${w} to check</span>` : "" }));
      }))),
    legend());
}
function legend() {
  return h("div.sec", null, h("h3", { text: "Reading the plan" }),
    h("ul.small.muted", { style: { margin: 0, paddingLeft: "18px" } },
      h("li", { text: "Numbers match the spec tables (Before and After are numbered separately). New pieces continue the numbering." }),
      h("li", { text: "Dashed outlines are on the ceiling (lights). Dashed arcs are door swings; orange arcs are swings the model had to guess." }),
      h("li", { text: "The coloured band inside each room is its wall colour." }),
      h("li", { text: "Orange outline: something to check (overlap, door swing, outside the room, no room to open drawers)." }),
      h("li", { text: "Road at the bottom, back garden at the top, No. 21 on the left." })));
}

/* ================================================================ room panel */
export function renderRoom(app, el, room) {
  clear(el);
  const st = app.state, db = app.db;
  const items = [...st.items.values()].filter(it => it.room === room.id).sort((a, b) => a.num - b.num);
  const warns = app.warnings;
  el.append(grip(el));
  el.append(h("div.sec", null,
    h("h2", { text: cap(room.name) }),
    h("div.chips", null, h("span.chip", { text: `${room.area.toFixed(1)} m²` }), h("span.chip", { text: room.storey === "ground" ? "Ground floor" : "First floor" }),
      room.change && room.change !== "unchanged" ? h("span.chip.acc", { text: room.change }) : null,
      warns.size ? h("span.chip.warn", { text: `${warns.size} to check` }) : h("span.chip.ok", { text: "No clashes" })),
    room.plain ? h("p.small.muted", { text: room.plain }) : null,
    h("div.row", { style: { marginTop: "8px" } }, h("button.primary", { onclick: () => openCatalogue(app, room), text: "+ Add from the catalogue" }))));

  /* walls */
  const wc = roomWalls(db, st, room);
  const acc = st.rooms.get(room.id)?.accent;
  const palTabs = h("div.seg", null, STYLES.map(sname => h("button", { "aria-pressed": String(app.ui.wallStyle === sname), text: sname, onclick: () => { app.ui.wallStyle = sname; app.refreshPanel(); } })));
  const pal = db.catalogue.wall_palettes[app.ui.wallStyle] || [];
  const edges = room.polygon.map((p, i) => {
    const q = room.polygon[(i + 1) % room.polygon.length], L = len2(sub2(q, p));
    const t = norm2(sub2(q, p)), mid = scale2(add2(p, q), 0.5);
    let n = [t[1], -t[0]];
    if (app.inside(add2(mid, scale2(n, 0.05)), room.polygon)) n = [-n[0], -n[1]];
    return { i, L, name: `${compassOf(n[0], n[1])} wall, ${L.toFixed(2)} m` };
  }).filter(e => e.L > 0.4);
  el.append(h("div.sec", null, h("h3", null, "Walls", h("span.grow"), h("span.tiny", { text: wc.name || wc.hex })),
    palTabs,
    h("div.swatches", { style: { marginTop: "10px" } }, pal.map(c => swatch(c, wc.hex, () => app.setRoom(room, "walls", { name: c.name, hex: c.hex, style: app.ui.wallStyle })))),
    h("div.row", { style: { marginTop: "10px" } }, h("span.small.muted", { text: "Any colour" }), colourInput(wc.hex, hex => app.setRoom(room, "walls", { name: "Custom " + hex, hex }))),
    h("div", { style: { marginTop: "12px" } }, h("div.small.muted", { text: "Accent wall" }),
      h("div.row", { style: { marginTop: "4px" } },
        selectEl([["", "None"], ...edges.map(e => [String(e.i), e.name])], acc ? String(acc.edge) : "", v => {
          if (v === "") app.setRoom(room, "accent", null);
          else app.setRoom(room, "accent", { edge: +v, name: acc?.name || "Soft clay", hex: acc?.hex || "#CDB8A3" });
        }),
        acc ? colourInput(acc.hex, hex => app.setRoom(room, "accent", { ...acc, hex, name: "Custom " + hex })) : null),
      acc ? h("div.swatches", { style: { marginTop: "8px" } }, pal.map(c => swatch(c, acc.hex, () => app.setRoom(room, "accent", { ...acc, name: c.name, hex: c.hex })))) : null)));

  /* floor */
  const fl = roomFloor(db, st, room), wet = /bath|wc|cloak|en-suite|utility|porch|lobby/i.test(room.name);
  el.append(h("div.sec", null, h("h3", null, "Floor", h("span.grow"), h("span.tiny", { text: fl.name })),
    groupedList(db.catalogue.floors.filter(f => f.rooms === "any" || (wet ? f.rooms === "wet" : true)), f => f.id === fl.id,
      f => app.setRoom(room, "floor", { id: f.id, name: f.name, hex: f.hex, pattern: f.pattern, unit_mm: f.unit_mm }),
      f => (f.rooms === "dry" && wet ? "not for wet rooms" : f.rooms === "wet" ? "tile" : "")),
  ));

  /* kitchen */
  const kitchenItems = items.filter(it => ["kitchen_unit", "kitchen_wall_units", "island"].includes(slotOf(db, it)));
  if (kitchenItems.length) {
    const o = st.rooms.get(room.id) || {};
    const runFront = o.fronts || partColour(db, st, kitchenItems.find(i => slotOf(db, i) !== "island") || kitchenItems[0], "front");
    const isl = kitchenItems.find(i => slotOf(db, i) === "island");
    const islFront = isl ? (o.island_fronts || partColour(db, st, isl, "front")) : null;
    const top = o.worktop || partColour(db, st, kitchenItems[0], "worktop");
    const pickF = (v, field) => app.setRoom(room, field, { id: v.id, name: v.name, hex: v.hex, door: v.door });
    el.append(h("div.sec", null, h("h3", { text: "Kitchen" }),
      h("div.small.muted", { text: `Fronts on the runs · now: ${runFront.name || runFront.hex}` }),
      groupedList(db.catalogue.kitchen_fronts, f => f.hex === runFront.hex, f => pickF(f, "fronts")),
      isl ? h("div.small.muted", { style: { marginTop: "10px" }, text: `Island fronts · now: ${islFront.name || islFront.hex}` }) : null,
      isl ? groupedList(db.catalogue.kitchen_fronts, f => f.hex === islFront.hex, f => pickF(f, "island_fronts")) : null,
      h("div.small.muted", { style: { marginTop: "10px" }, text: `Worktops · now: ${top.name || top.hex}` }),
      groupedList(db.catalogue.worktops, f => f.hex === top.hex, f => app.setRoom(room, "worktop", { id: f.id, name: f.name, hex: f.hex }))));
  }

  /* windows: curtains and blinds */
  const wins = app.windowsOf(room);
  if (wins.length) {
    const dressings = db.catalogue.entries.filter(e => e.slot === "window_dressing" && !e.signed_off);
    el.append(h("div.sec", null, h("h3", { text: "Curtains and blinds" }),
      wins.map(w => {
        const cur = app.dressingOf(room, w);
        const curE = cur && entryOf(db, cur);
        return h("div", { style: { marginBottom: "12px" } },
          h("div.small", null, h("b", { text: cap(w.label) }), h("span.tiny", { text: ` · ${Math.round(w.width * 1000)} mm wide` })),
          h("div.row", { style: { marginTop: "4px" } }, selectEl([["", "Nothing (bare window)"], ...(cur ? [["cur", "Now: " + cur.type]] : []),
            ...STYLES.flatMap(sty => dressings.filter(e => e.styles[0] === sty).map(e => [e.id, `${sty} · ${e.name}`]))], cur ? "cur" : "",
            v => { if (v === "cur") return; app.setDressing(room, w, v ? db.entries.get(v) : null); })),
          cur ? h("div.swatches", { style: { marginTop: "6px" } }, GENERIC.fabric.map(([name, hex]) => swatch({ name, hex }, partColour(db, st, cur, cur.materials?.fabric ? "fabric" : "all").hex,
            () => app.setFinish(cur, cur.materials?.fabric ? "fabric" : "all", { name, hex })))) : null);
      })));
  }

  /* lighting */
  const lights = items.filter(it => it.category === "lighting");
  if (lights.length) {
    el.append(h("div.sec", null, h("h3", null, "Lighting", h("span.grow"),
      h("button.ghost", { text: "All on", onclick: () => app.setLamps(room, lights, true) }), h("button.ghost", { text: "All off", onclick: () => app.setLamps(room, lights, false) })),
      h("div.list", null, lights.map(it => h("div.opt", null, h("span.num", { text: it.num }),
        h("span", null, h("div.nm", { text: cap(it.type) }), h("div.sub", { text: entryOf(db, it)?.name || "" })),
        h("span.row.tight", null, h("button.ghost", { text: "Change", onclick: () => app.select(it.id, true) }),
          h("button", { "aria-pressed": String(!!it.lampOn), text: it.lampOn ? "On" : "Off", onclick: () => app.toggleLamp(it), style: it.lampOn ? { background: "var(--accent-soft)" } : {} })))))));
  }

  el.append(notesSec(app, { room: room.id }, "Notes on this room"));

  /* items list */
  el.append(h("div.sec", null, h("h3", { text: `In this room (${items.length})` }),
    h("div.list.items-list", null, items.map(it => {
      const w = warns.get(it.id);
      return h("button.opt", { onclick: () => app.select(it.id, true) },
        h("span.num" + (w ? ".warn" : ""), { text: it.num }),
        h("span", null, h("div.nm", { text: cap(it.type) }), h("div.sub", { text: `${fmtSize(it.size_mm)} mm${w ? " · " + w[0].text : ""}` })),
        h("span.tag", { text: it.added ? "added" : it.swapped ? "swapped" : "" }));
    }))));
}

/* ================================================================ item panel */
export function renderItem(app, el, it) {
  clear(el);
  const st = app.state, db = app.db, e = entryOf(db, it), room = st.house.roomById.get(it.room);
  const warns = app.warnings.get(it.id) || [];
  const slot = e?.slot || "fixed";
  el.append(grip(el));
  el.append(h("div.sec", null,
    h("div.row", null, h("button.ghost", { text: "‹ " + cap(room?.name || "Room"), onclick: () => app.select(null) })),
    h("h2", null, h("span.num", { text: it.num, style: { marginRight: "8px", verticalAlign: "2px" } }), cap(it.type)),
    h("div.chips", { style: { marginTop: "6px" } },
      h("span.chip", { text: cap(it.category.replace("_", " ")) }),
      it.added ? h("span.chip.acc", { text: "added by you" }) : it.swapped ? h("span.chip.acc", { text: "swapped by you" }) : h("span.chip.ok", { text: "signed off (spec v1)" }),
      e?.placeholder ? h("span.chip", { text: "planner shape", title: "Drawn as a proportioned shape here. " + (e.model_status === "free, not downloaded" ? "A free 3D model exists (not downloaded)." : "The build makes it parametrically.") }) : h("span.chip.ok", { text: "3D model" }),
      e?.styles ? h("span.chip", { text: e.styles.join(" · ") }) : null),
    warns.length ? h("ul.warns", { style: { marginTop: "10px" } }, warns.map(w => h("li", { text: "⚠ " + w.text }))) : null));

  /* actions */
  const fixed = slot === "fixed" || slot === "kitchen_unit" || slot === "kitchen_wall_units" || it.asset?.source === "elements";
  el.append(h("div.sec", null, h("div.actions", null,
    h("button", { text: "⟲ 15°", title: "Turn left 15° ([)", onclick: () => app.rotateBy(it, 15) }),
    h("button", { text: "15° ⟳", title: "Turn right 15° (])", onclick: () => app.rotateBy(it, -15) }),
    h("button", { text: "Turn 90°", title: "R", onclick: () => app.rotateBy(it, -90) }),
    h("button", { text: "Duplicate", title: "D", onclick: () => app.duplicate(it) }),
    it.category === "lighting" ? h("button", { "aria-pressed": String(!!it.lampOn), text: it.lampOn ? "Lamp on" : "Lamp off", onclick: () => app.toggleLamp(it) }) : null,
    h("button.danger", { text: "Delete", title: "Delete / Backspace", onclick: () => app.remove(it) })),
    h("p.tiny", { style: { margin: "8px 0 0" }, text: "Drag it on the plan · arrows nudge 50 mm (Shift 10 mm) · R turns 90° · Shift or Alt while dragging = no snapping" }),
    fixed && it.asset?.source === "elements" ? h("p.tiny", { text: "Drawn on the architect's plans: moving it here records a request to the architect, not a free change." }) : null));

  /* what it is */
  const [W, D, Hh] = it.size_mm;
  const src = it.asset || {};
  const srcText = src.source === "polyhaven" ? h("span", null, "Poly Haven ", h("a", { href: src.url || `https://polyhaven.com/a/${src.id}`, target: "_blank", rel: "noopener", text: src.id }), ` (${src.licence || "CC0"})`)
    : src.source === "elements" ? `the architect's drawing (${src.element})` : e?.source?.source === "polyhaven" ? h("span", null, "Poly Haven ", h("a", { href: e.source.url, target: "_blank", rel: "noopener", text: e.source.id }), " (CC0)")
    : `made by the build (${src.kind || e?.source?.kind || "parametric"})`;
  const details = src.source === "parametric" ? Object.entries(src).filter(([k]) => !["source", "kind"].includes(k)).map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(", ") : "";
  el.append(h("div.sec", null, h("h3", { text: "What it is" }),
    e?.description && e.description !== it.type ? h("p.small", { style: { marginTop: 0 }, text: cap(e.name) + " — " + e.description }) : e ? h("p.small", { style: { marginTop: 0 }, text: cap(e.name) }) : null,
    h("dl.kv", null,
      h("dt", { text: "Size" }), h("dd", { text: `${W} wide × ${D} deep × ${Hh} high mm` }),
      h("dt", { text: "Where" }), h("dd", { text: `${cap(room?.name || it.room)}; x ${it.position_m[0].toFixed(2)}, z ${it.position_m[2].toFixed(2)}, ${Math.round(it.position_m[1] * 1000 - (room?.floor || 0) * 1000)} mm up; faces ${Math.round(it.yaw_deg || 0)}°` }),
      h("dt", { text: "Source" }), h("dd", null, srcText, details ? h("div.tiny", { text: details }) : null),
      h("dt", { text: "3D" }), h("dd", { text: e ? (e.model ? "real model" : e.model_status === "free, not downloaded" ? "free model online (not downloaded); a shape here" : e.model_status === "drawn (from the house model)" ? "drawn in the house model" : "a proportioned shape (no free model)") : "a shape" }),
      h("dt", { text: "Provenance" }), h("dd", { text: `${it.provenance || "proposed"}${it.status ? " · " + it.status : ""}` }),
      h("dt", { text: "Why here" }), h("dd", { text: it.evidence || (it.added ? "added in the planner" : "—") }))));

  /* finishes per part */
  const parts = Object.keys(it.materials || {}).filter(p => !["note"].includes(p));
  if (parts.length && !(parts.length === 1 && it.materials[parts[0]] === "as asset" && !e?.options?.all)) {
    el.append(h("div.sec", null, h("h3", { text: "Finish and colour" }),
      parts.map(p => {
        const cur = partColour(db, st, it, p);
        const opts = (e?.options?.[p] || (GENERIC[partFamily(p)] || []).map(([name, hex]) => ({ name, hex })));
        return h("div", null,
          h("div.sw-row", null, h("span.lab", { text: PART_LABEL[p] || cap(p) }), h("span.small", { text: cur.name || cur.hex })),
          h("div.swatches", { style: { marginBottom: "10px" } }, opts.map(o => swatch(o, cur.hex, () => app.setFinish(it, p, o))), colourInput(cur.hex, hex => app.setFinish(it, p, { name: "Custom " + hex, hex }))));
      })));
  }

  /* swap */
  if (!fixed) el.append(swapSec(app, it, e));
  el.append(notesSec(app, { item: it.id }, "Notes on this piece"));
}

function swapSec(app, it, e) {
  const db = app.db, st = app.state;
  const slot = e?.slot;
  const cands = db.catalogue.entries.filter(x => x.slot === slot && x.id !== it.catalogue);
  const sec = h("div.sec", null, h("h3", { text: "Change it for…" }));
  if (!cands.length) { sec.append(h("p.small.muted", { text: "Nothing else in the catalogue for this kind of piece yet." })); return sec; }
  const tabs = h("div.seg", { style: { marginBottom: "8px" } }, ["All", ...STYLES].map(sname => h("button", { "aria-pressed": String(styleTab === sname), text: sname, onclick: () => { styleTab = sname; app.refreshPanel(); } })));
  sec.append(tabs);
  const fits = [], nofit = [];
  for (const c of cands) {
    if (styleTab !== "All" && !c.styles.includes(styleTab)) continue;
    const pose = app.swapPose(it, c);
    const f = fitsAt(db, st, it, c, pose);
    (f.ok ? fits : nofit).push({ c, why: f.why });
  }
  const row = ({ c, why }) => h("button.opt" + (why.length ? ".nofit" : ""), { onclick: () => app.swap(it, c), title: why.join("; ") },
    h("span.ic", { style: { background: Object.values(c.part_hex || {}).find(Boolean) || "#ccc" } }),
    h("span", null, h("div.nm", { text: c.name }), h("div.sub", { text: `${fmtSize(c.size_mm)} mm · ${c.description}${why.length ? " · " + why[0] : ""}` })),
    h("span.tag", { html: `${c.styles.slice(0, 2).join("<br>")}<br><i>${c.model ? "3D model" : c.source.source === "polyhaven" ? "free model" : "shape"}</i>${c.signed_off ? "<br>in spec" : ""}` }));
  if (styleTab === "All") {
    for (const sname of STYLES) {
      const g = fits.filter(x => x.c.styles[0] === sname);
      if (!g.length) continue;
      sec.append(h("div.tiny", { style: { margin: "8px 0 2px", fontWeight: 650 }, text: sname }), h("div.list", null, g.map(row)));
    }
  } else sec.append(h("div.list", null, fits.map(row)));
  if (!fits.length) sec.append(h("p.small.muted", { text: "Nothing in this style fits the space here." }));
  if (nofit.length) sec.append(h("details", null, h("summary", { text: `Doesn't fit here (${nofit.length})` }), h("div.list", null, nofit.map(row))));
  return sec;
}

function notesSec(app, target, title) {
  const key = target.item ? "item:" + target.item : "room:" + target.room;
  const notes = app.state.notes.get(key) || [];
  const ta = h("textarea", { placeholder: "Write a note for the studio (saved with your changes)…" });
  return h("div.sec", null, h("h3", { text: title }),
    notes.map(n => h("div.note", null, n.text, h("span.tiny", { text: new Date(n.at).toLocaleString() }))),
    ta, h("div.row", { style: { marginTop: "6px", justifyContent: "flex-end" } }, h("button", { text: "Save note", onclick: () => { const t = ta.value.trim(); if (t) app.addNote(target, t); } })));
}

/* ================================================================ catalogue picker */
export function openCatalogue(app, room) {
  const db = app.db, cat = db.catalogue;
  const m = h("div.modal", { onclick: ev => { if (ev.target === m) m.remove(); } });
  const body = h("div.body");
  const search = h("input", { type: "search", placeholder: "Search: sofa, oak, lamp, rug…", value: catState.q, oninput: () => { catState.q = search.value; draw(); } });
  const groupBar = h("div.chips", { style: { marginTop: "10px" } });
  const styleBar = h("div.seg", { style: { marginTop: "10px" } });
  function draw() {
    clear(groupBar); clear(styleBar); clear(body);
    groupBar.append(...[null, ...cat.groups.map(g => g.name)].map(g => h("button.chip", { style: catState.group === g ? { background: "var(--accent-soft)", color: "var(--accent)" } : {}, text: g || "Everything", onclick: () => { catState.group = g; draw(); } })));
    styleBar.append(...["All", ...STYLES].map(sname => h("button", { "aria-pressed": String(catState.style === sname), text: sname, onclick: () => { catState.style = sname; draw(); } })));
    const q = catState.q.toLowerCase().trim();
    const groups = cat.groups.filter(g => !catState.group || g.name === catState.group);
    let shown = 0;
    for (const g of groups) for (const slot of g.slots) {
      const list = cat.entries.filter(e => e.slot === slot && (catState.style === "All" || e.styles.includes(catState.style))
        && (!q || (e.name + " " + e.description + " " + slot + " " + e.styles.join(" ")).toLowerCase().includes(q))
        && !(e.signed_off && cat.entries.some(x => x !== e && !x.signed_off && x.name === e.name)));
      if (!list.length) continue;
      shown += list.length;
      body.append(h("div.tiny", { style: { margin: "12px 0 4px", fontWeight: 650 }, text: `${cat.slot_names[slot] || slot} (${list.length})` }),
        h("div.list", null, list.slice(0, 40).map(e => h("button.opt", { onclick: () => { m.remove(); app.addEntry(e, room); } },
          h("span.ic", { style: { background: Object.values(e.part_hex || {}).find(Boolean) || "#ccc" } }),
          h("span", null, h("div.nm", { text: e.name }), h("div.sub", { text: `${fmtSize(e.size_mm)} mm · ${e.description}` })),
          h("span.tag", { html: `${e.styles.slice(0, 2).join("<br>")}<br><i>${e.model ? "3D model" : e.source.source === "polyhaven" ? "free model" : "shape"}</i>` })))));
    }
    if (!shown) body.append(h("p.muted", { text: "Nothing matches." }));
  }
  m.append(h("div.box", null,
    h("header", null, h("h2", { text: `Add to ${room.name}` }), h("button.ghost", { text: "Close", onclick: () => m.remove() }),
      h("div", { style: { flexBasis: "100%" } }, search, groupBar, styleBar)),
    body,
    h("footer", null, h("span.tiny", { style: { flex: 1 }, text: `${cat.counts.entries} pieces. "free model" = a CC0 Poly Haven model exists (not downloaded yet); "shape" = the build makes it. The new piece lands in a free spot; drag it where you want it.` }))));
  document.body.append(m);
  draw();
  setTimeout(() => search.focus(), 30);
}

/* ================================================================ the change list */
export function openChanges(app, sendMode = false) {
  const store = app.store;
  const m = h("div.modal", { onclick: ev => { if (ev.target === m) m.remove(); } });
  const active = store.active, undone = store.undone, sent = store.sent;
  const note = h("textarea", { placeholder: "Anything the studio should know about this batch (optional)" });
  const row = c => h("div.change" + (c.status === "undone" ? ".undone" : ""), null,
    h("span", { text: c.summary }), h("span.tiny", { text: c.version === "before" ? "Before" : "After" }),
    h("span.tiny", { text: `${new Date(c.at).toLocaleString()}${c.status === "sent" ? " · sent in " + c.batch : ""}` }));
  const body = h("div.body", null,
    sendMode ? h("p", { html: `These <b>${active.length}</b> change${active.length === 1 ? "" : "s"} will be written as one batch. The studio makes <b>spec v2</b> from it (the signed-off spec v1 is never edited) and does one rebuild. You can keep planning afterwards.` }) : null,
    !active.length ? h("p.muted", { text: "No unsent changes." }) : null,
    active.map(row),
    !sendMode && undone.length ? [h("div.tiny", { style: { margin: "14px 0 4px", fontWeight: 650 }, text: "Undone (Redo brings them back)" }), undone.map(row)] : null,
    !sendMode && sent.length ? [h("div.tiny", { style: { margin: "14px 0 4px", fontWeight: 650 }, text: `Already sent (${store.batches.length} batch${store.batches.length === 1 ? "" : "es"})` }), sent.slice(-30).map(row)] : null,
    sendMode ? h("div", { style: { marginTop: "12px" } }, note) : null,
    store.mode !== "server" ? h("p.banner", { text: "This device cannot reach the studio server: changes are kept in this browser only. Open the planner from the studio address to send them." }) : null);
  const sendB = h("button.primary", { text: `Send ${active.length} to build`, disabled: !active.length || store.mode !== "server",
    onclick: async () => {
      sendB.disabled = true; sendB.textContent = "Sending…";
      try { const j = await store.send(note.value.trim()); m.remove(); app.toast(`Sent ${j.count} change${j.count === 1 ? "" : "s"}: ${j.file}`); app.afterChange(); }
      catch (err) { sendB.disabled = false; sendB.textContent = "Try again"; body.append(h("p.banner", { text: String(err.message || err) })); }
    } });
  m.append(h("div.box", null,
    h("header", null, h("h2", { text: sendMode ? "Send to build" : "Your changes" }), h("button.ghost", { text: "Close", onclick: () => m.remove() })),
    body,
    h("footer", null, sendMode ? null : h("button", { text: "Undo last", disabled: !store.canUndo(), onclick: async () => { await app.undo(); m.remove(); openChanges(app); } }), sendB)));
  document.body.append(m);
}

/* ================================================================ bits */
function swatch(c, curHex, onclick) {
  return h("button.sw", { style: { background: c.hex }, title: c.name, "aria-label": c.name, "aria-pressed": String((curHex || "").toLowerCase() === c.hex.toLowerCase()), onclick });
}
function colourInput(hex, on) {
  const i = h("input", { type: "color", value: /^#[0-9a-f]{6}$/i.test(hex) ? hex.toLowerCase() : "#cccccc", title: "Pick any colour" });
  i.addEventListener("change", () => on(i.value.toUpperCase()));
  return i;
}
function selectEl(opts, value, on) {
  const s = h("select", null, opts.map(([v, t]) => h("option", { value: v, text: t, selected: v === value })));
  s.addEventListener("change", () => on(s.value));
  return s;
}
function groupedList(list, isCur, pick, note = () => "") {
  const wrap = h("div");
  for (const sname of STYLES) {
    const g = list.filter(f => f.styles[0] === sname);
    if (!g.length) continue;
    wrap.append(h("div.tiny", { style: { margin: "8px 0 2px", fontWeight: 650 }, text: sname }),
      h("div.list", null, g.map(f => h("button.opt" + (isCur(f) ? ".current" : ""), { onclick: () => pick(f) },
        h("span.ic", { style: { background: f.hex } }), h("span", null, h("div.nm", { text: f.name }), h("div.sub", { text: [f.styles.join(" · "), note(f)].filter(Boolean).join(" · ") })),
        h("span.tag", { text: isCur(f) ? "now" : "" })))));
  }
  return wrap;
}
function grip(el) {
  return h("div.sheet-grip", null, h("button", { "aria-label": "Show or hide details", onclick: () => el.classList.toggle("collapsed") }));
}
