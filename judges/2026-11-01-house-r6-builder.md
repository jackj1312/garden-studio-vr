# Judge: UK main contractor / site manager, round 6 (1 Nov 2026)
Checked: approved_2b.json, approved_2b_elements.json (stage_in/out, labels), CHECK.md round 6, look6 sheets and stage renders.

**Verdict: 7/10 for "a builder would use this to brief their team."** The order of works is now a real one and most of round 5 is fixed. Held back by structural carriers that arrive late, a front door that vanishes for ten stages, and compliance items (fire-stopping, restraint, roof insulation, first fix) that are absent.

**Round 5 follow-up.** Fixed: beam 5 with padstones now goes in with the walls (8); substructure (6) before slab (7); scaffold from stage 2 with lifts, boards, toe boards, ties, ladders; tarps and wing sheeting; ties, trays, closers, DPC, hangers, straps, drains are now geometry; first fix/plaster/second fix split; windows at 13. Not fixed: bedroom 3 door (`F-rearC~n1`) still floats. Props only partly (finding 6).

## Findings, worst first

1. **Openings cut at stage 3, lintels at stage 8. CONFIRMED.** `G-kitR~panel-cloaks-window-new`, `G-kitR~panel-utility-external-door-new`, `G-hallKit~panel-hall-cloaks-lobby-opening-enlarged` are `stage_out` 3. Their lintels (`L-G-kitR-k1-*`, `L-G-hallKit-hall-cloaks-lobby-*`) and pockets are stage 8. Five stages of open, unlintelled holes; needles are modelled only for beam 6. Fix: cut and lintel in the same stage, or show needles. Still open: bedroom 3 door `F-rearC~n1` (wall over a 762 door, no lintel). Add a "lintel by engineer" placeholder.

2. **Front door vanishes for ten stages. CONFIRMED.** `F-G-front-front-door-external` and the canopy go out at 3; the replacement `F-G-front-hall-door-from-porch` is at 13. The side scaffold fills the 0.6 m passage 2 to 13, so everything goes through the house, and the porch dig at 4 is in front of the open doorway. Fix: keep the old door until the porch door is hung, or show a secure temporary door and say where materials and muck-away enter.

3. **Stage 14 "first fix" has no first fix; roof has no insulation or ventilation. CONFIRMED.** Stage 14 is 13 elements: partitions plus `INS-ff` (floor quilt). No M&E zones, no roof/ceiling insulation, no eaves vents or loft hatch (0 hits), though stage 13's note lists eaves vents and the customer note says insulation goes in. Fix: add roof insulation, eaves vent trays, hatch trimmer, first-fix zones and a BC pre-plaster hold point.

4. **Inspector items absent. CONFIRMED.**
   - Fire-stopping and cavity barriers: 0 elements.
   - Joist lateral restraint straps: only 4 `RS-WP-*`, all at wall plates (11); first-floor joists (10) have hangers only.
   - Cavity trays: `CT-*` only for the kitchen window, porch door and two bedroom 3 windows; none over beam 5 (bi-fold has closers only) or the Catnic lintels at the cloaks window and utility door.
   - Utility door DPC 118 mm above the passage (<150) is still an open question.
   - Fix: add as typical parts at the right stage.

5. **Porch has no access or protection. CONFIRMED absent.** `TW-scaffold-*` covers side, wing and rear only. Porch walls 8, plate 11, rafters 12, tiles 13 (gable to 3.9 m) with no scaffold, tower or edge protection. Heras is two runs (`TW-site-heras-0-7.8`, `-1-0.1`): cannot enclose drive compound plus rear garden (PLAUSIBLE). Fix: front scaffold/tower 8-13, a gated drive Heras line, trench edge protection at 4-5.

6. **Props not credible. PLAUSIBLE.** `TW-roofprops-a` is "size 4", top 5.225: about 5.2-5.5 m from ground, past a size 4's reach (about 4.9 m), one pair at x 5.75. `TW-roofprops-c` sits on the 22 mm deck over joists (10-12) with no load path. "Design by others" is right, but the geometry implies a prop no TW designer would draw. Fix: stacked lengths on a spreader, or a frame; say where the load lands.

7. **Floor PIR at stage 7, exposed until 13-15. CONFIRMED stage; harm PLAUSIBLE.** `SL0-ins`/`SL1-ins` are 7; VCL and screed 15. 100 mm PIR under props, boards, scaffold and trades for eight stages, unroofed. Fix: slab and DPM at 7; PIR/VCL/screed after weathertight, or show protection.

8. **Raking gable ahead of restraint. CONFIRMED data; stability PLAUSIBLE.** `G-extRear~1` rises to 4.36 m; its upper courses (`WT-G-extRear~1-l9`) are laid at 9, before joists (10) and plate (11). Fix: move the rake above first-floor level to 11, or show raking props.

9. **Rear scaffold order. CONFIRMED.** `TW-scaffold-rear` at 7 has standards to 6.3 m and ties into walls that only appear at 8. Fix: ties with each lift, or reveal ties.

10. **Smaller.** No drain test/BC hold point between 6 and 7; no hoist, mixer or material route (PLAUSIBLE). Stage 15 still lumps plaster, screed, second fix, garden and completion. CHECK.md "Sequencing and temporary works" and "Omitted" are stale (12 stages, scaffold struck at 11, ties/trays listed as not modelled): mark superseded (CONFIRMED).

## What is genuinely good
- The 15-stage order is believable: demolition under needles, setting out, dig, trench fill, substructure to DPC, drains, slab, walls with steels on padstones before the brick over them, knock-through, joists, plate, roof, weathertight, first fix, plaster.
- Beam 5 and padstones set as the wall rises; lintels, closers, trays and ties staged per lift.
- Porch order is sensible beside the rear works (5, 6, 7, 8, 11, 12, 13), upper gable courses held back until beam 1 is in.
- Scaffold is credible: lifts 1.9/3.7/5.2, boards, toe boards, guardrails, tied ladders, braces; struck at 13.
- Skip, cabin, stacks, spoil heap and floor protection feel like a site; all temporary works are labelled "typical", props "design by others".
- Bearing check (0 faults) and "courses over a member wait for it" are what a builder wants.
