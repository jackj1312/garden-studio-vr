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

- 2026-11-01 · all gates · Jack: wherever a process is unsure, research deeply before building. Search X for relevant
  posts, find the most popular and best work, study it frame by frame, read the threads, blogs and scene notes that explain
  the method, and trace each one to its maker (reposts lie). Desktop/23 Battle Road is the benchmark folder for comparing agents.

- 2026-11-01 · all gates · Two benchmarks for two products, sharing methods both ways: Desktop/23 Battle Road (garden and
  home recreation) and Desktop/23 Battle Road - Build Sequence Benchmark (walkable, editable, regs-checked build sequence for
  architects and builders, from the drawings). Methods from one are used in the other wherever they help.
- 2026-11-01 · Unreal look (Jack): "i want this to look incredible not just a uprated version of ours". Rebuild the look in
  Unreal on the measured layout: positions, sizes and levels exact; surfaces from pre-scanned textures and objects from
  ready-made assets that look good and are close (the side shed's timber, the bench), not exact recreations.

## Capture (G1)
- 2026-10-31 · front garden · A 2-min 4K walk video + stills solves well (121 of 145 frames); frames ~1 per metre.
- 2026-10-31 · front garden · Ask for close-ups of every surface and object early (12-item list in the chat of
  31 Oct; now in SURVEY-METHOD.md): they were the biggest single jump in realism.
- 2026-10-31 · front garden · Photos taken months apart differ (the pergola was built between April and October):
  date every photo and use the newest for "today".

- 2026-10-31 · front garden · Most of Jack's 13 quality faults traced back to photos we never asked for: use the
  standard capture list in SURVEY-METHOD.md on the first visit.

- 2026-11-01 · benchmark 4 · The splat house that went viral was NOT a phone scan: Cameron Cone (broadcast DP, Austin)
  shot it on a Canon 5D Mk IV with 14 mm + 35 mm lenses plus a DJI Pocket gimbal, captured each area separately,
  aligned in RealityCapture, trained in Postshot, cleaned objects in C4D, compressed and merged in SuperSplat, over
  months and several versions. Realism comes from sharp, dense, overlapping stills per room, not from the app.
- 2026-11-01 · benchmark 4 · White walls do not align (no features): the 360 route (Tony Rose, Insta360 X5, ~1000
  interval photos every ~1 m, Spirula Studio with depth + normal priors) is how others filled plain walls.

- 2026-11-01 · front garden · Splat test: re-solving the walk video at 4 fps solved all 488 sharp frames (0.54 px
  reprojection) against the old solve's 107. Extract densely for splats. The RunPod image lacks libSM (pycolmap needs it):
  install it in the pod script. A global solve of 488 frames took 30 min on the pod's CPU.

- 2026-11-01 · front garden splat test · For a Gaussian splat the same 2-min walk is enough to look real at walking
  distance: at 4 fps all 488 sharp frames solved (the old 2 fps solve kept 107). Held-out frames scored 19.1 dB PSNR
  on average (porch 24, shed 23, path and tree 18-19). What it lacks: the ground within ~2 m of the feet (smeared), tree
  crowns and far trees (soft), and big floaters as soon as you turn away from the line walked. A capture for splats
  needs: a slow walk (~0.5 m/s) with the phone at chest height AND a second pass pointing down at the ground; a slow
  360° turn at 5-6 spots (path end, porch, lawn centre, tree, drive, shed); each tree circled at 2 m; locked exposure
  and no zoom; no people or own shadow (low sun drags a shadow through the drive); overcast light is best.

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

- 2026-11-01 · front garden · Architect's drawings (BDS, in Jack's Gmail) are a measuring source. Where the drawings
  and the photo solve disagree, ASK Jack each time (his rule); do not pick a winner. Drawings may be proposals, not
  as-built: the porch was built slightly differently from BDS's proposal, so the porch stays as the walk video shows it.

- 2026-11-01 · front garden · Ask every client for the architect's drawing set first: BDS's PDFs are true vector A1 at
  1:50 / 1:100 (plans, elevations, 5 sections, roof plan), so every wall, opening, ceiling and roof is read exactly with
  tools/plan/read_drawing.py. Get the newest revision of each sheet (here 4915.2B/3A/4A, 27 Oct 2022; 4915.1 = before).
  The PDF pages are stored rotated 270: draw overlays on the rendered image, transform vector paths by rotation_matrix.
