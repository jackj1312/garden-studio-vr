"""Test-house fixture for the build-stage viewer (house.html, src/house/).

    nice -n 10 /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        --python tools/house/make_fixture.py -- [out_dir]          # default assets/sites/house-fixture

A tiny two-storey rear extension on a box of a house, made ONLY to exercise every viewer feature: cavity walls as
layers, openings with lintels, a demolished wall + temporary props (stage 2 in / out), trench + slab layers, one steel
beam, 10 joists, 8 rafters + 2 hips + ridge, roof felt and tiles, doors and a window, a stair, rooms. Not a real house.

It is also the reference implementation of src/house/CONTRACT.md for the real generator (traced drawings -> Blender):
  1. the house is described first as PARAMETRIC ELEMENTS (walls with layer stacks, openings hosted on walls,
     lintels, fixtures, joist/rafter sets, stairs, rooms) in the VIEWER frame (+Y up, metres);
  2. every element is turned into mesh nodes carrying the glTF extras of the contract;
  3. per version it writes  house_<v>.glb, house_<v>.json (stages sidecar), house_<v>_elements.json, and versions.json.
Light work only (an 8 GB Mac): a few thousand triangles, one small boolean, no render, no bake.
Coordinates: viewer (x, y, z) = Blender (x, z, -y). Everything below is written in the viewer frame and converted
once, in frame_matrix()."""
import bpy, bmesh, json, math, os, sys, copy
from mathutils import Matrix, Vector

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.realpath(argv[0]) if argv else os.path.join(ROOT, "assets", "sites", "house-fixture")
os.makedirs(OUT, exist_ok=True)
DRW_GF, DRW_FF, DRW_SA, DRW_SB, DRW_RF = ("4915.2 ground floor plan", "4915.2 first floor plan",
                                          "4915.3A section A-A", "4915.3A section B-B", "4915.4 roof plan")
TYPICAL = "typical — not from the drawings"

# ---------------------------------------------------------------- materials
MATS = {  # name: (base colour sRGB, roughness, metallic, alpha)
    "brick": ((0.62, 0.33, 0.24), 0.85, 0, 1), "existing_brick": ((0.55, 0.36, 0.28), 0.9, 0, 1),
    "block": ((0.70, 0.70, 0.68), 0.9, 0, 1), "pir": ((0.86, 0.80, 0.52), 0.7, 0, 1),
    "plasterboard": ((0.93, 0.92, 0.89), 0.8, 0, 1), "concrete": ((0.62, 0.62, 0.60), 0.9, 0, 1),
    "hardcore": ((0.50, 0.47, 0.43), 1.0, 0, 1), "dpm": ((0.12, 0.13, 0.15), 0.4, 0, 1),
    "mesh_a142": ((0.40, 0.30, 0.25), 0.6, 0.6, 1), "screed": ((0.76, 0.74, 0.70), 0.9, 0, 1),
    "steel": ((0.30, 0.32, 0.34), 0.45, 0.8, 1), "timber": ((0.80, 0.64, 0.42), 0.8, 0, 1),
    "chipboard": ((0.78, 0.66, 0.48), 0.85, 0, 1), "felt": ((0.20, 0.27, 0.33), 0.6, 0, 1),
    "tile": ((0.42, 0.22, 0.17), 0.75, 0, 1), "existing_tile": ((0.32, 0.30, 0.30), 0.8, 0, 1),
    "frame_white": ((0.95, 0.95, 0.94), 0.4, 0, 1), "frame_grey": ((0.22, 0.24, 0.26), 0.4, 0.2, 1),
    "glass": ((0.75, 0.85, 0.90), 0.05, 0, 0.25), "lintel_galv": ((0.66, 0.68, 0.70), 0.4, 0.8, 1),
    "prop_steel": ((0.86, 0.62, 0.12), 0.5, 0.5, 1), "timber_temp": ((0.85, 0.72, 0.40), 0.8, 0, 1),
    "grass": ((0.33, 0.48, 0.24), 1.0, 0, 1), "earth": ((0.42, 0.32, 0.22), 1.0, 0, 1),
    "pvc_drain": ((0.78, 0.40, 0.15), 0.5, 0, 1), "paving": ((0.66, 0.63, 0.58), 0.9, 0, 1),
    "unit": ((0.30, 0.38, 0.36), 0.5, 0, 1), "worktop": ((0.85, 0.83, 0.78), 0.3, 0, 1),
    "existing_floor": ((0.70, 0.60, 0.48), 0.8, 0, 1), "stair": ((0.72, 0.58, 0.40), 0.7, 0, 1),
}


def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_materials():
    out = {}
    for name, (col, rough, metal, alpha) in MATS.items():
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Base Color"].default_value = (*[srgb_to_lin(c) for c in col], 1)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        if alpha < 1:
            bsdf.inputs["Alpha"].default_value = alpha
            try: m.surface_render_method = "BLENDED"
            except Exception: m.blend_method = "BLEND"
        out[name] = m
    return out


# ---------------------------------------------------------------- geometry helpers (viewer frame)
UP = Vector((0, 1, 0))


def conv(v):                      # viewer -> Blender
    return Vector((v[0], -v[2], v[1]))


def frame_matrix(o, U, W, V):
    """A local frame in the viewer: local (a, b, c) -> o + a*U + b*W + c*V. (U, W, V) must be right-handed
    (U x W = V). Returned as a Blender world matrix."""
    U, W, V = conv(U), conv(W), conv(V)
    o = conv(o)
    return Matrix(((U.x, W.x, V.x, o.x), (U.y, W.y, V.y, o.y), (U.z, W.z, V.z, o.z), (0, 0, 0, 1)))


def wall_frame(start, end):
    """Wall frame: a = along the centre line from start, b = height (viewer y), c = across, +c = n = (-dz, dx)."""
    d = Vector((end[0] - start[0], 0, end[1] - start[1]))
    L = d.length
    d.normalize()
    n = Vector((-d.z, 0, d.x))
    return Vector((start[0], 0, start[1])), d, n, L


def add_box(bm, a0, a1, b0, b1, c0, c1):
    vs = [bm.verts.new((a, b, c)) for a in (a0, a1) for b in (b0, b1) for c in (c0, c1)]
    # index = ia*4 + ib*2 + ic ; local frame -> Blender local coords (a, b, c) map directly (matrix does the rest)
    q = lambda ia, ib, ic: vs[ia * 4 + ib * 2 + ic]
    for f in ((q(0,0,0), q(0,0,1), q(0,1,1), q(0,1,0)), (q(1,0,0), q(1,1,0), q(1,1,1), q(1,0,1)),
              (q(0,0,0), q(1,0,0), q(1,0,1), q(0,0,1)), (q(0,1,0), q(0,1,1), q(1,1,1), q(1,1,0)),
              (q(0,0,0), q(0,1,0), q(1,1,0), q(1,0,0)), (q(0,0,1), q(1,0,1), q(1,1,1), q(0,1,1))):
        bm.faces.new(f)


def add_prism(bm, poly, b0, b1):
    """A vertical prism in local (a, c) plan coordinates poly, from height b0 to b1."""
    lo = [bm.verts.new((p[0], b0, p[1])) for p in poly]
    hi = [bm.verts.new((p[0], b1, p[1])) for p in poly]
    bm.faces.new(lo); bm.faces.new(hi)
    n = len(poly)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))


def add_slab(bm, pts3, n3, t0, t1):
    """A slab from a planar polygon pts3 (local coords), offset t0..t1 along unit normal n3."""
    lo = [bm.verts.new(Vector(p) + Vector(n3) * t0) for p in pts3]
    hi = [bm.verts.new(Vector(p) + Vector(n3) * t1) for p in pts3]
    bm.faces.new(lo); bm.faces.new(hi)
    for i in range(len(pts3)):
        j = (i + 1) % len(pts3)
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))


def finish_mesh(bm, name):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


IDENT = (Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))  # viewer world frame


# ---------------------------------------------------------------- the parts registry
PARTS = []          # (object, version set)
coll = None


def meta_props(meta, **over):
    m = dict(meta); m.update(over)
    return m


