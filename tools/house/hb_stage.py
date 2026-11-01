"""Version diff, staging and parts (pure Python).

diff(base_state, target_state) classifies every atom: kept (existing, stage 1), demolished (stage_out), new
(stage_in by trade). Walls are diffed by footprint overlap along their lines (so a wall cut back, lowered, opened up
or stripped of a leaf keeps what stays and demolishes only the rest); linear members (rafters, ridges, hips) by
collinear intervals (a rafter cut back keeps its stub); roof coverings by plane and convex piece; everything else by
geometric signature. Then temporary works from the spec, stages and seq, wall joins, and parts (closed meshes with the
contract's extras)."""
import math, re, copy
from hb_geom import (sub, add, mul, dot, unit, length, area, ccw, centroid, point_in_poly, box, prism, hexa, slab3d,
                     merge_meshes, rect_section, extrude_section, frame_matrix, apply_matrix, clip_convex, poly_halfplanes,
                     convex_minus, interval_minus, merge_intervals, clip_segment_convex, mesh_bbox, v3sub, v3len, v3unit,
                     v3add, v3mul, seg_point_dist, clip_half)
from hb_geom import interval_minus as G_interval_minus
from hb_walls import Wall, layer_stack, wall_parts, resolve_joins, CONSTRUCTIONS
from hb_build import atom, M, sig_of, slug, u_of, piece, parallel_overlap, dref, TYPICAL, _convex
import hb_roof as R

NEW_MAT = {"existing_brick": "brick", "plaster": "plaster"}
NEW_MAT_INNER = {"existing_brick": "block"}          # an infilled opening: new brick outside, block inside


# ======================================================================================== diff
SPEC_DW = {}         # fixture id -> spec_v1 doors_windows row (set per version by generate_house)


def diff(base, target, spec, lv):
    """-> list of atoms with 'cat' in existing | demolition | new, and wall pieces"""
    out = []
    bw = [a for a in base["atoms"] if a["kind"] == "wall"]
    tw = [a for a in target["atoms"] if a["kind"] == "wall"]
    beams_t = [a for a in target["atoms"] if a["kind"] == "member" and a["meta"]["group"] in ("steel",)]
    out.extend(diff_walls(bw, tw, beams_t, spec, lv))
    # linear members
    bl = [a for a in base["atoms"] if a.get("linear")]
    tl = [a for a in target["atoms"] if a.get("linear")]
    out.extend(diff_linear(bl, tl))
    # roof coverings
    bc = [a for a in base["atoms"] if a["kind"] == "cover"]
    tc = [a for a in target["atoms"] if a["kind"] == "cover"]
    out.extend(diff_covers(bc, tc))
    # battens follow the covers: regenerated per class
    out.extend(diff_battens([a for a in base["atoms"] if a["kind"] == "batten_set"], [a for a in target["atoms"] if a["kind"] == "batten_set"],
                            [a for a in out if a["kind"] == "cover" and a["meta"]["group"] == "roof_cover"]))
    # existing foundations: kept wherever a wall of the target still stands on them (one footing, never rebuilt)
    isx = lambda a: a["id"].startswith("XFD-")
    bx = [a for a in base["atoms"] if isx(a)]; tx = [a for a in target["atoms"] if isx(a)]
    def _ov(a, b):
        P = clip_convex(ccw(a["poly"]), poly_halfplanes(ccw(b["poly"]))) if _convex(ccw(a["poly"])) and _convex(ccw(b["poly"])) else None
        return bool(P) and len(P) >= 3 and abs(area(P)) > 0.005
    for b in bx:
        out.append(dict(b, cat="existing" if any(_ov(b, t) for t in tx) else "demolition"))
    for t in tx:
        if not any(_ov(t, b) for b in bx): out.append(dict(t, cat="new"))
    # existing floors and ceilings: the part a proposal keeps stays existing (never taken up and re-laid), only the
    # cut-out goes, and only what the base never had is new
    isxf = lambda a: a["kind"] == "slab" and a["id"].startswith(("XF-", "XC-"))
    from hb_geom import convex_pieces as _cp, poly_minus_convex as _pmc
    bf = [a for a in base["atoms"] if isxf(a)]; tf = [a for a in target["atoms"] if isxf(a)]
    key = lambda a: (a["id"][:4], round(a["z0"], 3), round(a["z1"], 3))
    for b in bf:
        same = [t for t in tf if key(t) == key(b)]
        tp = [P for t in same for P in _cp(ccw(t["poly"]))]
        keep = []
        for P in _cp(ccw(b["poly"])):
            for Q in tp:
                I = clip_convex(P, poly_halfplanes(Q))
                if I and len(I) >= 3 and abs(area(I)) > 1e-4: keep.append(I)
        rest = _pmc(b["poly"], tp) if tp else [ccw(b["poly"])]
        for k, P in enumerate(keep): out.append(dict(b, poly=P, id=b["id"] + (f"-k{k}" if len(keep) > 1 or rest else ""), cat="existing"))
        for k, P in enumerate(rest):
            if abs(area(P)) > 1e-3: out.append(dict(b, poly=P, id=f"{b['id']}-d{k}", cat="demolition"))
    for t in tf:
        same = [b for b in bf if key(t) == key(b)]
        rest = _pmc(t["poly"], [P for b in same for P in _cp(ccw(b["poly"]))]) if same else [ccw(t["poly"])]
        for k, P in enumerate(rest):
            if abs(area(P)) > 1e-3: out.append(dict(t, poly=P, id=f"{t['id']}-n{k}", cat="new"))
    # the rest by signature
    skip = lambda a: a["kind"] in ("wall", "cover", "batten_set") or a.get("linear") or isx(a) or isxf(a)
    bs = {a["sig"]: a for a in base["atoms"] if not skip(a)}
    ts = {a["sig"]: a for a in target["atoms"] if not skip(a)}
    for s, a in bs.items():
        b = dict(a); b["cat"] = "existing" if s in ts else "demolition"
        out.append(b)
    for s, a in ts.items():
        if s in bs: continue
        b = dict(a); b["cat"] = "new"
        out.append(b)
    return out


def same_op(o, p, tol=0.03):
    return all(abs(o[k] - p[k]) < tol for k in ("u0", "u1", "z0", "z1"))


def rect_minus(r, cuts):
    """(u0,u1,z0,z1) minus list of rects -> list of rects"""
    out = [r]
    for c in cuts:
        nxt = []
        for (u0, u1, z0, z1) in out:
            cu0, cu1, cz0, cz1 = max(u0, c[0]), min(u1, c[1]), max(z0, c[2]), min(z1, c[3])
            if cu1 - cu0 < 1e-4 or cz1 - cz0 < 1e-4:
                nxt.append((u0, u1, z0, z1)); continue
            if cu0 > u0: nxt.append((u0, cu0, z0, z1))
            if cu1 < u1: nxt.append((cu1, u1, z0, z1))
            if cz0 > z0: nxt.append((cu0, cu1, z0, cz0))
            if cz1 < z1: nxt.append((cu0, cu1, cz1, z1))
        out = nxt
    return [r for r in out if r[1] - r[0] > 0.005 and r[3] - r[2] > 0.005]