- 2026-11-01 · tooling · The Gmail connector reads mail but cannot save attachments; script/blob downloads are blocked
  after the first. What works: Claude in Chrome, click Gmail's own "Download all attachments" button (zip to Downloads).

- 2026-11-01 · front garden audit-2 · Locate every headset note from marks.json first: points3d are three.js (x, up, −plan y),
  normals too; the hit surface + normal says WHAT was marked (the "barge board" strokes faced down = the verge underside).
- 2026-11-01 · front garden audit-2 · Timber sections: probe two candidate squares (90 vs 150 mm) on 4+ close frames; the
  real silhouette matches one at a glance. Heights of anything (fence, shed front, beams): candidate lines at 2-3 heights.
- 2026-11-01 · front garden audit-2 · Check structures beside the house against its eaves: the pergola's rear post had to
  be in front of the porch gutter (photos), which fixed its line better than the ±10 cm probe.
- 2026-11-01 · front garden audit-2 · A dated photo can mislead an audit: the April stills show no main bed or pergola
  (built later); use the walk (Sept/Oct) for "today" and say which date a view shows.

- 2026-11-01 · front garden audit-3 · A hedge's footprint: draw candidate ground lines (x and y) on 3 frames; the bed's own
  edging is the clearest line. Jack's garden: the hedge stands on OUR side of the path line (x -4.95..-4.20) in its own
  bed (x -4.84..-4.02), not on the neighbour's side as the stroke-based plan had it. Height: candidate tops along the length.
- 2026-11-01 · front garden audit-3 · Objects' sizes: triangulate the two ends from two frames (measure.triangulate: the
  bench seat ends agreed to 7 mm); ground rays alone gave positions but not sizes. Ground rays need the ground's REAL height:
  the porch court sits ~7 cm above z 0 (3D points), which threw rays 0.2 m back at grazing angles.
- 2026-11-01 · front garden audit-3 · Colour sampling helper (scratch: sample.py): project a 3D quad into the 4K frame, mean
  the pixels inside, optional luminance/saturation filter (mortar = bright low-saturation pixels; lawn = green-only pixels;
  bins = dark pixels). ALWAYS save the crop and look: half the first boxes hit the wrong surface (log 52 again).

- 2026-11-01 · front garden audit-4 · Registering the architect's drawing to the photo frame: anchor on two walls the photos fix
  well (porch side wall x, main front wall face y) and the paving datum (photo z = drawn z + 0.231). Then probe each drawn line
  against the photo line on 3+ frames (arris lines, silhouettes against sky or a pale wall behind) and take the 3D-point face
  peaks: the drawing won where they agreed (bay sides 0.705/4.325, party line -4.63); upstairs heights, eaves, bay projection
  and chimney differ 8-33 cm and stay as photographed, listed for Jack. Existing-house surveys can be ~0.2 m out in height.
- 2026-11-01 · front garden audit-4 · Garbled voice notes: decode with imageio-ffmpeg and re-run faster-whisper with beam 5, no
  VAD and an initial_prompt of the likely trade words (bargeboard, fascia, soffit, soldier course): "Podge both" decoded as
  "Bargeboard", "surgical" as soldier course, "engine" as edging. The mark's own surface and normal say what was pointed at.

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

- 2026-11-01 · front garden audit-2 · Edgings that read right: lay_units() in front-garden-v2.py — the client's own paving
  faces turned to the border colour (luminance kept), 100 mm rows, 140/210 mm lengths, wedge-cut between the inner and
  outer lines on curves, rounded edges, runs laid in order with butt joints (a footprint index stops later runs at
  earlier ones, posts and walls). ~1,400 units build in ~2 s.
- 2026-11-01 · front garden audit-2 · Ground surfaces: one laid area per material, cut round everything that sits in it
  (cut_surface: prism + exact boolean, keep the top faces). Soil sits just under its edging tops (0.005 vs 0.014).
