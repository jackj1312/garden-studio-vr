"""Export freshness and contract check for a house site (the house twin of tools/check_site_export.py).

    uv run --offline --with numpy python tools/house/check_house_export.py assets/sites/house

PASS needs: every file versions.json names exists; each version's sidecars (stages, elements, check) are no older than
its GLBs (written by the same run); every textured primitive has TEXCOORD_0; every door leaf has hinge + swing_deg;
the version's check json reads 0 unintended clashes and 0 cross-stage bearing faults; no version sets as_built_default;
and at every stage no two walkable ground surfaces (group "ground", the house's and the garden model's) lie over each other
in plan within 30 mm in height (stacked ground reads as stripes and z-fighting from the road: round 6); and every GLB
(full, quest, meshopt, setting) has a source on every texture and a uri/bufferView on every image and loads headless
through three's GLTFLoader (tools/house/glb_load_test.mjs, row 190). Needs numpy and node."""
import sys, os, json, struct, math, re, subprocess
import numpy as np

site = sys.argv[1]
FINISHED = "--finished" in sys.argv          # G5c gate blocking too (a WIP "finished" milestone, judges, Unreal)
fails, notes = [], []
V = json.load(open(os.path.join(site, "versions.json")))


if any(v.get("furnish_runtime") for v in V["versions"]):
    subprocess.run(["node",os.path.join(os.path.dirname(__file__),"runtime_assets.mjs"),"--check",site],check=True)

def glb_json(p):
    b = open(p, "rb").read(); n = struct.unpack("<I", b[12:16])[0]
    return json.loads(b[20:20 + n])


CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def glb_full(p):
    b = open(p, "rb").read(); n = struct.unpack("<I", b[12:16])[0]
    return json.loads(b[20:20 + n]), b[20 + n + 8:]


def accessor(g, binb, i):
    a = g["accessors"][i]; bv = g["bufferViews"][a["bufferView"]]
    nc = NC[a["type"]]; dt = np.dtype(CT[a["componentType"]])
    off = bv.get("byteOffset", 0) + a.get("byteOffset", 0); stride = bv.get("byteStride", nc * dt.itemsize)
    raw = np.frombuffer(binb, np.uint8, count=stride * (a["count"] - 1) + nc * dt.itemsize, offset=off)
    out = np.lib.stride_tricks.as_strided(raw, shape=(a["count"], nc * dt.itemsize), strides=(stride, 1)).copy().view(dt).reshape(a["count"], nc)
    if a.get("normalized"): out = out.astype(np.float32) / np.iinfo(dt).max
    return out.astype(np.float64)


def node_matrix(nd):
    if "matrix" in nd: return np.array(nd["matrix"]).reshape(4, 4).T
    t = np.array(nd.get("translation", [0, 0, 0])); q = nd.get("rotation", [0, 0, 0, 1]); sc = np.array(nd.get("scale", [1, 1, 1]))
    x, y, z, w = q
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4); M[:3, :3] = R * sc; M[:3, 3] = t
    return M