def diff_walls(bw, tw, beams_t, spec, lv):
    out = []
    kept_proj = {id(t): [] for t in tw}
    for ba in bw:
        B = ba["wall"]
        kept = []          # (u0,u1,z0,z1, target atom, partial_layers or None)
        for ta in tw:
            T = ta["wall"]
            if T.ckey in ("cav337_new", "block_int", "stud", "ashlar") and B.meta.get("existing"): continue   # new walls are new
            iv = parallel_overlap(B, T)
            if not iv: continue
            if iv[1] - iv[0] < min(0.3, 0.5 * min(B.ub - B.ua, T.ub - T.ua)): continue      # a wall only touching another end-on
            z0, z1 = max(B.z0, T.z0), min(B.z1, T.z1)
            if z1 - z0 < 0.05: continue
            partial = None
            if T.t < B.t - 0.06:
                # keep only B's layers that lie inside T's drawn band (e.g. an inner leaf kept, outer skin removed)
                c_lo = dot(sub(T.a, B.a), B.n) - T.t / 2; c_hi = c_lo + T.t
                partial = [l["key"] for l in B.layers() if min(B.c_of(l["o0"]), B.c_of(l["o1"])) < c_hi - 0.005 and
                           max(B.c_of(l["o0"]), B.c_of(l["o1"])) > c_lo + 0.005]
            kept.append((iv[0], iv[1], z0, z1, ta, partial))
            kept_proj[id(ta)].append((u_of(T, B.point(iv[0], 0)), u_of(T, B.point(iv[1], 0)), z0, z1))
        # walling kept above a new beam set into this wall (the wall over a new opening stays, carried by the beam)
        for be in beams_t:
            A3, B3 = be["A"], be["B"]
            if abs(abs(dot(unit(sub(B3[:2], A3[:2])), B.d)) - 1) > 1e-3: continue
            off = dot(sub(A3[:2], B.a), B.n)
            if abs(off) > B.t / 2: continue
            u0, u1 = sorted((u_of(B, A3[:2]), u_of(B, B3[:2])))
            u0, u1 = max(u0, B.ua), min(u1, B.ub)
            top = max(A3[2], B3[2])
            if u1 - u0 > 0.05 and B.z1 > top + 0.02:
                # only where nothing else keeps it
                free = interval_minus([(u0, u1)], [(k[0], k[1]) for k in kept])
                for (a, b) in free:
                    kept.append((a, b, top, B.z1, None, None))
        rect = (B.ua, B.ub, B.z0, B.z1)
        demo = rect_minus(rect, [(k[0], k[1], k[2], k[3]) for k in kept])
        n = 0
        for (u0, u1, z0, z1, ta, partial) in kept:
            n += 1
            P = piece(B, u0, u1, z0, z1, pid=B.id if len(kept) == 1 and not demo else f"{B.id}~k{n}")
            if partial is not None and set(partial) != set(l["key"] for l in B.layers()):
                P.only_layers = partial
                Q = piece(B, u0, u1, z0, z1, pid=f"{B.id}~strip{n}")
                Q.only_layers = [l["key"] for l in B.layers() if l["key"] not in partial]
                qa = dict(ba, id=Q.id, wall=Q, cat="demolition", meta=dict(ba["meta"], label=f"{ba['meta']['label']} — leaf removed: "
                          + (ta["wall"].meta.get("type", "") if ta else "")))
                out.append(qa)
            T = ta["wall"] if ta else None
            # openings: union of base and target; infill where the base had one the target does not; panels where
            # the target opens what the base had closed
            b_ops = [o for o in P.openings]
            t_ops = []
            if T is not None:
                for o in T.openings:
                    a_, b_ = u_of(B, T.point(o["u0"], 0)), u_of(B, T.point(o["u1"], 0))
                    oo = dict(o, u0=min(a_, b_), u1=max(a_, b_))
                    if oo["u1"] > u0 + 1e-3 and oo["u0"] < u1 - 1e-3: t_ops.append(oo)
            P.openings = []
            for o in b_ops:
                P.openings.append(o)
                match = [p for p in t_ops if same_op(o, p)]
                if not match and T is not None:
                    for q in P.openings:
                        if q["id"] == o["id"]: q["infilled"] = True        # bricked up: no longer an opening after the strip-out
                    covering = [p for p in t_ops if p["u0"] <= o["u0"] + 0.03 and p["u1"] >= o["u1"] - 0.03 and p["z0"] <= o["z0"] + 0.03 and p["z1"] >= o["z1"] - 0.03]
                    for (iu0, iu1, iz0, iz1) in rect_minus((o["u0"], o["u1"], o["z0"], o["z1"]), [(p["u0"], p["u1"], p["z0"], p["z1"]) for p in t_ops]):
                        I = piece(B, iu0, iu1, iz0, iz1, pid=f"{B.id}~infill-{slug(o['id'])}")
                        I.openings = []; I.only_layers = P.only_layers; I.new_infill = True
                        lab = spec.get("infill_label", "existing opening infilled with walling & finishes to match the ext'g")
                        out.append(dict(ba, id=I.id, wall=I, cat="new", infill=True, phase=ba["phase"], seq_bias=0.6,
                                        meta=dict(ba["meta"], label=f"{o['id']}: {lab}", plain_label="Old opening bricked up", conf="scaled", seq_span=0.3)))
                        out[-1]["seq_bias"] = 0.2           # bricked up early in the stage, before new lintels bear on it
            for p in t_ops:
                if any(same_op(o, p) for o in b_ops): continue
                P.openings.append(p)
                for (iu0, iu1, iz0, iz1) in rect_minus((p["u0"], p["u1"], p["z0"], p["z1"]), [(o["u0"], o["u1"], o["z0"], o["z1"]) for o in b_ops]):
                    Q = piece(B, iu0, iu1, iz0, iz1, pid=f"{B.id}~panel-{slug(p['id'])}")
                    Q.openings = []; Q.only_layers = P.only_layers
                    out.append(dict(ba, id=Q.id, wall=Q, cat="demolition", panel=True,
                                    meta=dict(ba["meta"], label=f"{p['id']}: existing walling cut out for the new opening", plain_label="Wall cut away for a new opening")))
            P.openings_new = [p for p in t_ops if not any(same_op(o, p) for o in b_ops)]
            out.append(dict(ba, id=P.id, wall=P, cat="existing"))
        for k, (u0, u1, z0, z1) in enumerate(demo):
            Q = piece(B, u0, u1, z0, z1, pid=B.id if not kept and len(demo) == 1 else f"{B.id}~d{k + 1}")
            out.append(dict(ba, id=Q.id, wall=Q, cat="demolition", meta=dict(ba["meta"], plain_label=(ba["meta"].get("plain_label") or "Wall") + " — taken down")))
    for ta in tw:
        T = ta["wall"]
        rect = (T.ua, T.ub, T.z0, T.z1)
        new = rect_minus(rect, [(min(a, b), max(a, b), z0, z1) for (a, b, z0, z1) in kept_proj[id(ta)]])
        new = [r for r in new if r[1] - r[0] > 0.05]          # no slivers from tracing tolerances
        for k, (u0, u1, z0, z1) in enumerate(new):
            if T.profile: z1 = T.z1
            P = piece(T, u0, u1, z0, z1, pid=T.id if len(new) == 1 and not kept_proj[id(ta)] else f"{T.id}~n{k + 1}")
            if T.profile: P.profile = T.profile
            out.append(dict(ta, id=P.id, wall=P, cat="new"))
    return out


EXTENDABLE = ("ridge", "wall_plate")


