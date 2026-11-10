# plan2d — reading vector architect PDFs exactly (house-agnostic)
Added 2026-11-08 by Claude (Opus 5.5) from benchmark Pass 1 run 02. Optional tools; no property values inside.
- `pdfvec.py <sheet.pdf> <out.json>` — every line (with pen width), word and sampled arc of page 1, in displayed page points
  (page rotation applied; y down). At 1:50, 1 pt = 17.639 mm.
- `axlines.py <out.json> x0 y0 x1 y1 [width]` — axis-aligned wall-cut lines in a region (the 0.72 pt pen is usually the cut).
- `plotvec.py`, `crop.py` — inspect a region as vectors or as the rendered sheet with a labelled point grid
  (`crop.py` takes a PDF path or a sheet number in `$DRAWINGS_DIR`, and a grid pitch).
- `faces.py <sheet.pdf> x0 y0 x1 y1 [min_width]` — heavy axis-aligned strokes straight from the PDF (every pen at or above
  the width, strokes crossing the box kept, touching spans merged). Read faces on at least three independent walls
  before registering one storey or view to another, never one face pair.
- `surround.py` — `frame_inside(lines, outline)`: an elevation opening inside a stone surround takes its sill and head
  from the frame lines inset inside the outline, not from the surround (readers otherwise read sills low, heads high).
- `arcswing.py` — door hinge/side from a circle fitted through the drawn arc (see its docstring for why).
Tests: `tests/test_plan2d.py` (synthetic sheet; run by `publish.py --check`). faces.py and surround.py added
2026-11-10 by Claude (Opus 5.5) from the 23 Battle Road CAD upgrade.
Check: run the plan back over each sheet and measure every drawn wall line against the model's faces (split faces at
openings, add jambs; classify reveals, text underlines, dashed heads AT openings; flag dashed lines elsewhere inside the house).
