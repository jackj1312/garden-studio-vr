# Garden Studio — complete house benchmark

Jack · 6 November 2026 · Living master for every coding agent and model.

**ONE front door (8 Nov 2026): the staged protocol. Start with `PASS-1-SCENE-PROMPT.txt` (the red Desktop file). `PASTE-THIS-PROMPT.txt` is Pass 3 only.** A run works in its own folder under `~/Projects/Garden Studio Runs/` with this pack frozen in its `benchmark-input/` (9 Nov 2026: nothing is built inside iCloud, so not on the Desktop). Attaching a folder alone does not reliably start a task. A local agent must be able to read the original sources named in the manifest. A cloud session cannot access Mac paths automatically; it needs an explicitly authorised, complete source transfer first. No automatic upload is performed.

**The final outcome (reached by the three passes)** is a complete, furnished, editable, explorable 23 Battle Road Before/After house and garden, with the entire studio pipeline. A shell, three attractive rooms, a video without a working viewer, or documentation without working tools is incomplete.

This is a **shared-tools, independent-house benchmark**. All entrants may use the same frozen tool kit, generic assets, skills and accumulated lessons; none is mandatory if a better method achieves the full required outcome. Each reconstructs its own measured house and placements from original plans/media. Previous entrants' houses, images, scores and production decisions stay sealed until the new entrant has **presented its own frozen result to Jack**. Freezing without presenting does not unlock comparison. This supersedes the older benchmark's permission to compare before presentation.

## Staged protocol (Jack, 7 November 2026): use this for the next tests
A first test asked for everything at once and the layout came out wrong. The benchmark is now run in passes, each
approved by Jack before the next starts:
1. `PASS-1-SCENE-PROMPT.txt`: the whole scene (house Before/After, No. 21, the one large neighbouring building, street,
   front and back gardens) exact in one site frame, checked against the drawings and photos by the shipped checks and
   gate, fast enough in a browser; STOP and present.
2. `PASS-2-FINISH-PROMPT.txt`: finishes, fittings, furniture, planting and light on the approved scene; present.
3. `PASTE-THIS-PROMPT.txt`: the full studio tools and features on top of the approved finished house.
**To start a test, Jack drags the red file `~/Desktop/Garden Studio — PASS 1 Start Prompt.txt` into the agent.** It is an exact
copy of `PASS-1-SCENE-PROMPT.txt`: whoever changes that prompt must copy it over the Desktop file again (keep its red tag),
so every test starts from the identical prompt.
`NORTH-STAR.md` (Jack, 9 November 2026) is the owner's reference for what the finished build must feel like, studied from
its original source, with where ours must differ (a browser, a real house). Every pass reads it.
`AS-BUILT-NOTES.md` gives the owner facts the drawings don't show (porch as built, loft conversion, tape measurements,
current drawing revisions); a real client job gets these from a short call.

## Setup (once per run folder)
`sh shared-tools/setup_env.sh` creates `.venv` with python3.13 (fallback python3) and installs PyMuPDF, numpy, shapely, opencv-python-headless, trimesh, scipy (the mesh checks need it), pillow, pytest, pygltflib and rasterio. Use `.venv/bin/python` for the readers and checks.

## What ships (8 Nov 2026)
- `shared-tools/library/`: `materials/phototex` (Jack's photographed tiles, scales, unit libraries, decals, house PBR sets), `materials/cc0` (ambientCG, textures, Poly Haven props), `hdri` (skies), `models/veg` (trees, perennials, `plants.json`), `registers` (asset library and sources), `materials-schedule.json`, `LICENCES.md`.
- `shared-tools/methods/`: WORKFLOW, PRESENTATION-WORKFLOW, AIRBNB-METHOD, SURVEY-METHOD, CAPTURE.
- `shared-tools/judges/JUDGES-METHOD.md`: the three-judge protocol and personas (no verdicts).
- `shared-tools/checks/` and `shared-tools/gate/` (binding): the plan-data, roof, section, elevation, ceiling, ground, element and conflict checks and the gate that alone may write a gate file. `shared-tools/readers/` (PDF readers; walls are candidates) and `shared-tools/site/` (a plan-to-scene builder, judged weaker than the studio's own builders in `shared-tools/tools/house`) are available, not compulsory. Shipped 9 Nov 2026 with their tests passing; none has been proven on a full run yet.
- Not in the pack: the studio's own plan of 23 Battle Road (`truth`), anything built from it, and the frames and camera stations of the earlier approved house. An independent run derives the house from the originals; `NORTH-STAR.md` is the quality bar.
- `lessons/`: live and Codex FIRST-PASS / CORRECTIONS-LOG / DETAIL-CHECKLIST, STUDIO-MEMORY, earlier Codex mistakes, benchmark runs' MISTAKES.
- `OFFLINE-ORIGINALS.md`: originals that are iCloud placeholders and must be exported before a run.
Not shipped (sealed): any house geometry/layout, renders, screenshots, scores, comparisons, past plans.

## Contents
- `PASS-1-SCENE-PROMPT.txt` (start here), `PASS-2-FINISH-PROMPT.txt`, `PASTE-THIS-PROMPT.txt` (Pass 3 only).
- `REQUIREMENTS.md`: complete functional and quality contract, with stable IDs.
- `PROJECT-BRIEF.md`: 23 Battle Road decisions and current owner requirements.
- `ACCEPTANCE.md`: end-to-end checks and what finished means.
- `SOURCE-POLICY.md` and `source-manifest.json`: permitted original inputs, excluded outputs and availability.
- `MCP-AND-SKILLS.md`, `skills/`, `shared-tools/`, `tool-manifest.json`: common tool baseline, provenance and connection preflight.
- `lessons/`: BOTH Claude/live-project and Codex/worktree FIRST-PASS, CORRECTIONS-LOG and DETAIL-CHECKLIST, without discarding divergent entries.
- `COVERAGE-AUDIT.md`: conversation and whole-pipeline coverage; implemented versus requested capabilities.
- `SERVERS.md`: dedicated servers and dated per-model launchers in the separate Desktop Garden Studio Launchers folder.
- `MAINTAINING.md`: mandatory update procedure for every agent.
- `release.json`: hashes for this revision. A new run freezes these files before doing any build work.

The master lives at `~/Desktop/Garden Studio Benchmark` (iCloud) and is mirrored, byte for byte, at `~/Projects/Garden Studio References/Garden Studio Benchmark` (on the Mac). Runs copy from the mirror; the originals are read from `~/Projects/Garden Studio References` too. Its tracked publishing source is `docs/benchmark/` in the active Garden Studio checkout. Results belong in separate run folders, never in the clean master. Do not put comparison screenshots in this folder.

No standing prompt can guarantee a perfect autonomous result, access to an offline source, or a physical Quest test. These are acceptance gates, not assumed passes. Native, unpaid outputs must be completed without routine permission questions. Paid/cloud, login and protected image-approval stages remain gated; an unavailable gate is reported, not silently removed.

## Method freedom — Jack, 6 November 2026
The existing workflow is a resource, not a prescribed route. Agents may choose different engines, tools, schemas, algorithms, UI architectures, asset sources and stage order, or replace/rebuild a system where that produces a better result. No loyalty to Blender, Unreal, three.js, a particular MCP or the current implementation. Preserve required outcomes, measurable scale, editability, device experience, shared-design consistency and quality. Explain consequential method changes and verify them; do not turn method freedom into omitted features. The best-tool rule applies across the whole build.
