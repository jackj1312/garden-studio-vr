"""Seamless texture sheets from unit-built surfaces (for the headset and any real-time view): every brick and block is
built as geometry wearing the client's own faces (unit_surfaces.py), then photographed straight-on in flat light, so the
sheet carries real faces, joints and bond with no lighting baked in. Light on the Mac (Workbench).
    Blender -b --factory-startup --python tools/blender/bake_unit_sheets.py -- <out_dir> [px_per_m]"""
import bpy, os, sys, math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
G = {"__name__": "lib", "__file__": os.path.join(HERE, "unit_surfaces.py")}
exec(compile(open(G["__file__"]).read(), G["__file__"], "exec"), G)
args = sys.argv[sys.argv.index("--") + 1:]
OUT = args[0]; PPM = float(args[1]) if len(args) > 1 else 300.0
os.makedirs(OUT, exist_ok=True)

def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def shoot(name, cx, cy, cz, w, h, look):
    sc = bpy.context.scene
    for m in bpy.data.materials:                       # Workbench shows a material's viewport colour where it has no image
        if m.use_nodes:
            b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if b and not any(n.type == "TEX_IMAGE" for n in m.node_tree.nodes):
                m.diffuse_color = (0.035, 0.03, 0.024, 1) if "joint" in m.name else b.inputs["Base Color"].default_value
    try: sc.render.engine = "BLENDER_WORKBENCH"
    except TypeError as e: print(e)
    sh = sc.display.shading; sh.light = "FLAT"; sh.color_type = "TEXTURE"; sh.show_shadows = False; sh.show_cavity = False
    sc.view_settings.view_transform = "Standard"; sc.display.render_aa = "16"
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = "ORTHO"; cam.data.ortho_scale = max(w, h); cam.data.clip_end = 100
    cam.location = (cx, cy, cz); cam.rotation_euler = look
    sc.render.resolution_x, sc.render.resolution_y = int(w * PPM), int(h * PPM); sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.filepath = os.path.join(OUT, name + ".png"); sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True); print("sheet", name, sc.render.resolution_x, "x", sc.render.resolution_y)

# brick: a 4.0 m x 4.8 m sheet (wraps seamlessly: whole bricks per row width, whole courses per height)
L, J = 0.215, 0.010
W_BR = round(4.0 / (L + J)) * (L + J); H_BR = round(4.8 / (0.065 + J)) * (0.065 + J)
for nm, gain, mortar in (("brick_house", (1.08, 0.98, 0.94), (0.20, 0.19, 0.11)),
                         ("brick_porch", (1.22, 1.06, 0.92), (0.30, 0.26, 0.17)),
                         ("brick_neighbour", (0.78, 0.68, 0.72), (0.18, 0.17, 0.14))):
    clear()
    G["brick_wall"](nm, (0, 0, 0), (1, 0, 0), (0, 0, 1), W_BR, H_BR + J, gain=gain, mortar_rgb=mortar, seed=hash(nm) % 1000)
    shoot(nm, W_BR / 2, -5, H_BR / 2 + J / 2, W_BR, H_BR, (math.radians(90), 0, 0))
# block paving: a 4.0 m x 4.0 m sheet (whole rows), rows run along x
clear()
ROW = 0.16; H_PV = round(4.0 / ROW) * ROW
G["block_paving"]("paving", (0, 4.0, 0, H_PV), gain=(1.16, 0.96, 0.84))
shoot("paving", 2.0, H_PV / 2, 5, 4.0, H_PV, (0, 0, 0))
print("sizes m", {"brick": [round(W_BR, 3), round(H_BR, 3)], "paving": [4.0, round(H_PV, 3)]})