def diff_linear(bl, tl, tol=0.006, tol_by_group={"wall_plate": 0.04}):
    """members along lines. Same line and group: identical -> kept; target shorter (cut back) -> the stub is kept and
    the rest demolished; target longer -> the base member is replaced (a rafter is not spliced), except ridge boards
    and plates which are extended. A member classified new takes its wing's 'new' section/label."""
    out = []
    def axis(a):
        A, B = a["A"], a["B"]
        return A, v3unit(v3sub(B, A)), v3len(v3sub(B, A))
    def rel(b, t):
        A, d, L = axis(b); At, dt, Lt = axis(t)
        if t["meta"]["group"] != b["meta"]["group"]: return None
        c = sum(x * y for x, y in zip(d, dt))
        if abs(abs(c) - 1) > 1e-4: return None
        w = v3sub(At, A); proj = sum(x * y for x, y in zip(w, d))
        if v3len(v3sub(w, v3mul(d, proj))) > tol_by_group.get(b["meta"]["group"], tol): return None
        s0, s1 = sorted((proj, proj + Lt * c))
        if min(L, s1) - max(0, s0) < 0.01: return None
        return s0, s1, L
    status_t = {}
    for b in bl:
        A, d, L = axis(b)
        kept, replaced = [], False
        for t in tl:
            r = rel(b, t)
            if not r: continue
            s0, s1, _ = r
            ext = s0 < -0.01 or s1 > L + 0.01
            if ext and b["meta"]["group"] not in EXTENDABLE:
                replaced = True; status_t.setdefault(id(t), "whole"); continue
            lo_, hi_ = max(0, s0), min(L, s1)
            if b.get("tail") and b.get("wing_cat") == "existing" and hi_ < L - 0.01:
                # an existing rafter shortened by a new roof keeps its length to the wall: only the tail is cut ("cut back to plate level")
                hi_ = max(hi_, L - b["tail"])
            kept.append((lo_, hi_))
            status_t.setdefault(id(t), "cover")
        kept = merge_intervals(kept, gap=0.002)
        if replaced and not kept:
            out.append(_sub_member(b, A, d, 0, L, "demolition", "")); continue
        for (lo, hi) in kept:
            out.append(_sub_member(b, A, d, lo, hi, "existing", "" if (lo < 0.002 and hi > L - 0.002) else "~k"))
        for k, (lo, hi) in enumerate(interval_minus([(0, L)], kept)):
            out.append(_sub_member(b, A, d, lo, hi, "demolition", f"~d{k}" if kept else ""))
    for t in tl:
        A, d, L = axis(t)
        if status_t.get(id(t)) == "whole":
            out.append(_new_member(t, A, d, 0, L, "")); continue
        cov = []
        for b in bl:
            r = rel(t, b)
            if r: cov.append((max(0, r[0]), min(L, r[1])))
        for k, (lo, hi) in enumerate(interval_minus([(0, L)], merge_intervals(cov, gap=0.002))):
            if hi - lo < 0.02: continue
            out.append(_new_member(t, A, d, lo, hi, f"~n{k}" if cov else ""))
    return out


def _new_member(t, A, d, lo, hi, suffix):
    b = _sub_member(t, A, d, lo, hi, "new", suffix)
    ov = t.get("new_override")
    if ov:
        b["meta"] = dict(b["meta"], label=ov.get("label", b["meta"]["label"]), conf=ov.get("conf", b["meta"].get("conf")))
        if "section" in ov: b["section"] = rect_section(*ov["section"])
    if b.get("mat") == "timber_existing": b["mat"] = "timber"
    if b.get("mat") == "existing_tile": b["mat"] = "tile"
    return b


def _sub_member(a, A, d, lo, hi, cat, suffix):
    b = dict(a)
    b["A"] = v3add(A, v3mul(d, lo)); b["B"] = v3add(A, v3mul(d, hi))
    b["id"] = a["id"] + suffix
    b["cat"] = cat
    if cat == "demolition" and suffix:
        b["meta"] = dict(a["meta"], label=a["meta"]["label"] + " — end cut back", plain_label="Old roof timber cut back")
    return b


def diff_covers(bc, tc):
    """roof covering pieces: kept where the same plane is covered in both states (convex intersections)"""
    out = []
    for layer in ("tiles", "membrane"):
        B = [a for a in bc if a["layer"] == layer]; T = [a for a in tc if a["layer"] == layer]
        for b in B:
            same = [t for t in T if t["pkey"] == b["pkey"]]
            keep, rest = [], [b["poly"]]
            for t in same:
                inter = clip_convex(b["poly"], poly_halfplanes(t["poly"]))
                if inter and abs(area(inter)) > 1e-4: keep.append(inter)
                nxt = []
                for P in rest: nxt.extend(convex_minus(P, poly_halfplanes(t["poly"])) if clip_convex(P, poly_halfplanes(t["poly"])) else [P])
                rest = nxt
            for k, P in enumerate(keep):
                out.append(dict(b, poly=P, id=f"{b['id']}k{k}", cat="existing"))
            for k, P in enumerate(rest):
                if abs(area(P)) < 1e-4: continue
                out.append(dict(b, poly=P, id=f"{b['id']}d{k}", cat="demolition",
                                meta=dict(b["meta"], plain_label="Old roof tiles stripped where the new roof joins")))
        for t in T:
            same = [b for b in B if b["pkey"] == t["pkey"]]
            rest = [t["poly"]]
            for b in same:
                nxt = []
                for P in rest: nxt.extend(convex_minus(P, poly_halfplanes(b["poly"])) if clip_convex(P, poly_halfplanes(b["poly"])) else [P])
                rest = nxt
            for k, P in enumerate(rest):
                if abs(area(P)) < 1e-4: continue
                mat = "tile" if layer == "tiles" else "membrane"
                out.append(dict(t, poly=P, id=f"{t['id']}n{k}", cat="new", mat=mat))
    return out


def diff_battens(bb, tb, covers):
    """battens regenerated per classified tile piece"""
    out = []
    by_plane = {}
    for c in covers:
        by_plane.setdefault((c["plane"].id, c["cat"]), (c["plane"], []))[1].append(c["poly"])
    proto = {a["plane"].id: a for a in bb + tb}
    for (pid, cat), (pl, polys) in by_plane.items():
        if pid not in proto: continue
        m = battens_on(pl, polys)
        if not m: continue
        a = dict(proto[pid]); a["mesh"] = m; a["cat"] = cat; a["id"] = f"{a['id']}-{cat[:4]}"
        if cat == "new": a["mat"] = "batten"
        out.append(a)
    return out


def battens_on(pl, pieces, gauge=0.100, w=0.050, t=0.025):
    class _S: pass
    s = _S(); s.plane_pieces = lambda q: pieces
    return R.battens(s, pl, gauge, w, t)


# ======================================================================================== staging
def stage_atoms(atoms, spec, lv, version_kind):
    """fill meta stage_in/stage_out/seq/seq_out/category for every atom"""
    ST = spec["staging"]
    for a in atoms:
        m = a["meta"] = dict(a["meta"])
        cat = a.get("cat", "existing")
        if version_kind != "proposal":
            m.update(stage_in=1, stage_out=None, seq=0.0, seq_out=None, category="existing")
            continue
        if cat == "existing":
            m.update(stage_in=1, stage_out=None, seq=0.0, seq_out=None, category="existing")
        elif cat == "demolition":
            st, sq = demo_stage(a, ST)
            m.update(stage_in=1, stage_out=st, seq=0.0, seq_out=sq, category="demolition")
        else:
            ph = a.get("phase", "existing")
            if ph == "existing": ph = phase_from_group(a)
            st, sq = ST["phases"].get(ph, ST["phases"]["default"])
            if a.get("seq") is not None and a["kind"] == "slab": sq = a["seq"]
            if a.get("seq_bias"): sq = min(0.99, sq + a["seq_bias"])
            m.update(stage_in=st, stage_out=None, seq=sq, seq_out=None, category="finish" if ph in ST.get("finish_phases", []) else "new")
    return atoms


def phase_from_group(a):
    g = a["meta"]["group"]
    return {"fitting": "fitting", "window": "window", "door": "door", "roof_cover": "tiles", "slab_layer": "slab",
            "deck": "deck", "joist": "joist", "steel": "steel_gf", "lintel": "pad_gf", "wall_plate": "plate", "wall_outer": "gf_wall", "wall_inner": "gf_wall",
            "ceiling_joist": "ceiling", "rooflight": "rooflight"}.get(g, "default")


def demo_stage(a, ST):
    for rule in ST.get("demolition_overrides", []):
        if re.search(rule["match"], a["id"]): return rule["stage"], rule["seq"]
    g = a["meta"]["group"]; s = a["meta"].get("storey")
    order = ST["demolition_seq"]
    sq = order.get(g, order.get("default", 0.5))
    if s == "first" and g.startswith("wall"): sq = order.get("first_walls", sq)
    if s == "roof": sq = order.get("roof", sq)
    if a.get("panel"): sq = order.get("panel", sq)
    return ST.get("demolition_stage", 2), sq


