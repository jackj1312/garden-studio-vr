#!/usr/bin/env python3
"""Door leaves for the room planner (planner.html): hinge point and swing of every door leaf, per spec version.

Reads only the JSON chunk at the start of each version's GLB (the leaf nodes' extras: hinge, swing_deg, slide,
leaf_index, door_group; CONTRACT section 3) plus the spec's door_handing_overrides, and writes
assets/planner/<site>/doors.json. Read-only on everything else. The planner reads walls, openings, stairs and rooms
live from the elements file and the spec; a door missing here gets a derived swing in the browser (marked "derived").

    python3 tools/planner/make_doors.py --site house [--spec spec_v1.json]

Re-run after the house model is rebuilt (cheap: a few MB of JSON, no geometry).
"""
import argparse, json, os, struct
from datetime import datetime, timezone

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def glb_json(path):
    with open(path, "rb") as f:
        magic, _ver, _len = struct.unpack("<4sII", f.read(12))
        if magic != b"glTF":
            raise ValueError(f"{path}: not a GLB")
        n, kind = struct.unpack("<II", f.read(8))
        if kind != 0x4E4F534A:
            raise ValueError(f"{path}: first chunk is not JSON")
        return json.loads(f.read(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--spec", default=None, help="spec file name in assets/sites/<site>/spec/ (default: newest spec_v*.json)")
    a = ap.parse_args()
    site_dir = os.path.join(ROOT, "assets", "sites", a.site)
    spec_dir = os.path.join(site_dir, "spec")
    spec_name = a.spec or sorted(f for f in os.listdir(spec_dir) if f.startswith("spec_v") and f.endswith(".json"))[-1]
    spec = json.load(open(os.path.join(spec_dir, spec_name), encoding="utf-8"))
    versions = json.load(open(os.path.join(site_dir, "versions.json"), encoding="utf-8"))
    by_id = {v["id"]: v for v in versions["versions"]}
    out = {"site": a.site, "spec": spec_name, "made": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "made_by": "tools/planner/make_doors.py", "versions": {}}
    for key, sv in spec["versions"].items():
        vid = sv["elements"]
        glb = os.path.join(site_dir, by_id[vid]["glb"])
        j = glb_json(glb)
        leaves = {}
        for n in j.get("nodes", []):
            e = n.get("extras") or {}
            if e.get("part") == "leaf_glass" or str(n.get("name", "")).endswith("_glass"):
                continue
            if not isinstance(e.get("hinge"), list) or e.get("swing_deg") is None:
                continue
            el = e.get("element") or e.get("door_group")
            leaves.setdefault(el, []).append({
                "node": n.get("name"),
                "hinge": [round(e["hinge"][0], 4), round(e["hinge"][2], 4)],
                "y": round(e["hinge"][1], 4),
                "swing_deg": float(e["swing_deg"]),
                "slide": [round(e["slide"][0], 4), round(e["slide"][2], 4)] if isinstance(e.get("slide"), list) else None,
                "leaf_index": e.get("leaf_index", 0),
                "conf": e.get("swing_conf"),
                "source": "glb",
            })
        for fid, ov in (spec.get("door_handing_overrides", {}).get(key) or {}).items():
            for l in leaves.get(fid, []):
                l["swing_deg"] = float(ov["swing_deg"])
                l["source"] = "spec override: " + ov.get("why", "")[:160]
        for L in leaves.values():
            L.sort(key=lambda l: l["leaf_index"] or 0)
        out["versions"][key] = {"elements": vid, "glb": by_id[vid]["glb"], "leaves": leaves}
        print(f"{key} ({vid}): {len(leaves)} doors, {sum(len(v) for v in leaves.values())} leaves")
    dest = os.path.join(ROOT, "assets", "planner", a.site, "doors.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("->", os.path.relpath(dest, ROOT))


if __name__ == "__main__":
    main()
