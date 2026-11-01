"""Matched views of the HOUSE for the G6 self-check: the v2 model rendered through solved cameras, zoomed on the house.

    nice -n 10 /Applications/Blender.app/Contents/MacOS/Blender -b master/front-garden.blend \
        --python tools/blender/house_audit_render.py -- --frames walk_0017.jpg,... --out renders/front-garden/house-audit/r \
        [--passes eevee,ids,check,clash] [--box x0 x1 y0 y1 z0 z1] [--px 1000] [--build master/front-garden-v2.py]
        [--prefixes all|H_,P_,R_,N_]   (which objects get outlines; "all" = house AND garden, the audit-2 default for gardens)

Each view is cropped to where --box (default: the whole house and neighbour) falls in that frame, and rendered at up to
--px pixels on the crop's long side (never finer than the real 4K frame), so far views are not a few pixels of house.
The crop of each frame is written to <out>/meta.json; house_pairs.py cuts the real photo to the same window.
eevee: the cheap mockup (front-garden-v2.py's own light, tone map), full scene.
ids:   Workbench, flat random colour per object, only the --prefixes objects (default the house: H_, P_, R_, N_;
       "all": every object, plants of one kind share a colour so beds are not a mess of outlines), transparent background:
       house_pairs.py turns object boundaries into outlines drawn over the real photo.
check: the house wall clash check (bounding boxes of walls).
clash: tools/blender/clash_check.py over EVERY object: solid parts passing through each other, and the ground raster
       (surface over surface, soil over setts, setts through setts), and (audit-4) MUST TOUCH: the build's MUST_TOUCH rules
       (abutting elements, e.g. a shed against the house) must have no gap; written to <out>/clash.json.
Light on the 8 GB Mac: one process, Eevee/Workbench, <=1000 px rendered, no grass hair (CORRECTIONS-LOG 15)."""
import sys, os, json
import bpy, numpy as np
from mathutils import Matrix, Vector

R0 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def opt(n, d=None): return argv[argv.index(n) + 1] if n in argv else d
frames = [f for f in opt("--frames", "").split(",") if f]
out = os.path.join(R0, opt("--out", "renders/front-garden/house-audit/r"))
passes = opt("--passes", "eevee,ids").split(",")
src = os.path.join(R0, opt("--build", "master/front-garden-v2.py"))
PX = int(opt("--px", "1000"))
BOX = [float(v) for v in argv[argv.index("--box") + 1: argv.index("--box") + 7]] if "--box" in argv else [-11.0, 5.2, 0.2, 7.0, 0.0, 9.0]
os.makedirs(os.path.join(out, "ids"), exist_ok=True)
sys.argv = sys.argv[:sys.argv.index("--") + 1] if "--" in sys.argv else sys.argv   # the build reads its own argv
V = {"__name__": "fg_v2", "__file__": src}
exec(compile(open(src).read(), src, "exec"), V)
V["build"]()
SC = V["SC"]
_pf = opt("--prefixes", "H_,P_,R_,N_")
HOUSE_PREFIX = "" if _pf == "all" else tuple(_pf.split(","))
def _key(n):
    """colour key: plants of one kind share a colour (Plant2_bed_stipa_12 -> Plant2_stipa)"""
    if n.startswith("Plant2_"): return "Plant2_" + n.split("_")[2]
    return n

