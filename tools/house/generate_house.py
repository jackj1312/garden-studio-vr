"""Generate a house as walkable, staged 3D models from traced architect drawings (src/house/CONTRACT.md).

    nice -n 10 /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/house/generate_house.py -- \
        --data <house_drawn.json> --spec <build_versions.json> --out assets/sites/<site> [--versions a,b] [--no-check]

Generic: every house fact comes from the traced drawings (house_drawn.json, tools/plan/trace_drawing.py format) and the
version spec (versions, packages, roof wings, temporary works, stage notes). Per version it writes <id>.glb,
<id>_elements.json, <id>.json (stages sidecar) and versions.json, plus <id>_check.json (supports and clashes per
stage). Light work only: no render, no bake (8 GB Mac)."""
import sys, os, json, math, time, argparse, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import numpy as np

import hb_geom as G
from hb_build import StateBuilder, atom, M, sig_of, slug, TYPICAL, val
import hb_stage as S
import hb_roof as R
from hb_walls import resolve_joins
import hb_details as HD
import hb_asbuilt as AB

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--tex", default=os.path.join(os.path.dirname(HERE), "..", "master", "phototex", "house"))
ap.add_argument("--spec-v1", default=os.path.join(os.path.dirname(HERE), "..", "assets", "sites", "house", "spec", "spec_v1.json"))
ap.add_argument("--spec-tex", default=os.path.join(os.path.dirname(HERE), "..", "master", "phototex", "spec"))
ap.add_argument("--polyhaven", default=os.path.join(os.path.dirname(HERE), "..", "master", "polyhaven"))
ap.add_argument("--no-items", action="store_true", help="leave out the signed spec's interior (items, floor finishes, skirting)")
ap.add_argument("--versions", default=""); ap.add_argument("--no-check", action="store_true"); ap.add_argument("--blend", default="")
args = ap.parse_args(argv)
DATA = json.load(open(args.data)); SPEC = json.load(open(args.spec))


def resolve(o, defs, depth=0):
    """'@name' / '@name.key.0' references into spec['defs']; a reference to a list inside a list is spliced in"""
    if depth > 20: raise ValueError("reference loop")
    if isinstance(o, str) and o.startswith("@"):
        path = o[1:].split(".")
        v = defs[path[0]]
        for k in path[1:]: v = v[int(k)] if isinstance(v, list) else v[k]
        return resolve(v, defs, depth + 1)
    if isinstance(o, list):
        out = []
        for x in o:
            r = resolve(x, defs, depth + 1)
            if isinstance(x, str) and x.startswith("@") and isinstance(r, list): out.extend(r)
            else: out.append(r)
        return out
    if isinstance(o, dict):
        return {k: resolve(v, defs, depth + 1) for k, v in o.items()}
    return o


SPEC["versions"] = resolve(SPEC["versions"], SPEC.get("defs", {}))
OUT = os.path.abspath(args.out); os.makedirs(OUT, exist_ok=True)
T0 = time.time()
def log(*a): print(f"[house {time.time() - T0:6.1f}s]", *a, flush=True)


# ======================================================================================== materials and textures
MATS = {  # name: (sRGB, roughness, metallic, alpha, texture)
    "brick": ((0.66, 0.36, 0.25), 0.85, 0, 1, "brick"), "existing_brick": ((0.58, 0.38, 0.30), 0.9, 0, 1, "brick"),
    "block": ((0.80, 0.80, 0.77), 0.9, 0, 1, "block"), "pir": ((0.85, 0.85, 0.82), 0.4, 0.3, 1, None),
    "mineral_wool": ((0.93, 0.80, 0.35), 1.0, 0, 1, None), "plasterboard": ((0.94, 0.93, 0.90), 0.8, 0, 1, None),
    "plaster": ((0.90, 0.88, 0.84), 0.85, 0, 1, None), "concrete": ((0.63, 0.63, 0.61), 0.95, 0, 1, None),
    "hardcore": ((0.52, 0.49, 0.45), 1.0, 0, 1, None), "dpm": ((0.10, 0.11, 0.13), 0.4, 0, 1, None),
    "vcl": ((0.70, 0.78, 0.82), 0.3, 0, 1, None), "rebar": ((0.36, 0.22, 0.16), 0.6, 0.6, 1, None),
    "screed": ((0.78, 0.76, 0.72), 0.9, 0, 1, None), "floor_finish": ((0.72, 0.60, 0.45), 0.7, 0, 1, None),
    "steel": ((0.55, 0.20, 0.14), 0.6, 0.3, 1, None), "timber": ((0.85, 0.70, 0.46), 0.8, 0, 1, None),
    "timber_existing": ((0.62, 0.50, 0.36), 0.85, 0, 1, None), "chipboard": ((0.80, 0.68, 0.50), 0.85, 0, 1, None),
    "membrane": ((0.82, 0.86, 0.92), 0.5, 0, 1, None), "batten": ((0.55, 0.62, 0.42), 0.8, 0, 1, None),
    "tile": ((0.45, 0.25, 0.20), 0.75, 0, 1, "tile"), "existing_tile": ((0.36, 0.27, 0.24), 0.8, 0, 1, "tile"),
    "lead": ((0.50, 0.52, 0.54), 0.5, 0.5, 1, None), "upvc_white": ((0.95, 0.95, 0.94), 0.35, 0, 1, None),
    "black_upvc": ((0.08, 0.08, 0.09), 0.4, 0, 1, None), "glass": ((0.72, 0.84, 0.90), 0.05, 0, 0.3, None),
    "aluminium": ((0.24, 0.25, 0.27), 0.35, 0.6, 1, None), "door_leaf": ((0.92, 0.91, 0.88), 0.5, 0, 1, None),
    "trim": ((0.93, 0.92, 0.89), 0.45, 0, 1, None), "wboard": ((0.95, 0.94, 0.92), 0.4, 0, 1, None),
    "ironmongery": ((0.03, 0.03, 0.03), 0.45, 0.8, 1, None),
    "joinery": ((0.92, 0.91, 0.88), 0.5, 0, 1, None), "sanitary": ((0.97, 0.97, 0.97), 0.15, 0, 1, None),
    "lintel_galv": ((0.68, 0.70, 0.72), 0.4, 0.8, 1, None), "prop_steel": ((0.92, 0.55, 0.10), 0.5, 0.4, 1, None),
    "timber_temp": ((0.90, 0.78, 0.45), 0.8, 0, 1, None), "scaffold": ((0.70, 0.72, 0.74), 0.4, 0.8, 1, None),
    "scaffold_board": ((0.80, 0.66, 0.40), 0.8, 0, 1, None), "earth": ((0.40, 0.30, 0.20), 1.0, 0, 1, None),
    "ground": ((0.36, 0.45, 0.25), 1.0, 0, 1, None), "existing_floor": ((0.70, 0.62, 0.52), 0.85, 0, 1, None),
    "stair": ((0.72, 0.58, 0.40), 0.7, 0, 1, None), "felt": ((0.15, 0.15, 0.16), 0.7, 0, 1, None),
    "multiwall_skin": ((0.95,0.96,0.94),.14,0,.16,None), "multiwall_web": ((0.91,0.94,0.92),.20,0,.20,None),
    "polycarbonate": ((0.85, 0.88, 0.90), 0.2, 0, 0.5, None), "velux": ((0.25, 0.27, 0.28), 0.4, 0.2, 1, None),
    "existing_partition": ((0.88, 0.86, 0.82), 0.85, 0, 1, None),
}
TEX = {"brick": (0.900, 0.900), "block": (0.900, 0.900), "tile": (0.660, 0.600)}


def srgb_lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_texture(kind, base, size=512):
    """true-scale course lines: brick 215x65 + 10 joints (stretcher bond), block 440x215 + 10, plain tile 165 x 100 gauge"""
    W = H = size
    img = np.zeros((H, W, 4), np.float32)
    col = np.array([*base, 1.0], np.float32)
    mortar = np.array([0.80, 0.78, 0.72, 1.0], np.float32) if kind != "tile" else np.array([*(c * 0.55 for c in base), 1.0], np.float32)
    sx, sy = TEX[kind]
    if kind == "brick": uw, uh, j = 0.225, 0.075, 0.010
    elif kind == "block": uw, uh, j = 0.450, 0.225, 0.010
    else: uw, uh, j = 0.165, 0.100, 0.006
    ys = (np.arange(H) + 0.5) / H * sy; xs = (np.arange(W) + 0.5) / W * sx
    X, Y = np.meshgrid(xs, ys)
    row = np.floor(Y / uh)
    off = (row % 2) * uw / 2
    xm = np.mod(X + off, uw); ym = np.mod(Y, uh)
    joint = (xm < j) | (ym < j)
    rng = np.random.default_rng(3)
    unit_id = (np.floor((X + off) / uw) * 131 + row * 17).astype(np.int64)
    var = (np.sin(unit_id * 12.9898) * 43758.5453) % 1.0
    shade = 0.88 + 0.22 * var
    img[...] = col
    img[..., :3] *= shade[..., None]
    if kind == "tile":
        img[..., :3] *= (0.85 + 0.15 * (ym / uh))[..., None]      # each course darker at its tail
    img[joint] = mortar
    img[..., :3] = np.clip(img[..., :3], 0, 1)
    lin = np.vectorize(srgb_lin)
    im = bpy.data.images.new(f"tex_{kind}_{int(base[0]*100)}", W, H, alpha=False)
    im.pixels.foreach_set(np.flipud(img).ravel())
    im.pack()
    return im


TEXSET = {  # material -> texture set (make_textures.py); materials missing here fall back to their flat colour
    "brick": "brick_new", "existing_brick": "brick_existing", "brick_porch": "brick_porch", "block": "block", "pir": "pir",
    "mineral_wool": "mineral_wool", "plasterboard": "plasterboard", "plaster": "plaster", "concrete": "concrete", "hardcore": "hardcore",
    "dpm": "dpm", "vcl": "vcl", "rebar": "rebar", "screed": "screed", "floor_finish": "floor_finish", "steel": "steel", "timber": "timber",
    "timber_existing": "timber_existing", "chipboard": "chipboard", "membrane": "membrane", "batten": "batten", "tile": "tile_new",
    "existing_tile": "tile_existing", "lead": "lead", "upvc_white": "upvc_white", "black_upvc": "black_upvc", "aluminium": "aluminium",
    "door_leaf": "door_leaf", "joinery": "joinery", "sanitary": "sanitary", "lintel_galv": "lintel_galv", "prop_steel": "prop_steel",
    "timber_temp": "timber_temp", "scaffold": "scaffold", "scaffold_board": "timber_existing", "earth": "earth", "existing_floor": "existing_floor",
    "stair": "stair", "felt": "felt", "velux": "velux", "existing_partition": "existing_partition",
    "ground_paving": "ground_paving", "ground_lawn": "ground_lawn", "ground_gravel": "ground_gravel",
    "fence_board": "fence_board", "road": "road", "closeboard": "closeboard", "pvc_drain": "pvc_drain", "heras": "heras", "skip_steel": "skip_steel",
    "tarp": "tarp", "pallet": "pallet", "tote": "tote", "cabin": "cabin",
}
MATS.update({"anthracite_upvc": ((0.21, 0.23, 0.25), 0.4, 0, 1, None), "cream_stone": ((0.66, 0.62, 0.56), 0.85, 0, 1, None),
             "buff_concrete": ((0.58, 0.57, 0.53), 0.9, 0, 1, None), "packer": ((0.45, 0.33, 0.26), 0.7, 0, 1, None),
             "soldier_brick": ((0.6, 0.4, 0.32), 0.85, 0, 1, None), "black_metal": ((0.05, 0.05, 0.055), 0.45, 0.5, 1, None),
             "mirror": ((0.90, 0.92, 0.93), 0.03, 1.0, 1, None), "dish": ((0.74, 0.75, 0.76), 0.4, 0.2, 1, None),
             "slate": ((0.52, 0.53, 0.53), 0.3, 0, 1, None)})
TEXSET.update({"anthracite_upvc": "anthracite_upvc", "cream_stone": "cream_stone", "buff_concrete": "buff_concrete", "packer": "packer",
               "soldier_brick": "brick_soldier", "black_metal": "black_metal", "dish": "dish", "slate": "slate"})
MATS.update({"brick_porch": ((0.70, 0.40, 0.28), 0.85, 0, 1, None), "ground_paving": ((0.6, 0.5, 0.45), 0.85, 0, 1, None),
             "ground_lawn": ((0.35, 0.42, 0.2), 0.95, 0, 1, None), "ground_gravel": ((0.55, 0.5, 0.46), 0.9, 0, 1, None),
             "fence_board": ((0.55, 0.45, 0.35), 0.9, 0, 1, None), "road": ((0.25, 0.25, 0.26), 0.9, 0, 1, None),
             "closeboard": ((0.55, 0.47, 0.38), 0.9, 0, 1, None), "pvc_drain": ((0.72, 0.38, 0.18), 0.5, 0, 1, None),
             "heras": ((0.75, 0.77, 0.78), 0.4, 0.7, 1, None), "skip_steel": ((0.85, 0.55, 0.10), 0.6, 0.3, 1, None),
             "tarp": ((0.20, 0.35, 0.65), 0.6, 0, 1, None), "pallet": ((0.70, 0.58, 0.40), 0.85, 0, 1, None),
             "tote": ((0.88, 0.86, 0.80), 0.8, 0, 1, None), "cabin": ((0.85, 0.86, 0.84), 0.5, 0.1, 1, None)})
TMETA = {}
TILE = {}


def gltf_output_group():
    ng = bpy.data.node_groups.get("glTF Material Output")
    if ng: return ng
    ng = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    try:
        ng.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    except Exception:
        ng.inputs.new("NodeSocketFloat", "Occlusion")
    ng.nodes.new("NodeGroupInput")
    return ng


def img(path, noncolor):
    im = bpy.data.images.load(path, check_existing=True)
    if noncolor: im.colorspace_settings.name = "Non-Color"
    return im


# Quest draw calls (one batch per material): small or look-alike materials share one (round 6: 92 -> ~60 batches at the
# finished stage with the garden). The part keeps its own name in the contract; only the GLB material is shared.
ALIAS = {"slate": "black_metal", "velux": "anthracite_upvc", "vcl": "membrane", "floor_finish": "existing_floor",
         "existing_partition": "plaster", "stair": "timber_existing", "lead": "aluminium", "sanitary": "upvc_white",
         "batten": "timber", "timber_temp": "timber", "scaffold_board": "timber_existing", "pallet": "timber_existing",
         "tote": "cabin", "skip_steel": "prop_steel", "pvc_drain": "prop_steel", "felt": "black_upvc", "packer": "buff_concrete",
         "dish": "upvc_white", "polycarbonate": "glass", "door_leaf": "joinery", "fence_board": "closeboard"}


