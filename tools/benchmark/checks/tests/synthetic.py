"""Small synthetic houses for the check tests. Not a real property: an 8 x 6 m two-storey box with a hall stair,
optional loft stair, and deliberately faulty variants.

Plan (x east, y north, metres): external wall centrelines (0,0)-(8,0)-(8,6)-(0,6), 300 thick; internal wall x = 3.
Ground: hall (west, with the stair rising north) and living (east). First: landing (west) and bedroom (east)."""
import copy

SRC = {"source": "D1", "source_date": "2022-03-01"}
PHOTO = {"source": "P1", "source_date": "2026-10-31"}
G, F, L = 0.0, 2.65, 5.30
IN = [(0.15, 0.15), (7.85, 0.15), (7.85, 5.85), (0.15, 5.85)]


def wall(i, st, a, b, t, base, h, kind, **kw):
    d = {"id": i, "storey": st, "start": list(a), "end": list(b), "thickness_m": t, "base_m": base, "height_m": h, "kind": kind}
    d.update(SRC); d.update(kw); return d


def box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def good_house(loft=False):
    walls = []
    for st, base, h in (("G", G, F - G), ("F", F, 2.4)):
        walls += [wall("W-%s-S" % st, st, (0, 0), (8, 0), 0.3, base, h, "external"),
                  wall("W-%s-E" % st, st, (8, 0), (8, 6), 0.3, base, h, "external"),
                  wall("W-%s-N" % st, st, (8, 6), (0, 6), 0.3, base, h, "external"),
                  wall("W-%s-W" % st, st, (0, 6), (0, 0), 0.3, base, h, "external"),
                  wall("W-%s-int" % st, st, (3, 0), (3, 6), 0.1, base, 2.4, "stud")]
    openings = [
        dict(id="D-front", wall="W-G-S", kind="door", offset_m=1.6, width_m=0.9, sill_m=0.0, head_m=2.1,
             swing={"hinge": "start", "side": "left"}, external=True, **PHOTO),
        dict(id="D-hall-liv", wall="W-G-int", kind="door", offset_m=0.5, width_m=0.85, sill_m=0.0, head_m=2.05,
             swing={"hinge": "start", "side": "right"}, **SRC),
        dict(id="WIN-liv", wall="W-G-S", kind="window", offset_m=4.5, width_m=1.5, sill_m=0.9, head_m=2.1, swing=None, **PHOTO),
        dict(id="D-bed", wall="W-F-int", kind="door", offset_m=0.6, width_m=0.8, sill_m=0.0, head_m=2.0,
             swing={"hinge": "start", "side": "right"}, **SRC),
        dict(id="WIN-bed", wall="W-F-E", kind="window", offset_m=2.0, width_m=1.2, sill_m=0.9, head_m=2.1, swing=None, **PHOTO),
    ]
    rooms = [
        dict(id="R-hall", name="Hall", storey="G", polygon=box(0.15, 0.15, 2.95, 5.85), ceiling_m=2.4, doors=["D-front", "D-hall-liv"], **SRC),
        dict(id="R-living", name="Living", storey="G", polygon=box(3.05, 0.15, 7.85, 5.85), ceiling_m=2.4, doors=["D-hall-liv"], drawn_door_count=1, **SRC),
        dict(id="R-landing", name="Landing", storey="F", polygon=box(0.15, 0.15, 2.95, 5.85), ceiling_m=2.4, doors=["D-bed"], **SRC),
        dict(id="R-bed", name="Bedroom", storey="F", polygon=box(3.05, 0.15, 7.85, 5.85), ceiling_m=2.4, doors=["D-bed"], **SRC),
    ]
    rise = (F - G) / 14
    stairs = [dict(id="ST-main", from_storey="G", to_storey="F", headroom_min_m=2.0,
                   flights=[dict(start=[0.6, 1.5], direction=[0, 1], width_m=0.9, risers=14, rise_m=rise, going_m=0.25, base_m=G)], **SRC)]
    f_hole = [box(0.15, 1.6, 1.05, 4.75)]
    slabs = [dict(id="SL-G", kind="floor", storey="G", polygon=[list(p) for p in IN], z_m=G, thickness_m=0.15, **SRC),
             dict(id="SL-F", kind="floor", storey="F", polygon=[list(p) for p in IN], holes=f_hole, z_m=F, thickness_m=0.25, **SRC)]
    storeys = [dict(id="G", name="Ground", level_m=G, ceiling_m=2.4), dict(id="F", name="First", level_m=F, ceiling_m=2.4)]
    objects = [dict(id="OB-path", kind="path", footprint=box(1.6, -3.0, 2.5, -0.15), **PHOTO),
               dict(id="OB-units", kind="kitchen_unit", storey="G", footprint=box(7.25, 2.0, 7.85, 4.0), base_m=0.0, height_m=0.9, **PHOTO)]
    if loft:
        storeys.append(dict(id="L", name="Loft", level_m=L, ceiling_m=2.2))
        walls += [wall("W-L-S", "L", (0, 0), (8, 0), 0.3, L, 2.2, "external"), wall("W-L-E", "L", (8, 0), (8, 6), 0.3, L, 2.2, "external"),
                  wall("W-L-N", "L", (8, 6), (0, 6), 0.3, L, 2.2, "external"), wall("W-L-W", "L", (0, 6), (0, 0), 0.3, L, 2.2, "external")]
        rooms.append(dict(id="R-loft", name="Loft room", storey="L", polygon=[list(p) for p in IN], ceiling_m=2.2, doors=[], open_to=["ST-loft"], **PHOTO))
        lr = (L - F) / 14
        stairs.append(dict(id="ST-loft", from_storey="F", to_storey="L", headroom_min_m=2.0,
                           flights=[dict(start=[2.35, 2.34], direction=[0, 1], width_m=0.8, risers=14, rise_m=lr, going_m=0.22, base_m=F)], **PHOTO))
        slabs.append(dict(id="SL-L", kind="floor", storey="L", polygon=[list(p) for p in IN], holes=[box(1.95, 2.5, 2.75, 5.2)], z_m=L, thickness_m=0.25, **PHOTO))
        slabs.append(dict(id="SL-L-ceil", kind="ceiling", storey="L", polygon=[list(p) for p in IN], z_m=L + 2.215, thickness_m=0.015, **PHOTO))
    else:
        slabs.append(dict(id="SL-F-ceil", kind="ceiling", storey="F", polygon=[list(p) for p in IN], z_m=F + 2.415, thickness_m=0.015, **SRC))
    inventory = [dict(label=r["name"], drawing="D1", room=r["id"]) for r in rooms]
    version = dict(storeys=storeys, walls=walls, openings=openings, rooms=rooms, stairs=stairs, slabs=slabs, objects=objects, inventory=inventory)
    return {
        "schema": "garden-studio/plan-data/1", "property": "Synthetic test house", "units": "m",
        "frame": {"x": "east", "y": "north", "z": "up", "origin": "south-west external corner centreline", "north": "grid",
                  "z_datum": "ground floor FFL = 0"},
        "sources": [{"id": "D1", "file": "drawing-existing.pdf", "type": "drawing", "date": "2022-03-01"},
                    {"id": "P1", "file": "photo-front.jpg", "type": "photo", "date": "2026-10-31"}],
        "versions": {"before": version, "after": copy.deepcopy(version)},
    }


