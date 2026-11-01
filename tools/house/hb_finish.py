"""Finished surfaces (CORRECTIONS-LOG 185, 188; WORKFLOW G5/G6): every surface seen from a finished room gets its finish.

Generic, from the built geometry (no house facts): after a version is built, every face of a construction part (brick,
block, timber, insulation, membrane, lintel, steel, the old deck's underside...) that can be seen from inside a finished
room of the signed spec is covered by a finish skin 1 mm proud of it: plaster + the spec's matt paint on walls and reveals
(FIN-WALL), the ceiling paint on the undersides of floors, joists and ceilings (FIN-CEIL). The skin copies the face
exactly, so reveals and arrises stay crisp. "Seen" = a clear ray from the face to a point inside a room's volume (plan
polygon, floor to ceiling); the conservatory (bare brick by spec) and the outside never count, so outside reveals keep
their brick. Skins are merged per (lifetime, finish) to keep the draw calls down, and live as long as the part they cover
(an existing wall's skin is demolished with it; a new wall's skin goes on at the plastering stage).

Also: ceilings and vault linings (CL-*) take FIN-CEIL; the stair (ST-stair) takes FIN-STAIR (oak treads, white risers and
strings)."""
import math, re
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

RAW = re.compile(r"^(timber|timber_existing|membrane|mineral_wool|pir|block|batten|rebar|dpm|chipboard|prop_steel|lintel_galv|hardcore|"
                 r"existing_brick|brick|concrete|screed|insulation|felt|steel|existing_floor|floor_finish|buff_concrete|cream_stone)(\.\d+)?$", re.I)
DOWN_CEIL_GROUPS = {"deck", "joist", "ceiling_joist", "slab_layer", "floor_finish", "timber_beam", "steel", "wall_plate"}
BARE_ROOMS = re.compile(r"conservatory", re.I)


def _in_poly(x, y, P):
    c = False; n = len(P)
    for i in range(n):
        x1, y1 = P[i]; x2, y2 = P[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-15) + x1: c = not c
    return c


def _ccw2(P):
    a = sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))
    return P if a >= 0 else P[::-1]


def _grow(P, e):
    """offset a convex 2D polygon outward by e (mitred)"""
    P = _ccw2(list(P)); n = len(P); out = []
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        def nrm(p, q):
            dx, dy = q[0] - p[0], q[1] - p[1]; L = math.hypot(dx, dy) or 1e-12; return (dy / L, -dx / L)
        n1, n2 = nrm(a, b), nrm(b, c); bx, by = n1[0] + n2[0], n1[1] + n2[1]; L = math.hypot(bx, by)
        if L < 1e-9: out.append(b); continue
        bx, by = bx / L, by / L; cs = max(0.35, bx * n2[0] + by * n2[1])
        out.append((b[0] + bx * e / cs, b[1] + by * e / cs))
    return out