def add_part(name, mesh, frame, mat, props, versions=("today",)):
    """frame = (o, U, W, V) in the viewer frame. props = the contract's extras for this node."""
    ob = bpy.data.objects.new(name, mesh)
    ob.matrix_world = frame_matrix(*frame)
    if not ob.data.materials:
        ob.data.materials.append(MAT[mat])
    for k, v in props.items():
        if v is None:
            continue                     # IDProperties cannot hold None: absent means null (see CONTRACT.md)
        ob[k] = v
    coll.objects.link(ob)
    PARTS.append((ob, set(versions)))
    return ob


def box_part(name, mat, props, x0, x1, y0, y1, z0, z1, versions=("today",)):
    bm = bmesh.new(); add_box(bm, x0, x1, y0, y1, z0, z1)
    return add_part(name, finish_mesh(bm, name), IDENT, mat, props, versions)


# ---------------------------------------------------------------- elements
ELEMENTS = []
EL = {}


def element(eid, etype, params, meta, versions=("today",), **extra):
    e = {"id": eid, "type": etype, "params": params, "meta": meta, **extra}
    e["_versions"] = list(versions)
    ELEMENTS.append(e); EL[eid] = e
    return e


def M(stage_in, category, group, storey, label, drawing, conf, seq=0.0, stage_out=None, seq_out=None,
      collide=False, plain_label=None, seq_span=None):
    m = {"stage_in": stage_in, "stage_out": stage_out, "seq": seq, "seq_out": seq_out, "category": category,
         "group": group, "storey": storey, "label": label, "drawing": drawing, "conf": conf,
         "collide": collide, "plain_label": plain_label}
    if seq_span is not None:
        m["seq_span"] = seq_span          # how much of the stage a multi-part element's parts spread over
    return m


def node_props(e, **over):
    m = dict(e["meta"]); m.update(over)
    m["element"] = e["id"]
    return m


# ---------------------------------------------------------------- wall -> parts (same algorithm as src/house/geom.js)
def wall_cells(L, base, height, openings, lifts):
    """Cells of a wall face in (u, y): split at every opening edge and lift line; drop cells inside an opening.
    Returns [(lift_index, u0, u1, y0, y1)]."""
    us = sorted({0.0, L, *[max(0, min(L, o["offset"])) for o in openings],
                 *[max(0, min(L, o["offset"] + o["width"])) for o in openings]})
    top = base + height
    ys = sorted({base, top, *[y for y in lifts if base < y < top],
                 *[max(base, min(top, o["sill"])) for o in openings], *[max(base, min(top, o["head"])) for o in openings]})
    lift_lines = [base] + [y for y in lifts if base < y < top] + [top]
    out = []
    for i in range(len(us) - 1):
        for j in range(len(ys) - 1):
            u0, u1, y0, y1 = us[i], us[i + 1], ys[j], ys[j + 1]
            if u1 - u0 < 1e-6 or y1 - y0 < 1e-6:
                continue
            um, ym = (u0 + u1) / 2, (y0 + y1) / 2
            if any(o["offset"] < um < o["offset"] + o["width"] and o["sill"] < ym < o["head"] for o in openings):
                continue
            lift = max(k for k in range(len(lift_lines) - 1) if lift_lines[k] <= ym + 1e-9)
            out.append((lift, u0, u1, y0, y1))
    return out, len(lift_lines) - 1


def layer_spans(layers):
    T = sum(l["thickness"] for l in layers)
    c, out = T / 2, []
    for l in layers:                      # layer 0 is on the +n face
        out.append((c - l["thickness"], c))
        c -= l["thickness"]
    return out, T


LAYER_META = ("stage_in", "stage_out", "seq", "seq_out", "category", "group", "label", "plain_label", "drawing", "conf", "collide")


def wall_seq(meta, lift, nlifts, li, nlayers):
    """Recommended part seq for a lift of a layer (CONTRACT.md): lifts rise in order across the whole wall."""
    span = meta.get("seq_span", 0.85)
    return round(meta["seq"] + span * (lift + 0.3 * li / max(1, nlayers)) / nlifts, 4)


def build_wall(e, versions):
    p = e["params"]
    o, d, n, L = wall_frame(p["start"], p["end"])
    ops = [EL[i]["params"] for i in e.get("openings", [])]
    cells, nl = wall_cells(L, p["base"], p["height"], ops, p.get("lifts", []))
    spans, _ = layer_spans(p["layers"])
    for li, (layer, (c0, c1)) in enumerate(zip(p["layers"], spans)):
        if layer.get("void"):
            continue
        lm = dict(e["meta"]); lm.update({k: v for k, v in layer.items() if k in LAYER_META})
        for lift in range(nl):
            cs = [c for c in cells if c[0] == lift]
            if not cs:
                continue
            bm = bmesh.new()
            for _, u0, u1, y0, y1 in cs:
                add_box(bm, u0, u1, y0, y1, c0, c1)
            name = f"{e['id']}_L{li}_{layer['group']}_lift{lift}"
            seq = lm["seq"] if "seq" in layer else wall_seq(e["meta"], lift, nl, li, len(p["layers"]))
            props = node_props(e)
            props.update(lm)
            props.update(layer=li, lift=lift, seq=seq, element=e["id"], element_label=e["meta"]["label"])
            add_part(name, finish_mesh(bm, name), (o, d, UP, n), layer["material"], props, versions)


def opening_frame(op):
    host = EL[op["params"]["host"]]["params"]
    o, d, n, L = wall_frame(host["start"], host["end"])
    spans, T = layer_spans(host["layers"])
    return o, d, n, host, spans, T


def build_lintel(e, versions):
    op = EL[e["params"]["opening"]]
    o, d, n, host, spans, T = opening_frame(op)
    q = op["params"]
    b = e["params"]["bearing"]
    # across the structural leaves (not the lining): from the +n face to the inner face of the last non-lining layer
    c_hi = spans[0][1]
    c_lo = min(s[0] for s, l in zip(spans, host["layers"]) if l["group"] != "wall_lining")
    bm = bmesh.new()
    add_box(bm, q["offset"] - b, q["offset"] + q["width"] + b, q["head"], q["head"] + e["params"]["depth"], c_lo, c_hi)
    add_part(e["id"], finish_mesh(bm, e["id"]), (o, d, UP, n), e["params"].get("material", "lintel_galv"),
             node_props(e), versions)


CATALOGUE = {   # fixture catalogue: frame size, panes, materials (the viewer has the same table, geom.js)
    "door.bifold.3": {"frame": 0.07, "depth": 0.07, "panes": 3, "frame_mat": "frame_grey", "glass": True},
    "door.front.solid": {"frame": 0.06, "depth": 0.06, "panes": 1, "frame_mat": "frame_white", "glass": False},
    "window.casement.2": {"frame": 0.06, "depth": 0.07, "panes": 2, "frame_mat": "frame_white", "glass": True},
}


def build_fixture(e, versions):
    op = EL[e["params"]["opening"]]
    o, d, n, host, spans, T = opening_frame(op)
    q = op["params"]
    cat = CATALOGUE[e["params"]["catalogue"]]
    f, dep = cat["frame"], cat["depth"]
    c_mid = e["params"].get("plane", 0.0)          # across-wall position of the frame (0 = wall centre line)
    u0, u1, y0, y1 = q["offset"], q["offset"] + q["width"], q["sill"], q["head"]
    bm = bmesh.new()
    add_box(bm, u0, u1, y1 - f, y1, c_mid - dep / 2, c_mid + dep / 2)
    add_box(bm, u0, u1, y0, y0 + f * 0.6, c_mid - dep / 2, c_mid + dep / 2)
    k = cat["panes"]
    for i in range(k + 1):
        x = u0 + (u1 - u0 - f) * i / k
        add_box(bm, x, x + f, y0 + f * 0.6, y1 - f, c_mid - dep / 2, c_mid + dep / 2)
    add_part(e["id"] + "_frame", finish_mesh(bm, e["id"] + "_frame"), (o, d, UP, n), cat["frame_mat"],
             node_props(e, part="frame"), versions)
    bm = bmesh.new()
    add_box(bm, u0 + f, u1 - f, y0 + f * 0.6, y1 - f, c_mid - 0.006, c_mid + 0.006)
    add_part(e["id"] + "_leaf", finish_mesh(bm, e["id"] + "_leaf"), (o, d, UP, n),
             "glass" if cat["glass"] else cat["frame_mat"], node_props(e, part="leaf"), versions)


