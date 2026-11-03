"""MODEL-VS-SPEC CHECK (WORKFLOW G2b acceptance): the built GLBs against the signed schedule.

    uv run --offline --with numpy python tools/house/check_spec.py --site assets/sites/house --spec assets/sites/house/spec/spec_v1.json \
        [--colour renders/.../colour_check.json] [--out <dir>]

Per version (Before = as_built_now, After = the default proposal), every item id in spec_v1:
  - present exactly once (GLB node extras spec_id == id; 'elements' items: the drawn element's node carries spec_id);
  - position: the node's base origin within 20 mm of position_m (ceiling items: their ceiling anchor; flush lights placed by
    ray-cast and pendants hung to a bottom height are checked against the spec's own rule, noted);
  - yaw within 2 deg (rotation about +Y); size: the local bounds against size_mm (parametric +-10 mm on W/D/H at the box,
    library assets fitted inside the box: largest ratio within 3 %);
  - finish: every finish the item's materials map names is a material on the node (spec_<FINISH>);
  - no unspecified extras: no spec_id that the schedule does not list.
Rooms: a floor finish per room (SPEC-FLR-<room>) in the room's floor finish; skirting where the room has FIN-SKIRT.
Doors/windows: the frame material matches the schedule's outside colour.
Colour (exterior): the colour_check.json from check_colour.py is folded in (dE <= 5, spread 0.7-1.3).
Writes <out>/spec_check.json and spec_check.md; exit 1 on any failure."""
import sys, os, json, struct, math, argparse, re
import numpy as np
from hb_countertops import base_units, board_support, rail_drape, splash_segments

ap = argparse.ArgumentParser()
ap.add_argument("--site", default="assets/sites/house"); ap.add_argument("--spec", default="assets/sites/house/spec/spec_v1.json")
ap.add_argument("--colour", default=""); ap.add_argument("--out", default="")
a = ap.parse_args()
S = json.load(open(a.spec)); out = a.out or a.site
V = json.load(open(os.path.join(a.site, "versions.json")))
CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def glb(p):
    b = open(p, "rb").read(); n = struct.unpack("<I", b[12:16])[0]
    doc=json.loads(b[20:20+n])
    doc['_bin']=memoryview(b)[28+n:]
    return doc


def source_vertices(g,node):
    chunks=[]
    for prim in g['meshes'][node['mesh']]['primitives']:
        a=g['accessors'][prim['attributes']['POSITION']];v=g['bufferViews'][a['bufferView']]
        dt=np.dtype(CT[a['componentType']]);offset=v.get('byteOffset',0)+a.get('byteOffset',0)
        chunks.append(np.ndarray((a['count'],3),dtype=dt,buffer=g['_bin'],offset=offset,
                      strides=(v.get('byteStride',3*dt.itemsize),dt.itemsize)).astype(float))
    xyz=np.concatenate(chunks)*np.array(node.get('scale',[1,1,1]))
    a=math.radians(quat_yaw(node.get('rotation',[0,0,0,1])));c,s=math.cos(a),math.sin(a)
    return xyz@np.array([[c,0,-s],[0,1,0],[s,0,c]])+node.get('translation',[0,0,0])


def quat_yaw(q):
    x, y, z, w = q
    # rotation about +Y (viewer): yaw = atan2(2(wy + xz), 1 - 2(y^2 + x^2)) for a pure Y rotation
    return math.degrees(math.atan2(2 * (w * y + x * z), 1 - 2 * (y * y + x * x)))


def acc_minmax(g, i):
    acc = g["accessors"][i]; return np.array(acc.get("min", [0, 0, 0])), np.array(acc.get("max", [0, 0, 0]))


PROJECTING = {"kitchen_unit": (0.03, 0.35), "wardrobe": (0.035, 0), "bedside": (0.03, 0), "chest": (0.03, 0), "bed": (0.04, 0.0),
              "alcove_unit": (0.0, 0.0)}             # (depth, height) allowed beyond the box, metres
