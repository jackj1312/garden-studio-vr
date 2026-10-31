"""Draw a house's front elevation and roof section from its house JSON (house_v1.json), for sign-off
before the house is modelled. Solid = measured, dashed = rough. Labels say what each thing IS.
    ~/splat/bin/python tools/plan/draw_elevation.py <house.json> <out.png> [title]"""
import sys, json, math
from PIL import Image, ImageDraw, ImageFont

H = json.load(open(sys.argv[1])); out = sys.argv[2]; title = sys.argv[3] if len(sys.argv) > 3 else "Front elevation"
X0, X1, Z0, Z1 = -11.0, 5.2, -0.3, 9.2
ppm = 100
W1 = int((X1 - X0) * ppm); Hh = int((Z1 - Z0) * ppm)
SX0, SX1 = 0.0, 7.0                        # section: y from the porch front back
W2 = int((SX1 - SX0) * ppm)
img = Image.new("RGB", (W1 + W2 + 120, Hh + 230), (255, 255, 252)); d = ImageDraw.Draw(img)
def F(n): return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", n)
f, fs, fb = F(15), F(12), F(22)
P = lambda x, z: ((x - X0) * ppm + 20, (Z1 - z) * ppm + 60)
Q = lambda y, z: ((y - SX0) * ppm + W1 + 80, (Z1 - z) * ppm + 60)
BRICK, BRICK2, ROOF, STONE, FRAME, GLASS, WHITE, INK, ROUGH = (176, 92, 70), (196, 120, 90), (120, 80, 62), (226, 214, 186), (52, 56, 60), (170, 196, 214), (245, 245, 245), (25, 25, 25), (220, 120, 20)
def rect(fn, a, b, c, e, fill=None, outline=INK, w=2, dash=False):
    p0, p1 = fn(a, e), fn(b, c)
    if fill: d.rectangle([p0, p1], fill=fill)
    if dash:
        for (s, t) in ((p0, (p1[0], p0[1])), ((p1[0], p0[1]), p1), (p1, (p0[0], p1[1])), ((p0[0], p1[1]), p0)):
            L = math.dist(s, t); n = max(1, int(L / 10))
            for k in range(0, n, 2):
                d.line([(s[0] + (t[0] - s[0]) * k / n, s[1] + (t[1] - s[1]) * k / n), (s[0] + (t[0] - s[0]) * min(1, (k + 1) / n), s[1] + (t[1] - s[1]) * min(1, (k + 1) / n))], fill=ROUGH, width=w)
    elif outline: d.rectangle([p0, p1], outline=outline, width=w)
def T(fn, a, b, s, col=INK, font=fs): d.text(fn(a, b), s, fill=col, font=font)
# grid
for gx in range(int(X0), int(X1) + 1):
    d.line([P(gx, Z0), P(gx, Z1)], fill=(232, 232, 228)); d.text(P(gx + 0.03, Z0 + 0.25), str(gx), fill=(150, 150, 150), font=fs)
for gz in range(0, int(Z1) + 1):
    d.line([P(X0, gz), P(X1, gz)], fill=(232, 232, 228)); d.text(P(X0 + 0.03, gz + 0.18), f"{gz} m", fill=(150, 150, 150), font=fs)
d.line([P(X0, 0), P(X1, 0)], fill=INK, width=3)
E = H["eaves"]; R = H["main_roof"]; pw = H["party_wall_x"]["value"]
# main roof (seen from the front: eaves to ridge, across the whole terrace of two)
d.polygon([P(X0, E["fascia"][1]), P(4.4 + 0.33, E["fascia"][1]), P(4.4 + 0.33 - 0.8, R["ridge_z"]), P(X0, R["ridge_z"])], fill=ROOF)
d.line([P(X0, R["ridge_z"]), P(4.4 + 0.33 - 0.8, R["ridge_z"])], fill=ROUGH, width=3)
T(P, -1.0, R["ridge_z"] + 0.35, f"main roof ridge ~{R['ridge_z']} m ({R['accuracy']})", ROUGH, f)
# chimney
c = H["chimney"]; rect(P, c["x"][0], c["x"][1], R["ridge_z"] - 1.2, c["top_z"], BRICK, dash=True)
T(P, c["x"][1] + 0.1, c["top_z"] - 0.1, "chimney, pots (top ±0.3)", ROUGH)
# neighbour (as seen)
rect(P, X0, pw, 0, E["soffit_z"], BRICK2, None)
for w in H["neighbour"]["windows"]:
    rect(P, *w["frame"][:2], *w["frame"][2:], WHITE, (120, 120, 120), 3)
