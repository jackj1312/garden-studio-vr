"""G6 drawing check for a generated house: the model's cut lines (house_slices.py) drawn over the architect's sheet at
true scale, and measured against the sheet's own vector lines.

    uv run --offline --quiet --with pymupdf --with pillow python tools/house/house_overlay.py \
        --slices <v_slices.json> --spec <build_versions.json> --version <id> --out <dir>

For every view in spec["drawing_checks"]["views"] that lists the version: render the sheet region, draw the model in
red (walls), orange (roofs), blue (openings), and for each model line (>= 80 mm) find the nearest parallel drawing
line overlapping it: the perpendicular offset is its error. Plans and elevations are in the sheet's frame directly;
sections are first registered along the cut (the sheet's section x is an unknown offset of the house coordinate):
the offset is the mode of all vertical-line pairings. Writes <out>/<version>_<view>.png and <out>/<version>_checks.json."""
import sys, os, json, math, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "plan"))
import trace_drawing as td
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser()
ap.add_argument("--slices", required=True); ap.add_argument("--spec", required=True)
ap.add_argument("--version", required=True); ap.add_argument("--out", required=True); ap.add_argument("--dpi", type=int, default=150)
args = ap.parse_args()
SL = json.load(open(args.slices)); SPEC = json.load(open(args.spec))
DC = SPEC["drawing_checks"]
base = os.path.dirname(os.path.abspath(args.spec))
os.makedirs(args.out, exist_ok=True)
COL = {"wall": (220, 20, 20), "roof": (255, 120, 0), "open": (0, 110, 255), "other": (120, 60, 200)}
WALLG = ("wall_outer", "wall_inner", "wall_insulation")


def merge_collinear(segs, tol=0.002):
    """merge touching collinear segments of one part"""
    out = []
    for s in segs:
        x1, y1, x2, y2 = s
        if math.hypot(x2 - x1, y2 - y1) < 1e-4: continue
        out.append([x1, y1, x2, y2])
    changed = True
    while changed:
        changed = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                a, b = out[i], out[j]
                da = (a[2] - a[0], a[3] - a[1]); La = math.hypot(*da)
                db = (b[2] - b[0], b[3] - b[1]); Lb = math.hypot(*db)
                if La < 1e-6 or Lb < 1e-6: continue
                if abs(da[0] * db[1] - da[1] * db[0]) / (La * Lb) > 0.002: continue
                ux, uy = da[0] / La, da[1] / La
                if abs(-(b[0] - a[0]) * uy + (b[1] - a[1]) * ux) > tol: continue
                ts = [0, La, (b[0] - a[0]) * ux + (b[1] - a[1]) * uy, (b[2] - a[0]) * ux + (b[3] - a[1]) * uy]
                if min(ts[2], ts[3]) > La + tol or max(ts[2], ts[3]) < -tol: continue
                t0, t1 = min(ts), max(ts)
                out[i] = [a[0] + ux * t0, a[1] + uy * t0, a[0] + ux * t1, a[1] + uy * t1]
                out.pop(j); changed = True; break
            if changed: break
    return out


def nearest(seg, dsegs, max_d=0.06):
    """perpendicular offset to the nearest parallel drawing segment overlapping it (or None)"""
    x1, y1, x2, y2 = seg
    L = math.hypot(x2 - x1, y2 - y1); ux, uy = (x2 - x1) / L, (y2 - y1) / L
    best = None
    for (a, b) in dsegs:
        dx, dy = b[0] - a[0], b[1] - a[1]; Ld = math.hypot(dx, dy)
        if Ld < 0.02: continue
        if abs(ux * dy - uy * dx) / Ld > 0.035: continue          # within 2 degrees
        t0 = (a[0] - x1) * ux + (a[1] - y1) * uy; t1 = (b[0] - x1) * ux + (b[1] - y1) * uy
        ov = min(L, max(t0, t1)) - max(0, min(t0, t1))
        if ov < min(0.3 * L, 0.05): continue
        d = abs(-(a[0] - x1) * uy + (a[1] - y1) * ux)
        if d <= max_d and (best is None or d < best): best = d
    return best


