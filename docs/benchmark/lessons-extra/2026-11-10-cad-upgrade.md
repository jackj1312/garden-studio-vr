# Lessons of 10 November 2026: bringing a drawings-only CAD up to the Pass 1 standard (Claude Opus 5.5)

A neutral digest for future runs. The source run (a CAD of the house made from the architect's PDFs, then upgraded to
Gate 1A of Pass 1) stays sealed; no geometry, value or result of it is described here, only the method faults and the
rule that prevents each. Row ids are the run's own MISTAKES ids, kept so a maintainer can trace them.

## Pack faults this run found (fixed in this release)
1. **The shared environment must install every import the tests need (P01).** `requirements.txt` lacked `scipy`, which
   trimesh needs for the mesh checks; 10 of 87 check tests failed on a fresh `setup_env.sh`. Preflight: run every tool
   folder's tests in the run's own venv and stop on any import error. Fixed: `scipy` is now in `requirements.txt`.
2. **Plan overlays score only exposed wall faces (P03).** The overlay check measured each wall face over its full length,
   including the stretch buried inside the wall it meets, where a drawing never has a line; every 300 mm L-corner scored
   t/2 against the sheet. The shipped example is rendered from the model itself, so it could never show this. Fixed in
   `checks/overlays.py`; regression in `checks/tests/test_run_fixes.py`. Rule: test every check against a real
   drawing, not only against a drawing rendered from the model.
3. **A cited sloped ceiling lowers the room's ceiling (ceiling departure).** A room that takes the storey plane and cites
   a `ceiling_departure.underside_plane` now has its ceiling range from that plane, so a kneewall under the slope is not
   reported as a gap above. Fixed in `checks/plandata.py` (`room_ceiling`); regression in the same test file.

## Reading the drawings
4. **Reader output is candidates, not check-ready plan-data (P02).** The shipped reader's file failed the checks' schema
   on its own (sources without `id`, rooms without `id`/`polygon`, walls without `base_m`/`height_m`). A run's own builder
   writes plan-data from the reader's candidates plus confirmed edits, and the schema check runs on it before anything
   else.
5. **Drawn views declare `version` and `storey` (A02).** Without them the checks overlaid Before walls on After sheets and
   first-floor walls on ground-floor plans. Every drawn view states its version; every plan view states its storey.
6. **Register storeys on at least three wall-face pairs (F03).** One face pair gave a first-floor offset 1.4 pt out (about
   24 mm at 1:50), and the whole upper storey was built shifted. Read at least three independent faces that run through
   both floors (flank, wing, return) on every sheet that draws both; a conflict decision cites all of them.
7. **Elevation datums come from the drawn level-marker dashes (A07).** Datums anchored on the dpc or ground line were
   0.9 pt low. Read each elevation's FFL markers (the short dashes by the level text), every one of them, and fit the
   datum to those.
8. **Stone surrounds are not openings (A04, A06).** Readers took the outer rectangle of a surround as the window or door:
   sills read low, heads high, piers merged into the opening. Inside a surround the frame's own lines give sill and head
   (head = topmost long frame line inside; sill = topmost line of the bottom cluster, the cill nose sits lower); check the
   width against the plan opening. Doors take the jambs of their own arc. The surround stays in the model as flagged
   fabric, never deleted. Helper: `shared-tools/tools/plan2d/surround.py`.
9. **Every candidate is confirmed on the crop (A01, A03, A05).** Dashed lines along a "to be removed" note are
   demolition, not wall. Each written note (f-c, c-h) lands on exactly one opening; a door needs its own arc in its own
   gap. Party walls split at a boundary dash-dot, chimney-recess gaps, fan boxes and roofs seen from above are not walls
   or openings.
10. **Roof faces sit at tile level, not on the rafter line (A08).** Section readers that follow the heavy rafter stroke
    put every roof 70-90 mm low and call profile ends "eaves". The roof surface is the tile line; one pitch where every
    drawn slope agrees; section readings list only lines crossing the cut, with outlines beyond the cut kept separately.
11. **Reader and checker must define a feature the same way (A09).** An elevation reader that lists only ridges seen
    end-on, against a checker that counts every hip apex in the model, fails every elevation on counts. Settle the
    definition (visible apexes) before scoring; never paper over the difference.

## Gates and the owner
12. **As-built placeholders appear at every gate (R1A-2/3/4, repeated from run 02).** Items the drawings do not show as
    built (a porch, a loft conversion) appear at Gate 1A already, as flagged placeholders with their evidence level from
    the owner's notes, not deferred to a capture stage. Copied placeholders keep their drawn context, such as their steps
    (V1A-2).
13. **An unread value is a question, not a placeholder that looks like a value (R1A-5, V1A-4).** Door heads placed at the
    ceiling invented full-height doors. An unread height is a blocking question for the owner; the model carries it
    flagged. A placeholder note says exactly what it is (an upper bound, on which line).
14. **Steps come from the drawn nosings at riser levels (R1A-7/8, V1A-1).** "up N" at a door means the outside is N below
    at the threshold: tread j's top is minus the sum of risers up to j, and tread depths come from the drawn nosing lines
    parallel to the wall. Read every 'up' note (stacked 'up' / 'N' lines, 'Nno. N mm steps up'): one step per riser.
15. **Dated photos beat older drawings for garden elements (R1A-9).** A drawn element contradicted by a dated photo is a
    recorded conflict; the photo wins.
16. **Spaces with no drawn edge still need one (R1A-12).** A cupboard under the half landing is closed by the stair's top
    riser or spandrel; model that line rather than merging the cupboard into the hall.
17. **A conflict decision states only what the data holds (V1A-3).** Write the decision after the data change, never
    before; a placeholder is called a placeholder, not a decision.
18. **Freeze for review only when every FAIL is fixed or presented (R1A-1).** Each remaining FAIL is a question or a
    waiver request for the owner in the presentation.

## Acceptance checks these map to
- 1, 2, 3: `publish.py --check` runs the check tests in the pack venv (green, including `test_run_fixes.py`).
- 4, 5: `checks/run_checks.py` schema results on the run's plan-data (Gate 1A).
- 6, 7, 8, 10: the drawing overlays (`overlay.rms`, `overlay.edges`), `elevations.*` and `sections.heights`.
- 12, 13, 17, 18: the Gate 1A presentation (independent review; questions and waivers listed; conflict register).
- 14, 15, 16: the independent review (a crop of every door with an 'up' note; no shared computed check for steps yet).
- 9, 11: the independent review against the crops; 11 is open as a checker change (visible apexes only).
