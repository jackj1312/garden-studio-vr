"""Straighten one face of a real object in a photo into a texture (perspective rectification).

    ~/splat/bin/python tools/phototex/rectify.py <photo> <out.jpg> TLx TLy TRx TRy BRx BRy BLx BLy --size W H
Corners are in the upright photo's pixels; W x H is the output, in the face's real proportions."""
import argparse
import numpy as np
from PIL import Image, ImageOps

ap = argparse.ArgumentParser()
ap.add_argument("photo"); ap.add_argument("out"); ap.add_argument("pts", type=float, nargs=8)
ap.add_argument("--size", type=int, nargs=2, required=True)
a = ap.parse_args()
W, H = a.size
src = np.array(a.pts).reshape(4, 2)
dst = np.array([[0, 0], [W, 0], [W, H], [0, H]], float)
# solve for the transform taking OUTPUT pixels to INPUT pixels (what PIL wants)
A, b = [], []
for (x, y), (u, v) in zip(src, dst):
    A.append([u, v, 1, 0, 0, 0, -x * u, -x * v]); b.append(x)
    A.append([0, 0, 0, u, v, 1, -y * u, -y * v]); b.append(y)
coef = np.linalg.solve(np.array(A), np.array(b))
im = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB")
im.transform((W, H), Image.PERSPECTIVE, tuple(coef), Image.BICUBIC).save(a.out, quality=93)
print("ok", a.out, W, H)
