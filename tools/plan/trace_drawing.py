"""Trace an architect's vector PDF into real-world metres, and draw traced data back over the drawing to check it.

Works on any vector drawing sheet (any rotation, any scale). Positions on the sheet are given in PAPER MM in the
DISPLAYED frame (the sheet as you see it, title block the right way up). A local real-world frame is set by --origin
(paper mm of the real (0,0)) and --scale (1:N); real x runs right on the sheet, real y runs UP the sheet (plans: y
into the house when the road is at the bottom; elevations/sections: y is height). --flipx mirrors x (e.g. a rear
elevation seen from behind), --rot turns the frame (degrees, anticlockwise) for plans drawn askew.

PDF pages carry /Rotate: get_pixmap(clip=) uses the displayed frame, but get_drawings AND get_text("words") return the
UNROTATED frame (checked, PyMuPDF 1.28; the older read_drawing.py picked up the wrong plan's labels because of this);
every path point and word box here goes through page.rotation_matrix, so all three agree (verify with --check).

    uv run --quiet --with pymupdf --with pillow python tools/plan/trace_drawing.py <cmd> <pdf> [options]

  (every command takes --region x0 y0 x1 y1 in paper mm, or --rr x0 y0 x1 y1 in real metres of the --origin frame)
  render   --region x0 y0 x1 y1 [--origin ox oy --scale N --grid 0.5] [--dpi 300] --out crop.png
           crop the sheet; with --origin a real-metre grid (0 lines bold) is drawn over it.
  blocks   --region ... --origin ox oy --scale N [--out blocks.json]
           whole text blocks (notes and labels, exact wording) with real-world centre and box.
  words    --region ... --origin ox oy --scale N [--out words.json]
           every word with its real position (sorted top-to-bottom).
  segments --region ... --origin ox oy --scale N [--layers "external walls,detail"] [--minw 0.4] [--minlen 0.05]
           [--snap 1.5] [--out segs.json] [--check check.png]
           straight line segments (curves skipped; arcs listed separately as door swings) in real metres, with stroke
           width (pt), layer, dash pattern. --snap: segments within that many degrees of horizontal/vertical are made
           exactly orthogonal (about their midpoint). --check draws them in colour (by width) over the render.
  hv       same options as segments: groups the orthogonal segments into distinct x and y lines (rounded to 5 mm)
           with total drawn length, which is the quickest way to read wall faces off a plan.
  overlay  --region ... --origin ox oy --scale N --json data.json --path versions.today.storeys.ground [--dpi 200]
           [--title "..."] --out check.png
           draws walls (centre line + both faces from thickness), openings (along their wall), rooms (polygons),
           fittings, stairs, polylines and labelled points from the JSON node at --path over the drawing.
           Elevation mode: --elev "x" with the node holding {"marks":[{"z":..,"label":..}], "boxes":[[x0,z0,x1,z1,label]]}.

Measure the scale before trusting anything: `words` gives the written dimensions, `hv` the drawn lines; compare a few
(and the scale bar) in the report.
"""
import sys, json, math, argparse
import pymupdf

PT = 72 / 25.4          # points per paper mm


# ---------------------------------------------------------------- frame
class Frame:
    def __init__(self, page, scale, origin, flipx=False, rot=0.0):
        self.page, self.scale = page, scale
        self.ox, self.oy = origin if origin else (0.0, 0.0)
        self.fx = -1.0 if flipx else 1.0
        self.c, self.s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        self.rm = page.rotation_matrix

    def paper_to_real(self, xmm, ymm):
        dx = (xmm - self.ox) * self.scale / 1000 * self.fx
        dy = (self.oy - ymm) * self.scale / 1000
        return (self.c * dx + self.s * dy, -self.s * dx + self.c * dy)

    def real_to_paper(self, x, y):
        dx, dy = self.c * x - self.s * y, self.s * x + self.c * y
        return (self.ox + dx * self.fx * 1000 / self.scale, self.oy - dy * 1000 / self.scale)

    def pt_disp(self, p):            # unrotated drawing point -> displayed paper mm
        q = pymupdf.Point(p) * self.rm
        return q.x / PT, q.y / PT


def open_page(pdf, n=0):
    return pymupdf.open(pdf)[n]


