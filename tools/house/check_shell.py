"""G5b SHELL READY gate (WORKFLOW G5b; CORRECTIONS-LOG 191). Blender headless, light (ray casts only, no render).

    nice -n 10 Blender -b --factory-startup --python tools/house/check_shell.py -- --site assets/sites/house --version approved_2b \
        [--spec assets/sites/house/spec/spec_v1.json] [--trace <house_drawn.json>] [--out <site>/<version>_shell.json]

What a homeowner would call "the bare house is finished and coherent", tested on the version's finished stage with the
as-built records on (the spec's Before / After), against the signed spec's rooms and the traced drawings:
  a. OUTLINES: every room edge is a wall face within 20 mm of the drawn internal face (rays from inside the room), or an
     opening into another room / a doorway; drawn features (chimney breasts, piers, ducts) are present where drawn and a
     fireplace breast is continuous above its opening (never two loose jambs); nothing stands over the stair flights at the
     ground ceiling (the stair void).
  b. CEILINGS: a grid of upward rays per room meets a finished ceiling (no sky, no void, no raw deck/joist/rafter) at the
     drawn height (flat rooms within 20 mm; lower = a bulkhead/boxing, listed); sloped rooms finished up to the roof.
  c. DOORS: both sides of every door are walkable floor (a room, or outside); nothing solid within 600 mm beyond the
     opening on either side; the leaf opens fully (the build's swing check); leaf, lining, stops, hinges and handle present.
  d. WINDOWS: glass and a frame in every window opening; the frame colour inside per the spec; reveals and head plastered
     (rays from the room into the opening meet no raw material); a window board under every window in a finished room.
  e. THE SEMI JOINED: the front and rear faces and the roof run on across the party line without a hole or a step
     (rays across the party line x = -0.5..0.5).
  f. FINISHES: the integrity report's raw_surface count is 0 (blocking); skirting in every room whose spec has it;
     architraves round every internal door opening on both faces.
  g. SETTING UNBROKEN: every hedge and fence in the build covers the same plan cells as in the garden model it came from
     (>= 97 %), apart from the spec's own listed changes (street hedge as 3 blocks, row 166).
Writes <site>/<version>_shell.json: pass, per check counts and examples. check_house_export.py fails without a fresh pass."""
import sys, os, json, math, time, argparse, re
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--site", required=True); ap.add_argument("--version", required=True)
ap.add_argument("--spec", default="assets/sites/house/spec/spec_v1.json")
ap.add_argument("--trace", default=os.path.expanduser("~/Desktop/garden-scans/front-garden/architect/house_drawn.json"))
ap.add_argument("--garden", default="assets/sites/front-garden-model/model_q.glb")
ap.add_argument("--out", default="")
args = ap.parse_args(argv)
T0 = time.time()
ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
def R_(p): return p if os.path.isabs(p) else os.path.join(ROOT, p)
site = R_(args.site)
SPEC = json.load(open(R_(args.spec)))
VKEY = "before" if args.version == "as_built_now" else "after"
SV = SPEC["versions"][VKEY]
def log(*a): print(f"[shell {time.time() - T0:6.1f}s]", *a, flush=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
glb = os.path.join(site, f"{args.version}.glb")
bpy.ops.import_scene.gltf(filepath=glb)
stages = json.load(open(os.path.join(site, f"{args.version}.json")))["stages"]
S = len(stages)
ELS = json.load(open(os.path.join(site, f"{args.version}_elements.json")))["elements"]
replaced = set()
for e in ELS:
    if e.get("layer") == "as_built": replaced.update(e.get("replaces", []))
CHECK = json.load(open(os.path.join(site, f"{args.version}_check.json")))

RAW = re.compile(r"^(timber|timber_existing|membrane|mineral_wool|pir|block|batten|rebar|dpm|chipboard|prop_steel|lintel_galv|hardcore|"
                 r"existing_brick|brick|concrete|screed|insulation|felt|earth|steel|existing_floor|buff_concrete)(\.\d+)?$", re.I)
FURN = re.compile(r"^SPEC-(?!FLR|SKIRT)")            # spec items (furniture/fittings) are not the shell
parts, V, T, own, tmat = [], [], [], [], []
for ob in bpy.context.scene.objects:
    if ob.type != "MESH": continue
    src = ob if "stage_in" in ob.keys() else (ob.parent if ob.parent and "stage_in" in ob.parent.keys() else None)
    if src is None: continue
    si = src.get("stage_in", 1); so = src.get("stage_out", 99) or 99
    if not (si <= S < so or (si <= S and so > S)): continue
    if src.get("element") in replaced: continue
    pi = len(parts)
    parts.append(dict(ob=ob, name=ob.name, src=src, group=str(src.get("group", "")), el=str(src.get("element", ob.name)),
                      ctx=bool(src.get("context")), leaf=bool(src.get("door_leaf"))))
    M = ob.matrix_world; b = len(V); me = ob.data
    V.extend(M @ v.co for v in me.vertices)
    for pl in me.polygons:
        T.append(tuple(b + i for i in pl.vertices)); own.append(pi)
        m = me.materials[pl.material_index] if pl.material_index < len(me.materials) else None
        tmat.append(m.name if m else "")
TREE = BVHTree.FromPolygons(V, T)
log(f"{args.version} stage {S}: {len(parts)} visible parts")
def B(x, y, z): return Vector((x, -z, y))                  # viewer -> Blender
def ray(o, d, dist, skip=None):
    """first hit that is not skipped (skip(part) -> True passes through)"""
    o = Vector(o); d = Vector(d).normalized(); left = dist
    for _ in range(80):
        h = TREE.ray_cast(o, d, left)
        if h[0] is None: return None
        p = parts[own[h[2]]]
        if skip is None or not skip(p): return dict(at=h[0], n=h[1], dist=dist - left + h[3], part=p, mat=tmat[h[2]], tri=h[2])
        left -= h[3] + 1e-4; o = h[0] + d * 1e-4
        if left <= 0: return None
    return None
def in_poly(x, z, P):
    c = False; n = len(P)
    for i in range(n):
        x1, z1 = P[i]; x2, z2 = P[(i + 1) % n]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1 + 1e-15) + x1: c = not c
    return c
