"""Furnishing (WORKFLOW G5 'Studio asset library', G5c): the loose layer and the held joinery built to the bar, Blender side.

Called by hb_items.build_items. Reads the site's furnishing plan (assets/sites/<site>/spec/furnishing_plan.json: item id ->
library asset, route, adapt notes) and the lived-in addendum (spec_v1_addendum2_details.json).

  - library models (studio library ~/Desktop/garden-scans/asset-library: blendkit/<key>/source.blend, polyhaven/...) are
    loaded once, joined, turned so their front is +Y (local frame of hb_items), pivoted at the footprint centre of the base;
  - ADAPT (Jack 1 Nov: "get a baseline model and then just extend or manipulate to fit"): stretch zones keep the ends (arms,
    legs, handles: the outer 22 % each side) true and stretch only the middle to the spec size; a sofa's seat modules are
    removed whole (a 3-seat base becomes a 2-seat) before the stretch; NOT whole-object non-uniform scaling;
  - recolour: the asset's own material slots named by role (upholstery, legs, linen...) take the spec finish, with UVs
    re-projected at the finish's true scale;
  - studio-made soft items (cloth-sim results from tools/library/cloth_soft.py) and parametric v2 kinds (curtains with real
    pleats, rugs with a soft bullnose edge and woven border);
  - every loose node gets furnishing: true (and lived_in: true for the addendum); anything standing on a loose item inherits it;
  - a validator: every loose item rests on something (gap <= 10 mm) and passes into nothing (BVH overlap with the shell and
    with other loose items, small allowance for soft contact)."""
import os, re, json, math
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

LIB = os.path.expanduser("~/Desktop/garden-scans/asset-library")
HERE = os.path.dirname(os.path.abspath(__file__))
SOFT_TEX = os.path.join(HERE, "..", "..", "master", "phototex", "soft")
LOOSE = {"furniture", "soft_furnishing", "decor", "plant"}
_CACHE = {}
NOTES = []
REPORT = dict(items={}, validator=[], lived_in=[])
OUT_DIR = None

# material roles per library asset: regex on the asset's material name -> part name of the spec item's materials map
ROLES = {
    "BK-SOFA-BURRARD": [(r"fabric", "upholstery"), (r"wood|cap", "legs")],
    "BK-ARMCHAIR-ROUND": [(r"fabric|linen", "upholstery"), (r"wood", "frame")],
    "BK-ARMCHAIR-ALT": [(r"030|031", "upholstery"), (r"032", "frame")],
    "BK-BED-ULTIMA": [(r"bed (light|dark) fabric|black board", "frame"), (r"white pillow|sheet|blanket|orange pillow", "linen"), (r"orange cloth", "throw")],
    "BK-BED-SINGLE-OAK": [(r"wood|slatt", "frame"), (r"fabric", "linen")],
    "BK-CUSHION": [(r".", "all")],
    "BK-BEDSIDE-ARCH": [(r".", "all")],
    "BK-DESK-OAK": [(r"bois", "all"), (r"m.tal", "@METAL-BLACK")],
    "BK-RATTAN-SOFA": [(r"fabric", "cushions"), (r"straw", "frame")],
    "BK-RATTAN-CHAIR": [(r"fabric", "cushions"), (r"rattan|wicker", "frame")],
    "BK-KETTLE": [(r"enamel", "@CER-CREAM")],
    "BK-TOASTER": [(r"material\.00[12]|wire_227", "@CER-CREAM")],
    "BK-COFFEE": [(r"body paint", "@STEEL-BRUSHED")],
    "BK-OILVINEGAR": [(r"wood", "@WOOD-OAK-FURN")],
    "BK-DISH": [(r".", "@CER-CREAM")],
    "BK-WC-CC": [(r"ceramic|white|porcel|toilet|wc|material|default", "@SAN-WHITE")],
    "BK-WC-WALL": [(r"ceramic|white|porcel|toilet|wc|material|default", "@SAN-WHITE")],
}
# default finish per role when the spec item's map does not name one (the spec's own words: oak legs, linen...)
ROLE_DEFAULT = {"upholstery": "FAB-SOFA", "legs": "WOOD-OAK-FURN", "frame": "WOOD-OAK-FURN", "linen": "BED-LINEN", "throw": "THROW-BED",
                "cushions": "FAB-SOFA", "all": None}


def load_plan(spec_path):
    p = os.path.join(os.path.dirname(spec_path), "furnishing_plan.json")
    return json.load(open(p)) if os.path.exists(p) else None


def load_addendum(spec_path):
    p = os.path.join(os.path.dirname(spec_path), "spec_v1_addendum2_details.json")
    return (json.load(open(p)), p) if os.path.exists(p) else (None, p)


# ------------------------------------------------------------------------------------------------ library prototypes
def _join_blend(path, log, drop=r"^(camera|light|plane|floor|ground|backdrop|cyc|studio)"):
    before = set(bpy.data.objects)
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    sc = bpy.context.scene.collection
    new = [o for o in dst.objects if o is not None]
    for o in new:
        if o.name not in sc.objects: sc.objects.link(o)
    bpy.context.view_layer.update()                    # parents' transforms into matrix_world (FBX-style rotated empties)
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new(); mats = []
    for o in new:
        if o.type != "MESH" or re.search(drop, o.name, re.I) or o.hide_render: continue
        for md in o.modifiers:
            if md.type == "SUBSURF": md.levels = min(md.levels, 1)
        try: me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        except Exception: me = o.data.copy()
        idx = []
        for m in me.materials:
            if m not in mats: mats.append(m)
            idx.append(mats.index(m))
        tmp = bmesh.new(); tmp.from_mesh(me); tmp.transform(o.matrix_world)
        for f in tmp.faces: f.material_index = idx[f.material_index] if f.material_index < len(idx) else 0
        tm = bpy.data.meshes.new("_j"); tmp.to_mesh(tm); tmp.free(); bm.from_mesh(tm); bpy.data.meshes.remove(tm); bpy.data.meshes.remove(me)
    for o in new:
        try: bpy.data.objects.remove(o)
        except Exception: pass
    return bm, mats


def proto(key, log, front="-Y", cap=None):
    """(mesh, dims, matnames) for a library asset key: BK-... (blendkit/<key>/source.blend) or soft:<name> (cloth results)"""
    if key in _CACHE:
        c_ = _CACHE[key]
        try:
            if c_ is None or c_[0].name: return c_
        except ReferenceError: pass                 # the generator freed it with the previous version: load again
    if key.startswith("soft:"): path = os.path.join(LIB, "soft", key[5:], "source.blend")
    else: path = os.path.join(LIB, "blendkit", key, "source.blend")
    if not os.path.exists(path): log("library asset missing", key, path); _CACHE[key] = None; return None
    try: bm, mats = _join_blend(path, log)
    except Exception as ex: log("library load failed", key, ex); _CACHE[key] = None; return None
    if not bm.verts: _CACHE[key] = None; return None
    if front == "-Y": bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi, 3, "Z"))
    elif front == "+X": bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Z"))
    elif front == "-X": bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(-math.pi / 2, 3, "Z"))
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]
    if not key.startswith("soft:"):                      # cloth results are already in their spec item's frame: never re-pivot
        c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)))
        bmesh.ops.translate(bm, verts=bm.verts, vec=-c)
    me = bpy.data.meshes.new(f"LIB_{key}"); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    dims = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    cap = cap or (900 if max(dims) < 0.45 else 5000)
    if tris > cap:
        tmpo = bpy.data.objects.new("_dec", me); bpy.context.scene.collection.objects.link(tmpo)
        md = tmpo.modifiers.new("dec", "DECIMATE"); md.ratio = max(0.02, cap / tris); md.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get(); me2 = bpy.data.meshes.new_from_object(tmpo.evaluated_get(dg))
        bpy.data.objects.remove(tmpo); bpy.data.meshes.remove(me); me = me2; me.name = f"LIB_{key}"
        NOTES.append(f"{key}: {tris} -> {sum(len(p.vertices) - 2 for p in me.polygons)} triangles (Quest budget)")
    for m in me.materials:
        if not m: continue
        if not m.name.startswith(("LIB-", "spec_", "SPECFIN:", "soft_")): m.name = f"LIB-{key[:18]}-{m.name}"[:63]
        m.use_backface_culling = False
        if m.use_nodes:
            for g_ in [n for n in m.node_tree.nodes if n.type == "GROUP" and n.node_tree and "gltf" in n.node_tree.name.lower()]: m.node_tree.nodes.remove(g_)
            for tn in [n for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image and n.image.channels < 3]: m.node_tree.nodes.remove(tn)
            bs = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bs:
                for inp, val in (("Roughness", 0.6), ("Metallic", 0.0)):
                    if inp in bs.inputs:
                        for lk in list(bs.inputs[inp].links): m.node_tree.links.remove(lk)
                        if inp == "Metallic" and re.search(r"chrome|steel|metal|brass", m.name, re.I): bs.inputs[inp].default_value = 1.0
                        else: bs.inputs[inp].default_value = val
    _CACHE[key] = (me, dims, [m.name if m else "" for m in me.materials])
    return _CACHE[key]


