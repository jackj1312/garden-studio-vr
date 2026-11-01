"""Integrity faults -> close-up inspection cameras and a labelled contact sheet (row 179: every fault is looked at).

    python3 tools/house/fault_sheet.py cams <site>/<v>_integrity.json <out_dir> [--max 24]     # writes <out_dir>/cams.json
    (render: Blender -b --python tools/house/house_views.py -- --glb <v>.glb --eevee --asbuilt on --cams <out_dir>/cams.json
             --views cam:f00,cam:f01,... --out <out_dir> --px 520)
    uv run --with pillow python tools/house/fault_sheet.py sheet <out_dir>                     # writes <out_dir>/sheet.jpg
"""
import sys, os, json


def cams(ip, out, mx=24):
    r = json.load(open(ip)); os.makedirs(out, exist_ok=True)
    C = []
    def add(kind, rec, at, eye):
        C.append(dict(name=f"f{len(C):02d}", kind=kind, label=f"{kind}: {rec.get('a') or rec.get('part') or rec.get('foliage')} / "
                      f"{rec.get('b') or rec.get('solid') or ''} {rec.get('max_mm', rec.get('area_cm2', ''))}", eye=eye, target=at, lens=30, aspect=0.75))
    F = r["faults"]
    for k in ("gap", "z_fight"):
        for rec in F.get(k, [])[:8]:
            if rec.get("eye"): add(k, rec, rec["at"], rec["eye"])
    for rec in F.get("above_roof", [])[:5]:
        a = rec["at"]; add("above_roof", rec, a, [a[0] + 1.6, a[1] + 1.4, a[2] + 1.6])
    for rec in F.get("foliage_in_solid", [])[:5]:
        a = rec["at"]; add("foliage", rec, a, [a[0], a[1] + 1.3, a[2] + 1.6])
    for rec in F.get("sky_leak", [])[:3]:
        pass
    C = C[:mx]
    json.dump(C, open(os.path.join(out, "cams.json"), "w"), indent=1)
    print(",".join("cam:" + c["name"] for c in C))


def sheet(out):
    from PIL import Image, ImageDraw
    C = json.load(open(os.path.join(out, "cams.json")))
    ims = [(c, os.path.join(out, c["name"] + ".png")) for c in C if os.path.exists(os.path.join(out, c["name"] + ".png"))]
    if not ims: print("no frames"); return
    w, h = 520, 390; cols = 4; rows = (len(ims) + cols - 1) // cols
    S = Image.new("RGB", (cols * w, rows * (h + 34)), "white"); d = ImageDraw.Draw(S)
    for i, (c, p) in enumerate(ims):
        im = Image.open(p).convert("RGB").resize((w, h)); x, y = (i % cols) * w, (i // cols) * (h + 34)
        S.paste(im, (x, y)); d.text((x + 4, y + h + 2), (c["name"] + " " + c["label"])[:80], fill=(0, 0, 0)); d.text((x + 4, y + h + 17), (c["label"][80:160]), fill=(0, 0, 0))
    S.save(os.path.join(out, "sheet.jpg"), quality=85); print("wrote", os.path.join(out, "sheet.jpg"))


if __name__ == "__main__":
    if sys.argv[1] == "cams": cams(sys.argv[2], sys.argv[3], int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 24)
    else: sheet(sys.argv[2])