def ground_check(path, cell=0.25, box=(-30.0, -45.0, 45.0, 30.0), tol=0.03):
    """per stage: cells (plan, viewer x/z) where two ground nodes both have an upward face within tol of each other"""
    g, binb = glb_full(path)
    tops = []                                  # (name, si, so, {cell: z})
    x0, z0, x1, z1 = box; nx, nz = int((x1 - x0) / cell), int((z1 - z0) / cell)
    for nd in g["nodes"]:
        ex = nd.get("extras", {})
        if ex.get("group") != "ground" or "mesh" not in nd: continue
        if re.search(r"edging|kerb|border|upstand|step", nd.get("name", "")): continue      # laid units standing on a surface, not surfaces
        M = node_matrix(nd); cells = {}
        for pr in g["meshes"][nd["mesh"]]["primitives"]:
            P = accessor(g, binb, pr["attributes"]["POSITION"]); P = (np.c_[P, np.ones(len(P))] @ M.T)[:, :3]
            I = accessor(g, binb, pr["indices"]).astype(int).reshape(-1, 3) if "indices" in pr else np.arange(len(P)).reshape(-1, 3)
            A, B, C = P[I[:, 0]], P[I[:, 1]], P[I[:, 2]]
            N = np.cross(B - A, C - A); L = np.linalg.norm(N, axis=1) + 1e-12
            up = N[:, 1] / L > 0.7
            for a, b, c in zip(A[up], B[up], C[up]):
                lo = np.minimum(np.minimum(a, b), c); hi = np.maximum(np.maximum(a, b), c)
                i0, i1 = max(0, int((lo[0] - x0) / cell)), min(nx - 1, int((hi[0] - x0) / cell))
                k0, k1 = max(0, int((lo[2] - z0) / cell)), min(nz - 1, int((hi[2] - z0) / cell))
                if i1 < i0 or k1 < k0: continue
                ii, kk = np.meshgrid(np.arange(i0, i1 + 1), np.arange(k0, k1 + 1), indexing="ij")
                px = x0 + (ii + 0.5) * cell; pz = z0 + (kk + 0.5) * cell
                d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
                if abs(d) < 1e-12: continue
                l1 = ((b[2] - c[2]) * (px - c[0]) + (c[0] - b[0]) * (pz - c[2])) / d
                l2 = ((c[2] - a[2]) * (px - c[0]) + (a[0] - c[0]) * (pz - c[2])) / d
                l3 = 1 - l1 - l2
                m = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
                y = l1 * a[1] + l2 * b[1] + l3 * c[1]
                for i_, k_, y_ in zip(ii[m], kk[m], y[m]):
                    key = (int(i_), int(k_))
                    cells[key] = max(cells.get(key, -1e9), float(y_))
        tops.append((nd.get("name", "?"), int(ex.get("stage_in", 1)), int(ex.get("stage_out") or 99), cells))
    N = max([t[1] for t in tops] + [1])
    bad = {}
    for s_ in range(1, N + 1):
        live = [t for t in tops if t[1] <= s_ < t[2]]
        seen = {}
        for name, si, so, cells in live:
            for key, y in cells.items(): seen.setdefault(key, []).append((y, name))
        for key, lst in seen.items():
            if len(lst) < 2: continue
            lst.sort()
            for (ya, na), (yb, nb) in zip(lst, lst[1:]):
                if yb - ya < tol and na != nb:
                    bad.setdefault(s_, {}).setdefault(tuple(sorted((na, nb))), 0); bad[s_][tuple(sorted((na, nb)))] += 1
    return bad


for v in V["versions"]:
    if v.get("as_built_default"): fails.append(f"{v['id']}: as_built_default set")
    files = {k: os.path.join(site, v[k]) for k in ("glb", "glb_quest", "glb_quest_meshopt", "elements", "stages") if v.get(k)}
    files["check"] = os.path.join(site, f"{v['id']}_check.json")
    missing = [k for k, p in files.items() if not os.path.exists(p)]
    for k in missing: fails.append(f"{v['id']}: missing {k} {files[k]}")
    if missing: continue
    source_models=[files["glb"],files["glb_quest"]]
    if v.get("furnish_runtime"):
        report=json.load(open(os.path.join(site,"furnish",v["id"],"split-check.json")))
        source_models=[os.path.join(site,report["profiles"][kind]["source"]) for kind in ("full","quest")]
    t_glb=max(os.path.getmtime(model) for model in source_models)
    for k in ("elements", "stages", "check"):
        if os.path.getmtime(files[k]) + 120 < t_glb: fails.append(f"{v['id']}: {k} older than the GLB (stale)")
    g = glb_json(files["glb"])
    mats = g.get("materials", [])
    leaves = bad_leaf = notex = 0; loose_hw = []
    for nd in g["nodes"]:
        ex = nd.get("extras", {})
        if ex.get("door_leaf"):
            leaves += 1
            if not (isinstance(ex.get("hinge"), list) and "swing_deg" in ex): bad_leaf += 1
        if re.search(r"door-furniture|_leaf_handle$|letter", nd.get("name", ""), re.I) and not ex.get("door_leaf"): loose_hw.append(nd.get("name"))   # row 297 (F101): hardware on a leaf swings with it
        if "mesh" not in nd: continue
        for pr in g["meshes"][nd["mesh"]]["primitives"]:
            m = mats[pr.get("material", 0)] if mats else {}
            if m.get("pbrMetallicRoughness", {}).get("baseColorTexture") and "TEXCOORD_0" not in pr["attributes"]: notex += 1
    if loose_hw: fails.append(f"{v['id']}: door hardware without the leaf's hinge/door_leaf extras (it would stay put when the door opens): {loose_hw[:4]}")
    if bad_leaf: fails.append(f"{v['id']}: {bad_leaf}/{leaves} door leaves without hinge/swing_deg")
    if notex: fails.append(f"{v['id']}: {notex} textured primitives without TEXCOORD_0")
    q = glb_json(files["glb_quest"])
    # the meshopt twin is what phones and the Quest load: it must be rebuilt from this quest GLB (CORRECTIONS-LOG 198)
    mo_file = os.path.join(site, v["glb_quest"].replace("_quest.glb", "_quest_mo.glb"))
    if os.path.exists(mo_file) and not v.get("glb_quest_meshopt"):
        fails.append(f"{v['id']}: {os.path.basename(mo_file)} exists but versions.json does not list glb_quest_meshopt (196)")
    if v.get("glb_quest_meshopt"):
        mo = glb_json(files["glb_quest_meshopt"])
        if os.path.getmtime(files["glb_quest_meshopt"]) + 5 < os.path.getmtime(files["glb_quest"]):
            fails.append(f"{v['id']}: meshopt twin older than its quest GLB (stale: run tools/house/quest_meshopt.py)")
        if len(mo.get("nodes", [])) != len(q.get("nodes", [])):
            fails.append(f"{v['id']}: meshopt twin has {len(mo.get('nodes', []))} nodes, quest GLB {len(q.get('nodes', []))} (stale)")
    c = json.load(open(files["check"]))
    clashes = [x for x in c.get("clashes", []) if not x.get("allowed")]
    bearing = [x for x in c.get("bearing", []) if not x.get("allowed")]
    if clashes: fails.append(f"{v['id']}: {len(clashes)} unintended clashes")
    if bearing: fails.append(f"{v['id']}: {len(bearing)} cross-stage bearing faults")
    gb = ground_check(files["glb"])
    if gb:
        worst = sorted(((n, s_, pr) for s_, d in gb.items() for pr, n in d.items()), reverse=True)[:6]
        fails.append(f"{v['id']}: stacked ground surfaces (within 30 mm in plan) at stages {sorted(gb)}: "
                     + "; ".join(f"s{s_} {pr[0]} / {pr[1]} {n} cells" for n, s_, pr in worst))
    notes.append(f"{v['id']}: ground check {'clean' if not gb else 'STACKED'} at every stage; {leaves} leaves, {len(c.get('floating', []))} floating, {len(q.get('images', []))} quest images, "
                 f"GLB {os.path.getsize(files['glb']) / 1e6:.1f} / quest {os.path.getsize(files['glb_quest']) / 1e6:.1f} MB")