def build_member_set(e, versions):
    """joist_set / rafter_set / ceiling joists: linked duplicates of ONE mesh (the viewer instances them)."""
    p = e["params"]
    mesh_name = e["id"] + "_member"
    bm = bmesh.new()
    add_box(bm, 0, p["length"], -p["depth"] / 2, p["depth"] / 2, -p["width"] / 2, p["width"] / 2)
    me = finish_mesh(bm, mesh_name)
    for i, fr in enumerate(p["_frames"]):
        seq = round(e["meta"]["seq"] + e["meta"].get("seq_span", 0.5) * i / max(1, len(p["_frames"]) - 1), 4)
        add_part(f"{e['id']}_{i:02d}", me, fr, p.get("material", "timber"), node_props(e, seq=seq, member=i), versions)


# ---------------------------------------------------------------- the fixture house
def define():
    W, Wx = 0.3, 0.3
    ex_layers = [  # existing walls: assumed 300 cavity, two leaves, unfilled
        {"group": "wall_outer", "thickness": 0.1025, "material": "existing_brick", "label": "Existing brick outer leaf (assumed)"},
        {"group": "wall_cavity", "thickness": 0.095, "void": True, "label": "Existing cavity (assumed unfilled)"},
        {"group": "wall_inner", "thickness": 0.1025, "material": "existing_brick", "label": "Existing brick inner leaf (assumed)"},
    ]
    new_layers = [
        {"group": "wall_outer", "thickness": 0.1025, "material": "brick",
         "label": "102.5mm facing brickwork to match existing, in 1:1:6 mortar", "plain_label": "Outer brick wall, to match the house"},
        {"group": "wall_cavity", "thickness": 0.05, "void": True, "label": "50mm clear residual cavity, stainless wall ties at 900 x 450 c/c"},
        {"group": "wall_insulation", "thickness": 0.05, "material": "pir",
         "label": "50mm Celotex CW4050 PIR partial-fill cavity insulation", "plain_label": "Insulation in the wall cavity"},
        {"group": "wall_inner", "thickness": 0.1, "material": "block",
         "label": "100mm 7N/mm² aerated concrete block inner leaf", "plain_label": "Inner block wall"},
        {"group": "wall_lining", "thickness": 0.0155, "material": "plasterboard", "stage_in": 12, "seq": 0.2, "category": "finish",
         "label": "12.5mm plasterboard on dabs, 3mm skim finish", "plain_label": "Plastered inside face"},
    ]
    ex = lambda g, lab, **k: M(1, "existing", g, k.pop("storey", "ground"), lab, k.pop("drawing", DRW_GF), k.pop("conf", "assumed"), **k)
    BOTH = ("today", "before")

    # ---- site
    element("G-before", "mesh", {}, M(1, "existing", "ground", "site", "Existing ground: lawn on topsoil (assumed level)",
            "4915.1 site plan", "assumed", stage_out=3, seq_out=0.15, collide=True, plain_label="The garden as it is now"), BOTH)
    element("G-dug", "mesh", {}, M(3, "new", "ground", "site", "Reduced dig for slab, trenches 600 wide to 1000 deep below GL (to suit site conditions / BCO)",
            DRW_SA, "scaled", seq=0.15, collide=True, plain_label="Ground dug out for the new foundations"))
    element("P-patio", "mesh", {}, M(1, "demolition", "ground", "site", "Existing patio slabs on sand: lift and remove",
            "4915.1 site plan", "assumed", stage_out=2, seq_out=0.85, collide=True, plain_label="Old patio — taken up"), BOTH)
    element("SP-1", "mesh", {}, M(3, "temporary", "spoil", "site", f"Spoil heap from excavations, removed from site ({TYPICAL})",
            "", "assumed", seq=0.35, stage_out=12, seq_out=0.02, collide=True, plain_label="Soil dug out, taken away at the end"))
    element("SO-pegs", "mesh", {}, M(3, "temporary", "prop", "site", f"Setting-out profiles and string lines ({TYPICAL})",
            "", "assumed", seq=0.0, stage_out=4, seq_out=0.2, plain_label="Marking out where the walls go"))

    # ---- existing house: x -3..3, z -5..0 ; walls on centre lines
    for eid, s, e_, lab in (("W-X-front", (3, -4.85), (-3, -4.85), "front"), ("W-X-left", (-2.85, -5), (-2.85, 0), "left side"),
                            ("W-X-right", (2.85, 0), (2.85, -5), "right side"), ("W-X-rear", (-3, -0.15), (3, -0.15), "rear")):
        element(eid, "wall", {"start": list(s), "end": list(e_), "base": 0.0, "height": 5.3, "layers": ex_layers, "lifts": []},
                ex("wall_outer", f"Existing {lab} wall, 300mm cavity (assumed)", collide=True, plain_label=f"Existing {lab} wall of the house"),
                BOTH, openings=[])
    # the new opening in the existing rear wall (formed in stage 2, under beam 5); filled by the demolished panel until then
    element("O-X-rear", "opening", {"host": "W-X-rear", "offset": 1.4, "width": 2.8, "sill": 0.0, "head": 2.45},
            ex("wall_outer", "New 2800 wide structural opening in existing rear wall", drawing=DRW_GF, conf="scaled"), BOTH)
    EL["W-X-rear"]["openings"].append("O-X-rear")
    element("O-X-front", "opening", {"host": "W-X-front", "offset": 2.55, "width": 0.9, "sill": 0.15, "head": 2.25},
            ex("door", "Existing front door opening"), BOTH)
    EL["W-X-front"]["openings"].append("O-X-front")
    element("F-X-front", "fixture", {"catalogue": "door.front.solid", "opening": "O-X-front", "plane": 0.0},
            ex("door", "Existing front door", plain_label="Front door"), BOTH)
    element("D-rear-panel", "mesh", {}, M(1, "demolition", "wall_outer", "ground",
            "Existing rear wall below beam 5: carefully take down after props and needles are in", DRW_GF, "scaled",
            stage_out=2, seq_out=0.6, collide=True, plain_label="Part of the back wall that is knocked through"), BOTH)
    element("X-slab", "mesh", {}, ex("slab_layer", "Existing ground floor slab (assumed)", collide=True), BOTH)
    element("X-deck", "mesh", {}, ex("deck", "Existing first floor: timber joists and boards (assumed)", storey="first", collide=True), BOTH)
    element("X-roof", "mesh", {}, ex("roof_cover", "Existing pitched roof, concrete interlocking tiles", storey="roof", drawing=DRW_RF), BOTH)
    element("X-gables", "mesh", {}, ex("wall_outer", "Existing gable walls", storey="roof", collide=True), BOTH)
    element("S-X-1", "stair", {"start": [2.275, -0.6], "direction": [0, -1], "width": 0.85, "base": 0.15, "risers": 13,
                               "rise": round((2.967 - 0.15) / 13, 4), "going": 0.225, "top_floor": "X-deck"},
            ex("fitting", "Existing straight flight stair, 13 risers (assumed)", collide=True, plain_label="Stairs to the first floor"), BOTH)
    element("PR-1", "mesh", {}, M(1, "demolition", "wall_outer", "ground", "Existing back door step: remove", DRW_GF, "assumed",
            stage_out=2, seq_out=0.7, collide=True), BOTH)

    # ---- stage 2 temporary works: needles + props either side of the rear wall
    element("TW-needles", "member_set", {}, M(2, "temporary", "prop", "ground",
            f"152x152 timber needles through the wall at 1.0m c/c above the new opening ({TYPICAL})", "", "assumed",
            seq=0.02, seq_span=0.08, stage_out=7, seq_out=0.88, plain_label="Temporary timbers through the wall"))
    element("TW-props", "member_set", {}, M(2, "temporary", "prop", "ground",
            f"Acrow props, size 2, under each needle end ({TYPICAL})", "", "assumed",
            seq=0.15, seq_span=0.2, stage_out=7, seq_out=0.9, collide=True, plain_label="Temporary steel props holding the wall up"))

    # ---- stage 4 foundations + drains
    for i, (eid, lab) in enumerate((("FD-L", "left"), ("FD-R", "right"), ("FD-G", "garden"), ("FD-P", "porch"))):
        element(eid, "mesh", {}, M(4, "new", "foundation", "site",
                f"Trench-fill foundation, 600 wide, ST2/GEN1 concrete, min 1000 below GL ({lab} wall)", DRW_SA, "scaled",
                seq=0.05 + 0.2 * i, collide=True, plain_label="Concrete foundation poured in the trench"))
    element("DR-1", "mesh", {}, M(4, "new", "drain", "site", "110mm uPVC foul drain at 1:40, in pea shingle bed and surround", DRW_GF, "scaled",
            seq=0.7, plain_label="New drain pipe"))
    element("DR-IC", "mesh", {}, M(4, "new", "drain", "site", "450mm uPVC inspection chamber", DRW_GF, "scaled", seq=0.8))

    # ---- stage 5 slab
    slab = [("SL-hardcore", "hardcore", "150mm well-compacted MOT Type 1 hardcore, 25mm sand blinding", 0.0),
            ("SL-dpm", "dpm", "1200 gauge polythene DPM, lapped and taped, turned up at edges", 0.3),
            ("SL-ins", "pir", "100mm Celotex GA4100 PIR floor insulation, 25mm upstand at perimeter", 0.5),
            ("SL-mesh", "mesh_a142", "A142 steel mesh on chairs", 0.65),
            ("SL-conc", "concrete", "100mm ST4 concrete ground bearing slab", 0.8)]
    for eid, mat, lab, seq in slab:
        element(eid, "mesh", {"material": mat}, M(5, "new", "slab_layer", "ground", lab, DRW_SA, "exact", seq=seq,
                collide=eid in ("SL-conc", "SL-hardcore", "SL-ins"), plain_label={"SL-conc": "The new concrete floor slab", "SL-ins": "Floor insulation",
                                                       "SL-dpm": "Damp-proof sheet under the floor"}.get(eid)))

    # ---- extension walls
    xo0, xo1, zo1 = -2.4, 2.0, 4.0
    T = sum(l["thickness"] for l in new_layers)
    lc, rc, gc = xo0 + T / 2, xo1 - T / 2, zo1 - T / 2
    gf = dict(base=-0.15, height=2.9, layers=new_layers)
    ff = dict(base=2.75, height=2.55, layers=new_layers)
    wm = lambda st, lab, storey, seq=0.0: M(st, "new", "wall_outer", storey, lab, DRW_SA, "scaled", seq=seq, collide=True,
                                            plain_label="New cavity wall")
    element("W-L-gf", "wall", {"start": [lc, 0], "end": [lc, zo1], "lifts": [0.6, 1.65], **gf},
            wm(6, "Extension left wall, ground storey: 300 cavity wall on trench fill", "ground"), openings=[])
    element("W-R-gf", "wall", {"start": [rc, zo1], "end": [rc, 0], "lifts": [0.6, 1.65], **gf},
            wm(6, "Extension right wall, ground storey: 300 cavity wall on trench fill", "ground"), openings=[])
    element("W-G-gf", "wall", {"start": [xo0 + T, gc], "end": [xo1 - T, gc], "lifts": [0.6, 1.65], **gf},
            wm(6, "Extension garden wall, ground storey: 300 cavity wall on trench fill", "ground"), openings=["O-G-bifold"])
    element("O-G-bifold", "opening", {"host": "W-G-gf", "offset": 0.68, "width": 2.4, "sill": 0.15, "head": 2.25},
            M(6, "new", "door", "ground", "2400 x 2100 structural opening for bifold doors", DRW_GF, "exact"))
    element("L-G-bifold", "lintel", {"opening": "O-G-bifold", "bearing": 0.15, "depth": 0.15},
            M(6, "new", "lintel", "ground", "Catnic CG90/100 cavity wall lintel, 2700 long, 150mm end bearings", DRW_SA, "exact",
              seq=0.6, plain_label="Steel lintel over the new doors"))
    # an as-built record: on site the bifold lintel went in as precast concrete (shown with the "As built" toggle)
    element("L-G-bifold-AB", "lintel", {"opening": "O-G-bifold", "bearing": 0.15, "depth": 0.15, "material": "concrete"},
            M(6, "new", "lintel", "ground", "AS BUILT (site record, fixture): 2700 x 215 x 150 precast concrete lintel in lieu of Catnic CG90/100 "
              "— engineer to confirm", "site record", "assumed", seq=0.6, plain_label="The lintel that was actually fitted"),
            layer="as_built", replaces=["L-G-bifold"])
    element("W-L-ff", "wall", {"start": [lc, 0], "end": [lc, zo1], "lifts": [3.6, 4.45], **ff},
            wm(9, "Extension left wall, first storey: 300 cavity wall to wall plate", "first"), openings=[])
    element("W-R-ff", "wall", {"start": [rc, zo1], "end": [rc, 0], "lifts": [3.6, 4.45], **ff},
            wm(9, "Extension right wall, first storey: 300 cavity wall to wall plate", "first"), openings=["O-R-win"])
    element("W-G-ff", "wall", {"start": [xo0 + T, gc], "end": [xo1 - T, gc], "lifts": [3.6, 4.45], **ff},
            wm(9, "Extension garden wall, first storey: 300 cavity wall to wall plate", "first"), openings=[])
    element("O-R-win", "opening", {"host": "W-R-ff", "offset": 1.4, "width": 1.2, "sill": 3.85, "head": 4.95},
            M(9, "new", "window", "first", "1200 x 1100 window opening, bedroom 3", DRW_FF, "exact"))
    element("L-R-win", "lintel", {"opening": "O-R-win", "bearing": 0.15, "depth": 0.15},
            M(9, "new", "lintel", "first", "Catnic CG90/100 cavity wall lintel, 1500 long", DRW_SB, "exact", seq=0.55,
              plain_label="Lintel over the bedroom window"))
    # porch at the front door (stage 9 "porch walls")
    pl = new_layers[:4]
    pT = sum(l["thickness"] for l in pl)
    pm = lambda lab: M(9, "new", "wall_outer", "ground", lab, DRW_GF, "scaled", seq=0.0, seq_span=0.6, collide=True, plain_label="New porch wall")
    element("W-P-left", "wall", {"start": [-0.95 + pT / 2, -6.4], "end": [-0.95 + pT / 2, -5.0], "base": -0.15, "height": 2.45, "layers": pl, "lifts": [1.0]},
            pm("Porch left wall, 300 cavity wall"), openings=[])
    element("W-P-right", "wall", {"start": [0.95 - pT / 2, -5.0], "end": [0.95 - pT / 2, -6.4], "base": -0.15, "height": 2.45, "layers": pl, "lifts": [1.0]},
            pm("Porch right wall, 300 cavity wall"), openings=[])
    element("W-P-front", "wall", {"start": [0.95, -6.4 + pT / 2], "end": [-0.95, -6.4 + pT / 2], "base": -0.15, "height": 2.45, "layers": pl, "lifts": [1.0]},
            pm("Porch front wall, 300 cavity wall"), openings=["O-P-door"])
    element("O-P-door", "opening", {"host": "W-P-front", "offset": 0.5, "width": 0.9, "sill": 0.15, "head": 2.25},
            M(9, "new", "door", "ground", "Porch door opening 900 x 2100", DRW_GF, "exact"))
    element("L-P-door", "lintel", {"opening": "O-P-door", "bearing": 0.15, "depth": 0.15},
            M(9, "new", "lintel", "ground", "Catnic CG90/100 cavity wall lintel, 1200 long", DRW_GF, "exact", seq=0.65))

    # ---- stage 7 steel
    element("B-5", "beam", {"start": [-1.9, -0.15], "end": [1.5, -0.15], "base": 2.45, "section": "203x102x23 UB", "depth": 0.2032,
                            "width": 0.1018},
            M(7, "new", "steel", "ground", "beam 5 – 203x102x23kg/m UB steel beam with 8mm thick m/s plate welded to bottom of UB "
              "to carry out skin of brickwork over opening as per Struct. Engs design & calcs", DRW_SA, "exact", seq=0.2, collide=True,
              plain_label="Steel beam holding up the back wall of the house where it has been opened up"),
            bears_on=["W-X-rear"], regs=["PH-A-steel"])
    EL["W-X-rear"]["carries_from"] = ["B-5"]   # informative: the wall over the opening now sits on B-5

    # ---- stage 8 floor
    FFL1 = 2.967
    jx0, jx1 = xo0 + 0.2025, xo1 - 0.2025
    element("J-ff", "member_set", {"length": jx1 - jx0, "width": 0.047, "depth": 0.195, "count": 10, "spacing": 0.4,
                                   "material": "timber"},
            M(8, "new", "joist", "first", "47x195 C24 first floor joists at 400 c/c, built into inner leaf on joist hangers", DRW_SA, "exact",
              seq=0.05, seq_span=0.55, plain_label="New floor joists for bedroom 3"),
            bears_on=["W-L-gf", "W-R-gf"])
    element("DK-ff", "mesh", {}, M(8, "new", "deck", "first", "22mm moisture-resistant T&G chipboard flooring, glued and screwed", DRW_SA,
            "exact", seq=0.8, collide=True, plain_label="The new bedroom floor"), bears_on=["J-ff"])

    # ---- stage 10 roof structure (hip roof over the extension)
    element("WP-1", "mesh", {}, M(10, "new", "wall_plate", "roof", "100x50 sw wall plate bedded on inner leaf, strapped at 1.2m c/c",
            DRW_SA, "exact", seq=0.03))
    element("RB-1", "mesh", {}, M(10, "new", "ridge", "roof", "47x200 C24 ridge board", DRW_SA, "exact", seq=0.2), bears_on=[])
    element("RF-com", "member_set", {"width": 0.047, "depth": 0.15, "material": "timber"},
            M(10, "new", "rafter", "roof", "47x150 C24 rafters at 400 c/c, 35° pitch, birdsmouthed onto wall plate", DRW_SA, "exact",
              seq=0.3, seq_span=0.3, plain_label="Roof rafters"), bears_on=["W-L-ff", "W-R-ff"])
    element("RF-hip", "member_set", {"width": 0.047, "depth": 0.2, "material": "timber"},
            M(10, "new", "hip", "roof", "47x200 C24 hip rafters", DRW_RF, "scaled", seq=0.65, seq_span=0.05),
            bears_on=["W-G-ff", "W-L-ff", "W-R-ff"])
    element("CJ-1", "member_set", {"width": 0.047, "depth": 0.1, "material": "timber"},
            M(10, "new", "ceiling_joist", "roof", "47x100 C24 ceiling joists at 400 c/c (shown at 800 for clarity)", DRW_SA, "scaled",
              seq=0.8, seq_span=0.15), bears_on=["W-L-ff", "W-R-ff"])

    # ---- stage 11 coverings, windows, doors
    element("RL-felt", "mesh", {}, M(11, "new", "roof_layer", "roof", "Breathable roofing membrane (Tyvek Supro) on rafters, 25x50 tanalised battens",
            DRW_SA, "exact", seq=0.1, plain_label="Waterproof membrane under the tiles"))
    element("RC-tiles", "mesh", {}, M(11, "new", "roof_cover", "roof", "Marley Modern interlocking concrete tiles to match existing, colour smooth grey",
            DRW_SA, "exact", seq=0.45, plain_label="Roof tiles to match the house"))
    element("RC-porch", "mesh", {}, M(11, "new", "roof_cover", "ground", "Porch mono-pitch roof, tiles to match", DRW_GF, "scaled", seq=0.55))
    element("F-G-bifold", "fixture", {"catalogue": "door.bifold.3", "opening": "O-G-bifold", "plane": -0.02},
            M(11, "new", "door", "ground", "Aluminium 3-pane bifold door set, 2400 x 2100, Uw ≤ 1.4 W/m²K", DRW_GF, "exact", seq=0.8,
              plain_label="New folding glass doors to the garden"))
    element("F-R-win", "fixture", {"catalogue": "window.casement.2", "opening": "O-R-win", "plane": 0.0},
            M(11, "new", "window", "first", "uPVC double-glazed casement window 1200 x 1100, Uw ≤ 1.4, egress opening", DRW_FF, "exact", seq=0.7,
              plain_label="Bedroom window"))
    element("F-P-door", "fixture", {"catalogue": "door.front.solid", "opening": "O-P-door", "plane": 0.0},
            M(11, "new", "door", "ground", "Composite porch door 900 x 2100", DRW_GF, "exact", seq=0.9))

    # ---- stage 12 finishes
    element("SC-1", "mesh", {}, M(12, "finish", "slab_layer", "ground", "65mm sand:cement screed with underfloor heating", DRW_SA, "exact",
            seq=0.05, collide=True, plain_label="Floor screed (the finished floor goes on this)"))
    element("K-units", "fixture", {"catalogue": "kitchen.base.run"}, M(12, "finish", "fitting", "ground", "Kitchen base units 600 deep with worktop (client's supplier)",
            DRW_GF, "assumed", seq=0.6, plain_label="Kitchen units"))

    # ---- rooms (no geometry: tap-for-info, customer mode)
    element("R-kitchen", "room", {"name": "Kitchen-diner", "polygon": [[xo0 + T, 0], [xo1 - T, 0], [xo1 - T, zo1 - T], [xo0 + T, zo1 - T]],
                                  "floor": 0.15, "storey": "ground"},
            {"category": "new", "plain_label": "New kitchen-diner, open to the living room through the new opening, with folding doors to the garden.",
             "change": "new"})
    element("R-bed3", "room", {"name": "Bedroom 3", "polygon": [[xo0 + T, 0], [xo1 - T, 0], [xo1 - T, zo1 - T], [xo0 + T, zo1 - T]],
                               "floor": FFL1, "storey": "first"},
            {"category": "new", "plain_label": "New bedroom over the kitchen, with a window to the side.", "change": "new"})
    element("R-living", "room", {"name": "Living room and hall", "polygon": [[-2.7, -4.7], [2.7, -4.7], [2.7, -0.3], [-2.7, -0.3]],
                                 "floor": 0.15, "storey": "ground"},
            {"category": "existing", "plain_label": "Existing living room. Its back wall is opened up into the new kitchen.", "change": "altered"},
            ("today", "before"))
    element("R-landing", "room", {"name": "Landing and bedrooms 1–2", "polygon": [[-2.7, -4.7], [2.7, -4.7], [2.7, -0.3], [-2.7, -0.3]],
                                  "floor": FFL1, "storey": "first"},
            {"category": "existing", "plain_label": "Existing first floor, unchanged.", "change": "unchanged"}, ("today", "before"))
    element("R-porch", "room", {"name": "Porch", "polygon": [[-0.95 + pT, -6.4 + pT], [0.95 - pT, -6.4 + pT], [0.95 - pT, -5.0], [-0.95 + pT, -5.0]],
                                "floor": 0.15, "storey": "ground"},
            {"category": "new", "plain_label": "New entrance porch at the front door.", "change": "new"})
    return dict(xo0=xo0, xo1=xo1, zo1=zo1, T=T, FFL1=FFL1, jx0=jx0, jx1=jx1, pT=pT)


