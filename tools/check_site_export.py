"""Export checks for a modelled site (WORKFLOW G6/G7; CORRECTIONS-LOG 11, 12, 55, 80):

    python3 tools/check_site_export.py assets/sites/front-garden-model

FAILS (exit 1) when
- site.json is older than model.glb or model_q.glb (collision not regenerated with the model: log 80),
- an obstacle is malformed (box needs x z hw hd [rot]; circle x z r; polygon >= 3 pts),
- a GLB material has no texture, no vertex colours and a near-white base colour (an image lost on export: log 11, 12),
- a textured material is used by a primitive with no TEXCOORD_0 (texCoord -1: the texture cannot show: log 55),
- a GLB image is missing or empty.
Prints the material/texture counts so the audit can quote them."""
import json, os, struct, sys

def glb_json(path):
    with open(path, "rb") as f:
        magic, ver, length = struct.unpack("<III", f.read(12))
        assert magic == 0x46546C67, "not a GLB"
        clen, ctype = struct.unpack("<II", f.read(8)); J = json.loads(f.read(clen))
        blen = 0
        if f.tell() < length:
            blen, btype = struct.unpack("<II", f.read(8))
    return J, blen

def check_glb(path):
    J, blen = glb_json(path); errs = []
    mats = J.get("materials", []); tex = J.get("textures", []); imgs = J.get("images", []); views = J.get("bufferViews", [])
    textured = set(); vcol = set()
    for mesh in J.get("meshes", []):
        for p in mesh["primitives"]:
            attrs = set(p.get("attributes", {})) | set(p.get("extensions", {}).get("KHR_draco_mesh_compression", {}).get("attributes", {}))
            if "COLOR_0" in attrs: vcol.add(p.get("material"))
    for i, m in enumerate(mats):
        pbr = m.get("pbrMetallicRoughness", {})
        if "baseColorTexture" in pbr:
            textured.add(i); t = pbr["baseColorTexture"]["index"]
            if t >= len(tex): errs.append(f"{m.get('name')}: texture {t} missing")
            else:
                src = tex[t].get("source", tex[t].get("extensions", {}).get("EXT_texture_webp", {}).get("source"))
                if src is None or src >= len(imgs): errs.append(f"{m.get('name')}: image missing")
                else:
                    bv = imgs[src].get("bufferView")
                    if bv is None or views[bv]["byteLength"] < 64: errs.append(f"{m.get('name')}: image empty")
        else:
            c = pbr.get("baseColorFactor", [1, 1, 1, 1])
            if min(c[:3]) > 0.92 and not m.get("extensions") and i not in vcol: errs.append(f"{m.get('name')}: untextured near-white {c[:3]} (lost image?)")
    for mesh in J.get("meshes", []):
        for p in mesh["primitives"]:
            mi = p.get("material")
            attrs = set(p.get("attributes", {})) | set(p.get("extensions", {}).get("KHR_draco_mesh_compression", {}).get("attributes", {}))
            if mi in textured and "TEXCOORD_0" not in attrs: errs.append(f"mesh {mesh.get('name')}: material {mats[mi].get('name')} textured but no TEXCOORD_0")
    return errs, len(mats), len(textured), len(imgs), os.path.getsize(path)

def check_obstacles(meta):
    errs = []
    for k, o in enumerate(meta.get("obstacles", [])):
        if "pts" in o:
            if len(o["pts"]) < 3 or any(len(p) != 2 for p in o["pts"]): errs.append(f"obstacle {k} polygon malformed")
        elif "r" in o:
            if not all(isinstance(o.get(f), (int, float)) for f in ("x", "z", "r")): errs.append(f"obstacle {k} circle malformed")
        elif not all(isinstance(o.get(f), (int, float)) for f in ("x", "z", "hw", "hd")): errs.append(f"obstacle {k} box malformed")
    return errs

if __name__ == "__main__":
    d = sys.argv[1]; errs = []
    meta = json.load(open(os.path.join(d, "site.json")))
    for g in [meta.get("glb", "model.glb"), meta.get("glbQuest")]:
        if not g: continue
        p = os.path.join(d, g)
        if os.path.getmtime(os.path.join(d, "site.json")) < os.path.getmtime(p): errs.append(f"site.json is older than {g}: regenerate collision with the model")
        e, nm, nt, ni, sz = check_glb(p); errs += [f"{g}: {x}" for x in e]
        print(f"{g}: {sz / 1e6:.1f} MB, {nm} materials, {nt} textured, {ni} images, {len(e)} problems")
    eo = check_obstacles(meta); errs += eo
    print(f"site.json: {len(meta.get('obstacles', []))} obstacles ({sum('pts' in o for o in meta['obstacles'])} polygons, "
          f"{sum('r' in o for o in meta['obstacles'])} circles), start {meta.get('start')}, generated {meta.get('generated', {}).get('at')}")
    for e in errs: print("FAIL", e)
    print("EXPORT CHECK", "PASS" if not errs else f"FAIL ({len(errs)})")
    sys.exit(1 if errs else 0)
