"""Smooth, measured kerb lines for a plan (WORKFLOW G1; CORRECTIONS-LOG 5, 34, 46).

    ~/splat/bin/python tools/plan/kerb_fit.py <plan.json> <ortho.png> <x0> <y1> <res_m> <key> [--corners i,j] [--out plan.json]

For each point of plan[key]["edge"], looks along the outward normal in a true-scale top-down photo for the grey
kerb band (low saturation), and takes its inner edge. Each stretch between true corners (kerbs meeting at an
angle) is then fitted with a smoothing cubic spline: curvature is continuous, so there are no jumps. Points where
no kerb is found (a car parked on it, shadow) keep their old position at low weight. Prints the fit's residual and
its largest curvature jump; the check fails if a stretch jumps by more than 2/m."""
import argparse, json, sys
import numpy as np
from PIL import Image
from scipy.interpolate import splprep, splev

ap = argparse.ArgumentParser()
ap.add_argument("plan"); ap.add_argument("ortho"); ap.add_argument("x0", type=float); ap.add_argument("y1", type=float)
ap.add_argument("res", type=float); ap.add_argument("key")
ap.add_argument("--corners", default=""); ap.add_argument("--out", default="")
ap.add_argument("--inside", default="any", choices=["any", "green", "dark"], help="what must lie just inside the kerb: lawn (green) or bed soil/plants (dark)")
ap.add_argument("--hug", nargs=2, default=None, metavar=("KEY", "OFFSET"), help="where this edge runs beside KEY's edge (within 0.35 m), follow it exactly at OFFSET m outside it (one shared kerb)")
ap.add_argument("--step", type=float, default=0.05); ap.add_argument("--smooth", type=float, default=0.03)
a = ap.parse_args()
P = json.load(open(a.plan)); E = np.array(P[a.key]["edge"], float)
img = np.asarray(Image.open(a.ortho).convert("RGB")).astype(float) / 255
mx, mn = img.max(2), img.min(2); sat = (mx - mn) / np.maximum(mx, 1e-3); val = mx
grey = (sat < 0.15) & (val > 0.3) & (val < 0.85)
hue = np.zeros_like(val)
r_, g_, b_ = img[..., 0], img[..., 1], img[..., 2]
d_ = np.maximum(mx - mn, 1e-4)
hue = np.where(mx == r_, ((g_ - b_) / d_) % 6, np.where(mx == g_, (b_ - r_) / d_ + 2, (r_ - g_) / d_ + 4)) / 6
green = (hue > 0.11) & (hue < 0.40) & (sat > 0.28)
dark = (val < 0.5) | (green)
inside_ok = {"any": np.ones_like(grey), "green": green, "dark": dark}[a.inside]
H, W = grey.shape
def px(x, y): return int((x - a.x0) / a.res), int((a.y1 - y) / a.res)
# outward normals of a ccw loop
area = 0.5 * np.sum(E[:, 0] * np.roll(E[:, 1], -1) - np.roll(E[:, 0], -1) * E[:, 1])
if area < 0: E = E[::-1]
t = np.roll(E, -1, 0) - np.roll(E, 1, 0); t /= np.linalg.norm(t, axis=1)[:, None]
nrm = np.stack([t[:, 1], -t[:, 0]], 1)
pts, wts = [], []
for p, n in zip(E, nrm):
    s = np.arange(-0.20, 0.26, a.res)
    hits = []
    for d in s:
        i, j = px(*(p + n * d))
        hits.append(0 <= j < H and 0 <= i < W and grey[j, i])
    hits = np.array(hits)
    # first run of grey 6-18 cm wide: its inner edge is the lawn's edge
    best = None; k = 0
    while k < len(hits):
        if hits[k]:
            k2 = k
            while k2 < len(hits) and hits[k2]: k2 += 1
            w = (k2 - k) * a.res
            ii, jj = px(*(p + n * (s[k] - 2 * a.res)))
            inner_ok = 0 <= jj < H and 0 <= ii < W and inside_ok[jj, ii] and not grey[jj, ii]
            if 0.06 <= w <= 0.18 and inner_ok and (best is None or abs(s[k]) < abs(best)): best = s[k]
            k = k2
        else: k += 1
    if best is None: pts.append(p); wts.append(0.25)
    else: pts.append(p + n * best); wts.append(1.0)
