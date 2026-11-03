# Garden Studio VR furnishing progress

## 3 November 2026 · Stage 1 · codex/kit

- Built the reusable generator, catalogue, separate models, photographs and contact sheet in `tools/library/kit/`. The 280 entries cover 85 kinds. Each family has 39 style-specific entries and access to the same 46 shared fittings. Source geometry came from the independent furnishing and styling modules. The six families share the reviewed CC0 material library.
- Verified every model file, texture dependency, material digest and 256 px image. Three independent reviews caught UV stretching, support, thumbnail invalidation and duplicated neutral appliances. Corrected the causes and checked the exported models. Five custom-size Blender builds passed to 1 mm. Exported bouclé surface area below one quarter of intended UV density fell from 31.7% to zero. The contact sheet is `tools/library/kit/contact-sheet.jpg`.
- Captured the same three views at stage 15 on port 8450 in `renders/house-build/furnishing/{baseline,kit}/`. The room model is still the baseline at this stage. The updated Desktop pipeline PDF has 14 pages. Its rendered kit page, photographs and caption were checked together.
- Next is the house integration. Round-2 shell, export, spec, walk and lessons findings are still open. Physical Quest frame times have not been measured. Port 8443 remains under Claude's control.

## 3 November 2026 · Stage 2 · codex/interior · candidate under test

The generator reads the signed Before and After schedules, prepares measured kit meshes and places them through the regular house build. The candidate includes room-owned finish intervals and returns, metric oak boards, detailed windows and door hardware, the measured Before conservatory, apples and the existing lawn with the reviewed grass material. The build retains the seven previously reported construction-stage support warnings in the approved version.

Both signed versions passed the room-finish checklist and the seven-part shell check. Full-room rays found zero raw interior faces in the drawn and measured layers. The signed spec check returned zero failures. The private browser walk passed all four versions, including Bedroom 1. A previous support audit cleared all 105 Before and 123 After items with at most 2 mm gap. The latest stricter fit exposed a Bedroom 1 wardrobe that needs a 10 mm lateral and 25 mm forward move; the corner resolver is implemented and awaits re-export. The original five brick materials retain the same PBR parameters and texture bytes.

The measured opening head and rear-right conservatory post are fitted. The last Before scan had one remaining head/jamb joint at the kitchen doorway. Stage 2 is checkpointed pending that joint, the wardrobe re-export, device checks and final release tests. The expanded garden editor proceeds on its own local branch. The client house-wip model is still the previous publication.


## 3 November 2026 · Stage 2 · verified on codex/interior

The final measured kitchen soffit meets the jamb, and the Bedroom 1 wardrobe now sits at (3.085, 2.6775, −0.625) m in viewer coordinates with zero shell intersection. The furnished Before and After candidates include the scheduled fittings, lighting hardware, room-owned surfaces, fitted openings, the existing conservatory, and the surveyed garden with its grass and fallen fruit. The conservatory's signed finish retains its brick dwarf wall and house rear face.

All four integrity scans reported zero blocking faults. Both shell and finish checks passed. The signed spec checker returned zero failures across 337 scheduled entries, with 336 present at the checked stages. The placement validator checked 105 Before and 123 After loose placements with zero issues. All 14 exported viewer files loaded, including the repaired meshopt twins. The candidate walk passed all four versions in 12.4 s. The planner, house controls, room culling and doors passed on desktop, phone and simulated headset. Matched kitchen-diner, lounge and front-garden frames are in `renders/house-build/furnishing/interior/`.

The earlier seven approved-version construction-stage support warnings are still recorded. The client house model remains the previous publication while the runtime layout, round-2 marks and release gates are completed.

## 3 November 2026 · Stage 3 · codex/furnish-system

The walkthrough and `/plan/` now open a single versioned layout from `tools/layout_store.py`. `src/furnish/` provides the catalogue, shared placement and undo logic, actual furniture instances, wall and room finishes, overhead plan, and left-wrist/right-ray controls. `tools/house/runtime_assets.mjs` separates 121 Before and 152 After movable items from the fixed house. `tools/house/bake_layout.mjs` reconstructs the next build from a saved revision. Existing planner requests remain traceable. The requested Before living-room armchair sits 84 mm from its original proposed position so both conservatory doors can open. Fifteen inherited accessories now sit on the tops of their actual supports.

