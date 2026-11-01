"""Clash checks over EVERY model object (WORKFLOW G6, matched-view audit; CORRECTIONS-LOG 60, 64-).

    from clash_check import solid_clashes, ground_clashes      (inside Blender, after the build)
    or: house_audit_render.py ... --passes clash   (prints both reports and writes <out>/clash.json)

solid_clashes:  parts that pass THROUGH each other (posts through beams, rafters through fascias, beams through walls):
                triangle-level test (BVH overlap) where both triangles cross each other's plane by more than `tol`, so
                parts that merely touch (a post standing on paving, a beam sitting on a post) are not reported.
                Vegetation and flat ground surfaces are left out; ALLOW lists the intended embeds (a sill set into a
                wall, a fixture screwed to it) with the reason.
ground_clashes: a 1 cm plan raster of everything lying on the ground (surfaces, setts, kerbs, upstands, steps):
                - surface over surface (two ground surfaces covering the same spot: z-fighting or one poking through),
                - surface over unit (soil, lawn or gravel lying on top of an edging sett or paving block: Jack's
                  "soil overlaps the block"),
                - unit over unit (setts laid through each other: incoherent edging, Jack's note 9).
must_touch:     (audit-4, CORRECTIONS-LOG 106) the opposite check: elements that ABUT another (a shed against the house wall, a
                porch wall against the house, a fence against the shed) must actually touch it: the smallest distance
                between the two meshes must be <= tol. A gap there is a hole in Unreal and in the headset (Jack's
                "shed doesn't meet house"). The rules are the site's own (the build script's MUST_TOUCH list).
Site-agnostic: names are classified by the build's prefixes, passed in."""
import bpy, itertools
import numpy as np
from mathutils.bvhtree import BVHTree
from mathutils import Vector

