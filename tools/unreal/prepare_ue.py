"""Stage one site for the Unreal rebuild (local, light): spec + export + library -> one upload bundle with scene.json.
    ~/splat/bin/python tools/unreal/prepare_ue.py tools/unreal/sites/front-garden.json out/unreal-ue/front-garden \
        [--lib ~/Desktop/garden-scans/asset-library] [--aligned ~/Desktop/garden-scans/front-garden/sfm2/aligned.json]

- materials: tint = client colour target / library mean albedo (linear; foliage means taken inside the alpha mask), texel scale
  from the real unit size (brick course 75 mm, paving course 160 mm, roof gauge 100 mm) by finding the course period in the
  scanned map itself (autocorrelation), so N whole courses repeat per tile;
- cameras: the client's solved photo poses (aligned.json) in Unreal space, upright (phone stills are stored sideways in the
  solve), filmback at the photo's own aspect, focal from the solved fx (CORRECTIONS-LOG 147: one matched camera first);
- sun: the filmed direction; axis convention Blender (x, y, z) m -> Unreal (100x, -100y, 100z) cm, checked in Unreal against
  the imported meshes' bounds before any render;
- bundle: <out>/bundle/ (FBX, textures, plant variants, scene.json) and <out>/bundle.tar for cloud_ue.py put."""
import json, math, os, shutil, sys, tarfile
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def arg(n, d=None): return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d
def s2l(c): c = np.asarray(c, float) / 255; return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_mean(img_path, alpha_path=None):
    a = np.asarray(Image.open(img_path).convert("RGB").resize((512, 512)), np.float32) / 255
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4).reshape(-1, 3)
    if alpha_path:
        m = np.asarray(Image.open(alpha_path).convert("L").resize((512, 512)), np.float32).ravel() / 255
        return (lin * m[:, None]).sum(0) / max(m.sum(), 1)
    return lin.mean(0)


