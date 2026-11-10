"""OVERLAY checks v2 (CORRECTIONS-LOG 467, 471): the checker computes every residual itself from the model, the sheet
registration and the image. Numbers typed by the run (the v1 overlay-residuals.json) are ignored with a warning.

DRAWINGS (--drawings <dir>): for every drawn_views[] entry the plan-data walls, openings, roof lines, floors and ceilings
that belong to that view are projected into sheet points with `registration.affine_pt` = [a, b, c, d, e, f]
(pt_x = a*X + b*Y + c, pt_y = d*X + e*Y + f, where (X, Y) is (x, y) for plans / roof plans / site plans and (u, z) for
elevations and sections, see elevations.Frame), sampled every 0.1 m, and each sample is measured to the nearest drawn
line: `<view id>.vectors.json` {"lines": [[x0, y0, x1, y1], ...]} in sheet points (pure Python), or the sheet raster
`<view id>.png` rendered at `registration.px_per_pt` (default 3) pixels per point, with Canny edges and a distance
transform (needs cv2 + numpy). Limits at sheet points: RMS <= 3 pt, every element's worst sample <= 5 pt.

PHOTOS (--solves <dir>): one `<id>.json` per solved photo or frame:
  {"id": "20503", "image": "20503.jpg", "area": "front garden", "width_px": 4000, "height_px": 3000,
   "intrinsics": {"fx", "fy", "cx", "cy", "k1": 0, "k2": 0},
   "pose": {"R": [[..3x3..]], "t": [tx, ty, tz]} | {"rvec": [rx, ry, rz], "t": [..]}}   (site frame -> camera, OpenCV axes)
The house's external wall edges, opening outlines and roof lines are projected (with k1/k2 distortion) and measured to
the image's Canny edges. Limits in pixels at the image's native size: RMS <= 8 px, every element <= 15 px (per element
the 80th percentile of its samples, since foreground planting hides parts of real edges). `--min-images N` requires N
solved images per `area`.

Check ids:
  overlay.ignored      (per v1 residual file) self-reported numbers found and ignored
  overlay.coverage     every drawn view has registration + sheet vectors/raster (plans FAIL at 1A, all views at 1B);
                       a solves dir exists at 1B; each area has >= min_images solved images
  overlay.rms          RMS of all sample residuals for one view / image within the limit
  overlay.edges        every element's residual within the limit (names the worst elements)
  overlay.resolution   (photos) the solve's width/height equals the image file's
"""
import json, math, os
from geom import sub, add, mul, unit, dot, seg_closest, length, point_in_poly
from plandata import Result, HOUSE
from roof import seg2, lines_of
from elevations import Frame, visible_openings
from sections import _poly_crosses
from v2io import sheet_file

C = "overlay"
DRAW_RMS_PT = 3.0
DRAW_EDGE_PT = 5.0
PHOTO_RMS_PX = 8.0
PHOTO_EDGE_PX = 15.0
STEP_M = 0.1


def load(path):
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------- v1 files: ignored
def run_legacy(data, label="overlays"):
    """A v1 overlay-residuals file: its numbers are the run's own and are not evidence."""
    imgs = data.get("images") or [] if isinstance(data, dict) else []
    return [Result(C + ".ignored", "WARN", label, "self-reported, ignored: %d image(s) with typed rms/edge numbers; residuals are computed by the checker from --drawings / --solves" % len(imgs), None)]


def run(data, **kw):
    return run_legacy(data, kw.get("label", "overlays"))


# ---------------------------------------------------------------- model lines per view
def _sample(p0, p1, step=STEP_M):
    L = length(sub(p1, p0)); n = max(1, int(math.ceil(L / step)))
    d = unit(sub(p1, p0))
    return [add(p0, mul(d, L * k / n)) for k in range(n + 1)]


def _footprint(w, grow):
    """Wall rectangle grown by `grow` on every side (boundary-inclusive point tests)."""
    a = add(w.a, mul(w.d, -grow)); L = w.L + 2 * grow; t = w.t + 2 * grow
    n = w.n; h = t / 2
    return [add(a, mul(n, h)), add(add(a, mul(w.d, L)), mul(n, h)), add(add(a, mul(w.d, L)), mul(n, -h)), add(a, mul(n, -h))]


