"""Geometry INTEGRITY GATE for a generated house GLB (CORRECTIONS-LOG 179; WORKFLOW G5/G6). Blender headless, light (no render).

    nice -n 10 Blender -b --factory-startup --python tools/house/check_integrity.py -- \
        --site assets/sites/house --version approved_2b [--stage N] [--asbuilt on] [--spec assets/sites/house/spec/spec_v1.json]

What the homeowner sees at one stage (default: the version's last stage; the as-built records on, as the spec's Before/After)
is checked for:
  1. OPEN SHELLS: every wall, roof and floor part is a closed, outward-facing solid (no boundary or non-manifold edges after
     welding at 0.01 mm; signed volume > 0). Other solids are reported the same way (single-sided rendering shows a hole).
  2. GAPS: where parts meet (wall to wall of the same layer, wall to roof, wall to floor, frames to their reveals) there is no
     slot over 2 mm: rays from each face along its normal must not find the facing face of a meeting part 2-60 mm away.
  3. Z-FIGHTING: no two faces facing the same way lie in one plane (within 0.5 mm) and overlap by more than 1 cm2.
  4. ROOF: nothing stands above the roof planes (tile tops) by more than 20 mm except chimneys, flues, vents, rooflights,
     aerial, pots, flashings, ridge and hip tiles.
  5. FOLIAGE: no leaf card or plant intersects a solid (walls, windows, roofs, fences, furniture), except the ground and its pot.
  6. MISSING FACES: from every walkable position (room grids at eye height, the spec's walk waypoints and cameras, a ring
     round the house) rays find no back face of a single-sided solid first, and indoors no ray escapes to the sky.
Writes <site>/<version>_integrity.json (pass, counts by type, examples). check_house_export.py fails the build without a
fresh, passing report for the homeowner versions."""
import sys, os, json, math, time, argparse, re
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--site", required=True); ap.add_argument("--version", required=True)
ap.add_argument("--glb", default="", help="default <site>/<version>.glb")
ap.add_argument("--stage", type=float, default=None); ap.add_argument("--asbuilt", default="on")
ap.add_argument("--spec", default="assets/sites/house/spec/spec_v1.json")
ap.add_argument("--rays", type=int, default=1500); ap.add_argument("--out", default="")
args = ap.parse_args(argv)
T0 = time.time()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
site = args.site if os.path.isabs(args.site) else os.path.join(ROOT, args.site)
glb = args.glb or os.path.join(site, f"{args.version}.glb")
SPEC = json.load(open(args.spec if os.path.isabs(args.spec) else os.path.join(ROOT, args.spec)))
VKEY = "before" if args.version == SPEC.get("_before_id", "as_built_now") else "after"


def log(*a): print(f"[integrity {time.time() - T0:6.1f}s]", *a, flush=True)


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
sc = bpy.context.scene
stages = json.load(open(os.path.join(site, f"{args.version}.json")))["stages"]
S = args.stage if args.stage is not None else len(stages)
replaced = set()
elp = os.path.join(site, f"{args.version}_elements.json")
if args.asbuilt == "on" and os.path.exists(elp):
    for e in json.load(open(elp))["elements"]:
        if e.get("layer") == "as_built": replaced.update(e.get("replaces", []))

# ------------------------------------------------------------------------------------------------ the visible set
FOLIAGE_MAT = re.compile(r"leaves|leaf|vertexplant|branches|conifer|hedge|plant|foliage|grass", re.I)
OPEN_MAT = re.compile(r"glass|fence_gap|drain_grate|rebar|heras|mesh|tarp|mirror_face", re.I)
WALLS = {"wall_outer", "wall_inner", "wall_lining", "wall_insulation"}
ROOFS = {"roof_cover", "roof_layer", "ridge", "hip", "valley"}
FLOORS = {"slab_layer", "deck", "floor_finish"}
ROOF_OK = re.compile(r"chimney|CH-|flue|vent|svp|rooflight|RL-|LOFT-rooflight|aerial|pot|cowl|flash|apron|lead|soaker|ridge|hip|valley|dish|"
                     r"X-AERIAL|X-CHIMNEY|X-LOFT-RL|X-PORCH-RL|cctv", re.I)
