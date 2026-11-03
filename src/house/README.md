# House build-stage viewer (`house.html`, `src/house/`)

Walk through a house extension at true scale and watch it go up stage by stage from the drawings: on a laptop,
a phone, or a Meta Quest 3 (WebXR). Separate from the garden viewer (`index.html`, `src/app.js`); it only
borrows `src/presence.js` (fade, controller models, haptics) and the BVH idea of `src/surface.js`.

The house itself comes from the Blender generator (traced architect drawings → GLB + JSON) following
**[CONTRACT.md](CONTRACT.md)**. Until then it runs on a small fixture made by `tools/house/make_fixture.py`.

## Open it

Desktop (any static server; change requests and inspections then stay in the browser):
```
python3 -m http.server 8771
open "http://localhost:8771/house.html?mode=builder"                     # 23 Battle Road (site=house, the default)
open "http://localhost:8771/house.html?site=house-fixture&mode=builder"  # the small test house
```
Quest 3 (WebXR needs https; the server also saves change requests and inspections):
```
python3 tools/https-serve.py            # https on :8443
# on the headset: https://<mac-ip>:8443/house.html   (Advanced → Proceed once)
```
URL parameters: `site=<folder in assets/sites>` · `version=<id from versions.json>` ·
`mode=customer | review | builder | inspector | architect` (default builder) · `test=walk` (the walk test, below) ·
`xrsim=1` (a simulated headset on the desktop: fake controllers drive the VR code; `__house.sim` in the console) ·
`perf=1` (post the frame log from a desktop too).

**Walk test** (`house.html?test=walk`, `src/house/walktest.js`): every stair element is climbed and descended in every
version at every stage where it is walkable, two ways (stick: `walker.move` + settle; head: the feet moved straight
along the line, settle only, as a step of the real head does), and each storey's rooms are walked in a loop with the
doors open (a floor grid finds the free path; the walker must follow it). A stage whose stair has no floor at its foot
or head is reported, not walked. Result on the page, in the console and in `window.__walkTest`. Run it before every
release (CORRECTIONS-LOG round 6).

**Frame log** (`src/house/perf.js`): in the headset (or with `?perf=1`) a summary is POSTed every 10 s to
`/house/perf` and appended to `renders/house-build/perf/<site>-<yyyymmdd>.jsonl` (`GET /house/perf?site=house&n=20`
reads the last ones): fps, frame ms p50/p95/p99/worst, our own CPU ms, draw calls, triangles, textures, geometries,
programs, an estimate of texture MB, JS heap, eye height above the floor, board state, and every frame over 50 ms with
what was going on ("board open", "board draw 9 ms", "stage", "version load", "doors", "fly", "landing").

Rebuild the fixture (light, < 1 s of Blender, no render):
```
nice -n 10 /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/house/make_fixture.py
```
Render architect PDFs for the PLANS tab: `python3 tools/house/render_sheets.py <site> <sheet.pdf> …`
Regulations from the research dataset: `python3 tools/house/build_regs.py house "<…>/research/regs/REGS-DATASET.json"`
(writes `regs.json` and the hand-curated, reviewable `regs_map.json`; the map lives in `build_regs.py` MAP — edit it
there and re-run; it fails on an unknown rule id and prints any unmapped rule).

## Regulations: what the viewer claims, and what it does not

- The status button never says "all pass". It says what ran: "Model checks: 7 run · 3 pass · 1 fail · 1 not measured
  · 2 to check", and its tooltip and the rules panel say how many of the 167 rules are judgement, evidence or not
  modelled (163) — a person checks those — and "Guidance, not approval".
- Every Regs tab opens with the report's liability wording in full and "Not for construction — do not set out, order
  or build from this model". The start screen and the stage bar carry the same line.
