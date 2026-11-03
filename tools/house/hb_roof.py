"""Pitched roofs as unions of 'wings' (pure Python). A wing is a convex eaves footprint and a set of planes
(ridge planes, hip planes); its surface is the LOWEST of its planes, and a roof system's surface is the HIGHEST of
its wings (so hips come from planes meeting inside a wing, valleys from wings meeting). Everything is exact convex
clipping in plan: the visible region of each plane is a list of convex pieces, from which come the tiles, membrane,
battens, rafters (laid at their drawn/stated positions and clipped to the pieces), ridge boards, hips, valleys,
fascia/soffit/gutters, ridge and hip tiles. Distances in metres, drawing frame."""
import math
from hb_geom import (clip_half, clip_convex, convex_minus, poly_halfplanes, clip_segment_convex, merge_intervals,
                     area, ccw, sub, add, mul, dot, cross, unit, length, slab3d, extrude_section, rect_section,
                     frame_matrix, v3unit, v3sub, v3dot, v3len, hexa, merge_meshes, seg_point_dist, centroid, prism, prism_varz)

COVER = dict(tiles=0.030, battens=0.025, membrane=0.001)      # perpendicular thicknesses above the rafters
COVER_T = COVER["tiles"] + COVER["battens"] + COVER["membrane"]


class Plane:
    def __init__(self, pid, p0, down, pitch, wing):
        self.id, self.wing = pid, wing
        self.d = unit(tuple(down))
        self.e = (-self.d[1], self.d[0])               # along the eave
        self.pitch = pitch
        self.tan = math.tan(math.radians(pitch))
        self.cos = math.cos(math.radians(pitch))
        x0, y0, z0 = p0
        self.A, self.B = -self.d[0] * self.tan, -self.d[1] * self.tan
        self.C = z0 + (x0 * self.d[0] + y0 * self.d[1]) * self.tan
        nz = 1.0 / math.sqrt(self.A ** 2 + self.B ** 2 + 1)
        self.n = (-self.A * nz, -self.B * nz, nz)       # upward unit normal

    def z(self, p): return self.A * p[0] + self.B * p[1] + self.C

    def key(self):
        return (round(self.A, 4), round(self.B, 4), round(self.C, 3))

    def diff(self, other, dz=0.0):
        """half-plane coefficients of z_self - z_other - dz"""
        return (self.A - other.A, self.B - other.B, self.C - other.C - dz)


class Wing:
    def __init__(self, spec):
        self.spec = spec
        self.id = spec["id"]
        self.footprint = ccw([tuple(p) for p in spec["footprint"]])
        self.planes = [Plane(f"{self.id}.{p['id']}", p["p0"], p["down"], p["pitch"], self) for p in spec["planes"]]
        self.category = spec.get("category", "new")

    def z(self, p):
        return min(pl.z(p) for pl in self.planes)


