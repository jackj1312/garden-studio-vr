"""Pure-Python geometry for the house generator (no Blender): 2D convex clipping, polygon helpers and closed-solid
mesh primitives. Drawing frame = Blender frame: x along the front (right as seen from the road), y into the house,
z up from ground-floor FFL. A mesh is (verts, faces) with faces as vertex-index tuples; every primitive is a CLOSED
solid (the Blender side recalculates outward normals)."""
import math

EPS = 1e-9


# ---------------------------------------------------------------- 2D
def sub(a, b): return (a[0] - b[0], a[1] - b[1])
def add(a, b): return (a[0] + b[0], a[1] + b[1])
def mul(a, s): return (a[0] * s, a[1] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1]
def cross(a, b): return a[0] * b[1] - a[1] * b[0]
def length(a): return math.hypot(a[0], a[1])


def unit(a):
    L = length(a)
    return (a[0] / L, a[1] / L) if L > EPS else (0.0, 0.0)


def area(poly):
    s = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]; x1, y1 = poly[(i + 1) % len(poly)]
        s += x0 * y1 - x1 * y0
    return s / 2


def ccw(poly):
    return list(poly) if area(poly) >= 0 else list(reversed(poly))


def centroid(poly):
    A = area(poly)
    if abs(A) < 1e-12:
        n = len(poly); return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)
    cx = cy = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]; x1, y1 = poly[(i + 1) % len(poly)]
        f = x0 * y1 - x1 * y0
        cx += (x0 + x1) * f; cy += (y0 + y1) * f
    return (cx / (6 * A), cy / (6 * A))


def point_in_poly(p, poly):
    x, y = p; inside = False
    n = len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xi: inside = not inside
    return inside


def clip_half(poly, f, keep_le=True, eps=1e-9):
    """Sutherland-Hodgman: keep the part of convex (or any simple) polygon where f(p) <= 0 (keep_le) or >= 0.
    f is (a, b, c): a*x + b*y + c."""
    a, b, c = f
    s = 1.0 if keep_le else -1.0
    val = lambda p: s * (a * p[0] + b * p[1] + c)
    out = []
    n = len(poly)
    for i in range(n):
        P, Q = poly[i], poly[(i + 1) % n]
        vp, vq = val(P), val(Q)
        if vp <= eps:
            out.append(P)
        if (vp < -eps and vq > eps) or (vp > eps and vq < -eps):
            t = vp / (vp - vq)
            out.append((P[0] + (Q[0] - P[0]) * t, P[1] + (Q[1] - P[1]) * t))
    # drop duplicates
    res = []
    for p in out:
        if not res or length(sub(p, res[-1])) > 1e-7: res.append(p)
    if len(res) > 1 and length(sub(res[0], res[-1])) < 1e-7: res.pop()
    return res if len(res) >= 3 and abs(area(res)) > 1e-9 else []


def clip_convex(poly, halfplanes):
    for f in halfplanes:
        poly = clip_half(poly, f, True)
        if not poly: return []
    return poly


def poly_halfplanes(poly):
    """Half-planes (a,b,c) with a*x+b*y+c <= 0 inside, for a CCW convex polygon."""
    poly = ccw(poly); out = []
    for i in range(len(poly)):
        P, Q = poly[i], poly[(i + 1) % len(poly)]
        d = sub(Q, P)
        # inside is to the left: cross(d, p - P) >= 0  ->  -(d.x*(y-P.y) - d.y*(x-P.x)) <= 0
        a, b = d[1], -d[0]
        out.append((a, b, -(a * P[0] + b * P[1])))
    return out


def convex_minus(P, C_halfplanes, min_area=1e-6):
    """P (convex) minus C (convex, given as half-planes f<=0 inside): list of convex pieces."""
    pieces = []
    rest = P
    for f in C_halfplanes:
        if not rest: break
        outside = clip_half(rest, f, keep_le=False)
        if outside and abs(area(outside)) > min_area: pieces.append(outside)
        rest = clip_half(rest, f, keep_le=True)
    return pieces


