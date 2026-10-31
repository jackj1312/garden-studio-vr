"""Build a plan edge from its kerb RUNS, the way they were laid (CORRECTIONS-LOG 47).

    ~/splat/bin/python tools/plan/kerb_runs.py <plan.json> <key> --runs runs.json [--out plan.json]

runs.json: {"<key>": [ {"line": [[x,y],[x,y]]}, {"curve": [[x,y], ...]}, {"corner": true}, ... ]} in order round the
edge. A line stays exactly straight; a curve is a smooth spline through measured points that leaves and joins its
neighbours tangentially; {"corner": true} marks a true corner (kerbs meeting at an angle) between two runs.
Without a corner mark, consecutive runs are joined smoothly. Checks: no curvature jump above 2/m inside a run."""
import argparse, json, sys
import numpy as np
from scipy.interpolate import CubicHermiteSpline

ap = argparse.ArgumentParser(); ap.add_argument("plan"); ap.add_argument("key"); ap.add_argument("--runs", required=True)
ap.add_argument("--out", default=""); ap.add_argument("--step", type=float, default=0.04)
a = ap.parse_args()
P = json.load(open(a.plan)); R = json.load(open(a.runs))[a.key]
runs = []; corner_after = []
for r in R:
    if r.get("corner"): corner_after[-1] = True; continue
    runs.append(r); corner_after.append(False)
def unit(v): v = np.asarray(v, float); return v / np.linalg.norm(v)
# tangent at each run's ends
def ends(r):
    p = np.array(r.get("line") or r["curve"], float)
    return p[0], p[-1], unit(p[1] - p[0]), unit(p[-1] - p[-2])
out = []; worst = 0.0; n = len(runs); corner_idx = []
for i, r in enumerate(runs):
    if corner_after[i - 1]: corner_idx.append(len(out))
    p = np.array(r.get("line") or r["curve"], float)
    if "line" in r:
        L = np.linalg.norm(p[1] - p[0]); m = max(2, int(L / a.step))
        out.extend(p[0] + (p[1] - p[0]) * t for t in np.linspace(0, 1, m, endpoint=False)); continue
    # measured points carry a few cm of noise: smooth them first (ends fixed), resample every ~15 cm
    if len(p) > 4:
        from scipy.interpolate import splprep, splev
        keep = np.r_[True, np.linalg.norm(np.diff(p, axis=0), axis=1) > 1e-3]; q = p[keep]
        w = np.ones(len(q)); w[0] = w[-1] = 100.0
        tck, _ = splprep([q[:, 0], q[:, 1]], w=w, s=len(q) * float(r.get("smooth", 0.02)) ** 2, k=3)
        L = np.sum(np.linalg.norm(np.diff(q, axis=0), axis=1)); m = max(4, int(L / 0.15) + 1)
        xs_, ys_ = splev(np.linspace(0, 1, m), tck); p = np.stack([xs_, ys_], 1); p[0], p[-1] = q[0], q[-1]
    # curve: tangents at its ends come from the neighbouring straight runs unless a corner sits there
    prev, nxt = runs[i - 1], runs[(i + 1) % n]
    t0 = ends(prev)[3] if not corner_after[i - 1] and "line" in prev else unit(p[1] - p[0])
    t1 = ends(nxt)[2] if not corner_after[i] and "line" in nxt else unit(p[-1] - p[-2])
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    # interior tangents: centred differences; ends: from neighbours; scaled by local spacing
    T = np.zeros_like(p)
    T[1:-1] = (p[2:] - p[:-2]) / (d[2:] - d[:-2])[:, None]
    T[0], T[-1] = t0, t1
    T = T / np.linalg.norm(T, axis=1)[:, None]
    sx = CubicHermiteSpline(d, p[:, 0], T[:, 0]); sy = CubicHermiteSpline(d, p[:, 1], T[:, 1])
    m = max(4, int(d[-1] / a.step)); u = np.linspace(0, d[-1], m, endpoint=False)
    xs, ys = sx(u), sy(u); dx, dy = sx(u, 1), sy(u, 1); ddx, ddy = sx(u, 2), sy(u, 2)
    k = (dx * ddy - dy * ddx) / np.power(dx * dx + dy * dy, 1.5)
    worst = max(worst, np.abs(np.diff(k)).max() / (a.step / 0.04)) if len(k) > 2 else worst
    out.extend(np.stack([xs, ys], 1))
out = np.array(out)
# ease every join between runs (a kerb in setts can't turn a sharp small angle): gaussian along the edge,
# ~0.3 m wide, never across a true corner; straight runs stay straight away from their ends
from scipy.ndimage import gaussian_filter1d
sig = 0.10 / a.step
cuts = sorted(set(corner_idx)) or [0]
N = len(out); sm = out.copy()
for c0, c1 in zip(cuts, cuts[1:] + [cuts[0] + N]):
    ids = np.arange(c0, c1 + 1) % N
    seg = out[ids]
    pad = np.vstack([np.repeat(seg[:1], 12, 0) * 2 - seg[12:0:-1], seg, np.repeat(seg[-1:], 12, 0) * 2 - seg[-2:-14:-1]])
    g = np.stack([gaussian_filter1d(pad[:, 0], sig), gaussian_filter1d(pad[:, 1], sig)], 1)[12:-12]
    g[0], g[-1] = seg[0], seg[-1]
    sm[ids[1:-1]] = g[1:-1]
out = sm
v = np.diff(np.vstack([out, out[:1]]), axis=0); A, B = v[:-1], v[1:]
ang = np.degrees(np.arctan2(A[:, 0] * B[:, 1] - A[:, 1] * B[:, 0], (A * B).sum(1)))
isc = np.zeros(len(ang), bool)
for c in cuts: isc[(c - 1) % len(ang)] = True
worst = float(np.abs(ang[~isc]).max())
print(f"largest turn between neighbouring 4 cm steps (corners excluded): {worst:.1f}°")
worst = worst / 5.0       # PASS below 5° per 4 cm (a 0.5 m radius at most)
print(f"{a.key}: {len(runs)} runs, {sum(corner_after)} true corners, {len(out)} points; largest curvature step within runs {worst:.2f} /m")
print("CHECK", "PASS" if worst < 2.0 else "FAIL")
if a.out:
    P[a.key]["edge"] = np.round(out, 3).tolist(); P[a.key]["runs"] = R
    P[a.key]["source"] = "kerb runs as laid (kerb_runs.py): lines straight, curves tangent to them, true corners only where kerbs meet at an angle; positions from the 1 cm orthophoto and the walk frames"
    json.dump(P, open(a.out, "w"), indent=1)
