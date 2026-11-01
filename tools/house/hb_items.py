"""The signed design specification (spec_v1.json, WORKFLOW G2b) built into a house version: every item (furniture, fixtures,
fittings, lights, soft furnishings, decor, plants) at its spec position, yaw and size, from its spec asset (Poly Haven model
fitted uniformly to the size box) or its parametric definition; every room's finishes (floor, walls incl. tile zones and
accents, ceiling, skirting); door and window finishes; the spec's exterior items. Nothing is improvised: where the spec does
not say, the item or part is left out and written to QUESTIONS (and the report).

Called by generate_house.py per version (as_built_now -> spec "before", the proposal -> spec "after"), Blender side.
Frames: spec / viewer (x, y up, z) -> Blender drawing frame (x, -z, y). yaw: the item's FRONT faces 0 -> -z(viewer) = +y(Blender),
90 -> -x; the item is built in a local frame X = width, +Y = front, Z up, origin at the footprint centre of its base, then
rotated by yaw about Z and moved to the spec position. Every node carries spec_id, spec_kind and the contract's extras."""
import os, re, json, math
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

QUESTIONS = []          # spec gaps found while building (id, what, evidence)
NOTES = []              # interpretations made from the spec's own words (for the report)
_MAT = {}
_PH_CACHE = {}