def build(g):
    xo0, xo1, zo1, T, FFL1 = g["xo0"], g["xo1"], g["zo1"], g["T"], g["FFL1"]
    BOTH = ("today", "before")
    E = lambda i: EL[i]
    for e in ELEMENTS:
        if e["type"] == "wall":
            build_wall(e, e["_versions"])
        elif e["type"] == "lintel":
            build_lintel(e, e["_versions"])
            if e.get("layer") == "as_built":
                PARTS[-1][0]["as_built"] = True
        elif e["type"] == "fixture" and e["params"].get("opening"):
            build_fixture(e, e["_versions"])

    # ---- ground: before (whole) and dug (boolean); patio
    box_part("G-before", "grass", node_props(E("G-before")), -10, 10, -1.2, 0, -9, 12, BOTH)
    gd = box_part("G-dug", "grass", node_props(E("G-dug")), -10, 10, -1.2, 0, -9, 12)
    DE = 0.005     # the dig is 5 mm bigger than the concrete in it: no shared faces, so the section caps cannot z-fight
    cut = bmesh.new()
    add_box(cut, xo0 + 0.0, xo1 - 0.0, -0.267, 0.5, 0.0, zo1 - 0.0)                       # reduced dig under the slab
    for (x0, x1, z0, z1) in ((xo0 - 0.15, xo0 + T + 0.15, 0, zo1 + 0.15), (xo1 - T - 0.15, xo1 + 0.15, 0, zo1 + 0.15),
                             (xo0 - 0.15, xo1 + 0.15, zo1 - T - 0.15, zo1 + 0.15)):
        add_box(cut, x0 - DE, x1 + DE, -1.0 - DE, 0.5, z0 - DE, z1 + DE)                          # trenches 600 wide
    add_box(cut, -1.1 - DE, 1.1 + DE, -1.0 - DE, 0.5, -6.55 - DE, -5.0 + DE)                       # porch trench (shown as one dig)
    cutter = add_part("cutter", finish_mesh(cut, "cutter"), IDENT, "earth", {}, ())
    mod = gd.modifiers.new("dig", "BOOLEAN"); mod.operation = "DIFFERENCE"; mod.object = cutter
    try: mod.solver = "EXACT"
    except Exception: pass
    try: mod.use_self = True              # the cutter's boxes overlap each other
    except Exception: pass
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    gd.data = bpy.data.meshes.new_from_object(gd.evaluated_get(dg))
    print(f"fixture: dug ground {len(gd.data.vertices)} verts, {len(gd.data.polygons)} faces")
    assert len(gd.data.polygons) > 6, "boolean dig failed"
    gd.modifiers.clear()
    gd.data.materials.clear(); gd.data.materials.append(MAT["grass"])
    PARTS[:] = [(o, v) for o, v in PARTS if o is not cutter]
    bpy.data.objects.remove(cutter)
    box_part("P-patio", "paving", node_props(E("P-patio")), -2.6, 2.2, 0.0, 0.05, 0.0, 2.4, BOTH)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=1.1, radius2=0.25, depth=0.9,
                          matrix=Matrix.Translation((0, 0, 0)))
    for v in bm.verts:
        v.co = Vector((v.co.x, v.co.z + 0.45, v.co.y))        # cone along local y (up)
    add_part("SP-1", finish_mesh(bm, "SP-1"), (Vector((4.2, 0, 6.5)), Vector((1, 0, 0)), UP, Vector((0, 0, 1))), "earth",
             node_props(E("SP-1")))
    bm = bmesh.new()
    for (x, z) in ((xo0 - 0.8, -0.3), (xo0 - 0.8, zo1 + 0.8), (xo1 + 0.8, zo1 + 0.8), (xo1 + 0.8, -0.3)):
        add_box(bm, x - 0.03, x + 0.03, 0, 0.6, z - 0.03, z + 0.03)
    add_box(bm, xo0 - 0.8, xo1 + 0.8, 0.5, 0.51, zo1 + 0.79, zo1 + 0.81)
    add_box(bm, xo0 - 0.81, xo0 - 0.79, 0.5, 0.51, -0.3, zo1 + 0.8)
    add_box(bm, xo1 + 0.79, xo1 + 0.81, 0.5, 0.51, -0.3, zo1 + 0.8)
    add_part("SO-pegs", finish_mesh(bm, "SO-pegs"), IDENT, "timber_temp", node_props(E("SO-pegs")))

    # ---- demolished panel + step
    box_part("D-rear-panel", "existing_brick", node_props(E("D-rear-panel")), -1.6, 1.2, 0.0, 2.45, -0.3, 0.0, BOTH)
    box_part("PR-1", "paving", node_props(E("PR-1")), -0.6, 0.4, 0.0, 0.15, 0.0, 0.35, BOTH)

    # ---- existing slab, deck with stairwell, roof, gables
    box_part("X-slab", "existing_floor", node_props(E("X-slab")), -2.7, 2.7, 0.0, 0.15, -4.7, -0.3, BOTH)
    bm = bmesh.new()
    add_box(bm, -2.7, 1.8, 2.75, FFL1, -4.7, -0.3)
    add_box(bm, 1.8, 2.7, 2.75, FFL1, -4.7, -3.3)
    add_part("X-deck", finish_mesh(bm, "X-deck"), IDENT, "existing_floor", node_props(E("X-deck")), BOTH)
    pitch = math.radians(40); rise = 3.2 * math.tan(pitch)
    bm = bmesh.new()
    for s in (-1, 1):
        n = Vector((s * math.sin(pitch), math.cos(pitch), 0))
        pts = [(s * 3.2, 5.3 - 0.2 * math.tan(pitch), 0.15), (s * 3.2, 5.3 - 0.2 * math.tan(pitch), -5.2), (0, 5.3 + rise - 0.2 * math.tan(pitch), -5.2),
               (0, 5.3 + rise - 0.2 * math.tan(pitch), 0.15)]
        add_slab(bm, pts, n, 0.0, 0.12)
    add_part("X-roof", finish_mesh(bm, "X-roof"), IDENT, "existing_tile", node_props(E("X-roof")), BOTH)
    bm = bmesh.new()
    grise = 3.0 * math.tan(pitch)
    for z0, z1 in ((-0.3, 0.0), (-5.0, -4.7)):
        lo = [(-3.0, z0), (3.0, z0)]
        pts = [Vector((-3.0, 5.3, z0)), Vector((3.0, 5.3, z0)), Vector((0, 5.3 + grise, z0))]
        add_slab(bm, pts, Vector((0, 0, 1)), 0.0, z1 - z0)
    add_part("X-gables", finish_mesh(bm, "X-gables"), IDENT, "existing_brick", node_props(E("X-gables")), BOTH)

    # ---- stair: one mesh of 13 steps
    s = E("S-X-1")["params"]
    bm = bmesh.new()
    for k in range(s["risers"]):
        z_hi = s["start"][1] - k * s["going"]
        y1 = s["base"] + (k + 1) * s["rise"]
        z_lo = z_hi - s["going"] - (0.0 if k < s["risers"] - 1 else 0.0)
        if k == s["risers"] - 1:
            break                                   # the top riser lands on the deck
        add_box(bm, s["start"][0] - s["width"] / 2, s["start"][0] + s["width"] / 2, max(0.0, y1 - 0.25), y1, z_lo, z_hi)
    add_part("S-X-1", finish_mesh(bm, "S-X-1"), IDENT, "stair", node_props(E("S-X-1")), BOTH)

    # ---- temporary works
    nd = E("TW-needles")
    nd["params"] = {"length": 1.6, "width": 0.152, "depth": 0.152, "material": "timber_temp",
                    "_frames": [(Vector((x, 2.70, -0.95)), Vector((0, 0, 1)), UP, Vector((-1, 0, 0))) for x in (-0.8, 0.4)]}
    # local X along z (through the wall), local Y up, local Z = X x Y
    build_member_set(nd, ("today",))
    pr = E("TW-props")
    pr["params"] = {"length": 2.62, "width": 0.06, "depth": 0.06, "material": "prop_steel",
                    "_frames": [(Vector((x, y0, z)), UP, Vector((-1, 0, 0)), Vector((0, 0, 1)))
                                for x in (-0.8, 0.4) for (z, y0) in ((-0.8, 0.0), (0.5, 0.0))]}
    build_member_set(pr, ("today",))

    # ---- foundations + drain
    for eid, (x0, x1, z0, z1) in (("FD-L", (xo0 - 0.15, xo0 + T + 0.15, 0, zo1 + 0.15)),
                                   ("FD-R", (xo1 - T - 0.15, xo1 + 0.15, 0, zo1 + 0.15)),
                                   ("FD-G", (xo0 + T + 0.15, xo1 - T - 0.15, zo1 - T - 0.15, zo1 + 0.15)),
                                   ("FD-P", (-1.1, 1.1, -6.55, -5.0))):
        box_part(eid, "concrete", node_props(E(eid)), x0, x1, -1.0, -0.15, z0, z1)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.055, radius2=0.055, depth=4.6)
    me = finish_mesh(bm, "DR-1")
    add_part("DR-1", me, (Vector((0.9, -0.62, 2.6)), Vector((1, 0, 0)), UP, Vector((0, 0, 1))), "pvc_drain",
             node_props(E("DR-1")))
    box_part("DR-IC", "pvc_drain", node_props(E("DR-IC")), 0.675, 1.125, -0.75, 0.0, 5.0, 5.45)

    # ---- slab layers (inside the walls' inner faces; porch slab as part of the concrete)
    sx0, sx1, sz0, sz1 = xo0 + T, xo1 - T, 0.0, zo1 - T
    layers = {"SL-hardcore": (-0.267, -0.117), "SL-dpm": (-0.117, -0.115), "SL-ins": (-0.115, -0.015),
              "SL-mesh": (0.025, 0.031), "SL-conc": (-0.015, 0.085), "SC-1": (0.085, 0.15)}
    for eid, (y0, y1) in layers.items():
        mat = E(eid)["params"].get("material", "screed")
        bm = bmesh.new(); add_box(bm, sx0, sx1, y0, y1, sz0, sz1)
        add_box(bm, -0.95 + g["pT"], 0.95 - g["pT"], y0, y1, -6.4 + g["pT"], -5.0)
        add_part(eid, finish_mesh(bm, eid), IDENT, mat, node_props(E(eid)))

    # ---- steel beam: an I-section with the 8mm plate below
    b = E("B-5")["params"]
    bm = bmesh.new()
    L = b["end"][0] - b["start"][0]; D = b["depth"]; B = b["width"]; tf, tw = 0.0108, 0.0054
    add_box(bm, 0, L, 0.008, 0.008 + tf, -B / 2, B / 2)
    add_box(bm, 0, L, 0.008 + D - tf, 0.008 + D, -B / 2, B / 2)
    add_box(bm, 0, L, 0.008 + tf, 0.008 + D - tf, -tw / 2, tw / 2)
    add_box(bm, 0, L, 0.0, 0.008, -0.125, 0.125)                    # plate carries the outer leaf
    add_part("B-5", finish_mesh(bm, "B-5"), (Vector((b["start"][0], b["base"] - 0.008, b["start"][1])), Vector((1, 0, 0)), UP,
                                              Vector((0, 0, 1))), "steel", node_props(E("B-5")))

    # ---- joists (10, linked duplicates) + deck
    j = E("J-ff")
    j["params"]["_frames"] = [(Vector((g["jx0"], 2.75 + 0.0975, 0.2 + i * 0.4)), Vector((1, 0, 0)), UP, Vector((0, 0, 1))) for i in range(10)]
    build_member_set(j, ("today",))
    box_part("DK-ff", "chipboard", node_props(E("DK-ff")), xo0 + T, xo1 - T, 2.945, FFL1, 0.0, zo1 - T)

    # ---- roof: wall plate, ridge, 8 commons, 2 hips, ceiling joists, felt, tiles
    yp = 5.30; pit = math.radians(35); xc = (xo0 + xo1) / 2; half = (xo1 - xo0) / 2
    yr = yp + 0.05 + half * math.tan(pit); zr = zo1 - half                   # ridge height and hip end of the ridge
    bm = bmesh.new()
    add_box(bm, xo0 + 0.2, xo0 + 0.3, yp, yp + 0.05, 0, zo1 - 0.2)
    add_box(bm, xo1 - 0.3, xo1 - 0.2, yp, yp + 0.05, 0, zo1 - 0.2)
    add_box(bm, xo0 + 0.2, xo1 - 0.2, yp, yp + 0.05, zo1 - 0.3, zo1 - 0.2)
    add_part("WP-1", finish_mesh(bm, "WP-1"), IDENT, "timber", node_props(E("WP-1")))
    box_part("RB-1", "timber", node_props(E("RB-1")), xc - 0.0235, xc + 0.0235, yr - 0.12, yr + 0.08, 0.0, zr)
    rl = half / math.cos(pit)
    up_s = Vector((math.cos(pit), math.sin(pit), 0))        # left side: up the slope towards the ridge (+x)
    rf = E("RF-com")
    frames = []
    for zz in (0.3, 0.7, 1.1, 1.5):
        frames.append((Vector((xo0, yp + 0.05 + 0.075, zz)), up_s, Vector((-math.sin(pit), math.cos(pit), 0)), Vector((0, 0, 1))))
    up_r = Vector((-math.cos(pit), math.sin(pit), 0))
    for zz in (0.3, 0.7, 1.1, 1.5):
        frames.append((Vector((xo1, yp + 0.05 + 0.075, zz)), up_r, Vector((math.sin(pit), math.cos(pit), 0)), Vector((0, 0, -1))))
    rf["params"].update({"length": rl, "_frames": frames, "count": 8, "spacing": 0.4})
    build_member_set(rf, ("today",))
    hp = E("RF-hip")
    hip_frames = []
    for cx in (xo0, xo1):
        a = Vector((cx, yp + 0.05 + 0.1, zo1)); bpt = Vector((xc, yr, zr))
        U = (bpt - a); hl = U.length; U.normalize()
        Vh = Vector((U.z, 0, -U.x)).normalized()            # horizontal, square to the hip
        Wd = Vh.cross(U)                                      # so (U, Wd, Vh) is right-handed: U x Wd = Vh
        if Wd.y < 0:
            Vh = -Vh; Wd = Vh.cross(U)
        hip_frames.append((a, U, Wd, U.cross(Wd)))
    hp["params"].update({"length": hl, "_frames": hip_frames})
    build_member_set(hp, ("today",))
    cj = E("CJ-1")
    cj["params"].update({"length": (xo1 - xo0) - 0.4, "_frames": [(Vector((xo0 + 0.2, yp + 0.1, z)), Vector((1, 0, 0)), UP, Vector((0, 0, 1)))
                                                                for z in (0.5, 1.3, 2.1, 2.9)]})
    build_member_set(cj, ("today",))
    # roof planes on top of the rafters
    yt = yp + 0.05 + 0.075 / math.cos(pit) + 0.0                 # top of rafter line at the outer wall face
    ov = 0.3                                                      # eaves overhang
    eL = Vector((xo0 - ov, yt - ov * math.tan(pit), 0)); eL2 = Vector((xo0 - ov, yt - ov * math.tan(pit), zo1 + ov))
    eR = Vector((xo1 + ov, yt - ov * math.tan(pit), 0)); eR2 = Vector((xo1 + ov, yt - ov * math.tan(pit), zo1 + ov))
    rtop = Vector((xc, yt + half * math.tan(pit), 0)); rend = Vector((xc, yt + half * math.tan(pit), zr))
    planes = [([eL, eL2, rend, rtop], Vector((-math.sin(pit), math.cos(pit), 0))),
              ([eR, rtop, rend, eR2], Vector((math.sin(pit), math.cos(pit), 0))),
              ([eL2, eR2, rend], Vector((0, math.cos(pit), math.sin(pit))))]
    for eid, mat, t0, t1 in (("RL-felt", "felt", 0.0, 0.004), ("RC-tiles", "tile", 0.03, 0.065)):
        bm = bmesh.new()
        for pts, n in planes:
            add_slab(bm, pts, n, t0, t1)
        add_part(eid, finish_mesh(bm, eid), IDENT, mat, node_props(E(eid)))
    bm = bmesh.new()
    pts = [Vector((-1.1, 2.75, -6.7)), Vector((1.1, 2.75, -6.7)), Vector((1.1, 3.2, -5.0)), Vector((-1.1, 3.2, -5.0))]
    nn = (pts[1] - pts[0]).cross(pts[3] - pts[0]).normalized()
    if nn.y < 0: nn = -nn
    add_slab(bm, pts, nn, 0.0, 0.08)
    add_part("RC-porch", finish_mesh(bm, "RC-porch"), IDENT, "tile", node_props(E("RC-porch")))

    # ---- kitchen units
    bm = bmesh.new()
    add_box(bm, xo0 + T, xo0 + T + 0.6, 0.15, 0.97, 0.6, 3.2)
    add_part("K-units_carcass", finish_mesh(bm, "K-units_carcass"), IDENT, "unit", node_props(E("K-units"), part="carcass"))
    bm = bmesh.new()
    add_box(bm, xo0 + T, xo0 + T + 0.62, 0.97, 1.0, 0.6, 3.2)
    add_part("K-units_top", finish_mesh(bm, "K-units_top"), IDENT, "worktop", node_props(E("K-units"), part="worktop"))