def model_lines(v, view):
    """[(element id, p0, p1)] in the view's own 2D coordinates."""
    kind = view.get("kind"); out = []
    if kind == "plan":
        st = view.get("storey")
        walls = [w for w in v.house_walls() if not (st and w.storey != st)]
        for w in walls:
            others = [_footprint(o, 0.005) for o in walls if o is not w]
            for side in (0.5, -0.5):
                # a face is only drawn where it is exposed: skip the stretches buried inside (or flush against the
                # face of) another wall at a junction, where the drawing has no line (L-corner overlap, breast backs)
                n = max(1, int(math.ceil(w.L / STEP_M)))
                run = None
                for k in range(n):
                    u0, u1 = w.L * k / n, w.L * (k + 1) / n
                    mid = w.point((u0 + u1) / 2, side * w.t)
                    buried = any(point_in_poly(mid, poly) for poly in others)
                    if not buried:
                        run = (run[0], u1) if run else (u0, u1)
                    if (buried or k == n - 1) and run:
                        out.append((w.id, w.point(run[0], side * w.t), w.point(run[1], side * w.t))); run = None
        for o in v.openings.values():
            if o.wall is None or (st and o.wall.storey != st):
                continue
            w = o.wall
            for u in (o.u0, o.u1):
                out.append((o.id, w.point(u, -w.t / 2), w.point(u, w.t / 2)))
    elif kind in ("roof_plan",):
        for rf, ln in lines_of(v.roofs, None, None):
            out.append((rf, *seg2(ln)))
    elif kind in ("site_plan", "location_plan"):
        for w in v.house_walls():
            if w.kind == "external":
                out.append((w.id, w.a, w.b))
    elif kind == "elevation":
        fr = Frame(view)
        for o, u0, u1, z0, z1 in visible_openings(v, view):
            out += [(o.id, (u0, z0), (u1, z0)), (o.id, (u1, z0), (u1, z1)), (o.id, (u1, z1), (u0, z1)), (o.id, (u0, z1), (u0, z0))]
        for rf, ln in lines_of(v.roofs, ("eaves", "gutter", "ridge", "hip", "verge"), HOUSE):
            c, d = seg2(ln)
            out.append((rf, (fr.u(c), ln["start"][2]), (fr.u(d), ln["end"][2])))
    elif kind == "section":
        fr = Frame(view); a, b = fr.a, fr.b
        for rid, r in v.rooms.items():
            if r.get("kind") in ("outside", "void"):
                continue
            poly = [tuple(p) for p in r["polygon"]]
            if not _poly_crosses(poly, a, b):
                continue
            us = [fr.u(p) for p in poly]; u0, u1 = max(0.0, min(us)), min(fr.u(b), max(us))
            if u1 <= u0:
                continue
            z = v.room_floor(r); out.append((rid, (u0, z), (u1, z)))
            pl = v.plane(r.get("storey"))
            if pl is not None:
                out.append((rid, (u0, pl), (u1, pl)))
        from roof import seg_cross
        for w in v.house_walls():
            hit = seg_cross(a, b, w.a, w.b)
            if hit:
                u = fr.u(hit[0]); out.append((w.id, (u, w.base), (u, w.top(hit[1] * w.L))))
    return out


def to_sheet(aff, p):
    a, b, c, d, e, f = aff
    return (a * p[0] + b * p[1] + c, d * p[0] + e * p[1] + f)


def _vector_dist(pt, lines):
    best = None
    for x0, y0, x1, y1 in lines:
        d = seg_closest(pt, (x0, y0), (x1, y1))[0]
        if best is None or d < best:
            best = d
    return best


class RasterEdges:
    """Distance (in sheet points or pixels) from any pixel to the nearest edge/ink of a raster (cv2)."""
    def __init__(self, path, px_per_unit=1.0, mode="ink"):
        import numpy as np, cv2  # noqa: F401
        self.np, self.cv2 = np, cv2
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError("cannot read raster %s" % path)
        self.shape = img.shape; self.ppu = float(px_per_unit)
        if mode == "ink":
            edges = (img < 128).astype(np.uint8)
        else:
            edges = (cv2.Canny(img, 50, 150) > 0).astype(np.uint8)
        if edges.sum() == 0:
            raise ValueError("raster %s has no edges" % path)
        self.dist = cv2.distanceTransform((1 - edges).astype(np.uint8), cv2.DIST_L2, 3)

    def at(self, pt):
        col = int(round(pt[0] * self.ppu)); row = int(round(pt[1] * self.ppu))
        H, W = self.shape
        if not (0 <= col < W and 0 <= row < H):
            return None
        return float(self.dist[row, col]) / self.ppu