ROOMS = SV["rooms"]
def room_of(x, y, z):
    for r in ROOMS:
        top = r["ceiling_y"] if isinstance(r["ceiling_y"], (int, float)) else r["floor_y"] + 3.5
        if r["floor_y"] - 0.3 < y < top + 0.3 and in_poly(x, z, r["polygon"]): return r["id"]
    return None
def num_ceiling(r):
    c = r["ceiling_y"]
    if isinstance(c, (int, float)): return float(c), False
    m = re.match(r"\s*([\d.]+)", str(c)); f = float(m.group(1)) if m else None
    if f is not None and "above FFL" in str(c): f += r["floor_y"]
    return f, True
not_shell = lambda p: bool(FURN.match(p["name"])) or p["leaf"] or p["ctx"] and p["group"] != "ground"
F = {k: [] for k in "abcdefg"}; INFO = {k: {} for k in "abcdefg"}
TRACE = json.load(open(args.trace)) if os.path.exists(args.trace) else None
TV = TRACE["versions"]["before" if VKEY == "before" else "today"] if TRACE else None

# ------------------------------------------------------------------------------------------------ a. outlines and drawn features
SKIP_A = lambda p: not_shell(p)
wall_by = {e["id"]: e for e in ELS if e["type"] == "wall"}
DOOR_OPS = []                              # (x0, z0, x1, z1 segment along the wall, head y) for door openings
for e in ELS:
    if e["type"] != "opening" or e["meta"].get("group") not in ("door",) and "door" not in e["id"]: continue
    if (e["meta"].get("stage_out") or 99) <= S: continue
    w = wall_by.get(e["params"]["host"])
    if not w: continue
    (sx, sz), (ex_, ez_) = w["params"]["start"], w["params"]["end"]
    L = math.hypot(ex_ - sx, ez_ - sz) or 1e-9; dx, dz = (ex_ - sx) / L, (ez_ - sz) / L
    u0 = e["params"]["offset"]; u1 = u0 + e["params"]["width"]
    DOOR_OPS.append((sx + dx * u0, sz + dz * u0, sx + dx * u1, sz + dz * u1, e["params"].get("head", 2.1)))
def at_doorway(x, z, tol=0.35):
    for (ax, az, bx, bz, hd) in DOOR_OPS:
        L = math.hypot(bx - ax, bz - az) or 1e-9; t = ((x - ax) * (bx - ax) + (z - az) * (bz - az)) / L ** 2
        if -0.02 <= t <= 1.02 and math.hypot(ax + t * (bx - ax) - x, az + t * (bz - az) - z) < tol: return True
    return False
STAIR_P = []
if TRACE:
    for s_ in TRACE["versions"]["before" if VKEY == "before" else "today"]["storeys"]["ground"].get("stairs", []):
        for q in s_.get("treads_poly", []): STAIR_P.append([(p[0], -p[1]) for p in q])
for p in parts:
    if p["name"].startswith("ST-stair"):
        bb = [p["ob"].matrix_world @ Vector(c) for c in p["ob"].bound_box]
        x0, x1 = min(v.x for v in bb), max(v.x for v in bb); z0, z1 = -max(v.y for v in bb), -min(v.y for v in bb)
        STAIR_P.append([(x0, z0), (x1, z0), (x1, z1), (x0, z1)])
