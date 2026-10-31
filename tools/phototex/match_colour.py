"""Give a close-up texture the colour of the same surface in the sunlit walk video (WORKFLOW G4).
Close-ups shot in shade come out grey-blue; the walk frames carry the real colour. Keeps the texture's detail,
sets its mean chromaticity to the target's and its mean brightness to target * `albedo` (a sunlit pixel is
albedo x light, so the albedo sits below it).
    ~/splat/bin/python tools/phototex/match_colour.py <tile.jpg> <reference.png> x0 y0 x1 y1 [--albedo 0.8]
(x0..y1: a pixel box in the reference image that shows only that surface, in sun)"""
import sys, argparse
import numpy as np
from PIL import Image
ap = argparse.ArgumentParser(); ap.add_argument("tile"); ap.add_argument("ref"); ap.add_argument("box", type=int, nargs=4)
ap.add_argument("--albedo", type=float, default=0.8); a = ap.parse_args()
def lin(x): return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
def srgb(x): return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(np.clip(x, 0, None), 1 / 2.4) - 0.055)
t = lin(np.asarray(Image.open(a.tile).convert("RGB")).astype(np.float32) / 255)
r = lin(np.asarray(Image.open(a.ref).convert("RGB").crop(tuple(a.box))).astype(np.float32) / 255)
tm, rm = t.reshape(-1, 3).mean(0), r.reshape(-1, 3).mean(0)
gain = (rm / tm) * (a.albedo * rm.mean() / rm.mean())
out = srgb(np.clip(t * gain, 0, 1))
Image.fromarray((out * 255).astype(np.uint8)).save(a.tile, quality=93)
print(a.tile, "tile mean", (srgb(tm) * 255).round(), "-> ref", (srgb(rm) * 255).round(), "gain", gain.round(2))