def b3(p): return Vector((p[0], -p[2], p[1]))                     # viewer (x, y, z) -> Blender
def hexlin(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# ------------------------------------------------------------------------------------------------ materials (one per finish)
class Finishes:
    def __init__(self, spec, texdir, log):
        self.spec, self.texdir, self.log = spec, texdir, log
        self.F = {f["id"]: f for f in spec["finishes"]}
        mp = os.path.join(texdir, "spec_tex_meta.json")
        self.meta = json.load(open(mp))["finishes"] if os.path.exists(mp) else {}
        self.tile = {}

    def get(self, key):
        """a finish id, or an explicit colour 'c:#RRGGBB:rough:metal' (the spec's explicit colours, e.g. black #1A1A1A)"""
        if key in _MAT: return _MAT[key]
        if key.startswith("c:"):
            _, hx, r, mt = key.split(":")
            m = self._flat(f"spec_{hx.lstrip('#')}", hx, float(r), float(mt)); _MAT[key] = m; self.tile[m.name] = (1, 1); return m
        if key == "MIRROR":
            m = self._flat("spec_MIRROR", "#E6E8EA", 0.03, 1.0); _MAT[key] = m; self.tile[m.name] = (1, 1); return m
        f = self.F.get(key)
        if f is None: raise KeyError(f"finish {key} not in the spec")
        md = self.meta.get(key, {})
        rough, metal = md.get("rough", 0.6), md.get("metal", 0.0)
        files = md.get("files") or {}
        if key == "GLASS-CLEAR":
            m = self._flat(f"spec_{key}", f["colour_srgb"], 0.02, 0.0, alpha=0.18)
        elif files.get("col"):
            m = bpy.data.materials.new(f"spec_{key}"); m.use_nodes = True; nt = m.node_tree
            bs = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
            tc = nt.nodes.new("ShaderNodeTexImage"); tc.image = bpy.data.images.load(os.path.join(self.texdir, files["col"]), check_existing=True)
            nt.links.new(tc.outputs["Color"], bs.inputs["Base Color"])
            if files.get("nrm"):
                tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = bpy.data.images.load(os.path.join(self.texdir, files["nrm"]), check_existing=True)
                tn.image.colorspace_settings.name = "Non-Color"
                nm = nt.nodes.new("ShaderNodeNormalMap"); nt.links.new(tn.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
            bs.inputs["Roughness"].default_value = rough        # constant (a roughness map makes a 1-channel image WebP cannot hold)
            if md.get("rough_map") and files.get("rough"):      # paint: the subtle roughness drift, read from the G channel (3-channel ORM in glTF)
                tr = nt.nodes.new("ShaderNodeTexImage"); tr.image = bpy.data.images.load(os.path.join(self.texdir, files["rough"]), check_existing=True)
                tr.image.colorspace_settings.name = "Non-Color"
                sp = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(tr.outputs["Color"], sp.inputs["Color"])
                nt.links.new(sp.outputs["Green"], bs.inputs["Roughness"])
            bs.inputs["Metallic"].default_value = metal
            m.diffuse_color = (*hexlin(f["colour_srgb"]), 1)
            m.use_backface_culling = True
        else:
            m = self._flat(f"spec_{key}", f["colour_srgb"], rough, metal)
        m["spec_finish"] = key
        self.tile[m.name] = tuple(md.get("tile_m") or (1.0, 1.0))
        _MAT[key] = m
        return m

    def _flat(self, name, hx, rough, metal, alpha=1.0):
        m = bpy.data.materials.new(name); m.use_nodes = True
        bs = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bs.inputs["Base Color"].default_value = (*hexlin(hx), 1); bs.inputs["Roughness"].default_value = rough
        bs.inputs["Metallic"].default_value = metal
        if alpha < 1:
            bs.inputs["Alpha"].default_value = alpha
            try: m.surface_render_method = "BLENDED"
            except Exception: m.blend_method = "BLEND"
        m.diffuse_color = (*hexlin(hx), alpha)
        m.use_backface_culling = alpha >= 1
        return m


# ------------------------------------------------------------------------------------------------ a small mesh builder
class MB:
    """closed pieces in a local frame, each with a material key; -> one mesh with material slots and box UVs (m / tile)"""
    def __init__(self): self.pieces = []           # (verts, faces, key)

    def box(self, x0, x1, y0, y1, z0, z1, key, bevel=0.0):
        if x1 - x0 < 1e-5 or y1 - y0 < 1e-5 or z1 - z0 < 1e-5: return
        V = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        self.pieces.append((V, F, key, min(bevel, (x1 - x0) / 2.2, (y1 - y0) / 2.2, (z1 - z0) / 2.2)))

    def cbox(self, cx, cy, z0, w, d, h, key, bevel=0.0): self.box(cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2, z0, z0 + h, key, bevel)

    def cyl(self, cx, cy, z0, z1, r, key, seg=16, r1=None, axis="z"):
        r1 = r if r1 is None else r1
        V = []
        for k, (z, rr) in enumerate(((z0, r), (z1, r1))):
            for i in range(seg):
                a = 2 * math.pi * i / seg; V.append((cx + rr * math.cos(a), cy + rr * math.sin(a), z))
        F = [tuple(reversed(range(seg))), tuple(range(seg, 2 * seg))] + [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)]
        if axis != "z":
            def rot(v):
                x, y, z = v[0] - cx, v[1] - cy, v[2] - z0
                return (cx + z, cy + y, z0 + x) if axis == "x" else (cx + x, cy + z, z0 + y)
            V = [rot(v) for v in V]
            if axis == "y": F = [tuple(reversed(f)) for f in F]
        self.pieces.append((V, F, key, 0.0))

    def tube(self, cx, cy, z0, z1, r_out, r_in, key, seg=24):
        """an open-ended drum (lamp shade) as a closed ring solid"""
        V = []
        for z in (z0, z1):
            for rr in (r_out, r_in):
                for i in range(seg):
                    a = 2 * math.pi * i / seg; V.append((cx + rr * math.cos(a), cy + rr * math.sin(a), z))
        def idx(zl, ring, i): return zl * 2 * seg + ring * seg + (i % seg)
        F = []
        for i in range(seg):
            F.append((idx(0, 0, i), idx(0, 0, i + 1), idx(1, 0, i + 1), idx(1, 0, i)))           # outside
            F.append((idx(0, 1, i + 1), idx(0, 1, i), idx(1, 1, i), idx(1, 1, i + 1)))           # inside
            F.append((idx(0, 1, i), idx(0, 1, i + 1), idx(0, 0, i + 1), idx(0, 0, i)))           # bottom ring
            F.append((idx(1, 0, i), idx(1, 0, i + 1), idx(1, 1, i + 1), idx(1, 1, i)))           # top ring
        self.pieces.append((V, F, key, 0.0))

    def poly_prism(self, pts, z0, z1, key):
        n = len(pts)
        V = [(p[0], p[1], z0) for p in pts] + [(p[0], p[1], z1) for p in pts]
        s = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
        bot, top = list(range(n)), list(range(n, 2 * n))
        if s > 0: bot = bot[::-1]
        else: top = top[::-1]
        F = [tuple(bot), tuple(top)]
        for i in range(n):
            j = (i + 1) % n
            F.append((i, j, n + j, n + i) if s > 0 else (j, i, n + i, n + j))
        self.pieces.append((V, F, key, 0.0))

    def build(self, name, fin, ob=None):
        keys = []
        bm = bmesh.new()
        uv = bm.loops.layers.uv.new("UVMap")
        for V, F, key, bev in self.pieces:
            if key not in keys: keys.append(key)
            mi = keys.index(key)
            sub = bmesh.new()
            vs = [sub.verts.new(v) for v in V]
            for f in F:
                try: sub.faces.new([vs[i] for i in f])
                except ValueError: pass
            bmesh.ops.recalc_face_normals(sub, faces=sub.faces)
            if bev > 1e-4:
                bmesh.ops.bevel(sub, geom=sub.edges[:], offset=bev, segments=2, affect="EDGES", profile=0.5, clamp_overlap=True)
            tw, th = fin.tile.get(fin.get(key).name, (1.0, 1.0))
            me = bpy.data.meshes.new("_t"); sub.to_mesh(me); sub.free()
            off = len(bm.verts)
            nv = [bm.verts.new(v.co) for v in me.vertices]
            for p in me.polygons:
                try: f = bm.faces.new([nv[i] for i in p.vertices])
                except ValueError: continue
                f.material_index = mi
                n = p.normal
                for l in f.loops:
                    c = l.vert.co
                    if abs(n.z) > 0.7: l[uv].uv = (c.x / tw, c.y / th)
                    elif abs(n.x) > abs(n.y): l[uv].uv = (c.y / tw, c.z / th)
                    else: l[uv].uv = (c.x / tw, c.z / th)
            bpy.data.meshes.remove(me)
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        for k in keys: me.materials.append(fin.get(k))
        if ob is None: ob = bpy.data.objects.new(name, me)
        return ob


def place(ob, pos, yaw):
    ob.matrix_world = Matrix.Translation(b3(pos)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")


# ------------------------------------------------------------------------------------------------ parametric kinds (local frame)
def first_fin(text, default=None):
    m = re.search(r"\b(FIN-[A-Z-]+|FAB-[A-Z-]+|RUG-[A-Z]+|BED-LINEN|THROW-BED|WOOD-OAK-FURN|METAL-BLACK|BRASS|CER-CREAM|STONE-SLATE|SAN-WHITE|"
                  r"RATTAN|TV-BLACK|RAL9016|GLASS-CLEAR|STEEL-BRUSHED|KIT-[A-Z]+|KITB-[A-Z]+|TILE-METRO-WHITE)\b", str(text or ""))
    return m.group(1) if m else default


def mats_for(it, part, *fallbacks):
    """the finish for a part: the item's materials map (part, else 'all'), else the asset's own words naming a finish, else None"""
    M = it.get("materials") or {}
    v = M.get(part) or M.get("all")
    if v and v != "as asset": return first_fin(v, v if v.startswith("FIN") else None) or v
    a = it["asset"]
    for fb in (part,) + fallbacks:
        f = first_fin(a.get(fb, ""))
        if f: return f
    return None


WHITE = "RAL9016"         # the spec's own white for appliances, mounts, trims (meter box, radiators: 'white uPVC' = RAL 9016)
LINEN = "FAB-CURTAIN"     # 'linen' shades: the finish "Curtains, blinds, lamp shades: natural linen"


def k_bench_box(mb, W, D, H, it):
    m = mats_for(it, "all") or "WOOD-OAK-FURN"
    mb.box(-W / 2, W / 2, -D / 2, D / 2, H - 0.03, H, m, 0.003)
    for sx in (-1, 1): mb.box(sx * W / 2 - (0.02 if sx > 0 else 0) + (0 if sx > 0 else 0), sx * W / 2 + (0.02 if sx < 0 else 0), -D / 2, D / 2, 0, H - 0.03, m) if False else None
    mb.box(-W / 2, -W / 2 + 0.02, -D / 2, D / 2, 0, H - 0.03, m); mb.box(W / 2 - 0.02, W / 2, -D / 2, D / 2, 0, H - 0.03, m)
    n = 5; sw = (D - 0.02) / n
    for i in range(n): mb.box(-W / 2 + 0.02, W / 2 - 0.02, -D / 2 + 0.01 + i * sw + 0.004, -D / 2 + 0.01 + (i + 1) * sw - 0.004, 0.15, 0.17, m)


def k_hook_rail(mb, W, D, H, it):
    mb.box(-W / 2, W / 2, -D / 2, -D / 2 + 0.02, 0, H, mats_for(it, "rail") or "WOOD-OAK-FURN", 0.002)
    for i in range(4):
        x = -W / 2 + W * (i + 0.5) / 4
        mb.cyl(x, -D / 2 + 0.02, H / 2, H / 2 + 0.008, 0.006, mats_for(it, "hooks") or "METAL-BLACK", 8)
        mb.box(x - 0.006, x + 0.006, -D / 2 + 0.02, D / 2, H / 2 - 0.006, H / 2 + 0.006, mats_for(it, "hooks") or "METAL-BLACK")
    if it["asset"].get("coats"):
        QUESTIONS.append(dict(id=it["id"], what="the 2 coats on the hook rail have no colour or fabric in the spec: rail and hooks built, coats left out",
                              evidence=it["type"]))


def k_rug(mb, W, D, H, it):
    m = mats_for(it, "all")
    if m is None:
        pile = it["asset"].get("pile", "")
        if "waffle" in pile and "cotton" in pile: m = "BED-LINEN"; NOTES.append(f"{it['id']}: 'cotton waffle' built in BED-LINEN (the spec's white cotton waffle)")
        else:
            QUESTIONS.append(dict(id=it["id"], what="rug with no finish or colour", evidence=pile)); return False
    mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, H, m, min(0.004, H / 3))


def k_flush_disc(mb, W, D, H, it):
    r = it["asset"].get("dia_mm", W * 1000) / 2000
    body = mats_for(it, "all") or "METAL-BLACK"
    if not (it.get("materials") or {}).get("all"): NOTES.append(f"{it['id']}: flush light body matt black (METAL-BLACK) as the porch light; opal diffuser white (RAL9016)")
    mb.cyl(0, 0, -H * 0.4, 0, r, body, 32)                    # built downward from the ceiling anchor
    mb.cyl(0, 0, -H, -H * 0.4, r * 0.92, WHITE, 32)


def k_pendant_drum(mb, W, D, H, it):
    a = it["asset"]; drop = a.get("drop_mm", 600) / 1000; r = W / 2
    mb.cyl(0, 0, -0.02, 0, 0.05, "METAL-BLACK", 20)
    mb.cyl(0, 0, -drop, -0.02, 0.003, "METAL-BLACK", 6)
    mb.cyl(0, 0, -drop - 0.03, -drop, 0.02, "METAL-BLACK", 10)
    mb.tube(0, 0, -drop - H, -drop, r, r - 0.003, mats_for(it, "shade") or LINEN, 32)
    mb.cyl(0, 0, -drop - 0.012, -drop - 0.008, r - 0.003, "METAL-BLACK", 4) if False else None
    for i in range(3):                                          # the shade's spider: three arms from the lamp holder
        ang = 2 * math.pi * i / 3; x, y = math.cos(ang) * (r - 0.005) / 2, math.sin(ang) * (r - 0.005) / 2
        mb.box(min(0, 2 * x) - 0.002 if x < 0 else -0.002, max(0, 2 * x) + 0.002 if x > 0 else 0.002,
               min(0, 2 * y) - 0.002 if y < 0 else -0.002, max(0, 2 * y) + 0.002 if y > 0 else 0.002, -drop - 0.022, -drop - 0.018, "METAL-BLACK")


def k_radiator_panel(mb, W, D, H, it):
    m = mats_for(it, "all") or WHITE
    mb.box(-W / 2, W / 2, D / 2 - 0.022, D / 2, 0, H, m, 0.004)                     # the flat front panel
    mb.box(-W / 2 + 0.01, W / 2 - 0.01, -D / 2 + 0.012, D / 2 - 0.022, 0.03, H - 0.03, m)   # convector behind
    for sx in (-1, 1): mb.box(sx * W * 0.35 - 0.02, sx * W * 0.35 + 0.02, -D / 2, -D / 2 + 0.012, H * 0.6, H * 0.7, m)   # brackets
    mb.cyl(-W / 2 - 0.03, D / 2 - 0.02, -0.08, 0.06, 0.012, "METAL-BLACK", 12)        # TRV left
    mb.cyl(W / 2 + 0.03, D / 2 - 0.02, -0.06, 0.03, 0.01, "METAL-BLACK", 12)          # lockshield right
    mb.box(-W / 2 - 0.03, -W / 2, D / 2 - 0.026, D / 2 - 0.014, 0.0, 0.02, "METAL-BLACK"); mb.box(W / 2, W / 2 + 0.03, D / 2 - 0.026, D / 2 - 0.014, 0.0, 0.02, "METAL-BLACK")


ART = {"sage": "FAB-CUSH-SAGE", "terracotta": "FAB-CUSH-TERRA", "clay": "FIN-WALL-CLAY", "cream": "FAB-CUSH-CREAM", "warm grey": "FIN-FLR-TILE"}


def k_framed_print(mb, W, D, H, it):
    a = it["asset"]; fr = mats_for(it, "frame") or ("WOOD-OAK-FURN" if "oak" in a.get("frame", "") else "METAL-BLACK")
    t = 0.02
    mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, t, fr); mb.box(-W / 2, W / 2, -D / 2, D / 2, H - t, H, fr)
    mb.box(-W / 2, -W / 2 + t, -D / 2, D / 2, t, H - t, fr); mb.box(W / 2 - t, W / 2, -D / 2, D / 2, t, H - t, fr)
    mount = 0.05 if "mount 50" in a.get("frame", "") else 0.0
    mb.box(-W / 2 + t, W / 2 - t, -D / 2, D / 2 - 0.006, t, H - t, WHITE)            # the white mount
    motif = a.get("motif", "")
    cols = [v for k, v in ART.items() if k in motif]
    if cols:                                                # the print in the motif's own named colours (spec finishes)
        x0, x1, z0, z1 = -W / 2 + t + mount, W / 2 - t - mount, t + mount, H - t - mount
        if len(cols) == 1: mb.box(x0, x1, -D / 2, D / 2 - 0.004, z0, z1, cols[0])
        else:
            zm = z0 + (z1 - z0) * 0.55
            mb.box(x0, x1, -D / 2, D / 2 - 0.004, z0, zm, cols[0]); mb.box(x0, x1, -D / 2, D / 2 - 0.004, zm, z1, cols[1])
    else:
        QUESTIONS.append(dict(id=it["id"], what="print artwork: the motif names no colour/image the build can use; the frame and white mount are built, the print area is left as the mount",
                              evidence=motif))


