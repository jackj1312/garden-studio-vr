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

## Capture (G1)
- 2026-10-31 · front garden · A 2-min 4K walk video + stills solves well (121 of 145 frames); frames ~1 per metre.
- 2026-10-31 · front garden · Ask for close-ups of every surface and object early (12-item list in the chat of
  31 Oct; now in SURVEY-METHOD.md): they were the biggest single jump in realism.
- 2026-10-31 · front garden · Photos taken months apart differ (the pergola was built between April and October):
  date every photo and use the newest for "today".

## Measuring (G1)
- 2026-10-31 · front garden · Scale from known points (window corners, arch) seen in two photos: rms 4 cm.
- 2026-10-31 · front garden · Orthophoto from the walk video at 2 cm/px gives ground edges to ±5 cm; trace by
  colour, read kerbs off 1 cm enlargements.
- 2026-10-31 · front garden · Wall elevations (facade_ortho.py) at 1 cm/px give window, door and eaves positions
  directly; they are only true on their own plane (roofs and set-back walls project wrongly onto it).
- 2026-10-31 · front garden · Roof heights: from 3D points on the tiles, not from wall elevations.
- 2026-10-31 · front garden · UK semis are not always symmetrical: the neighbour's windows were not a mirror of ours.

## Textures and modelling (G4, G5)
- 2026-10-31 · front garden · tools/phototex: random surfaces (gravel, lawn) tile well with make_tile.py; brick,
  block paving and boards need make_tile_periodic.py (whole repeats) or they ghost; one-off faces (shed front,
  door) are straightened with rectify.py and used once, not tiled.
- 2026-10-31 · front garden · True scale from unit sizes: brick 225 × 75 mm module, block paving ~160 mm rows,
  pea shingle 15–20 mm, fence boards ~100 mm pitch.
- 2026-10-31 · front garden · glTF caps colour factors at 1.0: lighten a texture in its image, not with a tint.

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