parts = []          # dict(ob, name, props, mats, foliage, open, ctx)
for ob in sc.objects:
    if ob.type != "MESH": continue
    src = ob if "stage_in" in ob.keys() else (ob.parent if ob.parent and "stage_in" in ob.parent.keys() else None)
    if src is None: continue
    si = src.get("stage_in", 1); so = src.get("stage_out", 99) or 99
    vis = si <= S < so or (S == len(stages) and si <= S and so > S)
    if src.get("as_built") and args.asbuilt != "on": vis = False
    if args.asbuilt == "on" and src.get("element") in replaced: vis = False
    if not vis: continue
    mats = [m.name for m in ob.data.materials if m]
    dbl = [m for m in ob.data.materials if m and not m.use_backface_culling]
    foliage = any(FOLIAGE_MAT.search(m) for m in mats) or bool(re.match(r"(Plant2_|island_tree|Conifer|B_street_hedge|B_hedge|SPEC-.*PLANT)", ob.name)) \
        or str(src.get("category_spec", "")) == "plant"
    opn = all(OPEN_MAT.search(m) for m in mats) if mats else True
    parts.append(dict(ob=ob, name=ob.name, el=str(src.get("element", ob.name)), group=str(src.get("group", "")), props=src,
                      mats=mats, foliage=foliage, open=opn, ctx=bool(src.get("context")), spec=str(src.get("spec_id", ""))))
log(f"{args.version} stage {S}: {len(parts)} visible parts")

GROUND_Z = -0.25                 # outside ground (viewer y, the stages sidecar's site level)
# world geometry per part
for p in parts:
    me = p["ob"].data; M = p["ob"].matrix_world
    V = [M @ v.co for v in me.vertices]
    T = [tuple(pl.vertices) for pl in me.polygons]
    p["V"], p["T"] = V, T
    xs = [v.x for v in V] or [0]; ys = [v.y for v in V] or [0]; zs = [v.z for v in V] or [0]
    p["lo"] = Vector((min(xs), min(ys), min(zs))); p["hi"] = Vector((max(xs), max(ys), max(zs)))
    p["buried"] = p["hi"].z < GROUND_Z + 0.005
    # per-polygon material double-sidedness
    ds = []
    for pl in me.polygons:
        m = me.materials[pl.material_index] if pl.material_index < len(me.materials) else None
        ds.append(bool(m is None or not m.use_backface_culling or OPEN_MAT.search(m.name or "") or FOLIAGE_MAT.search(m.name or "")))
    p["ds"] = ds

FAULTS = {k: [] for k in ("open_shell", "gap", "z_fight", "above_roof", "foliage_in_solid", "missing_face", "sky_leak", "raw_surface")}
# construction materials that are never the finished face of a room (seen from inside a finished room = a missing lining,
# ceiling or floor: Jack's "missing surfaces"); brick counts too, except where the spec keeps it bare (conservatory)
RAW = re.compile(r"^(timber|timber_existing|membrane|mineral_wool|pir|block|batten|rebar|dpm|chipboard|prop_steel|lintel_galv|hardcore|"
                 r"existing_brick|brick|concrete|screed|insulation|felt|earth|steel)(\.\d+)?$", re.I)
BARE_OK_ROOMS = re.compile(r"conservatory", re.I)
# finished faces that wait for the interior spec (Jack's planner, spec v2): the floor finish over the new deck and the stair
# finish (FIN-STAIR). Counted and listed, not faults of the shell.
FINISH_PENDING = re.compile(r"^(DK-|ST-stair)")
INFO = {"open_other_solids": [], "positions_inside_solids": []}


def short(p): return p["name"][:70]


