"""Measured model -> Unreal parts (WORKFLOW G8). Blender side of the native Unreal rebuild (CORRECTIONS-LOG 147): the skeleton
(positions, sizes, levels) is ours; every surface is re-materialled in Unreal from scanned CC0 sets, props and plants swapped
for library models placed at the measured spot. Headless and light (exports only: no renders, no bakes; Jack's 8 GB Mac).

1) From the model build (front-garden-v2.py --ue <out>): calls export(...) after build().
   - merges every visible model part by its Unreal material (site spec "slots"), one FBX per material, true metres;
   - new UVs in metres for scanned materials: planar per face (walls: u along the wall, v up; roofs: v up the slope),
     timber along each piece's long axis (grain), random offset per unit for setts/boards so repeats don't line up;
     the apple tree and our vertex-coloured plants keep their own UVs/colours;
   - plants named in spec "replace" -> placements (library model, base centre, size); hedges -> leaf-ball scatter over
     their surface plus an inset dark core; lawns -> real grass blades (one Nanite mesh, vertex colours);
   - writes <out>/geometry.json (meshes, bounds for the axis check, instances).
2) Library models (blender -b --python tools/unreal/export_ue.py -- --prep-models <lib> <id> ...): each glTF node exported
   as its own FBX with its base centre at the origin (<lib>/polyhaven/models/<id>/ue/<node>.fbx + variants.json)."""
import bpy, bmesh, json, math, os, sys, time, random, fnmatch
import numpy as np
from mathutils import Vector

EXPORT_COLL = "UE_Export"


def _coll(scene):
    c = bpy.data.collections.get(EXPORT_COLL)
    if not c:
        c = bpy.data.collections.new(EXPORT_COLL); scene.collection.children.link(c)
    return c


def _fbx(obj, path, scene):
    """export one object alone; Blender metres -> FBX with unit scale, Unreal converts axes (checked by bounds in UE)"""
    vl = scene.view_layers[0]
    for o in scene.objects: o.select_set(False, view_layer=vl)
    obj.select_set(True, view_layer=vl); vl.objects.active = obj
    with bpy.context.temp_override(scene=scene, view_layer=vl, active_object=obj, selected_objects=[obj]):
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"}, apply_unit_scale=True, global_scale=1.0,
                                 apply_scale_options="FBX_SCALE_NONE", mesh_smooth_type="FACE", use_mesh_modifiers=True,
                                 add_leaf_bones=False, bake_anim=False, colors_type="SRGB", path_mode="STRIP", axis_forward="-Z", axis_up="Y")


def _tb(n):
    """planar frame per face: t along the surface horizontally, b up the surface (true metres)"""
    z = np.array([0.0, 0.0, 1.0])
    t = np.cross(z, n)                                         # walls: along the wall; roofs: along the eaves
    flat = np.linalg.norm(t, axis=1) < 0.3                     # floors (and near-floors): plan x/y
    t[flat] = np.where(n[flat, 2:3] >= 0, [1.0, 0, 0], [-1.0, 0, 0])
    t /= np.linalg.norm(t, axis=1)[:, None]
    b = np.cross(n, t)
    return t, b


class Bucket:
    def __init__(self, mi, mode, colours):
        self.mi, self.mode, self.colours = mi, mode, colours
        self.V, self.L, self.S, self.UV, self.C = [], [], [], [], []
        self.nv = self.nl = 0; self.bmin = np.full(3, 1e9); self.bmax = np.full(3, -1e9)

    def add(self, V, loops, starts, uv, col):
        self.V.append(V); self.L.append(loops + self.nv); self.S.append(starts + self.nl); self.UV.append(uv)
        if self.colours: self.C.append(col if col is not None else np.ones((len(loops), 4), np.float32))
        self.nv += len(V); self.nl += len(loops)
        self.bmin = np.minimum(self.bmin, V.min(0)); self.bmax = np.maximum(self.bmax, V.max(0))

    def mesh(self, name):
        V = np.concatenate(self.V); L = np.concatenate(self.L); S = np.concatenate(self.S); UV = np.concatenate(self.UV)
        used, inv = np.unique(L, return_inverse=True); V = V[used]; L = inv.astype(np.int32)
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(V)); me.vertices.foreach_set("co", V.astype(np.float32).ravel())
        me.loops.add(len(L)); me.loops.foreach_set("vertex_index", L)
        me.polygons.add(len(S)); me.polygons.foreach_set("loop_start", S.astype(np.int32))
        me.update(calc_edges=True)
        me.uv_layers.new(name="UVMap").data.foreach_set("uv", UV.astype(np.float32).ravel())
        if self.colours:
            ca = me.color_attributes.new("Col", "BYTE_COLOR", "CORNER"); ca.data.foreach_set("color", np.concatenate(self.C).astype(np.float32).ravel())
        smooth = self.mode in ("model", "vc")
        me.polygons.foreach_set("use_smooth", np.full(len(S), smooth))
        me.validate(clean_customdata=False)
        return me


