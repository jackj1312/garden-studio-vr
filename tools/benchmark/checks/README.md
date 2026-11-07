# Shared plan-data checks

Generic, house-agnostic machine checks for any reconstructed property. They read a run's `plan-data.json`
(schema: `PLAN-DATA-SCHEMA.md` at the root of the benchmark folder) and print PASS / WARN / FAIL with the element ids
and coordinates of every fault. Pure Python 3: no numpy, no Blender, nothing to install.

```
python3 run_checks.py plan-data.json --gate 1A [--register ../../inputs/prepared/source-register.json]
python3 run_checks.py plan-data.json --gate 1B --overlays overlay-residuals.json [--register ...] [--json checks.json]
python3 run_checks.py plan-data.json --version before --quiet      # only problems, one version
python3 tests/test_checks.py                                       # the unit tests (synthetic houses)
```
Exit code: 0 no FAIL, 1 at least one FAIL, 2 unreadable or invalid plan data.

## What is checked (each per version: Before and After)
| group | check | fails when |
|---|---|---|
| closure | `room-shape` | a room polygon has no area or crosses itself |
| closure | `room-boundary` | any part of a room's edge is not on the face of a wall that runs from the floor to the ceiling (open-plan edges need `open_to`; stairwell edges a balustrade or `open_to` the stair). Catches open stud-wall rooms, missing walls, walls stopping short, walls under windows that are missing |
| closure | `doors` | the doors found on a room's edge differ from its `doors` list or `drawn_door_count` |
| closure | `opening-fit` | an opening lies outside its wall, has no wall below its sill or no wall/lintel above its head |
| closure | `wall-joints` | a wall end does not meet another wall (gap), unless the wall is free-standing or the end is in `free_ends` |
| closure | `inventory` | a room label in `inventory[]` has no room (WARN: rooms not in the inventory) |
| closure | `floor`, `ceiling` | any point of a room has no floor under it or no ceiling/roof/floor above it (stairwells excepted) |
| circulation | `stair-rise` | risers do not add up to the storey height, or flights do not join; WARN for steep rises/short goings |
| circulation | `stair-ends` | the 0.6 m zone before the first riser or after the top riser is over a void or off the floor (a stair running the wrong way); WARN for a tight landing (under a third of the zone off the floor) |
| circulation | `headroom` | less than `headroom_min_m` (default 2.0 m) clear above the pitch line: slabs, other stairs, landings, objects |
| circulation | `stair-clash` | a stair or its end zones sit over/under another stair with less than the headroom between them |
| circulation | `door-swing` | a door leaf sweeps over a stair flight, a stair's top zone, another door's swing or a fitted item (WARN: bottom zone) |
| circulation | `door-approach` | the zone in front of a door is inside a stair flight, a fitted item or a floor hole |
| circulation | `reachable` | a room cannot be reached from outside through doors, open edges and stairs |
| evidence | `cited` | an element has no `source`, no valid `source_date`, or cites "assumed"/"estimate"/"typical"... |
| evidence | `register` | a citation does not resolve to `sources[]` (or the prepared register) or its date disagrees |
| evidence | `assumed`, `superseded` | WARN: elements marked assumed; Before elements resting only on captures older than the latest of their `area` |
| overlay | `resolution`, `rms`, `edges` | residuals not at native resolution; RMS > 8 px; any structural edge > 15 px |

Options: `--tol` (default 0.03 m, how far a room edge may sit from a wall face), `--landing` (0.6 m stair end zones).

## Files
- `run_checks.py` the runner; `plandata.py` loading, validation, derived geometry; `geom.py` 2D helpers;
  `closure.py`, `circulation.py`, `evidence.py`, `overlays.py` the checks.
- `example-plan-data.json`, `example-overlay-residuals.json`: a small synthetic house (not a real property) that passes.
- `tests/`: unit tests; `tests/synthetic.py` builds the good house and deliberately faulty ones (open room, reversed loft
  stair over the main stair, missing sill wall, object with no source, invented hedge, floor and ceiling gaps, wall gap,
  low headroom, door blocked by a stair, unreachable room, wrong door count).

These checks are a floor, not a ceiling: passing them does not prove the house is right (that needs the overlays and the
owner's review), but failing them proves it is wrong. Improvements go to the master for future runs.