# ------------------------------------------------------------------------------------------------ 1. open shells
def shell_stats(p):
    """boundary edges after welding (holes), non-manifold edges (cells kept as separate closed pieces: harmless when they
    are closed), and faces facing inwards: a ray from just outside a face along its normal must cross the part's own
    surface an even number of times (an inside-out face sends it through the solid: odd)"""
    bm = bmesh.new()
    for v in p["V"]: bm.verts.new(v)
    bm.verts.ensure_lookup_table()
    for t in p["T"]:
        try: bm.faces.new([bm.verts[i] for i in t])
        except ValueError: pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bnd = sum(1 for e in bm.edges if e.is_boundary); nm = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    vol = bm.calc_volume(signed=True) if bm.faces else 0.0
    bm.free()
    # generalized winding number just behind and just in front of every face: an outward face has the solid behind it
    # (w_behind - w_front ~ +1); a face between two closed cells has solid on both sides (~0, never seen); an inside-out
    # face has it in front (~ -1). Robust for cells kept as separate closed pieces.
    import numpy as np
    V = np.array([tuple(v) for v in p["V"]], dtype=np.float64)
    T = np.array([t[:3] for t in p["T"] if len(t) >= 3], dtype=np.int64)
    from integrity_winding import inward_mask
    inward = int(inward_mask(V[T]).sum())
    return bnd, nm, vol, inward


for p in parts:
    if p["foliage"] or p["open"] or p["ctx"] and p["group"] == "ground" or p["buried"]: continue
    if not p["T"]: continue
    bnd, nm, vol, inward = shell_stats(p)
    if bnd or inward or vol < -1e-9:
        rec = dict(part=short(p), element=p["el"], group=p["group"], boundary_edges=bnd, inward_faces=inward, faces=len(p["T"]),
                   nonmanifold_edges=nm, volume=round(vol, 6))
        if p["group"] in WALLS | ROOFS | FLOORS and not p["ctx"]: FAULTS["open_shell"].append(rec)
        else: INFO["open_other_solids"].append(rec)
    elif nm:
        INFO.setdefault("closed_cells_kept_apart", []).append(short(p))
log("open shells:", len(FAULTS["open_shell"]), "walls/roofs/floors;", len(INFO["open_other_solids"]), "other")

# ------------------------------------------------------------------------------------------------ one tree of everything
allV, allT, owner, tri_ds = [], [], [], []
for pi, p in enumerate(parts):
    p['tri_offset'] = len(allT)
    b = len(allV); allV.extend(p["V"])
    for k, t in enumerate(p["T"]):
        allT.append(tuple(b + i for i in t)); owner.append(pi); tri_ds.append(p["ds"][k])
TREE = BVHTree.FromPolygons(allV, allT, epsilon=0.0)
log("tree:", len(allT), "polygons")

# ------------------------------------------------------------------------------------------------ walkable positions (used by 2, 3 and 6)
def b_(x, y, z): return Vector((x, -z, y))        # viewer (x, y, z) -> Blender


def in_poly(x, z, P):
    c = False; j = len(P) - 1
    for i in range(len(P)):
        xi, zi = P[i]; xj, zj = P[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi + 1e-12) + xi: c = not c
        j = i
    return c


def dist_edge(x, z, P):
    best = 1e9
    for i in range(len(P)):
        (x1, z1), (x2, z2) = P[i], P[(i + 1) % len(P)]
        dx, dz = x2 - x1, z2 - z1; L2 = dx * dx + dz * dz or 1e-12
        t = max(0, min(1, ((x - x1) * dx + (z - z1) * dz) / L2))
        best = min(best, math.hypot(x - x1 - t * dx, z - z1 - t * dz))
    return best


positions = []          # (label, Blender point, indoors)
vs = SPEC["versions"][VKEY]
for r in vs["rooms"]:
    P = r["polygon"]; fy = r["floor_y"]
    xs = [q[0] for q in P]; zs = [q[1] for q in P]
    step = 0.6 if r.get("area_m2", 5) > 3 else 0.35
    x = min(xs) + 0.2
    while x < max(xs):
        z = min(zs) + 0.2
        while z < max(zs):
            if in_poly(x, z, P) and dist_edge(x, z, P) > 0.2:
                for eh in (1.6, 1.0):
                    positions.append((f"{r['id']} ({x:.2f}, {z:.2f}) eye {eh}", b_(x, fy + eh, z), True))
            z += step
        x += step
for nm, pt in SPEC["walkthrough"].get(VKEY, []):
    positions.append((f"walk {nm}", b_(pt[0], pt[1] + SPEC["walkthrough"]["eye_height_m"], pt[2]), None))
for c in SPEC["cameras"]:
    if VKEY in c["versions"] and isinstance(c["eye_m"], list):
        positions.append((f"camera {c['id']}", b_(*c["eye_m"]), None))
