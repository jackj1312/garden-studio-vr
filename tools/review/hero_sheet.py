"""A hero sheet: our fixed-camera frames next to the closest Airbnb frames (PLAN S8: same cameras every round, side by side).

    uv run --offline --with pillow python tools/review/hero_sheet.py <out.jpg> [--tile 640x360] [--cols 4] <label>=<image> ...

Images are fitted (cover-cropped) into equal tiles and captioned; a caption starting with "AIRBNB" is drawn in amber so the two
sources are never confused. Reusable: nothing here knows about 23 Battle Road."""
import sys
from PIL import Image, ImageDraw, ImageFont


def fit(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)))
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def main():
    a = sys.argv[1:]
    out = a[0]; tw, th, cols = 640, 360, 4
    items = []
    i = 1
    while i < len(a):
        if a[i] == "--tile": tw, th = map(int, a[i + 1].split("x")); i += 2
        elif a[i] == "--cols": cols = int(a[i + 1]); i += 2
        else: items.append(a[i].split("=", 1)); i += 1
    rows = (len(items) + cols - 1) // cols
    sh = Image.new("RGB", (tw * cols, th * rows), (20, 20, 20))
    try: f = ImageFont.load_default(18)
    except Exception: f = ImageFont.load_default()
    for k, (label, path) in enumerate(items):
        im = fit(Image.open(path).convert("RGB"), tw, th)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, len(label) * 10 + 12, 26], fill=(0, 0, 0))
        d.text((6, 3), label, fill=(255, 190, 60) if label.startswith("AIRBNB") else (255, 255, 255), font=f)
        sh.paste(im, ((k % cols) * tw, (k // cols) * th))
    sh.save(out, quality=86)
    print(out, sh.size)


if __name__ == "__main__":
    main()