def _v(h):
    return h["versions"]["before"]


def _get(lst, i):
    return next(x for x in lst if x["id"] == i)


def open_room():
    """First-floor stud wall stops short: landing and bedroom are not closed."""
    h = good_house(); w = _get(_v(h)["walls"], "W-F-int"); w["end"] = [3, 4.0]; return h


def missing_sill_wall():
    """Living window hosted on a head-only wall piece: no wall below the window."""
    h = good_house(); v = _v(h)
    v["walls"] = [w for w in v["walls"] if w["id"] != "W-G-S"]
    v["walls"] += [wall("W-G-S1", "G", (0, 0), (4.5, 0), 0.3, G, F, "external"),
                   wall("W-G-S2", "G", (4.5, 0), (6.0, 0), 0.3, G + 2.1, F - 2.1, "external"),
                   wall("W-G-S3", "G", (6.0, 0), (8, 0), 0.3, G, F, "external")]
    _get(v["openings"], "D-front")["wall"] = "W-G-S1"
    win = _get(v["openings"], "WIN-liv"); win["wall"] = "W-G-S2"; win["offset_m"] = 0.0
    return h


def reversed_loft_stair():
    """The loft stair is reversed (rises south instead of north) and starts beside the main stair's arrival, so it
    climbs back over the main stair: too little headroom above the main flight and its arrival zone blocked."""
    h = good_house(loft=True); v = _v(h)
    st = _get(v["stairs"], "ST-loft")["flights"][0]
    st["start"] = [0.6, 5.2]; st["direction"] = [0, -1]
    sl = _get(v["slabs"], "SL-L"); sl["holes"] = [box(0.2, 2.34, 1.0, 5.0)]
    return h


