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
5. Ground: orthophoto (ortho.py), dense traced edges (trace_lawn.py, smooth.py) (2, 4, 5, 6).
6. Vertical things (fences, walls, hedges): fit to 3D points on their faces (7, 10).
7. **Walls: straight-on elevations of every face** (facade_ortho.py) — windows, doors, eaves, roofs, party walls,
   chimneys, neighbours, measured from them (20, 23).

## G2 · Sign-off: plan and elevations
- Draw the plan (draw_plan.py) and the elevations; publish the review page with the review bar (1, 9).
- The client (now Jack) annotates; every note is answered and redrawn. Sign-off before any modelling (20, 25).

## G3 · Element inventory
- A list of every element on the house and in the garden: what it IS (mirror, not window), material, colour,
  size, position, and the photos that prove it (at least two) (19, 21, 22).
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
- Export checks: no white or missing materials (11, 12).
- Three judges (Sonnet) against the benchmarks and the matched views; act on all, but photos win (18).
- **No cloud spend until this gate passes and Jack signs off the matched views (26).**

## G7 · Viewer
- Site mode: the site's own name, no demo controls (13); bounds, start point, collisions from the plan.

## G8 · Cloud (RunPod, cost approved per run)
- tools/cloud/cloud_blender.py garden-bake: build, bake light maps, export, proof stills; hard money cap (15, 16).
- Watch the remote log in the first minutes; stop anything idle.

## G9 · Deliver
- Quest in the browser: baked light (fallback).
- Full-quality VR: Unreal on a cloud GPU streamed to the Quest (CloudXR.js / Pixel Streaming) — being set up.
- Film: Cycles or Unreal on the cloud.
