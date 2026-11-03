# PLAN: a full house from the architect's drawings, to the Airbnb's quality

**The anchor for the 23 Battle Road build.** Written 2 Nov 2026 from `AIRBNB-METHOD.md` (the benchmark, studied from its
primary sources) and from first principles, not from what we built before. **Re-read in full at the start of every stage,
before every fix round, after any context compaction or restart, and before reporting to Jack. Check the work against it
each time. Change it only on purpose, with a dated line in the change log at the end.** Every brief to an agent names this
file and this rule.

## 0. Goal: what done looks like
A walkable house, Before (the house today) and After (the approved scheme finished), that reads as a real, lived-in home
from every standing point, judged by the same seven things that make the Airbnb read as real (`AIRBNB-METHOD.md` §8), plus
measured accuracy from the drawings. Three outputs from one source:
1. **Unreal 5.8 on a cloud GPU**: the hero look, walkable; stills, a film, and a stream to the headset.
2. **Browser and Quest 3 (WebXR)**: the same geometry, materials and styling with the Unreal look **baked** in, 72 fps.
3. **The 2D planner**: the owner moves furniture and changes finishes before any 3D is spent; the build reloads from it.
Judged by: same-camera comparisons against the Airbnb frames; DETAIL-CHECKLIST.md with no "mid-build tell" anywhere; a
360 sweep of every space with zero faults; Jack's walk.

## 1. Principles (each one is a lesson from the method)
1. **Light makes it real.** A low warm sun with hard shadows from plants, god rays with dust, soft bounce in every corner,
   emissive switchable lamps, a warm grade. Lighting is designed in the spec, not added at the end.
2. **Real products at real sizes.** Every item of furniture and decor is a buyable product with its dimensions, materials and
   photo (the cart rule). No invented sizes, no generic shapes.
3. **Every surface has a texture at true scale**, with variation: plaster, plank, tile, weave, rattan, linen. Nothing flat,
   nothing stretched, nothing visibly tiled.
4. **Simple geometry, never wrong.** Softened edges, frames, skirting, reveals; no gap, nothing floating, nothing raw.
5. **Dress every view** to a shop's density: cushions, throw, rug, books, art, plants, vases, lamps, bedding layers.
6. **Fixed cameras, same view every version**, so progress is visible and faults can't hide.
7. **Hundreds of self-checks before the owner looks.** The machine and a cheap model look first; the owner sees a clean build.
8. **Blunt, specific feedback in short rounds** (name the object, the fault, the bar), four or five rounds, never more
   than one fix round per feedback round.
9. **Performance by profiling, not by removing beauty.** Costs move to when they're visible; resolution scales.
10. **The plan is the anchor.** Re-read it; log every mistake with its cause before fixing.

