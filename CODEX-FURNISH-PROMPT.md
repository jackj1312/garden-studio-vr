You are working in Jack's live studio project (this folder). Bring the quality of your own independent Battle Road build
(`~/Desktop/23 Battle Road/independent/`) into THIS build, and build the furnishing system described below, end to end.
Work autonomously, stage by stage, until every stage is done and tested. Ask me only for spending, logins/purchases, or a
design choice this brief and the project files don't answer, and batch those questions.

## What I liked, and what stays
- From your build, bring in: **every interior thing** (furniture, fittings, kitchen and bathroom, toilets, basins, washing
  machine, appliances, soft furnishings, styling, materials, the way the rooms are lit), **the windows, the front door, the
  internal doors, and the outside window surrounds**, and outside **the apples under the tree and your better grass**.
- Keep ours: **our brickwork** (yours was too bright and had visual bugs: don't touch our brick), **our front garden layout and
  paving**, our measured scale front and back, and our navigation.

## Read first
- `CLAUDE.md` (the project's rules: they apply to you), `PLAN.md` (the build plan, including its 2026-11-03 change-log
  entries), `CODEX-COMPARISON.md` (why your interior beat ours), `FIRST-PASS.md` (every lesson learned: don't repeat them),
  `DETAIL-CHECKLIST.md`, `renders/house-build/first-build/round-2/MARKS-GROUPED.md` and `round-2/STATUS.md` (my open marks).
- Your earlier work, the source to bring across: `~/Desktop/23 Battle Road/independent/` (tools/furnishings.py and the other
  tools, assets/asset-catalogue.json, the materials JSON and reviewed sources, viewer/*.js). Read-only there: copy what you
  need into this project; never edit that folder.
- Our build: `house.html`, `src/house/viewer.js`, `model.js`, `walk.js`, `cull.js`, `src/marks.js`, `src/notes.js`;
  the planner `planner.html`, `src/planner/*`; the server `tools/https-serve.py`; the generator `tools/house/*`
  (`generate_house.py`, `hb_build.py`, `hb_finish.py`, `hb_items.py`, `make_setting.py`); the spec
  `assets/sites/house/spec/spec_v1.json`; the published build `assets/sites/house-wip/`.

## First: your plan
Write `FURNISH-PLAN.md` (concise and highly descriptive: goal; the stages below with inputs, outputs and the check that
proves each done; risks) and show it to me before building. Re-read it in full at the start of every stage, before every
fix round, after any context reset, and before every report. Change it only with a dated line saying what changed and why.

## Stages, in this order (each on its own git branch off the previous one; commit in small steps; never push)

**Stage 1 · The studio kit and catalogue** (branch `codex/kit`)
1. Bring your furnishing generator and catalogue in as our own studio kit (`tools/library/kit/`), parameterised by size and
   style, for every client house. One axis convention (X width, Y depth, Z up, front -Y, bottom-centred, metres). Built to
   exact sizes; never stretch a whole item. Real-metre UVs, one reviewed CC0 material set, support/seating built in (fruit in
   bowls, throws on sofas, towels on rails). Every licence and source recorded.
2. A broader catalogue in styles: at least modern, contemporary, Scandinavian, country/farmhouse, industrial and
   traditional, each a coherent set across sofas, armchairs, tables, chairs, beds, bedside tables, wardrobes, dressers, rugs,
   curtains/blinds, lamps (table, floor, pendant), mirrors, art, plants, cushions/throws, kitchen and bathroom fittings and
   appliances. Quality bar: your Battle Road interior, close up.
3. Thumbnails: a small picture of every catalogue item (about 256 px, front three-quarter, neutral studio light), made by
   script (headless Blender with Eevee or Workbench, or three.js offscreen), one at a time, stored beside the catalogue and
   regenerated when an item changes.

**Stage 2 · Your interior, windows and doors in our house** (branch `codex/interior`)
- Our generator keeps the shell, brickwork and site. Replace our interior furnishing, fittings and finishes with yours
  (kitchen, bathroom, en-suite, cloaks, utility, every room), plus your windows (frames, glazing, boards, reveals), front
  door, internal doors with their hardware, and the outside window surrounds, fitted to our measured openings.
- Finishes built in, not patched on: assign every wall face, reveal, floor area, ceiling and skirting its finish as it is
  built (your `finish_layout`/`internal_lining` approach), replacing our raw-face detection passes in `hb_finish.py`. No raw
  brick, block or timber inside; never plaster on an outside face.
- Outside: add the apples under the tree and your better grass to our front garden; leave our paving, path and layout.

**Stage 3 · Furniture at runtime and furnishing it yourself** (branch `codex/furnish-system`)
1. Each catalogue item exports as its own small model (instanced where repeated). A layout file per site and version
   (`assets/sites/<site>/layout/<version>.json`: item id, kind/style/variant, position, rotation, host surface, room) is what
   the viewer loads. Start Battle Road's layout from Stage 2's placements; the house model keeps only fixed fittings.
2. An Edit mode on desktop, phone and in the Quest: a catalogue panel with the thumbnails, filtered by room type, kind and
   style (on the wrist panel in the headset); add an item where you point; drag it along the floor (or wall for wall items)
   with the mouse, touch or the controller ray; rotate with Q/E, two fingers or the thumbstick; delete; undo/redo. Snap to
   walls, corners and other items; live checks while moving: no overlap with walls or furniture, base on its host surface,
   front into the room, doors still open, a walking route kept. A blocked spot shows red and won't drop.
3. A bird's-eye room view: pick a room, see it from straight above with its furniture, lay it out by drag, rotate, add and
   delete with the same catalogue and checks; switching back to walking shows exactly the same layout. The room planner
   (`planner.html`) reads and writes the same layout file.
4. Saving: `GET/POST /layout?site=&version=` in `tools/https-serve.py` validates and writes the layout, keeps the previous
   copy and logs each change for the next build to bake in. The server on 8443 is Claude's: don't stop or restart it; test on
   your own server on port 8450.

**Stage 4 · Light and presentation in the viewer** (branch `codex/look`)
- Your lighting method in our viewer: soft contact shadows on desktop (GTAO), daylight from each room's real windows
  (your window-daylight lights), neutral tone mapping, restrained reflections, working lamps. On the Quest use what it can
  afford; never make it slower.
- Your branded loading screen and room title card, and a clean toolbar, in our viewer. Keep our controls, Before/After,
  Furnished/Unfurnished, Go to, marking tool and headset wrist panel working.

**Stage 5 · My open marks** (branch `codex/marks`)
- Everything still open in `round-2/STATUS.md` that Stages 2–4 didn't already fix: the path width (900 mm to match the rest),
  paving gaps, the shed front's projected door texture, the eaves timber, the wing roof hole, the porch roof and slope, the
  pergola post, the steel boxing, the living/kitchen floor junction, the front hall check (my 1.80 m was measured just inside
  the porch: compare with the drawings before changing anything), and the bedroom-1 walk-test fault.

**Stage 6 · Headset speed** (branch `codex/speed`)
- Merge each room's fixed parts into a few pieces per material (keep the per-item models for the layout), KTX2 textures,
  and keep our room culling (`src/house/cull.js`). Same picture, proven with matched before/after frames. Report draw calls
  and triangles in the simulated headset before and after; target 72 fps on the Quest 3.

## Rules
- Jack's Mac is an 8 GB M1 Air: one heavy job at a time (Blender, conversions, captures); no Cycles renders or light bakes.
- Don't break what works: navigation, Before/After, Furnished/Unfurnished, doors, marking tool, headset controls, room
  culling. Keep the walk test (`house.html?site=house-wip&test=walk`) passing.
- Publish to `assets/sites/house-wip` only when every check passes (integrity, shell, finish, spec, export and the walk test);
  rebuild the compressed twins with `tools/house/quest_meshopt.py` and run `tools/house/fix_glb_textures.py` on them.
- Log every mistake with its cause and the rule that stops it before you fix it:
  `python3 tools/review/lessons.py add --site house-wip --round codex-<stage> ...`.
- Checks stay proportionate: unit tests for the layout logic and snapping; browser tests at desktop and phone sizes and in the
  simulated headset (`?xrsim=1`); close-up thumbnails as the kit's visual check; matched before/after frames of the kitchen-
  diner, lounge and front garden at each stage. No giant evidence ledgers.
- Never upload the drawings, photos or anything private; no purchases, no logins, no keys.

## Hand back
After each stage, a short note in `FURNISH-PROGRESS.md`: what was built (paths), what was checked, the branch, what's left.
At the end, a short report: the catalogue (counts by style and kind, a contact sheet of the thumbnails), matched before/after
frames of the three spaces, how to use edit mode and the bird's-eye view on each device, performance numbers, and what's left.