# ---------------------------------------------------------------- sidecars
STAGES = [
    ("House before", "Survey the house as it stands; record existing services, levels and the drain runs.",
     "This is your house as it is today, before any work starts."),
    ("Strip-out and demolition, temporary props", "Needles and Acrow props in BEFORE the rear wall comes out; lift the patio and step.",
     "Temporary timbers and steel props go in to hold the house up, then the part of the back wall where the new opening goes is carefully taken down. The old patio comes up."),
    ("Setting out and trench dig", "Set out from the existing house; dig trenches 600 wide to 1000 min, BCO to inspect before concrete.",
     "The builder marks out exactly where the new walls go and digs the trenches for the foundations. Building Control checks the trenches."),
    ("Trench-fill foundations and drains", "Pour trench fill to 150 below GL; lay 110 foul drain at 1:40 to the new IC.",
     "Concrete is poured into the trenches to make the foundations, and the new drains are laid."),
    ("Slab: hardcore, DPM, insulation, mesh, concrete", "Compact hardcore, blind, DPM taped, PIR with perimeter upstand, A142 mesh, pour.",
     "The new floor is built up in layers: compacted stone, a damp-proof sheet, insulation, steel mesh and concrete."),
    ("Walls to first floor with lintels", "Raise both leaves together, ties at 900x450, lintel over the bifold opening at 2250.",
     "The new cavity walls go up to first-floor level, with a steel lintel over the opening for the garden doors."),
    ("Steel beams in", "Beam 5 on padstones; dry-pack, then strike the props once the engineer is happy.",
     "Stage 7 – steel beams: the back wall of the house now has a big opening, so a steel beam is lifted in to carry the bedroom floor and brickwork above. The temporary props held it up meanwhile and now come out."),
    ("First-floor joists and deck", "47x195 at 400 into hangers, noggins at mid-span, 22mm chipboard deck glued and screwed.",
     "The timber joists for the new bedroom floor go in, one by one, and are boarded over."),
    ("Walls to plate, porch walls", "Raise first storey to plate height, window lintel at 4950; build the porch walls.",
     "The walls go up to the roof line, including the bedroom window opening. The new porch walls at the front are built."),
    ("Roof structure", "Wall plate strapped, ridge, commons at 400, hips, ceiling joists.",
     "The timber roof frame goes on: rafters, the ridge at the top and the hips at the corners."),
    ("Felt, battens, tiles, windows, doors", "Membrane and battens, tile to match; windows and doors in; the extension is weathertight.",
     "The roof is felted and tiled, and the windows and doors go in. Now the extension is weathertight."),
    ("Finished", "Plasterboard and skim, screed with UFH, kitchen fit; spoil cleared.",
     "Inside is plastered, the floor screeded and the kitchen fitted. The finished extension."),
]


