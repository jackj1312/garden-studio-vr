# House data contract (contract 1)

What the Blender generator (traced architect drawings → Blender → GLB) must write so `house.html`
(`src/house/`) can show it. The reference implementation is `tools/house/make_fixture.py`, which writes
`assets/sites/house-fixture/`. Everything here is read by `src/house/model.js`, `viewer.js`, `geom.js`,
`edits.js`, `editops.js`, `rules.js`, `regs.js` and `requests.js`; a field not listed is ignored.

## 0. Frame and units

- Metres. **Viewer frame = glTF frame: +Y up.** Blender (x, y, z) → viewer (x, z, −y). The glTF exporter
  does this conversion for the GLB (`export_yup=True`); every JSON file below is written **in the viewer
  frame** (convert once, as `conv()` does in the fixture script).
- Plan coordinates in JSON are `[x, z]` pairs in the viewer frame. Heights are absolute viewer y
  (y = 0 is the site datum; the fixture puts ground level at 0 and existing FFL at 0.15).
- "Facing" angles (`yawDeg`) are about +Y; yaw 0 looks along −z, 90 looks along −x, 180 along +z.

## 1. Files per site

```
assets/sites/<site>/
  versions.json                 the list of versions (section 2)
  <glb>                         one GLB per version (section 3)
  <stages json>                 one sidecar per version: stages, sections, spawns (section 4)
  <elements json>               one parametric element file per version (section 5)
  regs.json + regs_map.json     the regulations dataset and which rules attach to which parts (section 12) — optional
  materials.json                each material's real tile size, for the UVs of walls rebuilt after an edit (section 15)
  sheets.json + sheets/*.png    rendered drawing sheets and per-element crops for the PLANS tab (section 14) — optional
  captures.json                 photos / splats of the actual build, per stage (section 13, hook only) — optional
  change_requests/<version>/    written by the server (section 10)
  inspections/<version>/        written by the server (section 11)
```
Open with `house.html?site=<site>&version=<id>&mode=customer|builder|inspector|architect`.

## 2. versions.json