## 2. Stage 0: inputs (before anything is built)
| Input | What exactly | Done when |
|---|---|---|
| Drawings | Plans, elevations, sections, site plan, roof plan, structural calcs; the approved scheme and the as-built set | Every sheet listed with its number and date; conflicts between sheets and photos listed |
| Photos | Every room from 4 directions plus floor and ceiling; every elevation square-on; the garden; close-ups of each finish (brick, roof, floor, worktop, tiles) | A contact sheet per room; each finish has a close-up |
| Levels | Floor levels, ceiling heights, ground levels (drawings, LiDAR, the client's capture) | A levels table per room and outside |
| Style | A style board (palette, materials, mood) chosen by the owner from 3 options; the Airbnb frames as the look reference | Owner-approved board |
| Products | A list of buyable items for every room: product, retailer link, size (W×D×H), material, colour, price | One list, every item in stock, sizes filled |
| Decisions | Before/After definitions; what is kept; time of day; which rooms are hero rooms; budget caps | One questions form, answered |
Gaps become one form of questions with recommended answers. Nothing is guessed.

## 3. Stages: input → output → the check that proves it's done → tools
**S1 · Drawings to data (gates G1, G2).** Every wall (line, thickness, height), opening (size, sill, head, swing), floor and
ceiling level, stair, roof plane, external feature, read to exact numbers; photos and site measurements override the
drawings where they differ, and every override is written down. *Done:* the plan and elevations drawn back from the data
sit on the drawings within 10 mm, and on the photos' matched views. *Tools:* `tools/plan/read_drawing.py`,
`trace_drawing.py`, `draw_plan.py`, `draw_elevation.py`; the matched-view audit.

**S2 · Design spec and planner (G2b).** Per room: finishes (floor, walls, ceiling, skirting, architraves, window boards),
the product list placed (position, yaw, host surface), lighting fittings and their switches, soft furnishings, the
styling layer (what is on every surface), the hero camera, and the window treatment (sheer on every sunlit window). The
owner edits it in the 2D planner first. *Done:* a signed spec; the planner's change list is empty. *Tools:* `planner.html`,
`spec_v1.json`, `check_spec.py`.

**S3 · Shell (G5b).** Scripted in Blender from the data: walls with plastered reveals, floors, ceilings, skirting,
architraves, window boards, doors with frames, handles and hinges, stairs with strings and handrails, the roof, chimneys,
the exterior. Softened edges on every visible arris. Material slots named by finish. Every finish pass and every gate tests the
layer the viewer shows (the drawn layer by default) and the as-built layer both (CORRECTIONS-LOG 240: the gate passed the
wrong layer). *Done:* watertight; 0 clashes; no raw brick, block, timber, felt or sky inside; every reveal plastered; shell
checks pass; a walk of every room shows nothing mid-build. *Tools:* `generate_house.py`, `check_shell.py`, `check_integrity.py`, `clash_check.py`.

**S4 · Fittings, furniture, styling (G5c).** Kitchen, bathrooms, wardrobes, radiators, switches, sockets, lights, then
every product from the list at its spec size: library model, free pre-made model, or an adapted base model (stretch zones);
scratch-modelled only when nothing exists, and then with real detail (seams, piping, legs, handles). Soft things are
simulated cloth or sculpted, never boxes: cushions with corner sag, throws over arms, duvets with folds, pleated sheers.
The styling layer on every surface. *Done:* every item passes a close-up test sheet under the scene's sun; nothing floats
or clips; the room reads as dressed from each hero camera. *Tools:* `hb_items.py`, `tools/library/*`, cloth sim, BlendKit
via the live Blender, the asset library with licence flags.

**S5 · Materials.** One PBR set per finish at true scale (plank width, tile size, weave repeat), colour measured from the
owner's photos (Lab ΔE check), roughness variation, subtle plaster tone variation, emissive shades, glass with the right
reflection; textures compressed for the web (KTX2) and full for Unreal. *Done:* a material sheet per finish rendered next
to its photo; no flat colour on any visible surface. *Tools:* `make_spec_textures.py`, `check_colour.py`, Poly Haven,
ambientCG, `tools/phototex/*`.

**S6 · The outside world.** Garden, drive, path, boundaries, the neighbours' massing with photo-matched facades, the
street, trees and hedges that cast leaf shadows through the windows, sky. *Done:* every window shows a world; the matched
road view sits on the photo. *Tools:* the garden pipeline, LiDAR levels, `make_setting.py`.

**S7 · Unreal scene (G8, G8b).** Import by script; materials rebound; sun (directional) and sky with four time-of-day
presets; real-time GI; local fog volumes for god rays (set the near limit below the room size); dust particles lit only
in the beams; every fitting emissive and switchable with a look-at prompt; post process: motion blur 50 %, bloom and lens
effects, dynamic vignette, DOF optional, warm grade; hero cameras per room; the help overlay and settings menu; the planner
reload. *Done:* the look-dev booth (uncertain materials: towels, bedding, brick, glass) and hero stills judged against the
Airbnb frames before any walkthrough. *Tools:* `cloud_ue.py`, `pod_agent.py`, `prepare_ue.py`, MRQ.

**S8 · The self-check loop (G6).** In the viewer the owner will use (Unreal for the hero look, the web viewer for the web
build): a 360 sweep from a grid of points in every room, cupboard, landing, stair and outside, at 1.22 m and 1.6 m, level, up
and down, furnished and unfurnished. Frames rejected unless every direction differs and the eye is inside its space. Checked
in order: machine (material-ID pixels of raw surfaces, floating and clipping from the clash data), a cheap model on contact
sheets, the main model only on flagged frames. Then the same hero cameras every round, side by side with the last round
and with the Airbnb frame they are closest to. Fix, re-sweep, repeat until a sweep finds nothing. *Done:* a sweep with zero
faults; counts recorded. The web sweep finds faults; the LOOK is judged in Unreal (S7) and, for the web build, after the
bake (S11): the live web viewer has no bounce light, bloom or god rays, so it cannot reach the benchmark on its own. *Tools:* `house_views.py`, `shell_walk.py`, the capture harness
(fixed per CORRECTIONS-LOG 237), `lessons.py`.

**S9 · Owner rounds.** Jack walks it (headset, with the marking tool); marks and voice notes are taken in as lessons with
their root cause before fixing; one fix round; the hero sheet re-rendered on the same cameras; four or five rounds at most.
*Done:* a round with no new marks.

**S10 · Performance, per output.** Profile first. Unreal: dynamic resolution, costs moved to when they're visible,
60 fps at the stream's resolution. Web and Quest: baked light and AO, KTX2 textures, meshopt geometry, a triangle budget per
room, 72 fps measured on the headset, not estimated. *Done:* measured frame times written down for each output.
*Status 2 Nov (h33):* room visibility (portal culling, `src/house/cull.js`) is in: cells = spec rooms + outside, portals = openings + wall gaps + slab voids found by ray, per-instance wedge test, empty batches skipped. Proof harness `tools/review/cull_test.js` (culling off vs on, same cameras, pixel diff). 72 fps still needs fewer draw calls (static merge per room) and baked light; see the h33 report.

**S11 · Web and Quest build.** The same scene with the Unreal look baked (light maps and AO from the cloud), the
Before/After, Furnished/Unfurnished, time-of-day and lamp switches where the budget allows, the planner reload. *Done:*
the same hero cameras in the web viewer sit next to the Unreal stills and read the same.

**S12 · Deliver and learn.** Stills, film, the streamed walkthrough, the web link, the planner. Every mistake of the build is
in the corrections log with its rule and check; FIRST-PASS.md regenerated; this plan's change log closed.

## 4. Order of work for 23 Battle Road (what starts first)
1. Stage 0 inputs sheet and the product list (the gap we have: a real buyable product for every item, with sizes).
2. Three spaces first, end to end through S3–S8, so the look is proven before the whole house is dressed (Jack, 2 Nov):
   **the new kitchen-diner (After), the front garden, the lounge**. Then Jack checks the output and decides the next step.
3. Unreal look-dev (S7 booth and hero stills) as soon as the three hero rooms pass S8 in the web viewer.
4. Only then the full house in Unreal, the bake, and the Quest build.

## 5. Budget and cost
- **Cloud GPU: £10 total for this house (Jack, 2 Nov).** So Unreal is used for look-dev and hero stills of the three
  spaces only (S7 booth + stills in one session), and the self-check loop (S8) runs in the web viewer, which costs nothing.
  Sessions carry a hard cap and the salvage watchdog; the project and shader cache are reused between sessions.
- **Claude usage.** The sweep is machine-checked first and read by a cheap model; the main model looks only at flagged
  frames and the hero sheets. Agents get briefs with this plan, not transcripts. One judge round and one fix round per stage.
- **Jack's time.** Stage 0 answers once; then four or five walks of 20–30 minutes.

## 5b. Which Claude model at each stage (Jack, 2 Nov: "tell me what model is needed at whatever stage")
Jack sets the session's model; the session hands the mechanical work to cheaper models as agents. The all-models weekly
allowance is what binds (Max 5x), so the top model is for judgement and the cheap ones for volume.
| Stage | Session model | Agents it uses | Why |
|---|---|---|---|
| Plan, spec sign-off, judging the look against the benchmark, decisions | **Fable 5.1** | none | the costliest mistakes are made here; a few turns, a few images |
| S1 drawings to data, S2 spec | **Opus 5.5** | Sonnet to verify numbers | reading drawings needs vision and judgement; an error here costs every later stage |
| S3 shell, S4 furniture, S6 outside, S7 Unreal scripts, S10 performance, fixing root causes | **Opus 5.5** | Sonnet for regeneration, checks, fetching and test sheets; Haiku for copies, hashes, counts | code with judgement at the top; loops at the bottom |
| S5 materials | Opus 5.5 | Sonnet to apply and measure | the judge of a material sheet against a photo is the session, on one image |
| S8 self-check loop, S11 bake and publish, S12 deliver, reports from data | **Sonnet 5.5** | Haiku for the machine passes | volume work; the session (Opus or Fable) looks only at flagged frames and the hero sheets |
| S9 owner rounds: taking in marks, fixing | Opus 5.5 | Sonnet to re-sweep | root causes need judgement; the re-check is mechanical |
Rule of thumb: Fable for the plan and the verdicts, Opus to build and fix, Sonnet to run and read, Haiku to count. Never
run a loop on Fable or Opus that a Sonnet agent could run.

## 6. Risks and how each is handled
- The Quest can't run the live look → S11 bakes it; KTX2 and meshopt; a triangle budget; measured on the headset.
- The 8 GB Mac → Blender headless only, one job at a time; Unreal and bakes only on the cloud.
- Cloth and foliage are heavy → simulated once, cached as meshes; foliage as cards for the web, meshes for Unreal.
- A whole house is ten rooms, not one → hero rooms first; the sweep is automated, not hand-driven.
- Captures that silently fail (row 237) → hash-checked before any review.
- Generic furniture → the product list rule; a close-up test sheet per item before placement.
- Blue-grey, flat light in the web viewer (FAULTS V-02) → the sun, sky and grade are designed in S2 and verified in S8 in the
  viewer itself, not only in Blender.

## 7. Decisions for Jack (asked once, with recommended answers)
All answered by Jack on 2 Nov 2026 (form):
1. **Go ahead with the plan:** yes.
2. **Unreal cloud money:** keep to £10 for this house (stills only; the checking loop runs in the web viewer).
3. **Furniture:** available assets (the library and free models) for this first test; the real buyable product list comes
   later. The product rule (§1.2) applies from the next round, not this one.
4. **Time of day and lamps:** yes: morning, afternoon, sunset, night, and a switch on every lamp, in Unreal; in the web build
   where the Quest budget allows (afternoon baked first; the other presets only if they stay smooth).
5. **First spaces:** the new kitchen-diner (After), the front garden, the lounge; then Jack checks the output and decides.
6. **Claude plan:** Max 5x. **Price per house:** about £800, plus £200 for the VR walkthrough version.

## Change log
- 2026-11-02 · Written from AIRBNB-METHOD.md after the furnished build reached Jack with faults everywhere. Supersedes the
  implicit plan (spec + gates) as the anchor; the spec and gates remain the checks inside it.
- 2026-11-02 · Jack set the first three spaces: new kitchen-diner, front garden, lounge; then he checks the output before
  anything else is dressed. §4 and §7 updated. Plan otherwise unchanged (he is gauging viability, not changing it).
- 2026-11-02 · Jack's form answers written in (§5, §7): go ahead; £10 Unreal cap (stills only, loop in the web viewer);
  available assets for this test, product list later; time-of-day presets and lamp switches yes; Max 5x; £800 + £200 VR.
- 2026-11-02 · §5b added: which model at each stage (Jack asked). Stage 0 inputs sheet written: renders/plan/INPUTS.md.
- 2026-11-02 · Round 1 (three spaces) done: S3 now says gates test the layer the viewer shows (row 240); S8 says the web sweep
  finds faults and the look is judged in Unreal, then after the bake. Round-1 report: renders/house-build/first-build/round-1/.
- 2026-11-02 · From @sorenxet's office posts (BENCHMARKS.md): S4 dresses one zone at a time and spends detail where the hero
  cameras look; S9 fix rounds take one named fix per instruction. Their photoreal footage was the reference scene, not output.
- 2026-11-03 · Round 2 (Jack's walk 2, 48 marks + door hardware): skins only where a room is on the face's normal side (outside faces and buried seams never skinned); everything fixed to a door leaf carries the leaf's hinge extras; internal door leaves are oak (SIGNOFF.md); border blocks grey and flush; log burner, open blind, oatmeal dining chairs, sage-and-sand print; candleholders, SIT-PLANT, LIV-PLANT-1 and the porch CCTV removed. Open: garden path width, paving gaps, shed front, eaves/wing-roof/porch-roof items, plant textures, steel boxing and floor/skirting junctions. After frames: renders/house-build/first-build/round-2/AFTER-SHEET.jpg.
- 2026-11-03 · Codex's independent build studied (CODEX-COMPARISON.md). Adopted: GTAO on desktop + baked AO on the Quest, window
  daylight lights per room, finishes assigned per room face at build time (not detected afterwards), one design language per
  house with real proportions, oak plank/photo palette generators, exterior life details, a branded loading screen and room
  title card, portal/shadow visibility and KTX2 from the start. Kept ours: navigation, measured scale, proportionate checks.
- 2026-11-03 · Jack: furnish it himself inside the viewer. Added as a requirement for S4/S11 (after the usage reset, with the kit):
  furniture is NOT baked into the house model; each kit item is its own small model placed at runtime from a layout file
  (spec + the planner's change list), so the viewer, the planner and the headset share one layout. In the viewer (desktop,
  phone, Quest): an Edit mode with a catalogue (wrist panel in VR), add an item, drag it with the mouse or controller ray
  along the floor or wall, rotate with the stick or Q/E, snap to walls and other items, delete; contact and collision checked
  as it moves. A per-room bird's-eye view (top-down, the room's plan) for laying out by drag; switching back to the walk
  shows the same layout. Saves to the change list on the Mac; the next build bakes it in.
