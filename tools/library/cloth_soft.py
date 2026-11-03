"""Studio-made soft items by Blender cloth simulation (DETAIL-CHECKLIST: "soft items are never boxes"), headless and light:
one small sim at a time, ~40-70 frames, no render. Each result is saved to the studio library as its own .blend
(~/Desktop/garden-scans/asset-library/soft/<name>/source.blend + asset.json) in the local frame of the spec item it dresses
(hb_items: X = width, +Y = front, base at z 0), with materials named "SPECFIN:<finish>" (swapped for the spec finish at
build time) or the terry / waffle / striped-cotton materials made by hb_furnish.soft_material.

    nice -n 10 Blender -b --factory-startup --python tools/library/cloth_soft.py -- --spec assets/sites/house/spec/spec_v1.json [--only name,name]

Items (parameterised by the spec, so any house's spec makes its own): towels over a towel radiator's bar, a hand towel through
a ring, a tea towel over an oven handle, knitted throws over the arm of the (adapted) sofa they dress, duvet + pillows + throw
on a mattress (with a studio-made oak frame when the plan has no library frame)."""
import sys, os, json, math, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "house"))
import bpy, bmesh
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--only", default="")
ap.add_argument("--lib", default=os.path.expanduser("~/Desktop/garden-scans/asset-library"))
a = ap.parse_args(argv)
S = json.load(open(a.spec))
ONLY = {x for x in a.only.split(",") if x}
TEXMETA = json.load(open(os.path.join(HERE, "..", "..", "master", "phototex", "spec", "spec_tex_meta.json")))["finishes"]
import hb_furnish as HF
ITEMS = {}
for v in S["versions"].values():
    for it in v["items"]: ITEMS.setdefault(it["id"], it)


def log(*x): print("[cloth]", *x, flush=True)


def clear():
    HF._CACHE.clear()
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.users == 0: bpy.data.meshes.remove(me)


def b3(p): return Vector((p[0], -p[2], p[1]))
def item_matrix(it): return Matrix.Translation(b3(it["position_m"])) @ Matrix.Rotation(math.radians(it["yaw_deg"]), 4, "Z")


def specfin(fid):
    nm = f"SPECFIN:{fid}"
    if nm in bpy.data.materials: return bpy.data.materials[nm]
    m = bpy.data.materials.new(nm); m.use_nodes = True
    h = TEXMETA.get(fid, {}).get("colour_srgb", "#CCCCCC").lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*[x ** 2.2 for x in c], 1)
    return m


def tile_of(fid): return (TEXMETA.get(fid, {}).get("tile_m") or [0.3, 0.3])[0]


def cloth_plane(name, w, l, nx, ny, M, mat, tile):
    """a grid w (x) by l (y) centred, transformed by M; UVs at true scale"""
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=nx, y_segments=ny, size=0.5)
    bmesh.ops.scale(bm, vec=(w, l, 1), verts=bm.verts)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        for lp in f.loops: lp[uv].uv = ((lp.vert.co.x + w / 2) / tile, (lp.vert.co.y + l / 2) / tile)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob); ob.matrix_world = M
    return ob


def collider(ob, thick=0.004):
    md = ob.modifiers.new("col", "COLLISION"); ob.collision.thickness_outer = thick; ob.collision.cloth_friction = 8.0
    return ob


def simulate(cl, frames=60, mass=0.3, stiff=8.0, bend=0.6, pins=None, self_col=False, shrink=0.0):
    md = cl.modifiers.new("cloth", "CLOTH"); s = md.settings
    s.quality = 6; s.mass = mass; s.tension_stiffness = stiff; s.compression_stiffness = stiff; s.shear_stiffness = stiff
    s.bending_stiffness = bend; s.air_damping = 1.0
    if shrink: s.shrink_min = shrink
    md.collision_settings.distance_min = 0.004; md.collision_settings.use_self_collision = self_col
    if self_col: md.collision_settings.self_distance_min = 0.004
    if pins:
        vg = cl.vertex_groups.new(name="pin"); vg.add(pins, 1.0, "REPLACE"); s.vertex_group_mass = "pin"
    md.point_cache.frame_start = 1; md.point_cache.frame_end = frames
    sc = bpy.context.scene; sc.frame_start = 1; sc.frame_end = frames
    for f in range(1, frames + 1): sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cl.evaluated_get(dg))
    me.transform(cl.matrix_world)
    return me