# ---------------------------------------------------------------- extraction
def extract(page, fr, region, layers=None, minw=0.0, minlen=0.0, snap=0.0):
    x0, y0, x1, y1 = region
    segs, arcs = [], []
    for d in page.get_drawings():
        lay = d.get("layer") or ""
        if layers and lay not in layers:
            continue
        w = d.get("width") or 0.0
        if w < minw:
            continue
        for it in d["items"]:
            if it[0] == "l":
                a, b = fr.pt_disp(it[1]), fr.pt_disp(it[2])
            elif it[0] in ("re", "qu"):         # rectangles and quads (window frames are often quads)
                r = it[1]
                q = r.quad if it[0] == "re" else r
                pts = [fr.pt_disp(p) for p in (q.ul, q.ur, q.lr, q.ll)]
                for i in range(4):
                    _add(segs, pts[i], pts[(i + 1) % 4], w, lay, d, region, fr, minlen, snap)
                continue
            elif it[0] == "c":
                a, b = fr.pt_disp(it[1]), fr.pt_disp(it[4])
                if _inside(a, region) or _inside(b, region):
                    arcs.append({"a": _r(fr.paper_to_real(*a)), "b": _r(fr.paper_to_real(*b)),
                                 "ctrl": [_r(fr.paper_to_real(*fr.pt_disp(it[2]))), _r(fr.paper_to_real(*fr.pt_disp(it[3])))],
                                 "w": round(w, 2), "layer": lay})
                continue
            else:
                continue
            _add(segs, a, b, w, lay, d, region, fr, minlen, snap)
    return segs, arcs


def _inside(p, region):
    x0, y0, x1, y1 = region
    return x0 <= p[0] <= x1 and y0 <= p[1] <= y1


def _r(p, n=4):
    return [round(p[0], n), round(p[1], n)]


def _add(segs, a, b, w, lay, d, region, fr, minlen, snap):
    if not (_inside(a, region) or _inside(b, region)):
        return
    A, B = fr.paper_to_real(*a), fr.paper_to_real(*b)
    L = math.hypot(B[0] - A[0], B[1] - A[1])
    if L < max(minlen, 1e-6):
        return
    ang = math.degrees(math.atan2(B[1] - A[1], B[0] - A[0])) % 180
    o = None
    if snap:
        if min(ang, 180 - ang) <= snap:
            ym = (A[1] + B[1]) / 2; A, B, o = (A[0], ym), (B[0], ym), "h"
        elif abs(ang - 90) <= snap:
            xm = (A[0] + B[0]) / 2; A, B, o = (xm, A[1]), (xm, B[1]), "v"
    segs.append({"a": _r(A), "b": _r(B), "len": round(L, 4), "ang": round(ang, 2), "o": o,
                 "w": round(w, 2), "layer": lay, "dash": d.get("dashes") or "", "color": d.get("color")})


def hv_lines(segs, tol=0.005):
    xs, ys = {}, {}
    for s in segs:
        if s["o"] == "v":
            k = round(s["a"][0] / tol) * tol
            e = xs.setdefault(round(k, 3), {"len": 0, "span": [1e9, -1e9], "w": set()})
            lo, hi = sorted((s["a"][1], s["b"][1]))
        elif s["o"] == "h":
            k = round(s["a"][1] / tol) * tol
            e = ys.setdefault(round(k, 3), {"len": 0, "span": [1e9, -1e9], "w": set()})
            lo, hi = sorted((s["a"][0], s["b"][0]))
        else:
            continue
        e["len"] += hi - lo; e["span"] = [min(e["span"][0], lo), max(e["span"][1], hi)]; e["w"].add(s["w"])
    fmt = lambda D: [{"at": k, "len": round(v["len"], 3), "span": [round(v["span"][0], 3), round(v["span"][1], 3)],
                      "w": sorted(v["w"])} for k, v in sorted(D.items())]
    return {"x_lines (vertical)": fmt(xs), "y_lines (horizontal)": fmt(ys)}


def blocks(page, fr, region):
    """Text blocks (notes, labels) as whole strings with their real-world box: the exact wording for a label."""
    out = []
    for b in page.get_text("blocks"):
        if b[6] != 0:
            continue
        r = pymupdf.Rect(b[:4]) * fr.rm
        cx, cy = (r.x0 + r.x1) / 2 / PT, (r.y0 + r.y1) / 2 / PT
        if not _inside((cx, cy), region):
            continue
        a = fr.paper_to_real(r.x0 / PT, r.y1 / PT); c = fr.paper_to_real(r.x1 / PT, r.y0 / PT)
        out.append({"text": " ".join(b[4].split()), "x": round((a[0] + c[0]) / 2, 3), "y": round((a[1] + c[1]) / 2, 3),
                    "box": [round(min(a[0], c[0]), 3), round(min(a[1], c[1]), 3), round(max(a[0], c[0]), 3), round(max(a[1], c[1]), 3)]})
    out.sort(key=lambda t: (-t["y"], t["x"]))
    return out


