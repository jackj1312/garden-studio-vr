# Mandatory for every agent — 6 November 2026

This rule applies to Codex, Claude and any other agent used on Garden Studio. Read this master at the start of relevant work. Before each milestone/handoff, carry every new tool, feature, owner detail, device control, workflow, skill/MCP dependency, fix and prevention rule into the benchmark. Do not wait for Jack to repeat it. This is an instruction-based maintenance rule; it cannot force an unrelated agent that has never received these instructions.

1. Read the current Desktop release before editing. Reconcile it with the active worktree's `docs/benchmark/`; do not overwrite a newer publication from another agent.
2. Update REQUIREMENTS/PROJECT-BRIEF and COVERAGE-AUDIT with stable IDs, precise behavior, current vs requested status and the check proving it. Add generic tooling to the allowlist in `tools/benchmark/publish.py`; include new source inputs only when they are original/owner-authored and safe for a blind run.
3. Use the established lessons workflow before fixes. Publish BOTH canonical/live and active-worktree FIRST-PASS, CORRECTIONS-LOG and DETAIL-CHECKLIST snapshots. Keep divergent entries and origins; never merge unrelated same-numbered findings blindly. Map new neutral prevention rules to acceptance checks. Historical open status is not the new entrant's own defect status.
4. Add a dated CHANGELOG line saying what changed and why, agent and affected requirement IDs. Update the illustrated pipeline section/status/picture and publish its HTML/PDF.
5. Run `python3 tools/benchmark/publish.py --check`, then `python3 tools/benchmark/publish.py --publish`. This refreshes the Desktop docs, common tools/skills, lesson snapshots, source availability and hashes. No symlinks to completed models/results; no credentials or private uploads. Resolve any concurrent-master change instead of forcing an overwrite.
6. Verify published manifest hashes and required files using `--verify`. Read the prompt and any changed requirements before reporting. Commit small local changes; never push.

## Freeze each test
A run copies the published pack into its own `benchmark-input/`, hashes original sources actually read and records the release ID. It never reads a later master revision silently. Improvements go to the master for future runs; an existing run changes scope only on Jack's instruction. Record provider/model/reasoning/tools, elapsed time/cost/usage where observable and hardware. Keep results in a separate folder. Freeze and PRESENT before any prior comparison result is read.

## Avoid contamination
Maintainers may inspect current production work to extract neutral requirements; contestants must not. Never place previous model files, render thumbnails, outcome rankings, build plans, scoreboards or curated competitor studies inside this master. Generic library thumbnails are allowed. Lessons are explicitly allowed by Jack, including Claude's original document. Shared code is an intentional common input; architecture/placements must still be independently derived.

If a future clean-room test forbids code reuse, create a separately named protocol with Jack's approval. Do not mix it with this shared-tools protocol and claim comparable scores.

Current publishing checkout: `/Users/Jack/Documents/Codex/2026-11-03-go-to-garden-studio-vr-folder/studio`. If working in another checkout, reconcile and carry over `docs/benchmark/` and `tools/benchmark/publish.py` before publishing from it. Do not run a stale publisher over newer Desktop content.