def clip_segment_convex(p0, p1, poly):
    """Parametric interval [t0, t1] of segment p0->p1 inside convex poly (CCW), or None."""
    t0, t1 = 0.0, 1.0
    d = sub(p1, p0)
    for (a, b, c) in poly_halfplanes(poly):
        num = -(a * p0[0] + b * p0[1] + c)
        den = a * d[0] + b * d[1]
        if abs(den) < 1e-12:
            if num < 0: return None
            continue
        t = num / den
        if den > 0: t1 = min(t1, t)
        else: t0 = max(t0, t)
        if t0 > t1 + 1e-12: return None
    return (t0, t1) if t1 - t0 > 1e-9 else None


def merge_intervals(iv, gap=1e-4):
    iv = sorted(iv); out = []
    for a, b in iv:
        if out and a <= out[-1][1] + gap: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    return [tuple(x) for x in out]


def interval_minus(iv, cuts):
    """[(a,b)] minus [(c,d)] -> [(a,b)]"""
    out = list(iv)
    for c, d in cuts:
        nxt = []
        for a, b in out:
            if d <= a or c >= b: nxt.append((a, b)); continue
            if c > a: nxt.append((a, c))
            if d < b: nxt.append((d, b))
        out = nxt
    return [(a, b) for a, b in out if b - a > 1e-6]


def seg_point_dist(p, a, b):
    d = sub(b, a); L2 = dot(d, d)
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, dot(sub(p, a), d) / L2))
    q = add(a, mul(d, t))
    return length(sub(p, q)), t


def line_intersect(p, d, q, e):
    """p + s*d = q + t*e -> point, or None if parallel"""
    den = cross(d, e)
    if abs(den) < 1e-12: return None
    s = cross(sub(q, p), e) / den
    return add(p, mul(d, s))


# ---------------------------------------------------------------- 3D vectors
def v3sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def v3add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def v3mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def v3dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def v3cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def v3len(a): return math.sqrt(v3dot(a, a))


def v3unit(a):
    L = v3len(a)
    return (a[0] / L, a[1] / L, a[2] / L) if L > EPS else (0.0, 0.0, 0.0)


# ---------------------------------------------------------------- closed-solid primitives (world coordinates)
HEXA_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def hexa(pts):
    """8 corners: bottom 0-3 (a loop), top 4-7 above them. Returns (verts, faces)."""
    return [tuple(p) for p in pts], [tuple(f) for f in HEXA_FACES]


def box(x0, x1, y0, y1, z0, z1):
    return hexa([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                 (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])


def prism(poly, z0, z1):
    """vertical prism of a plan polygon (any simple polygon)"""
    poly = ccw(poly); n = len(poly)
    V = [(p[0], p[1], z0) for p in poly] + [(p[0], p[1], z1) for p in poly]
    F = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        F.append((i, j, n + j, n + i))
    return V, F


def prism_varz(poly, zb, zt):
    """vertical prism whose bottom/top z vary per vertex (zb, zt functions of (x, y)); for planar tops only"""
    poly = ccw(poly); n = len(poly)
    V = [(p[0], p[1], zb(p)) for p in poly] + [(p[0], p[1], zt(p)) for p in poly]
    F = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        F.append((i, j, n + j, n + i))
    return V, F


def slab3d(pts3, normal, t0, t1):
    """planar 3D polygon offset along unit normal from t0 to t1 (a slab: tiles, membrane, deck on a slope)"""
    n = len(pts3)
    lo = [v3add(p, v3mul(normal, t0)) for p in pts3]
    hi = [v3add(p, v3mul(normal, t1)) for p in pts3]
    V = lo + hi
    F = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        F.append((i, j, n + j, n + i))
    return V, F


def extrude_section(section, L, plumb=None):
    """Local member mesh: section polygon in (y, z) extruded along local +x from 0 to L. plumb=(tan_s, tan_e): end
    faces cut vertical for a sloped member (x shift = -z*tan at the start, -z*tan at the end), section z measured
    from the member's TOP edge (z <= 0 below it)."""
    n = len(section)
    ts, te = plumb if plumb else (0.0, 0.0)
    V = [(0.0 - z * ts, y, z) for (y, z) in section] + [(L - z * te, y, z) for (y, z) in section]
    sec_area = area(section)
    base = list(range(n)) if sec_area < 0 else list(reversed(range(n)))
    F = [tuple(base), tuple(n + i for i in reversed(base))]
    for i in range(n):
        j = (i + 1) % n
        F.append((i, j, n + j, n + i))
    return V, F


def rect_section(w, d):
    """rectangle w wide, d deep, hanging below the top edge (z from 0 down to -d), centred in y"""
    return [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, -d), (-w / 2, -d)]


