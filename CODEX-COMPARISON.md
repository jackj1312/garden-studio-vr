# What Codex did better, and what we take (3 Nov 2026)

Studied: Codex's (Astar, max reasoning) independent build in `~/Desktop/23 Battle Road/` (`PLAN.md` v12, `independent/RUNBOOK.md`,
`independent/viewer/*`, `independent/tools/*`, its build walked in its own viewer: kitchen, living/dining, sitting room, front
garden). The GPT Sol test (`~/Documents/Codex/2026-11-03-sol-test`): Babylon.js viewer, a bare shell exported, no
furniture or finished materials when paused; far behind both. Jack's verdict: Codex's interior a big leap; exterior mixed
(nicer details, wrong scale front and back, missed paving detail); our navigation better; Codex used ~180% of a ChatGPT week
and did not finish.

## Why its interiors read better (evidence from its code and frames)
1. **Contact shadow on desktop:** a GTAO pass (screen-space ambient occlusion) in the browser, so furniture sits on the floor,
   corners darken and junctions read. Ours has no AO in the live view.
2. **Window daylight:** `window-daylight.js` / `daylight.js` place up to three soft lights at each room's real glazed openings
   (from the portal polygons, oriented by the window's normal), so rooms are lit from their windows, not by a flat fill.
   Neutral tone mapping, exposure 1, restrained environment reflections. Ours: one sun and a hemisphere fill, so rooms were
   flat, pale or blown.
3. **Finishes owned per room face at authoring time:** `finish_layout.py`, `internal_lining.py`, `floor_finish_regions.py`,
   `prepare_wall_junctions.py`: every wall face, reveal and floor region is assigned its finish when it is built. Ours
   finishes afterwards by detecting raw faces (`hb_finish.py` passes), which is where the outside-plaster regression and the
   raw reveals came from.
4. **One coherent design language:** a single Scandinavian-warm set (oak, oatmeal bouclé, linen, sage/terracotta prints), all
   furniture at real proportions, books with spines, artwork filled, pleated curtains on rings. Ours mixed downloaded models
   of different styles and qualities, stretched to spec boxes.
5. **Materials made for the house:** `oak_boards.py` / `oak_floor_palette.py` (planks at true width, colour variation),
   photo-matched palettes (`photo-materials.json`), marble, painted shaker joinery with brass pulls.
6. **Exterior detail where people look:** festoon lights on the pergola, fallen apples under the tree, a better grass
   material, wall lights, planters and cushions on the bench.
7. **Presentation:** a branded loading screen ("23 Battle Road · Opening the house · Preparing the light and materials",
   serif heading, quiet palette), a title card naming the room in plain English, a clean toolbar (Before/After,
   Furnished, Go to a room, Walk inside). It feels like a product.
8. **Performance by design:** `portal-visibility.js`, `shadow-visibility.js`, `exterior-visibility.js` (room and portal
   culling) and KTX2 textures from the start, with a target of 60 draw calls on the Quest.

## Where it was worse (do not copy)
- Front and rear scale wrong, paving details missed, neighbours as plain brick boxes, navigation weaker than ours.
- Process overweight: hash-bound evidence for every capture, 304 compact frames plus 3,912 cube faces planned before
  release, dozens of preflight/ledger files. That rigour is why it burned ~180% of a week and never finished. Our checks
  must stay proportionate: machine checks first, a few hero cameras, Jack's walk.
- Sol: spent its time on independence rules and ledgers; produced only a shell.

## What we adopt (into PLAN.md)
| From Codex | Where in our plan | Effect |
|---|---|---|
| GTAO on desktop; baked AO for the Quest | S7/S11, viewer LOOK | contact shadows, grounded furniture |
| Window daylight lights per room from real openings | S7, viewer LOOK | rooms lit from windows, not flat |
| Finish assigned per room face when built, not detected afterwards | S3/S5, generator | no raw reveals, no plaster outside |
| One design language and asset family per house; real proportions, no stretching whole items | S2/S4 | coherent, believable rooms |
| Oak plank and photo-matched palette generators | S5 | true-scale floors and finishes |
| Exterior "life" details: festoon lights, fruit, wall lights, cushions | S4/S6 | lived-in outside |
| Branded loading screen, room title card, plain toolbar | S11 | professional, on brand |
| Portal/shadow visibility, KTX2 from the start | S10 | headset speed |
| Keep ours: navigation, measured scale, paving detail, proportionate checks | — | our strengths |
