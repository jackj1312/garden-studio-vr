"""Services finished at the wall (WORKFLOW G5c 'Services'; DETAIL-CHECKLIST 'Interior finish': switches ~1.2 m, sockets 450 mm,
smoke alarms on the hall and landing ceilings). The signed spec does not schedule them, so they are placed as presumed facts
(WORKFLOW 'Presumed facts': UK typical), every one labelled "typical": a light switch on the wall beside each doorway of a
room (latch side where there is wall, 150 mm off the lining, centre 1.2 m), double sockets at 450 mm near the room's corners
(living/kitchen 4, bedrooms 2, halls 1; over the worktop at 1.1 m in a kitchen), an optical smoke alarm on the hall and landing
ceilings. White plates (RAL 9016, the spec's own white for trims and mounts). Fixed fittings: never furnishing."""
import math, re
import bpy, bmesh
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

SOCKETS = {"kitchen": 4, "living": 4, "bed": 2, "hall": 1, "bath": 0, "store": 0}
ROOM_TYPE = [("store", re.compile(r"utility|cpd|store|cupboard|conservatory", re.I)), ("kitchen", re.compile(r"kitchen", re.I)),
             ("bath", re.compile(r"bath|en-suite|ensuite|cloaks-WC|cloaks$|WC", re.I)), ("bed", re.compile(r"bedroom", re.I)),
             ("living", re.compile(r"living|sitting|lounge|dining", re.I)), ("hall", re.compile(r"hall|landing|lobby|porch", re.I))]


def rtype(rid):
    return next((t for t, rx in ROOM_TYPE if rx.search(rid)), "store")


def _in_poly(x, y, P):
    c = False; n = len(P)
    for i in range(n):
        (x1, y1), (x2, y2) = P[i], P[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1: c = not c
    return c


def _ccw(P):
    a = sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))
    return P if a >= 0 else P[::-1]


def _plate(name, w, h, d, kind, mat_w, mat_d):
    """a plate in its local frame: X across, Y out of the wall (front +Y), Z up; centred on (0, 0, 0) at the wall face"""
    bm = bmesh.new()
    def cube(x0, x1, y0, y1, z0, z1, mi, bev=0.0):
        r = bmesh.ops.create_cube(bm, size=1.0)
        vs = r["verts"]
        for v in vs: v.co = Vector(((x0 + x1) / 2 + v.co.x * (x1 - x0), (y0 + y1) / 2 + v.co.y * (y1 - y0), (z0 + z1) / 2 + v.co.z * (z1 - z0)))
        fs = list({f for v in vs for f in v.link_faces})
        for f in fs: f.material_index = mi
        if bev: bmesh.ops.bevel(bm, geom=list({e for v in vs for e in v.link_edges}), offset=bev, segments=2, affect="EDGES", profile=0.5, clamp_overlap=True)
    cube(-w / 2, w / 2, 0.0, d, -h / 2, h / 2, 0, 0.002)
    if kind == "switch":
        cube(-0.012, 0.012, d, d + 0.004, -0.018, 0.018, 0, 0.0015)
    elif kind == "socket":
        for sx in (-1, 1):
            cube(sx * 0.035 - 0.005, sx * 0.035 + 0.005, d, d + 0.003, 0.012, 0.024, 0, 0.001)            # rocker
            for (px, pz) in ((sx * 0.035 - 0.012, -0.006), (sx * 0.035 + 0.012, -0.006), (sx * 0.035, 0.002)):
                cube(px - 0.0025, px + 0.0025, d - 0.0005, d + 0.0005, pz - 0.004, pz + 0.004, 1)         # pin slots
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(mat_w); me.materials.append(mat_d)
    for p in me.polygons: p.use_smooth = False
    return me


ITEMS = {}; N_KEY = [None]