def measure(samples_by_element, dist_fn):
    """-> (rms, {element: worst}, n_samples, n_outside)."""
    sq = []; worst = {}; outside = 0
    for el, pts in samples_by_element.items():
        for p in pts:
            d = dist_fn(p)
            if d is None:
                outside += 1; continue
            sq.append(d * d); worst[el] = max(worst.get(el, 0.0), d)
    rms = math.sqrt(sum(sq) / len(sq)) if sq else None
    return rms, worst, len(sq), outside


def run_drawings(v, readings=None, gate="1B", rms_pt=DRAW_RMS_PT, edge_pt=DRAW_EDGE_PT):
    res = []
    views = v.drawn_views or []
    if not views:
        v1 = str((v.data or {}).get("schema", "")).endswith("/1")
        if gate == "1A" and v1:
            res.append(Result(C + ".coverage", "WARN", "-", "v1 plan data: no drawn_views[], so the sheet overlays are not computed (allowed at GATE 1A for a v1 file only; GATE 1B and every v2 file need drawn_views[])", v.name))
        else:
            res.append(Result(C + ".coverage", "FAIL", "-", "no drawn_views[]: no sheet view is declared, nothing can be overlaid (plans are required at 1A)", v.name))
        return res
    for d in views:
        vid = d["id"]; required = d.get("kind") == "plan" or gate == "1B"
        miss = "FAIL" if required else "WARN"
        reg = d.get("registration") or {}
        aff = reg.get("affine_pt")
        if not (isinstance(aff, list) and len(aff) == 6):
            res.append(Result(C + ".coverage", miss, vid, "no registration.affine_pt [a, b, c, d, e, f] (site -> sheet points): the view cannot be overlaid", v.name)); continue
        vec = sheet_file(readings, vid, ".vectors.json"); ras = sheet_file(readings, vid, ".png")
        if not vec and not ras:
            res.append(Result(C + ".coverage", miss, vid, "no <view id>.vectors.json or <view id>.png in --drawings: the view is not covered by a computed overlay", v.name)); continue
        lines = model_lines(v, d)
        if not lines:
            res.append(Result(C + ".coverage", "WARN", vid, "no model element projects into this view", v.name)); continue
        by = {}
        for el, p0, p1 in lines:
            by.setdefault(el, []).extend(to_sheet(aff, p) for p in _sample(p0, p1))
        if vec:
            try:
                vl = [tuple(float(c) for c in ln) for ln in load(vec).get("lines", [])]
            except Exception as e:  # noqa: BLE001
                res.append(Result(C + ".coverage", "FAIL", vid, "sheet vectors unreadable: %s" % e, v.name)); continue
            if not vl:
                res.append(Result(C + ".coverage", "FAIL", vid, "sheet vectors file has no lines", v.name)); continue
            fn = lambda p: _vector_dist(p, vl)  # noqa: E731
            how = "%d drawn vector lines" % len(vl)
        else:
            try:
                re_ = RasterEdges(ras, float(reg.get("px_per_pt", 3.0)), mode="ink")
            except Exception as e:  # noqa: BLE001
                res.append(Result(C + ".coverage", "FAIL", vid, "sheet raster not usable (mesh/raster mode needs cv2 + numpy from .venv-benchmark): %s" % e, v.name)); continue
            fn = re_.at; how = "raster ink at %.1f px/pt" % re_.ppu
        rms, worst, n, outside = measure(by, fn)
        res.append(Result(C + ".coverage", "PASS", vid, "%d element(s), %d samples vs %s%s" % (len(by), n, how, " (%d samples off the sheet)" % outside if outside else ""), v.name))
        if rms is None:
            res.append(Result(C + ".rms", "FAIL", vid, "no sample landed on the sheet: registration wrong?", v.name)); continue
        res.append(Result(C + ".rms", "PASS" if rms <= rms_pt else "FAIL", vid, "RMS %.2f pt (limit %.0f pt, %d samples)" % (rms, rms_pt, n), v.name))
        bad = sorted(((w, el) for el, w in worst.items() if w > edge_pt), reverse=True)
        res.append(Result(C + ".edges", "FAIL" if bad else "PASS", vid, ("%d element(s) over %.0f pt: %s" % (len(bad), edge_pt, "; ".join("%s %.1f pt" % (el, w) for w, el in bad[:10]))) if bad
                          else "every element within %.0f pt (worst %.1f)" % (edge_pt, max(worst.values()) if worst else 0.0), v.name))
    return res


