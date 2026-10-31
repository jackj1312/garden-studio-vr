"""Material test (WORKFLOW G4, CORRECTIONS-LOG 53-54): a 1 m patch of each hard surface, built properly, rendered in
Cycles next to the client's close-up. Nothing goes into the model until its patch passes.

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/blender/material_test.py -- <out_dir>

Brick: Poly Haven brick_4 (CC0 scan: colour, normal, roughness, displacement) at true scale, real displacement,
recoloured to Jack's sunlit brick. Paving: every block generated as geometry (Airbnb method: "generated in Python")
in Jack's tumbled three-size set and bond, chamfered edges, each block its own colour drawn from his photo, sand
joints, with the scanned grain of pavement_03 (normal + roughness) on every block."""
import bpy, bmesh, os, sys, json, math, urllib.request
import numpy as np
from mathutils import Vector

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "/tmp/mt"
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEX = os.path.join(ROOT, "master", "polyhaven", "tex"); os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "garden-studio-vr/1.0 (Poly Haven CC0 fetch)"}
rng = np.random.default_rng(7)

def fetch(asset, res="2k"):
    files = json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.polyhaven.com/files/{asset}", headers=UA)))
    out = {}
    for key, nm in (("Diffuse", "diff"), ("nor_gl", "nor"), ("Rough", "rough"), ("Displacement", "disp")):
        fmts = files[key][res]; fmt = "png" if (nm == "disp" and "png" in fmts) else ("jpg" if "jpg" in fmts else list(fmts)[0])
        dest = os.path.join(TEX, asset, f"{nm}_{res}.{fmt}"); os.makedirs(os.path.dirname(dest), exist_ok=True)
        if not os.path.exists(dest):
            with urllib.request.urlopen(urllib.request.Request(fmts[fmt]["url"], headers=UA)) as r, open(dest, "wb") as fh: fh.write(r.read())
        out[nm] = dest
    return out

def img(path, colour):
    i = bpy.data.images.load(path, check_existing=True); i.colorspace_settings.name = "sRGB" if colour else "Non-Color"; return i

def recolour(path, name, target_srgb, keep=1.0):
    """the scan's detail and per-brick variation, the client's mean colour (target = sunlit albedo, sRGB 0-255)"""
    src = img(path, True); w, h = src.size
    a = np.empty(w * h * 4, np.float32); src.pixels.foreach_get(a); a = a.reshape(-1, 4)
    lin = lambda x: np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
    t = lin(np.array(target_srgb, np.float32) / 255)
    m = a[:, :3].mean(0)
    a[:, :3] = np.clip(a[:, :3] * (t / np.maximum(m, 1e-4)) ** keep, 0, 1)
    o = bpy.data.images.new(name, w, h, alpha=False); o.colorspace_settings.name = "sRGB"; o.pixels.foreach_set(a.ravel()); o.pack(); return o