def _clip_convex(subj, clip):
    """Sutherland-Hodgman: subject polygon clipped by a convex polygon (both 2D); a non-convex clip returns the subject"""
    clip = _ccw2(list(clip)); n = len(clip)
    for i in range(n):
        a, b, c = clip[i], clip[(i + 1) % n], clip[(i + 2) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) < -1e-12: return subj
    out = list(subj)
    for i in range(n):
        a, b = clip[i], clip[(i + 1) % n]
        inside = lambda p: (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-12
        def inter(p, q):
            x1, y1, x2, y2 = p[0], p[1], q[0], q[1]; x3, y3, x4, y4 = a[0], a[1], b[0], b[1]
            den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if abs(den) < 1e-15: return q
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
            return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
        inp, out = out, []
        if not inp: break
        for j in range(len(inp)):
            cur, prv = inp[j], inp[j - 1]
            if inside(cur):
                if not inside(prv): out.append(inter(prv, cur))
                out.append(cur)
            elif inside(prv): out.append(inter(prv, cur))
    return out


def _num(v, default):
    if isinstance(v, (int, float)): return float(v)
    m = re.match(r"\s*([\d.]+)", str(v or ""))
    return float(m.group(1)) if m else default


def rooms_blender(spec_rooms):
    """spec rooms -> [(id, poly in Blender xy, z0, z1, bbox)] (viewer (x, z) -> Blender (x, -z)); sloped / vaulted rooms
    reach up to their roof (the clear-ray test keeps the loft out)"""
    out = []
    for r in spec_rooms:
        if BARE_ROOMS.search(r["id"]): continue
        P = [(x, -z) for (x, z) in r["polygon"]]
        fy = r["floor_y"]; cy = r["ceiling_y"]
        if isinstance(cy, (int, float)):
            top = cy + 0.03
        else:
            top = fy + 3.9                                   # vault / slope: bounded by the roof (clear-ray test)
            if fy > 2.0 and "above FFL" in str(cy): top = fy + 3.0
        xs = [p[0] for p in P]; ys = [p[1] for p in P]
        out.append((r["id"], P, fy - 0.05, top, (min(xs) - 0.6, min(ys) - 0.6, max(xs) + 0.6, max(ys) + 0.6)))
    return out


def _dist_edge(x, z, P):
    best = 9e9
    for i in range(len(P)):
        (x1, z1), (x2, z2) = P[i], P[(i + 1) % len(P)]
        dx, dz = x2 - x1, z2 - z1; L2 = dx * dx + dz * dz or 1e-12
        t = max(0.0, min(1.0, ((x - x1) * dx + (z - z1) * dz) / L2))
        best = min(best, math.hypot(x - x1 - t * dx, z - z1 - t * dz))
    return best


def standing_points(spec_rooms, extra_views=()):
    """the integrity gate's own standing points (check_integrity.py): room grids at 1.0 / 1.6 m, the walk and the cameras"""
    pts = []
    for r in spec_rooms:
        P = r["polygon"]; fy = r["floor_y"]
        xs = [q[0] for q in P]; zs = [q[1] for q in P]
        step = 0.6 if r.get("area_m2", 5) > 3 else 0.35
        x = min(xs) + 0.2
        while x < max(xs):
            z = min(zs) + 0.2
            while z < max(zs):
                if _in_poly(x, z, P) and _dist_edge(x, z, P) > 0.2:
                    for eh in (1.6, 1.0): pts.append((r["id"], Vector((x, -z, fy + eh))))
                z += step
            x += step
    for (_, v) in extra_views:                     # walk and camera points that stand inside a room (never the outside)
        rid = next((r["id"] for r in spec_rooms if _in_poly(v[0], v[2], r["polygon"]) and r["floor_y"] - 0.1 < v[1] < r["floor_y"] + 2.7), None)
        if rid: pts.append((rid, Vector((v[0], -v[2], v[1]))))
    return pts


def apply(objs, spec_rooms, fin, N, log, finish_seq=0.85, views=()):
    """objs: the version's [(ob, p)]; returns new [(ob, p)] skins (already linked to the first object's collections)"""
    rooms = rooms_blender(spec_rooms)
    # the homeowner sees the as-built records in place of the drawn parts they replace (row 191: the drawn wall left in the
    # ray tree hid the as-built window reveals from the room, so their brick stayed bare)
    replaced = set()
    for ob, p in objs:
        ab = (p.get("atom") or {}).get("as_built") if isinstance(p.get("atom"), dict) else None
        if ab: replaced.update(ab.get("replaces", []))
    def live_parts():
        out_ = []
        for ob, p in objs + extra:
            if ob.type != "MESH": continue
            pr = p["props"]
            if (pr.get("stage_out") or 99) <= N or pr.get("element") in replaced: continue
            out_.append((ob, p))
        return out_
    def make_tree(lp):
        V, T, own = [], [], []
        for ob, p in lp:
            M = ob.matrix_world; b = len(V)
            V.extend(M @ v.co for v in ob.data.vertices)
            for pl in ob.data.polygons: T.append(tuple(b + i for i in pl.vertices)); own.append(ob.name)
        return BVHTree.FromPolygons(V, T)
    extra = []
    coll = objs[0][0].users_collection[0]
    def new_obj(name, bm_or_mesh, finish, life, label):
        si, sq, so, sqo = life
        ob = bpy.data.objects.new(name, bm_or_mesh)
        props = dict(element=name, group="finish_skin", stage_in=si, seq=round(sq, 4), stage_out=so, seq_out=sqo,
                     category="finish" if N > 1 and si == N else "existing", storey="ground", label=label,
                     plain_label="Plastered and painted surface", drawing="spec_v1 (signed 1 Nov 2026)", conf="assumed",
                     provenance="typical", collide=False)
        for kk, vv in props.items():
            if vv is not None: ob[kk] = vv
        coll.objects.link(ob)
        return (ob, dict(props=props, spec=True, atom=dict(id=name, kind="skin", meta=props, provenance="typical")))
    def box_mesh(name, x0, y0, z0, x1, y1, z1, mat, tile=(1.5, 1.5)):
        bm = bmesh.new(); uv = bm.loops.layers.uv.new("UVMap")
        vs = [bm.verts.new(v) for v in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            fa = bm.faces.new([vs[i] for i in f])
            for l in fa.loops:
                c = l.vert.co; nn = fa.normal
                l[uv].uv = ((c.x / tile[0], c.y / tile[1]) if abs(nn.z) > 0.7 else ((c.x if abs(nn.y) > abs(nn.x) else c.y) / tile[0], c.z / tile[1]))
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(mat)
        return me

    # ---- 1. steels and timber beams seen from a finished room are boxed in plasterboard, painted (Jack, 1 Nov: "every steel is
    #         boxed"; typical: 12.5 mm board on 15 mm battens, 27.5 mm round the member), meeting the ceiling above
    ceil_of = {}
    for r in spec_rooms:
        if isinstance(r["ceiling_y"], (int, float)): ceil_of[r["id"]] = r["ceiling_y"]
    nbox = 0; boxes = []
    for ob, p in live_parts():
        pr = p["props"]; g = pr.get("group", "")
        if g not in ("steel", "timber_beam") or ob.name.startswith(("SC-", "FS-")): continue
        bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))); hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
        mid = (lo + hi) / 2
        rid = None
        for (rid_, P, z0, z1, bbx) in rooms:
            if bbx[0] <= mid.x <= bbx[2] and bbx[1] <= mid.y <= bbx[3] and _in_poly(mid.x, mid.y, P) and z0 < lo.z < z1 + 0.05: rid = rid_; break
        if rid is None: continue
        cy = ceil_of.get(rid)
        top = min(hi.z, cy) if cy is not None else hi.z
        if lo.z > top - 0.01: continue                  # above the ceiling line: hidden in the floor/roof zone
        e = 0.0275
        merged = False
        for bx_ in boxes:
            if bx_["lo"].x - e <= hi.x + e and lo.x - e <= bx_["hi"].x + e and bx_["lo"].y - e <= hi.y + e and lo.y - e <= bx_["hi"].y + e and abs(bx_["top"] - top) < 0.01:
                bx_["lo"] = Vector((min(bx_["lo"].x, lo.x), min(bx_["lo"].y, lo.y), min(bx_["lo"].z, lo.z)))
                bx_["hi"] = Vector((max(bx_["hi"].x, hi.x), max(bx_["hi"].y, hi.y), max(bx_["hi"].z, hi.z))); bx_["names"].append(ob.name); merged = True; break
        if merged: continue
        cat = pr.get("category")
        life = (pr.get("stage_in", 1), pr.get("seq", 0.0) or 0.0, pr.get("stage_out"), pr.get("seq_out")) if (cat in ("existing", "demolition") or N == 1) \
            else (max(N, pr.get("stage_in", 1)), finish_seq, pr.get("stage_out"), pr.get("seq_out"))
        boxes.append(dict(lo=lo, hi=hi, top=top, life=life, names=[ob.name]))
    for bx_ in boxes:
        e = 0.0275; lo, hi = bx_["lo"], bx_["hi"]
        name = f"FS-boxing-{bx_['names'][0][:40]}"
        me = box_mesh(name, lo.x - e, lo.y - e, lo.z - e, hi.x + e, hi.y + e, bx_["top"], fin.get("FIN-CEIL"))
        extra.append(new_obj(name, me, "FIN-CEIL", bx_["life"], f"plasterboard boxing round {', '.join(bx_['names'])} (12.5 mm board on battens, painted FIN-CEIL; typical)"))
        nbox += 1
    tree = make_tree(live_parts())
    live = [(ob, p) for ob, p in live_parts() if not ob.name.startswith("FS-")]

    # ---- 2. flat ceilings: wherever a room's ceiling is higher than drawn (an old deck without a ceiling, a gap between decks),
    #         a plasterboard ceiling at the drawn height; never over a stair (its void)
    stair_bb = []
    for ob, p in live:
        if ob.name.startswith("ST-stair"):
            bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            stair_bb.append((min(v.x for v in bb) - 0.05, min(v.y for v in bb) - 0.05, max(v.x for v in bb) + 0.05, max(v.y for v in bb) + 0.05))
    nfill = 0
    lp_shell = [(ob, p) for ob, p in live_parts() if not (ob.name.startswith("SPEC-") and not ob.name.startswith(("SPEC-FLR", "SPEC-SKIRT")))
                and not p["props"].get("door_leaf")]
    tree_shell = make_tree(lp_shell)
    mat_shell = []
    for ob, p in lp_shell:
        for pl in ob.data.polygons:
            m_ = ob.data.materials[pl.material_index] if pl.material_index < len(ob.data.materials) else None
            mat_shell.append(m_.name if m_ else "")
    for r in spec_rooms:
        if BARE_ROOMS.search(r["id"]): continue
        if isinstance(r["ceiling_y"], (int, float)): cy = float(r["ceiling_y"])
        else:
            mm_ = re.match(r"\s*([\d.]+) above FFL where flat", str(r["ceiling_y"]))        # flat with a lower slope: the flat part is filled
            if not mm_: continue
            cy = r["floor_y"] + float(mm_.group(1))
        P = [(x, -z) for (x, z) in r["polygon"]]
        xs = [q[0] for q in P]; ys = [q[1] for q in P]; st = 0.05
        nx_, ny_ = int((max(xs) - min(xs)) / st) + 1, int((max(ys) - min(ys)) / st) + 1
        need = set()
        for i in range(nx_):
            for j in range(ny_):
                x = min(xs) + (i + 0.5) * st; y = min(ys) + (j + 0.5) * st
                if not _in_poly(x, y, P) or (r["floor_y"] < 1.0 and any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in stair_bb)): continue
                for (ox_, oy_) in ((0, 0), (-0.45, -0.45), (0.45, -0.45), (0.45, 0.45), (-0.45, 0.45)):
                    h = tree_shell.ray_cast(Vector((x + ox_ * st, y + oy_ * st, r["floor_y"] + 1.2)), Vector((0, 0, 1)), 8.0)
                    if h[0] is None or h[0].z > cy + 0.02 or (h[0].z > cy - 0.03 and RAW.match(mat_shell[h[2]])): need.add((i, j)); break
        # greedy rectangles
        while need:
            i0, j0 = min(need)
            i1 = i0
            while (i1 + 1, j0) in need: i1 += 1
            j1 = j0
            while all((ii, j1 + 1) in need for ii in range(i0, i1 + 1)): j1 += 1
            for ii in range(i0, i1 + 1):
                for jj in range(j0, j1 + 1): need.discard((ii, jj))
            x0 = min(xs) + i0 * st; x1 = min(xs) + (i1 + 1) * st; y0 = min(ys) + j0 * st; y1 = min(ys) + (j1 + 1) * st
            name = f"FS-ceiling-{r['id']}-{nfill}"
            me = box_mesh(name, x0, y0, cy - 0.004, x1, y1, cy - 0.0008, fin.get("FIN-CEIL"))
            life = (1, 0.0, None, None) if N == 1 else (N, finish_seq, None, None)
            extra.append(new_obj(name, me, "FIN-CEIL", life, f"plasterboard ceiling at the drawn height {cy} ({r['id']}; spec FIN-CEIL; row 191)"))
            nfill += 1
    # floors: wherever a room has no floor at its level (a gap at a threshold, under a cupboard), a floor in the room's finish
    nfl = 0
    for r in spec_rooms:
        if BARE_ROOMS.search(r["id"]): continue
        fm_ = re.search(r"FIN-FLR-[A-Z]+", r["finishes"].get("floor", ""))
        if not fm_: continue
        fy = r["floor_y"]; P = [(x, -z) for (x, z) in r["polygon"]]
        xs = [q[0] for q in P]; ys = [q[1] for q in P]; st = 0.05
        nx_, ny_ = int((max(xs) - min(xs)) / st) + 1, int((max(ys) - min(ys)) / st) + 1
        need = set()
        for i in range(nx_):
            for j in range(ny_):
                x = min(xs) + (i + 0.5) * st; y = min(ys) + (j + 0.5) * st
                if not _in_poly(x, y, P) or (fy > 1.0 and any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in stair_bb)): continue
                h = tree_shell.ray_cast(Vector((x, y, fy + 1.0)), Vector((0, 0, -1)), 3.0)
                if h[0] is not None and h[1].z < -0.2: continue                      # inside a solid (breast, pier)
                if h[0] is None or h[0].z < fy - 0.03: need.add((i, j))
        while need:
            i0, j0 = min(need); i1 = i0
            while (i1 + 1, j0) in need: i1 += 1
            j1 = j0
            while all((ii, j1 + 1) in need for ii in range(i0, i1 + 1)): j1 += 1
            for ii in range(i0, i1 + 1):
                for jj in range(j0, j1 + 1): need.discard((ii, jj))
            x0 = min(xs) + i0 * st; x1 = min(xs) + (i1 + 1) * st; y0 = min(ys) + j0 * st; y1 = min(ys) + (j1 + 1) * st
            name = f"FS-floor-{r['id']}-{nfl}"
            me = box_mesh(name, x0, y0, fy - 0.03, x1, y1, fy - 0.001, fin.get(fm_.group(0)), fin.tile.get(fin.get(fm_.group(0)).name, (1, 1)))
            life = (1, 0.0, None, None) if N == 1 else (N, 0.7, None, None)
            extra.append(new_obj(name, me, fm_.group(0), life, f"floor in {fm_.group(0)} where the room had none at its level ({r['id']}; row 191)"))
            nfl += 1
    if nfl: log(f"finish: {nfl} floor patches where a room had no floor at its level")
    if nfill or nfl: tree = make_tree(live_parts())
    log(f"finish: {nbox} beams boxed, {nfill} ceiling boards where a room's ceiling was missing or higher than drawn")

    def room_at(q):
        for (rid, P, z0, z1, bb) in rooms:
            if bb[0] <= q.x <= bb[2] and bb[1] <= q.y <= bb[3] and z0 < q.z < z1 and _in_poly(q.x, q.y, P): return rid
        return None

    RV_, RT_ = [], []
    for ob_, p_ in live_parts():
        if p_["props"].get("group") in ("roof_cover", "ridge", "hip", "valley"):
            M_ = ob_.matrix_world; b_ = len(RV_); RV_.extend(M_ @ v.co for v in ob_.data.vertices)
            RT_.extend(tuple(b_ + i for i in pl.vertices) for pl in ob_.data.polygons)
    roof_tree = BVHTree.FromPolygons(RV_, RT_) if RT_ else None

    def under_cover(q):
        """inside the house's envelope: something above, and not standing on top of a roof (a point over the porch or the
        catslide roof is outside, even under the main roof's eaves)"""
        if tree.ray_cast(q, Vector((0, 0, 1)), 30.0)[0] is None: return False
        if roof_tree is not None:
            hr = roof_tree.ray_cast(q, Vector((0, 0, -1)), 8.0); ha = tree.ray_cast(q, Vector((0, 0, -1)), 8.0)
            if hr[0] is not None and ha[0] is not None and hr[3] <= ha[3] + 1e-4: return False
        return True

    def near_room(c):
        return any(bb[0] <= c.x <= bb[2] and bb[1] <= c.y <= bb[3] and z0 - 0.6 < c.z < z1 + 0.6 for (rid, P, z0, z1, bb) in rooms)

    def seen(samples, n):
        up = Vector((0, 0, 1))
        h = n.cross(up)
        if h.length < 1e-6: h = Vector((1, 0, 0))
        h.normalize(); vax = n.cross(h).normalized()
        dirs = [n, (n + h).normalized(), (n - h).normalized(), (n + vax).normalized(), (n - vax).normalized(),
                (n + 2 * h).normalized(), (n - 2 * h).normalized()]
        for s in samples:
            o = s + n * 0.002
            for d in dirs:
                for dist in (0.3, 0.8, 1.5):
                    q = o + d * dist
                    rid = room_at(q)
                    if rid is None: continue
                    hit = tree.ray_cast(o, d, dist)
                    if hit[0] is None: return rid
        return None

    groups = {}                     # (stage_in, seq, stage_out, seq_out, finish) -> list of (verts, src name)
    n_faces = 0; per_room = {}
    done = set()
    faces = {}                      # (ob name, poly) -> dict(ob, p, rid, cells: set or None (whole face), frame)
    CELL = 0.25
    def frame_of(ob, k):
        """a large planar face as a grid: origin, axes (u horizontal / v), extents; cells of CELL m"""
        M = ob.matrix_world; R = M.to_3x3().normalized(); pl = ob.data.polygons[k]
        n = (R @ pl.normal).normalized()
        vs = [M @ ob.data.vertices[i].co for i in pl.vertices]
        u = n.cross(Vector((0, 0, 1)))
        if u.length < 1e-6: u = Vector((1, 0, 0))
        u.normalize(); v = n.cross(u).normalized()
        o = vs[0]
        us = [(q - o).dot(u) for q in vs]; ws = [(q - o).dot(v) for q in vs]
        return dict(o=o, u=u, v=v, n=n, u0=min(us), u1=max(us), v0=min(ws), v1=max(ws),
                    nu=max(1, int(math.ceil((max(us) - min(us)) / CELL))), nv=max(1, int(math.ceil((max(ws) - min(ws)) / CELL))),
                    poly2=[(a_, b_) for a_, b_ in zip(us, ws)])
    def add_face(ob, p, k, rid, at=None):
        """mark a face (small: whole) or the cells of a large face that are seen (at: a hit point; None: run the cell test)"""
        key = (ob.name, k)
        pl = ob.data.polygons[k]
        if (ob.matrix_world.to_3x3() @ pl.normal).normalized().z > 0.7 and p["props"].get("group") in ("deck", "slab_layer", "floor_finish", "joist"): return
        area = pl.area * (ob.matrix_world.to_3x3().determinant() ** (2 / 3) if ob.matrix_world.to_3x3().determinant() > 0 else 1)
        rec = faces.get(key)
        if rec is None:
            if area <= 0.3:
                nn_ = (ob.matrix_world.to_3x3() @ pl.normal).normalized()
                if not under_cover(ob.matrix_world @ pl.center + nn_ * 0.008): return
            rec = faces[key] = dict(ob=ob, p=p, rid=rid, cells=None if area <= 0.3 else set(), fr=None if area <= 0.3 else frame_of(ob, k))
        if rec["cells"] is None: return
        fr = rec["fr"]
        if at is not None:
            d_ = at - fr["o"]; i = int((d_.dot(fr["u"]) - fr["u0"]) / CELL); j = int((d_.dot(fr["v"]) - fr["v0"]) / CELL)
            i, j = min(max(i, 0), fr["nu"] - 1), min(max(j, 0), fr["nv"] - 1)
            if (i, j) in rec["cells"]: return
            rec["cells"].add((i, j))
            for di in (-1, 0, 1):                 # a grazing ray lands near a cell edge: the neighbours that are in the room too
                for dj in (-1, 0, 1):
                    ii, jj = i + di, j + dj
                    if (ii, jj) in rec["cells"] or not (0 <= ii < fr["nu"] and 0 <= jj < fr["nv"]): continue
                    cc = fr["o"] + fr["u"] * (fr["u0"] + (ii + 0.5) * CELL) + fr["v"] * (fr["v0"] + (jj + 0.5) * CELL)
                    if room_at(cc + fr["n"] * 0.06) and under_cover(cc + fr["n"] * 0.06): rec["cells"].add((ii, jj))
            return
        for i in range(fr["nu"]):
            for j in range(fr["nv"]):
                if (i, j) in rec["cells"]: continue
                ua = fr["u0"] + i * CELL; ub = min(fr["u1"], ua + CELL); va = fr["v0"] + j * CELL; vb = min(fr["v1"], va + CELL)
                cc = fr["o"] + fr["u"] * ((ua + ub) / 2) + fr["v"] * ((va + vb) / 2)
                if not _in_poly((ua + ub) / 2, (va + vb) / 2, fr["poly2"]): continue
                smp = [cc] + [fr["o"] + fr["u"] * (ua + (ub - ua) * a_) + fr["v"] * (va + (vb - va) * b_) for a_, b_ in ((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8))]
                if under_cover(cc + fr["n"] * 0.05) and seen(smp, fr["n"]): rec["cells"].add((i, j))
    def emit():
        nonlocal n_faces
        for key, rec in faces.items():
            ob, p = rec["ob"], rec["p"]; k = key[1]
            pr = p["props"]; g = pr.get("group", "")
            M = ob.matrix_world; R = M.to_3x3().normalized(); pl = ob.data.polygons[k]
            n = (R @ pl.normal).normalized(); c = M @ pl.center
            down = n.z < -0.7
            finish = "FIN-CEIL" if down and (g in DOWN_CEIL_GROUPS or c.z > 2.0) else "FIN-WALL"
            if g == "ground": finish = "c:#26231F:0.95:0"                    # under-floor void: dark, as seen through a slot
            cat = pr.get("category")
            if g == "ground": life = (1, 0.0, None, None) if N == 1 else (N, finish_seq, None, None)
            elif cat in ("existing", "demolition") or N == 1:
                life = (pr.get("stage_in", 1), pr.get("seq", 0.0) or 0.0, pr.get("stage_out"), pr.get("seq_out"))
            else:
                life = (max(N, pr.get("stage_in", 1)), finish_seq, pr.get("stage_out"), pr.get("seq_out"))
            off = 0.004 if g in ("roof_layer",) else (0.001 if life[0] <= 1 else 0.0025)
            area_w = pl.area
            if rec["cells"] is None and g != "ground" and (area_w < 0.05 or g in ("rafter", "valley", "hip")):
                # a sliver (a ledge in a reveal, a rafter's edge at a ceiling junction) is finished in its own material: no skin
                # for a grazing ray to slip under. (A new part's sliver shows finished from its own stage on: noted.)
                if ob.data.users > 1: ob.data = ob.data.copy()
                me_ = ob.data; fm_ = fin.get(finish)
                if fm_.name not in [m.name for m in me_.materials if m]: me_.materials.append(fm_)
                pl_ = me_.polygons[k]; pl_.material_index = [m.name if m else "" for m in me_.materials].index(fm_.name)
                n_faces += 1; per_room[rec["rid"]] = per_room.get(rec["rid"], 0) + 1
                continue
            if rec["cells"] is None:
                vs = [M @ ob.data.vertices[i].co for i in pl.vertices]
                # plaster turns the corner: every edge of the skin runs 4 mm past the face's edge (a true in-plane offset), so no
                # grazing ray slips round it where a lining or reveal meets the face
                m_ = len(vs); area_sign = sum(((vs[(i + 1) % m_] - vs[i]).cross(vs[(i + 2) % m_] - vs[(i + 1) % m_])).dot(n) for i in range(m_))
                sg_ = 1 if area_sign >= 0 else -1
                outs = []
                for i in range(m_):
                    e_ = (vs[(i + 1) % m_] - vs[i])
                    outs.append(e_.cross(n).normalized() * sg_ if e_.length > 1e-9 else Vector((0, 0, 0)))
                nv = []
                for i in range(m_):
                    a_, b_ = outs[i - 1], outs[i]
                    bis = a_ + b_
                    if bis.length < 1e-6: nv.append(vs[i]); continue
                    bis.normalize(); cs_ = max(0.35, bis.dot(b_))
                    nv.append(vs[i] + bis * (0.020 / cs_))
                vs = nv
                groups.setdefault(life + (finish,), []).append(([v + n * off for v in vs], ob.name))
            else:
                if not rec["cells"]: continue
                fr = rec["fr"]; need = set(rec["cells"])
                while need:                                  # greedy rectangles of seen cells, clipped to the face's extent
                    i0, j0 = min(need); i1 = i0
                    while (i1 + 1, j0) in need: i1 += 1
                    j1 = j0
                    while all((ii, j1 + 1) in need for ii in range(i0, i1 + 1)): j1 += 1
                    for ii in range(i0, i1 + 1):
                        for jj in range(j0, j1 + 1): need.discard((ii, jj))
                    ua = fr["u0"] + i0 * CELL; ub = min(fr["u1"], fr["u0"] + (i1 + 1) * CELL)
                    va = fr["v0"] + j0 * CELL; vb = min(fr["v1"], fr["v0"] + (j1 + 1) * CELL)
                    if i0 == 0: ua -= 0.020
                    if ub >= fr["u1"] - 1e-6: ub += 0.020
                    if j0 == 0: va -= 0.020
                    if vb >= fr["v1"] - 1e-6: vb += 0.020
                    rect = [(ua, va), (ub, va), (ub, vb), (ua, vb)]
                    # never past the face itself (a gable's sloping top, a splayed reveal): clip to the face grown by 4 mm
                    clipped = _clip_convex(rect, _grow(fr["poly2"], 0.020))
                    if len(clipped) < 3: continue
                    q = [fr["o"] + fr["u"] * a_ + fr["v"] * b_ + n * off for a_, b_ in clipped]
                    groups.setdefault(life + (finish,), []).append((q, ob.name))
            n_faces += 1; per_room[rec["rid"]] = per_room.get(rec["rid"], 0) + 1
    for ob, p in live:
        pr = p["props"]; g = pr.get("group", "")
        if p.get("context") or pr.get("spec_id") or ob.name.startswith(("SPEC-", "XFD-")): continue
        if g in ("ground", "window", "door", "rooflight", "fitting", "glass", "roof_cover", "ridge"): continue
        mats = ob.data.materials
        if not mats or not any(m and RAW.match(m.name) for m in mats): continue
        M = ob.matrix_world; R = M.to_3x3().normalized()
        for pl in ob.data.polygons:
            m = mats[pl.material_index] if pl.material_index < len(mats) else None
            if not m or not RAW.match(m.name): continue
            n = (R @ pl.normal).normalized()
            c = M @ pl.center
            if not near_room(c): continue
            if m.name.startswith(("existing_floor", "floor_finish")) and n.z > -0.5: continue      # floors: only their undersides
            vs = [M @ ob.data.vertices[i].co for i in pl.vertices]
            samples = [c] + [c + (v - c) * 0.7 for v in vs[:4]]
            rid = seen(samples, n)
            if rid is None: continue
            add_face(ob, p, pl.index, rid)
    # ---- 3. what a person standing in each room actually sees: rays from a grid of standing points (eye 1.0 / 1.6 m; doors
    #         open or hidden, as the viewer allows) find raw faces the face test missed (seen through a slot, round a corner)
    lp = [(ob, p) for ob, p in live_parts() if not p["props"].get("door_leaf")]
    V2, T2, own2 = [], [], []
    for ob, p in lp:
        M = ob.matrix_world; b = len(V2); V2.extend(M @ v.co for v in ob.data.vertices)
        for pl in ob.data.polygons: T2.append(tuple(b + i for i in pl.vertices)); own2.append((ob, p, pl.index))
    tv = BVHTree.FromPolygons(V2, T2)
    nd = 1500; gold = math.pi * (3 - math.sqrt(5))
    DIRS = []
    for i in range(nd):
        yy = 1 - 2 * (i + 0.5) / nd; rr = math.sqrt(1 - yy * yy); t = gold * i
        DIRS.append(Vector((math.cos(t) * rr, math.sin(t) * rr, yy)))
    nview = 0
    bare = {r["id"] for r in spec_rooms if BARE_ROOMS.search(r["id"])}
    for rid, o in standing_points(spec_rooms, views):
        if rid in bare: continue
        hits = []; back = 0
        for d in DIRS:
            h = tv.ray_cast(o, d, 9.0)
            if h[0] is not None:
                if h[1].dot(d) > 0.05: back += 1
                hits.append(h)
        if back > 0.35 * nd: continue                  # standing inside a solid
        for h in hits:
            if h[3] > 8.0: continue
            ob, p, k = own2[h[2]]
            pr = p["props"]
            mats = ob.data.materials; pl = ob.data.polygons[k]
            m = mats[pl.material_index] if pl.material_index < len(mats) else None
            if pr.get("group") == "ground" and m and m.name.startswith("earth") and h[0].z < -0.05:
                add_face(ob, p, k, rid, at=h[0]); nview += 1; continue      # the ground under the floor, seen down a threshold slot: in shadow
            if p.get("context") or pr.get("spec_id") or ob.name.startswith(("SPEC-", "XFD-", "FS-")) or pr.get("group") in ("ground", "window", "door", "rooflight", "glass", "roof_cover", "ridge"): continue
            back_ok = pr.get("group") in ("rafter", "valley", "hip", "timber_beam", "joist", "ceiling_joist")   # a cut member seen through its open end
            if m and RAW.match(m.name) and (h[1].dot(h[0] - o) < 0 or back_ok):          # the face is seen from its front (a back face is the integrity's "missing face")
                add_face(ob, p, k, rid, at=h[0]); nview += 1
    log(f"finish: {nview} raw hits from standing points covered")
    # a roof member seen from a room (an old rafter foot left inside the new bedroom) is finished all over, like a boxed member
    members = {}
    for (nm_, k_), rec in list(faces.items()):
        if rec["p"]["props"].get("group") in ("rafter", "valley", "hip"): members[nm_] = rec
    for nm_, rec in members.items():
        ob = rec["ob"]; mats = ob.data.materials
        for pl in ob.data.polygons:
            m = mats[pl.material_index] if pl.material_index < len(mats) else None
            if m and RAW.match(m.name) and (nm_, pl.index) not in faces:
                faces[(nm_, pl.index)] = dict(ob=ob, p=rec["p"], rid=rec["rid"], cells=None, fr=None)
    emit()
    out = list(extra)
    for k, (life, faces) in enumerate(sorted(groups.items(), key=lambda kv: str(kv[0]))):
        si, sq, so, sqo, finish = life
        bm = bmesh.new(); uv = bm.loops.layers.uv.new("UVMap")
        tw, th = fin.tile.get(fin.get(finish).name, (1.5, 1.5))
        for vs, src in faces:
            try: f = bm.faces.new([bm.verts.new(v) for v in vs])
            except ValueError: continue
            nn = f.normal
            for l in f.loops:
                co = l.vert.co
                if abs(nn.z) > 0.7: l[uv].uv = (co.x / tw, co.y / th)
                else:
                    hh = Vector((-nn.y, nn.x, 0))
                    if hh.length > 1e-6: hh.normalize()
                    l[uv].uv = (co.dot(hh) / tw, co.z / th)
        name = f"FS-skin-{finish.replace(':', '').replace('#', '')[:12]}-s{si}-{k}"
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        base_m = fin.get(finish); m2 = bpy.data.materials.get(base_m.name + "_skin")
        if m2 is None:
            m2 = base_m.copy(); m2.name = base_m.name + "_skin"; m2.use_backface_culling = False
        me.materials.append(m2)
        ob = bpy.data.objects.new(name, me)
        props = dict(element=name, group="finish_skin", stage_in=si, seq=round(sq, 4), stage_out=so, seq_out=sqo,
                     category="finish" if N > 1 and si == N else "existing", storey="ground",
                     label=f"plaster and {finish} paint on {len(faces)} faces seen from finished rooms (spec_v1; row 185)",
                     plain_label="Plastered and painted surface", drawing="spec_v1 (signed 1 Nov 2026)", conf="assumed",
                     provenance="typical", collide=False)
        for kk, vv in props.items():
            if vv is not None: ob[kk] = vv
        coll.objects.link(ob)
        out.append((ob, dict(props=props, spec=True, atom=dict(id=name, kind="skin", meta=props, provenance="typical"))))
    log(f"finish skins: {n_faces} construction faces seen from finished rooms covered, {len(out)} merged objects; by room {per_room}")
    return out


