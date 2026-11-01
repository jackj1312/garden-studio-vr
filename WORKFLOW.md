# Workflow — a client's home, from capture to walkthrough, repeatable without Jack

Each stage ends in a gate. A gate is a check that must pass (or a sign-off) before the next stage starts.
The numbers in brackets are rows of CORRECTIONS-LOG.md that the gate exists to prevent.
**At every gate: re-read STUDIO-MEMORY.md (its section for the gate) and the log rows for the gate; at the end of
every gate, add what was learned to STUDIO-MEMORY.md and any mistake to CORRECTIONS-LOG.md.**
This is a draft built on Jack's own garden (Oct 2026); it becomes final when Jack is happy with that output.

## G0 · References and brief
- Read every reference the client or Jack gives, from the primary source; say back what it is in specifics (27).
- Agree the outputs: today (1:1, everything movable) and/or clean (fixed space only, the base for designs).

## G1 · Survey (measure, never estimate)
On site (SURVEY-METHOD.md, CAPTURE.md):
1. Walk video (slow loop of the whole site), stills of every face of the house.
2. **Close-ups of every surface and object** (the list in SURVEY-METHOD.md): brick, windows, doors, roof, paving,
   gravel, lawn, kerbs, fence, shed, bins, bench, pots, each plant, bark, hedges, gutters, downpipes, lights, drains.
   A sheet of A4 in some shots for scale. Overcast is best.
3. Later: Moasure for boundaries and levels; LiDAR phone for shape.

At the desk (tools/photogrammetry):
4. Solve the cameras (sfm_walk.py); lock the scale with known points (3); check camera heights and a known width.
5. Ground: orthophoto (ortho.py) at 1 cm; kerbs as laid runs with kerb_runs.py (lines, curves, true corners, eased joins), positions from kerb_fit.py (smooth splines between true corners,
   curvature check must pass) (2, 4, 5, 6, 34, 46).
6. Vertical things (fences, walls, hedges): fit to 3D points on their faces (7, 10).
7. **Walls: straight-on elevations of every face** (facade_ortho.py) — windows, doors, eaves, roofs, party walls,
   chimneys, neighbours, measured from them (20, 23).
8. **Mine the capture before asking for more (45).** Extract the walk video at full resolution (4K, every solved
   frame) and list, for every inventory element, the frames and photos that see it (find_views.py: ranked,
   full-resolution crops). Model, texture and check each element from its sheet. Ask the client for new photos only
   for elements no frame shows, and say which frames were searched.

## Presumed facts (Jack, 31 Oct 2026): ambiguity is filled by stated assumptions, never by gaps
No client's garden is ever fully visible. Where the evidence runs out, apply a documented assumption so the model
stays cohesive and lifelike, and mark it on the plan as **assumed** (its own colour) so the client can correct it:
- **Continuity**: a kerb, hedge, fence or wall continues as it was laid until evidence says it stops (35).
- **Regularity**: kerbs are smooth curves of steady radius and straight runs are straight; shared kerbs are one
  line; parallel things stay parallel; repeated things (posts, windows, setts) keep their spacing.
- **Standard sizes** (UK): brick 215 × 102.5 × 65 mm + 10 mm joints; block paving 200 × 100 mm (tumbled sets
  140/210 mm); kerb setts 100 × 100 mm; doors 2.0–2.1 m; step risers ~150 mm; wheelie bins 240 l; fence posts
  1.8 m apart; storey height ~2.6 m.
- **Like-for-like**: an unseen side of an object matches its seen side; an unseen part of a bed matches the
  planting beside it.
- **Hidden ground**: under a parked car or in deep shadow, the surface around it continues.
- Every assumption is listed in the site's plan JSON ("assumed": [...]) with what it fills and why; the client's
  correction always wins and goes into CORRECTIONS-LOG if the assumption was wrong.

## G2 · Sign-off: plan and elevations
- Draw the plan (draw_plan.py) and the elevations; publish the review page with the review bar (1, 9).
- The client (now Jack) annotates; every note is answered and redrawn. Sign-off before any modelling (20, 25).

