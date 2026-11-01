"""Exterior colour check against the signed spec (WORKFLOW G2b acceptance 'colour'; CORRECTIONS 165, 176).

    uv run --offline --with numpy --with pillow python tools/house/check_colour.py --spec assets/sites/house/spec/spec_v1.json \
        --renders <dir with ref_<photo>[_sN].png> --photos assets/sites/front-garden-model/refs [--stage N] [--out <dir>]

For each spec exterior material: its region (region_frac of its target photo) is measured in the matched render (rendered
through the photo's solved camera, house_views.py ref_<photo>) as the median CIE Lab and the L spread p10-p90. One exposure
offset per photo (median L of all that photo's regions, photo minus render) is applied to the render, then
dE76 = |render - target_lab| and spread ratio = render spread / target spread. PASS: dE <= 5 and spread ratio 0.7-1.3.
Writes <out>/colour_check.json and colour_check.md, and an overlay per photo (regions drawn on photo | render)."""
import os, json, argparse
import numpy as np
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument("--spec", required=True); ap.add_argument("--renders", required=True)
ap.add_argument("--photos", default="assets/sites/front-garden-model/refs"); ap.add_argument("--stage", default="")
ap.add_argument("--out", default=""); ap.add_argument("--de", type=float, default=5.0)
a = ap.parse_args()
out = a.out or a.renders
S = json.load(open(a.spec))


def lab(rgb):
    c = rgb / 255.0; c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], 1)


mats = S["exterior"]["materials"]
by_photo = {}
for m in mats: by_photo.setdefault(m["target_photo"], []).append(m)
res = []
for ph, ms in by_photo.items():
    pp = os.path.join(a.photos, ph + ".jpg")
    rp = os.path.join(a.renders, f"ref_{ph}" + (f"_s{a.stage}" if a.stage else "") + ".png")
    if not (os.path.exists(pp) and os.path.exists(rp)):
        for m in ms: res.append(dict(id=m["id"], photo=ph, missing="no solved camera for this photo (no matched render)" if not os.path.exists(rp) else pp))
        continue
    P = Image.open(pp).convert("RGB"); R = Image.open(rp).convert("RGB").resize(P.size)
    boxes = {m["id"]: tuple(int(v * s) for v, s in zip(m["region_frac"], (P.width, P.height, P.width, P.height))) for m in ms}
    Lp = np.concatenate([lab(np.asarray(P.crop(b), np.float64).reshape(-1, 3))[:, 0] for b in boxes.values()])
    Lr = np.concatenate([lab(np.asarray(R.crop(b), np.float64).reshape(-1, 3))[:, 0] for b in boxes.values()])
    off = float(np.median(Lp) - np.median(Lr))
    ov = Image.new("RGB", (P.width * 2, P.height)); ov.paste(P, (0, 0)); ov.paste(R, (P.width, 0)); d = ImageDraw.Draw(ov)
    for m in ms:
        b = boxes[m["id"]]
        for dx in (0, P.width):
            d.rectangle((b[0] + dx, b[1], b[2] + dx, b[3]), outline=(255, 0, 255), width=2); d.text((b[0] + dx + 3, b[1] + 2), m["id"][4:], fill=(255, 0, 255))
        Lr_ = lab(np.asarray(R.crop(b), np.float64).reshape(-1, 3)); Lph = lab(np.asarray(P.crop(b), np.float64).reshape(-1, 3))
        rm = np.median(Lr_, 0); rm[0] += off
        t = np.array(m["target_lab"], np.float64)
        sp_t = (m.get("target_L_spread_p10_p90") or [None, None])
        sp_t = (sp_t[1] - sp_t[0]) if sp_t[0] is not None else float(np.percentile(Lph[:, 0], 90) - np.percentile(Lph[:, 0], 10))
        sp_r = float(np.percentile(Lr_[:, 0], 90) - np.percentile(Lr_[:, 0], 10))
        de = float(np.linalg.norm(rm - t))
        res.append(dict(id=m["id"], name=m["name"][:60], photo=ph, exposure_offset_L=round(off, 1), target=[round(x, 1) for x in t],
                        photo_now=[round(float(x), 1) for x in np.median(Lph, 0)], render=[round(float(x), 1) for x in rm], dE=round(de, 1),
                        spread_target=round(sp_t, 1), spread_render=round(sp_r, 1), spread_ratio=round(sp_r / max(1e-3, sp_t), 2),
                        passed=bool(de <= a.de and 0.7 <= sp_r / max(1e-3, sp_t) <= 1.3)))
    ov.save(os.path.join(out, f"colour_regions_{ph}.jpg"), quality=85)
json.dump(res, open(os.path.join(out, "colour_check.json"), "w"), indent=1)
lines = ["| material | photo | target Lab | render Lab (exp. offset) | dE | spread x | pass |", "|---|---|---|---|---|---|---|"]
for r in res:
    if r.get("missing"): lines.append(f"| {r['id']} | {r['photo']} | | missing {r['missing']} | | | no |"); continue
    lines.append(f"| {r['id']} | {r['photo']} | {r['target']} | {r['render']} ({r['exposure_offset_L']:+}) | {r['dE']} | {r['spread_ratio']} | {'yes' if r['passed'] else 'NO'} |")
open(os.path.join(out, "colour_check.md"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
print(f"{sum(1 for r in res if r.get('passed'))}/{len(res)} pass")
