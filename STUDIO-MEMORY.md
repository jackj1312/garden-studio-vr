# Studio memory — what every build has taught us

Jack, 31 Oct 2026: "create a md that you note important memories in too that every build reads and adds too so
every individual project can build from the last, this needs to be referenced regularly not just once at the
beginning."

**Read it:** at the start of every session, again before every gate in WORKFLOW.md (the section for that gate),
and before any decision that costs money or Jack's time.
**Add to it:** the moment something worth keeping is learned: a technique that worked, a number worth reusing, a
preference of Jack's, a trap. One dated line, newest at the bottom of its section, with the build it came from.
Mistakes go in CORRECTIONS-LOG.md (with their rule); this file holds what to *do*.

## Jack: aims and preferences
- 2026-10-31 · front garden · The aim is the Airbnb modelled walkthrough's quality (every surface and object
  real), not "good for VR". kogu's bedroom render is the film-tier bar. Not photo-real for its own sake: 1:1.
- 2026-10-31 · front garden · Full-quality VR = Unreal on a cloud GPU streamed to his Quest, which he controls.
- 2026-10-31 · front garden · Two builds of every site: "today" (everything, 1:1) and "clean" (fixed space only)
  for proposals.
- 2026-10-31 · front garden · Show him plans and elevations to sign off before building; he annotates them on
  the review page (review bar) and expects every note answered.
- 2026-10-31 · front garden · He judges against reality: matched side-by-sides (real photo | model, same camera)
  are the most useful thing to show him.

- 2026-10-31 · front garden · Fill ambiguity with stated presumed facts (continuity, regularity, UK standard
  sizes, like-for-like), marked as assumed on the plan; the client corrects. See WORKFLOW.md "Presumed facts".

- 2026-10-31 · front garden · "It's the details that matter most": kerb runs, junctions, upstands, steps, paving
  bonds, full-length boundaries. All now in DETAIL-CHECKLIST.md.

- 2026-10-31 · front garden · Jack wants a cheap Blender mockup before any cloud rental, and an in-headset
  drawing tool (Guardian-style) to mark corrections and lay out proposals, saved back into the plan.