if "check" in passes:
    # clash check (G6): solid house parts whose boxes overlap in volume share faces or pass through each other.
    # Walls, wall pieces and roofs only; fixtures sitting in a wall are expected.
    import itertools
    solid = [o for o in V["coll"]().objects if o.name.startswith(HOUSE_PREFIX) and o.type == "MESH"
             and any(k in o.name for k in ("_LW_", "_RW_", "_RW", "_side", "_back", "_front", "_return", "_behind", "_wall", "N_wing", "N_far"))
             and not any(k in o.name for k in ("frame", "glass", "net", "room", "sill", "jamb", "head", "soldier", "mull", "sash", "eaves", "porch_", "win_", "plate", "roof", "hip", "ridge", "valley", "R_"))]
    bb = {}
    for o in solid:
        P = np.array([o.matrix_world @ v.co for v in o.data.vertices]); bb[o.name] = (P.min(0), P.max(0))
    hits = []
    for a_, b_ in itertools.combinations(bb, 2):
        lo = np.maximum(bb[a_][0], bb[b_][0]); hi = np.minimum(bb[a_][1], bb[b_][1]); d = hi - lo
        if (d > 0.005).all(): hits.append((a_, b_, float(np.prod(d))))
    print("CLASH CHECK:", len(solid), "solid parts,", len(hits), "overlapping pairs")
    for h in sorted(hits, key=lambda h: -h[2])[:40]: print("  overlap %.4f m3  %s  x  %s" % (h[2], h[0], h[1]))
if "clash" in passes:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import clash_check as CC
    objs = list(V["coll"]().objects)
    sol = CC.solid_clashes(objs); gnd = CC.ground_clashes(objs, soil_ok_near=V.get("SOIL_OK_NEAR", lambda: [])())
    selfov = []
    for o in objs:
        if o.type == "MESH" and any(k in o.name for k in ("edge", "kerb", "border", "upstand", "nosing", "setts")):
            a_ = CC.self_overlap_units(o)
            if a_ > 0.0004: selfov.append({"object": o.name, "overlap_m2": round(a_, 4)})
    print("CLASH (solid):", len(sol), "pairs pass through each other")
    for h in sol[:60]: print("  %.3f m  %s  x  %s  at %s" % (h["depth_m"], h["a"], h["b"], h["at"]))
    print("CLASH (ground):", len(gnd), "overlaps")
    for g in gnd[:60]: print("  %-22s %.4f m2  %s  /  %s  at %s %s" % (g["kind"], g["area_m2"], g["a"], g["b"], g["at"], g.get("spots_0.25m", "")))
    print("CLASH (setts within a run):", selfov)
    opn = CC.open_parts(objs); print("OPEN PARTS (not closed solids):", len(opn), opn[:40])
    mt_fail, mt_all = CC.must_touch(objs, V.get("MUST_TOUCH", []))                  # audit-4: abutting elements must touch
    print("MUST TOUCH:", len(mt_fail), "gaps of", len(mt_all), "rules")
    for r in mt_all: print("  %-22s -> %-22s gap %s  (%s)%s" % (r["a"], r["b"], r["gap_m"], r["why"], "  FAIL" if r in mt_fail else ""))
    os.makedirs(out, exist_ok=True)
    json.dump({"solid": sol, "ground": gnd, "self_overlap": selfov, "open_parts": opn, "must_touch_fail": mt_fail, "must_touch": mt_all}, open(os.path.join(out, "clash.json"), "w"), indent=1)
A = json.load(open(os.path.join(V["SITE_DIR"], "sfm2", "aligned.json"))); Rm = np.array(A["R"]); S = A["scale"]; T = np.array(A["t"])

def window(c):
    """pixel window (solve image px) where BOX falls, padded, clipped"""
    x0, x1, y0, y1, z0, z1 = BOX
    P = np.array([[x, y, z] for x in np.linspace(x0, x1, 9) for y in (y0, y1) for z in np.linspace(z0, z1, 7)])
    M = np.array(c["cam_from_world"]); f, cx, cy = c["camera"]["params"][:3]; w, h = c["camera"]["w"], c["camera"]["h"]
    pc = ((P - T) @ Rm / S) @ M[:, :3].T + M[:, 3]; ok = pc[:, 2] > 0.3
    if ok.sum() < 3: return [0, 0, w, h]
    u = f * pc[ok, 0] / pc[ok, 2] + cx; v = f * pc[ok, 1] / pc[ok, 2] + cy
    pad = 0.03 * max(w, h)
    return [int(max(0, u.min() - pad)), int(max(0, v.min() - pad)), int(min(w, u.max() + pad)), int(min(h, v.max() + pad))]

