"""Structural closures and trim junctions. Room finish ownership is authored by hb_room_faces.
"""
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


def opening_box_joint(bounds, head_z, surfaces):
    """Join a boxed beam to a scheduled wall head. Return the boxing footprint
    and the existing longitudinal head faces that need thicker backing."""
    x0,y0,_,x1,y1=bounds
    for head in surfaces:
        if not head['soffit'] or abs(head['hi'][2]-head_z)>.006:continue
        along=0 if head['hi'][0]-head['lo'][0]>head['hi'][1]-head['lo'][1] else 1
        cross=1-along
        lower=(x0,y0);upper=(x1,y1)
        if min(upper[along],head['hi'][along])-max(lower[along],head['lo'][along])<.15:continue
        mid=(lower[cross]+upper[cross])/2
        if not head['lo'][cross]<=mid<=head['hi'][cross]:continue
        ends=[head['lo'][along],head['hi'][along]]
        for wall in surfaces:
            if not wall['end'] or wall['lo'][2]>=bounds[2] or wall['hi'][2]<head_z-.006:continue
            if min(wall['hi'][cross],upper[cross])-max(wall['lo'][cross],lower[cross])<=0:continue
            if abs(wall['hi'][along]-ends[0])<.003:ends[0]=max(ends[0],wall['hi'][along])
            if abs(wall['lo'][along]-ends[1])<.003:ends[1]=min(ends[1],wall['lo'][along])
        if not lower[along]<=ends[0]<ends[1]<=upper[along]:continue
        sides=[lower[cross],upper[cross]]; thickened=[]
        for face in surfaces:
            if face['carrier']!=head['carrier'] or not face['wall'] or abs(face['lo'][2]-head_z)>.006:continue
            line=(face['lo'][cross]+face['hi'][cross])/2
            side=1 if line>mid else -1
            key='hi' if side==1 else 'lo'
            old=face[key][cross];datum=old
            # A retained pier still runs to the floor. Its room-side plane
            # sets the outer face of the board over the adjoining opening.
            for pier in surfaces:
                if not pier['wall'] or pier['carrier']==head['carrier'] or pier['room']!=face['room']:continue
                if pier['lo'][2]>=bounds[2] or pier['hi'][2]<head_z+.02:continue
                if pier['hi'][cross]-pier['lo'][cross]>.035:continue
                if min(abs(pier['lo'][along]-face['hi'][along]),abs(pier['hi'][along]-face['lo'][along]))>.003:continue
                at=pier[key][cross]
                if .002<side*(at-old)<.035 and side*(at-datum)>0:datum=at
            if datum!=old:thickened.append((face,cross,old,datum))
            i=int(side>0)
            if side*(datum-sides[i])>.002:sides[i]=datum
        # The designed fire enclosure at either bearing remains intact.
        outline=[]
        for i,(start,stop) in enumerate(((lower[along],upper[along]),(upper[along],lower[along]))):
            edge=(lower,upper)[i][cross];run=[(start,edge)]
            if sides[i]!=edge:
                a,b=ends if i==0 else ends[::-1]
                run.extend(((a,edge),(a,sides[i]),(b,sides[i]),(b,edge)))
            run.append((stop,edge));outline.extend(run)
        return (outline if along==0 else [(y,x) for x,y in outline]),thickened
    return None,[]


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
            if pr.get("group") != "wall_lining" or ob.name.startswith(("FS-", "SPEC-", "RL-")): continue
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
    surfaces=[]
    for ob,p in live_parts():
        pr=p['props'];atom=p.get('atom',{});carrier=atom.get('carrier');face=pr.get('surface_id','').split('/')[-1]
        wall=face in ('1','-1');end=face in ('end1','end-1');soffit=pr.get('plain_label')=='Painted opening soffit'
        if not carrier or not (wall or end or soffit):continue
        bb=[ob.matrix_world @ Vector(v) for v in ob.bound_box]
        surfaces.append(dict(ob=ob,carrier=carrier,room=pr.get('room_id'),wall=wall,end=end,soffit=soffit,
                             lo=tuple(min(v[j] for v in bb) for j in range(3)),hi=tuple(max(v[j] for v in bb) for j in range(3))))
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
        outline,fur=opening_box_joint(bx_['final'],bx_['top'],surfaces)
        for panel,axis,old,datum in fur:
            ob=panel['ob'];world=ob.matrix_world;local=world.inverted()
            if ob.data.users>1:ob.data=ob.data.copy()
            for v in ob.data.vertices:
                p=world @ v.co
                if abs(p[axis]-old)<.00002:
                    p[axis]=datum;v.co=local @ p
            ob.data.update()
        mat=fin.get('FIN-CEIL')
        me = prism_mesh(name,outline,z0,bx_['top'],mat) if outline else box_mesh(name,x0,y0,z0,x1,y1,bx_['top'],mat)
        extra.append(new_obj(name, me, "FIN-CEIL", bx_["life"], f"plasterboard boxing round {', '.join(bx_['names'])} (12.5 mm board on battens, painted FIN-CEIL; typical)"))
        nbox += 1
    log(f"finish: {nbox} boxed beams; horizontal finishes constructed from the schedule")
    return extra


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