def sidecar(version, label, stages, g):
    st = [{"n": i + 1, "name": n, "note": b, "customer_note": c} for i, (n, b, c) in enumerate(stages)]
    return {
        "contract": 1, "version": version, "label": label, "units": "m",
        "frame": "viewer (glTF): +Y up, metres; Blender (x, y, z) -> viewer (x, z, -y)",
        "stages": st,
        "sections": [   # normal points to the part that is KEPT (the direction you look in the drawing)
            {"name": "A-A", "origin": [0, 0, 2.0], "normal": [0, 0, -1], "drawing": DRW_SA,
             "note": "Across the extension, looking back at the house"},
            {"name": "B-B", "origin": [-0.2, 0, 0], "normal": [1, 0, 0], "drawing": DRW_SB,
             "note": "Through the ridge and the bifold door, looking right"},
            {"name": "C-C", "origin": [0, 0, -0.15], "normal": [0, 0, 1], "drawing": "4915.3B section C-C",
             "note": "Along the existing rear wall: beam 5, props"},
            {"name": "D-D", "origin": [1.84, 0, 0], "normal": [-1, 0, 0], "drawing": "4915.3B section D-D",
             "note": "Through the right wall and the bedroom window"},
            {"name": "E-E", "origin": [0, 0, 3.84], "normal": [0, 0, -1], "drawing": "4915.3B section E-E",
             "note": "Through the garden wall: bifold lintel, trench fill"},
        ],
        "spawns": [
            {"name": "Front door", "position": [0.0, 0.0, -10.0], "yawDeg": 180},
            {"name": "Garden", "position": [0.0, 0.0, 8.5], "yawDeg": 0},
            {"name": "First floor landing", "position": [0.0, g["FFL1"], -2.0], "yawDeg": 0},
        ],
        "storeys": {"site": 0.0, "ground": 0.15, "first": g["FFL1"], "roof": 5.3},
    }


