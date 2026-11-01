# Judge: UK extension builder / site manager, 1 Nov 2026
Subject: approved_2b build sequence, 23 Battle Road (BDS 4915.2B/3A/4A). Read-only review of the look renders, viewer screenshots, CHECK.md, `approved_2b.json`, `approved_2b_elements.json`, regs.json and the 3A notes.

**Verdict:** A builder would recognise the 12-step skeleton as the right order of works, but would stop trusting it at stage 6 and again at stage 12. The big items are an unbuildable wall/steel order, slab before substructure, no access or weather protection when needed, and detail that exists only as text.

## Faults, worst first

1. **Wall built over the bi-fold opening before the steel that carries it.**
   - Where: elements `G-extRear~1` (top 4.36 m, raking) and `G-extRear~2` (to 2.6755) are `stage_in` 6. `B-beam-5` and its padstones are stage 7, and `G-extRear~2` lists `B-beam-5` in `bears_on`. Seen in `look/persp_rear_r_s6.png`: the rear wall stands full height over an opening with no beam.
   - Why it matters: you cannot lay brick and block over a 3.4 m opening and put the steel in afterwards. The stage-7 note ("brickwork over beam 5 completed") contradicts the model. A 4.3 m free-standing 102 mm leaf with no floor or plate restraint for stages 6–8 is also a collapse risk. The stage-9 note says "catslide wall to its plate" but the model builds it at 6.
   - Fix: pad, beam 5 and beam 4 first (move the steels to the start of stage 6, or split 6a/6b), then walls over them. Raise the catslide gable with the first floor (stage 9).

2. **Slab before substructure walls.**
   - Where: stage 5 (slab, DPM) then stage 6 (walls from trench fill, dpc at −0.032).
   - Why it matters: the order is backwards. Normal practice is trench fill, then substructure brick/block to dpc (the cavity fill to 225 below dpc), then drains and hardcore, then slab, then superstructure. As drawn, the slab is cast with no perimeter walls, and the stage-5 note "DPM lapped to the dpc" refers to a dpc that doesn't exist until stage 6. The regs board also puts IP-DPC on stages 5 and 6.
   - Fix: split stage 4 into "trench fill" and "substructure to dpc". Make drains, hardcore, slab, then superstructure.

3. **Scaffold, edge protection and weather protection are missing when needed.**
   - Where: scaffold is `stage_in` 6, but stage 2 demolishes roof, rear-wing walls and first-floor wall, and sets needles at 2.4 m. Viewer shots `builder_stage02.jpg`, `builder_stage07.jpg` and `builder_stage10.jpg`: two lifts only (top deck about 4 m).
   - Why it matters: the plates are at 5.095 and the eaves higher. Stage 10 roof work has nobody standing at eaves height, with no guardrails, toe-boards, ladders or gate. The standards are a single thin row, with no ledgers, braces or ties.
   - Weather: the cut-open rear-wing and main-roof edges are exposed from stage 2 to stage 11, and the existing eaves and rafter tails are cut at stage 10. There is no temporary roof or sheeting.
   - Fix: scaffold goes up at stage 2 (or 1b), is lifted to the eaves plus guardrail before stage 9, and has a temporary roof or sheeting on the wing and the cut roof edges.

4. **Roof props are not credible.**
   - Where: `TW-roofprops-*`: two Acrow props 0.5 m apart at x 5.75 holding a 0.7 m head plate at 5.2 m. They are re-set "at reduced dig", stacked, on sole boards. The slab is cast around them (the "prop bases through the slab" allow-list), and they stay in until stage 10.
   - Why it matters: 5 m props from bare ground are not a temporary-works design. Casting the slab around them leaves them stuck. Nothing names a temporary works designer or the engineer's sign-off.
   - Fix: show a proper support (needles or a frame from the retained walls). Re-seat the props on the cured slab, or tag them "TW designer to detail".

5. **Detail is text only, with no geometry.**
   - Missing (checked in the elements JSON): dpc strips and cavity trays (the only "tray" hits are shower trays), wall ties, cavity closers, joist hangers (stage 8 says "on hangers"), restraint straps, eaves vents, the lead abutment flashing at the old/new roof junction, drain runs and soakaways (stage 4 says drains laid, none shown), toothing or a vertical dpc to the existing house, and pipe-through-foundation lintels (3A).
   - Why it matters: these are the things a site manager checks. Reading them in the spec isn't the same as seeing them.
   - Fix: show them as small parts, at least the dpc line, cavity trays at the abutments, the hanger line and the drain runs.

6. **Stage 12 is a lump.**
   - Where: 29 parts, with "Insulation, ceilings, dry-lining, VCL, screed, floor, partitions, sanitary" and "scaffold struck" in one step.
   - Why it matters: a builder expects first fix (electrics, plumbing, studs, noggins, insulation, BC insulation inspection), then board and skim, then second fix. There is no M&E, no stair works, and no external works or patio reinstatement.
   - Fix: split it into 12a first fix, 12b plaster, 12c second fix and decorating. Strike the scaffold after roof and brickwork, at the end of stage 11.

7. **Windows and doors appear at stage 11, while screenshots show glazed openings from stage 10.**
   - Where: `O-…` opening elements are in at stages 6 and 9, and fixtures at 11.
   - Why it matters: ask whether the viewer shows the glass early. In `builder_stage10.jpg` the panes look glazed before the stage-11 note says the windows go in.
   - Fix: check this. Bi-folds should arrive after the roof is felted.

8. **Open question: bedroom 3 door and the wall above it (`F-rearC~n1`).**
   - Why it matters: this is a real point for the engineer. A lintel and bearings are needed, so don't leave it floating on screen.
   - Fix: show a "lintel by engineer" placeholder.

9. **Site realism.**
   - Where: the look renders and viewer shots.
   - Why it matters: the grass is billiard-table green, the sky is a studio backdrop, and the brick is uniform and clean at every stage. A site person would expect a spoil heap, skip, materials stacks, welfare, hoarding or Heras, and mud and dust. Only the spoil heap appears (stages 3–4), and the temporary works look tidy.
   - Fix: add a skip, a pallet of bricks and blocks, a mixer or tote bag area, and a materials and welfare zone.

10. **Process gaps (not in the model).**
    - Missing items: asbestos survey before the conservatory comes down, a Party Wall notice (the foundations run 0.69 m from the No.21 line), service disconnections, and skip and muck-away at stages 2 and 3.
    - Fix: add them as stage notes.

## What is right
- The overall skeleton is right: demolition, dig, trench fill, slab, walls, steels, joists, upper walls, roof, covering, finish.
- Needles and props go in before the old rear wall is opened, and the wall comes out last (stage 7). That is good site-manager thinking: the house stays weathertight and habitable.
- The inspection points on the regs board are a strong feature: notice of intention, commencement, foundations before concrete, drains with test, DPC and DPM, reinforcement, structural members, insulation and completion. A builder will notice they are all there.
- The walls are built as layers (brick, partial-fill Celotex, clear cavity, block, plasterboard), with lifts of 675 mm and cavity fill to 225 below dpc.
- Padstones are bedded and dry-packed, and beam 5 has its 8 mm plate for the outer leaf.
- The temporary works are honestly labelled "typical, not from the drawings".
- Joists at stage 8 before the upper walls at 9, ceiling joists turned at the hips, and the valleys, hips and ridges all follow the 3A and 4A notes.
