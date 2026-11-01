"""Construction detail as geometry (pure Python): the things a site manager checks, which the drawings state in their
notes. dpc strips, cavity trays with stop ends over openings, cavity closers, wall ties (per lift), joist hangers,
plate restraint straps, vertical dpc / starter at junctions with the existing house, drains as drawn (runs, inspection
chamber, gully, soakaways, svp), lintels over pipes through the substructure. Each detail is its own element with the
drawing's wording where the drawing has it, and "(typical — not from the drawings)" where it only follows good practice.
Every detail takes its stage and seq from the part it belongs to."""
import math
from hb_geom import (sub, add, mul, dot, unit, length, prism, hexa, merge_meshes, box, rect_section, ccw, point_in_poly)
from hb_build import atom, M, sig_of, slug, TYPICAL
from hb_walls import layer_stack
import hb_stage as S


def _band(W, key_from, key_to=None):
    """c-range (outside offsets) of one layer or from one layer to another"""
    L = layer_stack(W.ckey, W.t)
    a = next(l for l in L if l["key"] == key_from); b = next(l for l in L if l["key"] == (key_to or key_from))
    return min(a["o0"], b["o0"]), max(a["o1"], b["o1"])


def _quad(W, u0, u1, o0, o1):
    c0, c1 = W.c_of(o0), W.c_of(o1)
    return [W.point(u0, c0), W.point(u1, c0), W.point(u1, c1), W.point(u0, c1)]


SPEC_REF = {}


def _lift_seq(a, z):
    """seq of the wall course at height z (so a detail goes in with its course)"""
    W = a["wall"]
    lines = [W.z0] + [l for l in W.lifts if W.z0 < l < W.z1] + [W.z1]
    nl = len(lines) - 1
    k = max(i for i in range(nl) if lines[i] <= z + 1e-6) if z >= W.z0 else 0
    if SPEC_REF.get("spec") and W.__dict__.get("_zband"):
        return S.lift_stage_seq(a, z, SPEC_REF["spec"])[1], k
    return S.wall_seq(a["meta"], k, nl, 0, 1), k


def _meta_from(a, group, label, plain, conf="typical", seq=None, collide=False, drawing=None):
    m = M(group, a["meta"]["storey"], label, drawing or a["meta"].get("drawing", ""), conf, plain, collide)
    m.update(stage_in=a["meta"]["stage_in"], stage_out=None, seq=round(seq if seq is not None else a["meta"]["seq"], 4), seq_out=None,
             category="new")
    if a.get("lift_stage_after") and seq is not None:
        pass
    return m


