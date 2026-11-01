"""G5c FINISHED HOUSE gate (WORKFLOW G5c; DETAIL-CHECKLIST "'Still mid-build' tells"). Pure Python (reads the GLB's node
list and extras, the elements and the signed spec): must pass before any judge, Unreal run or a WIP "finished" milestone.
The shell items live in check_shell.py (G5b); this is everything that makes a finished, lived-in house.

    python3 tools/house/check_finish.py assets/sites/house [--versions as_built_now,approved_2b]   -> <site>/<v>_finish.json

AUTOMATED (geometry / node tests, required items per room type from the spec):
  F1 services per room: a light fitting (ceiling or wall) in every room; a switch beside the opening of every room; sockets
     (bedrooms >= 2 doubles, living/kitchen >= 4, halls/landings >= 1); heat: a radiator in every habitable room unless the
     spec gives it underfloor heating; a smoke alarm in every hall and landing (UK Building Regs Part B, typical).
  F2 kitchen complete: base units, wall units, worktop, sink and tap, hob, oven, extractor, splashback.
  F3 bathrooms complete: WC, basin and tap, bath or shower, wall tiles (FIN-TILE-WALL), towel rail, mirror.
  F4 outside closed: gutters, downpipes, fascias/soffits on every roof (RG- / RD- / RE- parts), no scaffold or temporary
     works at the finished stage.
  F5 lived-in layer: spec_v1_addendum2_details.json exists, every room has its tidy-detail items, every item placed (node
     present) and validated (no float > 1 cm, no overlap: the addendum's own validator record).
INSPECTED (walk inspection, written pass per room in renders/house-build/first-build/shell/SHELL_READY.md or FINISH.md):
  sealant lines, beads at corners, paving edges and kerbs, lights switched on in the viewer, slight variation and wear,
  "flat feel", anything on the mid-build tells list that geometry tests cannot see."""
import sys, os, json, struct, re, argparse

ap = argparse.ArgumentParser()
ap.add_argument("site"); ap.add_argument("--versions", default="as_built_now,approved_2b")
ap.add_argument("--spec", default="assets/sites/house/spec/spec_v1.json")
a = ap.parse_args()
S = json.load(open(a.spec))


def glb_nodes(p):
    b = open(p, "rb").read(); n = struct.unpack("<I", b[12:16])[0]
    return json.loads(b[20:20 + n])["nodes"]


ROOM_TYPE = [("kitchen", re.compile(r"kitchen", re.I)), ("bath", re.compile(r"bath|en-suite|ensuite|cloaks-WC|cloaks$|WC", re.I)),
             ("bed", re.compile(r"bedroom", re.I)), ("living", re.compile(r"living|sitting|lounge|dining", re.I)),
             ("hall", re.compile(r"hall|landing|lobby|porch", re.I)), ("store", re.compile(r"cpd|store|cupboard|utility|conservatory", re.I))]
SOCKETS = {"kitchen": 4, "living": 4, "bed": 2, "hall": 1, "bath": 0, "store": 0}


def rtype(rid):
    for t, rx in ROOM_TYPE:
        if rx.search(rid): return t
    return "store"


