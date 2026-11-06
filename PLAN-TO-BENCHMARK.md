## Complete product benchmark — 6 November 2026
The current agent-neutral benchmark is `~/Desktop/Garden Studio Benchmark/README.md`, with `PASTE-THIS-PROMPT.txt`. It covers the ENTIRE house pipeline: original source reconstruction; full interior/kit; all garden/furniture/finish/planner editors; desktop/iPad/Pencil/phone/Quest/VR controls and help; persistence, marks, terrain, performance; native/Unreal/AI presentation workflows; MCPs/skills and both agents' mistakes. Every agent maintains it through `MAINTAINING.md`. Methods are unrestricted: existing tools are optional resources, not mandatory workflow. The full functionality and quality are required.
**Blind-run rule supersedes older comparison wording:** no previous benchmark result, model, render, score, production plan or report may be opened until the entrant has frozen AND PRESENTED its independent submission. Lessons and the explicitly supplied generic tool/asset baseline are allowed. This historical visual-reference document contains earlier output studies; new contestants must use the clean pack instead.

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

## Three outputs from one master (Jack, 31 Oct)

The Quest 3 is the limiting factor, so it must not limit the top of the range:
1. **Quest build** — the best the headset can hold at 90 fps (LOD, impostors, baked light),
   measured in the headset and then frozen as *the VR experience*.
2. **Desktop walkthrough** — the same assets at full detail with GTAO, big shadows and bloom;
   no Quest budget.
3. **Rendered film** — Blender (EEVEE Next or Cycles, cloud GPU if needed) wherever it beats
   real time. This is the realistic route to the SE Landscapes film itself; the in-app
   cinematic mode plays the same camera path live.

Every asset is built once with a full version and a Quest version, so the three never drift.

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
