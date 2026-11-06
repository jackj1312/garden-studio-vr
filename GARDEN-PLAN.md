# Garden drawing plan

3 November 2026 · Local branch `codex/garden-tool` · £0

**Existing iteration.** The studio garden in `index.html` / `src/app.js` already has a measured site viewer, desktop and Quest navigation, a left-wrist panel and right-trigger proposal strokes. `src/marks.js` closes loops, measures area/perimeter and saves marks. The house walkthrough uses the same marking module and displays the surveyed garden with the house. Its editor already has undo/redo, and the client planner has a metre-scaled SVG plan and room preview. The kit and interior branches contain the furnishing kit and a planned patio sketch. I found no saved parametric landscaping editor in either branch or the live files.

**Goal.** Extend these controls into one garden workspace. Open it from the garden viewer or house walkthrough. Every view edits the same measured design. Surveyed brick, paving and planting form the starting scene. Proposals stay reversible.

| Stage | Work and proof |
|---|---|
| 1 · Geometry and file | Give every object an ID, type, metre coordinates, exact primitive or editable cubic/arc controls, level, material/pattern and planting data. Store the garden section in `assets/sites/<site>/layout/<version>.json`, preserving furnishing fields. Fit rough strokes to straight runs, circular arcs or a small number of smooth cubic segments. Check radii, tangent continuity, closed areas, valid dimensions, save/reopen, backup and concurrent edits. |
| 2 · Drawing with the mouse | Add tools for patios, paths, lawn, gravel, decking, walls, retaining walls, beds, sunken areas, fire pits, steps, fences and edging. Drag out circles, squares and rectangles. Move, rotate, resize by handle or typed size, copy, delete and undo/redo. Make individual plant/tree instances. In the same scene provide whole-garden bird’s-eye and standing views. Check a mixed drawing, handle edits, palette changes and a save from a second browser. |
| 3 · Levels and presentation | Generate surfaces, retaining faces, raised-bed coping and one-action steps from the exact geometry. A negative level opens the terrain visually and gives the walker the proposed floor and steps. Check surveyed paving outside the footprint, level differences, step direction and matching plan/3D dimensions. |
| 4 · Quest | Extend the existing marking input and left wrist. The right trigger draws on the garden or grabs a handle; the stick adjusts the selected level. Provide straight-down whole-garden and standing modes with the same tools. Use a reversible indoor detail profile while keeping the garden, glazing, doors, indoor walking and views out. Test controller gestures in the simulator, compare draw counts and label physical headset measurements separately. |
| 5 · Handoff | Check the regular walkthrough, marks, furnishing compatibility, room planner and walk test. Capture the plan, a levelled 3D proposal and wrist/bird’s-eye views. Publish the illustrated pipeline HTML and PDF and leave a short controls note and local opening link. |

Re-read this plan, FIRST-PASS and the relevant project rules before each stage, fix and report. Record each fault and its cause with `lessons.py` before correcting it. One heavy job at a time. Test on port 8450. Claude’s 8443 server stays running. Keep design work local, preserve existing marks and keep the original furnishing work on its branches. Drawing export and agent polishing are later steps.

**Change log**  
2026-11-03 · Initial plan grounded in the live garden viewer, house editor, marks, planner and available git refs.
2026-11-03 · Jack requested a clickable How to use panel in every editor. Add contextual controls to the garden, original site viewer and marking tools, house editor, furnishing editor and client planner. Test opening and closing by pointer, keyboard and on the garden wrist.
2026-11-03 · Jack added iPad and Apple Pencil as a design device. Use the same Pointer Events editor, distinguish pen drawing from finger navigation, and check pen strokes, handles, two-finger pan/zoom, help and save at iPad sizes.
2026-11-03 · Jack added an Outbuilding base tool. Any closed footprint becomes a concrete slab with editable thickness and level. Display live and selected dimensions, area, perimeter, side or curved lengths and radius where applicable; retain exact rings, control points and slab levels under a stable ID for a later structure design session. Check a concave base, circle and curved footprint across save/reopen, plan, walking and wrist.
2026-11-03 · Preserve the existing 8443 walkthrough and marks server. Its ordinary viewer reads saved design files locally; editing entry points use port 8450 on the same Mac. This keeps existing links useful without restarting Claude’s server.

2026-11-03 · Jack requested locked-mouse walking with the garden panel minimised. Reuse house walking and head turning, suspend drawing, retain the current design and return to the same editing view. Test real pointer lock, Esc, relative mouse movement and WASD on the live route.
2026-11-03 · Jack reported low desktop frame rate. Measure the actual live Retina garden and keep its geometry, material and shadow detail while reducing screen passes and unnecessary roof queries during design. Verify the regular house render resumes on exit.

2026-11-03 · A minimised editor must support mouse look when the embedded browser denies native pointer lock. Garden and Furniture must be reachable in both directions while preserving drafts. The older Wi-Fi garden has explicit return links for the furnished preview and room planner.

2026-11-06 · Jack wants a studio base for a later tattoo-studio concept. Expose persistent Plan / 3D / Walk buttons using the existing shared scene and walking controls; check round trips, base selection, desktop and phone. Browser is the appropriate tool for measured interactive layout; nothing in this UI change is deferred to Unreal. Jack draws and saves the footprint first, then the agent constructs a box from that exact base and uses its original render for image generation.

2026-11-06 · Add temporary car and van clearance guides using existing rectangle editing and selection. Generic editable envelopes, not manufacturer dimensions; exclude them from saved layouts. Check moving/rotating/resizing, rendering and save exclusion.