def make_materials():
    global TMETA
    mp = os.path.join(args.tex, "tex_meta.json")
    TMETA = json.load(open(mp)) if os.path.exists(mp) else {}
    if not TMETA: log("WARNING: no texture sets at", args.tex, "- flat colours only (run make_textures.py)")
    out = {}
    for name, (col, rough, metal, alpha, tex) in MATS.items():
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Base Color"].default_value = (*[srgb_lin(c) for c in col], 1)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        ts = TEXSET.get(name)
        tm = TMETA.get(ts) if ts else None
        TILE[name] = tuple(tm["tile"]) if tm else (1.0, 1.0)
        if tm:
            f = tm["files"]
            tc = nt.nodes.new("ShaderNodeTexImage"); tc.image = img(os.path.join(args.tex, f["col"]), False)
            nt.links.new(tc.outputs["Color"], bsdf.inputs["Base Color"])
            if tm.get("alpha"):
                rnd = nt.nodes.new("ShaderNodeMath"); rnd.operation = "ROUND"
                nt.links.new(tc.outputs["Alpha"], rnd.inputs[0]); nt.links.new(rnd.outputs[0], bsdf.inputs["Alpha"])
                try: m.surface_render_method = "DITHERED"
                except Exception: m.blend_method = "CLIP"
            if "nrm" in f:
                tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = img(os.path.join(args.tex, f["nrm"]), True)
                nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 1.0
                nt.links.new(tn.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
            if "orm" in f:
                to = nt.nodes.new("ShaderNodeTexImage"); to.image = img(os.path.join(args.tex, f["orm"]), True)
                sep = nt.nodes.new("ShaderNodeSeparateColor")
                nt.links.new(to.outputs["Color"], sep.inputs["Color"])
                nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
                nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
                g = nt.nodes.new("ShaderNodeGroup"); g.node_tree = gltf_output_group()
                nt.links.new(sep.outputs["Red"], g.inputs["Occlusion"])
        if alpha < 1:
            bsdf.inputs["Alpha"].default_value = alpha
            try: m.surface_render_method = "BLENDED"
            except Exception: m.blend_method = "BLEND"
        m.diffuse_color = (*[srgb_lin(c) for c in col], alpha)
        # every house part is a closed solid (CONTRACT): single-sided; only the alpha-cut sheets (mesh, Heras) stay double-sided
        m.use_backface_culling = not (tm and tm.get("alpha"))
        out[name] = m
    for a, b in ALIAS.items():
        if a in out and b in out:
            bpy.data.materials.remove(out[a]); out[a] = out[b]; TILE[a] = TILE[b]
    return out


# ======================================================================================== pure helpers
def triangulate(poly):
    """ear clipping -> triangles (lists of 3 points) for a simple polygon"""
    P = G.ccw([tuple(p) for p in poly])
    idx = list(range(len(P))); tris = []
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        ear = False
        for i in range(len(idx)):
            a, b, c = idx[i - 1], idx[i], idx[(i + 1) % len(idx)]
            A, B, C = P[a], P[b], P[c]
            if G.cross(G.sub(B, A), G.sub(C, B)) <= 1e-12: continue
            if any(G.point_in_poly(P[k], [A, B, C]) for k in idx if k not in (a, b, c)): continue
            tris.append([A, B, C]); idx.pop(i); ear = True; break
        if not ear: break
    if len(idx) == 3: tris.append([P[i] for i in idx])
    return tris


def convex_pieces(poly):
    return [poly] if _is_convex(poly) else triangulate(poly)


def _is_convex(P):
    from hb_build import _convex
    return _convex(G.ccw(P))


# ======================================================================================== version build (pure part)
class VersionBuild:
    def __init__(self, vspec, states):
        self.v = vspec
        self.sb = StateBuilder(DATA, SPEC)
        self.lv = self.sb.lv
        self.notes = []
        tgt = self.sb.build(vspec)
        if AB.porch_primary(vspec["id"], SPEC):
            AB.apply_porch_door(tgt["atoms"], SPEC, self.notes)
        self.state = tgt
        self.notes += self.sb.notes
        if vspec["kind"] == "proposal":
            base_spec = next(v for v in SPEC["versions"] if v["id"] == vspec["base"])
            sb2 = StateBuilder(DATA, SPEC)
            base = sb2.build(base_spec)
            self.base = base
            atoms = S.diff(base, tgt, SPEC, self.lv)
            self.systems = sb2.eave_systems() + self.sb.eave_systems()
        else:
            atoms = [dict(a, cat="existing") for a in tgt["atoms"]]
            self.systems = self.sb.eave_systems()
        S.stage_atoms(atoms, SPEC, self.lv, vspec["kind"])
        self.N = len(SPEC["stage_sets"][vspec["stages"]]) if vspec.get("stages") else 1
        atoms += self.temporary_atoms()
        atoms += self.roof_tarps(atoms)
        atoms += self.fence_atoms()
        extra = S.finish_walls(atoms, SPEC, self.lv, vspec["kind"])
        S.stage_atoms(extra, SPEC, self.lv, vspec["kind"])
        atoms += extra
        lint = S.lintel_atoms(atoms, SPEC, self.lv)
        S.stage_atoms(lint, SPEC, self.lv, vspec["kind"])
        atoms += lint
        self.beam_lifts(atoms)
        self.lintel_seq(atoms)
        self.unique_ids(atoms)
        atoms += HD.drains(SPEC, self.lv, vspec["kind"], vspec["id"])
        if vspec["kind"] == "proposal":
            pockets = S.embed_new_members(atoms, self.N)
            atoms += pockets
            self.embed_lifts(atoms)
            self.tidy_lifts(atoms)
        self.atoms = atoms
        self.apply_overrides()
        self.joins()
        self.atoms += self.threshold_atoms()
        studs = S.stud_atoms(atoms, self.lv)
        self.atoms += studs
        if vspec["kind"] == "proposal":
            self.atoms += HD.wall_details(self.atoms, SPEC, self.lv, self.notes)
            self.atoms += HD.junction_dpc(self.atoms, SPEC, self.lv)
            self.atoms += HD.hangers_and_straps(self, self.atoms, SPEC, self.lv)
        self.questions = HD.threshold_flags(self.atoms, SPEC, self.lv)
        self.atoms += AB.loft_rooflight(SPEC, self.notes, vspec["id"], vspec["kind"])
        self.atoms += self.owner_windows()
        self.atoms += self.porch_vault() + self.steel_casings() + self.ceiling_slopes() + self.spec_finishes() + self.party_closers()
        abl, abq = AB.as_built(self, SPEC, self.notes)
        self.atoms += abl
        key=SPEC_V1_MAP.get(self.v['id'])
        if key and not args.no_items:
            import hb_room_faces
            scheduled=SPEC_V1['versions'][key]
            linings=hb_room_faces.build(self,scheduled['rooms'],scheduled['items'])
            from hb_horizontal import horizontal
            linings.extend(horizontal(self,scheduled['rooms']))
            SPEC_MATS.update(a['mat'][5:] for a in linings)
            self.atoms.extend(linings)
        self.questions += abq
        if abl: log(vspec["id"], f"as-built layer: {len(abl)} records")
        log(vspec["id"], f"{len(atoms)} atoms")

    def apply_overrides(self):
        import re
        for ov in SPEC.get("meta_overrides", {}).get(self.v["id"], []) + SPEC.get("meta_overrides_all", []):
            for a in self.atoms:
                if re.search(ov["match"], a["id"]):
                    a["meta"].update(ov.get("set", {}))
                    if ov.get("append_label") and ov["append_label"] not in a["meta"]["label"]:
                        a["meta"]["label"] = a["meta"]["label"] + " " + ov["append_label"]

    def beam_lifts(self, atoms):
        """wall lifts above a new steel set into a new wall come after the steel (stage 7)"""
        steels = [a for a in atoms if a["kind"] == "member" and a["meta"]["group"] == "steel" and a["meta"].get("category") == "new"]
        for a in atoms:
            if a["kind"] != "wall" or a["meta"].get("category") != "new": continue
            W = a["wall"]
            for s in steels:
                if W.id.split("~")[0] in s.get("embedded_in_ids", []) or self._steel_in_wall(s, W):
                    top = max(s["A"][2], s["B"][2])
                    lifts = [W.z0] + W.lifts
                    k = next((i for i, z in enumerate(lifts) if z >= top - 0.25), None)
                    if k is not None and s["meta"]["stage_in"] > S.lift_stage_seq(a, top, SPEC)[0]:
                        # split a lift at the beam top so the courses over the steel go in after it
                        if top - 0.05 > lifts[k - 1 if k else 0]:
                            W.lifts = sorted(set(W.lifts + [round(top, 4)]))
                            lifts = [W.z0] + W.lifts
                            k = lifts.index(round(top, 4))
                        set_after(a, lifts[k], s["meta"]["stage_in"], s["meta"]["seq"] + 0.1)

    def owner_windows(self):
        """the 2022 house had white uPVC windows; the owner replaced them with anthracite before the works (Jack, 1 Nov
        2026). In a build from 2022 they are swapped at the weathertight stage, so the finish matches today's house."""
        oc = SPEC.get("owner_changes", {})
        if self.v["id"] not in oc.get("versions", []): return []
        st, sq = oc["windows"]["stage"]; out = []
        for a in self.atoms:
            if a["kind"] != "fixture" or a["op"]["kind"] != "window" or a.get("internal") or a.get("frame_mat") == "anthracite_upvc": continue
            m = a["meta"]
            if m.get("category") != "existing" or m.get("stage_out"): continue
            if a["wall"].ckey == "massing": continue
            m.update(stage_out=st, seq_out=sq, category="demolition", plain_label="Window replaced by the owner (after 2022)")
            b = dict(a, id=a["id"] + "-owner", frame_mat="anthracite_upvc", sill_mat="anthracite_upvc", cat="new",
                     meta=dict(m, stage_in=st, seq=round(sq + 0.05, 4), stage_out=None, seq_out=None, category="new",
                               label=f"{m['label']}: {oc['windows']['label']}", plain_label="Window (anthracite, as the owner replaced them)",
                               drawing="photo survey sfm/house_v1.json (not on the drawings)", conf="measured from photos"))
            b["no_regs"] = True; b["provenance"] = "owner, after 2022, not on drawings"
            out.append(b)
        return out

    def porch_vault(self):
        """the porch is vaulted inside: plasterboard under the rafters, following the roof (as built)"""
        pv = SPEC.get("porch_vault")
        if not pv or self.v["id"] not in pv["versions"]: return []
        pl = next(p for w in SPEC["defs"]["porch"]["wings"] for p in w["planes"])
        t = math.tan(math.radians(pl["pitch"])); c = math.cos(math.radians(pl["pitch"]))
        zt = lambda p: pl["p0"][2] - (pl["p0"][1] - p[1]) * t - (R.COVER_T + pv["rafter_depth"]) / c - 0.001
        zb = lambda p: zt(p) - 0.0125 / c
        x0, y0, x1, y1 = pv["rect"]
        # The surveyed room perimeter belongs to the inner vault. The old
        # rafter rectangle stopped 80 mm short of the house-side wall.
        scheduled = SPEC_V1.get('versions', {}).get(SPEC_V1_MAP.get(self.v['id']), {})
        porch = next((r for r in scheduled.get('rooms', []) if 'porch' in r['id']), None)
        if porch:
            x0=min(x for x,z in porch['polygon']); x1=max(x for x,z in porch['polygon'])
            y0=min(-z for x,z in porch['polygon']); y1=max(-z for x,z in porch['polygon'])
        meta = M("wall_lining", "ground", pv["label"], "4915.3A section D-D (vaulted ceiling) / as built", "scaled", "Porch ceiling (vaulted)", False)
        if self.v["kind"] == "proposal" and self.v.get("base") not in pv["versions"]:      # the porch is built in this sequence
            st, sq = SPEC["staging"]["phases"].get("ceiling", [self.N, 0.1])
            meta.update(stage_in=st, seq=sq, stage_out=None, seq_out=None, category="finish")
        else: meta.update(stage_in=1, seq=0.0, stage_out=None, seq_out=None, category="existing")
        from hb_geom import prism_varz
        perimeter=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
        holes=[];returns=[]
        for light in SPEC['defs']['porch'].get('rooflights',[]):
            a,b,right,d=light['rect'];holes.append([(a,b),(right,b),(right,d),(a,d)])
            for lo,hi,front,rear in [(a,a+.010,b,d),(right-.010,right,b,d),(a+.010,right-.010,b,b+.010),(a+.010,right-.010,d-.010,d)]:
                returns.append(prism_varz([(lo,front),(hi,front),(hi,rear),(lo,rear)],zt,
                                          lambda p:zt(p)+pv['rafter_depth']/math.cos(math.radians(pl['pitch']))))
        mesh=G.merge_meshes([prism_varz(P,zb,zt) for P in G.poly_minus_convex(perimeter,holes)])
        parts=[atom("CL-porch-vault", "mesh", "existing", dict(meta,surface_role='ceiling',room_id=porch['id'] if porch else ''), sig=None, mesh=mesh,mat="plasterboard",cat=meta["category"])]
        if returns:parts.append(atom("CL-porch-rooflight-returns","mesh","existing",meta,sig=None,mesh=G.merge_meshes(returns),mat="plasterboard",cat=meta["category"]))
        for plate in [a for a in self.atoms if a['meta'].get('group')=='wall_plate' and a.get('poly') and a['id'].startswith('WP-porch') and not a['meta'].get('stage_out')]:
            P=plate['poly'];left,right=min(x for x,y in P),max(x for x,y in P);front,back=min(y for x,y in P),max(y for x,y in P)
            if back-front>.15 or right-left<.5:continue
            low=plate['z0']-.0125
            front_board=[(left,front-.013),(right,front-.013),(right,front),(left,front)]
            clad=[G.prism(P,low,plate['z0']-.0003),prism_varz(front_board,lambda p:low,zb)]
            parts.append(atom('CL-'+plate['id']+'-lining','mesh','existing',meta,sig=None,mesh=G.merge_meshes(clad),mat='plasterboard',cat=meta['category']))
        return parts

    def spec_finishes(self):
        """the signed spec's floor finishes (a 6 mm finish over each room's floor, 2 mm proud, clipped to the wall faces) and
        skirting (FIN-SKIRT 145 mm, 18 mm MDF, on every wall run of the rooms that have it, gaps at doorways)"""
        vkey = SPEC_V1_MAP.get(self.v["id"])
        if not vkey or args.no_items: return []
        V = SPEC_V1["versions"][vkey]; out = []
        st_, sq_, cat_ = (self.N, 0.9, "finish") if self.N > 1 else (1, 0.0, "existing")
        sqf = 0.7 if self.N > 1 else 0.0                      # the floor finish goes down on the finished screed (0.6)
        walls = self.walls_live()
        fps = [(w, w["wall"].footprint(full=True)) for w in walls]
        def in_wall(q): return any(G.point_in_poly(q, f) for (w, f) in fps)
        def doorway(q, outn):
            for (w, f) in fps:
                if not G.point_in_poly(q, f): continue
                W = w["wall"]; u = G.dot(G.sub(q, W.a), W.d)
                floor_open = 0.2 if W.storey == "ground" else 2.9          # a door opening starts at its floor
                if any(o["u0"] - 0.01 <= u <= o["u1"] + 0.01 and o["z0"] < floor_open for o in W.openings): return True
            return False
        for r in V["rooms"]:
            fin = r["finishes"]; fl = re.search(r"FIN-FLR-[A-Z]+", fin.get("floor", ""))
            P = [(x, -z) for (x, z) in r["polygon"]]; fy = r["floor_y"]
            P = self._to_walls(P, fps, fy)
            if fl:
                fid = fl.group(0); SPEC_MATS.add(fid)
                meta = M("slab_layer", r["storey"], f"floor finish {fid} ({r['name']}; spec_v1)", "spec_v1 (signed 1 Nov 2026)", "assumed",
                         f"Floor: {fin.get('floor', '')[:60]}", True)
                meta.update(stage_in=st_, seq=sqf, stage_out=None, seq_out=None, category=cat_)
                a_ = atom(f"SPEC-FLR-{r['id']}", "slab", "existing", meta, sig=None, poly=G.ccw(P), z0=fy, z1=fy + 0.002,
                          mat=f"spec_{fid}", clip_walls=True, clip_reach=0.05); a_["spec_id"] = f"FLOOR:{r['id']}"; a_["meta"].update(room_id=r["id"],surface_role="floor",surface_id="floor/"+r["id"])
                out.append(a_)
            if "FIN-SKIRT" not in fin.get("skirting", "") or SKIRTING_HELD: continue
            # moulded skirting 150 x 18 (hb_joinery.SKIRT), one swept solid per continuous run: mitred at every corner, stopping
            # square against the architrave beside each doorway (architrave outer edge 31 mm past the opening edge)
            import hb_joinery as J
            SPEC_MATS.add("FIN-SKIRT")
            Q = G.ccw(P); n = len(Q)
            runs_e = []                                   # per edge: (offset of the wall face, [(u0, u1)])
            for i in range(n):
                a0, b0 = Q[i], Q[(i + 1) % n]; L = G.length(G.sub(b0, a0))
                if L < 0.05: runs_e.append((0.0, [], L)); continue
                d = G.unit(G.sub(b0, a0)); inw = (-d[1], d[0]); outn = (d[1], -d[0])
                mid = G.add(a0, G.mul(d, L / 2))
                of = 0.0
                for k_ in range(1, 41):
                    if not in_wall(G.add(mid, G.mul(inw, k_ * 0.001 - 0.0005))): break
                    of = k_ * 0.001
                of += SKIRT_LINING_T          # the wall stack's footprint ends 10 mm short of the lined face the room sees: the board stood 8 mm proud of the plaster, not 18 (round-1 sweep: skirting invisible)
                steps = max(2, int(L / 0.01)); ok = []; door_ = []
                for k in range(steps):
                    u = (k + 0.5) * L / steps
                    q = G.add(G.add(a0, G.mul(d, u)), G.mul(outn, 0.02))
                    dw_ = in_wall(q) and doorway(q, outn)
                    door_.append(dw_); ok.append(in_wall(q) and not dw_)
                # the door jambs on this edge (exact): the skirting stops against the architrave, 31 mm past each jamb
                jambs = []
                for (w_, f_) in fps:
                    W_ = w_["wall"]
                    if abs(G.dot(W_.d, d)) < 0.95: continue
                    if abs(G.dot(G.sub(W_.point(0.0, 0.0), a0), inw)) > W_.t + 0.05: continue
                    floor_open = 0.2 if W_.storey == "ground" else 2.9
                    for o_ in W_.openings:
                        if o_["z0"] >= floor_open: continue
                        for uj in (o_["u0"], o_["u1"]):
                            jambs.append(G.dot(G.sub(W_.point(uj, 0.0), a0), d))
                def snap(u, sgn):
                    near = [t_ for t_ in jambs if abs(t_ - u) < 0.08]
                    return (min(near, key=lambda t_: abs(t_ - u)) + sgn * 0.031) if near else u + sgn * 0.031
                runs, cur = [], None
                for k, o in enumerate(ok + [False]):
                    if o and cur is None: cur = k
                    if not o and cur is not None:
                        u0_, u1_ = cur * L / steps, k * L / steps
                        if cur > 0 and door_[cur - 1]: u0_ = snap(u0_, 1)        # stop against the architrave
                        if k < steps and door_[k]: u1_ = snap(u1_, -1)
                        runs.append((u0_, u1_)); cur = None
                runs_e.append((of, [r_ for r_ in runs if r_[1] - r_[0] > 0.06], L))
            def face_pt(i, u):
                a0, b0 = Q[i], Q[(i + 1) % n]; d = G.unit(G.sub(b0, a0)); inw = (-d[1], d[0])
                return G.add(G.add(a0, G.mul(d, u)), G.mul(inw, runs_e[i][0]))
            def corner(i):                                 # face lines of edge i and i+1 meet (mitre point)
                j = (i + 1) % n
                a0, b0 = Q[i], Q[j]; d0 = G.unit(G.sub(b0, a0)); a1, b1 = Q[j], Q[(j + 1) % n]; d1 = G.unit(G.sub(b1, a1))
                q = G.line_intersect(face_pt(i, 0.0), d0, face_pt(j, 0.0), d1)
                return q if q is not None else face_pt(j, 0.0)
            # chain runs across corners: a run reaching the end of edge i joins one starting at edge i+1
            pieces = []                                    # lists of plan points
            used = set()
            for i in range(n):
                for ri, (u0_, u1_) in enumerate(runs_e[i][1]):
                    if (i, ri) in used: continue
                    L_i = runs_e[i][2]
                    # walk backwards to the chain start
                    si, sr = i, ri
                    for _ in range(n):
                        pi_ = (si - 1) % n; prev = runs_e[pi_][1]
                        if runs_e[si][1][sr][0] < 0.035 and prev and prev[-1][1] > runs_e[pi_][2] - 0.035 and (pi_, len(prev) - 1) not in used and pi_ != i:
                            si, sr = pi_, len(prev) - 1
                        else: break
                    pts = [face_pt(si, runs_e[si][1][sr][0])]
                    ci, cr = si, sr
                    for _ in range(n + 1):
                        used.add((ci, cr))
                        u1c = runs_e[ci][1][cr][1]; Lc = runs_e[ci][2]
                        nj = (ci + 1) % n; nxt = runs_e[nj][1]
                        if u1c > Lc - 0.035 and nxt and nxt[0][0] < 0.035 and (nj, 0) not in used:
                            pts.append(corner(ci)); ci, cr = nj, 0
                        else:
                            pts.append(face_pt(ci, u1c)); break
                    if len(pts) >= 2 and sum(G.length(G.sub(b_, a_)) for a_, b_ in zip(pts, pts[1:])) > 0.06: pieces.append(pts)
            if not pieces:
                longest = max([u1 - u0 for (_, rr, _) in runs_e for (u0, u1) in rr] + [0.0])
                self.notes.append(f"skirting: none in {r['id']} (no wall run between its doorways' architraves is longer than 60 mm; longest {longest * 1000:.0f} mm)")
            for k, pts in enumerate(pieces):
                V_, F_ = J.sweep(pts, J.SKIRT, lambda x, y, h: (x, y, fy + 0.002 + h))       # standing on the 2 mm floor finish
                meta = M("fitting", r["storey"], f"skirting 150 x 18 mm moulded MDF, satin FIN-SKIRT ({r['name']}; spec_v1 + joinery bar)", "spec_v1", "assumed",
                         "Skirting board", False)
                meta.update(stage_in=st_, seq=sq_, stage_out=None, seq_out=None, category=cat_)
                a_ = atom(f"SPEC-SKIRT-{r['id']}-{k}", "mesh", "existing", meta, sig=None, mesh=(V_, F_), mat="spec_FIN-SKIRT")
                a_["spec_id"] = f"SKIRT:{r['id']}"
                d0 = G.unit(G.sub(pts[0], pts[1])); d1 = G.unit(G.sub(pts[-1], pts[-2]))
                a_["skirt_ends"] = [(list(pts[0]), list(d0)), (list(pts[-1]), list(d1))]       # for the scribe pass (hb_finish)
                out.append(a_)
        return out

    def _to_walls(self, P, fps, fy, reach=0.05):
        """an edge with walls along all of it moves out 30 mm (clip_walls then trims it to the wall face): the floor finish
        always meets the wall, never runs into a doorway or the next room"""
        Q = G.ccw(P); n = len(Q); offs = []
        live = [f for (w, f) in fps if w["wall"].z0 <= fy + 0.01 and w["wall"].z1 > fy + 0.1
                and (w["meta"].get("stage_out") or 99) > self.N]                  # walls standing at the finished stage
        for i in range(n):
            a, b = Q[i], Q[(i + 1) % n]; d = G.unit(G.sub(b, a)); outn = (d[1], -d[0])
            hit = all(any(G.point_in_poly(G.add(G.add(a, G.mul(G.sub(b, a), t)), G.mul(outn, reach * 0.9)), f) for f in live) for t in (0.2, 0.5, 0.8))
            offs.append(reach if hit else 0.0)
        lines = [(G.add(Q[i], G.mul((G.unit(G.sub(Q[(i + 1) % n], Q[i]))[1], -G.unit(G.sub(Q[(i + 1) % n], Q[i]))[0]), offs[i])), G.unit(G.sub(Q[(i + 1) % n], Q[i]))) for i in range(n)]
        out = []
        for i in range(n):
            q = G.line_intersect(lines[i - 1][0], lines[i - 1][1], lines[i][0], lines[i][1])
            out.append(q if q is not None else lines[i][0])
        return out if abs(G.area(out)) >= abs(G.area(Q)) - 1e-6 else Q

    def ceiling_slopes(self):
        """sloped ceilings under a pitched roof (build_versions 'ceiling_slopes'): plasterboard under the rafters of one roof
        plane, over a plan polygon, never above the flat ceiling it meets (row 179: bedroom 3's catslide showed its rafters)"""
        out = []
        from hb_geom import prism_varz
        for cs in SPEC.get("ceiling_slopes", []):
            if self.v["id"] not in cs["versions"]: continue
            pl = next((q for (sp, sm) in self.systems if sp["id"] == cs["roof"] for q in sm.planes() if q.id == cs["plane"]), None)
            sysm = None
            if pl is None:
                log("ceiling slope: no plane", cs["roof"], cs["plane"], [sp["id"] for (sp, sm) in self.systems], [q.id for q in sysm.planes()] if sysm else None); continue
            rd = pl.wing.spec.get("rafters", {}).get("section", [0.045, 0.145])[1]
            cap = cs.get("flat_underside", 99)
            zt = lambda p, pl=pl, rd=rd, cap=cap: min(cap, pl.z(p) - (R.COVER_T + rd) / pl.cos - 0.0015)
            zb = lambda p, zt=zt, pl=pl, t=cs.get("t", 0.015): zt(p) - t / pl.cos
            meta = M("ceiling_joist", "first", cs["label"], cs.get("drawing", ""), cs.get("conf", "scaled"), cs.get("plain", "Ceiling"), False)
            if self.v["kind"] == "proposal":
                st, sq = SPEC["staging"]["phases"].get(cs.get("phase", "ceiling"), [self.N, 0.1])
                meta.update(stage_in=st, seq=sq, stage_out=None, seq_out=None, category="finish")
            else: meta.update(stage_in=1, seq=0.0, stage_out=None, seq_out=None, category="existing")
            # The signed internal section runs from the finished ashlar
            # top to the flat *underside*. The outside rafter plane does
            # not establish that datum. Clip the plan to the real room.
            scheduled=SPEC_V1.get('versions',{}).get(SPEC_V1_MAP.get(self.v['id']),{})
            room=next((r for r in scheduled.get('rooms',[]) if 'ashlar' in str(r['ceiling_y'])),None)
            if room and cs['plane']=='ext.left':
                ashlar=next(w['wall'] for w in self.walls_live() if w['wall'].ckey=='ashlar' and not w['meta'].get('stage_out'))
                start=max(x for x,y in ashlar.footprint())
                head=ashlar.top_at((ashlar.ua+ashlar.ub)/2)
                knee=max(x for x,y in cs['poly'])
                gradient=(cap-head)/(knee-start)
                zbottom=lambda p:head+(p[0]-start)*gradient
                top=lambda p:zbottom(p)+cs.get('t',.015)/pl.cos
                polygons=G.convex_pieces([(x,-z) for x,z in room['polygon']])
                strips=[G.clip_convex(P,[(-1,0,start),(1,0,-knee)]) for P in polygons]
                mesh=G.merge_meshes([prism_varz(P,zbottom,top) for P in strips if len(P)>=3 and abs(G.area(P))>1e-7])
                meta.update(room_id=room['id'],surface_role='ceiling')
            else:
                mesh=prism_varz([tuple(p) for p in cs['poly']],zb,zt)
            out.append(atom(cs["id"], "mesh", "existing", meta, sig=None, mesh=mesh,
                            mat="plasterboard", cat=meta["category"]))
        return out

    def steel_casings(self):
        sc = SPEC.get("steel_casings")
        if not sc or self.v["id"] not in sc["versions"] or self.v["kind"] != "proposal": return []
        st, sq = SPEC["staging"]["phases"].get("lining", [self.N, 0.1]); out = []
        for b in sc["boxes"]:
            if b["id"].startswith("SC-beam-6") and not any(a["id"].startswith("B-beam-6") for a in self.atoms): continue
            x0, y0, x1, y1 = b["rect"]
            meta = M("wall_lining", "ground", sc["label"], "", "assumed", "Boxing round the steel beam", False)
            meta.update(stage_in=st, seq=round(sq + 0.02, 4), stage_out=None, seq_out=None, category="finish")
            out.append(atom(b["id"], "prism", "existing", meta, sig=None, poly=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0=b["z"][0], z1=b["z"][1],
                            mat="plasterboard", cat="finish"))
        return out

    def threshold_atoms(self):
        """a floor through every doorway (Jack's walk: no gap at the door): the wall under a door opening is lowered 20 mm
        across its whole thickness and a threshold board fills the reveal flush with the floor, living as long as the
        opening does (a new opening's from when its panel is cut out; a bricked-up one's until the infill)"""
        out = []
        lv = self.lv
        atoms = self.atoms
        for a in [x for x in atoms if x["kind"] == "wall"]:
            W = a["wall"]
            if W.ckey == "massing" or a["meta"].get("category") == "demolition" and not a.get("panel") is None: pass
            if a.get("panel") or a.get("infill") or W.ckey == "massing": continue
            floor = lv.ffl if W.storey == "ground" else lv.ff
            new_ids = {o["id"] for o in getattr(W, "openings_new", [])}
            for o in W.openings:
                if o["kind"] not in ("door", "bifold", "opening") or abs(o["z0"] - floor) > 0.06 or o["z0"] < W.z0 + 0.03: continue
                m = a["meta"]; si, sq, so, sqo = m.get("stage_in", 1), m.get("seq", 0.0), m.get("stage_out"), m.get("seq_out")
                cat = m.get("category", "existing")
                if o["id"] in new_ids:                    # cut through an existing wall: the doorway exists once the panel is out
                    pan = [x for x in atoms if x["kind"] == "wall" and x.get("panel") and x["id"].startswith(f"{W.id}~panel-{slug(o['id'])}")]
                    if pan: si, sq, cat = pan[0]["meta"].get("stage_out") or si, min(0.99, (pan[0]["meta"].get("seq_out") or 0.5) + 0.02), "new"
                if o.get("infilled"):
                    inf = [x for x in atoms if x["kind"] == "wall" and x.get("infill") and x["id"].startswith(f"{W.id}~infill-{slug(o['id'])}")]
                    if inf: so, sqo = inf[0]["meta"].get("stage_in"), max(0.0, (inf[0]["meta"].get("seq") or 0.2) - 0.01)
                if m.get("category") == "new" and self.v["kind"] == "proposal":    # a new wall: when its courses reach the sill
                    si, sq = S.lift_stage_seq(a, o["z0"], SPEC); sq = min(0.99, sq + 0.01)
                cl, ch = W.full_extent_c()
                W.holes.append((o["u0"], o["u1"], o["z0"] - 0.02, o["z0"], -1.0, W.t + 1.0))
                # row 179: the threshold fills the doorway to within 1.5 mm of each jamb (it was 3 mm: a visible slot at every door)
                u0, u1 = o["u0"] + 0.0015, o["u1"] - 0.0015
                P = [W.point(u0, cl + 0.0015), W.point(u1, cl + 0.0015), W.point(u1, ch - 0.0015), W.point(u0, ch - 0.0015)]
                bb = (min(q[0] for q in P), min(q[1] for q in P), max(q[0] for q in P), max(q[1] for q in P))
                # a doorway shared by two pieces of one wall (a wall split by the diff) gets ONE threshold (two were coplanar: z-fighting)
                dup = next((t for t in out if t.get("_th_bb") and t.get("_th_z") == round(o["z0"], 4) and
                            (t["meta"].get("stage_in"),t["meta"].get("stage_out"),t["meta"].get("seq_out")) == (si,so,sqo) and
                            min(bb[2], t["_th_bb"][2]) - max(bb[0], t["_th_bb"][0]) > 0.05 and min(bb[3], t["_th_bb"][3]) - max(bb[1], t["_th_bb"][1]) > 0.05), None)
                if dup is not None:
                    tb = dup["_th_bb"]; dup["_th_bb"] = u = (min(tb[0], bb[0]), min(tb[1], bb[1]), max(tb[2], bb[2]), max(tb[3], bb[3]))
                    if abs(W.d[0]) > 0.999 or abs(W.d[1]) > 0.999:          # square to the axes: one threshold over both
                        dup["poly"] = [(u[0], u[1]), (u[2], u[1]), (u[2], u[3]), (u[0], u[3])]
                    continue
                ext = W.ckey in ("cav337_new", "cav_existing", "solid_existing", "party")
                meta = M("slab_layer", W.storey, (f"threshold through the doorway '{o['id']}': " +
                         ("external sill/threshold, flush with the floor inside (type not drawn)" if ext else "hardwood threshold, flush with the floors") + f" {TYPICAL}"),
                         "", "assumed", "Floor through the doorway", True)
                meta.update(stage_in=si, stage_out=so, seq=round(sq, 4), seq_out=sqo, category="existing" if si == 1 else "new")
                th = atom(f"TH-{slug(W.id)}-{slug(o['id'])}", "prism", "existing", meta, sig=None, poly=P, z0=o["z0"] - 0.0185, z1=o["z0"],   # 1.5 mm over the wall lowered 20 mm under it (was 3 mm: row 179)
                          mat="buff_concrete" if ext else ("spec_FIN-FLR-OAK" if (SPEC_V1_MAP.get(self.v["id"]) and not args.no_items) else "existing_floor"), cat=meta["category"])
                if not ext and SPEC_V1_MAP.get(self.v["id"]) and not args.no_items: SPEC_MATS.add("FIN-FLR-OAK")      # round-1 sweep: the internal threshold is a hardwood strip in the spec oak, not the raw 'existing_floor' tone
                th["_th_bb"] = bb; th["_th_z"] = round(o["z0"], 4)
                out.append(th)
        return out

    def embed_lifts(self, atoms):
        """a member set into a new wall in the same stage (padstones, beam 5, the pipe lintel): the wall gets course
        lines at its bottom and top, and the member goes in after the courses under it, before those over it"""
        walls = {a["id"]: a for a in atoms if a["kind"] == "wall"}
        for m in atoms:
            if m["meta"].get("category") != "new" or not m.get("embedded_in"): continue
            if m["kind"] == "member":
                zs = [m["A"][2], m["B"][2]]
                deep = 0.0
                for sec in [m["section"]] + [s_ for s_, mm in m.get("extra_sections", []) if s_]:
                    deep = max(deep, -min(z for _, z in sec))
                zb, zt = min(zs) - deep, max(zs)
            else:
                zz = [p[2] for p in m["mesh"][0]]; zb, zt = min(zz), max(zz)
            for wid in m["embedded_in"]:
                a = walls.get(wid)
                if a is None or a["meta"].get("category") != "new" or a.get("infill"): continue
                W = a["wall"]
                st, sq = S.lift_stage_seq(a, zb, SPEC)
                W.lifts = sorted(set(W.lifts + [round(z, 4) for z in (zb, zt) if W.z0 + 0.02 < z < W.z1 - 0.02]))
                W.__dict__.setdefault("_fixed", set()).update({round(zb, 4), round(zt, 4)})
                if st == m["meta"]["stage_in"]:
                    # on the courses under it, before the courses that start on its top
                    m["meta"]["seq"] = round(max(sq + 0.005, S.lift_stage_seq(a, zt, SPEC)[1] - 0.002), 4)
                elif m["meta"]["stage_in"] > st:
                    # set later than the wall (beam 4's end, the porch beam): the courses over it wait for it
                    set_after(a, round(zt, 4), m["meta"]["stage_in"], m["meta"]["seq"] + 0.05)

    def tidy_lifts(self, atoms):
        """a course line within 100 mm of a structural line (a lintel's bed or top, a member's seat or top, the dpc)
        is dropped, so no thin course is left between them and every member lands between whole courses"""
        for a in atoms:
            if a["kind"] != "wall" or a["meta"].get("category") != "new": continue
            W = a["wall"]
            fixed = set(W.__dict__.get("_fixed", set())) | {round(self.lv.dpc, 4)}
            W.lifts = sorted(l for l in W.lifts if l in fixed or all(abs(l - f) >= 0.1 for f in fixed))

    def lintel_seq(self, atoms):  # noqa
        """a lintel goes in after the lift that ends at its head, before the lift that starts on top of it"""
        for a in atoms:
            if "host" not in a or a["meta"].get("category") != "new": continue
            W = a["host"]
            host = next((h for h in atoms if h.get("wall") is W), None)
            if host is None or host["meta"].get("category") not in ("new", "existing"): continue
            if host["meta"].get("category") == "existing":
                a["meta"]["seq"] = 0.55; continue
            lines = [W.z0] + [l for l in W.lifts if W.z0 < l < W.z1] + [W.z1]
            nl = len(lines) - 1
            k = max(i for i in range(nl) if lines[i] <= a["head"] + 1e-4)       # lift that starts at (or below) the head
            st, sq = S.lift_stage_seq(host, a["head"], SPEC)
            a["meta"]["stage_in"] = st
            a["meta"]["seq"] = round(max(0.0, sq - 0.001), 4)                       # on the courses under the head, before those that start on it
            if host.get("lift_stage_after") and a["head"] >= host["lift_stage_after"][0] - 1e-4:
                a["meta"]["stage_in"] = host["lift_stage_after"][1]; a["meta"]["seq"] = host["lift_stage_after"][2]

    def unique_ids(self, atoms):
        seen = {}
        for a in atoms:
            i = a["id"]
            if i in seen:
                seen[i] += 1; a["id"] = f"{i}#{seen[i]}"
                if a["kind"] == "wall": a["wall"].id = a["id"]
            else: seen[i] = 0

    def _steel_in_wall(self, s, W):
        A, B = s["A"], s["B"]
        if abs(abs(G.dot(G.unit(G.sub(B[:2], A[:2])), W.d)) - 1) > 1e-3: return False
        return abs(G.dot(G.sub(A[:2], W.a), W.n)) < W.t / 2 and W.z0 < A[2] < W.z1 + 0.3

    def drop_buried(self):
        """a wall piece lying wholly inside another wall that stands at least as long (a corner drawn overlapping
        on the trace) adds nothing: it is dropped, with a note"""
        walls = [a for a in self.atoms if a["kind"] == "wall"]
        keep = []
        for a in self.atoms:
            if a["kind"] == "wall":
                W = a["wall"]; la = S.lifetime(a["meta"], self.N)
                p0, p1 = W.point(W.ua, 0), W.point(W.ub, 0)
                buried = False
                for b in walls:
                    if b is a or a.get("panel") or a.get("infill"): continue
                    B = b["wall"]; lb = S.lifetime(b["meta"], self.N)
                    if W.id.split("~")[0] == B.id.split("~")[0]: continue          # pieces of one wall fill each other's holes
                    if not (lb[0] <= la[0] and lb[1] >= la[1]) or lb == la or B.storey != W.storey: continue
                    if min(B.z1, W.z1) - max(B.z0, W.z0) < 0.9 * (W.z1 - W.z0): continue
                    fp = G.ccw(B.footprint(full=False))
                    inside = lambda p: all(aa * p[0] + bb * p[1] + cc <= 0.004 for (aa, bb, cc) in G.poly_halfplanes(fp))
                    if inside(p0) and inside(p1) and W.t <= B.t + 0.02 and (W.ub - W.ua) < B.t + 0.06:
                        buried = True; self.notes.append(f"{W.id}: dropped, lies inside {B.id} (corner overlap on the trace)"); break
                if buried: continue
            keep.append(a)
        self.atoms = keep

    def joins(self):
        self.drop_buried()
        walls = []
        for a in self.atoms:
            if a["kind"] != "wall": continue
            W = a["wall"]
            W._life = S.lifetime(a["meta"], self.N)
            walls.append(W)
        self.join_log = resolve_joins(walls, S.coexist_fn(self.N))

    # ---------------------------------------------------------------- temporary works (spec)
    def temporary_atoms(self):
        out = []
        TS = SPEC["staging"].get("temporary_stages", {})
        for t in SPEC.get("temporary", {}).get(self.v["id"], []):
            if t["id"] in TS:
                t = dict(t, **{k: v for k, v in TS[t["id"]].items() if k != "lift_stage_map"})
                lm = TS[t["id"]].get("lift_stage_map")
                if lm and "runs" in t:
                    t["runs"] = [dict(r, lift_stages={z: [lm.get(str(v[0]), v[0]), v[1]] for z, v in r.get("lift_stages", {}).items()}) for r in t["runs"]]
            meta = M(t["group"], t.get("storey", "ground"), f"{t['label']} {TYPICAL}", "", "assumed", t.get("plain"), t.get("collide", False))
            meta.update(stage_in=t["stage_in"], stage_out=t.get("stage_out"), seq=t.get("seq", 0.0), seq_out=t.get("seq_out", 0.5), category="temporary")
            kind = t["kind"]
            if kind == "props":
                for k, (x, y) in enumerate(t["at"]):
                    z0, z1 = t["z0"], t["z1"]
                    sec = [(0.03 * math.cos(a), 0.03 * math.sin(a) - 0.03) for a in [i * math.pi / 4 for i in range(8)]]
                    a = atom(f"{t['id']}-{k:02d}", "member", "temp", dict(meta, seq=round(t.get("seq", 0) + t.get("seq_span", 0.1) * k / max(1, len(t["at"]) - 1), 4)),
                             sig=sig_of("tp", t["id"], k), A=(x, y + 0.0, z1), B=(x, y, z0), section=[(yy, zz) for yy, zz in sec], mat="prop_steel")
                    a["A"], a["B"] = (x - 0.0, y, z1), (x, y, z0)
                    a["section"] = [(0.03 * math.cos(q), 0.03 * math.sin(q)) for q in [i * math.pi / 4 for i in range(8)]]
                    a["vertical"] = True
                    a["cat"] = "temporary"
                    out.append(a)
                    for (zz0, zz1) in ((z0, z0 + 0.008), (z1 - 0.008, z1)):
                        pm = atom(f"{t['id']}-{k:02d}-plate{int(zz0 > z0)}", "mesh", "temp", dict(a["meta"]), sig=sig_of("tpp", t["id"], k, zz0),
                                  mesh=G.box(x - 0.075, x + 0.075, y - 0.075, y + 0.075, zz0, zz1), mat="prop_steel")
                        pm["cat"] = "temporary"; out.append(pm)
            elif kind == "beams":
                for k, b in enumerate(t["members"]):
                    w_, d_ = t["section"]
                    a = atom(f"{t['id']}-{k:02d}", "member", "temp", dict(meta, seq=round(t.get("seq", 0) + t.get("seq_span", 0.05) * k / max(1, len(t["members"]) - 1), 4)),
                             sig=sig_of("tb", t["id"], k), A=tuple(b[0]), B=tuple(b[1]), section=G.rect_section(w_, d_), mat=t.get("mat", "timber_temp"))
                    a["cat"] = "temporary"; out.append(a)
            elif kind == "spoil":
                (x, y), r, h = t["at"], t["radius"], t["height"]
                n = 10
                lo = [(x + r * math.cos(2 * math.pi * i / n), y + 0.7 * r * math.sin(2 * math.pi * i / n)) for i in range(n)]
                hi = [(x + 0.35 * r * math.cos(2 * math.pi * i / n), y + 0.25 * r * math.sin(2 * math.pi * i / n)) for i in range(n)]
                V = [(p[0], p[1], t["z"]) for p in lo] + [(p[0], p[1], t["z"] + h) for p in hi]
                F = [tuple(reversed(range(n))), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
                a = atom(t["id"], "mesh", "temp", meta, sig=sig_of("sp", t["id"]), mesh=(V, F), mat="earth"); a["cat"] = "temporary"; out.append(a)
            elif kind == "scaffold":
                out.extend(self.scaffold(t, meta))
            elif kind in ("boxes", "skip", "heras", "sheet", "protection"):
                out.extend(self.site_atoms(t, meta))
        return out

    def fence_atoms(self):
        """boundary fences as closeboard: 100x100 posts at max 1.8 m, feather-edge boards on rails, a gravel board"""
        out = []
        # row 179: where two fence runs meet they share ONE post (the taller of the two); two coincident posts z-fought
        post_h = {}
        for f in SPEC.get("fences", []):
            for (x_, y_) in f["line"]:
                k_ = (round(x_, 2), round(y_, 2)); post_h[k_] = max(post_h.get(k_, 0), f["height"])
        posted = set()
        for f in SPEC.get("fences", []):
            (xa, ya), (xb, yb) = f["line"]
            d = G.unit((xb - xa, yb - ya)); n = (d[1], -d[0]); L = G.length((xb - xa, yb - ya))
            zg, h = f.get("ground", -0.25), f["height"]
            meshes_p, meshes_b, meshes_g = [], [], []
            nb = max(1, math.ceil(L / 1.8))
            for i in range(nb + 1):
                p = G.add((xa, ya), G.mul(d, L * i / nb))
                k_ = (round(p[0], 2), round(p[1], 2))
                if k_ in posted: continue
                posted.add(k_)
                P = [G.add(p, G.add(G.mul(d, s1 * 0.05), G.mul(n, s2 * 0.05))) for s1, s2 in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                meshes_p.append(G.prism(P, zg, zg + max(h, post_h.get(k_, h)) + 0.05))
            for i in range(nb):
                a = G.add(G.add((xa, ya), G.mul(d, L * i / nb + 0.05)), G.mul(n, 0.05)); b = G.add(G.add((xa, ya), G.mul(d, L * (i + 1) / nb - 0.05)), G.mul(n, 0.05))
                P = [a, b, G.add(b, G.mul(n, 0.022)), G.add(a, G.mul(n, 0.022))]
                meshes_b.append(G.prism(P, zg + 0.15, zg + h))
                meshes_g.append(G.prism(P, zg, zg + 0.15))
            meta = M("fitting", "site", f"{f['label']}", f.get("drawing", ""), f.get("conf", "scaled"), "Garden fence", True)
            meta.update(stage_in=1, stage_out=None, seq=0.0, seq_out=None, category="existing")
            for part, mm, mat in (("posts", meshes_p, "timber_existing"), ("boards", meshes_b, f.get("mat", "fence_board")), ("gravel", meshes_g, "concrete")):
                if not mm: continue
                a = atom(f"FN-{slug(f['label'])}-{part}", "mesh", "existing", dict(meta), sig=sig_of("fence", f["line"], part), mesh=G.merge_meshes(mm), mat=mat)
                a["cat"] = "existing"; out.append(a)
        return out

    def scaffold(self, t, meta):
        """independent tube scaffold planned as a site manager would: standards on sole boards, ledgers and transoms
        at every lift, boarded working lifts with double guardrails (950 / 470) and 150 toe boards, a ladder bay with
        ladders tied and 1 m past each landing, ties into the wall every other standard on alternate lifts, facade
        braces; a lift can be added later (lift_stages: the stage it is raised to)."""
        out = []
        tube = [(0.024 * math.cos(q), 0.024 * math.sin(q)) for q in [i * math.pi / 4 for i in range(8)]]
        k = [0]
        def tube_m(A, B, label, st=None, mat="scaffold"):
            m = dict(meta)
            if label: m["label"] = f"{label} {TYPICAL}"
            if st: m.update(stage_in=st[0], seq=st[1])
            a = atom(f"{t['id']}-{k[0]}", "member", "temp", m, sig=sig_of("sc", t["id"], k[0]), A=A, B=B, section=tube, mat=mat)
            a["cat"] = "temporary"; k[0] += 1
            if abs(A[0] - B[0]) < 1e-6 and abs(A[1] - B[1]) < 1e-6: a["vertical"] = True
            out.append(a); return a
        def prism_m(P, z0, z1, mat, label, st=None):
            m = dict(meta, label=f"{label} {TYPICAL}")
            if st: m.update(stage_in=st[0], seq=st[1])
            a = atom(f"{t['id']}-{k[0]}", "prism", "temp", m, sig=sig_of("scp", t["id"], k[0]), poly=P, z0=z0, z1=z1, mat=mat)
            a["cat"] = "temporary"; k[0] += 1; out.append(a); return a
        for run in t["runs"]:
            (xa, ya), (xb, yb) = run["line"]
            d = G.unit((xb - xa, yb - ya)); n = tuple(run["out"])
            L = G.length((xb - xa, yb - ya))
            nb = max(1, math.ceil(L / 2.0))
            wdt = run.get("width", t.get("width", 1.2)); gap = run.get("gap", 0.3)
            lst = {float(z): v for z, v in run.get("lift_stages", {}).items()}
            st_of = lambda z: lst.get(round(z, 3)) if lst.get(round(z, 3)) else None
            top = run["top"]
            pt = lambda s, off: G.add(G.add((xa, ya), G.mul(d, s)), G.mul(n, off))
            for row, off in (("in", gap), ("out", gap + wdt)):
                for i in range(nb + 1):
                    p = pt(L * i / nb, off)
                    ztop = run.get("inner_top", top) if row == "in" else top        # inner standards stop under the eaves overhang
                    tube_m((p[0], p[1], ztop), (p[0], p[1], run["z0"] + 0.04), "scaffold standard on a base plate and sole board")
                    sb = [G.add(p, G.add(G.mul(d, s1 * 0.2), G.mul(n, s2 * 0.09))) for s1, s2 in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                    prism_m(sb, run["z0"], run["z0"] + 0.038, "scaffold_board", "sole board under the standard")
                for z in run["lifts"]:
                    tube_m((*pt(0, off), z), (*pt(L, off), z), "ledger", st_of(z))
            for z in run["lifts"]:
                for i in range(nb + 1):
                    tube_m((*pt(L * i / nb, gap - 0.1), z + 0.05), (*pt(L * i / nb, gap + wdt + 0.1), z + 0.05), "transom", st_of(z))
            for z in run["boards"]:
                st = st_of(z)
                P = [pt(0, gap + 0.03), pt(L, gap + 0.03), pt(L, gap + wdt - 0.03), pt(0, gap + wdt - 0.03)]
                prism_m(P, z + 0.075, z + 0.113, "scaffold_board", "scaffold boards (working lift)", st)
                # double guardrail and toe board on the open (outer) side and both ends
                for zz in (z + 0.113 + 0.47, z + 0.113 + 0.95):
                    tube_m((*pt(0, gap + wdt), zz), (*pt(L, gap + wdt), zz), "guardrail (950 top rail, 470 intermediate)", st)
                    for s_ in (0.0, L):
                        tube_m((*pt(s_, gap), zz), (*pt(s_, gap + wdt), zz), "end guardrail", st)
                tb = [pt(0, gap + wdt - 0.06), pt(L, gap + wdt - 0.06), pt(L, gap + wdt - 0.03), pt(0, gap + wdt - 0.03)]
                prism_m(tb, z + 0.113, z + 0.113 + 0.15, "scaffold_board", "toe board", st)
                # ties into the wall at every other standard on this lift
                zt_ = min(z + 0.3, run.get("inner_top", top) - 0.06)
                for i in range(0, nb + 1, 2):
                    tube_m((*pt(L * i / nb, gap), zt_), (*pt(L * i / nb, 0.03), zt_), "wall tie (ring / through tie into the masonry)", st)
            # facade braces: zig-zag on the outer face, one per two bays
            zl = [run["z0"] + 0.1] + list(run["lifts"])
            for i in range(0, nb, 2):
                for j in range(len(zl) - 1):
                    s0, s1 = (L * i / nb, L * min(nb, i + 2) / nb) if j % 2 == 0 else (L * min(nb, i + 2) / nb, L * i / nb)
                    tube_m((*pt(s0, gap + wdt + 0.048), zl[j]), (*pt(s1, gap + wdt + 0.048), zl[j + 1]), "facade brace (clipped to the outer standards)", st_of(zl[j + 1]))
            # ladder bay: aluminium ladders lift to lift, inside the scaffold, 1 m past each landing
            if run.get("ladder", True):
                lb = run.get("ladder_bay", 0)
                s_mid = L * (lb + 0.5) / nb
                lands = [run["z0"]] + list(run["boards"])
                for j in range(len(lands) - 1):
                    zb0, zb1 = lands[j] + (0.113 if j else 0.0), lands[j + 1] + 0.113 + 1.0
                    off0, off1 = gap + wdt * 0.25, gap + wdt * 0.25 + (zb1 - zb0) / 4.0
                    off1 = min(off1, gap + wdt - 0.08)
                    st = st_of(lands[j + 1])
                    for side in (-0.21, 0.21):
                        A = (*pt(s_mid + side, off0), zb0); B = (*pt(s_mid + side, off1), zb1)
                        tube_m(A, B, "ladder stile (ladder tied at the top, 1 m past the landing)", st, mat="aluminium")
                    nr = int((zb1 - zb0) / 0.3)
                    for r in range(1, nr):
                        f_ = r / nr
                        A = (*pt(s_mid - 0.21, off0 + (off1 - off0) * f_), zb0 + (zb1 - zb0) * f_)
                        B = (*pt(s_mid + 0.21, off0 + (off1 - off0) * f_), zb0 + (zb1 - zb0) * f_)
                        a = tube_m(A, B, "ladder rung", st, mat="aluminium")
                        a["section"] = [(0.014 * math.cos(q), 0.014 * math.sin(q)) for q in [i * math.pi / 3 for i in range(6)]]
        for a in out:
            if a["kind"] == "member" and not a.get("vertical"):
                a["section"] = a.get("section", tube)
        return out

    def site_atoms(self, t, meta):
        """site set-up items: skip, welfare cabin, toilet, material pallets and bags, timber stacks, Heras fencing,
        protection boards, temporary sheeting (all typical — not from the drawings)"""
        out = []
        kind = t["kind"]
        def put(i, mesh, mat, label=None, plain=None, collide=None):
            m = dict(meta)
            if label: m["label"] = f"{label} {TYPICAL}"
            if plain: m["plain_label"] = plain
            if collide is not None: m["collide"] = collide
            a = atom(f"{t['id']}-{i}", "mesh", "temp", m, sig=sig_of("site", t["id"], i), mesh=mesh, mat=mat)
            a["cat"] = "temporary"; out.append(a); return a
        if kind == "boxes":
            for i, b in enumerate(t["items"]):
                x0, y0, x1, y1, z0, z1 = b["box"]
                ms = [G.box(x0, x1, y0, y1, z0 + (0.144 if b.get("pallet") else 0.0), z1)]
                if b.get("pallet"):
                    put(f"{i}p", G.merge_meshes([G.box(x0, x1, y0, y1, z0 + 0.122, z0 + 0.144)] +
                                                [G.box(x0, x1, y0 + f_ * (y1 - y0 - 0.1), y0 + f_ * (y1 - y0 - 0.1) + 0.1, z0, z0 + 0.122) for f_ in (0, 0.5, 1)]),
                        "pallet", "timber pallet", "Pallet")
                put(i, G.merge_meshes(ms), b["mat"], b.get("label"), b.get("plain"), b.get("collide", True))
        elif kind == "skip":
            (x0, y0, x1, y1), z, h = t["rect"], t["z"], t.get("height", 1.2)
            dxw = (x1 - x0); dyl = (y1 - y0)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            ax = t.get("axis", "y")
            lb, lt = (dyl * 0.70, dyl) if ax == "y" else (dxw * 0.70, dxw)
            wb, wt = (dxw * 0.92, dxw) if ax == "y" else (dyl * 0.92, dyl)
            def ring(l, w, zz):
                if ax == "y": return [(cx - w / 2, cy - l / 2, zz), (cx + w / 2, cy - l / 2, zz), (cx + w / 2, cy + l / 2, zz), (cx - w / 2, cy + l / 2, zz)]
                return [(cx - l / 2, cy - w / 2, zz), (cx + l / 2, cy - w / 2, zz), (cx + l / 2, cy + w / 2, zz), (cx - l / 2, cy + w / 2, zz)]
            outer = G.hexa(ring(lb, wb, z + 0.1) + ring(lt, wt, z + h))
            # hollow: inner shell 4 mm thick walls is drawn as an inner box of spoil/rubble to 0.6 full
            put("shell", outer, "skip_steel", t["label"], t.get("plain", "Skip"), True)
            put("feet", G.merge_meshes([G.box(cx - wb / 2 + 0.05, cx - wb / 2 + 0.15, y0 + 0.2, y1 - 0.2, z, z + 0.1) if ax == "y" else G.box(x0 + 0.2, x1 - 0.2, cy - wb / 2 + 0.05, cy - wb / 2 + 0.15, z, z + 0.1),
                                       G.box(cx + wb / 2 - 0.15, cx + wb / 2 - 0.05, y0 + 0.2, y1 - 0.2, z, z + 0.1) if ax == "y" else G.box(x0 + 0.2, x1 - 0.2, cy + wb / 2 - 0.15, cy + wb / 2 - 0.05, z, z + 0.1)]),
                "skip_steel", "skip runners", "Skip")
            boards = t.get("boards")
            if boards: put("boards", G.box(x0 - 0.1, x1 + 0.1, y0 - 0.1, y1 + 0.1, z - 0.025, z), "scaffold_board", "scaffold boards under the skip to spread the load on the drive", "Boards under the skip")
        elif kind == "heras":
            for li, line in enumerate(t["lines"]):
                for (xa, ya), (xb, yb) in zip(line, line[1:]):
                    d = G.unit((xb - xa, yb - ya)); L = G.length((xb - xa, yb - ya)); nrm = (-d[1], d[0])
                    np_ = max(1, math.ceil(L / 3.5))
                    frames, meshes, feet = [], [], []
                    for i in range(np_):
                        s0, s1 = L * i / np_, L * (i + 1) / np_
                        p0 = G.add((xa, ya), G.mul(d, s0 + 0.02)); p1 = G.add((xa, ya), G.mul(d, s1 - 0.02))
                        z0 = t["z"] + 0.12; z1 = z0 + 2.0
                        q = lambda p, o: G.add(p, G.mul(nrm, o))
                        rail = lambda pa, pb, za, zb: G.prism([q(pa, -0.0175), q(pb, -0.0175), q(pb, 0.0175), q(pa, 0.0175)], za, zb)
                        frames += [rail(p0, p1, z0, z0 + 0.035), rail(p0, p1, z1 - 0.035, z1),
                                   rail(p0, G.add(p0, G.mul(d, 0.035)), z0, z1), rail(G.add(p1, G.mul(d, -0.035)), p1, z0, z1)]
                        meshes.append(G.prism([q(G.add(p0, G.mul(d, 0.035)), -0.002), q(G.add(p1, G.mul(d, -0.035)), -0.002),
                                               q(G.add(p1, G.mul(d, -0.035)), 0.002), q(G.add(p0, G.mul(d, 0.035)), 0.002)], z0 + 0.035, z1 - 0.035))
                        for pp in (p0, p1):
                            feet.append(G.prism([q(G.add(pp, G.mul(d, -0.3)), -0.1), q(G.add(pp, G.mul(d, 0.3)), -0.1),
                                                 q(G.add(pp, G.mul(d, 0.3)), 0.1), q(G.add(pp, G.mul(d, -0.3)), 0.1)], t["z"], t["z"] + 0.14))
                    put(f"{li}-{xa:.1f}-frame", G.merge_meshes(frames), "scaffold", t["label"] + " (frames)", "Temporary site fence", True)
                    put(f"{li}-{xa:.1f}-mesh", G.merge_meshes(meshes), "heras", t["label"] + " (mesh)", "Temporary site fence", True)
                    put(f"{li}-{xa:.1f}-feet", G.merge_meshes(feet), "black_upvc", "Heras rubber feet", "Temporary site fence feet", False)
        elif kind == "sheet":
            for i, q in enumerate(t["quads"]):
                P = [tuple(p) for p in q]
                # thin closed slab: the quad and a copy 4 mm along its normal
                ux = [P[1][j] - P[0][j] for j in range(3)]; uy = [P[3][j] - P[0][j] for j in range(3)]
                nn = (ux[1] * uy[2] - ux[2] * uy[1], ux[2] * uy[0] - ux[0] * uy[2], ux[0] * uy[1] - ux[1] * uy[0])
                ln = math.sqrt(sum(v * v for v in nn)) or 1
                off = [0.004 * v / ln for v in nn]
                Q = [tuple(p[j] + off[j] for j in range(3)) for p in P]
                put(i, G.hexa(P + Q), t.get("mat", "tarp"), t["label"], t.get("plain", "Temporary sheeting"), False)
        elif kind == "protection":
            for i, poly in enumerate(t["polys"]):
                put(i, G.prism(poly["poly"], poly["z"], poly["z"] + 0.004), "chipboard", t["label"], t.get("plain", "Floor protection boards"), False)
        return out

    def roof_tarps(self, atoms):
        """temporary sheeting over the new roof's rafters from when they go up until the membrane goes on (the old
        roof is opened up at the same stage): a copy of each new membrane piece, blue tarp (typical)"""
        cfg = SPEC.get("temporary_roof_sheet", {}).get(self.v["id"])
        if not cfg: return []
        if SPEC["staging"].get("roof_tarp"): cfg = dict(cfg, **SPEC["staging"]["roof_tarp"])
        out = []
        for a in atoms:
            if a["kind"] != "cover" or a.get("layer") != "membrane" or a["meta"].get("category") != "new": continue
            m = M("prop", "roof", f"{cfg['label']} {TYPICAL}", "", "assumed", cfg.get("plain", "Temporary sheeting over the open roof"), False)
            m.update(stage_in=cfg["stage_in"], seq=cfg.get("seq", 0.9), stage_out=a["meta"]["stage_in"],
                     seq_out=max(0.0, (a["meta"].get("seq") or 0.0) - 0.01), category="temporary")
            b = dict(a, id="TW-tarp-" + a["id"], meta=m, mat="tarp", cat="temporary")
            out.append(b)
        return out

    # ---------------------------------------------------------------- clipping helpers for parts
    def walls_live(self):
        return [a for a in self.atoms if a["kind"] == "wall"]

    def party_closers(self):
        """CORRECTIONS-LOG 191 (Jack: "No.23 and No.21 don't join"): the party wall's cavity was open at its ends, a 94 mm slot
        through the whole terrace from the front to the back between the houses. A cavity wall's free end is closed: one brick
        (102.5 mm) of masonry fills the cavity at each end of a party wall, full height, as the facade brickwork runs across it."""
        from hb_walls import layer_stack as _ls
        out = []
        for a in self.walls_live():
            W = a["wall"]
            if W.ckey != "party" or a["meta"].get("category") == "demolition": continue
            void = [l for l in _ls(W.ckey, W.t) if l.get("void") or "cav" in l["key"]]
            if not void: continue
            c0v, c1v = sorted((W.c_of(void[0]["o0"]), W.c_of(void[-1]["o1"])))
            cl_, ch_ = W.full_extent_c()
            others = [o["wall"].footprint(full=True) for o in self.walls_live() if o is not a and o["wall"].z0 < W.z1 - 0.1 and o["wall"].z1 > W.z0 + 0.1]
            for end, sgn in (("a", 1), ("b", -1)):
                ue = W.end_u(end, (c0v + c1v) / 2); ui = ue + sgn * 0.1025
                ua_, ub_ = sorted((ue, ui))
                top = min(W.z1, W.top_at(ua_), W.top_at(ub_))
                # the closer fills the cavity; where a facade wall stops short of the party wall's face (No.21's walls end
                # 15 mm off the thinner first-floor party wall) it runs on, up to 30 mm, to meet that wall: no slot on the facade
                c0, c1 = c0v, c1v
                fill = []
                for side, cs, step in ((0, cl_, -1), (1, ch_, 1)):
                    for k in range(1, 31):
                        q = W.point(ue + sgn * 0.05, cs + step * (k - 0.5) * 0.001)
                        if any(G.point_in_poly(q, f) for f in others):
                            if k > 2: fill.append(tuple(sorted((cs, cs + step * (k - 1) * 0.001))))
                            break
                for (fa, fb) in fill:
                    Pf = [W.point(ua_, fa), W.point(ub_, fa), W.point(ub_, fb), W.point(ua_, fb)]
                    mf = dict(a["meta"], group="wall_outer", label="facade brickwork run on to meet the party wall (closes a slot on the facade; typical)",
                              plain_label="Facade brickwork", conf="typical")
                    out.append(atom(f"PC-{a['id']}-{end}-fill{len(out)}", "prism", a["meta"].get("category", "existing"), mf, sig=sig_of("pfill", Pf, W.z0, top),
                                    poly=G.ccw(Pf), z0=W.z0, z1=top, mat="existing_brick"))
                P = [W.point(ua_, c0), W.point(ub_, c0), W.point(ub_, c1), W.point(ua_, c1)]
                meta = dict(a["meta"], group="wall_outer", label=f"party wall cavity closed at its {'front' if end == 'a' else 'rear'} end (one brick; typical)",
                            plain_label="Party wall end (brickwork)", conf="typical")
                out.append(atom(f"PC-{a['id']}-{end}", "prism", a["meta"].get("category", "existing"), meta, sig=sig_of("pclose", P, W.z0, top),
                                poly=G.ccw(P), z0=W.z0, z1=top, mat="existing_brick"))
        return out

    def clip_slab(self, a):
        z0, z1 = a["z0"], a["z1"]
        life = S.lifetime(a["meta"], self.N)
        cutters = []
        for w in self.walls_live():
            W = w["wall"]
            wl = S.lifetime(w["meta"], self.N)
            if min(wl[1], life[1]) <= max(wl[0], life[0]): continue
            if min(W.z1, z1 + a.get("clip_reach", 0.0)) - max(W.z0, z0) < 0.002: continue
            fp = W.footprint(full=True)          # linings included: floors stop at the board face
            cutters.append(G.ccw(fp))
        for c in self.extra_cutters(a):
            cutters.append(c)
        pieces = convex_pieces(a["poly"])
        for C in cutters:
            hp = G.poly_halfplanes(C)
            nxt = []
            for P in pieces:
                if G.clip_convex(P, hp): nxt.extend(G.convex_minus(P, hp))
                else: nxt.append(P)
            pieces = nxt
        pieces = [P for P in pieces if abs(G.area(P)) > 1e-5]
        if not pieces: return None
        if a.get("mat")=="spec_FIN-FLR-OAK" and a.get('spec_id','').startswith('FLOOR:'):
            from hb_oak import floor_mesh
            return floor_mesh(pieces,z0,z1)
        if a.get("zfun"):
            zh, zr, ya, yb, t = a["zfun"]
            f = lambda p: zh + (zr - zh) * (p[1] - ya) / (yb - ya)
            return G.merge_meshes([G.prism_varz(P, lambda p: f(p) - t, f) for P in pieces])
        return G.merge_meshes([G.prism(P, z0, z1) for P in pieces])

    def extra_cutters(self, a):
        """joists for the between-joist insulation"""
        if not a.get("between_joists"): return []
        out = []
        for j in self.atoms:
            if j["kind"] == "member" and j["meta"]["group"] == "joist":
                A, B = j["A"], j["B"]
                d = G.unit(G.sub(B[:2], A[:2])); n = (d[1], -d[0]); w = 0.0226
                out.append(G.ccw([G.add(A[:2], G.mul(n, w)), G.add(B[:2], G.mul(n, w)), G.add(B[:2], G.mul(n, -w)), G.add(A[:2], G.mul(n, -w))]))
        return out

    def clip_member(self, a):
        A, B = a["A"], a["B"]
        zt = max(A[2], B[2]); zb = zt - 0.2
        life = S.lifetime(a["meta"], self.N)
        L = G.length(G.sub(B[:2], A[:2]))
        cuts = []
        for w in self.walls_live():
            W = w["wall"]
            wl = S.lifetime(w["meta"], self.N)
            if min(wl[1], life[1]) <= max(wl[0], life[0]): continue
            lay_top = max([W.layer_tops.get(l["key"], W.z1) for l in W.layers() if not l.get("void")] or [W.z1])
            # linings are below the joist zone (room z-range); cores matter
            if min(W.z1, zt) - max(W.z0, zb) < 0.01: continue
            r = G.clip_segment_convex(A[:2], B[:2], G.ccw(W.footprint(full=False)))
            if r: cuts.append((r[0] * L, r[1] * L))
        keep = G.interval_minus([(0, L)], G.merge_intervals(cuts))
        keep = [k for k in keep if k[1] - k[0] > 0.3]
        out = []
        for (s0, s1) in keep:
            f0, f1 = s0 / L, s1 / L
            out.append((tuple(A[i] + (B[i] - A[i]) * f0 for i in range(3)), tuple(A[i] + (B[i] - A[i]) * f1 for i in range(3))))
        return out

    def parts(self):
        key=SPEC_V1_MAP.get(self.v['id'])
        ctx = dict(spec=SPEC, clip_slab=self.clip_slab, clip_member=self.clip_member,spec_rooms=SPEC_V1['versions'][key]['rooms'] if key else [])

        P = []
        for a in self.atoms:
            if a["meta"].get("skip"): continue
            if a['kind']=='fixture' and ctx['spec_rooms']:a['finished_jamb']=True
            for p in S.parts_of(a, ctx):
                p["atom"] = a
                P.append(p)
        return P


# ======================================================================================== Blender side
def uv_layer(me, mode, mat="", brick_v=None):
    """UVs in metres / the material's real tile size. world: walls and solids (horizontal along the face, v = height
    so brick courses line up with the dpc); local: members (u along the member = grain); roof: along the eaves / down
    the slope."""
    if not mode: return
    sx, sy = TILE.get(mat, (1.0, 1.0))
    v0 = 0.0
    tm = TMETA.get(TEXSET.get(mat, ""), {})
    if "v_joint" in tm: v0 = tm["v_joint"]
    uvl = me.uv_layers.new(name="UVMap")
    V = me.vertices
    for poly in me.polygons:
        n = poly.normal
        for li in poly.loop_indices:
            co = V[me.loops[li].vertex_index].co
            if mode == "world":
                if abs(n.z) > 0.7: u, v = co.x / sx, co.y / sy
                else:
                    h = Vector((-n.y, n.x, 0))
                    if h.length > 1e-6: h.normalize()
                    u, v = co.dot(h) / sx, (co.z + 0.032) / sy + v0
            elif mode[0] == "band":                  # a course band (soldier course): v from its own bottom, u along the face
                _, zb, u0b, dd = mode
                u, v = (co.x * dd[0] + co.y * dd[1]) / sx, (co.z - zb) / sy
            elif mode == "local":
                ax = max(range(3), key=lambda k: abs(n[k]))
                if ax == 0: u, v = co.y / sx, co.z / sy
                elif ax == 1: u, v = co.x / sx, co.z / sy
                else: u, v = co.x / sx, co.y / sy
            else:
                _, e, d, cs = mode
                u = (co.x * e[0] + co.y * e[1]) / sx
                v = -(co.x * d[0] + co.y * d[1]) / cs / sy
            uvl.data[li].uv = (u, v)


def roof_uv(me, mode, mat):
    uv_layer(me, mode, mat)


def manifold_cells(bm, tol=1e-5):
    """closed cells (boxes) merged into one mesh -> one closed outward shell: faces that coincide (same corners, within
    tol) are interior and both go; then the corners weld. A part that is still open after that keeps its cells as
    separate closed pieces (each closed, normals per piece), never an inside-out or open shell."""
    from mathutils import kdtree
    kd = kdtree.KDTree(len(bm.verts))
    for i, v in enumerate(bm.verts): kd.insert(v.co, i)
    kd.balance()
    canon = {}
    for i, v in enumerate(bm.verts):
        if i in canon: continue
        for (_, j, _) in kd.find_range(v.co, tol): canon.setdefault(j, i)
    bm.verts.index_update()
    seen = {}
    for f in bm.faces:
        seen.setdefault(frozenset(canon[v.index] for v in f.verts), []).append(f)
    dup = [f for fs in seen.values() if len(fs) > 1 for f in fs]
    snapshot = None
    if dup:
        bmesh.ops.delete(bm, geom=dup, context="FACES_ONLY")
        loose = [v for v in bm.verts if not v.link_faces]
        if loose: bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=tol)
    return all(e.is_manifold for e in bm.edges)


def build_blender(vb, MAT, coll):
    parts = vb.parts()
    from hb_carrier_faces import CarrierFaces
    vkey=SPEC_V1_MAP.get(vb.v['id'])
    faces=CarrierFaces(vb,SPEC_V1['versions'][vkey]['rooms']) if vkey and not args.no_items else None
    meshes_by_key = {}
    objs = []
    for p in parts:
        if "local" in p:
            key = p["key"]
            me = meshes_by_key.get(key)
            if me is None:
                V, F = p["local"]
                me = bpy.data.meshes.new(p["name"] + "_m")
                me.from_pydata(V, [], F)
                bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
                uv_layer(me, "local", p["mat"])
                me.materials.append(MAT[p["mat"]])
                meshes_by_key[key] = me
            ob = bpy.data.objects.new(p["name"], me)
            ob.matrix_world = Matrix(p["matrix"])
        else:
            V, F = p["mesh"]
            if not F: continue
            me = bpy.data.meshes.new(p["name"])
            me.from_pydata([tuple(v) for v in V], [], [tuple(f) for f in F])
            me.validate(clean_customdata=False)
            bm = bmesh.new(); bm.from_mesh(me)
            if not p.get("open_sheet"):
                # wall cells of one part share whole faces: drop BOTH faces of every shared pair, then weld -> one manifold.
                # (row 179: welding first let bmesh keep one face of each pair; the leftover interior faces made the shell
                # non-manifold and recalc_face_normals turned whole walls inside out: "missing surfaces" in the headset)
                if not manifold_cells(bm):
                    bm.free(); bm = bmesh.new(); bm.from_mesh(me)          # T-junctions: keep the closed cells apart
                    NOTES_MANIFOLD.append(p["name"])
            # every other part is a set of separate closed pieces: normals fixed island by island
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
            if p.get("uv") and p["uv"] != "world": uv_layer(me, p["uv"], p["mat"])
            else: uv_layer(me, "world", p["mat"])
            me.materials.append(MAT[p["mat"]])
            if faces and p['atom']['kind']=='wall' and not p['props'].get('stage_out') and not p['props'].get('context') and p['props']['group'] in ('wall_outer','wall_inner','wall_insulation'):
                faces.assign(p,me,MAT)
            ob = bpy.data.objects.new(p["name"], me)
        for k, v in p["props"].items():
            if v is None: continue
            ob[k] = v
        coll.objects.link(ob)
        objs.append((ob, p))
    return objs


# ======================================================================================== checks: supports and clashes per stage
ALLOW = [  # (group a, group b, why) intended contacts that pass into each other
    ("rafter", "wall_plate", "rafters birdsmouthed over the wall plate"), ("rafter", "hip", "jack rafters cut against the hip"),
    ("rafter", "ridge", "rafters nailed to the ridge board"), ("rafter", "valley", "rafters cut to the valley"),
    ("hip", "ridge", "hips meet the ridge"), ("hip", "hip", "hips meet at the apex"), ("hip", "wall_plate", "hip birdsmouthed over the plate corner"),
    ("valley", "ridge", "valley meets the ridge"), ("valley", "valley", "valley members meet"), ("valley", "hip", "valley meets the hip"),
    ("valley", "wall_plate", "valley rafter on the plate"),
    ("ceiling_joist", "rafter", "ceiling joists nailed to the rafter feet"), ("ceiling_joist", "wall_plate", "ceiling joists notched on the plate"),
    ("roof_cover", "roof_cover", "tiles, ridge tiles, fascia and gutters overlap at their laps"), ("roof_cover", "roof_layer", "tiles on battens"),
    ("roof_layer", "roof_layer", "membrane and battens lap"), ("roof_cover", "valley", "tiles dressed over the valley lead"),
    ("roof_cover", "rooflight", "roof window flashed into the tiles"), ("roof_layer", "rooflight", "roof window set into the battens"),
    ("rooflight", "rafter", "roof window between trimmers"), ("prop", "slab_layer", "prop base sits through the new slab layers (typical)"),
    ("prop", "deck", "prop passes the boarding (typical)"), ("prop", "wall_outer", "needle through a hole in the wall (typical)"),
    ("prop", "wall_inner", "needle through a hole in the wall (typical)"), ("prop", "wall_lining", "needle through the lining"),
    ("prop", "prop", "prop heads under the needles"), ("foundation", "foundation", "new trench fill poured against the exposed existing footing"),
    ("drain", "ground", "drain laid in its trench and backfilled"), ("drain", "foundation", "drain passes under / through the substructure in its sleeve"),
    ("drain", "slab_layer", "drain under the slab in its sleeve"), ("fitting", "ground", "set on / into the ground"), ("scaffold", "wall_outer", "scaffold tie to the wall"), ("scaffold", "roof_cover", "scaffold at the eaves"),
    ("scaffold", "window", "tie through an opening"), ("prop", "ground", "Heras feet on the ground"), ("fitting", "fitting", "site set-up items"), ("scaffold", "scaffold", "scaffold fittings"),
    ("scaffold", "ground", "scaffold base plates on the ground"), ("spoil", "ground", "spoil heap on the ground"),
    ("fitting", "fitting", "sanitary ware parts"), ("lintel", "steel", "padstones and packers under the steel"),
    ("window", "lintel", "frame tight under the lintel"), ("door", "lintel", "frame tight under the lintel"),
    ("roof_cover", "wall_outer", "flashing / fascia against the wall head"), ("roof_cover", "rafter", "fascia nailed to the rafter feet"),
]


ALLOW_NAMES = [("DPC-", "_wall_", "dpc strip bedded in the joint"), ("WT-", "_wall_", "wall ties built into both leaves through the insulation"),
               ("CT-", "_wall_", "cavity tray built in over the lintel"), ("CT-", "L-", "cavity tray dressed over the lintel"), ("CC-", "_wall_", "cavity closer at the reveal"),
               ("VJ-", "_wall_", "vertical dpc / starter at the junction"), ("JH-", "_wall_", "hanger flange against the inner leaf"), ("JH-", "J-ff", "joist in its hanger"),
               ("RS-", "_wall_", "strap fixed to the inner leaf"), ("RS-", "WP-", "strap over the plate"), ("DR-", "_wall_", "pipe through the substructure under its lintel"),
               ("DR-", "L-pipe", "pipe under its lintel"), ("DR-", "DR-", "pipe connects into its chamber / gully / soakaway"), ("RE-", "L-F-", "eaves soffit board over the lintel toe at the wall head"), ("-cavfill", "_wall_outer", "cavity fill meets the return leaf at the corner (below ground)"),
    ("DR-L-pipe", "-cavfill", "pipe lintel bedded in the cavity fill"), ("-pad", "_wall_lining", "lining cut round the padstone when the room is dry-lined"), ("TW-sheet", "", "temporary sheeting fixed over the opened structure"), ("TW-tarp-", "", "tarpaulin battened over the rafters"),
    ("TW-protect", "", "protection boards laid on the floor"), ("TW-site", "G-site", "site set-up items stand on the ground"), ("TW-site", "G-dug", "site set-up items stand on the ground"),
    ("TW-site", "G-reinst", "site set-up items stand on the ground"), ("TW-site", "FN-", "Heras panel feet by the boundary fence"), ("TW-scaffold", "G-site", "scaffold sole boards on the ground"), ("TW-scaffold", "G-dug", "scaffold sole boards on the ground"), ("TW-scaffold", "G-reinst", "scaffold sole boards on the ground"),
    ("TW-scaffold", "TW-sheet", "sheeting fixed to the scaffold"), ("DR-", "G-site", "drain bedded in the ground"), ("DR-", "G-dug", "drain in its trench"), ("DR-", "G-reinst", "drain backfilled"),
    ("DR-", "FD-", "drain below / beside the trench fill"), ("DR-", "SL", "drain under the slab"), ("DR-", "XF-", "existing drain under the old floor"), ("FN-", "G-site", "fence posts set into the ground"), ("FN-", "G-dug", "fence posts set into the ground"), ("FN-", "G-reinstated", "fence posts set into the ground"),
               ("-studs", "B-beam", "partition head plate fixed to the beam soffit"), ("RV-house-main", "B-beam-3", "existing valley rafter foot packed onto the new beam (detail not drawn)"),
               ("CH-stack", "RR-", "ridge board stops at the stack (not drawn)"), ("RR-house-main", "F-party", "ridge board built into the party wall gable"), ("RR-house-main", "G-party", "ridge board built into the party wall"),
               ("CH-stack", "G-party", "stack built off the party wall"), ("CH-stack", "F-party", "stack built off the party wall"),
               ("CH-stack", "RC-", "stack passes through the roof (flashed)"), ("CH-stack", "RM-", "stack passes through the roof"),
               ("CH-stack", "RB-", "stack passes through the battens"), ("CH-stack", "RF-", "rafter trimmed round the stack (not drawn)"),
               ("-a393", "-rc", "mesh cast into the slab"), ("-a393", "SL", "mesh cast into the slab"),
               ("TH-", "_wall_", "threshold board in the doorway, on the wall lowered 20 mm under it"), ("TH-", "F-", "threshold under the door frame"),
               ("TH-", "XF-", "threshold meets the floor"), ("CL-porch-vault", "RL-porch", "vault lining cut round the roof window"),
               ("CL-porch-vault", "B-beam-1", "vault lining dressed over the beam where the rafters sit on it"), ("CL-porch-vault", "RF-porch", "lining fixed to the rafter undersides"),
               ("CL-porch-vault", "RT-porch", "lining fixed to the trimmers"), ("SC-beam", "B-beam", "boxing fixed round the steel"), ("SC-beam", "_wall_", "boxing meets the wall at the beam ends"), ("G-stair_", "SPEC-FLR-R-g-hall", "hall floor finish notched round the stair spine wall (as the hall floor)"), ("SPEC-SKIRT", "FT-G-pier", "skirting runs on behind the pier (hidden in it)"), ("SPEC-FLR", "SL", "floor finish laid on the slab (4 mm into the screed line)"), ("G-kitRear~d2_L0_wall_lining", "FR-outshot", "single-storey option (draft): the kept kitchen wall's lining meets the outshot roof's edge; walls under flat roofs now rise to them (row 179)"), ("SPEC-FLR", "XF-", "floor finish laid on the floor (4 mm in)"), ("SPEC-FLR", "DK-", "floor finish laid on the deck"), ("SPEC-SKIRT", "_wall_lining", "skirting fixed against the wall lining (scribed into it, <= 8 mm)"), ("SPEC-SKIRT", "_wall_inner", "skirting fixed against the plastered inner leaf (scribed, <= 8 mm)"), ("CL-porch-vault", "G-porchL_L5_wall_lining", "vault lining runs to the as-built porch wall face; the drawn wall it replaces is hidden when As built is on"), ("SPEC-SKIRT", "FT-F-flank-pier", "skirting runs on behind the pier (hidden in it)"), ("SPEC-SKIRT", "FT-G-chimney", "skirting runs on behind the breast (hidden in it)"), ("SPEC-SKIRT", "FT-F-chimney", "skirting runs on behind the breast (hidden in it)"), ("G-stair_", "XF-G-hall", "hall floor notched round the stair spine wall (floor vertices on the wall faces x 4.515 / 4.645; the depth test misreads the notch corner)"), ("TH-", "SL", "threshold meets the floor"), ("TH-", "DK-", "threshold meets the deck"),
               ("RC-porch", "G-porchL", "porch tiles bedded over the raking side-wall head at the verge (4 mm, the drawn verge detail)"),
               ("RC-porch", "VJ-G-porchF", "vertical dpc dressed under the porch tiles at the abutment"),
               ("RB-porch", "G-porchL", "porch battens carried over the raking side-wall head to the verge"),
               ("RB-house-ext", "G-extRear", "battens carried over the raking wall head under the catslide"),
               ("RM-house-ext", "G-extRear", "membrane over the raking wall head under the catslide")]
ALLOW += [("timber_beam", "wall_plate", "beam end notched into the wall plate where it bears (detail not drawn)"), ("valley", "timber_beam", "valley rafter seated on the flitch beam"), ("hip", "ceiling_joist", "hip foot over the ceiling edge at the wall"), ("valley", "ceiling_joist", "valley foot over the ceiling edge at the wall"),
          ("hip", "roof_cover", "hip tail under the fascia / gutter"), ("valley", "roof_cover", "valley tail under the fascia"), ("hip", "wall_outer", "hip birdsmouthed over the wall head at the corner"), ("hip", "wall_inner", "hip over the wall head at the corner"),
          ("hip", "wall_lining", "hip over the wall head"), ("valley", "wall_outer", "valley over the wall head at the corner"),
          ("valley", "wall_inner", "valley over the wall head"), ("valley", "wall_lining", "valley over the wall head"),
          ("hip", "roof_layer", "battens/membrane over the hip"), ("ridge", "roof_layer", "membrane over the ridge"),
          ("ceiling_joist", "hip", "ceiling joists nailed to the hip foot"), ("rafter", "rafter", "rafters meeting at hips and valleys"),
          ("roof_layer", "rafter", "battens nailed to the rafters"), ("roof_layer", "valley", "battens over the valley board")]


# joinery to the bar (hb_joinery; row 183/191): trims are scribed into what they meet, as fitted on site
ALLOW_NAMES += [("ST-soffit", "_wall_lining", "the stair soffit's plasterboard is scribed 5 mm into the wall lining each side (row 191)"),
                ("PC-", "_wall_", "party wall end: the closer is bonded into the party wall leaves"), ("PC-", "N21-", "party wall end meets No.21's facade"),
                ("_architraves", "_wall_", "architrave cut / scribed to a return wall beside the opening (<= 35 mm, typical)"),
                ("_architraves", "-studs", "architrave cut to a stud partition beside the opening"),
                ("_architraves", "_architraves", "two doors at a corner: their architraves are cut to each other (typical)"),
                ("SPEC-SKIRT", "_wall_", "skirting scribed into the wall face (<= 10 mm)"), ("SPEC-SKIRT", "-studs", "skirting scribed into the partition (<= 10 mm)"),
                ("SPEC-SKIRT", "_frame", "skirting butts the door lining (<= 8 mm scribe)"), ("SPEC-SKIRT", "ST-", "skirting scribed to the stair / guard"),
                ("SPEC-SKIRT", "_architraves", "skirting returned against the architrave"),
                ("WB-", "_wall_", "window board horns notched into the reveals (<= 30 mm)"), ("WB-", "_frame", "window board under the frame's inner edge"),
                ("_stops", "_frame", "stops pinned to the lining"), ("_hinges", "_frame", "hinges let into the lining"), ("_hinges", "_leaf", "hinges let into the leaf edge"),
                ("_architraves", "_frame", "architrave fixed to the lining edge"), ("_architraves", "SPEC-FLR", "architrave stands on the floor finish")]


def mesh_world(ob):
    me = ob.data
    mw = ob.matrix_world
    V = [mw @ v.co for v in me.vertices]
    me.calc_loop_triangles()
    T = [tuple(t.vertices) for t in me.loop_triangles]
    return V, T


def support_samples(V, T, cap=900):
    """points on the downward-facing faces (and the lowest vertices) of a part, about every 30 mm"""
    pts = []
    zmin = min(v.z for v in V)
    pts += [v for v in V if v.z < zmin + 0.004][:16]
    for t in T:
        a, b, c = V[t[0]], V[t[1]], V[t[2]]
        n = (b - a).cross(c - a)
        if n.length < 1e-9 or n.normalized().z > -0.2: continue
        m = max((b - a).length, (c - a).length, (c - b).length)
        k = max(2, min(60, int(m / 0.03)))
        for i in range(k + 1):
            for j in range(0, k + 1 - i, max(1, k // 6)):
                pts.append(a + (b - a) * (i / k) + (c - a) * (j / k))
        if len(pts) > cap: break
    return pts


def bearing_samples(V, T, cap=600):
    """(point, normal) on the part's downward-facing faces, about every 30 mm"""
    out = []
    for t in T:
        a, b, c = V[t[0]], V[t[1]], V[t[2]]
        n = (b - a).cross(c - a)
        if n.length < 1e-9: continue
        n = n.normalized()
        if n.z > -0.2: continue
        m = max((b - a).length, (c - a).length, (c - b).length)
        k = max(2, min(40, int(m / 0.03)))
        for i in range(1, k):
            for j in range(1, k - i, max(1, k // 6)):
                out.append((a + (b - a) * (i / k) + (c - a) * (j / k), n))
        if len(out) > cap: break
    return out


def sits_on(tree, pts, tol=0.006, depth=0.03):
    """a bearing face of the part rests on (within tol) or bears into (up to depth) an opposing, upward face of the tree"""
    for v, n in pts:
        loc, nrm, idx, dist = tree.find_nearest(v, depth)
        if loc is None or nrm.z < 0.3 or nrm.dot(n) > -0.7: continue
        if dist <= tol or (v - loc).dot(nrm) < 0: return True
    return False


def touches(tree, pts, tol=0.006):
    for v in pts:
        loc, nrm, idx, dist = tree.find_nearest(v)
        if loc is None: continue
        if dist <= tol or (v - loc).dot(nrm) < 0: return True
    return False


def run_checks(vb, objs, tol=0.004):
    """per stage end-state: (1) nothing floats: every part touches (from below, or bears into) a part present at its
    time, or is held by a temporary needle/prop passing through it; (2) no part passes into another by more than tol
    unless the pair is an intended contact."""
    N = vb.N
    info = []
    for ob, p in objs:
        pr = p["props"]
        V, T = mesh_world(ob)
        P = np.array([tuple(v) for v in V])
        ab = p.get("atom", {}).get("as_built")
        info.append(dict(ctx=bool(p.get("context")), ob=ob, p=p, si=pr["stage_in"], so=pr.get("stage_out") or (N + 1), seq=pr["seq"], sqo=pr.get("seq_out", 1.0), g=pr["group"],
                         el=pr["element"], cat=pr["category"], V=V, T=T, lo=P.min(0), hi=P.max(0),
                         ab=set(ab["replaces"]) if ab else None))
    trees = {}
    def tree(i):
        if i not in trees: trees[i] = BVHTree.FromPolygons(info[i]["V"], info[i]["T"])
        return trees[i]
    lo = np.array([x["lo"] for x in info]); hi = np.array([x["hi"] for x in info])
    # supporters of every part, whatever the time
    sup = []
    for i, x in enumerate(info):
        if x["g"] == "ground": sup.append([]); continue
        pts = support_samples(x["V"], x["T"])
        ov = np.all((np.minimum(hi[i], hi) - np.maximum(lo[i], lo)) > -0.007, axis=1)
        cand = [j for j in np.nonzero(ov)[0] if j != i]
        s_ = []
        for j in cand:
            if info[j]["g"] == "prop" and tree(i).overlap(tree(j)): s_.append(j); continue      # needle through it
            if touches(tree(j), pts): s_.append(j)
        sup.append(s_)
    def present(j, s, after_seq=None):
        x = info[j]
        if not (x["si"] <= s < x["so"]): return False
        if after_seq is not None and x["si"] == s and x["seq"] > after_seq + 1e-9: return False
        return True
    floating = []
    for s in range(1, N + 1):
        for i, x in enumerate(info):
            if x["g"] == "ground" or not (x["si"] <= s < x["so"]): continue
            if x["ab"] is not None and any(info[j]["ab"] is None or info[j]["ab"] is not None for j in sup[i]) and sup[i]: continue
            seq = x["seq"] if x["si"] == s else None
            if not any(present(j, s, seq) for j in sup[i]):
                floating.append(dict(stage=s, part=x["ob"].name, element=x["el"], group=x["g"], z=round(float(x["lo"][2]), 3)))
    # cross-stage bearing: nothing appears before everything that carries it (CORRECTIONS-LOG 117). A carrier is a part
    # under this one's bearing faces (or that it bears into) that can carry: not temporary works, the ground, linings,
    # insulation, ceilings hung from above, glazing, drains or fittings.
    bearing = []
    for i, x in enumerate(info):
        if x["g"] == "ground" or x["cat"] == "temporary" or x["ab"] is not None or x["si"] == 1 or x["g"] in NOT_CARRIED: continue
        pts = None
        for j in sup[i]:
            y = info[j]
            if y["el"] == x["el"] or not carries(y, x): continue
            if not (y["si"] > x["si"] or (y["si"] == x["si"] and y["seq"] > x["seq"] + 1e-9)): continue
            if pts is None: pts = bearing_samples(x["V"], x["T"])
            if not sits_on(tree(j), pts): continue              # an opposing face of j is under this part's bearing face
            if True:
                why = bearing_allowed(y, x)
                bearing.append(dict(part=x["ob"].name, element=x["el"], group=x["g"], stage=x["si"], seq=round(x["seq"], 3),
                                    carrier=y["ob"].name, carrier_element=y["el"], carrier_group=y["g"], carrier_stage=y["si"],
                                    carrier_seq=round(y["seq"], 3), allowed=why))
    run_checks.bearing = bearing
    # report each floating part once (first stage), with the stages it floats in
    fl = {}
    for f in floating:
        k = f["part"]
        if k in fl: fl[k]["stages"].append(f["stage"])
        else: fl[k] = dict(f, stages=[f["stage"]])
    clashes = {}
    for s in range(1, N + 1):
        pres = [i for i, x in enumerate(info) if x["si"] <= s < x["so"]]
        pset = set(pres)
        for i in pres:
            if info[i]["si"] != s and s != 1: continue
            ov = np.all((np.minimum(hi[i], hi) - np.maximum(lo[i], lo)) > tol, axis=1)
            for j in np.nonzero(ov)[0]:
                if j == i or j not in pset: continue
                a, b = info[i], info[j]
                key = tuple(sorted((a["ob"].name, b["ob"].name)))
                if key in clashes: continue
                if a["el"] == b["el"] or a["ctx"] or b["ctx"]: continue
                if a["ab"] is not None and (b["el"] in a["ab"] or (b["ab"] is not None)): continue      # as-built record over the drawn part it replaces
                if b["ab"] is not None and a["el"] in b["ab"]: continue
                if (a["ab"] is not None or b["ab"] is not None) and any(r in (a["ab"] or set()) | (b["ab"] or set()) for r in (a["el"], b["el"])): continue
                why = allowed(a, b)
                if not tree(i).overlap(tree(j)): continue
                d = depth(a, b, tree(i), tree(j))
                if d > tol:
                    clashes[key] = dict(stage=s, a=a["ob"].name, b=b["ob"].name, ga=a["g"], gb=b["g"], depth=round(d, 4),
                                        allowed=why, at=[round(float(v), 2) for v in (np.maximum(a["lo"], b["lo"]) + np.minimum(a["hi"], b["hi"])) / 2])
    return list(fl.values()), sorted(clashes.values(), key=lambda c: -c["depth"])


NON_CARRIER = {"ground", "prop", "scaffold", "spoil", "wall_insulation", "wall_lining", "wall_cavity", "drain", "window", "door", "fitting",
               "rooflight", "roof_cover"}
NON_CARRIER_MATS = {"plasterboard", "mineral_wool", "glass", "vcl", "tarp", "heras", "membrane"}
NON_CARRIER_MATS = set(NON_CARRIER_MATS) | {"spec_FIN-WALL", "spec_FIN-CEIL", "spec_FIN-SKIRT", "spec_FIN-FLR-OAK", "spec_FIN-FLR-TILE"}      # painted linings / ceilings and skirting carry nothing
NOT_CARRIED = {"wall_lining", "wall_cavity", "wall_insulation", "roof_cover", "drain"}        # fixed to their wall / laps, not borne by what is under them
BEARING_ALLOW = [  # (carrier name part, carried name part, why) where the carrier below is fixed after what sits on it
    ("INS-", "", "insulation laid between joists from below / above: carries nothing"),
    ("-cavfill", "", "cavity fill poured after the leaves: carries nothing"),
    ("-studs", "B-beam", "partition head plate fixed up to the beam soffit; the beam bears at its ends"),
]


CARRIES_ONLY = {"roof_layer": {"roof_cover", "roof_layer", "rooflight"}}     # battens carry tiles, never walls


def carries(y, x):
    if y["cat"] == "temporary" or y["g"] in NON_CARRIER or y["ab"] is not None: return False
    if y["g"] in CARRIES_ONLY and x["g"] not in CARRIES_ONLY[y["g"]]: return False
    m = (y["ob"].active_material.name if y["ob"].active_material else "").split(".")[0]
    if m in NON_CARRIER_MATS: return False
    if y["g"] == "ceiling_joist" and m in ("plasterboard", "spec_FIN-WALL"): return False
    return True


def bearing_allowed(y, x):
    for a, b, why in BEARING_ALLOW:
        if a in y["ob"].name and b in x["ob"].name: return why
    return None


LEAF_BLOCKERS = {"wall_outer", "wall_inner", "wall_lining", "fitting", "door", "window", "steel", "lintel", "prop", "slab_layer", "deck"}


HW_NAME = re.compile(r"door-furniture|_handle$|letter|lever|knocker", re.I)


def tag_leaf_hardware(objs):
    """Everything fixed to a door leaf swings with it (Jack's walk 2, F101: the front door's handle and letter plate stayed put when
    the leaf opened). A hardware part (handle, lever, letter plate, knocker, the as-built 'door furniture') that is not itself a leaf
    but sits on one (its centre inside the leaf's box, grown 6 cm, in a stage where both exist) takes that leaf's door_group,
    leaf_index, hinge, axis and swing, and door_leaf=True / part='handle', exactly as the internal doors' levers already do.
    Hinges stay on the frame (their knuckle is on the axis); a bell or camera beside the door is not in the leaf's box."""
    leaves = [(ob, p) for ob, p in objs if p["props"].get("door_leaf") and p["props"].get("part") in ("leaf",)]
    n_tag = 0; tagged = []
    for ob, p in objs:
        pr = p["props"]
        if pr.get("door_leaf") or pr.get("group") not in ("door", "fitting") or not HW_NAME.search(ob.name): continue
        V, T = mesh_world(ob)
        if not V: continue
        P = np.array([tuple(v) for v in V]); c = (P.min(0) + P.max(0)) / 2
        best = None
        for lob, lp in leaves:
            lpr = lp["props"]
            if min(lpr.get("stage_out") or 99, pr.get("stage_out") or 99) <= max(lpr.get("stage_in", 1), pr.get("stage_in", 1)): continue
            LV, _ = mesh_world(lob)
            LP = np.array([tuple(v) for v in LV]); lo, hi = LP.min(0) - 0.12, LP.max(0) + 0.12      # a lever stands 6-7 cm proud of the leaf: boxes overlap, not centres
            if np.all(P.max(0) >= lo) and np.all(P.min(0) <= hi):
                vol = float(np.prod(hi - lo)) * (1.0 if lob.name.startswith("AB-") == ob.name.startswith("AB-") else 4.0)   # the same layer's leaf first
                if best is None or vol < best[0]: best = (vol, lob, lp)
        if best is None:
            near = sorted(((float(np.linalg.norm(c - (np.array([tuple(v) for v in mesh_world(lob)[0]]).min(0) + np.array([tuple(v) for v in mesh_world(lob)[0]]).max(0)) / 2)), lob.name) for lob, _ in leaves))[:2]
            print("door hardware not on any leaf:", ob.name, [round(float(x), 3) for x in c], near, "stage", pr.get("stage_in"), pr.get("stage_out"))
            continue
        _, lob, lp = best; lpr = lp["props"]
        upd = dict(door_leaf=True, part="handle", door_group=lpr["door_group"], leaf_index=lpr.get("leaf_index", 0), hinge=list(lpr["hinge"]),
                   hinge_axis=list(lpr.get("hinge_axis", [0.0, 1.0, 0.0])), swing_deg=float(lpr["swing_deg"]))
        for k, v in upd.items():
            pr[k] = v; ob[k] = v
        n_tag += 1; tagged.append(ob.name)
    return tagged



def leaf_swing_check(vb, objs):
    """every door leaf opened to its swing angle (and halfway) must be clear of walls, fittings, frames and the other
    leaves opened with it ('open all'); a leaf that would hit something swings less, in 5-degree steps (recorded)"""
    N = vb.N
    handles = [(ob, p) for ob, p in objs if p["props"].get("door_leaf") and p["props"].get("part") == "handle"]
    leaves = [(ob, p) for ob, p in objs if p["props"].get("door_leaf") and p["props"].get("part") != "handle"]
    if not leaves: return []
    rest = []
    for ob, p in objs:
        pr = p["props"]
        if pr.get("door_leaf") or pr["group"] not in LEAF_BLOCKERS or p.get("context"): continue
        if ob.name.endswith(("_architraves", "_hinges")): continue      # an 18 mm trim on the next wall: the leaf rests against it
        if pr.get("as_built") and pr["group"] in ("door", "window"): pass
        V, T = mesh_world(ob)
        if not T: continue
        P = np.array([tuple(v) for v in V])
        rest.append(dict(ob=ob, pr=pr, V=V, T=T, lo=P.min(0), hi=P.max(0), tree=None))
    def tree(r):
        if r["tree"] is None: r["tree"] = BVHTree.FromPolygons(r["V"], r["T"])
        return r["tree"]
    opened = []          # leaves already placed open: (lo, hi, V, tree, (si, so))
    report = []
    def life(pr): return pr["stage_in"], (pr.get("stage_out") or N + 1)
    for ob, p in leaves:
        pr = p["props"]
        V0, T = mesh_world(ob)
        h = pr["hinge"]; hx, hy = h[0], -h[2]                      # viewer -> drawing plan
        lf = life(pr)
        def at(angle):
            ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            slide = pr.get("slide")
            dx, dy = (slide[0], -slide[2]) if slide else (0.0, 0.0)
            return [Vector((hx + (v.x - hx) * ca - (v.y - hy) * sa + dx, hy + (v.x - hx) * sa + (v.y - hy) * ca + dy, v.z)) for v in V0]
        def hits(V):
            P = np.array([tuple(v) for v in V]); lo, hi = P.min(0), P.max(0)
            tL = BVHTree.FromPolygons(V, T)
            for r in rest:
                rl = life(r["pr"])
                if min(rl[1], lf[1]) <= max(rl[0], lf[0]): continue
                if r["pr"]["element"] == pr["element"]: continue
                if bool(r["pr"].get("as_built")) != bool(pr.get("as_built")) and r["pr"]["group"] in ("door", "window", "wall_outer", "wall_inner", "wall_lining"): continue   # a layer and the drawing it replaces
                if np.any(np.minimum(hi, r["hi"]) - np.maximum(lo, r["lo"]) <= 0.004): continue
                if not tL.overlap(tree(r)): continue
                d = depth(dict(V=V, lo=lo, hi=hi), dict(V=r["V"], lo=r["lo"], hi=r["hi"]), tL, tree(r))
                if d > 0.004: return r["ob"].name, d
            for (olo, ohi, oV, otree, ol, oel) in opened:
                if oel == pr["door_group"] and pr.get("slide"): continue
                if min(ol[1], lf[1]) <= max(ol[0], lf[0]): continue
                if np.any(np.minimum(hi, ohi) - np.maximum(lo, olo) <= 0.004): continue
                if tL.overlap(otree):
                    d = depth(dict(V=V, lo=lo, hi=hi), dict(V=oV, lo=olo, hi=ohi), tL, otree)
                    if d > 0.004: return "open leaf " + oel, d
            return None
        full = float(pr["swing_deg"]); sgn = 1 if full > 0 else -1
        ang, hit = abs(full), None
        first_hit = None
        while ang >= 30:
            hit = hits(at(sgn * ang)) or (hits(at(sgn * ang / 2)) if not pr.get("slide") else None)
            if not hit: break
            first_hit = first_hit or hit
            ang -= 5
        if hit: ang = 30
        blocker = hit or first_hit
        if ang != abs(full):
            ob["swing_deg"] = float(sgn * ang); pr["swing_deg"] = float(sgn * ang)
            ob["swing_note"] = (pr.get("swing_note", "") + f"; opens {ang} deg, not 90: at 90 it would hit {blocker[0] if blocker else '?'}").strip("; ")
            pr["swing_note"] = ob["swing_note"]
        Vf = at(sgn * ang); P = np.array([tuple(v) for v in Vf])
        opened.append((P.min(0), P.max(0), Vf, BVHTree.FromPolygons(Vf, T), lf, pr["door_group"]))
        report.append(dict(leaf=ob.name, door=pr["door_group"], swing_deg=sgn * ang, drawn=abs(full), hit=(blocker[0] if blocker and ang != abs(full) else None),
                           conf=pr.get("swing_conf")))
        for hob, hp in handles:                    # the lever moves with its leaf: same hinge, same swing
            if hp["props"].get("door_group") == pr["door_group"] and hp["props"].get("leaf_index") == pr.get("leaf_index"):
                hob["swing_deg"] = float(sgn * ang); hp["props"]["swing_deg"] = float(sgn * ang)
    return report


def opening_checks(vb, objs):
    """every opening's clear box (sill to head, jamb to jamb, through the wall) must be free of lintels, beams,
    padstones and plates: a door head inside a beam is a clash, not a contact"""
    hits = []
    hard = [(ob, p) for ob, p in objs if p["props"]["group"] in ("lintel", "steel", "timber_beam", "wall_plate")]
    data = []
    for ob, p in hard:
        V, T = mesh_world(ob)
        data.append((ob, p, V))
    for a in vb.atoms:
        if a["kind"] != "wall" or a["meta"].get("category") == "demolition": continue
        W = a["wall"]
        for o in W.openings:
            if o.get("infilled"): continue
            u0, u1, z0, z1 = o["u0"] + 0.002, o["u1"] - 0.002, o["z0"] + 0.002, o["z1"] - 0.002
            for ob, p, V in data:
                n = 0
                for v in V:
                    rel = (v.x - W.a[0], v.y - W.a[1]); u = rel[0] * W.d[0] + rel[1] * W.d[1]; c = rel[0] * W.n[0] + rel[1] * W.n[1]
                    if u0 < u < u1 and z0 < v.z < z1 and -W.t / 2 - 0.05 < c < W.t / 2 + 0.05: n += 1
                if n:
                    zs = [v.z for v in V]
                    hits.append(dict(opening=o["id"], wall=W.id, part=ob.name, group=p["props"]["group"], head=round(o["z1"], 4),
                                     part_bottom=round(min(zs), 4), overlap_mm=round((o["z1"] - min(zs)) * 1000, 1)))
    return hits


def allowed(a, b):
    ga, gb = a["g"], b["g"]
    na, nb = a["ob"].name, b["ob"].name
    for (x, y, why) in ALLOW_NAMES:
        if (x in na and y in nb) or (x in nb and y in na): return why
    for x, y, why in ALLOW:
        if (ga == x and gb == y) or (ga == y and gb == x): return why
    if a["p"]["props"]["category"] == "temporary" and b["p"]["props"]["category"] == "temporary": return "temporary works parts"
    return None


def in_closed_solid(point,tree):
    # The closest plane of a U-shaped jamb is not a containment test.
    # Signed exit crossings also work for a part made of several closed cells.
    votes=0
    for direction in (Vector((.831,.257,.491)).normalized(),Vector((-.317,.911,.263)).normalized(),Vector((.211,-.473,.855)).normalized()):
        origin=point;score=0
        while True:
            hit,normal,_,_=tree.ray_cast(origin,direction)
            if hit is None:break
            side=normal.dot(direction)
            if abs(side)>1e-7:score+=1 if side>0 else -1
            origin=hit+direction*.00002
        if score>0:votes+=1
        if votes==2:return True
    return False


def depth(a, b, ta, tb):
    """deepest vertex of one inside the other (closed meshes, outward normals), vertices in the common box only"""
    d = 0.0
    lo = np.maximum(a["lo"], b["lo"]) - 0.002; hi = np.minimum(a["hi"], b["hi"]) + 0.002
    for (x, t) in ((a, tb), (b, ta)):
        vs = [v for v in x["V"] if lo[0] <= v.x <= hi[0] and lo[1] <= v.y <= hi[1] and lo[2] <= v.z <= hi[2]]
        if len(vs) > 4000: vs = vs[::len(vs) // 4000 + 1]       # thin evenly, never just the first few hundred (log: hidden clash)
        for v in vs:
            loc, nrm, idx, dist = t.find_nearest(v)
            if loc is not None and dist>d and (v-loc).dot(nrm)<-1e-5 and in_closed_solid(v,t):
                d=dist
    return d


# ======================================================================================== ground (boolean: once per version state)
def ground_objects(vb, MAT, coll):
    """the site as closed convex prisms (no booleans): priority-ordered zones (spec 'site_zones': surveyed paths, beds,
    lawn and paving, assumed patio / drive / street, the neighbours' gardens, a far field to the horizon), each at its
    level and in its own material on top (soil in the sides). Where the house sits (and, for proposals, the trenches and
    slab dig) the ground stops at the underside of what is there. States: existing, dug (3->6), reinstated (6->)."""
    lv = vb.lv
    zones_survey = SPEC.get("site_zones") or lv.ground_zones
    if not zones_survey: return []
    pf = SPEC.get("site_zones_plain_front")
    zones_plain = zones_survey
    if pf:
        zones_plain, done = [], False
        for zn in zones_survey:
            if zn["name"] in pf["replace"]:
                if not done: zones_plain += pf["zones"]; done = True
                continue
            zones_plain.append(zn)
    mode = setting_mode(vb)
    gr = SPEC.get("setting", {}).get("ground_region")
    if gr and mode in ("always", "last"):
        # where the garden model brings its own ground, the house ground has no surface (a soil top well below it)
        x0_, y0_, x1_, y1_ = gr["rect"]
        zones_survey = [dict(name="under the garden model's ground (hidden)", mat="earth", z=gr.get("under_z", -0.45),
                             poly=[[x0_, y0_], [x1_, y0_], [x1_, y1_], [x0_, y1_]])] + list(zones_survey)
    zp_plain = zone_pieces(zones_plain)
    zp_survey = zone_pieces(zones_survey) if zones_plain is not zones_survey else zp_plain
    zp = zp_plain if mode != "always" else zp_survey
    out = []
    ret = _ground_states(vb, MAT, coll, zp, zp_survey, mode, lv)
    return ret


def setting_mode(vb):
    """'always' (as built now: today's garden), 'last' (a proposal: the garden appears at the finished stage), 'none'"""
    st = SPEC.get("setting", {}).get("stage", {})
    k = {"proposal": "proposal", "existing": "existing", "as_built": "as_built"}[vb.v["kind"]]
    v = st.get(k, 1 if k != "proposal" else "last")
    return "always" if v == 1 else v


def zone_pieces(zones):
    zp = []                     # (convex poly, z, mat)
    taken = []
    for zn in zones:
        pieces = G.convex_pieces(zn["poly"]) if len(zn["poly"]) > 2 else []
        for C in taken:
            hp = C[1]
            nxt = []
            for P in pieces:
                if not bbox_hit(P, C[2]): nxt.append(P); continue
                if G.clip_convex(P, hp): nxt.extend(G.convex_minus(P, hp))
                else: nxt.append(P)
            pieces = nxt
        for P in pieces:
            if abs(G.area(P)) < 1e-5: continue
            zp.append((P, zn["z"], zn.get("mat", "ground_lawn")))
        for P in G.convex_pieces(zn["poly"]):
            taken.append((P, G.poly_halfplanes(P), bbox(P)))
    return zp


def _ground_states(vb, MAT, coll, zp, zp_final, mode, lv):
    out = []
    def cutters_at(atoms, when, extra=(), base_rooms=()):
        cs = []
        for a in atoms:
            m = a["meta"]
            life = S.lifetime(m, vb.N)
            if not (life[0] <= when < life[1]): continue
            if a["kind"] == "wall":
                W = a["wall"]
                if W.storey != "ground" or W.z0 > 0.05: continue
                cs.append((G.ccw(W.footprint(full=True)), W.z0, None))
            elif a["kind"] in ("prism", "slab") and m["group"] in ("slab_layer", "foundation", "wall_cavity") and a["z0"] < 0.0:
                ztop = a.get("z1") if m["group"] == "foundation" else None
                for P in G.convex_pieces(a["poly"]): cs.append((P, a["z0"], ztop))
        for (poly, z0) in list(extra) + list(base_rooms):
            for P in G.convex_pieces(poly): cs.append((P, z0, None))
        return sorted(cs, key=lambda c: c[1])
    def solid(cuts, zp=zp):
        V, F, MI = [], [], []
        mats = ["earth"] + sorted(set(m for _, _, m in zp))
        hps = [(G.poly_halfplanes(c[0]), c[1], bbox(c[0])) for c in cuts]
        tops = [c[2] for c in cuts]
        def add_prism(P, top, mat, bot=-1.6):
            v, f = G.prism(P, bot, top)
            o = len(V); V.extend(v)
            for k, face in enumerate(f):
                F.append(tuple(i + o for i in face)); MI.append(mats.index(mat) if k == 1 else 0)
        for (P, zt, mat) in zp:
            pb = bbox(P)
            rest = [P]
            for (hp, z0, cb) in hps:
                if not overlap(pb, cb): continue
                nxt = []
                for Q in rest:
                    if G.clip_convex(Q, hp): nxt.extend(G.convex_minus(Q, hp))
                    else: nxt.append(Q)
                rest = nxt
            for Q in rest:
                if abs(G.area(Q)) > 1e-5: add_prism(Q, zt, mat)
            # under each cutter that overlaps this zone piece: ground up to the cutter's bottom (deepest first wins)
            for k, (hp, z0, cb) in enumerate(hps):
                if not overlap(pb, cb): continue
                reg = G.clip_convex(P, hp)
                if not reg: continue
                pieces = [reg]
                for (hp2, z2, cb2) in hps[:k]:
                    if not overlap(cb, cb2): continue
                    nxt = []
                    for Q in pieces:
                        if G.clip_convex(Q, hp2): nxt.extend(G.convex_minus(Q, hp2))
                        else: nxt.append(Q)
                    pieces = nxt
                top = min(z0, zt)
                for Q in pieces:
                    if abs(G.area(Q)) > 1e-5 and top > -1.59: add_prism(Q, top, "earth")
                # a buried foundation: the ground closes over it (back-filled) outside every other cutter
                ft = tops[k]
                if ft is not None and ft < zt - 0.01:
                    over = list(pieces)
                    for k2, (hp2, z2, cb2) in enumerate(hps):
                        if k2 == k or not overlap(cb, cb2): continue
                        nxt = []
                        for Q in over:
                            if G.clip_convex(Q, hp2): nxt.extend(G.convex_minus(Q, hp2))
                            else: nxt.append(Q)
                        over = nxt
                    for Q in over:
                        if abs(G.area(Q)) > 1e-5: add_prism(Q, zt, mat, bot=ft)
        return V, F, MI, mats
    rooms = [(r["poly"], lv.existing_floor_bottom) for r in vb.state["rooms"] if r["storey"] == "ground"]
    if vb.v["kind"] != "proposal":
        states = [("G-site", 1, None, cutters_at(vb.atoms, 1, base_rooms=rooms), "Existing ground: surveyed front garden (paths, beds, lawn, paving), assumed patio, drive, street and neighbours' gardens")]
    else:
        base_rooms = [(r["poly"], lv.existing_floor_bottom) for r in vb.base["rooms"] if r["storey"] == "ground"]
        dig = []
        for a in vb.atoms:
            if a["meta"].get("category") == "new" and a["meta"]["group"] == "foundation":
                dig.append((a["poly"], a["z0"]))
            if a["meta"].get("category") == "new" and a["meta"]["group"] == "slab_layer" and a["kind"] == "slab" and a["z0"] < -0.3:
                dig.append((a["poly"], min(a["z0"], -0.556)))
            if a.get("trench") and isinstance(a["trench"], list):          # drain trenches: 450 wide, 150 bed under the pipe
                for p0, p1 in zip(a["trench"], a["trench"][1:]):
                    d = G.unit((p1[0] - p0[0], p1[1] - p0[1])); n = (-d[1] * 0.225, d[0] * 0.225)
                    q = [(p0[0] - n[0], p0[1] - n[1]), (p1[0] - n[0], p1[1] - n[1]), (p1[0] + n[0], p1[1] + n[1]), (p0[0] + n[0], p0[1] + n[1])]
                    dig.append((G.ccw(q), min(p0[2], p1[2]) - 0.2))
        st = SPEC["staging"]["ground"]
        last = mode == "last" and zp_final is not zp
        states = [("G-site", 1, st["dig"], cutters_at(vb.atoms, 1, base_rooms=base_rooms), "Existing ground (plain site: levels as written on the drawings; front surfaces assumed)"),
                  ("G-dug", st["dig"], st["reinstate"], cutters_at(vb.atoms, st["dig"], extra=dig, base_rooms=base_rooms),
                   "Ground dug out: trenches 600/450 wide, min 1m deep, reduced dig for the slab (to suit ground conditions and the Building Inspector)"),
                  ("G-reinstated", st["reinstate"], vb.N if last else None, cutters_at(vb.atoms, vb.N, base_rooms=base_rooms),
                   "Ground backfilled against the new walls")]
        if last:
            states.append(("G-final", vb.N, None, cutters_at(vb.atoms, vb.N, base_rooms=base_rooms),
                           "Ground made good: the front garden as it is today (garden survey), patio and lawn at the back"))
    for (gid, si, so, cuts, label) in states:
        V, F, MI, mats = solid(cuts, zp_final if gid == "G-final" else zp)
        me = bpy.data.meshes.new(gid); me.from_pydata(V, [], F)
        for mn in mats: me.materials.append(MAT[mn])
        for poly, mi in zip(me.polygons, MI): poly.material_index = mi
        uv_layer(me, "world", "ground_lawn")
        # per-material UV scale: retile each face by its own material's tile
        uvl = me.uv_layers.active
        for poly in me.polygons:
            sx, sy = TILE.get(mats[poly.material_index], (1.0, 1.0)); bx, by = TILE.get("ground_lawn", (1.0, 1.0))
            for li in poly.loop_indices:
                u, v = uvl.data[li].uv
                uvl.data[li].uv = (u * bx / sx, v * by / sy)
        ob = bpy.data.objects.new(gid, me); coll.objects.link(ob)
        props = dict(element=gid, stage_in=si, seq=(0.1 if gid != "G-final" else 0.85) if si > 1 else 0.0, category="existing" if si == 1 else "new", group="ground", storey="site",
                     label=label, plain_label="The ground around the house", drawing="garden survey (plan_v3) / 4915.2B written levels / site plan 4915.SP",
                     conf="scaled", collide=True)
        if so: props.update(stage_out=so, seq_out=0.12 if gid != "G-reinstated" or so != vb.N else 0.85)
        for k, v in props.items(): ob[k] = v
        out.append((ob, dict(props=props, atom=dict(id=gid, kind="ground", meta=props))))
    return out


def bbox(P):
    xs = [p[0] for p in P]; ys = [p[1] for p in P]
    return (min(xs), min(ys), max(xs), max(ys))


def overlap(a, b):
    return a[0] < b[2] - 1e-9 and b[0] < a[2] - 1e-9 and a[1] < b[3] - 1e-9 and b[1] < a[3] - 1e-9


def bbox_hit(P, b):
    return overlap(bbox(P), b)


# ======================================================================================== JSON sidecars (viewer frame)
def vf(p):  # drawing/Blender (x, y, z) -> viewer (x, z, -y)
    return [round(p[0], 4), round(p[2], 4), round(-p[1], 4)]


def vplan(p): return [round(p[0], 4), round(-p[1], 4)]


def elements_json(vb, objs, bears):
    els = {}
    for ob, p in objs:
        a = p["atom"]
        eid = p["props"]["element"]
        if eid in els: continue
        m = dict(a["meta"]) if isinstance(a.get("meta"), dict) else {}
        meta = {k: m.get(k) for k in ("stage_in", "stage_out", "seq", "seq_out", "category", "group", "storey", "label", "plain_label",
                                      "drawing", "conf", "collide")}
        meta = {k: (v if v is not None or k in ("stage_out", "seq_out") else None) for k, v in meta.items()}
        e = dict(id=eid, type="mesh", params={}, meta=meta)
        if a["kind"] == "wall":
            e.update(wall_contract(a))
        elif a["kind"] == "member":
            A3, B3 = a["A"], a["B"]
            e["type"] = "beam" if a["meta"]["group"] in ("steel", "timber_beam") else "mesh"
            e["params"] = dict(start=vplan(A3), end=vplan(B3), top=round(max(A3[2], B3[2]), 4), section=a["meta"]["label"][:80])
        elif a["kind"] == "fixture":
            W, o = a["wall"], a["op"]
            hid = W.id
            e["type"] = "fixture"
            e["params"] = dict(catalogue={"bifold": "door.bifold.3", "window": "window.casement.2"}.get(o["kind"], "door.front.solid"),
                               opening=f"O-{slug(W.id)}-{slug(o['id'])}", lights=a.get("nlights"), plane=round(a["c_plane"], 4))
        if a.get("embedded_in"): e["embedded_in"] = a["embedded_in"]
        if a.get("no_regs"): e["regs"] = []; e["regs_exclude"] = True
        if a.get("loft"): e["loft"] = True
        e["provenance"] = a.get("provenance") or ("typical" if "TYPICAL" in str(m.get("label", "")).upper() or "typical" in str(m.get("label", "")) else
                                                   "drawn" if m.get("drawing") else "assumed")
        e["bears_on"] = sorted(bears.get(eid, []))
        if a.get("as_built"):
            e["layer"] = "as_built"; e["replaces"] = a["as_built"]["replaces"]
        if a.get("stair"):
            sp = dict(a["stair"])
            conv = lambda f: dict(f, start=vplan(f["start"]), direction=[f["direction"][0], -f["direction"][1]])
            if "start" in sp: sp.update(start=vplan(sp["start"]), direction=[sp["direction"][0], -sp["direction"][1]])
            if "flights" in sp: sp["flights"] = [conv(f) for f in sp["flights"]]
            if "half_landing" in sp: sp["half_landing"] = dict(sp["half_landing"], poly=[vplan(p) for p in sp["half_landing"]["poly"]])
            e["type"] = "stair"; e["params"] = sp
        els[eid] = e
        # openings as their own elements
        if a["kind"] == "wall":
            for o in e.get("_ops", []): els[o["id"]] = o
            e.pop("_ops", None)
    rooms = []
    for r in vb.state["rooms"]:
        rid = f"R-{r['storey'][0]}-{slug(r['name'])}"
        rooms.append(dict(id=rid, type="room", params=dict(name=r["name"], polygon=[vplan(p) for p in r["poly"]], floor=r["floor"], storey=r["storey"]),
                          meta=dict(category="existing", plain_label=room_text(vb, r), change=room_change(vb, r))))
    return list(els.values()) + rooms


def room_text(vb, r):
    t = SPEC.get("room_text", {}).get(vb.v["id"], {}).get(r["name"])
    return t or r["name"].capitalize()


def room_change(vb, r):
    if vb.v["kind"] != "proposal": return "unchanged"
    names = {x["name"]: x for x in vb.base["rooms"]}
    if r["name"] not in names: return "new"
    return "unchanged" if names[r["name"]]["poly"] == r["poly"] else "altered"


def wall_contract(a):
    W = a["wall"]
    L = W.layers()
    cs = [W.c_of(l["o0"]) for l in L] + [W.c_of(l["o1"]) for l in L]
    cmin, cmax = min(cs), max(cs)
    cc = (cmin + cmax) / 2
    flip = W.out < 0         # contract layer 0 is on the +n face; ours list outside->inside
    ua, ub = W.ua, W.ub
    s, e = W.point(ua, cc), W.point(ub, cc)
    layers = []
    for l in (L if not flip else L)[::(1 if W.out > 0 else -1)]:
        d = dict(group=l["group"], thickness=round(l["t"], 4), label=l["label"])
        if l.get("void"): d["void"] = True
        else: d["material"] = l["mat"]
        if l.get("plain"): d["plain_label"] = l["plain"]
        if l.get("finish") and a["meta"].get("category") == "new": d.update(stage_in=SPEC["staging"]["phases"]["lining"][0], seq=SPEC["staging"]["phases"]["lining"][1], category="finish")
        layers.append(d)
    ops, oids = [], []
    for o in W.openings:
        oid = f"O-{slug(W.id)}-{slug(o['id'])}"
        oids.append(oid)
        plain = {"window": "Window opening", "door": "Door opening", "bifold": "Opening for the folding glass doors", "opening": "Opening in the wall"}.get(o["kind"], "Opening")
        lab = o["id"] + (f" — {o['panes']}" if o.get("panes") else "") + f" (sill {o['z0']:.3f}, head {o['z1']:.3f} above FFL; BDS chains read from the dpc line)"
        ops.append(dict(id=oid, type="opening", params=dict(host=a["id"], offset=round(o["u0"] - ua, 4), width=round(o["u1"] - o["u0"], 4),
                                                            sill=round(o["z0"], 4), head=round(o["z1"], 4)),
                        meta=dict(a["meta"], group="window" if o["kind"] == "window" else "door", label=lab, plain_label=plain,
                                  conf=o.get("conf", a["meta"].get("conf")), collide=False)))
    params = dict(start=vplan(s), end=vplan(e), base=round(W.z0, 4), height=round(W.z1 - W.z0, 4), lifts=[round(z, 4) for z in W.lifts] + [round(W.z1, 4)],
                  layers=layers, construction=W.ckey)
    if W.profile: params["top_profile"] = [[round(u - ua, 4), round(z, 4)] for u, z in W.profile]
    if W.only_layers is not None: params["only_layers"] = W.only_layers
    joins = {k: v for k, v in W.ends.items() if v[0] is not None}
    if joins: params["joins_baked"] = {k: [round(v[0] - ua, 4), round(v[1], 4)] for k, v in joins.items()}
    return dict(type="wall", params=params, openings=oids, _ops=ops)


def stages_json(vb):
    vs = vb.v
    if vs.get("stages"):
        st = [dict(n=i + 1, name=s["name"], note=s["note"], customer_note=s["customer_note"],
                   **{k: s[k] for k in ("customer_title", "key_stage", "regs_stage") if k in s}) for i, s in enumerate(SPEC["stage_sets"][vs["stages"]])]
        over = SPEC.get("stage_overrides", {}).get(vs["id"], {})
        for s in st:
            if str(s["n"]) in over: s.update(over[str(s["n"])])
    else:
        st = [dict(n=1, name=vs["name"], note=vs.get("note", vs["description"]), customer_note=vs.get("customer_note", vs["description"]))]
    lv = vb.lv
    return dict(contract=1, version=vs["id"], label=vs["name"], units="m",
                frame="viewer (glTF): +Y up, metres; Blender (x, y, z) -> viewer (x, z, -y); y=0 is ground-floor FFL",
                stages=st,
                sections=[dict(name=s["name"], origin=vf(s["origin"]), normal=vf(s["normal"]), drawing=s["drawing"], note=s["note"])
                          for s in SPEC.get("sections", [])],
                spawns=[dict(name=s["name"], position=vf(s["position"]), yawDeg=s["yawDeg"]) for s in SPEC.get("spawns", [])
                        if vs["id"] not in s.get("not_in", [])],
                storeys=dict(site=SPEC["levels"].get("site_datum", -0.25), ground=lv.ffl, first=lv.ff, roof=lv.plate))


# ======================================================================================== main
def main():
    if SPEC_V1 and not args.no_items:
        from prepare_kit import prepare
        prepare(OUT,args.spec_v1)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    MAT = make_materials()
    global MAT_BASE, TILE_BASE
    MAT_BASE = dict(MAT); TILE_BASE = dict(TILE)
    want = [v for v in args.versions.split(",") if v]
    versions = [v for v in SPEC["versions"] if not want or v["id"] in want]
    manifest = dict(contract=1, name=SPEC["name"], as_built_now=SPEC["as_built_now"], default=SPEC["default"], versions=[])
    summary = {}
    for vs in SPEC["versions"]:
        mv = dict(id=vs["id"], name=vs["name"], description=vs["description"], kind=vs["kind"], base=vs.get("base"),
                  glb=f"{vs['id']}.glb", glb_quest=f"{vs['id']}_quest.glb", elements=f"{vs['id']}_elements.json", stages=f"{vs['id']}.json")
        if vs.get("customer_description"): mv["customer_description"] = vs["customer_description"]
        if vs.get("staging"): mv["stage_set"] = vs.get("stages")
        manifest["versions"].append(mv)
    SPEC["_staging_default"] = SPEC["staging"]
    HD.SPEC_REF["spec"] = SPEC
    for vs in versions:
        log("building", vs["id"])
        SPEC["staging"] = SPEC.get(vs.get("staging") or "_staging_default") or SPEC["_staging_default"]
        _vk = SPEC_V1_MAP.get(vs["id"])
        S.SPEC_DW = {d["id"]: d for d in SPEC_V1["versions"][_vk]["doors_windows"]} if _vk else {}
        vb = VersionBuild(vs, None)
        coll = bpy.data.collections.new(vs["id"]); bpy.context.scene.collection.children.link(coll)
        vkey = SPEC_V1_MAP.get(vs["id"]) if not args.no_items else None
        FIN = None
        if vkey:
            import hb_items as HI; HI.HF.OUT_DIR = OUT
            HI._MAT.clear(); HI._PH_CACHE.clear()          # the previous version's materials and meshes were freed
            FIN = HI.Finishes(SPEC_V1, args.spec_tex, log)
            for fid in sorted(SPEC_MATS):
                MAT[f"spec_{fid}"] = FIN.get(fid); TILE[f"spec_{fid}"] = FIN.tile[MAT[f"spec_{fid}"].name]
            # spec_v1: every wall and ceiling of the house today / after is painted (FIN-WALL warm white matt): the plaster and
            # plasterboard faces take the finish (row 177: no improvised colour)
            for k_ in ("plaster", "plasterboard"):
                MAT[k_] = FIN.get("FIN-WALL"); TILE[k_] = FIN.tile[MAT[k_].name]
            MAT["joinery"] = FIN.get("FIN-DOOR"); TILE["joinery"] = (1.0, 1.0)          # internal doors, frames, linings: white satin
            MAT["door_oak"] = FIN.get("WOOD-OAK-FURN"); TILE["door_oak"] = FIN.tile[MAT["door_oak"].name]   # Jack, 2 Nov 2026 (walk 2, F75): internal door LEAVES are oak; frames, linings and stops stay white satin
            MAT["trim"] = FIN.get("FIN-SKIRT"); MAT["wboard"] = FIN.get("FIN-WBOARD"); MAT["ironmongery"] = FIN.get("METAL-BLACK")   # spec: architraves FIN-SKIRT, boards FIN-WBOARD, black levers
        else:
            MAT.update(MAT_BASE); MAT["door_oak"] = MAT["joinery"]
            for k_ in ("plaster", "plasterboard"): TILE[k_] = TILE_BASE[k_]
        objs = build_blender(vb, MAT, coll)
        objs += ground_objects(vb, MAT, coll)
        objs += setting_objects(coll, vb)
        if SPEC_V1_MAP.get(vs["id"]): place_spec_garden_items(objs, SPEC_V1, SPEC_V1_MAP[vs["id"]])
        rooms_for_push[:] = [r for r in vb.state["rooms"]]
        moved = push_foliage_clear(objs)
        if vkey:
            HI.QUESTIONS.clear(); HI.NOTES.clear(); HI.HELD.clear()
            import hb_kit
            items = hb_kit.place_schedule(SPEC_V1, vkey, vb.N, coll, objs, OUT, args.spec_v1, log)
            for ob_, p_ in items: p_["spec"] = True
            objs += items
            ext, drop = HI.build_exterior(SPEC_V1, vkey, vb.N, coll, FIN, objs, log)
            keep = []
            for ob_, p_ in objs:
                if any(d_ in ob_.name and not ob_.name.startswith("XFD-") for d_ in drop): bpy.data.objects.remove(ob_)
                else: keep.append((ob_, p_))
            objs[:] = keep + ext
            log(vs["id"], f"spec exterior: {len(ext)} new items, old parts dropped: {drop}")
            vb.notes.extend(f"spec: {n}" for n in HI.NOTES)
            vb.questions.extend(dict(id="Q-spec-" + q["id"], text=q["what"], evidence=q.get("evidence", "")) for q in HI.QUESTIONS)
            vb.notes.append(f"spec items held to the furniture bar (row 183): {HI.HELD}")
            log(vs["id"], f"spec items: {len(items)} built, {len(HI.HELD)} held (row 183), {len(HI.QUESTIONS)} questions")
        if vkey:
            import hb_finish as HF
            HF.recolour_finished(objs, FIN, log)
            HF.scribe_architraves(objs, vb.N, log)
            HF.scribe_skirting(objs, vb.N, log)
            views_ = [("walk", pt[0:1] + [pt[1] + SPEC_V1["walkthrough"]["eye_height_m"]] + pt[2:3]) for nm_, pt in SPEC_V1["walkthrough"].get(vkey, [])]
            views_ += [("camera", c_["eye_m"]) for c_ in SPEC_V1["cameras"] if vkey in c_["versions"] and isinstance(c_["eye_m"], list)]
            objs += HF.apply(objs, SPEC_V1["versions"][vkey]["rooms"], FIN, vb.N, log, views=views_)
            import hb_services as HS
            objs += HS.services(objs, SPEC_V1["versions"][vkey]["rooms"], FIN, vb.N, log, spec_items=SPEC_V1["versions"][vkey]["items"])
        if moved: log(vs["id"], f"planting moved clear of solids (row 179): {len(moved)} plants, up to {max(m[1] for m in moved) * 1000:.0f} mm")
        vb.notes.extend(f"planting {n} moved {d * 1000:.0f} mm clear of {s_}" for n, d, s_ in moved)
        log(vs["id"], f"{len(objs)} parts")
        floating, clashes, opening_hits = ([], [], [])
        bearing = []
        door_swings = []
        bears = {}
        hw_tagged = tag_leaf_hardware([o for o in objs if not o[1].get("context") and not o[1].get("spec")])
        log(vs["id"], f"door hardware fixed to a leaf swings with it: {len(hw_tagged)} parts {hw_tagged[:6]}")
        if not args.no_check:
            # the garden model's ground carries what stands on it (meter box, downpipe) where it is shown; it is not itself checked
            floating, clashes = run_checks(vb, [o for o in objs if not o[1].get("spec") and (not o[1].get("context") or o[1]["props"].get("group") == "ground")])
            opening_hits = opening_checks(vb, [o for o in objs if not o[1].get("context") and not o[1].get("spec")])
            door_swings = leaf_swing_check(vb, [o for o in objs if not o[1].get("context") and not o[1].get("spec")])
            log(vs["id"], f"doors: {len(door_swings)} leaves, {len([d for d in door_swings if d['swing_deg'] != d['drawn'] * (1 if d['swing_deg'] > 0 else -1)])} swing less than 90")
            bearing = getattr(run_checks, "bearing", [])
            log(vs["id"], f"check: {len(floating)} floating, {len([c for c in clashes if not c['allowed']])} clashes ({len(clashes)} incl. allowed), "
                          f"{len([b for b in bearing if not b['allowed']])} cross-stage bearing faults")
        bears = bearing_map(vb, [o for o in objs if not o[1].get("context") and not o[1].get("spec")])
        # export
        for o in bpy.context.scene.objects: o.select_set(False)
        for ob, p in objs: ob.select_set(True)
        bpy.context.view_layer.objects.active = objs[0][0]
        sanitize_images(objs)
        path = os.path.join(OUT, f"{vs['id']}.glb")
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_extras=True, export_yup=True,
                                  export_apply=False, export_cameras=False, export_lights=False, export_materials="EXPORT",
                                  export_image_format="WEBP", export_image_quality=85)
        # the Quest variant: every texture at <= 512 px (decoded on the headset without a spike), then the 1k images back
        big = [im for im in bpy.data.images if (im.size[0] > 512 or im.size[1] > 512) and im.name not in SETTING_IMAGES]
        for im in big:
            w, h = im.size; s_ = 512 / max(w, h); im.scale(max(1, int(w * s_)), max(1, int(h * s_)))
        bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, f"{vs['id']}_quest.glb"), export_format="GLB", use_selection=True, export_extras=True,
                                  export_yup=True, export_apply=False, export_cameras=False, export_lights=False, export_materials="EXPORT",
                                  export_image_format="WEBP", export_image_quality=80)
        for p_ in (path, os.path.join(OUT, f"{vs['id']}_quest.glb")): glb_texture_guard(p_)
        for im in big:
            if im.packed_file or not im.filepath: continue        # the setting's own (imported per version, freed with it)
            try: im.reload()
            except Exception as ex: log("reload failed", im.name, ex)
        els = elements_json(vb, objs, bears)
        json.dump(dict(contract=1, version=vs["id"], frame="viewer", elements=els), open(os.path.join(OUT, f"{vs['id']}_elements.json"), "w"), indent=1)
        json.dump(stages_json(vb), open(os.path.join(OUT, f"{vs['id']}.json"), "w"), indent=1)
        tris = sum(sum(len(pp.vertices) - 2 for pp in ob.data.polygons) for ob, p in objs if ob.type == "MESH")
        pairs = sorted({(p["props"].get("group"), ob.active_material.name if ob.active_material else "") for ob, p in objs})
        counts = {}
        for ob, p in objs:
            pr = p["props"]
            k = (pr["group"], pr["stage_in"], pr["category"])
            counts[k] = counts.get(k, 0) + 1
        check = dict(version=vs["id"], parts=len(objs), elements=len(els), tris_approx=tris, material_group_pairs=len(pairs),
                     floating=floating, clashes=clashes, opening_clashes=opening_hits, bearing=bearing, door_swings=door_swings, questions=vb.questions, joins=[list(j) for j in vb.join_log], notes=vb.notes,
                     counts=[dict(group=k[0], stage_in=k[1], category=k[2], n=n) for k, n in sorted(counts.items(), key=lambda x: (x[0][1], x[0][0]))])
        json.dump(check, open(os.path.join(OUT, f"{vs['id']}_check.json"), "w"), indent=1)
        FAULTS.extend(f"{vs['id']}: {b['part']} (stage {b['stage']}/{b['seq']}) before its carrier {b['carrier']} (stage {b['carrier_stage']}/{b['carrier_seq']})"
                      for b in bearing if not b["allowed"])
        summary[vs["id"]] = dict(parts=len(objs), elements=len(els), tris=tris, pairs=len(pairs), floating=len(floating),
                                 bearing_faults=len([b for b in bearing if not b["allowed"]]),
                                 clashes=len([c for c in clashes if not c["allowed"]]), mb=round(os.path.getsize(path) / 1e6, 2),
                                 quest_mb=round(os.path.getsize(os.path.join(OUT, f"{vs['id']}_quest.glb")) / 1e6, 2))
        log(vs["id"], summary[vs["id"]])
        if args.blend: bpy.ops.wm.save_as_mainfile(filepath=args.blend.replace(".blend", f"_{vs['id']}.blend"))
        # free this version
        for ob, p in objs: bpy.data.objects.remove(ob)
        bpy.data.collections.remove(coll)
        for me in list(bpy.data.meshes):
            if me.users == 0: bpy.data.meshes.remove(me)
        keep_m = {m.name for m in MAT.values()} if isinstance(MAT, dict) else set()
        for mt in list(bpy.data.materials):
            if mt.users == 0 and mt.name not in keep_m and mt.name not in MATS: bpy.data.materials.remove(mt)
        for im in list(bpy.data.images):
            if im.users == 0: bpy.data.images.remove(im)
    if not want:
        json.dump(manifest, open(os.path.join(OUT, "versions.json"), "w"), indent=1)
    else:
        mp = os.path.join(OUT, "versions.json")
        json.dump(manifest, open(mp, "w"), indent=1)
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    # for the viewer: real tile sizes per material (UVs are metres / tile; walls: v = (y_viewer + 0.032) / tile_v + v_joint)
    mats = {}
    for name in MATS:
        tm = TMETA.get(TEXSET.get(ALIAS.get(name, name), ""), {})
        mats[name] = dict(tile=list(TILE.get(name, (1.0, 1.0))), v_joint=tm.get("v_joint", 0.0), texture_set=TEXSET.get(ALIAS.get(name, name)), glb_material=ALIAS.get(name, name),
                          source=tm.get("source", "procedural (tools/house/make_textures.py)" if tm else "flat colour"))
    json.dump(dict(contract=1, uv="metres / tile; wall faces: u along the face, v = (height + 0.032) / tile_v + v_joint (a bed joint on the dpc)",
                   materials=mats), open(os.path.join(OUT, "materials.json"), "w"), indent=1)
    log("done", summary)
    if FAULTS:
        log(f"BUILD FAILED: {len(FAULTS)} cross-stage bearing faults (something appears before what carries it):")
        for f in FAULTS[:60]: log("  ", f)
        sys.exit(2)


def sanitize_images(objs):
    """row 190: an image node whose image has no pixels (a library file that failed to load, a 1-channel mask WebP cannot
    hold) makes the glTF exporter write a texture with no image source, which crashes three's GLTFLoader. Remove such
    nodes before export (the material keeps its constant inputs) and say which."""
    seen, removed = set(), []
    for ob, p in objs:
        if ob.type != "MESH": continue
        for m in ob.data.materials:
            if not m or m.name in seen or not m.use_nodes: continue
            seen.add(m.name)
            for n in [n for n in m.node_tree.nodes if n.type == "TEX_IMAGE"]:
                im = n.image; ok = im is not None
                if ok:
                    try:
                        if im.size[0] == 0 and not im.packed_file and im.filepath: im.reload()
                        ok = im.size[0] > 0 and im.size[1] > 0 and im.channels >= 3
                    except Exception: ok = False
                if not ok:
                    removed.append(f"{m.name}:{im.name if im else 'None'}"); m.node_tree.nodes.remove(n)
    if removed: log(f"export guard: {len(removed)} image nodes without usable pixels removed (row 190): {removed[:8]}")
    return removed


def glb_texture_guard(path):
    """after export: every texture must have an image source; if any does not, strip it (tools/house/fix_glb_textures.py)
    and say so loudly: the export guard above should have prevented it"""
    import struct, subprocess
    b = open(path, "rb").read(); j = json.loads(b[20:20 + struct.unpack("<I", b[12:16])[0]])
    def src(t): return t.get("source", next((e.get("source") for e in t.get("extensions", {}).values() if isinstance(e, dict) and "source" in e), None))
    changed=False
    uses={}
    for mesh in j.get('meshes',[]):
        for primitive in mesh['primitives']:
            if 'material' in primitive:uses.setdefault(primitive['material'],[]).append(primitive)
    def validate_uv(value,primitives):
        if isinstance(value,dict):
            if 'index' in value and value.get('texCoord',0)<0:
                if not all('TEXCOORD_0' in pr['attributes'] for pr in primitives):raise ValueError('Missing metric UV0 in '+path)
                del value['texCoord']
                return True
            return any([validate_uv(v,primitives) for v in value.values()])
        return False
    for idx,mat in enumerate(j.get('materials',[])):
        changed=validate_uv(mat,uses.get(idx,[])) or changed
        tint=mat.get('extras',{}).get('studio_tint');pbr=mat.get('pbrMetallicRoughness',{})
        if tint and 'baseColorTexture' in pbr:
            pbr['baseColorFactor']=[*tint,1.];changed=True
    if changed:
        old_len=struct.unpack('<I',b[12:16])[0];data=json.dumps(j,separators=(',',':')).encode()
        data+=b' '*((-len(data))%4);rest=b[20+old_len:]
        blob=b[:8]+struct.pack('<II',20+len(data)+len(rest),len(data))+b'JSON'+data+rest
        with open(path,'wb') as file:file.write(blob)
    bad = [i for i, t in enumerate(j.get("textures", [])) if src(t) is None]
    if bad:
        log(f"EXPORT GUARD: {os.path.basename(path)} had {len(bad)} textures without an image source: stripped (row 190)")
        subprocess.run([sys.executable if not sys.executable.endswith("Blender") else "python3", os.path.join(HERE, "fix_glb_textures.py"), path], check=False)


FAULTS = []
SPEC_V1 = json.load(open(args.spec_v1)) if os.path.exists(args.spec_v1) else None
SPEC_V1_MAP = {"as_built_now": "before", SPEC.get("default", "approved_2b"): "after"} if SPEC_V1 else {}
SPEC_MATS = set()
SKIRT_LINING_T = 0.010       # measured on the built GLB (party wall, living rear wall): skirting back 10 mm inside the lining face
SKIRTING_HELD = False    # Jack 1 Nov: skirting, architraves, window boards to the joinery bar: moulded profiles (hb_joinery), proved on the joinery test sheet
NOTES_MANIFOLD = []      # wall parts whose cells could not weld into one shell (kept as separate closed cells)
SETTING_IMAGES = set()        # the garden's own textures: kept at the garden test's size in the Quest GLB too (log 162)


def place_spec_garden_items(objs, spec, vkey):
    """a spec exterior item that IS a garden-model object ("garden model <name>" in its evidence) stands where the signed spec
    puts it: its plan box centre moved to the spec box centre (errata 3: X-CONIFER-1 30 mm clear of X-WASTE)"""
    for it in spec["exterior"]["items"]:
        if vkey not in it.get("versions", []): continue
        m = re.search(r"garden model (\S+)", it.get("evidence", ""))
        if not m: continue
        name = m.group(1).rstrip(";,")
        for ob, p in objs:
            if ob.type != "MESH" or not ob.name.startswith(name): continue
            bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            cx = (min(v.x for v in bb) + max(v.x for v in bb)) / 2; cz = -(min(v.y for v in bb) + max(v.y for v in bb)) / 2
            tx = (it["box_min"][0] + it["box_max"][0]) / 2; tz = (it["box_min"][2] + it["box_max"][2]) / 2
            if math.hypot(tx - cx, tz - cz) > 0.01:
                ob.matrix_world = Matrix.Translation(Vector((tx - cx, -(tz - cz), 0))) @ ob.matrix_world
                log(f"spec exterior: {ob.name} moved {math.hypot(tx - cx, tz - cz) * 1000:.0f} mm to {it['id']}'s spec box")


def set_after(a, z, stage, seq):
    """courses of wall a from height z up go in at (stage, seq) or later (a member set into it later carries them)"""
    cur = a.get("lift_stage_after")
    if cur is None or z < cur[0] - 1e-4 or (abs(z - cur[0]) < 1e-4 and (stage, seq) > (cur[1], cur[2])):
        a["lift_stage_after"] = (z, stage, min(0.99, seq))


def setting_objects(coll, vb):
    """the surveyed front garden (tools/house/make_setting.py), embedded so the viewer shows it natively. A proposal
    shows it at its finished stage only (before and during the works the front is a plain site); the 2022 house has
    none (the garden was made later); the houses opposite stand at every stage (spec setting.always_prefixes)."""
    sp = SPEC.get("setting", {}).get("glb")
    if not sp: return []
    mode = setting_mode(vb)
    always = tuple(SPEC.get("setting", {}).get("always_prefixes", []))
    path = os.path.join(OUT, sp)
    if not os.path.exists(path): log("setting missing:", path); return []
    before = set(bpy.data.objects); imgs_before = set(bpy.data.images)
    bpy.ops.import_scene.gltf(filepath=path)
    SETTING_IMAGES.update(im.name for im in bpy.data.images if im not in imgs_before)
    new = [o for o in bpy.data.objects if o not in before]
    out = []
    for o in new:
        for c in list(o.users_collection): c.objects.unlink(o)
        coll.objects.link(o)
        if o.type != "MESH": continue
        src = o if "stage_in" in o.keys() else (o.parent if o.parent and "stage_in" in o.parent.keys() else None)
        if src is None: continue
        props = {k: src[k] for k in src.keys() if k in ("element", "stage_in", "seq", "category", "group", "storey", "label", "plain_label", "drawing", "conf", "collide")}
        props["context"] = True
        keep_all = always and str(props.get("element", "")).replace("SET-", "").startswith(always)
        if mode == "none" and not keep_all:
            bpy.data.objects.remove(o); continue
        if mode == "last" and not keep_all:
            props.update(stage_in=vb.N, seq=0.9, category="new")
            props["label"] = props.get("label", "") + " — laid out at the end of the works (external works)"
        for k_, v_ in props.items(): o[k_] = v_
        out.append((o, dict(props=props, atom=dict(id=props["element"], kind="setting", meta=props), context=True)))
    return out


FOLIAGE_RE = re.compile(r"leaves|leaf|vertexplant|branches|hedge|plant|foliage", re.I)


rooms_for_push = []


def push_foliage_clear(objs, clear=0.02, rounds=6):
    """row 179 (Jack: 'leaves on show'): bed plants from the garden model poked through the house's walls, DPC and floors
    (the beds run up to the wall; the scanned plants are wider than the bed edge). Each plant that intersects a solid is moved
    horizontally away from it, by its deepest vertex behind the solid's face plus 20 mm, until it is clear. Only whole
    plants are moved (never cut or scaled), and every move is logged in the check json notes."""
    from mathutils.bvhtree import BVHTree as _B
    def world(ob):
        M = ob.matrix_world; me = ob.data
        return [M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]
    def bb(V): return (Vector((min(v.x for v in V), min(v.y for v in V), min(v.z for v in V))), Vector((max(v.x for v in V), max(v.y for v in V), max(v.z for v in V))))
    def is_fol(ob, p): return ob.type == "MESH" and ob.name.startswith("Plant2_")         # the garden's bed plants (whole plants)
    N = max(int(p["props"].get("stage_in", 1)) for ob, p in objs)
    solids = []
    for ob, p in objs:
        if ob.type != "MESH" or is_fol(ob, p): continue
        pr = p["props"]
        if (pr.get("stage_out") or 99) <= N: continue                                         # gone by the finished stage
        if pr.get("group") == "ground" or re.search(r"Pot_|soil|bed_|mulch|edging|kerb", ob.name): continue
        if pr.get("context"): continue          # the house's solids only: the garden's own posts stand among its plants as surveyed
        if any(FOLIAGE_RE.search(m.name) for m in ob.data.materials if m): continue
        V, T = world(ob)
        if not T: continue
        solids.append((ob, V, T, bb(V)))
    rooms = [r["poly"] for r in rooms_for_push]
    def inside_house(pt): return any(G.point_in_poly((pt.x, pt.y), P) for P in rooms)
    trees = {}
    def tree(i):
        if i not in trees: trees[i] = _B.FromPolygons(solids[i][1], solids[i][2])
        return trees[i]
    def depth_along(V, d):
        """how far the plant must move along d so that none of its vertices is inside a solid (ray from each vertex along d
        meets an exit face first = the vertex is inside); returns (depth, solid name) or (0, None)"""
        lo, hi = bb(V); worst, who = 0.0, None
        for i, (so, SV, ST, (slo, shi)) in enumerate(solids):
            if slo.x > hi.x or shi.x < lo.x or slo.y > hi.y or shi.y < lo.y or slo.z > hi.z or shi.z < lo.z: continue
            t = tree(i)
            for v in V:
                if not (slo.x - 1e-3 <= v.x <= shi.x + 1e-3 and slo.y - 1e-3 <= v.y <= shi.y + 1e-3 and slo.z - 1e-3 <= v.z <= shi.z + 1e-3): continue
                h = t.ray_cast(v, d, 3.0)
                if h[0] is not None and h[1].dot(d) > 0 and h[3] > worst: worst, who = h[3], so.name
        return worst, who
    moved = []
    for ob, p in objs:
        if not is_fol(ob, p): continue
        V0, T0 = world(ob)
        ft = _B.FromPolygons(V0, T0); lo, hi = bb(V0)
        if not any(ft.overlap(tree(i)) for i, (so, SV, ST, (slo, shi)) in enumerate(solids)
                   if not (slo.x > hi.x or shi.x < lo.x or slo.y > hi.y or shi.y < lo.y or slo.z > hi.z or shi.z < lo.z)): continue
        best = None
        for d in [Vector((math.cos(k * math.pi / 4), math.sin(k * math.pi / 4), 0)) for k in range(8)]:
            off = Vector((0, 0, 0)); who = None
            for _ in range(rounds):
                V = [v + off for v in V0]
                dep, w = depth_along(V, d)
                if dep <= 0: break
                off = off + d * (dep + clear); who = w
            V = [v + off for v in V0]
            if depth_along(V, d)[0] > 0: continue
            c = sum(V, Vector()) / len(V)
            if inside_house(c): continue
            if best is None or off.length < best[0].length: best = (off, who, d)
        if best is None: moved.append((ob.name, 0.0, "NOT CLEARED")); continue
        ob.matrix_world = Matrix.Translation(best[0]) @ ob.matrix_world
        moved.append((ob.name, best[0].length, f"{best[1]} (along {best[2].x:+.2f},{best[2].y:+.2f})"))
    return moved


def bearing_map(vb, objs):
    """element -> elements it sits on (bottom vertices within 6 mm of the other's surface, present at its stage)"""
    N = vb.N
    info = []
    for ob, p in objs:
        V, T = mesh_world(ob)
        P = np.array([tuple(v) for v in V])
        pr = p["props"]
        info.append((ob, pr, V, T, P.min(0), P.max(0)))
    lo = np.array([x[4] for x in info]); hi = np.array([x[5] for x in info])
    trees = {}
    bears = {}
    for i, (ob, pr, V, T, l, h) in enumerate(info):
        if pr["group"] in ("ground",) or pr["category"] in ("temporary",): continue
        zmin = l[2]
        bottom = [v for v in V if v.z < zmin + 0.004][:12]
        ov = np.all((np.minimum(h, hi) - np.maximum(l, lo)) > -0.006, axis=1)
        for j in np.nonzero(ov)[0]:
            if j == i: continue
            prj = info[j][1]
            if prj["element"] == pr["element"]: continue
            if prj["stage_in"] > pr["stage_in"]: continue
            if prj.get("stage_out") and prj["stage_out"] <= pr["stage_in"]: continue
            if j not in trees: trees[j] = BVHTree.FromPolygons(info[j][2], info[j][3])
            if any(trees[j].find_nearest(v, 0.006)[0] is not None for v in bottom):
                bears.setdefault(pr["element"], set()).add(prj["element"])
    return bears


main()