def write_versions(g):
    bpy.ops.object.select_all(action="DESELECT")
    versions = [("today", "Extension (proposal)"), ("before", "Before the works")]
    for v, label in versions:
        keep = [o for o, vs in PARTS if v in vs]
        for o, vs in PARTS:
            o.hide_set(False)
            o.select_set(o in keep)
        if v == "before":       # nothing is removed or added in the before state
            for o in keep:
                for k in ("stage_out", "seq_out"):
                    if k in o: del o[k]
                o["stage_in"] = 1; o["seq"] = 0.0
        path = os.path.join(OUT, f"house_{v}.glb")
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_extras=True,
                                  export_yup=True, export_apply=False, export_cameras=False, export_lights=False,
                                  export_materials="EXPORT")
        stages = STAGES if v == "today" else [("House before the works", "The house as surveyed.", "Your house as it is today.")]
        with open(os.path.join(OUT, f"house_{v}.json"), "w") as f:
            json.dump(sidecar(v, label, stages, g), f, indent=1)
        els = []
        for e in ELEMENTS:
            if v not in e["_versions"]:
                continue
            e2 = {k: copy.deepcopy(x) for k, x in e.items() if not k.startswith("_")}
            e2["params"] = {k: x for k, x in e2["params"].items() if not k.startswith("_")}
            if v == "before":
                e2["meta"] = dict(e2["meta"]); e2["meta"].update(stage_in=1, stage_out=None, seq=0.0, seq_out=None)
                e2["openings"] = [o for o in e2.get("openings", []) if v in EL[o]["_versions"]] if "openings" in e2 else None
                if e2["openings"] is None: del e2["openings"]
            els.append(e2)
        with open(os.path.join(OUT, f"house_{v}_elements.json"), "w") as f:
            json.dump({"contract": 1, "version": v, "frame": "viewer", "elements": els}, f, indent=1)
        print(f"fixture: {v}: {len(keep)} nodes -> {path}")
    desc = {"before": ("existing", None, "The fixture house as surveyed: nothing proposed."),
            "today": ("proposal", "before", "Two-storey rear extension with porch, built over 12 stages (fixture, not a real scheme).")}
    with open(os.path.join(OUT, "versions.json"), "w") as f:
        json.dump({"contract": 1, "name": "Test house (fixture)", "as_built_now": "before", "default": "today",
                   "versions": [{"id": v, "name": l, "description": desc[v][2], "kind": desc[v][0], "base": desc[v][1],
                                 "glb": f"house_{v}.glb", "elements": f"house_{v}_elements.json", "stages": f"house_{v}.json"}
                                for v, l in versions]}, f, indent=1)


bpy.ops.wm.read_factory_settings(use_empty=True)
coll = bpy.context.scene.collection
MAT = make_materials()
g = define()
build(g)
write_versions(g)
print("fixture: done")
