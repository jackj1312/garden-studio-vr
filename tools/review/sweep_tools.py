"""Check a captured sweep, run the machine pass, build the contact sheets (PLAN S8).

    uv run --offline --with numpy --with pillow python tools/review/sweep_tools.py check  <sweep dir>
    uv run --offline --with numpy --with pillow python tools/review/sweep_tools.py sheets <sweep dir> [--flagged N]

<sweep dir> = renders/house-build/first-build/round-1/sweep/<space>/<version>/ holding plan.json, meta.json, parts.json,
    the frames <point>_e<eye cm>_<f|u>_<yaw|up|dn>.jpg (colour) and ...id.png (the PART picture: every part flat-coloured
    with its index + 1 as 24-bit RGB, magenta = nothing drawn) and <point>_e<eye cm>_<f|u>.pos.json.

check (CORRECTIONS-LOG 237: a capture set is valid only if...)
  (a) every direction's frame at a point/eye/state differs (md5 of the picture), and
  (b) the eye is inside the room polygon (floor to ceiling), or, for a garden, inside the site bounds;
  a set that fails is rejected here, before anyone looks at a frame. Then the machine pass on every frame: near-black
  area; from the part picture the pixels of raw construction parts (brick, block, timber, felt, insulation, screed...) and
  holes (nothing drawn), with the part indices, so a fault names its part; the colour cast. -> validity.json, machine.json
parts: which raw parts show, in how many frames, and where they are (the root-cause list).
sheets: one 4 x 4 contact sheet (480 x 270 tiles) per point/eye/state: 12 level directions, up, down, a plan with the
  standing point, a legend; frames the machine flagged carry a coloured box round the pixels. --flagged N also writes the N
  worst-flagged sheets (flagged-01.jpg ...) mixing points. Nothing here is specific to one house."""
import hashlib, json, math, os, re, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

TW, TH = 480, 270
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
BLACK_FLAG, RAW_FLAG, HOLE_FLAG = 0.08, 0.0004, 0.0004     # fractions of the frame (0.0004 = about 50 pixels of 480 x 270)
RAW = re.compile(r"^(brick|existing_brick|soldier_brick|block|timber|timber_existing|steel|prop_steel|lintel_galv|mineral_wool|pir|dpm|chipboard|membrane|rebar|hardcore|screed|existing_floor|tile|existing_tile|vcl|batten|lead|earth|FG2_roof_felt_gltf)$", re.I)
MASONRY = re.compile(r"^(cream_stone|buff_concrete|concrete)$", re.I)
BG = 0xFF00FF
TABLE = {}


def bearing(yaw):                                         # yaw 0 looks along -z (west); bearing from north = +x
    return (270 - yaw) % 360