VEG = ("Plant", "Apple_tree", "Far_tree", "B_street_hedge", "B_shrub", "Hedge", "Opp_")
# intended embeds: (name fragment A, name fragment B, why). Matched in either order.
ALLOW = [
    ("_jamb", "H_", "stone jambs are set into the brick reveal"), ("_head", "H_", "lintels bear on the brick"),
    ("_sill", "H_", "sills are built into the wall"), ("_soldier", "H_", "soldier course is part of the wall face"),
    ("_frame", "H_", "frames sit in the reveal"), ("_room", "", "interior card behind the glass"),
    ("H_meter", "H_LW", "meter box is recessed into the wall"), ("_bracket", "", "bracket fixed into its support"),
    ("_mount", "", "camera mount fixed to the wall"), ("_flashing", "", "lead is dressed into the joints"),
    ("P_apron", "", "lead apron tucked into the wall"), ("H_waste_pipe", "H_LW", "pipe comes out of the wall"),
    ("R_chimney", "R_main", "the stack passes through the roof (flashed)"), ("R_aerial", "R_chimney", "aerial bracket"),
    ("R_pot", "R_chimney", "pot bedded in the flaunching"), ("R_chimney_flaunch", "R_chimney", "flaunching on the cap"),
    ("_dish_mast", "H_dish", "mast carries the dish"), ("_dish_arm", "H_dish", "LNB arm"), ("_dish_lnb", "", "LNB on its arm"),
    ("_cctv", "", "camera parts"), ("P_door_lintel", "P_side", "lintel bears on the wall"), ("P_door_threshold", "", "threshold under the door"),
    ("Perg_post", "G2_", "posts are set into the ground through the bed"), ("Bin_", "Bin_", "parts of one bin"),
    ("Bench_", "Bench_", "joints of the bench"), ("_wheel", "", "wheels on their axle"),
    ("N_win", "N_", "neighbour window parts in their reveal"), ("N_porch", "N_porch", "parts of one porch frame"),
    ("_mirror", "P_front", "mirror fixed to the wall"), ("_mirror", "_mirror", "mirror frame parts"),
    ("_dp_", "", "downpipe brackets"), ("_downpipe", "", "downpipe into its gutter / shoe"), ("_gutter", "", "gutter on its fascia"),
    ("Shed_", "Shed_", "parts of the shed carcass"), ("Perg_", "Perg_", "halved / notched timber joints"),
    ("H_panel", "H_RW", "panel fixed to the wall"), ("_light", "", "lights fixed to the wall"), ("H_alarm", "", "alarm box parts"),
    ("H_flood", "", "floodlight parts"), ("H_meter_split", "H_meter", "the split line is a groove in the box"),
    ("H_waste_pipe", "H_waste_pipe", "pipe legs joined at the bend"), ("P_eaves_fascia", "P_roof", "the tile edge bears on the fascia top"),
    ("R_pot", "R_pot_cowl", "cowl fitted on the pot"), ("_valley", "_ridge", "valley lead dressed under the ridge tiles"), ("_valley", "_hip", "valley lead under the hip tiles"), ("P_downlight", "P_eaves_soffit", "downlights are recessed into the soffit"), ("R_aerial", "R_aerial", "aerial elements on their boom"),
    ("_glass", "_mull", "glass runs into the mullion"), ("_glass", "_frame", "glass sits in its frame"), ("_glass", "_sash", "glass in its sash"),
    ("R_main", "R_right", "roof planes meeting at a hip"), ("R_main", "R_wing", "roof planes meeting at a valley"), ("R_wing", "R_wing", "wing roof planes at hips"),
    ("R_right", "R_wing", "roof planes meeting"), ("R_main_back", "R_main_front", "ridge"), ("N_roof", "N_roof", "neighbour roof planes"),
    ("N_roof", "R_main", "the two roofs meet over the party wall"), ("_hip", "R_", "hip tiles bedded on the roof"), ("_hip", "N_roof", "hip tiles bedded on the roof"), ("_hip", "_hip", "hips meet at the apex"),
    ("_ridge", "R_main", "ridge tiles bedded on the roof"), ("_ridge", "R_right", "ridge tiles"), ("_ridge", "R_wing", "ridge tiles"), ("_ridge", "N_roof", "ridge tiles"),
    ("_ridge", "_hip", "ridge meets the hips"), ("R_rooflight", "R_main", "roof window set into the slope"), ("P_rooflight", "P_roof", "roof window set into the slope"),
    ("P_roof", "H_", "lean-to roof tucked under the flashing into the wall"), ("P_roof", "P_side", "roof bears on the side wall"), ("P_roof", "P_front", "roof bears on the wall plate"),
    ("_soffit", "H_LW", "soffit fixed to the wall head"), ("_soffit", "H_RW", "soffit fixed to the wall head"), ("_soffit", "H_side", "soffit on the wall head"),
    ("_soffit", "H_back", "soffit on the wall head"), ("_soffit", "H_wall", "soffit on the wall head"), ("_soffit", "N_front", "soffit on the wall head"),
    ("_soffit", "N_wing", "soffit on the wall head"), ("_soffit", "N_far", "soffit on the wall head"), ("_soffit", "N_back", "soffit on the wall head"),
    ("P_eaves_soffit", "P_front", "soffit on the wall head"),
    ("_fascia", "_soffit", "fascia and soffit joint"), ("_fascia", "_fascia", "mitred corner"), ("N_porch_roof", "N_front", "lean-to into the wall"),
    ("N_porch_cheek", "", "porch cheek"), ("N_porch_plinth", "", "plinth under the frame"), ("N_door", "N_porch", "door in its frame"),
    ("H_RW", "H_RW", "wall pieces bonded"), ("H_LW", "H_LW", "wall pieces bonded"), ("N_front", "N_front", "wall pieces"), ("N_wing", "N_wing", "wall pieces"),
    ("P_side", "P_side", "wall pieces bonded"), ("R_chimney", "R_chimney", "stack parts"),
    ("B_fence", "B_fence", "fence parts (boards on posts, cap on posts)"), ("Perg_post", "Perg_beam", "beam sits on the post (bolted)"),
    ("Perg_beam", "Perg_rafter", "rafters notched over the beam"), ("Apple", "", "tree"),
    ("_upvc_sill", "_sill", "uPVC sill on the stone sill"), ("_upvc_sill", "_frame", "sill board under the frame"), ("_sash", "_frame", "sash in its frame"),
    ("_sash", "_mull", "sash against the mullion"), ("_net", "", "net curtain inside"), ("H_dish", "H_LW", "dish bracket on the wall"), ("Broom", "", "the broom leans on the shed"), ("P_letter", "P_door", "letter plate set in the leaf"),
    ("P_door_", "P_door", "door leaf parts"),
    ("P_barge", "P_barge", "the bargeboard and its box end are one boxed verge"), ("Shed_wall_flashing", "", "felt dressed onto the roof and the wall"),
    ("_lead", "_head", "lead strip dressed over the concrete head"), ("_lead", "_soldier", "lead strip tucked under the soldier course"),
    ("_lead", "H_LW", "lead flashing tucked into the wall"),
]

