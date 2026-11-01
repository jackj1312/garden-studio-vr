"""photo vs matched render: per-region colour distribution in CIE Lab (median L a b, L spread p10-p90)"""
import sys, json, numpy as np
from PIL import Image, ImageDraw
regs = json.load(open(sys.argv[1])); photo_dir, render_dir, tag = sys.argv[2], sys.argv[3], sys.argv[4]
def lab(rgb):
    c = rgb / 255.0; c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], 1)
out = {}
for n, rs in regs.items():
    P = Image.open(f"{photo_dir}/{n}.jpg").convert("RGB"); R = Image.open(f"{render_dir}/ref_{n}_s1.png").convert("RGB").resize(P.size)
    ov = P.copy(); d = ImageDraw.Draw(ov)
    for k, (x0, y0, x1, y1) in rs.items():
        box = (int(x0 * P.width), int(y0 * P.height), int(x1 * P.width), int(y1 * P.height)); d.rectangle(box, outline=(255, 0, 255), width=3); d.text((box[0] + 3, box[1] + 3), k, fill=(255, 0, 255))
        for src, im in (("photo", P), ("render", R)):
            a = np.asarray(im.crop(box), np.float64).reshape(-1, 3); L = lab(a)
            out.setdefault(k, {}).setdefault(src, []).append(L)
    ov.save(f"{render_dir}/regions_{n}.jpg")
res = {}
for k, d in out.items():
    p = np.concatenate(d["photo"]); r = np.concatenate(d["render"])
    st = lambda L: dict(L=round(float(np.median(L[:, 0])), 1), a=round(float(np.median(L[:, 1])), 1), b=round(float(np.median(L[:, 2])), 1),
                        Lspread=round(float(np.percentile(L[:, 0], 90) - np.percentile(L[:, 0], 10)), 1))
    sp, sr = st(p), st(r)
    dE = round(float(np.sqrt((sp["L"] - sr["L"]) ** 2 + (sp["a"] - sr["a"]) ** 2 + (sp["b"] - sr["b"]) ** 2)), 1)
    res[k] = dict(photo=sp, render=sr, dE_median=dE, spread_ratio=round(sr["Lspread"] / max(1e-3, sp["Lspread"]), 2))
json.dump(res, open(f"{render_dir}/colour_{tag}.json", "w"), indent=1)
for k, v in res.items(): print(f"{k:7s} photo L{v['photo']['L']:5.1f} a{v['photo']['a']:5.1f} b{v['photo']['b']:5.1f} sp{v['photo']['Lspread']:5.1f} | render L{v['render']['L']:5.1f} a{v['render']['a']:5.1f} b{v['render']['b']:5.1f} sp{v['render']['Lspread']:5.1f} | dE {v['dE_median']:5.1f} spread x{v['spread_ratio']}")
