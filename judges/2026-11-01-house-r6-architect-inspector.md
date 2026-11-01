# Judge R6: architectural technologist / building control (23 Battle Road, 1 Nov 2026)

**Verdict: 7.5/10 as a briefing tool an architect and an inspector would trust.** Geometry and spec text are strong. Provenance (what is drawn, what is photo, what is owner) and a few rule mappings are still loose.

Method: element JSON, GLB bounding boxes (my own parse of approved_2b.glb), regs.json/regs_map.json, rules.js, build_regs.py, TRACE.md, 3A/2B/4A text dumps. Reg 16 and 46A text read on legislation.gov.uk. I could not re-run the viewer or verify the AD B 2025/2026 amendments in regs.json (after my knowledge).

## Round 5 points: status
Fixed: padstones now have their own entry (A1, B-5.2), with dry packs separate. "All pass" is gone (summary says "Guidance, not approval"). Liability text and "Not for construction / do not set out" are present. Bi-fold head is 2.083 on the dpc datum and the opening clash check runs. IP-COMMENCE is now at dataset stage 5, which matches reg 46A(3)(b). B-5.6, B-5.5-on-every-wall, Q/O and the boundary rules are no longer blanket. B-2.10a is only on `-EE`. Still open (disclosed): kitchen flank 290/250, eaves 50-80 mm low, 60 mm censored error window.

## Findings, most severe first

1. **Owner items sit in the approved scheme with regs attached. CONFIRMED.**
   - `F-*-owner` (5 replacement windows): category `new`, stage 13, no `no_regs`. Only `LOFT-` is excluded in `regs_map` and `viewer.noRegs`. They therefore match `new_windows`, `windows_far` and `critical_glazing` (L-T4.2-window, F-T1.4, K-D5.1...).
   - `AB-X-porch-cctv/doorbell/mirror/plaque/step/downpipe` and `AB-S-porch-door-furniture` are stage 13-15 `new` primaries with no "not on the drawings" wording.
   - Fix: add `no_regs` to every owner and photo item, and put "owner, not on drawings" in the label.

2. **Porch door departs from the drawing under a drawing label. CONFIRMED.**
   - `O-G-porchL-porch-external-door`: model width 0.86 (u 0.985-1.845), head 2.029.
   - 2B: "950x2110mm high" (u 0.903-1.853, head 2.078 on the dpc datum). That is -90 mm width and -49 mm head.
   - It is labelled drawing "4915.2B section D-D", conf `scaled`. The drawn size appears only inside the toggle door's label.
   - Fix: conf "measured from photos", drawing "photo survey". Keep the drawn opening in the approved scheme and put the built door in the as-built layer.

3. **Conf vocabulary misuse. CONFIRMED.**
   - 57 photo-derived elements (AB-*, owner windows) are `scaled`. Only the 2 LOFT parts say "measured from photos".
   - `WT`, `CC`, `CT`, `DPC` (about 47 parts) are `exact`. The text is verbatim but placement and stop-end geometry are generated (3A says only "flexible cavity tray over").
   - A reader will take `exact` as dimensional. Fix: "text exact, placement generated".

4. **Rule mapping errors. CONFIRMED.**
   - Timber beams 1-3 are labelled roof-only supports ("support ext'g retained roof", porch rafters). They get B-5.1-TB2 (30 min) without B-5.3, the roof-only exemption.
   - All four steels get K-1.11 (stair headroom). None is over the stair: beam 6 ends x 3.689, the half landing starts at 3.69.
   - `B-5.1-TB2`: clause field says "Table B2", the quote says "Table B1". Check the primary source.
   - The porch (about 4 m², Sch 2 Class 7?) gets foundation and R30 rules. Only L-0.14 has the "building control to confirm" prompt.
   - Beams 2 and 3 replace a load-bearing wall but lack PROC-R3-2.

5. **Inspection mapping gap at pre-plaster. CONFIRMED.**
   - IP-INSUL carries dataset stages [9,10] = build stages 11-12 (walls to plate, roof structure). Insulation goes in at build stage 14 ("First fix and insulation"), whose regs_stage is 12, so it shows only IP-COMPLETE.
   - No pre-plaster/pre-cover visit exists where an inspector would make one.
   - Under the current regime the rest is right: 16(1) two-day notice, 16(2)-(3B) authority-specified stages, 16(3C) commencement notice within 5 days, 46A(3)(b) trigger = sub-surface plus ground-floor structure (build stage 7), 16(4) completion. Whether the 2022 approval falls under the pre-Oct-2023 transitional rules is flagged only by the liability text.