def _world_mesh(o, dg):
    """world-space verts, triangles, edges, and whether the evaluated mesh is closed (every edge has 2 faces)"""
    oe = o.evaluated_get(dg)
    try: me = oe.to_mesh()
    except RuntimeError: return None
    if me is None or not len(me.polygons): oe.to_mesh_clear(); return None
    me.calc_loop_triangles()
    mw = o.matrix_world
    V = [mw @ v.co for v in me.vertices]
    T = [tuple(t.vertices) for t in me.loop_triangles]
    E = [tuple(e.vertices) for e in me.edges]
    cnt = {}
    for p in me.polygons:
        for k in p.edge_keys: cnt[k] = cnt.get(k, 0) + 1
    closed = all(c == 2 for c in cnt.values())
    oe.to_mesh_clear()
    return V, T, E, closed

def _bbox(V):
    P = np.array([tuple(v) for v in V]); return P.min(0), P.max(0)

def _allowed(a, b):
    for fa, fb, why in ALLOW:
        if (fa in a and fb in b) or (fa in b and fb in a): return why
    return None

def is_flat_ground(o):
    if o.type != "MESH": return False
    bb = [o.matrix_world @ Vector(c) for c in o.bound_box]; zs = [p.z for p in bb]
    return max(zs) - min(zs) < 0.006 and max(zs) < 0.1

def _edge_samples(V, E, lo, hi, step=0.02, cap=6000):
    """points along the edges of A that lie inside the overlap box of A and B"""
    pts = []
    for a, b in E:
        pa, pb = V[a], V[b]; L = (pb - pa).length
        n = max(1, int(L / step))
        for k in range(n + 1):
            p = pa.lerp(pb, k / n)
            if lo[0] <= p.x <= hi[0] and lo[1] <= p.y <= hi[1] and lo[2] <= p.z <= hi[2]: pts.append(p)
        if len(pts) > cap: break
    return pts

def _depth_inside(pts, tree):
    """deepest of pts inside the closed mesh of tree (outward normals): distance to its surface"""
    d = 0.0
    for p in pts:
        loc, nrm, idx, dist = tree.find_nearest(p)
        if loc is not None and (p - loc).dot(nrm) < -1e-5 and dist > d: d = dist
    return d

def solid_clashes(objs, tol=0.004, report_allowed=False):
    """pairs whose parts pass into each other by more than tol: points along the edges of one that lie inside the
    other's closed volume (touching faces are not inside; a post through a fascia is)"""
    dg = bpy.context.evaluated_depsgraph_get()
    cand = [o for o in objs if o.type == "MESH" and not o.name.startswith(VEG) and not is_flat_ground(o) and not o.hide_render]
    data = {}
    for o in cand:
        r = _world_mesh(o, dg)
        if r: data[o.name] = (*r, *_bbox(r[0]))
    names = sorted(data); lo = np.array([data[n][4] for n in names]); hi = np.array([data[n][5] for n in names])
    hits = []; trees = {}
    def tree(n):
        if n not in trees: trees[n] = BVHTree.FromPolygons(data[n][0], data[n][1], epsilon=0.0)
        return trees[n]
    for i in range(len(names)):
        ov = np.all((np.minimum(hi[i], hi[i + 1:]) - np.maximum(lo[i], lo[i + 1:])) > tol, axis=1)
        for j in np.nonzero(ov)[0] + i + 1:
            a, b = names[i], names[j]
            why = _allowed(a, b)
            if why and not report_allowed: continue
            if not tree(a).overlap(tree(b)): continue
            blo = np.maximum(lo[i], lo[j]) - 0.001; bhi = np.minimum(hi[i], hi[j]) + 0.001
            depth = 0.0
            if data[b][3]: depth = max(depth, _depth_inside(_edge_samples(data[a][0], data[a][2], blo, bhi), tree(b)))
            if data[a][3]: depth = max(depth, _depth_inside(_edge_samples(data[b][0], data[b][2], blo, bhi), tree(a)))
            if data[a][3] and data[b][3]:                           # coplanar duplicates (z-fighting boxes): no edge goes INSIDE,
                cc = Vector(tuple((blo + bhi) / 2))                   # but the middle of their common volume is inside both
                da = _depth_inside([cc], tree(a)); db = _depth_inside([cc], tree(b))
                if da > 0.001 and db > 0.001: depth = max(depth, float(min(bhi - blo)) - 0.002)
            if depth > tol:
                c = (blo + bhi) / 2
                hits.append({"a": a, "b": b, "depth_m": round(depth, 4), "at": [round(float(v), 2) for v in c], "allowed": why})
    hits.sort(key=lambda h: -h["depth_m"])
    return hits

