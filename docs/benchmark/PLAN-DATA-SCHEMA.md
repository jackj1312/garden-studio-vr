# Plan data schema (`plan-data.json`) — version 1

Jack, 7 November 2026. One JSON file that describes a reconstructed property as measured data, so it can be checked by
machine (`shared-tools/checks/`) and compared like for like. It works for any house. Export it at GATE 1A (2D plan) and
again at GATE 1B (3D scene), from the same data your scene is built from. A worked example (a synthetic house, not this
property) is `shared-tools/checks/example-plan-data.json`.

## Conventions
- **Units: metres** (angles in degrees where named `_deg`). Dates are `YYYY-MM-DD`.
- **Site frame:** one right-handed frame for the whole site: `x` east, `y` north, `z` up. You choose the origin (say what
  it is in `frame.origin`) and the height datum (`frame.z_datum`, e.g. "ground floor FFL = 0" or "metres AOD"). Say which
  north you used (`frame.north`: grid, true or magnetic, and from which source). Plan points are `[x, y]`.
- **Absolute vs storey heights:** `z_m`, `base_m`, `level_m` and stair `base_m` are absolute heights in the site frame.
  Opening `sill_m` / `head_m`, room `ceiling_m` and storey `ceiling_m` are measured up from that storey's floor level (FFL),
  the way drawings dimension them.
- **ids** are unique within a version and never reused for a different thing between Before and After.
- **Every element cites its evidence:** `source` (a `sources[]` id, or a list of ids) and `source_date` (the capture or
  drawing date of that source; a list when `source` is a list). "assumed", "estimate", "typical" and similar are not
  sources. Add `assumed: true` (and say why in `note`) only for something you must build without direct evidence; it is
  reported, and you must present it as an assumption.

## Top level
```json
{
  "schema": "garden-studio/plan-data/1",
  "property": "23 Example Road",
  "units": "m",
  "frame": {"x": "east", "y": "north", "z": "up", "origin": "...", "north": "grid (site plan 1:500)", "z_datum": "ground floor FFL = 0"},
  "sources": [{"id": "S-4915.1", "file": "4915.1 ... .pdf", "type": "drawing", "date": "2022-03-30", "areas": ["house"], "note": "existing, superseded by ..."}],
  "versions": {"before": { ... }, "after": { ... }}
}
```
`sources[]` is your dated source register in short form: `id`, `file`, `type` (drawing, photo, video, frame, scan, lidar,
owner-note, measurement), `date`, optional `areas` (e.g. "front garden", "porch") and `note`. A video frame may be its
own source (`type: frame`, `file: "20494.mp4@63.0s"`). The prepared register `inputs/prepared/source-register.json` lists
every supplied file with its capture date.

## A version (`before`, `after`)
```json
{"storeys": [], "walls": [], "openings": [], "rooms": [], "stairs": [], "slabs": [], "objects": [], "inventory": []}
```

### storeys[]
`id`, `name`, `level_m` (finished floor level, absolute), `ceiling_m` (typical ceiling height above FFL). Include the
loft or any part-storey as its own storey.

### walls[]
A wall is a straight piece with a centreline and a thickness. Curved walls: several short pieces.
| field | meaning |
|---|---|
| `id`, `storey` | unique id; the storey the wall belongs to |
| `start`, `end` | centreline end points `[x, y]`; the centreline is the middle of the finished thickness |
| `thickness_m` | finished face to finished face (plaster to plaster, or brick face to plaster) |
| `base_m` | absolute height of the wall's bottom (at or below the storey floor; foundations may go lower) |
| `height_m` or `top_profile` | constant height, or `[[u_m, top_z_m], ...]`: absolute top height at distance `u` from `start` (gables, raking tops, stepped walls) |
| `kind` | `external`, `internal`, `party`, `stud`, `chimney_breast`, `boundary`, `garden`, `retaining`, `parapet`, `dwarf`, `screen` ... |
| `building` | `house` (the property, default), or the neighbour/outbuilding it belongs to (e.g. `No. 21`, `shed`) |
| `free_ends` | optional `["start"]`, `["end"]` or both: an end that really stops in space (a nib, a wall beside an open stair). Every other end must meet another wall. |
| `material`, `colour`, `note`, `source`, `source_date` | finish and evidence |

Draw the wall under and over every window as part of its wall (one wall with the opening cut in it). Do not leave a
window floating in a gap between two wall pieces.

### openings[]
| field | meaning |
|---|---|
| `id`, `wall` | host wall id (rooflights: `slab` instead of `wall`) |
| `kind` | `door`, `window`, `opening` (no leaf), `french_door`, `bifold_door`, `sliding_door`, `garage_door`, `rooflight` |
| `offset_m` | distance along the host wall from its `start` to the near edge of the structural opening |
| `width_m` | structural opening width |
| `sill_m`, `head_m` | sill and head heights above the storey FFL (doors: sill 0 or the threshold height) |
| `swing` | hinged leaves: `{"hinge": "start" \| "end" \| "both", "side": "left" \| "right"}`. `hinge` is the jamb nearer the wall's start or end; `side` is the side of the wall the leaf opens into, looking from `start` to `end`. Other leaves: `{"type": "sliding" \| "bifold" \| "none"}`; windows: `null` |
| `leaves` | number of leaves (default 1); `external` true for doors to the outside |
| `full_height` | true only for an opening that genuinely runs to the top of its wall (no lintel or wall above) |

