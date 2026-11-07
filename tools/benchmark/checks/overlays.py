"""OVERLAY residual checks: solved cameras and drawing registrations, at full resolution.

Input: an overlay-residuals JSON (schema in docs/benchmark/PLAN-DATA-SCHEMA.md, section "Overlay residuals"):
  {"schema": "garden-studio/overlay-residuals/1",
   "images": [{"id", "source", "kind": "photo|frame|drawing", "width_px", "height_px", "native_width_px",
               "native_height_px", "solve": {"method", "rms_px"}, "points": [{"id", "observed": [u, v],
               "projected": [u, v]}], "edges": [{"id", "element", "max_px"} | {"id", "element", "residuals_px": [...]}]}]}

Check ids:
  overlay.resolution  the overlay is at the source's full (native) resolution
  overlay.rms         camera / registration RMS <= 8 px (computed from points when given, else solve.rms_px)
  overlay.edges       every structural edge within 15 px (max residual along the edge)
  overlay.coverage    at least one solved image (WARN if fewer than `min_images`)
"""
import json, math
from plandata import Result

C = "overlay"
RMS_PX = 8.0
EDGE_PX = 15.0


def load(path):
    with open(path) as f:
        return json.load(f)


def run(data, rms_px=RMS_PX, edge_px=EDGE_PX, min_images=1, label="overlays"):
    res = []
    if data.get("schema") != "garden-studio/overlay-residuals/1":
        res.append(Result(C + ".schema", "FAIL", label, "schema must be 'garden-studio/overlay-residuals/1'", None))
        return res
    imgs = data.get("images") or []
    if len(imgs) < min_images:
        res.append(Result(C + ".coverage", "FAIL" if not imgs else "WARN", label, "%d solved image(s), expected at least %d" % (len(imgs), min_images), None))
    for im in imgs:
        iid = im.get("id") or im.get("source") or "?"
        w, h = im.get("width_px"), im.get("height_px")
        nw, nh = im.get("native_width_px", w), im.get("native_height_px", h)
        if not (w and h):
            res.append(Result(C + ".resolution", "FAIL", iid, "width_px and height_px are required", None))
        elif (w, h) != (nw, nh) and (w, h) != (nh, nw):
            res.append(Result(C + ".resolution", "FAIL", iid, "overlay at %dx%d, source is %dx%d: residuals must be measured at full resolution" % (w, h, nw, nh), None))
        else:
            res.append(Result(C + ".resolution", "PASS", iid, "%dx%d (full resolution)" % (w, h), None))
        pts = im.get("points") or []
        if pts:
            sq = [(p["observed"][0] - p["projected"][0]) ** 2 + (p["observed"][1] - p["projected"][1]) ** 2 for p in pts]
            rms = math.sqrt(sum(sq) / len(sq)); src = "%d points" % len(pts)
            worst = max(zip(sq, pts), key=lambda t: t[0])
            src += ", worst %s %.1f px" % (worst[1].get("id", "?"), math.sqrt(worst[0]))
        else:
            rms = (im.get("solve") or {}).get("rms_px"); src = "solve.rms_px"
        if rms is None:
            res.append(Result(C + ".rms", "FAIL", iid, "no points and no solve.rms_px: the camera/registration residual is unknown", None))
        else:
            res.append(Result(C + ".rms", "PASS" if rms <= rms_px else "FAIL", iid, "RMS %.2f px (limit %.0f; %s)" % (rms, rms_px, src), None))
        edges = im.get("edges") or []
        if not edges:
            res.append(Result(C + ".edges", "FAIL", iid, "no structural edge residuals reported", None))
            continue
        bad = []
        for e in edges:
            m = e.get("max_px")
            if m is None and e.get("residuals_px"):
                m = max(abs(x) for x in e["residuals_px"])
            if m is None:
                bad.append("%s: no residual" % e.get("id"))
            elif m > edge_px:
                bad.append("%s (%s) %.1f px" % (e.get("id"), e.get("element", "?"), m))
        res.append(Result(C + ".edges", "FAIL" if bad else "PASS", iid,
                          ("%d edge(s) over %.0f px: %s" % (len(bad), edge_px, "; ".join(bad[:10]))) if bad else "%d edges within %.0f px" % (len(edges), edge_px), None))
    return res