for ang in range(0, 360, 20):                      # a ring round the house in the gardens, eye height
    a = math.radians(ang); cx, cz = 4.6, -4.0
    x, z = cx + 9.5 * math.cos(a), cz + 11.0 * math.sin(a)
    positions.append((f"ring {ang}", b_(x, -0.25 + 1.6, z), False))


def fib(n):
    out = []; g = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        y = 1 - 2 * (i + 0.5) / n; r = math.sqrt(1 - y * y); t = g * i
        out.append(Vector((math.cos(t) * r, math.sin(t) * r, y)))
    return out




POS = [pt for _, pt, _ in positions]


def visible(pt, n=None, reach=9.0, tries=60):
    """pt (a point in air) is seen from some walkable position: a straight line from the position reaches it unobstructed"""
    near = sorted(((q - pt).length, q) for q in POS if (q - pt).length < reach)[:tries]
    for dist, q in near:
        d = (pt - q).normalized()
        if n is not None and d.dot(n) > -0.02: continue           # must look at the face's front
        h = TREE.ray_cast(q, d, dist + 0.01)
        if h[0] is None or h[3] >= dist - 0.004:
            e = pt + (q - pt).normalized() * min(1.0, dist)          # an inspection eye 1 m from the fault on that sight line
            return [round(e.x, 3), round(e.z, 3), round(-e.y, 3)]
    return None


def slot_mouth(m, n, d):
    """march from the slot midpoint m in the slot's plane until it is no longer between the two faces: the mouth point"""
    u = n.cross(Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))).normalized(); v = n.cross(u)
    for dv in (u, -u, v, -v):
        if TREE.ray_cast(m, dv, 0.6)[0] is not None: continue       # closed that way
        for k in range(1, 121):
            x = m + dv * (0.005 * k)
            a = TREE.ray_cast(x, -n, d); b = TREE.ray_cast(x, n, d)
            if a[0] is None or b[0] is None: return x
    return None

# ------------------------------------------------------------------------------------------------ 2. gaps where parts meet
MOVING = re.compile(r"_leaf|leaf_glass|door-furniture|furniture|handle", re.I)


FURNISHING = re.compile(r"^SPEC-(?!SKIRT|FLR)")          # loose furniture and decor: separate objects, not the building's joints


def meets(a, b):
    """parts that should meet face to face where they are close (a slot between them is a fault). Door leaves and their
    furniture move: the clearance round a leaf is the door's, not a gap in the build. Loose furnishings stand apart."""
    ga, gb = a["group"], b["group"]
    if FURNISHING.match(a["name"]) or FURNISHING.match(b["name"]): return False
    if MOVING.search(a["name"]) or MOVING.search(b["name"]) or a["props"].get("door_leaf") or b["props"].get("door_leaf"): return False
    if a["ctx"] or b["ctx"] or a["foliage"] or b["foliage"]: return False
    if ga == gb and ga in WALLS | ROOFS | FLOORS | {"fitting"}: return True
    pair = {ga, gb}
    if pair <= WALLS: return False                      # different leaves of a wall: the cavity is by design
    if pair & {"window", "door", "rooflight"} and pair & (WALLS | {"lintel", "fitting"}): return True     # frames to reveals
    if pair & {"wall_outer", "wall_lining"} and pair & (ROOFS | FLOORS | {"floor_finish", "ceiling"}): return True
    if "floor_finish" in pair and pair & {"wall_lining", "fitting"}: return True
    return False


def sample_face_points(V, t, step=0.25):
    a, b, c = V[t[0]], V[t[1]], V[t[-1]] if len(t) == 3 else V[t[2]]
    pts = []
    n = max(1, int(max((b - a).length, (c - a).length) / step))
    for i in range(n + 1):
        for j in range(n + 1 - i):
            u, v = (i + 0.33) / (n + 1), (j + 0.33) / (n + 1)
            if u + v < 1: pts.append(a + (b - a) * u + (c - a) * v)
    return pts


gap_pairs = {}; gap_tested = {}
def slot_open(m, n):
    """the slot at m (between two facing faces, normal n) opens to free space within 0.6 m in its own plane"""
    u = n.cross(Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))).normalized(); v = n.cross(u)
    for d_ in (u, -u, v, -v):
        if TREE.ray_cast(m, d_, 0.6)[0] is None: return True
    return False