class RoofSystem:
    def __init__(self, sid, wings):
        self.id = sid
        self.wings = [w if isinstance(w, Wing) else Wing(w) for w in wings]
        self.pieces = self._pieces()

    def planes(self):
        return [pl for w in self.wings for pl in w.planes]

    def z(self, p):
        best = None
        for w in self.wings:
            if _inside(p, w.footprint):
                z = w.z(p); best = z if best is None else max(best, z)
        return best

    def _pieces(self):
        out = []          # (plane, convex polygon)
        for w in self.wings:
            for pl in w.planes:
                R = clip_convex(list(w.footprint), [pl.diff(q) for q in w.planes if q is not pl])
                if not R: continue
                pieces = [R]
                for w2 in self.wings:
                    if w2 is w: continue
                    # where w2 is strictly higher than this plane
                    C = poly_halfplanes(w2.footprint) + [(-(q.A - pl.A), -(q.B - pl.B), -(q.C - pl.C) + 1e-6) for q in w2.planes
                                                          if q.key() != pl.key()]
                    if any(q.key() == pl.key() for q in w2.planes):
                        # same plane in another wing: the earlier wing keeps the shared region
                        if self.wings.index(w2) < self.wings.index(w):
                            C = poly_halfplanes(w2.footprint) + [(-(q.A - pl.A), -(q.B - pl.B), -(q.C - pl.C) - 1e-6)
                                                                 for q in w2.planes if q.key() != pl.key()]
                        else:
                            continue
                    nxt = []
                    for P in pieces:
                        nxt.extend(convex_minus(P, C))
                    pieces = nxt
                for P in pieces:
                    if abs(area(P)) > 1e-5: out.append((pl, P))
        return out

    # ------------------------------------------------ creases between visible pieces
    def creases(self, tol=0.003):
        """[(kind, plane_a, plane_b, p0, p1)] kind in ridge | hip | valley"""
        found = {}
        P = self.pieces
        for i in range(len(P)):
            pa, A = P[i]
            for j in range(i + 1, len(P)):
                pb, B = P[j]
                if pa.key() == pb.key(): continue
                for k in range(len(A)):
                    a0, a1 = A[k], A[(k + 1) % len(A)]
                    da = sub(a1, a0); La = length(da)
                    if La < 1e-4: continue
                    ua = mul(da, 1 / La)
                    for m in range(len(B)):
                        b0, b1 = B[m], B[(m + 1) % len(B)]
                        if abs(cross(ua, sub(b0, a0))) > tol or abs(cross(ua, sub(b1, a0))) > tol: continue
                        t0, t1 = sorted((dot(sub(b0, a0), ua), dot(sub(b1, a0), ua)))
                        s0, s1 = max(0, t0), min(La, t1)
                        if s1 - s0 < 0.005: continue
                        q0, q1 = add(a0, mul(ua, s0)), add(a0, mul(ua, s1))
                        # A plan boundary may be a vertical step. Only a line
                        # shared in XYZ can carry a hip, ridge or valley.
                        if any(abs(pa.z(q)-pb.z(q)) > tol for q in (q0, q1)): continue
                        key = (pa.id, pb.id)
                        found.setdefault(key, []).append((q0, q1, pa, pb, A, B))
        out = []
        for key, segs in found.items():
            for (q0, q1, pa, pb, A, B) in segs:
                m = mul(add(q0, q1), 0.5)
                ca, cb = centroid(A), centroid(B)
                za = pa.z(add(m, mul(unit(sub(ca, m)), 0.05))); zb = pb.z(add(m, mul(unit(sub(cb, m)), 0.05)))
                zm = pa.z(m)
                if za < zm and zb < zm:
                    kind = "ridge" if abs(pa.z(q0) - pa.z(q1)) < 0.003 else "hip"
                elif za > zm and zb > zm:
                    kind = "valley"
                else:
                    continue     # a step (one plane passes under the other): not a crease
                out.append((kind, pa, pb, q0, q1))
        return out

    def plane_pieces(self, pl):
        return [P for (q, P) in self.pieces if q is pl]


def _inside(p, poly):
    return all(a * p[0] + b * p[1] + c <= 1e-9 for (a, b, c) in poly_halfplanes(poly))


def on_boundary(p, poly, tol=0.002):
    n = len(poly)
    return any(seg_point_dist(p, poly[i], poly[(i + 1) % n])[0] < tol for i in range(n))


# ---------------------------------------------------------------- geometry builders
def lift(pl, pts, dz=0.0):
    return [(p[0], p[1], pl.z(p) + dz) for p in pts]


def cover_layers(system, plane_filter=None, holes=None):
    """{layer: [(plane, mesh)]} for tiles and membrane slabs on every visible piece. holes: [(plane_key, convex poly)]
    cut out of the tiles and membrane (roof lights)."""
    out = {"tiles": [], "membrane": []}
    for pl, P in system.pieces:
        if plane_filter and not plane_filter(pl): continue
        polys = [P]
        for (hk, H) in holes or []:
            if hk != pl.key(): continue
            nxt = []
            for Q in polys: nxt.extend(convex_minus(Q, poly_halfplanes(H)))
            polys = nxt
        for Q in polys:
            pts = lift(pl, Q)
            out["tiles"].append((pl, Q, slab3d(pts, pl.n, -COVER["tiles"], 0.0)))
            t0 = -COVER_T
            out["membrane"].append((pl, Q, slab3d(pts, pl.n, t0, t0 + COVER["membrane"])))
    return out