def course_count(img_path, axis):
    """whole courses per texture repeat along axis ('v' rows, 'u' columns), from the luminance autocorrelation"""
    im = np.asarray(Image.open(img_path).convert("L"), np.float32)
    sig = im.mean(1) if axis == "v" else im.mean(0); s = sig - sig.mean(); n = len(s)
    f = np.fft.rfft(s, 2 * n); ac = np.fft.irfft(f * np.conj(f))[:n]; ac /= ac[0]; best = None
    for l in range(6, n // 2):
        if ac[l] > ac[l - 1] and ac[l] >= ac[l + 1] and ac[l] > 0.15:
            if best is None or ac[l] > ac[best] * 1.15: best = l
            if best is not None and l > best * 1.6: break
    return max(1, round(n / best)) if best else None


def find_map(asset_dir, meta, prefix, kinds):
    """file for one map of an asset ('' or 'leaves_' prefix; kinds = diff/nor_dx/arm/alpha/disp names)"""
    for k, v in meta["files"].items():
        kl = k.lower()
        for want in kinds:
            if (prefix and kl == prefix + want) or (not prefix and kl == want): return os.path.join(asset_dir, v["file"])
    return None


def camera(c, R, name):
    M = np.array(c["cam_from_world"]); B = R @ M[:, :3].T @ np.diag([1, -1, -1])
    right, up, fwd = B[:, 0], B[:, 1], -B[:, 2]
    w, h = c["camera"]["w"], c["camera"]["h"]; fx = c["camera"]["params"][0]
    k = 0
    while up[2] < 0.6 and k < 4:                                # rotate the frame 90 deg until it stands upright
        right, up = up.copy(), -right.copy(); w, h = h, w; k += 1   # (sensor stored sideways in the solve)
    P = np.array(c["centre"])
    ue = lambda v, s=1.0: [float(v[0] * s), float(-v[1] * s), float(v[2] * s)]
    return {"name": name, "pos_cm": ue(P, 100), "fwd": ue(fwd), "up": ue(up), "w": int(w), "h": int(h),
            "sensor_w_mm": 36.0, "sensor_h_mm": 36.0 * h / w, "focal_mm": float(fx * 36.0 / w), "hfov_deg": math.degrees(2 * math.atan(w / 2 / fx)),
            "rot90": k, "pos_m_blender": P.round(3).tolist()}


def main():
    spec_p, out = sys.argv[1], sys.argv[2]
    lib = os.path.expanduser(arg("--lib", "~/Desktop/garden-scans/asset-library"))
    aligned = os.path.expanduser(arg("--aligned", "~/Desktop/garden-scans/front-garden/sfm2/aligned.json"))
    spec = json.load(open(spec_p)); geo = json.load(open(os.path.join(out, "geometry.json")))
    B = os.path.join(out, "bundle"); shutil.rmtree(B, ignore_errors=True); os.makedirs(os.path.join(B, "tex")); os.makedirs(os.path.join(B, "mesh"))
    assets = {}
    for src in ("polyhaven", "ambientcg"):
        for kind in ("textures", "models", "hdris"):
            d = os.path.join(lib, src, kind)
            for aid in (os.listdir(d) if os.path.isdir(d) else []):
                if os.path.exists(os.path.join(d, aid, "asset.json")): assets[aid] = (os.path.join(d, aid), json.load(open(os.path.join(d, aid, "asset.json"))))

    def stage_tex(path):
        if not path: return None
        dst = os.path.join(B, "tex", os.path.basename(path))
        if not os.path.exists(dst): shutil.copy(path, dst)
        return os.path.basename(path)

    mats = {}
    for name, m in spec["materials"].items():
        e = {"type": m["type"]}
        if m["type"] in ("scan", "foliage"):
            aid, _, prefix = m["tex"].partition(":")
            d, meta = assets[aid]
            diff = find_map(d, meta, prefix, ["diffuse", "diff"]); nor = find_map(d, meta, prefix, ["nor_dx"]); arm = find_map(d, meta, prefix, ["arm"])
            alpha = find_map(d, meta, "", [m["alpha"].lower()]) if m.get("alpha") else None
            disp = find_map(d, meta, prefix, ["displacement", "disp"]) if m.get("displace_cm") else None
            e.update({"diff": stage_tex(diff), "nor": stage_tex(nor), "arm": stage_tex(arm), "alpha": stage_tex(alpha), "disp": stage_tex(disp),
                      "source": meta["page"], "licence": meta["licence"]})
            mean = lin_mean(diff, alpha)
            tint = (s2l(m["target_srgb"]) / np.maximum(mean, 1e-3)).clip(0.25, 4.0) if m.get("target_srgb") else np.ones(3)
            if m.get("desat"):                                     # tint applies after desaturation: compare with the grey mean
                g = float(mean @ [0.2126, 0.7152, 0.0722]); grey = mean * (1 - m["desat"]) + g * m["desat"]
                tint = (s2l(m["target_srgb"]) / np.maximum(grey, 1e-3)).clip(0.25, 6.0) if m.get("target_srgb") else np.ones(3)
            e["tint"] = [round(float(x), 4) for x in tint]
            if m.get("uv") == "model" or m["type"] == "foliage":
                e["tile"] = [1.0, 1.0]
            elif m.get("course_m"):
                cu, cv = m["course_m"]
                if cv: n = course_count(diff, "v"); tv = n * cv; e["courses"] = n
                if cu and not cv: n = course_count(diff, "u"); tv = n * cu; e["courses"] = n
                e["tile"] = [tv, tv]                                # square scans: the same scale both ways
            else:
                e["tile"] = m.get("tile_m", [1.0, 1.0])
            for k in ("rot90", "macro", "antitile", "displace_cm", "rough_mul", "desat"):
                if k in m: e[k] = m[k]
        else:
            for k in ("color", "rough", "metal", "noise", "opacity"):
                if k in m: e[k] = m[k]
            if "color" in e: e["color_lin"] = [round(float(x), 4) for x in s2l(e["color"])]
        mats[name] = e
    for msh in geo["meshes"]:
        shutil.copy(os.path.join(out, msh["fbx"]), os.path.join(B, "mesh", msh["fbx"]))
    # library models used by the instances (one FBX per variant)
    models = {}
    used = {i["model"] for i in geo["instances"]} | {t["model"] for t in spec.get("far_trees", [])}
    for mid in used:
        d, meta = assets[mid]; var = json.load(open(os.path.join(d, "ue", "variants.json")))
        for v in var.values(): shutil.copy(os.path.join(d, "ue", v["fbx"]), os.path.join(B, "mesh", v["fbx"]))
        models[mid] = var
    inst = list(geo["instances"])
    for t in spec.get("far_trees", []):
        inst.append({"of": "far_tree", "model": t["model"], "mi": None, "loc": [t["xy"][0], t["xy"][1], 0.0], "yaw": (hash(tuple(t["xy"])) % 360), "fit": {"h": t["h"]}})
    for ring in [r for r in (spec.get("far_ring"), spec.get("far_ring2")) if r]:                                                     # a background screen of trees all round, off the road
        import random as _r; R_ = _r.Random(5 + len(inst)); k = 0
        while k < ring["n"]:
            a = R_.uniform(0, 2 * math.pi); rr = R_.uniform(*ring["r"])
            x, y = ring["centre"][0] + rr * math.cos(a), ring["centre"][1] + rr * math.sin(a)
            if ring.get("skip_road_y") and ring["skip_road_y"][0] < y < ring["skip_road_y"][1]: continue
            if ring.get("skip_box") and ring["skip_box"][0] < x < ring["skip_box"][1] and ring["skip_box"][2] < y < ring["skip_box"][3]: continue
            inst.append({"of": "far_tree", "model": ring["model"], "mi": None, "loc": [x, y, 0.0], "yaw": R_.uniform(0, 360), "fit": {"h": R_.uniform(*ring["h"])}}); k += 1
    tr = spec.get("tree_rows")
    if tr:
        import random as _r; R2 = _r.Random(9)
        for x0, y0, x1, y1, sp, hh in tr["rows"]:
            L_ = math.hypot(x1 - x0, y1 - y0); n_ = max(2, int(L_ / sp))
            for i in range(n_ + 1):
                f = i / n_; inst.append({"of": "far_tree", "model": tr["model"], "mi": None, "yaw": R2.uniform(0, 360), "fit": {"h": R2.uniform(*hh)},
                                         "loc": [x0 + (x1 - x0) * f + R2.uniform(-1, 1), y0 + (y1 - y0) * f + R2.uniform(-1, 1), 0.0]})
    # instance material per slot for multi-slot models (far trees)
    model_slots = {"island_tree_01": {"island_tree_01": "MI_FarBark", "island_tree_01_branches": "MI_FarBark", "island_tree_01_leaves": "MI_FarTree"}}
    # cameras
    A = json.load(open(aligned)); R = np.array(A["R"])
    cams = [camera(A["cameras"][n], R, n.split(".")[0]) for n in spec["cameras"]["set"]]
    # a short walk film along the client's own walk (solved poses, smoothed): street -> path -> porch
    video = None
    if spec.get("video"):
        V = spec["video"]; names = [n for n in sorted(A["cameras"]) if n.startswith("walk_") and V["from"] <= int(n[5:9]) <= V["to"]]
        P_ = np.array([A["cameras"][n]["centre"] for n in names]); F_ = []
        for n in names:
            M = np.array(A["cameras"][n]["cam_from_world"]); F_.append(-(R @ M[:, :3].T @ np.diag([1, -1, -1]))[:, 2])
        F_ = np.array(F_)
        k = V.get("smooth", 5); ker = np.ones(k) / k
        sm = lambda a: np.array([np.convolve(np.pad(a[:, i], (k // 2, k // 2), mode="edge"), ker, mode="valid") for i in range(a.shape[1])]).T
        P_ = sm(P_); F_ = sm(F_); P_[:, 2] = V.get("eye_m", 1.6)
        d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P_[:, :2], axis=0), axis=1))]
        T = d / V.get("speed_mps", 1.1)
        keys = []
        for i in range(0, len(P_), max(1, V.get("step", 3))):
            f = F_[i] / np.linalg.norm(F_[i]); yaw = math.degrees(math.atan2(-f[1], f[0])); pitch = max(-8, min(2, 0.4 * math.degrees(math.asin(f[2]))))
            keys.append({"t": float(T[i]), "pos_cm": [float(P_[i, 0] * 100), float(-P_[i, 1] * 100), float(P_[i, 2] * 100)], "pitch": pitch, "yaw": yaw})
        for a_, b_ in zip(keys, keys[1:]):                       # unwrap yaw
            while b_["yaw"] - a_["yaw"] > 180: b_["yaw"] -= 360
            while b_["yaw"] - a_["yaw"] < -180: b_["yaw"] += 360
        video = {"keys": keys, "fps": V.get("fps", 24), "res": V.get("res", [1280, 720]), "hfov_deg": V.get("hfov_deg", 70), "seconds": float(T[-1])}
    sun = spec["sun"]; az, el = math.radians(sun["blender_az_deg"]), math.radians(sun["elevation_deg"])
    to_sun = np.array([-math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
    scene = {"site": spec["site"], "axis": "unreal = (100x, -100y, 100z) of the Blender plan metres", "materials": mats,
             "meshes": geo["meshes"], "instances": inst, "models": models, "model_slots": model_slots,
             "cameras": cams, "video": video, "check": [c.split(".")[0] for c in spec["cameras"]["check"]], "long_edge_px": spec["cameras"]["long_edge_px"],
             "sun": {"to_sun_ue": [float(to_sun[0]), float(-to_sun[1]), float(to_sun[2])], "elevation_deg": sun["elevation_deg"]}}
    json.dump(scene, open(os.path.join(B, "scene.json"), "w"), indent=1)
    with tarfile.open(os.path.join(out, "bundle.tar"), "w") as tf: tf.add(B, arcname="bundle")
    print("materials", len(mats), "meshes", len(geo["meshes"]), "instances", len(inst), "cameras", len(cams))
    for n, e in mats.items():
        if e["type"] in ("scan", "foliage"): print(f"  {n:16s} tile {e['tile']} tint {e['tint']} {('courses %d' % e['courses']) if 'courses' in e else ''}")
    for c in cams: print(f"  cam {c['name']}: {c['w']}x{c['h']} f={c['focal_mm']:.1f}mm hfov {c['hfov_deg']:.1f} rot90 {c['rot90']} at {c['pos_m_blender']}")
    print("bundle", os.path.getsize(os.path.join(out, "bundle.tar")) // (1 << 20), "MB")


if __name__ == "__main__":
    main()
