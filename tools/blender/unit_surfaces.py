"""Hard surfaces built from the client's own units (WORKFLOW G4/G5; CORRECTIONS-LOG 53-54).
Every brick and block is real geometry (bevelled, slightly irregular) wearing one of the client's own faces, cut from
their close-ups by tools/phototex/unit_library.py; joints and mortar are real recesses.

Used two ways:
  * test patches:  Blender -b --factory-startup --python tools/blender/unit_surfaces.py -- <out_dir>
  * in the build:  exec this file, then call brick_wall(...) / block_paving(...)"""
import bpy, bmesh, os, sys, json, math
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UNITS = os.path.join(ROOT, "master", "phototex", "units")

def atlas(kind, gain=(1, 1, 1), flip=True):
    """pack a unit library into one image; returns (image, [(u0, v0, u1, v1, aspect), ...]) — with flipped copies"""
    from math import ceil
    lib = json.load(open(os.path.join(UNITS, kind, "library.json")))["units"]
    imgs = []
    for u in lib:
        i = bpy.data.images.load(os.path.join(UNITS, kind, u["file"]), check_existing=True)
        w, h = i.size; a = np.empty(w * h * 4, np.float32); i.pixels.foreach_get(a); a = a.reshape(h, w, 4)
        asp = (u["px"][0] / u["px"][1]) if "px" in u else w / h
        imgs.append((a, asp))
        if flip:
            imgs.append((a[::-1, ::-1].copy(), asp))                 # the same unit turned round: a new face
    cw, ch = 256, 256 if kind == "block" else 80
    cols = 8; rows = ceil(len(imgs) / cols)
    W, H = cols * cw, rows * ch
    A = np.ones((H, W, 4), np.float32)
    cells = []
    g = np.array(list(gain) + [1.0], np.float32)
    for k, (a, asp) in enumerate(imgs):
        r, c = divmod(k, cols)
        ys = (0.04 * a.shape[0] + np.arange(ch) * a.shape[0] * 0.92 / ch).astype(int); xs = (0.04 * a.shape[1] + np.arange(cw) * a.shape[1] * 0.92 / cw).astype(int)
        A[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = np.clip(a[ys][:, xs] * g, 0, 1)
        cells.append((c * cw / W, r * ch / H, (c + 1) * cw / W, (r + 1) * ch / H, asp))
    name = f"FGU_{kind}_atlas"
    old = bpy.data.images.get(name)
    if old: bpy.data.images.remove(old)
    im = bpy.data.images.new(name, W, H, alpha=False); im.colorspace_settings.name = "sRGB"; im.pixels.foreach_set(A.ravel()); im.pack()
    return im, cells

def unit_material(name, atlas_img, rough=0.85, bump=0.6):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled"); nt.links.new(b.outputs[0], out.inputs[0])
    uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = atlas_img; t.interpolation = "Cubic"; nt.links.new(uv.outputs[0], t.inputs[0])
    nt.links.new(t.outputs[0], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = rough
    bw = nt.nodes.new("ShaderNodeRGBToBW"); nt.links.new(t.outputs[0], bw.inputs[0])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump; bp.inputs["Distance"].default_value = 0.002
    nt.links.new(bw.outputs[0], bp.inputs["Height"]); nt.links.new(bp.outputs[0], b.inputs["Normal"])
    return m

def flat(name, rgb, rough=0.9):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"); b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    return m

def _unit(bm, uvl, centre, axes, size, cell, rng, bevel, face_axis):
    """one unit: a box of `size` along `axes` (3 unit vectors), its show face (normal +axes[face_axis]) mapped to `cell`"""
    res = bmesh.ops.create_cube(bm, size=1.0); vs = res["verts"]
    jit = rng.normal(0, 0.0006, 3)
    for v in vs:
        p = Vector(centre) + sum((axes[i] * (v.co[i] * size[i]) for i in range(3)), Vector()) + Vector(jit)
        v.co = p
    faces = list({f for v in vs for f in v.link_faces})
    bmesh.ops.bevel(bm, geom=list({e for v in vs for e in v.link_edges}), offset=bevel, segments=2, profile=0.6, affect="EDGES")
    faces = list({f for v in vs for f in v.link_faces}) if all(v.is_valid for v in vs) else faces
    return vs

def brick_wall(name, origin, along, up, length, height, M=None, seed=1, gain=(1, 1, 1), mortar_rgb=(0.20, 0.19, 0.11),   # greenish-tan (20506, linear)
               brick=(0.215, 0.065, 0.10), joint=0.010, recess=0.004):
    """a wall face of real bricks in stretcher bond: the brick faces lie in the plane through `origin` spanned by
    `along` and `up`, facing nrm = along x up (for a front wall running +x, that is -y: towards the road); bricks extend
    behind it; the mortar is a plane `recess` behind the faces."""
    rng = np.random.default_rng(seed)
    along, up = Vector(along).normalized(), Vector(up).normalized(); nrm = along.cross(up).normalized()
    img, cells = atlas("brick", gain=gain)
    bm = bmesh.new()
    L, Hh, D = brick; pitch_x, pitch_z = L + joint, Hh + joint
    bricks = []                      # (x (unclipped start), z, x0, x1, cell)
    course = 0; z = joint
    while z + Hh <= height + 1e-6:
        x = -(pitch_x / 2) * (course % 2)
        while x < length:
            x0, x1 = max(x, 0.0), min(x + L, length)
            if x1 - x0 > 0.03:
                cell = cells[rng.integers(len(cells))]
                c = Vector(origin) + along * ((x0 + x1) / 2) + up * (z + Hh / 2) - nrm * (D / 2 + rng.normal(0, 0.0008))
                res = bmesh.ops.create_cube(bm, size=1.0); vs = res["verts"]
                for v in vs:
                    v.co = c + along * (v.co.x * (x1 - x0)) + up * (v.co.z * Hh) - nrm * (v.co.y * D)   # right-handed: no mirroring
                bmesh.ops.recalc_face_normals(bm, faces=list({f for v in vs for f in v.link_faces}))
                bmesh.ops.bevel(bm, geom=list({e for v in vs for e in v.link_edges}), offset=0.0025, segments=2, profile=0.6, affect="EDGES")
                bricks.append((x, z, x0, x1, cell))
            x += pitch_x
        z += pitch_z; course += 1
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    # UVs after the bevel: every face looking out of the wall maps onto its own brick's piece of the client's photo
    uvl = me.uv_layers.new(name="UVMap"); uvl.active = True; uvl.active_render = True
    O = Vector(origin)
    zs = np.array([b[1] for b in bricks]); xs0 = np.array([b[2] for b in bricks]); xs1 = np.array([b[3] for b in bricks])
    for poly in me.polygons:
        cp = poly.center - O; ca, cu = cp.dot(along), cp.dot(up)
        if abs(cp.dot(nrm)) > 0.004 or abs(poly.normal.dot(nrm)) < 0.5: continue   # the show face, on the wall plane
        k = np.nonzero((zs - 0.001 <= cu) & (cu <= zs + Hh + 0.001) & (xs0 - 0.001 <= ca) & (ca <= xs1 + 0.001))[0]
        if not len(k): continue
        x, z, x0, x1, (u0, v0, u1, v1, _) = bricks[k[0]]
        for li in poly.loop_indices:
            p = me.vertices[me.loops[li].vertex_index].co - O
            s_ = min(max((p.dot(along) - x) / L, 0), 1); t_ = min(max((p.dot(up) - z) / Hh, 0), 1)
            uvl.data[li].uv = (u0 + (u1 - u0) * s_, v0 + (v1 - v0) * t_)
    o = bpy.data.objects.new(name, me); (bpy.context.scene.collection if not M else M["_coll"]).objects.link(o)
    me.materials.append(unit_material(name + "_mat", img, rough=0.82, bump=0.9))
    # mortar plane, just behind the brick faces
    q = [Vector(origin) - nrm * recess, Vector(origin) + along * length - nrm * recess,
         Vector(origin) + along * length + up * height - nrm * recess, Vector(origin) + up * height - nrm * recess]
    mm = bpy.data.meshes.new(name + "_mortar"); mm.from_pydata([tuple(p - nrm * 0.0) for p in q], [], [(0, 1, 2, 3)])
    mo = bpy.data.objects.new(name + "_mortar", mm); (bpy.context.scene.collection if not M else M["_coll"]).objects.link(mo)
    mm.materials.append(flat(name + "_mortar_mat", mortar_rgb, 0.95))
    return o

def block_paving(name, poly_box, M=None, seed=2, gain=(1, 1, 1), row_w=0.16, joint=0.005, depth=0.06,
                 sizes=((0.11, 0.25), (0.16, 0.40), (0.23, 0.35)), joint_rgb=(0.16, 0.15, 0.12), z=0.0, along_x=True):
    """tumbled block paving over a rectangle (x0, x1, y0, y1), rows across x, each block wearing one of the client's
    own block faces (chosen to match its shape), chamfered edges, dark grit joints"""
    rng = np.random.default_rng(seed)
    img, cells = atlas("block", gain=gain)
    asp = np.array([c[4] for c in cells])
    x0, x1, y0, y1 = poly_box
    bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
    L_opts = np.array([s[0] for s in sizes]); P = np.array([s[1] for s in sizes]); P = P / P.sum()
    y = y0
    while y < y1 - 0.02:
        x = x0 - rng.uniform(0, 0.1)
        while x < x1:
            L = rng.choice(L_opts, p=P); a0, a1 = max(x, x0), min(x + L, x1)
            if a1 - a0 > 0.03:
                want = L / row_w; k = int(np.argmin(np.abs(asp - want) + rng.uniform(0, 0.25, len(asp))))
                u0, v0, u1, v1, _ = cells[k]
                h = depth + rng.normal(0, 0.0012); tilt = rng.normal(0, 0.004, 2)
                cx, cy = (a0 + a1) / 2, y + row_w / 2
                res = bmesh.ops.create_cube(bm, size=1.0); vs = res["verts"]
                for v in vs:
                    px, py = v.co.x * (a1 - a0 - joint), v.co.y * (row_w - joint)
                    pz = (v.co.z + 0.5) * h - depth + z + px * tilt[0] + py * tilt[1]
                    v.co = Vector((cx + px, cy + py, pz))
                fs = list({f for v in vs for f in v.link_faces}); bmesh.ops.recalc_face_normals(bm, faces=fs)
                for f in fs:
                    f.normal_update()
                    if f.normal.z > 0.9:
                        for lp in f.loops:
                            s = (lp.vert.co.x - (a0 + joint / 2)) / (a1 - a0 - joint); t = (lp.vert.co.y - (y + joint / 2)) / (row_w - joint)
                            lp[uvl].uv = (u0 + (u1 - u0) * s, v0 + (v1 - v0) * t)
                bmesh.ops.bevel(bm, geom=list({e for v in vs for e in v.link_edges}), offset=0.013, segments=4, profile=0.6, affect="EDGES")   # tumbled: well-rounded
            x += L
        y += row_w
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.uv_layers["UVMap"].active = True; me.uv_layers["UVMap"].active_render = True
    o = bpy.data.objects.new(name, me); (bpy.context.scene.collection if not M else M["_coll"]).objects.link(o)
    me.materials.append(unit_material(name + "_mat", img, rough=0.8, bump=0.7))
    gm = bpy.data.meshes.new(name + "_joints"); gm.from_pydata([(x0, y0, z - 0.012), (x1, y0, z - 0.012), (x1, y1, z - 0.012), (x0, y1, z - 0.012)], [], [(0, 1, 2, 3)])
    go = bpy.data.objects.new(name + "_joints", gm); (bpy.context.scene.collection if not M else M["_coll"]).objects.link(go)
    gm.materials.append(flat(name + "_joint_mat", joint_rgb, 0.95))
    return o

if __name__ == "__main__":
    OUT = sys.argv[sys.argv.index("--") + 1]; os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "METAL"; prefs.get_devices(); [setattr(d, "use", True) for d in prefs.devices]; sc.cycles.device = "GPU"
    except Exception: pass
    sc.cycles.samples = 96; sc.cycles.use_denoising = True
    try: sc.view_settings.view_transform = "Khronos PBR Neutral"
    except TypeError: pass
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND"); bg.inputs[0].default_value = (0.55, 0.68, 0.9, 1); bg.inputs[1].default_value = 0.8
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
    sun.data.energy = 4.0; sun.data.color = (1.0, 0.9, 0.78); sun.data.angle = math.radians(1.0)
    sun.rotation_euler = (math.radians(66), 0, math.radians(40))
    # paving colour: the close-up was shot in shade (cool); give it the chromaticity of the sunlit walk (185,159,144)
    pv_gain = (1.16, 0.96, 0.84)      # sunlit path chromaticity (walk 0019: 185,159,144)
    block_paving("paving", (0.2, 1.6, -0.7, 0.7), gain=pv_gain)
    brick_wall("wall", (-1.6, 0.0, 0.0), (1, 0, 0), (0, 0, 1), 1.2, 1.0, gain=(1.08, 0.98, 0.94))
    def shot(name, loc, look, lens=35, res=(1000, 1000)):
        cam = bpy.data.objects.get("Cam") or bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
        if cam.name not in sc.collection.objects: sc.collection.objects.link(cam)
        cam.location = loc; cam.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = lens
        sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = res; sc.render.filepath = os.path.join(OUT, name + ".png")
        bpy.ops.render.render(write_still=True); print("rendered", name)
    shot("paving_top", (0.9, 0.0, 1.05), (0.9, 0.0, 0.0), lens=30)
    shot("paving_raking", (0.9, -1.6, 0.9), (0.9, 0.1, 0.0), lens=35, res=(1200, 800))
    shot("brick_front", (-1.0, -1.0, 0.5), (-1.0, 0.0, 0.5), lens=35)
    shot("brick_raking", (-0.25, -0.9, 0.6), (-1.0, 0.0, 0.5), lens=35, res=(1200, 800))
