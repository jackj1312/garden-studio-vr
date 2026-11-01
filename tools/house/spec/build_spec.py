import json, math, os, sys, base64, io, copy
sys.path.insert(0, os.path.dirname(__file__))
import spec_data as SD, spec_more as SM

REPO = "/Users/Jack/Library/Application Support/Claude/scratch-workspaces/cd50e9e5-31ba-4912-8a12-2cd5e6840a09/26acb63f-ba00-4d05-8613-053726bb4022/scratch-2026-10-30-84369f"
HOUSE = REPO + "/assets/sites/house"
SCR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = HOUSE + "/spec"
HTML_DIR = os.path.expanduser("~/Desktop/23 Battle Road - First Build Spec")
REFS = REPO + "/assets/sites/front-garden-model/refs"
CHECK_ONLY = "--check" in sys.argv

def load(v): return json.load(open(f"{HOUSE}/{v}_elements.json"))["elements"]
EL = {"before": load("as_built_now"), "after": load("approved_2b")}
BOX = {"before": json.load(open(SCR + "/abn_boxes.json")), "after": json.load(open(SCR + "/a2b_boxes.json"))}
MEAS = {}
for f in ("measured_final.json",):
    MEAS.update(json.load(open(SCR + "/" + f)))

def area(poly):
    s = 0
    for i in range(len(poly)):
        x1, z1 = poly[i]; x2, z2 = poly[(i + 1) % len(poly)]
        s += x1 * z2 - x2 * z1
    return abs(s) / 2

# ------------------------------------------------------------------ rooms
ROOMS = {}
ALIAS = {"after": {"R-f-hall-landing": "R-f-landing"}}
for v in ("before", "after"):
    rs, seen = [], {}
    for e in EL[v]:
        if e["type"] != "room": continue
        rid = e["id"]
        if rid in seen: seen[rid] += 1; rid = f"{rid}-{seen[rid]}"
        else: seen[rid] = 1
        p = e["params"]
        rs.append(dict(id=rid, name=p["name"], storey=p["storey"], floor_y=p["floor"], polygon=[[round(a, 3), round(b, 3)] for a, b in p["polygon"]],
                       area_m2=round(area(p["polygon"]), 2), change=e["meta"].get("change"), plain=e["meta"].get("plain_label")))
    ROOMS[v] = rs
# Porch exists today: Before takes the as-built porch polygon from 2B (CORRECTIONS 134/156: porch as built in both)
por = [r for r in ROOMS["after"] if r["id"] == "R-g-porch-vaulted"][0]
ROOMS["before"].insert(0, dict(por, change="as built by the owner (after 2022)"))
CEIL = {"ground": 2.43, "first": 2.405}
for v in ROOMS:
    for r in ROOMS[v]:
        r["ceiling_y"] = round(r["floor_y"] + CEIL.get(r["storey"], 2.43), 4)
        f = SM.ROOM_FIN.get(r["id"], SM.DRY)
        r["finishes"] = dict(f)
        if r["id"] == "R-g-porch-vaulted": r["ceiling_y"] = "vaulted (follows the 36 deg porch roof)"
        if r["id"] == "R-g-conservatory-uPVC-polycarbonate-roof": r["ceiling_y"] = "polycarbonate roof (glazing 0.59-2.07; ridge 2.34)"
        if r["id"] == "R-f-bedroom-3-rear-new": r["ceiling_y"] = "2.405 above FFL where flat; slopes to 1.55 at the ashlar wall x 2.7925"
        if r["id"] == "R-g-kitchen-living-dining-open-plan": r["ceiling_y"] = "2.43 flat over the kitchen; sloped under the catslide for x < 2.69 (plate 2.455)"

# ------------------------------------------------------------------ items per version
def items_for(v):
    out = []
    for it in SD.ITEMS:
        if v not in it["versions"]: continue
        d = copy.deepcopy(it); d.pop("versions")
        d["room"] = ALIAS.get(v, {}).get(d["room"], d["room"])
        d["in_both_versions"] = len(it["versions"]) == 2
        out.append(d)
    return out
