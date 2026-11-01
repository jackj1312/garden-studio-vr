"""Light Workbench renders of a generated house GLB (8 GB Mac: Workbench only, <=1200 px, one at a time).

    nice -n 10 Blender -b --factory-startup --python tools/house/house_views.py -- --glb <v.glb> --out <dir> \
        [--stage N] [--views persp_front,persp_rear,plan_ground,plan_first,elev_east,...] [--px 1000]

--stage N shows the parts present at the END of stage N (stage_in <= N < stage_out), like the viewer's slider.
Ortho views take an explicit real-world window (x0 y0 x1 y1 in the drawing frame) so they can be laid over the
drawing crops by house_overlay.py. Writes <out>/<view>[_sN].png and <out>/<view>.json (the camera window)."""
import sys, os, json, math, argparse
import bpy
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--stage", type=float, default=None); ap.add_argument("--views", default="persp_front,persp_rear")
ap.add_argument("--px", type=int, default=1000); ap.add_argument("--windows", default="")
ap.add_argument("--hide", default="", help="comma list of groups to hide"); ap.add_argument("--only", default="")
ap.add_argument("--xray", action="store_true"); ap.add_argument("--eevee", action="store_true"); ap.add_argument("--tag", default="")
ap.add_argument("--asbuilt", default="off", help="on: the as-built records replace the drawn parts (customer view); off: the drawing")
ap.add_argument("--hdri", default="assets/hdri/kloofendal_43d_clear_puresky_2k.exr"); ap.add_argument("--transform", default="Standard")
ap.add_argument("--sun", type=float, default=4.5)
ap.add_argument("--hide-leaves", action="store_true", help="hide door leaves (the viewer's 'No doors'): doorway frames see into the room")
ap.add_argument("--headlight", type=float, default=0.0, help="cam: views: a warm point light of this power (W) just above the eye (room lights on, as a visit)")
ap.add_argument("--cams", default="", help="JSON list of {name, eye, target, lens} in the VIEWER frame (x, y up, z): close-up "
                "inspection and the spec cameras; views named cam:<name> render them")
ap.add_argument("--sun-dir", default="filmed", help="filmed (bearing 138, 22 up) | afternoon (234, 25): the spec's lighting")
ap.add_argument("--photo-frame", action="store_true", help="the GLB is in the garden model's photo frame: cameras shift by -(4.63, -3.09, -0.231)")
args = ap.parse_args(argv)
os.makedirs(args.out, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=args.glb)
sc = bpy.context.scene

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
replaced = set()
elp = args.glb.replace("_quest.glb", ".glb").replace(".glb", "_elements.json")
if args.asbuilt == "on" and os.path.exists(elp):
    for e in json.load(open(elp))["elements"]:
        if e.get("layer") == "as_built": replaced.update(e.get("replaces", []))
hide = set(g for g in args.hide.split(",") if g)
only = set(g for g in args.only.split(",") if g)
for ob in list(sc.objects):
    if ob.type != "MESH": continue
    ud = ob
    src = ob if "stage_in" in ob.keys() else (ob.parent if ob.parent and "stage_in" in ob.parent.keys() else None)
    if src is None: continue
    si = src.get("stage_in", 1); so = src.get("stage_out", 99) or 99
    g = src.get("group", "")
    vis = True
    if args.stage is not None and not (si <= args.stage < so): vis = False
    if g in hide: vis = False
    if only and g not in only: vis = False
    if src.get("as_built") and args.asbuilt != "on": vis = False
    if args.asbuilt == "on" and src.get("element") in replaced: vis = False
    if args.hide_leaves and src.get("door_leaf"): vis = False
    ob.hide_render = not vis
    ob.hide_viewport = not vis

ap2 = args
if "--eevee" in argv:
    for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try: sc.render.engine = e; break
        except TypeError: pass
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
    nt = w.node_tree; bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    hdr = args.hdri if os.path.isabs(args.hdri) else os.path.join(ROOT, args.hdri)
    if os.path.exists(hdr):
        te = nt.nodes.new("ShaderNodeTexEnvironment"); te.image = bpy.data.images.load(hdr); nt.links.new(te.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.8
    sd = bpy.data.lights.new("sun", "SUN"); sd.energy = args.sun; sd.angle = math.radians(1.5)
    so = bpy.data.objects.new("sun", sd); sc.collection.objects.link(so)
    az, el = math.radians(-138.0), math.radians(22.0)           # the garden's filmed sun (drawing frame: +y into the house)
    if args.sun_dir in ("afternoon", "filmed"):
        # spec lighting: filmed bearing 138 deg (SE) 22 up; afternoon 234 deg (SW) 25 up; house +x = north, +z(viewer) = east
        b_, el = (math.radians(234.0), math.radians(25.0)) if args.sun_dir == "afternoon" else (math.radians(138.0), math.radians(22.0))
        north, east = math.cos(b_), math.sin(b_)
        dirv0 = Vector((north * math.cos(el), -east * math.cos(el), math.sin(el)))
        az = math.atan2(dirv0.x, dirv0.y)
    dirv = Vector((math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el)))
    so.rotation_euler = (-dirv).to_track_quat("-Z", "Y").to_euler()
    try:
        sc.eevee.use_shadows = True; sc.eevee.use_gtao = True
    except Exception: pass
    vts = [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items]
    sc.view_settings.view_transform = args.transform if args.transform in vts else ("AgX" if "AgX" in vts else "Filmic")
    sc.render.film_transparent = False
    eevee = True