for pi, p in enumerate(parts):
    if p["foliage"] or p["open"] or p["ctx"] or p["buried"]: continue
    if p["group"] not in WALLS | ROOFS | FLOORS | {"window", "door", "fitting", "lintel", "floor_finish", "ceiling", "rooflight"}: continue
    for k, t in enumerate(p["T"]):
        if len(t) < 3: continue
        a, b, c = p["V"][t[0]], p["V"][t[1]], p["V"][t[2]]
        n = (b - a).cross(c - a)
        if n.length < 1e-10: continue
        area = n.length / 2; n.normalize()
        if area < 2e-4: continue
        for q in sample_face_points(p["V"], t, 0.2)[:40]:
            hit = TREE.ray_cast(q + n * 1e-4, n, 0.03)
            if hit[0] is None: continue
            d = hit[3]; j = owner[hit[2]]
            if j == pi or d <= 0.002: continue
            if hit[1].dot(n) > -0.9: continue          # not a facing face
            o = parts[j]
            if not meets(p, o) or o["buried"]: continue
            key = tuple(sorted((p["name"], o["name"])))
            if gap_tested.get(key, 0) >= 6 and key not in gap_pairs: continue
            gap_tested[key] = gap_tested.get(key, 0) + 1
            mouth = slot_mouth(q + n * (d / 2), n, d)
            if mouth is None: continue
            eye = visible(mouth)
            if eye is None: continue
            g = gap_pairs.setdefault(key, dict(a=short(p), b=short(o), groups=[p["group"], o["group"]], n=0, max_mm=0, min_mm=1e9, at=None))
            g["n"] += 1; g["max_mm"] = max(g["max_mm"], round(d * 1000, 1)); g["min_mm"] = min(g["min_mm"], round(d * 1000, 1))
            if g["at"] is None: g["at"] = [round(x, 3) for x in (mouth.x, mouth.z, -mouth.y)]; g["eye"] = eye       # viewer frame (x, y, z)
FAULTS["gap"] = sorted(gap_pairs.values(), key=lambda g: -g["n"])
log("gaps:", len(FAULTS["gap"]), "pairs")

# ------------------------------------------------------------------------------------------------ 3. coplanar same-facing overlaps
def plane_key(n, d):
    return (round(n.x, 2), round(n.y, 2), round(n.z, 2), round(d * 1000))


def tri2d(P, o, u, v): return [((x - o).dot(u), (x - o).dot(v)) for x in P]


def clip(subj, clipper):
    def inside(p, a, b): return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-12
    def inter(p1, p2, a, b):
        x1, y1 = p1; x2, y2 = p2; x3, y3 = a; x4, y4 = b
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) < 1e-15: return p2
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    out = subj
    for i in range(len(clipper)):
        a, b = clipper[i], clipper[(i + 1) % len(clipper)]
        inp, out = out, []
        if not inp: break
        s = inp[-1]
        for e in inp:
            if inside(e, a, b):
                if not inside(s, a, b): out.append(inter(s, e, a, b))
                out.append(e)
            elif inside(s, a, b): out.append(inter(s, e, a, b))
            s = e
    return out


def area2(P):
    return abs(sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))) / 2 if len(P) >= 3 else 0.0


def ccw(P):
    s = sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))
    return P if s > 0 else P[::-1]


buckets = {}
for pi, p in enumerate(parts):
    if p["foliage"] or p["open"] or p["buried"]: continue
    for k, t in enumerate(p["T"]):
        P = [p["V"][i] for i in t]
        if len(P) < 3: continue
        n = (P[1] - P[0]).cross(P[2] - P[0])
        if n.length < 1e-10: continue
        ar = n.length / 2; n.normalize()
        if ar < 1e-4: continue
        d = n.dot(P[0])
        buckets.setdefault(plane_key(n, d), []).append((pi, k, n, d, P))
