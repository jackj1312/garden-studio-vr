# readers: architect PDFs to plan-data v2

Stage 1 of `BENCHMARK-REBUILD-PLAN.md`. Deterministic, house-agnostic readers of vector architect sheets (AutoCAD-plotted
PDFs). Site values exist only in `tests/fixtures/`.

## Run

```
PY="/Users/Jack/Garden Studio VR/.venv-benchmark/bin/python"     # pymupdf, numpy, shapely, cv2, pytest
"$PY" read_house.py "<pdf-dir>" --out "<out-dir>"                # about 5 s for four A1 sheets
"$PY" -m pytest -q -p no:cacheprovider tests                    # add -s to print the truth difference table
```

The command writes these files. **They are candidates for review, not check-ready plan-data** (a run on 10 Nov 2026
found the file fails the checks' schema on its own: sources without `id`, rooms without `id`/`polygon`, walls without
`base_m`/`height_m`; elevation outlines include stone surrounds, section apexes follow the rafter line, drawn views carry
no `version`/`storey`). A run's own builder writes plan-data from these candidates plus confirmed edits and runs the
schema check on it first (lessons/extra/2026-11-10-cad-upgrade.md).
- `plan-data.json`: schema `garden-studio/plan-data/2`. It holds `sources[]` (the register), `drawn_views[]`, the
  `versions.before/after` storeys (one ceiling plane per storey, D10), walls, openings, rooms, inventory and `roofs[]` (After),
  plus `conflicts[]`, `questions[]` and `scale_check`.
- `readings.json`: every per-view reading in sheet points, for checks and overlays. It covers dimensions with residuals,
  door arcs with circle fits, section levels, profiles and apexes, elevation outlines with pane counts, the roof graph,
  and the view registration.

## Modules

| module | reads |
|---|---|
| `pdfvec.py` | exact vectors: segments with weight and colour, Bezier samples, fills, words, text lines with direction |
| `sheet_views.py` | title block, views and their scales, scale bars, north arrow, section markers and cut lines |
| `dims.py` | written dimensions linked to arrow-tipped dimension lines (measured, residual), `WxHmm high` labels, worded values (e.g. `1550` beside `ashlar wall`) |
| `source_register.py` | sha256, readability, drawing number and revision. The latest revision of each base number is `current` |
| `read_plans.py` | wall-face pairs, openings (gaps), door swings by circle fit (hinge = centre), room labels, scale check |
| `read_roof_plan.py` | members, V nodes, ridges, hips, valleys, valley heads and eaves as a graph with kinds; rafter direction and spacing per bay; labels |
| `read_sections.py` | `NNNN ffl to ...` levels, written and drawn; GF FFL datum; roof profile polyline; apexes, eaves and pitches |
| `read_elevations.py` | opening outlines, lights and leaves (rail-to-rail mullions), sill and head, hip apex x (end-on ridge-tile cap) |
| `assemble.py` | plan frame, view registration (section markers refined by wall lines; wall lines alone where no markers), section-to-roof matching, D5 decisions |
| `lidar_fit.py`, `site_frame.py` | optional site frame: footprint fit to LiDAR nDSM; site-plan buildings, road, spot level |
| `read_house.py` | the CLI |

## Guarantees

- **Deterministic.** Re-running gives byte-identical JSON: keys are sorted, metres are rounded to 1 mm, there are no
  timestamps, and every list is sorted. `test_deterministic_rerun` checks this.
- **No typical values.** A value that cannot be read becomes a `questions[]` entry, never a default.
- **Every two-source value is compared.** It appears in `conflicts[]` with both values, its `status`
  (`agree`/`conflict`), the decision and the rule.
- **Computed cross-checks.** The scale residual is checked against written dimensions. Section floor-to-ceiling is
  checked against the written level. Elevation hip-apex spacing is checked against roof-plan ridge spacing
  (the 23 Battle Road residual is -3 mm). Section apex spacing is checked against ridge spacing.

## D5 precedence

When sources disagree, the higher one wins:

latest revision > written dimension > section > elevation > plan > notes/planning statement

Photos win for anything as built, and the owner's tape wins at its station. Those two come from the run, not from these
readers. Superseded revisions are registered but not read for geometry.

## Frame

Plan frame, in metres: x runs to the sheet's right and y towards the sheet's top. z = 0 is the GF FFL read from the
sections. The origin is the corner (min x, max y) of the heavy wall-face runs of at least 1 m on the After GF plan, and is
reported in sheet points. Other views are registered to that plan. Site rotation is applied only if a north arrow is read.
Otherwise a question is raised; the 4915 sheets have no readable arrow on the plan sheets. The tests convert to the truth
frame through the fixture.

## Limits (honest)

- **Walls are candidates** (`candidate: true` in plan-data). They are bands of paired heavy faces (all weights
  >= 0.45 pt), joined across openings and closed at junctions: an L-corner runs to the outer face, a T to the centreline.
  Thickness classes are stud 60-110, internal 110-200, external 250-360 and thick 360-450 mm. Against the truth, the
  median endpoint difference is 0.17 m After and 0.88 m Before. The Before truth includes as-built/owner walls that are
  not on 4915.1, and dash-dot boundary lines still split the party wall. **The 2D gate must confirm every wall before
  it is built from.**
- **Plan openings** are wall-band breaks of at least 450 mm. They are matched to elevation outlines by POSITION along the
  facade. Each elevation is registered to the plan by matching opening centres (`plan_registration` in readings); width
  is only a 30% sanity bound. Sill and head come from the elevation. The elevation datum is the threshold of the tallest
  door, and its offset from the section FFL is recorded as a `z_datum_offset_mm` conflict (D5: section wins). Elevations
  with no door outline (e.g. 4915.2B front) give no sill or head; a question is raised.
- **Roof plan.** Hip and valley heights are computed: ridge apex height minus the perpendicular run x tan(pitch), with
  the pitch taken from the matched section. A valley between parallel ridges is the intersection of the two slopes (a
  flat valley), so it is no longer the drawn stub. Its extent is the overlap of the two ridges, which can overrun where
  a valley meets an older roof. Ridge heights exist only where a section cut reaches the ridge. Existing members drawn
  with the same lines as removed ones are not told apart.
- **Sections.** Labels other than `NNNN ffl to ...` are not read, and dimension chains in sections use arrows only
  where drawn. The `2253,23 ffl to top of plate` label is kept as written but unchecked: its lines were not identified.
- **Elevations.** Apexes are found only where the end-on ridge-tile cap is drawn.
- **Site frame** (`--dsm --dtm --lidar-init E,N --theta-range a,b --party-side left --site-plan SP.pdf --sp-match m.json`).
  `lidar_fit.py` fits the GF external-wall footprint to the nDSM; `site_frame.py` reads the site-plan buildings, road
  lines and spot level. Both are adapted from run 02 with paths and constants as arguments. The fit is only as good as
  the candidate-wall footprint: on 23 Battle Road it reached theta 70.25 deg, score 0.39, against run 02's hand
  footprint at 68.5 deg, score 4.33, so it is not yet trustworthy.
