"""The house's real setting from the surveyed garden model: keep the garden's own parts (ground surfaces, edgings,
hedges, fences, apple tree, planting, shed, pergola, bench, pots, bins, the houses opposite), drop its house, roofs and
neighbour (the house generator models those from the drawings), decimate the vegetation for the Quest, move everything
into the drawing frame, and tag each node with the contract's extras (existing, stage 1, never removed).

    nice Blender -b --factory-startup --python tools/house/make_setting.py -- <garden.glb> <out.glb> --shift dx dy dz \
        [--keep G2_,B_,...] [--decimate Plant2_=0.3,island_tree=0.25]

Registration for 23 Battle Road (renders/front-garden/audit-4/AUDIT.md): photo x = drawn x - 4.63, y = drawn y + 3.09,
z = drawn z + 0.231, so the shift into the drawing frame is (+4.63, -3.09, -0.231)."""
import sys, argparse, math
import bpy
from mathutils import Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("out")
ap.add_argument("--shift", nargs=3, type=float, default=[4.63, -3.09, -0.231])
# spec_v1 garden.exclude: Broom_* is clutter (Jack's sign-off decision 9) -> not kept
ap.add_argument("--keep", default="G2_,B_,island_tree,Plant2_,Conifer,Pot_,Bench_,Bird_table,Shed_,Perg_,Bin_,Opp_")
ap.add_argument("--spec", default="assets/sites/house/spec/spec_v1.json", help="the signed spec: garden fault fixes (GF-1 hedge blocks, colour targets)")
# round 6 (Jack: "the front garden has slipped in quality from our garden test", log 162): the source is the garden test's
# own Quest cut (model_q.glb) at its own detail and texture size; nothing is decimated, capped or merged here any more
ap.add_argument("--decimate", default="", help="name=ratio,... (off: model_q.glb's level of detail is the floor)")
ap.add_argument("--max-tex", type=int, default=0, help="0: keep the garden test's texture sizes")
ap.add_argument("--merge", action="store_true", help="share look-alike garden materials (off: every garden material kept)")
ap.add_argument("--site-json", default="", help="the garden test's site.json (grass density, sun) for the extras")
ap.add_argument("--ground-region", nargs=4, type=float, default=[-9.37, -31.19, 20.63, 0.0],
                help="x0 y0 x1 y1 (drawing frame): the garden's ground is clipped to this rectangle; the house ground covers the rest")
ap.add_argument("--drop", default="G2_far_ground", help="garden parts never used (the house ground has its own far field)")
args = ap.parse_args(argv)
keep = [k for k in args.keep.split(",") if k]
dec = {k: float(v) for k, v in (p.split("=") for p in args.decimate.split(",") if p)}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=args.src)
T = Matrix.Translation(args.shift)
GROUP = [("G2_", "ground"), ("B_fence", "fitting"), ("B_", "fitting"), ("island_tree", "fitting"), ("Apple_", "fitting"), ("Plant2_", "fitting"),
         ("Opp_", "fitting"), ("Shed_", "fitting"), ("Perg_", "fitting")]
PLAIN = [("G2_lawn", "Front lawn"), ("G2_paving", "Block paving"), ("G2_gravel", "Gravel drive"), ("G2_", "Front garden surface / edging"),
         ("B_street_hedge", "Hedge along the road"), ("B_hedge", "Boundary hedge"), ("B_fence", "Fence by the drive"), ("island_tree", "Apple tree"), ("Apple_", "Apple tree"),
         ("Plant2_", "Planting"), ("Conifer", "Topiary in a pot"), ("Pot_", "Pot"), ("Bench_", "Stone bench"), ("Bird_table", "Bird table"),
         ("Shed_", "Shed"), ("Perg_", "Pergola"), ("Bin_", "Bins"), ("Opp_", "House across the road")]
for ob in bpy.data.objects:                 # unparent, keeping world placement
    if ob.type == "MESH" and ob.parent is not None:
        mw = ob.matrix_world.copy(); ob.parent = None; ob.matrix_world = mw
