"""Fetch free scanned assets (CC0 only) into the studio's shared asset library, outside the repo, reusable for every client.
    ~/splat/bin/python tools/unreal/fetch_assets.py tools/unreal/sites/front-garden.json [--lib ~/Desktop/garden-scans/asset-library]

Reads the site spec's "library" list ({"src": "polyhaven", "id": ..., "kind": "texture|model|hdri", "maps": [...]}) and downloads
each asset once to <lib>/<src>/<kind>s/<id>/ (2k JPG maps; DirectX normals for Unreal; ARM = AO/rough/metal packed like Unreal's
ORM). Writes <lib>/<src>/<kind>s/<id>/asset.json (source page, file URLs, licence, real-world size, mean linear albedo) and
<lib>/LIBRARY.md, the human list with every source URL and licence (CREDITS.md points at it). Poly Haven's API asks for a
User-Agent. Nothing here logs in or costs money: paid/Fab assets are recommendations only (Jack, 1 Nov)."""
import json, os, sys, time, urllib.request, concurrent.futures as cf

UA = {"User-Agent": "GardenStudio/1.0 (asset library)"}
SKIP = {"blend", "fbx", "gltf", "usd", "mtlx"}


def get_json(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())


def download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0: return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read()
    open(path + ".part", "wb").write(data); os.replace(path + ".part", path); return path


def mean_albedo(path):
    """mean linear albedo of a diffuse map (for colour-matching tints against the client's photos)"""
    try:
        import numpy as np
        from PIL import Image
        a = np.asarray(Image.open(path).convert("RGB").resize((256, 256)), np.float32) / 255
        lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
        return [round(float(v), 4) for v in lin.reshape(-1, 3).mean(0)]
    except Exception as e:
        return None


def fetch_polyhaven(item, lib, res="2k"):
    aid, kind = item["id"], item["kind"]
    dest = os.path.join(lib, "polyhaven", kind + "s", aid)
    info = get_json(f"https://api.polyhaven.com/info/{aid}")
    files = get_json(f"https://api.polyhaven.com/files/{aid}")
    got, jobs = {}, []
    if kind == "hdri":
        r = item.get("res", "2k"); f = files["hdri"][r]["exr"]
        jobs.append((f["url"], os.path.join(dest, f"{aid}_{r}.exr"), "hdri"))
    else:
        want = item.get("maps") or [k for k in files if k not in SKIP and k not in ("nor_gl", "AO", "Rough")]
        for k in want:
            if k not in files: print(f"  {aid}: no map {k}"); continue
            fmt = "png" if k.lower().endswith(("disp", "displacement")) and item.get("disp_png") else "jpg"
            f = files[k][res][fmt]; jobs.append((f["url"], os.path.join(dest, os.path.basename(f["url"])), k))
        if kind == "model":                                    # geometry: the glTF and its .bin (textures fetched above)
            g = files["gltf"][res]["gltf"]
            jobs.append((g["url"], os.path.join(dest, f"{aid}.gltf"), "gltf"))
            for rel, inc in g["include"].items():
                if rel.endswith(".bin"): jobs.append((inc["url"], os.path.join(dest, rel), "bin"))
    with cf.ThreadPoolExecutor(6) as ex:
        for (url, path, k), _ in zip(jobs, ex.map(lambda j: download(j[0], j[1]), jobs)): got[k] = {"file": os.path.basename(path), "url": url}
    diff = next((v["file"] for k, v in got.items() if k.lower() in ("diffuse", "diff")), None)
    meta = {"id": aid, "source": "Poly Haven", "page": f"https://polyhaven.com/a/{aid}", "licence": "CC0 1.0",
            "authors": list((info.get("authors") or {}).keys()), "kind": kind, "name": info.get("name"),
            "dimensions_mm": info.get("dimensions"), "files": got, "fetched": time.strftime("%Y-%m-%d"),
            "mean_albedo_linear": mean_albedo(os.path.join(dest, diff)) if diff else None}
    json.dump(meta, open(os.path.join(dest, "asset.json"), "w"), indent=1)
    return meta


def fetch_ambientcg(item, lib, res="2K"):
    aid = item["id"]; dest = os.path.join(lib, "ambientcg", "textures", aid)
    url = f"https://ambientcg.com/get?file={aid}_{res}-JPG.zip"
    z = download(url, os.path.join(dest, f"{aid}_{res}-JPG.zip"))
    import zipfile
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            if n.endswith((".jpg", ".png")) and "/" not in n: zf.extract(n, dest)
    files = {n.split("_")[-1].split(".")[0]: {"file": n, "url": url} for n in os.listdir(dest) if n.endswith((".jpg", ".png"))}
    diff = next((v["file"] for k, v in files.items() if k == "Color"), None)
    meta = {"id": aid, "source": "ambientCG", "page": f"https://ambientcg.com/a/{aid}", "licence": "CC0 1.0", "kind": "texture",
            "files": files, "fetched": time.strftime("%Y-%m-%d"), "mean_albedo_linear": mean_albedo(os.path.join(dest, diff)) if diff else None}
    json.dump(meta, open(os.path.join(dest, "asset.json"), "w"), indent=1)
    return meta


def write_index(lib):
    rows = []
    for src in sorted(os.listdir(lib)):
        for kind in sorted(os.listdir(os.path.join(lib, src))) if os.path.isdir(os.path.join(lib, src)) else []:
            p = os.path.join(lib, src, kind)
            for aid in sorted(os.listdir(p)) if os.path.isdir(p) else []:
                m = os.path.join(p, aid, "asset.json")
                if os.path.exists(m):
                    a = json.load(open(m)); rows.append(f"| {a['id']} | {a['source']} {a['kind']} | {a['page']} | {a['licence']} | {a.get('fetched', '')} |")
    open(os.path.join(lib, "LIBRARY.md"), "w").write(
        "# Studio asset library (free, CC0 only)\n\nFetched by tools/unreal/fetch_assets.py; reused by every client build. "
        "CC0 = public domain, safe for commercial client work, no attribution required (credited anyway).\n\n"
        "| Asset | Source | Page | Licence | Fetched |\n|---|---|---|---|---|\n" + "\n".join(rows) + "\n")


def main():
    spec = json.load(open(sys.argv[1]))
    lib = os.path.expanduser(sys.argv[sys.argv.index("--lib") + 1] if "--lib" in sys.argv else "~/Desktop/garden-scans/asset-library")
    for item in spec["library"]:
        t = time.time()
        try:
            m = (fetch_ambientcg if item.get("src") == "ambientcg" else fetch_polyhaven)(item, lib)
            print(f"{item['id']:28s} {item['kind']:8s} {len(m['files'])} files  albedo {m.get('mean_albedo_linear')}  {time.time() - t:.0f}s")
        except Exception as e:
            print(f"{item['id']:28s} FAILED {e}")
    write_index(lib); print("index:", os.path.join(lib, "LIBRARY.md"))


if __name__ == "__main__":
    main()