zf = {}
seen_keys = set()
for key, lst in buckets.items():
    # the same plane may straddle a 1 mm bin: compare with the next bin up too
    k2 = (key[0], key[1], key[2], key[3] + 1)
    cand = lst + buckets.get(k2, [])
    if len(cand) < 2: continue
    import numpy as np
    points = np.array([[tuple(v) for v in row[4][:3]] for row in cand])
    # GLB polygons are triangles. Match the existing AABB tolerance before
    # entering the narrow phase, preserving pair order and both plane bins.
    bb_lo, bb_hi = points.min(axis=1), points.max(axis=1)
    part_ids = np.array([row[0] for row in cand])
    for i in range(len(lst)):
        pi, ki, ni, di, Pi = lst[i]
        hit = (part_ids[i+1:] != pi) & np.all(bb_hi[i+1:] >= bb_lo[i] - 1e-6, axis=1) & np.all(bb_lo[i+1:] <= bb_hi[i] + 1e-6, axis=1)
        for j in (np.flatnonzero(hit) + i + 1):
            pj, kj, nj, dj, Pj = cand[j]
            if abs(di - dj) > 0.0005 or ni.dot(nj) < 0.999: continue
            u = (Pi[1] - Pi[0]).normalized(); v = ni.cross(u)
            A = ccw(tri2d(Pi, Pi[0], u, v)); B = ccw(tri2d(Pj, Pi[0], u, v))
            Cp = clip(A, B); ov = area2(Cp)
            if ov < 1e-4: continue
            cx = sum(c_[0] for c_ in Cp) / len(Cp); cy = sum(c_[1] for c_ in Cp) / len(Cp)
            cpt = Pi[0] + u * cx + v * cy + ni * 0.002
            eye = visible(cpt, ni, reach=30.0)
            if eye is None: continue
            pa, pb = parts[pi], parts[pj]
            if FURNISHING.match(pa["name"]) and FURNISHING.match(pb["name"]): continue      # two loose items side by side
            kk = tuple(sorted((pa["name"], pb["name"])))
            z = zf.setdefault(kk, dict(a=short(pa), b=short(pb), groups=[pa["group"], pb["group"]], area_cm2=0.0, at=[round(x, 3) for x in (cpt.x, cpt.z, -cpt.y)], eye=eye))
            z["area_cm2"] = round(z["area_cm2"] + ov * 1e4, 1)
FAULTS["z_fight"] = sorted(zf.values(), key=lambda z: -z["area_cm2"])
log("z-fighting:", len(FAULTS["z_fight"]), "pairs")

# ------------------------------------------------------------------------------------------------ 4. above the roof planes
rV, rT, aV, aT = [], [], [], []
for p in parts:
    if p["group"] in ROOFS and not p["ctx"]:
        b = len(aV); aV.extend(p["V"]); aT.extend(tuple(b + i for i in t) for t in p["T"])
for p in parts:
    # the roof PLANES are the tile covers (material 'tile'), never the eaves boards and gutters (RE-/RG-) hung below them
    if p["group"] == "roof_cover" and not p["ctx"] and any("tile" in m.lower() for m in p["mats"]) and not re.search(r"ridge|hip|valley|^RT-|^RE-|^RG-", p["name"], re.I):
        b = len(rV); rV.extend(p["V"]); rT.extend(tuple(b + i for i in t) for t in p["T"])
ROOF = BVHTree.FromPolygons(rV, rT) if rT else None
ROOFALL = BVHTree.FromPolygons(aV, aT) if aT else None
above = {}
if ROOF:
    for p in parts:
        if p["group"] in ("roof_cover", "ridge", "hip", "valley") or p["ctx"] and not p["foliage"]: continue
        if ROOF_OK.search(p["name"]) or ROOF_OK.search(p["el"]) or ROOF_OK.search(p["spec"]): continue
        worst = 0.0; at = None; cnt = 0
        for v in p["V"]:
            hit = ROOF.ray_cast(v, Vector((0, 0, -1)), 6.0)
            if hit[0] is None or hit[1].z < 0.2: continue
            if hit[3] > 0.02 and ROOFALL.ray_cast(v + Vector((0, 0, 1e-4)), Vector((0, 0, 1)), 20.0)[0] is None:
                cnt += 1
                if hit[3] > worst: worst, at = hit[3], v
        if cnt:
            above[p["name"]] = dict(part=short(p), element=p["el"], group=p["group"], vertices=cnt, max_mm=round(worst * 1000), at=[round(x, 3) for x in (at.x, at.z, -at.y)])
