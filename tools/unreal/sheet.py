"""Matched side-by-side sheet: the client's frame | the Unreal still from the same solved camera (WORKFLOW G6/G8).
    ~/splat/bin/python tools/unreal/sheet.py <renders dir with S_<name>.png> [--refs assets/sites/front-garden-model/refs]
        [--out <dir>/sheet.jpg] [--names a,b,c]
Prints, per frame, the exposure difference (EV, median log-luminance photo vs render) so the next render's --ev can be set
from the photos rather than by eye, and a mean colour comparison of the lower half (ground) and upper half."""
import glob, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def arg(n, d=None): return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d


def lin(a): a = a / 255.0; return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def main():
    rd = sys.argv[1]; refs = arg("--refs", os.path.join(ROOT, "assets/sites/front-garden-model/refs"))
    out = arg("--out", os.path.join(rd, "sheet.jpg"))
    pngs = sorted(glob.glob(os.path.join(rd, "S_*.png")))
    if arg("--names"): pngs = [os.path.join(rd, f"S_{n}.png") for n in arg("--names").split(",")]
    H = 900; panels = []; evs = []
    try: font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except Exception: font = ImageFont.load_default()
    for p in pngs:
        name = os.path.basename(p)[2:-4]; rp = os.path.join(refs, name + ".jpg")
        if not os.path.exists(rp) or not os.path.exists(p): print("missing", name); continue
        ph = Image.open(rp).convert("RGB"); ue = Image.open(p).convert("RGB")
        ph = ph.resize((round(ph.width * H / ph.height), H)); ue = ue.resize((round(ue.width * H / ue.height), H))
        a, b = lin(np.asarray(ph, np.float32)), lin(np.asarray(ue, np.float32))
        la = np.median(np.log2(1e-4 + a @ [0.2126, 0.7152, 0.0722])); lb = np.median(np.log2(1e-4 + b @ [0.2126, 0.7152, 0.0722]))
        ev = la - lb; evs.append(ev)
        top = lambda x: (x[: x.shape[0] // 2].reshape(-1, 3).mean(0) ** (1 / 2.2) * 255).round().astype(int).tolist()
        bot = lambda x: (x[x.shape[0] // 2:].reshape(-1, 3).mean(0) ** (1 / 2.2) * 255).round().astype(int).tolist()
        print(f"{name:18s} EV photo-render {ev:+.2f}   top photo {top(a)} ue {top(b)}   bottom photo {bot(a)} ue {bot(b)}")
        pan = Image.new("RGB", (ph.width + ue.width + 8, H + 36), (24, 24, 24)); pan.paste(ph, (0, 36)); pan.paste(ue, (ph.width + 8, 36))
        ImageDraw.Draw(pan).text((6, 6), f"{name}: Jack's frame | Unreal 5.8 rebuild (scanned CC0 materials, Lumen HWRT)", fill=(230, 230, 230), font=font)
        panels.append(pan)
    if not panels: print("no panels"); return
    cols = 3 if len(panels) > 4 else len(panels); rows = (len(panels) + cols - 1) // cols
    W = max(p.width for p in panels); sheet = Image.new("RGB", (cols * (W + 12), rows * (H + 48)), (16, 16, 16))
    for i, p in enumerate(panels): sheet.paste(p, ((i % cols) * (W + 12), (i // cols) * (H + 48)))
    sheet.save(out, quality=90); print("sheet", out, sheet.size, "median EV offset %+.2f" % float(np.median(evs)))


if __name__ == "__main__":
    main()