# ======================================================================================== walls: finishing touches after the diff
def finish_walls(atoms, spec, lv, version_kind):
    """bases, lifts, linings z-range, cavity fill, lintels, studs; returns extra atoms"""
    extra = []
    ST = spec["staging"]
    for a in atoms:
        if a["kind"] != "wall": continue
        W = a["wall"]
        m = a["meta"]
        isnew = m.get("category") in ("new", "finish") and not a.get("infill")
        L = W.layers()
        if W.ckey in ("cav337_new", "block_int") and W.storey == "ground" and isnew and W.z0 > lv.found_top - 0.01 and W.z0 < 0.05:
            W.z0 = lv.found_top
        # room-side linings: floor..ceiling of the storey (raking walls: up to the top)
        f_, c_ = (lv.ffl - 0.025, lv.gclg) if W.storey == "ground" else (lv.ff, lv.fclg)
        for l in L:
            if l.get("z") == "room":
                # row 179: a raking wall under a vaulted room (the porch) is lined up to its raking top, not to the flat ceiling
                # line (the block and insulation showed above 2.43 in the porch vault)
                vr = spec.get("porch_vault", {}).get("rect")
                mid = W.point((W.ua + W.ub) / 2, 0)
                vaulted = bool(vr) and vr[0] - 0.4 <= mid[0] <= vr[2] + 0.4 and vr[1] - 0.4 <= mid[1] <= vr[3] + 0.4
                # (vaulted porch walls: lined up to the vault lining's underside, i.e. the raking top less the vault build-up)
                pv = spec.get("porch_vault", {})
                top = c_          # (the porch vault walls: lining above 2.43 waits for a raking lining layer; reported, not faked)
                if l["key"] == "plaster_out" and W.storey == "ground": top = min(W.z1, lv.ff)     # through the floor zone: floors meet it
                W.layer_z[l["key"]] = (f_, top)
        if W.ckey == "cav337_new":
            W.layer_z["pir"] = (max(W.z0, lv.cavity_fill_top), W.z1)
            if W.storey == "ground" and isnew:
                cav = [l for l in layer_stack(W.ckey, W.t) if l["key"] in ("cavity", "pir")]
                o0, o1 = min(l["o0"] for l in cav), max(l["o1"] for l in cav)
                c0, c1 = W.c_of(o0), W.c_of(o1)
                P = [W.point(W.ua, c0), W.point(W.ub, c0), W.point(W.ub, c1), W.point(W.ua, c1)]
                meta = M("wall_cavity", "ground", "Cavity fill min.225mm below dpc", "4915.3A section A-A", "exact", "Concrete fill at the bottom of the cavity", False)
                extra.append(atom(f"{W.id}-cavfill", "prism", "cavfill", meta, sig=sig_of("cf", P), poly=P, z0=W.z0, z1=lv.cavity_fill_top,
                                  mat="concrete", cat="new", wall_ref=W.id))
        # lifts (course bands) for new walls; existing walls are one piece per layer
        if isnew and not a.get("infill"):
            W._zband = (lv.dpc, lv.ff) if W.storey == "ground" else (lv.ff, lv.plate)
            if W.ckey in ("stud", "ashlar"): W._zband = (W.z0, W.z1)
        if isnew or a.get("infill"):
            step = ST.get("lift_courses", 9) * 0.075
            z = lv.dpc; lifts = [z]
            while z + step < W.z1 - 0.1: z += step; lifts.append(round(z, 4))
            W.lifts = [l for l in lifts if W.z0 + 0.1 < l < W.z1 - 0.1]
        else:
            W.lifts = []
        if a.get("infill"):
            for l in L: pass
    return extra


def lintel_atoms(atoms, spec, lv):
    """lintels over the openings of new walls and the new openings of kept walls"""
    out = []
    LT = spec.get("lintels", {})
    for a in atoms:
        if a["kind"] != "wall": continue
        W = a["wall"]; cat = a["meta"].get("category")
        ops = []
        if cat in ("new",) and not a.get("infill"): ops = list(W.openings)
        elif cat == "existing": ops = list(getattr(W, "openings_new", []))
        for o in ops:
            if o["id"] in LT.get("skip", []): continue
            if (W.ub - W.ua) < (o["u1"] - o["u0"]) + 0.1: continue        # the piece is all opening: nothing to bear on
            txt = o.get("lintel") or LT.get("by_opening", {}).get(o["id"])
            if not txt:
                txt = LT.get("default_cavity" if W.ckey in ("cav337_new", "cav_existing") else "default_internal")
            if not txt: continue
            L = layer_stack(W.ckey, W.t)
            core = [l for l in L if not l.get("lining")]
            brg = 0.15
            u0, u1 = o["u0"] - brg, o["u1"] + brg
            z = o["z1"]
            meshes, holes = [], []
            if "concrete" in txt.lower():
                h = 0.14; wd = 0.10
                o_mid = W.t / 2
                for (oa, ob) in [(o_mid - wd / 2, o_mid + wd / 2)] if W.ckey not in ("cav337_new", "cav_existing") else [(core[-1]["o0"], core[-1]["o1"])]:
                    c0, c1 = W.c_of(oa), W.c_of(ob)
                    P = [W.point(u0, c0), W.point(u1, c0), W.point(u1, c1), W.point(u0, c1)]
                    meshes.append(prism(P, z, z + h)); holes.append((u0, u1, z, z + h, oa, ob))
                mat = "concrete"
            else:
                h = 0.215 if "CH" in txt else 0.150
                outer = core[0]; inner = core[-1]
                oc0, oc1 = outer["o1"], inner["o0"]           # cavity zone
                # outer toe plate, inner box, sloped web over the cavity (Catnic-type steel cavity lintel)
                for (oa, ob, zb, zt) in [(outer["o0"] + 0.01, outer["o1"], z, z + 0.006), (inner["o0"], inner["o1"], z, z + h)]:
                    c0, c1 = W.c_of(oa), W.c_of(ob)
                    P = [W.point(u0, c0), W.point(u1, c0), W.point(u1, c1), W.point(u0, c1)]
                    meshes.append(prism(P, zb, zt))
                # web: a slab from the outer leaf's inner face at the toe up to the inner leaf top
                ca, cb = W.c_of(oc0), W.c_of(oc1)
                p0a, p1a = W.point(u0, ca), W.point(u1, ca)
                p0b, p1b = W.point(u0, cb), W.point(u1, cb)
                web = [(p0a[0], p0a[1], z), (p1a[0], p1a[1], z), (p1b[0], p1b[1], z + h - 0.006), (p0b[0], p0b[1], z + h - 0.006),
                       (p0a[0], p0a[1], z + 0.006), (p1a[0], p1a[1], z + 0.006), (p1b[0], p1b[1], z + h), (p0b[0], p0b[1], z + h)]
                meshes.append(hexa(web))
                holes += [(u0, u1, z, z + 0.006, outer["o0"], outer["o1"]), (u0, u1, z, z + h, oc0, inner["o1"])]
                mat = "lintel_galv"
            for hh in holes: W.holes.append(hh)
            phase = "lintel_gf" if W.storey == "ground" else "lintel_ff"
            meta = M("lintel", W.storey, f"{o['id']}: {txt}", dref(o.get("src") or W.meta.get("src", ""), W.storey), "exact" if o.get("lintel") else "assumed",
                     "Lintel over the opening", False)
            out.append(atom(f"L-{slug(W.id)}-{slug(o['id'])}", "mesh", phase, meta, sig=sig_of("lintel", W.id, o["id"]), mesh=merge_meshes(meshes),
                            mat=mat, cat="new", head=z, top=z + h, host=W))
            if a["meta"].get("category") == "new" or a.get("infill") is None:
                W.lifts = sorted(set([round(l, 4) for l in W.lifts] + ([round(z, 4), round(z + h, 4)] if a["meta"].get("category") == "new" else [])))
                if a["meta"].get("category") == "new": W.__dict__.setdefault("_fixed", set()).update({round(z, 4), round(z + h, 4)})
    return out