FAULTS["above_roof"] = sorted(above.values(), key=lambda a: -a["max_mm"])
log("above the roof:", len(FAULTS["above_roof"]))

# ------------------------------------------------------------------------------------------------ 5. foliage in solids
ftrees = {}
for pi, p in enumerate(parts):
    if not p["foliage"] or not p["T"]: continue
    ftrees[pi] = BVHTree.FromPolygons(p["V"], p["T"])
fol = {}
for pi, tr in ftrees.items():
    p = parts[pi]
    for qj, q in enumerate(parts):
        if q["foliage"] or q["group"] == "ground" or q["open"] and not re.search(r"glass", " ".join(q["mats"]), re.I): continue
        if re.search(r"Pot_|pot|planter|soil|bed_|mulch", q["name"], re.I): continue
        if p["spec"] and q["group"] in ("slab_layer", "deck", "fitting"): continue     # a pot plant stands on its floor / table
        if q["ctx"] and re.match(r"(Perg_post|Bird_table)", q["name"]):          # posts standing among the surveyed planting
            if (q["lo"].x <= p["hi"].x and q["hi"].x >= p["lo"].x and q["lo"].y <= p["hi"].y and q["hi"].y >= p["lo"].y):
                INFO.setdefault("planting_round_garden_posts", []).append(f"{p['name']} / {q['name']}")
            continue
        if (q["lo"].x > p["hi"].x or q["hi"].x < p["lo"].x or q["lo"].y > p["hi"].y or q["hi"].y < p["lo"].y or q["lo"].z > p["hi"].z or q["hi"].z < p["lo"].z): continue
        qt = BVHTree.FromPolygons(q["V"], q["T"])
        ov = tr.overlap(qt)
        if ov:
            v = p["V"][p["T"][ov[0][0]][0]]
            fol[(p["name"], q["name"])] = dict(foliage=short(p), solid=short(q), solid_group=q["group"], triangles=len(ov), at=[round(x, 3) for x in (v.x, v.z, -v.y)])
FAULTS["foliage_in_solid"] = sorted(fol.values(), key=lambda f: -f["triangles"])
log("foliage in solids:", len(FAULTS["foliage_in_solid"]))

# ------------------------------------------------------------------------------------------------ 6. missing faces seen from walkable positions
DIRS = fib(args.rays)
miss = {}; leaks = {}; raw = {}
for label, pt, indoor in positions:
    # indoors for a walk/camera point: inside some room polygon at that height
    if indoor is None:
        vx, vy, vz = pt.x, pt.z, -pt.y
        indoor = any(in_poly(vx, vz, r["polygon"]) and r["floor_y"] - 0.1 < vy < r["floor_y"] + 2.6 for r in vs["rooms"])
    hits = []
    back = 0
    for d in DIRS:
        h = TREE.ray_cast(pt, d, 200.0)
        hits.append(h)
        if h[0] is not None and h[1].dot(d) > 0.05 and not tri_ds[h[2]]: back += 1
    if back > 0.35 * len(DIRS):
        INFO["positions_inside_solids"].append(dict(position=label, back_fraction=round(back / len(DIRS), 2)))
        continue
    room_here = None
    if indoor:
        vx, vy, vz = pt.x, pt.z, -pt.y
        room_here = next((r["id"] for r in vs["rooms"] if in_poly(vx, vz, r["polygon"]) and r["floor_y"] - 0.1 < vy < r["floor_y"] + 2.7), None)
    for d, h in zip(DIRS, hits):
        if h[0] is not None and indoor and room_here and not BARE_OK_ROOMS.search(room_here) and h[3] < 8.0:
            o = parts[owner[h[2]]]
            pl_ = allT[h[2]]
            mi = None
            mname = o["mats"][0] if len(o["mats"]) == 1 else None
            if mname is None and o["mats"]:
                # multi-material part: the polygon's own material
                k_local = h[2] - o['tri_offset']
                try: mname = o["ob"].data.materials[o["ob"].data.polygons[k_local].material_index].name
                except Exception: mname = o["mats"][0]
            if mname and RAW.match(mname):
                if FINISH_PENDING.match(o["name"]):
                    INFO.setdefault("finish_pending_spec_v2", {}); INFO["finish_pending_spec_v2"][o["name"]] = INFO["finish_pending_spec_v2"].get(o["name"], 0) + 1
                    continue
                rk = (room_here, o["name"])
                rr = raw.setdefault(rk, dict(room=room_here, part=short(o), material=mname, group=o["group"], rays=0,
                                             at=[round(x, 3) for x in (h[0].x, h[0].z, -h[0].y)], seen_from=label))
                rr["rays"] += 1
    for d, h in zip(DIRS, hits):
        if h[0] is None:
            if indoor:
                lk = leaks.setdefault(label.split(" (")[0], dict(position=label, rays=0, dir=[round(d.x, 2), round(d.z, 2), round(-d.y, 2)]))
                lk["rays"] += 1
            continue
        if h[1].dot(d) > 0.05 and not tri_ds[h[2]]:
            o = parts[owner[h[2]]]
            m = miss.setdefault(o["name"], dict(part=short(o), element=o["el"], group=o["group"], rays=0, seen_from=label,
                                                at=[round(x, 3) for x in (h[0].x, h[0].z, -h[0].y)], dist_m=round(h[3], 2)))
            m["rays"] += 1