def k_sofa(mb, W, D, H, it):
    a = it["asset"]; up = mats_for(it, "upholstery", "upholstery") or mats_for(it, "cushions") or "FAB-SOFA"
    frame = mats_for(it, "frame")
    legs = mats_for(it, "legs") or ("WOOD-OAK-FURN" if "oak" in str(a.get("legs", "oak")) else None)
    n = int(a.get("seats", 3)); arm = 0.15 if "150" in str(a.get("arms", "150")) else 0.12
    if frame == "RATTAN":
        mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, 0.38, "RATTAN", 0.01); mb.box(-W / 2, W / 2, -D / 2, -D / 2 + 0.12, 0.38, H, "RATTAN", 0.01)
        for sx in (-1, 1): mb.box(sx * W / 2 - (arm if sx > 0 else 0), sx * W / 2 + (arm if sx < 0 else 0), -D / 2, D / 2, 0.38, 0.62, "RATTAN", 0.01)
        sw = (W - 2 * arm) / n
        for i in range(n):
            x0 = -W / 2 + arm + i * sw
            mb.box(x0 + 0.005, x0 + sw - 0.005, -D / 2 + 0.12, D / 2 - 0.02, 0.38, 0.5, up, 0.03)
            mb.box(x0 + 0.01, x0 + sw - 0.01, -D / 2 + 0.12, -D / 2 + 0.27, 0.5, H - 0.05, up, 0.04)
        return
    lh = 0.12
    for sx in (-1, 1):
        for sy in (-1, 1): mb.cyl(sx * (W / 2 - 0.06), sy * (D / 2 - 0.06), 0, lh, 0.022, legs or "WOOD-OAK-FURN", 10, r1=0.016)
    mb.box(-W / 2, W / 2, -D / 2, D / 2, lh, 0.30, up, 0.015)                                     # base
    for sx in (-1, 1): mb.box(sx * W / 2 - (arm if sx > 0 else 0), sx * W / 2 + (arm if sx < 0 else 0), -D / 2, D / 2, 0.30, 0.62, up, 0.04)
    mb.box(-W / 2 + arm, W / 2 - arm, -D / 2, -D / 2 + 0.18, 0.30, H - 0.22, up, 0.03)             # back frame
    sw = (W - 2 * arm) / n
    for i in range(n):
        x0 = -W / 2 + arm + i * sw
        mb.box(x0 + 0.004, x0 + sw - 0.004, -D / 2 + 0.18, D / 2 - 0.01, 0.30, 0.45, up, 0.035)   # seat cushion
        mb.box(x0 + 0.008, x0 + sw - 0.008, -D / 2 + 0.03, -D / 2 + 0.22, 0.45, H, up, 0.05)       # back cushion


def k_cushion(mb, W, D, H, it):
    m = mats_for(it, "all", "fabric") or "FAB-CUSH-CREAM"
    b = it["asset"].get("corner_bulge_mm", 25) / 1000
    mb.box(-W / 2, W / 2, -D / 2 + 0.002, D / 2 - 0.002, 0.002, H, m, min(D * 0.45, b * 2.4))     # never in a face plane of the seat


def k_throw_drape(mb, W, D, H, it):
    m = mats_for(it, "all") or "FAB-THROW"
    w = W / 2                                              # folded in half along its width
    mb.box(-w / 2, w / 2, -0.30, 0.25, 0, H, m, 0.003)                                  # on the seat / arm
    mb.box(-w / 2, w / 2, 0.25, 0.25 + H, -0.38, 0, m, 0.003)                           # hanging down the front


def k_stove(mb, W, D, H, it):
    m = mats_for(it, "all") or "METAL-BLACK"
    mb.box(-W / 2, W / 2, -D / 2, D / 2, 0.08, H, m, 0.006)
    for sx in (-1, 1): mb.box(sx * W * 0.4 - 0.02, sx * W * 0.4 + 0.02, -D * 0.35, D * 0.35, 0, 0.08, m)
    mb.box(-W * 0.36, W * 0.36, D / 2, D / 2 + 0.004, 0.16, H - 0.12, "TV-BLACK")     # the glass door (off by day)


def k_slab(mb, W, D, H, it): mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, H, mats_for(it, "all") or "STONE-SLATE", 0.004)
def k_tv(mb, W, D, H, it): mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, H, mats_for(it, "all") or "TV-BLACK", 0.003)


def shaker(mb, x0, x1, y_front, z0, z1, key, frame=0.07, t=0.02, inset=0.006):
    """a shaker door/drawer front in the XZ plane at y_front (front face), frame members proud of the panel"""
    mb.box(x0, x1, y_front - t, y_front - inset, z0, z1, key)
    fr = min(frame, (x1 - x0) / 4, (z1 - z0) / 4)
    mb.box(x0, x0 + fr, y_front - inset, y_front, z0, z1, key); mb.box(x1 - fr, x1, y_front - inset, y_front, z0, z1, key)
    mb.box(x0 + fr, x1 - fr, y_front - inset, y_front, z0, z0 + fr, key); mb.box(x0 + fr, x1 - fr, y_front - inset, y_front, z1 - fr, z1, key)


def k_alcove_unit(mb, W, D, H, it):
    a = it["asset"]; ch = a.get("cupboard_h_mm", 900) / 1000; st = a.get("shelf_t_mm", 30) / 1000; sd = a.get("shelf_d_mm", 300) / 1000
    cup, sh, top = mats_for(it, "cupboard") or "KIT-FRONT", mats_for(it, "shelves") or "WOOD-OAK-FURN", mats_for(it, "top") or "WOOD-OAK-FURN"
    mb.box(-W / 2, W / 2, -D / 2, D / 2 - 0.02, 0.0, ch - 0.03, cup)
    for i in range(2): shaker(mb, -W / 2 + i * W / 2 + 0.002, -W / 2 + (i + 1) * W / 2 - 0.002, D / 2, 0.08, ch - 0.032, cup)
    mb.box(-W / 2, W / 2, -D / 2, D / 2, ch - 0.03, ch, top)
    for y in a.get("shelves_y_m", []): mb.box(-W / 2, W / 2, -D / 2, -D / 2 + sd, y - st, y, sh)


def k_armchair(mb, W, D, H, it):
    up = mats_for(it, "upholstery", "upholstery") or "FAB-SOFA"; fr = mats_for(it, "frame") or "WOOD-OAK-FURN"
    if fr == "RATTAN":
        mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, 0.38, "RATTAN", 0.01); mb.box(-W / 2, W / 2, -D / 2, -D / 2 + 0.12, 0.38, H, "RATTAN", 0.01)
        for sx in (-1, 1): mb.box(sx * W / 2 - (0.1 if sx > 0 else 0), sx * W / 2 + (0.1 if sx < 0 else 0), -D / 2, D / 2, 0.38, 0.6, "RATTAN", 0.01)
        mb.box(-W / 2 + 0.1, W / 2 - 0.1, -D / 2 + 0.12, D / 2 - 0.02, 0.38, 0.5, up, 0.03); return
    for sx in (-1, 1):
        for sy in (-1, 1): mb.cyl(sx * (W / 2 - 0.05), sy * (D / 2 - 0.06), 0, 0.14, 0.02, fr, 10, r1=0.015)
    mb.box(-W / 2, W / 2, -D / 2, D / 2, 0.14, 0.40, up, 0.06)
    mb.box(-W / 2, W / 2, -D / 2, -D / 2 + 0.2, 0.40, H, up, 0.09)
    for sx in (-1, 1): mb.box(sx * W / 2 - (0.12 if sx > 0 else 0), sx * W / 2 + (0.12 if sx < 0 else 0), -D / 2 + 0.1, D / 2 - 0.04, 0.40, 0.58, up, 0.05)


def k_floor_lamp(mb, W, D, H, it):
    a = it["asset"]; base = mats_for(it, "base") or "METAL-BLACK"; shade = mats_for(it, "shade") or LINEN
    sh = 0.30; r = W / 2; top = H - sh
    for i in range(3):
        ang = 2 * math.pi * i / 3 + 0.5; fx, fy = math.cos(ang) * 0.17, math.sin(ang) * 0.17
        bm_ = bmesh.new()
        mb.pieces.append(_leg((fx, fy, 0), (0, 0, top * 0.85), 0.008, base))
    mb.cyl(0, 0, top * 0.85, top + 0.12, 0.008, base, 8)
    mb.tube(0, 0, top, H, r, r - 0.003, shade, 32)


def _leg(a, b, r, key, seg=6):
    A, B = Vector(a), Vector(b); d = (B - A).normalized()
    u = d.orthogonal().normalized(); v = d.cross(u)
    V = [tuple(P + (u * math.cos(2 * math.pi * i / seg) + v * math.sin(2 * math.pi * i / seg)) * r) for P in (A, B) for i in range(seg)]
    F = [tuple(reversed(range(seg))), tuple(range(seg, 2 * seg))] + [(i, (i + 1) % seg, seg + (i + 1) % seg, seg + i) for i in range(seg)]
    return (V, F, key, 0.0)


def k_table_lamp(mb, W, D, H, it):
    base = mats_for(it, "base") or "CER-CREAM"; shade = mats_for(it, "shade") or LINEN
    if not (it.get("materials") or {}).get("base"): NOTES.append(f"{it['id']}: base CER-CREAM and linen shade from the asset words")
    mb.cyl(0, 0, 0, 0.26, 0.08, base, 24, r1=0.06)
    mb.cyl(0, 0, 0.26, H - 0.2, 0.006, "BRASS", 8)
    mb.tube(0, 0, H - 0.22, H, W / 2, W / 2 - 0.003, shade, 32)


def k_curtain_pair(mb, W, D, H, it):
    a = it["asset"]; fab = mats_for(it, "fabric", "fabric") or LINEN; pole = mats_for(it, "pole") or "METAL-BLACK"
    pw = a.get("pole_width_mm", W * 1000) / 1000; stack = a.get("stacked_each_side_mm", 300) / 1000
    mb.cyl(-pw / 2, 0.0, H - 0.0125, H + 0.0125, 0.0125, pole, 12, axis="x") if False else None
    mb.box(-pw / 2, pw / 2, -0.0125, 0.0125, H - 0.03, H - 0.005, pole, 0.006)
    for sx in (-1, 1): mb.cyl(sx * (pw / 2 + 0.03), 0.0, H - 0.045, H + 0.01, 0.022, pole, 12)
    for sx in (-1, 1):
        x0 = sx * pw / 2 - (stack if sx > 0 else 0); x1 = x0 + stack
        # pleated panel: a zig-zag of folds (fullness 2 -> fold depth)
        nf = 6; pts_f, pts_b = [], []
        for k in range(nf * 2 + 1):
            x = x0 + (x1 - x0) * k / (nf * 2); y = (0.035 if k % 2 else -0.035)
            pts_f.append((x, y + 0.01)); pts_b.append((x, y - 0.01))
        poly = pts_f + pts_b[::-1]
        mb.poly_prism(poly, 0.0, H - 0.035, fab)