def words(page, fr, region):
    # get_text returns UNROTATED coordinates (checked with PyMuPDF 1.28: a /Rotate 270 sheet gives words in the
    # unrotated frame, while get_pixmap's clip is in the displayed frame), so map every word box through
    # rotation_matrix and filter by region afterwards (a clip= here would select the wrong area).
    out = []
    for w in page.get_text("words"):
        r = pymupdf.Rect(w[:4]) * fr.rm
        cx, cy = (r.x0 + r.x1) / 2 / PT, (r.y0 + r.y1) / 2 / PT
        if not _inside((cx, cy), region):
            continue
        rx, ry = fr.paper_to_real(cx, cy)
        out.append({"text": w[4], "x": round(rx, 3), "y": round(ry, 3),
                    "vertical": r.height > 1.5 * r.width and len(w[4]) > 1})
    out.sort(key=lambda t: (-t["y"], t["x"]))
    return out


# ---------------------------------------------------------------- rendering
def render(page, region, dpi):
    from PIL import Image
    x0, y0, x1, y1 = region
    pix = page.get_pixmap(dpi=dpi, clip=pymupdf.Rect(x0 * PT, y0 * PT, x1 * PT, y1 * PT))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    k = pix.width / (x1 - x0)                    # px per paper mm
    to_px = lambda xmm, ymm: ((xmm - x0) * k, (ymm - y0) * k)
    return img, to_px