# row 179: the garden model carries a few exact duplicates (Opp_roof_N_ridge and .001 in one place): they z-fight from the road.
# A copy whose mesh has the same vertex count and the same world bounds (5 mm) as a kept object of the same base name goes.
_seen = {}
for ob in sorted([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: o.name):
    import re as _re
    base = _re.sub(r"\.\d+$", "", ob.name)
    bb = [ob.matrix_world @ __import__("mathutils").Vector(c) for c in ob.bound_box]
    key = (base, len(ob.data.vertices))
    lo = tuple(round(min(v[i] for v in bb), 2) for i in range(3)); hi = tuple(round(max(v[i] for v in bb), 2) for i in range(3))
    dup = next((k for k in _seen.get(key, []) if all(abs(x - y) <= 0.005 + 1e-9 for x, y in zip(k, lo + hi))), None)
    if dup is not None:
        print("setting: dropped duplicate", ob.name); bpy.data.objects.remove(ob); continue
    _seen.setdefault(key, []).append(lo + hi)
removed = kept = 0
tris_before = tris_after = 0
for ob in list(bpy.data.objects):
    if ob.type != "MESH":
        continue
    if not any(ob.name.startswith(k) for k in keep):
        bpy.data.objects.remove(ob); removed += 1; continue
    tris_before += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    for k, r in dec.items():
        if ob.name.startswith(k) and r < 1:
            if ob.data.users > 1: ob.data = ob.data.copy()
            m = ob.modifiers.new("dec", "DECIMATE"); m.ratio = r
            bpy.context.view_layer.objects.active = ob
            dg = bpy.context.evaluated_depsgraph_get()
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
            ob.modifiers.clear(); ob.data = me
            break
    tris_after += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    ob.matrix_world = T @ ob.matrix_world
    g = next((v for k, v in GROUP if ob.name.startswith(k)), "fitting")
    plain = next((v for k, v in PLAIN if ob.name.startswith(k)), "Front garden")
    props = dict(element="SET-" + ob.name, stage_in=1, seq=0.0, category="existing", group=g, storey="site",
                 label=f"Front garden as surveyed (garden model, registered to the drawings): {ob.name}", plain_label=plain,
                 drawing="garden survey (photo model, audit-4 registration)", conf="scaled",
                 collide=g == "ground" or ob.name.startswith(("B_fence", "Shed_", "Perg_post", "Bench_", "B_hedge", "B_street_hedge", "Bin_")),
                 context=True)
    for k, v in props.items(): ob[k] = v
    kept += 1
# ground: one surface per place (round 6: the road view showed the garden's ground stacked 2-9 cm over the house's).
# The garden's far field goes; every other ground part is clipped to the ground region, which the house ground leaves to it.
import bmesh
drop = tuple(p for p in args.drop.split(",") if p)
x0, y0, x1, y1 = args.ground_region
for ob in list(bpy.data.objects):
    if ob.type != "MESH": continue
    if ob.name.startswith(drop):
        bpy.data.objects.remove(ob); continue
    if not ob.name.startswith("G2_"): continue
    me = ob.data
    if me.users > 1: ob.data = me = me.copy()
    bm = bmesh.new(); bm.from_mesh(me); bm.transform(ob.matrix_world)
    for co, no in (((x0, 0, 0), (-1, 0, 0)), ((x1, 0, 0), (1, 0, 0)), ((0, y0, 0), (0, -1, 0)), ((0, y1, 0), (0, 1, 0))):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True)
    if ob.name.startswith("G2_soil"):          # the hidden base: 20 mm lower, so nothing laid on it sits within 30 mm of it
        for v in bm.verts: v.co.z -= 0.02
    bm.transform(ob.matrix_world.inverted()); bm.to_mesh(me); bm.free()
    if not me.polygons: bpy.data.objects.remove(ob)
# Quest draw calls: look-alike materials of the garden share one (round 6: 47 -> ~27 batches)
MERGE = [("FG2_timber_pale_v", "FG2_timber_pale"), ("FG2_bin_grey_face", "FG2_bin_grey"), ("FG2_bin_brown_face", "FG2_bin_brown"),
         ("FG2_anthracite", "FG_gutter_black"), ("FG2_dark_grey", "FG_gutter_black"), ("FG_wheel", "FG_gutter_black"),
         ("FG2_drain_grate", "FG_gutter_black"), ("FG2_roof_felt", "FG_gutter_black"), ("FG2_lamp_white", "FG_fascia_white"),
         ("FG_soil", "FG_mulch"), ("FG_turf_neighbour", "FG_lawn"), ("FG_kerb", "FG2_sett_grey"), ("FG2_conifer_rust", "FG2_conifer_green"),
         ("FG2_fence_gap", "FG2_timber_pine"), ("FG2_hedge_leaf", "FG_hedge_face"), ("island_tree_02.", "island_tree_02_branches")]
