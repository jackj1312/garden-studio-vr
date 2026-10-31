"""Cut every whole brick out of a straight-on close-up of a wall, by its mortar lines (WORKFLOW G4).
    ~/splat/bin/python tools/phototex/brick_library.py <photo> <out_dir> --crop x0 y0 x1 y1 [--course-px 95]
Mortar is pale and low in red: rows of mortar are found as peaks of 'mortarness' across the crop, then within each
course the vertical joints as peaks along the course. Each brick between joints is saved (inset 4 %)."""
import argparse, json, os
import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage as nd
from scipy.signal import find_peaks
ap = argparse.ArgumentParser(); ap.add_argument("photo"); ap.add_argument("out"); ap.add_argument("--crop", type=int, nargs=4, required=True)
ap.add_argument("--course-px", type=float, default=95); a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
im = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB").crop(tuple(a.crop))
x = np.asarray(im).astype(np.float32) / 255
mort = (x[..., 1] - x[..., 0]) + 0.5 * x.mean(2)                     # cream mortar: greener and lighter than brick
row = nd.gaussian_filter1d(mort.mean(1), 2)
rows, _ = find_peaks(row, distance=a.course_px * 0.7, prominence=np.std(row) * 0.4)
out = []
for r0, r1 in zip(rows[:-1], rows[1:]):
    if not (0.6 * a.course_px < r1 - r0 < 1.5 * a.course_px): continue
    band = mort[r0 + 4:r1 - 4]
    col = nd.gaussian_filter1d(band.mean(0), 2)
    cols, _ = find_peaks(col, distance=a.course_px * 1.4, prominence=np.std(col) * 0.6)
    for c0, c1 in zip(cols[:-1], cols[1:]):
        wid, hgt = c1 - c0, r1 - r0
        if not (1.8 < wid / hgt < 4.2): continue                     # whole stretchers only (215 x 65 + joints)
        mx, my = int(0.06 * wid), int(0.14 * hgt)
        face = im.crop((c0 + mx, r0 + my, c1 - mx, r1 - my)).resize((256, 80), Image.LANCZOS)
        name = f"brick_{len(out):02d}.jpg"; face.save(os.path.join(a.out, name), quality=92)
        out.append({"file": name, "px": [int(wid), int(hgt)]})
json.dump({"kind": "brick", "source": os.path.basename(a.photo), "units": out}, open(os.path.join(a.out, "library.json"), "w"), indent=1)
print(f"{len(rows)} mortar courses, {len(out)} whole bricks")
