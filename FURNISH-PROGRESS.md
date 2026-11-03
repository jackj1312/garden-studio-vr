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
