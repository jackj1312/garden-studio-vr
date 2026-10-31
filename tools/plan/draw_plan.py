"""Draw a property's scale plan from its plan JSON, colour-coded by how each
line was measured. The plan is what the customer (and Jack) sign off before
anything is modelled.

    python3 tools/plan/draw_plan.py <plan.json> <out.png> [title]

Plan JSON (metres; x along the house front, y towards the house, road at -y):
  house:   {porch:[x0,x1,y0,y1], left_wing_face_y, right_wing_face_y, right_wing_x:[x0,x1]}
  lawn.edge, bed.edge, paving_apron.poly, path_900.x, tree_trunk.xy, pergola_posts,
  bins.xy_range, hedge.xy_range, fence_drive_side.points, street.pavement_back_y
Every entry carries a "source" and (where not exact) an "accuracy".
"""
import sys, json, math
from PIL import Image, ImageDraw, ImageFont

plan = json.load(open(sys.argv[1])); out = sys.argv[2]
OVER = "--overlay" in sys.argv
args = [a for a in sys.argv[1:] if not a.startswith("--")]
title = args[2] if len(args) > 2 else "Plan"
X0, X1, Y0, Y1 = plan.get("view", [-9.0, 15.0, -15.0, 6.0])
ppm = 1200.0 / (X1 - X0)
W, H = int((X1 - X0) * ppm), int((Y1 - Y0) * ppm)
img = Image.new("RGB", (W, H + 300), (255, 255, 252)); d = ImageDraw.Draw(img)
P = lambda x, y: ((x - X0) * ppm, (Y1 - y) * ppm + 60)
if OVER and "underlay" in plan:   # the top-down photo under the lines, so every line can be checked by eye
    u = plan["underlay"]; ux0, ux1, uy0, uy1 = u["extent"]; ui = Image.open(u["png"]).convert("RGB")
    ui = ui.resize((int((ux1 - ux0) * ppm), int((uy1 - uy0) * ppm)))
    ui = Image.blend(ui, Image.new("RGB", ui.size, (255, 255, 255)), 0.15)
    img.paste(ui, tuple(int(v) for v in P(ux0, uy1)))
def font(n):
    try: return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", n)
    except Exception: return ImageFont.load_default()
F, FB, FS = font(15), font(22), font(12)
SC, PH, EST = (25, 25, 25), (20, 90, 200), (230, 120, 20)
GRASS, PAVE, GRAV, SOIL, HEDGE, HOUSE = (150, 196, 110), (205, 170, 160), (232, 222, 196), (130, 105, 85), (70, 120, 60), (196, 120, 96)

for gx in range(int(X0), int(X1) + 1):  # grid
    d.line([P(gx, Y0), P(gx, Y1)], fill=(232, 232, 228) if gx % 5 else (200, 200, 195)); d.text(P(gx + 0.05, Y0 + 0.45), str(gx), fill=(150, 150, 150), font=FS)
for gy in range(int(Y0), int(Y1) + 1):
    d.line([P(X0, gy), P(X1, gy)], fill=(232, 232, 228) if gy % 5 else (200, 200, 195)); d.text(P(X0 + 0.05, gy + 0.3), str(gy), fill=(150, 150, 150), font=FS)

def poly(pts, fill=None, outline=None, w=2):
    q = [P(*p) for p in pts]
    if fill and not OVER: d.polygon(q, fill=fill)
    if outline: d.line(q + [q[0]], fill=outline, width=w)
def dash(pts, col, w=3, close=False):
    q = [P(*p) for p in pts] + ([P(*pts[0])] if close else [])
    for (ax, ay), (bx, by) in zip(q, q[1:]):
        L = math.hypot(bx - ax, by - ay); n = max(1, int(L / 12))
        for k in range(0, n, 2):
            t0, t1 = k / n, min(1, (k + 1) / n)
            d.line([(ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1)], fill=col, width=w)
def T(x, y, s, col=SC, f=F): d.text(P(x, y), s, fill=col, font=f)
def dim(a, b, s, off=(0, 0)):
    pa, pb = P(*a), P(*b); d.line([pa, pb], fill=PH, width=1)
    for p in (pa, pb): d.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3], fill=PH)
    d.text(((pa[0] + pb[0]) / 2 + off[0], (pa[1] + pb[1]) / 2 + off[1]), s, fill=PH, font=FS)