def wall_details(atoms, spec, lv, notes):
    out = []
    WN = spec["structure_notes"]
    for a in atoms:
        if a["kind"] != "wall" or a["meta"].get("category") not in ("new",) or a.get("infill"): continue
        W = a["wall"]
        if W.ckey not in ("cav337_new", "block_int"): continue
        ua, ub = max(W.end_u("a", 0), W.ua), min(W.end_u("b", 0), W.ub)
        L = layer_stack(W.ckey, W.t)
        # --- dpc strips in each masonry leaf at the dpc line (a 3 mm band in the bed joint)
        if W.z0 < lv.dpc < W.z1 and W.storey == "ground":
            meshes = []
            for l in L:
                if l["key"] in ("brick", "block", "core"):
                    # row 179: 1 mm back from both leaf faces (the strip shared the brick face plane: z-fighting on the facade)
                    meshes.append(prism(_quad(W, ua, ub, l["o0"] + 0.001, l["o1"] - 0.001), lv.dpc - 0.0015, lv.dpc + 0.0015))
            sq, _ = _lift_seq(a, lv.dpc + 0.01)
            m = _meta_from(a, "wall_outer", WN["dpc"], "Damp-proof course in the wall", seq=max(0, sq - 0.01))
            if spec["staging"]["phases"].get("dpc_detail"): m["stage_in"], m["seq"] = spec["staging"]["phases"]["dpc_detail"]
            out.append(atom(f"DPC-{W.id}", "mesh", "detail", m, sig=sig_of("dpc", W.id), mesh=merge_meshes(meshes), mat="dpm", cat="new"))
        if W.ckey != "cav337_new": continue
        cav = _band(W, "cavity"); ins = _band(W, "pir"); brick = _band(W, "brick"); block = _band(W, "block")
        # --- wall ties at 750 x 450 (staggered), through the insulation into both leaves (merged per lift)
        lines = [W.z0] + [l for l in W.lifts if W.z0 < l < W.z1] + [W.z1]
        per_lift = {}
        zt = max(W.z0, lv.cavity_fill_top) + 0.225
        row = 0
        while zt < W.top_at((ua + ub) / 2) - 0.15:
            off = 0.375 if row % 2 else 0.0
            u = ua + 0.2 + off
            while u < ub - 0.15:
                if not any(o["u0"] - 0.05 < u < o["u1"] + 0.05 and o["z0"] - 0.05 < zt < o["z1"] + 0.3 for o in W.openings) and \
                        zt < min(W.top_at(u), W.layer_tops.get("brick", 9.0), W.layer_tops.get("block", 9.0)) - 0.1:
                    k = max(i for i in range(len(lines) - 1) if lines[i] <= zt)
                    q = _quad(W, u - 0.01, u + 0.01, brick[1] - 0.05, block[0] + 0.05)
                    per_lift.setdefault(k, []).append(prism(q, zt - 0.002, zt + 0.002))
                u += 0.75
            zt += 0.45; row += 1
        for k, ms in per_lift.items():
            st, sq = S.lift_stage_seq(a, lines[k], spec)
            if a.get("lift_stage_after") and lines[k] >= a["lift_stage_after"][0] - 1e-4: st, sq = a["lift_stage_after"][1], a["lift_stage_after"][2]
            m = _meta_from(a, "wall_cavity", WN["wall_ties"], "Stainless steel ties joining the two skins of the wall", seq=sq)
            m["stage_in"] = st
            out.append(atom(f"WT-{W.id}-l{k}", "mesh", "detail", m, sig=sig_of("ties", W.id, k), mesh=merge_meshes(ms), mat="lintel_galv", cat="new"))
        # --- per opening: closers at the jambs and sill (in the clear cavity), a cavity tray with stop ends over the lintel
        for o in W.openings:
            if o["kind"] == "opening": continue
            u0, u1, z0, z1 = o["u0"], o["u1"], o["z0"], o["z1"]
            cl = []
            for (a0, a1) in ((u0 - 0.10, u0), (u1, u1 + 0.10)):
                cl.append(prism(_quad(W, a0, a1, cav[0] + 0.002, cav[1] - 0.002), max(z0, W.z0), z1))
            if z0 > lv.dpc + 0.1:
                cl.append(prism(_quad(W, u0, u1, cav[0] + 0.002, cav[1] - 0.002), z0 - 0.10, z0))
            sq, _ = _lift_seq(a, z0 + 0.05)
            out.append(atom(f"CC-{W.id}-{slug(o['id'])}", "mesh", "detail", _meta_from(a, "wall_cavity", WN["closers"], "Insulated closer sealing the cavity round the opening", seq=sq),
                            sig=sig_of("closer", W.id, o["id"]), mesh=merge_meshes(cl), mat="mineral_wool", cat="new"))
            if o["id"] in spec["lintels"].get("skip", []): continue        # beam 5 opening: the plate does the job
            h = 0.215 if "CH" in (o.get("lintel") or spec["lintels"]["by_opening"].get(o["id"], "")) else 0.150
            # tray: from the outer leaf's inner face just above the lintel toe, rising across the cavity to the inner leaf
            pa, pb = W.c_of(brick[1]), W.c_of(ins[1])
            ta = (u0 - 0.15, u1 + 0.15)
            P = lambda u, c: W.point(u, c)
            tr = [(*P(ta[0], pa), z1 + 0.010), (*P(ta[1], pa), z1 + 0.010), (*P(ta[1], pb), z1 + h - 0.003), (*P(ta[0], pb), z1 + h - 0.003),
                  (*P(ta[0], pa), z1 + 0.013), (*P(ta[1], pa), z1 + 0.013), (*P(ta[1], pb), z1 + h), (*P(ta[0], pb), z1 + h)]
            ends = [prism(_quad(W, ta[0], ta[0] + 0.003, brick[1] + 0.002, ins[1] - 0.002), z1 + 0.013, z1 + 0.10),
                    prism(_quad(W, ta[1] - 0.003, ta[1], brick[1] + 0.002, ins[1] - 0.002), z1 + 0.013, z1 + 0.10)]
            sq = S.lift_stage_seq(a, z1, spec)[1] + 0.03
            out.append(atom(f"CT-{W.id}-{slug(o['id'])}", "mesh", "detail",
                            _meta_from(a, "wall_cavity", WN["tray"], "Cavity tray over the lintel, sheds water out through weep holes", seq=sq),
                            sig=sig_of("tray", W.id, o["id"]), mesh=merge_meshes([hexa(tr)] + ends), mat="dpm", cat="new"))
    return out