def kitchen_unit(mb, W, D, H, it):
    a = it["asset"]; front = mats_for(it, "front", "front") or "KIT-FRONT"; top = mats_for(it, "worktop")
    unit = a.get("unit", ""); pl = a.get("plinth_mm", 150) / 1000; wt = a.get("worktop_top_y", 0.91)
    tall = H > 1.2
    tt = 0.038 if top == "KITB-TOP" else 0.03
    ctop = H if tall else min(H, wt - tt) if H >= wt - 0.01 else H - 0.02
    mb.box(-W / 2, W / 2, -D / 2, D / 2 - 0.07, 0, pl, "METAL-BLACK" if False else front)              # plinth (front colour)
    mb.box(-W / 2, W / 2, -D / 2, D / 2 - 0.022, pl, ctop, front)                                       # carcass
    handles = "BRASS" if front == "KIT-FRONT" else None
    if "washing machine" in unit or "tumble dryer" in unit:
        mb.box(-W / 2 + 0.002, W / 2 - 0.002, D / 2 - 0.022, D / 2 - 0.002, pl, ctop, WHITE)
        mb.cyl(0, D / 2 - 0.002, pl + 0.32, pl + 0.32 + 0.001, 0.0, WHITE) if False else None
        mb.cyl(0, D / 2 - 0.004, (pl + ctop) / 2 - 0.2, (pl + ctop) / 2 + 0.2, 0.17, "TV-BLACK", 32) if False else None
        mb.pieces.append(_disc((0, D / 2 - 0.002, (pl + ctop) / 2 - 0.05), 0.16, 0.012, "TV-BLACK"))
        NOTES.append(f"{it['id']}: appliance white = RAL9016 (the spec's white)")
    elif "oven" in unit:
        shaker(mb, -W / 2 + 0.002, W / 2 - 0.002, D / 2, ctop - 0.14, ctop - 0.002, front)
        mb.box(-W / 2 + 0.01, W / 2 - 0.01, D / 2 - 0.022, D / 2, pl + 0.02, ctop - 0.16, "TV-BLACK")
        mb.box(-W * 0.35, W * 0.35, D / 2, D / 2 + 0.02, ctop - 0.2, ctop - 0.18, "STEEL-BRUSHED")
    elif "dishwasher" in unit:
        shaker(mb, -W / 2 + 0.002, W / 2 - 0.002, D / 2, pl + 0.002, ctop - 0.002, front)
    elif "drawer" in unit or "pan drawers" in unit:
        n = 3 if "3 drawers" in unit or "drawers" in unit else 2
        hh = (ctop - pl) / n
        for i in range(n):
            shaker(mb, -W / 2 + 0.002, W / 2 - 0.002, D / 2, pl + i * hh + 0.002, pl + (i + 1) * hh - 0.002, front)
            if handles: mb.box(-0.08, 0.08, D / 2, D / 2 + 0.025, pl + (i + 1) * hh - 0.06, pl + (i + 1) * hh - 0.048, handles, 0.004)
    else:
        nd = 2 if W > 0.65 else 1
        dw = W / nd
        for i in range(nd):
            x0 = -W / 2 + i * dw
            shaker(mb, x0 + 0.002, x0 + dw - 0.002, D / 2, pl + 0.002, ctop - 0.002, front)
            if handles:
                hx = x0 + dw - 0.05 if (i == 0 and nd == 2) or nd == 1 else x0 + 0.05
                mb.box(hx - 0.006, hx + 0.006, D / 2, D / 2 + 0.025, ctop - 0.24 if not tall else 0.9, ctop - 0.08 if not tall else 1.06, handles, 0.004)
    if not tall and top:
        mb.box(-W / 2, W / 2, -D / 2, D / 2, ctop, ctop + tt, top, 0.002)
        if "sink" in unit:
            mb.box(-0.22, 0.22, -0.2, 0.18, ctop + tt - 0.001, ctop + tt + 0.004, "STEEL-BRUSHED")          # sink rim (bowl below)
            mb.cyl(0, -0.24, ctop + tt, ctop + tt + 0.3, 0.014, "BRASS" if "brass" in unit else "STEEL-BRUSHED", 12)
            mb.box(-0.012, 0.012, -0.24, -0.02, ctop + tt + 0.28, ctop + tt + 0.3, "BRASS" if "brass" in unit else "STEEL-BRUSHED")
            if "chrome" in unit: NOTES.append(f"{it['id']}: chrome mixer built in STEEL-BRUSHED (the spec's only bright metal)")
        if "hob" in unit:
            mb.box(-min(0.39, W / 2 - 0.01), min(0.39, W / 2 - 0.01), -0.26, 0.26, ctop + tt, ctop + tt + 0.006, "TV-BLACK")
    elif tall and top is None:
        pass


def _disc(c, r, t, key, seg=32):
    """a disc facing +y (a washing-machine door)"""
    cx, cy, cz = c
    V = [(cx + r * math.cos(2 * math.pi * i / seg), cy + dy, cz + r * math.sin(2 * math.pi * i / seg)) for dy in (-t, 0.0) for i in range(seg)]
    F = [tuple(range(seg)), tuple(reversed(range(seg, 2 * seg)))] + [(i, seg + i, seg + (i + 1) % seg, (i + 1) % seg) for i in range(seg)]
    return (V, F, key, 0.0)


def k_cooker_hood(mb, W, D, H, it):
    m = mats_for(it, "all") or "STEEL-BRUSHED"
    mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, 0.06, m, 0.003)
    mb.box(-W / 2 + 0.05, W / 2 - 0.05, -D / 2, D / 2 - 0.12, 0.06, 0.16, m)
    mb.box(-0.13, 0.13, -D / 2, -D / 2 + 0.26, 0.16, H, m)


def k_wall_units(mb, W, D, H, it, origin):
    """segments in world x or z: built in the item's local frame relative to its position"""
    a = it["asset"]; front = mats_for(it, "front", "front") or "KIT-FRONT"; d = a.get("depth_mm", 330) / 1000
    segs = a.get("segments_x") or a.get("segments_z") or []
    along_z = "segments_z" in a
    yaw = it["yaw_deg"]
    ex = a.get("extractor")
    for s0, s1 in segs:
        lo, hi = min(s0, s1), max(s0, s1)
        # local x along the run: for yaw 0 local x = world x; for yaw 90 local x = world -z? (W axis = (cos yaw, -sin yaw) in viewer x,z)
        def lx(w):
            if along_z: return -(w - origin[2]) if math.isclose(math.sin(math.radians(yaw)), 1, abs_tol=1e-6) else (w - origin[2])
            return w - origin[0]
        x0, x1 = sorted((lx(lo), lx(hi)))
        cuts = [x0, x1]
        if ex and along_z:
            e0, e1 = sorted((lx(ex["z"][0]), lx(ex["z"][1])))
            cuts = sorted(set([x0, x1] + [c for c in (e0, e1) if x0 < c < x1]))
        n_d = max(1, round((x1 - x0) / 0.6))
        for i in range(len(cuts) - 1):
            c0, c1 = cuts[i], cuts[i + 1]
            is_ex = ex and along_z and abs(((c0 + c1) / 2) - (sum(sorted((lx(ex["z"][0]), lx(ex["z"][1])))) / 2)) < 0.05
            mb.box(c0, c1, -D / 2, -D / 2 + d - 0.02, 0, H, front)
            nd = max(1, round((c1 - c0) / 0.5))
            dw = (c1 - c0) / nd
            for k in range(nd):
                shaker(mb, c0 + k * dw + 0.002, c0 + (k + 1) * dw - 0.002, -D / 2 + d, 0.002, H - 0.002, front)
            if is_ex: mb.box(c0 + 0.01, c1 - 0.01, -D / 2 + 0.02, -D / 2 + d - 0.03, -0.004, 0.0, "STEEL-BRUSHED")


def k_tile_band(mb, W, D, H, it): mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, H, mats_for(it, "all") or "TILE-METRO-WHITE")


def k_kettle(mb, W, D, H, it):
    m = "CER-CREAM"; NOTES.append(f"{it['id']}: '{it['asset'].get('finish', '')}' built in CER-CREAM (the spec's matt cream)")
    r0 = D / 2                                             # body across the depth; the handle takes the width
    mb.cyl(-W / 2 + r0, 0, 0, 0.02, r0, "METAL-BLACK", 20)
    mb.cyl(-W / 2 + r0, 0, 0.02, H - 0.04, r0 * 0.98, m, 20, r1=r0 * 0.75)
    mb.cyl(-W / 2 + r0, 0, H - 0.04, H, r0 * 0.45, m, 16)
    mb.box(-W / 2 + 2 * r0 - 0.01, W / 2, -0.012, 0.012, H * 0.3, H * 0.85, m, 0.006)


def k_toaster(mb, W, D, H, it):
    mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, H, "CER-CREAM", 0.03)
    for sy in (-0.04, 0.04): mb.box(-W * 0.38, W * 0.38, sy - 0.012, sy + 0.012, H - 0.003, H + 0.001, "METAL-BLACK")
    NOTES.append(f"{it['id']}: cream enamel built in CER-CREAM")


def k_coffee_machine(mb, W, D, H, it):
    m = mats_for(it, "all") or "STEEL-BRUSHED"
    mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, H, m, 0.01)
    mb.box(-W * 0.3, W * 0.3, D / 2 - 0.12, D / 2 + 0.002, 0.04, H * 0.45, "TV-BLACK")


def k_board(mb, W, D, H, it):
    m = "WOOD-OAK-FURN"
    tilt = math.radians(12) if it["asset"].get("leaning") else 0
    V = []
    for (x, y, z) in [(-W / 2, -D / 2, 0), (W / 2, -D / 2, 0), (W / 2, D / 2, 0), (-W / 2, D / 2, 0),
                      (-W / 2, -D / 2, H), (W / 2, -D / 2, H), (W / 2, D / 2, H), (-W / 2, D / 2, H)]:
        V.append((x, y - z * math.sin(tilt) + 0.0, z * math.cos(tilt)))
    F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mb.pieces.append((V, F, m, 0.0))


