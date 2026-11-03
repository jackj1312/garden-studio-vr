"""Close-up test sheet for library assets (WORKFLOW 'Studio asset library': every new asset passes one before placement):
Eevee (never Cycles), ~480 px per view, a 3/4 front view and a second angle, neutral grey studio, soft sun. Light work.

    nice -n 10 Blender -b --factory-startup --python tools/library/test_sheet.py -- --out <dir> --items soft/towel_pair_rail_BTH-TOWELS,blendkit/BK-SOFA-BURRARD [--adapt]

--adapt: blendkit items are shown as the build makes them (hb_furnish proto: front turned to +Y, pivot at the base centre)."""
import sys, os, math, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "house"))
import bpy
from mathutils import Vector, Matrix
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--items", required=True); ap.add_argument("--px", type=int, default=480)
ap.add_argument("--lib", default=os.path.expanduser("~/Desktop/garden-scans/asset-library")); ap.add_argument("--views", default="34,side")
a = ap.parse_args(argv); os.makedirs(a.out, exist_ok=True)
import hb_furnish as HF
sc = bpy.context.scene
for o in list(bpy.data.objects): bpy.data.objects.remove(o)          # the factory scene's cube, camera and light
for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try: sc.render.engine = e; break
    except TypeError: pass
sc.render.resolution_x = sc.render.resolution_y = a.px; sc.render.film_transparent = False
try: sc.view_settings.view_transform = "Standard"
except Exception: pass
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.55, 0.56, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 3.0; sun.data.angle = 0.3
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); sc.collection.objects.link(sun)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 50
gm = bpy.data.meshes.new("g"); gm.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [], [(0, 1, 2, 3)])
g = bpy.data.objects.new("ground", gm); sc.collection.objects.link(g)
gmat = bpy.data.materials.new("gm"); gmat.use_nodes = True; gmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1); gm.materials.append(gmat)
def log(*x): print("[sheet]", *x, flush=True)
for item in [x for x in a.items.split(",") if x]:
    kind, name = item.split("/", 1)
    for o in [o for o in sc.objects if o.name.startswith("A_")]: bpy.data.objects.remove(o)
    if kind == "soft": pr = HF.proto("soft:" + name, log, front="+Y", cap=40000)
    else: pr = HF.proto(name, log, front=HF.ASSET_CFG.get(name, {}).get("front", "-Y"), cap=40000)
    if pr is None: log("missing", item); continue
    me = pr[0]; ob = bpy.data.objects.new("A_" + name, me); sc.collection.objects.link(ob)
    bb = [Vector(c) for c in ob.bound_box]; lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))); hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
    g.location.z = lo.z - 0.0005
    c = (lo + hi) / 2; r = max((hi - lo).length / 2, 0.05)
    for vw in a.views.split(","):
        d = Vector((0.75, 1.6, 0.75)) if vw == "34" else (Vector((1.8, 0.2, 0.35)) if vw == "side" else Vector((0.2, 1.8, 0.35)))
        d.normalize(); cam.location = c + d * r * 2.9
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(a.out, f"{name}__{vw}.png"); bpy.ops.render.render(write_still=True)
    log("rendered", item, f"{(hi - lo).x * 1000:.0f}x{(hi - lo).y * 1000:.0f}x{(hi - lo).z * 1000:.0f} mm")