def junction_dpc(atoms, spec, lv):
    """vertical dpc and wall starter where a new cavity wall meets the existing house"""
    out = []
    walls = [a for a in atoms if a["kind"] == "wall"]
    ex = [w for w in walls if w["meta"].get("category") == "existing" and w["wall"].ckey != "massing"]
    for a in walls:
        if a["meta"].get("category") != "new" or a["wall"].ckey != "cav337_new": continue
        W = a["wall"]
        for which in ("a", "b"):
            u = W.end_u(which, 0)
            p = W.point(u, 0)
            hit = None
            for e in ex:
                B = e["wall"]
                rel = sub(p, B.a); ub_, cb = dot(rel, B.d), dot(rel, B.n)
                if B.ua - 0.02 <= ub_ <= B.ub + 0.02 and -B.t / 2 - 0.03 <= cb <= B.t / 2 + 0.03 and min(B.z1, W.z1) - max(B.z0, W.z0) > 0.3:
                    hit = e; break
            if not hit: continue
            sgn = 1 if which == "a" else -1
            q = _quad(W, u + sgn * 0.0015, u + sgn * 0.0055, 0.0015, W.t - 0.0015)    # row 179: 1.5 mm inside both wall faces (it shared them: z-fighting)
            z0, z1 = max(W.z0, lv.dpc), min(W.z1, hit["wall"].z1)
            m = M("wall_cavity", W.storey, spec["structure_notes"]["junction"], "4915.3A construction notes", "assumed",
                  "Damp-proof strip and wall ties where the new wall joins the old house", False)
            m.update(stage_in=a["meta"]["stage_in"], stage_out=None, seq=a["meta"]["seq"], seq_out=None, category="new")
            out.append(atom(f"VJ-{W.id}-{which}", "mesh", "detail", m, sig=sig_of("vdpc", W.id, which), mesh=prism(q, z0, z1), mat="dpm", cat="new"))
    return out


