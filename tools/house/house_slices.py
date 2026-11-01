"""Cut a generated house GLB with planes (plan cuts, section planes) and write the cut lines as 2D segments, per part,
for the drawing checks (house_overlay.py). Light: bmesh bisect only, no render.

    nice Blender -b --factory-startup --python tools/house/house_slices.py -- --glb <v.glb> --spec <build_versions.json> \
        --out <slices.json> [--stage N]

Planes: plan_ground (z = 1.2 above ground FFL), plan_first (first FFL + 1.2), and every section of the spec
(origin + normal). 2D frame: plans (x, y) in the drawing frame; sections (u, z) with u = y for an x-normal cut and
u = x for a y-normal cut."""
import sys, json, argparse, math
import bpy, bmesh
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--stage", type=float, default=None)
args = ap.parse_args(argv)
spec = json.load(open(args.spec))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=args.glb)

ff = 2.6755
planes = {"plan_ground": ((0, 0, 1.2), (0, 0, 1), "xy"), "plan_first": ((0, 0, ff + 1.2), (0, 0, 1), "xy")}
for s in spec.get("sections", []):
    n = s["normal"]
    planes["section_" + s["name"]] = (tuple(s["origin"]), tuple(n), "yz" if abs(n[0]) > 0.5 else "xz")

parts = []
for ob in bpy.data.objects:
    if ob.type != "MESH": continue
    src = ob if "stage_in" in ob.keys() else (ob.parent if ob.parent and "stage_in" in ob.parent.keys() else None)
    if src is None: continue
    si = src.get("stage_in", 1); so = src.get("stage_out", 99) or 99
    if args.stage is not None and not (si <= args.stage < so): continue
    if args.stage is None and src.get("stage_out"): continue        # final state
    if src.get("as_built") or src.get("context"): continue            # the drawing check is of the drawn model only
    parts.append((ob, src))

out = {}
for name, (o, n, frame) in planes.items():
    O, N = Vector(o), Vector(n).normalized()
    res = []
    for ob, src in parts:
        mw = ob.matrix_world
        # quick reject by bounding box
        bb = [mw @ Vector(c) for c in ob.bound_box]
        ds = [(p - O).dot(N) for p in bb]
        if min(ds) > 0 or max(ds) < 0: continue
        bm = bmesh.new(); bm.from_mesh(ob.data); bm.transform(mw)
        r = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=O, plane_no=N, clear_inner=False, clear_outer=False)
        segs = []
        for e in [g for g in r["geom_cut"] if isinstance(g, bmesh.types.BMEdge)]:
            a, b = e.verts[0].co, e.verts[1].co
            if (a - b).length < 1e-4: continue
            if frame == "xy": segs.append([round(a.x, 4), round(a.y, 4), round(b.x, 4), round(b.y, 4)])
            elif frame == "yz": segs.append([round(a.y, 4), round(a.z, 4), round(b.y, 4), round(b.z, 4)])
            else: segs.append([round(a.x, 4), round(a.z, 4), round(b.x, 4), round(b.z, 4)])
        bm.free()
        if segs:
            res.append(dict(part=ob.name, group=src.get("group"), category=src.get("category"), element=src.get("element"), segs=segs))
    out[name] = dict(origin=o, normal=n, frame=frame, parts=res)
    print(name, len(res), "parts cut")
# elevations: edges of the parts that face each elevation, projected to (u, z) (no hidden-line removal: parts are
# filtered by a depth window; roofs always)
ELEV = {"east": ("y", lambda b: b[0][1] < 1.5, "x"), "west": ("y", lambda b: b[1][1] > 5.0, "x"),
        "north": ("x", lambda b: b[1][0] > 7.9, "y"), "south": ("x", lambda b: b[0][0] < 1.2, "y")}
for en, (axis, keep, uax) in ELEV.items():
    res = []
    for ob, src in parts:
        g = src.get("group")
        if g not in ("wall_outer", "window", "door", "roof_cover", "rooflight"): continue
        mw = ob.matrix_world
        bb = [mw @ Vector(c) for c in ob.bound_box]
        lo = (min(p.x for p in bb), min(p.y for p in bb)); hi = (max(p.x for p in bb), max(p.y for p in bb))
        if g != "roof_cover" and not keep((lo, hi)): continue
        me = ob.data
        segs = []
        for e in me.edges:
            a, b = mw @ me.vertices[e.vertices[0]].co, mw @ me.vertices[e.vertices[1]].co
            if (a - b).length < 0.02: continue
            ua, ub = (a.x, b.x) if uax == "x" else (a.y, b.y)
            if abs(ua - ub) < 1e-4 and abs(a.z - b.z) < 1e-4: continue      # edge seen end-on
            segs.append([round(ua, 4), round(a.z, 4), round(ub, 4), round(b.z, 4)])
        if segs: res.append(dict(part=ob.name, group=g, category=src.get("category"), element=src.get("element"), segs=segs))
    out["elev_" + en] = dict(frame="u" + uax, parts=res)
res = []
for ob, src in parts:                               # roof plan: tile and ridge/hip-tile edges seen from above
    if src.get("group") not in ("roof_cover", "rooflight"): continue
    mw = ob.matrix_world; me = ob.data; segs = []
    for e in me.edges:
        a, b = mw @ me.vertices[e.vertices[0]].co, mw @ me.vertices[e.vertices[1]].co
        if math.hypot(a.x - b.x, a.y - b.y) < 0.02: continue
        segs.append([round(a.x, 4), round(a.y, 4), round(b.x, 4), round(b.y, 4)])
    if segs: res.append(dict(part=ob.name, group=src.get("group"), category=src.get("category"), element=src.get("element"), segs=segs))
out["plan_roof_top"] = dict(frame="xy", parts=res)
json.dump(out, open(args.out, "w"))