def recolour_finished(objs, fin, log):
    """ceilings and the porch vault lining -> FIN-CEIL; the stair -> oak treads (FIN-FLR-OAK) and white satin risers/strings"""
    n_c = n_s = 0
    for ob, p in objs:
        if ob.type != "MESH": continue
        nm = ob.name; g = p["props"].get("group", "")
        if nm.startswith("CL-") or (g == "ceiling_joist" and any(m and m.name.startswith("spec_FIN-WALL") for m in ob.data.materials)):
            if any(m and m.name.startswith("spec_FIN-WALL") for m in ob.data.materials):
                ob.data.materials.clear(); ob.data.materials.append(fin.get("FIN-CEIL")); n_c += 1
        elif nm.startswith("ST-stair"):
            me = ob.data
            oak, white = fin.get("FIN-FLR-OAK"), fin.get("c:#F2EFEA:0.4:0")
            me.materials.clear(); me.materials.append(white); me.materials.append(oak)
            R = ob.matrix_world.to_3x3().normalized()
            for pl in me.polygons: pl.material_index = 1 if (R @ pl.normal).z > 0.7 else 0
            n_s += 1
    log(f"finishes: {n_c} ceilings/vault linings -> FIN-CEIL, {n_s} stair parts -> FIN-STAIR (oak treads, white risers)")