def i_section(D, B, tw, tf, plate=None):
    """UB I-section, top flange at z 0, bottom at -D. plate=(t, width) welded under the bottom flange (separate solid
    returned as a second polygon)."""
    hb, hw = B / 2, tw / 2
    sec = [(-hb, 0), (hb, 0), (hb, -tf), (hw, -tf), (hw, -D + tf), (hb, -D + tf), (hb, -D), (-hb, -D),
           (-hb, -D + tf), (-hw, -D + tf), (-hw, -tf), (-hb, -tf)]
    return sec


def frame_matrix(origin, X, Z_hint=(0, 0, 1)):
    """4x4 (row-major lists) local->world: local x along X, local z the component of Z_hint perpendicular to X,
    local y = z cross x (right-handed)."""
    X = v3unit(X)
    Zh = Z_hint
    if abs(v3dot(X, v3unit(Zh))) > 0.999: Zh = (0, 1, 0) if abs(X[1]) < 0.9 else (1, 0, 0)
    Z = v3unit(v3sub(Zh, v3mul(X, v3dot(Zh, X))))
    Y = v3cross(Z, X)
    o = origin
    return [[X[0], Y[0], Z[0], o[0]], [X[1], Y[1], Z[1], o[1]], [X[2], Y[2], Z[2], o[2]], [0, 0, 0, 1]]


def apply_matrix(M, V):
    return [(M[0][0] * x + M[0][1] * y + M[0][2] * z + M[0][3],
             M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3],
             M[2][0] * x + M[2][1] * y + M[2][2] * z + M[2][3]) for (x, y, z) in V]


def merge_meshes(meshes):
    V, F = [], []
    for v, f in meshes:
        o = len(V); V.extend(v); F.extend(tuple(i + o for i in face) for face in f)
    return V, F


def mesh_bbox(V):
    xs = [p[0] for p in V]; ys = [p[1] for p in V]; zs = [p[2] for p in V]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def triangulate(poly):
    """ear clipping -> triangles (lists of 3 points) for a simple polygon"""
    P = ccw([tuple(p) for p in poly])
    idx = list(range(len(P))); tris = []
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        ear = False
        for i in range(len(idx)):
            a, b, c = idx[i - 1], idx[i], idx[(i + 1) % len(idx)]
            A, B, C = P[a], P[b], P[c]
            if cross(sub(B, A), sub(C, B)) <= 1e-12: continue
            if any(point_in_poly(P[k], [A, B, C]) for k in idx if k not in (a, b, c)): continue
            tris.append([A, B, C]); idx.pop(i); ear = True; break
        if not ear: break
    if len(idx) == 3: tris.append([P[i] for i in idx])
    return tris


def is_convex(P):
    P = ccw(P); n = len(P)
    for i in range(n):
        a, b, c = P[i], P[(i + 1) % n], P[(i + 2) % n]
        if cross(sub(b, a), sub(c, b)) < -1e-12: return False
    return True


def convex_pieces(poly):
    return [ccw(poly)] if is_convex(poly) else triangulate(poly)


def poly_minus_convex(poly, cutters, min_area=1e-5):
    """any simple polygon minus convex cutters -> convex pieces"""
    pieces = convex_pieces(poly)
    for C in cutters:
        hp = poly_halfplanes(C)
        nxt = []
        for P in pieces:
            if clip_convex(P, hp): nxt.extend(convex_minus(P, hp))
            else: nxt.append(P)
        pieces = nxt
    return [P for P in pieces if abs(area(P)) > min_area]
