"""Heavy straight strokes inside a box of a vector PDF sheet, to read wall faces and frame lines exactly.

    python faces.py SHEET.pdf x0 y0 x1 y1 [min_width] [--page N]

Coordinates are displayed-page points (page rotation applied), y down, as in pdfvec.py. Prints the horizontal strokes
(y: merged x-spans with the heaviest pen width) and the vertical strokes (x: merged y-spans). Unlike axlines.py it reads
the PDF directly, keeps every pen at or above `min_width` (default 0.5 pt) and keeps strokes that only cross the box.
Use it to read faces on several independent walls before registering one view to another (never one face pair).
Added 2026-11-10 by Claude (Opus 5.5) from the 23 Battle Road CAD upgrade; no property values inside."""
import sys


def extract_lines(pdf, page=0):
    """Every straight line and rectangle edge on the page as (x0, y0, x1, y1, width) in displayed points."""
    import fitz
    p = fitz.open(pdf)[page]; M = p.rotation_matrix
    out = []
    for dr in p.get_drawings():
        w = dr.get("width") or 0.0
        for it in dr["items"]:
            if it[0] == "l":
                a, b = fitz.Point(it[1]) * M, fitz.Point(it[2]) * M
                out.append((a.x, a.y, b.x, b.y, w))
            elif it[0] == "re":
                r = fitz.Rect(it[1]) * M; r.normalize()
                out += [(r.x0, r.y0, r.x1, r.y0, w), (r.x1, r.y0, r.x1, r.y1, w), (r.x1, r.y1, r.x0, r.y1, w), (r.x0, r.y1, r.x0, r.y0, w)]
            elif it[0] == "qu":
                q = it[1] * M; pts = [q.ul, q.ur, q.lr, q.ll]
                out += [(pts[k].x, pts[k].y, pts[(k + 1) % 4].x, pts[(k + 1) % 4].y, w) for k in range(4)]
    return out


def _merge(spans, gap=0.05):
    spans = sorted(spans); out = [list(spans[0])]
    for a, b, w in spans[1:]:
        if a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b); out[-1][2] = max(out[-1][2], w)
        else:
            out.append([a, b, w])
    return [tuple(s) for s in out]


def strokes(lines, box, min_width=0.5, axis_tol=0.05, min_len=0.3, nd=1):
    """(H, V): {y: [(x_min, x_max, width)]} and {x: [(y_min, y_max, width)]} for axis-aligned strokes of pen >= min_width
    that touch the box; positions rounded to `nd` decimals, touching spans merged."""
    x0, y0, x1, y1 = box; H, V = {}, {}
    for a, b, c, d, w, *_ in lines:
        if w < min_width:
            continue
        if not (min(a, c) <= x1 and max(a, c) >= x0 and min(b, d) <= y1 and max(b, d) >= y0):
            continue
        if abs(b - d) < axis_tol and abs(a - c) > min_len:
            H.setdefault(round((b + d) / 2, nd), []).append((round(min(a, c), nd), round(max(a, c), nd), round(w, 3)))
        elif abs(a - c) < axis_tol and abs(b - d) > min_len:
            V.setdefault(round((a + c) / 2, nd), []).append((round(min(b, d), nd), round(max(b, d), nd), round(w, 3)))
    return {k: _merge(v) for k, v in H.items()}, {k: _merge(v) for k, v in V.items()}


def main(argv):
    page = 0
    if "--page" in argv:
        i = argv.index("--page"); page = int(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    if len(argv) < 5:
        print(__doc__); return 2
    pdf = argv[0]; box = tuple(map(float, argv[1:5])); mw = float(argv[5]) if len(argv) > 5 else 0.5
    H, V = strokes(extract_lines(pdf, page), box, mw)
    print("H (y: x-spans, width)"); [print(f"  y {k}: {v}") for k, v in sorted(H.items())]
    print("V (x: y-spans, width)"); [print(f"  x {k}: {v}") for k, v in sorted(V.items())]
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