- 2026-10-31 · front garden · Jack wants his reference photos around him in the headset, ranked by where he
  stands, cycled with the grip (export_refs.py + the viewer's reference view).

## Capture (G1)
- 2026-10-31 · front garden · A 2-min 4K walk video + stills solves well (121 of 145 frames); frames ~1 per metre.
- 2026-10-31 · front garden · Ask for close-ups of every surface and object early (12-item list in the chat of
  31 Oct; now in SURVEY-METHOD.md): they were the biggest single jump in realism.
- 2026-10-31 · front garden · Photos taken months apart differ (the pergola was built between April and October):
  date every photo and use the newest for "today".

- 2026-10-31 · front garden · Most of Jack's 13 quality faults traced back to photos we never asked for: use the
  standard capture list in SURVEY-METHOD.md on the first visit.

## Measuring (G1)
- 2026-10-31 · front garden · kerb_fit.py: lawn kerb found at 175/351 points, fit median 2 cm, curvature step
  0.34/m; a lawn edge beside a bed follows the bed's kerb at 0.11 m (one kerb, not two lines).
- 2026-10-31 · front garden · Extract the walk video at full 4K (frames match the solve 1:1) and run
  find_all_views.py: 26 elements, each seen in 7–61 views. It answered 11 of my 12 photo requests.
- 2026-10-31 · front garden · Scale from known points (window corners, arch) seen in two photos: rms 4 cm.
- 2026-10-31 · front garden · Orthophoto from the walk video at 2 cm/px gives ground edges to ±5 cm; trace by
  colour, read kerbs off 1 cm enlargements.
- 2026-10-31 · front garden · Wall elevations (facade_ortho.py) at 1 cm/px give window, door and eaves positions
  directly; they are only true on their own plane (roofs and set-back walls project wrongly onto it).
- 2026-10-31 · front garden · Roof heights: from 3D points on the tiles, not from wall elevations.
- 2026-10-31 · front garden · UK semis are not always symmetrical: the neighbour's windows were not a mirror of ours.

- 2026-10-31 · front garden house audit · probe.py: draw candidate 3D lines (two wall positions, three fascia
  heights) on 4K frames from 3+ cameras; the right one sits on the real edge in every view. Settled the porch wall,
  ridge, fascia, dish and step in minutes each.
- 2026-10-31 · front garden house audit · Wall faces: histogram the solve's 3D points by x (or y) at the wall; the
  peak is the face (porch: −1.67 vs the −1.85 in the plan). Fixtures: measure.py ray onto the plane at the
  fixture's OWN depth (the dish stands 0.24 m off its wall); two-view triangulation for things off any wall
  (alarm box: 1.4 cm spread).
- 2026-10-31 · front garden house audit · Roof: tiles end over the gutter at the fascia top (4.86), 0.40 m out from
  the wall; with the probed ridge (7.52 at y 5.45) that gives the pitch (44°). Mid-slope point fits alone drift ±3°.

## Textures and modelling (G4, G5)
- 2026-10-31 · front garden · Restarted the 3D build (v2) from the measured facts: the first build was patched from
  pre-survey code and could not reach the Airbnb bar. Keep the survey, data and tools; rebuild the model.
- 2026-10-31 · front garden · tools/phototex: random surfaces (gravel, lawn) tile well with make_tile.py; brick,
  block paving and boards need make_tile_periodic.py (whole repeats) or they ghost; one-off faces (shed front,
  door) are straightened with rectify.py and used once, not tiled.
- 2026-10-31 · front garden · True scale from unit sizes: brick 225 × 75 mm module, block paving ~160 mm rows,
  pea shingle 15–20 mm, fence boards ~100 mm pitch.
- 2026-10-31 · front garden · glTF caps colour factors at 1.0: lighten a texture in its image, not with a tint.

- 2026-10-31 · front garden · Build v2 (master/front-garden-v2.py) builds in 7 s; Eevee mockups render in 2-11 s per view
  headless at ~1000 px (1.1 GB peak): iterate on mockups freely on the Mac. Export of both GLBs: 46 s, 2.1 GB peak.
- 2026-10-31 · front garden · Close-ups shot in shade are grey-blue: colour-match each to the sunlit walk (match_colour.py).

- 2026-10-31 · front garden · The Airbnb method, re-read: CC0 scanned PBR materials (full map sets) + Python-generated
  textures on modest models, then Unreal's lighting and camera effects carry the realism. Never replace a PBR set with a
  colour-only photo; judge realism only in Unreal or Cycles.

- 2026-10-31 · front garden · Hard surfaces that work: every brick/block real geometry (bevelled) wearing one of the
  client's OWN unit faces cut from the close-up (tools/phototex/unit_library.py for blocks; mortar-mask cut for brick),
  flipped copies doubling the library, mortar/joint plane recessed behind. tools/blender/unit_surfaces.py. Patch test
  (1 m wall + 1.4 m paving, Cycles 96 spp, Mac GPU): 62 s, 3.7 GB peak. Traps: a mirrored axis turns bmesh cubes
  inside out; assign UVs after bevel, by position.

- 2026-10-31 · front garden house audit · G6 for a house: house_audit_render.py (Eevee + flat-colour ids, cropped to
  the house, plus a wall clash check) then house_pairs.py (photo undistorted with its solved lens | model | photo
  with the model's outlines). 37 views in ~90 s, 1.2 GB peak. The outline panel finds 0.1 m errors at 15 m.
- 2026-10-31 · front garden house audit · Where roofs meet is its own element: a wing hipped at the front has its
  outer slope in one plane with the main hip and its inner slope meets the main slope in a valley; lean-tos get
  stepped flashing up the wall and an apron at the top.

## Lighting and look (G5, G7)
- 2026-10-31 · front garden · Sun direction and height from the client's own frames (shadows, sun in shot); for
  Jack's garden: ~22° up, from the street side and the west.
- 2026-10-31 · front garden · Neutral tone mapping matched his photos; AgX washed them grey.
- 2026-10-31 · front garden · Cycles proof from a walk-frame camera is the quickest honest look test.

## Cloud and cost (G8)
- 2026-10-31 · front garden · RunPod via tools/cloud/cloud_blender.py; an L40 or 4090 bakes the ground light map
  (2040 × 2550, 256 spp) in ~4 min. Always a money cap; watch the remote log in the first minutes.
- 2026-10-31 · front garden · Python light-map packing hangs on ~450 objects: use smart_project +
  average_islands_scale + pack_islands.