def stud_atoms(atoms, lv):
    out = []
    for a in atoms:
        if a["kind"] != "wall": continue
        W = a["wall"]
        C = CONSTRUCTIONS[W.ckey]
        if "studs" not in C or a["meta"].get("category") == "demolition": continue
        sd = C["studs"]
        L = layer_stack(W.ckey, W.t)
        core = next(l for l in L if l["key"] == "core")
        c0, c1 = W.c_of(core["o0"]), W.c_of(core["o1"])
        sp = sd["spacing"] or 0.4
        z0, z1 = W.z0, W.z1
        meshes_s = []
        ua_, ub_ = max(W.end_u("a", c0), W.end_u("a", c1)), min(W.end_u("b", c0), W.end_u("b", c1))
        n = max(1, int((ub_ - ua_ - sd["w"]) / sp))
        us = [ua_ + sd["w"] / 2 + k * (ub_ - ua_ - sd["w"]) / n for k in range(n + 1)]
        hw = sd["w"] / 2
        for o in W.openings:
            us += [o["u0"] - hw, o["u1"] + hw]
        us = sorted(u for u in us if ua_ + hw - 1e-6 <= u <= ub_ - hw + 1e-6)
        ded = []
        for u in us:
            if ded and u - ded[-1] < sd["w"] + 0.002: continue
            ded.append(u)
        us = ded
        for u in us:
            if any(o["u0"] - hw < u < o["u1"] + hw - 1e-6 and not (abs(u - (o["u0"] - hw)) < 1e-6 or abs(u - (o["u1"] + hw)) < 1e-6) for o in W.openings): continue
            top = min(z1, W.top_at(u)) - sd["w"]
            P = [W.point(u - sd["w"] / 2, c0), W.point(u + sd["w"] / 2, c0), W.point(u + sd["w"] / 2, c1), W.point(u - sd["w"] / 2, c1)]
            meshes_s.append(prism(P, z0 + sd["w"], top))
        for (zz0, zz1) in [(z0, z0 + sd["w"])] + ([(z1 - sd["w"], z1)] if not W.profile else []):
            for (sa, sb) in ([(ua_, ub_)] if zz0 > z0 else G_interval_minus([(ua_, ub_)], [(o["u0"], o["u1"]) for o in W.openings if o["z0"] <= z0 + 0.01])):
                P = [W.point(sa, c0), W.point(sb, c0), W.point(sb, c1), W.point(sa, c1)]
                meshes_s.append(prism(P, zz0, zz1))
        for o in W.openings:
            if o["z1"] < z1 - 0.1:
                P = [W.point(o["u0"], c0), W.point(o["u1"], c0), W.point(o["u1"], c1), W.point(o["u0"], c1)]
                meshes_s.append(prism(P, o["z1"], o["z1"] + 0.045))
        meta = M("wall_inner", W.storey, sd["label"], a["meta"]["drawing"], a["meta"]["conf"], "Timber studs of the partition", True)
        b = atom(f"{W.id}-studs", "mesh", a["phase"], meta, sig=sig_of("studs", W.id), mesh=merge_meshes(meshes_s), mat="timber", cat=a.get("cat"))
        b["meta"] = dict(meta, **{k: a["meta"].get(k) for k in ("stage_in", "stage_out", "seq", "seq_out", "category")})
        out.append(b)
    return out


# ======================================================================================== joins and lifetimes
def lifetime(m, N):
    si = m.get("stage_in", 1); so = m.get("stage_out") or (N + 1)
    return si, so


def coexist_fn(N):
    def f(A, B):
        a0, a1 = A._life; b0, b1 = B._life
        return min(a1, b1) > max(a0, b0)
    return f


# ======================================================================================== parts
def contract_props(a, **over):
    m = a["meta"]
    p = dict(element=a["id"], stage_in=m.get("stage_in", 1), seq=round(float(m.get("seq", 0.0)), 4), category=m.get("category", "existing"),
             group=m["group"], storey=m["storey"], label=m["label"], plain_label=m.get("plain_label") or "", drawing=m.get("drawing", ""),
             conf=m.get("conf", "scaled"), collide=bool(m.get("collide", False)))
    if m.get("stage_out"): p["stage_out"] = int(m["stage_out"]); p["seq_out"] = round(float(m.get("seq_out") or 0.5), 4)
    if a.get("as_built"): p["as_built"] = True
    if a.get("loft"): p["loft"] = True
    if a.get("no_regs") or a.get("loft"): p["no_regs"] = True       # owner's / as-built items: no drawing spec, no regs mapping
    if a.get("provenance"): p["provenance"] = a["provenance"]
    p.update(over)
    return p


def lift_stage_seq(a, z, spec, li=0, nlayers=1):
    """(stage, seq) of the course of new wall `a` that starts at height z: the substructure (below the dpc) in its own
    stage when the staging has one, otherwise the wall's stage; seq rises with height over the stage's band, so every
    wall of a stage lays the same course at the same time and a member set in a wall goes in between the courses under
    it and over it (CORRECTIONS-LOG 117)"""
    W = a["wall"]; m = a["meta"]
    ph = spec["staging"]["phases"].get("substructure")
    dpc = spec.get("levels", {}).get("dpc", -0.032)
    if ph and sub_eligible(a) and z < dpc - 1e-4:
        st, base, span, (z0, z1) = ph[0], ph[1], 0.8, (W.z0, dpc)
    else:
        st, base, span = m.get("stage_in", 1), m.get("seq", 0.0) or 0.0, m.get("seq_span", 0.85)
        z0, z1 = getattr(W, "_zband", None) or (W.z0, W.z1)
    f = min(1.0, max(0.0, (z - z0) / max(1e-6, z1 - z0)))
    return st, round(base + span * (0.95 * f + 0.004 * li / max(1, nlayers)), 4)


def sub_eligible(a):
    W = a.get("wall")
    return (W is not None and a["meta"].get("category") == "new" and not a.get("infill") and W.storey == "ground"
            and W.ckey in ("cav337_new", "block_int"))


def substructure(a, k, spec, li=0, nlayers=1):
    """(stage, seq) for lift k of a new ground-floor masonry wall when the staging builds the substructure (the lifts
    below the dpc) in its own stage (with the drains) before the oversite slab; None otherwise (CORRECTIONS-LOG 117)"""
    ph = spec["staging"]["phases"].get("substructure")
    W = a.get("wall")
    if not ph or W is None or a["meta"].get("category") != "new" or a.get("infill") or W.storey != "ground": return None
    if W.ckey not in ("cav337_new", "block_int"): return None
    dpc = spec.get("levels", {}).get("dpc", -0.032)
    lines = [W.z0] + [l for l in W.lifts if W.z0 < l < W.z1] + [W.z1]
    if k + 1 >= len(lines) or lines[k + 1] > dpc + 1e-3: return None
    nsub = len([z for z in lines[1:] if z <= dpc + 1e-3])
    return ph[0], round(ph[1] + 0.8 * (k + 0.3 * li / max(1, nlayers)) / max(1, nsub), 4)


def wall_seq(meta, lift, nl, li, nlayers):
    span = meta.get("seq_span", 0.85)
    return round(meta.get("seq", 0.0) + span * (lift + 0.3 * li / max(1, nlayers)) / max(1, nl), 4)