by_name = {m.name: m for m in bpy.data.materials}
merged = 0
for ob in (bpy.data.objects if args.merge else []):
    if ob.type != "MESH": continue
    for slot in ob.material_slots:
        if not slot.material: continue
        for a, b in MERGE:
            if slot.material.name.startswith(a):
                tgt = next((m for n, m in by_name.items() if n.startswith(b) and not any(n.startswith(x) for x, _ in MERGE)), None)
                if tgt is not None and tgt is not slot.material: slot.material = tgt; merged += 1
                break
print("setting: merged material slots", merged)
# what the garden test's viewer adds at run time, written as extras so the house viewer can do the same (src/site.js):
# grass tufts on the lawn, cut-out foliage drawn with alpha-to-coverage and kept out of the Quest shadow pass, the sun
import json as _json, os as _os
site = {}
sj = args.site_json or _os.path.join(_os.path.dirname(_os.path.abspath(args.src)), "site.json")
if _os.path.exists(sj): site = _json.load(open(sj))
for m in bpy.data.materials:
    nm = m.name.lower()
    if any(k in nm for k in ("leaves", "leaf", "vertexplant", "branches", "conifer", "hedge")):
        m["foliage"] = True; m["quest_cast_shadow"] = False
    if "lawn" in nm or "turf" in nm:
        m["grass_per_m2"] = site.get("grassPerM2", 520); m["grass_per_m2_quest"] = site.get("grassPerM2Quest", 160)
src_tris = {}
import numpy as _np
from mathutils import Vector as _V

# --- homeowner judge r6 (log 165-167): surfaces from the photos, the frontage open, real shrubs ------------------------
# 1. street hedge: separate clipped blocks beside the path gap and at the drive edge, the frontage open between (photos
#    walk_0001/0133/0143/0153/0157/0175); the garden model's continuous hedge is wrong there too (a note for the garden build)
HEDGE_BLOCKS = [(-2.25, -0.25), (0.70, 2.70), (7.10, 9.15)]                 # drawing x ranges (round 6)
HEDGE_TOP = None
try:                                                                            # spec_v1 GF-1 (signed): the blocks' x ranges and height
    import json as _j, re as _r, os as _o
    _sp = args.spec if _o.path.isabs(args.spec) else _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), "..", "..", args.spec)
    _gf = next(f for f in _j.load(open(_sp))["garden"]["known_faults"] if f["id"] == "GF-1")
    _xr = [(float(a), float(b)) for a, b in _r.findall(r"x (-?[\d.]+)\.\.(-?[\d.]+)", _gf["fix"])]
    _h = _r.search(r"height ([\d.]+)-([\d.]+)", _gf["fix"])
    if len(_xr) == 3: HEDGE_BLOCKS = _xr
    if _h: HEDGE_TOP = (float(_h.group(1)), float(_h.group(2)))
    print("setting: GF-1 hedge blocks from the spec", HEDGE_BLOCKS, HEDGE_TOP)
except Exception as _e: print("setting: GF-1 not read from the spec:", _e)
for ob in list(bpy.data.objects):
    if ob.type != "MESH" or not ob.name.startswith("B_street_hedge"): continue
    pieces = []
    for (xa, xb) in HEDGE_BLOCKS:
        me = ob.data.copy(); bm = bmesh.new(); bm.from_mesh(me); bm.transform(ob.matrix_world)
        for co, no in (((xa, 0, 0), (-1, 0, 0)), ((xb, 0, 0), (1, 0, 0))):
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no, clear_outer=True)
        if not bm.faces: bm.free(); continue
        # close the cut ends and give the top an irregular clipped line (+-6 cm)
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
        if HEDGE_TOP:                    # scale the block so its clipped top sits at the spec height (ground = drawing z -0.231)
            g0 = min(v.co.z for v in bm.verts); top = max(v.co.z for v in bm.verts)
            want = -0.231 + (HEDGE_TOP[0] + HEDGE_TOP[1]) / 2 - 0.03
            if top - g0 > 0.1:
                for v in bm.verts: v.co.z = g0 + (v.co.z - g0) * (want - g0) / (top - g0)
        for v in bm.verts:
            if v.co.z > 1.2 - 0.231: v.co.z += 0.045 * _np.sin(v.co.x * 3.1) * _np.cos(v.co.y * 5.3)    # irregular rounded top (+-45 mm)
        bm.transform(ob.matrix_world.inverted()); bm.to_mesh(me); bm.free()
        o2 = ob.copy(); o2.data = me; o2.name = f"{ob.name}_block_{xa:+.2f}"; bpy.context.scene.collection.objects.link(o2)
        pieces.append(o2)
    bpy.data.objects.remove(ob)
    print("setting: street hedge ->", len(pieces), "clipped blocks")