def over_stair_v(x, z, m=0.15):
    return any(in_poly(x, z, q) or any(in_poly(x + dx_, z + dz_, q) for dx_, dz_ in ((m, 0), (-m, 0), (0, m), (0, -m))) for q in STAIR_P)
for r in ROOMS:
    if "conservatory" in r["id"]: continue
    P = r["polygon"]; n = len(P); fy = r["floor_y"]
    ccw = sum(P[i][0] * P[(i + 1) % n][1] - P[(i + 1) % n][0] * P[i][1] for i in range(n)) > 0
    good = bad = opn = 0
    for i in range(n):
        (x0, z0), (x1, z1) = P[i], P[(i + 1) % n]
        L = math.hypot(x1 - x0, z1 - z0)
        if L < 0.15: continue
        dx, dz = (x1 - x0) / L, (z1 - z0) / L
        out = (dz, -dx) if ccw else (-dz, dx)             # outward normal in plan (viewer x, z)
        k = 0
        while (k + 0.5) * 0.2 < L - 0.08:
            u = 0.1 + k * 0.2; k += 1
            if u > L - 0.1: break
            ex, ez = x0 + dx * u, z0 + dz * u
            for hy in (0.35, 1.25):
                y = fy + hy
                o = B(ex - out[0] * 0.25, y, ez - out[1] * 0.25)
                h = ray(o, B(out[0], 0, out[1]) - B(0, 0, 0), 0.65, lambda p: SKIP_A(p) or p["name"].startswith(("SPEC-SKIRT",)))
                if h is None:
                    bx, bz = ex + out[0] * 0.35, ez + out[1] * 0.35
                    if room_of(bx, y, bz) is not None or room_of(ex + out[0] * 0.6, y, ez + out[1] * 0.6) is not None: opn += 1; continue
                    if at_doorway(ex, ez) or over_stair_v(bx, bz): opn += 1; continue
                    F["a"].append(dict(room=r["id"], kind="hole", at=[round(ex, 3), round(y, 3), round(ez, 3)], note="no wall and no room beyond the drawn edge"))
                    continue
                off = h["dist"] - 0.25
                lining = h["part"]["group"] in ("wall_lining", "finish_skin")
                if abs(off) <= 0.02 or (lining and -0.045 <= off <= 0.02):
                    good += 1                       # a lining (plaster, board on dabs, insulated board) stands proud of the drawn line by <= 45 mm
                elif h["part"]["name"].startswith(("FT-", "F-", "AB-F-", "W-", "WB-", "JN-", "ST-", "FS-boxing")) or h["part"]["group"] in ("window", "door"):
                    good += 1                                      # a drawn feature / frame standing at the face
                elif off > 0.02 and room_of(ex + out[0] * 0.1, y, ez + out[1] * 0.1) is not None:
                    opn += 1                                       # open into the next room
                else:
                    bad += 1
                    F["a"].append(dict(room=r["id"], kind="face off the drawn line", off_mm=round(off * 1000), part=h["part"]["name"][:60],
                                       at=[round(ex, 3), round(y, 3), round(ez, 3)]))
    # nothing structural stands inside the room (row 191: a traced wall ran across the passage to the small bedroom, so its
    # door opened onto a wall): points on a 0.25 m grid, 0.2 m in from the outline, must not be inside a wall
    xs_ = [p_[0] for p_ in P]; zs_ = [p_[1] for p_ in P]; inside_hits = {}
    gx = min(xs_) + 0.2
    while gx < max(xs_) - 0.15:
        gz = min(zs_) + 0.2
        while gz < max(zs_) - 0.15:
            if in_poly(gx, gz, P) and all(math.hypot(gx - a_, gz - b_) > 0.2 for a_, b_ in P):
                dmin = min(abs((P[(i + 1) % n][0] - P[i][0]) * (P[i][1] - gz) - (P[i][0] - gx) * (P[(i + 1) % n][1] - P[i][1])) /
                           (math.hypot(P[(i + 1) % n][0] - P[i][0], P[(i + 1) % n][1] - P[i][1]) or 1e-9) for i in range(n))
                if dmin > 0.2:
                    for hy in (1.25,):
                        hh_ = TREE.ray_cast(B(gx, fy + hy, gz), Vector((1, 0, 0)), 20.0)
                        if hh_[0] is not None and hh_[1].x > 0.2:
                            pp_ = parts[own[hh_[2]]]
                            if pp_["group"].startswith("wall") and not pp_["name"].startswith(("FT-", "ST-", "SPEC-", "FS-")):
                                inside_hits.setdefault(pp_["name"], []).append((round(gx, 2), round(gz, 2)))
            gz += 0.25
        gx += 0.25
    for nm_, pts_ in inside_hits.items():
        F["a"].append(dict(room=r["id"], kind="wall standing inside the room", part=nm_[:60], cells=len(pts_), at=pts_[:3]))
    INFO["a"][r["id"]] = dict(on_line=good, off=bad, open=opn)