def pbr_material(name, maps, scale_m, diff_img=None, disp_scale=0.01, rough_mul=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled"); nt.links.new(b.outputs[0], out.inputs[0])
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / scale_m,) * 3
    nt.links.new(tc.outputs["Object"], mp.inputs[0])
    def t(i):
        n = nt.nodes.new("ShaderNodeTexImage"); n.image = i; n.projection = "BOX"; n.projection_blend = 0.2; nt.links.new(mp.outputs[0], n.inputs[0]); return n
    nt.links.new(t(diff_img or img(maps["diff"], True)).outputs[0], b.inputs["Base Color"])
    r = t(img(maps["rough"], False)); mr = nt.nodes.new("ShaderNodeMath"); mr.operation = "MULTIPLY"; mr.inputs[1].default_value = rough_mul
    nt.links.new(r.outputs[0], mr.inputs[0]); nt.links.new(mr.outputs[0], b.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(t(img(maps["nor"], False)).outputs[0], nm.inputs["Color"]); nt.links.new(nm.outputs[0], b.inputs["Normal"])
    if "disp" in maps and disp_scale:
        d = nt.nodes.new("ShaderNodeDisplacement"); d.inputs["Scale"].default_value = disp_scale; d.inputs["Midlevel"].default_value = 0.5
        nt.links.new(t(img(maps["disp"], False)).outputs[0], d.inputs["Height"]); nt.links.new(d.outputs[0], out.inputs["Displacement"])
        try: m.displacement_method = "BOTH"
        except AttributeError: m.cycles.displacement_method = "BOTH"
    return m

# ------------------------------------------------------------------ scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
try: prefs.compute_device_type = "METAL"; prefs.get_devices(); [setattr(d, "use", True) for d in prefs.devices]; sc.cycles.device = "GPU"
except Exception: pass
sc.cycles.samples = 96; sc.cycles.use_denoising = True
try: sc.view_settings.view_transform = "Khronos PBR Neutral"
except TypeError: pass
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND"); bg.inputs[0].default_value = (0.55, 0.68, 0.9, 1); bg.inputs[1].default_value = 0.9
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
sun.data.energy = 4.5; sun.data.color = (1.0, 0.9, 0.78); sun.data.angle = math.radians(1.0)
sun.rotation_euler = (math.radians(68), 0, math.radians(35))      # ~22° up, raking like the walk frames

def link(o): sc.collection.objects.link(o); return o

# ---- brick wall patch, 1.2 x 1.0 m, true displacement
B = fetch("brick_4")
brick_img = recolour(B["diff"], "brick_jack", (150, 92, 78), keep=1.0)   # Jack's brick in sun, as albedo (walk frames / elevation)
mb = pbr_material("brick", B, 0.5, diff_img=brick_img, disp_scale=0.012, rough_mul=1.0)
bpy.ops.mesh.primitive_plane_add(size=1.0); wall = bpy.context.object; wall.scale = (1.2, 1.0, 1); wall.rotation_euler = (math.radians(90), 0, 0)
wall.location = (-1.0, 0, 0.5); bpy.ops.object.transform_apply(scale=True, rotation=True)
sub = wall.modifiers.new("sub", "SUBSURF"); sub.subdivision_type = "SIMPLE"; sub.levels = 0; sub.render_levels = 9          # ~2.3 mm grid: real displacement of the mortar
try: wall.cycles.use_adaptive_subdivision = True
except AttributeError: pass
wall.data.materials.append(mb)

# ---- paving patch: every block as geometry
P = fetch("pavement_03")
pal = np.array(json.load(open(os.path.join(ROOT, "master", "phototex", "paving_palette.json")))["srgb"]) / 255.0
pal_lin = np.where(pal <= 0.04045, pal / 12.92, ((pal + 0.055) / 1.055) ** 2.4)
row_w, joint, depth = 0.16, 0.007, 0.06                  # tumbled set: 160 mm rows (STUDIO-MEMORY), sand joints
lengths, probs = np.array([0.12, 0.16, 0.24]), np.array([0.25, 0.4, 0.35])
bm = bmesh.new(); col_layer = bm.loops.layers.color.new("Col")
X0, X1, Y0, Y1 = 0.2, 1.6, -0.7, 0.7
y = Y0
while y < Y1:
    x = X0 - rng.uniform(0, 0.12)
    while x < X1:
        L = rng.choice(lengths, p=probs)
        cx, cy = x + L / 2, y + row_w / 2
        res = bmesh.ops.create_cube(bm, size=1.0)
        vs = res["verts"]
        h = depth + rng.normal(0, 0.0015)
        ang = rng.normal(0, 0.006)
        for v in vs:
            px, py, pz = v.co.x * (L - joint), v.co.y * (row_w - joint), (v.co.z + 0.5) * h - depth
            v.co = Vector((cx + px * math.cos(ang) - py * math.sin(ang), cy + px * math.sin(ang) + py * math.cos(ang), pz + rng.normal(0, 0.0004)))
        c = pal_lin[rng.integers(len(pal_lin))] * rng.uniform(0.9, 1.1)
        faces = list({f for v in vs for f in v.link_faces})
        for f in faces:
            for lp in f.loops: lp[col_layer] = (*np.clip(c, 0, 1), 1.0)
        edges = list({e for v in vs for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=edges, offset=0.009, segments=3, profile=0.6, affect="EDGES")
        x += L
    y += row_w
me = bpy.data.meshes.new("paving"); bm.to_mesh(me); bm.free()
pave = link(bpy.data.objects.new("paving", me))
# block colour x scanned concrete grain (normal + roughness + a little of its tone)
m = bpy.data.materials.new("paving_blocks"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled"); nt.links.new(b.outputs[0], out.inputs[0])
tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1 / 2.0,) * 3
nt.links.new(tc.outputs["Object"], mp.inputs[0])
def tx(i):
    n = nt.nodes.new("ShaderNodeTexImage"); n.image = i; n.projection = "BOX"; n.projection_blend = 0.2; nt.links.new(mp.outputs[0], n.inputs[0]); return n
attr = nt.nodes.new("ShaderNodeVertexColor"); attr.layer_name = "Col"
grain = tx(img(P["diff"], True)); bw = nt.nodes.new("ShaderNodeRGBToBW"); nt.links.new(grain.outputs[0], bw.inputs[0])
gm = nt.nodes.new("ShaderNodeMath"); gm.operation = "MULTIPLY_ADD"; gm.inputs[1].default_value = 1.4; gm.inputs[2].default_value = 0.45
nt.links.new(bw.outputs[0], gm.inputs[0])
mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"; mix.inputs["Factor"].default_value = 1.0
nt.links.new(attr.outputs[0], mix.inputs[6]); nt.links.new(gm.outputs[0], mix.inputs[7]); nt.links.new(mix.outputs[2], b.inputs["Base Color"])
nt.links.new(tx(img(P["rough"], False)).outputs[0], b.inputs["Roughness"])
nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 1.2
nt.links.new(tx(img(P["nor"], False)).outputs[0], nm.inputs["Color"]); nt.links.new(nm.outputs[0], b.inputs["Normal"])
me.materials.append(m)
# sand in the joints
bpy.ops.mesh.primitive_plane_add(size=1.0, location=((X0 + X1) / 2, 0, -0.006)); sand = bpy.context.object; sand.scale = (X1 - X0 + 0.3, Y1 - Y0 + 0.3, 1)
ms = bpy.data.materials.new("sand"); ms.use_nodes = True
next(n for n in ms.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.36, 0.30, 0.22, 1)
sand.data.materials.append(ms)

# ---- cameras: close, like Jack's close-ups, and a wider raking view
def shot(name, loc, look, lens=35, res=(1000, 1000)):
    cam = bpy.data.objects.get("Cam") or link(bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")))
    cam.location = loc; cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = lens
    sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = res; sc.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True); print("rendered", name)
shot("paving_top", (0.9, 0.0, 1.05), (0.9, 0.0, 0.0), lens=30)
shot("paving_raking", (0.9, -1.6, 0.9), (0.9, 0.1, 0.0), lens=35, res=(1200, 800))
shot("brick_front", (-1.0, -1.0, 0.5), (-1.0, 0.0, 0.5), lens=35)
shot("brick_raking", (-0.2, -0.9, 0.6), (-1.0, 0.0, 0.5), lens=35, res=(1200, 800))