else:
    eevee = False
if not eevee: sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"; sh.color_type = "MATERIAL"; sh.show_cavity = True; sh.show_object_outline = True
sh.cavity_type = "WORLD"
if args.xray: sh.show_xray = True; sh.xray_alpha = 0.6
sc.display.shading.background_type = "VIEWPORT"
sc.render.film_transparent = False
sc.render.resolution_percentage = 100

# drawing frame windows: name -> (kind, params)
# plan views look down; elevations look horizontally; sections cut with a clip box via camera clip planes
WIN = {
    "plan_ground": ("plan", dict(x0=-1.5, y0=-4.0, x1=11.0, y1=10.0, zcut=1.2)),
    "plan_first": ("plan", dict(x0=-1.5, y0=-4.0, x1=11.0, y1=10.0, zcut=3.9)),
    "plan_roof": ("plan", dict(x0=-1.5, y0=-4.0, x1=11.0, y1=10.0, zcut=20.0)),
    "elev_east": ("elev", dict(look=(0, 1, 0), u0=-1.0, u1=11.0, z0=-0.8, z1=9.2)),         # front: looking +y (x to the right)
    "elev_west": ("elev", dict(look=(0, -1, 0), u0=-11.0, u1=0.6, z0=-0.8, z1=9.6)),        # rear: looking -y (x mirrored)
    "elev_north": ("elev", dict(look=(-1, 0, 0), u0=-3.0, u1=9.8, z0=-0.8, z1=9.0)),        # right flank: looking -x (y to the right)
    "elev_south": ("elev", dict(look=(1, 0, 0), u0=-10.0, u1=3.0, z0=-0.8, z1=9.2)),        # party side: looking +x
}
if args.windows:
    WIN.update(json.load(open(args.windows)))


def cam_obj():
    cd = bpy.data.cameras.new("cam"); co = bpy.data.objects.new("cam", cd); sc.collection.objects.link(co); sc.camera = co
    return co, cd