def thicken(me, t):
    ob = bpy.data.objects.new("_th", me); bpy.context.scene.collection.objects.link(ob)
    s = ob.modifiers.new("sol", "SOLIDIFY"); s.thickness = t; s.offset = 0.0
    dg = bpy.context.evaluated_depsgraph_get(); me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    for p in me2.polygons: p.use_smooth = True                 # soft shading; no subdivision (Quest budget)
    bpy.data.objects.remove(ob)
    return me2


def save(name, meshes, M_item_inv, meta):
    """join meshes (world coords) into the item's local frame and write the library .blend"""
    bm = bmesh.new(); mats = []
    for me in meshes:
        idx = []
        for m in me.materials:
            if m not in mats: mats.append(m)
            idx.append(mats.index(m))
        tmp = bmesh.new(); tmp.from_mesh(me); tmp.transform(M_item_inv)
        for f in tmp.faces: f.material_index = idx[f.material_index] if f.material_index < len(idx) else 0
        tm = bpy.data.meshes.new("_s"); tmp.to_mesh(tm); tmp.free(); bm.from_mesh(tm); bpy.data.meshes.remove(tm)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    out = os.path.join(a.lib, "soft", name); os.makedirs(out, exist_ok=True)
    bpy.data.libraries.write(os.path.join(out, "source.blend"), {ob}, fake_user=True, compress=True)
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    meta.update(id=name, tris=tris, source="studio-made (tools/library/cloth_soft.py, Blender cloth simulation)", licence="studio-made; CC0 textures",
                web_ok=True, stream_ok=True, render_ok=True, made="2026-11-02")
    json.dump(meta, open(os.path.join(out, "asset.json"), "w"), indent=1)
    log(name, "saved", tris, "tris")


