/* Room planner: the inspector (item panel, room panel, floor overview), the catalogue picker and the change list.
 * Every control calls an action on `app` (app.js), which records a change; nothing here edits the state directly. */
import { h, clear, fmtSize, esc, cap, compassOf, len2, sub2, norm2, segDist, add2, scale2, luminance } from "./util.js?v=p8";
import { entryOf, slotOf, sizeM, partColour, roomWalls, roomFloor, resolveColour, mountOf } from "./data.js?v=p8";
import {fineMove} from '../furnish/placement.mjs';
import { catalogueMatch, roomTypes, styleName, wallFaces } from './shared.mjs';
import { fitsAt } from "./checks.js?v=p8";

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
let catState = { q:"", kind:"", style:"", room:"current" };

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
      h("p.small", { html: "Tap a room to open it full screen. In a room you can <b>drag</b> pieces, <b>turn</b> them, swap them for something else that fits, change wall colours, floors, kitchen fronts, curtains and lights, and leave notes. Use <b>Save layout</b> to see your furniture and finishes in the walkthrough. Notes and building requests stay in <b>Changes</b> until you send them to the studio." })),
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
  el.lastChild.append(h('a',{className:'planner-walk',href:'house.html?'+new URLSearchParams({site:db.site,version:st.house.elements}),
    target:'_blank',rel:'noopener',text:'Open this saved version in the walkthrough ↗'}));

  /* walls */
  const wc = roomWalls(db, st, room);
  const faces=wallFaces(st,room.id), unique=[...new Map(faces.map(f=>[f.id,f])).values()];
  const face=unique.find(f=>f.id===app.ui.wallId);
  const palette=db.catalogue.wall_palettes[app.ui.wallStyle] || [];
  const colours=new Set(unique.map(f=>st.wallColours?.[f.id] || wc.hex));
  const colour=face ? (st.wallColours?.[face.id] || wc.hex) : colours.size===1 ? [...colours][0] : wc.hex;
  const paint=hex=>face ? app.changeFurniture(s=>s.setWall(face.id,hex)) : app.setRoom(room,'walls',hex?{hex}:null);
  const options=[['','All walls in '+room.name],...unique.map(f=>{
    const name=f.a ? compassOf(-f.normal[0],-f.normal[1])+' wall · '+len2(sub2(f.b,f.a)).toFixed(2)+' m' : 'Return';
    return [f.id,name+' · '+f.wall];
  })];
  const selector=selectEl(options,face?.id || '',id=>{app.ui.wallId=id;app.render(true);});
  selector.setAttribute('aria-label','Wall face to paint');
  el.append(h('div.sec',null,h('h3',{text:'Wall paint'}),selector,!face && colours.size>1 ? h('p.tiny',{text:'These faces have different colours.'}) : null,
    h('div.seg',{style:{marginTop:'8px'}},STYLES.map(sty=>h('button',{'aria-pressed':String(app.ui.wallStyle===sty),text:sty,
      onclick:()=>{app.ui.wallStyle=sty;app.refreshPanel();}}))),
    h('div.swatches',{style:{marginTop:'8px'}},palette.map(c=>swatch(c,colour,()=>paint(c.hex)))),
    h('div.row',{style:{marginTop:'8px'}},h('span.small.muted',{text:'Custom paint'}),colourInput(colour,paint),
      h('button.ghost',{text:'Use signed finish',onclick:()=>paint(null)}))));

  /* floor */
  const fl = roomFloor(db, st, room), wet = /bath|wc|cloak|en-suite|utility|porch|lobby/i.test(room.name);
  el.append(h("div.sec", null, h("h3", null, "Floor", h("span.grow"), h("span.tiny", { text: fl.name })),
    st.rooms.get(room.id)?.floor ? h('button.ghost',{text:'Use signed floor',onclick:()=>app.setRoom(room,'floor',null)}) : null,
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
    const dressings = [...db.entries.values()].filter(e => e.kit && e.slot === "window_dressing");
    el.append(h("div.sec", null, h("h3", { text: "Curtains and blinds" }),
      wins.map(w => {
        const cur = app.dressingOf(room, w);
        const curE = cur && entryOf(db, cur);
        return h("div", { style: { marginBottom: "12px" } },
          h("div.small", null, h("b", { text: cap(w.label) }), h("span.tiny", { text: ` · ${Math.round(w.width * 1000)} mm wide` })),
          h("div.row", { style: { marginTop: "4px" } }, selectEl([["", "Nothing (bare window)"], ...(cur ? [["cur", "Now: " + cur.type]] : []),
            ...app.db.kit.styles.map(styleName).flatMap(sty => dressings.filter(e => e.styles[0] === sty).map(e => [e.id, `${sty} · ${e.name}`]))], cur ? "cur" : "",
            v => { if (v === "cur") return; app.setDressing(room, w, v ? db.entries.get(v) : null); })),
          cur ? h("div.swatches", { style: { marginTop: "6px" } }, GENERIC.fabric.map(([name, hex]) => swatch({ name, hex }, partColour(db, st, cur, cur.materials?.fabric ? "fabric" : "all").hex,
            () => app.setFinish(cur, cur.materials?.fabric ? "fabric" : "all", { name, hex })))) : null);
      })));
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
  const fixed = !it.shared && (slot === 'fixed' || slot === 'kitchen_unit' || slot === 'kitchen_wall_units' || it.asset?.source === 'elements');
  el.append(h("div.sec", null, h("div.actions", null,
    h("button", { text: "⟲ 15°", title: "Turn left 15° ([)", onclick: () => app.rotateBy(it, 15) }),
    h("button", { text: "15° ⟳", title: "Turn right 15° (])", onclick: () => app.rotateBy(it, -15) }),
    it.shared ? h("button",{text:"Raise 1 cm",onclick:()=>app.putFurniture(fineMove(it.shared,"PageUp"))}) : null,
    it.shared ? h("button",{text:"Lower 1 cm",onclick:()=>app.putFurniture(fineMove(it.shared,"PageDown"))}) : null,
    h("button", { text: "Turn 90°", title: "R", onclick: () => app.rotateBy(it, -90) }),
    h("button", { text: "Duplicate", title: "D", onclick: () => app.duplicate(it) }),
    h("button.danger", { text: "Delete", title: "Delete / Backspace", onclick: () => app.remove(it) })),
    h("p.tiny", { style: { margin: "8px 0 0" }, text: "Drag it on the plan · arrows nudge 10 mm (Shift 1 mm) · R turns 90° · Shift or Alt while dragging = no snapping" }),
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
  const cands = it.shared ? [...db.entries.values()].filter(x=>x.kit && x.kind===it.shared.kind && x.id!==it.catalogue) : db.catalogue.entries.filter(x => x.slot === slot && x.id !== it.catalogue);
  const sec = h("div.sec", null, h("h3", { text: "Change it for…" }));
  if (!cands.length) { sec.append(h("p.small.muted", { text: "Nothing else in the catalogue for this kind of piece yet." })); return sec; }
  const availableStyles = it.shared ? app.db.kit.styles.map(styleName) : STYLES;
  const tabs = h("div.seg", { style: { marginBottom: "8px" } }, ["All", ...availableStyles].map(sname => h("button", { "aria-pressed": String(styleTab === sname), text: sname, onclick: () => { styleTab = sname; app.refreshPanel(); } })));
  sec.append(tabs);
  const fits = [], nofit = [];
  for (const c of cands) {
    if (styleTab !== "All" && !c.styles.includes(styleTab)) continue;
    const f = it.shared ? app.swapCandidate(it,c) : fitsAt(db,st,it,c,app.swapPose(it,c));
    (f.ok ? fits : nofit).push({ c, why: f.reasons || f.why });
  }
  const row = ({ c, why }) => h("button.opt" + (why.length ? ".nofit" : ""), { onclick: () => app.swap(it, c), title: why.join("; ") },
    c.thumbnail ? h("img.ic",{src:"/tools/library/kit/"+c.thumbnail,alt:"",loading:"lazy"}) : h("span.ic", { style: { background: Object.values(c.part_hex || {}).find(Boolean) || "#ccc" } }),
    h("span", null, h("div.nm", { text: c.name }), h("div.sub", { text: `${fmtSize(c.size_mm)} mm · ${c.description}${why.length ? " · " + why[0] : ""}` })),
    h("span.tag", { html: `${c.styles.slice(0, 2).join("<br>")}<br><i>${c.model ? "3D model" : c.source.source === "polyhaven" ? "free model" : "shape"}</i>${c.signed_off ? "<br>in spec" : ""}` }));
  if (styleTab === "All") {
    for (const sname of availableStyles) {
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
  const entries=app.db.kit.items, kinds=[...new Set(entries.map(e=>e.kind))].sort(), types=[...new Set(entries.flatMap(e=>e.roomTypes))].filter(t=>t!=='any').sort();
  const modal=h('div.modal',{onclick:ev=>{if(ev.target===modal)modal.remove();}}), body=h('div.body'), count=h('span.tiny',{'aria-live':'polite'});
  const search=h('input',{type:'search','aria-label':'Search studio catalogue',placeholder:'Search furniture and fittings',value:catState.q,
    oninput:()=>{catState.q=search.value;draw();}});
  const selector=(label,key,choices)=>h('label',null,label,selectEl(choices,catState[key],v=>{catState[key]=v;draw();}));
  const filters=h('div.kit-filters',null,
    selector('Room type','room',[['current','This room'],['','All rooms'],...types.map(t=>[t,cap(t)])]),
    selector('Kind','kind',[['','All kinds'],...kinds.map(t=>[t,cap(t.replaceAll('_',' '))])]),
    selector('Style','style',[['','All styles'],...app.db.kit.styles.map(t=>[t,styleName(t)])]));
  function draw() {
    const roomFilter=catState.room==='current'?roomTypes(room):catState.room;
    const list=entries.filter(e=>catalogueMatch(e,{room:roomFilter,kind:catState.kind,style:catState.style,search:catState.q}));
    clear(body);count.textContent=list.length+' of '+entries.length+' studio pieces';
    if(!list.length) {body.append(h('p.muted',{text:'No pieces match these filters.'}));return;}
    body.append(h('div.kit-results',null,list.map(e=>h('button.kit-tile',{'data-catalogue-id':e.id,onclick:()=>{modal.remove();app.addEntry(app.db.entries.get(e.id),room);}},
      h('img',{src:'/tools/library/kit/'+e.thumbnail,alt:'',loading:'lazy',width:128,height:128}),
      h('b',{text:e.name}),h('small',{text:styleName(e.style)+' · '+fmtSize(e.size_m.map(v=>v*1000))+' mm'})))));
  }
  modal.append(h('div.box',null,h('header',null,h('h2',{text:'Add to '+room.name}),h('button.ghost',{text:'Close',onclick:()=>modal.remove()}),
    h('div',{style:{flexBasis:'100%'}},search,filters)),body,h('footer',null,count)));
  document.body.append(modal);draw();search.focus();
}

/* ================================================================ the change list */
export function openChanges(app, sendMode = false) {
  const store = app.store;
  const m = h("div.modal", { onclick: ev => { if (ev.target === m) m.remove(); } });
  const active = store.active, undone = store.undone, sent = store.sent;
  const receipts=new Map([...app.sessions.values()].flatMap(s=>(s.moveReceipts||[]).map(r=>[r.sourceId,r])));
  const note = h("textarea", { placeholder: "Anything the studio should know about this batch (optional)" });
  const row = c => h("div.change" + (c.status === "undone" ? ".undone" : ""), null,
    h("span", { text: c.summary }), h("span.tiny", { text: c.version === "before" ? "Before" : "After" }),
    h("span.tiny", { text: `${new Date(c.at).toLocaleString()}${store.imported.has(c.id) ? ' · carried into starting layout' : ''}${c.status === "sent" ? " · sent in " + c.batch : ""}` }),
    receipts.has(c.id) ? h('span.tiny',{text:(receipts.get(c.id).status==='adjusted'?'Adjusted by '+Math.round(Math.hypot(...receipts.get(c.id).delta)*1000)+' mm':'Pending')+' · '+receipts.get(c.id).reason}) : null);
  const body = h("div.body", null,
    sendMode ? h("p", { text: `Send these ${active.length} signed-spec requests as one batch for the next studio build. Furniture and room finishes have their own Save layout button.` }) : null,
    app.session?.layout.dirty ? h('p.banner',{text:'This room has an unsaved furniture or finish edit. Close this list and choose Save layout to open it in the walkthrough.'}) : null,
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
