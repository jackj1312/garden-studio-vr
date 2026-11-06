# Detail checklist — the things that make a model read as real

Jack, 31 Oct 2026: "these are all the sort of details we need to look for in new projects too because its the
details that matter most." Every project checks every line at G3 (inventory) and again at G6 (matched views).
Each line came from a mistake on Jack's garden (CORRECTIONS-LOG row in brackets). Add a line whenever a new
detail is found. New lines from review findings are added by tools/review/lessons.py at the end, each tagged with its log row.

## Edges, kerbs and junctions
- Each kerb is a **run as it was laid**: its unit (setts, roll-top, timber, steel), rows, flush or **upstand**
  (height), and whether it is straight or curved (24, 43, 47).
- **How each run meets the next**: continuous, butt, mitre, a sweep into a straight, or an upstand that **dives
  down** to meet flush edging (47).
- Curves are smooth with no kinks; straights are straight; true corners only where kerbs meet at an angle (5, 34, 46).
- Where two areas share a kerb, it is one kerb, not two lines (46).
- **Every edging run is its own item, drawn full length** from where it starts to where it really stops (path
  edging to the street; a paving border on to the fence), even across stretches hidden by a car (48).

- **Trace the whole perimeter of every paved area**: what border it has (colour, rows), where it turns, and that a
  kerb shared with a lawn is the same run (50). Runs that continue are one straight or one curve, never a kink (49).
- Fence and wall lines: is there an edging or gravel board along their whole length (50)?

## Levels
- Every step and threshold, with riser height and nosing (44).
- Upstands, raised beds, edges proud of the lawn or gravel (43).
- Loose surfaces have depth: gravel sits up against its kerbs (33).

## Surfaces
- Each paved area separately: unit sizes, bond (stretcher, herringbone, random three-size), laying direction,
  joint colour, colour mix (32).
- Lawn: blade length, mowing stripes, leaf litter, worn patches, colour from the close-up (39).
- Beds: mulch, bark, soil, every plant (42); include **beds against the house** (41).

## Boundaries
- Every boundary runs its **full length**; check both ends and every gap (path, drive) (35).
- Fences as their parts: boards, gaps, posts, rails, cap, gravel board (38).
- Hedges: species mix, clipped or loose, height, top shape (10, 35).

## The house
- Each element is what it **is** (a mirror is not a window) (22).
- Windows: frame colour and profile, panes, recess, sill, surround, lintel, soldier course (25).
- Roofs: form in two views (lean-to, hip, verge), pitch, eaves and verge details, flashing (21).
- Fascia, soffit and gutter colours per element (porch differs from house) (29).
- Wall thicknesses grow inwards from the scanned outer face (28).
- Fixtures: number plaque, lights, cameras, meter box, dish, downpipes (30).

## Neighbours and context
- Neighbours modelled from their own photos: their brick, windows, porch, garden. Never mirrored or copied (23, 40).
- Street: pavement, verge, kerb, any brick strips, road, opposite houses as seen.

## Objects and trees
- Every object to its real shape: bins (wheels, lids, handles, number), benches, pots, planters, ornaments (37).
- Trees to the real tree: trunk height and splits, limb count, holes and scars, crown spread and shape (36).
- Movable items tagged for the clean build.

## From Jack's headset marks, 1 Nov 2026 (check on every project)
- Hedges and shrubs run all the way to the walls they meet (no gap between a bush and the house).
- No surface overlaps another: soil or mulch must never poke through paving or edging (z-fighting, overlaps).
- Every structure has its roof (sheds, porches, outbuildings) and its trims: bargeboards, soffits, fascias.
- Every bed exists, including small ones beside paving; nothing planted is missing.
- Neighbouring brick matches what is really there (if it is the same brick as the client's, use the client's).
- No clipping: timber, posts and beams never pass through each other or through walls.
- Edging blocks match the paving they border (same family, different colour where real) and are laid coherently.
- Upstands match the border they continue (same unit), raised.
- Photo-textured objects (doors, shed fronts) need real geometry under the photo, so they hold up in Unreal light.
- Loose clutter in photos (a broom handle) belongs to the "today" build only, modelled, not painted into a texture.

## From the matched-view audit 2, 1 Nov 2026 (check on every project)
- Every plan outline says what it IS: the soil edge, or the outer edge of its border; borders lie on the side the
  orthophoto shows (CORRECTIONS-LOG 66).
