# Garden Studio — complete house benchmark

Jack · 6 November 2026 · Living master for every coding agent and model.

**Open this folder as the coding agent's workspace, then paste `PASTE-THIS-PROMPT.txt`.** Attaching a folder alone does not reliably start a task. A local agent must be able to read the original sources named in the manifest. A cloud session cannot access Mac paths automatically; it needs an explicitly authorised, complete source transfer first. No automatic upload is performed.

**Start with `PASTE-THIS-PROMPT.txt`.** The outcome is a complete, furnished, editable, explorable 23 Battle Road Before/After house and garden, with the entire studio pipeline. A shell, three attractive rooms, a video without a working viewer, or documentation without working tools is incomplete.

This is a **shared-tools, independent-house benchmark**. All entrants may use the same frozen tool kit, generic assets, skills and accumulated lessons; none is mandatory if a better method achieves the full required outcome. Each reconstructs its own measured house and placements from original plans/media. Previous entrants' houses, images, scores and production decisions stay sealed until the new entrant has **presented its own frozen result to Jack**. Freezing without presenting does not unlock comparison. This supersedes the older benchmark's permission to compare before presentation.

## Staged protocol (Jack, 7 November 2026): use this for the next tests
A first test asked for everything at once and the layout came out wrong. The benchmark is now run in passes, each
approved by Jack before the next starts:
1. `PASS-1-SCENE-PROMPT.txt`: the whole scene (house Before/After, No. 21, neighbours, street, front garden) as exact
   shells in one site frame, checked against the drawings and photos; STOP and present.
2. `PASS-2-FINISH-PROMPT.txt`: finishes, fittings, furniture, planting and light on the approved scene; present.
3. `PASTE-THIS-PROMPT.txt`: the full studio tools and features on top of the approved finished house.
`AS-BUILT-NOTES.md` gives the owner facts the drawings don't show (porch as built, loft conversion, tape measurements,
current drawing revisions); a real client job gets these from a short call.

## Contents
- `PASTE-THIS-PROMPT.txt`: the one prompt to start a fresh, isolated run.
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

The master lives at `~/Desktop/Garden Studio Benchmark`. Its tracked publishing source is `docs/benchmark/` in the active Garden Studio checkout. Results belong in separate run folders, never in the clean master. Do not put comparison screenshots in this folder.

No standing prompt can guarantee a perfect autonomous result, access to an offline source, or a physical Quest test. These are acceptance gates, not assumed passes. Native, unpaid outputs must be completed without routine permission questions. Paid/cloud, login and protected image-approval stages remain gated; an unavailable gate is reported, not silently removed.

## Method freedom — Jack, 6 November 2026
The existing workflow is a resource, not a prescribed route. Agents may choose different engines, tools, schemas, algorithms, UI architectures, asset sources and stage order, or replace/rebuild a system where that produces a better result. No loyalty to Blender, Unreal, three.js, a particular MCP or the current implementation. Preserve required outcomes, measurable scale, editability, device experience, shared-design consistency and quality. Explain consequential method changes and verify them; do not turn method freedom into omitted features. The best-tool rule applies across the whole build.