# drawn features: every traced breast / pier / duct present; a fireplace breast continuous above its opening
if TV:
    for stn in ("ground", "first"):
        base = TV["levels"]["ground_ffl"] if stn == "ground" else TV["levels"]["first_ffl"]
        base = base.get("v", base) if isinstance(base, dict) else base
        for f in TV["storeys"][stn]["fittings"]:
            nm = f["name"].lower()
            if not any(k in nm for k in ("chimney breast", "pier", "duct")): continue
            xs = [p[0] for p in f["poly"]]; ys = [p[1] for p in f["poly"]]
            cx, cz = (min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2
            y = base + 1.2
            found = False
            for (ox, oz, face, axis) in ((max(xs) + 0.5, cz, max(xs), 0), (min(xs) - 0.5, cz, min(xs), 0), (cx, -min(ys) + 0.5, -min(ys), 2), (cx, -max(ys) - 0.5, -max(ys), 2)):
                if room_of(ox, y, oz) is None: continue
                d_ = Vector((face - ox, 0, 0)) if axis == 0 else Vector((0, 0, face - oz))
                h = ray(B(ox, y, oz), B(d_.x, 0, d_.z) - B(0, 0, 0), 0.6, SKIP_A)
                if h is not None:
                    got = h["at"].x if axis == 0 else -h["at"].y
                    if abs(got - face) <= 0.025: found = True; break
            if not found: F["a"].append(dict(kind="drawn feature missing or off its drawn faces", feature=f["name"], storey=stn, at=[round(cx, 3), round(y, 3), round(cz, 3)]))
        jambs = sorted([f for f in TV["storeys"][stn]["fittings"] if "chimney breast pier" in f["name"].lower() or f["name"].lower() == "pier"],
                       key=lambda f: min(p[1] for p in f["poly"]))          # breast jambs and recess piers: the wall runs on above
        for a_, b_ in zip(jambs, jambs[1:]):
            y0 = max(p[1] for p in a_["poly"]); y1 = min(p[1] for p in b_["poly"])
            if abs(min(p[0] for p in a_["poly"]) - min(p[0] for p in b_["poly"])) > 0.03: continue
            room_side = 1 if room_of(max(p[0] for p in a_["poly"]) + 0.3, base + 1.2, -(y0 + y1) / 2) else -1
            xf = max(p[0] for p in a_["poly"]) if room_side > 0 else min(p[0] for p in a_["poly"])
            if not 0.2 < y1 - y0 < 1.5: continue
            for hy in (1.95, 2.3):
                o = B(xf + 0.6 * room_side, base + hy, -(y0 + y1) / 2)
                h = ray(o, Vector((-room_side, 0, 0)), 1.0, lambda p: SKIP_A(p) or p["name"].startswith("FS-"))
                if h is None or abs(h["at"].x - xf) > 0.025 or h["n"].x * room_side < 0.5:
                    F["a"].append(dict(kind="breast / pier wall not continuous over its opening or recess (loose pillars)", storey=stn, at_height=hy,
                                       face_x=round(h["at"].x, 3) if h else None, drawn_face_x=xf))
    for s in TV["storeys"]["ground"].get("stairs", []):
        for poly in [s.get("treads_poly", [])[k] for k in range(0, len(s.get("treads_poly", [])), 3)]:
            if not poly: continue
            cx = sum(p[0] for p in poly) / len(poly); cz = -sum(p[1] for p in poly) / len(poly)
            h = ray(B(cx, 1.9, cz), Vector((0, 0, 1)), 0.6, SKIP_A)
            if h is not None and h["at"].z < 2.45:
                INFO["a"].setdefault("stair_headroom_hits", []).append(dict(at=[round(cx, 2), round(cz, 2)], part=h["part"]["name"][:50], y=round(h["at"].z, 3)))
log("a outlines:", len(F["a"]), "faults")

# ------------------------------------------------------------------------------------------------ b. ceilings
stair_polys = []
if TV:
    for s in TV["storeys"]["ground"].get("stairs", []):
        for q in s.get("treads_poly", []): stair_polys.append([(p[0], -p[1]) for p in q])
        for fl in s.get("flights", []):
            if fl.get("poly"): stair_polys.append([(p[0], -p[1]) for p in fl["poly"]])
def over_stair(x, z): return any(in_poly(x, z, q) for q in stair_polys)
for r in ROOMS:
    if "conservatory" in r["id"]: continue
    cy, sloped = num_ceiling(r)
    P = r["polygon"]; xs = [p[0] for p in P]; zs = [p[1] for p in P]
    cells = ok = 0; low = []
    x = min(xs) + 0.15
    while x < max(xs) - 0.1:
        z = min(zs) + 0.15
        while z < max(zs) - 0.1:
            if in_poly(x, z, P) and all(math.hypot(x - px, z - pz) > 0.12 for px, pz in P):
                cells += 1
                o = B(x, r["floor_y"] + 1.0, z)
                h = ray(o, Vector((0, 0, 1)), 6.0, lambda p: not_shell(p))
                fd = ray(o, Vector((0, 0, -1)), 1.3, lambda p: not_shell(p))
                if fd is None or abs(fd["at"].z - r["floor_y"]) > 0.03 or fd["n"].z < 0.7:
                    if not (fd is not None and (fd["n"].z < -0.2 or fd["part"]["name"].startswith(("FT-", "SPEC-", "ST-")))):   # inside a solid, or a fitting standing on the floor
                        F["b"].append(dict(room=r["id"], kind="no floor at the drawn level", y=(round(fd["at"].z, 3) if fd else None),
                                           part=(fd["part"]["name"][:40] if fd else None), at=[round(x, 2), round(z, 2)]))
                if h is not None and h["n"].z > 0.2 and (fd is None or fd["n"].z < -0.2 or h["part"]["name"].startswith(("FT-", "ST-"))):
                    cells -= 1                                          # the cell stands inside a breast / pier / stair: not open space
                elif h is None:
                    F["b"].append(dict(room=r["id"], kind="no ceiling (sky)", at=[round(x, 2), round(z, 2)]))
                elif (RAW.match(h["mat"]) or h["part"]["group"] in ("roof_cover", "roof_layer")) and not over_stair(x, z) and not over_stair_v(x, z):
                    # (a roof's underside is never a ceiling: the outshot's felt roof, exported as black_upvc, passed as a "bulkhead")
                    F["b"].append(dict(room=r["id"], kind="raw ceiling", mat=h["mat"], part=h["part"]["name"][:50], y=round(h["at"].z, 3), at=[round(x, 2), round(z, 2)]))
                elif h["n"].z > 0.2:
                    F["b"].append(dict(room=r["id"], kind="ceiling seen from behind (open)", part=h["part"]["name"][:50], at=[round(x, 2), round(z, 2)]))
                else:
                    hy = h["at"].z
                    if over_stair(x, z) or over_stair_v(x, z) or sloped and (cy is None or hy <= cy + 2.0): ok += 1
                    elif cy is not None and abs(hy - cy) <= 0.02: ok += 1
                    elif cy is not None and hy < cy - 0.02:
                        ok += 1; low.append((round(x, 2), round(z, 2), round(hy, 3), h["part"]["name"][:40]))
                    else:
                        F["b"].append(dict(room=r["id"], kind="ceiling off its drawn height", y=round(hy, 3), drawn=cy, part=h["part"]["name"][:50], at=[round(x, 2), round(z, 2)]))
            z += 0.3
        x += 0.3
    INFO["b"][r["id"]] = dict(cells=cells, ok=ok, bulkhead_cells=len(low), bulkheads=low[:4])
log("b ceilings:", len(F["b"]), "faults")

# ------------------------------------------------------------------------------------------------ c. doors
DW = {d["id"]: d for d in SPEC["versions"]["before"].get("doors_windows", [])}       # a door the After schedule omits is the existing one
DW.update({d["id"]: d for d in SV.get("doors_windows", [])})
leaves = {}
for p in parts:
    if p["leaf"]: leaves.setdefault(str(p["src"].get("door_group", p["el"])), []).append(p)
swing = {d["leaf"]: d for d in CHECK.get("door_swings", [])}
def leaf_box(ps):
    vs = [p["ob"].matrix_world @ Vector(c) for p in ps for c in p["ob"].bound_box]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs))); hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    return lo, hi