# ---------------------------------------------------------------- photos
def _rodrigues(rv):
    th = math.sqrt(sum(c * c for c in rv))
    if th < 1e-12:
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    kx, ky, kz = [c / th for c in rv]; c, s = math.cos(th), math.sin(th); C1 = 1 - c
    return [[c + kx * kx * C1, kx * ky * C1 - kz * s, kx * kz * C1 + ky * s],
            [ky * kx * C1 + kz * s, c + ky * ky * C1, ky * kz * C1 - kx * s],
            [kz * kx * C1 - ky * s, kz * ky * C1 + kx * s, c + kz * kz * C1]]


class Camera:
    def __init__(self, cam):
        K = cam["intrinsics"]; P = cam["pose"]
        self.fx, self.fy, self.cx, self.cy = float(K["fx"]), float(K["fy"]), float(K["cx"]), float(K["cy"])
        self.k1, self.k2 = float(K.get("k1", 0.0)), float(K.get("k2", 0.0))
        self.R = P["R"] if "R" in P else _rodrigues(P["rvec"]); self.t = [float(c) for c in P["t"]]
        self.w, self.h = cam.get("width_px"), cam.get("height_px")

    def project(self, X):
        Xc = [sum(self.R[i][k] * X[k] for k in range(3)) + self.t[i] for i in range(3)]
        if Xc[2] <= 1e-6:
            return None
        x, y = Xc[0] / Xc[2], Xc[1] / Xc[2]
        r2 = x * x + y * y; f = 1 + self.k1 * r2 + self.k2 * r2 * r2
        u, vv = self.fx * x * f + self.cx, self.fy * y * f + self.cy
        if self.w and self.h and not (0 <= u < self.w and 0 <= vv < self.h):
            return None
        return (u, vv)


def model_lines_3d(v):
    """[(element id, P0, P1)] structural 3D edges of the house: external wall faces (top, bottom, ends), opening
    outlines on the outer face, roof lines."""
    out = []
    for w in v.house_walls():
        if w.kind != "external":
            continue
        for side in (0.5, -0.5):
            a = w.point(0.0, side * w.t); b = w.point(w.L, side * w.t)
            out.append((w.id, (a[0], a[1], w.base), (b[0], b[1], w.base)))
            out.append((w.id, (a[0], a[1], w.top(0.0)), (b[0], b[1], w.top(w.L))))
            out.append((w.id, (a[0], a[1], w.base), (a[0], a[1], w.top(0.0))))
            out.append((w.id, (b[0], b[1], w.base), (b[0], b[1], w.top(w.L))))
    for o in v.openings.values():
        if o.wall is None or o.wall.kind != "external":
            continue
        w = o.wall
        for side in (0.5, -0.5):
            p0 = w.point(o.u0, side * w.t); p1 = w.point(o.u1, side * w.t)
            z0, z1 = o.sill_z, o.head_z
            out += [(o.id, (p0[0], p0[1], z0), (p1[0], p1[1], z0)), (o.id, (p1[0], p1[1], z0), (p1[0], p1[1], z1)),
                    (o.id, (p1[0], p1[1], z1), (p0[0], p0[1], z1)), (o.id, (p0[0], p0[1], z1), (p0[0], p0[1], z0))]
    for rf, ln in lines_of(v.roofs, None, HOUSE):
        out.append((rf, tuple(ln["start"]), tuple(ln["end"])))
    return out


def _sample3(P0, P1, step=STEP_M):
    L = math.sqrt(sum((P1[i] - P0[i]) ** 2 for i in range(3))); n = max(1, int(math.ceil(L / step)))
    return [tuple(P0[i] + (P1[i] - P0[i]) * k / n for i in range(3)) for k in range(n + 1)]


