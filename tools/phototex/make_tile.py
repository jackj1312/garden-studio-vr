"""Turn a close-up photo of a real surface into a seamless, evenly lit texture at true scale.

    ~/splat/bin/python tools/phototex/make_tile.py <photo> <out.jpg> --crop x0 y0 x1 y1 [--size 2048] [--flatten 0.15]

The crop is in the upright photo's pixels and should be square-ish and as straight-on as
possible. Lighting is flattened by dividing out a wide blur (the day's sun and shade gradient),
then the tile is made seamless by cross-blending it with itself shifted half a tile.
Also writes <out>_h.png, a height guess from fine luminance detail (for bump/normal maps)."""
import sys, argparse
import numpy as np
from PIL import Image, ImageOps, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("photo"); ap.add_argument("out")
ap.add_argument("--crop", type=int, nargs=4, required=True)
ap.add_argument("--size", type=int, default=2048)
ap.add_argument("--flatten", type=float, default=0.15, help="blur radius for lighting removal, as a fraction of the tile")
ap.add_argument("--keep", type=float, default=0.85, help="how much of the flattening to apply (1 = fully even)")
a = ap.parse_args()

im = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB").crop(tuple(a.crop)).resize((a.size, a.size), Image.LANCZOS)
x = np.asarray(im).astype(np.float32) / 255.0
lin = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)          # work in linear light
r = max(4, int(a.size * a.flatten))
blur = np.asarray(Image.fromarray((lin * 65535).astype(np.uint16).mean(2).astype(np.float32)).filter(ImageFilter.GaussianBlur(r)) if False else None)
# a wide luminance blur, per channel mean kept
L = lin.mean(2)
Lb = np.asarray(Image.fromarray(np.clip(L * 255 * 4, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / (255 * 4) + 1e-4
gain = (L.mean() / Lb) ** a.keep
lin = np.clip(lin * gain[..., None], 0, 1)
# seamless: blend with itself rolled by half, weighted towards the centre of each
n = a.size; t = np.linspace(0, 1, n, endpoint=False)
w1 = np.minimum(t, 1 - t) * 2                                                       # 0 at the edges, 1 in the middle
W = np.minimum.outer(w1, w1) ** 0.8
rolled = np.roll(np.roll(lin, n // 2, 0), n // 2, 1)
tile = lin * W[..., None] + rolled * (1 - W[..., None])
s = np.where(tile <= 0.0031308, tile * 12.92, 1.055 * np.power(tile, 1 / 2.4) - 0.055)
Image.fromarray((np.clip(s, 0, 1) * 255).astype(np.uint8)).save(a.out, quality=92)
# height: fine luminance detail
Lt = tile.mean(2)
hp = Lt - np.asarray(Image.fromarray((Lt * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(2, n // 64)))).astype(np.float32) / 255
h = np.clip(0.5 + hp * 3, 0, 1)
Image.fromarray((h * 255).astype(np.uint8)).save(a.out.rsplit(".", 1)[0] + "_h.png")
print("ok", a.out, im.size)