def faces_only(lines):
    """keep, per wall element and direction, only the two extreme parallel lines (the wall's faces): internal leaf
    and insulation boundaries are not drawn as straight lines on the sheets"""
    by = {}
    for (k, n, s) in lines:
        if k != "wall": continue
        el = n.split("_L")[0]
        dx, dy = s[2] - s[0], s[3] - s[1]; L = math.hypot(dx, dy)
        if L < 1e-6: continue
        ang = round(math.degrees(math.atan2(dy, dx)) % 180 / 2) * 2 % 180
        nx, ny = -math.sin(math.radians(ang)), math.cos(math.radians(ang))
        off = s[0] * nx + s[1] * ny
        by.setdefault((el, ang), []).append((off, (k, n, s)))
    keep = []
    for key, items in by.items():
        lo = min(o for o, _ in items); hi = max(o for o, _ in items)
        keep += [it for o, it in items if abs(o - lo) < 0.003 or abs(o - hi) < 0.003]
    return keep


def model_lines(view, sl):
    parts = sl["parts"]
    out = []
    for p in parts:
        g = p["group"] or ""
        kind = "wall" if g in WALLG else ("roof" if g in ("roof_cover", "rooflight") else ("open" if g in ("window", "door") else "other"))
        if kind == "other" and g in ("ground", "prop", "scaffold", "spoil", "wall_lining"): continue
        segs = p["segs"]
        if view.get("transform"): segs = [view["transform"](s) for s in segs]
        for s in merge_collinear(segs) if len(segs) < 400 else segs:
            out.append((kind, p["part"], s))
    return out


