#!/usr/bin/env python3
"""Download Poly Haven models (CC0) as glTF at a given resolution.

usage: python3 tools/fetch-polyhaven.py 2k island_tree_01 shrub_01 ...
Files land in master/polyhaven/<id>/ with their textures beside them.
"""
import json, os, sys, urllib.request

res = sys.argv[1]
root = os.path.join(os.path.dirname(__file__), "..", "master", "polyhaven")

UA = {"User-Agent": "garden-studio-vr/1.0 (Poly Haven CC0 fetch)"}   # the CDN refuses urllib's default

def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA))

def get(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with fetch(url) as r, open(dest, "wb") as f:
        f.write(r.read())

for asset in sys.argv[2:]:
    files = json.load(fetch(f"https://api.polyhaven.com/files/{asset}"))
    entry = files["gltf"][res]["gltf"]
    folder = os.path.join(root, asset)
    get(entry["url"], os.path.join(folder, f"{asset}.gltf"))
    for rel, f in entry.get("include", {}).items():
        get(f["url"], os.path.join(folder, rel))
    total = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(folder) for f in fs)
    print(f"{asset}: {total // 1024} KB")
