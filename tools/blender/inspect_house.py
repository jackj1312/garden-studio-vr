"""Light check of the model against Jack's photos (no lighting, no bake: safe on the 8 GB Mac).
    /Applications/Blender.app/Contents/MacOS/Blender -b master/front-garden.blend --python tools/blender/inspect_house.py -- <frame> ...
Rebuilds the model (grass and hedge leaves off), renders Workbench (textures, studio light) through each
photo's solved camera, into renders/front-garden/inspect/<frame>.png"""
import sys, os, json
import bpy, numpy as np
from mathutils import Matrix, Vector
R0 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
frames = sys.argv[sys.argv.index("--") + 1:]
SITE = bpy.data.scenes["Site"]
G = {"__name__": "fg_build", "__file__": R0 + "/master/front-garden-build.py"}
with bpy.context.temp_override(scene=SITE, view_layer=SITE.view_layers[0]):
    exec(compile(open(R0 + "/master/front-garden-build.py").read(), "build", "exec"), G)
    G["build"]()
    for o in G["coll"]().objects:
        for m in o.modifiers:
            if m.type == "PARTICLE_SYSTEM": m.show_render = False; m.show_viewport = False
    if bpy.data.collections.get("FG_Reference"): bpy.data.collections["FG_Reference"].hide_render = True
    bpy.data.collections["FG_Model"].hide_render = False
    SITE.render.film_transparent = False
    try: SITE.render.engine = "BLENDER_WORKBENCH"
    except TypeError as e: print(e)
    sh = SITE.display.shading; sh.light = "STUDIO"; sh.color_type = "TEXTURE"; sh.show_cavity = True; sh.show_shadows = False
    SITE.display_settings.display_device = "sRGB"; SITE.view_settings.view_transform = "Standard"
    A = json.load(open("/Users/Jack/Desktop/garden-scans/front-garden/sfm2/aligned.json")); R = np.array(A["R"])
    cam = bpy.data.objects.get("FG_Cam_Frame") or bpy.data.objects.new("FG_Cam_Frame", bpy.data.cameras.new("FG_Cam_Frame"))
    if cam.name not in SITE.collection.objects: SITE.collection.objects.link(cam)
    SITE.camera = cam
    for fr in frames:
        c = A["cameras"][fr]; M = np.array(c["cam_from_world"])
        cam.matrix_world = Matrix.Translation(Vector(c["centre"])) @ Matrix((R @ M[:, :3].T @ np.diag([1, -1, -1])).tolist()).to_4x4()
        w, h = c["camera"]["w"], c["camera"]["h"]
        cam.data.sensor_fit = "HORIZONTAL"; cam.data.sensor_width = 36; cam.data.lens = c["camera"]["params"][0] * 36 / w
        cam.data.clip_start = 0.05
        s = 960 / max(w, h)
        SITE.render.resolution_x, SITE.render.resolution_y = int(w * s), int(h * s); SITE.render.resolution_percentage = 100
        SITE.render.filepath = os.path.join(R0, "renders/front-garden/inspect", fr.replace(".jpg", ".png"))
        bpy.ops.render.render(write_still=True, scene=SITE.name)
        print("rendered", fr)