def _islands(me):
    """connected-component id per polygon (units in a laid run: setts, boards)"""
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    lab = np.full(len(bm.faces), -1); k = 0
    for f in bm.faces:
        if lab[f.index] >= 0: continue
        stack = [f]; lab[f.index] = k
        while stack:
            g = stack.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if lab[h.index] < 0: lab[h.index] = k; stack.append(h)
        k += 1
    bm.free(); return lab


def object_arrays(o, dg):
    eo = o.evaluated_get(dg); me = eo.to_mesh()
    n = len(me.vertices); nl = len(me.loops); npoly = len(me.polygons)
    if not npoly: eo.to_mesh_clear(); return None
    co = np.empty(n * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(n, 3)
    M = np.array(o.matrix_world); V = co @ M[:3, :3].T + M[:3, 3]
    loops = np.empty(nl, np.int32); me.loops.foreach_get("vertex_index", loops)
    starts = np.empty(npoly, np.int32); me.polygons.foreach_get("loop_start", starts)
    tot = np.empty(npoly, np.int32); me.polygons.foreach_get("loop_total", tot)
    mat = np.empty(npoly, np.int32); me.polygons.foreach_get("material_index", mat)
    pn = np.empty(npoly * 3, np.float32); me.polygons.foreach_get("normal", pn)
    Nm = np.linalg.inv(M[:3, :3]).T; pn = pn.reshape(npoly, 3) @ Nm.T; pn /= np.maximum(np.linalg.norm(pn, axis=1), 1e-9)[:, None]
    uv = None
    if me.uv_layers.active:
        uv = np.empty(nl * 2, np.float32); me.uv_layers.active.data.foreach_get("uv", uv); uv = uv.reshape(nl, 2)
    col = None
    ca = me.color_attributes.active_color if hasattr(me.color_attributes, "active_color") else None
    if ca is not None:
        c = np.empty(len(ca.data) * 4, np.float32); ca.data.foreach_get("color", c); c = c.reshape(-1, 4)
        col = c[loops] if ca.domain == "POINT" else c
    lab = _islands(me) if o.get("_ue_islands") else None
    mats = [m.name if m else "" for m in o.data.materials] or [""]
    eo.to_mesh_clear()
    return dict(V=V, loops=loops, starts=starts, tot=tot, mat=mat, pn=pn, uv=uv, col=col, lab=lab, mats=mats)


def compute_uv(A, sel, mode, long_axis=None, rand=False, seed=0):
    """per-loop UVs (metres) for the polygons in sel"""
    starts, tot = A["starts"][sel], A["tot"][sel]
    lp = np.concatenate([np.arange(s, s + t) for s, t in zip(starts, tot)]) if len(sel) else np.zeros(0, int)
    pid = np.repeat(np.arange(len(sel)), tot)
    n = A["pn"][sel]
    if mode == "model" and A["uv"] is not None: return lp, A["uv"][lp]
    t, b = _tb(n)
    if mode == "grain" and long_axis is not None:
        L = np.asarray(long_axis, float)
        Lp = L[None, :] - (n @ L)[:, None] * n
        ok = np.linalg.norm(Lp, axis=1) > 0.35
        t[ok] = Lp[ok] / np.linalg.norm(Lp[ok], axis=1)[:, None]; b[ok] = np.cross(n[ok], t[ok])
    P = A["V"][A["loops"][lp]]
    uv = np.stack([(P * t[pid]).sum(1), (P * b[pid]).sum(1)], 1)
    if rand:
        rng = np.random.default_rng(seed)
        lab = A["lab"][sel] if A["lab"] is not None else np.zeros(len(sel), int)
        off = rng.uniform(0, 7.0, (lab.max() + 1, 2)); uv = uv + off[lab][pid]
    return lp, uv


def export(model_coll, scene, out, spec, cams_src=None):
    t0 = time.time(); os.makedirs(out, exist_ok=True)
    random.seed(7); rng = np.random.default_rng(7)
    slots, mats = spec["slots"], spec["materials"]
    rep = {k: v for k, v in spec.get("replace", {}).items() if k != "note"}
    hedge = spec.get("hedges", {}); lawn = spec.get("lawn", {})
    dg = bpy.context.evaluated_depsgraph_get()
    buckets, instances, missing = {}, [], {}
    lawn_faces = []

    def bucket(mi):
        m = mats.get(mi, {})
        mode = "vc" if m.get("type") == "vcfoliage" else ("model" if m.get("uv") == "model" or m.get("type") == "foliage" else
                                                          ("grain" if m.get("grain") else "planar"))
        if mi not in buckets: buckets[mi] = Bucket(mi, mode, mode == "vc")
        return buckets[mi]

    objs = [o for o in model_coll.objects if o.type == "MESH" and not o.hide_render]
    for o in objs:
        name = o.name
        r = next((v for k, v in rep.items() if fnmatch.fnmatch(name, k)), None)
        if r:                                                    # library model at the measured spot
            bb = np.array([o.matrix_world @ Vector(c) for c in o.bound_box])
            mn, mx = bb.min(0), bb.max(0)
            instances.append({"of": name, "model": r["model"], "mi": r["mi"], "variants": r.get("variants"),
                              "loc": [float((mn[0] + mx[0]) / 2), float((mn[1] + mx[1]) / 2), float(mn[2])],
                              "yaw": float(rng.uniform(0, 360)), "fit": {"h": float(mx[2] - mn[2]), "w": float(((mx[0] - mn[0]) + (mx[1] - mn[1])) / 2)}})
            continue
        rand = any(mats.get(slots.get(m.name if m else "", ""), {}).get("random_offset") for m in o.data.materials)
        if rand: o["_ue_islands"] = 1
        A = object_arrays(o, dg)
        if A is None: continue
        if name in hedge.get("objects", []):                     # leaf balls over the hedge face + an inset dark core
            _hedge(A, hedge, instances, rng); A = _inset(A, hedge.get("core_inset_m", 0.12))
            mi_over = "MI_HedgeCore"
        else:
            mi_over = None
        if name in lawn.get("objects", []): lawn_faces.append(A)
        for bf in spec.get("bed_fill", []):                      # under-planting: no bare soil between the measured plants
            if name in bf["objects"]:
                a_, b_, c_, area, nrm, n = _surface_samples(A, 1.0 / math.sqrt(bf["per_m2"]), rng, upward_only=True)
                if n:
                    idx = rng.choice(len(area), n, p=area / area.sum()); r1, r2 = rng.random(n), rng.random(n); sq = np.sqrt(r1)
                    P = a_[idx] * (1 - sq)[:, None] + b_[idx] * (sq * (1 - r2))[:, None] + c_[idx] * (sq * r2)[:, None]
                    for q in P:
                        instances.append({"of": "bedfill", "model": bf["model"], "mi": bf["mi"], "variants": bf.get("variants"),
                                          "loc": [float(q[0]), float(q[1]), float(q[2])], "yaw": float(rng.uniform(0, 360)), "fit": {"h": float(rng.uniform(*bf["h"]))}})
        long_axis = None
        Vc = A["V"] - A["V"].mean(0)
        if len(Vc) >= 3:
            w, vec = np.linalg.eigh(Vc.T @ Vc); long_axis = vec[:, -1]
        for mi_idx, mname in enumerate(A["mats"]):
            sel = np.nonzero(A["mat"] == mi_idx)[0] if len(A["mats"]) > 1 else np.arange(len(A["starts"]))
            if not len(sel): continue
            mi = mi_over or slots.get(mname)
            if not mi: missing[mname] = missing.get(mname, 0) + 1; continue
            B = bucket(mi)
            lp, uv = compute_uv(A, sel, B.mode, long_axis, mats.get(mi, {}).get("random_offset", False), seed=hash(name) & 0xffff)
            # polygons of this selection as their own loop list
            tot = A["tot"][sel]; starts = np.r_[0, np.cumsum(tot)[:-1]]
            col = A["col"][lp] if (B.colours and A["col"] is not None) else None
            B.add(A["V"], A["loops"][lp], starts, uv, col)
    if lawn_faces and lawn.get("blades_per_m2"):
        _lawn_blades(lawn_faces, lawn, bucket("MI_LawnBlades"), rng)
    # write one FBX per Unreal material
    coll = _coll(scene); meshes = []
    for mi, B in buckets.items():
        if not B.V: continue
        me = B.mesh("SM_" + mi[3:]); mat = bpy.data.materials.get(mi) or bpy.data.materials.new(mi); me.materials.append(mat)
        ob = bpy.data.objects.new("SM_" + mi[3:], me); coll.objects.link(ob)
        path = os.path.join(out, f"SM_{mi[3:]}.fbx"); _fbx(ob, path, scene)
        meshes.append({"fbx": os.path.basename(path), "mi": mi, "verts": len(me.vertices), "polys": len(me.polygons),
                       "bounds": [B.bmin.round(3).tolist(), B.bmax.round(3).tolist()]})
        print(f"  {mi:18s} {len(me.polygons):8d} polys  {os.path.getsize(path) // 1024:7d} KB")
        bpy.data.objects.remove(ob); bpy.data.meshes.remove(me)
    geo = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "units": "metres, Blender plan frame (x, y towards the house, z up)",
           "meshes": meshes, "instances": instances, "unmapped_materials": missing}
    json.dump(geo, open(os.path.join(out, "geometry.json"), "w"), indent=1)
    print(f"UE export: {len(meshes)} meshes, {len(instances)} instances, unmapped {missing}, {time.time() - t0:.0f}s")
    return geo


