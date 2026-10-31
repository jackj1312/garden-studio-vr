"""Matched-view sheets for the house audit (WORKFLOW G6): real | model | real with the model's outlines.

    ~/splat/bin/python tools/blender/house_pairs.py <render_dir> <out.jpg> frame,frame,... [--cols 3] [--crop x0,y0,x1,y1]
        [--panels real,model,overlay] [--title "..."]

The real photo is UNDISTORTED with its solved lens (SIMPLE_RADIAL k) to the pinhole camera the render uses, so lines
can be compared exactly. Overlay: every boundary between objects in <render_dir>/ids/<frame>.png (house_audit_render.py
'ids' pass) is drawn in yellow on the real photo; misfits show as yellow lines off the real edges.
--crop is in fractions of the frame (0-1), to blow up one element."""
import sys, os, json, argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("rd"); ap.add_argument("out"); ap.add_argument("frames")
ap.add_argument("--cols", type=int, default=0); ap.add_argument("--crop", default="")
ap.add_argument("--panels", default="real,model,overlay"); ap.add_argument("--title", default="")
ap.add_argument("--label", default="model")
a = ap.parse_args()
SITE = "/Users/Jack/Desktop/garden-scans/front-garden"
A = json.load(open(f"{SITE}/sfm2/aligned.json"))
F = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)

def real_undistorted(fr, size, meta=None):
    c = A["cameras"][fr]; w, h = c["camera"]["w"], c["camera"]["h"]; f, cx, cy, k = c["camera"]["params"][:4]
    for d in (f"{SITE}/frames4k", f"{SITE}/sfm2/images"):
        p = os.path.join(d, fr)
        if os.path.exists(p): break
    im = np.asarray(Image.open(p).convert("RGB")); s_img = im.shape[1] / w
    W, H = size
    if meta: s = meta["scale"]; ox, oy = meta["window"][0] * s, meta["window"][1] * s     # cropped render window
    else: s = W / w; ox = oy = 0
    uu, vv = np.meshgrid(np.arange(W) + 0.5 + round(ox), np.arange(H) + 0.5 + round(oy))
    x = (uu / s - cx) / f; y = (vv / s - cy) / f; r2 = x * x + y * y
    ud = (f * x * (1 + k * r2) + cx) * s_img; vd = (f * y * (1 + k * r2) + cy) * s_img
    ui = np.clip(ud.astype(int), 0, im.shape[1] - 1); vi = np.clip(vd.astype(int), 0, im.shape[0] - 1)
    # area-average a little when the source is much larger (4K -> 1000 px)
    out = im[vi, ui].astype(np.float32)
    if s_img / s > 1.6:
        o = int(s_img / s / 2)
        for du, dv in ((o, 0), (-o, 0), (0, o), (0, -o)):
            out += im[np.clip(vi + dv, 0, im.shape[0] - 1), np.clip(ui + du, 0, im.shape[1] - 1)]
        out /= 5
    return Image.fromarray(out.astype(np.uint8))

def outline(ids_path, base):
    idm = np.asarray(Image.open(ids_path).convert("RGBA")).astype(np.int32)
    col = idm[..., :3].copy(); col[idm[..., 3] < 128] = -200          # background is its own "object"
    def diff(a, b): return np.abs(a - b).sum(-1) > 40                 # ignore dither noise inside a face
    e = np.zeros(col.shape[:2], bool)
    e[:, 1:] |= diff(col[:, 1:], col[:, :-1]); e[1:, :] |= diff(col[1:, :], col[:-1, :])
    b = np.asarray(base).copy(); b = (b * 0.85).astype(np.uint8)
    b[e] = (255, 230, 0)
    return Image.fromarray(b)

panels_wanted = a.panels.split(",")
tiles = []
for fr in a.frames.split(","):
    mp = os.path.join(a.rd, fr.replace(".jpg", ".png"))
    ip = os.path.join(a.rd, "ids", fr.replace(".jpg", ".png"))
    ref = Image.open(mp if os.path.exists(mp) else ip).convert("RGB")
    mf = os.path.join(a.rd, "meta.json"); META = json.load(open(mf)) if os.path.exists(mf) else {}
    real = real_undistorted(fr, ref.size, META.get(fr))
    P = {"real": real, "model": ref, "overlay": outline(ip, real) if os.path.exists(ip) else real}
    ims = [P[p] for p in panels_wanted]
    orient = Image.open(f"{SITE}/sfm2/images/{fr}").getexif().get(274, 1) if os.path.exists(f"{SITE}/sfm2/images/{fr}") else 1
    if not fr.startswith("walk_") and orient in (6, 8, 3):              # stills: show upright (the solve is unrotated)
        ims = [i.transpose({6: Image.ROTATE_270, 8: Image.ROTATE_90, 3: Image.ROTATE_180}[orient]) for i in ims]
    if a.crop:
        x0, y0, x1, y1 = [float(v) for v in a.crop.split(",")]
        ims = [i.crop((int(x0 * i.width), int(y0 * i.height), int(x1 * i.width), int(y1 * i.height))) for i in ims]
        ims = [i.resize((int(i.width * 900 / max(i.size)), int(i.height * 900 / max(i.size)))) for i in ims]
    W, H = ims[0].size
    t = Image.new("RGB", (len(ims) * (W + 6), H + 28), (18, 18, 18))
    for i, im in enumerate(ims): t.paste(im, (i * (W + 6), 28))
    ImageDraw.Draw(t).text((6, 4), f"{fr}: " + " | ".join("real" if p == "real" else a.label if p == "model" else "real + model outline" for p in panels_wanted),
                           fill=(240, 240, 240), font=F)
    tiles.append(t)
cols = a.cols or (1 if len(tiles) == 1 else 2)
W = max(t.width for t in tiles); H = max(t.height for t in tiles); top = 40 if a.title else 0
sheet = Image.new("RGB", (cols * W, top + ((len(tiles) + cols - 1) // cols) * H), (10, 10, 10))
if a.title: ImageDraw.Draw(sheet).text((8, 8), a.title, fill=(255, 255, 255), font=ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24))
for i, t in enumerate(tiles): sheet.paste(t, ((i % cols) * W, top + (i // cols) * H))
if max(sheet.size) > 4000: sheet.thumbnail((4000, 4000))
sheet.save(a.out, quality=88); print(a.out, sheet.size)