def battens(system, pl, gauge=0.100, w=0.050, t=0.025):
    """batten boxes on plane pl (one merged mesh): 50x25 at the tile gauge, laid along the eave direction"""
    pieces = system.plane_pieces(pl)
    if not pieces: return None
    ws = [dot(p, pl.d) for P in pieces for p in P]
    lo, hi = min(ws), max(ws)                       # d increases downhill: hi = eave
    gh = gauge * pl.cos
    meshes = []
    es = [dot(p, pl.e) for P in pieces for p in P]
    e0, e1 = min(es) - 1, max(es) + 1
    k = 0
    while True:
        wpos = hi - 0.06 - k * gh
        if wpos < lo + 0.02: break
        k += 1
        a = add(mul(pl.d, wpos), mul(pl.e, e0)); b = add(mul(pl.d, wpos), mul(pl.e, e1))
        iv = []
        for P in pieces:
            r = clip_segment_convex(a, b, P)
            if r: iv.append(r)
        for (t0, t1) in merge_intervals(iv):
            p0 = add(a, mul(sub(b, a), t0)); p1 = add(a, mul(sub(b, a), t1))
            L = length(sub(p1, p0))
            if L < 0.05: continue
            # box on the membrane: local x along the batten, z = plane normal
            base = -COVER["tiles"] - COVER["battens"]
            o3 = (p0[0], p0[1], pl.z(p0))
            o3 = (o3[0] + pl.n[0] * (base + t), o3[1] + pl.n[1] * (base + t), o3[2] + pl.n[2] * (base + t))
            X = (p1[0] - p0[0], p1[1] - p0[1], 0.0)
            M = frame_matrix(o3, X, pl.n)
            from hb_geom import apply_matrix, box
            V, F = box(0, L, -w / 2, w / 2, -t, 0)
            meshes.append((apply_matrix(M, V), F))
    return merge_meshes(meshes) if meshes else None


def member_on_plane(pl, p_hi, p_lo, w, d, cover_t=COVER_T):
    """a rafter whose TOP edge runs from p_hi to p_lo (plan points) on the rafter-top plane; plumb ends.
    Returns (origin3, X3, local mesh, matrix) with the mesh in local coordinates for instancing."""
    dz = -cover_t / pl.cos
    A = (p_hi[0], p_hi[1], pl.z(p_hi) + dz)
    B = (p_lo[0], p_lo[1], pl.z(p_lo) + dz)
    X = v3sub(B, A); L = v3len(X)
    return linear_member(A, B, rect_section(w, d), plumb=True)


def linear_member(A, B, section, plumb=False, up=(0, 0, 1)):
    """section (y, z) hanging below the top edge A->B; local x along A->B; returns (verts_local, faces, matrix, L, key)"""
    X = v3sub(B, A); L = v3len(X)
    M = frame_matrix(A, X, up)
    tanp = None
    if plumb:
        Xu = v3unit(X); h = math.hypot(Xu[0], Xu[1])
        Z = (M[0][2], M[1][2], M[2][2])
        if h > 1e-6:
            Xhu = (Xu[0] / h, Xu[1] / h, 0.0)
            tanp = (Z[0] * Xhu[0] + Z[1] * Xhu[1]) / h
    V, F = extrude_section(section, L, (tanp, tanp) if tanp else None)
    key = (tuple((round(a, 4), round(b, 4)) for a, b in section), round(L, 3), round(tanp or 0, 4))
    return V, F, M, L, key


