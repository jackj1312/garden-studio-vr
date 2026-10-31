"""Rigid lock of the photo solve to the scan at a series of fixed scales.
For each scale: rigid ICP on the overlap only; report how much of the house
front sits on the scan (inliers within 5 cm), phone heights, and pergola post
spacing. The true scale is where these agree.

    ~/splat/bin/python tools/photogrammetry/align_fixed_scale.py <model> <scan.npy> <coarse aligned.json> <out.json> [s0 s1 n]
"""
import sys, json
import numpy as np
import pycolmap as p
from scipy.spatial import cKDTree
model, scan_npy, coarse_json, out_json = sys.argv[1:5]
s0, s1, n = (float(sys.argv[5]), float(sys.argv[6]), int(sys.argv[7])) if len(sys.argv) > 7 else (0.8, 1.2, 17)
rec = p.Reconstruction(model)
ids = [k for k, pt in rec.points3D.items() if pt.error < 2.0]
pts = np.array([rec.points3D[k].xyz for k in ids])
cams = {img.name: img.projection_center() for img in rec.images.values()}
scan = np.load(scan_npy); tree = cKDTree(scan)
c = json.load(open(coarse_json)); S0, R0, T0 = c["scale"], np.array(c["R"]), np.array(c["t"])

def rigid(A, B):
    ma, mb = A.mean(0), B.mean(0)
    U, _, Vt = np.linalg.svd((B - mb).T @ (A - ma))
    D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt
    return R, mb - R @ ma

rows = []
for s in np.linspace(s0, s1, n):
    S = S0 * s
    # start from the coarse pose, rescaled about the coarse cloud's centre of overlap
    cur0 = S0 * pts @ R0.T + T0
    centre = np.median(cur0[tree.query(cur0)[0] < 0.5], axis=0)
    R, T = R0.copy(), centre - S * (R0 @ np.median(pts[tree.query(cur0)[0] < 0.5], axis=0))
    for thr in (0.6, 0.4, 0.25, 0.15, 0.1):
        for _ in range(12):
            cur = S * pts @ R.T + T
            dist, idx = tree.query(cur)
            keep = dist < thr
            if keep.sum() < 300: break
            dR, dT = rigid(cur[keep], scan[idx[keep]])
            R, T = dR @ R, dR @ T + dT
    cur = S * pts @ R.T + T
    dist, _ = tree.query(cur)
    inl = int((dist < 0.05).sum())
    hz = np.median([(S * R @ C + T)[2] for C in cams.values()])
    q = cur[(cur[:, 2] > 0.5) & (cur[:, 2] < 2.2) & (cur[:, 1] > -1.8) & (cur[:, 1] < -0.9)]
    h, e = np.histogram(q[:, 0], bins=np.arange(-3, 6, 0.1))
    peaks = sorted(round(e[i] + 0.05, 2) for i in np.argsort(-h)[:3])
    rows.append((s, inl, hz, peaks, S, R, T))
    print(f"scale x{s:.3f}: on-scan points {inl:6d}   phone height {hz:.2f} m   post columns {peaks}", flush=True)
json.dump([{"s": float(r[0]), "S": float(r[4]), "R": r[5].tolist(), "T": r[6].tolist(), "inliers": r[1], "height": float(r[2])} for r in rows],
          open(out_json.replace(".json", "_candidates.json"), "w"))
best = max(rows, key=lambda r: r[1])
s, inl, hz, peaks, S, R, T = best
print(f"best by fit: x{s:.3f} (phone height {hz:.2f} m)")
out = {"scale": S, "R": R.tolist(), "t": T.tolist(), "cameras": {}, "points": []}
for img in rec.images.values():
    cam = rec.cameras[img.camera_id]
    out["cameras"][img.name] = {"centre": (S * R @ img.projection_center() + T).tolist(),
                                "cam_from_world": img.cam_from_world().matrix().tolist(),
                                "camera": {"model": cam.model.name, "w": cam.width, "h": cam.height, "params": list(cam.params)}}
for k in ids:
    pt = rec.points3D[k]
    out["points"].append([*(S * R @ pt.xyz + T).tolist(), *[int(v) for v in pt.color]])
json.dump(out, open(out_json, "w"))