# ------------------------------------------------------------------------------------------------ adapt (stretch zones, modules)
def _remap(c, lo, hi, tgt, keep=0.22):
    """piecewise map of coordinate c from [lo, hi] onto [-tgt/2, tgt/2]: the outer `keep` of each side kept at size, the
    middle stretched (if the target is too small for that, everything scales evenly)"""
    L = hi - lo
    if L < 1e-6: return c
    e = keep * L
    mid_src, mid_dst = L - 2 * e, tgt - 2 * e
    if mid_dst <= 0.1 * mid_src:                                   # cannot keep the ends: plain scale
        return -tgt / 2 + (c - lo) * tgt / L
    if c <= lo + e: return -tgt / 2 + (c - lo)
    if c >= hi - e: return tgt / 2 - (hi - c)
    return -tgt / 2 + e + (c - lo - e) * mid_dst / mid_src


def adapt(me_src, dims, W, D, H, modules=None, keep=0.22):
    """a new mesh: the library mesh fitted to W x D x H by stretch zones; modules=(n_src, n_dst) removes whole middle seat
    modules along X first (islands inside a removed slab are deleted, the frame closes up)"""
    me = me_src.copy()
    bm = bmesh.new(); bm.from_mesh(me)
    if modules and modules[0] > modules[1]:
        n_src, n_dst = modules
        xs = [v.co.x for v in bm.verts]; x0, x1 = min(xs), max(xs)
        arm = 0.15 * (x1 - x0) / 2 if (x1 - x0) > 1.0 else 0.0
        pitch = (x1 - x0 - 2 * arm) / n_src
        cut = pitch * (n_src - n_dst)
        # islands
        bm.verts.ensure_lookup_table(); seen = set(); dele = []
        for v in bm.verts:
            if v.index in seen: continue
            stack = [v]; isl = []
            while stack:
                q = stack.pop()
                if q.index in seen: continue
                seen.add(q.index); isl.append(q)
                for ed in q.link_edges:
                    o = ed.other_vert(q)
                    if o.index not in seen: stack.append(o)
            cx = sum(q.co.x for q in isl) / len(isl); w = max(q.co.x for q in isl) - min(q.co.x for q in isl)
            if abs(cx) < cut / 2 and w < pitch * 1.3: dele.extend(isl)
        if dele: bmesh.ops.delete(bm, geom=list(set(dele)), context="VERTS")
        for v in bm.verts:
            if v.co.x > cut / 2: v.co.x -= cut / 2
            elif v.co.x < -cut / 2: v.co.x += cut / 2
            else: v.co.x = 0.0
        xs = [v.co.x for v in bm.verts]
        dims = (max(xs) - min(xs), dims[1], dims[2])
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]
    lx, hx, ly, hy, lz, hz = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
    for v in bm.verts:
        x = _remap(v.co.x, lx, hx, W, keep); y = _remap(v.co.y, ly, hy, D, keep)
        z = _remap(v.co.z, lz, hz, H, keep) + H / 2
        v.co = Vector((x, y, z))
    bm.to_mesh(me); bm.free()
    return me


def uniform_fit(me_src, dims, W, D, H):
    s = min(W / max(dims[0], 1e-6), D / max(dims[1], 1e-6), H / max(dims[2], 1e-6))
    me = me_src.copy(); me.transform(Matrix.Scale(s, 4)); return me, s


# ------------------------------------------------------------------------------------------------ recolour
def recolour(me, key, it, fin, mats_for):
    """swap the asset's own role slots for the spec finishes; UVs of swapped faces box-projected at the finish's true scale"""
    roles = ROLES.get(key, [])
    if not roles: return []
    swapped = {}
    for i, m in enumerate(me.materials):
        nm = (m.name if m else "").lower()
        for rx, role in roles:
            if re.search(rx, nm):
                if role.startswith("@"): fk = role[1:]
                else: fk = mats_for(it, role) or ROLE_DEFAULT.get(role)
                if fk and fk in fin.F: swapped[i] = fk
                break
    if not swapped: return []
    uvl = me.uv_layers.active or me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        if p.material_index not in swapped: continue
        fk = swapped[p.material_index]; tw, th = fin.tile.get(fin.get(fk).name, (1.0, 1.0))
        n = p.normal
        for li in p.loop_indices:
            c = me.vertices[me.loops[li].vertex_index].co
            if abs(n.z) > 0.7: uvl.data[li].uv = (c.x / tw, c.y / th)
            elif abs(n.x) > abs(n.y): uvl.data[li].uv = (c.y / tw, c.z / th)
            else: uvl.data[li].uv = (c.x / tw, c.z / th)
    for i, fk in swapped.items():
        m2 = fin.get(fk)
        me.materials[i] = m2
    return sorted(set(swapped.values()))