def crease_member(pl_a, pl_b, q0, q1, w, d, cover_t=COVER_T):
    """hip / valley / ridge member: top edge along the crease lowered by the cover (vertical), vertical section"""
    ca = cover_t / pl_a.cos
    # a convex crease (hip) is set down so its square top edges stay under the two roof planes
    m = mul(add(q0, q1), 0.5); dd = unit(sub(q1, q0)); nn = (dd[1], -dd[0])
    zm = pl_a.z(m)
    drop = max(0.0, max(zm - pl_a.z(add(m, mul(nn, w / 2))), zm - pl_b.z(add(m, mul(nn, -w / 2))),
                        zm - pl_a.z(add(m, mul(nn, -w / 2))), zm - pl_b.z(add(m, mul(nn, w / 2)))))
    ca += drop
    A = (q0[0], q0[1], pl_a.z(q0) - ca); B = (q1[0], q1[1], pl_a.z(q1) - ca)
    if A[2] < B[2]: A, B = B, A
    return linear_member(A, B, rect_section(w, d), plumb=True)


def seated_crease(pa, pb, q0, q1, width):
    """Plumb-cut the structural toe behind its enclosing fascia. The
    weathering above it continues to the full measured roof perimeter."""
    low, high = (q0,q1) if pa.z(q0)<pa.z(q1) else (q1,q0)
    if not any(on_boundary(low,p.wing.footprint) for p in (pa,pb)):
        return q0,q1
    toward = unit(sub(high,low)); across = (-toward[1],toward[0]); cut = 0.
    for plane in (pa,pb):
        footprint = plane.wing.footprint
        for i,a in enumerate(footprint):
            edge = unit(sub(footprint[(i+1)%len(footprint)],a)); inside = (-edge[1],edge[0])
            rate = dot(toward,inside)
            if rate<=.001 or dot(plane.d,inside)>-.99: continue
            setback = .070 + width*.5*abs(dot(across,inside)) - dot(sub(low,a),inside)
            cut = max(cut,setback/rate)
    if cut >= length(sub(high,low))-.02: return None
    toe = add(low,mul(toward,cut))
    return (toe,high) if low==q0 else (high,toe)


def rafter_lines(system, pl, positions, trim_crease=0.032, trim_ridge=0.016, eave_back=0.07):
    """rafters on plane pl at plan positions along pl.e: [(p_hi, p_lo, s, end_types)]"""
    pieces = system.plane_pieces(pl)
    if not pieces: return []
    wing = pl.wing
    ridges = [c for c in system.creases() if (c[1] is pl or c[2] is pl)]
    ws = [dot(p, pl.d) for P in pieces for p in P]
    lo, hi = min(ws) - 1, max(ws) + 1
    out = []
    for s in positions:
        a = add(mul(pl.e, s), mul(pl.d, lo)); b = add(mul(pl.e, s), mul(pl.d, hi))
        iv = []
        for P in pieces:
            r = clip_segment_convex(a, b, P)
            if r: iv.append(r)
        for (t0, t1) in merge_intervals(iv, gap=0.003):
            p_hi = add(a, mul(sub(b, a), t0)); p_lo = add(a, mul(sub(b, a), t1))
            types = []
            for which, p, sign in (("hi", p_hi, 1), ("lo", p_lo, -1)):
                if on_boundary(p, wing.footprint):
                    typ = "eave" if which == "lo" else "abutment"
                    back = eave_back if typ == "eave" else 0.0
                else:
                    typ, back = "crease", trim_crease
                    for (kind, pa, pb, q0, q1) in ridges:
                        if seg_point_dist(p, q0, q1)[0] < 0.004:
                            typ = kind; back = trim_ridge if kind == "ridge" else trim_crease
                            break
                types.append(typ)
                # move the end along the rafter towards its middle by `back`
                dvec = unit(sub(p_lo, p_hi))
                if which == "hi": p_hi = add(p_hi, mul(dvec, back))
                else: p_lo = add(p_lo, mul(dvec, -back))
            if length(sub(p_lo, p_hi)) > 0.08:
                out.append((p_hi, p_lo, s, tuple(types)))
    return out


