"""Runs on the rented GPU (blender -b scene.blend --python garden_cloud.py -- --out DIR):
rebuild the front garden from plan_v3.json, bake its light maps, export desktop + Quest GLBs,
render proof stills from two walk-video cameras. Everything lands in --out."""
import sys, os, json, time, traceback, math
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else "/workspace/out"
os.makedirs(OUT, exist_ok=True)
J = os.path.dirname(os.path.abspath(__file__))
os.environ["FG_ROOT"] = os.path.join(J, "root")
os.environ["FG_PLAN"] = os.path.join(J, "plan_v3.json")
os.makedirs(os.path.join(J, "root", "master", "polyhaven", "tex"), exist_ok=True)
log = open(os.path.join(OUT, "cloud_log.txt"), "w")
def say(*m):
    line = " ".join(str(x) for x in m); print(line, flush=True); log.write(line + "\n"); log.flush()

prefs = bpy.context.preferences.addons["cycles"].preferences
for t in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = t; prefs.get_devices()
        if any(d.type == t for d in prefs.devices): break
    except TypeError:
        pass
for d in prefs.devices: d.use = d.type != "CPU"
say("devices", [(d.name, d.type, d.use) for d in prefs.devices])

SITE = bpy.data.scenes["Site"]
G = {"__name__": "fg_build", "__file__": os.path.join(J, "front-garden-build.py")}
t0 = time.time()
with bpy.context.temp_override(scene=SITE, view_layer=SITE.view_layers[0]):
    exec(compile(open(os.path.join(J, "front-garden-build.py")).read(), "front-garden-build.py", "exec"), G)
    G["build"](); say("built %.0fs" % (time.time() - t0))
    exec(compile(open(os.path.join(J, "front-garden-bake.py")).read(), "front-garden-bake.py", "exec"), G)
    sun = G["light_rig"](sun_az=48, sun_el=22); sun.data.energy = 5.0; sun.data.color = (1.0, 0.90, 0.76); sun.data.angle = 0.014
    for c in ("FG_Model",):
        bpy.data.collections[c].hide_render = False
    if bpy.data.collections.get("FG_Reference"): bpy.data.collections["FG_Reference"].hide_render = True
    SITE.render.film_transparent = False
    SITE.use_nodes = False
    try:
        t = time.time(); G["bake_ground"](px_per_m=85, samples=256, out_dir=OUT); say("ground baked %.0fs" % (time.time() - t))
    except Exception:
        say("GROUND BAKE FAILED\n" + traceback.format_exc())
    try:
        t = time.time(); G["bake_vertical"](size=4096, samples=256, out_dir=OUT); say("vertical baked %.0fs" % (time.time() - t))
    except Exception:
        say("VERTICAL BAKE FAILED\n" + traceback.format_exc())
    for m in [m for m in bpy.data.materials if m.name.endswith("_gltf")]: bpy.data.materials.remove(m)
    t = time.time()
    G["export_glb"](os.path.join(OUT, "model.glb")); G["export_quest"](os.path.join(OUT, "model_q.glb"))
    say("exported %.0fs" % (time.time() - t))
    # proof stills through the exact pose and lens of two walk frames
    A = json.load(open(os.path.join(J, "aligned.json")))
    import numpy as np
    R = np.array(A["R"])
    cam = bpy.data.objects.get("FG_Cam_Frame") or bpy.data.objects.new("FG_Cam_Frame", bpy.data.cameras.new("FG_Cam_Frame"))
    if cam.name not in SITE.collection.objects: SITE.collection.objects.link(cam)
    SITE.camera = cam
    SITE.render.engine = "CYCLES"; SITE.cycles.device = "GPU"; SITE.cycles.samples = 128; SITE.cycles.use_denoising = True
    SITE.render.resolution_x, SITE.render.resolution_y = 1080, 1920; SITE.render.resolution_percentage = 100
    SITE.render.image_settings.file_format = "PNG"
    for fr in ("walk_0017.jpg", "walk_0169.jpg", "walk_0237.jpg"):
        c = A["cameras"][fr]; M = np.array(c["cam_from_world"])
        Rwc = R @ M[:, :3].T @ np.diag([1, -1, -1])
        cam.matrix_world = Matrix.Translation(Vector(c["centre"])) @ Matrix(Rwc.tolist()).to_4x4()
        cam.data.sensor_fit = "HORIZONTAL"; cam.data.sensor_width = 36; cam.data.lens = c["camera"]["params"][0] * 36 / c["camera"]["w"]
        SITE.render.filepath = os.path.join(OUT, "proof_" + fr.replace(".jpg", ".png"))
        t = time.time(); bpy.ops.render.render(write_still=True, scene=SITE.name); say("still", fr, "%.0fs" % (time.time() - t))
say("ALL DONE %.0fs" % (time.time() - t0))