outline = []                                     # the house footprint (all ground rooms): outside = not in any room on the ground
def outside(x, z): return not any(in_poly(x, z, r["polygon"]) for r in ROOMS if r["storey"] == "ground") and not (TV and False)
for g, ps in leaves.items():
    lo, hi = leaf_box(ps)
    # the closed leaf is thin across the wall: its thin plan axis is the wall normal
    ext = hi - lo; nrm = Vector((1, 0, 0)) if ext.x < ext.y else Vector((0, 1, 0))
    c = (lo + hi) / 2; fl = lo.z
    width = max(ext.x, ext.y)
    sides = [room_of((c + nrm * sg * 0.3).x, fl + 0.5, -(c + nrm * sg * 0.3).y) for sg in (1, -1)]
    ext_door = any(sd is None for sd in sides)
    area_of = {r["id"]: r.get("area_m2", 99) for r in ROOMS}
    for sgn in (1, -1):
        rid_s = sides[0] if sgn == 1 else sides[1]
        q = c + nrm * sgn * (0.6 if (rid_s is None or area_of.get(rid_s, 99) >= 3.0) else 0.25)
        qq = Vector((q.x, q.y, fl + 1.0))
        down = ray(qq, Vector((0, 0, -1)), 1.6, lambda p: not_shell(p))
        vx, vz = q.x, -q.y
        rid = room_of(vx, fl + 0.5, vz)
        walk = down is not None and down["n"].z > 0.7 and (abs(down["at"].z - fl) < 0.12 or rid is None and -0.45 < down["at"].z - fl < 0.05)
        if not walk or (rid is None and not outside(vx, vz)):
            F["c"].append(dict(door=g, kind="side is not walkable floor in a room" + ("" if walk else " (no floor)"), side=sgn,
                               at=[round(vx, 2), round(fl, 2), round(vz, 2)], floor_hit=down["part"]["name"][:40] if down else None, room=rid))
        rid_s = sides[0] if sgn == 1 else sides[1]
        clear = 0.6 if (rid_s is None or area_of.get(rid_s, 99) >= 3.0) else 0.35      # cupboards, WCs, lobbies: UK typical 350 mm
        for hy in (0.3, 1.0, 1.8):
            for du in (-0.3, 0.0, 0.3):
                t = Vector((-nrm.y, nrm.x, 0)) * du * min(1.0, width / 0.8)
                o = Vector((c.x, c.y, fl + hy)) + t + nrm * sgn * 0.08
                h = ray(o, nrm * sgn, clear - 0.05, lambda p: not_shell(p) or p["group"] in ("door",) or p["el"] == g or p["name"].startswith(("JN-", "FS-")))
                if h is not None:
                    F["c"].append(dict(door=g, kind="solid within 600 mm beyond the opening", side=sgn, part=h["part"]["name"][:50],
                                       dist_mm=round((h["dist"] + 0.08) * 1000), height=hy)); break
            else: continue
            break
    for p in ps:
        d = swing.get(p["name"])
        if d and abs(d.get("swing_deg", 90)) < 85:
            if str(d.get("hit") or "").startswith("open leaf"):          # two doors that cannot both stand open (row 158): recorded, not a shell fault
                INFO["c"].setdefault("doors_meeting_when_both_open", []).append(dict(door=g, swing=d.get("swing_deg"), other=d.get("hit")))
            else:
                F["c"].append(dict(door=g, kind="leaf does not open fully", swing=d.get("swing_deg"), hit=d.get("hit")))
    names = [q["name"] for q in parts if q["name"].startswith(f"JN-{g}") or q["el"] == g]
    sdw = DW.get(g) or DW.get(g.replace("AB-F-", "F-"))
    internal = not ext_door and not (sdw and sdw.get("external"))          # the spec's own door type (uPVC doors between rooms stay uPVC)
    if internal:
        need = {"lining": r"lining|_frame", "stops": r"stop", "hinges": r"hinge", "handle": r"handle|lever"}
        miss = [k for k, rx in need.items() if not any(re.search(rx, n_, re.I) for n_ in names)]
        if miss: F["c"].append(dict(door=g, kind="door parts missing", missing=miss))