def services(objs, spec_rooms, fin, N, log, spec_items=None):
    ITEMS["v"] = spec_items or []; N_KEY[0] = "v"
    coll = objs[0][0].users_collection[0]
    live = [(ob, p) for ob, p in objs if ob.type == "MESH" and not p.get("context") and (p["props"].get("stage_out") or 99) > N
            and not p["props"].get("door_leaf") and not (ob.name.startswith("SPEC-") and not ob.name.startswith(("SPEC-FLR", "SPEC-SKIRT")))]
    V, T, own = [], [], []
    for ob, p in live:
        M = ob.matrix_world; b = len(V)
        V.extend(M @ v.co for v in ob.data.vertices)
        for pl in ob.data.polygons: T.append(tuple(b + i for i in pl.vertices)); own.append((ob, p))
    tree = BVHTree.FromPolygons(V, T)
    doors = []
    for ob, p in objs:
        if ob.type != "MESH" or not p["props"].get("door_leaf") or (p["props"].get("stage_out") or 99) <= N: continue
        bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        doors.append((Vector((sum(v.x for v in bb) / 8, sum(v.y for v in bb) / 8, min(v.z for v in bb))), max(max(v.x for v in bb) - min(v.x for v in bb), max(v.y for v in bb) - min(v.y for v in bb))))
    kitchen_units = []
    for ob, p in objs:
        if ob.name.startswith("SPEC-") and p["props"].get("spec_kind") == "kitchen_unit":
            bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]; kitchen_units.append((min(v.x for v in bb), min(v.y for v in bb), max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
    white = fin.get("RAL9016"); dark = fin.get("c:#2A2A2A:0.5:0")
    out = []
    def wall_hit(q, d, dist=0.16):
        h = tree.ray_cast(q, d, dist)
        if h[0] is None: return None
        ob, p = own[h[2]]
        g = p["props"].get("group", "")
        if g in ("window", "glass", "door", "rooflight") or "glass" in ob.name.lower(): return None
        return h
    def add(name, me, M, label, plain):
        ob = bpy.data.objects.new(name, me); ob.matrix_world = M
        props = dict(element=name, group="fitting", stage_in=N, seq=0.96 if N > 1 else 0.0, category="finish" if N > 1 else "existing",
                     storey="first" if M.translation.z > 2.0 else "ground", label=label, plain_label=plain, drawing="typical (not on the drawings or the spec)",
                     conf="assumed", provenance="typical", collide=False)
        for k, v in props.items(): ob[k] = v
        coll.objects.link(ob); out.append((ob, dict(props=props, spec=True, atom=dict(id=name, kind="fitting", meta=props, provenance="typical"))))
    placed_pts = []
    def clear_of_openings(h, z, w=0.16):
        """no plate within a window board's or frame's reach (rays just above, below and to the sides of the plate)"""
        nrm = Vector((h[1].x, h[1].y, 0)).normalized(); tx = Vector((-nrm.y, nrm.x, 0))
        for dz in (-0.07, 0.0, 0.08):
            for dx in (-w / 2 - 0.03, 0.0, w / 2 + 0.03):
                q = Vector((h[0].x, h[0].y, z + dz)) + nrm * 0.08 + tx * dx
                hh = tree.ray_cast(q, -nrm, 0.12)
                if hh[0] is None: return False
                ob_, p_ = own[hh[2]]
                if ob_.name.startswith(("WB-", "JN-")) or p_["props"].get("group", "") in ("window", "glass", "door") or "frame" in ob_.name: return False
        return all((Vector((h[0].x, h[0].y, z)) - q_).length > 0.25 for q_ in placed_pts)
    def plate_at(h, z, name, kind, label, plain):
        placed_pts.append(Vector((h[0].x, h[0].y, z)))
        nrm = Vector((h[1].x, h[1].y, 0)).normalized()
        yaw = math.atan2(-nrm.x, nrm.y)
        pos = Vector((h[0].x, h[0].y, z)) + nrm * 0.0015
        w, hh = (0.086, 0.086) if kind in ("switch",) else (0.146, 0.086)
        add(name, _plate(name, w, hh, 0.009, kind, white, dark), Matrix.Translation(pos) @ Matrix.Rotation(yaw, 4, "Z"), label, plain)
    nsw = nsk = nsm = 0
    for r in spec_rooms:
        rid = r["id"]
        if "conservatory" in rid: continue
        t = rtype(rid); fy = r["floor_y"]
        P = _ccw([(x, -z) for (x, z) in r["polygon"]])
        # switch beside each door into this room (only where the spec gives the room a light: a switch for no light is wrong)
        k = 0
        lit = any(i_["room"] == rid and i_["category"] == "lighting" for i_ in ITEMS.get(N_KEY[0], []))
        for (dc, dw) in (doors if lit else []):
            if abs(dc.z - fy) > 0.3: continue
            # nearest polygon edge to the door centre, within 0.35 m
            best = None
            for i in range(len(P)):
                (ax, ay), (bx, by) = P[i], P[(i + 1) % len(P)]
                L = math.hypot(bx - ax, by - ay)
                if L < 0.1: continue
                tx, ty = (bx - ax) / L, (by - ay) / L
                s = max(0.0, min(L, (dc.x - ax) * tx + (dc.y - ay) * ty))
                px, py = ax + tx * s, ay + ty * s
                d = math.hypot(dc.x - px, dc.y - py)
                if d < 0.55 and (best is None or d < best[0]): best = (d, i, s, tx, ty, L)
            if best is None: continue
            _, i, s, tx, ty, L = best
            (ax, ay) = P[i]; nx, ny = ty, -tx                    # outward normal
            placed = False
            for side, extra in ((1, 0.0), (-1, 0.0), (1, 0.12), (-1, 0.12), (1, 0.3), (-1, 0.3)):
                off = side * (dw / 2 + 0.08 + 0.15 + extra)
                if not (0.05 < s + off < L - 0.05): continue
                q = Vector((ax + tx * (s + off) - nx * 0.10, ay + ty * (s + off) - ny * 0.10, fy + 1.2))
                if not _in_poly(q.x, q.y, P): continue
                h = wall_hit(q, Vector((nx, ny, 0)))
                if h is None or not clear_of_openings(h, fy + 1.2, 0.086): continue
                plate_at(h, fy + 1.2, f"JN-SW-{rid}-{k}", "switch", f"light switch, white plate 86 mm, centre 1.2 m, beside the door ({rid}; typical, not on the drawings)", "Light switch")
                k += 1; nsw += 1; placed = True; break
        if lit and k == 0:                                     # no door matched (pocket door, lobby): a switch on the nearest clear wall
            for i in range(len(P)):
                (ax, ay), (bx, by) = P[i], P[(i + 1) % len(P)]
                L = math.hypot(bx - ax, by - ay)
                if L < 0.4 or k: continue
                tx, ty = (bx - ax) / L, (by - ay) / L; nx, ny = ty, -tx
                for s in (0.2, L - 0.2, L / 2):
                    q = Vector((ax + tx * s - nx * 0.10, ay + ty * s - ny * 0.10, fy + 1.2))
                    if not _in_poly(q.x, q.y, P): continue
                    h = wall_hit(q, Vector((nx, ny, 0)))
                    if h is None: continue
                    plate_at(h, fy + 1.2, f"JN-SW-{rid}-{k}", "switch", f"light switch, white plate 86 mm, centre 1.2 m ({rid}; typical, not on the drawings)", "Light switch")
                    k += 1; nsw += 1; break
        # sockets
        need = SOCKETS.get(t, 0) if not (t == "hall" and r.get("area_m2", 5) < 1.5) else 0
        cand = []
        for i in range(len(P)):
            (ax, ay), (bx, by) = P[i], P[(i + 1) % len(P)]
            L = math.hypot(bx - ax, by - ay)
            if L < 0.5: continue
            tx, ty = (bx - ax) / L, (by - ay) / L; nx, ny = ty, -tx
            ss = [0.3, L - 0.3, L / 2] + [0.3 + 0.25 * k for k in range(1, int((L - 0.6) / 0.25))]
            for s in ss:
                if 0.2 <= s <= L - 0.2: cand.append((L, i, s, ax + tx * s, ay + ty * s, nx, ny))
        cand.sort(key=lambda c: -c[0])
        got = []
        for (L, i, s, px, py, nx, ny) in cand:
            if len(got) >= need: break
            if any(math.hypot(px - gx, py - gy) < 1.2 for gx, gy in got): continue
            if any(math.hypot(px - dc.x, py - dc.y) < dw / 2 + 0.3 for dc, dw in doors if abs(dc.z - fy) < 0.3): continue
            z = fy + 0.45
            if t == "kitchen":
                over = [u for u in kitchen_units if u[0] - 0.05 <= px <= u[2] + 0.05 and u[1] - 0.05 <= py <= u[3] + 0.05 and u[4] < fy + 1.0]
                if over: z = fy + 1.1
                elif kitchen_units: z = fy + 0.45
            q = Vector((px - nx * 0.10, py - ny * 0.10, z))
            if not _in_poly(q.x, q.y, P): continue
            if t == "kitchen" and z > fy + 1.0: q = Vector((px - nx * 0.05, py - ny * 0.05, z))
            h = wall_hit(q, Vector((nx, ny, 0)), 0.2)
            if h is None or not clear_of_openings(h, z): continue
            plate_at(h, z, f"JN-SKT-{rid}-{len(got)}", "socket", f"double switched socket, white, {int(round((z - fy) * 1000))} mm ({rid}; typical, not on the drawings)", "Double socket")
            got.append((px, py)); nsk += 1
        # smoke alarm: halls and landings, on the ceiling at the room centre (or the nearest point inside)
        if t == "hall" and ("hall" in rid or "landing" in rid):
            cx = sum(p_[0] for p_ in P) / len(P); cy = sum(p_[1] for p_ in P) / len(P)
            if not _in_poly(cx, cy, P):
                best = min(((x_, y_) for x_ in [min(p_[0] for p_ in P) + 0.1 * k_ for k_ in range(80)] for y_ in [min(p_[1] for p_ in P) + 0.1 * j_ for j_ in range(80)]
                            if _in_poly(x_, y_, P)), key=lambda q_: (q_[0] - cx) ** 2 + (q_[1] - cy) ** 2, default=None)
                if best is None: continue
                cx, cy = best
            h = tree.ray_cast(Vector((cx, cy, fy + 1.5)), Vector((0, 0, 1)), 3.0)
            if h[0] is None: continue
            bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.055, radius2=0.05, depth=0.035)
            bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, -0.0175))
            me = bpy.data.meshes.new(f"JN-SMOKE-{rid}"); bm.to_mesh(me); bm.free(); me.materials.append(white)
            add(f"JN-SMOKE-{rid}", me, Matrix.Translation(h[0] - Vector((0, 0, 0.0005))), f"optical smoke alarm, mains with battery back-up, on the ceiling ({rid}; Part B typical)", "Smoke alarm")
            nsm += 1
    log(f"services: {nsw} light switches, {nsk} double sockets, {nsm} smoke alarms (typical, UK heights)")
    return out