- Per rule: why it is on this part (and a part-specific prompt: padstone bearing, DPC height, the EE window's sill,
  the flue beside the porch rooflight, the porch exemption), document and clause, "applies to an extension: yes / no /
  conditional — <conditions>", the plain-English text, the value, the check type said honestly (judgement: never
  passed by the model; evidence: what is needed; numeric: checkable from the drawing only when the part is `exact`,
  otherwise "scaled / assumed: measure on site"), the edition and the date it was verified, and a short quote with
  its source.
- Inspector: the inspection points (IP-PLANS … IP-COMPLETE) sit at the stages the dataset's own rules are tagged with:
  commencement at stage 5 (foundations and ground-floor structure done, the post-2023 meaning), not at strip-out.

## The look (renders/house-build/VIEWER-LOOK.md)

**Round 6c (the Quest frame rate):** every GLB material arrived double-sided, so every back face was rasterised:
the house's materials now draw front faces only (closed solids; the slice still turns both sides on while cutting),
foliage keeps both sides and is alpha-tested and drawn after the solid scene, mesh fences / rebar likewise, and the
sky sphere is drawn last (only the pixels left uncovered are shaded). The frame log's `passes` says what the calls are
made of: eyes (WebGLRenderer draws each eye separately, so XR calls ≈ 2 × visible batches + overlays), house /
setting / edited batches live, the overlays shown, and how many shadow passes ran.

The midday HDRI (`kloofendal_43d_clear_puresky_2k.exr`) lights the scene through PMREM at 0.85, with its sun disc
clamped out; the matching sky JPEG is the background, both turned so the sky's sun sits where the filmed sun is.
The sun is the garden viewer's filmed sun (`front-garden-model/site.json`: azimuth −138°, elevation 22° →
(−0.689, 0.375, 0.620) in the viewer frame; VIEWER-LOOK.md's vector has x and z swapped, and the garden is the
source), so the street side is lit and the garden side in soft shade, as filmed. Soft PCF shadows (radius 3.5,
2048) fitted to the house and re-rendered only when the stage or the model changes; Khronos Neutral tone
mapping; ORM ambient occlusion at 1.0 plus GTAO (0.4 m) on a screen; anisotropic filtering on every texture.
**Quest path:** the version's `glb_quest_meshopt` first (MeshoptDecoder; `glb_quest` if it fails; `?glb=meshopt | quest`
forces either on a desktop), no post, one 1024 shadow map (radius 1.5, static), no EXR decode and no 2k prefilter at load (the 2k
sky JPEG is the background; the lighting comes from it shrunk to 256 x 128 and prefiltered after the first frame, a
few ms), a version's `glb_quest` (≤ 512 px textures) when the generator writes one, else textures halved to 512 px as
they load, only the asked-for version in memory.

**Measured (laptop, approved scheme, 1269 parts in 52 batches, from the garden):** renderer CPU time 0.85 ms a frame
with per-instance culling + sorting, 0.25 ms with culling and no sorting, 0.25 ms with neither — so per-instance
SORTING was the cost, not culling. Opaque batches no longer sort (only transparent ones: glass, x-ray). A stage change
(applyStage over every part) costs 0.26 ms. The Quest's CPU is several times slower and renders two eyes: not
measured on the headset yet.

**Round 5 (setting + as-built):** the front-garden setting (nodes with `context: true`, ~47 materials) is batched
apart from the house, once, and never re-staged; tree leaves stay out of the ray tree. A house batch with nothing
visible at the current stage is switched off (no draw call, no shadow pass): the approved scheme has 74 house
material batches in all but 50–69 live per stage (stage 1: 50 · 2–3: 60 · 6–9: 66–69 · 12: 59), plus the 47 setting
batches. Shadows only re-render on a stage change. Getting every stage under 60 needs fewer house materials (an atlas
or merged materials, generator side). `as_built_default: {"customer": true}` starts the As-built toggle on for
homeowners (round 6: only when versions.json says so; the build sequence starts from the drawn 2022 house). The establishing start avoids standing behind a tree (it tries spots along the front-path line).
The stair headroom check now measures each flight (`params.flights`): 2038 mm at flight 1 nosing 2 — reported as
"to check", because a 38 mm margin on scaled geometry is not a pass.

