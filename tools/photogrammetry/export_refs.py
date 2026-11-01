"""Export a site's reference photos for the in-headset reference view (WORKFLOW G7).
Every solved photo and video frame becomes a ~1280 px JPEG plus its camera in VIEWER coordinates
(viewer x = plan x, viewer y = up, viewer z = -plan y), so the headset can rank photos by where Jack stands
and which way he looks. Unsolved close-ups are added too, without a position ("closeup").
    ~/splat/bin/python tools/photogrammetry/export_refs.py <aligned.json> <out_dir> --dirs d1,d2 [--closeups glob] [--every 2]"""
import argparse, glob, json, math, os, re
import numpy as np
from PIL import Image, ImageOps

ap = argparse.ArgumentParser(); ap.add_argument("aligned"); ap.add_argument("out")
ap.add_argument("--dirs", required=True); ap.add_argument("--closeups", default=""); ap.add_argument("--every", type=int, default=2)
ap.add_argument("--size", type=int, default=1280)
a = ap.parse_args()
d = json.load(open(a.aligned)); R = np.array(d["R"])
os.makedirs(os.path.join(a.out, "refs"), exist_ok=True)
dirs = a.dirs.split(",")
refs = []
names = sorted(d["cameras"])
walk = [n for n in names if n.startswith("walk_")][:: a.every]
for n in walk + [n for n in names if not n.startswith("walk_")]:
    c = d["cameras"][n]; M = np.array(c["cam_from_world"])
    Rc = M[:, :3]
    fwd = R @ (Rc.T @ np.array([0, 0, 1.0])); fwd /= np.linalg.norm(fwd)
    up = R @ (Rc.T @ np.array([0, -1.0, 0])); up /= np.linalg.norm(up)
    C = np.array(c["centre"])
    src = next((os.path.join(p, n) for p in dirs if os.path.exists(os.path.join(p, n))), None)
    if not src: continue
    im = Image.open(src); im = ImageOps.exif_transpose(im) if not n.startswith("walk_") else im
    im = im.convert("RGB")
    w0, h0 = c["camera"]["w"], c["camera"]["h"]
    # the solve saw the image unrotated; if the file is upright (EXIF), the picture's up is the camera's -x or +x
    rotated = (im.width > im.height) != (w0 > h0)
    f = c["camera"]["params"][0]
    hf = 2 * math.degrees(math.atan(w0 / 2 / f)); vf = 2 * math.degrees(math.atan(h0 / 2 / f))
    if rotated: hf, vf = vf, hf
    im.thumbnail((a.size, a.size), Image.LANCZOS)
    out = re.sub(r"\.\w+$", ".jpg", n); im.save(os.path.join(a.out, "refs", out), quality=82)
    date = n[:8] if n[:8].isdigit() else "20261031"
    refs.append({"file": "refs/" + out, "kind": "walk" if n.startswith("walk_") else "still", "date": date,
                 "pos": [round(C[0], 3), round(C[2], 3), round(-C[1], 3)],
                 "dir": [round(fwd[0], 4), round(fwd[2], 4), round(-fwd[1], 4)],
                 "hfov": round(hf, 1), "vfov": round(vf, 1), "w": im.width, "h": im.height})
for p in sorted(glob.glob(a.closeups)) if a.closeups else []:
    im = ImageOps.exif_transpose(Image.open(p)).convert("RGB"); im.thumbnail((a.size, a.size), Image.LANCZOS)
    out = "closeup_" + os.path.basename(p).rsplit(".", 1)[0] + ".jpg"; im.save(os.path.join(a.out, "refs", out), quality=82)
    refs.append({"file": "refs/" + out, "kind": "closeup", "date": "20261031", "pos": None, "dir": None, "w": im.width, "h": im.height})
json.dump({"coords": "viewer: x = plan x, y = up, z = -plan y; dir is the camera's forward unit vector",
           "refs": refs}, open(os.path.join(a.out, "refs.json"), "w"), indent=0)
print(len(refs), "refs;", sum(r["kind"] == "walk" for r in refs), "walk,", sum(r["kind"] == "still" for r in refs), "stills,",
      sum(r["kind"] == "closeup" for r in refs), "close-ups")