def scribe_architraves(objs, N, log, reach=0.035):
    """an architrave that stops 1-35 mm short of a return wall is scribed to it (a joiner widens or cuts it to fit): the
    leg's outer edge moves to touch the wall, so no sliver shows at the corner (integrity gap check)"""
    V, T, own = [], [], []
    for ob, p in objs:
        if ob.type != "MESH" or (p["props"].get("stage_out") or 99) <= N or p["props"].get("door_leaf"): continue
        if ob.name.endswith("_architraves") or ob.name.startswith(("SPEC-", "FS-skin")): continue
        M = ob.matrix_world; b = len(V); V.extend(M @ v.co for v in ob.data.vertices)
        T.extend(tuple(b + i for i in pl.vertices) for pl in ob.data.polygons)
    tree = BVHTree.FromPolygons(V, T)
    moved = 0
    for ob, p in objs:
        if not ob.name.endswith("_architraves") or "wall_dir" not in ob.keys(): continue
        d = Vector((ob["wall_dir"][0], ob["wall_dir"][1], 0)).normalized(); nn = Vector((-d.y, d.x, 0))
        me = ob.data; M = ob.matrix_world; Mi = M.inverted()
        W = [M @ v.co for v in me.vertices]
        cen = sum(W, Vector()) / len(W)
        for side in (-1, 1):
            for face in (-1, 1):
                grp = [i for i, w in enumerate(W) if (w - cen).dot(nn) * face > 0]
                if not grp: continue
                ext = max((W[i] - cen).dot(d) * side for i in grp)
                edge = [i for i in grp if (W[i] - cen).dot(d) * side > ext - 0.0025]
                zs = [W[i].z for i in edge]
                if not zs: continue
                zlo, zhi = min(zs), max(zs)
                best = None
                for zz in [zlo + 0.15 + k_ * (zhi - zlo - 0.3) / 6 for k_ in range(7)]:
                    o = sum((W[i] for i in edge), Vector()) / len(edge); o.z = zz
                    o = o - d * side * 0.001
                    h = tree.ray_cast(o, d * side, reach + 0.001)
                    if h[0] is None: continue
                    t = h[3] - 0.001
                    best = t if best is None else min(best, t)
                if best is not None and best > 0.0008:
                    for i in edge:
                        me.vertices[i].co = Mi @ (W[i] + d * side * (best - 0.0003))
                    moved += 1
        # the back of each face's architrave beds onto the wall: where the wall face is set back (a stud head over a door),
        # each back vertex moves in to touch it (<= 15 mm), as a joiner scribes it
        W = [M @ v.co for v in me.vertices]
        for face in (-1, 1):
            grp = [i for i, w in enumerate(W) if (w - cen).dot(nn) * face > 0]
            if not grp: continue
            back = min((W[i] - cen).dot(nn) * face for i in grp)
            for i in [i for i in grp if (W[i] - cen).dot(nn) * face < back + 0.001]:
                o = W[i] + nn * face * 0.001
                h = tree.ray_cast(o, -nn * face, 0.016)
                if h[0] is not None and h[3] - 0.001 > 0.0008:
                    me.vertices[i].co = Mi @ (W[i] - nn * face * (h[3] - 0.001 - 0.0003))
    log(f"joinery: {moved} architrave legs scribed to the return wall beside them")


