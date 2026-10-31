"""Find every photo and video frame that sees an element, and crop the best views (WORKFLOW G1/G3).

    ~/splat/bin/python tools/photogrammetry/find_views.py <aligned.json> <out.jpg> --box x0 x1 y0 y1 z0 z1
        [--dirs dir1,dir2] [--n 8] [--name "street hedge"] [--pad 0.3]

The solve was made on reduced frames; any larger copy of the same frame (the 4K extraction) is found in
--dirs by name and the camera is scaled to it, so crops come out at full resolution. Views are ranked by
how many pixels the element covers, how square-on the view is, and whether it is fully in frame.
Writes a contact sheet <out.jpg> and <out>.json (the ranked list) for the inventory."""
import argparse, json, os
import numpy as np
from PIL import Image, ImageOps, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("aligned"); ap.add_argument("out")
ap.add_argument("--box", type=float, nargs=6, required=True)
ap.add_argument("--dirs", default="")
ap.add_argument("--n", type=int, default=8)
ap.add_argument("--name", default="")
ap.add_argument("--pad", type=float, default=0.3, help="metres of context round the element in each crop")
a = ap.parse_args()
d = json.load(open(a.aligned)); S = d["scale"]; R = np.array(d["R"]); T = np.array(d["t"])
x0, x1, y0, y1, z0, z1 = a.box
corners = np.array([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])
padded = np.array([[x, y, z] for x in (x0 - a.pad, x1 + a.pad) for y in (y0 - a.pad, y1 + a.pad) for z in (max(0, z0 - a.pad), z1 + a.pad)])
centre = corners.mean(0)
dirs = [p for p in a.dirs.split(",") if p] + [os.path.join(os.path.dirname(a.aligned), "images")]

def project(c, P):
    M = np.array(c["cam_from_world"]); f, cx, cy, k = c["camera"]["params"][:4]
    pc = ((P - T) @ R / S) @ M[:, :3].T + M[:, 3]
    z = pc[:, 2]; x = pc[:, 0] / np.where(z > 0, z, 1); y = pc[:, 1] / np.where(z > 0, z, 1)
    r2 = x * x + y * y
    return f * x * (1 + k * r2) + cx, f * y * (1 + k * r2) + cy, z

rows = []
for name, c in d["cameras"].items():
    u, v, z = project(c, corners)
    if (z <= 0.2).any(): continue
    w, h = c["camera"]["w"], c["camera"]["h"]
    inside = np.mean((u >= 0) & (u < w) & (v >= 0) & (v < h))
    if inside < 0.5: continue
    area = (np.clip(u, 0, w).max() - np.clip(u, 0, w).min()) * (np.clip(v, 0, h).max() - np.clip(v, 0, h).min()) / (w * h)
    C = np.array(c["centre"]); dist = np.linalg.norm(centre - C)
    rows.append({"name": name, "inside": float(inside), "area": float(area), "dist": float(dist), "score": float(area * inside ** 2)})
rows.sort(key=lambda r: -r["score"])
best = rows[: a.n]
tiles = []
for r in best:
    c = d["cameras"][r["name"]]; w, h = c["camera"]["w"], c["camera"]["h"]
    path = next((os.path.join(p, r["name"]) for p in dirs if os.path.exists(os.path.join(p, r["name"]))), None)
    if not path: continue
    im = Image.open(path).convert("RGB")
    s = im.width / w                                   # the 4K copy of a reduced solve frame
    u, v, _ = project(c, padded)
    bx = [max(0, int(u.min() * s)), max(0, int(v.min() * s)), min(im.width, int(u.max() * s)), min(im.height, int(v.max() * s))]
    if bx[2] - bx[0] < 20 or bx[3] - bx[1] < 20: continue
    crop = im.crop(bx); crop.thumbnail((640, 640))
    t = Image.new("RGB", (640, 680), (20, 20, 20)); t.paste(crop, ((640 - crop.width) // 2, 40))
    ImageDraw.Draw(t).text((6, 6), f"{r['name']}  {r['dist']:.1f} m  {int(crop.width)}px wide of {bx[2]-bx[0]}", fill=(255, 255, 0),
                           font=ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16))
    r["crop_px"] = bx; r["file"] = path; tiles.append(t)
cols = 4; rws = max(1, (len(tiles) + cols - 1) // cols)
sheet = Image.new("RGB", (cols * 640, rws * 680 + 40), (10, 10, 10))
ImageDraw.Draw(sheet).text((8, 8), f"{a.name or 'element'}: box {a.box}  ({len(rows)} views see it)", fill=(255, 255, 255),
                           font=ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20))
for i, t in enumerate(tiles): sheet.paste(t, ((i % cols) * 640, 40 + (i // cols) * 680))
sheet.save(a.out, quality=88)
json.dump({"name": a.name, "box": a.box, "views": len(rows), "best": best}, open(a.out.rsplit(".", 1)[0] + ".json", "w"), indent=1)
print(f"{a.name}: {len(rows)} views; best {[b['name'] for b in best]}")