def parts_of(a, ctx):
    """-> list of part dicts: name, mat, props, mesh (V,F) world OR local mesh + matrix + key, uv"""
    k = a["kind"]
    out = []
    if k == "wall":
        W = a["wall"]
        L = W.layers()
        new_infill = getattr(W, "new_infill", False)
        for (li, lay, lift, nl, mesh) in wall_parts(W):
            name = f"{a['id']}_L{li}_{lay['group']}_lift{lift}"
            mat = lay["mat"]
            if new_infill: mat = (NEW_MAT_INNER if lay["group"] == "wall_inner" else NEW_MAT).get(mat, mat)
            for pre, mm in ctx["spec"].get("wall_material_overrides", {}).items():
                if a["id"].startswith(pre) and a["meta"].get("category") == "existing": mat = mm.get(mat, mat)
            props = contract_props(a, group=lay["group"], layer=li, lift=lift, element_label=a["meta"]["label"], label=lay["label"])
            if lay.get("plain"): props["plain_label"] = lay["plain"]
            if lay.get("conf"): props["conf"] = lay["conf"]
            m = a["meta"]
            if m.get("category") in ("new",) and lay.get("finish"):
                st, sq = ctx["spec"]["staging"]["phases"]["lining"]
                props.update(stage_in=st, seq=sq, category="finish")
            elif m.get("stage_out"):
                props["seq_out"] = round(float(m.get("seq_out") or 0.5), 4)
            elif m.get("category") in ("new", "finish"):
                lines = [W.z0] + [l for l in W.lifts if W.z0 < l < W.z1] + [W.z1]
                props["stage_in"], props["seq"] = lift_stage_seq(a, lines[min(lift, len(lines) - 1)], ctx["spec"], li, len(L))
                za = a.get("lift_stage_after")
                if za and lines[min(lift, len(lines) - 1)] >= za[0] - 1e-4:
                    props["stage_in"], props["seq"] = za[1], round(min(0.99, za[2] + 0.3 * (lines[min(lift, len(lines) - 1)] - za[0]) / max(0.1, W.z1 - za[0])), 4)
            props["collide"] = lay["group"] in ("wall_outer", "wall_inner") or (lay["group"] == "wall_lining" and False)
            out.append(dict(name=name, mat=mat, props=props, mesh=mesh, uv="world"))
        return out
    if k == "prism":
        return [dict(name=a["id"], mat=a["mat"], props=contract_props(a), mesh=prism(a["poly"], a["z0"], a["z1"]), uv="world")]
    if k == "slab":
        mesh = ctx["clip_slab"](a)
        if not mesh: return []
        return [dict(name=a["id"], mat=a["mat"], props=contract_props(a), mesh=mesh, uv="world")]
    if k == "mesh":
        return [dict(name=a["id"], mat=a["mat"], props=contract_props(a), mesh=a["mesh"], uv=("band",) + tuple(a["uv_band"]) if a.get("uv_band") else "world")]
    if k == "batten_set":
        return [dict(name=a["id"], mat=a["mat"], props=contract_props(a), mesh=a["mesh"], uv=None)]
    if k == "cover":
        pl = a["plane"]
        pts = R.lift(pl, a["poly"])
        from hb_geom import prism_varz
        c = pl.cos
        # layers offset vertically (plumb edges): nothing pushes past an abutment wall or the eaves line
        if a["layer"] == "tiles": mesh = prism_varz(a["poly"], lambda p: pl.z(p) - R.COVER["tiles"] / c, lambda p: pl.z(p))
        else: mesh = prism_varz(a["poly"], lambda p: pl.z(p) - R.COVER_T / c, lambda p: pl.z(p) - (R.COVER_T - R.COVER["membrane"]) / c)
        uv = ("roof", pl.e, pl.d, pl.cos)
        return [dict(name=a["id"], mat=a["mat"], props=contract_props(a), mesh=mesh, uv=uv if a["layer"] == "tiles" else None)]
    if k == "member":
        A3, B3 = a["A"], a["B"]
        if a.get("clip_to_walls"):
            segs = ctx["clip_member"](a)
        else:
            segs = [(A3, B3)]
        res = []
        for si, (P0, P1) in enumerate(segs):
            secs = [(a["section"], a["mat"])] + [(s, m) for s, m in a.get("extra_sections", []) if s]
            by_mat = {}
            for s, m in secs: by_mat.setdefault(m, []).append(s)
            for mi, (mat, ss) in enumerate(by_mat.items()):
                X = v3sub(P1, P0); Lm = v3len(X)
                if Lm < 0.02: continue
                Mx = frame_matrix(P0, X)
                tanp = None
                if a.get("plumb"):
                    Xu = v3unit(X); h = math.hypot(Xu[0], Xu[1])
                    Z = (Mx[0][2], Mx[1][2], Mx[2][2])
                    if h > 1e-6: tanp = (Z[0] * Xu[0] / h + Z[1] * Xu[1] / h) / h
                meshes = []
                for s in ss:
                    sec = s
                    if a.get("raise_section"): sec = [(y, z) for (y, z) in s]
                    meshes.append(extrude_section(sec, Lm, (tanp, tanp) if tanp else None))
                V, F = merge_meshes(meshes)
                key = (mat, tuple(tuple((round(y, 4), round(z, 4)) for y, z in s) for s in ss), round(Lm, 3), round(tanp or 0, 4))
                nm = a["id"] + (f"_{si}" if len(segs) > 1 else "") + (f"_{mat}" if len(by_mat) > 1 else "")
                res.append(dict(name=nm, mat=mat, props=contract_props(a, member=si) if len(segs) > 1 else contract_props(a),
                                local=(V, F), matrix=Mx, key=key, uv=None))
        return res
    if k == "fixture":
        return fixture_parts(a)
    return out


def _vf(p):            # drawing (x, y, z) -> viewer (x, z, -y)
    return [round(p[0], 4), round(p[2], 4), round(-p[1], 4)]


def door_swing(a, W, o):
    """(hinge end 'a'|'b', swing side +1 (toward +n) | -1, pair, conf, note) from the traced hinge / swing words
    ("rear end (y 1.074)", "inward, into hall (+y)", "pair, into conservatory (+y)", "into en-suite")"""
    hinge, swing = (o.get("hinge") or ""), (o.get("swing") or "")
    pair = "pair" in swing.lower()
    conf, notes = "scaled", []
    m = re.search(r"\b([xy])\s*(-?\d+(?:\.\d+)?)", hinge)
    if m:
        ax, v = (0 if m.group(1) == "x" else 1), float(m.group(2))
        pa, pb = W.point(o["u0"], 0), W.point(o["u1"], 0)
        end = "a" if abs(pa[ax] - v) <= abs(pb[ax] - v) else "b"
    else:
        end = "a"; conf = "assumed"; notes.append("hinge side not drawn: assumed at the first jamb")
    side = None
    m = re.search(r"\(([+-])([xy])\)", swing)
    if m:
        vec = (1.0, 0.0) if m.group(2) == "x" else (0.0, 1.0)
        if m.group(1) == "-": vec = (-vec[0], -vec[1])
        side = 1 if dot(W.n, vec) > 0 else -1
    else:
        mid = (o["u0"] + o["u1"]) / 2
        words = [w for w in re.findall(r"[a-z\-]+", swing.lower()) if w not in ("into", "inward", "outward", "pair", "the")]
        for sgn in (1, -1):
            p = W.point(mid, sgn * (W.t / 2 + 0.3))
            for name, poly in a.get("rooms", []):
                if point_in_poly(p, poly) and (not words or any(w in name.lower() for w in words)):
                    side = sgn; break
            if side: break
        if side is None:
            for sgn in (1, -1):        # an outside door opens in: towards the side that has a room
                p = W.point(mid, sgn * (W.t / 2 + 0.3))
                if any(point_in_poly(p, poly) for _, poly in a.get("rooms", [])): side = sgn; break
        if side is None: side = 1
        if not m: conf = "assumed" if not swing else conf
        if not swing: notes.append("swing not drawn: assumed into the room")
    return end, side, pair, conf, "; ".join(notes)