def soft_material(name, col, nrm, tile, rough=0.85):
    """terry / waffle / striped cotton for towels (not spec finishes: the spec names the colour, the checklist the weave)"""
    if name in bpy.data.materials: return bpy.data.materials[name]
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    bs = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tc = nt.nodes.new("ShaderNodeTexImage"); tc.image = bpy.data.images.load(os.path.join(SOFT_TEX, col), check_existing=True)
    nt.links.new(tc.outputs["Color"], bs.inputs["Base Color"])
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = bpy.data.images.load(os.path.join(SOFT_TEX, nrm), check_existing=True)
    tn.image.colorspace_settings.name = "Non-Color"
    nm = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(tn.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
    bs.inputs["Roughness"].default_value = rough
    if "Sheen Weight" in bs.inputs: bs.inputs["Sheen Weight"].default_value = 0.3
    m["soft_tile_m"] = tile; m.use_backface_culling = False
    return m


def box_uv(me, tile):
    uvl = me.uv_layers.active or me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        n = p.normal
        for li in p.loop_indices:
            c = me.vertices[me.loops[li].vertex_index].co
            if abs(n.z) > 0.7: uvl.data[li].uv = (c.x / tile, c.y / tile)
            elif abs(n.x) > abs(n.y): uvl.data[li].uv = (c.y / tile, c.z / tile)
            else: uvl.data[li].uv = (c.x / tile, c.z / tile)


# ------------------------------------------------------------------------------------------------ studio-made v2 kinds
def _solid_from_grid(P, thick, key, mb):
    """a closed solid from a grid surface P[i][j] (local coords) offset by `thick` along its normals (curtains, blinds)"""
    ni, nj = len(P), len(P[0])
    def nrm_at(i, j):
        a = Vector(P[min(i + 1, ni - 1)][j]) - Vector(P[max(i - 1, 0)][j]); b = Vector(P[i][min(j + 1, nj - 1)]) - Vector(P[i][max(j - 1, 0)])
        n = a.cross(b); return n.normalized() if n.length > 1e-9 else Vector((0, 1, 0))
    F_ = [[tuple(Vector(P[i][j]) + nrm_at(i, j) * thick / 2) for j in range(nj)] for i in range(ni)]
    B_ = [[tuple(Vector(P[i][j]) - nrm_at(i, j) * thick / 2) for j in range(nj)] for i in range(ni)]
    V = [v for row in F_ for v in row] + [v for row in B_ for v in row]
    off = ni * nj
    def ix(i, j, back=0): return back * off + i * nj + j
    Fs = []
    for i in range(ni - 1):
        for j in range(nj - 1):
            Fs.append((ix(i, j), ix(i + 1, j), ix(i + 1, j + 1), ix(i, j + 1)))
            Fs.append((ix(i, j + 1, 1), ix(i + 1, j + 1, 1), ix(i + 1, j, 1), ix(i, j, 1)))
    for i in range(ni - 1):
        Fs.append((ix(i, 0, 1), ix(i + 1, 0, 1), ix(i + 1, 0), ix(i, 0)))
        Fs.append((ix(i, nj - 1), ix(i + 1, nj - 1), ix(i + 1, nj - 1, 1), ix(i, nj - 1, 1)))
    for j in range(nj - 1):
        Fs.append((ix(0, j), ix(0, j + 1), ix(0, j + 1, 1), ix(0, j, 1)))
        Fs.append((ix(ni - 1, j, 1), ix(ni - 1, j + 1, 1), ix(ni - 1, j + 1), ix(ni - 1, j)))
    mb.pieces.append((V, Fs, key, 0.0))


def k_curtain_pair2(mb, W, D, H, it, mats_for, LINEN="FAB-CURTAIN"):
    """double pinch-pleat curtains, open, stacked each side: a matt black 25 mm pole with finials and brackets; each panel a
    real pleated drape: pinch pleats every ~100 mm at the heading, folds that open and deepen towards the hem, a weighted hem
    a little proud; fabric FAB-CURTAIN at true scale (spec: fullness 2, drop to 10 mm above the floor)"""
    a = it["asset"]; fab = mats_for(it, "fabric", "fabric") or LINEN; pole = mats_for(it, "pole") or "METAL-BLACK"
    pw = a.get("pole_width_mm", W * 1000) / 1000; stack = a.get("stacked_each_side_mm", 300) / 1000
    r = 0.0125
    mb.cyl(-pw / 2 - 0.02, 0.0, H - r, H + r, r, pole, 12, axis="x") if False else None
    # pole as a round bar along X: built from a cylinder along x
    seg = 14; V = []
    for k_, x in enumerate((-pw / 2 - 0.03, pw / 2 + 0.03)):
        for i in range(seg):
            ang = 2 * math.pi * i / seg; V.append((x, r * math.cos(ang), H + r * math.sin(ang)))
    Fs = [tuple(reversed(range(seg))), tuple(range(seg, 2 * seg))] + [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)]
    Fs = [Fs[0], Fs[1]] + [tuple(reversed(f)) for f in Fs[2:]]
    mb.pieces.append((V, Fs, pole, 0.0))
    for sx in (-1, 1):
        mb.cyl(sx * (pw / 2 + 0.05), 0.0, H - 0.022, H + 0.022, 0.022, pole, 14, axis="x") if False else None
        # finial: a short fat cylinder along x
        V = []
        for x in (sx * (pw / 2 + 0.03), sx * (pw / 2 + 0.075)):
            for i in range(seg):
                ang = 2 * math.pi * i / seg; V.append((x, 0.024 * math.cos(ang), H + 0.024 * math.sin(ang)))
        Fs = [tuple(range(seg)), tuple(reversed(range(seg, 2 * seg)))] + [(i, seg + i, seg + (i + 1) % seg, (i + 1) % seg) for i in range(seg)]
        if sx < 0: Fs = [tuple(reversed(f)) for f in Fs]
        mb.pieces.append((V, Fs, pole, 0.0))
        for bx in (sx * (pw / 2 - 0.12),):                       # bracket to the wall (behind, -Y)
            mb.box(bx - 0.012, bx + 0.012, -0.09, -0.002, H - 0.012, H + 0.012, pole, 0.003)
    drop = H - 0.03 - 0.01                                        # rings below the pole, hem 10 mm off the floor
    for sx in (-1, 1):
        x0 = sx * pw / 2 - (stack if sx > 0 else 0); x1 = x0 + stack
        nfold = max(4, int(stack / 0.05))                         # stacked fabric: a fold every ~50 mm
        ni, nj = 16, nfold * 4 + 1
        P = []
        for i in range(ni):
            t = i / (ni - 1); z = H - 0.03 - t * drop                # t 0 heading .. 1 hem
            row = []
            for j in range(nj):
                u = j / (nj - 1); x = x0 + u * (x1 - x0)
                ph = 2 * math.pi * u * nfold
                amp = 0.028 + 0.022 * t                           # folds deepen towards the hem
                if t < 0.06: amp *= 0.55 + 0.45 * (1 - abs(math.cos(ph)))     # pinched at the heading
                y = 0.06 + amp * math.sin(ph) + (0.012 * t * t)        # the hem sits a little proud
                row.append((x, y, z))
            P.append(row)
        _solid_from_grid(P, 0.004, fab, mb)
        mb.box(x0 + 0.004, x1 - 0.004, 0.035, 0.085, H - 0.04, H - 0.028, fab, 0.004)    # heading tape band behind the pleats


def k_rug2(mb, W, D, H, it, mats_for, QUESTIONS):
    """rug with a soft bullnose edge and rounded corners (never a sharp slab); a woven border where the spec says
    ('cream with fine charcoal border': border in the spec's charcoal #3A3A3C, errata 3)"""
    m = mats_for(it, "all")
    pile = it["asset"].get("pile", "")
    if m is None:
        if "waffle" in pile and "cotton" in pile: m = "BED-LINEN"
        else: QUESTIONS.append(dict(id=it["id"], what="rug with no finish or colour", evidence=pile)); return False
    border = "border" in pile and "charcoal" in pile
    r = min(0.03, W / 6, D / 6); seg = 5
    def rr(w, d, rad):
        pts = []
        for cx, cy, a0 in ((w / 2 - rad, d / 2 - rad, 0), (-w / 2 + rad, d / 2 - rad, 90), (-w / 2 + rad, -d / 2 + rad, 180), (w / 2 - rad, -d / 2 + rad, 270)):
            for k in range(seg + 1):
                a_ = math.radians(a0 + 90 * k / seg); pts.append((cx + rad * math.cos(a_), cy + rad * math.sin(a_)))
        return pts
    # body: a stack of 3 rings (bullnose): bottom full size, middle +0, top inset by H/2
    rings = [(0.0, rr(W - H * 0.6, D - H * 0.6, r)), (H * 0.45, rr(W, D, r)), (H, rr(W - H * 0.9, D - H * 0.9, r))]
    n = len(rings[0][1]); V = []
    for z, pts in rings: V.extend((x, y, z) for x, y in pts)
    Fs = [tuple(reversed(range(n))), tuple(range(2 * n, 3 * n))]
    for k in range(2):
        for i in range(n): Fs.append((k * n + i, k * n + (i + 1) % n, (k + 1) * n + (i + 1) % n, (k + 1) * n + i))
    mb.pieces.append((V, Fs, m, 0.0))
    if border:
        b = 0.045; w_ = 0.012                                     # a fine 12 mm charcoal line 45 mm in from the edge
        for (x0, x1, y0, y1) in ((-W / 2 + b, W / 2 - b, D / 2 - b - w_, D / 2 - b), (-W / 2 + b, W / 2 - b, -D / 2 + b, -D / 2 + b + w_),
                                 (-W / 2 + b, -W / 2 + b + w_, -D / 2 + b, D / 2 - b), (W / 2 - b - w_, W / 2 - b, -D / 2 + b, D / 2 - b)):
            mb.box(x0, x1, y0, y1, H - 0.0005, H + 0.0006, "c:#3A3A3C:0.9:0", 0.0)


def k_roman_blind2(mb, W, D, H, it, mats_for, LINEN="FAB-CURTAIN"):
    """roman blind inside the recess: a head rail and 5 soft folds, each a gently curved, slightly sagging pleat"""
    m = mats_for(it, "all", "fabric") or LINEN; n = int(it["asset"].get("folds", 5))
    mb.box(-W / 2, W / 2, -D / 2, D / 2 - 0.02, H - 0.04, H, m, 0.006)
    fh = (H - 0.05) / n; ni, nj = 7 * n + 1, 25
    stack = min(0.24, 0.045 * n)          # OPEN (Jack, walk 2, F69): raised, the fabric stacked in tight folds under the head rail; the window is clear below it
    P = []
    for i in range(ni):
        t = i / (ni - 1); z = (H - 0.05) - stack * t
        ph = (t * n) % 1.0
        row = []
        for j in range(nj):
            u = j / (nj - 1); x = -W / 2 + 0.004 + u * (W - 0.008)
            bulge = 0.030 * math.sin(math.pi * ph) * (0.75 + 0.25 * math.sin(math.pi * u))
            sag = 0.006 * math.sin(math.pi * u) * math.sin(math.pi * ph)
            row.append((x, 0.0 + bulge, z - sag))
        P.append(row)
    _solid_from_grid(P, 0.003, m, mb)