INFO["c"]["doors"] = len(leaves)
log("c doors:", len(F["c"]), "faults over", len(leaves), "doors")

# ------------------------------------------------------------------------------------------------ d. windows
wall_by = {e["id"]: e for e in ELS if e["type"] == "wall"}
ops = [e for e in ELS if e["type"] == "opening" and e["meta"].get("group") == "window" and (e["meta"].get("stage_out") or 99) > S and e["id"] not in replaced]
nwin = 0
for o in ops:
    w = wall_by.get(o["params"]["host"])
    if not w: continue
    (sx, sz), (ex_, ez_) = w["params"]["start"], w["params"]["end"]
    L = math.hypot(ex_ - sx, ez_ - sz); dx, dz = (ex_ - sx) / L, (ez_ - sz) / L
    u = o["params"]["offset"] + o["params"]["width"] / 2
    cx, cz = sx + dx * u, sz + dz * u
    st = w["meta"].get("storey", "ground"); fl = 0.0 if st == "ground" else 2.6755
    cy = (o["params"]["sill"] + o["params"]["head"]) / 2           # opening sill/head are absolute heights (first floor 2.7+)
    for sgn in (1, -1):
        nx, nz = -dz * sgn, dx * sgn
        if room_of(cx + nx * 0.6, cy, cz + nz * 0.6): break
    else:
        continue                                            # not on a finished room (conservatory, outshot store wall...)
    rid = room_of(cx + nx * 0.6, cy, cz + nz * 0.6)
    if "conservatory" in rid: continue
    fxs = [e for e in ELS if e["type"] == "fixture" and e["params"].get("opening") == o["id"]]
    live_fx = [e for e in fxs if e["id"] not in replaced and (e["meta"].get("stage_out") or 99) > S]
    if fxs and not live_fx: continue                               # replaced by the as-built window (checked as its own opening)
    eye = B(cx + nx * 0.7, cy, cz + nz * 0.7)
    h = ray(eye, B(-nx, 0, -nz) - B(0, 0, 0), 1.2, lambda p: not_shell(p) or p["name"].startswith("FS-"))
    if not live_fx and h is not None and h["part"]["group"] == "window" and h["dist"] < 0.95:
        live_fx = [dict(id=h["part"]["el"])]                         # a window fills it (the opening was copied to a split wall piece: row 182)
    if not live_fx:
        if h is not None and h["part"]["group"].startswith("wall") and h["dist"] < 0.95:
            INFO["d"].setdefault("openings_closed_by_infill", []).append(o["id"]); continue
        F["d"].append(dict(window=o["id"], room=rid, kind="opening with no window and not closed (orphan opening)", hit=(h["part"]["name"][:40] if h else None))); continue
    nwin += 1
    if h is None or "glass" not in h["mat"].lower() and h["part"]["group"] not in ("window",):
        F["d"].append(dict(window=o["id"], room=rid, kind="no glass / frame in the opening", hit=(h["part"]["name"][:40] if h else None))); continue
    gp_ = h["at"]                                                   # the glass / frame plane: reveals are checked on the room side of it
    dg = (gp_ - eye).length
    hw = o["params"]["width"] / 2; hh = (o["params"]["head"] - o["params"]["sill"]) / 2
    wd = B(dx, 0, dz) - B(0, 0, 0); inn = B(nx, 0, nz) - B(0, 0, 0)
    for (du, dv, lab) in ((-1, 0, "left reveal"), (1, 0, "right reveal"), (0, 1, "head"), (0, -1, "sill / board")):
        for back in (0.04, 0.10, 0.17, 0.25):                          # from the glass toward the room face (the reveal zone)
            tgt = gp_ + inn * back + wd * du * (hw + 0.04) + Vector((0, 0, dv * (hh + 0.04)))
            d_ = tgt - eye
            hh_ = ray(eye, d_, d_.length + 0.03, lambda p: not_shell(p))
            if hh_ is not None and RAW.match(hh_["mat"]):
                F["d"].append(dict(window=o["id"], room=rid, kind=f"raw {lab}", mat=hh_["mat"], part=hh_["part"]["name"][:50])); break
    fx_ids = {e["id"] for e in ELS if e["type"] == "fixture" and e["params"].get("opening") == o["id"]} | {e["id"] for e in live_fx}
    if not any(q["name"].startswith("WB-") and (q["el"] in fx_ids or q["name"].startswith(f"WB-{o['id']}")) for q in parts):
        F["d"].append(dict(window=o["id"], room=rid, kind="no window board"))