- Ground surfaces never stack: paving, gravel and lawn are cut round beds and each other; soil sits below its edging (65).
- Junctions between edging runs: one butts into the other, no sett passes through another; edgings stop at walls and
  are cut round posts (67).
- Timber: post, beam and rafter sections measured on close frames; heights from 3D points or probe lines (68).
- Anything standing beside the house (pergola, shed, posts) clears the eaves, gutters, downpipes and walls (68).
- Every trim follows the line it finishes (a sloped roof has a sloped fascia) (69).
- Hedges and beds at the foot of every wall and boundary, both ends confirmed in photos (70).
- No single-sided visible parts (soffits, boards, tiles, wheels): closed solids only; the open-parts check reads 0 (71).
- Boundary heights (fences, walls, hedges) probed on 3 frames (74).
- A neighbour's material differs from the client's only if the same frame, in the same light, shows it (73).
- Movable things in the photos (benches, pots, bikes, brooms) are modelled for the today build, located by ground rays.

## From the matched-view audit 3, 1 Nov 2026 (check on every project)
- Hedges: base footprint probed on the ground (both faces and the front) and the top probed along the length; clipped
  blocks are built as flat-faced blocks with crisp tops, loose growth and leaders as they are; a hedge has its own bed and
  border where the photos show one (CORRECTIONS-LOG 84).
- Every tiling texture wraps: tile it 2x2 and look at the seams before use; dark lines repeating at the tile size in a
  render are a seam, not a shadow (85).
- Mortar colour sampled (sunlit, low-saturation pixels), never typed (86).
- Each window on its own: number of lights, surround width (probe 5/7/9 cm), head type (stone head, steel lintel, packer
  strip), sill type (stone, flush band), surround colour (87).
- A mirror must show the garden (a baked reflection from its own position) and its bars counted (88).
- Every object's SIZE measured (two-view triangulation of its ends, height probes), not only its position (89).
- Printed things read as printed: house plaques, bin numbers and stickers as decals with the text the close-up shows
  (black or white numerals as photographed) (90, 91).
- Sweep each wall end to end, including behind posts and in beds: panels, bird tables, lights (92).
- Fixture colours (a white floodlight) and roof-edge heights read at the edge itself (93).
- Ground levels: is a paved area flat or falling? 3D points of the ground in 0.5 m bands (94).
- Collision is generated with the model (site.json newer than model.glb), curved beds as polygons; the start point is
  near the entrance (80, 95).
- Closed parts face outwards (signed volume > 0): the viewer draws front faces only (inside-out check in the build).

## From the matched-view audit 4, 1 Nov 2026 (check on every project)
- Window heads: what each one really is, from its close-up AND a frame (concrete head, lead or zinc flashing strip, packer, steel
  lintel); a thin flashing is not a lintel. The client's word on what a part is wins (CORRECTIONS-LOG 105).
- Soldier courses: the house's own bricks on end, each unit cut from the course's own close-up, the same brick as the wall
  around them (never flat tone bands) (105).
- Verge foot / box end: bargeboard depth and the box end (depth back to the wall, bottom height) probed; no wall face shows
  above a soffit line anywhere round a porch or bay (109).
- Every element that abuts the house (shed, porch walls, lean-to roofs, fences to sheds, hedges to walls) touches it: listed
  in the build's MUST_TOUCH and the must-touch check reads 0 gaps (106).
- Wall lines (party line, bay sides, flank) from the architect's drawings registered on two walls and checked against 3D-point
  face peaks and arris probes; > 5 cm conflicts listed for the client (110).