# 2. the boundary 'hedge' by the door was a hairy box: three real shrubs (the garden's own scanned plant, alpha-tested)
shrubs = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("Plant2_")]
box = next((o for o in bpy.data.objects if o.type == "MESH" and o.name == "B_hedge"), None)
if box is not None and shrubs:
    def hgt(o):
        zs = [v.co.z for v in o.data.vertices]; return max(zs) - min(zs)
    proto = next((o for o in shrubs if o.data.name.startswith("box_ball")), max(shrubs, key=hgt))   # the clipped evergreen
    bb = [box.matrix_world @ _V(c) for c in box.bound_box]
    x0, x1 = min(v.x for v in bb), max(v.x for v in bb); y0, y1 = min(v.y for v in bb), max(v.y for v in bb); z0, z1 = min(v.z for v in bb), max(v.z for v in bb)
    ph = hgt(proto); pv = [v.co for v in proto.data.vertices]
    pw = max(max(v.x for v in pv) - min(v.x for v in pv), max(v.y for v in pv) - min(v.y for v in pv))
    n = max(1, round((y1 - y0) / 1.0))
    for k in range(n):
        o2 = bpy.data.objects.new(f"Plant2_door_shrub_{k}", proto.data)        # linked: one mesh, instanced
        bpy.context.scene.collection.objects.link(o2)
        sz = (z1 - z0) / ph; sxy = min(sz, (x1 - x0) * 1.1 / max(pw, 1e-3))
        o2.scale = (sxy, sxy, sz); o2.rotation_euler = (0, 0, 1.3 * k)
        cx = sum(v.x for v in pv) / len(pv); cy = sum(v.y for v in pv) / len(pv); mz = min(v.z for v in pv)
        o2.location = ((x0 + x1) / 2 - cx * sxy, y0 + (k + 0.5) * (y1 - y0) / n - cy * sxy, z0 - mz * sz)
        for kk in box.keys(): o2[kk] = box[kk]
        o2["plain_label"] = "Shrub by the door"; o2["element"] = f"SET-door-shrub-{k}"
    bpy.data.objects.remove(box)
    print("setting: door hedge box ->", n, "shrubs (", proto.name, ")")
# 3. gravel warm gold flint, block paving deep red/brown/charcoal with contrast (walk_0011, 0027, 0035, 0041, 20260719_102925)
def recolour_image(im, target, contrast):
    """per-channel gain to the photo's mean colour, then contrast about the mean: each unit keeps its own colour
    (red / brown / charcoal mix), only the whole sheet moves to the photographed colour"""
    a = _np.array(im.pixels[:], dtype=_np.float32).reshape(-1, 4)
    rgb = a[:, :3]
    t = _np.array(target, _np.float32) / 255.0
    t = _np.where(t <= 0.04045, t / 12.92, ((t + 0.055) / 1.055) ** 2.4)        # images hold linear values in Blender
    mean = _np.maximum(rgb.mean(0), 1e-4)
    g = rgb * (t / mean)
    a[:, :3] = _np.clip(t + (g - t) * contrast, 0, 1)
    im.pixels[:] = a.ravel(); im.update()
done_im = set()
for m in bpy.data.materials:
    nm = m.name.lower()
    # MEASURED (row 176): per-region Lab medians and spreads of the photos walk_0011/0019/0027 and 20260719_102925 against
    # the matched renders (renders/house-build/judge-r6/after/colour_*.json); the gravel read 1:1, so the targets are the
    # photos' own medians, and the contrast lifts each unit's spread towards the photos' blend (red / brown / buff / charcoal)
    tgt = ((196, 178, 152), 2.0) if "gravel" in nm else ((182, 158, 146), 2.6) if ("paving_units" in nm or nm.startswith("fg_paving")) \
        else ((116, 128, 58), 1.15) if ("fg_lawn" in nm or "turf" in nm) else None
    if not tgt or not m.use_nodes: continue
    for nd in m.node_tree.nodes:
        if nd.type == "TEX_IMAGE" and nd.image and nd.image.name not in done_im and nd.image.colorspace_settings.name != "Non-Color":
            recolour_image(nd.image, *tgt); done_im.add(nd.image.name)
            if nd.image.packed_file or True: nd.image.pack()