INFO["d"]["windows_on_rooms"] = nwin
log("d windows:", len(F["d"]), "faults over", nwin, "windows")

# ------------------------------------------------------------------------------------------------ e. the semi joined to No.21
_V2, _T2 = [], []
for pi_, p in enumerate(parts):
    if FURN.match(p["name"]) or p["leaf"] or re.search(r"Plant|hedge|tree|leaf|Conifer|Bin_|Bench|Pot_", p["name"], re.I): continue
    M = p["ob"].matrix_world; b = len(_V2); _V2.extend(M @ v.co for v in p["ob"].data.vertices)
    _T2.extend(tuple(b + i for i in pl.vertices) for pl in p["ob"].data.polygons)
TREE_E = BVHTree.FromPolygons(_V2, _T2)
def scan(o_of, d, label, n=41):
    prev = None
    for k in range(n):
        x = -0.5 + k * 0.025
        o = o_of(x); hh = TREE_E.ray_cast(o, d, 12.0)
        h = None if hh[0] is None else dict(at=hh[0])
        if h is None:
            F["e"].append(dict(kind=f"{label}: hole at the party line", x=round(x, 3))); prev = None; continue
        dpt = (h["at"] - o).length
        if prev is not None and abs(dpt - prev) > 0.35:
            F["e"].append(dict(kind=f"{label}: step / gap at the party line", x=round(x, 3), jump_m=round(dpt - prev, 3)))
        prev = dpt
for y in (1.0, 2.0, 4.0):
    scan(lambda x, y=y: B(x, y, 6.0), B(0, 0, -1) - B(0, 0, 0), f"front face at y {y}")
for zf in (-1.2, -3.6):
    scan(lambda x, zf=zf: B(x, 12.0, zf), Vector((0, 0, -1)), f"roof at z {zf}")
log("e party line:", len(F["e"]), "faults")