nb = H["neighbour"]["bay_and_porch"]; rect(P, nb["x"][0], nb["x"][1], 0, 3.0, None, None, 2, True)
T(P, -10.3, 3.3, "neighbour's bay and porch (rough)", ROUGH); T(P, -10.8, 6.0, "NEIGHBOUR (as seen, white windows)", INK, f)
d.line([P(pw, 0), P(pw, R["ridge_z"])], fill=(90, 90, 90), width=2); T(P, pw + 0.05, 0.25, f"party wall x {pw}", INK)
# left wing
LW = H["left_wing"]; rect(P, pw, LW["x"][1], 0, E["soffit_z"], BRICK, None)
# right wing (in front)
RW = H["right_wing"]; rect(P, RW["x"][0], RW["x"][1], 0, E["soffit_z"], BRICK, INK, 2)
# eaves band
for a, b in ((X0, LW["x"][1] + 0.1), (RW["x"][0] - 0.33, RW["x"][1] + 0.33)):
    rect(P, a, b, E["soffit_z"], E["fascia"][1], WHITE, INK, 1)
T(P, -4.9, E["fascia"][1] + 0.08, f"white soffit {E['soffit_z']} m, fascia to {E['fascia'][1]} m, black gutter", INK)
def window(w):
    x0, x1, z0, z1 = w["frame"]
    rect(P, x0 - 0.06, x1 + 0.06, z0 - 0.07, z1 + (0.08 if "lintel" in w.get("surround", "") else 0), STONE, None)
    rect(P, x0, x1, z0, z1, GLASS, FRAME, 4)
    for i in range(1, w.get("panes", 2)):
        x = x0 + (x1 - x0) * i / w["panes"]; d.line([P(x, z0), P(x, z1)], fill=FRAME, width=4)
    T(P, x0, z0 - 0.25, f"{w['id']}: {x0}..{x1}, {z0}-{z1} m", INK)
for w in LW["windows"] + RW["windows"]: window(w)
for (a, b) in ((-3.42, -2.03), (1.72, 3.20)):
    rect(P, a, b, 2.30, 2.55, (200, 110, 84), INK, 1); T(P, a + 0.02, 2.62, "soldier course", INK)
# porch (in front of the left wing)
po = H["porch"]; r = po["roof"]
sx = po["side_wall_outer_x"]; ov = r.get("verge_overhang", 0.1)
d.polygon([P(sx - ov, r["front_eaves_z"]), P(po["x"][1], r["front_eaves_z"]), P(po["x"][1], r["meets_wall_z"]), P(sx - ov, r["meets_wall_z"])], fill=ROOF)
d.line([P(sx - ov, r["front_eaves_z"]), P(sx - ov, r["meets_wall_z"])], fill=(70, 74, 78), width=6)
rect(P, sx, po["x"][1], 0, r["front_eaves_z"], (214, 132, 96), INK, 2)
rect(P, sx - ov, po["x"][1], r["front_eaves_z"] - 0.05, r["front_eaves_z"] + 0.22, (70, 74, 78), None)
T(P, sx + 0.05, r["front_eaves_z"] - 0.2, "dark grey fascia, 2 downlights, camera at the corner", INK)
T(P, -2.3, r["meets_wall_z"] + 0.1, f"porch: LEAN-TO, {r['pitch_deg']}°, verge on the path side (not a hip), meets the wall at {r['meets_wall_z']} m", INK)
rl = r["roof_light"]; rect(P, rl["x"][0], rl["x"][1], 2.9, 3.4, GLASS, FRAME, 2); T(P, rl["x"][1] + 0.05, 3.1, "roof light", INK)
m = po["mirror"]; x0, x1, z0, z1 = m["box"]; rw = (x1 - x0) / 2
d.rectangle([P(x0, z1 - rw), P(x1, z0)], fill=(205, 220, 228), outline=(10, 10, 10), width=4)
d.pieslice([P(x0, z1), P(x1, z1 - 2 * rw)], 180, 360, fill=(205, 220, 228), outline=(10, 10, 10), width=4)
T(P, x0 - 0.1, z0 - 0.25, "arched garden MIRROR (not a window)", (160, 0, 0))
T(P, -1.8, 0.3, "front door + house number:\non the porch's left side (section)", INK)
for fx in (-1.95, 0.55, 4.45): d.line([P(fx, 0), P(fx, 4.7)], fill=(20, 20, 20), width=4)
T(P, 4.5, 2.0, "downpipes", INK)
# fixtures
dx, dz = LW["fixtures"][0]["centre"]; d.ellipse([P(dx - 0.25, dz + 0.25), P(dx + 0.25, dz - 0.25)], outline=INK, width=2, fill=(230, 230, 230)); T(P, dx - 0.4, dz - 0.4, "satellite dish", INK)
mb = LW["fixtures"][1]["box"]; rect(P, mb[0], mb[1], mb[2], mb[3], WHITE, INK, 1); T(P, mb[0], mb[3] + 0.05, "meter box", INK)
dp = RW["fixtures"][0]["box"]; rect(P, dp[0], dp[1], dp[2], dp[3], (40, 40, 40), None); T(P, dp[0] - 0.2, dp[3] + 0.05, "metal wall panel", INK)
# ---- section through the porch, looking from the path (y back from the front, z up)
for gy in range(0, 8):
    d.line([Q(gy, Z0), Q(gy, Z1)], fill=(232, 232, 228)); d.text(Q(gy + 0.03, Z0 + 0.25), f"y{gy}", fill=(150, 150, 150), font=fs)