def k_table_low2(mb, W, D, H, it, mats_for):
    """rattan coffee table: a rattan-wrapped frame (rounded rails and legs, woven shelf) under a 6 mm clear glass top"""
    fr = mats_for(it, "frame") or "RATTAN"
    t = 0.035
    for sx in (-1, 1):
        for sy in (-1, 1): mb.box(sx * (W / 2 - t) - t / 2, sx * (W / 2 - t) + t / 2, sy * (D / 2 - t) - t / 2, sy * (D / 2 - t) + t / 2, 0, H - 0.006, fr, 0.012)
    for z0 in (H - 0.006 - 0.04, 0.10):
        mb.box(-W / 2 + t / 2, W / 2 - t / 2, D / 2 - t, D / 2 - t / 2 + 0.0, z0, z0 + 0.035, fr, 0.01)
        mb.box(-W / 2 + t / 2, W / 2 - t / 2, -D / 2 + t / 2, -D / 2 + t, z0, z0 + 0.035, fr, 0.01)
        mb.box(-W / 2 + t / 2, -W / 2 + t, -D / 2 + t, D / 2 - t, z0, z0 + 0.035, fr, 0.01)
        mb.box(W / 2 - t, W / 2 - t / 2, -D / 2 + t, D / 2 - t, z0, z0 + 0.035, fr, 0.01)
    mb.box(-W / 2 + t, W / 2 - t, -D / 2 + t, D / 2 - t, 0.115, 0.125, fr)                # woven shelf
    mb.box(-W / 2, W / 2, -D / 2, D / 2, H - 0.006, H, "GLASS-CLEAR", 0.002)


# ------------------------------------------------------------------------------------------------ validator
def bvh_of(ob):
    me = ob.data; M = ob.matrix_world
    return BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])