- 2026-11-01 · front garden audit-2 · Full-scene clash check (tools/blender/clash_check.py via house_audit_render.py
  --passes clash): solid inside-volume test + coplanar duplicates + 1 cm ground raster + setts within runs + open parts.
  559 objects in ~10 s. Before: 46 / 10 / 6 / 18; after 0 / 0 / 0 / 0. Things standing ON the ground are solids, not
  ground units (else wheels and pots read as "soil over block").
- 2026-11-01 · front garden audit-2 · Real doors for Unreal: build the leaf round its glazed openings, recess the glass,
  add beads, handle, letter plate; map the photo only on outward faces (two material slots) so edges stay clean.

- 2026-11-01 · front garden audit-3 · Seamless sheets: lay rows cyclically (the unit crossing the edge is repeated on the
  other side) and check by tiling 2x2 (bake_unit_sheets.py seam_check). The old paving sheet drew a dark broken line every
  4 m, mistaken for shadows in audit-2.
- 2026-11-01 · front garden audit-3 · Foliage and stone from the client's own frames: make_tile.py on a tight crop of the
  hedge face (walk_0043), the conifers (20504/20505), the lava-glaze pot, the bench, then match_colour.py to a sunlit walk
  box; box-projected at the crop's true width (hedge 0.56 m, conifer 0.17-0.35 m, pot/bench 0.2 m).