def fixture_parts(a):
    W, o = a["wall"], a["op"]
    c = a["c_plane"]
    kind = o["kind"]
    f = 0.06 if kind != "bifold" else 0.07
    dep = 0.07 if not a.get("internal") else 0.035
    u0, u1, z0, z1 = o["u0"], o["u1"], o["z0"], o["z1"]
    def bx(ua, ub, za, zb, ca, cb):
        P = [W.point(ua, ca), W.point(ub, ca), W.point(ub, cb), W.point(ua, cb)]
        return prism(P, za, zb)
    fr, gl = [], []
    leaves = []                       # (meshes by material, hinge (u, c), swing sign, extra props)
    out_sign = 1 if W.out > 0 else -1          # +c is outside when out=+1
    zsill = None
    is_door = kind in ("door", "bifold")
    end, side, pair, dconf, dnote = door_swing(a, W, o) if is_door else ("a", 1, False, "", "")
    if kind == "window" and not a.get("internal"):
        zsill = z0; z0 = z0 + 0.035            # the sill board sits in the opening; the frame stands on it
    if kind == "window" or kind == "bifold" or (kind == "door" and not a.get("internal")):
        # outer frame (70 mm uPVC / aluminium profile)
        fr.append(bx(u0, u1, z1 - f, z1, c - dep / 2, c + dep / 2))
        zb = z0 + (f if kind == "window" else 0.02)
        fr.append(bx(u0, u1, z0, zb, c - dep / 2, c + dep / 2))
        fr.append(bx(u0, u0 + f, zb, z1 - f, c - dep / 2, c + dep / 2)); fr.append(bx(u1 - f, u1, zb, z1 - f, c - dep / 2, c + dep / 2))
        n = a["nlights"] if not (kind == "door" and pair) else 2          # a pair of doors: two leaves
        fan = kind == "window" and (z1 - z0) > 0.85            # top lights (fanlights) over casements, as on the house
        zt = z1 - f - 0.30 if fan else None
        if fan: fr.append(bx(u0 + f, u1 - f, zt - 0.03, zt + 0.03, c - dep / 2, c + dep / 2))
        bays = [(u0 + f + (u1 - u0 - 2 * f) * i / n, u0 + f + (u1 - u0 - 2 * f) * (i + 1) / n) for i in range(n)]
        if kind != "bifold":
            for i in range(1, n):
                x = bays[i][0]; fr.append(bx(x - 0.035, x + 0.035, zb, z1 - f, c - dep / 2, c + dep / 2))     # mullions
        glass = kind != "door"
        sw_ = 0.05 if kind != "bifold" else 0.06                   # sash profile, stepped 15 mm proud of the frame
        cs = c + out_sign * 0.015
        for bi, (xa, xb) in enumerate(bays):
            lf, lg = [], []
            tgt_f = lf if is_door else fr
            tgt_g = (lg if is_door else gl) if glass else tgt_f
            for (ya, yb) in ([(zb, zt - 0.03), (zt + 0.03, z1 - f)] if fan else [(zb + (0.004 if is_door else 0), z1 - f - (0.004 if is_door else 0))]):
                gap = 0.004 if is_door else 0.0                       # a leaf stands clear of its frame
                xa2 = xa + (0.035 if (xa > u0 + f + 1e-6 and not is_door) else 0) + gap
                xb2 = xb - (0.035 if (xb < u1 - f - 1e-6 and not is_door) else 0) - gap
                tgt_f.append(bx(xa2, xb2, ya, ya + sw_, cs - 0.03, cs + 0.03)); tgt_f.append(bx(xa2, xb2, yb - sw_, yb, cs - 0.03, cs + 0.03))
                tgt_f.append(bx(xa2, xa2 + sw_, ya + sw_, yb - sw_, cs - 0.03, cs + 0.03)); tgt_f.append(bx(xb2 - sw_, xb2, ya + sw_, yb - sw_, cs - 0.03, cs + 0.03))
                tgt_g.append(bx(xa2 + sw_, xb2 - sw_, ya + sw_, yb - sw_, cs - 0.012, cs + 0.012))
            if is_door:
                leaves.append(dict(lf=lf, lg=lg, ua=xa + gap, ub=xb - gap, cf=(cs - 0.03, cs + 0.03), bay=bi, n=n))
        if kind == "window" and not a.get("internal"):
            # external sill: white uPVC, projecting 40 mm past the brick face
            L_ = layer_stack(W.ckey, W.t)
            face = W.c_of(L_[0]["o0"]) if out_sign > 0 else W.c_of(L_[0]["o0"])
            ca, cb = sorted((c - out_sign * dep / 2, face + out_sign * 0.04))
            sill = [bx(u0, u1, zsill, zsill + 0.035, ca, cb)]
            # the internal window board (FIN-WBOARD 25 mm MDF, white satin) where the inside is a finished room
            import hb_joinery as J
            cl_, ch_ = W.full_extent_c(); c_in = cl_ if out_sign > 0 else ch_
            mid = W.point((u0 + u1) / 2, c_in - out_sign * 0.3)
            room_in = next((nm_ for nm_, poly in a.get("rooms", []) if point_in_poly(mid, poly)), None)
            if room_in and "conservator" not in room_in.lower():
                a = dict(a, _wboard=J.window_board(W, u0, u1, zsill + 0.035 - 0.025, c - out_sign * dep / 2, c_in, -out_sign))
    else:
        # internal door to the joinery bar (CORRECTIONS-LOG 183/191; hb_joinery): a lining the full depth of the finished wall,
        # 12 x 38 stops on the closing side, a 4-panel shaker leaf (FIN-DOOR "white 4-panel shaker"), 3 hinges, lever on rose
        # both faces, moulded architraves mitred round both faces
        import hb_joinery as J
        fw = 0.03
        cl_, ch_ = W.full_extent_c()
        fr.append(bx(u0, u1, z1 - fw, z1, cl_, ch_))
        fr.append(bx(u0, u0 + fw, z0, z1 - fw, cl_, ch_)); fr.append(bx(u1 - fw, u1, z0, z1 - fw, cl_, ch_))
        sc_ = -side                                              # the stops stand on the side the leaf closes against
        s0, s1 = sorted((c + sc_ * 0.0175, c + sc_ * (0.0175 + 0.038)))
        stops = [J.box_uc(W, u0 + fw, u0 + fw + 0.012, z0, z1 - fw, s0, s1), J.box_uc(W, u1 - fw - 0.012, u1 - fw, z0, z1 - fw, s0, s1),
                 J.box_uc(W, u0 + fw, u1 - fw, z1 - fw - 0.012, z1 - fw, s0, s1)]
        a = dict(a, _joinery=dict(stops=stops, arch=[J.architrave(W, u0 + fw, u1 - fw, z0, z1 - fw, cl_, -1),
                                                      J.architrave(W, u0 + fw, u1 - fw, z0, z1 - fw, ch_, 1)]))
        la, lb = u0 + fw + 0.003, u1 - fw - 0.003
        spans = [(la, (la + lb) / 2 - 0.0015), ((la + lb) / 2 + 0.0015, lb)] if pair else [(la, lb)]
        for k_, (pa_, pb_) in enumerate(spans):
            leaves.append(dict(lf=J.shaker_leaf(W, pa_, pb_, z0 + 0.008, z1 - fw - 0.003, c - 0.0175, c + 0.0175), lg=[], ua=pa_, ub=pb_,
                               cf=(c - 0.0175, c + 0.0175), bay=k_, n=len(spans), shaker=True))
    frame_mat = a.get("frame_mat") or {"bifold": "aluminium"}.get(kind, "upvc_white" if not a.get("internal") else "joinery")
    # spec_v1 doors_windows (row 178): each frame's colour from the signed schedule (outside face)
    sd = SPEC_DW.get(a["id"]) or SPEC_DW.get(a["id"].replace("-owner", ""))
    if sd:
        t_ = (sd.get("frame_outside") or "").lower()
        frame_mat = ("anthracite_upvc" if ("7016" in t_ or "anthracite" in t_) else "upvc_white" if ("9016" in t_ or "white upvc" in t_)
                     else "joinery" if "fin-door" in t_ else frame_mat)
        a = dict(a, sill_mat=frame_mat)
        if a.get("leaf_mat") or kind in ("door", "bifold"): a = dict(a, leaf_mat=frame_mat if not a.get("internal") else "joinery")
    leaf_mat = a.get("leaf_mat") or ("joinery" if a.get("internal") else ("aluminium" if kind == "bifold" else "upvc_white"))
    props = contract_props(a, part="frame")
    res = [dict(name=a["id"] + "_frame", mat=frame_mat, props=props, mesh=merge_meshes(fr), uv=None)]
    if a.get("_joinery"):
        jn = a["_joinery"]
        res.append(dict(name=a["id"] + "_stops", mat="joinery", props=contract_props(a, part="stops"), mesh=merge_meshes(jn["stops"]), uv=None))
        res.append(dict(name=a["id"] + "_architraves", mat="trim", props=contract_props(a, part="architraves", wall_dir=[round(W.d[0], 6), round(W.d[1], 6)]),
                        mesh=merge_meshes(jn["arch"]), uv=None))
    if a.get("_wboard"):
        res.append(dict(name="WB-" + a["id"].replace("F-", "O-", 1) + "_window_board", mat="wboard", props=contract_props(a, part="window_board", group="fitting",
                        plain_label="Window board (25 mm MDF, bullnose, white satin)"), mesh=a["_wboard"], uv=None))
    if kind == "window" and not a.get("internal"):
        res.append(dict(name=a["id"] + "_sill", mat=a.get("sill_mat") or frame_mat, props=contract_props(a, part="sill"), mesh=merge_meshes(sill), uv=None))
    if gl: res.append(dict(name=a["id"] + "_leaf", mat="glass", props=contract_props(a, part="glass"), mesh=merge_meshes(gl), uv=None))
    # door leaves: their own nodes with the hinge (CONTRACT: door leaves) so every door can be opened in the viewer
    zl = z0
    for L in leaves:
        k, n = L["bay"], L["n"]
        cface = L["cf"][1] if side > 0 else L["cf"][0]               # the face on the side it opens to
        sgn_n = side
        if kind == "bifold":
            # folds outward and stacks at the first jamb: even leaves hinge on their near edge, odd on their far edge
            out_side = out_sign
            cface = L["cf"][1] if out_side > 0 else L["cf"][0]
            sgn_n = out_side
            hinge_u = L["ua"] if k % 2 == 0 else L["ub"]
            t_ = L["cf"][1] - L["cf"][0]
            stack_u = u0 + f + (k + (0 if k % 2 == 0 else 1)) * (t_ + 0.004)
            slide = sub(W.point(stack_u, cface), W.point(hinge_u, cface))
        elif pair:
            hinge_u = L["ua"] if k == 0 else L["ub"]
            slide = None
        else:
            hinge_u = L["ua"] if end == "a" else L["ub"]
            slide = None
        e = W.d if hinge_u <= (L["ua"] + L["ub"]) / 2 else (-W.d[0], -W.d[1])     # from the hinge to the free edge
        s_vec = (W.n[0] * sgn_n, W.n[1] * sgn_n)
        rot90 = (-e[1], e[0])
        sign = 1 if dot(rot90, s_vec) > 0 else -1
        hp = W.point(hinge_u, cface)
        extra = dict(part="leaf", door_leaf=True, hinge=_vf((hp[0], hp[1], zl)), hinge_axis=[0.0, 1.0, 0.0], swing_deg=float(90 * sign),
                     door_group=a["id"], leaf_index=k, swing_conf=("typical" if kind == "bifold" else dconf))
        if slide is not None: extra["slide"] = [round(slide[0], 4), 0.0, round(-slide[1], 4)]
        if dnote and kind != "bifold": extra["swing_note"] = dnote
        if kind == "bifold": extra["swing_note"] = "bi-fold (typical — not drawn): opens outwards and stacks against the side wall at the dining end, keeping the kitchen side clear (Jack, 1 Nov 2026)"
        nm = a["id"] + (f"_leaf{k}" if len(leaves) > 1 else "_leaf")
        res.append(dict(name=nm, mat=leaf_mat, props=contract_props(a, **extra), mesh=merge_meshes(L["lf"]), uv=None, leaf=True))
        if L.get("shaker"):
            import hb_joinery as J
            hg, hd = J.door_ironmongery(W, L["ua"], L["ub"], z0 + 0.008, hinge_u, L["cf"][0], L["cf"][1], z1 - 0.03 - 0.003)
            res.append(dict(name=nm + "_hinges", mat="ironmongery", props=contract_props(a, part="hinges"), mesh=merge_meshes(hg), uv=None))
            res.append(dict(name=nm + "_handle", mat="ironmongery", props=contract_props(a, **dict(extra, part="handle")), mesh=merge_meshes(hd), uv=None, leaf=True))
        if L["lg"]:
            res.append(dict(name=nm + "_glass", mat="glass", props=contract_props(a, **dict(extra, part="leaf_glass")), mesh=merge_meshes(L["lg"]), uv=None, leaf=True))
    return res


