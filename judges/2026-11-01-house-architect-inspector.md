# Judge: architectural technologist / building control, 23 Battle Road model (1 Nov 2026)

Read-only review of CHECK.md, the overlays, regs.json, regs_map.json, build_regs.py, rules.js, the element and check JSON, REGS-REPORT.md, TRACE.md and the 2B/3A/4A text.

## Ranked faults

1. **Padstones and packs carry lintel rules.**
   - 10 of the 17 parts in group `lintel` are not lintels: beam-4 pad1/pad2/pack3/pack4, beam-5 pad1/pad2 and beam-6 pad6-9.
   - They get A-2C24 (150 mm bearing, or 100 mm), B-5.18 cavity barriers and PROC-R3-2. board_regs_lintel.jpg shows it on a padstone.
   - The dry-pack/shim parts are "assumed" and still get a 150 mm bearing rule.
   - The beams they carry get only A1 (judgement), so nothing tells the reader to check padstone bearing and spreading.
   - Fix: give them their own group, with a bearing/spreader rule.

2. **"Regs: all pass" is a stub.**
   - viewer.js line 932 shows it on every view (see inspector_stage03_regs_foundation.jpg, where 0/14 inspection items are ticked).
   - rules.js runs three checks: stair rise/going/2R+G, stair headroom and removed-wall load.
   - Nothing else is tested, yet a builder or inspector reads "all pass".
   - It also cites K "para 1.10 / Diagram 1.2", where the dataset says 1.11 / 1.3.
   - Many Regs-tab entries say "Check: numeric (the model can test it)" for values that are scaled or assumed.

3. **Liability wording is weaker than the report recommends.**
   - The Regs tab shows one short dim paragraph, 24 px, capped at 5 lines.
   - It omits: a "pass" is not approval, a certificate or a warranty; the edition and transitional rules; and that the model is not a design or a set-out.
   - No "not for construction / do not set out from this" appears anywhere in src/house or versions.json.
   - The two sentences that exist are fine; they are too small and too few.

4. **Assumed things are presented as drawn.**
   - Stage-1 "existing" foundations (FD-3/FD-4) and the existing floor (SL1-*) carry the new-extension spec: 200 RC slab, A393, 100 Celotex, DPM, 600 trench fill.
   - They are sourced "4915.3A" with conf "scaled".
   - 2B says the existing floor is "not known... assumed solid", and the existing foundations are "to be exposed & inspected".
   - Foundation depth is also "scaled", although the drawings give only "min 1 m... to the approval of the Building Inspector".
   - Every opening's `plain_label` is its host wall's text. The new bi-fold doors read "New cavity wall: brick outside, insulation, block inside".
   - Five of the seven new-opening lintels are assumed, and CH vs CG is mixed.

5. **Geometry.**
   - **Bi-fold head against beam 5.**
     - The head is 2.115 against a beam-5 underside of 2.085, so the door head sits 30 mm inside the beam.
     - Section A-A dimensions 2110 from the dpc line, and the dpc is 32 mm below FFL.
     - On a dpc datum the drawn opening is about 2.08, which matches the beam.
     - Opening cuts are not tested as clashes, so the check and Questions list miss it.
   - **Elevation datum.**
     - TRACE conflict 5 says written sill/head chains start at the dpc, yet they are applied as FFL values.
     - That risks a systematic 32 mm offset on every opening. The 30 mm elevation tolerance would hide it.
   - **Reported errors are censored.**
     - The 60 mm pairing window caps "worst" at about 60 mm.
     - 2B ground is 91% within 20 mm (126/139) and first floor is 86%. p95 is 40-47 mm.
     - Sections are 80% (A-A 28/35). D-D is 2/4, effectively unchecked.
   - **Roof.**
     - Only 52% of roof-plan lines match.
     - The eaves are 50-80 mm below the drawn fascia and tile edge. The ridges win, and the pitch is 44° against 45° on C-C.
     - These are real drawing conflicts, but the user is not shown the resolution.
   - **Kitchen flank.** It is 40-59 mm off 2B by decision (290 against 250). The wall governs the kitchen and utility widths, so it needs the architect's answer, not an override.

