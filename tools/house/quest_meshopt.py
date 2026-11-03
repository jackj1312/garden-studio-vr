"""Meshopt-compressed Quest GLBs (geometry ~halves; extras kept) beside each <id>_quest.glb, listed in versions.json as
`glb_quest_meshopt`. The viewer must register three's MeshoptDecoder (GLTFLoader.setMeshoptDecoder) before it uses
them; until then it keeps loading `glb_quest`. Positions are quantized (KHR_mesh_quantization: scale moves into the
node transforms), so a viewer reading raw attributes must apply the node matrix (it already does for instancing).

    python3 tools/house/quest_meshopt.py assets/sites/house [--gt ~/Documents/ChatGPT/.tools/gltf/node_modules/.bin/gltf-transform]
"""
import sys, os, json, subprocess, argparse

ap = argparse.ArgumentParser()
ap.add_argument("site")
ap.add_argument("--gt", default=os.path.expanduser("~/Documents/ChatGPT/.tools/gltf/node_modules/.bin/gltf-transform"))
a = ap.parse_args()
if not os.path.exists(a.gt):
    sys.exit(f"quest_meshopt: gltf-transform not found at {a.gt} (installing it is a download: ask Jack first)")
vp = os.path.join(a.site, "versions.json")
V = json.load(open(vp))
for v in V["versions"]:
    src = os.path.join(a.site, v.get("glb_quest") or "")
    if not v.get("glb_quest") or not os.path.exists(src): continue
    out = src.replace("_quest.glb", "_quest_mo.glb")
    subprocess.run([a.gt, "meshopt", src, out, "--level", "medium"], check=True, capture_output=True)
    v["glb_quest_meshopt"] = os.path.relpath(out,a.site)
    print(f"{v['id']}: {os.path.getsize(src) / 1e6:.1f} MB -> {os.path.getsize(out) / 1e6:.1f} MB")
json.dump(V, open(vp, "w"), indent=1)
