# Resume point

## 3 Nov 2026, ~00:30 (paused for Jack's Codex test)
- PLAN.md is the anchor: re-read it first.
- Round 2 (Jack's 48 marks + the front hall 1.65 m → 1.80 m + the front door hardware + the bedroom-1 walk-test fault) was
  paused mid-way: about 30 of 52 findings fixed; house-wip holds an UNGATED 00:14 publish (walk test and shell fail; round-1 backup in the scratchpad house_backup_r1). Status: renders/house-build/first-build/round-2/STATUS.md (written by the agent at
  the pause); grouped work list: round-2/MARKS-GROUPED.md. Resume by re-running the round on what STATUS.md says is left.
- Viewer h34 is live: room culling (src/house/cull.js), plant colours restored, presets on the marking tool, body radius 0.18.
- Next after round 2: the static merge for headset speed (Quest at 7–10 fps; needs `gl caps multi_draw` from a Quest log), then
  the cloud light bake, then Unreal look-dev stills (£10 cap).
- Waiting for the weekly reset (Fri 7 Nov ~22:00) before the next build: adopt Codex's furniture kit, viewer light (AO + window daylight), branded loader, in-viewer furnishing (PLAN change log 3 Nov).
- Usage rule: house work stops at 90% of the weekly card (78% at 00:30 on 3 Nov; resets Fri 7 Nov ~22:00).
- Codex is running its challenge from ~/Desktop/23 Battle Road; don't run Blender while it does.

## 2 Nov 2026, 22:45 (Jack quit the app to fix a UI bug)
- PLAN.md is the anchor (re-read it first). Round 1 of the three spaces (new kitchen-diner, lounge, front garden) is done and
  published to house-wip; report in renders/house-build/first-build/round-1/ (FAULTS.md, HERO.jpg). Jack is walking it and
  answering a six-question form (dining chairs, TV unit, plants, blank print, garden edge, pendant heights).
- Next: the fix round on Opus 5.5 (Jack's answers + the open round-1 faults), then Unreal look-dev stills within the £10 cap.
- Usage rule this week: house work stops when the usage card reads 90% (10% kept for website work). Card at 73% at 22:40.
- Restart the headset server after reopening: `python3 tools/https-serve.py 8443` from this folder (links: /w/ review, /p/ preview).
  The game server (8444) runs on its own from ~/Desktop/23 Battle Road Game.
- Codex challenge folder: ~/Desktop/23 Battle Road (sealed-claude-plan/ holds PLAN.md and AIRBNB-METHOD.md).

## Earlier: 1 Nov 2026, about 21:45 (Mac restart)

Everything below is saved on disk. Nothing was running when the Mac restarted: both build jobs were stopped cleanly, and
the servers and Blender were closed.

## Where the house build is
- **2 Nov 2026, ~06:30 (furnishing job):** both versions FURNISHED and published to `assets/sites/house-wip/` (walk at
  https://192.168.1.118:8443/w/, Furnished/Unfurnished switch hides every `furnishing: true` node). Read
  `renders/house-build/first-build/furnish/MORNING.md` first: what was built, frames per room (r3 = final), what was left
  out (coats, tiles in wet rooms, shower screens, sheers...), spec questions, lessons F17-F37, gate results, not verified.
  All build gates PASS; `lessons.py gate --site house-wip` FAILS on F34 (rafter ends still visible at the stairwell wall head
  from the landing, two fixes tried in hb_finish.py 1b2) and F36 (decorative book sets far too small). Fix those two first.
  Pipeline: tools/house/hb_furnish.py (library + ADAPT + lived-in + validator), hb_services.py, tools/library/cloth_soft.py,
  tools/library/test_sheet.py; plan assets/sites/house/spec/furnishing_plan.json; library ~/Desktop/garden-scans/asset-library/.
- Next: Jack's morning review of the furnished house (both ways), then the open items in MORNING.md ("left out"), then
  G6 colour / lighting look, Quest frame-rate check on the headset, Unreal G8b.
- Spec v1 signed off, with errata 1 and 3, addendum 2 (lived-in layer), and Jack's decisions:
  `assets/sites/house/spec/SIGNOFF.md`. Before = the house today (as_built_now); After = approved 2B finished.
- SHELL READY (WORKFLOW G5b): the automated checks PASS on both versions (`assets/sites/house/*_shell.json`, about
  20:10), and the integrity gate passes. NOT done: the room-by-room walk inspection write-up
  (`renders/house-build/first-build/shell/SHELL_READY.md`; frames in `shell/before` and `shell/after`), and refreshing
  `assets/sites/house-wip/` (still the 17:10 copy). Then STOP for Jack's walk-through before furniture.
- After the shell: furniture/fittings/soft items to the bar (library first: BlendKit in Jack's live Blender, Poly Haven;
  cloth sim for soft items), lived-in layer, G5c FINISHED HOUSE gate, outside colour tuning, Quest budget + KTX2 (no-admin
  install route needed), refresh house-preview. Then Unreal G8b look-dev (GBP 10 total cap).
- Stop-gap: `tools/house/fix_glb_textures.py` removes sourceless textures (CORRECTIONS-LOG 190) before publishing GLBs.

## Overnight 1-2 Nov (Jack asleep)
- Shell job: finishing the SHELL READY walk fixes, logging each as a lesson, then hands over and quits Blender.
- Furnishing job: phase A (asset plan + downloads, no Blender) now; phase B (Blender) only after the main session says
  "GO PHASE B" once the shell job has finished. Report: renders/house-build/first-build/furnish/MORNING.md.
- Viewer job: Furnished / Unfurnished switch (hides `furnishing: true`), cache h24.
- Lessons loop: tools/review/lessons.py + FIRST-PASS.md (read before every round and fix).

## Where the viewer work is
- Done and tested earlier: Hide doors ("No doors" on the wrist), Before = today (`beforeAfter()` in `src/house/viewer.js`).
- In progress when stopped (`src/house/viewer.js`, `modes.js`, house.html at h18; screenshots `renders/house-build/viewer/r7_*`):
  `?mode=review` with the marking tool, Fast walk, 4 ft default height applied at VR start, right-trigger teleport, the
  wrist "Go to" rooms menu. Its last note: "Height 4 ft" and "Fast on" working, the Go to menu next. Needs finishing and
  verifying (xrsim + walk test), and the /marks save check for site=house.

## After restarting the Mac
1. Open the Claude app and this session.
2. Ask Claude to "resume from RESUME.md". It restarts the headset server (`python3 tools/https-serve.py 8443`, run from this
   folder) and the two jobs: finish SHELL READY, and finish/verify the viewer controls.
3. Open Blender only when the furniture step starts (BlendKit is installed and logged in; the connector auto-starts).

## Links (once the server is back)
- Work in progress: https://192.168.1.118:8443/w/  · Preview: https://192.168.1.118:8443/p/
- Room planner: https://192.168.1.118:8443/plan/  · Room scan: https://192.168.1.118:8443/scan.html
- Game (separate session): https://192.168.1.118:8443/game.html

## Key files
WORKFLOW.md (gates G1b, G2b, G5b, G5c, G8b), CORRECTIONS-LOG.md (to row 191), DETAIL-CHECKLIST.md, STUDIO-MEMORY.md,
`~/Desktop/23 Battle Road - First Build Spec/`, `~/Desktop/garden-scans/asset-library/` (README, SOURCES, LIBRARY),
`~/Desktop/Plan-to-3D Studio Plan/`, `~/Desktop/23 Battle Road - Build Sequence Benchmark/PRODUCT-BRIEF.md`.