def _surface_samples(A, spacing, rng, upward_only=False):
    """jittered area-weighted points on the polygons (fan-triangulated), with their face normals"""
    V, loops, starts, tot, pn = A["V"], A["loops"], A["starts"], A["tot"], A["pn"]
    tri, nrm = [], []
    for i, (s, t) in enumerate(zip(starts, tot)):
        if upward_only and pn[i, 2] < 0.7: continue
        for k in range(1, t - 1): tri.append((loops[s], loops[s + k], loops[s + k + 1])); nrm.append(pn[i])
    if not tri: return None, None, None, None, None, 0
    tri = np.array(tri); nrm = np.array(nrm)
    a, b, c = V[tri[:, 0]], V[tri[:, 1]], V[tri[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    n = int(area.sum() / (spacing * spacing)) if spacing > 0 else 0
    return a, b, c, area, nrm, n


def _hedge(A, h, instances, rng):
    a, b, c, area, nrm, n = _surface_samples(A, h.get("spacing_m", 0.28), rng)
    if n == 0: return
    idx = rng.choice(len(area), n, p=area / area.sum())
    r1, r2 = rng.random(n), rng.random(n); s = np.sqrt(r1)
    P = a[idx] * (1 - s)[:, None] + b[idx] * (s * (1 - r2))[:, None] + c[idx] * (s * r2)[:, None]
    ball = h.get("ball_m", 0.42)
    for p, nn in zip(P, nrm[idx]):
        if p[2] < 0.08: continue                                 # not under the ground
        sc = ball * rng.uniform(0.8, 1.2)
        q = p - nn * sc * 0.42                                   # ball sits mostly inside the clipped face
        instances.append({"of": "hedge", "model": h["model"], "mi": h["mi"], "loc": [float(q[0]), float(q[1]), float(q[2] - sc * 0.5)],
                          "yaw": float(rng.uniform(0, 360)), "fit": {"h": float(sc)}})


def _inset(A, d):
    """pull a hedge core in by d along its vertex normals (so the leaf balls form the face)"""
    V = A["V"].copy(); vn = np.zeros_like(V)
    for i, (s, t) in enumerate(zip(A["starts"], A["tot"])):
        vn[A["loops"][s:s + t]] += A["pn"][i]
    vn /= np.maximum(np.linalg.norm(vn, axis=1), 1e-9)[:, None]
    V -= vn * d; V[:, 2] = np.clip(V[:, 2], A["V"][:, 2].min(), A["V"][:, 2].max() - 2.2 * d)   # no core spike above the leaf balls (judges r8)
    B = dict(A); B["V"] = V; return B


def _srgb2lin(c): c = np.asarray(c, float) / 255; return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _lawn_blades(faces, L, B, rng):
    dens = L["blades_per_m2"]; h0, h1 = L["height_m"]; w0, w1 = L["width_m"]; base = _srgb2lin(L.get("colour_srgb", [92, 122, 40]))
    total = 0
    for A in faces:
        a, b, c, area, nrm, n = _surface_samples(A, 1.0 / math.sqrt(dens), rng, upward_only=True)
        if n == 0: continue
        idx = rng.choice(len(area), n, p=area / area.sum())
        r1, r2 = rng.random(n), rng.random(n); s = np.sqrt(r1)
        P = a[idx] * (1 - s)[:, None] + b[idx] * (s * (1 - r2))[:, None] + c[idx] * (s * r2)[:, None]
        ang = rng.uniform(0, 2 * np.pi, n); side = np.stack([np.cos(ang), np.sin(ang), np.zeros(n)], 1)
        lean = rng.uniform(0, 0.45, n); la = rng.uniform(0, 2 * np.pi, n)
        band = None
        if L.get("stripe_m"):                                    # mown stripes: alternate bands lean opposite ways (as a mower leaves them)
            ax = 1 if L.get("stripe_axis", "y") == "y" else 0
            band = (np.floor(P[:, ax] / L["stripe_m"]) % 2).astype(int)
            base_dir = np.pi / 2 if ax == 1 else 0.0
            la = np.where(band == 0, base_dir, base_dir + np.pi) + rng.normal(0, 0.5, n); lean = rng.uniform(0.25, 0.6, n)
        h = rng.uniform(h0, h1, n) * (1 + 0.25 * rng.standard_normal(n)).clip(0.6, 1.6); w = rng.uniform(w0, w1, n)
        tip = P + np.stack([np.cos(la) * lean * h, np.sin(la) * lean * h, h * np.sqrt(1 - lean ** 2)], 1)
        V = np.empty((n * 3, 3)); V[0::3] = P - side * (w / 2)[:, None]; V[1::3] = P + side * (w / 2)[:, None]; V[2::3] = tip
        V[0::3, 2] += 0.002; V[1::3, 2] += 0.002
        loops = np.arange(n * 3, dtype=np.int32); starts = np.arange(0, n * 3, 3, dtype=np.int32)
        # colour: Jack's lawn green with per-blade variation, a few straw/dead blades, darker at the root
        var = rng.normal(1.0, 0.18, (n, 1)).clip(0.6, 1.5) * base[None, :]
        dead = rng.random(n) < 0.06; var[dead] = _srgb2lin([150, 135, 80]) * rng.uniform(0.7, 1.1, (dead.sum(), 1))
        hue = rng.normal(0, 0.08, n); var[:, 0] *= (1 + hue); var[:, 2] *= (1 - hue)
        patch = 1 + 0.12 * np.sin(P[:, 0] * 1.7 + 0.6) * np.sin(P[:, 1] * 1.3)    # soft patchiness over metres
        var *= patch[:, None]
        if band is not None: g_ = L.get("stripe_gain", 0.07); var *= np.where(band == 0, 1 + g_, 1 - g_)[:, None]
        col = np.ones((n * 3, 4), np.float32)
        col[0::3, :3] = var * 0.45; col[1::3, :3] = var * 0.45; col[2::3, :3] = np.minimum(var * L.get("tip", 1.25), 1)
        uv = np.zeros((n * 3, 2), np.float32); uv[2::3, 1] = 1; uv[1::3, 0] = 1
        B.add(V, loops, starts, uv, col); total += n
    print("lawn blades:", total)


# ------------------------------------------------------------------ library models -> one FBX per variant
def prep_models(lib, ids):
    sc = bpy.context.scene
    for aid in ids:
        d = os.path.join(lib, "polyhaven", "models", aid); g = os.path.join(d, f"{aid}.gltf")
        if not os.path.exists(g): print("no glTF for", aid); continue
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=g)
        new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        os.makedirs(os.path.join(d, "ue"), exist_ok=True); variants = {}
        for o in new:
            bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
            o.parent = None
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            bb = np.array([o.matrix_world @ Vector(c) for c in o.bound_box]); mn, mx = bb.min(0), bb.max(0)
            ctr = Vector(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, mn[2]))
            o.data.transform(__import__("mathutils").Matrix.Translation(-ctr)); o.location = (0, 0, 0)
            nm = o.name.replace(aid + "_", "").replace("_LOD0", "").replace(".", "_")
            path = os.path.join(d, "ue", f"{aid}__{nm}.fbx")
            _fbx(o, path, sc)
            variants[nm] = {"fbx": os.path.basename(path), "size_m": (mx - mn).round(4).tolist(), "polys": len(o.data.polygons),
                            "slots": [m.name for m in o.data.materials if m]}
        json.dump(variants, open(os.path.join(d, "ue", "variants.json"), "w"), indent=1)
        for o in new: bpy.data.objects.remove(o)
        print(aid, len(variants), "variants")


if __name__ == "__main__" and "--prep-models" in sys.argv:
    a = sys.argv[sys.argv.index("--prep-models") + 1:]
    prep_models(os.path.expanduser(a[0]), a[1:])
