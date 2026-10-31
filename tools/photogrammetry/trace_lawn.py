"""Trace the lawn edge from an orthophoto (ortho.py) by colour, as a smooth measured curve.

    ~/splat/bin/python tools/photogrammetry/trace_lawn.py <ortho.npz> <out.json> <preview.png> [cx cy] [x0 x1 y0 y1]

Lawn = excess-green pixels (2g - r - b on chromaticity), cleaned, largest piece. The edge is
found along rays every 1 degree from a centre inside the lawn, then smoothed along the curve
(circular Gaussian, ~15 cm) so stray tufts and gravel specks don't make it wobble.
"""
import sys, json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as nd

z = np.load(sys.argv[1]); out, prev = sys.argv[2], sys.argv[3]
cx, cy = (float(sys.argv[4]), float(sys.argv[5])) if len(sys.argv) > 5 else (0.0, -6.0)
box = list(map(float, sys.argv[6:10])) if len(sys.argv) > 9 else [-4.35, 3.9, -13.5, -0.9]
rgb = z["rgb"].astype(float); X0, X1, Y0, Y1 = z["extent"]; r = float(z["res"]); seen = z["seen"]
s = rgb.sum(2) + 1
exg = nd.gaussian_filter(2 * rgb[..., 1] / s - rgb[..., 0] / s - rgb[..., 2] / s, 1.5)
H, W = exg.shape
I, J = np.mgrid[0:H, 0:W]; X = X0 + (J + 0.5) * r; Y = Y1 - (I + 0.5) * r
inbox = (X > box[0]) & (X < box[1]) & (Y > box[2]) & (Y < box[3])
m = (exg > 0.15) & inbox & seen
m = nd.binary_closing(m, iterations=3); m = nd.binary_opening(m, iterations=4)
lab, n = nd.label(m); m = lab == (np.bincount(lab.ravel())[1:].argmax() + 1)
m = nd.binary_fill_holes(m)
pts = []
for a in np.radians(np.arange(0, 360, 1.0)):
    dx, dy = np.cos(a), np.sin(a); last = 0.0; t = 0.0; gap = 0.0
    while t < 14:
        t += r / 2; x, y = cx + dx * t, cy + dy * t
        i, j = int((Y1 - y) / r), int((x - X0) / r)
        if not (0 <= i < H and 0 <= j < W): break
        if m[i, j]: last, gap = t, 0.0
        else:
            gap += r / 2
            if gap > 0.3: break
    pts.append(last)
rad = np.array(pts)
rs = nd.gaussian_filter1d(rad, 2.0, mode="wrap")         # ~2 degrees: keeps the corners, drops specks
ang = np.radians(np.arange(0, 360, 1.0))
edge = np.stack([cx + np.cos(ang) * rs, cy + np.sin(ang) * rs], 1)
res = np.abs(rad - rs)
json.dump({"edge": np.round(edge, 3).tolist(), "centre": [cx, cy], "raw_radius": np.round(rad, 3).tolist(),
           "smoothing_residual_cm": {"median": float(np.median(res) * 100), "p90": float(np.percentile(res, 90) * 100)},
           "area_m2": float(m.sum() * r * r)}, open(out, "w"))
im = Image.fromarray(z["rgb"]); d = ImageDraw.Draw(im)
q = [((x - X0) / r, (Y1 - y) / r) for x, y in edge]; d.line(q + [q[0]], fill=(255, 0, 255), width=3)
for gx in range(int(X0), int(X1) + 1): d.line([((gx - X0) / r, 0), ((gx - X0) / r, H)], fill=(255, 0, 0) if gx == 0 else (80, 80, 80))
for gy in range(int(Y0), int(Y1) + 1): d.line([(0, (Y1 - gy) / r), (W, (Y1 - gy) / r)], fill=(255, 0, 0) if gy == 0 else (80, 80, 80))
im.save(prev)
print(f"area {m.sum()*r*r:.1f} m2; smoothing residual median {np.median(res)*100:.1f} cm, 90th {np.percentile(res,90)*100:.1f} cm")
