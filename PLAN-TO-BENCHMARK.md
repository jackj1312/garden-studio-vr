# Plan to reach the benchmarks (31 Oct 2026)

Benchmarks are in BENCHMARKS.md. Honest gap today:

| Area | Ours now | Benchmark | Gap |
|---|---|---|---|
| Trees | drawn sprig texture on random cards in a blob; no branches | scanned species trees, full canopies, dappled light | large |
| Planting | three generic card "species" | full beds of real perennials, grasses, climbers | large |
| Light | bright, hazy, bloom (done today); hard shadows, no AO | soft shadows, dappled light, AO everywhere | medium |
| Existing garden | textured boxes for house and fences | photoreal capture (Airbnb) | large — only the capture fixes it |
| Design | studio in an unchanged lawn | a designed garden: slatted fence, curved lawn, lighting plan | large |
| Film | none | 1:22 drone arcs, reveal, day→night, music | not started |

## Steps, in order

1. **Trees and shrubs from scans (today).** Poly Haven has photoscanned CC0 vegetation:
   island_tree_01–03, jacaranda_tree, tree_small_02, shrub_01–04, fern_02, grass_medium_01/02,
   grass_bermuda_01, periwinkle, celandine, dandelion, nettle, moss_01, plus 40 bark textures.
   Bring them into Blender, make Quest versions (full mesh near, baked impostor cards beyond
   ~12 m), Draco. In three.js: leaf material with translucency, canopy-bent normals, wind, and
   alpha-tested shadows for dappled light. Test shot: our stage 6 vs the video at 0:22.
2. **UK garden palette (today/tomorrow).** Lavender, alliums, stipa, hydrangea, box balls,
   ferns, climbers. Poly Haven where it has them; otherwise CC-BY from Sketchfab with a credits
   page (your form, Q3), or assembled in Blender from scanned parts. Beds planted to the video's
   density: three heights, no bare soil, repeats of each plant.
3. **The design pass in Blender (tomorrow).** Lauren's garden, not just her studio: horizontal
   slat cedar fence, pergola, curved lawn with a steel edge, stone paving with joints, a
   lighting plan. Then bake AO and lightmaps for the whole garden, not only the studio.
4. **Light.** Softer shadows (contact-hardening), per-time colour grade, night uplighters and
   path lights baked as emissive with a few real lights.
5. **Film mode (day 3).** One camera path: drone arc, low track through planting, studio
   reveal, day→night cut. Plays in-app as the cinematic button; exported frame by frame at the
   premium tier into a video with CC0 music.
6. **Quest budget on every step.** ≤150 draw calls, ≤500k triangles, measured; impostors and
   LOD keep 90 fps. Nothing ships unmeasured in the headset.
7. **The real garden.** Capture yours (CAPTURE.md), reconstruct, splat backdrop (Spark),
   drop the fake house. This is the only route to the Airbnb bar.

Before every output to Jack: re-open both benchmarks, three judges, act on all of it.