ITEMS = {v: items_for(v) for v in ("before", "after")}
rooms_by = {v: {r["id"]: r for r in ROOMS[v]} for v in ROOMS}
for v in ITEMS:
    for d in ITEMS[v]:
        assert d["room"] in rooms_by[v], (v, d["id"], d["room"])

# ------------------------------------------------------------------ validation (footprints)
def footprint(d):
    x, y, z = d["position_m"]; W, D, H = [s / 1000 for s in d["size_mm"]]; t = math.radians(d["yaw_deg"])
    u = (math.cos(t), -math.sin(t)); f = (-math.sin(t), -math.cos(t))
    return [(x + sx * W / 2 * u[0] + sy * D / 2 * f[0], z + sx * W / 2 * u[1] + sy * D / 2 * f[1]) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
def inside(pt, poly, tol=0.06):
    x, z = pt; c = False
    for i in range(len(poly)):
        x1, z1 = poly[i]; x2, z2 = poly[(i + 1) % len(poly)]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1: c = not c
    if c: return True
    for i in range(len(poly)):        # near an edge
        x1, z1 = poly[i]; x2, z2 = poly[(i + 1) % len(poly)]
        dx, dz = x2 - x1, z2 - z1; L2 = dx * dx + dz * dz or 1e-9
        t = max(0, min(1, ((x - x1) * dx + (z - z1) * dz) / L2))
        if math.hypot(x - x1 - t * dx, z - z1 - t * dz) <= tol: return True
    return False
def sat(a, b, shrink=0.01):
    for poly in (a, b):
        for i in range(4):
            x1, z1 = poly[i]; x2, z2 = poly[(i + 1) % 4]; nx, nz = z1 - z2, x2 - x1
            pa = [nx * p[0] + nz * p[1] for p in a]; pb = [nx * p[0] + nz * p[1] for p in b]
            n = math.hypot(nx, nz)
            if max(pa) - shrink * n <= min(pb) or max(pb) - shrink * n <= min(pa): return False
    return True
NONBLOCK = ("rug", "mat", "runner", "note", "curtain", "blind", "throw", "cushion")
issues = []
for v in ITEMS:
    floor_items = []
    for d in ITEMS[v]:
        r = rooms_by[v][d["room"]]
        if not any(d["size_mm"]): continue
        fp = footprint(d)
        on_floor = abs(d["position_m"][1] - r["floor_y"]) < 0.02
        if d["category"] in ("decor", "lighting") and not on_floor: continue
        if "throw" not in d["type"]:
            for c in fp:
                if not inside(c, r["polygon"]):
                    issues.append(f"{v}: {d['id']} corner {tuple(round(q, 3) for q in c)} outside {d['room']}"); break
        if on_floor and not any(k in d["type"] for k in NONBLOCK) and d["category"] not in ("decor",):
            floor_items.append((d, fp))
    for i in range(len(floor_items)):
        for j in range(i + 1, len(floor_items)):
            a, fa = floor_items[i]; b, fb = floor_items[j]
            if a["room"] != b["room"]: continue
            ta, tb = a["type"], b["type"]
            if ("table" in ta and "chair" in tb) or ("table" in tb and "chair" in ta): continue   # chairs tucked under tables
            if sat(fa, fb): issues.append(f"{v}: overlap {a['id']} x {b['id']}")

# door sweeps (hinge + swing from the GLB extras): no floor item may sit in a leaf's swept quarter
from glbbox import load as glb_load
GLBF = {"before": HOUSE + "/as_built_now.glb", "after": HOUSE + "/approved_2b.glb"}
HANDING = {"after": {"F-G-utilKit-utility-door-910": {"swing_deg": -90, "why": "opens INTO the utility (the model's derived swing put the leaf across the island stools)"}}}
for v in ITEMS:
    gone = {e["id"] for e in EL[v] if e["meta"].get("stage_out")}
    g = glb_load(GLBF[v]); leafbox = {}
    for n in BOX[v]:
        if n["part"] == "leaf": leafbox.setdefault(n["element"], []).append(n)
    for n in g["nodes"]:
        ex = n.get("extras") or {}
        if not (ex.get("door_leaf") and ex.get("part") == "leaf" and ex.get("hinge") and ex.get("swing_deg")) or ex.get("slide"): continue
        if ex["element"] in gone: continue
        if ex["element"] in HANDING.get(v, {}): ex = dict(ex, swing_deg=HANDING[v][ex["element"]]["swing_deg"])
        hx, hz = ex["hinge"][0], ex["hinge"][2]; hy = ex["hinge"][1]
        bs = [b for b in leafbox.get(ex["element"], [])]
        if not bs: continue
        b = min(bs, key=lambda q: abs((q["lo"][0] + q["hi"][0]) / 2 - hx) + abs((q["lo"][2] + q["hi"][2]) / 2 - hz))
        cx, cz = (b["lo"][0] + b["hi"][0]) / 2, (b["lo"][2] + b["hi"][2]) / 2
        L = 2 * math.hypot(cx - hx, cz - hz); c = ((cx - hx) / (L / 2), (cz - hz) / (L / 2))
        t = math.radians(ex["swing_deg"]); o = (c[0] * math.cos(t) + c[1] * math.sin(t), -c[0] * math.sin(t) + c[1] * math.cos(t))
        for d in ITEMS[v]:
            r = rooms_by[v][d["room"]]
            if abs(r["floor_y"] - hy) > 0.5 or not any(d["size_mm"]): continue
            if abs(d["position_m"][1] - r["floor_y"]) > 0.02 or any(k in d["type"] for k in NONBLOCK): continue
            for (px, pz) in footprint(d) + [(d["position_m"][0], d["position_m"][2])]:
                dx, dz = px - hx, pz - hz
                if math.hypot(dx, dz) < L - 0.01 and dx * c[0] + dz * c[1] > 0.01 and dx * o[0] + dz * o[1] > 0.01:
                    issues.append(f"{v}: {d['id']} in the sweep of {ex['element']}"); break

print("CHECK:", len(issues), "issues"); [print("  ", s) for s in issues]
if CHECK_ONLY: sys.exit(0)

# ------------------------------------------------------------------ openings / door & window finishes
OWNER_ANTH = ("LW-ground", "LW-first", "RW-ground", "RW-first", "bathroom-window")
def opening_rows(v):
    els = EL[v]; ops = {e["id"]: e for e in els if e["type"] == "opening"}
    fixtures = [e for e in els if e["type"] == "fixture" and not e["meta"].get("stage_out")]
    walls = {e["id"]: e for e in els if e["type"] == "wall"}
    replaced = set()
    for e in els:
        if e.get("layer") == "as_built":
            replaced.update(e.get("replaces", []))
    rows = []; done = set()
    for f in fixtures:
        p = f["params"]; o = ops.get(p.get("opening"))
        if not o or o["meta"].get("stage_out"): continue
        if f["id"].startswith("F-N21"): continue
        oid = o["id"]
        if oid in done: continue
        # As-built front openings win over the drawn ones they replace (both versions show the porch/front as built)
        if (f["id"] in replaced or o["id"].replace("O-", "F-") in replaced) and not f["id"].startswith("AB-"): continue
        if f["id"] in ("F-G-front-living-front-window", "F-G-bayfront-sitting-front-window", "F-F-front-bedroom-1-front-window", "F-F-bayfront-bedroom-2-front-window") : continue
        if f["id"].endswith("-owner"): continue
        if v == "after" and f["id"] == "F-G-porchL-porch-external-door": pass
        if v == "before" and f["id"] == "F-G-porchL-porch-external-door": continue   # replaced by AB front door
        done.add(oid)
        op = o["params"]; lab = f["meta"].get("label") or ""
        ext = walls.get(op["host"], {}).get("meta", {}).get("group") == "wall_outer" or "porch" in oid or op["host"].startswith(("G-ext", "F-ext", "G-kitR", "G-os", "AB-"))
        kind = "window" if "window" in f["meta"].get("group", "") or "window" in oid else "door"
        lid = f["id"]
        # finishes by rule
        if not ext:
            out_c = in_c = "FIN-DOOR white 4-panel shaker" if kind == "door" else "n/a"; iron = "matt black lever on rose, 3 black hinges"; bars = "4 panels"
            prov = "drawn (finish chosen)"
        elif "bi-fold" in lab:
            out_c = in_c = "aluminium RAL 7016 (both sides)"; iron = "black D-handle on the traffic leaf, flush bolts"; bars = "4 leaves, no bars"; prov = "drawn (4915.2B 3160 x 2110); colour " + SM.P
        elif "front-door" in lid or "porch external door" in lab and v == "after" or lid.startswith("AB-F-AB-G-porchL"):
            out_c = in_c = "anthracite composite RAL 7016 (both faces)"; iron = "black lever, black letter plate, chrome cylinder, video doorbell beside"; bars = "leaded glass panels (centre vertical light)"; prov = "photo survey (as built, owner)"
        elif "hall door from porch" in lab or "front door (external)" in lab:
            out_c = in_c = "white uPVC RAL 9016, half-glazed (the 2022 front door, now inside the porch)"; iron = "white lever + letter plate (2022)"; bars = "1 light"; prov = "drawn 4915.1 (white in 2022, Jack 1 Nov); assumed kept"
        else:
            anth = lid.startswith("AB-") or "bathroom-window" in lid
            if v == "after": anth = True
            out_c = "anthracite uPVC RAL 7016" if anth else "white uPVC RAL 9016"
            in_c = "white RAL 9016 (" + SM.P + ")" if anth else "white RAL 9016"
            iron = ("black" if anth else "white") + (" espag handles" if kind == "window" else " lever + white letter-plate-free leaf")
            bars = f"{p.get('lights', 1)} lights, no glazing bars"
            prov = ("photo survey (owner replacement after 2022)" if lid.startswith("AB-") or "bathroom-window" in lid else "drawn") + ("" if v == "before" or lid.startswith("AB-") else "; colour per D3 " + SM.P)
        rows.append(dict(id=lid, opening=oid, label=lab[:120], kind=kind, external=bool(ext), width_mm=round(op["width"] * 1000), sill_y=op["sill"], head_y=op["head"],
                         frame_outside=out_c, frame_inside=in_c, glazing=bars, ironmongery=iron, provenance=prov,
                         surround=("buff concrete reveals + head band, lead strip, soldier course over" if "LW-ground" in lid else
                                   "cream stone sill, 90 mm jambs, head band to the soffit" if ("LW-first" in lid or "RW-first" in lid) else
                                   "cream stone sill, jambs, lintel; soldier course over" if "RW-ground" in lid else "")))
    return rows
OPEN = {v: opening_rows(v) for v in ("before", "after")}

# ------------------------------------------------------------------ drawn fixtures from GLB boxes
def drawn_fixtures(v):
    agg = {}
    for n in BOX[v]:
        e = n["element"] or ""
        if not e.startswith(("ST-", "FT-G-chimney", "FT-F-chimney", "FT-G-pier", "FT-F-flank", "FT-conservatory", "CH-stack", "FT-front-door-canopy")): continue
        a = agg.setdefault(e, {"lo": [9e9] * 3, "hi": [-9e9] * 3, "mat": set()})
        for k in range(3): a["lo"][k] = min(a["lo"][k], n["lo"][k]); a["hi"][k] = max(a["hi"][k], n["hi"][k])
        a["mat"].update(n["mat"])
    out = []
    for e, a in agg.items():
        if v == "after" and e == "FT-front-door-canopy-flat-hood-over-the-brick-surro": continue  # removed at stage 3
        if v == "after" and e.startswith("FT-conservatory"): continue
        out.append(dict(element=e, box_min=[round(q, 3) for q in a["lo"]], box_max=[round(q, 3) for q in a["hi"]], model_materials=sorted(a["mat"]),
                        finish=("FIN-STAIR" if e.startswith("ST-") else "FIN-WALL (plastered)" if "chimney-breast" in e or "pier" in e or "flank" in e else
                                "white uPVC + clear glazing on EXT-BRICK-MAIN dwarf wall" if "conservatory" in e else "EXT-CHIMNEY" if e == "CH-stack" else "as model")))
    return out
DRAWN = {v: drawn_fixtures(v) for v in ("before", "after")}

# ------------------------------------------------------------------ colour helpers
def hex2lab(h):
    h = h.lstrip("#"); rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]
    M = [[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]
    X, Y, Z = [sum(M[i][j] * c[j] for j in range(3)) for i in range(3)]
    X /= 0.95047; Z /= 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return [round(116 * f(Y) - 16, 1), round(500 * (f(X) - f(Y)), 1), round(200 * (f(Y) - f(Z)), 1)]
def lab2hex(L, a, b):
    fy = (L + 16) / 116; fx = fy + a / 500; fz = fy - b / 200
    inv = lambda t: t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787
    X, Y, Z = inv(fx) * 0.95047, inv(fy), inv(fz) * 1.08883
    M = [[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]]
    rgb = [sum(M[i][j] * (X, Y, Z)[j] for j in range(3)) for i in range(3)]
    g = lambda c: 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(g(c) * 255))) for c in rgb)