pts = np.array(pts); wts = np.array(wts)
if a.hug:
    O = np.array(P[a.hug[0]]["edge"], float); off = float(a.hug[1])
    if 0.5 * np.sum(O[:, 0] * np.roll(O[:, 1], -1) - np.roll(O[:, 0], -1) * O[:, 1]) < 0: O = O[::-1]
    ot = np.roll(O, -1, 0) - np.roll(O, 1, 0); ot /= np.linalg.norm(ot, axis=1)[:, None]
    on = np.stack([ot[:, 1], -ot[:, 0]], 1)
    from scipy.spatial import cKDTree
    dd, jj = cKDTree(O).query(E)
    near = dd < 0.35
    pts[near] = O[jj[near]] + on[jj[near]] * off; wts[near] = 3.0
    print(f"{a.key}: {int(near.sum())} points follow {a.hug[0]} at {off} m")
corners = sorted(int(c) for c in a.corners.split(",") if c != "")
# corners are indices into the (possibly reversed) loop; find them as nearest points to the originals
orig = np.array(P[a.key]["edge"], float)
cpos = [orig[c] for c in corners]
cidx = sorted(int(np.argmin(np.linalg.norm(E - c, axis=1))) for c in cpos)
def fit(seg, w, closed):
    L = np.sum(np.linalg.norm(np.diff(seg, axis=0), axis=1))
    m = max(int(L / a.step), 4)
    # drop near-duplicates (splprep needs distinct points)
    keep = np.r_[True, np.linalg.norm(np.diff(seg, axis=0), axis=1) > 1e-4]
    seg, w = seg[keep], w[keep]
    tck, _ = splprep([seg[:, 0], seg[:, 1]], w=w, s=len(seg) * a.smooth ** 2, per=closed, k=3)
    u = np.linspace(0, 1, m, endpoint=not closed)
    x, y = splev(u, tck); dx, dy = splev(u, tck, der=1); ddx, ddy = splev(u, tck, der=2)
    kappa = (dx * ddy - dy * ddx) / np.power(dx * dx + dy * dy, 1.5)
    return np.stack([x, y], 1), kappa
out, worst = [], 0.0
if not cidx:
    curve, kappa = fit(pts, wts, True); out = curve; worst = np.abs(np.diff(kappa)).max()
else:
    n = len(pts)
    for c0, c1 in zip(cidx, cidx[1:] + [cidx[0] + n]):
        ids = np.arange(c0, c1 + 1) % n
        seg = pts[ids].copy(); w = wts[ids].copy()
        w[0] = w[-1] = 50.0      # corners stay put (on the kerb line, after any --hug)
        curve, kappa = fit(seg, w, False)
        out.extend(curve[:-1]); worst = max(worst, np.abs(np.diff(kappa[2:-2])).max() if len(kappa) > 5 else 0)
    out = np.array(out)
from scipy.spatial import cKDTree
res = cKDTree(out).query(pts[wts > 0.5])[0] if (wts > 0.5).any() else np.array([0])
print(f"{a.key}: kerb found at {int((wts > 0.5).sum())}/{len(wts)} points; fit residual median {np.median(res)*100:.1f} cm, "
      f"90th {np.percentile(res, 90)*100:.1f} cm; largest curvature step {worst:.2f} /m; {len(out)} points")
ok = worst < 2.0
print("CHECK", "PASS" if ok else "FAIL: curvature jumps")
if a.out:
    P[a.key]["edge"] = np.round(out, 3).tolist()
    P[a.key]["source"] = (P[a.key].get("source", "") + "; kerb line re-found in the 1 cm orthophoto and fitted with smoothing splines between true corners (kerb_fit.py)").strip("; ")
    P[a.key]["kerb_detected"] = [np.round(pts[wts > 0.5], 3).tolist()]
    json.dump(P, open(a.out, "w"), indent=1)
sys.exit(0 if ok else 1)
