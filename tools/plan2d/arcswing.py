"""Door swing from a drawn plan arc (house-agnostic).

Why: a quarter arc's two ends are equidistant from BOTH opposite corners of its bounding box, so choosing the hinge as a
bounding-box corner is a guess (half the doors come out mirrored). Fit a circle through points sampled along the drawn
curve instead: the centre IS the hinge. Partial arcs (doors drawn part-open) fit the same way.

  pts   = sampled points along the arc (e.g. Bezier evaluated at t = 0, .25, .5, .75, 1 per segment; see pdfvec.py 'arcs')
  wall  = dict(axis='H'|'V', c=centre-line coordinate, f=(face1, face2), a=run start, b=run end)   (sheet units)
  jambs = (j0, j1) along the wall
Returns {'hinge': 'start'|'end', 'side': 'left'|'right' (looking from run start to run end in SHEET coordinates)} or raises.
Convert 'side' to your site frame if the sheet y axis is flipped (y down). A drawn door with no arc is an error, not a pass."""
import math
import numpy as np


def fit_circle(pts):
    P = np.asarray(pts, float); x, y = P[:, 0], P[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones(len(x))]; b = x * x + y * y
    cx, cy, c = np.linalg.lstsq(A, b, rcond=None)[0]; r = math.sqrt(c + cx * cx + cy * cy)
    return cx, cy, r, float(np.sqrt(np.mean((np.hypot(x - cx, y - cy) - r) ** 2)))


def swing(arcs, wall, jambs, leaves=1, tol=5.0):
    lo, hi = sorted(jambs); lw = (hi - lo) / leaves; H = wall["axis"] == "H"; c = wall["c"]; f = wall["f"]
    best = []
    for pts in arcs:
        cx, cy, r, rms = fit_circle(pts)
        if rms > 0.6: continue
        along, across = (cx, cy) if H else (cy, cx)
        dj = min(abs(along - lo), abs(along - hi))
        if f[0] - tol <= across <= f[1] + tol and dj <= 0.3 * lw + 2 and 0.5 * lw <= r <= 1.3 * lw:
            tip = max((pts[0], pts[-1]), key=lambda t: abs((t[1] if H else t[0]) - c))
            best.append((dj, (cx, cy), tip, along))
    if not best: raise ValueError("no drawn arc for this door")
    best.sort(key=lambda z: z[0]); _, C, tip, along = best[0]
    js, je = (lo, hi) if wall["b"] >= wall["a"] else (hi, lo)
    hinge = "start" if abs(along - js) < abs(along - je) else "end"
    a = np.array((wall["a"], c) if H else (c, wall["a"])); b = np.array((wall["b"], c) if H else (c, wall["b"]))
    d = b - a; t = np.array(tip) - a; cr = d[0] * t[1] - d[1] * t[0]
    return {"hinge": hinge, "side": "left" if cr > 0 else "right", "centre": C}