6. **Mapping: wrong or missing attachments.**
   - **DPC.**
     - C-5.5b (DPC at least 150 mm above ground) is on slab layers, not walls.
     - No dpc, cavity-tray, closer or weep-hole part exists, though the sheets draw them (Type E and Type X trays, 150 mm).
     - At the side-passage utility door the ground is -0.15 and the dpc -0.032. That is 118 mm, under 150, and nothing flags it.
   - **Escape windows.**
     - B-2.10a goes on every new window, including cloaks and kitchen. Nothing singles out the one bedroom 3 "EE" window (conf assumed).
     - Its sill is 1.0 m above FFL, so the 1100 mm test is tight and unevaluated.
   - **Inapplicable rules attached.**
     - B-5.6 (integral garage) sits on every new wall and door.
     - B-5.5 (party wall) sits on every new wall.
     - Q/O "not applicable" rules sit on windows.
     - Boundary rules B-11.8 and B-D11.5 sit on all windows with no distance test.
   - **Flue.**
     - Section D-D shows the boiler flue beside the 550x780 porch Velux. J-D34 is on windows and doors but not on rooflights.
   - **Roof parts.**
     - Rafters get both L-T4.2-roof and L-T4.2-wall.
     - There is no roof external fire spread (B4) rule, nothing on abutment trays and flashings, and nothing on the drawn 10,000 mm²/m eaves vent.
   - **Beams.**
     - Beams 5 and 6 replace load-bearing leaves but lack PROC-R3-2.
     - Props and temporary works get no rule.
     - The porch (about 4.7 m²) may be Schedule 2 Class 7 exempt, yet beam 1 gets R30 steel rules.

7. **Inspection grouping.**
   - **Stage-list mismatch.** INSPECTION_STAGES is hard-coded and contradicts the dataset.
     - IP-COMPLEX is at stage 7, but its rules (ties, closers, barriers) sit at stages 6 and 9.
     - IP-STRUCT is at 7/8/10, but the lintel rules tagged IP-STRUCT sit at 6 and 9.
     - IP-INSUL is at 9/11, against 6/9 and 10/11 in the rules and the report.
   - **IP-COMMENCE.** It is shown at stage 2 (strip-out), while PROC-R16-3C / PROC-R46A-1 and the report put it at stage 5, on completion of the foundations and ground-floor structure. That would tell a builder the wrong day.
   - **Labelling.** "Complex parts of structure" is a poor label for wall ties and closers. Stage 6/9 are cavity-insulation and DPC visits.
   - **ESBCP note 9.** I could not verify it from the repo beyond the report's paraphrase.

## What is right

- Scale bars and written dimensions agree within 5 mm, mostly 0-3 mm.
- Long wall faces are 0-15 mm on the 4915.1 plans (99/100 ground).
- Beam sizes, positions and bearings match the drawn notes: beam 4 UB 178x102x19, beam 5 203x102x23 plus 8 mm plate, beam 6 2no UB 178, and the flitch beams 2 and 3.
- The slab and foundation levels were corrected to the 3A lines.
- The bedroom 3 door support question is flagged and not faked.
- The conflict log (44/45°, 2110/2115, 35/36°) is honest.
- Temporary works are labelled "typical - not from the drawings".
- The stair is 14 x 191.1 / 230.5. That gives 2R+G 612.7 mm and a pitch of 39.7°, inside AD K.
- U-values (0.18 / 0.15 / 1.4), D2 LD3 alarms, the 0.33 m² / 450 mm / 1100 mm escape limits and the 1 m clay foundation depth match both the drawings and the dataset.
- The dataset flags inapplicable rules (ext False) and UNVERIFIED rules.