def positions_for(pl, spec, pieces):
    """rafter positions along pl.e: spec {"list": [...]} absolute (x or y as the eave direction runs) or
    {"from": v, "spacing": s}; values are converted to the e-coordinate."""
    es = [dot(p, pl.e) for P in pieces for p in P]
    emin, emax = min(es), max(es)
    sign = 1.0 if (abs(pl.e[0]) > abs(pl.e[1]) and pl.e[0] > 0) or (abs(pl.e[1]) >= abs(pl.e[0]) and pl.e[1] > 0) else -1.0
    conv = lambda v: v * sign
    lo_abs, hi_abs = spec.get("min", -1e9), spec.get("max", 1e9)
    if "list" in spec:
        return [conv(v) for v in spec["list"] if lo_abs <= v <= hi_abs]
    f, sp = conv(spec["from"]), abs(spec.get("spacing", 0.4))
    out = []
    k = 0
    while f - k * sp > emin + 0.02:
        out.append(f - k * sp); k += 1
    k = 1
    while f + k * sp < emax - 0.02:
        out.append(f + k * sp); k += 1
    return sorted(p for p in out if emin + 0.02 < p < emax - 0.02 and lo_abs - 1e-6 <= p * sign <= hi_abs + 1e-6)


def eave_edges(system):
    """[(wing, plane, p0, p1)] footprint edges that are horizontal low edges of a visible piece (eaves)"""
    out = []
    for pl, P in system.pieces:
        fp = pl.wing.footprint
        for i in range(len(P)):
            a, b = P[i], P[(i + 1) % len(P)]
            if length(sub(b, a)) < 0.02: continue
            if not (on_boundary(a, fp) and on_boundary(b, fp)): continue
            m = mul(add(a, b), 0.5)
            if abs(pl.z(a) - pl.z(b)) > 0.003: continue
            # low edge: moving inward raises z
            inward = sub(centroid(P), m)
            if pl.z(add(m, mul(unit(inward), 0.05))) > pl.z(m):
                out.append((pl.wing, pl, a, b))
    return out


def board_edges(system):
    """Runs of fabricated fascia/soffit, including a short rake at a hip toe.

    The plane patch of a hipped roof can run out just before the physical
    footprint corner. The adjoining plane covers the remaining part of the
    same edge. Continue the board there to meet the next board on the actual
    corner, carrying the original tile-plane run separately for its identity.
    """
    edges = eave_edges(system)
    out = []
    for wing, plane, a, b in edges:
        ends = []
        for p, other in ((a,b),(b,a)):
            along = unit(sub(p,other))
            projection = wing.spec.get('overhang_by_plane',{}).get(plane.id.split('.')[-1],wing.spec.get('overhang',.25))
            tip = p
            for corner in wing.footprint:
                delta = sub(corner,p)
                # Only the short rake within the roof covering depth can be
                # formed on the same board. A longer side is a distinct verge.
                if not .001 < dot(delta,along) <= min(projection,COVER_T/plane.cos) or abs(cross(delta,along)) > .001: continue
                if not any(w is wing and q is not plane and (length(sub(c,corner)) < .001 or length(sub(d,corner)) < .001)
                           for w,q,c,d in edges): continue
                mid = mul(add(p,corner),.5)
                if not on_boundary(mid,wing.footprint) or abs(system.z(mid)-wing.z(mid)) > .002: continue
                tip = corner; break
            ends.append(tip)
        out.append((wing,plane,*ends,a,b))
    return out