FINISHES = [dict(id=i, name=n, use=u, colour_srgb=h, colour_lab=hex2lab(h), asset=a, notes=s, status=st) for i, n, u, h, a, s, st in SM.FIN]
EXT = []
for mid, name, photo, box, light, key, extra in SM.EXT_MAT:
    m = MEAS[key]
    row = dict(id=mid, name=name, target_photo=photo, region_frac=box, light=light, target_lab=[m["L"], m["a"], m["b"]],
               target_L_spread_p10_p90=[m["Lp10"], m["Lp90"]], target_srgb_median=m["hex"], measured_with="tools/house/measure_colour.py method (median Lab of the region, 960x1280 refs copy)", **extra)
    if mid == "EXT-LW-REVEAL":
        row["white_balanced_lab"] = [m["L"], round(m["a"] + 4.3, 1), round(m["b"] + 18.9, 1)]
    if mid == "EXT-UPVC-ANTH":
        row["white_balanced_lab"] = [m["L"], round(m["a"] + 4.3, 1), round(m["b"] + 18.9, 1)]
    EXT.append(row)
# the main brick: add the white-balanced close-up reference
EXT[0]["secondary"] = {"photo": "closeup_20504", "region_frac": [0.024, 0.018, 0.17, 0.209], "raw_lab": [MEAS["brick_lw_close"]["L"], MEAS["brick_lw_close"]["a"], MEAS["brick_lw_close"]["b"]],
                       "white_balanced_lab": [MEAS["brick_lw_close"]["L"], round(MEAS["brick_lw_close"]["a"] + 4.3, 1), round(MEAS["brick_lw_close"]["b"] + 18.9, 1)]}
