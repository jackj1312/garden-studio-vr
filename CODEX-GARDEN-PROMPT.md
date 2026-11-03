You are working in Jack's live studio project: `~/Garden Studio VR` (this folder). Before anything else, tell me in one line
to switch you to your highest reasoning level, and wait until I say it's done.

I already have a first iteration of a garden design tool being built in this folder. **Find it first** (look on the
`codex/*` branches, in `FURNISH-PLAN.md` / `FURNISH-PROGRESS.md` and any garden, landscape or site editor code), read what it
does, and **add to it and improve it**: don't start a second tool, don't throw away what works. Work autonomously, stage by
stage, until every stage is done and tested. Ask me only for spending, logins/purchases, sending any photo to an outside
service, or a design choice this brief and the project files don't answer, and batch those questions.

## The idea
Garden design for clients that stays consistent from every angle. An image generator can't keep a layout the same across
many photos, so the design lives in 3D and every picture comes from it:
1. **Capture:** the client's garden photographed from many angles; we solve the camera positions to get the garden in true
   3D. A reference pole (known height) and/or two markers a measured distance apart confirm the scale.
2. **Concepts (optional, image generator):** a few design ideas painted onto ONE hero photo (Mediterranean, modern with a
   sunken fire pit, cottage garden...) for the client to react to. Mood boards only; nobody builds from them.
3. **Design:** the chosen idea is drawn in plan in the garden editor with real dimensions, as parametric building blocks.
4. **Matched "after" pictures:** the design rendered from the same solved camera positions as the client's photos, so
   before and after line up exactly and the layout can't drift.
5. **Polish (optional, image generator):** each render made more photoreal with the edges and depth locked, so only
   plants, textures and light change, never the layout.

## Read first
- `CLAUDE.md` (the project's rules: they apply to you), `PLAN.md` (the build plan; see its 2026-11-03 change-log entries,
  including the AI-light roadmap), `FIRST-PASS.md` (lessons: don't repeat them), `DETAIL-CHECKLIST.md`, `SURVEY-METHOD.md`,
  `CAPTURE.md`, `BENCHMARKS.md` (the SE Landscapes garden walkthrough is the bar for designed gardens).
- What exists for gardens: the camera solve and photo tools (`tools/photogrammetry/*`), the plan tools (`tools/plan/*`), the
  front garden build (`assets/sites/front-garden-model/`, `tools/house/make_setting.py`), the marking tool (`src/marks.js`:
  proposals are drawn on the ground in plan coordinates), the room planner (`planner.html`), the studio kit and layout
  system from the furnishing work, and my iteration of the garden tool (find it, as above).

## First: your plan
Write `GARDEN-PLAN.md` (concise and highly descriptive: what my iteration already does; goal; the stages below with inputs,
outputs and the check that proves each done; risks) and show it to me before building. Re-read it in full at the start of
every stage, before every fix round, after any context reset, and before every report. Change it only with a dated line
saying what changed and why.

## Stages (each on its own git branch off the current work; commit in small steps; never push)

**Stage 1 · Capture and scale** (branch `codex/garden-capture`)
- A simple capture guide for clients (how many photos, from where, the pole or two markers) and a checker that tells them
  before they leave the garden whether the photos are enough.
- Scale from the pole/markers, checked against the camera solve; the ground surface and levels (with LiDAR where available,
  WORKFLOW G1b) ready for design. Done when the solved garden matches a tape measurement within 20 mm.

**Stage 2 · The garden editor** (branch `codex/garden-editor`, extending my iteration)
- Draw in plan (desktop, phone; and in the headset with the controller ray on the ground) with snapping and typed dimensions:
  patios and paths (laying patterns: stretcher, herringbone, random flags; edging and borders), curved and straight retaining
  walls (drag the curve; height, coping, material), steps, sunken areas and fire pits (depth, steps down, seating, the fire
  bowl), raised beds (modular, sleeper/brick/rendered), lawns, gravel, decking, fences, gates, pergolas, lighting (festoon,
  spike, wall), water features, seating and garden furniture from the studio kit.
- Every element a parametric building block from the studio kit, reusable for every client, with real materials at true
  scale. Levels respected: a sunken fire pit really cuts into the ground, a retaining wall really holds a level change.
- Planting: palettes (cottage, Mediterranean, modern grasses, shade, wildlife), placed by drawing a bed and choosing a palette
  and density, with real species, heights and spread; mature and newly planted versions.
- The design saves to a layout file the walkthrough, the headset and the planner all read, like the furnishing layout.

**Stage 3 · Matched before/after pictures** (branch `codex/garden-views`)
- Render the design from every solved photo position, same lens, so each client photo has its "after" from exactly the same
  spot; a slider or side-by-side page to compare. No Cycles on the Mac: use the viewer's renderer, or prepare a capped cloud
  render job that I approve before it runs.

**Stage 4 · Optional image-generator steps** (branch `codex/garden-ai`)
- Concept boards from one hero photo, and the structure-locked polish of the matched renders (edges and depth locked; only
  plants, textures and light may change; reject any output whose outline moves). Prefer a local model if one runs on this
  Mac; otherwise prepare the service integration and STOP for my approval before any photo leaves the Mac. Client photos are
  private: send them nowhere without my explicit yes. Record which service, what is sent and the cost.
- These steps are optional extras; the garden works fully without them.

**Stage 5 · Into the walkthrough** (branch `codex/garden-walk`)
- The designed garden appears in the house walkthrough (Before = the garden today, After = the design), on desktop, phone and
  Quest, with the headset kept smooth (instancing, shared materials, plant cards for distance, room/area culling).

## Rules
- Jack's Mac is an 8 GB M1 Air: one heavy job at a time (Blender, conversions, captures); no Cycles renders or light bakes.
  Check `RESOURCE-STATUS.json`-style coordination with any other Codex job before starting a heavy one.
- Don't break what works: the house walkthrough, the furnishing system, the planner, navigation, marking tool, headset
  controls. Keep the walk test passing. Our front garden's brickwork, paving and layout stay as they are unless I approve.
- Log every mistake with its cause and the rule that stops it before you fix it:
  `python3 tools/review/lessons.py add --site house-wip --round codex-garden ...`.
- Checks stay proportionate: unit tests for the geometry blocks (walls hold levels, pits cut the ground, no overlaps), browser
  tests at desktop and phone sizes and in the simulated headset (`?xrsim=1`), and matched before/after frames of the front
  garden. No giant evidence ledgers.
- Never upload the drawings, photos or anything private without my explicit approval; no purchases, no logins, no keys.

## Keep the pipeline document current
Add the garden design stages to `docs/pipeline/Garden Studio Pipeline.html` (what each does, pictures, status badge, links),
and update it whenever you add or change something; publish with `tools/docs/publish_pipeline.sh`.

## Hand back
After each stage, a short note in `GARDEN-PROGRESS.md`: what was built (paths), what was checked, the branch, what's left.
At the end, a short report: the building blocks and planting palettes (with thumbnails), a matched before/after sheet of the
front garden with a sample design (patio, curved retaining wall, sunken fire pit, raised beds, planting), how to use the
editor on each device, headset performance, and what's left.