6. **Door heights, 32 mm short. PLAUSIBLE.** The dpc shift is applied to heads of doors whose sill stays at FFL. The utility door and cloaks window head is 2.078 against "950x2110mm high", and 2110 is a door size, not a dpc-chain value. TRACE.md conflicts 3 and 5 are stale (still say FFL / 2.115).

7. **Steel bearings and edits not in the labels. CONFIRMED from the GLB.**
   - Beam 4 ends at the pad centres: z -4.612 and -7.971 against pads -4.66...-4.56 and -8.02...-7.92. Bearing is about 48-50 mm of a 100 mm pad.
   - Beam 6 is 3.099 long against 2.949 traced (+150). The right pad bears 134 mm and the left 150. This is in CHECK.md, not on the element.
   - Beam 1: timber soffit 2.314 against the drawn "2110 to u/side encased beam" (2.078 on the dpc datum), about 230 mm higher. The casing was removed on Jack's instruction, but CHECK.md section 7 still says "casing added".

8. **Typical steel boxing reads as a spec. PLAUSIBLE.** "12.5mm board and skim on battens" is invented, and a single 12.5 mm standard board rarely gives R30. Label it "protection to the engineer's specification".

9. **Loft and AD B. PLAUSIBLE.** The loft floor is above 4.5 m. B-2.2, B-2.5 and the escape-window logic assume a two-storey house. The "no regs" blanket hides this effect, so add a one-line prompt on the stair and EE window.

10. **Minor.** A393 top is at -0.249 against slab top -0.205, giving 44 mm cover against the drawn "min.50". Stair guard labels cite K 1.33 while the dataset has 1.38/3.2. B-5.5 has empty parameters (no REI value).

## Sampled values (model vs drawing)
| Element | Model | Drawing |
|---|---|---|
| beam 5 | 203x102 + 8 plate; underside 2.085; x 1.581-5.041 (3.46) | 2.085; 3.460 |
| beam 5 pads | 300x100x150, 150 bearing | same |
| beam 6 | 178 deep, underside 2.110 | 2.110 |
| beam 4 | 178x102, top 2.6533 | UB 178x102x19 (level not drawn) |
| beam 3 | timber 100 wide, plate 10x180 | 2x45 + 10, 180 deep |
| beam 2 | 195x90, length 3.179 | 2no 195x45, 3.179 |
| beam 1 | 2.218 x 122x90 | 2.218, 2x45x122 |
| joists | 45x195, 0.4 c/c, top 2.654 | 45x195; deck 22 |
| ceiling joists | 45x145 at 5.095 | 45x145 |
| rafters | 45x95, 44.1° | 44° |
| ridge board | 32x175 | 32x175 |
| plate | 5.095; porch 2.253 | 5.095; 2253.23 |
| slab layers | 25/75/103/201/150 | 25/75/100/200/150 |
| trench fill | 0.6 / 0.45 wide, 1.0 m below -0.30 | 600/450, min 1 m |
| kitchen window | 1.81 x 1.060 | 1810x1060 |
| cloaks window | 0.686 x 1.060 | 685x1060 |
| bedroom 3 windows | 1.245 / 1.81 x 0.975; sill 0.968 above floor | 1248/1810 x 975 |
| bi-fold | 3.16 wide; x 1.733; head 2.083 | 3160; 1228 from the corner; 2115 from the dpc |
| stair | 14 x 191.1 / 230.5; pitch 39.7°; 2R+G 612.7 | 14 risers to 2.6755 |

Only items 2, 6 and 7 (and the known eaves/flank) exceed 20 mm. All sampled conf labels were right except for the provenance cases in items 2 and 3. The 337 walls show 335 or 340 (blockwork 98 or 103 against the nominal 100), inside tolerance.

## Stair, escape, fire
- **Headroom.** My ray test from the GLB gives a minimum of 2.038 m at nosing 2, under the 2.430 ceiling. That passes AD K by 38 mm on scaled geometry, and the viewer correctly warns.
- **Guarding.** The landing balustrade is 900, the masonry spine about 897, and the handrails are 900. All are labelled typical or assumed.
- **Escape window.** The EE window is the right-hand 3-light unit, sill 968 mm. The frame estimate is about 0.45 m² and is correctly a warn.
- **No.21.** The new work does not touch the party wall. B-5.5, B-9.24 and E2 attach to it only.

## Genuinely good
- Beam, joist, slab and foundation values match the drawings to 0-3 mm.
- Round-5 faults were fixed in data, not hidden.
- The typical/not-drawn labels on temporary works, handrails, hangers, straps and thresholds are consistent and honest.
- Q1 (bedroom 3 door) and the 118 mm utility-door dpc are shown as open questions.
- The liability wording is strong.
- The loft is fully excluded from regs.