FAULTS["missing_face"] = sorted([m for m in miss.values() if m["rays"] >= 2], key=lambda m: -m["rays"])
FAULTS["sky_leak"] = sorted([l for l in leaks.values() if l["rays"] >= 2], key=lambda l: -l["rays"])
FAULTS["raw_surface"] = sorted([r for r in raw.values() if r["rays"] >= 3], key=lambda r: -r["rays"])
INFO["single_ray_back_faces"] = len([m for m in miss.values() if m["rays"] < 2])
log("missing faces:", len(FAULTS["missing_face"]), "parts; sky leaks:", len(FAULTS["sky_leak"]), "rooms;", len(positions), "positions")

# open items Jack must decide (spec gaps) or that wait on a named next fix: each with its reason, reported, never silent
ALLOW = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "integrity_allow.json")))["allow"]
allowed = {}
for k, lst in FAULTS.items():
    keep = []
    for f in lst:
        txt = " ".join(str(f.get(x, "")) for x in ("a", "b", "part", "foliage", "solid", "position", "room"))
        hit = next((a for a in ALLOW if a["category"] == k and a.get("version", args.version) == args.version and all(t in txt for t in a["match"])), None)
        if hit: allowed.setdefault(k, []).append(dict(f, allowed=hit["reason"]))
        else: keep.append(f)
    FAULTS[k] = keep
BLOCKING = ("open_shell", "gap", "z_fight", "above_roof", "foliage_in_solid", "missing_face", "sky_leak", "raw_surface")   # raw_surface blocking from 1 Nov (rows 185, 191)
counts = {k: len(v) for k, v in FAULTS.items()}
res = dict(version=args.version, stage=S, asbuilt=args.asbuilt, glb=os.path.basename(glb), glb_mtime=os.path.getmtime(glb),
           written=time.time(), passed=not any(counts[k] for k in BLOCKING), counts=counts, blocking=list(BLOCKING),
           allowed=allowed, allowed_counts={k: len(v) for k, v in allowed.items()},
           note="raw_surface (construction seen from a finished room) is BLOCKING (rows 185, 191; the finish pass is tools/house/hb_finish.py)", faults={k: v[:200] for k, v in FAULTS.items()},
           info={k: (v[:100] if isinstance(v, list) else v) for k, v in INFO.items()}, info_counts={k: (len(v) if isinstance(v, list) else v) for k, v in INFO.items()},
           positions=len(positions), rays_per_position=len(DIRS),
           rules="row 179: shells closed; gaps <= 2 mm where parts meet; no same-facing coplanar overlap > 1 cm2; nothing above the roof planes "
                 "> 20 mm except chimney/flue/vent/rooflight/aerial/flashing; no foliage through a solid; no back face or sky seen from a walkable position")
out = args.out or os.path.join(site, f"{args.version}_integrity.json")
json.dump(res, open(out, "w"), indent=1)
log("PASS" if res["passed"] else "FAIL", counts, "->", out)