### rooms[]
| field | meaning |
|---|---|
| `id`, `name`, `storey` | `name` as labelled on the drawing (Bed 1, Cpd, Landing) |
| `polygon` | closed polygon of the room's internal finished faces `[[x, y], ...]` (do not repeat the first point) |
| `kind` | `room` (default), `cupboard`, `landing`, `circulation`, `stair`, `void` (not walkable), `outside` |
| `doors` | ids of every door/opening on this room's boundary |
| `drawn_door_count` | optional: how many doors the drawing shows for it (checked against the model) |
| `open_to` | rooms or stairs this room is open to with no wall between (open-plan zones, a landing open to the stairwell) |
| `ceiling_m` | ceiling height above the room's floor; sloped ceilings `{"min_m": eaves, "max_m": ridge}`; `ceiling: "open"` for double height |
| `floor_offset_m` | optional step relative to the storey FFL (sunken or raised floors) |

### stairs[]
| field | meaning |
|---|---|
| `id`, `from_storey`, `to_storey` | the stair rises from `from_storey` to `to_storey` |
| `flights[]` | each `{"start": [x, y], "direction": [dx, dy], "width_m", "risers", "rise_m", "going_m", "base_m", "waist_m"?}` |
| `landings[]` | `{"polygon": [...], "z_m": landing surface height}` for half or quarter landings |
| `headroom_min_m` | default 2.0; a lower value (loft conversions) must be justified in `note` |

A flight's `start` is the centre of its first (bottom) riser line; `direction` points UP the flight, horizontally;
`base_m` is the absolute height the flight starts from. With `risers` n, the treads are 1 .. n-1 and the n-th riser
arrives on the landing or floor, so the flight's plan length is `(n - 1) x going_m`. Winders: model as short flights at
their angles, or several one-riser flights.

### slabs[]
Floors, ceilings and roofs as plan polygons: `id`, `kind` (`floor`, `ceiling`, `roof`), `storey`, `polygon`, `holes`
(stairwells, chimneys, rooflight voids), `z_m` (absolute height of the slab's TOP surface; floors: the storey FFL),
`thickness_m`, optional `underside_plane: [a, b, c]` (underside height = a·x + b·y + c, for sloped ceilings and roofs).
A storey's ceiling is either its own `ceiling`/`roof` slab or the `floor` slab of the storey above. Required at GATE 1B.

### objects[]
Everything else that is built: fitted items, chimney breasts drawn as objects, balustrades, and the whole outside (paths,
kerbs, road, pavement, beds, lawn, fences, hedges, walls drawn as objects, steps, structures, trees).
`id`, `kind`, optional `storey`, and one of `footprint` (polygon), `line` (polyline, with `thickness_m`) or `position`
(`[x, y]`, with `size_m`); `base_m`, `height_m`, `colour`, `area` (e.g. "front garden"), `blocks` (true if it stops people
walking through; default true for fitted kinds), `source`, `source_date`. Balustrades, guards and rails (`kind`:
`balustrade`, `guard`, `rail`, `screen`) given as a `line` count as room edges for the closure check.

### inventory[]
The room inventory read from the drawing labels: `{"label": "Bed 1", "drawing": "4915.1", "room": "R-bed1"}`. Every
labelled room, cupboard, landing and stair appears once and points to a room id.

## Overlay residuals (`overlay-residuals.json`)
One file per gate (or several) with every solved photo, video frame and drawing registration:
```json
{"schema": "garden-studio/overlay-residuals/1",
 "images": [{"id": "20503", "source": "S-20503", "kind": "photo|frame|drawing", "width_px": 4000, "height_px": 3000,
   "native_width_px": 4000, "native_height_px": 3000, "solve": {"method": "PnP from 14 marked points", "rms_px": 3.2},
   "points": [{"id": "porch-ridge", "observed": [1234.5, 456.0], "projected": [1236.1, 452.9]}],
   "edges": [{"id": "front-eaves", "element": "W-G-front", "max_px": 9.5}]}]}
```
Measure at the source's full (native) resolution. `points` are the control points used to solve the camera (or to
register a drawing sheet); RMS is computed from them (or taken from `solve.rms_px` when only that is available). `edges`
are structural edges of the model projected into the image, each with its worst residual (`max_px`) or every sampled
residual (`residuals_px`). Limits: **RMS ≤ 8 px, every edge ≤ 15 px**.

## Running the checks
```
python3 shared-tools/checks/run_checks.py plan-data.json --gate 1A --register inputs/prepared/source-register.json
python3 shared-tools/checks/run_checks.py plan-data.json --gate 1B --overlays overlay-residuals.json --register inputs/prepared/source-register.json --json checks-1B.json
```
Exit code 0 means no FAIL. At GATE 1A slabs and overlays may be missing (reported as warnings); at GATE 1B they are
required. A failed check is fixed at its cause and re-run; present the JSON report with the gate.