```json
{
  "contract": 1,
  "name": "12 Example Road",
  "as_built_now": "as-built-now",          // the "Before" of the Before / After switch
  "default": "approved-4915-2B",           // opened first (the "After")
  "versions": [
    { "id": "existing-2022", "name": "Existing 2022", "description": "Survey, BDS 4915.1",
      "kind": "existing", "base": null,
      "glb": "existing-2022.glb", "elements": "existing-2022_elements.json", "stages": "existing-2022.json" },
    { "id": "as-built-now", "name": "As built now", "description": "Existing + the completed porch",
      "kind": "as_built", "base": "existing-2022", "glb": "...", "elements": "...", "stages": "..." },
    { "id": "approved-4915-2B", "name": "Approved scheme 4915.2B", "description": "Two-storey rear extension (not built)",
      "kind": "proposal", "base": "as-built-now", "glb": "...", "elements": "...", "stages": "..." }
  ]
}
```
- `id`: `[a-z0-9_-]`, stable (edits, change requests and inspections are saved against it). `kind`: `existing | as_built | proposal`.
- `base`: the version this one builds from (its stage 1 is that version's finished state). Informative for
  now; each version's GLB is still complete on its own.
- Before / After in the viewer = `as_built_now` vs the proposal currently chosen.
- Every version is viewable in every mode; nothing in a version is mode-specific.
- Optional per version: `as_built_default: {"<mode>": true}` (the As-built toggle starts on in that mode; nothing else
  turns it on — leave it out for a build sequence that starts from the drawn house before the works),
  `customer_description` (plain words, no drawing numbers; else the viewer strips refs from
  `description`), and `glb_quest`: the same GLB with every texture at ≤ 512 px (the "textures_512" variant), which the
  Quest loads instead so it neither decodes 1024 px images nor downscales them at load (until KTX2);
  `glb_quest_meshopt`: the same with EXT_meshopt_compression + KHR_mesh_quantization, which the Quest loads FIRST
  (three's MeshoptDecoder), falling back to `glb_quest` if it fails (the viewer dequantizes to floats for its
  batches); `stage_set`: the name of the stage list the sidecar follows (informative).

## 3. GLB: one mesh node per part, extras on the node

Each mesh node is one PART (a layer lift of a wall, one joist, a lintel, a door frame…). Blender object
custom properties export as node `extras` with `export_extras=True`; three.js reads them into
`object.userData` (for a multi-material node, on the parent group — the viewer looks up the tree).

| key | type | required | meaning |
|---|---|---|---|
| `element` | string | yes | id of the element in the elements file (section 5) this part belongs to |
| `stage_in` | int 1–N | yes | the stage in which the part appears (1 = there before the works) |
| `stage_out` | int or absent | no | the stage in which it is removed (demolition, temporary works). **Absent = never removed** (Blender IDProperties cannot hold null; the viewer also treats `null`, `0`, `-1` as never) |
| `seq` | float 0–1 | yes | build order within `stage_in`. The stage window is v ∈ (s−1, s]; a part with seq q builds over [0.85q, 0.85q + 0.15] of it, so 0 = first, 1 = last |
| `seq_out` | float 0–1 | no (1) | removal order within `stage_out`, same timing |
| `category` | `existing \| demolition \| temporary \| new \| finish` | yes | a temporary item's `label` must end "(typical — not from the drawings)" |
| `group` | see list | yes | foundation, slab_layer, wall_outer, wall_cavity, wall_insulation, wall_inner, wall_lining, lintel, steel, timber_beam, joist, deck, wall_plate, rafter, hip, valley, ridge, ceiling_joist, roof_layer, roof_cover, window, door, rooflight, fitting, drain, prop, scaffold, spoil, ground |
| `storey` | `site \| ground \| first \| roof` | yes | for the hide-storey toggles |
| `label` | string | yes | the exact spec text from the drawing, e.g. `beam 5 – 203x102x23kg/m UB steel beam with 8mm thick m/s plate welded to bottom of UB to carry out skin of brickwork over opening as per Struct. Engs design & calcs` |
| `plain_label` | string | no | homeowner wording ("Steel beam holding up the back wall…"); falls back to the element's, then a per-group phrase |
| `drawing` | string | yes | e.g. `4915.3A section A-A` (empty string for typical temporary works) |
| `conf` | `exact \| scaled \| assumed \| measured from photos` | yes | dimensioned on the drawing / scaled off it / assumed / measured from photos (treated as scaled: never a checkable drawn dimension) |
| `collide` | bool | yes | blocks walking (walls, floors, stairs, slabs, props, steels at head height). Floors must be collide to be stood on |
| `element_label` | string | no | for a wall layer: the wall's own label (the layer's spec is `label`) |
| `layer`, `lift` | int | walls | which layer of the element's stack (0 = +n face) and which lift (course band) |
| `member` | int | sets | index in a joist/rafter/prop set |
| `part` | string | no | sub-part name (`frame`, `leaf`, `leaf_glass`, `glass`, `sill`, `carcass`, `worktop`). Window glass is `glass` and is never a door |
| `as_built` | bool | no | an as-built record (section 6) |
| `door_leaf` | bool | door leaves | true on every opening leaf of a door (with `part: "leaf"`) |
| `hinge` | [x, y, z] | door leaves | viewer-frame metres: a point on the hinge axis (the bottom of the hinge edge is best) |
| `hinge_axis` | [x, y, z] | no ([0, 1, 0]) | the hinge axis direction |
| `swing_deg` | number | door leaves | the open angle, signed: positive = counter-clockwise seen from above (a right-hand turn about +Y) |
| `slide` | [x, y, z] | no | sliding door: the leaf moves by this vector. With `hinge` + `swing_deg` too (a bi-fold leaf) the leaf turns on its hinge AND is carried by the slide: pose = T(slide·k) · R(hinge, swing·k), k = 0…1 |
| `door_group` | string | no (the element id) | the leaves of one door share it and open together |
| `leaf_index` | int | no (0) | which leaf of the door; a door's glass (`part: "leaf_glass"`, `door_leaf: true`) moves with the leaf of the same `door_group` + `leaf_index` (and borrows its hinge if it has none) |
| `swing_conf`, `swing_note` | string | no | how sure the swing is, and why (shown on the board under the door) |
| `loft`, `no_regs` | bool | no | the owner's loft conversion: no regulations are mapped; the board says "converted by the owner, not on the drawings: measured by scan / to come from scan" |
| `context` | bool | setting | a setting node (below); it may carry `stage_in` like any part |
| `seq_span` | float | no | informative: how much of the stage a multi-part element's parts spread over |

