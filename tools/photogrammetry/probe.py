"""Draw measured 3D lines on the real photos (with the solved lens), to test a measurement against every view.

    ~/splat/bin/python tools/photogrammetry/probe.py <out.jpg> --frames walk_0049.jpg,... --lines lines.json [--pad 80] [--w 700]
    lines.json: {"name": [[x,y,z],[x,y,z],...], ...}  (plan metres; a name starting "*" is drawn dashed-red, others cycle colours)

Each frame is cropped round the lines (plus --pad px) at full resolution (4K walk frames, stills), stills shown upright.
Used for the house audit (G6): e.g. the porch's front corner drawn at y 0.87 vs 1.15 shows which one sits on the bricks."""
import argparse, json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--frames", required=True); ap.add_argument("--lines", required=True)
ap.add_argument("--pad", type=int, default=80); ap.add_argument("--w", type=int, default=700); ap.add_argument("--cols", type=int, default=0)
ap.add_argument("--full", action="store_true", help="whole frame, not a crop")
a = ap.parse_args()
SITE = "/Users/Jack/Desktop/garden-scans/front-garden"
d = json.load(open(f"{SITE}/sfm2/aligned.json")); S = d["scale"]; R = np.array(d["R"]); T = np.array(d["t"])
L = json.load(open(a.lines)) if os.path.exists(a.lines) else json.loads(a.lines)
COLS = [(255, 230, 0), (0, 255, 255), (255, 80, 255), (120, 255, 80), (255, 150, 40), (90, 140, 255)]
F = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 15)

def proj(c, P, s):
    M = np.array(c["cam_from_world"]); f, cx, cy, k = c["camera"]["params"][:4]
    pc = ((np.asarray(P, float) - T) @ R / S) @ M[:, :3].T + M[:, 3]
    z = pc[:, 2]; x = pc[:, 0] / np.where(z > 0.05, z, np.nan); y = pc[:, 1] / np.where(z > 0.05, z, np.nan); r2 = x * x + y * y
    return np.stack([(f * x * (1 + k * r2) + cx) * s, (f * y * (1 + k * r2) + cy) * s], 1)

tiles = []
for fr in a.frames.split(","):
    c = d["cameras"][fr]
    p = next(q for q in (f"{SITE}/frames4k/{fr}", f"{SITE}/sfm2/images/{fr}") if os.path.exists(q))
    im = Image.open(p).convert("RGB"); s = im.width / c["camera"]["w"]
    dr = ImageDraw.Draw(im); allp = []
    for i, (nm, pts) in enumerate(L.items()):
        pts = np.asarray(pts, float)
        dense = np.concatenate([np.linspace(pts[j], pts[j + 1], 40) for j in range(len(pts) - 1)]) if len(pts) > 1 else pts
        uv = proj(c, dense, s); ok = np.isfinite(uv).all(1)
        col = (255, 40, 40) if nm.startswith("*") else COLS[i % len(COLS)]
        lw = max(2, int(im.width / 900))
        for j in range(len(uv) - 1):
            if ok[j] and ok[j + 1] and (not nm.startswith("*") or (j // 4) % 2 == 0):
                dr.line([tuple(uv[j]), tuple(uv[j + 1])], fill=col, width=lw)
        if ok.any():
            q = uv[ok][0]; dr.text((q[0] + 4, q[1] - 16), nm.lstrip("*"), fill=col, font=ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(14 * s * 1.3)))
            allp.append(uv[ok])
    if not allp: continue
    allp = np.concatenate(allp)
    allp = allp[(allp[:, 0] >= 0) & (allp[:, 0] < im.width) & (allp[:, 1] >= 0) & (allp[:, 1] < im.height)]   # lines running out of frame
    if not len(allp): continue
    if not a.full:
        x0, y0 = np.clip(allp.min(0) - a.pad * s, 0, None); x1, y1 = allp.max(0) + a.pad * s
        im = im.crop((int(x0), int(y0), int(min(x1, im.width)), int(min(y1, im.height))))
    orient = Image.open(p).getexif().get(274, 1)
    if not fr.startswith("walk_") and orient in (6, 8, 3): im = im.transpose({6: Image.ROTATE_270, 8: Image.ROTATE_90, 3: Image.ROTATE_180}[orient])
    im.thumbnail((a.w, a.w)); t = Image.new("RGB", (im.width, im.height + 22), (15, 15, 15)); t.paste(im, (0, 22))
    ImageDraw.Draw(t).text((4, 3), fr, fill=(255, 255, 255), font=F); tiles.append(t)
cols = a.cols or min(4, len(tiles)); W = max(t.width for t in tiles); H = max(t.height for t in tiles)
sheet = Image.new("RGB", (cols * W, ((len(tiles) + cols - 1) // cols) * H), (8, 8, 8))
for i, t in enumerate(tiles): sheet.paste(t, ((i % cols) * W, (i // cols) * H))
sheet.save(a.out, quality=90); print(a.out, sheet.size)