def font(n):
    from PIL import ImageFont
    for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
              "/Library/Fonts/Arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, n)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_grid(img, to_px, fr, region, step):
    from PIL import ImageDraw
    dr = ImageDraw.Draw(img, "RGBA")
    x0, y0, x1, y1 = region
    corners = [fr.paper_to_real(x, y) for x in (x0, x1) for y in (y0, y1)]
    rx = [c[0] for c in corners]; ry = [c[1] for c in corners]
    f = font(max(10, img.width // 160))
    i = math.floor(min(rx) / step)
    while i * step <= max(rx):
        v = i * step
        a, b = fr.real_to_paper(v, min(ry)), fr.real_to_paper(v, max(ry))
        bold = abs(v) < 1e-9
        dr.line([to_px(*a), to_px(*b)], fill=(220, 40, 40, 200) if bold else (30, 140, 255, 90), width=2 if bold else 1)
        p = to_px(*fr.real_to_paper(v, max(ry))); dr.text((p[0] + 2, p[1] + 2), f"{v:g}", fill=(20, 90, 220, 255), font=f)
        i += 1
    i = math.floor(min(ry) / step)
    while i * step <= max(ry):
        v = i * step
        a, b = fr.real_to_paper(min(rx), v), fr.real_to_paper(max(rx), v)
        bold = abs(v) < 1e-9
        dr.line([to_px(*a), to_px(*b)], fill=(220, 40, 40, 200) if bold else (30, 140, 255, 90), width=2 if bold else 1)
        p = to_px(*fr.real_to_paper(min(rx), v)); dr.text((p[0] + 2, p[1] - 14), f"{v:g}", fill=(20, 90, 220, 255), font=f)
        i += 1


WCOL = {0.12: (180, 180, 180), 0.24: (0, 160, 255), 0.48: (0, 190, 60), 0.72: (230, 30, 30), 0.96: (200, 0, 200)}


def draw_segments(img, to_px, fr, segs):
    from PIL import ImageDraw
    dr = ImageDraw.Draw(img, "RGBA")
    for s in segs:
        c = WCOL.get(s["w"], (255, 140, 0))
        dr.line([to_px(*fr.real_to_paper(*s["a"])), to_px(*fr.real_to_paper(*s["b"]))], fill=c + (200,), width=2)


# ---------------------------------------------------------------- overlay of traced JSON
COL = {"wall": (230, 30, 30), "face": (255, 120, 0), "open": (0, 170, 255), "room": (0, 170, 60),
       "fit": (170, 0, 200), "stair": (0, 120, 120), "line": (255, 0, 160), "pt": (0, 0, 0)}


def node_at(data, path):
    n = data
    for k in path.split("."):
        n = n[int(k)] if isinstance(n, list) else n[k]
    return n


def val(v):
    return v["v"] if isinstance(v, dict) and "v" in v else v


def overlay(page, fr, region, node, dpi, title, out, elev=False):
    from PIL import ImageDraw
    img, to_px = render(page, region, dpi)
    img = img.convert("RGB")
    from PIL import Image
    img = Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), 0.35)
    dr = ImageDraw.Draw(img, "RGBA")
    P = lambda x, y: to_px(*fr.real_to_paper(x, y))
    ppm = (to_px(*fr.real_to_paper(1, 0))[0] - to_px(*fr.real_to_paper(0, 0))[0])   # px per real metre (signed)
    ppm = abs(ppm) or 1
    f = font(max(11, int(ppm * 0.12))); fs = font(max(9, int(ppm * 0.09)))
    if elev:
        for m in node.get("marks", []):
            z = val(m["z"]); xs = m.get("x", None)
            xa, xb = (xs if xs else [node.get("x_range", [-1, 12])[0], node.get("x_range", [-1, 12])[1]])
            dr.line([P(xa, z), P(xb, z)], fill=(230, 30, 30, 220), width=2)
            dr.text((P(xb, z)[0] + 4, P(xb, z)[1] - 8), f'{m.get("label", "")} {z:.3f}', fill=(200, 0, 0), font=fs)
        for b in node.get("boxes", []):
            x0, z0, x1, z1 = map(val, b[:4])
            (ax, ay), (bx, by) = P(x0, z1), P(x1, z0)
            dr.rectangle([min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)], outline=(0, 140, 255, 255), width=2)
            if len(b) > 4:
                dr.text((min(ax, bx) + 2, min(ay, by) - 14), str(b[4]), fill=(0, 90, 200), font=fs)
        for pl in node.get("polylines", []):
            pts = [P(*map(val, p)) for p in pl["pts"]]
            dr.line(pts, fill=COL["line"] + (230,), width=2)
    else:
        for r in node.get("rooms", []):
            poly = [P(*p) for p in r["poly"]]
            dr.polygon(poly, fill=COL["room"] + (40,), outline=COL["room"] + (255,))
            cx = sum(p[0] for p in r["poly"]) / len(r["poly"]); cy = sum(p[1] for p in r["poly"]) / len(r["poly"])
            cl = val(r.get("ceiling", ""))
            dr.text(P(cx - 0.4, cy - 0.25), f'{r["name"]} {cl if isinstance(cl, (int, float)) else ""}', fill=(0, 110, 40), font=fs)
        for fi in node.get("fittings", []):
            if "poly" in fi:
                dr.polygon([P(*p) for p in fi["poly"]], outline=COL["fit"] + (255,))
                dr.text(P(*fi["poly"][0]), fi["name"], fill=COL["fit"], font=fs)
        for st in node.get("stairs", []):
            for tr in st.get("treads_poly", []):
                dr.polygon([P(*p) for p in tr], outline=COL["stair"] + (255,))
        for w in node.get("walls", []):
            x1, y1, x2, y2 = map(val, w["line"]); t = val(w["t"])
            L = math.hypot(x2 - x1, y2 - y1) or 1
            nx, ny = -(y2 - y1) / L * t / 2, (x2 - x1) / L * t / 2
            dr.polygon([P(x1 + nx, y1 + ny), P(x2 + nx, y2 + ny), P(x2 - nx, y2 - ny), P(x1 - nx, y1 - ny)],
                       fill=COL["wall"] + (55,), outline=COL["face"] + (255,))
            dr.line([P(x1, y1), P(x2, y2)], fill=COL["wall"] + (255,), width=2)
            if w.get("id"):
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                dr.text(P(mx, my), w["id"], fill=(150, 0, 0), font=fs)
            for o in w.get("openings", []):
                c, wd = val(o["c"]), val(o["w"])
                ux, uy = (x2 - x1) / L, (y2 - y1) / L
                a = (x1 + ux * (c - wd / 2), y1 + uy * (c - wd / 2)); b = (x1 + ux * (c + wd / 2), y1 + uy * (c + wd / 2))
                for sgn in (1, -1):
                    dr.line([P(a[0] + sgn * nx * 1.3, a[1] + sgn * ny * 1.3), P(a[0] - sgn * nx * 1.3, a[1] - sgn * ny * 1.3)],
                            fill=COL["open"] + (255,), width=3)
                    dr.line([P(b[0] + sgn * nx * 1.3, b[1] + sgn * ny * 1.3), P(b[0] - sgn * nx * 1.3, b[1] - sgn * ny * 1.3)],
                            fill=COL["open"] + (255,), width=3)
                dr.line([P(*a), P(*b)], fill=COL["open"] + (255,), width=5)
                dr.text(P(a[0] + nx * 3, a[1] + ny * 3), f'{o.get("id", o["kind"])} {wd*1000:.0f}', fill=(0, 90, 200), font=fs)
        for pl in node.get("polylines", []):
            dr.line([P(*p) for p in pl["pts"]], fill=COL["line"] + (230,), width=3)
            dr.text(P(*pl["pts"][0]), pl.get("name", ""), fill=COL["line"], font=fs)
        for pt in node.get("points", []):
            x, y = P(pt["xy"][0], pt["xy"][1])
            dr.ellipse([x - 5, y - 5, x + 5, y + 5], outline=(0, 0, 0), width=2)
            dr.text((x + 6, y - 6), pt.get("name", ""), fill=(0, 0, 0), font=fs)
    o = P(0, 0); dr.line([(o[0] - 15, o[1]), (o[0] + 15, o[1])], fill=(0, 0, 0), width=3)
    dr.line([(o[0], o[1] - 15), (o[0], o[1] + 15)], fill=(0, 0, 0), width=3)
    if title:
        dr.rectangle([0, 0, img.width, 34], fill=(255, 255, 255, 230)); dr.text((8, 6), title, fill=(0, 0, 0), font=f)
    img.save(out)
    return out


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["render", "words", "blocks", "segments", "hv", "overlay"])
    ap.add_argument("pdf")
    ap.add_argument("--page", type=int, default=0)
    ap.add_argument("--region", type=float, nargs=4, metavar=("X0", "Y0", "X1", "Y1"), help="paper mm, displayed frame")
    ap.add_argument("--rr", type=float, nargs=4, metavar=("RX0", "RY0", "RX1", "RY1"),
                    help="region in REAL metres of the --origin frame instead of --region")
    ap.add_argument("--origin", type=float, nargs=2)
    ap.add_argument("--scale", type=float, default=50)
    ap.add_argument("--flipx", action="store_true")
    ap.add_argument("--rot", type=float, default=0)
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--grid", type=float, default=0)
    ap.add_argument("--layers")
    ap.add_argument("--minw", type=float, default=0)
    ap.add_argument("--minlen", type=float, default=0.0)
    ap.add_argument("--snap", type=float, default=1.5)
    ap.add_argument("--check")
    ap.add_argument("--json"); ap.add_argument("--path"); ap.add_argument("--title", default="")
    ap.add_argument("--elev", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    page = open_page(a.pdf, a.page)
    fr = Frame(page, a.scale, a.origin, a.flipx, a.rot)
    if a.rr:
        cs = [fr.real_to_paper(x, y) for x in (a.rr[0], a.rr[2]) for y in (a.rr[1], a.rr[3])]
        region = [min(c[0] for c in cs), min(c[1] for c in cs), max(c[0] for c in cs), max(c[1] for c in cs)]
    else:
        region = a.region
    if a.cmd == "render":
        img, to_px = render(page, region, a.dpi)
        if a.origin and a.grid:
            draw_grid(img, to_px, fr, region, a.grid)
        img.save(a.out); print(a.out, img.size)
    elif a.cmd == "words":
        res = words(page, fr, region)
        s = json.dumps(res, indent=0)
        open(a.out, "w").write(s) if a.out else print("\n".join(f'{w["x"]:8.3f} {w["y"]:8.3f}  {w["text"]}' for w in res))
    elif a.cmd == "blocks":
        res = blocks(page, fr, region)
        json.dump(res, open(a.out, "w"), indent=0) if a.out else print("\n".join(f'{b["x"]:8.3f} {b["y"]:8.3f}  {b["text"]}' for b in res))
    elif a.cmd in ("segments", "hv"):
        layers = set(a.layers.split(",")) if a.layers else None
        segs, arcs = extract(page, fr, region, layers, a.minw, a.minlen, a.snap)
        res = {"segments": segs, "arcs": arcs} if a.cmd == "segments" else hv_lines(segs)
        if a.out:
            json.dump(res, open(a.out, "w"), indent=0)
        elif a.cmd == "hv":
            for k, v in res.items():
                print(k)
                for e in v:
                    print(f'  {e["at"]:8.3f}  len {e["len"]:7.3f}  span {e["span"][0]:7.3f}..{e["span"][1]:7.3f}  w {e["w"]}')
        else:
            print(len(segs), "segments", len(arcs), "arcs")
        if a.check:
            img, to_px = render(page, region, a.dpi)
            from PIL import Image
            img = Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), 0.5)
            draw_segments(img, to_px, fr, segs)
            if a.grid:
                draw_grid(img, to_px, fr, region, a.grid)
            img.save(a.check); print(a.check)
    elif a.cmd == "overlay":
        data = json.load(open(a.json))
        node = node_at(data, a.path) if a.path else data
        print(overlay(page, fr, region, node, a.dpi, a.title, a.out, a.elev))


if __name__ == "__main__":
    main()