def ground_clashes(objs, region=(-6.0, 8.0, -19.0, 3.4), res=0.01, underlay=("G2_soil", "G2_far_ground", "G2_nb_", "G2_road", "G2_pavement", "G2_kerb", "G2_lawn_west"),
                   soil=("G2_bed_soil", "G2_bed_strip", "G2_house_bed", "G2_wing_bed", "G2_hedge_soil"), hard=("G2_paving", "G2_gravel"),
                   soil_ok_near=(), soil_ok_r=0.12):
    """plan raster of everything on the ground; returns a list of faults with areas (m2) and a centre.
    audit-4 (Jack's "soil still clips here", CORRECTIONS-LOG 107): also 'soil past its border': a bed's soil showing
    (no edging unit over it) right beside paving or gravel, i.e. the soil runs out past the edging that should hold it"""
    x0, x1, y0, y1 = region; W = int((x1 - x0) / res); H = int((y1 - y0) / res)
    dg = bpy.context.evaluated_depsgraph_get()
    surf_id = np.full((H, W), -1, np.int32); surf_z = np.full((H, W), -9.0, np.float32)
    unit_cnt = np.zeros((H, W), np.uint8); unit_z = np.full((H, W), -9.0, np.float32); unit_id = np.full((H, W), -1, np.int32)
    names = []; faults = {}
    def add(kind, a, b, mask):
        k = (kind, a, b); n = int(mask.sum())
        if not n: return
        ys, xs = np.nonzero(mask)
        f = faults.setdefault(k, [0, 0.0, 0.0]); f[0] += n; f[1] += float(xs.sum()); f[2] += float(ys.sum())
    def raster_poly(P):
        """cells inside polygon P (Nx2, plan metres) -> (rows slice, cols slice, mask)"""
        c0 = max(0, int((P[:, 0].min() - x0) / res)); c1 = min(W, int((P[:, 0].max() - x0) / res) + 1)
        r0 = max(0, int((P[:, 1].min() - y0) / res)); r1 = min(H, int((P[:, 1].max() - y0) / res) + 1)
        if c1 <= c0 or r1 <= r0: return None
        X = x0 + (np.arange(c0, c1) + 0.5) * res; Y = y0 + (np.arange(r0, r1) + 0.5) * res
        XX, YY = np.meshgrid(X, Y); inside = np.zeros(XX.shape, bool)
        n = len(P)
        for k in range(n):
            (xa, ya), (xb, yb) = P[k], P[(k + 1) % n]
            if ya == yb: continue
            cond = (ya > YY) != (yb > YY)
            xi = xa + (YY - ya) * (xb - xa) / (yb - ya)
            inside ^= cond & (XX < xi)
        return slice(r0, r1), slice(c0, c1), inside
    for o in sorted(objs, key=lambda o: o.name):
        if o.type != "MESH" or o.hide_render or o.name.startswith(VEG) or o.name.startswith(underlay): continue
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]; zs = [p.z for p in bb]
        flat_ = max(zs) - min(zs) < 0.006
        if max(zs) > 0.30 or (flat_ and min(zs) > 0.06) or (not flat_ and min(zs) > -0.005): continue   # surfaces, and units bedded IN the ground (things standing on it are solids)
        oe = o.evaluated_get(dg); me = oe.to_mesh(); mw = o.matrix_world
        oid = len(names); names.append(o.name)
        flat = max(zs) - min(zs) < 0.006
        if flat:
            # one outline per connected flat region: rasterise the triangles (handles holes and concave shapes)
            me.calc_loop_triangles(); cov = None
            V = np.array([tuple(mw @ v.co) for v in me.vertices])
            m = np.zeros((H, W), bool)
            for t in me.loop_triangles:
                r = raster_poly(V[list(t.vertices), :2])
                if r: m[r[0], r[1]] |= r[2]
            z = float(V[:, 2].mean())
            prev = surf_id[m]
            for p in np.unique(prev[prev >= 0]):
                add("surface over surface", names[p], o.name, m & (surf_id == p))
            under = m & (unit_cnt > 0) & (unit_z < z + 0.002)
            for p in np.unique(unit_id[under]):
                add("surface over unit", o.name, names[p], under & (unit_id == p))
            upd = m & (z > surf_z); surf_id[upd] = oid; surf_z[m] = np.maximum(surf_z[m], z)
        else:
            mine = np.zeros((H, W), np.uint8); top = np.full((H, W), -9.0, np.float32)
            for p in me.polygons:
                n = mw.to_3x3() @ p.normal
                if n.z < 0.7: continue
                P = np.array([tuple(mw @ me.vertices[k].co) for k in p.vertices])
                if P[:, 2].mean() < -0.01: continue
                r = raster_poly(P[:, :2])
                if not r: continue
                rs, cs, ins = r
                mine[rs, cs] += ins.astype(np.uint8); top[rs, cs] = np.where(ins, np.maximum(top[rs, cs], P[:, 2].mean()), top[rs, cs])
            # a unit object's own top faces should not overlap each other (bevel strips of one block do not: they tile)
            m = mine > 0
            covered = m & (surf_z > top + 0.002) & (surf_id >= 0)
            for p in np.unique(surf_id[covered]):
                add("surface over unit", names[p], o.name, covered & (surf_id == p))
            uu = m & (unit_cnt > 0) & (np.abs(unit_z - top) < 0.15)
            for p in np.unique(unit_id[uu]):
                add("unit over unit", names[p], o.name, uu & (unit_id == p))
            unit_cnt[m] = np.minimum(unit_cnt[m] + 1, 250); unit_z[m] = np.maximum(unit_z[m], top[m]); unit_id[m] = oid
        oe.to_mesh_clear()
    spots = {}
    # soil past its border: visible soil cells (top surface is a soil, no unit over it) 4-adjacent to visible paving/gravel
    vis = np.where(unit_cnt > 0, -2, surf_id)
    is_soil = np.zeros(len(names) + 1, bool); is_hard = np.zeros(len(names) + 1, bool)
    for i, n in enumerate(names): is_soil[i] = n.startswith(soil); is_hard[i] = n.startswith(hard)
    S_ = (vis >= 0) & is_soil[np.clip(vis, 0, None)]; Hd = (vis >= 0) & is_hard[np.clip(vis, 0, None)]
    nb = np.zeros_like(Hd); nb[1:] |= Hd[:-1]; nb[:-1] |= Hd[1:]; nb[:, 1:] |= Hd[:, :-1]; nb[:, :-1] |= Hd[:, 1:]
    edge = S_ & nb
    for (px_, py_) in soil_ok_near:                                    # intended: soil round a post set in a bed's edge
        c0, c1 = int((px_ - soil_ok_r - x0) / res), int((px_ + soil_ok_r - x0) / res) + 1
        r0, r1 = int((py_ - soil_ok_r - y0) / res), int((py_ + soil_ok_r - y0) / res) + 1
        edge[max(r0, 0):max(r1, 0), max(c0, 0):max(c1, 0)] = False
    # single cells along a curved edge are the 1 cm raster on a 3 mm joint: count only clusters (>= 5 cells in 0.25 m)
    ys_, xs_ = np.nonzero(edge); key = (np.floor((x0 + xs_ * res) * 4)).astype(int) * 100000 + (np.floor((y0 + ys_ * res) * 4)).astype(int)
    u_, inv_, cnt_ = np.unique(key, return_inverse=True, return_counts=True)
    edge[ys_[cnt_[inv_] < 5], xs_[cnt_[inv_] < 5]] = False
    for p in np.unique(vis[edge]):
        hard_n = [names[q] for q in np.unique(surf_id[np.roll(edge & (vis == p), 1, 0) | np.roll(edge & (vis == p), -1, 0)]) if q >= 0 and is_hard[q]]
        add("soil past its border", names[p], hard_n[0] if hard_n else "paving/gravel", edge & (vis == p))
        ys, xs = np.nonzero(edge & (vis == p)); g = {}
        for xx, yy in zip(x0 + xs * res, y0 + ys * res): k = (round(xx * 4) / 4, round(yy * 4) / 4); g[k] = g.get(k, 0) + 1
        spots.setdefault(names[p], []).extend(sorted(((n, k) for k, n in g.items() if n >= 1), reverse=True)[:8])
    out = []
    for (kind, a, b), (n, sx, sy) in faults.items():
        area = n * res * res
        if area < 0.0004 and kind != "soil past its border": continue  # < 4 cm2: raster noise along shared edges
        out.append({"kind": kind, "a": a, "b": b, "area_m2": round(area, 4),
                    "at": [round(x0 + (sx / n + 0.5) * res, 2), round(y0 + (sy / n + 0.5) * res, 2)]})
        if kind == "soil past its border": out[-1]["spots_0.25m"] = [[k[0], k[1], c] for c, k in spots.get(a, [])]
    out.sort(key=lambda f: -f["area_m2"])
    return out