Geometry rules (the viewer depends on them):
- **Closed solids with outward normals** (recalculate normals). The section caps paint the inside of a cut
  solid; an open sheet shows no cap. Thin layers (DPM, felt) are still solids (≥ 1 mm).
- **A solid inside another solid's void never shares its faces** (trench fill in the dug ground, a frame in its
  opening): leave 3–5 mm, or the cut faces z-fight in the section view. Layers that merely abut are fine.
- **Repeated members are linked duplicates** (Alt+D: one mesh datablock, many objects). The GLB then holds
  one mesh referenced by many nodes and the viewer instances it (joists, rafters, battens, props).
- One material per part where possible; material names are stable (`brick`, `block`, `pir`, `concrete`,
  `steel`, `timber`, …) because regenerated walls look materials up by name (section 5 `material`).
- Walls are split by lift (≈ 0.75–1.1 m course bands) so a part-built stage shows courses rising; each lift
  is its own node with `seq` from the formula in section 5.
- No modifiers left unapplied, no negative scales (instancing cannot flip winding per instance).
- Budget for the Quest 3: ≤ 300k triangles for the whole house, ≤ 60 distinct material×group pairs
  (each is one draw call), no textures above 1k, KTX2 later.

Setting nodes (the surveyed garden, trees, the houses opposite) carry `context: true` in their extras: the viewer
batches them separately (one batch per material) and keeps foliage materials (`leaves`, `branches`, `VertexPlant`) out
of its ray tree. A setting node may carry `stage_in` (and `seq`): it then appears at that stage, all at once (it is
not lowered in like a member), and a setting batch with nothing visible costs no draw call — e.g. the finished front
garden at the last stage only, while the build starts from the house before the works.

