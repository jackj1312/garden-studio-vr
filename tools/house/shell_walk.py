"""G5b walk inspection (WORKFLOW G5b item 9): a frame from the doorway and from the centre of every room, per version.

    python3 tools/house/shell_walk.py cams --site assets/sites/house --version approved_2b --out renders/house-build/first-build/shell/after
        -> <out>/cams.json and prints the --views list for house_views.py
    (render: Blender -b --python tools/house/house_views.py -- --glb <site>/<v>.glb --eevee --asbuilt on --stage <N> --sun-dir afternoon
             --cams <out>/cams.json --views <list> --out <out> --px 900)
    uv run --with pillow python tools/house/shell_walk.py sheet --out <dir>     -> <out>/sheet_<k>.jpg contact sheets, labelled

Centre frame: eye 1.55 m above the floor at the room's centroid (pulled inside if the centroid falls outside the polygon),
looking at the farthest corner (the longest view across the room), 16 mm lens (wide, as a person turning sees it).
Doorway frame: eye 0.35 m outside each door opening that leads into the room, looking through it at the room's centre."""
import sys, os, json, math, argparse

ap = argparse.ArgumentParser()
ap.add_argument("mode"); ap.add_argument("--site", default="assets/sites/house"); ap.add_argument("--version", default="approved_2b")
ap.add_argument("--spec", default="assets/sites/house/spec/spec_v1.json"); ap.add_argument("--out", required=True)
a = ap.parse_args()


def in_poly(x, z, P):
    c = False; n = len(P)
    for i in range(n):
        x1, z1 = P[i]; x2, z2 = P[(i + 1) % n]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1 + 1e-15) + x1: c = not c
    return c


def cams():
    S = json.load(open(a.spec)); vk = "before" if a.version == "as_built_now" else "after"
    rooms = S["versions"][vk]["rooms"]
    els = json.load(open(os.path.join(a.site, f"{a.version}_elements.json")))["elements"]
    walls = {e["id"]: e for e in els if e["type"] == "wall"}
    doors = []
    for e in els:
        if e["type"] != "opening" or "door" not in (e["meta"].get("group", "") + e["id"]): continue
        w = walls.get(e["params"]["host"])
        if not w: continue
        (sx, sz), (ex, ez) = w["params"]["start"], w["params"]["end"]
        L = math.hypot(ex - sx, ez - sz) or 1e-9; dx, dz = (ex - sx) / L, (ez - sz) / L
        u = e["params"]["offset"] + e["params"]["width"] / 2
        doors.append((e["id"], sx + dx * u, sz + dz * u, -dz, dx, w["meta"].get("storey", "ground")))
    C = []
    for r in rooms:
        P = r["polygon"]; fy = r["floor_y"]
        n = len(P); A = cx = cz = 0.0
        for i in range(n):
            x1, z1 = P[i]; x2, z2 = P[(i + 1) % n]; cr = x1 * z2 - x2 * z1; A += cr; cx += (x1 + x2) * cr; cz += (z1 + z2) * cr
        cx, cz = (cx / (3 * A), cz / (3 * A)) if abs(A) > 1e-9 else (P[0][0], P[0][1])
        if not in_poly(cx, cz, P):
            best = min(((x, z) for x in [min(p[0] for p in P) + 0.1 * k for k in range(200)] for z in [min(p[1] for p in P) + 0.1 * k for k in range(200)]
                        if in_poly(x, z, P)), key=lambda q: (q[0] - cx) ** 2 + (q[1] - cz) ** 2, default=(cx, cz))
            cx, cz = best
        # the room seen across its longest diagonal: from just inside one corner toward the far corner (eye 1.55 m)
        pa, pb = max(((p, q) for p in P for q in P), key=lambda t: (t[0][0] - t[1][0]) ** 2 + (t[0][1] - t[1][1]) ** 2)
        ex_, ez_ = pa[0] + (pb[0] - pa[0]) * 0.1, pa[1] + (pb[1] - pa[1]) * 0.1
        for _ in range(20):
            if in_poly(ex_, ez_, P): break
            ex_, ez_ = ex_ + (cx - ex_) * 0.2, ez_ + (cz - ez_) * 0.2
        tid = r["id"].replace("R-", "").replace("-", "_")[:40]
        C.append(dict(name=f"{tid}__centre", room=r["id"], eye=[round(ex_, 3), round(fy + 1.55, 3), round(ez_, 3)],
                      target=[pb[0], fy + 1.0, pb[1]], lens=14, aspect=0.5625))
        k = 0
        for (did, ox, oz, nx, nz, st) in doors:
            if abs((0.0 if st == "ground" else 2.6755) - fy) > 0.5: continue
            for sg in (1, -1):
                ix, iz = ox + nx * sg * 0.4, oz + nz * sg * 0.4
                if in_poly(ix, iz, P):
                    ex_, ez_ = ox - nx * sg * 0.35, oz - nz * sg * 0.35
                    C.append(dict(name=f"{tid}__door{k}", room=r["id"], door=did, eye=[round(ex_, 3), round(fy + 1.55, 3), round(ez_, 3)],
                                  target=[round(cx, 3), fy + 1.2, round(cz, 3)], lens=16, aspect=0.5625))
                    k += 1
                    break
            if k >= 1: break
    os.makedirs(a.out, exist_ok=True)
    json.dump(C, open(os.path.join(a.out, "cams.json"), "w"), indent=1)
    print(",".join("cam:" + c["name"] for c in C))


def sheet():
    from PIL import Image, ImageDraw
    C = json.load(open(os.path.join(a.out, "cams.json")))
    ims = []
    for c in C:
        fs = [f for f in os.listdir(a.out) if f.startswith(c["name"]) and f.endswith(".png")]
        if fs: ims.append((c, os.path.join(a.out, fs[0])))
    W, H = 600, 338; cols = 3; per = 12
    for s0 in range(0, len(ims), per):
        chunk = ims[s0:s0 + per]; rows = (len(chunk) + cols - 1) // cols
        Sh = Image.new("RGB", (cols * W, rows * (H + 18)), "white"); d = ImageDraw.Draw(Sh)
        for i, (c, p) in enumerate(chunk):
            x, y = (i % cols) * W, (i // cols) * (H + 18)
            Sh.paste(Image.open(p).convert("RGB").resize((W, H)), (x, y)); d.text((x + 4, y + H + 3), c["name"], fill=(0, 0, 0))
        Sh.save(os.path.join(a.out, f"sheet_{s0 // per + 1}.jpg"), quality=85)
        print("wrote", os.path.join(a.out, f"sheet_{s0 // per + 1}.jpg"))


cams() if a.mode == "cams" else sheet()