def hangers_and_straps(vb, atoms, spec, lv):
    out = []
    # joist hangers: at every joist end that stops against the face of a wall standing in the joist zone
    meshes = []
    walls = [w["wall"] for w in atoms if w["kind"] == "wall" and w["meta"].get("category") != "demolition"]
    for a in atoms:
        if a["kind"] != "member" or a["meta"]["group"] != "joist" or not a.get("clip_to_walls") or a["meta"].get("category") != "new": continue
        for (P0, P1) in vb.clip_member(a):
            for (pe, po) in ((P0, P1), (P1, P0)):
                d = unit(sub(pe[:2], po[:2])); n = (d[1], -d[0]); zt = pe[2]
                probe = add(pe[:2], mul(d, 0.012))
                if not any(W.z0 < zt - 0.1 and W.z1 > zt - 0.1 and point_in_poly(probe, ccw(W.footprint(full=False))) for W in walls): continue
                w = 0.0225
                fl = [add(pe[:2], mul(n, -w - 0.005)), add(pe[:2], mul(n, w + 0.005)), add(add(pe[:2], mul(n, w + 0.005)), mul(d, -0.002)), add(add(pe[:2], mul(n, -w - 0.005)), mul(d, -0.002))]
                meshes.append(prism(fl, zt - 0.195, zt - 0.02))
                seat = [add(pe[:2], mul(n, -w - 0.003)), add(pe[:2], mul(n, w + 0.003)), add(add(pe[:2], mul(n, w + 0.003)), mul(d, -0.08)), add(add(pe[:2], mul(n, -w - 0.003)), mul(d, -0.08))]
                meshes.append(prism(seat, zt - 0.197, zt - 0.195))
    if meshes:
        m = M("joist", "first", spec["structure_notes"]["hangers"], "4915.3A / 4A first floor joist plan", "assumed", "Steel hangers the joists sit in", False)
        m.update(stage_in=spec["staging"]["phases"]["joist"][0], stage_out=None, seq=max(0.0, spec["staging"]["phases"]["joist"][1] - 0.04), seq_out=None, category="new")
        out.append(atom("JH-ff-hangers", "mesh", "detail", m, sig=sig_of("hangers"), mesh=merge_meshes(meshes), mat="lintel_galv", cat="new"))
    # plate restraint straps: 30x5 galvanised, down the inner face of the inner leaf at 1.2 m
    for a in atoms:
        if a["kind"] != "member" or a["meta"]["group"] != "wall_plate" or a["meta"].get("category") != "new": continue
        W = next((w["wall"] for w in atoms if w["kind"] == "wall" and w["wall"].id == a.get("plate_wall")), None)
        if W is None or W.ckey != "cav337_new": continue
        L = layer_stack(W.ckey, W.t); blk = next(l for l in L if l["key"] == "block")
        A, B = a["A"], a["B"]
        Lp = math.dist(A[:2], B[:2]); d = unit(sub(B[:2], A[:2]))
        ms = []
        k = 0.3
        while k < Lp - 0.1:
            u = dot(sub(add(A[:2], mul(d, k)), W.a), W.d)
            hit = next((o for o in W.openings if o["u0"] - 0.06 < u < o["u1"] + 0.06 and o["z1"] + 0.25 > A[2] - 1.0), None)
            if hit:                                   # never across an opening: move the strap past its jamb
                u = hit["u1"] + 0.08 if hit["u1"] + 0.08 < W.ub - 0.1 else hit["u0"] - 0.08
                k = dot(sub(W.point(u, 0), A[:2]), d)
            q = _quad(W, u - 0.015, u + 0.015, blk["o1"], blk["o1"] + 0.005)
            ms.append(prism(q, A[2] - 1.0, A[2] + 0.002))
            k += 1.2
        if ms:
            m = M("wall_plate", "roof", spec["structure_notes"]["straps"], "", "assumed", "Steel straps tying the roof plate to the wall", False)
            m.update(stage_in=a["meta"]["stage_in"], stage_out=None, seq=a["meta"]["seq"] + 0.005, seq_out=None, category="new")
            out.append(atom(f"RS-{a['id']}", "mesh", "detail", m, sig=sig_of("straps", a["id"]), mesh=merge_meshes(ms), mat="lintel_galv", cat="new"))
    return out


