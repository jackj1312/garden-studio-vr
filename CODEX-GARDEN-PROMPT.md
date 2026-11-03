You are working in Jack's live studio project: `~/Garden Studio VR` (this folder). Before anything else, tell me in one line
to switch you to your highest reasoning level, and wait until I say it's done.

I already have a first iteration of a garden design tool in this folder. Find it first (the `codex/*` branches, the progress
files, any garden or site editor code), then add to it and improve it. Don't start a second tool.

## What I want
A garden design tool on my computer where I draw the garden myself, like a simple CAD for landscaping. Fully editable,
everything by mouse, with clean shapes:
- **Draw anything garden-related:** patios, paths, lawns, gravel, decking, walls (straight and curved), retaining walls,
  raised beds, sunken areas, fire pits, steps, fences, edging, planting beds.
- **Clean curves, always.** When I draw a rough curve it snaps to a smooth one (arcs and smooth splines, never wobbly lines).
  I can drag points and handles to adjust it afterwards.
- **Shapes by click and drag:** click and drag outward to make a perfect circle (or square/rectangle), then resize it by
  dragging its edge or typing a size.
- **Levels:** select any shape and raise or sink it (type a depth or drag up/down). A sunken circle becomes a sunken pit with
  a wall round it; add steps down into it with one action; raised shapes become raised beds or walls with a height and a coping.
- **Edit everything:** select, move, rotate, resize, copy, delete, undo/redo, change material (paving pattern, brick, render,
  timber sleepers, gravel, lawn) and planting (choose a palette for a bed).
- **See it as I go:** a plan view to draw in and a 3D view of the same design, side by side or switchable, in our garden with
  the house; the design opens in the house walkthrough and the headset too.
- **In my Quest too:** design standing in the garden. The toolkit lives on a panel on my LEFT hand (pick a tool, shape,
  material, depth, steps, undo); my RIGHT controller draws on the ground with the marking tool we already have (`src/marks.js`:
  point at the ground, hold the trigger and sweep). A swept stroke becomes a clean shape: a rough curve snaps to a smooth
  wall/edge/path, a closed loop becomes a patio or bed, a trigger-and-drag outward makes a perfect circle or square. Then grab
  points or handles with the ray to adjust, and raise or sink a selected shape with the thumbstick. Everything I make in the
  headset is the same design file as on the computer, and the reverse.
- It saves the design to a file in the project, so I can come back and keep editing.

## Later, not now
Once my base design is down, an agent will polish it and turn it into precise measured drawings for an architectural
drawing. So keep the design data clean and exact underneath (every shape stored as real geometry in metres: centre, radius,
corners, curve control points, levels, materials), ready for that step.

## How to work
- Write `GARDEN-PLAN.md` first (short: what my iteration already does, what you'll add, how each part is checked) and show it
  to me. Re-read it at the start of every stage, before every fix, and before every report.
- Work on a git branch `codex/garden-tool`; commit in small steps; never push.
- Follow `CLAUDE.md`'s rules. Log every mistake with its cause before fixing it
  (`python3 tools/review/lessons.py add --site house-wip --round codex-garden ...`).
- My Mac is an 8 GB M1 Air: one heavy job at a time, no Cycles renders or bakes. Don't break the house walkthrough, the
  furnishing system or the planner. Don't change our front garden's existing brickwork, paving or layout unless I ask.
- Add the garden tool to the pipeline document (`docs/pipeline/`) and publish it with `tools/docs/publish_pipeline.sh`.
- When it's done, show me how to use it in a short note with a few screenshots, and give me the link to open it.