def self_overlap_units(o, res=0.005):
    """setts within ONE laid run that overlap each other in plan (sharp curves, joins laid twice): returns m2.
    Each sett is a closed island of the mesh; islands' top faces are rasterised and counted."""
    import bmesh
    bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
    bm.faces.ensure_lookup_table()
    tops = []
    seen = set()
    for f in bm.faces:
        if f.index in seen: continue
        stack = [f]; isl = []
        while stack:
            g = stack.pop()
            if g.index in seen: continue
            seen.add(g.index); isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen: stack.append(h)
        P = np.array([tuple(v.co) for g in isl for v in g.verts])
        zt = P[:, 2].max(); top = P[P[:, 2] > zt - 0.004][:, :2]
        if len(top) >= 3: tops.append(top)
    bm.free()
    if not tops: return 0.0
    allp = np.concatenate(tops); x0, y0 = allp.min(0) - 0.01; x1, y1 = allp.max(0) + 0.01
    W = int((x1 - x0) / res) + 1; H = int((y1 - y0) / res) + 1
    cnt = np.zeros((H, W), np.uint8)
    for P in tops:
        # convex hull of the top vertices, rasterised
        c = P.mean(0); ang = np.arctan2(P[:, 1] - c[1], P[:, 0] - c[0]); P = P[np.argsort(ang)]
        c0, c1 = int((P[:, 0].min() - x0) / res), int((P[:, 0].max() - x0) / res) + 1
        r0, r1 = int((P[:, 1].min() - y0) / res), int((P[:, 1].max() - y0) / res) + 1
        X, Y = np.meshgrid(x0 + (np.arange(c0, c1) + 0.5) * res, y0 + (np.arange(r0, r1) + 0.5) * res)
        ins = np.ones(X.shape, bool)
        for k in range(len(P)):
            (xa, ya), (xb, yb) = P[k], P[(k + 1) % len(P)]
            ins &= (xb - xa) * (Y - ya) - (yb - ya) * (X - xa) >= -1e-9
        cnt[r0:r1, c0:c1] += ins.astype(np.uint8)
    return float((cnt > 1).sum() * res * res)