def compass(yaw):
    return COMPASS[int((bearing(yaw) + 11.25) // 22.5) % 16]


def inside(x, z, poly):
    c = False
    for i in range(len(poly)):
        (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % len(poly)]
        if (z1 > z) != (z2 > z) and x < (x2 - x1) * (z - z1) / (z2 - z1) + x1:
            c = not c
    return c


def groups(d):
    """(point, eye cm, state) -> {tag: path} from the file names"""
    g = {}
    for f in sorted(os.listdir(d)):
        if not f.endswith(".jpg") or "_" not in f:
            continue
        p, e, s, tag = f[:-4].split("_")
        g.setdefault((p, e, s), {})[tag] = os.path.join(d, f)
    return g


def font(n):
    try:
        return ImageFont.load_default(n)
    except Exception:
        return ImageFont.load_default()


def load_table(d):
    p = os.path.join(d, "parts.json")
    TABLE.clear()
    if os.path.exists(p):
        rows = json.load(open(p))
        TABLE["rows"] = {r[0] + 1: r for r in rows}
        n = max(TABLE["rows"]) + 1
        cls = np.zeros(n, dtype=np.uint8)                      # 0 finished/other, 1 raw construction, 2 masonry (sills, thresholds), 3 glass
        for k, r in TABLE["rows"].items():
            cls[k] = 1 if RAW.match(r[2]) else 2 if MASONRY.match(r[2]) else 3 if re.search(r"glass|mirror", r[2], re.I) else 0
        TABLE["cls"] = cls


def id_masks(idpng):
    """(raw, masonry, hole, ids) from a part picture"""
    b = np.asarray(Image.open(idpng).convert("RGB")).astype(np.int64)
    ids = (b[..., 0] << 16) | (b[..., 1] << 8) | b[..., 2]
    cls = TABLE["cls"]
    hole = (ids == BG) | (ids >= len(cls))
    c = np.where(hole, 0, cls[np.minimum(ids, len(cls) - 1)])
    return (c == 1) & ~hole, (c == 2) & ~hole, hole, ids


def analyse(jpg):
    a = np.asarray(Image.open(jpg).convert("RGB")).astype(np.int16)
    mx = a.max(axis=2)
    out = {"black": float((mx < 16).mean()), "mean": float(a.mean()), "cast": float((a[..., 2].mean() - a[..., 0].mean()) / 255)}
    idp = jpg[:-4] + ".id.png"
    if os.path.exists(idp) and "cls" in TABLE:
        raw, mas, hole, ids = id_masks(idp)
        out.update(raw=float(raw.mean()), mas=float(mas.mean()), hole=float(hole.mean()))
        if raw.any():
            u, c = np.unique(ids[raw], return_counts=True)
            out["raw_parts"] = {int(k - 1): int(v) for k, v in zip(u, c) if v >= 6}
    return out


def check(d):
    plan = json.load(open(os.path.join(d, "plan.json")))
    meta = json.load(open(os.path.join(d, "meta.json")))
    load_table(d)
    g = groups(d)
    val = {"space": plan["space"], "version": plan["version"], "groups": len(g), "frames": 0, "dupes": [], "outside": [], "missing": [], "ok": True}
    mach = {}
    perfloor = {}
    for (p, e, s), frames in sorted(g.items()):
        hashes = {}
        for tag, path in frames.items():
            h = hashlib.md5(open(path, "rb").read()).hexdigest()
            val["frames"] += 1
            if h in hashes:
                val["dupes"].append(f"{os.path.basename(path)} == {os.path.basename(hashes[h])}")
            hashes[h] = path
            mach[os.path.basename(path)] = analyse(path)
        want = len(plan["yaws"]) + 2
        if len(frames) != want:
            val["missing"].append(f"{p}_{e}_{s}: {len(frames)} of {want}")
        pos = json.load(open(os.path.join(d, f"{p}_{e}_{s}.pos.json")))
        ex, ey, ez = pos["eye"]
        if plan["kind"] == "room":
            ok = inside(pos["x"], pos["z"], plan["polygon"]) or str(next(q for q in plan["points"] if q["id"] == p)["tag"]).startswith("door")
            ok = ok and plan["floor_y"] < ey < plan["ceiling_y"]
        else:
            x0, x1, z0, z1 = plan["bounds"]
            ok = x0 <= ex <= x1 and z0 <= ez <= z1 and -0.5 < ey < 4
        if not ok:
            val["outside"].append(f"{p}_{e}_{s}: eye {pos['eye']}")
    val["ok"] = not (val["dupes"] or val["outside"] or val["missing"])
    json.dump(val, open(os.path.join(d, "validity.json"), "w"), indent=1)
    json.dump(mach, open(os.path.join(d, "machine.json"), "w"))
    # summary
    fl = {"black": [], "raw": [], "hole": []}
    for n, m in mach.items():
        if m["black"] >= BLACK_FLAG: fl["black"].append(n)
        if m.get("raw", 0) >= RAW_FLAG: fl["raw"].append(n)
        if m.get("hole", 0) >= HOLE_FLAG: fl["hole"].append(n)
    cast = {s: round(float(np.mean([m["cast"] for n, m in mach.items() if f"_{s}_" in n])), 4) for s in "fu"}
    print(f"{plan['space']}/{plan['version']}: {val['frames']} colour frames in {val['groups']} groups; valid={val['ok']} "
          f"(dupes {len(val['dupes'])}, outside {len(val['outside'])}, missing {len(val['missing'])}); "
          f"flags: near-black {len(fl['black'])}, raw {len(fl['raw'])}, hole {len(fl['hole'])}; mean blue-minus-red {cast}")
    if not val["ok"]:
        print("  REJECTED:", (val["dupes"] + val["outside"] + val["missing"])[:6])
    json.dump(fl, open(os.path.join(d, "flags.json"), "w"), indent=1)
    return val, mach, fl


def plan_tile(plan, pid):
    im = Image.new("RGB", (TW, TH), (245, 243, 238)); dr = ImageDraw.Draw(im)
    if plan["kind"] == "room":
        poly = plan["polygon"]; xs = [p[0] for p in poly]; zs = [p[1] for p in poly]
    else:
        x0, x1, z0, z1 = [0.0, 10.0, 0.0, 22.0]; poly = [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]
        xs = [x0, x1]; zs = [z0, z1]
    pad = 18; sx = (TW - 2 * pad) / (max(zs) - min(zs) + 1e-6); sy = (TH - 2 * pad) / (max(xs) - min(xs) + 1e-6); s = min(sx, sy)
    ox = pad + ((TW - 2 * pad) - s * (max(zs) - min(zs))) / 2; oy = pad + ((TH - 2 * pad) - s * (max(xs) - min(xs))) / 2
    P = lambda x, z: (ox + (z - min(zs)) * s, TH - oy - (x - min(xs)) * s)     # north up (+x), east right (+z, the road)
    dr.polygon([P(x, z) for x, z in poly], outline=(60, 60, 60), fill=(255, 255, 255))
    if plan["kind"] != "room":
        dr.rectangle([P(0, -0.0)[0], P(5.5, 0)[1], P(0, 2.0)[0] + 2, P(0, 0)[1]], outline=(150, 150, 150))
    for q in plan["points"]:
        px, py = P(q["x"], q["z"]); r = 5 if q["id"] == pid else 2
        dr.ellipse([px - r, py - r, px + r, py + r], fill=(200, 30, 30) if q["id"] == pid else (150, 150, 150))
    dr.text((6, 4), "N up, road (E) right", fill=(90, 90, 90), font=font(13))
    return im


def tile(path, label, flags, fnt):
    im = Image.open(path).convert("RGB")
    idp = path[:-4] + ".id.png"
    if os.path.exists(idp) and "cls" in TABLE and (flags.get("raw", 0) >= RAW_FLAG or flags.get("hole", 0) >= HOLE_FLAG):
        raw, mas, hole, _ = id_masks(idp)
        a = np.asarray(im).copy()
        if flags.get("raw", 0) >= RAW_FLAG: a[raw] = (255, 0, 0)
        if flags.get("hole", 0) >= HOLE_FLAG: a[hole] = (255, 0, 255)
        im = Image.fromarray(a)
    if im.size != (TW, TH):
        im = im.resize((TW, TH))
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, len(label) * 8 + 8, 17], fill=(0, 0, 0))
    dr.text((4, 1), label, fill=(255, 255, 255), font=fnt)
    return im