**Doors (round 6).** Threshold parts (`TH-*`, collide, flat top) are floors like any other: the walk steps over doorways on them.
Every door leaf opens in the viewer (trigger in the headset, a click while walking, "Open all
doors"). Write on each leaf node: `part: "leaf"`, `door_leaf: true`, `hinge`, `hinge_axis`, `swing_deg`, optionally
`slide` and `door_group` (table above). A leaf without `hinge` + `swing_deg` (and without `slide`) gets a derived hinge:
the vertical edge of its box nearer a wall corner, 90° into the room that is not the hall / landing (a bi-fold folds to
15 % of its width at that end) — the viewer logs every derived one, so write the extras. Closed leaves block walking
whatever their `collide`; open ones do not. A leaf opens only at stages where it is built. Leaves must be their own
nodes (not merged with the frame), one per leaf.

## 4. Stages sidecar (one per version)

```json
{
  "contract": 1, "version": "approved-4915-2B", "label": "Approved scheme 4915.2B", "units": "m",
  "frame": "viewer (glTF): +Y up, metres; Blender (x, y, z) -> viewer (x, z, -y)",
  "stages": [
    { "n": 1, "name": "House before", "note": "builder one-liner", "customer_note": "plain English: what happens and why" },
    "… 12 for a build version: 1 house before · 2 strip-out and demolition, temporary props · 3 setting out and trench dig ·
       4 trench-fill foundations and drains · 5 slab: hardcore, DPM, insulation, mesh, concrete · 6 walls to first floor with lintels ·
       7 steel beams in · 8 first-floor joists and deck · 9 walls to plate, porch walls · 10 roof structure: rafters, hips, valleys,
       ridge beam, trimmers · 11 felt, battens, tiles, windows, doors · 12 finished"
  ],
  "sections": [
    { "name": "A-A", "origin": [x, y, z], "normal": [x, y, z], "drawing": "4915.3A section A-A", "note": "looking back at the house" }
  ],
  "spawns": [
    { "name": "Front door", "position": [x, y, z], "yawDeg": 180 },
    { "name": "Garden", "position": [x, y, z], "yawDeg": 0 },
    { "name": "First floor landing", "position": [x, y, z], "yawDeg": 0 }
  ],
  "storeys": { "site": 0.0, "ground": 0.15, "first": 2.967, "roof": 5.3 }
}
```
- `stages` length N drives the slider (a version with one stage hides it). `customer_note` is shown in
  `?mode=customer`, `note` in builder/architect. Optional per stage:
  - `customer_title`: the homeowner's title ("The new ground floor is laid"); else the viewer maps the trade name.
  - `key_stage`: the name of the key step it belongs to (consecutive stages with the same name form one step); the
    homeowner sees the key steps (about six) with every stage one tap away. Without it a 12-stage list is grouped 1 /
    2-3 / 4-5 / 6-9 / 10-11 / 12.
  - `regs_stage`: the stage number(s) in the regulations dataset's own 12-stage list (regs.json meta.stages) this
    stage corresponds to. Inspection points are placed by it; without it only a 12-stage sequence maps (one to one).
- A section plane keeps the side its `normal` points to (the direction you look on the drawing). `origin`
  is any point on the cut line. The viewer adds free vertical cuts and a plan cut of its own.
- Spawn `position` is the FEET (floor level), not the eye.

## 5. Elements file (the parametric design; edits act on it)

```json
{ "contract": 1, "version": "approved-4915-2B", "frame": "viewer", "elements": [ … ] }
```
Every element:
```json
{ "id": "W-L-gf", "type": "wall", "params": { … }, "meta": { … }, "openings": ["O-…"], "bears_on": ["W-…"],
  "regs": ["A-lintel-bearing", "…"], "layer": "as_built", "replaces": ["…"] }
```
- `regs`: ids of rules in `regs.json` this element must meet (in addition to rules matched by `applies_to`).
- `id`: stable, unique in the version; the GLB parts' `element` extras point here.
- `meta`: the same keys as the extras (`stage_in, stage_out, seq, seq_out, category, group, storey, label,
  plain_label, drawing, conf, collide`, optional `seq_span`), the element-level defaults. `stage_out` may be
  `null` here (JSON).
- `bears_on`: ids of the elements this one is carried by (joists → the walls they bear on, a beam → its
  piers, rafters → the walls under the plate). The structural rule uses it.
- Types the viewer can **regenerate** from parameters (geom.js); others (`mesh`, `beam`, `member_set`,
  `stair`, `room`) keep their baked geometry and can only be removed:

**wall**
```json
"params": { "start": [x, z], "end": [x, z], "base": -0.15, "height": 2.9,
            "lifts": [0.6, 1.65],
            "layers": [ { "group": "wall_outer", "thickness": 0.1025, "material": "brick", "label": "…", "plain_label": "…" },
                        { "group": "wall_cavity", "thickness": 0.05, "void": true, "label": "50mm clear cavity" },
                        { "group": "wall_lining", "thickness": 0.0155, "material": "plasterboard",
                          "stage_in": 12, "seq": 0.2, "category": "finish", "label": "…" } ] },
"openings": ["O-G-bifold"]
```
- `start`/`end`: the CENTRE LINE in plan. n = (−dz, dx)/|d| for d = end − start; **layer 0 is on the +n face**,
  layers run to the −n face. (With start→end along +x, layer 0 is on the +z side.)
- `base`, `height`: absolute bottom and height. `lifts`: absolute y of the course bands' tops (inner lines).
- A layer may override any meta key (`stage_in`, `seq`, `category`, `label`, `group`, `collide`…); `void`
  layers take thickness but make no geometry.
- Geometry: the wall face (u along the centre line 0…L, y) is split at every opening edge and lift line;
  cells inside an opening are dropped; each kept cell is a box through each layer's thickness; one part
  per (layer, lift). Part seq (unless the layer sets `seq`):
  `seq = meta.seq + (meta.seq_span ?? 0.85) * (lift + 0.3 * layerIndex / nLayers) / nLifts`.
  Node name `<id>_L<layer>_<group>_lift<lift>`.

**opening** (hosted by a wall; no geometry of its own)
```json
"params": { "host": "W-G-gf", "offset": 0.68, "width": 2.4, "sill": 0.15, "head": 2.25 }
```
`offset`: distance along the host's centre line from `start` to the near jamb. `sill`/`head`: absolute y.

**lintel** — `"params": { "opening": "O-G-bifold", "bearing": 0.15, "depth": 0.15, "material": "lintel_galv" }`:
a box from `offset − bearing` to `offset + width + bearing`, `head` to `head + depth`, through every layer
except `wall_lining`.

**fixture** — `"params": { "catalogue": "door.bifold.3", "opening": "O-G-bifold", "plane": -0.02 }`: fills its
opening; `plane` = across-wall position of the frame from the centre line (along n). Catalogue ids
(geom.js `CATALOGUE`, same table in the fixture script): `door.bifold.3`, `door.front.solid`,
`window.casement.2`; kitchen/sanitaryware ids (`kitchen.base.run`, …) are baked for now, swap comes later
with a catalogue of GLB assets keyed by the same id. Parts: `<id>_frame`, `<id>_leaf`.

**beam** — `"params": { "start": [x, z], "end": [x, z], "base": y, "section": "203x102x23 UB", "depth": d, "width": w }`.
**member_set** (joists, rafters, hips, ceiling joists, props, needles) — `"params": { "length", "width", "depth",
"count", "spacing", "material" }`; parts `<id>_NN`, linked duplicates.
**stair** — `"params": { "start": [x, z], "direction": [dx, dz], "width", "base", "risers", "rise", "going", "flights":
[{start, direction, width, base, risers, going}] (a dog-leg lists each flight; headroom is measured per flight),
"top_floor": "<deck id>" }`; `start` is the first riser's centre line; treads run along `direction`; tread k
(1-based) has its nosing (k−1)·going from `start`, k·rise above `base`.
**room** (no geometry; tap-for-info, area, customer text) — `"params": { "name", "polygon": [[x, z], …],
"floor": y, "storey" }`, `"meta": { "category", "plain_label", "change": "new | altered | unchanged" }`.
**mesh** — anything else: baked geometry, metadata only.

## 6. As-built layer

An element with `"layer": "as_built"` and `"replaces": ["<drawn element id>", …]` is a record of what was
actually built where it differs from the drawing (its parts carry `as_built: true`). The viewer's
"As built" toggle shows these and hides the drawn elements they replace; off (default) shows the drawing.

## 7. Edits (written by the viewer, not the generator)

`{ "contract": 1, "site", "version", "saved", "edits": [ … ] }`, replayed in order over the elements file:
`{ "op": "remove", "id" }`, `{ "op": "restore", "id" }`, `{ "op": "set", "id", "params": { …partial… } }`,
`{ "op": "add", "element": { …a full element… } }`, `{ "op": "batch", "label", "ops": [ …the above… ] }` (one
undo step). A removed wall takes its openings, lintels and fixtures with it. Each op also carries `at` (time). Saved in localStorage per site + version, and downloadable / loadable as this JSON.

## 8. Rules hook

`checkRules(elements, ctx) → [{ elementId, rule, clause, status: "pass|fail|warn|unknown", message }]`
(`src/house/rules.js`), run after every edit on the current element table (removed elements carry
`removed: true`). `ctx.clearanceAbove(x, y, z)` measures to the first solid thing above in the finished
proposal. The rules need: stairs as `stair` elements with real `rise`/`going`, and `bears_on` on every
structural element.

## 9. Role modes

`?mode=customer | builder | inspector | architect` (`src/house/modes.js`) changes only what is shown, never the
data. Board tab order per mode (the BOARD is the hand-held clipboard in VR, the side panel on a screen):
customer `About · Build · Plans · Notes · Tools` (plain_label, room, customer_note; builder's spec one tap deeper);
builder `Spec · Build · Regs · Plans · Notes · Tools`; inspector `Regs · Spec · Build · Plans · Notes · Tools`
(+ the inspection-point checklist); architect `Spec · Regs · Build · Plans · Notes · Tools` (+ edit tools on Tools,
live rule checks).

## 10. Change requests (written by the viewer through the server)

Anyone, in any mode, can point at a part or a spot and leave a note (typed, or a voice clip transcribed on the
Mac by `tools/transcribe.py`, like the garden's marks). The server writes one file per request:
`assets/sites/<site>/change_requests/<version>/<UTC yyyymmddThhmmssZ>-<id>.json`

```json
{
  "contract": 1,
  "id": "crmvx6lsjdful",                       // [A-Za-z0-9_-]{1,64}
  "site": "house-fixture", "version": "today", // the version the person was looking at
  "created": "2026-11-01T01:58:02.000Z",       // client time; "received" = server time
  "mode": "customer | builder | inspector | architect",
  "author": "name typed on the board, or null",
  "status": "open",                            // open | done | rejected — for whoever acts on it
  "elements": ["W-L-gf"],                      // element ids pointed at (CONTRACT §5)
  "parts": ["W-L-gf_L0_wall_outer_lift1"],     // the node picked
  "point": [x, y, z],                          // the spot, viewer frame, metres (null if none)
  "camera": [x, y, z],                         // where they stood (eye), viewer frame
  "stage": 12, "stage_value": 12.0,            // the stage on screen
  "note": "Move this wall out 300 so the kitchen fits a 3 m island",
  "audio": "change_requests/today/<id>.webm",  // optional voice clip (relative to the site folder)
  "note_status": "typed | awaiting transcription | transcribed",
  "transcript": "…",                           // added by the server when the transcription lands
  "edits": [ … ],                              // architect only: the edit ops of §7 at the time (may be [])
  "rules": [ … ]                               // the failing / warning rule results (§8) at the time
}
```
An agent acting on a request: read `elements` + `note` (+ `edits`, which are exact parameter changes on the
elements file), apply them to the version's element spec, re-run the generator to write a new version (a new
`id` in versions.json with `base` = this version), then set `status`. Without the server (plain static hosting)
requests stay in the browser (`localStorage house-requests:<site>:<version>`) and can be downloaded.
Endpoints: `GET/POST /house/requests?site&version`, `POST /house/requests/audio?site&version&id` (raw
audio/webm|mp4|ogg|mpeg|wav, ≤ 10 MB) — `tools/https-serve.py`, its "House viewer endpoints" section.

### 10b. Marks (Jack's studio review, `?mode=review`; written by the viewer through the server)

Drawn on any surface in the headset or on a screen (src/marks.js, the garden's marking tool). All marks of a site are one
file, `assets/sites/<site>/marks.json`, rewritten whole on each save (`GET/POST /marks?site=<site>`, voice clips
`POST /marks/audio?site&id` -> `marks_audio/<id>.<ext>`, transcribed into `note`). Per stroke, the garden's fields
(`id, kind: correction | proposal, closed, points` (plan x, -z), `points3d, normals` (viewer frame), `surface` (material),
`length_m, area_m2` (closed shapes), `created, note, audio, note_status`) plus the house's:
```json
{ "version": "approved_2b", "version_name": "Approved scheme 4915.2B", "view": "after", "stage": 15,
  "stage_name": "Finished: your new rooms", "mode": "review", "camera": [x, y, z],
  "parts": ["G-extRear~1_L5_wall_lining_lift1", "…"], "elements": ["G-extRear~1", "…"],
  "room": "Kitchen-diner", "storey": "ground", "element_label": "1no. layer 12.5mm Gyproc wallboard …" }
```
`parts` are the GLB nodes the stroke lay on (most first), `elements` their element ids (§5), `view` before = the as-built
version (today), after = the proposal. An agent acting on a mark: the version + elements + note say what to fix and where;
`points3d` is the exact place on the surface.

## 11. Inspection records

One file per inspection point: `assets/sites/<site>/inspections/<version>/<point>.json`, the whole checklist
replaced on each save (`GET/POST /house/inspections?site&version&stage=<point>`):
```json
{ "contract": 1, "point": "excavation", "inspector": "name or null", "saved": "…",
  "checks": { "<rule id>": { "status": "checked | pass | fail", "note": "1.1 m to firm clay", "at": "…", "stage": 3 },
              "<rule id>@<element id>": { … } } }
```
Points (`regs.js INSPECTION_POINTS`, overridable by a sidecar `"inspection_points": [{id, name, stages, note}]`):
commencement (2), excavation (3), foundations (4), drains (4), oversite_dpc (5–6), structure_preplaster (7–11),
completion (12). A key `rule@element` is a check made on one part from its REGS tab; a bare rule id is the
checklist line.

## 12. regs.json + regs_map.json — the regulations

Built by `tools/house/build_regs.py <site> REGS-DATASET.json [REGS-REPORT.md]`:
- `regs.json` (contract 2): the dataset's rules unchanged (+ `inspection_ids` parsed from `inspection_point`), its
  `meta`, `meta.product_liability` (REGS-REPORT.md §5, verbatim: shown in full on every Regs tab and the rules panel),
  `meta.not_for_construction`, and `inspection_points: [{id, name, description, dataset_stages, stage_weights, rules}]`.
  A point's `dataset_stages` are voted by its own rules' `stage` tags (weighted down for rules tagged to many stages or
  many points; stage 1 counts only for the plans check), never typed by hand. The viewer maps them to the version's
  stages through each stage's `regs_stage` (§4).
- `regs_map.json` (contract 2): hand-curated, reviewable. `entries: [{id, when, rules, why, prompt?}]`; a part shows
  every entry whose `when` holds, grouped by `why`, with the part-specific `prompt` first. `when` keys (all must hold,
  a list is any-of, `not_<key>` negates): `type`, `group`, `category`, `storey`, `material` (the part's material
  name), `element` / `label` (regex on element id / spec label), `room` (regex on the room the picked point is in; room
  rules are listed under the part), `near_boundary` (true/false: within 1.0 m of a boundary line — parts labelled
  "boundary" and walls with `construction: "party"`; the distance is shown), `low_glazing` (a glazed opening whose sill
  is < 800 mm above its floor). Plus `project` (whole-job rules), `not_applicable` ([{id, reason}]) and `unmapped`.
- Conventions the map relies on (the generator keeps them): padstones say "padstone" in their label and dry packs
  "dry pack" (whatever their group); the escape window's element id ends `-EE`; boundary features say "boundary" in
  their label; the party wall has `params.construction: "party"`.
- Live checks (rules.js, §8): stair rise / going / 2R+G (AD K para 1.3, Table 1.1), headroom (para 1.11, Diagram 1.3:
  needs the stair's start / direction / width / base), escape window (AD B para 2.10(a): sill from the opening, clear
  opening only estimated from the frame and `lights`, so never a plain pass), removed load-bearing wall (AD A, A1).
  A numeric rule is called checkable from the model only when the part's `conf` is `exact`.
- A rule with no `verified_on`, or a status containing "UNVERIFIED", is a placeholder (the fixture's).

## 13. Captures (hook only)

`captures.json`: `{ "captures": [ { "stage": 4, "type": "photo | splat", "url": "…", "pose": { "position": [x,y,z],
"quaternion": [x,y,z,w] }, "taken": "…", "by": "…" } ] }` — photos or Gaussian splats of the real build in the
viewer frame, for the inspector to overlay on the design. Not drawn yet; the BUILD tab says where it will appear.

## 14. sheets.json — drawing crops for the PLANS tab

Made by `tools/house/render_sheets.py <site> <pdf…>` (macOS PDFKit, no extra libraries):
`{ "sheets": [ { "drawing": "4915.3A section A-A", "image": "sheets/<file>.png", "width", "height", "pdf" } ],
"crops": { "<element id>": { "drawing": "<a sheets[].drawing>", "rect": [x, y, w, h] } } }` (rect in that PNG's
pixels). With a crop the PLANS tab shows that piece of the real drawing; without one it draws a plan of the
storey from the elements with the part highlighted and the section lines marked.

## 15. materials.json and the wall parameters the viewer honours

`materials.json` (`{materials: {<name>: {tile: [u, v] metres, v_joint, glb_material}}}`) gives each material's real
tile size and the shared GLB material the name is drawn with (`glb_material`: rebuilt / edited walls and fixtures look
their material up through it, e.g. `door_leaf` → `joinery`);
walls rebuilt after an edit use it for their UVs exactly as the generator does (metres / tile; on wall faces
v = (height + 0.032) / tile_v + v_joint). Of the generator's extra wall parameters the viewer honours
`only_layers` (a stripped leaf); `top_profile` (raking tops), `joins_baked` (mitred / butt ends) and
`construction` are kept in the data but a REBUILT wall is square-topped and square-ended (baked walls keep them).

## 16. Editing operations the viewer can make (architect)

Move a wall along its normal (connected wall ends and the same wall on the other storey follow, one undo step:
a `batch` op), add a wall (two points; a partition stack by default), remove / restore anything, add a door or
window in a wall (opening + lintel + fixture, three `add` ops), move / widen / narrow an opening, swap a
fixture for the next catalogue item of its kind. Slabs, roofs and joists are not re-planned by the viewer: the
rules flag what bears on a moved or removed wall, and the change request carries the edits to the generator.