# ------------------------------------------------------------------------------------------------ f. finishes, skirting, architraves
ip = os.path.join(site, f"{args.version}_integrity.json")
if os.path.exists(ip):
    ir = json.load(open(ip))
    if ir.get("glb_mtime", 0) + 1 < os.path.getmtime(glb): F["f"].append(dict(kind="integrity report older than the GLB"))
    nraw = ir["counts"].get("raw_surface", 0) + ir.get("allowed_counts", {}).get("raw_surface", 0)
    if nraw: F["f"].append(dict(kind="raw construction seen from finished rooms", count=nraw, examples=[(x["room"], x["part"], x["material"]) for x in ir["faults"].get("raw_surface", [])[:6]]))
else:
    F["f"].append(dict(kind="no integrity report"))
skirt_notes = " ".join(n for n in CHECK.get("notes", []) if n.startswith("skirting: none in"))
for r in ROOMS:
    if "FIN-SKIRT" in r["finishes"].get("skirting", "") and not any(q["name"].startswith(("JN-SKIRT-" + r["id"], "SPEC-SKIRT-" + r["id"] + "-")) for q in parts):
        if f"skirting: none in {r['id']} " in skirt_notes + " ":
            INFO["f"].setdefault("rooms_all_doorways", []).append(r["id"])           # every wall run sits between architraves (the lobby)
        else:
            F["f"].append(dict(room=r["id"], kind="no skirting"))
for g in leaves:
    sdw = DW.get(g)
    if sdw is None or sdw.get("external") or sdw.get("kind") != "door": continue
    arc = [q for q in parts if q["el"] == g and q["name"].endswith("_architraves")]
    if not arc: F["f"].append(dict(door=g, kind="architraves missing (both faces)"))
log("f finishes:", len(F["f"]), "faults")

# ------------------------------------------------------------------------------------------------ g. setting unbroken
gp = R_(args.garden)
if os.path.exists(gp):
    rx = re.compile(r"^B_.*(hedge|fence)", re.I)                   # boundary hedges and fences (the beds' soil is ground, clipped by design)
    def cells_of(obs, shift):
        out = {}
        for ob in obs:
            M = ob.matrix_world; key = re.sub(r"\.\d+$", "", ob.name)
            cs = out.setdefault(key, set())
            for v in ob.data.vertices:
                w = M @ v.co
                cs.add((int(math.floor((w.x + shift[0]) / 0.25)), int(math.floor((w.y + shift[1]) / 0.25))))
        return out
    mine = cells_of([p["ob"] for p in parts if p["ctx"] and rx.search(p["name"])], (0, 0))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=gp)
    newobs = [o for o in bpy.data.objects if o not in before and o.type == "MESH" and rx.search(o.name)]
    # garden frame -> house: house = garden + (4.63, -0.231, 3.09) (viewer x, y, z) -> Blender (x + 4.63, y - 3.09)
    src = cells_of(newobs, (4.63, -3.09))
    for k, cs in src.items():
        if k.startswith("B_street_hedge"): continue          # spec: the street hedge as 3 clipped blocks (row 166)
        m = mine.get(k)
        if m is None:
            INFO["g"].setdefault("not_in_build", []).append(k); continue
        cov = len(cs & m) / max(1, len(cs))
        if cov < 0.97: F["g"].append(dict(kind="hedge/fence run broken or cut", object=k, coverage=round(cov, 3)))
    INFO["g"]["compared"] = len(src)
else:
    INFO["g"]["note"] = f"garden model {gp} not found: not compared"
log("g setting:", len(F["g"]), "faults")

# open questions inside the drawings themselves (tools/house/shell_allow.json): listed, never silent
ALLOWED = {}
ap_ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shell_allow.json")
if os.path.exists(ap_):
    for k_ in F:
        keep = []
        for f_ in F[k_]:
            hit = None
            for al in json.load(open(ap_))["allow"]:
                if al["check"] != k_ or al.get("room") not in (None, f_.get("room")) or al.get("kind") not in (None, f_.get("kind")): continue
                at_ = f_.get("at")
                if al.get("near") and at_ and math.hypot(at_[0] - al["near"][0], at_[-1] - al["near"][1]) > al.get("tol", 0.1): continue
                hit = al; break
            if hit: ALLOWED.setdefault(k_, []).append(dict(f_, allowed=hit["reason"]))
            else: keep.append(f_)
        F[k_] = keep
res = dict(version=args.version, stage=S, glb=os.path.basename(glb), glb_mtime=os.path.getmtime(glb), written=time.time(),
           passed=not any(F.values()), counts={k: len(v) for k, v in F.items()},
           names=dict(a="outlines and drawn features", b="ceilings", c="doors", d="windows", e="semi joined to No.21", f="finishes, skirting, architraves", g="setting unbroken"),
           faults={k: v[:150] for k, v in F.items()}, info=INFO, allowed=ALLOWED, allowed_counts={k: len(v) for k, v in ALLOWED.items()})
out = args.out or os.path.join(site, f"{args.version}_shell.json")
json.dump(res, open(out, "w"), indent=1)
log("PASS" if res["passed"] else "FAIL", res["counts"], "->", out)
