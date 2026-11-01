"""Remove textures that have no image source (a GLB exported with them crashes three's GLTFLoader with "Cannot read
properties of undefined (reading 'uri')") and drop every material slot that pointed at them; remaps texture indices.
    python3 tools/house/fix_glb_textures.py <file.glb> [...]   (rewrites in place; prints what it removed)"""
import json, struct, sys


def src(t):
    if "source" in t:
        return t["source"]
    for e in t.get("extensions", {}).values():
        if isinstance(e, dict) and "source" in e:
            return e["source"]
    return None


def fix(path):
    b = open(path, "rb").read()
    jlen = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + jlen])
    rest = b[20 + jlen:]
    imgs, tex = j.get("images", []), j.get("textures", [])
    bad = {i for i, t in enumerate(tex) if src(t) is None or not 0 <= src(t) < len(imgs)}
    if not bad:
        print(path, "ok"); return
    remap, keep = {}, []
    for i, t in enumerate(tex):
        if i not in bad:
            remap[i] = len(keep); keep.append(t)
    j["textures"] = keep
    dropped = 0

    def walk(o):
        nonlocal dropped
        if isinstance(o, dict):
            for k in list(o):
                v = o[k]
                if isinstance(v, dict) and "index" in v and k.lower().endswith("texture"):
                    if v["index"] in bad:
                        del o[k]; dropped += 1; continue
                    v["index"] = remap[v["index"]]
                walk(o[k])
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(j.get("materials", []))
    out = json.dumps(j, separators=(",", ":")).encode()
    out += b" " * ((4 - len(out) % 4) % 4)
    body = struct.pack("<I", len(out)) + b"JSON" + out + rest
    open(path, "wb").write(b[:8] + struct.pack("<I", 12 + len(body)) + body)
    print(path, f"removed {len(bad)} sourceless textures, {dropped} material slots")


for p in sys.argv[1:]:
    fix(p)