# ------------------------------------------------------------------------------------------------ items
def towels(rail_id, towels_id):
    clear(); rail, tw = ITEMS[rail_id], ITEMS[towels_id]
    Mr = item_matrix(rail); W, D, H = [x / 1000 for x in rail["size_mm"]]
    zbar = 0.1 + (H - 0.15) * 7 / 8; ybar = D / 2 - 0.015      # the 7th of 9 bars, at the front (hb_items k_towel_rail)
    bar = bpy.data.meshes.new("bar"); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.011, radius2=0.011, depth=W)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y")); bm.to_mesh(bar); bm.free()
    for i in range(9):                                       # every bar of the rail collides (the towels hang in front of / behind them)
        zb_ = 0.1 + (H - 0.15) * i / 8
        bo = bpy.data.objects.new(f"bar{i}", bar); bpy.context.scene.collection.objects.link(bo); bo.matrix_world = Mr @ Matrix.Translation((0, ybar, zb_))
        collider(bo, 0.003)
    wall = bpy.data.meshes.new("wall"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(wall); bm.free()
    wo = bpy.data.objects.new("wall", wall); bpy.context.scene.collection.objects.link(wo)
    wo.matrix_world = Mr @ Matrix.Translation((0, -D / 2 - 0.05, H / 2)) @ Matrix.Diagonal((W + 0.4, 0.1, H + 0.4, 1)); collider(wo, 0.003)
    meshes = []
    for k, (col, xo) in enumerate((("TOWEL-CREAM_col.jpg", -0.115), ("TOWEL-SAGE_col.jpg", 0.115))):
        mat = HF.soft_material(f"soft_terry_{k}", col, "TOWEL_nrm.jpg", 0.12)
        # a 600 x 1000 bath towel folded in thirds lengthwise: a 200 mm wide strip, 1.0 m long, dropped centred over the bar
        cl = cloth_plane(f"towel{k}", 0.205, 1.0, 14, 64, Mr @ Matrix.Translation((xo, 0.0, zbar + 0.03)), mat, 0.12)
        cl.matrix_world = Mr @ Matrix.Translation((xo, ybar, zbar + 0.025))
        # lay it flat above the bar, long axis across the bar (front-back), so it folds over it
        me = simulate(cl, frames=80, mass=0.4, stiff=10, bend=0.35)          # soft terry: drapes and rounds over the bar
        meshes.append(thicken(me, 0.012)); bpy.data.objects.remove(cl)
    save(f"towel_pair_rail_{towels_id}", meshes, item_matrix(tw).inverted(), dict(dresses=towels_id, rail=rail_id, colours="cream + sage terry (spec)"))


def hand_towel(item_id):
    clear(); it = ITEMS[item_id]; M = item_matrix(it); W, D, H = [x / 1000 for x in it["size_mm"]]
    blk = HF.soft_material("soft_black", "TOWEL-CREAM_col.jpg", "TOWEL_nrm.jpg", 0.12) if False else specfin("METAL-BLACK")
    meshes = []
    # wall plate + ring (as hb_items k_towel_ring) in world
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bmesh.ops.scale(bm, vec=(0.06, 0.012, 0.06), verts=bm.verts)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, -D / 2 + 0.006, H - 0.03)); me = bpy.data.meshes.new("plate"); bm.to_mesh(me); bm.free(); me.materials.append(blk)
    me.transform(M); meshes.append(me)
    bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=False, segments=32, radius=0.076)
    me_r = bpy.data.meshes.new("ringc"); bm.to_mesh(me_r); bm.free()
    ro = bpy.data.objects.new("ring", me_r); bpy.context.scene.collection.objects.link(ro)
    ro.matrix_world = M @ Matrix.Translation((0, -D / 2 + 0.03, H - 0.11)) @ Matrix.Rotation(math.pi / 2, 4, "X")
    sk = ro.modifiers.new("skin", "SKIN")
    for v in me_r.skin_vertices[0].data: v.radius = (0.006, 0.006)
    dg = bpy.context.evaluated_depsgraph_get(); ring = bpy.data.meshes.new_from_object(ro.evaluated_get(dg)); ring.transform(ro.matrix_world)
    ring.materials.clear(); ring.materials.append(blk); meshes.append(ring)
    ro.modifiers.clear()
    rc = bpy.data.objects.new("ringcol", ring.copy()); bpy.context.scene.collection.objects.link(rc); collider(rc, 0.002)
    wall = bpy.data.meshes.new("wall"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(wall); bm.free()
    wo = bpy.data.objects.new("wall", wall); bpy.context.scene.collection.objects.link(wo)
    wo.matrix_world = M @ Matrix.Translation((0, -D / 2 - 0.05, H / 2)) @ Matrix.Diagonal((0.8, 0.1, 1.2, 1)); collider(wo, 0.003)
    mat = HF.soft_material("soft_waffle", "WAFFLE-CREAM_col.jpg", "WAFFLE_nrm.jpg", 0.1)
    # a 300 x 500 hand towel folded in half: 150 wide strip, 0.6 long, over the bottom of the ring
    cl = cloth_plane("htowel", 0.16, 0.62, 12, 44, M @ Matrix.Translation((0, -D / 2 + 0.03, H - 0.11 - 0.076 + 0.02)), mat, 0.1)
    me = simulate(cl, frames=70, mass=0.25, stiff=10, bend=0.35)
    meshes.append(thicken(me, 0.009))
    save(f"hand_towel_ring_{item_id}", meshes, M.inverted(), dict(dresses=item_id, colour="cream waffle (spec)"))


def tea_towel(item_id):
    clear(); it = ITEMS[item_id]; M = item_matrix(it)
    # the oven handle: a 12 mm bar 0.45 m long, 35 mm proud of the unit front, at the item's anchor height
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.008, radius2=0.008, depth=0.45)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y")); me = bpy.data.meshes.new("h"); bm.to_mesh(me); bm.free()
    ho = bpy.data.objects.new("handle", me); bpy.context.scene.collection.objects.link(ho); ho.matrix_world = M @ Matrix.Translation((0, 0.0, 0.0)); collider(ho, 0.002)
    door = bpy.data.meshes.new("door"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bm.to_mesh(door); bm.free()
    do = bpy.data.objects.new("door", door); bpy.context.scene.collection.objects.link(do)
    do.matrix_world = M @ Matrix.Translation((0, -0.05, -0.2)) @ Matrix.Diagonal((0.8, 0.06, 0.8, 1)); collider(do, 0.003)
    mat = HF.soft_material("soft_teatowel", "TEATOWEL_col.jpg", "COTTON_nrm.jpg", 0.5)
    cl = cloth_plane("tt", 0.25, 0.7, 12, 36, M @ Matrix.Translation((0, 0.0, 0.02)), mat, 0.5)
    me = simulate(cl, frames=60, mass=0.15, stiff=10, bend=0.8)
    save(f"tea_towel_handle_{item_id}", [thicken(me, 0.003)], M.inverted(), dict(dresses=item_id, colour="striped cream/sage cotton (spec)"))


class _Fin:                     # geometry-only stand-in for hb_items.Finishes (no recolour at sim time)
    F = {}; tile = {}
    def get(self, k): return None


def throw(throw_id, sofa_id):
    clear(); th, so = ITEMS[throw_id], ITEMS[sofa_id]
    W, D, H = [x / 1000 for x in so["size_mm"]]
    pl = json.load(open(os.path.join(os.path.dirname(a.spec), "furnishing_plan.json")))
    key = pl["items"][sofa_id]["asset"]
    ob = HF.build_library_item(so, key, None, W, D, H, _Fin(), lambda it_, part, *f: None, log)
    bpy.context.scene.collection.objects.link(ob); ob.matrix_world = item_matrix(so); collider(ob, 0.006)
    floor = bpy.data.meshes.new("floor"); bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=3.0); bm.to_mesh(floor); bm.free()
    fo = bpy.data.objects.new("floor", floor); bpy.context.scene.collection.objects.link(fo); fo.matrix_world = Matrix.Translation(b3(so["position_m"])); collider(fo, 0.003)
    Mt = item_matrix(th)
    mat = specfin("FAB-THROW")
    # the throw folded in half (650 x 1700), laid across the arm from back to front, 80 mm above the arm top, then dropped
    yaw_rel = math.radians(th["yaw_deg"] - so["yaw_deg"])
    # the arm under the throw: the sofa's highest point within 140 mm of the end nearest the throw, in front of the back
    Ms = item_matrix(so); Mi = Ms.inverted(); tl = Mi @ b3(th["position_m"])
    side = 1 if tl.x > 0 else -1
    arm = [v.co for v in ob.data.vertices if side * v.co.x > W / 2 - 0.14 and v.co.y > -D / 2 + 0.25]
    arm_top = max(v.z for v in arm) if arm else 0.62
    log(throw_id, "arm top", round(arm_top, 3), "throw local", [round(x, 3) for x in tl])
    # folded in half (650 wide), laid over the arm from just in front of the back to past the seat front, 40 mm above it
    x_arm = side * (W / 2 - 0.075) - side * 0.12            # centred a little in from the arm: most of it drapes onto the seat
    cl = cloth_plane("throw", 0.60, 0.95, 20, 32, Ms @ Matrix.Translation((x_arm, 0.18, arm_top + 0.03)), mat, tile_of("FAB-THROW"))
    me = simulate(cl, frames=60, mass=0.3, stiff=15, bend=2.5)
    save(f"throw_arm_{throw_id}", [thicken(me, 0.008)], Mt.inverted(), dict(dresses=throw_id, over=sofa_id, base=key, finish="FAB-THROW (spec)"))