def run_photos(v, solves_dir=None, gate="1B", rms_px=PHOTO_RMS_PX, edge_px=PHOTO_EDGE_PX, min_images=1, percentile=0.8):
    res = []
    if not solves_dir:
        st = "FAIL" if gate == "1B" else "WARN"
        return [Result(C + ".coverage", st, "photos", "no --solves <dir>: no photo/frame overlay computed%s" % (" (allowed at GATE 1A)" if gate == "1A" else ""), v.name)]
    if not os.path.isdir(solves_dir):
        return [Result(C + ".coverage", "FAIL", "photos", "solves dir not found: %s" % solves_dir, v.name)]
    files = sorted(f for f in os.listdir(solves_dir) if f.endswith(".json"))
    if not files:
        return [Result(C + ".coverage", "FAIL", "photos", "no camera solve JSON in %s" % solves_dir, v.name)]
    lines = model_lines_3d(v)
    per_area = {}
    for fn in files:
        try:
            cam_d = load(os.path.join(solves_dir, fn)); cam = Camera(cam_d)
        except Exception as e:  # noqa: BLE001
            res.append(Result(C + ".coverage", "FAIL", fn, "camera solve unreadable: %s" % e, v.name)); continue
        iid = cam_d.get("id") or fn[:-5]
        if cam_d.get("version") not in (None, v.name):
            continue
        img = cam_d.get("image")
        path = img if img and os.path.isabs(img) else (os.path.join(solves_dir, img) if img else None)
        if not path or not os.path.exists(path):
            res.append(Result(C + ".coverage", "FAIL", iid, "image not found: %s" % img, v.name)); continue
        try:
            re_ = RasterEdges(path, 1.0, mode="canny")
        except Exception as e:  # noqa: BLE001
            res.append(Result(C + ".coverage", "FAIL", iid, "photo mode needs cv2 + numpy (.venv-benchmark): %s" % e, v.name)); continue
        H, W = re_.shape
        if cam.w and cam.h and (W, H) != (cam.w, cam.h):
            res.append(Result(C + ".resolution", "FAIL", iid, "solve declares %dx%d but the image is %dx%d: solve and measure at native resolution" % (cam.w, cam.h, W, H), v.name))
        else:
            res.append(Result(C + ".resolution", "PASS", iid, "%dx%d native" % (W, H), v.name))
        cam.w, cam.h = W, H
        per_el = {}
        for el, P0, P1 in lines:
            for P in _sample3(P0, P1):
                q = cam.project(P)
                if q is None:
                    continue
                d = re_.at(q)
                if d is not None:
                    per_el.setdefault(el, []).append(d)
        allv = [d for ds in per_el.values() for d in ds]
        per_area.setdefault(cam_d.get("area") or "(no area)", []).append(iid)
        if not allv:
            res.append(Result(C + ".coverage", "FAIL", iid, "no model edge projects into this image: pose or intrinsics wrong?", v.name)); continue
        res.append(Result(C + ".coverage", "PASS", iid, "%d element(s), %d samples vs Canny edges" % (len(per_el), len(allv)), v.name))
        rms = math.sqrt(sum(d * d for d in allv) / len(allv))
        res.append(Result(C + ".rms", "PASS" if rms <= rms_px else "FAIL", iid, "RMS %.2f px (limit %.0f px, %d samples)" % (rms, rms_px, len(allv)), v.name))
        bad = []
        for el, ds in per_el.items():
            ds = sorted(ds); p = ds[min(len(ds) - 1, int(percentile * (len(ds) - 1)))]
            if p > edge_px:
                bad.append((p, el))
        bad.sort(reverse=True)
        res.append(Result(C + ".edges", "FAIL" if bad else "PASS", iid, ("%d element(s) over %.0f px (%.0fth percentile): %s" % (len(bad), edge_px, percentile * 100, "; ".join("%s %.1f px" % (el, p) for p, el in bad[:10]))) if bad
                          else "every element within %.0f px" % edge_px, v.name))
    if min_images:
        short = {a: ids for a, ids in per_area.items() if len(ids) < min_images}
        if short:
            res.append(Result(C + ".coverage", "FAIL", "photos", "areas with fewer than %d solved images: %s" % (min_images, "; ".join("%s (%d)" % (a, len(i)) for a, i in short.items())), v.name))
        elif per_area:
            res.append(Result(C + ".coverage", "PASS", "photos", "%d area(s) each with >= %d solved image(s)" % (len(per_area), min_images), v.name))
    return res
