## Complete studio benchmark — Jack, 6 November 2026
For EVERY Garden Studio / architectural pipeline task, first read `~/Desktop/Garden Studio Benchmark/README.md` and `MAINTAINING.md`. At every milestone/handoff, update that shared benchmark with every added/changed tool, feature, owner requirement, quality detail, workflow, MCP/skill dependency and prevention lesson, including both Claude and Codex mistakes. Do not make Jack explain them again. Preserve newer work from other agents. Refresh its prompt, requirements, original-source inventory, common tool/skill inventory, full lesson snapshots and hashes through the active checkout's `tools/benchmark/publish.py`; update/publish the illustrated pipeline too.
For a benchmark contestant, read the clean pack instead of old project plans/results: derive an independent house from original plans/media. Shared tools, assets and mistakes are explicitly allowed; previous generated houses, layouts, renders, scores, build plans and reports are sealed until the entrant has frozen AND PRESENTED its own submission to Jack. A frozen result alone does not unlock them. Start a fresh chat/run for an uncontaminated comparison. All existing methods are OPTIONAL: use any better workflow/engine/tool/architecture; preserve the full product outcomes, highest quality and honest checks. Spending, privacy and login approvals still apply. See `PASTE-THIS-PROMPT.txt` for the complete agent-neutral brief.

# Garden Studio VR — project rules

## MAJOR RULE: every build follows WORKFLOW.md (Jack, 31 Oct 2026)
"we need to have a mapped workflow and mark every place we went wrong and where ive made corrections so they
never happen again… this needs to be a major rule for this project, when we have mastered the workflow we will
create a studio software so every build follows the same flow."

- Every property — Jack's own garden now, every client's home later — goes through **WORKFLOW.md**, gate by gate,
  in order. No stage starts until the previous gate has passed. No skipping, no "quick" builds outside it.
- **CORRECTIONS-LOG.md** records every mistake: mine, a judge's, or one Jack corrects. Add the row *before*
  fixing. Each row names its root cause, the rule that prevents it, and the gate that checks it. A row is
  closed only when the rule is built into a tool or a gate check.
- Before each stage, read the log rows for its gate.
- When Jack corrects something, that correction becomes a rule in the log and, where possible, a check in a
  tool. The same mistake must never reach him twice.
- The workflow and the tools are written so they can become the studio software: each gate a step with clear
  inputs, outputs and checks; scripts parameterised by site, never hard-coded to Jack's garden.

## PLAN.md is the anchor for every build (Jack, 2 Nov 2026)
- Every build starts with a written plan for the whole build: concise and highly descriptive (goal; stages in order with
  inputs, outputs, the check that proves each done, tools and assets; risks and costs). Shown to Jack before building.
- Re-read the plan in full at the start of every stage, before every fix round, after any context compaction or restart,
  and before reporting to Jack, and check the work against it so it never gets diluted by long context.
- Change it only on purpose, with a dated line saying what changed and why. Every agent brief names the plan to re-read.
- **The house build's plan is `PLAN.md` (written 2 Nov 2026 from `AIRBNB-METHOD.md`).** It is the anchor from now on;
  WORKFLOW.md gates and the spec are the checks inside it. When a new plan is written it replaces the old one as the anchor.

## The pipeline document stays current (Jack, 3 Nov 2026)
- `docs/pipeline/` is Jack's illustrated start-to-finish guide (published to ~/Desktop/Garden Studio Pipeline/ as HTML + PDF,
  with links to the planner and walkthrough). Whenever a stage, tool, link or method is added or changed, update it and run
  `tools/docs/publish_pipeline.sh`. Applies to Claude and Codex alike.

## Tell Jack which model (Jack, 2 Nov 2026)
- Claude says, unprompted and at the top of the reply, when to change the session model and to which: **Model: switch to
  Opus 5.5 now (the fix round).** PLAN.md §5b has the model per stage. Loops go to cheaper agents regardless.

## FIRST-PASS.md — the reviewer reads it constantly (Jack, 1 Nov 2026)
- Every headset mark and every fix we make ourselves becomes a lesson (tools/review/lessons.py: intake / add /
  resolve / fixed) with its root cause, rule and check BEFORE it is fixed. FIRST-PASS.md is regenerated from them.
- Read FIRST-PASS.md at the start of every round and before every fix; every agent brief says so.
- `lessons.py gate --site <site>` must PASS before Jack is shown anything.

## STUDIO-MEMORY.md — read it often, add to it always (Jack, 31 Oct 2026)
- Read it at the start of every session, again before every gate (its section for that gate), and before any
  decision that costs money or Jack's time. Not once: regularly.
- Add a dated line the moment something worth keeping is learned. Every project builds from the last.

## Details matter most (Jack, 31 Oct 2026)
- DETAIL-CHECKLIST.md is checked line by line on every project at G3 and G6, and grows with every new detail.

## Standing rules
- Plan first: measured plan and elevations signed off before any modelling (SURVEY-METHOD.md).
- The client's own photos are the truth; they outrank judges and assumptions.
- No heavy Blender work (bakes, Cycles renders) on Jack's 8 GB Mac: RunPod, with the cost approved first.
- No cloud spend until the model passes the matched-view self-check and Jack signs it off.
- Two builds of every site: "today" (1:1) and "clean" (fixed space only, the base for proposals).
- Benchmarks: BENCHMARKS.md (Airbnb modelled walkthrough is the aim; kogu's bedroom for the film tier).
- Full-quality VR is Unreal streamed from a cloud GPU to the Quest; the baked browser build is the fallback.
- Three judges (Sonnet) after every output, checked against the client's photos.

## Best-tool authoring and explicit Unreal omissions — Jack, 4 November 2026
Read [BUILD-ENGINE-RULE.md](BUILD-ENGINE-RULE.md) before any build stage. It applies to every element without exception by category: if it is better built in Unreal, build it directly there; Blender is not a required first step. Every preview, report and handoff must name anything missing/simplified because it is deferred to Unreal, explain the specific benefit and intended replacement, and distinguish planned work from visually verified results. Carry this rule into every agent brief.
