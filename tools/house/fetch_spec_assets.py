#!/usr/bin/env python3
"""Fetch every free library asset a signed spec names (WORKFLOW G2b): Poly Haven models (glTF, 1k) for items with
asset.source "polyhaven", and Poly Haven texture sets (1k JPG: diffuse, normal GL, roughness) for the finishes and
exterior materials. CC0 only; each fetch is listed in <root>/fetched.json for CREDITS.md.

    python3 tools/house/fetch_spec_assets.py assets/sites/house/spec/spec_v1.json [--res 1k]

Models land in master/polyhaven/<id>/, texture sets in master/polyhaven/tex/<id>/ (skipped when already there).
Extra ids not named by the spec (a furnishing plan's library picks): --models id,id --textures id,id (spec "-" to skip the spec).
--library <asset-library dir> also mirrors each fetched set into <library>/polyhaven/models|textures/<id>/ with asset.json."""
import json, os, sys, argparse, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("spec"); ap.add_argument("--res", default="1k")
ap.add_argument("--models", default=""); ap.add_argument("--textures", default=""); ap.add_argument("--library", default="")
ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "master", "polyhaven"))
a = ap.parse_args()
UA = {"User-Agent": "garden-studio-vr/1.0 (Poly Haven CC0 fetch)"}
S = json.load(open(a.spec)) if a.spec != "-" else {"versions": {}, "finishes": []}


def fetch(url): return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60)


def get(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0: return 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with fetch(url) as r, open(dest + ".part", "wb") as f: f.write(r.read())
    os.replace(dest + ".part", dest)
    return os.path.getsize(dest)


models, texsets = set(), set()
for v in S["versions"].values():
    for it in v["items"]:
        if it["asset"].get("source") == "polyhaven": models.add(it["asset"]["id"])
for f in S["finishes"]:
    if f["asset"].get("source") == "polyhaven": texsets.add(f["asset"]["id"])
    fb = f["asset"].get("fallback_texture", "")
    if fb.startswith("polyhaven "): texsets.add(fb.split()[1])
models |= {x for x in a.models.split(",") if x}; texsets |= {x for x in a.textures.split(",") if x}
log = {}
for m in sorted(models):
    folder = os.path.join(a.root, m)
    files = json.load(fetch(f"https://api.polyhaven.com/files/{m}"))
    if "gltf" not in files and "blend" in files:          # some sets (decorative_book_set_01) come as .blend only
        e = files["blend"][a.res]["blend"]
        n = get(e["url"], os.path.join(folder, f"{m}.blend"))
        for rel, f in e.get("include", {}).items(): n += get(f["url"], os.path.join(folder, rel))
        log[m] = dict(kind="model", url=f"https://polyhaven.com/a/{m}", licence="CC0", res=a.res, bytes=n, format="blend")
        print(f"model {m}: {n // 1024} KB new (.blend)"); continue
    e = files["gltf"][a.res]["gltf"]
    n = get(e["url"], os.path.join(folder, f"{m}.gltf"))
    for rel, f in e.get("include", {}).items(): n += get(f["url"], os.path.join(folder, rel))
    log[m] = dict(kind="model", url=f"https://polyhaven.com/a/{m}", licence="CC0", res=a.res, bytes=n)
    print(f"model {m}: {n // 1024} KB new")
for t in sorted(texsets):
    folder = os.path.join(a.root, "tex", t)
    files = json.load(fetch(f"https://api.polyhaven.com/files/{t}"))
    n = 0
    for key in ("Diffuse", "nor_gl", "Rough"):
        if key not in files: continue
        e = files[key][a.res].get("jpg") or files[key][a.res].get("png")
        n += get(e["url"], os.path.join(folder, os.path.basename(e["url"])))
    log[t] = dict(kind="texture", url=f"https://polyhaven.com/a/{t}", licence="CC0", res=a.res, bytes=n)
    print(f"texture {t}: {n // 1024} KB new")
if a.library:                                             # mirror into the studio asset library (README: every build looks there first)
    import shutil
    for k, v in log.items():
        src = os.path.join(a.root, k) if v["kind"] == "model" else os.path.join(a.root, "tex", k)
        dst = os.path.join(a.library, "polyhaven", "models" if v["kind"] == "model" else "textures", k)
        if not os.path.isdir(dst): shutil.copytree(src, dst)
        json.dump(dict(id=k, source="Poly Haven", page=v["url"], licence="CC0 1.0", web_ok=True, stream_ok=True, render_ok=True, res=v["res"]),
                  open(os.path.join(dst, "asset.json"), "w"), indent=1)
lp = os.path.join(a.root, "fetched.json")
old = json.load(open(lp)) if os.path.exists(lp) else {}
old.update(log); json.dump(old, open(lp, "w"), indent=1)
print(len(models), "models,", len(texsets), "texture sets")
