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

## STUDIO-MEMORY.md — read it often, add to it always (Jack, 31 Oct 2026)
- Read it at the start of every session, again before every gate (its section for that gate), and before any
  decision that costs money or Jack's time. Not once: regularly.
- Add a dated line the moment something worth keeping is learned. Every project builds from the last.

## Standing rules
- Plan first: measured plan and elevations signed off before any modelling (SURVEY-METHOD.md).
- The client's own photos are the truth; they outrank judges and assumptions.
- No heavy Blender work (bakes, Cycles renders) on Jack's 8 GB Mac: RunPod, with the cost approved first.
- No cloud spend until the model passes the matched-view self-check and Jack signs it off.
- Two builds of every site: "today" (1:1) and "clean" (fixed space only, the base for proposals).
- Benchmarks: BENCHMARKS.md (Airbnb modelled walkthrough is the aim; kogu's bedroom for the film tier).
- Full-quality VR is Unreal streamed from a cloud GPU to the Quest; the baked browser build is the fallback.
- Three judges (Sonnet) after every output, checked against the client's photos.