def support_gap(ob, tree_all, own_names, max_d=0.5):
    """gap (m) from the item's lowest point down to the first surface that is not its own (rays start 5 mm above its
    lowest point at its lowest vertices and step through its own faces); the smallest gap counts"""
    M = ob.matrix_world; wv = [M @ v.co for v in ob.data.vertices]
    if not wv: return None
    z0 = min(v.z for v in wv)
    own = bvh_of(ob)
    low = [v for v in wv if v.z < z0 + 0.01]
    pts = [(sum(v.x for v in low) / len(low), sum(v.y for v in low) / len(low))] + [(v.x, v.y) for v in low[:: max(1, len(low) // 6)]]
    DN = Vector((0, 0, -1)); gaps = []
    for (px, py) in pts:
        q = Vector((px, py, z0 + 0.005)); g = max_d
        for _ in range(6):
            h = tree_all.ray_cast(q, DN, max_d)
            if h[0] is None: break
            ho = own.ray_cast(q, DN, max_d)
            if ho[0] is not None and abs(ho[3] - h[3]) < 1e-4:
                q = h[0] + DN * 0.0002; continue
            g = max(0.0, z0 - h[0].z); break
        gaps.append(g)
    return min(gaps) if gaps else None


# ------------------------------------------------------------------------------------------------ library items for spec ids
# per asset: which way its front faces in its own file, stretch zones per axis (keep_lo, keep_hi fractions kept at size),
# and seat modules (count in the base model)
ASSET_CFG = {
    "BK-SOFA-BURRARD": dict(front="-Y", zx=(0.12, 0.12), zy=(0.3, 0.3), zz=(0.45, 0.12), modules=3),
    "BK-RATTAN-SOFA": dict(front="-Y", zx=(0.12, 0.12), zy=(0.3, 0.3), zz=(0.4, 0.15), modules=3),
    "BK-ARMCHAIR-ROUND": dict(front="-Y", zx=(0.25, 0.25), zy=(0.25, 0.25), zz=(0.4, 0.25)),
    "BK-ARMCHAIR-ALT": dict(front="-Y"),
    "BK-RATTAN-CHAIR": dict(front="-Y", cap=9000),
    "BK-BED-ULTIMA": dict(front="-Y", zx=(0.18, 0.18), zy=(0.2, 0.3), zz=(0.55, 0.08)),
    "BK-BED-SINGLE-OAK": dict(front="-Y", zx=(0.15, 0.15), zy=(0.15, 0.15), zz=(0.4, 0.15)),
    "BK-CUSHION": dict(front="-Y", zx=(0.3, 0.3), zy=(0.3, 0.3), zz=(0.3, 0.3)),
    "BK-BEDSIDE-ARCH": dict(front="-Y", zx=(0.25, 0.25), zy=(0.25, 0.25), zz=(0.3, 0.3)),
    "BK-DESK-OAK": dict(front="-Y", zx=(0.15, 0.15), zy=(0.2, 0.2), zz=(0.3, 0.3)),
    "BK-WC-CC": dict(front="-Y", zx=(0.3, 0.3), zy=(0.3, 0.3), zz=(0.3, 0.3)),
    "BK-WC-WALL": dict(front="+Y", zx=(0.3, 0.3), zy=(0.3, 0.3), zz=(0.3, 0.3)),
}
UNIFORM = {"BK-KETTLE", "BK-TOASTER", "BK-COFFEE", "BK-OILVINEGAR", "BK-SOAP", "BK-DIFFUSER", "BK-CANDLE-JAR", "BK-CANDLES-PILLAR",
           "BK-BOOKS-STACK", "BK-KEYS", "BK-DISH", "BK-TOWEL-FOLDED"}


def _remap2(c, lo, hi, tgt, klo, khi):
    L = hi - lo
    if L < 1e-6: return c - lo - L / 2
    e0, e1 = klo * L, khi * L
    ms, md = L - e0 - e1, tgt - e0 - e1
    if md <= 0.15 * ms: return -tgt / 2 + (c - lo) * tgt / L
    if c <= lo + e0: return -tgt / 2 + (c - lo)
    if c >= hi - e1: return tgt / 2 - (hi - c)
    return -tgt / 2 + e0 + (c - lo - e0) * md / ms


def adapt_cfg(me_src, W, D, H, cfg, n_dst=None):
    me = adapt(me_src, None, 1, 1, 1, modules=(cfg["modules"], n_dst) if cfg.get("modules") and n_dst else None) if cfg.get("modules") and n_dst and n_dst < cfg["modules"] else me_src.copy()
    xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; zs = [v.co.z for v in me.vertices]
    lx, hx, ly, hy, lz, hz = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
    zx, zy, zz = cfg.get("zx", (0.22, 0.22)), cfg.get("zy", (0.22, 0.22)), cfg.get("zz", (0.22, 0.22))
    for v in me.vertices:
        v.co = Vector((_remap2(v.co.x, lx, hx, W, *zx), _remap2(v.co.y, ly, hy, D, *zy), _remap2(v.co.z, lz, hz, H, *zz) + H / 2))
    me.update()
    return me


def _adapt_fix(me_src, W, D, H, cfg, n_dst):
    """adapt() above resizes as a side effect when removing modules; this wrapper keeps the module step size-neutral"""
    if cfg.get("modules") and n_dst and n_dst < cfg["modules"]:
        xs = [v.co.x for v in me_src.vertices]; ys = [v.co.y for v in me_src.vertices]; zs = [v.co.z for v in me_src.vertices]
        dims = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
        me1 = adapt_modules(me_src, cfg["modules"], n_dst)
    else: me1 = me_src.copy()
    me2 = adapt_cfg(me1, W, D, H, dict(cfg, modules=None))
    if me1 is not me_src: bpy.data.meshes.remove(me1)
    return me2


def adapt_modules(me_src, n_src, n_dst):
    me = me_src.copy(); bm = bmesh.new(); bm.from_mesh(me)
    xs = [v.co.x for v in bm.verts]; x0, x1 = min(xs), max(xs)
    arm = 0.075 * (x1 - x0)
    pitch = (x1 - x0 - 2 * arm) / n_src; cut = pitch * (n_src - n_dst)
    cx0 = (x0 + x1) / 2
    bm.verts.ensure_lookup_table(); seen = set(); dele = []
    for v in bm.verts:
        if v.index in seen: continue
        stack = [v]; isl = []
        while stack:
            q = stack.pop()
            if q.index in seen: continue
            seen.add(q.index); isl.append(q)
            for ed in q.link_edges:
                o = ed.other_vert(q)
                if o.index not in seen: stack.append(o)
        cx = sum(q.co.x for q in isl) / len(isl) - cx0; w = max(q.co.x for q in isl) - min(q.co.x for q in isl)
        if abs(cx) < cut / 2 and w < pitch * 1.25: dele.extend(isl)
    if dele: bmesh.ops.delete(bm, geom=list(set(dele)), context="VERTS")
    for v in bm.verts:
        dx = v.co.x - cx0
        if dx > cut / 2: v.co.x -= cut / 2
        elif dx < -cut / 2: v.co.x += cut / 2
        else: v.co.x = cx0
    bm.to_mesh(me); bm.free(); return me


def build_library_item(it, lib_key, soft_key, W, D, H, fin, mats_for, log):
    """the spec item from the studio library: a BlendKit base adapted to the spec box and recoloured, and/or a cloth-sim
    soft item (towels, throws, bedding). Returns the object (local frame of hb_items: X width, +Y front, base at 0) or None."""
    parts = []
    if lib_key:
        cfg = ASSET_CFG.get(lib_key, dict(front="-Y"))
        pr = proto(lib_key, log, front=cfg.get("front", "-Y"), cap=cfg.get("cap"))
        if pr is None: return None
        me0, dims, _ = pr
        if lib_key in UNIFORM:
            me, s_ = uniform_fit(me0, dims, W, D, H)
        else:
            n_dst = int(it["asset"].get("seats", 0)) or None
            me = _adapt_fix(me0, W, D, H, cfg, n_dst)
        sw = recolour(me, lib_key, it, fin, mats_for)
        NOTES.append(f"{it['id']}: {lib_key} {'fitted' if lib_key in UNIFORM else 'adapted (stretch zones)'} to {W * 1000:.0f}x{D * 1000:.0f}x{H * 1000:.0f}"
                     + (f"; spec finishes {sw}" if sw else ""))
        parts.append(me)
    if soft_key:
        pr = proto(soft_key, log, front="+Y", cap=7000)
        if pr is None:
            if not parts: return None
        else:
            me0, dims, _ = pr
            me = me0.copy()          # cloth results are made at the spec size in the hb_items local frame already
            for i, m in enumerate(me.materials):
                nm = m.name if m else ""
                mm = re.match(r"SPECFIN:(.+?)(\.\d{3})?$", nm)
                if mm and mm.group(1) in fin.F: me.materials[i] = fin.get(mm.group(1))
            if lib_key and it["id"] in ("B3B-BED",):
                pass
            parts.append(me)
            NOTES.append(f"{it['id']}: soft items from cloth simulation ({soft_key})")
    if not parts: return None
    if len(parts) == 1: me = parts[0]
    else:
        bm = bmesh.new(); mats = []
        for pme in parts:
            idx = []
            for m in pme.materials:
                if m not in mats: mats.append(m)
                idx.append(mats.index(m))
            tmp = bmesh.new(); tmp.from_mesh(pme)
            for f in tmp.faces: f.material_index = idx[f.material_index] if f.material_index < len(idx) else 0
            tm = bpy.data.meshes.new("_p"); tmp.to_mesh(tm); tmp.free(); bm.from_mesh(tm); bpy.data.meshes.remove(tm)
        me = bpy.data.meshes.new(f"SPEC-{it['id']}"); bm.to_mesh(me); bm.free()
        for m in mats: me.materials.append(m)
    me.name = f"SPEC-{it['id']}"
    return bpy.data.objects.new(f"SPEC-{it['id']}", me)


# ------------------------------------------------------------------------------------------------ the lived-in layer (addendum 2)
FRUIT_LAYOUT = {   # fruit in a 313 mm bowl: (polyhaven id, dx, dy, dz above the bowl base, yaw)
    "before": [("food_pears_asian_01", -0.04, 0.01, 0.022, 0), ("food_apple_01", 0.065, -0.03, 0.03, 40), ("food_apple_01", 0.055, 0.055, 0.03, 110),
               ("lemon", -0.02, -0.075, 0.03, 70), ("food_lime_01", 0.0, 0.075, 0.035, 20)],
    "after": [("bananas", 0.0, 0.0, 0.05, 15), ("food_apple_01", 0.07, -0.04, 0.03, 30), ("food_apple_01", -0.07, 0.05, 0.03, 200),
              ("food_pears_asian_01", -0.035, -0.045, 0.024, 90), ("lemon", 0.06, 0.06, 0.035, 0)],
}


def _lived_props(ad, N):
    return dict(element=f"SPEC-{ad['id']}", spec_id=ad["id"], spec_kind="lived_in", stage_in=N, seq=0.97 if N > 1 else 0.0,
                category="finish" if N > 1 else "existing", group="fitting", storey="first" if ad["position_m"][1] > 2.0 else "ground",
                label=f"{ad['type']} ({ad['id']}; addendum 2 lived-in layer)", plain_label=ad["type"][:80], drawing="spec_v1 addendum 2 (Jack, 1 Nov 2026)",
                conf="assumed", provenance="typical", collide=False, furnishing=True, lived_in=True)


def build_addendum(spec_path, vkey, N, coll, fin, items_out, house_objs, log, ph):
    A, ap = load_addendum(spec_path)
    if A is None: return []
    out = []
    # surfaces to stand on: the house (floors, worktops, cisterns, window boards) + the items just built
    tri_v, tri_t = [], []
    def add_tree(ob):
        if ob.type != "MESH": return
        b = len(tri_v); M = ob.matrix_world
        tri_v.extend(M @ v.co for v in ob.data.vertices); tri_t.extend(tuple(b + i for i in p.vertices) for p in ob.data.polygons)
    for ob, p in house_objs:
        if p.get("context") or (p["props"].get("stage_out") or 99) <= N: continue
        add_tree(ob)
    for ob, p in items_out: add_tree(ob)
    T = BVHTree.FromPolygons(tri_v, tri_t)
    for ad in A["items"]:
        if vkey not in ad.get("versions", []): continue
        W, D, H = [x / 1000 for x in (ad.get("size_mm") or [100, 100, 100])]
        x, y, z = ad["position_m"]
        asset = ad["asset"]
        meshes = []                                   # (mesh, local offset (x, y, z), yaw)
        if asset.startswith("BK-"):
            pr = proto(asset, log, front="-Y")
            if pr is None: log("addendum: missing", asset); continue
            me, s_ = uniform_fit(pr[0], pr[1], W, D, H)
            recolour(me, asset, dict(materials={}, asset={}), fin, lambda it_, part, *f: None)
            meshes.append((me, (0, 0, 0), 0))
        elif "food_" in asset or "bananas" in asset:
            for (aid, dx, dy, dz, yw) in FRUIT_LAYOUT[vkey]:
                pr = ph(aid)
                if pr is None: continue
                me_, dims_ = pr
                m2 = me_.copy()
                if aid == "bananas":                  # the 5-banana layout: keep a bunch of 2 (the left 40 %)
                    bm = bmesh.new(); bm.from_mesh(m2); xs = [v.co.x for v in bm.verts]; cut = min(xs) + 0.4 * (max(xs) - min(xs))
                    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.x > cut], context="VERTS")
                    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]
                    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, 0)))
                    bm.to_mesh(m2); bm.free()
                meshes.append((m2, (dx, dy, dz), yw))
        elif asset.startswith("polyhaven:book_encyclopedia_set_01"):
            pr = ph("book_encyclopedia_set_01")
            if pr is None: continue
            me, s_ = uniform_fit(pr[0], pr[1], W, D, H); meshes.append((me, (0, 0, 0), 0))
        else:
            log("addendum: unknown asset", asset); continue
        # one object per lived-in item
        bm = bmesh.new(); mats = []
        for me_, (dx, dy, dz), yw in meshes:
            idx = []
            for m in me_.materials:
                if m not in mats: mats.append(m)
                idx.append(mats.index(m))
            tmp = bmesh.new(); tmp.from_mesh(me_)
            tmp.transform(Matrix.Translation(Vector((dx, dy, dz))) @ Matrix.Rotation(math.radians(yw), 4, "Z"))
            for f in tmp.faces: f.material_index = idx[f.material_index] if f.material_index < len(idx) else 0
            tm = bpy.data.meshes.new("_a"); tmp.to_mesh(tm); tmp.free(); bm.from_mesh(tm); bpy.data.meshes.remove(tm)
        me = bpy.data.meshes.new(f"SPEC-{ad['id']}"); bm.to_mesh(me); bm.free()
        for m in mats: me.materials.append(m)
        ob = bpy.data.objects.new(f"SPEC-{ad['id']}", me)
        # snap onto the host top: ray down from 0.35 m above the planned point; spiral to a clear spot if it overlaps
        best = None
        tries = [(0.0, 0.0)] + [(r_ * math.cos(a_), r_ * math.sin(a_)) for r_ in (0.03, 0.06, 0.09, 0.12) for a_ in [k * math.pi / 4 for k in range(8)]]
        for (ox, oz) in tries:
            q = Vector((x + ox, -(z + oz), y + 0.35))
            h = T.ray_cast(q, Vector((0, 0, -1)), 0.8)
            if h[0] is None: continue
            ob.matrix_world = Matrix.Translation(Vector((x + ox, -(z + oz), h[0].z + 0.0005))) @ Matrix.Rotation(math.radians(ad.get("yaw_deg", 0)), 4, "Z")
            bpy.context.view_layer.update() if False else None
            tb = bvh_of(ob)
            pairs = tb.overlap(T)
            zb = h[0].z
            deep = 0
            if pairs:
                me_w = [ob.matrix_world @ v.co for v in ob.data.vertices]
                for (ia, ib) in pairs[:400]:
                    pa = ob.data.polygons[ia]
                    cz = sum(me_w[vi].z for vi in pa.vertices) / len(pa.vertices)
                    if cz > zb + 0.008: deep += 1
            if best is None or deep < best[0]: best = (deep, ox, oz, zb)
            if deep == 0: break
        if best is None:
            log("addendum: no surface under", ad["id"]); continue
        deep, ox, oz, zb = best
        ob.matrix_world = Matrix.Translation(Vector((x + ox, -(z + oz), zb + 0.0005))) @ Matrix.Rotation(math.radians(ad.get("yaw_deg", 0)), 4, "Z")
        if "fruit" in ad["type"]:                            # the fruit settles: lowered until the lowest one touches the bowl
            g_ = support_gap(ob, T, None, 0.1)
            if g_ and 0.001 < g_ < 0.08:
                ob.matrix_world = Matrix.Translation(Vector((0, 0, -g_ + 0.0005))) @ ob.matrix_world; zb -= g_ - 0.0005
        ad["position_m"] = [round(x + ox, 3), round(zb + 0.0005, 3), round(z + oz, 3)]
        ad["validator"] = dict(ok=deep == 0, gap_mm=0.5, overlap_faces=deep, moved_mm=round(1000 * math.hypot(ox, oz)), version_checked=vkey)
        ad["status"] = "placed by the build (2 Nov 2026)"
        props = _lived_props(ad, N)
        for k_, v_ in props.items(): ob[k_] = v_
        coll.objects.link(ob)
        out.append((ob, dict(props=props, spec=True, atom=dict(id=props["element"], kind="spec", meta=props, provenance="typical"))))
        REPORT["lived_in"].append(dict(id=ad["id"], version=vkey, ok=deep == 0, moved_mm=ad["validator"]["moved_mm"]))
    json.dump(A, open(ap, "w"), indent=1)
    log(f"lived-in layer ({vkey}): {len(out)} items placed, {sum(1 for o in out if o[0].get('spec_id') and True)} tagged; "
        f"{sum(1 for r in REPORT['lived_in'] if r['version'] == vkey and not r['ok'])} failing the validator")
    return out