def bedding(bed_id, frame="studio"):
    """duvet, pillows and the throw across the foot, on the spec mattress; with a studio-made oak frame (slatted headboard
    panel) when frame == 'studio'. Built in the bed item's local frame (headboard at -Y, foot at +Y)."""
    clear(); it = ITEMS[bed_id]; A_ = it["asset"]
    W, D, H = [x / 1000 for x in it["size_mm"]]
    mw, ml, mh = [x / 1000 for x in A_.get("mattress_mm", [W * 1000 - 100, D * 1000 - 100, 220])]
    hb = A_.get("headboard_h_mm", H * 1000) / 1000
    meshes = []
    oak, lin, thr = specfin("WOOD-OAK-FURN"), specfin("BED-LINEN"), specfin("THROW-BED")
    def box(x0, x1, y0, y1, z0, z1, mat, bev=0.004):
        bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, z1 - z0), verts=bm.verts); bmesh.ops.translate(bm, verts=bm.verts, vec=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
        if bev: bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bev, segments=2, affect="EDGES", profile=0.5, clamp_overlap=True)
        uv = bm.loops.layers.uv.new("UVMap"); t = tile_of(mat.name[8:]) if mat.name.startswith("SPECFIN:") else 0.5
        for f in bm.faces:
            n = f.normal
            for lp in f.loops:
                c = lp.vert.co
                lp[uv].uv = ((c.x / t, c.y / t) if abs(n.z) > 0.7 else ((c.y / t, c.z / t) if abs(n.x) > abs(n.y) else (c.x / t, c.z / t)))
        me = bpy.data.meshes.new("b"); bm.to_mesh(me); bm.free(); me.materials.append(mat); return me
    base_h = 0.30
    if frame == "studio":
        y0, y1 = -D / 2 + 0.06, D / 2
        meshes.append(box(-W / 2, -W / 2 + 0.045, y0, y1, 0.0, base_h, oak))                       # side rails (oak 45)
        meshes.append(box(W / 2 - 0.045, W / 2, y0, y1, 0.0, base_h, oak))
        meshes.append(box(-W / 2 + 0.045, W / 2 - 0.045, y1 - 0.045, y1, 0.0, base_h + 0.03, oak))  # foot rail
        for sx in (-1, 1):
            for sy in (y0 + 0.03, y1 - 0.03): meshes.append(box(sx * (W / 2 - 0.035) - 0.035, sx * (W / 2 - 0.035) + 0.035, sy - 0.035, sy + 0.035, 0.0, 0.08, oak))
        # headboard panel: a frame with vertical slats (the spec's "oak slatted, headboard panel")
        meshes.append(box(-W / 2, W / 2, -D / 2, -D / 2 + 0.06, 0.0, 0.07, oak))
        meshes.append(box(-W / 2, -W / 2 + 0.06, -D / 2, -D / 2 + 0.06, 0.0, hb, oak)); meshes.append(box(W / 2 - 0.06, W / 2, -D / 2, -D / 2 + 0.06, 0.0, hb, oak))
        meshes.append(box(-W / 2, W / 2, -D / 2, -D / 2 + 0.06, hb - 0.06, hb, oak))
        n = int((W - 0.12) / 0.075)
        for k in range(n):
            x = -W / 2 + 0.06 + (k + 0.5) * (W - 0.12) / n
            meshes.append(box(x - 0.022, x + 0.022, -D / 2 + 0.012, -D / 2 + 0.048, 0.07, hb - 0.06, oak, 0.003))
        mtop = base_h + mh
        my0 = -D / 2 + 0.07
    else:
        # the library frame (adapted by hb_furnish exactly as the build does): find its mattress top
        pl = json.load(open(os.path.join(os.path.dirname(a.spec), "furnishing_plan.json")))
        key = pl["items"][bed_id]["asset"]
        fob = HF.build_library_item(it, key, None, W, D, H, _Fin(), lambda it_, part, *f: None, log)
        fme = fob.data
        zs = [fme.vertices[i].co.z for p in fme.polygons if p.material_index < len(fme.materials) and fme.materials[p.material_index]
              and "fabric" in fme.materials[p.material_index].name.lower() for i in p.vertices]
        mtop = max(zs) if zs else base_h + mh
        ys = [fme.vertices[i].co.y for p in fme.polygons if p.material_index < len(fme.materials) and fme.materials[p.material_index]
              and "fabric" in fme.materials[p.material_index].name.lower() for i in p.vertices]
        my0 = min(ys) if ys else -D / 2 + 0.07
        xs_ = [fme.vertices[i].co.x for p in fme.polygons if p.material_index < len(fme.materials) and fme.materials[p.material_index]
               and "fabric" in fme.materials[p.material_index].name.lower() for i in p.vertices]
        if xs_: mw = max(xs_) - min(xs_)
        if ys: ml = max(ys) - min(ys)
        fo = bpy.data.objects.new("frame", fme); bpy.context.scene.collection.objects.link(fo); collider(fo, 0.004)
    log(bed_id, "mattress top", round(mtop, 3), "head end", round(my0, 3), "frame", frame)
    if frame == "studio":                                   # the frame collides too (the duvet hangs outside the rails)
        for k_, fm in enumerate(list(meshes)):
            fc = bpy.data.objects.new(f"fcol{k_}", fm.copy()); bpy.context.scene.collection.objects.link(fc); collider(fc, 0.004)
    mat_me = box(-mw / 2, mw / 2, my0, my0 + ml, mtop - mh, mtop, lin, 0.03)
    if frame == "studio": meshes.append(mat_me)
    mo = bpy.data.objects.new("mattress", mat_me.copy()); bpy.context.scene.collection.objects.link(mo); collider(mo, 0.004)
    # pillows: the library cushion adapted to a 650 x 420 x 130 pillow, leaning a little against the headboard
    npill = int(A_.get("pillows", 2)); rows = 2 if npill >= 4 else 1; per = max(1, npill // rows)
    pr = HF.proto("BK-CUSHION", log, front="-Y")
    pw = min(0.65, (mw - 0.04) / per)
    for r_ in range(rows):
        for k in range(per):
            pme = HF._adapt_fix(pr[0], pw - 0.02, 0.42, 0.13, HF.ASSET_CFG["BK-CUSHION"], None)
            pme.materials.clear(); pme.materials.append(lin)
            HF.box_uv(pme, tile_of("BED-LINEN"))
            x = -mw / 2 + (k + 0.5) * (mw / per)
            # lay flat (cushion's Z is its thickness after the adapt: rotate so the 420 side runs along Y)
            Mp = Matrix.Translation((x, my0 + 0.05 + 0.21 + r_ * 0.07, mtop + 0.065 + r_ * 0.06)) @ Matrix.Rotation(math.radians(-70 + r_ * 8), 4, "X")
            pme.transform(Mp); meshes.append(pme)
    # duvet: a cloth (mattress + 200 overhang each side), from 400 below the headboard to past the foot, dropped; the floor collides
    fl = bpy.data.meshes.new("fl"); bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=2.0); bm.to_mesh(fl); bm.free()
    flo = bpy.data.objects.new("floor", fl); bpy.context.scene.collection.objects.link(flo); collider(flo, 0.003)
    duvet_w = (mw + 0.40) if mw > 1.1 else (mw + 0.10); duvet_l = ml - 0.40 + 0.18      # a single bed against a wall: a tucked duvet
    cl = cloth_plane("duvet", duvet_w, duvet_l, 34, 46, Matrix.Translation((0, my0 + 0.42 + duvet_l / 2, mtop + 0.06)), lin, tile_of("BED-LINEN"))
    me = simulate(cl, frames=60, mass=0.6, stiff=10, bend=0.8)
    meshes.append(thicken(me, 0.035)); bpy.data.objects.remove(cl)
    # the throw across the foot (THROW-BED), over the duvet
    dv = bpy.data.objects.new("dcol", meshes[-1].copy()); bpy.context.scene.collection.objects.link(dv); collider(dv, 0.004)
    cl = cloth_plane("bthrow", mw + 0.25, 0.55, 30, 14, Matrix.Translation((0, my0 + ml - 0.32, mtop + 0.16)), thr, tile_of("THROW-BED"))
    me = simulate(cl, frames=55, mass=0.4, stiff=8, bend=0.6)
    meshes.append(thicken(me, 0.008))
    for me_ in meshes:                                     # nothing below the floor (a solidified duvet hem reaches into it)
        for v in me_.vertices:
            if v.co.z < 0.004: v.co.z = 0.004
    save(f"bed_{bed_id}", meshes, Matrix.Identity(4), dict(dresses=bed_id, frame=frame, linen="BED-LINEN", throw="THROW-BED", pillows=npill))


JOBS = [("towels_BTH", lambda: towels("BTH-TOWELRAD", "BTH-TOWELS")), ("towels_ENS", lambda: towels("ENS-TOWELRAD", "ENS-TOWELS")),
        ("hand_towel", lambda: hand_towel("CLA-TOWEL")), ("tea_towel", lambda: tea_towel("KA-DEC-8")),
        ("throw_LIV", lambda: throw("LIV-THROW", "LIV-SOFA")), ("throw_SIT", lambda: throw("SIT-THROW", "SIT-SOFA")),
        ("throw_KA", lambda: throw("KA-THROW", "KA-SOFA")),
        ("bed_BD2", lambda: bedding("BD2-BED", "studio")), ("bed_B3B", lambda: bedding("B3B-BED", "library"))]
for nm, fn in JOBS:
    if ONLY and nm not in ONLY: continue
    try: fn(); log("done", nm)
    except Exception as ex:
        import traceback; traceback.print_exc(); log("FAILED", nm, ex)