def sheet(d, plan, mach, key, frames):
    p, e, s = key
    fnt = font(13)
    sh = Image.new("RGB", (TW * 4, TH * 4), (30, 30, 30))
    order = [f"{y:03d}" for y in plan["yaws"]] + ["up", "dn"]
    for i, tag in enumerate(order):
        if tag not in frames:
            continue
        name = os.path.basename(frames[tag])
        yaw = int(tag) if tag.isdigit() else 0
        lab = f"{tag} {compass(yaw)}" if tag.isdigit() else {"up": "UP +35", "dn": "DOWN -35"}[tag]
        sh.paste(tile(frames[tag], lab, mach.get(name, {}), fnt), ((i % 4) * TW, (i // 4) * TH))
    sh.paste(plan_tile(plan, p), (2 * TW, 3 * TH))
    leg = Image.new("RGB", (TW, TH), (20, 20, 20)); dr = ImageDraw.Draw(leg); f2 = font(17)
    pt = next(q for q in plan["points"] if q["id"] == p)
    fl = [n for n in mach if n.startswith(f"{p}_{e}_{s}_") and (mach[n]["black"] >= BLACK_FLAG or mach[n].get("raw", 0) >= RAW_FLAG or mach[n].get("hole", 0) >= HOLE_FLAG)]
    lines = [f"{plan['space']} / {plan['version']}", f"point {p} ({pt['tag']})  x {pt['x']} z {pt['z']}", f"eye {int(e[1:]) / 100:.2f} m   {'FURNISHED' if s == 'f' else 'UNFURNISHED'}",
             f"flagged frames: {len(fl)}"] + [f"  {n.split('_', 3)[3][:-4]}: " + ",".join(k for k, t in (("black", BLACK_FLAG), ("raw", RAW_FLAG), ("hole", HOLE_FLAG)) if mach[n].get(k, 0) >= t) for n in fl[:7]]
    for i, t in enumerate(lines):
        dr.text((10, 8 + i * 24), t, fill=(235, 235, 235), font=f2)
    sh.paste(leg, (3 * TW, 3 * TH))
    out = os.path.join(d, "sheets"); os.makedirs(out, exist_ok=True)
    sh.save(os.path.join(out, f"{p}_{e}_{s}.jpg"), quality=78)


def sheets(d, nflag=0):
    plan = json.load(open(os.path.join(d, "plan.json")))
    mach = json.load(open(os.path.join(d, "machine.json")))
    load_table(d)
    g = groups(d)
    for key, frames in g.items():
        sheet(d, plan, mach, key, frames)
    print(f"{plan['space']}/{plan['version']}: {len(g)} contact sheets -> {os.path.relpath(os.path.join(d, 'sheets'))}")
    if nflag:
        sev = sorted(((max(m["black"] / BLACK_FLAG, m.get("raw", 0) / RAW_FLAG / 4, m.get("hole", 0) / HOLE_FLAG / 4), n) for n, m in mach.items()
                      if m["black"] >= BLACK_FLAG or m.get("raw", 0) >= RAW_FLAG or m.get("hole", 0) >= HOLE_FLAG), reverse=True)
        names = [n for _, n in sev][: nflag * 16]
        fnt = font(13)
        for k in range(0, len(names), 16):
            sh = Image.new("RGB", (TW * 4, TH * 4), (30, 30, 30))
            for i, n in enumerate(names[k:k + 16]):
                sh.paste(tile(os.path.join(d, n), n[:-4], mach[n], fnt), ((i % 4) * TW, (i // 4) * TH))
            sh.save(os.path.join(d, f"flagged-{k // 16 + 1:02d}.jpg"), quality=78)
        print(f"  {len(names)} flagged frames on {math.ceil(len(names) / 16)} sheets (flagged-NN.jpg)")


def parts(d, top=30):
    """which raw parts show in the frames, how often, and where: the root-cause list"""
    mach = json.load(open(os.path.join(d, "machine.json")))
    load_table(d)
    agg = {}
    for n, m in mach.items():
        for k, px in m.get("raw_parts", {}).items():
            r = TABLE["rows"][int(k) + 1]
            a = agg.setdefault((r[1], r[2]), {"frames": set(), "px": 0, "bbox_cm": [r[7:10], r[10:13]], "label": r[6], "storey": r[4]})
            a["frames"].add(n); a["px"] += px
    rows = sorted(agg.items(), key=lambda kv: -len(kv[1]["frames"]))[:top]
    out = [{"element": k[0], "material": k[1], "frames": len(v["frames"]), "px": v["px"], "label": v["label"], "bbox_cm": v["bbox_cm"], "example": sorted(v["frames"])[0]} for k, v in rows]
    json.dump(out, open(os.path.join(d, "raw_parts.json"), "w"), indent=1)
    for o in out:
        print(f"{o['frames']:5d} frames {o['px']:8d} px  {o['material']:<22} {o['element'][:46]:<46} bbox_cm {o['bbox_cm']}  e.g. {o['example']}")
    return out


if __name__ == "__main__":
    cmd, d = sys.argv[1], sys.argv[2]
    if cmd == "check":
        check(d)
    elif cmd == "parts":
        parts(d)
    elif cmd == "sheets":
        sheets(d, int(sys.argv[sys.argv.index("--flagged") + 1]) if "--flagged" in sys.argv else 0)