def drains(spec, lv, version_kind, vid=None):
    """drains as drawn: runs (110 / 100 pvc-u in pea shingle), the existing inspection chamber, gullies, soakaways, svp"""
    out = []
    D = spec.get("drains", {})
    def pipe(p0, p1, r, n=8):
        X = sub(p1[:2], p0[:2]); L2 = length(X)
        d3 = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]); L = math.sqrt(sum(v * v for v in d3))
        from hb_geom import frame_matrix, apply_matrix, extrude_section
        Mx = frame_matrix(p0, d3, (0, 0, 1) if L2 > 1e-6 else (1, 0, 0))
        sec = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]
        V, F = extrude_section(sec, L)
        return apply_matrix(Mx, V), F
    for it in D.get("items", []):
        if vid and vid in it.get("skip_versions", []): continue
        cat = it.get("category_by_version", {}).get(vid, it.get("category", "new"))
        if version_kind != "proposal" and cat == "new": continue
        if version_kind != "proposal" and cat == "demolition": cat = "existing"
        meshes = []
        if it["kind"] == "run":
            P = it["points"]
            for p0, p1 in zip(P, P[1:]): meshes.append(pipe(p0, p1, it.get("r", 0.055)))
            mat = "pvc_drain"
        elif it["kind"] == "chamber":
            (x, y), r, zc, depth = it["at"], it.get("r", 0.225), it["cover_z"], it["depth"]
            n = 12; poly = [(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
            meshes.append(prism(poly, zc - depth, zc - 0.02)); meshes.append(box(x - r - 0.03, x + r + 0.03, y - r - 0.03, y + r + 0.03, zc - 0.02, zc))
            mat = it.get("mat", "concrete")
        elif it["kind"] == "box":
            (x0, y0, x1, y1), z0, z1 = it["rect"], it["z0"], it["z1"]
            meshes.append(box(x0, x1, y0, y1, z0, z1)); mat = it.get("mat", "black_upvc")
        elif it["kind"] == "stack":
            (x, y), z0, z1 = it["at"], it["z0"], it["z1"]
            meshes.append(pipe((x, y, z0), (x, y, z1), it.get("r", 0.055))); mat = it.get("mat", "black_upvc")
        m = M(it.get("group", "drain"), "site", it["label"], it.get("drawing", ""), it.get("conf", "scaled"), it.get("plain", "Drain"), False)
        if version_kind == "proposal":
            if cat == "new":
                st, sq = spec["staging"]["phases"].get(it.get("phase", "drain"))
                m.update(stage_in=st, stage_out=None, seq=min(0.99, sq + it.get("seq_bias", 0.0)), seq_out=None, category="new")
            elif cat == "demolition":
                m.update(stage_in=1, stage_out=spec["staging"].get("demolition_stage", 2), seq=0.0, seq_out=it.get("seq_out", 0.2), category="demolition")
            else:
                m.update(stage_in=1, stage_out=None, seq=0.0, seq_out=None, category="existing")
        else:
            m.update(stage_in=1, stage_out=None, seq=0.0, seq_out=None, category="existing")
        a = atom(it["id"], "mesh", "drain", m, sig=sig_of("drain", it["id"]), mesh=merge_meshes(meshes), mat=mat, cat=m["category"])
        if it.get("trench") and it["kind"] == "run": a["trench"] = [tuple(p) for p in it["points"]]
        if it.get("embed"): a["embed"] = True
        out.append(a)
    return out


def threshold_flags(atoms, spec, lv):
    """external doors where the dpc is under 150 mm above the outside ground (drawn condition: flag, never hide)"""
    flags = []
    zones = spec.get("site_zones", [])
    for a in atoms:
        if a["kind"] != "wall" or a["wall"].ckey not in ("cav337_new", "cav_existing"): continue
        W = a["wall"]
        for o in W.openings:
            if o["kind"] not in ("door", "bifold") or o["z0"] > 0.1: continue
            mid = (o["u0"] + o["u1"]) / 2
            out_pt = W.point(mid, W.c_of(-0.4))
            g = next((z["z"] for z in zones if len(z["poly"]) > 2 and point_in_poly(out_pt, z["poly"])), None)
            if g is None: continue
            h = lv.dpc - g
            if h < 0.15:
                flags.append(dict(id=f"Q-dpc-{slug(o['id'])}", position=[round(out_pt[0], 3), round(out_pt[1], 3), round(g, 3)],
                                  text=f"{o['id']}: the dpc ({lv.dpc:+.3f}) is {h * 1000:.0f} mm above the outside ground ({g:+.3f}) — under the 150 mm the "
                                       "notes and AD C ask for. Drawn condition: a level threshold / drainage channel or lowered ground is needed (question for the architect).",
                                  element=a["id"], opening=o["id"], dpc_above_ground_mm=round(h * 1000)))
    return flags
