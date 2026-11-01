# Judge: homeowner in the Quest and on a phone — 23 Battle Road model (1 Nov 2026)

Read-only review of renders/house-build/{viewer,look}, Jack's front-garden photos (20260719_102925.jpg is the clearest),
BENCHMARKS.md, src/house/{modes,board,walk,viewer,model}.js. Nothing was run, so headset behaviour is read from code, not felt.

## Verdict
A clean, accurate-looking massing model with believable brick scale and an excellent stage idea. It does NOT yet look like
Jack's house or like the Airbnb/SE Landscapes bar. It reads as "architect's SketchUp render", which is what Jack objected to
in the test house. Realism is the biggest gap; the stage story is the biggest strength.

## Faults, worst first
1. **The setting is empty and fake.** Flat saturated-green plane to a hard horizon, no apple tree, no gravel drive, no car,
   no hedge, shrubs, neighbours, wires or road. Jack's own photo is full of life and warm gold gravel; the model is a house
   on a billiard table. In a headset that is what you look at most. Fix: dress the plot from the photos (tree, gravel drive with
   edging, hedge, neighbour houses on the horizon, desaturated lawn).
2. **Roof is the wrong colour and material.** Model: beige-pink, soft, shingle-like. Real: dark orange-brown clay plain tiles
   with visible courses and ridge tiles. It is the largest surface in every exterior view and it makes the house look
   different from the one Jack lives in. Fix: sample the real tile from frames4k and rebuild at true course spacing.
3. **First 60 seconds in the headset are not a reveal.** Customer start = "Front path" (4.3, -0.25, 4.5), stage 12, walking. The
   customer screenshot at that spot shows a close wall and eaves, no front door, no whole house. Nobody sees "my house + the new
   extension" as an establishing view; the extension is at the back, out of sight, so the first impression is the old front.
   Fix: spawn at the end of the path looking at the whole front, then offer "Go to garden" as the second beat, with a short
   spoken/board caption saying what to do.
4. **Customer mode leaks builder language.** Footer in every customer screenshot: "W A S D · Shift faster · [ ] stages · X x-ray
   · V walk · trigger picks · A/B stages · X pins the board" and "catslide, kitchen-diner, utility, cloaks … (BDS 4915.2B / 3A /
   4A, 27 Oct 2022)". Clicked part card shows "G-front · wall_lining · existing". Stage names like "Slab: hardcore, mesh, concrete,
   DPM, insulation", "Walls to plate", "Felt, battens" are trade terms (the explanatory sentence under each is good, the title is
   not). Fix: hide ids and drawing refs in customer mode; plain titles ("The floor is laid", "The upstairs walls go up").
5. **On a phone the UI covers ~60% of the picture.** The stage list takes the left third, the bottom panel the base, the top bar
   the head. The model is a postage stamp. Fix: collapse the list to a stage chip + slider, auto-hide the rest.
6. **Brick: right scale, wrong colour and pattern.** Bricks are the correct size (about 35 px each at 3.5 m on screen), but the colour
   is cold pink-purple against the real warm orange-red with darker headers; mortar is too pale and high-contrast; big flat
   walls show no variation, no cills, no soldier courses, no weathering. Windows are flat white boxes with featureless blue-grey
   glass; the real ones are white uPVC with fanlights and a visible cill.
7. **Fences are an unlikely grey slab with orange posts.** Looks blue-grey concrete (and wrong against the horizontal-slat
   fencing in the neighbour's plot in Jack's photo and the SE Landscapes benchmark).
8. **Light is flat.** The sun is at the filmed azimuth but the look renders are dull and overcast-grey in the sky, no bounce, no
   haze, no warm grade. Jack's photos are hard blue-sky sunshine. The Quest build has a 1024 shadow map for the whole plot, so shadows
   will be soft and low-res; contact shadows under eaves matter most and will be missing.