def k_washing_machine(mb, W, D, H, it):
    mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, H, WHITE, 0.01)
    mb.pieces.append(_disc((0, D / 2 + 0.008, H * 0.45), 0.16, 0.01, "TV-BLACK"))
    mb.box(-W / 2 + 0.02, W / 2 - 0.02, D / 2, D / 2 + 0.004, H - 0.1, H - 0.02, "STEEL-BRUSHED")
    NOTES.append(f"{it['id']}: 'white' appliance = RAL9016")


def k_table_low(mb, W, D, H, it):
    fr = mats_for(it, "frame") or "RATTAN"
    mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, H - 0.006, fr, 0.01)
    mb.box(-W / 2, W / 2, -D / 2, D / 2, H - 0.006, H, "GLASS-CLEAR")


def k_bed(mb, W, D, H, it):
    a = it["asset"]; fr = mats_for(it, "frame") or "FAB-SOFA"; lin_ = mats_for(it, "linen") or "BED-LINEN"
    throw = mats_for(it, "throw") or ("THROW-BED" if a.get("throw") else None)
    mw, ml, mh = [x / 1000 for x in a.get("mattress_mm", [W * 1000 - 100, D * 1000 - 100, 250])]
    hb = a.get("headboard_h_mm", H * 1000) / 1000
    base_h = 0.30
    mb.box(-W / 2, W / 2, -D / 2 + 0.08, D / 2, 0, base_h, fr, 0.02)
    mb.box(-W / 2, W / 2, -D / 2, -D / 2 + 0.08, 0, hb, fr, 0.025)                                     # headboard
    mb.box(-mw / 2, mw / 2, -D / 2 + 0.09, -D / 2 + 0.09 + ml, base_h, base_h + mh, lin_, 0.04)         # mattress + sheet
    mb.box(-mw / 2 - 0.02, mw / 2 + 0.02, -D / 2 + 0.55, -D / 2 + 0.09 + ml + 0.03, base_h + mh, base_h + mh + 0.06, lin_, 0.03)   # duvet
    n = int(a.get("pillows", 2)); pw = mw / max(1, n // 2 if n >= 4 else n)
    rows = 2 if n >= 4 else 1
    for r in range(rows):
        for i in range(n // rows):
            x0 = -mw / 2 + i * pw
            mb.box(x0 + 0.02, x0 + pw - 0.02, -D / 2 + 0.11 + r * 0.06, -D / 2 + 0.11 + r * 0.06 + 0.42, base_h + mh + 0.01 + r * 0.05, base_h + mh + 0.15 + r * 0.05, lin_, 0.05)
    if throw:
        y1 = -D / 2 + 0.09 + ml + 0.04
        mb.box(-mw / 2 - 0.03, mw / 2 + 0.03, y1 - 0.5, y1, base_h + mh + 0.06, base_h + mh + 0.075, throw, 0.005)


def k_bedside(mb, W, D, H, it):
    m = mats_for(it, "all") or "WOOD-OAK-FURN"
    mb.box(-W / 2, W / 2, -D / 2, D / 2 - 0.02, 0.06, H, m, 0.004)
    for sx in (-1, 1):
        for sy in (-1, 1): mb.box(sx * (W / 2 - 0.03) - 0.015, sx * (W / 2 - 0.03) + 0.015, sy * (D / 2 - 0.04) - 0.015, sy * (D / 2 - 0.04) + 0.015, 0, 0.06, m)
    shaker(mb, -W / 2 + 0.01, W / 2 - 0.01, D / 2, H - 0.18, H - 0.03, m, frame=0.03)
    mb.cyl(0, D / 2 + 0.012, H - 0.105, H - 0.095, 0.012, "BRASS", 12, axis="y") if False else None


def k_wardrobe(mb, W, D, H, it):
    m = mats_for(it, "all", "front") or "KIT-FRONT"; a = it["asset"]
    mb.box(-W / 2, W / 2, -D / 2, D / 2 - 0.022, 0, H, m)
    n = int(a.get("doors", 2)); dw = W / n
    for i in range(n):
        x0 = -W / 2 + i * dw
        shaker(mb, x0 + 0.002, x0 + dw - 0.002, D / 2, 0.08, H - 0.002, m)
        if "brass" in a.get("handles", ""):
            hx = x0 + dw - 0.05 if i % 2 == 0 else x0 + 0.05
            mb.pieces.append(_disc((hx, D / 2 + 0.03, 1.05), 0.015, 0.03, "BRASS", 12))


def k_chest(mb, W, D, H, it):
    m = mats_for(it, "all") or "WOOD-OAK-FURN"; n = int(it["asset"].get("drawers", 3))
    mb.box(-W / 2, W / 2, -D / 2, D / 2 - 0.02, 0.06, H, m, 0.004)
    mb.box(-W / 2 + 0.03, W / 2 - 0.03, -D / 2 + 0.03, D / 2 - 0.05, 0, 0.06, m)
    hh = (H - 0.1) / n
    for i in range(n): shaker(mb, -W / 2 + 0.01, W / 2 - 0.01, D / 2, 0.08 + i * hh, 0.08 + (i + 1) * hh - 0.004, m, frame=0.035)


def k_desk(mb, W, D, H, it):
    m = mats_for(it, "all") or "WOOD-OAK-FURN"
    mb.box(-W / 2, W / 2, -D / 2, D / 2, H - 0.025, H, m, 0.003)
    for sx in (-1, 1):
        for sy in (-1, 1): mb.box(sx * (W / 2 - 0.04) - 0.02, sx * (W / 2 - 0.04) + 0.02, sy * (D / 2 - 0.04) - 0.02, sy * (D / 2 - 0.04) + 0.02, 0, H - 0.025, m)
    if it["asset"].get("drawers"): shaker(mb, -W * 0.25, W * 0.25, D / 2 - 0.04, H - 0.12, H - 0.03, m, frame=0.02)


def k_mirror_cabinet(mb, W, D, H, it):
    mb.box(-W / 2, W / 2, -D / 2, D / 2 - 0.006, 0, H, WHITE, 0.003)
    mb.box(-W / 2 + 0.005, W / 2 - 0.005, D / 2 - 0.006, D / 2, 0.005, H - 0.005, "MIRROR")
    NOTES.append(f"{it['id']}: body 'white' = RAL9016; mirror face = mirror")


def k_towel_rail(mb, W, D, H, it):
    m = mats_for(it, "all") or "METAL-BLACK"
    for sx in (-1, 1): mb.cyl(sx * (W / 2 - 0.015), 0, 0, H, 0.015, m, 10)
    n = 9
    for i in range(n):
        z = 0.1 + (H - 0.15) * i / (n - 1)
        mb.box(-W / 2 + 0.015, W / 2 - 0.015, -0.01, 0.01, z - 0.01, z + 0.01, m)
    for sx in (-1, 1): mb.box(sx * (W / 2 - 0.015) - 0.01, sx * (W / 2 - 0.015) + 0.01, -D / 2, -0.01, H * 0.8, H * 0.8 + 0.02, m)


def k_towels(mb, W, D, H, it):
    col = it["asset"].get("colour", "")
    keys = [k for w, k in (("cream", "FAB-CUSH-CREAM"), ("sage", "FAB-CUSH-SAGE")) if w in col]
    if not keys: QUESTIONS.append(dict(id=it["id"], what="towel colour not named", evidence=col)); return False
    NOTES.append(f"{it['id']}: towels '{col}' in the spec's cream and sage finishes")
    for i, k in enumerate(keys):
        x0 = -W / 2 + i * W / len(keys)
        mb.box(x0 + 0.01, x0 + W / len(keys) - 0.01, -D / 2, D / 2, 0, H, k, 0.008)


def k_island(mb, W, D, H, it):
    a = it["asset"]; front = mats_for(it, "front", "front") or "KIT-ISLAND"; top = mats_for(it, "top") or "KIT-TOP"
    cd = a.get("carcass_d_mm", 650) / 1000; tt = a.get("top_t_mm", 30) / 1000
    # overhang on +z (viewer) = local -Y for yaw 0 (front faces -z): the carcass sits at the -z (front, +Y local) side
    y0 = D / 2 - cd
    mb.box(-W / 2 + 0.05, W / 2 - 0.05, y0 + 0.05, D / 2 - 0.05, 0, 0.15, front)
    mb.box(-W / 2, W / 2, y0, D / 2 - 0.02, 0.15, H - tt, front)
    nd = 2; dw = W / nd
    for i in range(nd): mb.box(-W / 2 + i * dw + 0.002, -W / 2 + (i + 1) * dw - 0.002, D / 2 - 0.02, D / 2, 0.152, H - tt - 0.002, front)
    mb.box(-W / 2, W / 2, -D / 2, D / 2, H - tt, H, top, 0.003)


def k_upstand(mb, W, D, H, it): mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, H, mats_for(it, "all") or "KIT-TOP")


def k_roman_blind(mb, W, D, H, it):
    m = mats_for(it, "all", "fabric") or LINEN; n = int(it["asset"].get("folds", 5))
    mb.box(-W / 2, W / 2, -D / 2, D / 2 - 0.03, H - 0.04, H, m)                           # head rail cover
    fh = (H - 0.04) / n
    for i in range(n): mb.box(-W / 2, W / 2, -D / 2, D / 2 - 0.03 + 0.03 * (i % 2), i * fh, (i + 1) * fh, m, 0.008)


def k_dining_table(mb, W, D, H, it):
    m = mats_for(it, "all") or "WOOD-OAK-FURN"
    mb.box(-W / 2, W / 2, -D / 2, D / 2, H - 0.04, H, m, 0.02)
    for sx in (-1, 1):
        for sy in (-1, 1): mb.box(sx * (W / 2 - 0.1) - 0.035, sx * (W / 2 - 0.1) + 0.035, sy * (D / 2 - 0.1) - 0.035, sy * (D / 2 - 0.1) + 0.035, 0, H - 0.04, m)
    mb.box(-W / 2 + 0.135, W / 2 - 0.135, -D / 2 + 0.11, -D / 2 + 0.13, H - 0.12, H - 0.04, m)
    mb.box(-W / 2 + 0.135, W / 2 - 0.135, D / 2 - 0.13, D / 2 - 0.11, H - 0.12, H - 0.04, m)


def k_linear_pendant(mb, W, D, H, it, anchor_y):
    m = mats_for(it, "all") or "METAL-BLACK"; by = it["asset"].get("bottom_y", 1.6)
    z0 = by - anchor_y
    mb.box(-W / 2, W / 2, -D / 2, D / 2, z0 + 0.006, z0 + H, m, 0.004)
    mb.box(-W / 2 + 0.005, W / 2 - 0.005, -D / 2 + 0.006, D / 2 - 0.006, z0, z0 + 0.006, WHITE)          # opal diffuser
    for sx in (-1, 1):
        mb.cyl(sx * W * 0.4, 0, z0 + H, 0, 0.0015, m, 4)
        mb.box(sx * W * 0.4 - 0.04, sx * W * 0.4 + 0.04, -0.03, 0.03, -0.015, 0, m)


def k_bottle_pair_tray(mb, W, D, H, it):
    mb.box(-W / 2, W / 2, -D / 2, D / 2, 0, 0.015, "WOOD-OAK-FURN", 0.003)
    for sx in (-1, 1):
        mb.cyl(sx * W * 0.22, 0, 0.015, H * 0.75, 0.032, "GLASS-CLEAR", 16)
        mb.cyl(sx * W * 0.22, 0, H * 0.75, H, 0.012, "GLASS-CLEAR", 10)


def k_tea_towel(mb, W, D, H, it):
    a = it["asset"].get("fabric", "")
    keys = [k for w, k in (("cream", "FAB-CUSH-CREAM"), ("sage", "FAB-CUSH-SAGE")) if w in a]
    if not keys: QUESTIONS.append(dict(id=it["id"], what="tea towel colours", evidence=a)); return False
    n = 7; sw = W / 2 / n                                    # folded over the handle: half the width hangs
    for i in range(n): mb.box(-W / 4 + i * sw, -W / 4 + (i + 1) * sw, -0.004, 0.004, -H / 2, 0, keys[i % len(keys)])
    NOTES.append(f"{it['id']}: striped cream/sage in the spec's cream and sage finishes, hung folded (half the width)")


def k_mirror_round(mb, W, D, H, it):
    fr = mats_for(it, "frame") or "WOOD-OAK-FURN"; r = W / 2
    V = []; seg = 48
    mb.pieces.append(_ring_y(0, 0, H / 2, r, r - 0.02, D, fr, seg))
    mb.pieces.append(_disc((0, D / 2 - 0.004, H / 2), r - 0.02, 0.006, "MIRROR", seg))


def _ring_y(cx, cy, cz, ro, ri, d, key, seg):
    V = []
    for y in (-d / 2, d / 2):
        for rr in (ro, ri):
            for i in range(seg): a = 2 * math.pi * i / seg; V.append((cx + rr * math.cos(a), cy + y, cz + rr * math.sin(a)))
    def ix(yl, ring, i): return yl * 2 * seg + ring * seg + i % seg
    F = []
    for i in range(seg):
        F.append((ix(0, 0, i), ix(1, 0, i), ix(1, 0, i + 1), ix(0, 0, i + 1)))
        F.append((ix(0, 1, i + 1), ix(1, 1, i + 1), ix(1, 1, i), ix(0, 1, i)))
        F.append((ix(0, 1, i), ix(0, 0, i), ix(0, 0, i + 1), ix(0, 1, i + 1)))
        F.append((ix(1, 0, i), ix(1, 1, i), ix(1, 1, i + 1), ix(1, 0, i + 1)))
    return (V, F, key, 0.0)


def k_mirror_rect(mb, W, D, H, it):
    t = 0.012
    for (x0, x1, z0, z1) in ((-W / 2, W / 2, 0, t), (-W / 2, W / 2, H - t, H), (-W / 2, -W / 2 + t, t, H - t), (W / 2 - t, W / 2, t, H - t)):
        mb.box(x0, x1, -D / 2, D / 2, z0, z1, "METAL-BLACK")
    mb.box(-W / 2 + t, W / 2 - t, -D / 2, D / 2 - 0.004, t, H - t, "MIRROR")


def k_towel_ring(mb, W, D, H, it):
    mb.box(-0.03, 0.03, -D / 2, -D / 2 + 0.012, H - 0.06, H, "METAL-BLACK")
    mb.pieces.append(_ring_y(0, -D / 2 + 0.03, H - 0.11, 0.08, 0.072, 0.012, "METAL-BLACK", 24))
    mb.box(-0.11, 0.11, -D / 2 + 0.02, -D / 2 + 0.05, 0, H - 0.16, "FAB-CUSH-CREAM", 0.006)
    NOTES.append(f"{it['id']}: 'cream waffle' towel in FAB-CUSH-CREAM")


KINDS = dict(bench_box=k_bench_box, hook_rail=k_hook_rail, rug=k_rug, flush_disc=k_flush_disc, pendant_drum=k_pendant_drum,
             radiator_panel=k_radiator_panel, framed_print=k_framed_print, sofa=k_sofa, cushion=k_cushion, throw_drape=k_throw_drape,
             stove=k_stove, slab=k_slab, tv=k_tv, alcove_unit=k_alcove_unit, armchair=k_armchair, floor_lamp=k_floor_lamp,
             table_lamp=k_table_lamp, curtain_pair=k_curtain_pair, kitchen_unit=kitchen_unit, cooker_hood=k_cooker_hood,
             tile_band=k_tile_band, kettle=k_kettle, toaster=k_toaster, coffee_machine=k_coffee_machine, board=k_board,
             washing_machine=k_washing_machine, table_low=k_table_low, bed=k_bed, bedside=k_bedside, wardrobe=k_wardrobe, chest=k_chest,
             desk=k_desk, mirror_cabinet=k_mirror_cabinet, towel_rail=k_towel_rail, towels=k_towels, island=k_island, upstand=k_upstand,
             roman_blind=k_roman_blind, dining_table=k_dining_table, bottle_pair_tray=k_bottle_pair_tray, tea_towel=k_tea_towel,
             mirror_round=k_mirror_round, mirror_rect=k_mirror_rect, towel_ring=k_towel_ring, bookcase=None)


def k_bookcase(mb, W, D, H, it):
    m = mats_for(it, "all") or "KIT-FRONT"; n = int(it["asset"].get("shelves", 5)); t = 0.018
    mb.box(-W / 2, -W / 2 + t, -D / 2, D / 2, 0, H, m); mb.box(W / 2 - t, W / 2, -D / 2, D / 2, 0, H, m)
    mb.box(-W / 2 + t, W / 2 - t, -D / 2, -D / 2 + 0.008, 0, H, m)
    mb.box(-W / 2 + t, W / 2 - t, -D / 2, D / 2, H - t, H, m); mb.box(-W / 2 + t, W / 2 - t, -D / 2 + 0.008, D / 2 - 0.02, 0, 0.08, m)
    for i in range(1, n): z = 0.08 + (H - 0.08 - t) * i / n; mb.box(-W / 2 + t, W / 2 - t, -D / 2 + 0.008, D / 2 - 0.01, z - t, z, m)


KINDS["bookcase"] = k_bookcase


# ------------------------------------------------------------------------------------------------ Poly Haven assets
def _ph_proto(aid, root, log):
    """one normalised prototype object per Poly Haven id: meshes joined, front turned to +Y (Poly Haven models face -Y),
    origin at the footprint centre of the base; returns (object, (bx, by, bz)) or None"""
    if aid in _PH_CACHE: return _PH_CACHE[aid]
    d = os.path.join(root, aid)
    before = set(bpy.data.objects)
    try:
        if os.path.exists(os.path.join(d, f"{aid}.gltf")):
            bpy.ops.import_scene.gltf(filepath=os.path.join(d, f"{aid}.gltf"))
        elif os.path.exists(os.path.join(d, f"{aid}.blend")):
            with bpy.data.libraries.load(os.path.join(d, f"{aid}.blend"), link=False) as (src, dst):
                dst.objects = [n for n in src.objects]
            for o in dst.objects:
                if o is not None: bpy.context.scene.collection.objects.link(o)
        else:
            _PH_CACHE[aid] = None; return None
    except Exception as ex:
        log("polyhaven import failed", aid, ex); _PH_CACHE[aid] = None; return None
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes: _PH_CACHE[aid] = None; return None
    bm = bmesh.new()
    mats = []
    for o in meshes:
        me = o.data; M = o.matrix_world
        idx = []
        for m in me.materials:
            if m not in mats: mats.append(m)
            idx.append(mats.index(m))
        tmp = bmesh.new(); tmp.from_mesh(me); tmp.transform(M)
        for f in tmp.faces: f.material_index = idx[f.material_index] if f.material_index < len(idx) else 0
        tm = bpy.data.meshes.new("_ph"); tmp.to_mesh(tm); tmp.free()
        bm.from_mesh(tm); bpy.data.meshes.remove(tm)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi, 3, "Z"))
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]
    c = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)))
    bmesh.ops.translate(bm, verts=bm.verts, vec=-c)
    me = bpy.data.meshes.new(f"PH_{aid}")
    bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    for o in new: bpy.data.objects.remove(o)
    dims = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    # Quest budget (CONTRACT: <= 300k triangles for the whole house): a library model is reduced to a cap by its size
    # (small decor 3k, furniture and plants 10k); instances share the reduced mesh
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    cap = 1500 if max(dims) < 0.45 else 6000
    if tris > cap:
        tmpo = bpy.data.objects.new("_dec", me); bpy.context.scene.collection.objects.link(tmpo)
        md = tmpo.modifiers.new("dec", "DECIMATE"); md.ratio = cap / tris; md.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get(); me2 = bpy.data.meshes.new_from_object(tmpo.evaluated_get(dg))
        bpy.data.objects.remove(tmpo); bpy.data.meshes.remove(me); me = me2; me.name = f"PH_{aid}"
        NOTES.append(f"{aid}: {tris} -> {sum(len(p.vertices) - 2 for p in me.polygons)} triangles (Quest budget)")
    for m in mats:
        if not m: continue
        m.use_backface_culling = False       # library models are open shells (tubes, vase mouths): drawn both sides
        # roughness / metal maps become constants (the glTF exporter cannot write a 1-channel WebP; and fewer textures for the Quest)
        if m.use_nodes:
            for g_ in [n for n in m.node_tree.nodes if n.type == "GROUP" and n.node_tree and "gltf" in n.node_tree.name.lower()]:
                m.node_tree.nodes.remove(g_)          # occlusion from the ARM map: a 1-channel image WebP cannot hold
            for tn in [n for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image and n.image.channels < 3]:
                m.node_tree.nodes.remove(tn)          # 1-channel masks (the book set): WebP cannot hold them
            bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf:
                for inp, val in (("Roughness", 0.6), ("Metallic", 0.0)):
                    for lk in list(bsdf.inputs[inp].links): m.node_tree.links.remove(lk)
                    bsdf.inputs[inp].default_value = val
    _PH_CACHE[aid] = (me, dims)
    return _PH_CACHE[aid]