for gz in range(0, int(Z1) + 1): d.line([Q(SX0, gz), Q(SX1, gz)], fill=(232, 232, 228))
d.line([Q(SX0, 0), Q(SX1, 0)], fill=INK, width=3)
rect(Q, po["front_y"], LW["face_y"], 0, r["front_eaves_z"], (214, 132, 96), INK, 2)
d.polygon([Q(po["front_y"], r["front_eaves_z"]), Q(LW["face_y"], r["front_eaves_z"]), Q(LW["face_y"], r["meets_wall_z"] - 0.12), Q(po["front_y"], r["front_eaves_z"] + 0.2)], fill=(214, 132, 96))
T(Q, 1.2, 2.5, "brick gable under the verge", INK)
pl = [f for f in po["fixtures"] if f["id"] == "house_number_plaque"][0]; rect(Q, pl["y"][0], pl["y"][1], pl["z"][0], pl["z"][1], (90, 96, 104), INK, 1); T(Q, pl["y"][0] - 0.2, pl["z"][1] + 0.1, "no. plaque", INK)
d.line([Q(r["front_eaves_y"], r["front_eaves_z"]), Q(LW["face_y"], r["meets_wall_z"])], fill=ROOF, width=10)
fd = po["front_door"]; rect(Q, fd["y"][0], fd["y"][1], fd["z"][0], fd["z"][1], (60, 66, 72), INK, 2); T(Q, fd["y"][0], fd["z"][1] + 0.1, "front door (porch side)", INK)
rect(Q, LW["face_y"], LW["face_y"] + 3.0, 0, E["soffit_z"], BRICK, INK, 2)
d.line([Q(LW["face_y"] - E["overhang"], E["fascia"][1]), Q(R["ridge_y"], R["ridge_z"])], fill=ROOF, width=10)
d.line([Q(R["ridge_y"], R["ridge_z"]), Q(R["ridge_y"] + 2.6, E["fascia"][1])], fill=ROUGH, width=4)
T(Q, LW["face_y"] + 0.1, 6.3, f"main roof {R['pitch_deg']}°\nridge ~{R['ridge_z']} m (rough)", INK)
T(Q, 0.3, 4.6, f"porch roof {r['pitch_deg']}°", INK)
d.text((20, 14), title, fill=INK, font=fb); d.text((W1 + 80, 14), "Section through the porch (seen from the path)", fill=INK, font=F(18))
y = Hh + 90
d.line([(20, y), (60, y)], fill=INK, width=4); d.text((70, y - 9), "measured (wall elevations, 3D points, close-ups)", fill=INK, font=f)
d.line([(20, y + 26), (32, y + 26)], fill=ROUGH, width=4); d.line([(42, y + 26), (54, y + 26)], fill=ROUGH, width=4); d.text((70, y + 17), "rough: please check", fill=ROUGH, font=f)
for i, q in enumerate(H.get("open_questions", [])): d.text((20, y + 55 + 21 * i), "? " + q, fill=(90, 90, 90), font=f)
img.save(out); print(img.size)
