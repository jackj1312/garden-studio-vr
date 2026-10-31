"""Lock a structure-from-motion model onto the measured scan (similarity: scale,
rotation, translation), then write every camera and every 3D point in the scan's
metres, so photos can be used as measuring instruments.

    ~/splat/bin/python tools/photogrammetry/align.py <sparse-model-dir> <scan_points.npy> <out.json>

Method: the ground is the biggest near-horizontal plane in the sparse points; the
house front is the biggest plane square to it. That fixes up and the facade
direction. Scale and the remaining offsets come from trimmed ICP (Umeyama with
scale) against the scan's vertices, run from several starting turns so it can't
lock onto the wrong side of the house.
"""
import sys, json
import numpy as np
import pycolmap as p

model_dir, scan_npy, out_json = sys.argv[1], sys.argv[2], sys.argv[3]
rec = p.Reconstruction(model_dir)
pts = np.array([pt.xyz for pt in rec.points3D.values()])
err = np.array([pt.error for pt in rec.points3D.values()])
pts = pts[err < 2.0]
scan = np.load(scan_npy)
rng = np.random.default_rng(0)
scan_s = scan[rng.choice(len(scan), min(40000, len(scan)), replace=False)]

def plane_ransac(P, iters=3000, tol=None, mask_normal=None):
    if tol is None:
        tol = 0.01 * np.linalg.norm(P.max(0) - P.min(0))
    best = (0, None, None)
    for _ in range(iters):
        a, b, c = P[rng.choice(len(P), 3, replace=False)]
        n = np.cross(b - a, c - a); L = np.linalg.norm(n)
        if L < 1e-9: continue
        n /= L
        if mask_normal is not None and abs(n @ mask_normal) > 0.2: continue
        d = -n @ a
        inl = np.abs(P @ n + d) < tol
        if inl.sum() > best[0]: best = (inl.sum(), n, d)
    return best

def umeyama(A, B):
    """s, R, t minimising |s R A + t - B|"""
    ma, mb = A.mean(0), B.mean(0)
    A0, B0 = A - ma, B - mb
    U, S, Vt = np.linalg.svd(B0.T @ A0 / len(A))
    D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt
    s = np.trace(np.diag(S) @ D) / (A0 ** 2).sum() * len(A)
    return s, R, mb - s * R @ ma

from scipy.spatial import cKDTree
_trees = {}
def nn(Q, ref):
    key = id(ref)
    if key not in _trees:
        _trees[key] = cKDTree(ref)
    dist, idx = _trees[key].query(Q)
    return idx, dist

# 1. up and facade from planes
ng, gn, gd = plane_ransac(pts)
# the ground has the cameras above it: orient its normal towards the camera centres
cams = np.array([img.projection_center() for img in rec.images.values()])
if ((cams @ gn + gd) < 0).mean() > 0.5: gn, gd = -gn, -gd
nf, fn, fd = plane_ransac(pts, mask_normal=gn)
# facade faces the cameras (the road side)
if ((cams @ fn + fd) < 0).mean() > 0.5: fn, fd = -fn, -fd
z = gn; y = -fn; y -= z * (y @ z); y /= np.linalg.norm(y); x = np.cross(y, z)
R0 = np.stack([x, y, z])                      # rows: sfm -> (x along facade, y into house, z up)
P0 = pts @ R0.T
# scale guess: facade width of the sparse cloud near the facade plane vs the scan's
near = np.abs(pts @ fn + fd) < 0.02 * np.linalg.norm(pts.max(0) - pts.min(0))
w_sfm = np.percentile(P0[near, 0], 95) - np.percentile(P0[near, 0], 5)
w_scan = np.percentile(scan[:, 0], 95) - np.percentile(scan[:, 0], 5)
s0 = w_scan / max(w_sfm, 1e-9)
best = None
for flip in (False, True):
    for dyaw in np.radians([-10, -5, 0, 5, 10]):
        c, s_ = np.cos(dyaw), np.sin(dyaw)
        Rz = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])
        F = np.diag([-1, -1, 1]) if flip else np.eye(3)
        R = Rz @ F @ R0
        A = (pts @ R.T) * s0
        # translation: ground to z=0, centre the facade
        t = np.array([np.median(scan[:, 0]) - np.median(A[near, 0]), np.median(scan[scan[:, 2] > 1.5, 1]) - np.median(A[near, 1]),
                      -np.percentile(A[:, 2], 10)])
        S, Rt, T = s0, R, t
        Q = pts
        for it in range(40):
            cur = S * (Q @ Rt.T) + T
            idx, dist = nn(cur, scan_s)
            keep = dist < np.percentile(dist, 70)
            s2, R2, t2 = umeyama(Q[keep], scan_s[idx[keep]])
            S, Rt, T = s2, R2, t2
        cur = S * (Q @ Rt.T) + T
        idx, dist = nn(cur, scan_s)
        score = np.median(dist)
        if best is None or score < best[0]:
            best = (score, S, Rt, T, np.percentile(dist, 70))
score, S, Rt, T, p70 = best
print(f"coarse: scale {S:.4f}, median residual {score*100:.1f} cm")
# refine on overlap only: points with no scan underneath (lawn, drive) must not pull the fit
for thr in ():   # free-scale refinement shrinks the model; scale is fixed separately (align_fixed_scale.py)
    for it in range(15):
        cur = S * (pts @ Rt.T) + T
        idx, dist = nn(cur, scan_s)
        keep = dist < thr
        if keep.sum() < 200: break
        S, Rt, T = umeyama(pts[keep], scan_s[idx[keep]])
cur = S * (pts @ Rt.T) + T
idx, dist = nn(cur, scan_s)
inl = dist < 0.08
print(f"aligned: scale {S:.4f}, {inl.sum()} overlap points, residual on them median {np.median(dist[inl])*100:.1f} cm, 90th {np.percentile(dist[inl],90)*100:.1f} cm")
out = {"scale": S, "R": Rt.tolist(), "t": T.tolist(), "median_residual_m": float(score),
       "cameras": {}, "points": []}
for img in rec.images.values():
    C = S * (Rt @ img.projection_center()) + T
    cam = rec.cameras[img.camera_id]
    out["cameras"][img.name] = {"centre": C.tolist(), "cam_from_world": img.cam_from_world().matrix().tolist(),
                                "camera": {"model": cam.model.name, "w": cam.width, "h": cam.height, "params": list(cam.params)}}
for pt in rec.points3D.values():
    if pt.error < 2.0:
        out["points"].append([*(S * (Rt @ pt.xyz) + T).tolist(), *[int(c) for c in pt.color]])
json.dump(out, open(out_json, "w"))
print(f"wrote {len(out['cameras'])} cameras, {len(out['points'])} points")