# row 179: the geometry INTEGRITY GATE (tools/house/check_integrity.py) must have passed on the homeowner versions (Before =
# as_built_now, After = the default proposal), on THESE GLBs (report newer than the GLB)
for vid in (V.get("as_built_now"), V.get("default")):
    if not vid: continue
    ip = os.path.join(site, f"{vid}_integrity.json"); gp = os.path.join(site, f"{vid}.glb")
    if not os.path.exists(ip): fails.append(f"{vid}: no integrity report (run check_integrity.py)"); continue
    r_ = json.load(open(ip))
    if os.path.exists(gp) and r_.get("written", 0) + 1 < os.path.getmtime(gp): fails.append(f"{vid}: integrity report older than the GLB (stale)"); continue
    if not r_.get("passed"):
        fails.append(f"{vid}: integrity gate FAILED " + ", ".join(f"{k} {n}" for k, n in r_["counts"].items() if n and k in r_.get("blocking", r_["counts"])))
    notes.append(f"{vid}: integrity {'PASS' if r_.get('passed') else 'FAIL'} {r_['counts']}; allowed (open, reported) {r_.get('allowed_counts', {})}")
# G5b SHELL READY (tools/house/check_shell.py, row 191): blocking, fresh, for the homeowner versions; G5c FINISHED HOUSE
# (tools/house/check_finish.py) reported always, blocking with --finished
for vid in (V.get("as_built_now"), V.get("default")):
    if not vid: continue
    sp = os.path.join(site, f"{vid}_shell.json"); gp = os.path.join(site, f"{vid}.glb")
    if not os.path.exists(sp): fails.append(f"{vid}: no shell report (run check_shell.py: G5b)"); continue
    r_ = json.load(open(sp))
    if os.path.exists(gp) and r_.get("written", 0) + 1 < os.path.getmtime(gp): fails.append(f"{vid}: shell report older than the GLB (stale)"); continue
    if not r_.get("passed"): fails.append(f"{vid}: SHELL READY (G5b) FAILED " + ", ".join(f"{r_['names'][k]} {n}" for k, n in r_["counts"].items() if n))
    notes.append(f"{vid}: shell {'PASS' if r_.get('passed') else 'FAIL'} {r_['counts']}; open drawing questions {r_.get('allowed_counts', {})}")
    fp = os.path.join(site, f"{vid}_finish.json")
    if os.path.exists(fp):
        f_ = json.load(open(fp))
        notes.append(f"{vid}: finished-house (G5c) {'PASS' if f_.get('passed') else 'not yet'} {f_['counts']}")
        if FINISHED and not f_.get("passed"): fails.append(f"{vid}: FINISHED HOUSE (G5c) FAILED {f_['counts']}")
    elif FINISHED: fails.append(f"{vid}: no finished-house report (run check_finish.py: G5c)")