def step_board(system,plane,a,b):
    """Scribe the fascia of an upper roof to the tile plane below it.
    There is no horizontal soffit or gutter through the lower roof."""
    mid=add(mul(add(a,b),.5),mul(plane.d,.002))
    below=system.z(mid)
    if below is None: return None
    lower=next((p for p,Q in system.pieces if p is not plane and _inside(mid,Q) and abs(p.z(mid)-below)<.002),None)
    if lower is None:return None
    P=ccw([a,b,add(b,mul(plane.d,-.018)),add(a,mul(plane.d,-.018))])
    top_drop=COVER['tiles']/plane.cos
    # Clip to the zero-depth intersection. A triangular end must terminate
    # on that line rather than turn inside out behind the lower tiles.
    Q=clip_half(P,lower.diff(plane,-top_drop))
    if not Q:return None
    # A vertical prism tapers to zero at the scribe. Weld that edge here
    # so the closed component has triangles in place of collapsed quads.
    vv,ff=prism_varz(Q,lower.z,lambda p:plane.z(p)-top_drop)
    ids={}; verts=[]; remap=[]
    for v in vv:
        key=tuple(round(x,8) for x in v)
        if key not in ids:ids[key]=len(verts);verts.append(v)
        remap.append(ids[key])
    faces=[tuple(dict.fromkeys(remap[i] for i in f)) for f in ff]
    return verts,[f for f in faces if len(f)>=3]


def end_rakes(wing,plane,a,b,tile_a,tile_b,mitres):
    """Develop the few millimetres of raking top across a hip-end mitre.
    The station is measured back from the cut line, so both sides of the
    gutter reach the adjoining run's level across its full width."""
    ramps=[]
    for corner,old,away in ((a,tile_a,b),(b,tile_b,a)):
        gap=length(sub(corner,old))
        if gap<.001:continue
        toward=unit(sub(corner,away))
        change=wing.z(corner)-plane.z(corner)
        for nx,ny,c in mitres:
            rate=dot((nx,ny),toward)
            if rate<=.001 or abs(nx*corner[0]+ny*corner[1]+c)>.002:continue
            ramps.append(((-nx/rate,-ny/rate,-c/rate-gap),-change/gap));break
    return ramps


def eave_solid(poly,bottom,top,ramps,gutter=False):
    if not ramps:return prism(poly,bottom,top)
    pieces=[ccw(poly)]
    for line,_ in ramps:
        pieces=[q for piece in pieces for q in (clip_half(piece,line),clip_half(piece,line,False)) if q]
    verts=[]; ids={}; faces=[]; sides={}
    def vertex(p,z):
        key=tuple(round(v,8) for v in (*p,z))
        if key not in ids:ids[key]=len(verts);verts.append((*p,z))
        return ids[key]
    for piece in pieces:
        lower=[]; upper=[]
        for x,y in piece:
            dz=sum(min(0.,nx*x+ny*y+c)*gain for (nx,ny,c),gain in ramps)
            lower.append(vertex((x,y),bottom+(dz if gutter else 0.)))
            upper.append(vertex((x,y),top+dz))
        faces.extend((tuple(reversed(lower)),tuple(upper)))
        for i in range(len(lower)):
            j=(i+1)%len(lower);key=tuple(sorted((lower[i],lower[j])))
            if key in sides:del sides[key]
            else:sides[key]=(lower[i],lower[j],upper[j],upper[i])
    return verts,faces+list(sides.values())


def verge_edges(system):
    out = []
    for pl, P in system.pieces:
        fp = pl.wing.footprint
        for i in range(len(P)):
            a, b = P[i], P[(i + 1) % len(P)]
            if length(sub(b, a)) < 0.02: continue
            if on_boundary(a, fp) and on_boundary(b, fp) and abs(pl.z(a) - pl.z(b)) > 0.003:
                out.append((pl.wing, pl, a, b))
    return out


def top_edges(system):
    """horizontal high footprint edges (abutments against a wall)"""
    out = []
    for pl, P in system.pieces:
        fp = pl.wing.footprint
        for i in range(len(P)):
            a, b = P[i], P[(i + 1) % len(P)]
            if length(sub(b, a)) < 0.02: continue
            if not (on_boundary(a, fp) and on_boundary(b, fp)): continue
            if abs(pl.z(a) - pl.z(b)) > 0.003: continue
            m = mul(add(a, b), 0.5)
            if pl.z(add(m, mul(unit(sub(centroid(P), m)), 0.05))) < pl.z(m):
                out.append((pl.wing, pl, a, b))
    return out