def validate(vkey, items_out, house_objs, log):
    """every loose item: support gap (<= 10 mm) and no passing into the shell (wall, floor, ceiling) beyond soft contact"""
    tri_v, tri_t, tri_own = [], [], []
    for ob, p in house_objs:
        if ob.type != "MESH" or p.get("context") or (p["props"].get("stage_out") or 99) <= 99 and False: continue
        if (p["props"].get("stage_out") or 99) < 99 and p["props"].get("stage_out") is not None: continue
        b = len(tri_v); M = ob.matrix_world
        tri_v.extend(M @ v.co for v in ob.data.vertices)
        for pl in ob.data.polygons: tri_t.append(tuple(b + i for i in pl.vertices)); tri_own.append(ob.name)
    shell = BVHTree.FromPolygons(tri_v, tri_t)
    allv, allt = list(tri_v), list(tri_t)
    for ob, p in items_out:
        if ob.type != "MESH": continue
        b = len(allv); M = ob.matrix_world
        allv.extend(M @ v.co for v in ob.data.vertices); allt.extend(tuple(b + i for i in pl.vertices) for pl in ob.data.polygons)
    T_all = BVHTree.FromPolygons(allv, allt)
    bad = []
    for ob, p in items_out:
        if ob.type != "MESH" or not ob.get("furnishing"): continue
        if ob.get("spec_kind") in HUNG and ob.get("spec_kind") not in ("rug", "throw_drape"): continue      # hung on a wall / rail / ceiling
        tb = bvh_of(ob)
        M = ob.matrix_world; wv = [M @ v.co for v in ob.data.vertices]
        if not wv: continue
        zb = min(v.z for v in wv)
        pairs = tb.overlap(shell)
        deep = 0; who = {}
        for (ia, ib) in pairs[:3000]:
            pa = ob.data.polygons[ia]
            if min(wv[vi].z for vi in pa.vertices) > zb + 0.01:          # wholly above its own footing: a real pass-through
                deep += 1; who[tri_own[ib]] = who.get(tri_own[ib], 0) + 1
        soft_ = str(ob.get("asset_library", "")).startswith("soft:") or bool(ob.get("soft_dressed"))
        gap = None if soft_ else support_gap(ob, T_all, None)          # cloth rests by simulation, hung items hang
        rec = dict(id=ob.get("spec_id"), version=vkey, shell_overlap_faces=deep, into=sorted(who, key=lambda k: -who[k])[:4],
                   support_gap_mm=None if gap is None else round(gap * 1000, 1))
        REPORT["validator"].append(rec)
        if deep > 6: bad.append(rec)
    floaty = [r for r in REPORT["validator"] if r["version"] == vkey and r.get("support_gap_mm") is not None and r["support_gap_mm"] > 10]
    log(f"furnishing validator ({vkey}): {len([r for r in REPORT['validator'] if r['version'] == vkey])} loose items checked, {len(bad)} pass into the shell: "
        f"{[b['id'] for b in bad][:12]}; {len(floaty)} float > 10 mm: {[r['id'] for r in floaty][:12]}")
    if OUT_DIR:
        json.dump(dict(version=vkey, validator=[r for r in REPORT["validator"] if r["version"] == vkey], lived_in=[r for r in REPORT["lived_in"] if r["version"] == vkey],
                       notes=NOTES), open(os.path.join(OUT_DIR, f"{'as_built_now' if vkey == 'before' else 'approved_2b'}_furnish.json"), "w"), indent=1)
    return bad


# ------------------------------------------------------------------------------------------------ sanitaryware (G5c: no placeholder blocks)
CHROME = "c:#C9CBCE:0.12:1.0"          # the spec's words 'chrome' (polished): a product material, not a chosen colour