## G3 · Element inventory
- A list of every element on the house and in the garden: what it IS (mirror, not window), material, colour,
  size, position, and the photos that prove it (at least two) (19, 21, 22).
- Each element's evidence sheet (find_views.py) is attached to its inventory row.
- **Go through DETAIL-CHECKLIST.md line by line**; every line is answered in the inventory (seen, assumed, or not present).
- Each element is tagged fixed or movable (bins, broom, bike, pots, cushions, toys) for the clean build.
- Vehicles are never built (8). Neighbours are modelled as seen, never mirrored (23).

## G4 · Textures from the client's own surfaces
- tools/phototex: make_tile.py (random surfaces), make_tile_periodic.py (brick, paving, boards),
  rectify.py (one-off faces: doors, shed fronts). True scale from known unit sizes (17, 18).
- The client's photos outrank judges and assumptions (18).

## G5 · Build (Blender, scripted)
- master/<site>-build.py reads the plan, elevations and inventory; FG_MODE=today or clean.
- Real units for real things: kerbs and edgings as setts, boards as boards, windows from the elevation (24, 25).
- Sun direction and height from the client's own shadows (14).

## G6 · Self-check against reality (on the Mac, light)
- tools/blender/inspect_house.py: the model rendered through every solved camera, side by side with the photo.
- Go element by element through the inventory in every matched view; anything off goes in the log first (26).
- Re-check every line of DETAIL-CHECKLIST.md against the matched views.
- Export checks: no white or missing materials (11, 12).
- Three judges (Sonnet) against the benchmarks and the matched views; act on all, but photos win (18).
- **Matched-view audit before anything is shown to Jack (PERMANENT, Jack 1 Nov 2026: "save this step as a permanent step before
  presenting it to me").** A dedicated agent renders the model through EVERY solved camera that sees each part, pairs real |
  model | model-outline-on-photo (tools/blender/house_audit_render.py, house_pairs.py), goes element by element through the
  inventory and DETAIL-CHECKLIST.md, writes every discrepancy with evidence to an AUDIT.md, fixes each from measurements,
  runs the clash check (0 overlapping parts), and repeats until outlines sit on the real edges. Covers house, ground, kerbs,
  junctions, beds, boundaries, objects. Also checks the headset marks list (marks.json notes) so Jack's notes become checks.
  First run (house, 1 Nov): 52 faults found and fixed. Then the three judges (quality vs benchmarks), then Jack.
- **Cheap mockup first (Jack, 31 Oct):** a low-quality Blender render of the full scene on the Mac, headless
  (Eevee or Workbench, grass hair off, ~1000 px, one at a time), from the matched cameras and a short walk path.
  Iterate on that until it is right. Only then rent a cloud GPU for the real light bake, film or streaming.
- **No cloud spend until this gate passes and Jack signs off the matched views and the mockup (26).**

## G7 · Viewer
- Site mode: the site's own name, no demo controls (13); bounds, start point, collisions from the plan.

- **Reference view in the headset (Jack, 31 Oct):** the client's own photos surround the viewer, ranked by where they
  stand and look (tools/photogrammetry/export_refs.py makes refs.json from the camera solve); the grip cycles tabs.
  The model is judged against the evidence from inside it.

## G8 · Cloud (RunPod, cost approved per run)
- tools/cloud/cloud_blender.py garden-bake: build, bake light maps, export, proof stills; hard money cap (15, 16).
- Watch the remote log in the first minutes; stop anything idle.

## G9 · Deliver
- Quest in the browser: baked light (fallback).
- Full-quality VR: Unreal on a cloud GPU streamed to the Quest (CloudXR.js / Pixel Streaming) — being set up.
- **In-headset marking tool (Jack, 31 Oct; to build):** point the controller at the ground and draw, the way you
  draw the Quest's Guardian boundary. Two uses: mark corrections on the model ("this kerb is wrong here") and lay out
  proposed changes (new beds, paths, a studio footprint). Drawings are saved in plan coordinates and come straight
  back into the plan JSON, so a correction made in the headset updates the plan and the next build.
- Film: Cycles or Unreal on the cloud.