**First minute in the headset:** a how-to card floats in front of you for 16 s (or until the trigger): turn the left
wrist up for the board (Y hides it), point the right controller and pull the trigger to pick (or open a door), A / B
for the stages, the sticks, hold the right grip to fly. While a version loads in the
headset a loading card with a progress bar replaces the page's (invisible) bar. Board text is never under 30 px on
its 1024-px canvas.

**Round 7 (Jack, 1 Nov): studio review mode, fast walk, trigger teleport, Go to, 4 ft height.**
- `?mode=review` (Jack's studio review): exactly the homeowner walkthrough below (`MODE.as = "customer"` everywhere) plus the
  MARKING TOOL (`src/marks.js` + `src/notes.js`, the garden's, adapted): the house BVH is the surface (walls, floors,
  ceilings, fittings, the garden), corrections (orange) / proposals (cyan), a closed shape shows its area, each mark opens a
  note (type, or hold A / Record and talk), marks listed (screen: the Marks panel, Note / Look / Delete; headset: the labels,
  point + trigger opens the note, which has Delete). Saved with POST `/marks?site=<site>` to `assets/sites/<site>/marks.json`;
  each mark also carries `version`, `version_name`, `view` (before | after), `stage`, `stage_name`, `mode`, `camera` (eye),
  `parts` (what the stroke lay on, most first), `elements` (their element ids), `room`, `storey`, `element_label`. Marks of
  the other version stay in the file but are hidden. Screen: Mark button or M, drag on a surface to draw, right-drag looks,
  K kind, Z undo, Esc / M done. Headset: Mark on the wrist; the trigger draws (teleport and doors are off while marking),
  X Correction / Proposal, Y undo, A held = talk while a note is open.
- Wrist panel (homeowner and review), three rows: Before | After | Height (shows the height; press = re-check) /
  No doors | Go to | Fast / −1 in | +1 in | Mark (review only).
- FAST walk (wrist Fast, G, the bottom bar's Fast, the board's Tools): walking 1.4 (homeowners 0.9) → 3.0 m/s in the
  headset, easing in over 0.6 s and stopping at once on release; a screen's W A S D and click-to-walk double. Fly
  speeds unchanged. Remembered for the session (sessionStorage `house-fast-walk`).
- Teleport on the trigger (homeowner / review): point at a floor or the ground, a green ring shows the landing spot,
  click. Refused (red dot, a tick): walls, roofs, wall / furniture tops, stair treads, spots with < 1.5 m headroom.
  A door still opens, a wrist button still presses; the stick-forward teleport stays.
- Go to (wrist Go to, the bottom bar's list): every room by its plain name per storey (rooms of the version on screen,
  so After-only rooms show only After; cupboards skipped) plus Road, Front path, Drive (the front court), Porch, Back
  garden. A room uses the spec's named camera (`spec/spec_v1.json` cameras, matched by Before / After) when its eye is in
  the room, else the free spot nearest the room's middle facing the longest clear view. A preview copy of a site (`<site>-wip`, `-preview`, `-fixture`) has no spec of its own, so it reads `assets/sites/<site>/spec/spec_v1.json` of the site it previews (without it there is no Drive and rooms use the free-spot rule).
- Height: the default person height is 4 ft (1.219 m; Jack tested it), applied automatically at the start of every VR
  session in every mode (eyes at 1.14 m; the first card says "Height set to 4 ft; change it under Height"), adjustable (wrist −1 in / +1 in, board Tools) and remembered under
  `house-person-height-v2` (the bump drops older stored values once). Logged as `height check` with `auto: true`.

**Round 7c (Jack, 1 Nov): smooth turning and motion blur (homeowner and review; the other modes keep snap + vignette).**
- Right stick left / right turns SMOOTHLY: 75°/s at full push, scaled by the push, easing in and out over 0.15 s; the
  stick-forward teleport stays. Wrist "Turn" switches smooth / snap (30°); remembered for the session (`house-turn`).
- Wrist "Comfort": blur (default) / vignette / off, for the session (`house-comfort`). `src/house/motionblur.js`: a
  depth-free camera motion blur (each pixel's view ray, a point 2.5 m along it, re-projected with last frame's camera,
  8 taps along the difference). Screen: a pass in the composer after GTAO; any camera turn or move fast enough fades
  it in over 0.15 s. Headset: only while turning or moving on the sticks, each eye is drawn into an 8-bit sRGB offscreen
  target at 70 % of the eye buffer, then the shader writes the eye buffer blurring the OUTER part of each eye only;
  only the rig's motion counts, never real head motion; at rest the headset renders exactly as before. A governor
  times the blurred frames: under 68 fps (and slower than without it) the copy drops to 60 %, 50 %, then Comfort
  switches itself to the vignette for the visit (frame log: `motion blur fps`). GTAO no longer draws sprites (the marks'
  labels were black boxes); the simulated headset renders without the desktop post, like the Quest.
- Wrist panel, four rows: Before | After | Height / No doors | Go to | Fast / Turn | Comfort | Mark (review) / −1 in | +1 in.

**Round 7d (Jack, 1 Nov): mouse-look, phone thumb sticks, blur toned down.**
- Screen with a mouse (walking, any mode): click the view once to capture the mouse (Pointer Lock; hint "Click to look
  around · Esc to free the mouse"), then moving it looks (0.13°/count, no inverted Y); W A S D walk, Shift / Fast, F or
  Space fly (homeowner / review). A centre crosshair (yellow over a door, green over a floor you can jump to); a left
  click opens / shuts a door or jumps to the floor (homeowner / review; walls, roofs, worktops refused), or picks /
  measures in the other modes; in Mark mode hold the click and look to draw. A mark's note frees the mouse to type.
  Esc frees it. Refused capture: "click again" (browsers refuse within ~1 s of Esc); twice and never granted: drag-to-look.
- Phones / tablets (homeowner / review): two thumb sticks, each resting faintly in its bottom corner and jumping to where
  the thumb lands in its half of the lower 58 % of the screen. Left moves (speed by push, Fast respected), right looks
  (eased, a light curve for fine aim), both at once. A quick tap anywhere (also in a stick zone) opens a door or jumps
  to the floor; dragging in the upper view still looks. In Mark mode the sticks step aside and the finger draws. The
  buttons move to a compact bar at the top (safe-area insets; one row in landscape).
- Motion blur toned down (Jack: "way too much"): a third of the strength, only on genuinely fast turns (screens over
  about 115°/s; the headset only on a near-full stick turn or a fast flight; walking never), edges only (headset: the
  middle 70 % of each eye sharp; screens: a light sideways smear at the sides), 0.08 s fades. Comfort is "subtle blur /
  vignette / off" (default subtle blur) on the wrist and on the screen's bar (vignette on screens darkens the edges
  while turning or moving).

**Homeowner mode, simplified (round 6c, Jack 1 Nov; this REPLACES the key-stages design below):** just Before /
After and Fly. Before = the proposal's stage 1 (the house before the works, no porch), After = its last stage
(finished, with the front garden); it opens on After. Screen and phone: two big buttons (Before / After, keys B / N)
plus Fly (F; W A S D, Q / E); no stage slider or list, no "See the extension" tour, no board, no measure / heights /
slice / x-ray / hide / doors-all / notes / scale figure. Headset: a tiny panel on the back of the left wrist (Before |
After | Height) instead of the board; A / B = After / Before; walking, teleport, snap turn and fly (right grip +
right stick, hover on release, left grip lands) as in the other modes; pointing at a door and pulling the trigger
opens it (kept: it is how you get through a house, not a tool). The first card says "Stand or sit comfortably, then
press A to set your height" and stays until A (Height check) or the trigger. Builder, inspector and architect keep
everything.

**Homeowner mode (before round 6c, superseded):** plain stage titles (the stages JSON's `customer_title`, else mapped from the trade names), six key
steps with every stage one tap away ("All 12 stages"), no element ids or drawing numbers, a friendly help line, and
an establishing start: on the line of the front path, far enough back that the whole front fits, then "See the
extension ▸" goes to the garden. On a phone the toolbar folds behind ☰, the stage note behind the stage title, and the
board scrolls in a short panel so the house stays in view.

## Modes (one page, one data set)

| | customer | builder | inspector | architect |
|---|---|---|---|---|
| opens on | finished proposal, at the front door, walking | stage 1, overview | stage 3 (excavation), overview | finished, overview |
| stages | list of all 12 front and centre, plain-English `customer_note` | slider + builder notes | list grouped by inspection point, each with its checklist (checked / pass / fail + note) | slider + builder notes |
| tap a part | plain words, room + m², when it goes in; builder's spec one tap deeper | exact spec text, drawing, conf, rule tags | regs first: document, clause, requirement, value, evidence, pass/fail | spec, live regs, edit tools |
| tools | See inside, Lift roof / first floor, simple tape, Before/After, notes | + slice A-A…E-E/free/plan, x-ray, hide storeys, temporary works | as builder | + move / add / remove walls, add / move / resize / remove openings, swap fixtures, undo/redo, save/load edits, live Building Regs checks |

## Controls

**Desktop** — drag to orbit, right-drag to pan, scroll to zoom; click a part (board on the right: tabs Spec /
Build / Regs / Plans / Notes / Tools); `[` `]` stages, `Space` play, `X` x-ray, `M` measure (snaps to corners
— pink — and edges — blue), `V` walk (WASD + drag to look, Shift faster, collision with what is built at that
stage, steps up slabs and stairs), `Esc` clears. "Leave a note" opens the Notes tab for a change request on the
selected part or spot. Architect: `Ctrl/Cmd+Z` undo, `Shift+` redo.

**Phone** — drag to turn, pinch to zoom; in walk mode drag to look and tap a floor twice to walk there.

**Desktop extras (round 6)** — `F` fly (W A S D, `Q` / `E` down / up, Shift fast; `F` again eases you down to the
floor beneath, out of any wall), `O` opens / closes every door (the toolbar's "Open doors"), a click on a door while
walking swings it (in the overview a click only picks it; the board then has "Open this door"), `H` the frame HUD,
toolbar "Heights" (point at a ceiling or beam: its height above the floor and above your eyes) and "Scale figure"
(a 1.80 m figure beside a 1 m post in 100 mm bands, put down in front of you).

**Quest 3** — nothing is picked by looking. The RIGHT controller always shows its laser and a dot where it lands;
the part under it gets a soft highlight; the **trigger** picks it and the board HOLDS that part until you pick
another (or pull the trigger at nothing, which clears it). The trigger on a door swings it open or shut (0.6 s).
*The board*: turn your left wrist up (like reading a clipboard) to see it; `X` pins it; `Y` minimises it to a small
"Board ▴" tab on the left wrist (so does the — button on the board); point the laser at the tab and pull the trigger,
or press `Y` / `X`, to bring it back. With the board raised and in view, the left stick flips tabs, left-stick click
pages long content, or press a tab / button with the laser. The strip at the bottom always has the stage slider,
◀ Stage, Play, Stage ▶ and the tool button (Info → Measure → Heights).

| button | does |
|---|---|
| right trigger | pick (the board holds it) · press on the board · open / shut a door · measure points |
| A / B | next / previous stage |
| right grip (hold) + right stick | FLY (Jack, row 159): the stick steers while the grip is held — forward / back along where the right controller points (its pitch too: point up and push forward to climb, point down to descend), left / right strafe level, push harder to go faster (1.5 up to 10 m/s); no collision. Let go of the grip: you HOVER where you stopped |
| left grip | LAND: ease down to the floor beneath (nudged out of a wall if you stopped inside one) |
| right stick (grip not held) | left / right snap-turn 30° (also while hovering) · forward: aim a teleport, release to go (from a hover it lands you there) |
| right stick click | frame HUD (fps, worst frame, draw calls, triangles, textures) |
| Y | minimise / restore the board |
| X | pin the board (and restore it if minimised) |
| left stick | walk (1.4 m/s; 0.9 m/s with a stronger comfort vignette for homeowners; Fast: 3.0 m/s) · while hovering it moves you level at that height · flips the board's tabs while you look at it |
| left stick click | clear the tape while measuring; otherwise the board's next page (the Tools tab also has "Clear tape") |

Play / pause is on the board's strip (it was `Y` until round 6). Tools tab: slice, x-ray, hide, versions,
Before/After, As built, Go to (spawn points), Open / Close all doors, Heights, Scale figure, Fly (hint / Land), Frame
HUD, **Height check** (your height in cm or ft/in, remembered; Reset floor), VR quality, and the architect's edit palette.

**Height check (round 6c)** — the Quest logged Jack's eyes 1.14–1.24 m above the floor all session (6 ft 1, so about
1.74 expected): sitting, or the Quest's floor set ~0.5 m high. Sitting or standing, press Height check: the rig is
lifted so the eyes are at height × 0.936 (1.854 m → 1.735 m), shown as "floor corrected by +0.50 m"; Reset floor
undoes it; press again after changing posture. The height is set on the board (−/+ 1 cm or 1 inch in the headset;
typed as "185", "1.854" or "6 ft 1" on a screen) and kept in localStorage. Standing with the eyes under 1.35 m for
10 s (and no correction) shows one card per session: "You look seated or your Quest floor is low: press Height
check". The old "Seated" (+45 cm) toggle is REMOVED: the Height check replaces it. The frame log records
`eye_above_floor`, `eye_raw`, `floor_offset`, `person_m`.

**VR quality (round 6c)** — Sharp (100 % eye buffer, shadows) · Balanced (90 %, shadows; the default) · Fast (80 %,
no shadows). Chosen on the Tools tab, used from the next Enter VR; fixed foveation is always 1 (strongest). A session
under 64 fps after 20 s makes the next one start a step lower (a card says so).
Notes tab: "● Voice note" records until pressed again, then sends it as a change request (transcribed on the Mac).

**Scale in the headset** — the rig's y is the floor you stand on (`local-floor` reference space); the headset's own
height is the eye: nothing is added to it (the desktop's 1.65 m `EYE` is never used in XR; Seated adds 0.45 m only
when pressed). The world is 1:1 (no scale on the rig or the model; near plane 3 cm). Measured in the model: ground
floor 0.000 to ceiling 2.430 (every ground room), first floor 2.6755 to ceiling 2.405, kitchen steels (beam 6)
underside 2.110 above the floor. For a 1.854 m person (eyes ≈ 1.74 m) the ceiling is 0.69 m and the steel 0.37 m above
the eyes — the steel IS low. The Heights tool shows these against your real eye height, and the frame log records
`eye_above_floor`: if it is not about 1.74 standing, the Quest's floor (Guardian) is set wrong.

## How it works

- `model.js` — every GLB mesh node is a *part* with the contract's extras; parts are drawn through one
  `BatchedMesh` per material × group (43 draw calls for the 173-part fixture), linked duplicates share one
  geometry (instancing). Each part keeps its own visibility / matrix / colour, so a stage is part-built from
  `seq`: wall lifts rise, joists drop in one by one, demolition is tinted red then sinks away, props leave at
  their `stage_out`. Regenerated (edited) elements are plain meshes with the same materials.
- `bvh.js` — one triangle BVH of the whole house with a part per triangle; every ray (pick, hover, tape, walk,
  headroom rule) passes a mask of what is built / shown / solid *now* and the slice plane.
- `section.js` — one clipping plane; cut solids are capped with the drawing's hatch by painting their back
  faces in plane space (no stencil, works in the headset). X-ray swaps materials per batch.
- `walk.js` — capsule probes + floor ray: step-up 360 mm, refuses drops over 600 mm (trenches, stairwells). The
  floor is read across a footprint (the highest floor under a 12 cm sole, so the 115 mm gap at the stair top and the
  doorways with no floor of their own are stepped over; a 22 cm edge ring keeps you on an edge), back faces are
  ignored (`bvh.raycast(…, front)`), nothing under you keeps the last floor, and the head probes going down a stair
  are measured from the lower tread ahead.
- `doors.js` — door leaves swing / slide on their hinges (CONTRACT §3 door extras; a bi-fold leaf turns AND slides;
  a door's `leaf_glass` moves with its leaf; window `glass` is never a door; a derived hinge only when extras are
  missing), closed leaves block the walk, open ones do not; rebuilt after an edit.
- `perf.js` — the frame log, the HUD and the POST to `/house/perf`. `walktest.js` — the walk test.
- `geom.js` / `edits.js` / `editops.js` — walls, openings, lintels and fixtures rebuilt in the browser from
  their parameters; edits are a diff over the drawn elements (undo/redo, localStorage, JSON file).
- `rules.js` — `checkRules(elements, ctx)`, live checks (AD K stair rise/going/2R+G, AD K headroom by ray,
  AD A removed load-bearing wall). `regs.js` — the regulations dataset (`regs.json`) per part and per
  inspection point; placeholders are always flagged UNVERIFIED.
- `board.js` — the board's content model, drawn to a canvas in VR and to DOM on a screen. In VR the canvas is
  redrawn only when its content changes (a key of its text and states), text is wrapped a few ms a frame before it is
  drawn (word widths cached), the upload happens on the next frame (with the board down it goes to the GPU then, via
  `renderer.initTexture`, so raising the board costs nothing), the stage strip is its own small canvas (≤ 10 redraws a
  second), and the laser's cursor and hover box are meshes. Plans: the storey's plan is drawn once and the part laid
  over it; sheet crops are cut and shrunk off the main thread (`createImageBitmap`).
- `requests.js` — change requests and inspection records (server or browser), voice notes.
- `modes.js` — the four modes.

## Known gaps

- Round 6 (after Jack's first Quest test) is checked on the desktop with the simulated headset (`?xrsim=1`) and the
  walk test, not yet in the headset: the wrist tab's place, the fly speeds, the door swing directions (derived until
  the generator writes hinge extras), the frame log's real numbers.
- The Quest keeps one version in memory (switching frees the last one); a version switch in the headset still costs
  a load (GLB parse, BVH ~0.2 s on a laptop), now shown with the loading card and logged.
- Hand tracking: the board rides the left controller's target-ray space, which exists for tracked hands too,
  but there is no pinch-to-press yet.
- Walls meet at corners without mitres (the fixture shows a cavity slot at extension corners).
- Moving a wall does not re-plan the slab, joists or roof that sat on it (flagged by the rules, sent to the
  generator through a change request).
- The regulations: 167 verified rules from REGS-DATASET.json; the mapping to parts is keyword-built
  (`regs_map.json`, 2 rules unmapped) and wants a human read. The fixture's rules are still placeholders.
- The captures overlay is a hook only.
- The real stair element has no start / direction / width / base yet, so its headroom check reports "not measured".
- Not in the regulations dataset yet: roof external fire spread (AD B, B4), abutment trays / flashings, a separate
  eaves-ventilation rule. The roof parts say so instead of showing nothing.
- Boundary distances are measured in the model (e.g. G-extL ≈ 0.35 m from the party-wall line, because its baked
  corner join reaches past its centre-line face) — not from the site plan; the site plan's own figure governs.