def _basin_bowl(mb, W, D, top, thick, key, rim=0.035, depth=0.11, r=0.035, nx=30, ny=24):
    """a ceramic basin: rounded-rectangle body `thick` deep whose top dishes into an elliptic bowl (closed solid)"""
    a_, b_ = W / 2 - rim, D / 2 - rim
    def z_top(x, y):
        u, v = x / a_, (y + 0.01) / b_
        q = 1 - u * u - v * v
        if q <= 0: return top
        f = min(1.0, q / 0.45); s_ = f * f * (3 - 2 * f)        # smooth (C1) from the rim down into the bowl
        return top - depth * s_ * (0.7 + 0.3 * min(1.0, q))
    xs = [-W / 2 + W * i / nx for i in range(nx + 1)]; ys = [-D / 2 + D * j / ny for j in range(ny + 1)]
    def corner(x, y):                                       # pull the grid's corners in to round them
        cx, cy = W / 2 - r, D / 2 - r
        dx, dy = abs(x) - cx, abs(y) - cy
        if dx > 0 and dy > 0:
            L = math.hypot(dx, dy); s = r / L
            return (math.copysign(cx + dx * s, x), math.copysign(cy + dy * s, y))
        return (x, y)
    V, F = [], []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            x2, y2 = corner(x, y); V.append((x2, y2, z_top(x2, y2)))
    n = len(V)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            x2, y2 = corner(x, y); V.append((x2, y2, top - thick))
    def ix(i, j, b=0): return b * n + j * (nx + 1) + i
    for j in range(ny):
        for i in range(nx):
            F.append((ix(i, j), ix(i + 1, j), ix(i + 1, j + 1), ix(i, j + 1)))
            F.append((ix(i, j + 1, 1), ix(i + 1, j + 1, 1), ix(i + 1, j, 1), ix(i, j, 1)))
    for i in range(nx):
        F.append((ix(i, 0, 1), ix(i + 1, 0, 1), ix(i + 1, 0), ix(i, 0))); F.append((ix(i, ny), ix(i + 1, ny), ix(i + 1, ny, 1), ix(i, ny, 1)))
    for j in range(ny):
        F.append((ix(0, j), ix(0, j + 1), ix(0, j + 1, 1), ix(0, j, 1))); F.append((ix(nx, j, 1), ix(nx, j + 1, 1), ix(nx, j + 1), ix(nx, j)))
    mb.pieces.append((V, F, key, 0.0))
    mb.cyl(0, 0.01, top - depth - 0.002, top - depth + 0.002, 0.02, CHROME, 16)       # waste


def _tap(mb, x, y, z, key, kind="monobloc"):
    if kind == "pillar":
        for sx in (-1, 1):
            mb.cyl(x + sx * 0.06, y, z, z + 0.07, 0.014, key, 14); mb.cyl(x + sx * 0.06, y, z + 0.07, z + 0.085, 0.022, key, 14)
        return
    mb.cyl(x, y, z, z + 0.012, 0.026, key, 18)
    mb.cyl(x, y, z + 0.012, z + 0.16, 0.016, key, 16)
    if kind == "swan":
        V, F = [], []
        seg = 10; pts = [(x, y + 0.0, z + 0.16 + 0.07 * math.sin(math.pi * k / 8)) for k in range(1)]
    # spout forward (+Y) from the top, and a lever
    mb.pieces.append(HI_leg((x, y, z + 0.15), (x, y + 0.11, z + 0.15), 0.011, key))
    mb.pieces.append(HI_leg((x, y + 0.11, z + 0.15), (x, y + 0.12, z + 0.125), 0.010, key))
    mb.pieces.append(HI_leg((x, y - 0.005, z + 0.135), (x - 0.06, y - 0.02, z + 0.14), 0.006, key))


def HI_leg(a, b, r, key, seg=10):
    A, B = Vector(a), Vector(b); d = (B - A).normalized()
    u = d.orthogonal().normalized(); v = d.cross(u)
    V = [tuple(P + (u * math.cos(2 * math.pi * i / seg) + v * math.sin(2 * math.pi * i / seg)) * r) for P in (A, B) for i in range(seg)]
    F = [tuple(reversed(range(seg))), tuple(range(seg, 2 * seg))] + [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)]
    return (V, F, key, 0.0)


def k_sanitary2(mb, W, D, H, it, mats_for, shaker):
    """basins to the spec's words (asset.parametric): semi-pedestal, compact vanity (oak front), wall-hung vanity, small
    wall-hung basin; tap per the words (chrome pillar, brushed brass monobloc/swan neck). Local frame: front +Y, back -Y at the wall."""
    words = (it["asset"].get("parametric", "") + " " + it["type"]).lower()
    san = mats_for(it, "basin") or mats_for(it, "all") or "SAN-WHITE"
    if san not in ("SAN-WHITE",): san = "SAN-WHITE"
    tapk = "BRASS" if "brass" in words else CHROME
    top = H
    if "vanity" in words:
        oak = mats_for(it, "vanity") or "WOOD-OAK-FURN"
        wall_hung = "wall-hung" in words or "wall hung" in words
        z0 = 0.30 if wall_hung else 0.0
        mb.box(-W / 2 + 0.005, W / 2 - 0.005, -D / 2, D / 2 - 0.02, z0 + (0.0 if wall_hung else 0.08), top - 0.14, oak, 0.004)
        if not wall_hung: mb.box(-W / 2 + 0.03, W / 2 - 0.03, -D / 2 + 0.01, D / 2 - 0.06, 0.0, 0.08, oak)
        shaker(mb, -W / 2 + 0.008, W / 2 - 0.008, D / 2, z0 + (0.0 if wall_hung else 0.085) + 0.004, top - 0.145, oak, frame=0.045)
        _basin_bowl(mb, W, D, top, 0.14, san, depth=0.10)
    else:
        bw, bd = W, D
        _basin_bowl(mb, bw, bd, top, 0.15, san, depth=0.11 if W > 0.3 else 0.08)
        if "semi-pedestal" in words or "semi pedestal" in words:
            mb.box(-0.09, 0.09, -D / 2, -D / 2 + 0.2, top - 0.5, top - 0.15, san, 0.05)                # the shroud hiding the trap
        else:
            mb.cyl(0, -D / 2 + 0.08, top - 0.35, top - 0.15, 0.022, CHROME, 14)                       # chrome bottle trap
    _tap(mb, 0, -D / 2 + 0.055, top, tapk, "pillar" if "pillar" in words else "monobloc")
    NOTES.append(f"{it['id']}: studio-made basin from the spec's words ({it['asset'].get('parametric', '')[:60]})")


HUNG = {"framed_print", "mirror_round", "mirror_rect", "curtain_pair", "roman_blind", "towels", "towel_ring", "tea_towel", "throw_drape", "rug",
        "hanging_picture_frame_02", "hanging_picture_frame_03", "pendant_drum", "flush_disc", "linear_pendant", "downlight_set"}


