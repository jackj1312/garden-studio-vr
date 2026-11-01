# Resume point — 1 Nov 2026, about 21:45 (Mac restart)

Everything below is saved on disk. Nothing was running when the Mac restarted: both build jobs were stopped cleanly, and
the servers and Blender were closed.

## Where the house build is
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
- Work in progress: https://192.168.1.131:8443/w/  · Preview: https://192.168.1.131:8443/p/
- Room planner: https://192.168.1.131:8443/plan/  · Room scan: https://192.168.1.131:8443/scan.html
- Game (separate session): https://192.168.1.131:8443/game.html

## Key files
WORKFLOW.md (gates G1b, G2b, G5b, G5c, G8b), CORRECTIONS-LOG.md (to row 191), DETAIL-CHECKLIST.md, STUDIO-MEMORY.md,
`~/Desktop/23 Battle Road - First Build Spec/`, `~/Desktop/garden-scans/asset-library/` (README, SOURCES, LIBRARY),
`~/Desktop/Plan-to-3D Studio Plan/`, `~/Desktop/23 Battle Road - Build Sequence Benchmark/PRODUCT-BRIEF.md`.