def scribe_skirting(objs, N, log, reach=0.025):
    """a skirting run that stops 1-25 mm short of what it meets (an architrave, a balustrade, the next room's skirting, the
    stair string) is run on to touch it, as fitted: its end cap moves along the run"""
    V, T, own = [], [], []
    for ob, p in objs:
        if ob.type != "MESH" or (p["props"].get("stage_out") or 99) <= N or p["props"].get("door_leaf"): continue
        if ob.name.startswith(("FS-skin",)): continue
        M = ob.matrix_world; b = len(V); V.extend(M @ v.co for v in ob.data.vertices)
        for pl in ob.data.polygons: T.append(tuple(b + i for i in pl.vertices)); own.append(ob.name)
    tree = BVHTree.FromPolygons(V, T)
    def cast(o, d, dist, me_name):
        left = dist; o = o.copy(); trav = 0.0
        for _ in range(6):
            h = tree.ray_cast(o, d, left)
            if h[0] is None: return None
            if own[h[2]] != me_name: return trav + h[3]
            trav += h[3] + 1e-4; left -= h[3] + 1e-4; o = h[0] + d * 1e-4
            if left <= 0: return None
        return None
    moved = 0
    for ob, p in objs:
        a = p.get("atom") if isinstance(p.get("atom"), dict) else None
        if not a or not a.get("skirt_ends"): continue
        me = ob.data; M = ob.matrix_world; Mi = M.inverted()
        W = [M @ v.co for v in me.vertices]
        z0 = min(w.z for w in W)
        for (pt, dr) in a["skirt_ends"]:
            d = Vector((dr[0], dr[1], 0)).normalized(); P0 = Vector((pt[0], pt[1], 0))
            ext = max((Vector((w.x, w.y, 0)) - P0).dot(d) for w in W)
            cap = [i for i, w in enumerate(W) if (Vector((w.x, w.y, 0)) - P0).dot(d) > ext - 0.0015]
            if not cap: continue
            best = None
            for i in cap:                                         # any part of the end that meets something within reach
                w = W[i]
                if not (z0 + 0.01 < w.z < z0 + 0.14): continue
                o = w - d * 0.002
                hd = cast(o, d, reach + 0.002, ob.name)
                if hd is None: continue
                t = hd - 0.002
                best = t if best is None else min(best, t)
            if best is not None and best > 0.0008:
                for i in cap: me.vertices[i].co = Mi @ (W[i] + d * (best - 0.0003))
                moved += 1
    log(f"joinery: {moved} skirting ends run on to meet what they stop against")
