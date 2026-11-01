"""Printed faces (house number plaque, bin print) as decal images, from what the client's close-ups SAY and SHOW
(text read off the photo, layout measured off it, colours sampled from the walk frames). WORKFLOW G4.
    ~/splat/bin/python tools/phototex/make_decals.py <out_dir>
Front garden (audit-3): plaque 20506 (slate acrylic, black serif "23", rule, "BATTLE ROAD"); bins 20515 (dark grey:
Wealden District Council mark + white "23"; brown: "LOVE WHERE YOU LIVE" + house-heart mark, "Love Recycling")."""
import sys, os
from PIL import Image, ImageDraw, ImageFont
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
SUP = "/System/Library/Fonts/Supplemental/"
def lin(c): c /= 255; return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def srgb(v): return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
def albedo(rgb, a=0.8): return tuple(int(round(255 * srgb(a * lin(c)))) for c in rgb)
def font(name, size, idx=0):
    for p in (SUP + name, "/System/Library/Fonts/" + name):
        if os.path.exists(p): return ImageFont.truetype(p, size, index=idx)
    return ImageFont.load_default()

# plaque: 0.28 x 0.13 m at 2000 px/m; slate grey sampled in sun (walk_0049: 132, 136, 136) -> albedo
W, H = 560, 260; bg = albedo((132, 136, 136)); ink = (14, 14, 16)
im = Image.new("RGB", (W, H), bg); d = ImageDraw.Draw(im)
f23 = font("Georgia.ttf", 140); d.text((W / 2, 84), "23", font=f23, fill=ink, anchor="mm")
d.rectangle((int(W * 0.08), 172, int(W * 0.92), 177), fill=ink)
fb, fs = font("Georgia.ttf", 40), font("Georgia.ttf", 30)
x = W / 2; words = [("B", fb), ("ATTLE ", fs), ("R", fb), ("OAD", fs)]
tw = sum(d.textlength(t, font=f) for t, f in words); x = (W - tw) / 2
for t, f in words:
    d.text((x, 225), t, font=f, fill=ink, anchor="ls"); x += d.textlength(t, font=f)
for cx, cy in ((22, 22), (W - 22, 22), (22, H - 22), (W - 22, H - 22)):           # the four chrome stand-off caps
    d.ellipse((cx - 11, cy - 11, cx + 11, cy + 11), fill=(178, 180, 182), outline=(110, 112, 114), width=2)
im.save(os.path.join(OUT, "plaque_23.png"))

# bins: their fronts' print, on the bin colour sampled in the walk frames (shade: walk_0069 / 0063)
def bin_face(name, body, draw_fn, W=400, H=330):
    im = Image.new("RGB", (W, H), body); draw_fn(ImageDraw.Draw(im), W, H); im.save(os.path.join(OUT, name))
white = (226, 226, 222)
def grey_face(d, W, H):
    d.text((W / 2, 70), "Wealden", font=font("Arial Bold.ttf", 44), fill=(150, 152, 156), anchor="mm")
    d.text((W / 2, 104), "District Council", font=font("Arial Bold.ttf", 20), fill=(150, 152, 156), anchor="mm")
    d.arc((W / 2 + 20, 18, W / 2 + 120, 70), 200, 340, fill=(150, 152, 156), width=5)
    d.text((W / 2, 220), "23", font=font("Arial Bold.ttf", 170), fill=white, anchor="mm")
def brown_face(d, W, H):
    fb = font("Arial Bold.ttf", 52)
    d.text((24, 60), "LOVE", font=fb, fill=white, anchor="ls"); d.text((24, 92), "WHERE YOU", font=font("Arial Bold.ttf", 28), fill=white, anchor="ls")
    d.text((24, 146), "LIVE", font=fb, fill=white, anchor="ls")
    hx, hy = 200, 70                                                        # the house outline with a heart in it
    d.line([(hx, hy + 70), (hx, hy + 20), (hx + 40, hy - 15), (hx + 80, hy + 20), (hx + 80, hy + 70), (hx, hy + 70)], fill=white, width=7)
    d.text((hx + 40, hy + 40), "♥", font=font("Arial Bold.ttf", 44), fill=white, anchor="mm")
    d.text((24, 196), "Love Recycling", font=font("Arial Bold Italic.ttf", 34), fill=white, anchor="ls")
bin_face("bin_grey_23.png", (68, 69, 71), grey_face)
bin_face("bin_brown_print.png", (53, 43, 38), brown_face)
print("decals ->", OUT)