EXT_ITEMS = []
for (iid, ver, name, x0, x1, y0, y1, z0, z1, fin, prov, ev) in SM.EXT_ITEMS:
    EXT_ITEMS.append(dict(id=iid, versions={"BA": ["before", "after"], "A": ["after"], "B": ["before"]}[ver], name=name,
                          box_min=[x0, y0, z0], box_max=[x1, y1, z1], size_mm=[round((x1 - x0) * 1000), round((y1 - y0) * 1000), round((z1 - z0) * 1000)],
                          finish=fin, provenance=prov, evidence=ev, status=(SM.P if SM.P in ev or prov in ("proposed",) else "fixed")))

FACADES = {
 "before": [
   "Main house walls: EXT-BRICK-MAIN; soldier courses over the ground-floor front windows from the house's own bricks (tools/phototex/soldier_units.py)",
   "Porch walls: EXT-BRICK-PORCH; roof EXT-ROOF-PORCH at 36 deg with dark grey (RAL 7016) fascia, bargeboard and 0.30 m box end, lead apron to the wing, rooflight 550x780, black half-round gutter + downpipe",
   "Main and wing roofs: EXT-ROOF-MAIN, half-round ridge, bonnet hips; white uPVC fascia/soffit (RAL 9016) with black 110 half-round gutters; eaves soffit 4.68 (photographed) — drawings put the plate at 5.095: keep the elements' geometry",
   "Front windows: the owner's anthracite uPVC (LW ground/first, RW ground/first) with their surrounds; north bathroom window anthracite; every other window white uPVC (CORRECTIONS 157; judge r6 item 11)",
   "Rear: conservatory (white uPVC on a brick dwarf wall 590, polycarbonate roof) and the single-storey outshot (store, lobby, cloaks) as the elements",
   "No.23/No.21 shared chimney with pots + aerial (X-CHIMNEY-POTS, X-AERIAL); No.21 front as seen (X-NO21-PORCH, X-NO21-WINDOWS, EXT-NO21-BRICK)",
 ],
 "after": [
   "Everything in the Before front, unchanged (porch as built)",
   "Two-storey rear extension: facing brick 'to match the existing' = EXT-BRICK-MAIN (same scan, same tint, same course height 75 mm); catslide on the party side",
   "Extension roof: tiles 'to match existing' = EXT-ROOF-MAIN (without moss, 5 % lighter value: new tiles), bonnet hips, half-round ridge; white uPVC fascia/soffit, black half-round gutters 110 + 68 downpipes (2B notes)",
   "Bi-folds: aluminium RAL 7016, 4 leaves stacking to the party side, outward opening (Jack 1 Nov); rear windows and cloaks window anthracite uPVC per D3",
   "Conservatory, outshot, kitchen windows 1-2 and the landing window removed/infilled as 4915.2B (infills in EXT-BRICK-MAIN, toothed in)",
 ],
}