def snap_loose(items_out, house_objs, N, log, spec_items):
    """the loose layer sits where a real one would (the written description governs over a spec coordinate, row 188):
    1. furniture and plants stand clear of the wall linings and skirting they were drawn into (pushed straight out along
       their front, 5 mm steps, up to 45 mm);
    2. decor, plants and cushions stand ON their surface: lowered or lifted onto the first surface under them within 60 mm
       (searching up to 150 mm sideways when nothing is under their centre, e.g. a plant drawn just off a window board);
    3. decor and plants never pass into a wall or a chimney breast: nudged clear (8 directions, up to 300 mm)."""
    pos_of = {i["id"]: i for i in spec_items}
    def tree_of(pairs, vertical_only=False):
        V, T = [], []
        for ob, p in pairs:
            if ob.type != "MESH": continue
            b = len(V); M = ob.matrix_world; R = M.to_3x3()
            V.extend(M @ v.co for v in ob.data.vertices)
            for pl in ob.data.polygons:
                if vertical_only and abs((R @ pl.normal).normalized().z) > 0.4: continue
                T.append(tuple(b + i for i in pl.vertices))
        return BVHTree.FromPolygons(V, T) if T else None
    shell = [(ob, p) for ob, p in house_objs if not p.get("context") and (p["props"].get("stage_out") or 99) > N
             and not (ob.name.startswith(("SPEC-", "JN-")) and not ob.name.startswith(("SPEC-FLR", "SPEC-SKIRT")))]
    WALLS = tree_of(shell, vertical_only=True)
    DN = Vector((0, 0, -1)); moved = []
    def deep_hits(o_, tree_, margin=1.0, lift=0.01):
        if tree_ is None: return 0
        wv = [o_.matrix_world @ v.co for v in o_.data.vertices]
        if not wv: return 0
        zb = min(v.z for v in wv)
        if margin != 1.0:
            cx_ = sum(v.x for v in wv) / len(wv); cy_ = sum(v.y for v in wv) / len(wv)
            wv = [Vector((cx_ + (v.x - cx_) * margin, cy_ + (v.y - cy_) * margin, v.z)) for v in wv]
        t_ = BVHTree.FromPolygons(wv, [tuple(pl.vertices) for pl in o_.data.polygons])
        return sum(1 for (ia, ib) in t_.overlap(tree_)[:3000] if min(wv[vi].z for vi in o_.data.polygons[ia].vertices) > zb + lift)
    # 1. push furniture and plants out of the walls along their front
    for ob, p in items_out:
        it = pos_of.get(ob.get("spec_id"))
        if it is None or ob.type != "MESH" or it["category"] not in ("furniture", "plant") or ob.get("spec_kind") in HUNG: continue
        if deep_hits(ob, WALLS) <= 2: continue
        R3 = ob.matrix_world.to_3x3(); M0 = ob.matrix_world.copy(); done = None
        dirs = []
        for lv in (Vector((0, 1, 0)), Vector((1, 0, 0)), Vector((-1, 0, 0))):      # out along the front first, then sideways
            d_ = R3 @ lv; d_.z = 0; dirs.append(d_.normalized())
        for d_ in dirs:
            for k in range(1, 25 if it["category"] == "furniture" else 10):       # up to 120 mm (a bed drawn 25 mm into the wall, duvet overhang)
                ob.matrix_world = Matrix.Translation(d_ * 0.005 * k) @ M0
                if deep_hits(ob, WALLS) <= 2: done = k * 5; break
            if done: break
        if done is None: ob.matrix_world = M0; continue
        ob["nudge_mm"] = done; moved.append((it["id"], f"out of the wall {done} mm"))
    # 1b. cushions rest against the sofa's back cushions, never inside them: moved forward along their front, up to 300 mm
    def tree_of_items(cats):
        return tree_of([(o, p_) for o, p_ in items_out if (pos_of.get(o.get("spec_id")) or {}).get("category") in cats and o.get("spec_kind") not in HUNG])
    SEATS = tree_of_items(("furniture",))
    for ob, p in items_out:
        it = pos_of.get(ob.get("spec_id"))
        if it is None or ob.get("spec_kind") != "cushion" or ob.type != "MESH": continue
        if deep_hits(ob, SEATS, lift=0.02) <= 4: continue
        fwd = ob.matrix_world.to_3x3() @ Vector((0, 1, 0)); fwd.z = 0; fwd.normalize()
        M0 = ob.matrix_world.copy(); done = None
        for k in range(1, 31):
            ob.matrix_world = Matrix.Translation(fwd * 0.01 * k) @ M0
            if deep_hits(ob, SEATS, lift=0.02) <= 4: done = k * 10; break
        if done is None: ob.matrix_world = M0; continue
        ob["nudge_mm"] = done; moved.append((it["id"], f"forward {done} mm out of the sofa back"))
    # 1c. hung prints and mirrors slide along their wall until clear of a stair soffit, beam boxing or ceiling
    SLOPES = None
    VS, TS = [], []
    for ob_, p_ in shell:
        if ob_.type != "MESH": continue
        b_ = len(VS); M_ = ob_.matrix_world; R_ = M_.to_3x3()
        VS.extend(M_ @ v.co for v in ob_.data.vertices)
        for pl in ob_.data.polygons:
            if abs((R_ @ pl.normal).normalized().z) > 0.2: TS.append(tuple(b_ + i for i in pl.vertices))
    if TS: SLOPES = BVHTree.FromPolygons(VS, TS)
    for ob, p in items_out:
        it = pos_of.get(ob.get("spec_id"))
        if it is None or ob.type != "MESH" or ob.get("spec_kind") not in ("framed_print", "mirror_round", "mirror_rect", "hanging_picture_frame_02", "hanging_picture_frame_03"): continue
        if deep_hits(ob, SLOPES, lift=-1) == 0: continue
        side = ob.matrix_world.to_3x3() @ Vector((1, 0, 0)); side.z = 0; side.normalize()
        M0 = ob.matrix_world.copy(); done = None
        for k in range(1, 14):
            for sg in (1, -1):
                ob.matrix_world = Matrix.Translation(side * sg * 0.05 * k) @ M0
                if deep_hits(ob, SLOPES, lift=-1) == 0: done = sg * k * 50; break
            if done: break
        if done is None: ob.matrix_world = M0; continue
        ob["nudge_mm"] = abs(done); moved.append((it["id"], f"slid {done} mm along the wall clear of the soffit"))
    # 2. snap small things onto their surfaces (the whole scene: house + the loose layer as now placed)
    T = tree_of([(ob, p) for ob, p in house_objs if not p.get("context") and (p["props"].get("stage_out") or 99) > N] + list(items_out))
    for ob, p in items_out:
        it = pos_of.get(ob.get("spec_id"))
        if it is None or ob.type != "MESH" or it["category"] not in ("decor", "plant", "soft_furnishing") or ob.get("spec_kind") in HUNG: continue
        fl = 2.6755 if it["position_m"][1] > 2.0 else 0.0
        if it["position_m"][1] - fl < 0.005: continue
        M = ob.matrix_world; wv = [M @ v.co for v in ob.data.vertices]
        if not wv: continue
        z0 = min(v.z for v in wv); low = [v for v in wv if v.z < z0 + 0.01]
        cx = sum(v.x for v in low) / len(low); cy = sum(v.y for v in low) / len(low)
        own = bvh_of(ob)
        def surface_under(x, y):
            q = Vector((x, y, z0 + 0.06))
            for _ in range(60):
                h = T.ray_cast(q, DN, 0.2)
                if h[0] is None: return None
                ho = own.ray_cast(q, DN, 0.2)
                if ho[0] is not None and abs(ho[3] - h[3]) < 1e-4: q = h[0] + DN * 0.0002; continue
                return h[0]
            return None
        hit = surface_under(cx, cy); off = Vector((0, 0, 0))
        if hit is None or abs(hit.z - z0) > 0.06:
            best = None
            for r_ in (0.03, 0.06, 0.09, 0.12, 0.15):
                for k in range(8):
                    d = Vector((math.cos(k * math.pi / 4) * r_, math.sin(k * math.pi / 4) * r_, 0))
                    hh = surface_under(cx + d.x, cy + d.y)
                    if hh is not None and abs(hh.z - z0) <= 0.06: best = (d, hh); break
                if best: break
            if best is None: continue
            off, hit = best
        dz = hit.z + 0.0005 - z0
        if abs(dz) < 0.002 and off.length == 0: continue
        ob.matrix_world = Matrix.Translation(Vector((off.x, off.y, dz))) @ ob.matrix_world
        if abs(dz) >= 0.002: ob["snap_dz_mm"] = round(dz * 1000, 1)       # check_spec reads it (vertical snap onto the surface)
        if off.length: ob["nudge_mm"] = round(off.length * 1000 + (ob.get("nudge_mm") or 0))     # adds to an earlier push
        moved.append((it["id"], round(dz * 1000), round(off.length * 1000)))
    # 3. decor and plants clear of walls and breasts (leaves with a 6 % margin so they clear the paint skin too)
    for ob, p in items_out:
        it = pos_of.get(ob.get("spec_id"))
        if it is None or ob.type != "MESH" or it["category"] not in ("decor", "plant") or ob.get("spec_kind") in HUNG: continue
        mg = 1.06 if it["category"] == "plant" else 1.0; lim = 0 if it["category"] == "plant" else 2
        if deep_hits(ob, WALLS, mg) <= lim: continue
        M0 = ob.matrix_world.copy(); best = None
        for r_ in (0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30):
            for k in range(8):
                d = Vector((math.cos(k * math.pi / 4) * r_, math.sin(k * math.pi / 4) * r_, 0))
                ob.matrix_world = Matrix.Translation(d) @ M0
                if deep_hits(ob, WALLS, mg) <= lim: best = d; break
            if best is not None: break
        ob.matrix_world = (Matrix.Translation(best) @ M0) if best is not None else M0
        if best is not None:
            ob["nudge_mm"] = round(best.length * 1000 + (ob.get("nudge_mm") or 0)); moved.append((it["id"], f"clear of the wall {round(best.length * 1000)} mm"))
    if moved:
        NOTES.append(f"placed on and clear of their surfaces (written description governs; spec coordinates off by a few cm): {moved}")
        log(f"furnishing: {len(moved)} loose items set onto/clear of their surfaces: {moved[:12]}")
    return moved