def object_without_source():
    h = good_house(); ob = _get(_v(h)["objects"], "OB-path"); ob.pop("source"); ob.pop("source_date"); return h


def invented_object():
    """A hedge built from nothing: cites 'assumed'."""
    h = good_house(); _v(h)["objects"].append(dict(id="OB-hedge", kind="hedge", footprint=box(3, -3, 8, -2.5), source="assumed", source_date="2026-11-01")); return h


def floor_gap():
    h = good_house(); sl = _get(_v(h)["slabs"], "SL-G"); sl["polygon"] = box(0.15, 0.15, 7.0, 5.85); return h


def ceiling_gap():
    h = good_house(); sl = _get(_v(h)["slabs"], "SL-F-ceil"); sl["polygon"] = box(0.15, 0.15, 5.0, 5.85); return h


def door_count_mismatch():
    h = good_house(); _get(_v(h)["rooms"], "R-living")["drawn_door_count"] = 2; return h


def unreachable_room():
    h = good_house(); v = _v(h)
    v["openings"] = [o for o in v["openings"] if o["id"] != "D-bed"]
    for r in v["rooms"]:
        r["doors"] = [d for d in r.get("doors", []) if d != "D-bed"]
    return h


def wall_gap():
    """East wall moved 0.25 m east on the ground floor: the corners open up."""
    h = good_house(); w = _get(_v(h)["walls"], "W-G-E"); w["start"] = [8.25, 0]; w["end"] = [8.25, 6]; return h


def low_headroom():
    """Stairwell hole too short: the first floor slab cuts across the stair."""
    h = good_house(); _get(_v(h)["slabs"], "SL-F")["holes"] = [box(0.15, 3.0, 1.05, 4.75)]; return h


def door_blocked():
    """Bedroom door moved behind the loft stair: its approach is inside the stair flight."""
    h = good_house(loft=True); _get(_v(h)["openings"], "D-bed")["offset_m"] = 3.0; return h


def inventory_missing_room():
    h = good_house(); _v(h)["inventory"].append(dict(label="Box room", drawing="D1", room="R-box")); return h


def good_overlays():
    return {"schema": "garden-studio/overlay-residuals/1", "images": [
        {"id": "photo-front", "source": "P1", "kind": "photo", "width_px": 4000, "height_px": 3000,
         "native_width_px": 4000, "native_height_px": 3000, "solve": {"method": "PnP", "rms_px": 3.1},
         "points": [{"id": "c1", "observed": [100, 200], "projected": [103, 198]}, {"id": "c2", "observed": [900, 220], "projected": [897, 224]}],
         "edges": [{"id": "e1", "element": "W-G-S", "max_px": 9.0}, {"id": "e2", "element": "W-G-E", "residuals_px": [2, 5, -7]}]}]}


def bad_overlays():
    d = good_overlays(); im = d["images"][0]
    im["points"] = [{"id": "c1", "observed": [100, 200], "projected": [110, 190]}]
    im["edges"][0]["max_px"] = 22.0
    d["images"].append({"id": "frame-12", "source": "V1", "kind": "frame", "width_px": 1100, "height_px": 619,
                        "native_width_px": 3840, "native_height_px": 2160, "solve": {"rms_px": 2.0},
                        "edges": [{"id": "e1", "element": "W-G-S", "max_px": 4}]})
    return d