# ------------------------------------------------------------------------------------------------ the build
CEILING_KINDS = {"pendant_drum", "flush_disc", "linear_pendant"}
# CORRECTIONS 183 (Jack, 1 Nov: "it should be scripted well in the first place"): these scripted types are held back until each
# passes its close-up test sheet against a real product (renders/house-build/first-build/furniture-tests/); not placed as boxes
HOLD_KINDS = {"sofa", "armchair", "bed", "wardrobe", "desk", "dining_table", "island", "rug", "curtain_pair", "roman_blind",
              "throw_drape", "cushion", "chest", "bedside", "bookcase", "alcove_unit", "table_low", "bench_box"}
HELD = []
# G5b SHELL READY (Jack, 1 Nov 2026; CORRECTIONS-LOG 191): nothing is furnished until the bare shell passes tools/house/check_shell.py.
# Fixed fittings (kitchen and utility runs, sanitaryware, radiators, light fittings, joinery) are part of the shell; furniture,
# soft furnishings, decor and plants are held (the code stays: set SHELL_ONLY False once Jack has seen the shell).
SHELL_ONLY = True
SHELL_HOLD_CATS = {"furniture", "soft_furnishing", "decor", "plant"}
SOLID_CATS = {"furniture", "joinery", "appliance", "sanitary", "radiator"}


