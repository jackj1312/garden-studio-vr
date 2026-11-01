"""Cut every brick of a SOLDIER COURSE (bricks on end) out of its own close-up, as a unit library (WORKFLOW G4).

    ~/splat/bin/python tools/phototex/soldier_units.py <photo> <out_dir> --quad x,y x,y x,y x,y --count N
        [--match-sheet master/phototex/sheets/brick_house.png] [--pitch-mm 75] [--height-mm 220]

--quad: the band's corners in the UPRIGHT photo (EXIF applied), top-left, top-right, bottom-right, bottom-left: from the
top of the mortar over the bricks to the bottom of the lowest brick. The band is straightened (homography) to true
proportions, the vertical joints are found as peaks of 'mortarness' (pale, low-red), and each brick between two joints
is saved (inset past the joint). --match-sheet: the units' mean colour is matched (linear light) to the brick pixels of
that wall sheet, so the soldier course is the same brick as the wall around it (Jack's note mmvx77sy, CORRECTIONS-LOG 105).
Writes <out_dir>/soldier_NN.jpg, atlas.png (one row, a cell per unit, with flipped copies) and library.json."""
import argparse, json, os
import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage as nd
from scipy.signal import find_peaks

ap = argparse.ArgumentParser(); ap.add_argument("photo"); ap.add_argument("out")
ap.add_argument("--quad", nargs=4, required=True); ap.add_argument("--count", type=int, required=True)
ap.add_argument("--pitch-mm", type=float, default=75); ap.add_argument("--height-mm", type=float, default=220)
ap.add_argument("--match-sheet", default=""); ap.add_argument("--ref-crop", default="", help="x0,y0,x1,y1: wall bricks in the SAME photo; the soldier/wall colour ratio seen there is kept"); a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)

im = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB")
Q = np.array([[float(v) for v in q.split(",")] for q in a.quad])
PXM = 4.0                                                              # px per mm in the straightened band
W, H = int(a.count * a.pitch_mm * PXM), int(a.height_mm * PXM)
dst = np.array([[0, 0], [W, 0], [W, H], [0, H]], float)
# PIL's perspective takes the coefficients that map OUTPUT pixels to INPUT pixels
A = []; b = []
for (x, y), (u, v) in zip(dst, Q):
    A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
    A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
coef = np.linalg.solve(np.array(A), np.array(b))
band = im.transform((W, H), Image.PERSPECTIVE, tuple(coef), Image.BICUBIC)
band.save(os.path.join(a.out, "band.jpg"), quality=92)
x = np.asarray(band).astype(np.float32) / 255
mort = (x[..., 1] - x[..., 0]) + 0.5 * x.mean(2)
col = nd.gaussian_filter1d(mort[int(0.15 * H):int(0.9 * H)].mean(0), 3)
pitch = a.pitch_mm * PXM
pk, _ = find_peaks(col, distance=pitch * 0.6, prominence=np.std(col) * 0.3)
joints = [0.0] + [float(p) for p in pk if pitch * 0.4 < p < W - pitch * 0.4] + [float(W)]
# keep joints near the expected pitch; fill gaps with the expected spacing
J = [joints[0]]
for p in joints[1:]:
    while p - J[-1] > pitch * 1.5: J.append(J[-1] + pitch)
    if p - J[-1] > pitch * 0.6: J.append(p)
row = nd.gaussian_filter1d(mort.mean(1), 3)                            # top mortar bed: the brick starts below it
top = int(np.argmax(row[:int(0.25 * H)])) + int(9 * PXM)
units = []
lin = lambda c: np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
srgb = lambda c: np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.clip(c, 0, 1), 1 / 2.4) - 0.055)
faces = []
for k, (c0, c1) in enumerate(zip(J[:-1], J[1:])):
    m = 9 * PXM                                                        # past the 10 mm joint and the brick arris
    f = band.crop((int(c0 + m), top, int(c1 - m), H - int(3 * PXM))).resize((64, 208), Image.LANCZOS)
    faces.append(np.asarray(f).astype(np.float32) / 255)
gain = np.ones(3, np.float32)
if a.match_sheet:
    s = np.asarray(Image.open(a.match_sheet).convert("RGB")).astype(np.float32) / 255
    sm = (s[..., 1] - s[..., 0]) + 0.5 * s.mean(2)
    brick = s[sm < np.percentile(sm, 70)]                              # brick pixels (mortar is the pale, greener 30 %)
    tgt = lin(brick).mean(0); cur = np.mean([lin(f).reshape(-1, 3).mean(0) for f in faces], 0)
    if a.ref_crop:                                                     # keep the real difference between soldiers and stretchers
        r = np.asarray(im.crop(tuple(int(v) for v in a.ref_crop.split(",")))).astype(np.float32) / 255
        rm = (r[..., 1] - r[..., 0]) + 0.5 * r.mean(2); wall = lin(r[rm < np.percentile(rm, 70)]).mean(0)
        tgt = tgt * cur / np.maximum(wall, 1e-4)
    gain = (tgt / np.maximum(cur, 1e-4)).astype(np.float32)
for k, f in enumerate(faces):
    g = srgb(lin(f) * gain)
    Image.fromarray((np.clip(g, 0, 1) * 255).astype(np.uint8)).save(os.path.join(a.out, f"soldier_{k:02d}.jpg"), quality=92)
    units.append({"file": f"soldier_{k:02d}.jpg", "joint_px": [round(J[k], 1), round(J[k + 1], 1)]})
cells = [np.asarray(Image.open(os.path.join(a.out, u["file"]))) for u in units]
cells += [c[::-1, ::-1] for c in cells]                                # rotated 180: a brick on end reads either way up
Image.fromarray(np.concatenate(cells, 1)).save(os.path.join(a.out, "atlas.png"))
json.dump({"kind": "soldier", "source": os.path.basename(a.photo), "quad": Q.tolist(), "count": a.count, "found": len(units),
           "gain_linear": gain.round(3).tolist(), "match_sheet": a.match_sheet, "ref_crop": a.ref_crop, "atlas_cells": len(cells), "units": units}, open(os.path.join(a.out, "library.json"), "w"), indent=1)
print("soldier units", len(units), "of", a.count, "gain", gain.round(3), "->", a.out)