All 28 runtime and planner logic tests, 14 layout-store tests and six local network tests passed. The normal desktop, phone and simulated headset editors passed place, blocked drop, rotate, undo, save and reopen across the planner and walkthrough. The desktop material check inspected the rendered meshes for one wall and one floor. The Before reconstruction paints 16 primitives on four faces and changes one floor. All 14 models passed the export loader, the shell and finish checks passed, and the four-version walk passed in 16.7 seconds. Matched pictures and simulator results are in `renders/house-build/furnishing/furnish-system/`. Simulated calls/triangles before the lighting work were 336/441,135 in the kitchen-diner, 329/399,609 in the lounge and 743/1,056,510 in the front garden. The Mac simulator runs on a 60 Hz display.

The garden was handed over separately. The house is still the private release candidate while lighting, remaining marks and headset optimisation are completed.

## 3 November 2026 · Stage 4 · codex/look

`src/house/room-lighting.js` uses the actual room polygons, glass, doorways and current build stage. Desktop daylight comes through the measured exterior openings, with neutral tone mapping and short-range GTAO. Individual practicals, room groups and the whole house can be switched on screen or on the wrist. The branded entry, live load percentage, passive room title and responsive toolbar are in `src/house/presentation.js` and `presentation.css`. The complete 280-item kit is available to both planners, including wall and ceiling fittings.

Desktop, phone and simulated Quest passed the ordinary Before/After, furnishing, Go to, marking, lamp and room-title controls. Holding a real furniture file held the loader at 98% with Explore disabled. The corrected physical-wrist pose put both lamp buttons inside the simulator frame, and the handheld Help and status UI kept their targets. The fresh four-version walk passed in 15.8 seconds. Seven lighting tests include the actual Before/After fixture and material headers. Matched pictures, the clean all-on lounge view and simulator results are in `renders/house-build/furnishing/look/`. The Desktop pipeline PDF has 18 pages; the illustrated lighting section is page 14.

The steady simulated headset used 336 draws / 441,135 triangles in the kitchen-diner, 329 / 399,609 in the lounge, and 743 / 1,056,510 in the garden with the lighting profile enabled or disabled. Median frame intervals were 16.7 ms on the Mac simulator. Frame pairs match exactly in the garden and in at least 99.95% of pixels indoors. This measures the ordinary daylight setting with lamps off. Physical Quest 3 frame time remains to be measured. The next stage addresses the original marks and retains the client’s published house until all release checks pass.

The release rehearsal also verified the normal two-site workflow. First publication creates a missing design file and preserves an existing client file byte for byte. The next build read furniture, individual wall and floor finishes, garden data and historical model resources from the client’s saved revision, even when the private candidate had a different revision. A second build without flags produced the same receipt. All 36 related Node tests and 24 Python store, publication and network tests passed.

## 3 November 2026 · Stage 5 checkpoint · codex/marks

The four-version private build contains the 1.810 m hall, 801 mm sitting-room door, roof returns and finished steel junction, 900 mm cross-path, real shed doors, pergola clearance, measured kitchen splash/board/towel and other recorded repairs. The signed spec passed (337 scheduled, 336 present), the equipment and path checks passed, and all 26 named camera destinations passed the room-visibility check. Jack confirmed that the neighbouring-lawn stroke was accidental; its original vertices, UVs and finish match.

A read-only latest-house preview is available at `https://192.168.1.118:8450/preview/`. It renders the completed candidate, with 152 After and 121 Before movable items. Desktop and simulated Quest opened both versions; the headset loaded each repaired meshopt twin. The client publication remains on its older release. The live garden now offers locked mouse look and WASD when minimised, with Escape and Tab restoring mouse/UI control.

The normal desktop house now renders directly while moving and restores screen contact shadows when settled. The matched Retina walking tests on this Mac went from 4.2 to 40.9 fps in the kitchen, 2.3 to 43.4 in the lounge and 4.5 to 30.5 in the front garden. `renders/garden-tool/performance/{house-native,house-balanced}.json` holds the measured frame intervals.

**Pending at the usage checkpoint.** The corrected timber support, final plant colour, signed wooden bowls, ceramic roughness and distinct artwork recipes still need the combined export. Then run fresh integrity → shell → finish/spec → export/meshopt/texture repair → walk and marked-view checks, reconcile the findings and refresh the preview. Stage 6 fixed-part batching, KTX2 conversion, final matched simulator measurements and gated client publication are outstanding. Physical Quest 3 timing is unmeasured.