9. **Interiors are barely evidenced.** The only interior I can see is a grey tiled floor and bare walls at stage 7; no finished
   room render exists in the folder. Stage 12 says "plastered walls, bathroom fittings" but I could not see furniture, skirting,
   light fittings, kitchen. A homeowner will walk into empty boxes. Unverified: I did not find finished-interior images.

## First 60 seconds in the headset (from code)
- Spawn position and yaw are authored (Front path / Front door / Garden / Hall / Landing); VR start uses the mode's spawn.
  Local-floor, eye height from real head, good. Scale is 1:1, correct.
- Load: no VR-specific progress; the loading overlay is a DOM element that is invisible inside the headset, and the EXR sky (a
  2k float EXR + PMREM) is generated on the Quest on load. Expect a multi-second freeze or black wait after "Enter VR". Fix: bake the
  PMREM to a small KTX2/HDR cube offline; show a loading card in-headset.
- Comfort: customer = teleport + 30-degree snap turn + vignette + fade, seated option. That is the right choice for a first-timer.
  Fine. But teleport only lands on surfaces facing up and within 25 m; stairs are walked by stick, a risk for sickness.
- Board: 0.24 x 0.34 m at the left wrist, raise to show, laser or gaze to press. Spec says body text is >=30 px, but in the
  vr_board capture most lines are ~24 px and the regs block is a wall of small grey text. About 1 degree of visual angle:
  just readable, tiring over time. Customer tabs (About/Build/Plans/Notes/Tools) are fine but "Plans", "Tools" will be unclear.
  A first-time user is told nothing about "turn your left wrist up" until after entering; that hint is footer text on a flat page.

## Quest risks
- Draw calls: BatchedMesh, ~45 batches, good. But 1254 instances per version are culled and sorted per instance, per eye, on a mobile
  CPU. Measure it. Stage changes toggling visibility are cheap, but moving the whole thing to a batch update on every stage tick
  may hitch.
- Textures: decoded full-size then shrunk to 512 on the Quest (peak memory spike during load, with ~120 WebP images). Settled
  memory is fine (~170 MB), but 512 px on a 4 m brick tile means the brick will look soft and smeared at arm's length. KTX2 is the real
  fix (already noted).
- Anisotropy 8 and PCF shadows on every frame the stage moves; keep fixed foveation at 0.5 or higher, but check 72 vs 90 Hz.
- 4 versions at 7-16 MB each and only a 16 MB model downloaded over Wi-Fi from a Mac: fine locally, slow on a client's connection.

## Scores (0-10; the single biggest fix)
| Area | Score | Biggest fix |
|---|---|---|
| Brick | 5 | Warmer sampled colour, headers, cills, mortar value down |
| Roof | 3 | Real clay-tile colour and course lines |
| Windows | 4 | uPVC frames, fanlights, reveals, believable glass |
| Ground / lawn | 2 | Photo-based gravel, path, tree, lawn texture |
| Fences / boundaries | 3 | Match the real fence types |
| Sky and light | 4 | Warm high-key sun, bounce, haze, contact shadows |
| Interiors | 3 | Furnished, lit finished rooms (unverified) |
| Stage explanations | 7 | Strip builder jargon from titles and footers |
| Headset first minute | 5 | Establishing spawn + in-headset load and tutorial card |
| Quest performance | 6 | Measure instance culling; KTX2 and a pre-baked sky |

Against the benchmarks: Airbnb (lighting carries it) ~3/10; SE Landscapes (planting, atmosphere) ~1/10 for the garden.

## What works
- Stage-by-stage build with a plain-English sentence per stage, scrubber, play, and "Lift the roof" / "See inside" is the clearest
  non-builder explanation I have seen and is a real selling point.
- True-scale walking with sensible collision, a handful of named spawn points, teleport + snap turn + vignette + seated option.
- Geometry is accurate and clean: correct massing, hips, catslide, chimney, scaffold, steel and props at the right stages.
- Batched draw calls and low triangle counts (22k-81k) give the Quest real headroom to spend on look.
- Honest "Not built" label on the scheme.
