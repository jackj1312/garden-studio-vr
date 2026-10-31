"""True-scale top-down photo (orthophoto) of the ground from solved cameras.

    ~/splat/bin/python tools/photogrammetry/ortho.py <aligned.json> <image_dir> <out.png> [cm_per_px] [x0 x1 y0 y1]

Every ground cell (z = 0; the ground is flat to ~5 cm on Jack's site) is projected into
every camera. Each cell takes the median colour of its 3 nearest cameras that see it,
which removes most things standing on the ground (posts, legs, a passing foot).
Writes <out.png> and <out>.npz (rgb, extent) for edge tracing.
"""
import sys, json
import numpy as np
from PIL import Image

aj, idir, out = sys.argv[1], sys.argv[2], sys.argv[3]
res = float(sys.argv[4]) / 100 if len(sys.argv) > 4 else 0.04
X0, X1, Y0, Y1 = map(float, sys.argv[5:9]) if len(sys.argv) > 8 else (-7, 8, -19.5, 1)
d = json.load(open(aj)); S = d["scale"]; R = np.array(d["R"]); T = np.array(d["t"])
xs = np.arange(X0 + res / 2, X1, res); ys = np.arange(Y1 - res / 2, Y0, -res)
GX, GY = np.meshgrid(xs, ys); P = np.stack([GX.ravel(), GY.ravel(), np.zeros(GX.size)], 1)
Psfm = ((P - T) @ R) / S                       # world -> SfM frame
K = 3
best_d = np.full((GX.size, K), np.inf, np.float32); best_c = np.zeros((GX.size, K, 3), np.uint8)
used = 0
for name, c in d["cameras"].items():
    C = np.array(c["centre"])
    if not (1.2 < C[2] < 2.0): continue        # a bad pose (camera far off head height) is skipped
    M = np.array(c["cam_from_world"]); f, cx, cy, k = c["camera"]["params"][:4]
    pc = Psfm @ M[:, :3].T + M[:, 3]
    z = pc[:, 2]; ok = z > 0.05
    x = np.where(ok, pc[:, 0] / np.where(ok, z, 1), 0); y = np.where(ok, pc[:, 1] / np.where(ok, z, 1), 0)
    r2 = x * x + y * y; ok &= r2 < 1.2
    u = f * x * (1 + k * r2) + cx; v = f * y * (1 + k * r2) + cy
    w, h = c["camera"]["w"], c["camera"]["h"]
    ok &= (u >= 1) & (u < w - 1) & (v >= 1) & (v < h - 1)
    dist = np.linalg.norm(P - C, axis=1).astype(np.float32)
    ok &= dist < float(__import__("os").environ.get("MAXD", "9.0"))
    if ok.sum() == 0: continue
    im = np.asarray(Image.open(f"{idir}/{name}").convert("RGB"))
    if im.shape[1] != w: im = np.asarray(Image.open(f"{idir}/{name}").convert("RGB").resize((w, h)))
    idx = np.nonzero(ok)[0]
    col = im[v[idx].astype(int), u[idx].astype(int)]
    dd = dist[idx]
    # insert into the K-nearest lists
    worst = best_d[idx].argmax(1); repl = dd < best_d[idx, worst]
    ii = idx[repl]; best_d[ii, worst[repl]] = dd[repl]; best_c[ii, worst[repl]] = col[repl]
    used += 1
n = np.isfinite(best_d).sum(1)
med = np.where(n[:, None] >= 2, np.median(np.where(np.isfinite(best_d)[..., None], best_c, np.nan), 1), np.nan)
rgb = np.nan_to_num(med, nan=255).reshape(GX.shape + (3,)).astype(np.uint8)
seen = (n >= 1).reshape(GX.shape)
rgb[~seen] = 255
Image.fromarray(rgb).save(out)
np.savez_compressed(out.rsplit(".", 1)[0] + ".npz", rgb=rgb, seen=seen, extent=np.array([X0, X1, Y0, Y1]), res=res)
print(f"{used} cameras, {rgb.shape[1]}x{rgb.shape[0]} px at {res*100:.0f} cm/px, {seen.mean()*100:.0f}% seen")