street_y = plan.get("street", {}).get("pavement_back_y", -13.0) if isinstance(plan.get("street", {}).get("pavement_back_y"), (int, float)) else -13.0
_fp = plan.get("fence_drive_side", {}).get("points", [[12, 0], [12, -1]])
def fence_x(y):   # the fence as a straight line through its first and last points (it needn't be parallel to the house)
    (xa, ya), (xb, yb) = _fp[0], _fp[-1]
    return xa if ya == yb else xa + (xb - xa) * (y - ya) / (yb - ya)
lawn = [tuple(p) for p in plan["lawn"]["edge"]]
px0, px1 = plan["path_900"]["x"]
apron = [tuple(p) for p in plan.get("paving_apron", {}).get("poly", [])]
apron_x = max((p[0] for p in apron), default=4.4)
# ground fills: gravel everywhere first, then paving, lawn, bed on top
poly([(px1, street_y), (fence_x(street_y), street_y), (fence_x(1.5), 1.5), (px1, 1.5)], GRAV)
if "lawn_west" in plan: poly([tuple(p) for p in plan["lawn_west"]["poly"]], GRASS)
if "vehicle" in plan: poly([tuple(p) for p in plan["vehicle"]["poly"]], (150, 150, 155)); T(plan["vehicle"]["poly"][0][0] + 0.2, plan["vehicle"]["poly"][0][1] - 0.6, "van (parked, rough)", (255, 255, 255), FS)
poly([(px0, street_y), (px1, street_y), (px1, -1.0), (px0, -1.0)], PAVE)
h = plan["house"]; pz = h["porch"]
poly([(px0, -1.0), (h["right_wing_x"][1], -1.0), (h["right_wing_x"][1], h["right_wing_face_y"]), (pz[1], h["right_wing_face_y"]),
      (pz[1], pz[2]), (pz[0], pz[2]), (pz[0], h["left_wing_face_y"]), (px0, h["left_wing_face_y"])], PAVE)
if apron: poly(apron, PAVE, PH, 2)
if "paving_side" in plan:
    ps = [tuple(p) for p in plan["paving_side"]["poly"]]; poly(ps, PAVE); dash(ps, PH if "walk" in plan["paving_side"].get("source", "") else EST, 2, True)
    T(4.55, -2.3, "block paving", PH, FS)
if "shed" in plan:   # front face measured; the depth is drawn dashed until it is seen
    sh = plan["shed"]; (sx0, sy), (sx1, _) = sh["front"]; sd = sh.get("depth_m", 1.5)
    poly([(sx0, sy), (sx1, sy), (sx1, sy + sd), (sx0, sy + sd)], (150, 62, 52)); dash([(sx1, sy), (sx1, sy + sd), (sx0, sy + sd)], EST, 2)
    d.line([P(sx0, sy), P(sx1, sy)], fill=PH, width=4); T(sx0 + 0.1, sy + 1.0, "SHED", (255, 255, 255), FS)
poly(lawn, GRASS, PH, 3)
poly([tuple(p) for p in plan["bed"]["edge"]], SOIL, PH, 3)
for e in plan.get("edgings", []):     # every edging run as its own laid line, full length
    (ax, ay), (bx, by) = e["line"]; L = math.hypot(bx - ax, by - ay); nx, ny = -(by - ay) / L * e["width"] / 2, (bx - ax) / L * e["width"] / 2
    poly([(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)], (150, 150, 146), (90, 90, 90), 1)
if "hedge" in plan:
    (hx0, hx1), (hy0, hy1) = plan["hedge"]["xy_range"]
    poly([(hx0, hy0), (hx1, hy0), (hx1, hy1), (hx0, hy1)], HEDGE); dash([(hx0, hy0), (hx1, hy0), (hx1, hy1), (hx0, hy1)], EST, 2, True)
    T(-8.6, (hy0 + hy1) / 2, f"{plan['hedge'].get('kind', 'hedge')} {plan['hedge'].get('accuracy', '')}", PH if "walk" in plan["hedge"].get("source", "") else EST, FS)
if "street_hedge" in plan:
    (hx0, hx1), (hy0, hy1) = plan["street_hedge"]["xy_range"]
    poly([(hx0, hy0), (hx1, hy0), (hx1, hy1), (hx0, hy1)], HEDGE); dash([(hx0, hy0), (hx1, hy0), (hx1, hy1), (hx0, hy1)], EST, 2, True)
    T(hx0 + 0.2, hy0 - 0.7, f"street hedge {plan['street_hedge'].get('height_m', '')} m tall (west end ±0.5 m)", PH, FS)
