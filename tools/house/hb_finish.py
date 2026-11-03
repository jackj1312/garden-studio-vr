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
import math, re, os, json
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
            if (ob.name.startswith("SPEC-") and not ob.name.startswith(("SPEC-FLR", "SPEC-SKIRT"))) or ob.name.startswith("JN-"): continue   # furniture is not the shell
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

    def prism_mesh(name, quad, z0, z1, mat, tile=(1.5, 1.5)):
        """a closed prism over a plan quad (any orientation), outward normals, box-projected UVs"""
        bm = bmesh.new(); uv = bm.loops.layers.uv.new("UVMap")
        Q = _ccw2(list(quad))
        vs = [bm.verts.new((x, y, z0)) for x, y in Q] + [bm.verts.new((x, y, z1)) for x, y in Q]
        n = len(Q)
        for f in [tuple(range(n))[::-1], tuple(range(n, 2 * n))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]:
            fa = bm.faces.new([vs[i] for i in f])
            for l in fa.loops:
                c = l.vert.co; nn = fa.normal
                l[uv].uv = ((c.x / tile[0], c.y / tile[1]) if abs(nn.z) > 0.7 else ((c.x if abs(nn.y) > abs(nn.x) else c.y) / tile[0], c.z / tile[1]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
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
    # ---- 1b. kept roof members over a new room (CORRECTIONS-LOG 213): the part of a rafter, hip or valley that hangs below a
    #          room's ceiling lining (a ray down from it meets no lining before the floor, a ray up meets one) is boxed as a
    #          bulkhead; members of one roof plane run on as one box while it stays inside the room; a box within 0.35 m of a
    #          wall runs on to it. Painting a member is never a finish.
    def rect_inside(P, x0, y0, x1, y1, st=0.04):
        nx_, ny_ = max(2, int((x1 - x0) / st) + 1), max(2, int((y1 - y0) / st) + 1)
        return all(_in_poly(x0 + (x1 - x0) * i / (nx_ - 1), y0 + (y1 - y0) * j / (ny_ - 1), P) for i in range(nx_) for j in range(ny_))
    lin_parts = [(ob, p) for ob, p in live_parts() if ob.name.startswith(("CL-", "XC-")) and p["props"].get("group") in ("ceiling_joist", "deck")]
    lin_tree = make_tree(lin_parts) if lin_parts else None
    UP, DN = Vector((0, 0, 1)), Vector((0, 0, -1))
    nroof = 0
    for r in spec_rooms:
        if BARE_ROOMS.search(r["id"]) or lin_tree is None: continue
        P = [(x, -z) for (x, z) in r["polygon"]]; Pin = _grow(P, -0.004) if len(P) >= 3 else P
        pxs = [q_[0] for q_ in P]; pys = [q_[1] for q_ in P]; fy = r["floor_y"]
        def hanging(q):
            if not _in_poly(q.x, q.y, Pin) or q.z < fy + 1.2 or q.z > fy + 4.0: return False
            up = lin_tree.ray_cast(q + UP * 0.001, UP, 1.5)
            if up[0] is None: return False
            dn = lin_tree.ray_cast(q - UP * 0.001, DN, q.z - fy - 0.3)
            return dn[0] is None
        mem = []
        for ob, p in live_parts():
            pr = p["props"]
            if pr.get("group") not in ("rafter", "hip", "valley") or ob.name.startswith(("SC-", "FS-")): continue
            M = ob.matrix_world; vs = [M @ v.co for v in ob.data.vertices]
            if not vs or max(v.x for v in vs) < min(pxs) or min(v.x for v in vs) > max(pxs) or max(v.y for v in vs) < min(pys) or min(v.y for v in vs) > max(pys): continue
            if min(v.z for v in vs) > fy + 4.0 or max(v.z for v in vs) < fy + 1.2: continue
            pts = []
            for ed in ob.data.edges:
                a_, b_ = vs[ed.vertices[0]], vs[ed.vertices[1]]
                for k_ in range(41):
                    q = a_.lerp(b_, k_ / 40)
                    if hanging(q): pts.append(q)
            if len(pts) < 2: continue
            lo = Vector((min(q.x for q in pts), min(q.y for q in pts), min(q.z for q in pts)))
            hi = Vector((max(q.x for q in pts), max(q.y for q in pts), max(q.z for q in pts)))
            mem.append(dict(lo=lo, hi=hi, names=[ob.name], plane=ob.name.rsplit("-", 1)[0].rstrip("-"), life=(pr.get("stage_in", 1), pr.get("seq", 0.0) or 0.0, pr.get("stage_out"), pr.get("seq_out"))))
        merged_ = True
        while merged_:
            merged_ = False
            for i in range(len(mem)):
                for j in range(i + 1, len(mem)):
                    a_, b_ = mem[i], mem[j]
                    if a_["plane"] != b_["plane"]: continue
                    gx = max(a_["lo"].x, b_["lo"].x) - min(a_["hi"].x, b_["hi"].x); gy = max(a_["lo"].y, b_["lo"].y) - min(a_["hi"].y, b_["hi"].y)
                    if max(gx, gy) > 0.45: continue
                    lo = Vector((min(a_["lo"].x, b_["lo"].x), min(a_["lo"].y, b_["lo"].y), min(a_["lo"].z, b_["lo"].z)))
                    hi = Vector((max(a_["hi"].x, b_["hi"].x), max(a_["hi"].y, b_["hi"].y), max(a_["hi"].z, b_["hi"].z)))
                    if not rect_inside(Pin, lo.x, lo.y, hi.x, hi.y): continue
                    mem[i] = dict(lo=lo, hi=hi, names=a_["names"] + b_["names"], plane=a_["plane"], life=a_["life"]); mem.pop(j); merged_ = True; break
                if merged_: break
        e = 0.0275
        for bx_ in mem:
            x0, y0, x1, y1 = bx_["lo"].x - e, bx_["lo"].y - e, bx_["hi"].x + e, bx_["hi"].y + e
            while x0 < x1 and not rect_inside(Pin, x0, y0, x0 + 0.002, y1): x0 += 0.002
            while x1 > x0 and not rect_inside(Pin, x1 - 0.002, y0, x1, y1): x1 -= 0.002
            while y0 < y1 and not rect_inside(Pin, x0, y0, x1, y0 + 0.002): y0 += 0.002
            while y1 > y0 and not rect_inside(Pin, x0, y1 - 0.002, x1, y1): y1 -= 0.002
            for side in range(4):
                for step in range(1, 176):
                    d_ = step * 0.002
                    t = [x0 - d_ if side == 0 else x0, y0 - d_ if side == 2 else y0, x1 + d_ if side == 1 else x1, y1 + d_ if side == 3 else y1]
                    if not rect_inside(Pin, *t):
                        if step > 1:
                            if side == 0: x0 -= (step - 1) * 0.002
                            elif side == 1: x1 += (step - 1) * 0.002
                            elif side == 2: y0 -= (step - 1) * 0.002
                            else: y1 += (step - 1) * 0.002
                        break
            if x1 - x0 < 0.01 or y1 - y0 < 0.01: continue
            tops = []
            for i in range(5):
                for j in range(5):
                    q = Vector((x0 + (x1 - x0) * (i + 0.5) / 5, y0 + (y1 - y0) * (j + 0.5) / 5, bx_["lo"].z))
                    h = lin_tree.ray_cast(q, UP, 1.5)
                    if h[0] is not None: tops.append(h[0].z)
            if not tops: continue
            top = max(tops) + 0.002
            name = f"FS-boxing-{bx_['names'][0][:34]}-{r['id'][4:14]}"
            me = box_mesh(name, x0, y0, bx_["lo"].z - e, x1, y1, top, fin.get("FIN-CEIL"))
            life = bx_["life"] if N == 1 else (max(N, bx_["life"][0]), finish_seq, bx_["life"][2], bx_["life"][3])
            extra.append(new_obj(name, me, "FIN-CEIL", life, f"plasterboard bulkhead boxing the kept roof members {', '.join(bx_['names'][:6])} below the "
                                 f"{r['id']} ceiling (row 213; typical)"))
            nroof += 1
    if nroof: log(f"finish: {nroof} bulkheads round kept roof members below a room ceiling (row 213)")
    # ---- 1b2. a wall that stops short of the ceiling it meets leaves a slot into the roof or the next space (row 213: the old
    #           rear wall's top at 4.62 under the bedroom 3 ceiling at 5.08 showed the plate and rafter feet): the slot over the
    #           wall head is closed with a stud-and-board head infill up to the ceiling lining, finished as the wall
    shell_lp = [(ob, p) for ob, p in live_parts() if not (ob.name.startswith("SPEC-") and not ob.name.startswith(("SPEC-FLR", "SPEC-SKIRT")))
                and not p["props"].get("door_leaf") and not ob.name.startswith("FS-skin")]
    s_tree = make_tree(shell_lp)
    s_grp = [p["props"].get("group", "") for ob, p in shell_lp for pl in ob.data.polygons]
    MEMBER = ("rafter", "hip", "valley", "wall_plate", "joist", "ceiling_joist", "timber_beam", "steel")
    # spaces open to a room that are not spec rooms (the stairwell under its own ceiling deck) are closed the same way
    pseudo = []
    for ob, p in live_parts():
        if ob.name.startswith("XC-") and "stairwell" in ob.name:
            bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            x0, x1 = min(v.x for v in bb), max(v.x for v in bb); y0, y1 = min(v.y for v in bb), max(v.y for v in bb); zc = min(v.z for v in bb)
            pseudo.append(dict(id="R-stairwell-" + ob.name[3:20], polygon=[(x0, -y0), (x1, -y0), (x1, -y1), (x0, -y1)], floor_y=zc - 2.405, ceiling_y=zc))
    ninf = 0
    for r in list(spec_rooms) + pseudo:
        if BARE_ROOMS.search(r["id"]) or lin_tree is None or r["floor_y"] < 1.0: continue
        P = _ccw2([(x, -z) for (x, z) in r["polygon"]]); fy = r["floor_y"]
        for i in range(len(P)):
            (ax, ay), (bx2, by2) = P[i], P[(i + 1) % len(P)]
            L_ = math.hypot(bx2 - ax, by2 - ay)
            if L_ < 0.2: continue
            tx, ty = (bx2 - ax) / L_, (by2 - ay) / L_; nx_, ny_ = ty, -tx          # outward normal of a ccw polygon
            segs = []
            for k in range(int(L_ / 0.1)):
                s = (k + 0.5) * L_ / int(L_ / 0.1)
                px, py = ax + tx * s, ay + ty * s
                base = Vector((px - nx_ * 0.05, py - ny_ * 0.05, 0))
                up_h = lin_tree.ray_cast(Vector((base.x, base.y, fy + 1.0)), UP, 3.5)
                if up_h[0] is None: continue
                up2 = s_tree.ray_cast(Vector((base.x, base.y, fy + 1.0)), UP, 3.5)      # a bulkhead under the ceiling: up to its soffit
                ctop = min(up_h[0].z, up2[0].z) if (up2[0] is not None and up2[0].z > fy + 1.6) else up_h[0].z   # a stair below is not a soffit
                col = []
                z = fy + 1.5
                while z < ctop - 0.008 and len(col) < 200:          # bounded (row: the hung slot scan)
                    h = s_tree.ray_cast(Vector((base.x, base.y, z)), Vector((nx_, ny_, 0)), 0.40)
                    col.append((z, h[0] is not None and s_grp[h[2]] not in MEMBER)); z += 0.02      # a roof member is never a wall face
                if len(col) < 3: continue
                if os.environ.get("HB_DEBUG_INFILL"): log(f"infill-dbg {r['id'][:18]} e{i} s{s:.2f} ({px:.2f},{py:.2f}) ctop {ctop:.3f} " + "".join("#" if ok else "." for zz, ok in col))
                # the highest open run with wall below it, reaching to within 60 mm of the ceiling (a plate may close the top)
                oi = [k_ for k_, (zz, ok) in enumerate(col) if not ok]
                if not oi or ctop - col[oi[-1]][0] > 0.07: continue
                k_ = oi[-1]
                while k_ - 1 >= 0 and not col[k_ - 1][1]: k_ -= 1
                if k_ == 0: continue                                      # nothing below: an open side (stair, balustrade)
                zt_ = col[oi[-1]][0]; zb = col[k_][0] - 0.01
                if zt_ - zb < 0.04: continue
                segs.append((s, zb, ctop))
            # merge neighbouring samples with the same span into one board
            runs = []
            for s, zb, zt in segs:
                if runs and abs(runs[-1]["s1"] - (s - 0.05)) < 0.06 and abs(runs[-1]["zb"] - zb) < 0.03 and abs(runs[-1]["zt"] - zt) < 0.03:
                    runs[-1]["s1"] = s + 0.05; runs[-1]["zb"] = min(runs[-1]["zb"], zb); runs[-1]["zt"] = max(runs[-1]["zt"], zt)
                else: runs.append(dict(s0=s - 0.05, s1=s + 0.05, zb=zb, zt=zt))
            for rn in runs:
                o0, o1 = (0.002, 0.027) if not r["id"].startswith("R-stairwell") else (-0.016, -0.003)   # a stairwell's board is laid over the face (members cut flush in it)
                p0 = (ax + tx * rn["s0"] + nx_ * o0, ay + ty * rn["s0"] + ny_ * o0); p1 = (ax + tx * rn["s1"] + nx_ * o0, ay + ty * rn["s1"] + ny_ * o0)
                q0 = (ax + tx * rn["s0"] + nx_ * o1, ay + ty * rn["s0"] + ny_ * o1); q1 = (ax + tx * rn["s1"] + nx_ * o1, ay + ty * rn["s1"] + ny_ * o1)
                name = f"FS-headinfill-{r['id'][4:20]}-{i}-{int(rn['s0'] * 100)}"
                me = prism_mesh(name, [p0, p1, q1, q0], rn["zb"] - 0.01, rn["zt"] + 0.016, fin.get("FIN-WALL"))
                life = (N, finish_seq, None, None)
                extra.append(new_obj(name, me, "FIN-WALL", life, f"stud and plasterboard head infill closing the slot between the wall head and the "
                                     f"{r['id']} ceiling (row 213; typical)"))
                ninf += 1
    if ninf: log(f"finish: {ninf} wall-head infills closing slots under a ceiling (row 213)")
    # ---- 1b3. a wall lining that stops a few cm under the ceiling above it (the drawn 5.05 head under a 5.081 ceiling) leaves
    #           a slit showing the plate and rafter seats: the lining runs on up to the ceiling's underside (row 213)
    nrun = 0
    if lin_tree is not None:
        for ob, p in live_parts():
            pr = p["props"]
            if pr.get("group") != "wall_lining" or ob.name.startswith(("FS-", "SPEC-")): continue
            bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))); hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
            if min(hi.x - lo.x, hi.y - lo.y) > 0.03 or hi.z - lo.z < 1.0: continue
            along_x = (hi.x - lo.x) >= (hi.y - lo.y)
            L_ = (hi.x - lo.x) if along_x else (hi.y - lo.y)
            hits = []
            for k in range(max(3, int(L_ / 0.25))):
                f = (k + 0.5) / max(3, int(L_ / 0.25))
                q = Vector((lo.x + (hi.x - lo.x) * f if along_x else (lo.x + hi.x) / 2, (lo.y + hi.y) / 2 if along_x else lo.y + (hi.y - lo.y) * f, hi.z + 0.001))
                h = lin_tree.ray_cast(q, UP, 0.06)
                hits.append(h[0].z if h[0] is not None else None)
            if not hits or any(hz is None for hz in hits): continue
            ztop = min(hits)
            if ztop - hi.z < 0.004: continue
            name = f"FS-liningrun-{ob.name[:40]}"
            ins = 0.0008                                    # inset from the lining's faces: never coplanar with a board edge
            if along_x: me = box_mesh(name, lo.x, lo.y + ins, hi.z, hi.x, hi.y - ins, ztop - 0.004, fin.get("FIN-WALL"))
            else: me = box_mesh(name, lo.x + ins, lo.y, hi.z, hi.x - ins, hi.y, ztop - 0.004, fin.get("FIN-WALL"))
            life = (pr.get("stage_in", 1), pr.get("seq", 0.0) or 0.0, pr.get("stage_out"), pr.get("seq_out")) if N == 1 else \
                (max(N, pr.get("stage_in", 1)), finish_seq, pr.get("stage_out"), pr.get("seq_out"))
            extra.append(new_obj(name, me, "FIN-WALL", life, f"wall lining run on {1000 * (ztop - hi.z):.0f} mm up to the ceiling over {ob.name} (row 213; typical)"))
            nrun += 1
    if nrun: log(f"finish: {nrun} wall linings run on to the ceiling above them (row 213)")
    # ---- 1c. ceilings at different heights meet at a boxed step (CORRECTIONS-LOG 214): a beam's boxing beside a ceiling lining
    #          comes down past that lining's underside and laps its edge, so no member, joist side or slot shows between them
    linings = []
    for ob, p in live_parts():
        if ob.name.startswith("CL-") and p["props"].get("group") == "ceiling_joist":
            bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
            linings.append((ob.name, Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))), Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))))
    for bx_ in boxes:
        e = 0.0275
        x0, y0, z0, x1, y1 = bx_["lo"].x - e, bx_["lo"].y - e, bx_["lo"].z - e, bx_["hi"].x + e, bx_["hi"].y + e
        for nm_, llo, lhi in linings:
            if abs(llo.z - z0) > 0.10: continue
            ovx = min(x1, lhi.x) - max(x0, llo.x); ovy = min(y1, lhi.y) - max(y0, llo.y)
            near = False
            if ovy > 0.05:
                if 0 <= llo.x - x1 <= 0.06: x1 = llo.x + 0.01; near = True
                elif 0 <= x0 - lhi.x <= 0.06: x0 = lhi.x - 0.01; near = True
            if ovx > 0.05:
                if 0 <= llo.y - y1 <= 0.06: y1 = llo.y + 0.01; near = True
                elif 0 <= y0 - lhi.y <= 0.06: y0 = lhi.y - 0.01; near = True
            if near and llo.z - 0.005 < z0:
                z0 = llo.z - 0.005; bx_.setdefault("step", []).append(nm_)
        bx_["final"] = (x0, y0, z0, x1, y1)
    for bx_ in boxes:
        e = 0.0275; lo, hi = bx_["lo"], bx_["hi"]
        name = f"FS-boxing-{bx_['names'][0][:40]}"
        x0, y0, z0, x1, y1 = bx_["final"]
        if bx_.get("step"): log(f"finish: {name} made a boxed step with {bx_['step']} (row 214)")
        me = box_mesh(name, x0, y0, z0, x1, y1, bx_["top"], fin.get("FIN-CEIL"))
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
    mat_shell, grp_shell = [], []
    for ob, p in lp_shell:
        for pl in ob.data.polygons:
            m_ = ob.data.materials[pl.material_index] if pl.material_index < len(ob.data.materials) else None
            mat_shell.append(m_.name if m_ else ""); grp_shell.append(p["props"].get("group", ""))
    filled = {}                     # one world grid for every room: two rooms' bands never lay boards over each other
    for r in spec_rooms:
        if BARE_ROOMS.search(r["id"]): continue
        if isinstance(r["ceiling_y"], (int, float)): cy = float(r["ceiling_y"])
        else:
            mm_ = re.match(r"\s*([\d.]+) above FFL where flat", str(r["ceiling_y"]))        # flat with a lower slope: the flat part is filled
            if not mm_: continue
            cy = r["floor_y"] + float(mm_.group(1))
        P = [(x, -z) for (x, z) in r["polygon"]]
        xs = [q[0] for q in P]; ys = [q[1] for q in P]; st = 0.05
        ox = math.floor((min(xs) - 0.15) / st) * st; oy = math.floor((min(ys) - 0.15) / st) * st
        gi0, gj0 = int(round(ox / st)), int(round(oy / st)); lvl = round(r["floor_y"], 1)      # per storey
        nx_, ny_ = int((max(xs) + 0.15 - ox) / st) + 1, int((max(ys) + 0.15 - oy) / st) + 1
        need = {}                   # cell -> the board's top: the drawn height, or just under a flat roof that sits lower
        ceiled = set()              # cells under an existing ceiling at the drawn height (the boards lap under these)
        for i in range(nx_):
            for j in range(ny_):
                if (gi0 + i, gj0 + j, lvl) in filled: continue
                x = ox + (i + 0.5) * st; y = oy + (j + 0.5) * st
                # the room and a 200 mm band round it: a wall the scheme takes out leaves its footprint between two rooms
                # with no ceiling over it (row 191 walk inspection: the After landing showed the roof void through it)
                inside = _in_poly(x, y, P)
                if not (inside or _dist_edge(x, y, P) < 0.2) or (r["floor_y"] < 1.0 and any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in stair_bb)): continue
                if not inside:              # a band cell counts only where it is open to the room (no wall, lining or cavity)
                    best_ = None
                    for k_ in range(len(P)):
                        (ax, ay), (bx, by) = P[k_], P[(k_ + 1) % len(P)]
                        L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1e-12
                        t_ = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2))
                        qx, qy = ax + t_ * (bx - ax), ay + t_ * (by - ay); dd = math.hypot(qx - x, qy - y)
                        if best_ is None or dd < best_[0]: best_ = (dd, qx, qy)
                    dv = Vector((best_[1] - x, best_[2] - y, 0))
                    if dv.length < 1e-6: continue
                    dv.normalize(); o_ = Vector((x, y, r["floor_y"] + 1.2))
                    if tree_shell.ray_cast(o_, dv, best_[0] + 0.05)[0] is not None or tree_shell.ray_cast(o_, -dv, 0.02)[0] is not None: continue
                for (ox_, oy_) in ((0, 0), (-0.45, -0.45), (0.45, -0.45), (0.45, 0.45), (-0.45, 0.45)):
                    h = tree_shell.ray_cast(Vector((x + ox_ * st, y + oy_ * st, r["floor_y"] + 1.2)), Vector((0, 0, 1)), 8.0)
                    if h[0] is None or h[0].z > cy + 0.02 or (h[0].z > cy - 0.03 and RAW.match(mat_shell[h[2]])):
                        need[(i, j)] = min(need.get((i, j), cy), cy); break
                    # a flat roof lower than the drawn ceiling (the old outshot's felt roof at 2.16 under a drawn 2.43): its
                    # underside showed in the rooms below. The ceiling goes on under the roof instead (row 191, walk inspection)
                    if abs(h[0].z - cy) <= 0.02 and h[1].z < -0.7 and ox_ == 0 and oy_ == 0: ceiled.add((i, j))
                    if inside and h[0].z <= cy - 0.03 and h[1].z < -0.9 and grp_shell[h[2]] in ("roof_cover", "roof_layer"):
                        need[(i, j)] = min(need.get((i, j), cy), round(h[0].z, 4))
        # greedy rectangles, one height at a time
        allneed = dict(need)
        for (i_, j_), hz_ in need.items(): filled[(gi0 + i_, gj0 + j_, lvl)] = hz_
        while need:
            i0, j0 = min(need); hz = need[(i0, j0)]
            i1 = i0
            while need.get((i1 + 1, j0)) == hz: i1 += 1
            j1 = j0
            while all(need.get((ii, j1 + 1)) == hz for ii in range(i0, i1 + 1)): j1 += 1
            for ii in range(i0, i1 + 1):
                for jj in range(j0, j1 + 1): need.pop((ii, jj), None)
            x0 = ox + i0 * st; x1 = ox + (i1 + 1) * st; y0 = oy + j0 * st; y1 = oy + (j1 + 1) * st
            # boards lap 10 mm under the ceilings they meet: butted on the 50 mm grid they left slits the roof void showed
            # through (row 191 walk inspection: After landing)
            # (only on edges that meet something else, never over the next fill board: coplanar laps z-fight)
            lap = lambda cells: any(c_ in ceiled for c_ in cells) and not any(c_ in allneed for c_ in cells)
            if lap([(i0 - 1, jj) for jj in range(j0, j1 + 1)]): x0 -= 0.01      # toward an existing ceiling only, never
            if lap([(i1 + 1, jj) for jj in range(j0, j1 + 1)]): x1 += 0.01      # over the next fill board (coplanar laps
            if lap([(ii, j0 - 1) for ii in range(i0, i1 + 1)]): y0 -= 0.01      # z-fight)
            if lap([(ii, j1 + 1) for ii in range(i0, i1 + 1)]): y1 += 0.01
            name = f"FS-ceiling-{r['id']}-{nfill}"
            me = box_mesh(name, x0, y0, hz - 0.0133, x1, y1, hz - 0.0008, fin.get("FIN-CEIL")) if hz < cy - 0.001 else \
                 box_mesh(name, x0, y0, cy - 0.004, x1, y1, cy - 0.0008, fin.get("FIN-CEIL"))
            life = (1, 0.0, None, None) if N == 1 else (N, finish_seq, None, None)
            what = f"at the drawn height {cy}" if hz >= cy - 0.001 else f"under the flat roof at {hz:.3f} (lower than the drawn {cy})"
            extra.append(new_obj(name, me, "FIN-CEIL", life, f"plasterboard ceiling {what} ({r['id']}; spec FIN-CEIL; row 191)"))
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
    # under the ground-floor stair (the void under flight 1, open to the cupboard once the soffit closes it): the treads stood
    # over the bare ground (walk inspection, 1 Nov: lawn seen through the cupboard door). The cupboard's floor runs under it.
    cup = next((r for r in spec_rooms if re.search(r"under.?stair", r["id"], re.I)), None)
    cfm_ = re.search(r"FIN-FLR-[A-Z]+", cup["finishes"].get("floor", "")) if cup else None
    for (bx0, by0, bx1, by1) in stair_bb:
        if not cfm_: break
        fy = cup["floor_y"]; st = 0.05
        nx_, ny_ = int((bx1 - bx0) / st) + 1, int((by1 - by0) / st) + 1
        need = set()
        for i in range(nx_):
            for j in range(ny_):
                x = bx0 + (i + 0.5) * st; y = by0 + (j + 0.5) * st
                h = tree_shell.ray_cast(Vector((x, y, fy + 0.05)), Vector((0, 0, -1)), 3.0)
                if h[0] is not None and h[1].z < -0.2: continue                      # inside the first tread / a wall
                if h[0] is None or h[0].z < fy - 0.03: need.add((i, j))
        rects = []
        while need:
            i0, j0 = min(need); i1 = i0
            while (i1 + 1, j0) in need: i1 += 1
            j1 = j0
            while all((ii, j1 + 1) in need for ii in range(i0, i1 + 1)): j1 += 1
            for ii in range(i0, i1 + 1):
                for jj in range(j0, j1 + 1): need.discard((ii, jj))
            rects.append((bx0 + i0 * st, by0 + j0 * st, bx0 + (i1 + 1) * st, by0 + (j1 + 1) * st))
        if rects:                                   # one object (Quest batches, row 187)
            fm = fin.get(cfm_.group(0)); tile = fin.tile.get(fm.name, (1, 1)); z0, z1 = fy - 0.03, fy - 0.001
            bm = bmesh.new(); uv = bm.loops.layers.uv.new("UVMap")
            for (x0, y0, x1, y1) in rects:
                vs = [bm.verts.new(v) for v in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
                for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
                    fa = bm.faces.new([vs[i] for i in f])
                    for l in fa.loops:
                        c = l.vert.co; nn = fa.normal
                        l[uv].uv = ((c.x / tile[0], c.y / tile[1]) if abs(nn.z) > 0.7 else ((c.x if abs(nn.y) > abs(nn.x) else c.y) / tile[0], c.z / tile[1]))
            name = f"FS-floor-under-stair-{nfl}"
            me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(fm)
            life = (1, 0.0, None, None) if N == 1 else (N, 0.7, None, None)
            extra.append(new_obj(name, me, cfm_.group(0), life, f"floor in {cfm_.group(0)} under the stair, as the cupboard ({cup['id']}; row 191)"))
            nfl += 1
    if nfl: log(f"finish: {nfl} floor patches where a room had no floor at its level")
    if nfill or nfl: tree = make_tree(live_parts())
    log(f"finish: {nbox} beams boxed, {nfill} ceiling boards where a room's ceiling was missing or higher than drawn")

    bare_rooms = []                                  # (rooms_blender leaves the bare rooms out)
    for r_ in spec_rooms:
        if not BARE_ROOMS.search(r_["id"]): continue
        P_ = [(x, -z) for (x, z) in r_["polygon"]]; xs_ = [q[0] for q in P_]; ys_ = [q[1] for q in P_]
        bare_rooms.append((r_["id"], P_, r_["floor_y"] - 0.05, r_["floor_y"] + 3.9, (min(xs_), min(ys_), max(xs_), max(ys_))))

    def in_bare(q):
        """a point in a room the spec keeps bare (the conservatory: face brick and dwarf walls), seen from anywhere"""
        for (rid, P, z0, z1, bb) in bare_rooms:
            if bb[0] <= q.x <= bb[2] and bb[1] <= q.y <= bb[3] and z0 - 0.3 < q.z < z1 + 0.3 and _in_poly(q.x, q.y, P): return True
        return False

    H8 = [Vector((math.cos(a_ * math.pi / 4), math.sin(a_ * math.pi / 4), 0.0)) for a_ in range(8)]

    def outdoors(q, n=None):
        """out in the open (the garden, the street): two of eight level rays escape within 8 m, or a wall face looks straight out. Interior skins never
        go on an outside wall face seen through an open doorway (row 191 walk inspection: No.21's and No.23's front walls
        took the porch's plaster as white patches)"""
        if sum(1 for d_ in H8 if tree.ray_cast(q, d_, 8.0)[0] is None) >= 2: return True     # (leaves and glass: closed)
        if n is not None and abs(n.z) < 0.3:        # a wall face looking straight out into the open
            return tree.ray_cast(q, Vector((n.x, n.y, 0)).normalized(), 8.0)[0] is None
        return False

    def close_to_room(q, tol=0.22):        # (unused now: the skins test outdoors instead)
        """in a finished room, or within tol of one in plan (a reveal, a slot, a wall end): never a face out in the garden
        or the street seen through an open doorway (row 191 walk inspection: No.21's front wall got the porch's plaster)"""
        for (bx0, by0, bx1, by1) in stair_bb:            # the stairwell is a finished space too (no room of its own)
            if bx0 - tol <= q.x <= bx1 + tol and by0 - tol <= q.y <= by1 + tol and -0.1 < q.z < 5.3: return True
        for (rid, P, z0, z1, bb) in rooms:
            if BARE_ROOMS.search(rid) or not (z0 - 0.3 < q.z < z1 + 0.3): continue
            if not (bb[0] - tol <= q.x <= bb[2] + tol and bb[1] - tol <= q.y <= bb[3] + tol): continue
            if _in_poly(q.x, q.y, P): return True
            n_ = len(P)
            for i_ in range(n_):
                (ax, ay), (bx, by) = P[i_], P[(i_ + 1) % n_]
                L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1e-12
                t_ = max(0.0, min(1.0, ((q.x - ax) * (bx - ax) + (q.y - ay) * (by - ay)) / L2))
                if math.hypot(ax + t_ * (bx - ax) - q.x, ay + t_ * (by - ay) - q.y) < tol: return True
        return False

    def room_at(q):
        for (rid, P, z0, z1, bb) in rooms:
            if BARE_ROOMS.search(rid): continue          # the spec keeps it bare (conservatory: face brick, dwarf walls): no skins
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
    n_faces = 0; n_outside = 0; n_buried = 0; per_room = {}
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
    lin_ = [(o_, p_) for o_, p_ in live_parts() if o_.name.startswith(("CL-", "XC-"))]
    lining_tree = make_tree(lin_) if lin_ else None

    def over_lining(ob, k):
        """a joist face resting on (or through) a ceiling lining is above the ceiling, not in the room: its skin (grown 20 mm
        past its edges) hung below the lining as white ribs (row 191 walk inspection: kitchen-diner and bedroom 3 ceilings)"""
        if lining_tree is None: return False
        M = ob.matrix_world; vs = [M @ ob.data.vertices[i].co for i in ob.data.polygons[k].vertices]
        c = sum(vs, Vector()) / len(vs); zmin = min(v.z for v in vs)
        return lining_tree.ray_cast(Vector((c.x, c.y, zmin + 0.002)), Vector((0, 0, -1)), 0.004)[0] is not None   # resting on it (+-2 mm)

    def add_face(ob, p, k, rid, at=None):
        """mark a face (small: whole) or the cells of a large face that are seen (at: a hit point; None: run the cell test)"""
        key = (ob.name, k)
        if p["props"].get("group") in ("ceiling_joist", "joist") and not ob.name.startswith(("CL-", "XC-")) and over_lining(ob, k): return
        pl = ob.data.polygons[k]
        if (ob.matrix_world.to_3x3() @ pl.normal).normalized().z > 0.7 and p["props"].get("group") in ("deck", "slab_layer", "floor_finish", "joist"): return
        area = pl.area * (ob.matrix_world.to_3x3().determinant() ** (2 / 3) if ob.matrix_world.to_3x3().determinant() > 0 else 1)
        rec = faces.get(key)
        if rec is None:
            if area <= 0.3:
                nn_ = (ob.matrix_world.to_3x3() @ pl.normal).normalized()
                if not under_cover(ob.matrix_world @ pl.center + nn_ * 0.008): return
                if in_bare(ob.matrix_world @ pl.center + nn_ * 0.05) or outdoors(ob.matrix_world @ pl.center + nn_ * 0.05, nn_): return
            rec = faces[key] = dict(ob=ob, p=p, rid=rid, cells=None if area <= 0.3 else set(), fr=None if area <= 0.3 else frame_of(ob, k))
        if rec["cells"] is None: return
        fr = rec["fr"]
        if at is not None:
            if in_bare(at + fr["n"] * 0.05) or outdoors(at + fr["n"] * 0.05, fr["n"]): return
            d_ = at - fr["o"]; i = int((d_.dot(fr["u"]) - fr["u0"]) / CELL); j = int((d_.dot(fr["v"]) - fr["v0"]) / CELL)
            i, j = min(max(i, 0), fr["nu"] - 1), min(max(j, 0), fr["nv"] - 1)
            if (i, j) in rec["cells"]: return
            rec["cells"].add((i, j))
            for di in (-1, 0, 1):                 # a grazing ray lands near a cell edge: the neighbours that are in the room too
                for dj in (-1, 0, 1):
                    ii, jj = i + di, j + dj
                    if (ii, jj) in rec["cells"] or not (0 <= ii < fr["nu"] and 0 <= jj < fr["nv"]): continue
                    cc = fr["o"] + fr["u"] * (fr["u0"] + (ii + 0.5) * CELL) + fr["v"] * (fr["v0"] + (jj + 0.5) * CELL)
                    if room_at(cc + fr["n"] * 0.06) and under_cover(cc + fr["n"] * 0.06) and not in_bare(cc + fr["n"] * 0.06): rec["cells"].add((ii, jj))
            return
        for i in range(fr["nu"]):
            for j in range(fr["nv"]):
                if (i, j) in rec["cells"]: continue
                ua = fr["u0"] + i * CELL; ub = min(fr["u1"], ua + CELL); va = fr["v0"] + j * CELL; vb = min(fr["v1"], va + CELL)
                cc = fr["o"] + fr["u"] * ((ua + ub) / 2) + fr["v"] * ((va + vb) / 2)
                if not _in_poly((ua + ub) / 2, (va + vb) / 2, fr["poly2"]): continue
                smp = [cc] + [fr["o"] + fr["u"] * (ua + (ub - ua) * a_) + fr["v"] * (va + (vb - va) * b_) for a_, b_ in ((0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8))]
                if under_cover(cc + fr["n"] * 0.05) and not in_bare(cc + fr["n"] * 0.05) and seen(smp, fr["n"]): rec["cells"].add((i, j))
    _seam = {}
    def seam_tree(asb):
        if asb not in _seam:
            it_ = [(o_, p_) for o_, p_ in objs if o_.type == "MESH" and not p_.get("context") and not o_.name.startswith(("FS-", "SPEC-", "XFD-", "JN-"))
                   and o_.name.startswith("AB-") == asb and p_["props"].get("group") in ("wall_outer", "wall_inner", "wall_cavity", "wall_insulation", "foundation", "lintel", "steel", "timber_beam", "wall_lining")]
            _seam[asb] = make_tree(it_) if it_ else None
        return _seam[asb]
    def emit():
        nonlocal n_faces, n_outside, n_buried
        for key, rec in faces.items():
            ob, p = rec["ob"], rec["p"]; k = key[1]
            pr = p["props"]; g = pr.get("group", "")
            M = ob.matrix_world; R = M.to_3x3().normalized(); pl = ob.data.polygons[k]
            n = (R @ pl.normal).normalized(); c = M @ pl.center
            down = n.z < -0.7
            # Jack's walk 2 (F99, row 295): a skin is a room's plaster, never an outer face. A wall face that looks straight out into the
            # open (nothing within 8 m along its horizontal normal) is an outside face: the front, party, porch and wing walls, the
            # porch step. It keeps its brick/render. (Large faces were never tested once their cells were gathered.)
            # (the 8 m 'looks straight out' ray veto was dropped: it also stripped the plaster from faces looking through the porch's open front and
            #  the stair void: 16 raw faces back in the shell gate. Wall CELLS are now filtered by 'a finished room is on the normal side' in emit's cell branch.)
            # a face buried against a neighbouring solid of its own layer (the seam between two wall lifts, a lintel's end in the
            # wall): not an exposed surface at all, and its skin (grown 4-20 mm past the face's edge) poked out of the wall as white
            # patches and strips on the outer brick (walk 2: the porch, the party wall, the wing). Start 0.4 mm out along the normal: if
            # that point is inside a solid, the first surface met looks along the ray (a front face), not back at it.
            if g != "ground" and not rec.get("exact"):
                st_ = seam_tree(ob.name.startswith("AB-"))
                if st_ is not None:
                    h_ = st_.ray_cast(c + n * 0.0004, n, 3.0)
                    if h_[0] is not None and h_[1] is not None and h_[1].dot(n) > 0.2:
                        n_buried += 1; continue
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
            if rec.get("exact"):
                vs0 = [M @ ob.data.vertices[i].co for i in pl.vertices]
                m0 = len(vs0); sg0 = 1 if sum(((vs0[(i + 1) % m0] - vs0[i]).cross(vs0[(i + 2) % m0] - vs0[(i + 1) % m0])).dot(n) for i in range(m0)) >= 0 else -1
                outs0 = [((vs0[(i + 1) % m0] - vs0[i]).cross(n).normalized() * sg0 if (vs0[(i + 1) % m0] - vs0[i]).length > 1e-9 else Vector((0, 0, 0))) for i in range(m0)]
                vg = []
                for i in range(m0):                                   # 4 mm in-plane growth: neighbouring skins meet at the corners (no hairline of brick), no wrap onto the next surface
                    bis0 = outs0[i - 1] + outs0[i]
                    if bis0.length < 1e-6: vg.append(vs0[i]); continue
                    bis0.normalize(); vg.append(vs0[i] + bis0 * (0.004 / max(0.35, bis0.dot(outs0[i]))))
                groups.setdefault(life + (finish,), []).append(([v + n * off for v in vg], ob.name))
                n_faces += 1; per_room[rec["rid"]] = per_room.get(rec["rid"], 0) + 1
                continue
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
                if abs(n.z) < 0.3:       # row 295: a wall cell is a room's plaster only if the room is on its normal side (10 cm in front of it is inside a finished room)
                    keep_ = set()
                    for (ci_, cj_) in need:
                        cc_ = fr["o"] + fr["u"] * (fr["u0"] + (ci_ + 0.5) * CELL) + fr["v"] * (fr["v0"] + (cj_ + 0.5) * CELL)
                        if room_at(cc_ + fr["n"] * 0.10) is not None: keep_.add((ci_, cj_))
                        else: n_outside += 1
                    need = keep_
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
            if in_bare(c + n * 0.05): continue                # a face of the conservatory (face brick): seen through a door, still bare
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
                if in_bare(h[0] - (h[0] - o).normalized() * 0.05): continue            # seen through the doors into the conservatory: bare by spec
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
    # ---- 4. the reveal sweep (round-1 sweep, PLAN S3 "every reveal plastered, head and sill"). Passes 1-3 test what a ray sees in
    #         the LIVE tree, which keeps only the as-built records and drops the drawn parts they replace; the viewer shows the DRAWN
    #         layer unless As built is switched on, so the drawn wall's reveals (head, one jamb) and wall ends were never tested and
    #         stayed raw brick, block or insulation. Here every small raw face INSIDE THE WALL THICKNESS of a finished room (within
    #         22 cm of its wall line, not pointing away from the room, not out in the open, not in a room kept bare) is finished,
    #         drawn and as-built layers alike, whether or not a sampled ray saw it.
    def _nearest(x, y, P):
        best, bp = 9e9, (x, y)
        for i_ in range(len(P)):
            (x1, y1), (x2, y2) = P[i_], P[(i_ + 1) % len(P)]
            dx, dy = x2 - x1, y2 - y1; L2 = dx * dx + dy * dy or 1e-12
            t_ = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
            qx, qy = x1 + t_ * dx, y1 + t_ * dy; d_ = math.hypot(x - qx, y - qy)
            if d_ < best: best, bp = d_, (qx, qy)
        return best, bp

    def wall_zone(c, n, reach=0.22):
        for (rid, P, z0, z1, bb) in rooms:
            if not (z0 < c.z < z1) or not (bb[0] <= c.x <= bb[2] and bb[1] <= c.y <= bb[3]): continue
            if _in_poly(c.x, c.y, P): continue                    # inside the room: passes 1-3 own it
            d_, (qx, qy) = _nearest(c.x, c.y, P)
            if d_ > reach: continue
            nh = Vector((n.x, n.y, 0.0))
            if nh.length > 0.3 and nh.normalized().dot(Vector((qx - c.x, qy - c.y, 0.0)).normalized()) < -0.15: continue   # facing away from the room (row 295: was -0.5, which let outer-leaf ends and steps through)
            return rid
        return None
    lin_cover = make_tree([(o_, p_) for o_, p_ in live_parts() if p_["props"].get("group") == "wall_lining"])
    SOLID_GROUPS = {"wall_inner", "wall_outer", "wall_cavity", "wall_insulation", "foundation", "lintel", "steel", "timber_beam"}
    nrev = 0; _dbg_rev = []
    for ob, p in objs:
        if ob.type != "MESH" or ob.name.startswith(("FS-", "SPEC-", "XFD-", "JN-")): continue
        pr = p["props"]; g = pr.get("group", "")
        if p.get("context") or pr.get("spec_id") or g in ("ground", "window", "door", "rooflight", "fitting", "glass", "roof_cover", "ridge", "finish_skin"): continue
        if (pr.get("stage_out") or 99) <= N: continue
        mats = ob.data.materials
        if not mats or not any(m and RAW.match(m.name) for m in mats): continue
        M = ob.matrix_world; R = M.to_3x3().normalized()
        for pl in ob.data.polygons:
            m = mats[pl.material_index] if pl.material_index < len(mats) else None
            if not m or not RAW.match(m.name) or (ob.name, pl.index) in faces: continue
            if pl.area > 0.6 or pl.area < 1e-5: continue
            c = M @ pl.center; n = (R @ pl.normal).normalized()
            if m.name.startswith(("existing_floor", "floor_finish")) and n.z > -0.5: continue
            rid = wall_zone(c, n)
            if rid is None or in_bare(c + n * 0.05) or outdoors(c + n * 0.05, n): continue
            if lin_cover.ray_cast(c + n * 0.0003, n, 0.002)[0] is not None: continue       # a lining's own face stands within 2 mm in front of it (flush): a second skin would z-fight with it
            if pl.area > 0.3:                                  # a full-height wall end (0.3-0.6 m2): the whole face, as an exact skin (the cell test is for big flat faces)
                faces[(ob.name, pl.index)] = dict(ob=ob, p=p, rid=rid, cells=None, fr=None, exact=True); nrev += 1
                if os.environ.get("HB_DEBUG_REVEAL"): _dbg_rev.append((ob.name, g, rid, round(pl.area, 3), [round(x, 2) for x in c], [round(x, 2) for x in n]))
                continue
            add_face(ob, p, pl.index, rid)
            if (ob.name, pl.index) in faces and g in SOLID_GROUPS: faces[(ob.name, pl.index)]["exact"] = True    # a closed wall solid keeps its own faces: the finish is a separate skin, never a material swap on the solid (it split the part into two primitives: integrity open_shell)
            if os.environ.get("HB_DEBUG_REVEAL"): _dbg_rev.append((ob.name, g, rid, round(pl.area, 3), [round(x, 2) for x in c], [round(x, 2) for x in n]))
            nrev += 1
    log(f"finish: {nrev} raw faces inside the wall thickness of finished rooms (reveals, wall ends, heads, both layers) covered")
    if os.environ.get("HB_DEBUG_REVEAL"):
        _all = []
        for (nm_, k_), rec in faces.items():
            o_ = rec["ob"]; pl_ = o_.data.polygons[k_]; M_ = o_.matrix_world
            c_ = M_ @ pl_.center; n_ = (M_.to_3x3().normalized() @ pl_.normal).normalized()
            _all.append((nm_, rec["p"]["props"].get("group", ""), rec["rid"], round(pl_.area, 3), [round(x, 2) for x in c_], [round(x, 2) for x in n_], 1 if rec.get("cells") is not None and rec.get("fr") else 0))
        json.dump(dict(rev=_dbg_rev, all=_all), open(os.environ["HB_DEBUG_REVEAL"], "w"))
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
    log(f"finish skins: {n_outside} outside-looking and {n_buried} buried (seam) faces left unskinned (row 295); {n_faces} construction faces seen from finished rooms covered, {len(out)} merged objects; by room {per_room}")
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