- A straightened photo used as a surface carries only that surface (no wall or sky past its edge) (111).
- Bed corners and inside borders: no soil showing between border and paving or gravel, corners included (the 'soil past its
  border' check reads 0) (107, 112).
- Raised edging that dives to meet flush edging eases down over the whole length the client marks (107).
- Chimney: count the pots (and cowls, aerials) on a 4K crop.


## Interior finish: "it needs to feel like a finished house" (Jack, 1 Nov 2026; check on every project)
"Internal doors need to look real… even down to skirtings, architraves and window boards, these are the details that matter most."
- [ ] Internal doors are real panel/shaker doors: lining and stops, 3 hinges, lever on rose with latch, ~3 mm gaps, swing correct.
- [ ] Architraves on both faces of every opening (moulded profile, mitred corners); loft hatch trimmed.
- [ ] Skirting in every room (moulded, ~145-170 mm, mitred, returned at architraves, painted); tile skirting in wet rooms per spec.
- [ ] Window boards on every window (~25 mm, bullnose, 20-30 mm projection, notched round reveals); crisp plastered reveals.
- [ ] Switches (~1.2 m) and sockets (450 mm) at UK heights; radiators under windows with valves and pipes; smoke alarms.
- [ ] Ceiling lights, curtain poles/blinds, door stops, stair balustrade and handrail as real joinery.
- [ ] Walls meet ceilings and floors cleanly: no gaps, no floating trim, no exposed raw edges.
- [ ] Scripted furniture passes its close-up test against a real product before placement (CORRECTIONS-LOG 183).
- [ ] Lived-in layer in every room (Jack, 1 Nov): fruit in the bowl, reed diffusers, candles, books, throws, towels, kitchen
      counter items, keys dish, plants; tidy and homely, no toys or mess; every prop on its surface (validator: no overlap,
      no float > 1 cm).

## SHELL READY (G5b, Jack 1 Nov 2026): the bare house before any furniture
- [ ] Rooms match the drawn outlines; chimney breasts, piers, bays, nibs and the stair void as drawn (never two loose pillars).
- [ ] Ceilings in every room at the drawn height (sloped under roofs); no voids, no sky.
- [ ] Every door opens fully into a room or outside; no wall or solid behind or in the swing.
- [ ] Every window: glass, frame colour, plastered reveals (no brick showing), head, window board.
- [ ] The semi joins its neighbour: continuous party wall, roofs meeting, nothing through the roof.
- [ ] Finishes everywhere, skirting and architraves; no raw construction material visible.
- [ ] Setting unbroken (hedges, fences, paving continuous as in the photos).
- [ ] Walk inspection frames per room, Before and After, each passed in writing.

## "Still mid-build" tells: none may show in a finished house (Jack, 1 Nov 2026)
Walls and ceilings: bare brick/block/stud, plasterboard joints, unpainted plaster, missing or open ceilings, visible joists,
rafters or deck undersides, gaps where walls meet ceilings or floors, raw corners (no beads).
Structure: bare steels or timber beams, padstones, lintels or wall plates visible from rooms.
Openings: brick in reveals, no window boards, no heads, doorways without doors, linings or architraves; doors with no
handles, gaps or swings into walls; holes with no frame.
Floors: bare screed, chipboard or joists; no thresholds between rooms; no skirting; unfinished stair treads, no balustrade.
Services: wires or pipes showing, no switches, sockets, light fittings (bare bulbs), radiators, valves, smoke alarms.
Kitchen and bathrooms: carcasses without doors or worktops, no taps, no tiles or splashbacks, no sealant lines.
Outside: open eaves, no gutters or downpipes, scaffold marks, rubble, bare ground, unfinished paving edges.
Feel: everything flat and identical, no wear or variation, no light fittings on, empty rooms.
Finished = every surface finished and edged (beads, skirting, architraves, window boards, sealant), every opening framed
and dressed, services finished at the wall, kitchen and bathrooms complete, lights on, outside closed and tidy, a lived-in
layer (soft furnishings, books, plants, fruit) and slight natural variation and wear.
- [ ] Soft items are never boxes (Jack, 1 Nov: "the towels have no texture, they are just bricks"): towels, throws, bedding,
      cushions and curtains get real shape from Blender cloth simulation (draped over the rail, folded, plumped) or a
      scanned/library model, and a fabric material with weave normal, sheen and roughness variation (terry for towels);
      in Unreal the cloth shading model adds the soft sheen. Each passes the close-up test sheet before placement.

## Learned from review findings (tools/review/lessons.py; check on every project)
- Unfurnished toast count equals the number of distinct loose items (row 197)
- Look up at the underside of every stair flight from the hall and the under-stair cupboard: a plastered soffit, never stepped blocks (row 199)
- From inside every room under a two-storey part, no roof surface below the ceiling (row 201)
- Conservatory (and any bare-by-spec room): its walls read as their spec material, no plaster patches (row 202)
- Look into the under-stair cupboard at floor level: floor finish all the way under the stair (row 203)
- Front and rear facades from the road and garden: brick and render only, no white plaster patches (row 205)
- Look along every new ceiling at a low angle: flat board, no ribs (row 206)
- Every joist field's z_bottom equals the top of the ceiling lining under it (row 207)
- After any finish change, re-run an upward ray sweep over each storey's rooms (row 209)
- Ceilings and painted walls read flat at 2-4 m; no stripes (row 211)
- From the landing and inside bedroom 3 (After): no rafter, joist or plate shows below or through the ceiling (row 213)
- Where two ceilings of different heights meet: a clean boxed step, no member ends or lines (row 214)
- Every Go-to place opens looking into the room it names, not at a wall or door edge (row 235)
- A viewer fault sheet for every room exists and every item on it is fixed or accepted by Jack before the build is shown (row 236)
- Review captures: every direction differs and every eye point is inside its room, checked before review (row 237)
- PLAN.md exists, was shown to Jack, and is re-read at every stage (the brief for each stage names it) (row 238)
- Questions form: each question is one plain-words decision with its consequence and a recommendation (row 239)
- Part-ID sweep of each room (sweep_tools.py check): zero raw-material pixels from any standing point, in the layer the viewer shows by default (row 240)
- From each wall base in the sweep a skirting edge is visible (18 mm proud, 150 mm high), checked on the built GLB (row 242)
- Sweep mean blue-minus-red indoors at or below +0.03 and the ceiling reads warm white in the up frames (row 244)
- No frame of the sweep has more than 8 percent near-black pixels (row 245)
- Every framed print in the sweep shows a print inside its frame (row 246)
- Open every door: nothing fixed to the leaf is left behind (row 297)
- Lounge close-up: the stove reads as a log burner with logs behind glass and a flue (row 251)
- SIGNOFF.md dated decision; item gone from spec_v1 and the furnishing plan (row 254)
- SIGNOFF.md dated decision; KA-DEC-10 gone from spec_v1 (row 262)
- SIGNOFF.md dated decision; no AB-X-porch-cctv in the GLB (row 294)
- Lounge: both prints show artwork (row 257)
- Kitchen rear window clear below a stacked blind (row 265)
- check_spec: leaf material oak; SIGNOFF.md decision (row 271)
- Hall, landing and stair clear widths match a tape measurement on site within 20 mm (row 298)
- Lounge shelf close-up: frame face and book spines toward the room (row 249)
- Lounge shelf close-up: frame face and book spines toward the room (row 250)
- SIGNOFF.md; LIV-PLANT-1 gone (row 252)
- Front garden: border blocks grey, same block as the path, flush with it (row 287)
- house-wip only ever changes through the gated publish script (row 300)
- Every placed item: front faces the room, base touches its host surface within 5 mm, no penetration, built to its catalogue size (row 301)
- The three hero frames are rendered without saved mark ribbons. (row 303)
- Exercise signed living-room lamp and bowl moves and save validation. (row 470)
- Select two distinct faces and compare photo texture output for carpet and concrete. (row 471)
- Minimise both panels, move camera and restore editing. (row 472)
- Move a bowl and compare stationary batch matrices and geometry versions. (row 473)
- Measure individual and grouped first-use switches in the furnished lounge. (row 474)
- Click two distinct wall spans in the client room planner. (row 475)
- Actual baked material has all three inputs, correct scale and metre UVs; use matched lit detail views. (row 476)
- Minimise and verify mouse look turns in the real in-app browser after native capture is refused. (row 477)
- Switch using the toolbar, inspect the same fixtures from the garden and connecting room, and measure on/off frame intervals. (row 478)
- Go from furniture into garden and return in the same version without losing an unsaved edit. (row 479)
- Cross the measured exterior/room threshold and inspect actual aperture persistence. (row 480)
- Inspect the colour, normal and roughness material strip. (row 481)
- Matched pixels, doorway visibility and measured moving-frame intervals in the Wi-Fi preview. (row 482)
- Measure coplanar triangle intersections in the issued and candidate floors. (row 483)
- Verify fixing targets against each joist and rafter, reject a neighbouring rafter, and rerun the staged clash report. (row 484)
- Compare matched real scene detail while moving and after settling, including after the moving budget steps down. (row 485)
- At three stations verify matched finish height, no raised skirting and no overlapping top triangles. (row 255)
- At three stations verify matched finish height, no raised skirting and no overlapping top triangles. (row 256)
- Check exported pavement bounds against the setting generation rectangle and run the stacked-ground check. (row 486)
- Re-export and run visibility, integrity, shell, stacked ground and walk checks against those same files. (row 487)
- Require both surveyed walls, compare their finished span to the trace, and report any intervening part and its clearance. (row 488)
- Report both widths and both first-hit names. Any obstruction except the actual stair soffit still fails the wall-width check. (row 489)
- Verify the perpendicular board stops at both frame jamb edges, the timber bears on its jack and the export reports no unintended overlaps. (row 490)
- The adjacent hall reveal and painted wing wall must share no outward triangle area. (row 491)
- The bedroom-door gap and collision checks must both pass on the same exported geometry. (row 492)
- Capture the same landing view with no hovered part and compare its signed ceiling material. (row 493)
- Require a unique basis with sub-centimetre imported-bounds error. Preserve imported assets and the first checkpoint when restarting the camera stage. (row 494)
- The four recorded landing pixels first hit the finished enclosure, with no changed structural member. (row 495)
- Matched garden frame and close crops show correct timber and foliage colour, grass silhouette, gravel relief and paving detail (row 496)
- Report requires nonzero material rebinding and zero failed colour connections (row 497)
- Before rendering assert house mesh count, lighting and material replacement count; inspect downloaded frame (row 498)
- Browser vertical FOV equals 2 atan(tan(horizontal FOV / 2) / aspect) (row 499)
- Player reports 10 seconds, seek to 8.5 succeeds and playback time advances (row 500)
- Hallway first frame sees through the open living-room doorway (row 501)
- Alcove top has one surface owner; cupboard and shelf junction geometry checked and close-up inspected (row 502)
- Staged glTF dependencies resolve and lesson command succeeds (row 503)
- Presentation lamp top is below the first shelf underside (row 504)
- Rendered paving receives displacement through an engine-supported material input (row 505)
- No Nanite translucent-material warnings in the accepted render and windows visually reflect/transmit (row 506)
- Garden shadow detail and natural foliage colour remain visible in the hero frame (row 507)
- Fresh revision imports preserve roof tiles and all source material bindings in rendered frames (row 508)
- enable_volumetric_fog is true and light shafts are visible at real openings (row 509)
- Leaf slots use the leaf material and render green with alpha and transmission (row 510)
- House-side shrubs have natural, dense leaf coverage without changing their footprints (row 511)
- Close-up has natural stone detail and relief without pyramid repetition (row 512)
- Flames and vapour rise vertically from their source in the interior frame and film (row 513)
- Gravel reads as roughly 20–30 mm stones; the unchanged kerb reads as concrete, not tiny tiles (row 514)
- New candle base at 0.924 m and footprint inside the window board; flame attached above its body (row 515)
- Updated gravel parameters reach all gravel slots and render at the intended scale (row 516)
- Interior still render completes with flame and steam materials compiled (row 517)
- Lounge and alcove close-up show front-facing joinery, clear camera and warm fire without green artifacts (row 518)
- Changed alcove transform changes source hash, cabinet faces room, and fire/candle/steam close-ups read correctly (row 519)
- Film inventory is contiguous 0000 through 0575 and encoded duration is 24 seconds (row 520)
- Window flame rises from the wick and fire has continuous non-repeating tongues; steam rises from lid (row 521)
- Effects have zero pitch and roll, with yaw only; candle and stove flames remain upright from multiple camera angles (row 522)
- Fire has varied moving density with no row of identical silhouettes (row 523)
- Atlas alpha background is zero; fire close-up contains no card rectangle (row 524)
- Fire is attached to logs, has rising varied tips and no rectangular card edge (row 525)
- Final lounge and film have no green optical ghost beside the stove (row 526)
- Final inventory and encoder use .jpeg and verify frames 0000 through 0575 (row 527)
- Desktop playback reaches 24 seconds; seeking and phone player load pass (row 528)
- The immutable LAN review URL and its media return 200 without altering the house current-preview pointer (row 529)
- Switch every view pair and retain selected footprint and history (row 530)
- Inspect header at desktop and phone widths (row 531)
- Vehicle regression tests (row 532)