cam = bpy.data.objects.get("FG_Cam_Frame") or bpy.data.objects.new("FG_Cam_Frame", bpy.data.cameras.new("FG_Cam_Frame"))
if cam.name not in SC.collection.objects: SC.collection.objects.link(cam)
meta = {}
def setup(fr):
    c = A["cameras"][fr]; M_ = np.array(c["cam_from_world"])
    cam.matrix_world = Matrix.Translation(Vector(c["centre"])) @ Matrix((Rm @ M_[:, :3].T @ np.diag([1, -1, -1])).tolist()).to_4x4()
    w, h = c["camera"]["w"], c["camera"]["h"]
    cam.data.sensor_fit = "HORIZONTAL"; cam.data.sensor_width = 36; cam.data.lens = c["camera"]["params"][0] * 36 / w
    cam.data.clip_start = 0.05; SC.camera = cam
    wx0, wy0, wx1, wy1 = window(c)
    native = 2.0 if fr.startswith("walk_") else 1.0                      # 4K walk frames are 2x the solve images
    s = min(PX / max(wx1 - wx0, wy1 - wy0), native)
    SC.render.resolution_x, SC.render.resolution_y = int(round(w * s)), int(round(h * s)); SC.render.resolution_percentage = 100
    SC.render.use_border = True; SC.render.use_crop_to_border = True
    SC.render.border_min_x, SC.render.border_max_x = wx0 / w, wx1 / w
    SC.render.border_min_y, SC.render.border_max_y = 1 - wy1 / h, 1 - wy0 / h
    meta[fr] = {"window": [wx0, wy0, wx1, wy1], "scale": s, "size": [w, h]}

if "eevee" in passes:
    V["mockup"]([], out)                                                 # lights, engine, tone map only
    for fr in frames:
        setup(fr); SC.render.image_settings.file_format = "PNG"
        SC.render.filepath = os.path.join(out, fr.replace(".jpg", ".png"))
        bpy.ops.render.render(write_still=True, scene=SC.name); print("eevee", fr)

if "ids" in passes:
    try: SC.render.engine = "BLENDER_WORKBENCH"
    except TypeError as e: print(e)
    sh = SC.display.shading; sh.light = "FLAT"; sh.color_type = "OBJECT"
    rng = np.random.default_rng(7); names = {}
    keyc = {}
    for i, o in enumerate(sorted(V["coll"]().objects, key=lambda o: o.name)):   # a distinct colour per object, recorded
        if o.name.startswith(HOUSE_PREFIX):
            k = _key(o.name)
            if k not in keyc: keyc[k] = rng.integers(20, 236, 3)
            rgb = keyc[k]; o.color = (*[(v / 255) ** 2.2 for v in rgb], 1); names[o.name] = [int(v) for v in rgb]
    json.dump(names, open(os.path.join(out, "ids", "names.json"), "w"))
    sh.show_cavity = False; sh.show_shadows = False; sh.show_object_outline = False; sh.show_xray = False
    SC.view_settings.view_transform = "Standard"; SC.view_settings.exposure = 0.0
    SC.render.film_transparent = True; SC.render.image_settings.color_mode = "RGBA"; SC.render.dither_intensity = 0.0
    hidden = []
    for o in V["coll"]().objects:
        if not o.name.startswith(HOUSE_PREFIX) and not o.hide_render: o.hide_render = True; hidden.append(o)
    for fr in frames:
        setup(fr); SC.render.image_settings.file_format = "PNG"
        SC.render.filepath = os.path.join(out, "ids", fr.replace(".jpg", ".png"))
        bpy.ops.render.render(write_still=True, scene=SC.name); print("ids", fr)
    for o in hidden: o.hide_render = False
old = json.load(open(os.path.join(out, "meta.json"))) if os.path.exists(os.path.join(out, "meta.json")) else {}
old.update(meta); json.dump(old, open(os.path.join(out, "meta.json"), "w"), indent=1)
print("house_audit_render done", len(frames), "frames ->", out)