def build_items(spec, vkey, N, coll, fin, ph_root, house_objs, log):
    """every spec item of version vkey -> [(ob, p)] in the generator's objs format; QUESTIONS/NOTES filled"""
    out = []
    V = spec["versions"][vkey]
    # a tree of the house for ceiling ray-casts (flush lights on the vault)
    hv, ht = [], []
    for ob, p in house_objs:
        if ob.type != "MESH" or p.get("context"): continue
        b = len(hv); M = ob.matrix_world
        hv.extend(M @ v.co for v in ob.data.vertices); ht.extend(tuple(b + i for i in pl.vertices) for pl in ob.data.polygons)
    TREE = BVHTree.FromPolygons(hv, ht) if ht else None
    by_el = {}
    for ob, p in house_objs: by_el.setdefault(p["props"].get("element"), []).append(ob)
    stage = 1 if N == 1 else N
    # anything standing ON a held item is held with it (nothing may float: a lamp on a held bedside stays out too)
    held_boxes = []
    for it in V["items"]:
        if it["asset"].get("source") == "parametric" and it["asset"].get("kind") in HOLD_KINDS:
            W_, D_, H_ = [x / 1000 for x in it["size_mm"]]; held_boxes.append((it["position_m"], it["yaw_deg"], W_, D_, H_))
    def on_held(it):
        x, y, z = it["position_m"]
        for (p, yaw, W_, D_, H_) in held_boxes:
            c, s_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
            dx, dz = x - p[0], z - p[2]
            u = dx * c - dz * s_; v = -dx * s_ - dz * c          # along W (cos, -sin) and along the front (-sin, -cos)
            if abs(u) <= W_ / 2 + 0.02 and abs(v) <= D_ / 2 + 0.02 and p[1] + 0.05 < y <= p[1] + H_ + 0.08: return True
        return False
    for it in V["items"]:
        if SHELL_ONLY and it["category"] in SHELL_HOLD_CATS:
            HELD.append(it["id"] + " (G5b: no furniture/decor until SHELL READY)"); continue
        if it["asset"].get("source") in ("parametric", "polyhaven") and it["asset"].get("kind") not in HOLD_KINDS and on_held(it):
            HELD.append(it["id"] + " (stands on a held item)"); continue
        a = it["asset"]; src = a.get("source"); W, D, H = [x / 1000 for x in it["size_mm"]]
        pos = list(it["position_m"]); yaw = it["yaw_deg"]
        props = dict(element=f"SPEC-{it['id']}", spec_id=it["id"], spec_kind=a.get("kind") or a.get("id") or a.get("element"),
                     stage_in=stage, seq=0.95 if N > 1 else 0.0, category="finish" if N > 1 else "existing",
                     group="fitting", storey="first" if pos[1] > 2.0 else "ground",
                     label=f"{it['type']} ({it['id']}; spec_v1 {it['status']})", plain_label=it["type"][:80],
                     drawing="spec_v1 (signed 1 Nov 2026)", conf="assumed", provenance=it.get("provenance", "typical"),
                     collide=bool(it["category"] in SOLID_CATS and H > 0.3))
        ob = None
        if src == "elements":
            obs = by_el.get(a["element"], [])
            if not obs: QUESTIONS.append(dict(id=it["id"], what=f"element {a['element']} not in this build", evidence="")); continue
            key = (it.get("materials") or {}).get("all") or next(iter((it.get("materials") or {}).values()), None)
            for o in obs:
                if key and key in fin.F: o.data.materials.clear(); o.data.materials.append(fin.get(key))
                o["spec_id"] = it["id"]; o["spec_kind"] = "elements"
            continue
        if a.get("kind") == "note_only":
            ob = bpy.data.objects.new(f"SPEC-{it['id']}", None); place(ob, pos, yaw)
        elif src == "polyhaven":
            proto = _ph_proto(a["id"], ph_root, log)
            fit = a.get("fit", "uniform")
            if proto is None:
                QUESTIONS.append(dict(id=it["id"], what=f"Poly Haven {a['id']} could not be loaded: item left out", evidence=a.get("url", ""))); continue
            me, (bx, by, bz) = proto
            r = [W / max(bx, 1e-6), D / max(by, 1e-6), H / max(bz, 1e-6)]
            if fit == "scale_to_box" and (max(r) - min(r)) / max(r) > 0.05:
                kind = "framed_print" if "frame" in a["id"] else None
                if kind:
                    NOTES.append(f"{it['id']}: {a['id']} would stretch {100 * (max(r) - min(r)) / max(r):.0f} % to the box (rule: <= 5 %): built as the parametric framed print")
                    mb = MB(); KINDS[kind](mb, W, D, H, dict(it, asset=dict(a, frame="oak 20 mm, white mount 50 mm", motif=it["type"])))
                    ob = mb.build(f"SPEC-{it['id']}", fin)
                else:
                    s_ = min(r); ob = bpy.data.objects.new(f"SPEC-{it['id']}", me); ob.scale = (s_, s_, s_)
                    NOTES.append(f"{it['id']}: {a['id']} fitted uniformly (x{s_:.2f}) inside the box: stretching it would exceed the 5 % rule")
            else:
                s_ = min(r) if fit == "uniform" else None
                ob = bpy.data.objects.new(f"SPEC-{it['id']}", me)
                if s_ is not None: ob.scale = (s_, s_, s_)
                else: ob.scale = tuple(r)
            pl_ = Matrix.Translation(b3(pos)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
            if a.get("drop_to_bottom_y") is not None:          # a pendant hung so its bottom is at the given height
                pl_ = Matrix.Translation(b3([pos[0], a["drop_to_bottom_y"], pos[2]])) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
            ob.matrix_world = pl_ @ Matrix.Diagonal((*ob.scale, 1.0))
            ov = {k_: v_ for k_, v_ in (it.get("materials") or {}).items() if v_ in fin.F}
            if ov and ob.type == "MESH":                       # spec finish on a named part of the library model (pot, glaze, frame)
                me2 = ob.data.copy(); ob.data = me2
                for k_, v_ in ov.items():
                    hit = [i for i, m_ in enumerate(me2.materials) if m_ and k_.lower() in m_.name.lower()]
                    if not hit and len(me2.materials) == 1: hit = [0]
                    if not hit: NOTES.append(f"{it['id']}: no part '{k_}' on {a['id']}: finish {v_} not applied"); continue
                    for i in hit:
                        m2 = fin.get(v_).copy(); m2.name = fin.get(v_).name + "_2s"; m2.use_backface_culling = False   # open model: both sides
                        me2.materials[i] = m2
        elif src == "parametric" and a.get("kind") in HOLD_KINDS:
            HELD.append(it["id"]); continue
        elif src == "parametric":
            k = a.get("kind")
            fn = KINDS.get(k)
            if k == "downlight_set":
                mb = MB()
                for (x, z) in a.get("positions_xz", []):
                    dx, dz = x - pos[0], z - pos[2]
                    mb.cyl(dx, -dz, -0.01, 0.0, 0.0425, WHITE, 20)
                ob = mb.build(f"SPEC-{it['id']}", fin); place(ob, pos, 0)
            elif k == "wall_units":
                mb = MB(); k_wall_units(mb, W, D, H, it, pos); ob = mb.build(f"SPEC-{it['id']}", fin); place(ob, pos, yaw)
            elif k == "linear_pendant":
                mb = MB(); k_linear_pendant(mb, W, D, H, it, pos[1]); ob = mb.build(f"SPEC-{it['id']}", fin); place(ob, pos, yaw)
            elif fn is None:
                QUESTIONS.append(dict(id=it["id"], what=f"parametric kind '{k}' has no builder", evidence=it["type"])); continue
            else:
                mb = MB()
                if fn(mb, W, D, H, it) is False or not mb.pieces: continue
                ob = mb.build(f"SPEC-{it['id']}", fin)
                p2 = list(pos)
                if k == "flush_disc" and "ray-cast" in a.get("place", "") and TREE is not None:
                    h = TREE.ray_cast(b3([pos[0], 1.2, pos[2]]), Vector((0, 0, 1)), 4.0)
                    if h[0] is not None: p2[1] = h[0].z - 0.002; NOTES.append(f"{it['id']}: placed on the vault soffit at y {p2[1]:.3f} (ray-cast, spec y {pos[1]})")
                place(ob, p2, yaw)
        if ob is None: continue
        for k_, v_ in props.items(): ob[k_] = v_
        coll.objects.link(ob)
        out.append((ob, dict(props=props, atom=dict(id=props["element"], kind="spec", meta=props, provenance=props["provenance"]))))
    return out


# ------------------------------------------------------------------------------------------------ exterior items new to the build
def _ext_props(xid, name, stage, N, storey="site", collide=False, group="fitting"):
    return dict(element=f"SPEC-{xid}", spec_id=xid, spec_kind="exterior", stage_in=stage, seq=0.95 if N > 1 else 0.0,
                category="existing", group=group, storey=storey, label=f"{name} (spec_v1 exterior {xid})", plain_label=name[:80],
                drawing="spec_v1 (signed 1 Nov 2026)", conf="measured from photos", provenance="photo", collide=collide)


def build_exterior(spec, vkey, N, coll, fin, objs, log):
    """the spec's exterior items that the model did not have: chimney pots + cowl (GF-7), aerial, the rear loft rooflight
    (assumed), No.21's porch as seen (GF-7, replacing the old massing porch), the patio. Returns (new objs, names to drop)."""
    X = {it["id"]: it for it in spec["exterior"]["items"] if vkey in it["versions"]}
    out, drop = [], []
    def add(xid, mb, name, **kw):
        ob = mb.build(f"SPEC-{xid}", fin); ob.matrix_world = Matrix.Identity(4)
        pr = _ext_props(xid, name, 1, N, **kw)
        for k, v in pr.items(): ob[k] = v
        coll.objects.link(ob); out.append((ob, dict(props=pr, atom=dict(id=pr["element"], kind="spec", meta=pr, provenance="photo"), spec=True)))
    def B(x, y, z): return (x, -z, y)                       # viewer -> Blender (MB works in Blender coordinates here)
    if "X-CHIMNEY-POTS" in X:
        it = X["X-CHIMNEY-POTS"]; y0 = it["box_min"][1]; zc = (it["box_min"][2] + it["box_max"][2]) / 2
        mb = MB(); tc, cw = "c:#A9533A:0.8:0", "c:#2B2B2B:0.6:0.2"
        px, pz = it["box_max"][0] - 0.25, zc                 # centre-right of the stack
        mb.cyl(px, -pz, y0, y0 + 0.40, 0.13, tc, 20, r1=0.105); mb.cyl(px, -pz, y0 + 0.40, y0 + 0.43, 0.11, tc, 20)
        mb.cyl(px, -pz, y0 + 0.43, y0 + 0.47, 0.03, cw, 10); mb.cyl(px, -pz, y0 + 0.47, y0 + 0.50, 0.15, cw, 20, r1=0.1)
        qx = it["box_min"][0] + 0.25                         # the lower pot, partly hidden (assumed)
        mb.cyl(qx, -pz, y0, y0 + 0.22, 0.12, tc, 20, r1=0.1)
        add("X-CHIMNEY-POTS", mb, "chimney pots: terracotta pot with a dark cowl, and a lower pot (assumed)", storey="roof")
    if "X-AERIAL" in X:
        it = X["X-AERIAL"]; (x0, y0, z0), (x1, y1, z1) = it["box_min"], it["box_max"]; al = "c:#B9BCBF:0.35:0.9"
        mb = MB(); zc = (z0 + z1) / 2
        mb.cyl(x0 + 0.03, -zc, y0, y1, 0.019, al, 10)                               # mast
        mb.box(x0 + 0.03, x1, -zc - 0.012, -zc + 0.012, y1 - 0.12, y1 - 0.096, al)    # boom
        for k in range(9):
            x = x0 + 0.12 + k * (x1 - x0 - 0.15) / 8; h = 0.24 - 0.012 * k
            mb.box(x - 0.004, x + 0.004, -zc - h / 2, -zc + h / 2, y1 - 0.112, y1 - 0.104, al)
        add("X-AERIAL", mb, "TV aerial (Yagi) on a mast clamped to the chimney stack", storey="roof")
    if "X-LOFT-RL-REAR" in X:
        it = X["X-LOFT-RL-REAR"]; (x0, y0, z0), (x1, y1, z1) = it["box_min"], it["box_max"]
        # on the rear slope: low edge at (y0, z0), high edge at (y1, z1); a 60 mm frame proud of the tiles
        a, b = Vector(B(x0, y0, z0)), Vector(B(x0, y1, z1)); up = (b - a).normalized(); n = Vector((0, 0, 1)) - up * up.z; n.normalize()
        V = []
        for (x, P) in ((x0, a), (x1, a), (x1, b), (x0, b)):
            V.append(tuple(Vector((x, P.y, P.z)))); 
        V2 = [tuple(Vector(v) + n * 0.06) for v in V]
        F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        mb = MB(); mb.pieces.append((V + V2, F, "c:#383E42:0.4:0.1", 0.0))
        V3 = [tuple(Vector(v) + n * 0.061 + Vector((0.06 if i in (0, 3) else -0.06, 0, 0)) + up * (0.06 if i in (0, 1) else -0.06)) for i, v in enumerate(V)]
        V4 = [tuple(Vector(v) + n * 0.004) for v in V3]
        mb.pieces.append((V3 + V4, F, "GLASS-CLEAR", 0.0))
        add("X-LOFT-RL-REAR", mb, "loft rooflight, rear slope (assumed: as the front one, mirrored)", storey="roof")
    if "X-NO21-PORCH" in X:
        it = X["X-NO21-PORCH"]; (x0, yb, z0), (x1, yt, z1) = it["box_min"], it["box_max"]
        g = -0.25; pl_ = g + 0.60; wh, gr, br = "RAL9016", "c:#4B4B4D:0.8:0", "c:#A67B67:0.85:0"
        mb = MB(); f = 0.07
        # brick plinth on three sides (front z1, sides x0/x1), door gap in the front middle
        dw = 0.86; dx0, dx1 = (x0 + x1) / 2 - dw / 2, (x0 + x1) / 2 + dw / 2
        for (a0, a1) in ((x0, dx0), (dx1, x1)): mb.box(a0, a1, -z1, -(z1 - 0.10), g, pl_, br)
        for xs in ((x0, x0 + 0.10), (x1 - 0.10, x1)): mb.box(xs[0], xs[1], -(z1 - 0.10), -z0 - 0.002, g, pl_, br)
        top = 2.10
        # white uPVC frames: corner posts, door posts, transom; side lights above the plinth (glass)
        for xp in (x0, dx0 - f, dx1, x1 - f): mb.box(xp, xp + f, -z1, -(z1 - f), pl_ if xp in (x0, x1 - f) else g, top, wh)
        for zp in (z1 - f, z0 + 0.01): mb.box(x0, x0 + f, -(zp + f), -zp, pl_, top, wh); mb.box(x1 - f, x1, -(zp + f), -zp, pl_, top, wh)
        mb.box(x0, x1, -z1, -(z1 - f), top - f, top, wh)
        for (a0, a1) in ((x0 + f, dx0 - f), (dx1 + f, x1 - f)): mb.box(a0, a1, -(z1 - 0.04), -(z1 - 0.03), pl_, top - f, "GLASS-CLEAR")
        for xs in (x0 + 0.03, x1 - 0.04): mb.box(xs, xs + 0.01, -(z1 - f), -(z0 + f), pl_, top - f, "GLASS-CLEAR")
        mb.box(x0 + f, x1 - f, -z1, -(z1 - f), pl_ - 0.02, pl_, wh)
        # the door: white with two narrow glazed panels
        mb.box(dx0, dx1, -(z1 - 0.02), -(z1 - 0.06), g + 0.02, top - f, wh)
        for k in (0, 1):
            gx = dx0 + 0.22 + k * 0.30; mb.box(gx, gx + 0.12, -(z1 - 0.015), -(z1 - 0.019), g + 0.9, top - f - 0.15, "GLASS-CLEAR")
        # dark grey tiled lean-to hood with hipped ends, from the wall down to the front
        hz0, hz1 = top + 0.02, yt
        V = [(x0 - 0.05, -z0, hz1), (x1 + 0.05, -z0, hz1), (x1 + 0.05, -(z1 + 0.08), hz0), (x0 - 0.05, -(z1 + 0.08), hz0)]
        V2 = [(v[0], v[1], v[2] + 0.04) for v in V]
        mb.pieces.append((V + V2, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], gr, 0.0))
        add("X-NO21-PORCH", mb, "No.21 porch as seen: white uPVC on a brick plinth, side lights, glazed white door, dark grey tiled hood", collide=True)
        drop += [n for n in ("N21-porch-", "no21porch")]
    for xid, col in (("X-PATIO-AFTER", "c:#BDB4A6:0.6:0"), ("X-PATIO-BEFORE", "c:#A9A39A:0.8:0")):
        if xid in X:
            it = X[xid]; (x0, y0, z0), (x1, y1, z1) = it["box_min"], it["box_max"]
            mb = MB(); mb.box(x0, x1, -z1, -z0, y0, y1, col)
            add(xid, mb, it["name"][:80], collide=True)
    return out, drop