def scribe_to_room_finish(trim,linings):
    """Cut a moulding back to an intersecting room lining, as a joiner scribes the profile."""
    def geometry(ob):
        vs=[ob.matrix_world@v.co for v in ob.data.vertices]
        return vs,[tuple(p.vertices) for p in ob.data.polygons]
    tv,tf=geometry(trim)
    lo=[min(v[i] for v in tv) for i in range(3)];hi=[max(v[i] for v in tv) for i in range(3)]
    tree=BVHTree.FromPolygons(tv,tf)
    for ob,mn,mx in linings:
        if min(min(hi[i],mx[i])-max(lo[i],mn[i]) for i in range(3))<.0038:continue
        lv,lf=geometry(ob)
        if not tree.overlap(BVHTree.FromPolygons(lv,lf)):continue
        cutter=ob.copy();cutter.data=ob.data.copy()
        for v in cutter.data.vertices:v.co+=v.normal*.0005
        cutter.data.update();trim.users_collection[0].objects.link(cutter)
        mod=trim.modifiers.new('Scribe architrave to finished return','BOOLEAN');mod.operation='DIFFERENCE';mod.object=cutter
        deps=bpy.context.evaluated_depsgraph_get()
        clipped=bpy.data.meshes.new_from_object(trim.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps)
        trim.modifiers.remove(mod);bpy.data.objects.remove(cutter,do_unlink=True)
        if not clipped.polygons:
            bpy.data.meshes.remove(clipped);print('Scribe retained original at coplanar contact:',trim.name,ob.name);continue
        trim.data=clipped
        tv,tf=geometry(trim);tree=BVHTree.FromPolygons(tv,tf)

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
    linings=[]
    for ob,p in objs:
        if ob.type=='MESH' and p['props'].get('surface_role')=='wall' and not p['props'].get('as_built'):
            verts=[ob.matrix_world@v.co for v in ob.data.vertices]
            linings.append((ob,[min(v[k] for v in verts) for k in range(3)],[max(v[k] for v in verts) for k in range(3)]))
    for ob,p in objs:
        if ob.name.endswith('_architraves') and not p['props'].get('as_built'):scribe_to_room_finish(ob,linings)
    structure=[]
    for ob,p in objs:
        props=p['props']
        if ob.type!='MESH' or props.get('stage_out') or props.get('context') or props.get('group') not in ('wall_outer','wall_inner','wall_plate'):continue
        v=[ob.matrix_world@q.co for q in ob.data.vertices]
        if v:structure.append((props.get('element'),ob,[min(q[k] for q in v) for k in range(3)],[max(q[k] for q in v) for k in range(3)]))
    for ob,p in objs:
        cut=p.get('atom') or {}
        if cut.get('scribe_neighbours'):
            scribe_to_room_finish(ob,[(part,lo,hi) for host,part,lo,hi in structure if host!=cut['carrier']])
    valleys=[]
    for ob,p in objs:
        if ob.type=='MESH' and p['props'].get('group')=='valley' and not p['props'].get('stage_out'):
            v=[ob.matrix_world@q.co for q in ob.data.vertices]
            valleys.append((ob,[min(q[k] for q in v) for k in range(3)],[max(q[k] for q in v) for k in range(3)]))
    for ob,p in objs:
        if ob.name.startswith('RCF-WP-'):scribe_to_room_finish(ob,valleys)
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