# conf from the source (architect-inspector r6, log 172): generated detail never "exact"; photo-survey items "measured from photos"
GEN = ("WT-", "CC-", "CT-", "DPC-", "VJ-", "JH-", "RS-", "TH-", "TW-", "SC-")
for v in V["versions"]:
    p_ = os.path.join(site, v["glb"])
    if not os.path.exists(p_): continue
    bad = []
    for nd in glb_json(p_)["nodes"]:
        ex = nd.get("extras", {}); nm = nd.get("name", "")
        if nm.startswith(GEN) and ex.get("conf") == "exact": bad.append(nm)
        if ex.get("provenance") == "photo survey" and ex.get("conf") not in ("measured from photos",) and not ("layer" in ex and ex.get("conf") == "assumed"):
            bad.append(nm)          # (a re-cut wall's layer build-up stays the drawing's assumption: only its openings are surveyed)
    if bad: fails.append(f"{v['id']}: {len(bad)} parts with conf not matching their source (e.g. {bad[:3]})")
# the garden in the house build keeps the garden test's own detail (log 162): warn if a kept setting object lost >10 % of its
# triangles against the garden test's Quest file (ground clipped to its region and the street hedge cut into blocks: by design)
src = os.path.join(os.path.dirname(os.path.abspath(site)), "front-garden-model", "model_q.glb")
setp = os.path.join(site, "setting_front.glb")
if os.path.exists(src) and os.path.exists(setp):
    def tri_by_node(p_):
        g = glb_json(p_); out = {}
        for nd in g["nodes"]:
            if "mesh" not in nd: continue
            t = 0
            for pr in g["meshes"][nd["mesh"]]["primitives"]:
                a = g["accessors"][pr["indices"]] if "indices" in pr else g["accessors"][pr["attributes"]["POSITION"]]
                t += a["count"] // 3
            out[nd["name"]] = out.get(nd["name"], 0) + t
        return out
    S_, K_ = tri_by_node(src), tri_by_node(setp)
    lost = [(n, S_[n], t) for n, t in K_.items() if n in S_ and not n.startswith(("G2_", "B_street_hedge")) and t < 0.9 * S_[n]]
    for n, a, b in lost: notes.append(f"WARN setting: {n} {b} tris vs {a} in model_q.glb (-{100 - 100 * b // max(1, a)} %)")
    notes.append(f"setting vs model_q.glb: {len(K_)} objects kept, {sum(K_.values())} tris; {len(lost)} lost more than 10 %")
# row 190: every GLB the viewer can load is valid for three's GLTFLoader: every texture has an image source, every image a
# uri or bufferView, and every file loads headless through GLTFLoader (meshopt decoder registered, as house.html does)
def tex_source(t):
    if "source" in t: return t["source"]
    for e in t.get("extensions", {}).values():
        if isinstance(e, dict) and "source" in e: return e["source"]
    return None


glbs = []
for v in V["versions"]:
    for k in ("glb", "glb_quest", "glb_quest_meshopt"):
        if v.get(k) and os.path.exists(os.path.join(site, v[k])): glbs.append(os.path.join(site, v[k]))
for extra in ("setting_front.glb", "setting_front_lod.glb"):
    if os.path.exists(os.path.join(site, extra)): glbs.append(os.path.join(site, extra))
for p_ in glbs:
    g = glb_json(p_); imgs = g.get("images", [])
    nosrc = [i for i, t in enumerate(g.get("textures", [])) if tex_source(t) is None or not 0 <= tex_source(t) < len(imgs)]
    noimg = [i for i, im in enumerate(imgs) if not im.get("uri") and "bufferView" not in im]
    if nosrc: fails.append(f"{os.path.basename(p_)}: {len(nosrc)} textures without an image source (three's GLTFLoader crashes: row 190)")
    if noimg: fails.append(f"{os.path.basename(p_)}: {len(noimg)} images without uri or bufferView (row 190)")
import subprocess
lt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glb_load_test.mjs")
try:
    r = subprocess.run(["node", lt] + glbs, capture_output=True, text=True, timeout=900)
    for ln in r.stdout.splitlines():
        if ln.startswith("FAIL"): fails.append("GLTFLoader " + ln[5:])
    if r.returncode == 3: fails.append("GLTFLoader load test could not run: " + r.stderr.strip()[:200])
    notes.append(f"GLTFLoader headless load: {len([l for l in r.stdout.splitlines() if l.startswith('ok')])}/{len(glbs)} files ok")
except Exception as ex:
    fails.append(f"GLTFLoader load test could not run: {ex}")
for n in notes: print(n)
print("FAIL\n  " + "\n  ".join(fails) if fails else "PASS")
sys.exit(1 if fails else 0)
