"""Openings drawn inside a stone (or render) surround on an elevation: read sill and head from the FRAME, not the outline.

Elevation readers that take the outer rectangle of a window or door as the opening read the surround and its head band
instead: sills come out low, heads high (on one run by 45 mm and up to 330 mm). Inside a surround the frame's own long
horizontal lines are strictly inset from both sides of the outline. The head is the topmost of them; the sill is the
topmost line of the bottom cluster (the projecting cill nose is drawn lower). The width usually stays the surround's
opening width, which must agree with the plan; `frame_x` is returned too so the caller can check.

    from surround import frame_inside
    rect, found, info = frame_inside(lines, (x0, y0, x1, y1))

`lines` are (x0, y0, x1, y1, ...) in displayed-page points, y down (pdfvec.py / faces.extract_lines). Insets are in sheet
points: the default 1.8 pt is about 63 mm at 1:100 (3.6 pt at 1:50). Keep the surround in the model as flagged fabric;
never delete drawn fabric. Added 2026-11-10 by Claude (Opus 5.5) from the 23 Battle Road CAD upgrade (MISTAKES A06)."""


def frame_inside(lines, outline, min_inset=1.8, min_span=0.8, axis_tol=0.05, edge_tol=0.3, top_margin=1.0, band_depth=(2.0, 10.0)):
    """Returns (rect, found, info). rect = (x0, head_y, x1, sill_y) when frame lines are found inside the outline, else the
    outline unchanged with found=False. info: {'frame_x': (min, max) of the frame lines, 'head_band': bool, 'lines': n}."""
    ox0, oy0, ox1, oy1 = outline; w = ox1 - ox0
    H = [(min(a, c), max(a, c), (b + d) / 2) for a, b, c, d, *_ in lines
         if abs(b - d) < axis_tol and oy0 - edge_tol <= (b + d) / 2 <= oy1 + edge_tol
         and min(a, c) >= ox0 - edge_tol and max(a, c) <= ox1 + edge_tol]
    band = any(h[0] <= ox0 + 0.5 and h[1] >= ox1 - 0.5 and oy0 + band_depth[0] <= h[2] <= oy0 + band_depth[1] for h in H)
    inner = [h for h in H if h[0] >= ox0 + min_inset and h[1] <= ox1 - min_inset and (h[1] - h[0]) >= min_span * w
             and oy0 + top_margin < h[2] < oy1 - edge_tol]
    info = {"head_band": band, "lines": len(inner), "frame_x": None}
    if len(inner) < 2:
        return outline, False, info
    mid = (oy0 + oy1) / 2
    top = min(h[2] for h in inner); bottoms = [h[2] for h in inner if h[2] > mid]
    if not bottoms or top > mid:
        return outline, False, info
    info["frame_x"] = (min(h[0] for h in inner), max(h[1] for h in inner))
    return (ox0, top, ox1, min(bottoms)), True, info