SCHEMA_REF = "assets/sites/house/spec/SCHEMA.md"
spec = {
 "spec": "23 Battle Road — first-build design specification (WORKFLOW gate G2b)", "version": "1.0", "date": "2026-11-01",
 "status": "DRAFT for Jack's sign-off through the questions form. After sign-off nothing changes except by Jack's change request.",
 "schema": SCHEMA_REF,
 "frame": {"name": "elements 'viewer' frame (CONTRACT section 0)", "units": "metres (sizes in mm)",
           "x": "along the front towards the north flank; 0 = party-wall centre line", "z": "minus the depth into the house; 0 = outside face of the main front wall; negative = towards the back garden (west); positive = towards the road (east)",
           "y": "up from ground-floor FFL (0); first-floor FFL 2.6755; outside paving -0.231 (garden registration; the stages sidecar uses -0.25)",
           "yaw_deg": "direction the item's front faces, about +Y: 0 -> -z (west, garden), 90 -> -x (south, party wall), 180 -> +z (east, road), -90 -> +x (north)",
           "position": "centre of the footprint at the item's base (floor items: floor level; wall items: the item's bottom edge)",
           "drawing_frame": "house_drawn.json uses (x, y_drawn = -z, z_up = y)", "garden_frame": SM.GARDEN["frame_transform"]},
 "sources": {"elements": ["assets/sites/house/as_built_now_elements.json (Before)", "assets/sites/house/approved_2b_elements.json (After)"],
             "glb_boxes": "GLB node bounds of as_built_now.glb / approved_2b.glb (viewer frame)", "drawings": "BDS 4915.1, 4915.2B/3A/4A (house_drawn.json; kitchen units and furniture are NOT drawn)",
             "photos": "assets/sites/front-garden-model/refs/ (copies of Jack's photos; private, never uploaded)", "benchmark": "BENCHMARKS.md section 1 (Airbnb Unreal walkthrough)"},
 "build_rules": [
   "Build exactly this schedule: no colour, position, product or finish is improvised. Anything not covered stops the build and becomes a question to Jack (WORKFLOW G2b).",
   "Unchanged rooms are identical in Before and After (same ids, same items, same positions).",
   "Library assets are fitted uniformly to the size box (non-uniform scale <= 5 %); otherwise build the parametric definition.",
   "Parametric items are built from the numbers given; textures from the finish table at true scale.",
   "Items marked 'proposed — Jack to confirm' are built as written unless Jack changes them at sign-off.",
 ],
 "acceptance": {
   "every_item_present": "each id in this file exists once in the build (GLB extras 'spec_id' = id), none extra",
   "position_tolerance_mm": 20, "rotation_tolerance_deg": 2, "size_tolerance": "parametric +-10 mm; library assets +-3 % after uniform fit",
   "colour": "measured exterior materials: median Lab within dE76 <= 5 of target in the matched view, after one exposure offset per photo (median L of the house crop); L spread ratio 0.7-1.3. Chosen interior finishes: rendered under neutral check light, dE <= 5 to colour_lab",
   "support_and_clash": "nothing floats (contact gap <= 3 mm); no interpenetration (tools/blender/clash_check.py = 0); door leaves open fully without hitting an item",
   "order": "automated schedule check passes BEFORE any judge; then one judge round + one fix round, then Jack",
 },
 "versions": {},
 "finishes": FINISHES,
 "exterior": {"materials": EXT, "items": EXT_ITEMS, "facades": FACADES},
 "garden": SM.GARDEN,
 "lighting": SM.SUN,
 "cameras": [dict(id=c[0], versions={"BA": ["before", "after"], "A": ["after"], "B": ["before"]}[c[1]], name=c[2], eye_m=c[3], target_m=c[4], lens_mm=c[5], sun=c[6], purpose=c[7]) for c in SM.CAMERAS],
 "walkthrough": SM.WALK,
 "unreal_look": {"benchmark": SM.AIRBNB, "current": SM.OUR_R9, "gaps": [dict(id=g[0], gap=g[1], closes_it=g[2], target=g[3]) for g in SM.GAPS],
                 "targets": [dict(id=t[0], area=t[1], target=t[2]) for t in SM.TARGETS]},
 "paid_alternatives_not_used": [dict(name=p[0], what=p[1], price=p[2], why=p[3]) for p in SM.PAID],
 "open_decisions": [dict(id=d[0], title=d[1], question=d[2], recommendation=d[3]) for d in SM.DECISIONS],
 "door_handing_overrides": HANDING,
 "known_model_faults_to_fix": [
   "as_built_now.glb paints the drawn rear/side windows anthracite (kitchen 1-2, store, landing, rear bedroom, cloaks): spec = white uPVC in the Before",
   "FT-G-gas-meter-box-external duplicates the photographed meter box X-METER: build X-METER only",
   "Porch mirror is rectangular in the model: arched head per X-MIRROR",
   "Roof tile colour was salmon (CORRECTIONS 165): EXT-ROOF-MAIN target",
 ],
}
for v in ("before", "after"):
    spec["versions"][v] = {
        "elements": "as_built_now" if v == "before" else "approved_2b",
        "description": "The house today: 2022 house + the owner's porch (as built), anthracite front windows and loft rooflights; conservatory and outshot at the back." if v == "before"
                       else "Approved scheme 4915.2B finished: porch as built, two-storey rear extension (kitchen-living-dining, utility, cloaks, bedroom 3 + en-suite).",
        "rooms": ROOMS[v], "items": ITEMS[v], "doors_windows": OPEN[v], "drawn_fixtures": DRAWN[v]}

os.makedirs(OUT_DIR, exist_ok=True)
json.dump(spec, open(OUT_DIR + "/spec_v1.json", "w"), indent=1)
counts = {v: dict(rooms=len(ROOMS[v]), items=len(ITEMS[v]),
                  fixtures=sum(1 for d in ITEMS[v] if d["category"] in ("fixture", "fitting", "sanitary", "appliance", "joinery", "radiator", "lighting")),
                  furniture=sum(1 for d in ITEMS[v] if d["category"] in ("furniture", "soft_furnishing", "decor", "plant")),
                  openings=len(OPEN[v]), drawn=len(DRAWN[v])) for v in ("before", "after")}
counts["finishes"] = len(FINISHES); counts["exterior_materials"] = len(EXT); counts["exterior_items"] = len(EXT_ITEMS)
counts["unique_item_ids"] = len(SD.ITEMS)
json.dump(counts, open(SCR + "/counts.json", "w"), indent=1)
print(json.dumps(counts, indent=1))
import pickle
pickle.dump(dict(spec=spec, counts=counts, issues=issues), open(SCR + "/spec.pkl", "wb"))