print("setting: recoloured", sorted(done_im))
# --- GPU (viewer perf r6c): closed solids single-sided, foliage alpha-tested (MASK), never blended --------------------
OPEN = ("leaves", "leaf", "vertexplant", "branches", "conifer", "hedge", "fence", "board", "glass", "mesh", "grate")
for m in bpy.data.materials:
    open_sheet = any(k in m.name.lower() for k in OPEN)
    m.use_backface_culling = not open_sheet
    if (m.get("foliage") or "leaves" in m.name.lower() or "leaf" in m.name.lower()) and m.use_nodes:
        # alpha-tested, never blended: the glTF exporter writes MASK when the alpha runs through a Math ROUND node
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf and bsdf.inputs["Alpha"].is_linked:
            lk = bsdf.inputs["Alpha"].links[0]
            if not (lk.from_node.type == "MATH" and lk.from_node.operation == "ROUND"):
                rnd = nt.nodes.new("ShaderNodeMath"); rnd.operation = "ROUND"
                nt.links.new(lk.from_socket, rnd.inputs[0]); nt.links.new(rnd.outputs[0], bsdf.inputs["Alpha"])
        try: m.blend_method = "CLIP"
        except Exception: pass
        try: m.surface_render_method = "DITHERED"
        except Exception: pass
# a far LOD for the apple tree (swap at ~15 m), written to <out>_lod.glb so a viewer without LOD support never draws both
LOD = []
# every keep prefix must match something: a renamed part in the garden model must not vanish silently
names = [o.name for o in bpy.data.objects]
missing = [k for k in keep if not any(n.startswith(k) for n in names)]
if missing: print("setting: WARNING keep prefixes with no match (renamed in the garden model?):", missing)
# the Quest budget: no texture above 1k (the garden's tree came with 2k Poly Haven maps)
for im in bpy.data.images:
    w, h = im.size
    if args.max_tex and max(w, h) > args.max_tex:
        s = args.max_tex / max(w, h); im.scale(int(w * s), int(h * s))
# empties / parents left over
for ob in list(bpy.data.objects):
    if ob.type != "MESH" and not ob.children: bpy.data.objects.remove(ob)
for o in bpy.data.objects:
    if o.type == "MESH" and o.name.startswith(("island_tree", "Conifer")):
        o["lod_group"] = "apple_tree" if o.name.startswith("island_tree") else o.name.split(".")[0]; o["lod_role"] = "near"; o["lod_switch_m"] = 15.0
for ob in bpy.data.objects: ob.select_set(ob.type == "MESH")
bpy.ops.export_scene.gltf(filepath=args.out, export_format="GLB", use_selection=True, export_extras=True, export_yup=True,
                          export_apply=True, export_image_format="WEBP", export_image_quality=80)
print(f"setting: kept {kept}, removed {removed}, tris {tris_before} -> {tris_after}")
# far LOD (contract: lod_group, lod_role near|far, lod_switch_m): the near node stays in the setting as it is; the far copy
# (decimated) goes to a separate file the viewer loads only if it swaps LODs
for o in [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(("island_tree", "Conifer"))]:
    grp = "apple_tree" if o.name.startswith("island_tree") else o.name.split(".")[0]
    o["lod_group"] = grp; o["lod_role"] = "near"; o["lod_switch_m"] = 15.0
    f = o.copy(); f.data = o.data.copy(); f.name = o.name + "_far"; bpy.context.scene.collection.objects.link(f)
    m = f.modifiers.new("dec", "DECIMATE"); m.ratio = 0.15 if grp == "apple_tree" else 0.3
    bpy.context.view_layer.objects.active = f
    dg = bpy.context.evaluated_depsgraph_get(); me = bpy.data.meshes.new_from_object(f.evaluated_get(dg)); f.modifiers.clear(); f.data = me
    f["lod_group"] = grp; f["lod_role"] = "far"; f["lod_switch_m"] = 15.0; f["element"] = str(o.get("element", o.name)) + "-far"
    LOD.append(f)
if LOD:
    for ob in bpy.data.objects: ob.select_set(ob in LOD)
    lp = args.out.replace(".glb", "_lod.glb")
    bpy.ops.export_scene.gltf(filepath=lp, export_format="GLB", use_selection=True, export_extras=True, export_yup=True,
                              export_apply=True, export_image_format="WEBP", export_image_quality=80)
    print("setting: far LODs", len(LOD), "->", lp, sum(len(p.vertices) - 2 for f in LOD for p in f.data.polygons), "tris")