def run_view(view):
    pdf = os.path.join(base, DC["sheets"][view["sheet"]])
    page = td.open_page(pdf)
    fr = td.Frame(page, view["scale"], tuple(view["origin"]), view.get("flipx", False))
    rr = view["rr"]
    cs = [fr.real_to_paper(x, y) for x in (rr[0], rr[2]) for y in (rr[1], rr[3])]
    region = [min(c[0] for c in cs), min(c[1] for c in cs), max(c[0] for c in cs), max(c[1] for c in cs)]
    dsegs_raw, _arcs = td.extract(page, fr, region, minlen=0.03)
    dsegs = [(tuple(s["a"]), tuple(s["b"])) for s in dsegs_raw]
    sl = SL[view["slice"]]
    lines = model_lines(view, sl)
    # sections: register along the cut
    offset = 0.0
    if view.get("register"):
        sgn = view["register"]
        dvx = [s[0][0] for s in dsegs if abs(s[0][0] - s[1][0]) < 0.002 and abs(s[1][1] - s[0][1]) > 0.3]
        mvx = [s[2][0] for s in lines if s[0] == "wall" and abs(s[2][0] - s[2][2]) < 0.002 and abs(s[2][3] - s[2][1]) > 0.3]
        hist = {}
        for m in mvx:
            for d in dvx:
                k = round((d - sgn * m) / 0.005) * 0.005
                hist[k] = hist.get(k, 0) + 1
        if hist:
            offset = max(hist.items(), key=lambda kv: kv[1])[0]
        tf = lambda s: [sgn * s[0] + offset, s[1], sgn * s[2] + offset, s[3]]
        lines = [(k, n, tf(s)) for (k, n, s) in lines]
    if view["slice"].startswith("elev"): measured = [l for l in lines if l[0] in ("roof", "open")]
    else: measured = faces_only(lines) + [l for l in lines if l[0] == "roof"]
    errs = []
    for (kind, name, s) in measured:
        L = math.hypot(s[2] - s[0], s[3] - s[1])
        if L < 0.08 or kind == "roof" and view.get("skip_roof_numbers"): continue
        d = nearest(s, dsegs)
        errs.append(dict(kind=kind, part=name, seg=[round(v, 3) for v in s], err=None if d is None else round(d, 4), len=round(L, 3)))
    # draw
    img, to_px = td.render(page, region, args.dpi)
    img = img.convert("RGB")
    img = Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), 0.30)
    dr = ImageDraw.Draw(img, "RGBA")
    P = lambda x, y: to_px(*fr.real_to_paper(x, y))
    for (kind, name, s) in lines:
        dr.line([P(s[0], s[1]), P(s[2], s[3])], fill=COL[kind] + (200 if kind != "other" else 120,), width=2 if kind == "wall" else 1)
    matched = [e for e in errs if e["err"] is not None and (e["kind"] != "open" or view["slice"].startswith("elev"))]
    for e in matched:
        if e["err"] > view.get("tol", 0.02):
            s = e["seg"]; m = P((s[0] + s[2]) / 2, (s[1] + s[3]) / 2)
            dr.ellipse([m[0] - 6, m[1] - 6, m[0] + 6, m[1] + 6], outline=(255, 0, 255, 255), width=2)
    within = [e for e in matched if e["err"] <= view.get("tol", 0.02)]
    # reverse: every thick drawn line (walls, roof outline: stroke >= 0.45 pt) inside the model's extent should have a
    # model line within tol
    msegs = [s for (k, n, s) in lines]
    if msegs:
        xs = [v for s in msegs for v in (s[0], s[2])]; ys = [v for s in msegs for v in (s[1], s[3])]
        bx = (min(xs) - 0.05, min(ys) - 0.05, max(xs) + 0.05, max(ys) + 0.05)
    rev = []
    for s in dsegs_raw:
        if s["w"] < view.get("thick", 0.45) or s["len"] < 0.15 or (s.get("dash") not in ("", "[] 0", None)): continue
        a, b = s["a"], s["b"]
        if not msegs or not (bx[0] <= a[0] <= bx[2] and bx[1] <= a[1] <= bx[3] and bx[0] <= b[0] <= bx[2] and bx[1] <= b[1] <= bx[3]): continue
        d = nearest([a[0], a[1], b[0], b[1]], [((m[0], m[1]), (m[2], m[3])) for m in msegs], max_d=0.15)
        rev.append(dict(seg=[round(v, 3) for v in (a[0], a[1], b[0], b[1])], w=s["w"], err=None if d is None else round(d, 4)))
    rev_m = [r for r in rev if r["err"] is not None]
    rev_ok = [r for r in rev_m if r["err"] <= view.get("tol", 0.02)]
    for r in rev:
        if r["err"] is None or r["err"] > view.get("tol", 0.02):
            s = r["seg"]; dr.line([P(s[0], s[1]), P(s[2], s[3])], fill=(0, 200, 0, 230), width=4)
    title = (f"{args.version} · {view['name']} · model (red walls, orange roof, blue openings, violet structure) over {view['sheet_label']} · "
             f"{len(within)}/{len(matched)} matched lines within {int(view.get('tol', 0.02) * 1000)} mm" + (f" · section offset {offset:+.3f}" if view.get("register") else ""))
    dr.rectangle([0, 0, img.size[0], 22], fill=(255, 255, 255, 230)); dr.text((6, 4), title, fill=(0, 0, 0), font=td.font(13))
    path = os.path.join(args.out, f"{args.version}_{view['name']}.png")
    img.save(path)
    errs_m = sorted([e for e in matched], key=lambda e: -e["err"])
    stats = dict(view=view["name"], sheet=view["sheet_label"], tol=view.get("tol", 0.02), model_lines=len(errs), matched=len(matched),
                 within_tol=len(within), unmatched=len([e for e in errs if e["err"] is None]),
                 p95=round(sorted(e["err"] for e in matched)[int(0.95 * (len(matched) - 1))], 4) if matched else None,
                 worst=errs_m[:8], offset=offset if view.get("register") else None, png=os.path.relpath(path, args.out),
                 drawn_thick=len(rev), drawn_within_tol=len(rev_ok), drawn_no_model_line=len([r for r in rev if r["err"] is None]),
                 drawn_worst=sorted(rev_m, key=lambda r: -r["err"])[:8])
    print(view["name"], f"model->drawing {len(within)}/{len(matched)} within tol (p95 {stats['p95']}); drawing thick lines -> model {len(rev_ok)}/{len(rev)} within tol, {stats['drawn_no_model_line']} with no model line in 150 mm")
    return stats


res = []
for v in DC["views"]:
    if args.version not in v["versions"]: continue
    if v["slice"] not in SL: continue
    res.append(run_view(v))
json.dump(res, open(os.path.join(args.out, f"{args.version}_checks.json"), "w"), indent=1)