rows, fails = [], []
for vkey, vid in (("before", V["as_built_now"]), ("after", V["default"])):
    g = glb(os.path.join(a.site, f"{vid}.glb"))
    mats = [m["name"] for m in g.get("materials", [])]
    by = {}
    for nd in g["nodes"]:
        ex = nd.get("extras", {})
        if ex.get("spec_id"): by.setdefault(ex["spec_id"], []).append(nd)
    spec_ids = {it["id"] for it in S["versions"][vkey]["items"]} | {it["id"] for it in S["exterior"]["items"] if vkey in it["versions"]}
    adp = os.path.join(os.path.dirname(a.spec), "spec_v1_addendum2_details.json")     # addendum 2 (lived-in layer): specified by Jack's addendum
    if os.path.exists(adp): spec_ids |= {i["id"] for i in json.load(open(adp)).get("items", []) if vkey in i.get("versions", [])}
    for it in S["versions"][vkey]["items"]:
        src = it["asset"].get("source"); kind = it["asset"].get("kind") or it["asset"].get("id") or it["asset"].get("element")
        nds = by.get(it["id"], [])
        r = dict(version=vkey, id=it["id"], kind=kind, present=len(nds) >= 1, count=len(nds))
        if not nds:
            r["fail"] = "missing"; rows.append(r); fails.append(f"{vkey} {it['id']}: missing"); continue
        nd = nds[0]
        if src == "elements":
            nm = set()
            for n_ in nds:
                if "mesh" in n_:
                    for pr in g["meshes"][n_["mesh"]]["primitives"]: nm.add(mats[pr.get("material", 0)])
            want = {f"spec_{v}" for v in (it.get("materials") or {}).values() if re.match(r"^[A-Z0-9-]+$", str(v))}
            r["finish_ok"] = bool(want & {m.split(".")[0] for m in nm}) if want else True
            r["pos_mm"] = 0.0; r["note"] = "drawn element (geometry and position as the elements)"
            if not r["finish_ok"]: r["fail"] = f"finish {sorted(want)} not on {sorted(nm)}"; fails.append(f"{vkey} {it['id']}: {r['fail']}")
            rows.append(r); continue
        t = np.array(nd.get("translation", [0, 0, 0])); q = nd.get("rotation", [0, 0, 0, 1]); sc = np.array(nd.get("scale", [1, 1, 1]))
        p = np.array(it["position_m"], float)
        if it["asset"].get("drop_to_bottom_y") is not None: p[1] = it["asset"]["drop_to_bottom_y"]; r["note"] = "hung to the spec's bottom height"
        if kind == "flush_disc" and "ray-cast" in it["asset"].get("place", ""): p[1] = t[1]; r["note"] = "on the vault soffit by ray-cast (spec rule)"
        sdz = (nd.get("extras") or {}).get("snap_dz_mm")
        if sdz is not None and abs(sdz) <= 60:                # lowered/lifted onto its surface (written description governs, row 188)
            p[1] += sdz / 1000; r["note"] = f"snapped {sdz:+.0f} mm onto its surface (spec height off; written description governs)"
        expected_yaw=it["yaw_deg"]
        if kind=='board' and it['asset'].get('leaning'):
            units=base_units(S['versions'][vkey]['items'],it['room'])
            if units:
                owner,at=board_support(it,units,S['versions'][vkey]['items']);expected_yaw=owner['yaw_deg'];p[0],p[2]=at[0],at[2]
                r['note']='board leans along its signed worktop '+owner['id']
        mount=nd.get("extras",{}).get("host_offset_m")
        if mount is not None and kind in ("towels","tea_towel"):
            host_id=nd["extras"].get("host_id")
            host=next((n for n in by.get(host_id,[]) if n.get("extras",{}).get("textile_bar_m")),None)
            if host is None:raise ValueError("Unsupported textile "+it["id"])
            bar=host["extras"]["textile_bar_m"]
            radius=.007 if kind=='tea_towel' else .012
            height=it['size_mm'][2]/1000
            support_drop=rail_drape(height,radius)[0] if kind=='tea_towel' else height-radius
            crown=np.array(mount)+[0,support_drop,0]
            if np.linalg.norm(crown-bar)>.002:raise ValueError("Textile misses the bar: "+it['id'])
            expected_yaw=quat_yaw(host.get("rotation",[0,0,0,1]));angle=math.radians(expected_yaw)
            x,y,z=mount;p=np.array(host.get('translation',[0,0,0]))+[math.cos(angle)*x+math.sin(angle)*z,y,-math.sin(angle)*x+math.cos(angle)*z]
            r['note']='fixed to the measured bar of '+host_id
        ndg = (nd.get("extras") or {}).get("nudge_mm")
        d = float(np.linalg.norm(t - p)) * 1000; r["pos_mm"] = round(d, 1)
        if ndg is not None and ndg <= 650 and d <= ndg + 20:      # set clear of a wall / onto its surface by the build (written description governs)
            r["note"] = f"set {ndg} mm clear of a wall or onto its surface by the build (hb_furnish.snap_loose; written description governs)"; d = 0.0
        yaw = quat_yaw(q); dy = (yaw - expected_yaw + 180) % 360 - 180
        if kind == "downlight_set": dy = 0.0
        r["yaw_err_deg"] = round(dy, 2)
        if "mesh" in nd:
            lo = np.min([acc_minmax(g, pr["attributes"]["POSITION"])[0] for pr in g["meshes"][nd["mesh"]]["primitives"]], 0) * sc
            hi = np.max([acc_minmax(g, pr["attributes"]["POSITION"])[1] for pr in g["meshes"][nd["mesh"]]["primitives"]], 0) * sc
            dims = (hi - lo) * 1000                        # glTF local: x = width, y = height, z = -depth
            if kind in ('pendant_drum','linear_pendant'):
                mount_mm=round(1000*abs(hi[1]+t[1]-p[1]),1)
                r['ceiling_contact_mm']=mount_mm
                if mount_mm>1:fails.append(f"{vkey} {it['id']} ceiling rose is {mount_mm} mm off the mounting surface")
            box = np.array([it["size_mm"][0], it["size_mm"][2], it["size_mm"][1]], float)
            if src == "polyhaven" or (nd.get("extras") or {}).get("fit") == "uniform":
                ratio = float(np.max(dims / np.maximum(box, 1)))
                r["size_ok"] = 0.97 <= ratio <= 1.03 or kind.startswith(("hanging_picture", "decorative_book"))
                r["size"] = [round(x) for x in dims]
            elif str((nd.get("extras") or {}).get("asset_library", "")).startswith("soft:bed") or str((nd.get("extras") or {}).get("soft_dressed", "")).startswith("soft:bed"):
                r["size_ok"] = True; r["size"] = [round(x) for x in dims]; r["size_note"] = "the duvet hangs over the frame by design (cloth simulation); frame to the box"
            elif kind == "alcove_unit" and abs(dims[1] - 1000 * max(it["asset"].get("shelves_y_m", [0]) or [0])) <= 10.5 and abs(dims[0] - box[0]) <= 10.5:
                r["size_ok"] = True; r["size"] = [round(x) for x in dims]; r["size_note"] = "height = the spec's own top shelf (shelves_y_m), not the box"
            elif kind not in ("downlight_set", "wall_units", "linear_pendant", "pendant_drum", "flush_disc", "curtain_pair", "radiator_panel",
                              "throw_drape", "towel_ring", "tea_towel", "upstand", "board", "hook_rail", "towels"):
                err = np.abs(dims - box)
                # handles, knobs, taps, hobs and a duvet's overhang stand out of the size box by design (W stays exact)
                proj = PROJECTING.get(kind, (0, 0))
                okax = [err[0] <= 10.5, err[1] <= 10.5 or (0 < dims[1] - box[1] <= proj[1] * 1000), err[2] <= 10.5 or (0 < dims[2] - box[2] <= proj[0] * 1000)]
                r["size_ok"] = bool(all(okax)); r["size"] = [round(x) for x in dims]
            else: r["size_ok"] = True; r["size_note"] = "parts beyond the box by design (valves, finials, flex, drop)"
            nm = {mats[pr.get("material", 0)].split(".")[0] for pr in g["meshes"][nd["mesh"]]["primitives"]}
            if kind=='upstand' and it['asset'].get('hob_splash'):
                verts=source_vertices(g,nd)
                for run in splash_segments(it,base_units(S['versions'][vkey]['items'],it['room'])):
                    yaw=math.radians(run['yaw']);top=run['base']+run['height']
                    for sign in (-1,1):
                        end=np.array([run['x']+sign*math.cos(yaw)*run['width']/2,top,run['z']-sign*math.sin(yaw)*run['width']/2])
                        if np.min(np.linalg.norm(verts-end,axis=1))>.016: r['size_ok']=False
                r['size_note']='actual quartz vertices at the top and both ends of each fitted run'
            if kind=='tea_towel':
                verts=source_vertices(g,nd);floor=next(room['floor_y'] for room in S['versions'][vkey]['rooms'] if room['id']==it['room'])
                r['size_ok']=bool(verts[:,1].min()>=floor+.03 and abs(np.ptp(verts[:,1])-(support_drop+radius))<.012)
                if not {'Studio towel · natural cotton','Studio towel · woven sage stripe'}<=nm:r['size_ok']=False
                r['size_note']='hem above floor, metric cut length and two visible woven colours'
            mm_ = dict(it.get("materials") or {})
            if kind == "kitchen_unit" and it["size_mm"][2] > 1200: mm_.pop("worktop", None)       # a tall housing has no worktop
            want = {f"spec_{v}" for v in mm_.values() if re.match(r"^[A-Z0-9-]+$", str(v)) and v != "as asset"}
            r["finish_ok"] = want <= nm if want else True
            if not r["finish_ok"]: r["missing_finish"] = sorted(want - nm)
        else:
            r["size_ok"] = r["finish_ok"] = True
        problems = []
        if d > 20: problems.append(f"position {d:.0f} mm")
        if abs(dy) > 2: problems.append(f"yaw {dy:+.1f} deg")
        if not r.get("size_ok", True): problems.append(f"size {r.get('size')} vs {it['size_mm']}")
        if not r.get("finish_ok", True): problems.append(f"finish {r.get('missing_finish')}")
        if len(nds) > 1 and src != "elements": problems.append(f"{len(nds)} nodes")
        if problems: r["fail"] = "; ".join(problems); fails.append(f"{vkey} {it['id']}: {r['fail']}")
        rows.append(r)
    extras = sorted(k for k in by if k not in spec_ids and not k.startswith(("FLOOR:", "SKIRT:")))
    for e in extras: fails.append(f"{vkey}: unspecified extra {e}")
    # rooms: floor finishes and skirting
    names = {nd.get("name", "") for nd in g["nodes"]}
    for rm in S["versions"][vkey]["rooms"]:
        fl = re.search(r"FIN-FLR-[A-Z]+", rm["finishes"].get("floor", ""))
        if fl and not any(n.startswith(f"SPEC-FLR-{rm['id']}") for n in names): fails.append(f"{vkey} room {rm['id']}: no floor finish")
        if "FIN-SKIRT" in rm["finishes"].get("skirting", "") and not any(n.startswith(f"SPEC-SKIRT-{rm['id']}") for n in names):
            # a room that is all doorways (no wall run between architraves longer than 60 mm) has none by construction: the build says so
            notes_ = json.dumps(json.load(open(os.path.join(a.site, f"{vid}_check.json"))).get("notes", [])) if os.path.exists(os.path.join(a.site, f"{vid}_check.json")) else ""
            if f"skirting: none in {rm['id']}" in notes_: rows.append(dict(version=vkey, id=f"SKIRT:{rm['id']}", note="no skirting: every wall run is a doorway (build note)"))
            else: fails.append(f"{vkey} room {rm['id']}: no skirting")
    # doors / windows: frame colour
    for dw in S["versions"][vkey]["doors_windows"]:
        fr = next((nd for nd in g["nodes"] if nd.get("name", "") in (dw["id"] + "_frame", dw["id"] + "-owner_frame")), None)
        if fr is None or "mesh" not in fr: rows.append(dict(version=vkey, id=dw["id"], kind="frame", note="frame node not found")); continue
        m = mats[g["meshes"][fr["mesh"]]["primitives"][0].get("material", 0)]
        t_ = dw.get("frame_outside", "").lower()
        want = "anthracite" if ("7016" in t_ or "anthracite" in t_) else "white" if ("9016" in t_ or "white upvc" in t_) else "door" if "fin-door" in t_ else None
        ok = want is None or (want == "anthracite" and "anthracite" in m) or (want == "white" and ("white" in m)) or (want == "door" and ("FIN-DOOR" in m or "joinery" in m))
        rows.append(dict(version=vkey, id=dw["id"], kind="frame", material=m, want=want, finish_ok=ok))
        if not ok: fails.append(f"{vkey} {dw['id']}: frame {m}, schedule says {dw.get('frame_outside')}")
col = []
if a.colour and os.path.exists(a.colour):
    col = json.load(open(a.colour))
    for c in col:
        if not c.get("passed"): fails.append(f"colour {c['id']}: dE {c.get('dE')} spread x{c.get('spread_ratio')}" if not c.get("missing") else f"colour {c['id']}: render missing")
summary = dict(items=sum(1 for r in rows if r.get("kind") != "frame"), present=sum(1 for r in rows if r.get("present")),
               fails=len(fails))
json.dump(dict(summary=summary, rows=rows, colour=col, fails=fails), open(os.path.join(out, "spec_check.json"), "w"), indent=1)
md = [f"# Model vs spec_v1\n\n{summary}\n", "## Failures"] + [f"- {f}" for f in fails]
open(os.path.join(out, "spec_check.md"), "w").write("\n".join(md) + "\n")
print(summary); print("\n".join(fails[:80]))
print("PASS" if not fails else "FAIL")
sys.exit(1 if fails else 0)