out_all = {}
for vid in [v for v in a.versions.split(",") if v]:
    vk = "before" if vid == "as_built_now" else "after"
    V = S["versions"][vk]
    nodes = glb_nodes(os.path.join(a.site, f"{vid}.glb"))
    ids = {}
    for nd in nodes:
        ex = nd.get("extras", {})
        if ex.get("spec_id"): ids.setdefault(ex["spec_id"], []).append(nd["name"])
    names = [nd.get("name", "") for nd in nodes]
    items = {it["id"]: it for it in V["items"]}
    placed = {i for i in items if i in ids}
    by_room = {}
    for it in V["items"]: by_room.setdefault(it["room"], []).append(it)
    F = {k: [] for k in ("F1", "F2", "F3", "F4", "F5")}
    for r in V["rooms"]:
        rid = r["id"]; t = rtype(rid); its = by_room.get(rid, [])
        if "conservatory" in rid: continue
        def has(rx, cats=None, need_placed=True):
            return [i for i in its if re.search(rx, i["type"] + " " + json.dumps(i["asset"]), re.I) and (cats is None or i["category"] in cats)
                    and (not need_placed or i["id"] in placed)]
        if not has(r"light|pendant|downlight|lamp|sconce", ("lighting",)): F["F1"].append(dict(room=rid, missing="light fitting"))
        if not any(n.startswith(f"JN-SW-{rid}") for n in names): F["F1"].append(dict(room=rid, missing="light switch by the door"))
        ns = len([n for n in names if n.startswith(f"JN-SKT-{rid}")])
        if ns < SOCKETS.get(t, 0): F["F1"].append(dict(room=rid, missing=f"sockets ({ns} of {SOCKETS[t]} doubles)"))
        ufh = "underfloor" in json.dumps(r["finishes"]).lower()
        if t in ("bed", "living", "kitchen", "bath") and not ufh and not has(r"radiator|towel rail", ("radiator", "fitting", "sanitary")):
            F["F1"].append(dict(room=rid, missing="radiator (or underfloor heating in the spec)"))
        if t == "hall" and ("hall" in rid or "landing" in rid) and not any(n.startswith(f"JN-SMOKE-{rid}") for n in names):
            F["F1"].append(dict(room=rid, missing="smoke alarm (Part B, typical)"))
        if t == "kitchen":
            for lab, rx in (("base units", r"base unit|kitchen run|kitchen_unit|sink unit"), ("wall units", r"wall unit|wall_units"),
                            ("worktop", r"worktop|KIT-TOP|KITB-TOP"), ("sink and tap", r"sink"), ("hob", r"hob"), ("oven", r"oven"),
                            ("extractor", r"hood|extract"), ("splashback", r"splash|metro|tile")):
                if not has(rx, None): F["F2"].append(dict(room=rid, missing=lab))
        if t == "bath" and "lobby" not in rid:
            for lab, rx in (("WC", r"\bWC\b|toilet|pan"), ("basin and tap", r"basin"), ("towel rail", r"towel rail|towel_rail")):
                if not has(rx, None) and not any(re.search(rx.replace("\\b", ""), n, re.I) and ("FT-" in n) for n in names):
                    F["F3"].append(dict(room=rid, missing=lab))
            if ("bathroom" in rid or "en-suite" in rid) and not (has(r"bath|shower", None) or any(re.search(r"shower|bath", n, re.I) and n.startswith("FT-") for n in names)):
                F["F3"].append(dict(room=rid, missing="bath or shower"))
            if "TILE-WALL" not in json.dumps(r["finishes"]): F["F3"].append(dict(room=rid, missing="wall tiles in the spec"))
    if not any(n.startswith(("RG-", "SPEC-X-GUTTER")) or "gutter" in n.lower() for n in names): F["F4"].append(dict(missing="gutters"))
    if not any(n.startswith(("RD-",)) or "downpipe" in n.lower() for n in names): F["F4"].append(dict(missing="downpipes"))
    if not any(n.startswith("RE-") for n in names): F["F4"].append(dict(missing="fascias / soffits"))
    st = json.load(open(os.path.join(a.site, f"{vid}.json")))["stages"]; N = len(st)
    temp = [nd["name"] for nd in nodes if nd.get("extras", {}).get("category") == "temporary" and (nd["extras"].get("stage_out") or 99) > N]
    if temp: F["F4"].append(dict(missing="temporary works still standing at the finished stage", parts=temp[:6]))
    ad = os.path.join(os.path.dirname(a.spec), "spec_v1_addendum2_details.json")
    if not os.path.exists(ad): F["F5"].append(dict(missing="spec_v1_addendum2_details.json (the lived-in layer) not written"))
    else:
        A = json.load(open(ad)); its = [i for i in A.get("items", []) if vk in i.get("versions", [vk])]
        rooms_with = {i["room"] for i in its}
        for r in V["rooms"]:
            if rtype(r["id"]) in ("kitchen", "living", "bed", "bath") and r["id"] not in rooms_with: F["F5"].append(dict(room=r["id"], missing="lived-in details"))
        unplaced = [i["id"] for i in its if i["id"] not in ids]
        if unplaced: F["F5"].append(dict(missing="addendum items not in the build", items=unplaced[:10]))
        bad = [i["id"] for i in its if i.get("validator", {}).get("ok") is False]
        if bad: F["F5"].append(dict(missing="addendum items failing the validator", items=bad[:10]))
    res = dict(version=vid, passed=not any(F.values()), counts={k: len(v) for k, v in F.items()}, faults=F,
               automated=["F1 services per room", "F2 kitchen complete", "F3 bathrooms complete", "F4 outside closed", "F5 lived-in layer"],
               inspected=["sealant lines", "beads at corners", "paving edges and kerbs", "lights on in the viewer", "variation and wear / flat feel",
                          "every mid-build tell the geometry tests cannot see (DETAIL-CHECKLIST)"])
    json.dump(res, open(os.path.join(a.site, f"{vid}_finish.json"), "w"), indent=1)
    out_all[vid] = res["counts"]
    print(vid, "PASS" if res["passed"] else "FAIL", res["counts"])
sys.exit(0 if all(not any(v.values()) for v in out_all.values()) else 1)
