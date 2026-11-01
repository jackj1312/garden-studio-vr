"""
Matched views for a splat test: the real walk frame | the splat rendered from the same solved camera, for frames the
splat never trained on (gsplat holds out every 8th frame). Light work (PIL + numpy), runs on the Mac.

    ~/splat/bin/python tools/cloud/splat_pairs.py <site>/splat-test <out-dir> path=f_0035 porch=f_0083 ...

Each name=frame picks the held-out frame (nearest held-out one if that frame trained). Writes <name>.jpg per view,
sheet.jpg (all views), and pairs.json (per-view PSNR, whole frame and the central half).
"""
import json, os, sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
post = json.load(open(f'{src}/out/post.json')); val = post['val_names']
renders = sorted(f for f in os.listdir(f'{src}/out/val') if f.startswith(f'val_step{max(int(f.split("_step")[1].split("_")[0]) for f in os.listdir(f"{src}/out/val"))}_'))
assert len(renders) == len(val), (len(renders), len(val))
try: font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 34); small = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 26)
except Exception: font = small = ImageFont.load_default()


def psnr(a, b): return float(10 * np.log10(1 / max(((a - b) ** 2).mean(), 1e-10)))


rep, tiles = {}, []
for arg in sys.argv[3:]:
    label, want = arg.split('=')
    num = lambda n: int(''.join(ch for ch in n if ch.isdigit()))
    i = min(range(len(val)), key=lambda k: abs(num(val[k]) - num(want)))
    im = Image.open(f'{src}/out/val/{renders[i]}').convert('RGB'); w, h = im.size
    real, splat = im.crop((0, 0, w // 2, h)), im.crop((w // 2, 0, w, h))
    a, b = np.asarray(real, np.float32) / 255, np.asarray(splat, np.float32) / 255
    hh, ww = a.shape[:2]; c = (slice(hh // 4, 3 * hh // 4), slice(ww // 4, 3 * ww // 4))
    rep[label] = {'frame': val[i], 'psnr': round(psnr(a, b), 2), 'psnr_centre': round(psnr(a[c], b[c]), 2)}
    bar = 64; pair = Image.new('RGB', (w + 12, h + bar), 'white'); pair.paste(real, (0, bar)); pair.paste(splat, (w // 2 + 12, bar))
    d = ImageDraw.Draw(pair)
    d.text((14, 14), f'{label}: real walk frame {val[i]} (held out, never trained on)', fill='black', font=small)
    d.text((w // 2 + 26, 14), f'splat, same camera · PSNR {rep[label]["psnr"]:.1f} dB', fill='black', font=small)
    pair.save(f'{out}/{label}.jpg', quality=90); tiles.append(pair); print(label, rep[label])
if tiles:
    tw = 900; th = int(tiles[0].height * tw / tiles[0].width)
    sheet = Image.new('RGB', (tw * 2, th * ((len(tiles) + 1) // 2)), 'white')
    for k, t in enumerate(tiles): sheet.paste(t.resize((tw, th), Image.LANCZOS), ((k % 2) * tw, (k // 2) * th))
    sheet.save(f'{out}/sheet.jpg', quality=88)
json.dump({'views': rep, 'val_stats': post.get('val_stats'), 'gaussians': post['gaussians']}, open(f'{out}/pairs.json', 'w'), indent=1)
