"""Small 2D geometry helpers for the plan-data checks (pure Python, no dependencies).

Points are (x, y) tuples in metres. Polygons are lists of points, closed implicitly (last joins first)."""
import math


def sub(a, b): return (a[0] - b[0], a[1] - b[1])
def add(a, b): return (a[0] + b[0], a[1] + b[1])
def mul(a, s): return (a[0] * s, a[1] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1]
def cross(a, b): return a[0] * b[1] - a[1] * b[0]
def length(a): return math.hypot(a[0], a[1])


def unit(a):
    n = length(a)
    return (a[0] / n, a[1] / n) if n > 1e-12 else (0.0, 0.0)


def left_normal(d):
    """Unit normal to the LEFT of direction d (d rotated +90 degrees)."""
    return (-d[1], d[0])


def area(poly):
    """Signed area (positive = anticlockwise)."""
    s = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def centroid(poly):
    a = area(poly)
    if abs(a) < 1e-12:
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    cx = cy = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        f = x1 * y2 - x2 * y1
        cx += (x1 + x2) * f; cy += (y1 + y2) * f
    return (cx / (6 * a), cy / (6 * a))


def bbox(poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def point_in_poly(p, poly):
    """Even-odd rule. Points exactly on an edge may fall either way; callers inset samples."""
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                inside = not inside
    return inside


def seg_closest(p, a, b):
    """(distance, t) from p to segment a-b; t in [0, 1] along the segment."""
    ab = sub(b, a)
    L2 = dot(ab, ab)
    if L2 < 1e-18:
        return length(sub(p, a)), 0.0
    t = max(0.0, min(1.0, dot(sub(p, a), ab) / L2))
    q = add(a, mul(ab, t))
    return length(sub(p, q)), t


def dist_to_boundary(p, poly):
    return min(seg_closest(p, poly[i], poly[(i + 1) % len(poly)])[0] for i in range(len(poly)))


def segments_intersect(p1, p2, p3, p4):
    """Proper intersection of segments p1-p2 and p3-p4 (touching at endpoints does not count)."""
    d1 = cross(sub(p4, p3), sub(p1, p3)); d2 = cross(sub(p4, p3), sub(p2, p3))
    d3 = cross(sub(p2, p1), sub(p3, p1)); d4 = cross(sub(p2, p1), sub(p4, p1))
    return ((d1 > 1e-12 and d2 < -1e-12) or (d1 < -1e-12 and d2 > 1e-12)) and \
           ((d3 > 1e-12 and d4 < -1e-12) or (d3 < -1e-12 and d4 > 1e-12))


def self_intersections(poly):
    n = len(poly); hits = []
    for i in range(n):
        for j in range(i + 1, n):
            if abs(i - j) <= 1 or (i == 0 and j == n - 1):
                continue
            if segments_intersect(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]):
                hits.append((i, j))
    return hits


def rect(start, direction, width, length_):
    """Rectangle starting on the line through `start`, centred across it, running `length_` along `direction`."""
    d = unit(direction); n = left_normal(d); h = width / 2.0
    a = add(start, mul(n, -h)); b = add(start, mul(n, h))
    return [a, add(a, mul(d, length_)), add(b, mul(d, length_)), b]


def sector(centre, r, a0, a1, steps=12):
    """Pie slice from angle a0 to a1 (radians, anticlockwise from +x) around centre."""
    if a1 < a0:
        a0, a1 = a1, a0
    pts = [centre]
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        pts.append((centre[0] + r * math.cos(a), centre[1] + r * math.sin(a)))
    return pts


def grid_samples(poly, spacing=0.1, inset=0.02, max_points=4000):
    """Interior sample points at least `inset` from the boundary. Spacing grows if the polygon is large."""
    x0, y0, x1, y1 = bbox(poly)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return []
    while (w / spacing + 1) * (h / spacing + 1) > max_points:
        spacing *= 1.5
    pts = []
    nx = int(w / spacing) + 1; ny = int(h / spacing) + 1
    ox = x0 + (w - (nx - 1) * spacing) / 2; oy = y0 + (h - (ny - 1) * spacing) / 2
    for i in range(nx):
        for j in range(ny):
            p = (ox + i * spacing, oy + j * spacing)
            if point_in_poly(p, poly) and dist_to_boundary(p, poly) >= inset:
                pts.append(p)
    if not pts:  # very thin shapes: use the centroid
        c = centroid(poly)
        if point_in_poly(c, poly):
            pts.append(c)
    return pts


def edge_samples(poly, step=0.05, end_skip=0.0):
    """Yield (edge_index, t_along_m, point) samples along each edge."""
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        L = length(sub(b, a))
        if L < 1e-9:
            continue
        d = unit(sub(b, a))
        n = max(1, int(round(L / step)))
        for k in range(n + 1):
            s = L * k / n
            if s < end_skip - 1e-9 or s > L - end_skip + 1e-9:
                continue
            yield i, s, add(a, mul(d, s))


def overlap_points(poly_a, poly_b, spacing=0.05, inset=0.01):
    """Sample points of A that fall inside B (empty list = no overlap at this resolution)."""
    x0, y0, x1, y1 = bbox(poly_a); u0, v0, u1, v1 = bbox(poly_b)
    if x1 < u0 or u1 < x0 or y1 < v0 or v1 < y0:
        return []
    return [p for p in grid_samples(poly_a, spacing, inset, max_points=3000) if point_in_poly(p, poly_b)
            and dist_to_boundary(p, poly_b) >= inset]


def fmt(p):
    return "(%.2f, %.2f)" % (p[0], p[1])
