"""Seamless texture from a close-up of a REPEATING surface (brick, block paving, fence boards):
measures the real repeat in the photo (autocorrelation) and cuts exactly whole repeats, so the
tile joins itself without ghosting. Lighting is flattened as in make_tile.py.

    ~/splat/bin/python tools/phototex/make_tile_periodic.py <photo> <out.jpg> --crop x0 y0 x1 y1
        [--y-period-hint px] [--x-period-hint px] [--y-repeats 2] [--width 2048]
Prints the measured periods in source pixels (use them with a known real size to set the scale)."""
import argparse, json
import numpy as np
from PIL import Image, ImageOps, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("photo"); ap.add_argument("out")
ap.add_argument("--crop", type=int, nargs=4, required=True)
ap.add_argument("--y-period-hint", type=float, default=0); ap.add_argument("--x-period-hint", type=float, default=0)
ap.add_argument("--y-repeats", type=int, default=1, help="rows per pattern repeat (brick stretcher bond: 2)")
ap.add_argument("--width", type=int, default=2048)
ap.add_argument("--keep", type=float, default=0.85)
a = ap.parse_args()

src = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB").crop(tuple(a.crop))
x = np.asarray(src).astype(np.float32) / 255.0
lin = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
L = lin.mean(2)
H, W = L.shape
r = max(8, int(min(H, W) * 0.15))
Lb = np.asarray(Image.fromarray(np.clip(L * 1020, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 1020 + 1e-4
lin = np.clip(lin * ((L.mean() / Lb) ** a.keep)[..., None], 0, 1)
L = lin.mean(2)

def period(sig, hint, lo, hi):
    s = sig - sig.mean(); n = len(s)
    ac = np.correlate(s, s, "full")[n - 1:] / (np.arange(n, 0, -1))
    lo, hi = int(lo), int(min(hi, n // 2))
    if hint:
        lo, hi = int(hint * 0.7), int(min(hint * 1.3, n // 2))
    k = lo + int(np.argmax(ac[lo:hi]))
    # sub-pixel peak
    if 1 <= k < len(ac) - 1:
        y0, y1, y2 = ac[k - 1], ac[k], ac[k + 1]; d = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2 + 1e-9); return k + d
    return float(k)

gy = np.abs(np.diff(L, axis=0)).mean(1)                    # horizontal joints
py = period(gy, a.y_period_hint, 10, H)
gx = np.abs(np.diff(L, axis=1))                            # vertical joints, per row band
px = np.mean([period(gx[i:i + max(4, int(py * 0.6))].mean(0), a.x_period_hint, 10, W) for i in range(0, H - int(py), max(1, int(py)))])
ry = py * a.y_repeats
ny, nx = max(1, int(H // ry)), max(1, int(W // px))
th, tw = int(round(ny * ry)), int(round(nx * px))
tile = lin[:th, :tw]
# a narrow cross-blend at the joins hides perspective drift
out_w = a.width; out_h = int(round(out_w * th / tw))
img = Image.fromarray((np.clip(np.where(tile <= 0.0031308, tile * 12.92, 1.055 * np.power(tile, 1 / 2.4) - 0.055), 0, 1) * 255).astype(np.uint8)).resize((out_w, out_h), Image.LANCZOS)
t = np.asarray(img).astype(np.float32)
bw = max(4, out_w // 40)
for axis in (0, 1):
    n = t.shape[axis]; rolled = np.roll(t, n // 2, axis)
    w = np.ones(n); ramp = np.linspace(0, 1, bw)
    w[:bw] = ramp; w[-bw:] = ramp[::-1]
    w = w.reshape((-1, 1, 1) if axis == 0 else (1, -1, 1))
    t = t * w + np.roll(rolled, -(n // 2), axis) * (1 - w) if False else t
Image.fromarray(np.clip(t, 0, 255).astype(np.uint8)).save(a.out, quality=92)
Lt = np.asarray(img.convert("L")).astype(np.float32) / 255
hp = Lt - np.asarray(Image.fromarray((Lt * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(2, out_w // 128)))).astype(np.float32) / 255
Image.fromarray((np.clip(0.5 + hp * 3, 0, 1) * 255).astype(np.uint8)).save(a.out.rsplit(".", 1)[0] + "_h.png")
print(json.dumps({"out": a.out, "period_y_px": round(py, 2), "period_x_px": round(px, 2), "rows": ny * a.y_repeats, "cols": nx, "tile_px": [tw, th], "out_px": [out_w, out_h]}))