def embed_new_members(atoms, N):
    """new steels, timber beams, padstones and lintels set into walls: holes in those walls; where the wall is
    existing, the pocket is cut out (a demolition part) at the stage the member goes in"""
    out = []
    walls = [a for a in atoms if a["kind"] == "wall"]
    for m in atoms:
        if m["meta"].get("category") != "new": continue
        if m["kind"] == "member" and m["meta"]["group"] in ("steel", "timber_beam"):
            from hb_geom import frame_matrix, apply_matrix
            A3, B3 = m["A"], m["B"]
            X = v3sub(B3, A3); L = v3len(X); Mx = frame_matrix(A3, X)
            pts = []
            for sec in [m["section"]] + [s_ for s_, mm in m.get("extra_sections", []) if s_]:
                V, F = extrude_section(sec, L); pts += apply_matrix(Mx, V)
        elif m["kind"] == "mesh" and (m["meta"]["group"] == "lintel" or m.get("embed")):
            pts = m["mesh"][0]
        else:
            continue
        ml = lifetime(m["meta"], N)
        for w in walls:
            W = w["wall"]
            if w is m.get("host_atom") or W is m.get("host"): continue
            wl = lifetime(w["meta"], N)
            if min(wl[1], ml[1]) <= max(wl[0], ml[0]): continue
            us = [u_of(W, p[:2]) for p in pts]; cs = [dot(sub(p[:2], W.a), W.n) for p in pts]; zs = [p[2] for p in pts]
            if max(cs) <= -W.t / 2 + 1e-3 or min(cs) >= W.t / 2 - 1e-3: continue
            u0, u1 = max(min(us), W.ua), min(max(us), W.ub)
            z0, z1 = max(min(zs), W.z0), min(max(zs), W.z1)
            if u1 - u0 < 2e-3 or z1 - z0 < 2e-3: continue
            o_lo = min(W.t / 2 - W.out * c for c in (min(cs), max(cs))); o_hi = max(W.t / 2 - W.out * c for c in (min(cs), max(cs)))
            o_lo, o_hi = max(o_lo, -1), min(o_hi, W.t + 1)
            W.holes.append((u0, u1, z0, z1, o_lo, o_hi))
            m.setdefault("embedded_in", []).append(w["id"])
            if w["meta"].get("category") == "existing":
                keys = [l["key"] for l in W.layers() if not l.get("void") and min(o_hi, l["o1"]) - max(o_lo, l["o0"]) > 1e-4]
                if not keys: continue
                Q = piece(W, u0, u1, z0, z1, pid=f"{W.id}~pocket-{m['id']}")
                Q.openings = []; Q.holes = []; Q.only_layers = keys
                meta = dict(w["meta"], label=f"existing walling cut out to take {m['id']} ({TYPICAL})", plain_label="Wall cut away for the beam",
                            category="demolition", stage_in=1, stage_out=m["meta"]["stage_in"], seq_out=max(0.0, m["meta"]["seq"] - 0.02))
                out.append(dict(w, id=Q.id, wall=Q, cat="demolition", meta=meta, panel=True))
    return out