def open_parts(objs):
    """visible parts that are not closed solids (single-sided faces vanish from behind in the headset and in Unreal:
    the porch verge soffit, Jack's notes 6-7). Ground surfaces, glass panes and vegetation are expected to be open."""
    dg = bpy.context.evaluated_depsgraph_get(); out = []
    for o in objs:
        if o.type != "MESH" or o.hide_render or o.name.startswith(VEG) or is_flat_ground(o): continue
        if any(k in o.name for k in ("glass", "_net", "_room", "mirror", "_flashing", "_apron", "_valley", "cheek", "rooflight_glass", "_backing")): continue
        r = _world_mesh(o, dg)
        if r and not r[3]: out.append(o.name)
    return sorted(out)


def must_touch(objs, rules):
    """rules: [(name prefix A, name prefix B, tol m, why)]. For each rule, the smallest distance between any object named A*
    and any named B* (vertices and face centres of A against B's surface, and B's against A's). Returns the failing rules
    (gap > tol, or one side missing) and the measured gaps of all rules."""
    dg = bpy.context.evaluated_depsgraph_get()
    by = {o.name: o for o in objs if o.type == "MESH" and not o.hide_render}
    def pts_tree(prefix):
        P, Tr = [], []
        for n, o in by.items():
            if not n.startswith(prefix): continue
            r = _world_mesh(o, dg)
            if not r: continue
            V, T, _, _ = r
            P += V + [(V[a] + V[b] + V[c]) / 3 for a, b, c in T]
            Tr.append(BVHTree.FromPolygons(V, T, epsilon=0.0))
        return P, Tr
    report, fails = [], []
    for a, b, tol, why in rules:
        Pa, Ta = pts_tree(a); Pb, Tb = pts_tree(b)
        if not Pa or not Pb:
            r = {"a": a, "b": b, "gap_m": None, "why": why, "missing": a if not Pa else b}; report.append(r); fails.append(r); continue
        g = min(min((t.find_nearest(p)[3] for t in Tb for p in Pa), default=9), min((t.find_nearest(p)[3] for t in Ta for p in Pb), default=9))
        r = {"a": a, "b": b, "gap_m": round(g, 4), "tol_m": tol, "why": why}; report.append(r)
        if g > tol: fails.append(r)
    return fails, report
