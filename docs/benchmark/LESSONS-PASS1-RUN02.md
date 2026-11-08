# Neutral prevention rules from Pass 1 run 02 (Claude Opus 5.5, 7-8 Nov 2026)
House-agnostic; found by two independent fresh-context reviews of Gate 1A. Turn each into a check.
1. Door hinge = centre of a circle fitted through the drawn arc; never a bounding-box corner (quarter arcs are equidistant
   from both opposite corners). A drawn door with no swing found is an error, not a pass.
2. Dashed lines at a door position are the door head; never auto-dismiss dashed lines inside the storey's walls when
   measuring overlay residuals.
3. Walls joined centre-line to centre-line leave an empty square at every external L-corner; the shared joint check passes
   anyway. Extend one wall to the outer face.
4. A circled height on a recess or pier means the wall continues above it; check that every upper-storey wall stands on a
   wall or beam below.
5. Never delete drawn fabric without dated evidence that it is gone; flag it instead.
6. Owner as-built items (porch, loft conversion) appear at every gate as flagged placeholders, not "later".
7. Classify site-plan outlines as buildings only where LiDAR height says so; garden parcels close as polygons too.
8. Doors the drawing shows clashing are source facts: present them and ask the owner; never move a door to pass a check.
9. Record a model hinge/side audit against the drawn arc for every door, so the swing check is not the model checking itself.
10. Before publishing, count iCloud online-only (dataless) sources: publish.py skips them silently and the release then drops those tools (2026-11-08: 101 files dropped, restored from the previous release's byte-identical copies). Hydrate first, or carry the previous copies over and say so.
