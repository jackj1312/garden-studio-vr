"""Smooth closed curves for plans: centripetal Catmull-Rom through measured points,
resampled every `step` metres, so a kerb curve is drawn and modelled as a curve.

    from smooth import closed_curve
    pts = closed_curve([(x, y), ...], step=0.08, corners={i, ...})

`corners` are indices of points where the edge has a true corner (the curve passes
through without rounding it off).
"""
import math


def _cr(p0, p1, p2, p3, n):
    def tj(ti, a, b): return ti + max(math.dist(a, b), 1e-6) ** 0.5
    t0 = 0; t1 = tj(t0, p0, p1); t2 = tj(t1, p1, p2); t3 = tj(t2, p2, p3)
    out = []
    for k in range(n):
        t = t1 + (t2 - t1) * k / n
        def L(a, b, ta, tb): return tuple(((tb - t) * a[i] + (t - ta) * b[i]) / (tb - ta) for i in range(2))
        A1, A2, A3 = L(p0, p1, t0, t1), L(p1, p2, t1, t2), L(p2, p3, t2, t3)
        B1, B2 = L(A1, A2, t0, t2), L(A2, A3, t1, t3)
        out.append(L(B1, B2, t1, t2))
    return out


def closed_curve(pts, step=0.08, corners=()):
    n = len(pts); out = []
    for i in range(n):
        p1, p2 = pts[i], pts[(i + 1) % n]
        # at a corner, the neighbour beyond it is mirrored so the curve meets it straight
        p0 = pts[i - 1] if i not in corners else tuple(2 * p1[k] - p2[k] for k in range(2))
        p3 = pts[(i + 2) % n] if (i + 1) % n not in corners else tuple(2 * p2[k] - p1[k] for k in range(2))
        seg = max(1, int(math.dist(p1, p2) / step))
        out += _cr(p0, p1, p2, p3, seg)
    return [(round(x, 3), round(y, 3)) for x, y in out]