# house
poly([(-6.6, h["left_wing_face_y"]), (pz[0], h["left_wing_face_y"]), (pz[0], pz[2]), (pz[1], pz[2]), (pz[1], h["right_wing_face_y"]),
      (h["right_wing_x"][1], h["right_wing_face_y"]), (h["right_wing_x"][1], 5.5), (-6.6, 5.5)], HOUSE, SC, 4)
T(-6.0, 4.2, "HOUSE (front measured from scan)", (255, 255, 255)); T(pz[0] + 0.25, 2.0, "PORCH", (255, 255, 255)); T(pz[1] + 0.7, 2.0, "RIGHT WING", (255, 255, 255))
# measured objects
tx, ty = plan["tree_trunk"]["xy"]; c = P(tx, ty)
d.ellipse([c[0] - 150, c[1] - 150, c[0] + 150, c[1] + 150], outline=(60, 140, 60), width=2)
d.ellipse([c[0] - 8, c[1] - 8, c[0] + 8, c[1] + 8], fill=PH)
T(tx + 0.25, ty + 0.35, f"apple tree trunk ({tx}, {ty}) {plan['tree_trunk'].get('accuracy', '')}", PH)
T(tx - 1.6, ty + 2.6, "canopy ≈ 6 m (estimate)", (60, 140, 60), FS)
for x, y in plan["pergola_posts"]["front"] + plan["pergola_posts"]["rear"]:
    c = P(x, y); d.rectangle([c[0] - 4, c[1] - 4, c[0] + 4, c[1] + 4], fill=SC)
T(-0.6, -0.55, "pergola posts (scan + photo agree ±12 cm)", SC, FS)
if "bins" in plan:
    (bx0, bx1), (by0, by1) = plan["bins"]["xy_range"]
    d.rectangle([*P(bx0, by1), *P(bx1, by0)], outline=EST, width=2); T(bx0, by0 - 0.1, f"bins {plan['bins'].get('accuracy', '')}", EST, FS)
if "fence_drive_side" in plan:
    fd = plan["fence_drive_side"]; dash([tuple(p) for p in fd["points"]], PH if "walk" in fd.get("source", "") else EST, 3)
    fx, fy = fd["points"][0]; T(fx - 2.4, -7.0, f"slatted fence {fd.get('accuracy', '')}", PH if "walk" in fd.get("source", "") else EST, FS)
st = plan.get("street", {}); dash([(X0, street_y), (X1, street_y)], PH if "walk" in st.get("source", "") else EST, 3)
T(X0 + 0.3, street_y - 0.6, f"back of pavement y {street_y}  {st.get('accuracy', '(NOT measured)')}", PH if "walk" in st.get("source", "") else EST)
T(-3.0, -4.2, "LAWN", (40, 90, 30), FB); T(4.2, -12.0, "GRAVEL", (120, 100, 60), FB)
bed = plan["bed"]["edge"]; T(sum(p[0] for p in bed) / len(bed) - 0.4, sum(p[1] for p in bed) / len(bed), "bed", (255, 255, 255), FS)
# dimensions
dim((px0, -3.0), (px1, -3.0), f"{px1 - px0:.2f} m", (-50, -16))
xs = [p[0] for p in lawn]; dim((min(xs), -8.5), (max(xs), -8.5), f"lawn {max(xs) - min(xs):.1f} m wide", (-40, 4))
front = min(p[1] for p in lawn); dim((-3.3, -1.0), (-3.3, front), f"{-1.0 - front:.1f} m: paving to the lawn's front edge", (6, 40))
d.text((14, 12), title, fill=SC, font=FB)
y = H + 80
d.line([(20, y), (20 + 5 * ppm, y)], fill=SC, width=4)
for k in range(6): d.line([(20 + k * ppm, y - 6), (20 + k * ppm, y + 6)], fill=SC, width=2)
d.text((20, y + 10), "0        1        2        3        4        5 m", fill=SC, font=FS)
d.line([(330, y), (380, y)], fill=SC, width=4); d.text((390, y - 9), "measured from the scan", fill=SC, font=F)
d.line([(330, y + 26), (380, y + 26)], fill=PH, width=4); d.text((390, y + 17), "measured from photos (cameras locked to the scan, ±4 cm)", fill=PH, font=F)
d.line([(330, y + 52), (345, y + 52)], fill=EST, width=4); d.line([(355, y + 52), (370, y + 52)], fill=EST, width=4); d.text((390, y + 43), "rough: seen only far away, or not at all", fill=EST, font=F)
for i, line in enumerate(plan.get("checks", [])):
    d.text((20, y + 80 + 22 * i), line, fill=(90, 90, 90), font=F)
img.save(out); print(img.size)
