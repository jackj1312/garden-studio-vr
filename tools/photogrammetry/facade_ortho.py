"""True-scale straight-on photo of a wall (an elevation), from solved cameras — the ground
orthophoto method turned upright. The wall is a vertical plane: y = const (a front face) or
x = const (a side face).

    ~/splat/bin/python tools/photogrammetry/facade_ortho.py <aligned.json> <image_dir> <out.png>
        --plane y 0.68 --range 0.4 4.8 --z 0 7 [--res 0.01] [--cams name,name] [--k 3] [--maxd 14]

Every cell is projected into every camera that faces the wall; it takes the median colour of the
k nearest, most face-on views (so a tree branch or a post in one photo drops out)."""
import argparse, json
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("aligned"); ap.add_argument("images"); ap.add_argument("out")
ap.add_argument("--plane", nargs=2, required=True); ap.add_argument("--range", type=float, nargs=2, required=True)
ap.add_argument("--z", type=float, nargs=2, default=(0, 7)); ap.add_argument("--res", type=float, default=0.01)
ap.add_argument("--cams", default=""); ap.add_argument("--k", type=int, default=3); ap.add_argument("--maxd", type=float, default=14)
a = ap.parse_args()
d = json.load(open(a.aligned)); S = d["scale"]; R = np.array(d["R"]); T = np.array(d["t"])
axis, val = a.plane[0], float(a.plane[1])
us = np.arange(a.range[0] + a.res / 2, a.range[1], a.res); zs = np.arange(a.z[1] - a.res / 2, a.z[0], -a.res)
U, Z = np.meshgrid(us, zs)
P = np.stack([U.ravel(), np.full(U.size, val), Z.ravel()], 1) if axis == "y" else np.stack([np.full(U.size, val), U.ravel(), Z.ravel()], 1)
normal = np.array([0, -1, 0.]) if axis == "y" else np.array([1., 0, 0])     # front faces look to -y (the road); side: +x or -x picked per camera
Psfm = ((P - T) @ R) / S
K = a.k
best = np.full((len(P), K), np.inf, np.float32); bc = np.zeros((len(P), K, 3), np.uint8)
names = [n for n in d["cameras"] if (not a.cams or n in a.cams.split(","))]
used = 0
for name in names:
    c = d["cameras"][name]; C = np.array(c["centre"])
    v = P - C; dist = np.linalg.norm(v, axis=1)
    n = normal if axis == "y" else (np.array([1., 0, 0]) if C[0] > val else np.array([-1., 0, 0]))
    cosang = -(v @ n) / np.maximum(dist, 1e-6)                    # how face-on the view is
    M = np.array(c["cam_from_world"]); f, cx, cy, k = c["camera"]["params"][:4]
    pc = Psfm @ M[:, :3].T + M[:, 3]; z = pc[:, 2]; ok = (z > 0.1) & (cosang > 0.35) & (dist < a.maxd)
    x = np.where(ok, pc[:, 0] / np.where(ok, z, 1), 0); y = np.where(ok, pc[:, 1] / np.where(ok, z, 1), 0)
    r2 = x * x + y * y; ok &= r2 < 1.5
    uu = f * x * (1 + k * r2) + cx; vv = f * y * (1 + k * r2) + cy
    w, h = c["camera"]["w"], c["camera"]["h"]; ok &= (uu >= 1) & (uu < w - 1) & (vv >= 1) & (vv < h - 1)
    if ok.sum() < 100: continue
    im = Image.open(f"{a.images}/{name}").convert("RGB")
    if im.size != (w, h): im = im.resize((w, h))
    im = np.asarray(im)
    idx = np.nonzero(ok)[0]; col = im[vv[idx].astype(int), uu[idx].astype(int)]
    score = (dist[idx] / np.maximum(cosang[idx], 0.2)).astype(np.float32)   # near and face-on wins
    worst = best[idx].argmax(1); rep = score < best[idx, worst]
    ii = idx[rep]; best[ii, worst[rep]] = score[rep]; bc[ii, worst[rep]] = col[rep]; used += 1
n = np.isfinite(best).sum(1)
med = np.where(n[:, None] >= 1, np.nanmedian(np.where(np.isfinite(best)[..., None], bc, np.nan), 1), 255)
img = np.nan_to_num(med, nan=255).reshape(U.shape + (3,)).astype(np.uint8)
Image.fromarray(img).save(a.out)
print(f"{used} cameras, {img.shape[1]}x{img.shape[0]} px at {a.res*100:.0f} mm... cm/px: {a.res*100:.1f}")