def render(name):
    path = os.path.join(args.out, name + (f"_s{int(args.stage)}" if args.stage is not None else "") + (f"_{args.tag}" if args.tag else "") + ".png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("wrote", path)
    return path


co, cd = cam_obj()
CAMS = {}
if args.cams:
    for c_ in json.load(open(args.cams)): CAMS[c_["name"]] = c_
REFS = os.path.join(ROOT, "assets", "sites", "front-garden-model", "refs.json")
for v in [v for v in args.views.split(",") if v]:
    if v.startswith("ref_"):
        # a photo's solved camera (refs.json, garden viewer frame: x = photo x, y up, z = -photo y) moved into the drawing
        # frame by the audit-4 registration (+4.63, -3.09, -0.231): the matched view for a photo / model sheet
        R_ = next(r for r in json.load(open(REFS))["refs"] if os.path.basename(r["file"]).startswith(v[4:]))
        px, py, pz = R_["pos"]; dx, dy, dz = R_["dir"]
        eye = Vector((px + 4.63, -pz - 3.09, py - 0.231)); fwd = Vector((dx, -dz, dy)).normalized()
        cd.type = "PERSP"; cd.sensor_fit = "VERTICAL"; cd.angle_y = math.radians(R_["vfov"])
        sc.render.resolution_x, sc.render.resolution_y = R_["w"], R_["h"]
        co.location = eye; co.rotation_euler = fwd.to_track_quat("-Z", "Y").to_euler()
        cd.clip_start = 0.05; cd.clip_end = 200
        render(v)
        continue
    if v.startswith("cam:"):
        c_ = CAMS[v[4:]]
        ex, ey, ez = c_["eye"]; tx, ty, tz = c_["target"]
        eye, tgt = Vector((ex, -ez, ey)), Vector((tx, -tz, ty))          # viewer (x, y up, z) -> drawing (x, -z, y)
        cd.type = "PERSP"; cd.sensor_fit = "HORIZONTAL"; cd.sensor_width = 36.0; cd.lens = c_.get("lens", 18)
        sc.render.resolution_x = args.px; sc.render.resolution_y = int(args.px * c_.get("aspect", 0.5625))
        co.location = eye; co.rotation_euler = (tgt - eye).to_track_quat("-Z", "Y").to_euler()
        cd.clip_start = 0.02; cd.clip_end = 200
        if args.headlight > 0:
            hl = bpy.data.objects.get("headlight")
            if hl is None:
                ld = bpy.data.lights.new("headlight", "POINT"); ld.color = (1.0, 0.86, 0.72); ld.shadow_soft_size = 0.4
                hl = bpy.data.objects.new("headlight", ld); sc.collection.objects.link(hl)
            hl.data.energy = args.headlight; hl.location = eye + Vector((0, 0, 0.45))
        render(v[4:])
        continue
    if v.startswith("persp"):
        cd.type = "PERSP"; cd.lens = 28
        sc.render.resolution_x = args.px; sc.render.resolution_y = int(args.px * 0.66)
        P = {"persp_front": ((14.0, -14.0, 7.5), (4.5, 1.0, 3.0)), "persp_rear": ((-4.5, 20.0, 8.5), (4.5, 5.0, 2.8)),
             "persp_rear_r": ((15.0, 17.0, 7.0), (4.5, 5.0, 2.5)), "persp_top": ((4.5, -9.0, 22.0), (4.5, 3.0, 3.0)),
             "persp_inside": ((2.2, 7.4, 1.6), (4.5, 1.0, 1.4)),
             "persp_street": ((3.0, -27.5, 1.65), (4.6, 0.0, 2.6)), "persp_garden": ((1.2, -15.5, 1.65), (5.0, -1.0, 2.4)),
             "persp_front_near": ((2.4, -7.2, 1.65), (4.2, -1.0, 2.2)), "persp_site": ((22.0, -18.0, 12.0), (6.0, 2.0, 1.0)),
             # interiors at Jack's eye height (1.74 m standing, 6 ft 1): under beam 6, the stair head both ways, the porch
             "persp_steel": ((2.0, 7.3, 1.74), (2.2, 3.6, 2.05)), "persp_stairhead": ((5.06, 3.05, 2.103 + 1.74), (5.06, 1.6, 3.2)),
             "persp_landing": ((4.6, 1.55, 2.6755 + 1.74), (5.06, 3.4, 2.2)), "persp_porch": ((4.9, -1.2, 1.74), (3.3, -1.2, 1.5)),
             "persp_road": ((4.3, -25.0, -0.311 + 1.74), (4.3, 0.0, 2.6)),
             "persp_pavement": ((2.0, -23.3, -0.211 + 1.74), (4.6, 0.0, 2.4)), "persp_drive": ((9.3, -14.0, -0.24 + 1.74), (4.8, 0.0, 2.4)),
             # garden match (log 162): the garden test and the house build from the same four poses, eye 1.65
             "persp_gm_road": ((4.3, -24.6, -0.311 + 1.65), (4.3, 0.0, 2.2)), "persp_gm_path": ((1.3, -3.8, -0.25 + 1.65), (3.6, -1.0, 1.2)),
             "persp_gm_drive": ((9.3, -14.0, -0.24 + 1.65), (4.8, 0.0, 2.0)), "persp_gm_lawn": ((1.6, -13.2, -0.227 + 1.65), (5.6, -1.0, 2.0))}[v]
        eye, tgt = Vector(P[0]), Vector(P[1])
        if args.photo_frame: eye -= Vector((4.63, -3.09, -0.231)); tgt -= Vector((4.63, -3.09, -0.231))
        co.location = eye
        co.rotation_euler = (tgt - eye).to_track_quat("-Z", "Y").to_euler()
        cd.clip_start = 0.05; cd.clip_end = 200
        render(v)
        continue
    kind, w = WIN[v]
    cd.type = "ORTHO"
    if kind == "plan":
        W, H = w["x1"] - w["x0"], w["y1"] - w["y0"]
        sc.render.resolution_x = args.px; sc.render.resolution_y = int(round(args.px * H / W))
        cd.ortho_scale = max(W, H)
        co.location = ((w["x0"] + w["x1"]) / 2, (w["y0"] + w["y1"]) / 2, w["zcut"])
        co.rotation_euler = (0, 0, 0)
        cd.clip_start = 0.0; cd.clip_end = 30
    elif kind == "elev":
        look = Vector(w["look"]); W, H = w["u1"] - w["u0"], w["z1"] - w["z0"]
        sc.render.resolution_x = args.px; sc.render.resolution_y = int(round(args.px * H / W))
        cd.ortho_scale = max(W, H)
        right = look.cross(Vector((0, 0, 1))).normalized()
        uc = (w["u0"] + w["u1"]) / 2; zc = (w["z0"] + w["z1"]) / 2
        # u is measured along 'right' from the origin
        base = right * uc + Vector((0, 0, zc))
        dist = w.get("dist", 40.0)
        cut = w.get("cut")                    # section: the plane offset along look where the cut is
        if cut is not None:
            co.location = base + look * (cut - 0.001) - look * 0.0
            co.location = base - look * 0.0 + look * cut
            cd.clip_start = 0.0; cd.clip_end = 60
            co.location = base + look * cut
        else:
            co.location = base - look * dist
            cd.clip_start = 0.01; cd.clip_end = 200
        co.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
        if cut is not None: co.location = co.location  # camera on the cut plane: clip_start 0 keeps everything beyond
    json.dump(dict(view=v, kind=kind, window=w, px=[sc.render.resolution_x, sc.render.resolution_y]),
              open(os.path.join(args.out, v + ".json"), "w"))
    render(v)