- 2026-11-01 · front garden audit-3 · Printed faces (plaque, bin numbers) as decal images drawn with PIL from what the
  close-up says (tools/phototex/make_decals.py); check the decal is not mirrored in the matched view (u runs to the
  viewer's right).
- 2026-11-01 · front garden audit-3 · A mirror in a real-time viewer: render the garden from the viewer's reflection
  behind the mirror plane (hide everything behind the plane), flip, dim to 85 %, use as the mirror's face
  (front-garden-v2.py --mirror). Reads as a garden mirror in Eevee and three.js.
- 2026-11-01 · front garden audit-3 · cyl() had all faces inside out ((u, w, d) left-handed); the viewer's FrontSide hid
  their outsides. Every build now ends with an outward-normals pass over all closed parts and an inside-out check.
- 2026-11-01 · front garden audit-3 · Lawn tile: take the fallen leaves out (tools/phototex/remove_leaves.py) or the same
  leaves repeat every tile; sample the lawn green from green-only pixels (116, 131, 42 sunlit), not the whole patch.

- 2026-11-01 · front garden audit-4 · Soldier courses from their own close-up: tools/phototex/soldier_units.py straightens the
  band (4-corner homography), finds the joints by 'mortarness', cuts each brick and matches the set to the wall sheet keeping
  the soldier/stretcher colour ratio seen in the same photo; the build puts one atlas cell on each 65 mm unit, 4 mm proud.
- 2026-11-01 · front garden audit-4 · Lean-to porch verges end in a BOX END (here 0.30 m bargeboard, box from the fascia back to
  the wall, bottom 1.92): build it as one closed prism; the level front soffit starts at the wall line, the verge soffit behind
  the box. Without it a hole shows the brick above the soffit.
- 2026-11-01 · front garden audit-4 · Edging corners: cut legs at the middle of the angle plateau, run the leg ending at a corner
  past it by the band's lip and cut the last unit to fit; inside borders sit 8 mm over the paving edge.
- 2026-11-01 · front garden audit-4 · New G6 checks in tools/blender/clash_check.py: must_touch (the site's MUST_TOUCH rules,
  min mesh distance) and 'soil past its border' in the ground raster (clusters >= 5 cells, posts allow-listed).
- 2026-11-01 · house build · Drawings -> staged model: tools/house/generate_house.py (Blender headless, ~15 s a version on the Mac) reads the trace (house_drawn.json) plus a version spec; a proposal is the DIFF of its base state and its own state (walls by footprint overlap, rafters by collinear intervals, roof tiles by plane pieces), so demolition, kept and new parts fall out without hand-listing. Version specs live beside the client's drawings (private).
- 2026-11-01 · house build · Pitched roofs as unions of convex 'wings' (lowest of a wing's planes, highest of the wings) give hips, valleys, catslides and verges exactly; rafters are laid at the drawn positions and clipped to each plane's visible pieces. Check the planes against a drawn section's bearing before trusting plan-scaled hip points.
- 2026-11-01 · house build · Real-looking construction materials without downloads: tools/house/make_textures.py (true-scale PBR: client brick sheets, sampled roof colour (156,138,120) with moss, 440x215 block, foil PIR 1200x450 with print, C24 with grain and grade stamp, membrane, DPM, A393 mesh as alpha mask, plus local CC0 Poly Haven concrete/gravel/soil). 43 sets in 13 s; WebP in the GLB (approved scheme 14 MB, 69k tris).
- 2026-11-01 · house build · G6 for drawings: tools/house/house_slices.py cuts the exported GLB (plans at FFL+1.2, section planes, elevation projections) and house_overlay.py measures each wall face against the sheet's own vectors (trace_drawing.extract). Measure faces only: internal leaf/insulation lines are not drawn as straight lines and pair with the wrong neighbour.

- 1 Nov 2026 (house build, round 5): temporary works are modelled as a site manager would plan them, each "typical — not from the drawings": Heras compound, skip on boards, welfare cabin and toilet, pallets and bulk bags, floor protection, scaffold up for the strip-out with guardrails, toe boards, ladder bay, ties and braces, inner standards stopping under an eaves overhang, sheeting over an opened wing, tarps over new rafters until the membrane. Props say "temporary works design by others".
- 1 Nov 2026: an as-built layer (CONTRACT §6) from the photo survey sits over the drawn front: walls re-cut where the survey puts the frames, the real anthracite frames, stone/concrete surrounds, lead strip, the soldier course from Jack's own cut bricks, dish, meter box, lights, mirror and plaque. Depths stay drawn; where the survey's face depth differs (bay 255 mm) it is a question, not geometry.
- 1 Nov 2026: Jack's roof photos read median (153,126,109) in sun and (107,88,82) in shade, against the garden model's flat (156,138,120). The tile texture base was set darker and browner (148,116,100) because the sunlit front slope renders lighter than the photo under the look-render sun.

- 2026-11-02 · house furnishing · BlendKit through Jack's live Blender, scripted: requests the public search API for
  `asset_base_id:<id>`, `blenderkit.search.parse_result(result)`, then `blenderkit.download.start_download(ad, model_location=..,
  model_rotation=.., resolution='resolution_1K')`; a bpy.app.timers queue starts the next when `download.download_tasks` is empty
  and clears the appended objects. 28 models in ~10 min; files land in ~/blenderkit_data/models/<slug>_<id>/*.blend with
  textures packed. Copy each to asset-library/blendkit/<KEY>/source.blend + asset.json (licence flags) and quit the GUI.
- 2026-11-02 · house furnishing · Library models: link, then `view_layer.update()` BEFORE reading child matrix_world (FBX-style
  rotated parent empties), or they come in lying on their backs. BlendKit fronts face -Y (turn 180 to the +Y item frame),
  except some (the wall-hung WC faces +Y): the close-up sheet (tools/library/test_sheet.py) shows it at once. A test-sheet scene
  must delete the factory cube.
- 2026-11-02 · house furnishing · ADAPT by stretch zones (hb_furnish._remap2: keep_lo/keep_hi fractions per axis kept at size,
  middle stretched) and whole seat modules removed for sofas (islands inside the cut slab deleted, the frame closes up):
  Burrard 3-seat -> 2-seat 1600/1700 reads right. Beds: keep the bottom 55 % (mattress, bedding) and stretch only the headboard.
- 2026-11-02 · house furnishing · Cloth sims headless are fast (tools/library/cloth_soft.py): 20x40 grids, 60-70 frames, ~1 s
  each on the M1; colliders for every bar/frame/floor (else a duvet falls to -0.5 m), no subdivision (Quest), solidify for
  thickness, smooth shading. Save in the spec item's own frame and never re-pivot on load.
- 2026-11-02 · house furnishing · A furnished GLB renders at ~65-80 s per Eevee frame on the Mac (shader compile for the library
  materials): budget ~35 min for both versions' room frames; furnished After ~850k tris / 52 MB quest GLB before meshopt.
- 2026-11-02 · house furnishing · Every scan loop in a build script needs a hard bound (e.g. `while ... and len(col) < 200`):
  one scripted edit put a step after an inline comment, the loop never advanced and the build swapped 7.5 GB on the 8 GB Mac (F37).
- 2026-11-02 · house furnishing · A shell fix is closed only by a matched close-up frame from the camera that saw the fault.
  The stairwell wall head (F34) passed every gate twice and still showed rafter ends from the landing.

## Lighting and look (G5, G7)
- 2026-10-31 · front garden · Sun direction and height from the client's own frames (shadows, sun in shot); for
  Jack's garden: ~22° up, from the street side and the west.
- 2026-10-31 · front garden · Neutral tone mapping matched his photos; AgX washed them grey.
- 2026-10-31 · front garden · Cycles proof from a walk-frame camera is the quickest honest look test.

- 2026-11-01 · front garden audit-3 · site.json is written by the export step from plan + built objects (boxes with rot,
  circles, polygons for curved beds; app.js resolves polygons), and tools/check_site_export.py fails if it is older than
  either GLB. The viewer shows a byte progress bar and starts on the path 6 m from the door.

- 1 Nov 2026: the house look renders use the Standard view transform, the clear-sky HDRI (kloofendal_43d, strength 0.8) and the sun at 4.5. AgX with the partly cloudy sky washed the brick out.

- 2026-11-01 · house, first Quest test · What landed: standing at the road looking at the whole house. What didn't: gaze
  picking (use a right-controller ray), a board that can't be hidden, flat "cartoon" surfaces, falling through at the
  stair top, freezes. A desktop pass proves nothing about the headset: walk every stair, read frame time and memory on
  the Quest, and do a scale check against known heights (the drawn 2110 under a steel feels low in VR even when right).

## Cloud and cost (G8)
- 2026-10-31 · front garden · RunPod via tools/cloud/cloud_blender.py; an L40 or 4090 bakes the ground light map
  (2040 × 2550, 256 spp) in ~4 min. Always a money cap; watch the remote log in the first minutes.
- 2026-10-31 · front garden · Python light-map packing hangs on ~450 objects: use smart_project +
  average_islands_scale + pack_islands.

- 2026-11-01 · front garden splat test · tools/cloud/cloud_splat.py (+ splat_pod.sh/.py): walk video in, splat out on
  one RunPod GPU. Run 2: L40S $0.79/h, 64 min, $0.84 (£0.66): installs 3 min, frames 4 fps 40 s, GPU SIFT 18 s,
  17.5k pairs matched 48 s, GLOMAP global solve 23-30 min (CPU-bound, only ~3 cores used: the slow step), gsplat MCMC
  30k steps at 1080x1920, 1.5M Gaussians in 25 min, download 1.2 GB in 7 min. The whole test cost £1.02 (run 1 £0.36 lost).
- 2026-11-01 · splat test · Lock a new solve to the site's metres by finding the old solve's frames among the new ones
  by picture, then Umeyama on camera centres: 0.15 m RMS at 4 fps (nearest-frame timing; interpolate for better).
- 2026-11-01 · splat test · Web formats: splat-transform 3.10.1 .compressed.ply works on a CPU pod (1.5M Gaussians ->
  92 MB; the 700k Quest copy -> 43 MB); .sog fails there (k-means needs a GPU device for node). The viewer is
  splat.html?site=<name> (PlayCanvas 2.23.1, WebXR, stick locomotion); the Quest uses the light copy over :8443.
- 2026-11-01 · Unreal cloud · Epic's engine images (ghcr.io/epicgames/unreal-engine, newest dev-slim-5.8.4) need the GitHub
  account to be IN the EpicGames org (accept the invite at github.com/orgs/EpicGames/invitation), not just linked. No SSH in
  them: drive the pod with tools/cloud/pod_agent.py over RunPod's HTTPS proxy. Jack's rule: every teardown salvages first
  (renders, logs, project, shader cache) so a failure never wastes money already spent.
- 2026-11-01 · house viewer · A read path must never copy the whole design; cache text widths (measureText ~40 µs a call);
  draw and upload a hidden VR panel before it is shown. Test VR code with `?xrsim=1` and `?test=walk` (head mode too).
- 2026-11-01 · house round 6 · A room outline is not a floor: probe the walking line at stair heads. Diff kept existing
  floors/foundations by area. Time wall courses by height. gltf-transform meshopt halves the Quest GLB and keeps extras.
  ambientCG API: ambientcg.com/api/v2/full_json?type=Material&q=…, download get?file=<id>_1K-JPG.zip. Heights: ray-cast the
  GLB per room before believing "it feels wrong" (the drawings were right; 2.11 m steel is low by design).
- 2026-11-01 · studio · Jack's Mac (8 GB) struggles when several jobs run: run one heavy job at a time, stop servers that
  are not in use (review page, old upload/static servers), keep only the headset server up while he tests.
- 2026-11-01 · tools · AnyScene (github.com/apekshik/anyscene, MIT, 151 stars, Oct 2026; seen via @CY160909): agents build
  Blender scenes from a brief; image->3D props via Tripo H3.1 + Meshy 7.1 on fal (~$1.65 a prop, pick the better), a
  prop validator after every dressing pass (BVH overlap with a 3 mm lift, prop-prop clashes, floating > 1 cm with the ray
  started above the support, spiral-search to a clear spot), gates with contact sheets (concept, picks, clay layout,
  lit stills, shot previews), grime/edge-wear node group with per-instance tint, a camera rig (handheld walk, rack focus,
  lens FX). Borrow: the validator and the clay-sheet gate (free). Later, with Jack's OK: image->3D for signature items
  free libraries lack. Not for us: inventing scenes from a brief (we need measured truth); Cycles on a local NVIDIA GPU.
- 2026-11-01 · planner · SVG drawn in metres: give strokes and label halos in world units or vector-effect non-scaling-stroke,
  or px values become metres and cover the plan. Room planner: planner.html (2D first, 3D boxes on demand), change list in
  assets/sites/house/spec/changes/ via /spec/changes, catalogue_v1.json (399 entries, style-tagged).
- 2026-11-01 · planner · Jack: "this is the kind of thing this is useful for, it catches mistakes early." The planner's live checks
  (faces the wall, overlaps, door swings, drawer clearance, floating) found 9 back-to-front kitchen/utility units in a signed
  spec before any 3D time. Run its checks on every spec; fixes go in as numbered errata in SIGNOFF.md with Jack's OK.
- 2026-11-01 · assets · Free sources ranked in ~/Desktop/garden-scans/asset-library/SOURCES.md. No login: Poly Haven (CC0, API,
  User-Agent required), ambientCG (CC0), Smithsonian (decor). Best for fittings: BlendKit (ex-BlenderKit; free plan, .blend,
  needs Jack's login; prefer CC0 items for the web viewer). Fab/Megascans not free since 2024 (free packs fortnightly; keep
  out of the web viewer until the EULA is read). Avoid IKEA (NC), Thingiverse, Poliigon/CGTrader/TurboSquid/Dimensiva/BIM in
  the web viewer (fine in renders). No free source has decent skirting/architraves/window boards/shaker doors: model them.
- 2026-11-01 · tools · gaussian-splat-to-blender-nodes ("World to World Mapping", github.com/gokayfem/gaussian-splat-to-blender-nodes,
  MIT, 71 stars, 24 Oct 2026; seen via @VFXDESK): an AGENT-GUIDED reconstruction skill, not an automatic splat-to-mesh
  converter: splat as reference -> measured frame and cameras -> scene parts rebuilt as editable Geometry/Shader Nodes ->
  audit + matched-view comparison -> optional calibrated multi-view projection of the captured look onto the meshes (UV
  prep, depth visibility, robust projection, material fallback) -> packed .blend. Same idea as our measured model + photo
  textures; worth borrowing its hybrid projection tools for "today" surfaces (brick, paving, garden) after the first build.
  Review the code before installing it as a skill (external code).
- 2026-11-01 · viewer · The Quest browser cannot use screen post effects in VR: a VR motion blur is drawn per eye off-screen at reduced
  resolution, only while the sticks move (never for real head motion), periphery only, behind a frame-rate check that steps
  resolution down then falls back to the vignette (src/house/motionblur.js). Smooth turn 75 deg/s, eased 0.15 s.
- 2026-11-01 · viewer · Effect strengths (blur, vignette, speeds) are judged by Jack on the device before they become defaults, tuned
  from subtle upward in small steps. Desktop = pointer-lock mouse-look with a crosshair; phones = twin thumb sticks (h22).
- 2026-11-01 · viewer · Phones use the headset's light path (meshopt quest GLB, 2k sky, 1024 shadows, no screen post, pixel ratio <= 1.25, one
  version in memory): LITE in src/house/viewer.js (h23). The desktop browser's quality = full textures + GTAO + MSAA; the Quest can't run that live,
  and there is no Mac-to-Quest PC-VR streaming route (Link, Air Link, Steam Link, ALVR all need Windows/Linux). Close the gap with baked light/AO + KTX2.
- 2026-11-01 · process · Lessons loop: every headset mark and every self-found fix becomes a finding (tools/review/lessons.py) with root
  cause, rule and check before it is fixed; FIRST-PASS.md is what every reviewer reads first; lessons.py gate before Jack sees anything.
- 2026-11-02 · process · Wait loops must wait on a PID or a done-file, never on `pgrep -f <script name>` (the loop's own command line
  matches, so it never ends: two stuck loops in the shell round).
- 2026-11-02 · viewer · Check every build IN THE VIEWER, not only in Blender frames: furniture rendered black in three (vertexColors
  + texCoord 1 lost in batching) while Blender looked right. A hidden browser pane doesn't redraw: render manually and POST the
  canvas to a local receiver to see true frames.
- 2026-11-02 · review · Jack: one capture per room misses most faults; planned audit = 360 sweep at a grid of points in every nook
  and outside, machine material-ID check first, cheap model on contact sheets, main model only on flagged frames (WORKFLOW G6).
- 2026-11-02 · plan · The Airbnb benchmark studied from its primary sources (write-up + video): AIRBNB-METHOD.md. The look is light
  (low warm sun, hard plant shadows, god rays + dust, bounce, emissive lamps, warm grade), true-scale textures, shop-density styling,
  simple clean geometry, a film camera, 849 self-check screenshots, 5 blunt feedback rounds on fixed cameras, real buyable products.
  PLAN.md written from it; it is the anchor for the house build (re-read every stage / fix round / compaction / report).
- 2026-11-02 · process · Jack's first three spaces for the plan: new kitchen-diner, front garden, lounge, then he checks. Questions to him must
  be one idea each in plain words with the consequence; he didn't understand 'hero rooms', 'anchor', 'presets' (row 239).
- 2026-11-02 · business · Jack: Max 5x; price per house ~£800 + £200 for VR. Unreal cap stays £10 for this house (stills only; the
  checking loop runs in the free web viewer). Available assets for this test; buyable product list later. First spaces: new
  kitchen-diner, front garden, lounge; then he checks. Usage card at 70% of the week after ~2 days: work in small checkable steps.
- 2026-11-02 · process · Standing rule: tell Jack when to change the session model and to which, one line at the top of the reply
  (Model: switch to … now). Fable = plan/verdict, Opus = build/fix, Sonnet = run/read, Haiku = count.
- 2026-11-02 · usage · Jack keeps 10% of the week for website work: house work stops when the usage card reads 90% (week resets
  Fri 7 Nov). Check the card before every heavy step and when an agent reports; stop an agent at ~88% so it can report.
- 2026-11-02 · sweep (G6/S8) · The capture harness works: `?capture=1` gives `__house.captureAt` (feet, yaw, pitch, eye; JPEG, or the PART
  picture with ids:true), 14 to 50 frames a second in a hidden pane; a whole room sweep (800 to 1,500 frames, both furnishings, both
  eyes) takes 20 to 60 s, so the cost is reading, never capturing. The PART picture (every part flat-coloured with its index + 1, no
  anti-aliasing) names the part and material of every pixel: raw construction, holes and the root-cause part list come from numbers,
  not eyes (tools/review/sweep_tools.py check / parts). Read only the machine-flagged sheets and one point per room.
- 2026-11-02 · sweep · The integrity gate's raw_surface count was 0 while the viewer showed 117,000 px of raw brick: the finish pass
  tests the as-built layer's ray tree, the viewer shows the DRAWN layer unless As built is on (and check_house_export forbids
  as_built_default). Any gate that tests one layer must test the layer the viewer shows by default, or both.
- 2026-11-02 · generator · The wall stack's footprint (hb_walls full=True) ends 10 mm short of the lined face the room sees, so
  anything fixed to the plaster from the footprint (skirting) ends 10 mm too deep; measure joinery on the built GLB. Material swaps
  made in place on a closed wall solid (hb_finish sliver path) split it and fail the integrity open_shell test: finish a solid with a
  separate skin. A skin grown 20 mm wraps onto neighbours; 4 mm closes corner hairlines.
- 2026-11-02 · viewer look (G7) · The blue interior came from a pure-blue-sky environment used as the whole fill, no ground bounce
  for downward faces, and glass casting a solid shadow (no sun inside). Fixed in the LOOK block: sun bearing 234 / elevation 25 at
  5000 K (spec afternoon), warm hemisphere and a bounce from below, env 0.28, glass casts no shadow, and eye adaptation (exposure 1.5
  with a roof overhead, 0.6 in the open) because one exposure cannot serve a sun of 9 and a room fill of 1. Mean blue-minus-red of a
  sweep is the cheap number: +0.09 before, -0.03 to -0.05 after. Not yet measured on the Quest.
- 2026-11-02 · round 1 · Three spaces swept (7,208 frames, hash-checked) and fixed at the cause: reveals (row 240, the gate had tested
  the wrong layer), thresholds, skirting, pendants; viewer LOOK block (SW afternoon sun, warm fill, eye adaptation). Blue cast gone;
  still pale and flat next to the Airbnb: the live web viewer can't do bounce/bloom/god rays, so the look is judged in Unreal.
- 2026-11-02 · references · @sorenxet's 'full office' posts: the photoreal shots are the Unreal REFERENCE scene (labelled), not the
  AI's output; the output is a grey viewport. Check labels and captions frame by frame before treating any video as a bar.
- 2026-11-02 · viewer · Marking tool presets (h31): Visual bug, Missing item, Hole in wall, Missing texture, Clipping, Wrong way round,
  Don't like item; one tap fills the note (saved as extra 'preset'); lessons.py intake tags the gate; 'Don't like item' = design change.
- 2026-11-02 · viewer perf (h33) · Quest draw calls are per INSTANCE if WEBGL_multi_draw is missing (perf note 'gl caps' now logs it): cull instances,
  not just batches. Room culling = cells (rooms+outside) + portals (openings, wall gaps and slab voids found by BVH rays, never trusted from
  openings alone: a knocked-through wall has none) + wedge test per cell; prove every change with tools/review/cull_test.js at 60 and 105 deg FOV.
- 2026-11-03 · benchmark · Codex (Astar, max) built a far better INTERIOR: GTAO contact shadow, window-daylight lights from real
  openings, finishes owned per room face at build time, one coherent furniture language, branded loader. Exterior weaker (scale).
  It burned ~180% of a ChatGPT week on over-heavy evidence (3,912 cube faces planned) and didn't finish. CODEX-COMPARISON.md.
- 2026-11-03 · assets · Codex's better interior came from a parametric furniture KIT (46 kinds in furnishings.py: sofa to toilet, oven,
  washing machine), one axis convention, exact sizes, real-metre UVs, one reviewed CC0 material set, support/seating built in, NOT
  from better downloads (it used 3 Poly Haven plants). Our 103-row library is mixed downloads; adopt the kit approach (row 301).
  Jack: its brickwork was too bright and buggy; the work stays here, but match Codex's interior quality.
- 2026-11-03 · product · Jack wants to furnish rooms himself in the viewer (desktop, phone, Quest) plus a per-room bird's-eye view;
  needs furniture placed at runtime from one shared layout file (not baked into the GLB). In PLAN.md change log; after the reset.
- 2026-11-03 · direction · Jack: take every interior thing from Codex's build plus its windows, front door, internal doors and
  outside window surrounds, its apples and grass; KEEP our brickwork, front garden layout/paving, scale and navigation.
  Codex runs it in our folder (CODEX-FURNISH-PROMPT.md, 6 staged branches).
