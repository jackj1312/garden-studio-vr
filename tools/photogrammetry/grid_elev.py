"""Grid a facade_ortho elevation for reading measurements: lines every --step m, labelled in plan metres.
    ~/splat/bin/python tools/photogrammetry/grid_elev.py <elev.png> <out.jpg> --u0 -14.2 --ztop 7.5 [--res 0.01] [--step 0.5] [--scale 2]"""
import argparse
from PIL import Image, ImageDraw, ImageFont
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out")
ap.add_argument("--u0", type=float, required=True); ap.add_argument("--ztop", type=float, required=True)
ap.add_argument("--res", type=float, default=0.01); ap.add_argument("--step", type=float, default=0.5); ap.add_argument("--scale", type=int, default=2)
ap.add_argument("--flip", action="store_true", help="u runs right-to-left (a side face seen from +x)")
a = ap.parse_args()
im = Image.open(a.inp).convert("RGB"); im = im.resize((im.width * a.scale, im.height * a.scale), Image.LANCZOS)
d = ImageDraw.Draw(im); f = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
px = a.scale / a.res
import math
u1 = a.u0 + im.width / px
k = math.ceil(a.u0 / a.step)
while k * a.step < u1:
    u = k * a.step; X = (u - a.u0) * px
    d.line([(X, 0), (X, im.height)], fill=(255, 255, 0) if abs(u - round(u)) < 1e-6 else (255, 255, 120), width=1); d.text((X + 2, 2), f"{u:g}", fill=(255, 255, 0), font=f); k += 1
z = math.floor(a.ztop / a.step) * a.step
while z > a.ztop - im.height / px:
    Y = (a.ztop - z) * px
    d.line([(0, Y), (im.width, Y)], fill=(0, 255, 255), width=1); d.text((2, Y + 1), f"z{z:g}", fill=(0, 255, 255), font=f); z -= a.step
im.save(a.out, quality=90); print(a.out, im.size)
