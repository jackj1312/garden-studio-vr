"""House generator core (pure Python): traced drawings (house_drawn.json, the trace format of
tools/plan/trace_drawing.py) + a version spec  ->  a STATE per version: a flat list of ATOMS (every physical item:
wall pieces, members, slabs, covers, fixtures, fittings), each with a geometric signature so two states can be
diffed generically (hb_stage.py). Nothing here is specific to one house: house facts live in the data and the spec.
Frame: drawing frame = Blender frame (x along the front, y into the house, z up from ground-floor FFL)."""
import math, re, copy
from hb_geom import (sub, add, mul, dot, unit, length, area, ccw, centroid, point_in_poly, box, prism, hexa, slab3d,
                     merge_meshes, rect_section, i_section, clip_convex, poly_halfplanes, convex_minus, interval_minus,
                     merge_intervals, seg_point_dist, clip_half, clip_segment_convex)
from hb_walls import Wall, classify_construction, layer_stack, CONSTRUCTIONS
import hb_roof as R

TYPICAL = "(typical — not from the drawings)"


def resolve_spec(o, defs, depth=0):
    """'@name' / '@name.key.0' references into spec['defs']; a reference to a list inside a list is spliced in"""
    if depth > 20: raise ValueError("reference loop")
    if isinstance(o, str) and o.startswith("@"):
        path = o[1:].split(".")
        v = defs[path[0]]
        for k in path[1:]: v = v[int(k)] if isinstance(v, list) else v[k]
        return resolve_spec(v, defs, depth + 1)
    if isinstance(o, list):
        out = []
        for x in o:
            r = resolve_spec(x, defs, depth + 1)
            if isinstance(x, str) and x.startswith("@") and isinstance(r, list): out.extend(r)
            else: out.append(r)
        return out
    if isinstance(o, dict):
        return {k: resolve_spec(v, defs, depth + 1) for k, v in o.items()}
    return o


def val(x):
    return x["v"] if isinstance(x, dict) and "v" in x else x


def conf_of(x, default="scaled"):
    c = x.get("conf") if isinstance(x, dict) else None
    c = (c or default).split()[0].strip(" ,;()").lower()
    return c if c in ("exact", "scaled", "assumed") else default


SHEETS = ["4915.2B", "4915.3A", "4915.4A", "4915.1"]
VIEWS = [("base wall layout", "base wall layout"), ("joist plan", "first floor joist plan"), ("roof plan", "roof plan"),
         ("east elev", "east elevation"), ("west elev", "west elevation"), ("north elev", "north elevation"),
         ("south elev", "south elevation"), ("A-A", "section A-A"), ("B-B", "section B-B"), ("C-C", "section C-C"),
         ("D-D", "section D-D"), ("E-E", "section E-E"), (" FF", "first floor plan"), (" GF", "ground floor plan"),
         ("notes", "construction notes")]


def dref(src, storey=None):
    if not src: return ""
    s = " " + src
    sheets = [n for n in SHEETS if n in s]
    if not sheets: return src[:60]
    views = []
    for k, n in VIEWS:
        if k in s and n not in views: views.append(n)
    if not views and storey in ("ground", "first") and sheets[0] in ("4915.2B", "4915.1"):
        views = ["ground floor plan" if storey == "ground" else "first floor plan"]
    return f"{sheets[0]} {views[0]}" if views else sheets[0]


def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "-", str(s)).strip("-")[:48]


def r3(x): return round(x, 3)


def sig_of(*vals):
    def f(v):
        if isinstance(v, float): return f"{v:.3f}"
        if isinstance(v, (list, tuple)): return "(" + ",".join(f(x) for x in v) + ")"
        return str(v)
    return "|".join(f(v) for v in vals)


def atom(id, kind, phase, meta, **geom):
    return dict(id=id, kind=kind, phase=phase, meta=meta, **geom)


def M(group, storey, label, drawing, conf, plain=None, collide=False, **kw):
    m = dict(group=group, storey=storey, label=label, plain_label=plain, drawing=drawing, conf=conf, collide=collide)
    m.update(kw)
    return m


# ======================================================================================== levels
class Levels:
    def __init__(self, V, spec):
        lv = V["levels"]
        self.ffl = val(lv["ground_ffl"]); self.ff = val(lv["first_ffl"])
        self.gclg = val(lv["ground_ceiling"]); self.fclg = val(lv["first_ceiling_z"])
        self.plate = val(lv["wall_plate_top"]); self.soffit = val(lv["eaves_soffit"])
        L = spec.get("levels", {})
        self.dpc = L.get("dpc", -0.032)
        self.found_top = L.get("foundation_top", -0.601)
        self.cavity_fill_top = L.get("cavity_fill_top", self.dpc - 0.225)
        self.existing_base = L.get("existing_wall_base", -0.60)
        self.existing_floor_bottom = L.get("existing_floor_bottom", -0.15)
        self.ground_zones = L.get("ground_zones", [])


# ======================================================================================== walls from the trace
OPENING_DATUM = {"shift": 0.0}


def opening_element_id(prefix, wall_id, op):
    # A corrected carrier may own a previously reviewed door, threshold and
    # opening. Preserve the issued ID independently of its current physical host.
    host = op.get("identity_host") or (wall_id.split("~")[0] if prefix == "F" else wall_id)
    return f"{prefix}-{slug(host)}-{slug(op['id'])}"


def opening_from(o, base_z):
    c, wdt = val(o.get("c")), val(o.get("w"))
    z0, z1 = val(o.get("sill_z")), val(o.get("head_z"))
    z0 = 0.0 if z0 is None else z0
    # BDS height chains run from the dpc line (32 mm below FFL): written sills and heads move down by that much;
    # a door sill at its floor stays at the floor (CORRECTIONS-LOG 122)
    sh = OPENING_DATUM["shift"]
    if sh:
        floor = base_z if base_z > 0.5 else 0.0
        if z0 > floor + 0.05: z0 += sh
        z1 += sh
    note = None
    if z0 < base_z - 1e-6:
        note = f"sill {z0} below the wall base {base_z}: taken as the floor (CORRECTIONS-LOG 99)"
        z0 = base_z
    return dict(id=o.get("id") or o.get("kind"), identity_host=o.get("identity_host"),
                retained_exterior_frame=o.get("retained_exterior_frame", False), kind=o.get("kind", "opening"), u0=c - wdt / 2, u1=c + wdt / 2, z0=z0, z1=z1,
                panes=o.get("panes"), leaf=val(o.get("leaf")), hinge=o.get("hinge"), swing=o.get("swing"),
                lintel=o.get("lintel"), src=o.get("src", ""), conf=conf_of(o), note=note, elev=o.get("elev"))


NEW_TOKENS = ("new 337", "new internal", "timber stud", "ashlar")


def read_walls(V, storey, all_existing=False, known_ids=()):
    out = []
    for w in V["storeys"][storey]["walls"]:
        x1, y1, x2, y2 = w["line"]
        t = val(w["t"])
        existing = all_existing or any(k in w["type"] for k in ("existing", "party", "ext'g")) or \
            (w["id"] in known_ids and not any(k in w["type"] for k in NEW_TOKENS))
        ck = classify_construction(w["type"], existing, t)
        W = Wall(w["id"], (x1, y1), (x2, y2), t, w["base_z"], w["top_z"], ck, 1, storey)
        W.meta = dict(type=w["type"], src=w.get("src", ""), conf=conf_of(w), note=w.get("note", ""), existing=existing)
        if "top_profile" in w:
            W.profile = sorted((abs(px - x1) if abs(x2 - x1) > abs(y2 - y1) else abs(px - y1), pz)
                               for px, pz in w["top_profile"]["pts_x_z"])
            W.meta["profile_src"] = w["top_profile"].get("src", "")
        for o in w.get("openings", []):
            W.openings.append(opening_from(o, W.z0))
        out.append(W)
    return out


def u_of(W, p):
    return dot(sub(p, W.a), W.d)


def parallel_overlap(a, b, tol=0.02):
    """interval of a (in a's u) covered by b's footprint, if parallel and overlapping across; else None"""
    if abs(abs(dot(a.d, b.d)) - 1) > 1e-3: return None
    off = abs(dot(sub(b.a, a.a), a.n))
    if off > (a.t + b.t) / 2 - tol: return None
    u_b0, u_b1 = u_of(a, b.point(b.ua, 0)), u_of(a, b.point(b.ub, 0))
    lo, hi = max(a.ua, min(u_b0, u_b1)), min(a.ub, max(u_b0, u_b1))
    return (lo, hi) if hi - lo > 0.02 else None


def piece(W, u0, u1, z0=None, z1=None, pid=None):
    P = copy.copy(W)
    P.openings = [dict(o) for o in W.openings if o["u1"] > u0 + 1e-4 and o["u0"] < u1 - 1e-4]
    P.holes = list(W.holes); P.layer_tops = dict(W.layer_tops); P.layer_z = dict(W.layer_z)
    P.ends = {"a": (None, 0.0), "b": (None, 0.0)}; P.meta = dict(W.meta)
    P.ua, P.ub = u0, u1
    if z0 is not None: P.z0 = z0
    if z1 is not None: P.z1 = z1
    if P.profile and z1 is not None and z1 < W.z1: P.profile = None
    P.id = pid or W.id
    P.only_layers = W.only_layers
    return P


def dedupe_storeys(gw, fw, ff_level, snap=0.1, log=None):
    """cut ground walls down to the first-floor base wherever a first-floor wall overlaps them (CORRECTIONS-LOG 100)"""
    out = []
    for W in gw:
        if W.z1 <= ff_level + 0.01:
            out.append(W); continue
        cov, fbase = [], ff_level
        for F in fw:
            iv = parallel_overlap(W, F)
            if iv: cov.append(iv); fbase = min(fbase, F.z0)
        if not cov:
            out.append(W); continue
        cov = merge_intervals(cov, gap=snap)
        cov = [(W.ua if a - W.ua < snap else a, W.ub if W.ub - b < snap else b) for a, b in cov]
        free = interval_minus([(W.ua, W.ub)], cov)
        segs = sorted([(a, b, True) for a, b in cov] + [(a, b, False) for a, b in free])
        for k, (a, b, covered) in enumerate(segs):
            P = piece(W, a, b, pid=W.id if len(segs) == 1 else f"{W.id}~{k + 1}")
            if covered:
                P.z1 = fbase; P.profile = None
            P.meta["dedupe"] = "cut to the first-floor base" if covered else "full height (no first-floor wall over it)"
            out.append(P)
        if log is not None: log.append(f"{W.id}: ground wall cut to {fbase} over {[(round(a,3), round(b,3)) for a, b in cov]}")
    return out


def orient(walls, rooms_by_storey):
    for W in walls:
        rooms = rooms_by_storey.get(W.storey, [])
        m = W.point((W.ua + W.ub) / 2, 0)
        r = W.t / 2 + 0.25
        pin = any(point_in_poly(add(m, mul(W.n, r)), p) for p in rooms)
        nin = any(point_in_poly(add(m, mul(W.n, -r)), p) for p in rooms)
        W.out = -1 if (pin and not nin) else 1
        W.meta["rooms"] = (pin, nin)


# ======================================================================================== state
class StateBuilder:
    def __init__(self, data, spec):
        self.D, self.S = data, spec
        self.Vt, self.Vb = data["versions"]["today"], data["versions"]["before"]
        self.lv = Levels(self.Vt, spec)
        self.notes = []
        OPENING_DATUM["shift"] = spec.get("levels", {}).get("opening_datum_shift", 0.0)

    def V(self, key): return self.D["versions"][key]

    # -------------------------------------------------------------- top level
    def build(self, vspec):
        st = vspec["state"]
        A = []                                          # atoms
        self.st = st
        gsrc, fsrc = self.V(st["ground"]), self.V(st["first"])
        rooms = {"ground": [r["poly"] for r in gsrc["storeys"]["ground"]["rooms"]] + [r["poly"] for r in st.get("extra_rooms_ground", [])],
                 "first": [r["poly"] for r in fsrc["storeys"]["first"]["rooms"]]}
        known = {w["id"] for stn in ("ground", "first") for w in self.Vb["storeys"][stn]["walls"]}
        gw = [w for w in read_walls(gsrc, "ground", st["ground"] == "before", known) if w.id not in st.get("exclude_walls", [])]
        fw = [w for w in read_walls(fsrc, "first", st["first"] == "before", known) if w.id not in st.get("exclude_walls", [])]
        for add_ in st.get("add_walls", []):
            for w in read_walls(self.V(add_["from"]), add_["storey"], add_["from"] == "before"):
                if w.id != add_["id"]: continue
                if "u_abs" in add_:
                    ax = 0 if abs(w.d[0]) > 0.5 else 1
                    us = sorted(abs(v - w.a[ax]) for v in add_["u_abs"])
                    w = piece(w, us[0], us[1], pid=add_.get("as", w.id))
                    w.openings = []
                (gw if add_["storey"] == "ground" else fw).append(w)
        for measured in self.S.get('finish_interfaces',{}).get('walls',[]):
            if vspec['id'] not in measured['versions']:continue
            line=measured['line']
            W=Wall(measured['id'],line[:2],line[2:],measured['thickness'],measured['base'],measured['top'],'stud_existing',storey='ground')
            W.meta=dict(type='Existing internal door head',src=self.S['finish_interfaces']['source'],conf='scaled',existing=True)
            W.openings=[dict(id=measured['opening'],kind='door',u0=0.,u1=measured['width'],z0=0.,z1=measured['head'],swing=measured['swing'],src=W.meta['src'],conf='scaled')]
            gw.append(W)
        for cw in st.get("context_walls", []):            # walls not on the trace (the attached neighbour), as massing
            x1, y1, x2, y2 = cw["line"]
            W = Wall(cw["id"], (x1, y1), (x2, y2), cw["t"], cw.get("z0", 0.0), cw["z1"], "massing", 1, cw.get("storey", "ground"))
            W.meta = dict(type="No.21 (neighbour) — massing", src=cw.get("src", ""), conf="assumed", note=cw.get("note", ""), existing=True,
                          context=True, label=cw.get("label"),
                          # row 179: the massing walls stop under their own roof (they stood 48 mm through No.21's eaves)
                          profile_from_roof=cw.get("profile_from_roof", "no21"), profile_mode="min")
            for o in cw.get("openings", []):
                W.openings.append(dict(id=o["id"], kind=o.get("kind", "window"), u0=o["u0"], u1=o["u1"], z0=o["z0"], z1=o["z1"],
                                       panes=o.get("panes", "2-light"), src=cw.get("src", ""), conf="assumed"))
            (gw if W.storey == "ground" else fw).append(W)
        for rep in st.get("replace_openings", []):
            srcw = next((w for w in read_walls(self.V(rep["from"]), rep["storey"]) if w.id == rep["wall"]), None)
            if srcw is None: srcw = Wall("none", (0, 0), (1, 0), 0.1, 0, 1, "masonry_int")
            for w in gw + fw:
                if w.id == rep["wall"]:
                    w.openings = [o for o in w.openings if o["id"] not in rep["remove"]] + [o for o in srcw.openings if o["id"] in rep["add"]]
        for wid, ov in st.get("wall_overrides", {}).items():
            for w in gw + fw:
                if w.id == wid:
                    for k, v in ov.items():
                        if k == "drop_openings": w.openings = [o for o in w.openings if o["id"] not in v]
                        elif k == "profile_from_roof": w.meta["profile_from_roof"] = v
                        elif k == "profile_mode": w.meta["profile_mode"] = v
                        elif k == "type": w.meta["type"] = v; w.ckey = classify_construction(v, w.meta["existing"], w.t)
                        elif k in ("ua_abs", "ub_abs"):
                            ax = 0 if abs(w.d[0]) > 0.5 else 1
                            setattr(w, k[:2], abs(v - w.a[ax]))
                        else: setattr(w, k, v)
        gw = dedupe_storeys(gw, fw, self.lv.ff, log=self.notes)
        orient(gw + fw, rooms)
        # row 179: an old outside wall with rooms on BOTH sides (the wing's flank between the hall and the sitting room, the old
        # rear wall inside the kitchen-diner) is plastered on its old outside face too; it showed bare brick inside the rooms
        for W in gw + fw:
            pin, nin = W.meta.get("rooms", (False, False))
            W.plaster_out = bool(pin and nin and W.ckey in ("cav_existing", "solid_existing", "leaf_existing"))
        self.walls = gw + fw
        self.rooms_named = {"ground": [(r["name"], r["poly"]) for r in gsrc["storeys"]["ground"]["rooms"]] +
                                      [(r["name"], r["poly"]) for r in st.get("extra_rooms_ground", [])],
                            "first": [(r["name"], r["poly"]) for r in fsrc["storeys"]["first"]["rooms"]]}
        for W in self.walls:
            A.append(self.wall_atom(W))
            A.extend(self.fixture_atoms(W))
        A.extend(self.floor_atoms(st))
        A.extend(self.fitting_atoms(st, gsrc, fsrc))
        A.extend(self.stair_atoms(st, gsrc))
        A.extend(self.chimney_atoms(st))
        A.extend(self.existing_footings())
        if st.get("structure"):
            A.extend(self.structure_atoms(st["structure"]))
        A.extend(self.extra_member_atoms(st))
        for sysspec in st.get("roofs", []):
            A.extend(self.roof_atoms(sysspec))
        for fr in st.get("flat_roofs", []):
            A.extend(self.flat_roof_atoms(fr,st.get('flat_roofs', [])))
        from hb_walls import resolve_joins
        resolve_joins(self.walls, lambda a, b: True)          # corners of this state, so plates stop at the inner leaf
        A.extend(self.wall_plate_atoms(st))
        self.apply_eaves_tops(st)
        self.walls_up_to_flat_roofs(st)
        self.embed_holes(A)
        rooms_out = self.room_atoms(st, gsrc, fsrc)
        return dict(id=vspec["id"], atoms=A, rooms=rooms_out, walls=self.walls, systems=self.systems if hasattr(self, "systems") else [])

    # -------------------------------------------------------------- walls
    def wall_label(self, W):
        if W.meta.get("label"): return W.meta["label"]
        s = self.Vt["structure"]["walls"]
        if W.ckey == "cav337_new": return s["external_new_337"]["label"]
        if W.ckey == "block_int": return s["internal_blockwork"]
        if W.ckey == "stud": return s["internal_stud"]
        if W.ckey == "ashlar": return s["ashlar"]["label"]
        return W.meta.get("type", CONSTRUCTIONS[W.ckey]["name"])

    def wall_atom(self, W):
        plain = {"cav337_new": "New cavity wall: brick outside, insulation, block inside",
                 "cav_existing": "Existing outside wall of the house", "party": "Party wall shared with No.21",
                 "masonry_int": "Existing inside wall", "leaf_existing": "Existing inner wall kept",
                 "solid_existing": "Existing brick wall", "block_int": "New inside block wall",
                 "stud": "New timber stud partition", "stud_existing": "Existing light partition",
                 "ashlar": "Short timber wall under the sloping ceiling"}.get(W.ckey, "Wall")
        ext = W.ckey in ("cav337_new", "cav_existing", "party", "solid_existing")
        meta = M("wall_outer" if ext else "wall_inner", W.storey, self.wall_label(W), dref(W.meta.get("src", ""), W.storey),
                 W.meta.get("conf", "scaled"), plain, True)
        phase = ("gf_wall" if W.storey == "ground" else "ff_wall")
        if W.ckey == "stud": phase = "partition"
        if W.ckey == "ashlar": phase = "ashlar"
        return atom(W.id, "wall", phase, meta, wall=W, sig=None)

    # -------------------------------------------------------------- windows and doors
    def fixture_atoms(self, W):
        out = []
        L = layer_stack(W.ckey, W.t)
        core = [l for l in L if not l.get("lining")]
        ext = W.ckey in ("cav337_new", "cav_existing", "solid_existing")
        for o in W.openings:
            if o["kind"] == "opening": continue
            if o["id"] in self.st.get("skip_fixtures", []): continue
            # frame plane: windows/external doors just behind the outer leaf, internal doors centred
            if ext and o["kind"] in ("window", "door", "bifold") and len(core) >= 2:
                o_plane = core[0]["o1"] + 0.04
            else:
                o_plane = W.t / 2
            c_plane = W.c_of(o_plane)
            kind = o["kind"]
            internal = not (ext or o.get("retained_exterior_frame"))
            pan = o.get("panes") or ""
            m = re.search(r"(\d)-light", pan)
            nlights = int(m.group(1)) if m else (4 if kind == "bifold" else (2 if kind == "window" else 1))
            if kind == "bifold": m2 = re.search(r"(\d) leaves", pan); nlights = int(m2.group(1)) if m2 else 4
            lbl = o["id"]
            if o.get("lintel"): pass
            plain = {"window": "Window", "door": "Internal door" if internal else "Outside door", "bifold": "Folding glass doors to the garden"}.get(kind, kind)
            g = "window" if kind == "window" else "door"
            meta = M(g, W.storey, f"{lbl}" + (f" ({pan})" if pan else ""), dref(o.get("src") or W.meta.get("src", ""), W.storey),
                     o.get("conf", "scaled"), plain, False)
            sig = sig_of("fx", W.point(o["u0"], 0), W.point(o["u1"], 0), o["z0"], o["z1"], kind, lbl)
            out.append(atom(opening_element_id("F", W.id, o), "fixture", "window" if kind == "window" else "door", meta,
                            sig=sig, wall=W, op=o, c_plane=c_plane, nlights=nlights, internal=internal,
                            rooms=self.rooms_named.get(W.storey, [])))
            if ext and kind == "window" and self.st.get("window_colour", "anthracite") == "anthracite":
                # the house's own frames are anthracite (photo survey); new windows 'to match' (colour not drawn)
                out[-1].update(frame_mat="anthracite_upvc", sill_mat="anthracite_upvc")
        return out

    # -------------------------------------------------------------- floors, ceilings
    def floor_atoms(self, st):
        lv = self.lv; out = []
        from hb_geom import poly_minus_convex
        def cut(poly, stn):
            cuts = [ccw(c) for c in st.get("floor_cuts", {}).get(stn, [])]
            return poly_minus_convex(poly, cuts) if cuts else [ccw(poly)]
        src = self.V(st.get("existing_floors_from", "before"))
        from hb_geom import line_intersect
        def to_walls(poly, stn, reach=0.03):
            """row 179: a traced room outline can stop short of the wall faces (25 mm slots at the floor and ceiling edges, seen
            from the rooms). Each edge with a wall face within 30 mm beyond it moves out by 30 mm; clip_walls then trims the floor
            back to the board face exactly, so it always meets the wall and never runs into a doorway or another room."""
            P = ccw([tuple(p) for p in poly]); n = len(P); poly = poly
            zr = (lv.existing_floor_bottom, lv.ffl) if stn == "ground" else (lv.gclg, lv.ff)
            walls = [W for W in self.walls if min(W.z1, zr[1]) - max(W.z0, zr[0]) > 0.005]       # walls through the floor's depth
            offs = []
            for i in range(n):
                a, b = P[i], P[(i + 1) % n]; d = unit(sub(b, a)); outn = (d[1], -d[0])           # ccw: outward is to the right
                # the whole edge runs along walls (all three probes in a wall): an edge open to a stairwell or another room stays put
                hit = all(any(point_in_poly(add(add(a, mul(sub(b, a), t)), mul(outn, reach * 0.66)), W.footprint(full=True)) for W in walls)
                          for t in (0.2, 0.5, 0.8))
                off = reach if hit else 0.0
                if not hit:
                    # two traced rooms a few mm apart with no wall between (the cupboards on the landing): each floor runs to
                    # the middle of the slot, so the ceiling under them is closed
                    for other in rooms_all.get(stn, []):
                        if other is poly: continue
                        Q = ccw([tuple(q) for q in other]); m_ = len(Q)
                        for j in range(m_):
                            c_, e_ = Q[j], Q[(j + 1) % m_]; dq = unit(sub(e_, c_))
                            if abs(d[0] * dq[1] - d[1] * dq[0]) > 1e-3 or dot(d, dq) > -0.999: continue
                            sep = dot(sub(c_, a), outn)
                            if not (0.0008 < sep <= 0.12): continue
                            t0, t1 = sorted((dot(sub(c_, a), d), dot(sub(e_, a), d)))
                            if min(t1, length(sub(b, a))) - max(t0, 0.0) < 0.05: continue
                            off = max(off, sep / 2)
                offs.append(off)
            lines = [(add(P[i], mul((unit(sub(P[(i + 1) % n], P[i]))[1], -unit(sub(P[(i + 1) % n], P[i]))[0]), offs[i])), unit(sub(P[(i + 1) % n], P[i]))) for i in range(n)]
            out = []
            for i in range(n):
                q = line_intersect(lines[i - 1][0], lines[i - 1][1], lines[i][0], lines[i][1])
                out.append(q if q is not None else lines[i][0])
            return out if abs(area(out)) >= abs(area(P)) - 1e-6 else P
        rooms_all = {stn: [r["poly"] for r in src["storeys"][stn]["rooms"]] for stn in ("ground", "first")}
        for stn in ("ground", "first"):
            for r in src["storeys"][stn]["rooms"]:
                if r["name"] in st.get("exclude_existing_floors", []): continue
                for k, P in enumerate(cut(to_walls(r["poly"], stn), stn)):
                    if abs(area(P)) < 0.02: continue
                    nm = f"{slug(r['name'])}" + (f"-{k + 1}" if k else "")
                    if stn == "ground":
                        meta = M("slab_layer", "ground", f"existing ground floor, {r['name']} (solid floor construction assumed, 'sol.')",
                                 "4915.1 ground floor plan", "assumed", "Existing floor", True)
                        out.append(atom(f"XF-G-{nm}", "slab", "existing", meta, sig=sig_of("xfg", P), poly=P,
                                        z0=lv.existing_floor_bottom, z1=lv.ffl, mat="existing_floor", clip_walls=True))
                    else:
                        meta = M("deck", "first", f"existing first floor, {r['name']} (joists and boards, not drawn; assumed)",
                                 "4915.1 first floor plan", "assumed", "Existing upstairs floor", True)
                        out.append(atom(f"XF-F-{nm}", "slab", "existing", meta, sig=sig_of("xff", P), poly=P,
                                        z0=lv.gclg, z1=lv.ff, mat="existing_floor", clip_walls=True))
                        if r["name"] not in st.get("exclude_existing_ceilings", []):
                            meta = M("ceiling_joist", "first", f"existing first-floor ceiling, {r['name']} (assumed)", "4915.1",
                                     "assumed", "Existing ceiling", False)
                            out.append(atom(f"XC-F-{nm}", "slab", "existing", meta, sig=sig_of("xcf", P), poly=P,
                                            z0=lv.fclg, z1=lv.fclg + 0.0145, mat="plasterboard", clip_walls=True))
        # row 179: the stairwell has no first-floor room, so it had no ceiling: from the landing you looked up into the loft
        # (membrane, rafters). The ceiling over the stair is the stair's plan (both flights and the half landing) less the rooms.
        from hb_geom import poly_minus_convex, convex_pieces
        gV = self.V(st["ground"])
        for s_ in (gV.get("stairs") or gV["storeys"]["ground"].get("stairs") or []):
            f1, f2, hl_ = s_.get("flight1"), s_.get("flight2"), s_.get("half_landing")
            if not (f1 and f2 and hl_): continue
            xs = list(f1["x"]) + list(f2["x"]) + [p[0] for p in hl_["poly"]]
            ys = list(f1["risers_y"]) + list(f2["risers_y"]) + [p[1] for p in hl_["poly"]]
            box_ = [(min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys))]
            cutters = [c for r in src["storeys"]["first"]["rooms"] for c in convex_pieces(ccw(r["poly"]))]
            for k, P in enumerate(poly_minus_convex(ccw(box_), cutters)):
                if abs(area(P)) < 0.02: continue
                meta = M("ceiling_joist", "first", "ceiling over the stairwell (existing; assumed, as the first-floor ceilings)", "4915.1", "assumed",
                         "Ceiling over the stairs", False)
                out.append(atom(f"XC-F-stairwell" + (f"-{k + 1}" if k else ""), "slab", "existing", meta, sig=sig_of("xcs", P), poly=P,
                                z0=lv.fclg, z1=lv.fclg + 0.0145, mat="plasterboard", clip_walls=True))
        return out

    # -------------------------------------------------------------- fittings
    FIT_H = [("wc", 0.40, "fitting", "sanitary", "WC (pan and cistern, height assumed)"),
             ("basin", 0.85, "fitting", "sanitary", "basin (height assumed)"),
             ("shower tray", 0.05, "fitting", "sanitary", "shower tray"),
             ("shower 1800", 0.05, "fitting", "sanitary", "1800x900 shower tray"),
             ("wardrobe", 2.10, "fitting", "joinery", "wardrobe 'wd.' (height assumed)"),
             # row 179 / spec_v1 drawn_fixtures: breasts, piers and ducts inside the rooms are plastered (FIN-WALL); bare brick showed
             ("chimney breast", None, "wall_inner", "plaster", "chimney breast (brick, plastered)"),
             ("pier", None, "wall_inner", "plaster", "pier (brick, plastered)"),
             ("duct", None, "wall_inner", "plaster", "pier / duct (plastered)"),
             ("gas meter", 0.60, "fitting", "meter", "gas meter box"),
             ("mv cooker", None, None, None, None)]

    def fitting_atoms(self, st, gsrc, fsrc):
        out = []
        from hb_conservatory import elevations
        roof=next((r for r in st.get('flat_roofs',[]) if r.get('mat')=='polycarbonate' and 'z_house' in r),None)
        records=[r for r in gsrc['storeys']['ground']['fittings'] if 'conservatory' in r['name'].lower() and r['name'] not in st.get('exclude_fittings',[])]
        if roof and records:out.extend(elevations(records, roof, self.walls, st.get("flat_roofs", [])))
        for stn, V in (("ground", gsrc), ("first", fsrc)):
            for f in V["storeys"][stn]["fittings"]:
                if roof and f in records:continue
                if f["name"] in st.get("exclude_fittings", []): continue
                out.extend(self._fitting(f, stn))
        for inc in st.get("add_fittings", []):
            for f in self.V(inc["from"])["storeys"][inc["storey"]]["fittings"]:
                if f["name"] in inc["names"]: out.extend(self._fitting(f, inc["storey"]))
        # CORRECTIONS-LOG 191 (Jack: "chimney breasts built as two pillars"): a plan cuts a breast at ~1 m, so a fireplace
        # breast is traced as two jambs ("chimney breast pier (front)/(rear)") with the opening between; the breast itself runs on
        # across the opening above it. The head (breast over the fireplace opening) is built from the jambs' own line and top:
        # opening head at 1.0 m above the floor (typical UK fireplace/stove opening, not drawn: assumed).
        for stn, V in (("ground", gsrc), ("first", fsrc)):
            jambs = [f for f in V["storeys"][stn]["fittings"] if "chimney breast pier" in f["name"].lower() and f["name"] not in st.get("exclude_fittings", [])]
            jambs.sort(key=lambda f: min(p[1] for p in f["poly"]))
            base = self.lv.ffl if stn == "ground" else self.lv.ff
            for a_, b_ in zip(jambs, jambs[1:]):
                ax = (min(p[0] for p in a_["poly"]), max(p[0] for p in a_["poly"])); bx = (min(p[0] for p in b_["poly"]), max(p[0] for p in b_["poly"]))
                y0 = max(p[1] for p in a_["poly"]); y1 = min(p[1] for p in b_["poly"])
                if abs(ax[0] - bx[0]) > 0.03 or abs(ax[1] - bx[1]) > 0.03 or not 0.2 < y1 - y0 < 1.5: continue
                x0, x1 = max(ax[0], bx[0]), min(ax[1], bx[1]); z1 = min(a_.get("top_z") or 9, b_.get("top_z") or 9)
                P = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                meta = M("wall_inner", stn, f"chimney breast over the fireplace opening, between the traced jambs (opening head 1.0 m: typical, not drawn)",
                         dref(a_.get("src", ""), stn), "assumed", "Chimney breast (plastered)", True)
                out.append(atom(f"FT-{stn[0].upper()}-chimney-breast-head-{slug(P[0])}", "prism", "fitting", meta,
                                sig=sig_of("fit", "breast head", P, base + 1.0, z1), poly=P, z0=base + 1.0, z1=z1, mat="plaster"))
        # the same for a wall drawn with piers and low recesses between them ("inner face alternates"; circled heights in the
        # recesses, the recess openings dashed = wall over): the wall face runs on above each recess at its circled height,
        # so the piers are not loose pillars (row 191). Heights are read from the trace note in drawing order (rear first).
        for stn, V in (("ground", gsrc), ("first", fsrc)):
            piers = [f for f in V["storeys"][stn]["fittings"] if f["name"].lower() == "pier" and f["name"] not in st.get("exclude_fittings", [])]
            if len(piers) < 2: continue
            hs = []
            for f in piers:
                m = re.search(r"circled heights ((?:'\d+'(?:,| and )?\s*)+)", f.get("src", ""))
                if m: hs = [int(x) / 1000.0 for x in re.findall(r"'(\d+)'", m.group(1))]; break
            if not hs: continue
            piers.sort(key=lambda f: -max(p[1] for p in f["poly"]))           # rear (larger y) first, as drawn top to bottom
            base = self.lv.ffl if stn == "ground" else self.lv.ff
            k = 0
            for a_, b_ in zip(piers, piers[1:]):
                ax = (min(p[0] for p in a_["poly"]), max(p[0] for p in a_["poly"])); bx = (min(p[0] for p in b_["poly"]), max(p[0] for p in b_["poly"]))
                y1 = min(p[1] for p in a_["poly"]); y0 = max(p[1] for p in b_["poly"])
                if abs(ax[0] - bx[0]) > 0.03 or abs(ax[1] - bx[1]) > 0.03 or not 0.2 < y1 - y0 < 1.5 or k >= len(hs): continue
                x0, x1 = max(ax[0], bx[0]), min(ax[1], bx[1]); z1 = min(a_.get("top_z") or 9, b_.get("top_z") or 9)
                P = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                meta = M("wall_inner", stn, f"wall over a {int(hs[k] * 1000)} mm high recess between the traced piers (circled height on 4915.1; reading: recess height)",
                         dref(a_.get("src", ""), stn), "assumed", "Wall over a low recess (plastered)", True)
                out.append(atom(f"FT-{stn[0].upper()}-recess-head-{slug(P[0])}", "prism", "fitting", meta,
                                sig=sig_of("fit", "recess head", P, base + hs[k], z1), poly=P, z0=base + hs[k], z1=z1, mat="plaster"))
                k += 1
        return out

    def _fitting(self, f, stn):
        nm = f["name"].lower()
        base = self.lv.ffl if stn == "ground" else self.lv.ff
        ceil = self.lv.gclg if stn == "ground" else self.lv.fclg
        P = f["poly"]
        if "recess" in nm or "mv " in nm: return []
        if any(k in nm for k in ("wc", "basin", "shower", "wardrobe")):
            xs = [p[0] for p in P]; ys = [p[1] for p in P]; e = 0.03          # clear of the wall linings
            P = [(min(xs) + e, min(ys) + e), (max(xs) - e, min(ys) + e), (max(xs) - e, max(ys) - e), (min(xs) + e, max(ys) - e)]
        if "canopy" in nm:
            z0, z1 = f.get("z", [2.149, 2.228])
            meta = M("fitting", "ground", f["name"], dref(f.get("src", "")), conf_of(f), "Old canopy over the front door", False)
            return [atom(f"FT-{slug(f['name'])}", "prism", "existing", meta, sig=sig_of("fit", P, z0, z1), poly=P, z0=z0, z1=z1, mat="upvc_white")]
        if "conservatory" in nm:
            sill = f.get("sill_z", 0.59); gh = f.get("glazing_h", 1.48)
            # row 179: the traced conservatory sides overlap at their corners; each later side gives way to the earlier ones
            # (two dwarf walls in one place z-fought from the garden)
            done = getattr(self, "_cons_polys", [])
            from hb_geom import poly_minus_convex
            pieces = poly_minus_convex(ccw(P), [ccw(c) for c in done]) if done else [ccw(P)]
            self._cons_polys = done + [ccw(P)]
            pieces = [q for q in pieces if abs(area(q)) > 1e-4]
            if not pieces: return []
            if len(pieces) > 1 or abs(area(pieces[0]) - abs(area(P))) > 1e-6:
                outp = []
                for k, Q in enumerate(pieces):
                    meta = M("wall_outer", "ground", f["name"] + " (dwarf wall 590 + glazing 1480 written)", dref(f.get("src", "")), conf_of(f),
                             "Old conservatory wall and windows", True)
                    sfx = f"-{k + 1}" if k else ""
                    outp.append(atom(f"FT-{slug(f['name'])}-dwarf{sfx}", "prism", "existing", meta, sig=sig_of("cons", Q), poly=Q, z0=0.0, z1=sill, mat="existing_brick"))
                    meta2 = dict(meta, group="window", collide=False, plain_label="Old conservatory glazing")
                    outp.append(atom(f"FT-{slug(f['name'])}-glazing{sfx}", "prism", "existing", meta2, sig=sig_of("consg", Q), poly=Q, z0=sill, z1=min(sill + gh, 2.05), mat="glass"))
                return outp
            meta = M("wall_outer", "ground", f["name"] + " (dwarf wall 590 + glazing 1480 written)", dref(f.get("src", "")), conf_of(f),
                     "Old conservatory wall and windows", True)
            dw = atom(f"FT-{slug(f['name'])}-dwarf", "prism", "existing", meta, sig=sig_of("cons", P), poly=P, z0=0.0, z1=sill, mat="existing_brick")
            meta2 = dict(meta, group="window", collide=False, plain_label="Old conservatory glazing")
            gl = atom(f"FT-{slug(f['name'])}-glazing", "prism", "existing", meta2, sig=sig_of("consg", P), poly=P, z0=sill, z1=min(sill + gh, 2.05), mat="glass")
            return [dw, gl]
        for key, h, grp, mat, lbl in self.FIT_H:
            if key in nm:
                if grp is None: return []
                z1 = (f.get("top_z") or ceil) if h is None else base + h
                if "external" in nm:                 # an external box stands on the ground outside
                    base = self.st.get("external_ground", -0.25); z1 = base + h
                plain = {"sanitary": "Bathroom fitting", "joinery": "Built-in wardrobe", "existing_brick": "Existing chimney breast / pier",
                         "plaster": "Existing chimney breast / pier (plastered)",
                         "meter": "Gas meter box"}.get(mat, "Fitting")
                meta = M(grp, stn, f["name"] + ("" if h is None else f" — {lbl}"), dref(f.get("src", ""), stn), conf_of(f), plain,
                         grp != "fitting" or h > 1.0)
                matn = {"sanitary": "sanitary", "joinery": "joinery", "existing_brick": "existing_brick", "plaster": "plaster", "meter": "sanitary"}[mat]
                return [atom(f"FT-{stn[0].upper()}-{slug(f['name'])}-{slug(P[0])}", "prism", "fitting" if "external" not in nm else "existing", meta,
                             sig=sig_of("fit", f["name"], P, base, z1), poly=P, z0=base, z1=z1, mat=matn)]
        return []

    # -------------------------------------------------------------- stair
    def stair_atoms(self, st, gsrc):
        """the existing dog-leg stair: treads that butt (no gaps along the walking line), the landing floor carried
        right to the top riser (the room outline on the trace stops 121 mm short, at the end of the balustrade wall), the
        guarding the plans show ('M' masonry between the flights; the stair-side wall lowered to 900, 4915.2B) and a
        handrail on each flight (AD K 1.34, typical: not drawn)"""
        out = []
        lv = self.lv
        for s in gsrc["storeys"]["ground"].get("stairs", []):
            rise = val(s["rise"]); n = val(s["risers"])
            treads = s.get("treads_poly", [])
            meshes = []
            for k, T in enumerate(treads):
                ztop = rise * (k + 1) if k < len(treads) - 1 else val(s["half_landing"]["z"])
                if k >= 7 and k < len(treads) - 1:          # flight 2 continues from the landing
                    ztop = val(s["half_landing"]["z"]) + rise * (k - 6)
                xs = [p[0] for p in T]; ys = [p[1] for p in T]
                e_ = 0.005 if k == len(treads) - 1 else 0.0          # treads butt along the walking line; the half landing stands clear of its walls
                Ts = [(min(xs) + 0.005, min(ys) + e_), (max(xs) - 0.005, min(ys) + e_), (max(xs) - 0.005, max(ys) - e_), (min(xs) + 0.005, max(ys) - e_)]
                meshes.append(prism(Ts, max(0.0, ztop - (0.2 if k == len(treads) - 1 else 0.25)), ztop))
            meta = M("fitting", "ground", f"{s['name']}: {n} risers of {rise*1000:.1f}, going {val(s['going'])*1000:.1f}, half landing at {val(s['half_landing']['z'])}",
                     dref(s.get("src", "")), conf_of(s), "Existing stairs", True)
            out.append(atom("ST-stair", "mesh", "existing", meta, sig=sig_of("stair", n, rise), mesh=merge_meshes(meshes), mat="stair",
                            stair=self._stair_params(s, rise, n)))
            # the underside of each flight is closed by a plastered soffit (row 191 walk inspection: the tread blocks' stepped
            # undersides showed from the hall like a floating stair). Plane through the back-bottom corners of the treads (the
            # steps' lowest edges), carried up at the top to the ground-floor ceiling; the walls each side close it.
            fl_blocks = {1: [], 2: []}
            for k, T in enumerate(treads):
                if k == len(treads) - 1: continue                    # the half landing has its own flat underside
                ztop = rise * (k + 1) if k < 7 else val(s["half_landing"]["z"]) + rise * (k - 6)
                xs = [p[0] for p in T]; ys = [p[1] for p in T]
                fl_blocks[1 if k < 7 else 2].append((min(xs), max(xs), min(ys), max(ys), max(0.0, ztop - 0.25)))
            for fk, bl in fl_blocks.items():
                if len(bl) < 2: continue
                d = 1 if (bl[1][2] + bl[1][3]) > (bl[0][2] + bl[0][3]) else -1
                back = (lambda b: b[3]) if d > 0 else (lambda b: b[2]); front = (lambda b: b[2]) if d > 0 else (lambda b: b[3])
                ya, yb = back(bl[0]), back(bl[-1])
                if abs(yb - ya) < 0.1: continue
                slope = rise * (len(bl) - 1) / (yb - ya)              # dz/dy along the flight
                # the line under every block's two bottom corners (lower envelope): nothing of a tread pokes through it
                c0 = min(b[4] - slope * y for b in bl for y in (b[2], b[3]))
                zl = lambda y: c0 + slope * y
                y0 = front(bl[0])
                if zl(y0) < 0.0: y0 = -c0 / slope                    # flight 1 starts on the floor
                y1 = back(bl[-1])
                z_up = val(s["half_landing"]["z"]) - 0.2 if fk == 1 else lv.gclg          # flight 1 runs up under the half landing
                if zl(y1) < z_up: y1 = y1 + d * min(0.4, (z_up - zl(y1)) / abs(slope))
                xa, xb = min(b[0] for b in bl) - 0.005, max(b[1] for b in bl) + 0.005   # to the wall faces each side (scribed in)
                ylo, yhi = min(y0, y1), max(y0, y1)
                q = [(xa, ylo), (xb, ylo), (xb, yhi), (xa, yhi)]          # counter-clockwise from above (outward normals)
                V = [(x, y, zl(y) - 0.0125) for (x, y) in q] + [(x, y, zl(y)) for (x, y) in q]
                meta = M("wall_inner", "ground", f"plastered soffit under flight {fk} (plasterboard on the strings, skimmed; {TYPICAL}): "
                         "closes the underside of the stair", dref(s.get("src", "")), "assumed", "Stair soffit (plastered)", True)
                out.append(atom(f"ST-soffit-flight{fk}", "mesh", "existing", meta, sig=sig_of("soffit", fk, q), mesh=hexa(V), mat="plaster"))
            f1, f2 = s.get("flight1"), s.get("flight2")
            if not (f1 and f2): continue
            y_top = f2["risers_y"][-1]                      # the top riser (14) at the landing
            x1a, x1b = f1["x"]; x2a, x2b = f2["x"]
            hl = val(s["half_landing"]["z"]); ff = lv.ff
            land = next((r for r in self.Vb["storeys"]["first"]["rooms"] if "landing" in r["name"]), None)
            y_room = max(p[1] for p in land["poly"]) if land else y_top
            if y_top - y_room > 0.01:
                P = [(x2a, y_room), (x2b, y_room), (x2b, y_top), (x2a, y_top)]
                meta = M("deck", "first", f"landing floor at the stair head: the landing runs to the top riser (14) at y {y_top:.3f}; the traced "
                         f"room outline stops at {y_room:.3f}, the end of the balustrade wall (existing joists and boards, trimmer at the "
                         "stairwell edge; assumed)", "4915.1 / 4915.2B first floor plan (riser 14 and the landing edge)", "scaled",
                         "Landing floor at the top of the stairs", True)
                out.append(atom("XF-F-landing-head", "slab", "existing", meta, sig=sig_of("landhead", P), poly=P, z0=lv.gclg, z1=ff,
                                mat="existing_floor", clip_walls=True))
            # guarding between the flights: the spine wall continues up ('M' on 4915.2B FF) to 900 above the pitch line
            going = val(s["going"]); xs0, xs1 = x1b, x2a
            y_hl = f2["risers_y"][0]
            def pitch(y): return hl + rise + (y_hl - y) / going * rise    # flight 2 pitch line (through the nosings)
            ya = y_room - 0.0                                               # from the landing edge over flight 1
            zg = lambda y: min(ff, pitch(max(y, y_top))) + 0.9
            q = [(xs0, ya), (xs1, ya), (xs1, y_hl), (xs0, y_hl)]
            V = [(x, y, lv.gclg) for (x, y) in q] + [(x, y, max(lv.gclg + 0.01, zg(y))) for (x, y) in q]
            meta = M("wall_inner", "first", "masonry between the flights carried up as guarding to 900 above the pitch line and the landing "
                     "('M' between the flights on 4915.2B FF; height to AD K 1.33, assumed)", "4915.2B first floor plan", "assumed",
                     "Wall guarding the stairwell", True)
            out.append(atom("ST-guard-spine", "mesh", "existing", meta, sig=sig_of("spineguard", q), mesh=hexa(V), mat="existing_partition"))
            # guarding along the landing edge over flight 1 (typical) and handrails (typical)
            meta = M("fitting", "first", f"balustrade along the landing edge over flight 1, 900 high {TYPICAL} (AD K 1.33)", "", "assumed",
                     "Banister along the landing", True)
            bal = [box(x1a + 0.01, x1b, ya - 0.045, ya, ff, ff + 0.9 - 0.06), box(x1a + 0.01, x1b, ya - 0.06, ya + 0.015, ff + 0.9 - 0.06, ff + 0.9)]
            nb = int((x1b - x1a) / 0.11)
            out.append(atom("ST-balustrade-landing", "mesh", "existing", meta, sig=sig_of("landbal"), mesh=merge_meshes(bal[1:] + [
                box(x1a + 0.02 + k_ * (x1b - x1a - 0.04) / max(1, nb), x1a + 0.052 + k_ * (x1b - x1a - 0.04) / max(1, nb), ya - 0.04, ya - 0.008, ff, ff + 0.84)
                for k_ in range(nb + 1)]), mat="joinery"))
            hr = []
            for (xa, xb, y0, y1, z0_, z1_) in ((x2b - 0.07, x2b - 0.03, y_hl, y_top, hl + rise, ff),):      # flight 2, on the balustrade-wall side
                L = math.hypot(y1 - y0, z1_ - z0_)
                hr.append(hexa([(xa, y0, z0_ + 0.90), (xb, y0, z0_ + 0.90), (xb, y1, z1_ + 0.90), (xa, y1, z1_ + 0.90),
                                (xa, y0, z0_ + 0.94), (xb, y0, z0_ + 0.94), (xb, y1, z1_ + 0.94), (xa, y1, z1_ + 0.94)]))
            y10, y11 = f1["risers_y"][0], f1["risers_y"][-1]
            hr.append(hexa([(x1a + 0.03, y10, rise + 0.90), (x1a + 0.07, y10, rise + 0.90), (x1a + 0.07, y11, hl + 0.90), (x1a + 0.03, y11, hl + 0.90),
                            (x1a + 0.03, y10, rise + 0.94), (x1a + 0.07, y10, rise + 0.94), (x1a + 0.07, y11, hl + 0.94), (x1a + 0.03, y11, hl + 0.94)]))
            for (wx, rx, y0, y1, z0_, z1_) in ((x2b, x2b - 0.03, y_hl, y_top, hl + rise, ff), (x1a, x1a + 0.03, y10, y11, rise, hl)):
                nbk = max(2, int(abs(y1 - y0) / 0.8) + 1)
                for kb in range(nbk):                        # brackets screwed to the wall under the rail
                    yb = y0 + (y1 - y0) * (0.08 + 0.84 * kb / (nbk - 1)); zb = z0_ + (z1_ - z0_) * (yb - y0) / (y1 - y0) + 0.90
                    hr.append(box(min(wx, rx), max(wx, rx), yb - 0.015, yb + 0.015, zb - 0.06, zb))
            meta = M("fitting", "ground", f"handrails, 900 above the pitch line, one each flight {TYPICAL} (AD K 1.34-1.36: a stair under 1 m wide "
                     "needs a handrail on at least one side; none drawn)", "", "assumed", "Handrail", False)
            out.append(atom("ST-handrails", "mesh", "existing", meta, sig=sig_of("handrails"), mesh=merge_meshes(hr), mat="joinery"))
        return out

    def _stair_params(self, s, rise, n):
        """contract 5 stair: start = first riser's centre line (drawing frame here, converted on write), treads along
        direction, tread k's nosing (k-1).going from start at k.rise above base. A dog-leg is given flight by flight."""
        out = dict(rise=rise, going=val(s["going"]), risers=n, base=0.0, top_floor="XF-F-hall-landing")
        fl = []
        z = 0.0
        for key in ("flight1", "flight2"):
            f = s.get(key)
            if not f: continue
            ry = f["risers_y"]; x0, x1 = f["x"]
            d = 1.0 if ry[-1] > ry[0] else -1.0
            fl.append(dict(start=[round((x0 + x1) / 2, 4), round(ry[0], 4)], direction=[0.0, d], width=round(val(f["width"]), 4),
                           base=round(z, 4), risers=len(ry) if key == "flight1" else len(ry) + 0, going=round(abs(ry[1] - ry[0]), 4),
                           numbers=f.get("numbers", "")))
            z = val(s["half_landing"]["z"]) if s.get("half_landing") else z
        if fl:
            out.update(start=fl[0]["start"], direction=fl[0]["direction"], width=fl[0]["width"], flights=fl)
        if s.get("half_landing"):
            out["half_landing"] = dict(poly=s["half_landing"]["poly"], z=val(s["half_landing"]["z"]))
        return out

    # -------------------------------------------------------------- chimney
    def chimney_atoms(self, st):
        ch = self.Vt["chimney"]
        x0, x1 = ch["x"]; y0, y1 = val(ch["y"])
        top, cap = val(ch["top_z"]), val(ch["cap_top_z"])
        cx0, cx1 = ch["cap_x"]
        base = self.lv.plate
        meta = M("wall_outer", "roof", "chimney stack (straddles the party wall, shared with No.21); pots not drawn",
                 dref(ch.get("src", "")), conf_of(ch), "Chimney (shared with next door)", True)
        stack = box(x0, x1, y0, y1, base, top)
        capm = box(cx0, cx1, y0 - 0.025, y1 + 0.025, top, cap)
        return [atom("CH-stack", "mesh", "existing", meta, sig=sig_of("chim"), mesh=merge_meshes([stack, capm]), mat="existing_brick")]

    # -------------------------------------------------------------- existing footings (assumed)
    def existing_footings(self):
        """existing ground-floor walls go down to their (assumed) footings; new masonry stands on the trench fill"""
        lv = self.lv
        for W in self.walls:
            if W.storey != "ground": continue
            if W.meta.get("existing") or W.ckey in ("masonry_int", "leaf_existing", "solid_existing", "stud_existing", "cav_existing", "party", "massing"):
                W.z0 = min(W.z0, lv.existing_base)
            elif W.ckey in ("cav337_new", "block_int") and W.z0 < 0.05:
                W.z0 = lv.found_top
        out = []
        lab = self.S.get("structure_notes", {}).get("existing_foundations",
              "Existing foundations to be exposed & inspected on site & subject to Building inspector approval.")
        for W in self.walls:
            if W.storey != "ground" or W.z0 > lv.existing_base + 0.01 or W.ckey in ("stud_existing",): continue
            if not (W.meta.get("existing") or W.ckey == "massing"): continue
            spread = 0.15 if W.t > 0.2 else 0.1
            cl, ch = -W.t / 2 - spread, W.t / 2 + spread
            P = [W.point(W.ua - (spread if True else 0), cl), W.point(W.ub + spread, cl), W.point(W.ub + spread, ch), W.point(W.ua - spread, ch)]
            meta = M("foundation", "site", f"{lab} — not drawn: shown as an assumed strip footing under {W.id}", "4915.3A / 4A notes", "assumed",
                     "Existing foundation (not known: to be uncovered and checked)", True)
            out.append(atom(f"XFD-{W.id}", "prism", "existing", meta, sig=sig_of("xfd", W.id, P), poly=P, z0=lv.existing_base - 0.225, z1=lv.existing_base,
                            mat="concrete"))
        return out

    # -------------------------------------------------------------- the structure of the approved drawings (4915.3A/4A)
    def structure_atoms(self, pk):
        """pk: which packages of today's structure apply (spec): foundations, slab, beams, joists, lintels..."""
        S = self.Vt["structure"]; lv = self.lv; out = []
        G = S["groundworks"]
        flabel = G["foundations"][0]["label"]
        zones = self.lv.ground_zones
        def gl_at(p):
            for z in zones:
                if point_in_poly(p, z["poly"]): return z["z"]
            return -0.25
        # foundations
        for f in G["foundations"]:
            if "centre_lines" not in f: continue
            wdt = val(f["width"])
            for k, ln in enumerate(f["centre_lines"]):
                key = f"{f['name'][:20]}-{k}"
                if key_in(pk.get("foundations", "all"), k, f):
                    (xa, ya), (xb, yb) = ln
                    d = unit((xb - xa, yb - ya)); n = (d[1], -d[0])
                    ext = wdt / 2
                    a = (xa - d[0] * ext, ya - d[1] * ext); b = (xb + d[0] * ext, yb + d[1] * ext)
                    P = [add(a, mul(n, wdt / 2)), add(b, mul(n, wdt / 2)), add(b, mul(n, -wdt / 2)), add(a, mul(n, -wdt / 2))]
                    gl = gl_at(mul(add(a, b), 0.5))
                    zb = gl - val(G["foundations"][0]["depth_min"])
                    meta = M("foundation", "site", (flabel if wdt > 0.5 else f"{f['name']} — " + flabel) +
                             " [shown at the stated minimum, 1 m below ground; final depth to suit ground conditions and the Building Inspector]",
                             dref(f.get("src", "")), "assumed", "Concrete foundation in the trench", True)
                    out.append(atom(f"FD-{k}-{slug(f['name'][:24])}", "prism", "found", meta, sig=sig_of("fd", P), poly=P,
                                    z0=zb, z1=lv.found_top, mat="concrete", gl=gl))
        # slab layers (drawn section levels; CORRECTIONS-LOG 98)
        sl = G["slab"]
        polys = [e["poly"] for e in sl["extent"][1:] if isinstance(e, dict)]
        use = pk.get("slabs", list(range(len(polys))))
        stack = self.S["slab_stack"]
        for i in use:
            P = polys[i]
            for lay in stack:
                meta = M("slab_layer", "ground", lay["label"], "4915.3A section B-B / construction notes", lay.get("conf", "scaled"),
                         lay.get("plain"), lay.get("collide", False))
                out.append(atom(f"SL{i}-{lay['key']}", "slab", lay.get("phase", "slab"), meta, sig=sig_of("sl", i, lay["key"], P),
                                poly=P, z0=lay["z0"], z1=lay["z1"], mat=lay["mat"], seq=lay.get("seq", 0.5), clip_walls=True))
        # beams
        for b in S["beams"]:
            if b["id"] not in pk.get("beams", []): continue
            out.extend(self.beam_atoms(b))
        # FF joists, noggins, deck, insulation, ceiling below
        if pk.get("ff_joists"):
            out.extend(self.ff_joist_atoms(S["first_floor"]))
        return out

    def beam_atoms(self, b):
        lv = self.lv; out = []
        ov = self.S.get("beam_overrides", {}).get(b["id"], {})
        lines = b.get("plan_lines") or [b["plan_line"]]
        us, ts = val(b.get("underside_z")), val(b.get("top_z"))
        us, ts = ov.get("underside", us), ov.get("top", ts)
        sec = b["section"]
        drawing = dref(b.get("src", ""))
        conf = conf_of(b.get("length", {}))
        plain = ov.get("plain", "Beam")
        blabel = b["label"] + (f" [{ov['top_note']}]" if ov.get("top_note") else "")
        for k, ln in enumerate(lines):
            (xa, ya), (xb, yb) = [tuple(p) for p in ln]
            ext = ov.get("extend", {})
            d = unit((xb - xa, yb - ya))
            xa, ya = xa - d[0] * ext.get("start", 0), ya - d[1] * ext.get("start", 0)
            xb, yb = xb + d[0] * ext.get("end", 0), yb + d[1] * ext.get("end", 0)
            bid = f"B-{slug(b['id'])}" + (f"-{k + 1}" if len(lines) > 1 else "")
            A3, B3 = (xa, ya, ts), (xb, yb, ts)
            if "UB" in sec:
                D, Bw, tw, tf = (0.2032, 0.1018, 0.0054, 0.0093) if "203x102" in sec else (0.1778, 0.1012, 0.0048, 0.0079)
                section = i_section(D, Bw, tw, tf)
                plate = None
                if "plate" in sec or "8 mm" in sec or "8mm" in b["label"]:
                    # 8 mm plate under the bottom flange, wide enough for the outer skin (width from the spec)
                    pw = ov.get("plate_width", 0.34); po = ov.get("plate_offset", 0.0)
                    plate = [(po - pw / 2 + 0.0, -D), (po + pw / 2, -D), (po + pw / 2, -D - 0.008), (po - pw / 2, -D - 0.008)]
                    A3, B3 = (xa, ya, us + 0.008 + D), (xb, yb, us + 0.008 + D)
                else:
                    A3, B3 = (xa, ya, us + D), (xb, yb, us + D)
                meta = M("steel", "ground" if us < lv.ff else "first", b["label"], drawing, conf, plain, True)
                out.append(atom(bid, "member", ov.get("phase") or ("steel_ff" if us > lv.ff else ("steel_floor" if "floor void" in b["label"] else "steel_gf")),
                                meta, sig=sig_of("beam", A3, B3, sec), A=A3, B=B3, section=section, mat="steel", extra_sections=[(plate, "steel")] if plate else [],
                                bearings=ov.get("bearings")))
            elif "flitch" in sec:
                h = ts - us
                tim = [(-0.05, 0), (-0.005, 0), (-0.005, -h), (-0.05, -h)]
                tim2 = [(0.005, 0), (0.05, 0), (0.05, -h), (0.005, -h)]
                pl = [(-0.005, -0.0075), (0.005, -0.0075), (0.005, -0.1875), (-0.005, -0.1875)]
                meta = M("timber_beam", "first", b["label"], drawing, conf, plain, False)
                out.append(atom(bid, "member", "beam_roof", meta, sig=sig_of("beam", A3, B3, sec), A=A3, B=B3, section=tim, mat="timber",
                                extra_sections=[(tim2, "timber"), (pl, "steel")]))
            else:
                # timber: '2no. 45x122' / '2no. 195x45'
                nums = [float(x) / 1000 for x in re.findall(r"(\d+)x(\d+)", sec)[0]]
                wd, dp = (min(nums), max(nums))
                h = ts - us if ts and us else dp
                n2 = 2 if "2no" in sec else 1
                tim = [(-wd * n2 / 2, 0), (wd * n2 / 2, 0), (wd * n2 / 2, -h), (-wd * n2 / 2, -h)]
                meta = M("timber_beam", "ground" if us < lv.ff else "first", blabel, drawing, conf, plain, False)
                out.append(atom(bid, "member", "beam_roof" if us > lv.ff else ov.get("phase", "beam_porch"), meta, sig=sig_of("beam", A3, B3, sec),
                                A=A3, B=B3, section=tim, mat="timber"))
            # padstones
            for pad in ov.get("padstones", []):
                (px, py), (lx, ly, lz) = pad["at"], pad["size"]
                z1 = pad.get("top", us)
                meta = M("lintel", "ground" if z1 < lv.ff else "first", pad.get("label", "300x100x150mm deep mass concrete padstone"),
                         drawing, pad.get("conf", "scaled"), "Concrete pad the beam sits on", False)
                ax = pad.get("axis", "x")
                P = box(px - lx / 2, px + lx / 2, py - ly / 2, py + ly / 2, z1 - lz, z1) if ax == "x" else box(px - ly / 2, px + ly / 2, py - lx / 2, py + lx / 2, z1 - lz, z1)
                out.append(atom(f"{bid}-pad{len(out)}", "mesh", ov.get("pad_phase", "pad_" + ("ff" if us > lv.ff else "gf")), meta,
                                sig=sig_of("pad", px, py, z1), mesh=P, mat="concrete", embed=True))
            for pk_ in ov.get("packers", []):
                (px, py), (lx, ly), z0, z1 = pk_["at"], pk_["size"], pk_["z0"], pk_["z1"]
                meta = M("lintel", "ground", f"dry pack / steel shims between padstone and beam {TYPICAL}", "", "assumed", "Packing", False)
                out.append(atom(f"{bid}-pack{len(out)}", "mesh", ov.get("pad_phase", "pad_gf"), meta, sig=sig_of("pack", px, py), mesh=box(px - lx / 2, px + lx / 2, py - ly / 2, py + ly / 2, z0, z1),
                                mat="concrete"))
        return out

    def ff_joist_atoms(self, ff):
        lv = self.lv; out = []
        J = ff["joists"]
        w, d = 0.045, 0.195
        ztop = lv.ff - 0.022
        ext = J["extent"]
        y0, y1 = ext[0][1], ext[2][1]
        xs = sorted(set([round(x, 4) for x in J["x_centres"]] + [round(x, 4) for x in J["doubled"]["x"]] + [J["trimmer_by_beam4"]["x"]]))
        lbl = J["label"]
        for x in xs:
            meta = M("joist", "first", lbl if x not in J["doubled"]["x"] else J["doubled"]["label"], "4915.4A first floor joist plan",
                     "scaled" if x != J["trimmer_by_beam4"]["x"] else "scaled", "Floor joist for the new bedroom floor", False)
            out.append(atom(f"J-ff-{x:.4f}", "member", "joist", meta, sig=sig_of("jff", x), A=(x, y0, ztop), B=(x, y1, ztop),
                            section=rect_section(w, d), mat="timber", clip_to_walls=True, hanger=True))
        # noggins at mid-span between joists
        yn = J["noggins"]["y"]
        for xa, xb in zip(xs, xs[1:]):
            if xb - xa < 0.1: continue
            meta = M("joist", "first", J["noggins"]["label"], "4915.4A first floor joist plan", "scaled", "Bracing between joists", False)
            out.append(atom(f"J-nog-{xa:.3f}", "member", "joist", meta, sig=sig_of("nog", xa), A=(xa + w / 2, yn, ztop), B=(xb - w / 2, yn, ztop),
                            section=rect_section(0.045, d), mat="timber", seq_bias=0.3))
        # deck
        P = [(ext[0][0], y0), (ext[1][0], y0), (ext[2][0], y1), (ext[3][0], y1)]
        meta = M("deck", "first", ff["deck"]["label"], "4915.3A section C-C", "exact", "New upstairs floor boards", True)
        out.append(atom("DK-ff", "slab", "deck", meta, sig=sig_of("deck", P), poly=P, z0=ztop, z1=lv.ff, mat="chipboard", clip_walls=True, seq=0.8))
        meta = M("deck", "first", ff["insulation"], "4915.3A construction notes", "exact", "Sound insulation between the joists", False)
        out.append(atom("INS-ff", "slab", "ff_insulation", meta, sig=sig_of("insff", P), poly=P, z0=ztop - 0.10, z1=ztop - 0.001,
                        mat="mineral_wool", clip_walls=True, seq=0.5, between_joists=True))
        meta = M("ceiling_joist", "ground", ff["ceiling_below"], "4915.3A construction notes", "exact", "Kitchen ceiling", False)
        out.append(atom("CL-gf", "slab", "ceiling", meta, sig=sig_of("clgf", P), poly=P, z0=lv.gclg, z1=lv.gclg + 0.0125, mat="plasterboard",
                        clip_walls=True, seq=0.15))
        return out

    def extra_member_atoms(self, st):
        """members the spec adds (assumed beams for an option, ceiling-joist fields, ashlar studs, binders)"""
        out = []
        for f in st.get("member_fields", []):
            out.extend(self.member_field(f))
        for b in st.get("extra_beams", []):
            out.extend(self.beam_atoms(b))
        for m in st.get("extra_meshes", []):
            meta = M(m["group"], m["storey"], m["label"], m.get("drawing", ""), m.get("conf", "assumed"), m.get("plain"), m.get("collide", False))
            out.append(atom(m["id"], "prism", m.get("phase", "existing"), meta, sig=sig_of("xm", m["id"], m["poly"], m["z0"], m["z1"]),
                            poly=m["poly"], z0=m["z0"], z1=m["z1"], mat=m["mat"]))
        return out

    def member_field(self, f):
        """parallel members: {"id", "dir": "x"|"y", "positions": [...] | {"from","to","spacing"}, "extent": [a, b],
        "z_bottom" | "z_top", "section": [w, d], "label", "group", "phase", "mat"}"""
        out = []
        if isinstance(f["positions"], dict):
            p = f["positions"]; pos = []; v = p["from"]
            while v <= p["to"] + 1e-6: pos.append(round(v, 4)); v += p["spacing"]
        else:
            pos = f["positions"]
        w, d = f["section"]
        ztop = f["z_top"] if "z_top" in f else f["z_bottom"] + d
        a, b = f["extent"]
        for k, s in enumerate(pos):
            A3 = (a, s, ztop) if f["dir"] == "x" else (s, a, ztop)
            B3 = (b, s, ztop) if f["dir"] == "x" else (s, b, ztop)
            meta = M(f["group"], f.get("storey", "roof"), f["label"], f.get("drawing", ""), f.get("conf", "scaled"), f.get("plain"), False)
            out.append(atom(f"{f['id']}-{k:02d}", "member", f["phase"], meta, sig=sig_of("mf", f["id"], A3, B3), A=A3, B=B3,
                            section=rect_section(w, d), mat=f.get("mat", "timber"), clip_to_walls=f.get("clip_to_walls", False),
                            clip_to_roof=f.get("clip_to_roof")))
        return out

    # -------------------------------------------------------------- roofs
    def roof_atoms(self, sysspec):
        """atoms of one pitched roof system: covers (convex pieces per plane), membrane, battens, rafters, creases,
        eaves boards, ridge/hip tiles."""
        out = []
        wings = []
        for w in sysspec["wings"]:
            wings.append(R.Wing(w))
        sysm = R.RoofSystem(sysspec["id"], wings)
        if not hasattr(self, "systems"): self.systems = []
        self.systems.append((sysspec, sysm))
        sid = sysspec["id"]
        holes = []
        for h in sysspec.get("rooflights", []):
            pl = next(p for p in sysm.planes() if p.id == h["plane"])
            x0, y0, x1, y1 = h["rect"]
            holes.append((pl.key(), [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
        massing = sysspec.get("massing", False)
        lay = R.cover_layers(sysm, holes=holes)
        if massing: lay["membrane"] = []
        cov = self.S["roof_cover"]
        for k, (pl, Q, mesh) in enumerate(lay["tiles"]):
            ws = pl.wing.spec
            cat = ws.get("category", "new")
            meta = M("roof_cover", "roof", ws.get("tiles_label", cov["tiles_label"]), ws.get("drawing", cov["drawing"]), ws.get("conf", "scaled"),
                     "Roof tiles", False)
            out.append(atom(f"RC-{sid}-{pl.id}-{k}", "cover", "tiles", meta, sig=None, plane=pl, poly=Q, layer="tiles",
                            mat="tile" if cat == "new" else "existing_tile", pkey=pl.key(), wing_cat=cat))
        for k, (pl, Q, mesh) in enumerate(lay["membrane"]):
            ws = pl.wing.spec
            meta = M("roof_layer", "roof", ws.get("membrane_label", cov["membrane_label"]), ws.get("drawing", cov["drawing"]),
                     "exact" if ws.get("category") == "new" else "assumed", "Breathable roof membrane under the tiles", False)
            out.append(atom(f"RM-{sid}-{pl.id}-{k}", "cover", "membrane", meta, sig=None, plane=pl, poly=Q, layer="membrane",
                            mat="membrane", pkey=pl.key(), wing_cat=ws.get("category", "new")))
        for pl in ([] if massing else sysm.planes()):
            ws = pl.wing.spec
            # Use the same clipped tile polygons for battens and the rooflight.
            from hb_stage import battens_on
            bm=battens_on(pl,[Q for tile,Q,_ in lay['tiles'] if tile is pl])
            if bm:
                meta = M("roof_layer", "roof", ws.get("batten_label", cov["batten_label"]), ws.get("drawing", cov["drawing"]),
                         "exact" if ws.get("category") == "new" else "assumed", "Tiling battens", False)
                out.append(atom(f"RB-{sid}-{pl.id}", "batten_set", "battens", meta, sig=None, plane=pl, mesh=bm, mat="batten",
                                wing_cat=ws.get("category", "new"), pkey=pl.key()))
            # rafters
            pieces = sysm.plane_pieces(pl)
            if not pieces: continue
            rp = ws.get("rafters", {})
            pos_spec = rp.get("positions", {}).get(pl.id.split(".")[-1]) or rp.get("default")
            if not pos_spec: continue
            pos = R.positions_for(pl, pos_spec, pieces)
            w_, d_ = rp["section"]
            rl_rects = [h for h in sysspec.get("rooflights", []) if h["plane"] == pl.id]
            lines = []
            for (p_hi, p_lo, s, types) in R.rafter_lines(sysm, pl, pos):
                cut = None
                ae = 0 if abs(pl.e[0]) > 0.5 else 1
                for h in rl_rects:
                    if h["rect"][ae] + 0.03 < p_hi[ae] < h["rect"][ae + 2] - 0.03:
                        cut = h; break
                if cut is None:
                    lines.append((p_hi, p_lo, s, types)); continue
                # rafter interrupted by the roof light: stops at the trimmers (45 + 45 each side)
                x0, y0, x1, y1 = cut["rect"]
                ax = 1 if abs(pl.d[1]) > 0.5 else 0
                lo_, hi_ = (y0, y1) if ax == 1 else (x0, x1)
                tw = cut.get("trimmer", 0.09)
                a_ = p_hi[ax]; b_ = p_lo[ax]
                for (qa, qb) in ((a_, hi_ + tw if a_ > b_ else lo_ - tw), (lo_ - tw if a_ > b_ else hi_ + tw, b_)):
                    P0 = list(p_hi); P1 = list(p_hi); P0[ax] = qa; P1[ax] = qb
                    if abs(qb - qa) > 0.1: lines.append((tuple(P0), tuple(P1), s, types))
            for h in rl_rects:
                x0, y0, x1, y1 = h["rect"]
                tw = h.get("trimmer", 0.09); dbl = h.get("doubled", [])
                xa = max([x for x in dbl if x < x0 + 0.05] or [x0]) + 0.0225; xb = min([x for x in dbl if x > x1 - 0.05] or [x1]) - 0.0225
                for yy in (y1 + tw / 2, y0 - tw / 2):
                    V_, F_, Mx_, L_, key_ = R.member_on_plane(pl, (xa, yy), (xb, yy), tw, rp["section"][1])
                    A3 = (Mx_[0][3], Mx_[1][3], Mx_[2][3]); B3 = (A3[0] + Mx_[0][0] * L_, A3[1] + Mx_[1][0] * L_, A3[2] + Mx_[2][0] * L_)
                    meta = M("rafter", "roof", "roof light trimmer (top and bottom): 2no.45x95mm C24", ws.get("drawing", cov["drawing"]), "scaled",
                             "Timber frame round the roof window", False)
                    out.append(atom(f"RT-{sid}-trim-{yy:+.3f}", "member", "rafter", meta, sig=sig_of("trim", A3, B3), A=A3, B=B3,
                                    section=[(0.0, 0.0), (rp["section"][1], 0.0), (rp["section"][1], -tw), (0.0, -tw)] if False else rect_section(tw, rp["section"][1]),
                                    mat="timber", wing_cat=ws.get("category", "new")))
            if ws.get("category") == "new":
                # where a new roof is built over an existing one, its rafters stop where they would cut into the
                # existing rafters (they land on layboards over them)
                seated = []
                for pl_ in lines:
                    segs = [(pl_[0], pl_[1])]
                    for w2 in sysm.wings:
                        if w2.category != "existing": continue
                        for q in w2.planes:
                            # region (inside w2) where this new rafter's underside is below q's rafter tops + 25 mm layboard
                            dv = (R.COVER_T + d_) / pl.cos; dq = R.COVER_T / q.cos
                            hp = poly_halfplanes(w2.footprint) + [(pl.A - q.A, pl.B - q.B, (pl.C - dv) - (q.C - dq) - 0.025)]
                            hp += [(q.A - o.A, q.B - o.B, q.C - o.C) for o in w2.planes if o is not q]
                            nxt = []
                            for (a_, b_) in segs:
                                r = clip_segment_convex(a_, b_, ccw_poly_from_hp(hp))
                                if not r: nxt.append((a_, b_)); continue
                                L2 = ((b_[0] - a_[0]), (b_[1] - a_[1]))
                                for (t0, t1) in interval_minus([(0, 1)], [r]):
                                    pa_ = (a_[0] + L2[0] * t0, a_[1] + L2[1] * t0); pb_ = (a_[0] + L2[0] * t1, a_[1] + L2[1] * t1)
                                    if math.hypot(pb_[0] - pa_[0], pb_[1] - pa_[1]) > 0.1: nxt.append((pa_, pb_))
                            segs = nxt
                    for (a_, b_) in segs: seated.append((a_, b_, pl_[2], pl_[3]))
                lines = seated
            for (p_hi, p_lo, s, types) in lines:
                V, F, Mx, L, key = R.member_on_plane(pl, p_hi, p_lo, w_, d_)
                meta = M("rafter", "roof", rp["label"], ws.get("drawing", cov["drawing"]), rp.get("conf", "scaled"), "Roof rafter", False)
                A3 = (Mx[0][3], Mx[1][3], Mx[2][3])
                B3 = (A3[0] + Mx[0][0] * L, A3[1] + Mx[1][0] * L, A3[2] + Mx[2][0] * L)
                out.append(atom(f"RF-{sid}-{pl.id}-{s:+.3f}", "member", "rafter", meta, sig=sig_of("raf", A3, B3, w_, d_), A=A3, B=B3,
                                section=rect_section(w_, d_), mat="timber" if ws.get("category") == "new" else "timber_existing", plumb=True,
                                linear=True, wing_cat=ws.get("category", "new"), plane=pl, ends=types, new_override=ws.get("new_rafters"),
                                tail=(max(0.0, ws.get("overhang_by_plane", {}).get(pl.id.split(".")[-1], ws.get("overhang", 0.25)) - 0.07) / pl.cos
                                      if types and types[-1] == "eave" else 0.0)))
        # creases: ridge boards, hips, valleys
        for (kind, pa, pb, q0, q1) in sysm.creases():
            wa, wb = pa.wing.spec, pb.wing.spec
            cat = "new" if "new" in (wa.get("category"), wb.get("category")) else "existing"
            same = pa.wing is pb.wing
            spec_w = wa if wa.get("category") == cat else wb
            if massing and kind != "valley":
                tag = "ridge_tiles" if kind == "ridge" else "hip_tiles"
            elif massing:
                tag = None
            elif kind == "ridge":
                w_, d_ = spec_w.get("ridge_section", [0.032, 0.175])
                A3 = (q0[0], q0[1], pa.z(q0) - R.COVER_T / pa.cos - 0.018); B3 = (q1[0], q1[1], pa.z(q1) - R.COVER_T / pa.cos - 0.018)
                lbl = spec_w.get("ridge_label", "32x175mm ridgeboard")
                meta = M("ridge", "roof", lbl, spec_w.get("drawing", ""), spec_w.get("conf", "scaled"), "Ridge board at the top of the roof", False)
                out.append(atom(f"RR-{sid}-{pa.id}-{pb.id}", "member", "ridge", meta, sig=sig_of("ridge", A3, B3), A=A3, B=B3,
                                section=rect_section(w_, d_), mat="timber" if cat == "new" else "timber_existing", linear=True, wing_cat=cat,
                                new_override=wa.get("new_ridge") or wb.get("new_ridge")))
                tag = "ridge_tiles"
            elif kind in ("hip", "valley"):
                w_, d_ = spec_w.get("hip_section" if kind == "hip" else "valley_section", [0.045, 0.145])
                lbl = spec_w.get("hip_label" if kind == "hip" else "valley_label", f"{kind} rafter")
                meta = M(kind, "roof", lbl, spec_w.get("drawing", ""), spec_w.get("conf", "scaled"), "Hip rafter" if kind == "hip" else "Valley rafter", False)
                nspec = (wa.get("new_hips") if kind == "hip" else wa.get("new_valleys")) or (wb.get("new_hips") if kind == "hip" else wb.get("new_valleys"))
                seat=R.seated_crease(pa,pb,q0,q1,w_)
                if seat:
                    V, F, Mx, L, key = R.crease_member(pa, pb, *seat, w_, d_)
                    A3 = (Mx[0][3], Mx[1][3], Mx[2][3]); B3 = (A3[0] + Mx[0][0] * L, A3[1] + Mx[1][0] * L, A3[2] + Mx[2][0] * L)
                    out.append(atom(f"R{kind[0].upper()}-{sid}-{pa.id}-{pb.id}-{q0[0]:.2f}", "member", kind, meta, sig=sig_of(kind, A3, B3),
                                    A=A3, B=B3, section=rect_section(w_, d_), mat="timber" if cat == "new" else "timber_existing", plumb=True,
                                    linear=True, wing_cat=cat, new_override=nspec))
                tag = "hip_tiles" if kind == "hip" else ("valley_lead" if cat == "new" else None)
            else:
                tag = "valley_lead"
            # weathering on the crease
            if tag in ("ridge_tiles", "hip_tiles"):
                lbl = cov["ridge_tile_label"] if tag == "ridge_tiles" else cov["hip_tile_label"]
                meta = M("roof_cover", "roof", lbl, cov["drawing"], "exact" if cat == "new" else "assumed", "Ridge / hip tiles", False)
                A3 = (q0[0], q0[1], pa.z(q0)); B3 = (q1[0], q1[1], pa.z(q1))
                if A3[2] < B3[2]: A3, B3 = B3, A3
                sec = [(-0.11, 0.0), (0.11, 0.0), (0.08, 0.06), (0.0, 0.09), (-0.08, 0.06)]
                sec = [(y, z) for (y, z) in sec]
                out.append(atom(f"RT-{sid}-{pa.id}-{pb.id}-{q0[0]:.2f}", "member", "roof_trim", meta, sig=sig_of(tag, A3, B3), A=A3, B=B3,
                                section=sec, mat="tile" if cat == "new" else "existing_tile", raise_section=True, linear=True, wing_cat=cat))
            if tag == "valley_lead" or (kind == "valley" and cat == "new"):
                meta = M("valley", "roof", self.Vt["structure"]["roof_structure"]["rear_extension"]["valley"], "4915.4A roof plan", "exact",
                         "Lead-lined valley gutter", False)
                strips = []
                for pl_ in (pa, pb):
                    PP = next((P for (q, P) in sysm.pieces if q is pl_ and any(seg_point_dist(v, q0, q1)[0] < 0.004 for v in P)), None)
                    if PP is None: continue
                    inward = unit(sub(centroid(PP), mul(add(q0, q1), 0.5)))
                    dd = unit(sub(q1, q0)); nrm = (dd[1], -dd[0])
                    if dot(nrm, inward) < 0: nrm = mul(nrm, -1)
                    S4 = [q0, q1, add(q1, mul(nrm, 0.15)), add(q0, mul(nrm, 0.15))]
                    S4 = clip_convex(S4, poly_halfplanes(PP)) or S4
                    pts = R.lift(pl_, S4)
                    strips.append(slab3d(pts, pl_.n, 0.0005, 0.0035))
                if strips:
                    out.append(atom(f"RV-{sid}-{pa.id}-{pb.id}-{q0[0]:.2f}", "mesh", "roof_lead", meta, sig=sig_of("vlead", q0, q1),
                                    mesh=merge_meshes(strips), mat="lead", wing_cat="new"))
        # eaves: fascia, soffit, gutter. Row 179: where two eave lines meet (a hip corner, or an inside corner) every board is
        # mitred on the corner's bisector; square-ended boards overlapped there in one plane (z-fighting soffits and fascias).
        RUNS = R.board_edges(sysm) if not massing else [(w,p,a,b,a,b) for w,p,a,b in R.eave_edges(sysm)]
        def exterior_run(pl,a,b):
            # An upper eave may continue over a lower roof after an inside
            # corner. That short step is not a third wing of the soffit joint.
            probe = add(mul(add(a,b),.5), mul(pl.d,.002))
            return massing or sysm.z(probe) is None
        EDGES = [run[:4] for run in RUNS if exterior_run(run[1],run[2],run[3])]; SOFFITS = []
        def _mitres(a, b):
            hps, ends = [], []
            for (c, d_this) in ((a, unit(sub(b, a))), (b, unit(sub(a, b)))):
                count = len(hps)
                for (_w2, _p2, a2, b2) in EDGES:
                    for (c2, far) in ((a2, b2), (b2, a2)):
                        if length(sub(c2, c)) > 0.012 or length(sub(far, c2)) < 1e-6: continue
                        d_oth = unit(sub(far, c2))
                        if abs(dot(d_oth, d_this)) > 0.999: continue          # the same line (or its continuation)
                        m = unit(add(d_this, d_oth)); nperp = (-m[1], m[0])
                        sgn = 1.0 if dot(d_this, nperp) >= 0 else -1.0
                        # keep dot(p - c, nperp) * sgn >= 0  ->  -sgn*(nperp.p - nperp.c) <= 0
                        hps.append((-sgn * nperp[0], -sgn * nperp[1], sgn * (nperp[0] * c[0] + nperp[1] * c[1])))
                ends.append(len(hps)>count)
            return hps, ends
        def _cut(P, hps):
            Q = clip_convex(P, hps) if hps else P
            return Q if Q else P
        for (wing, pl, a, b, tile_a, tile_b) in RUNS:
            ws = wing.spec
            if ws.get("no_eaves_boards"): continue
            cat = ws.get("category", "new")
            dd = unit(sub(b, a)); outw = (dd[1], -dd[0])
            if dot(outw, pl.d) < 0: outw = mul(outw, -1)
            zt = pl.z(a)                                    # tile surface at the eave line
            soff = ws.get("soffit_by_plane", {}).get(pl.id.split(".")[-1], ws.get("soffit_z", self.lv.soffit))
            ov = ws.get("overhang_by_plane", {}).get(pl.id.split(".")[-1], ws.get("overhang", 0.25))
            outside = exterior_run(pl,a,b)
            HP, joined = _mitres(a,b) if outside else ([],(False,False))
            rakes=R.end_rakes(wing,pl,a,b,tile_a,tile_b,HP)
            # At an inside corner an inset board runs on past the tile's
            # corner station. Cut its extended blank to the actual mitre.
            A = add(a, mul(dd,-ov-.12)) if joined[0] and not massing else a
            B = add(b, mul(dd, ov+.12)) if joined[1] and not massing else b
            fa = add(A, mul(outw, -0.05)); fb = add(B, mul(outw, -0.05))
            ztop = zt - R.COVER_T / pl.cos - 0.03 * pl.tan
            fas = [fa, fb, add(fb, mul(outw, -0.02)), add(fa, mul(outw, -0.02))]
            meta = M("roof_cover", "roof", self.Vt["structure"]["roof_structure"]["coverings"]["fascia"], cov["drawing"],
                     "exact" if cat == "new" else "assumed", "Fascia and soffit boards", False)
            edge_id = f"RE-{sid}-{pl.id}-{tile_a[0]:.2f}-{tile_a[1]:.2f}"
            if not outside:
                step=R.step_board(sysm,pl,a,b)
                if step:out.append(atom(edge_id,'mesh','eaves',meta,sig=sig_of('eave-step',a,b,step[0]),mesh=step,mat='upvc_white',wing_cat=cat))
                continue
            from hb_geom import poly_minus_convex
            from hb_eaves import porch_trim
            porch = porch_trim(self.S, pl, (a, b), soff) if sid == 'porch' else None
            fq = _cut(fas, HP)
            # a fascia gives way to the boards already laid at this level (No.21's traced wing eaves miss their corners by 225 mm)
            prev = [q for (q, qz) in SOFFITS if abs(qz - soff) < 0.02]
            parts = [R.eave_solid(Q, soff, max(soff + 0.05, ztop), rakes) for Q in (poly_minus_convex(ccw(fq), prev) if prev else [fq])]
            SOFFITS.append((ccw(fq), soff))
            sof = [add(fa, mul(outw, -0.02)), add(fb, mul(outw, -0.02)), add(fb, mul(outw, -ov + 0.002)), add(fa, mul(outw, -ov + 0.002))]
            if ov > 0.08:
                # a soffit gives way to the soffits already laid in this roof (No.21's traced eaves overlap by up to 40 mm)
                from hb_geom import poly_minus_convex
                sq = _cut(sof, HP)
                for Q in (poly_minus_convex(ccw(sq), [q for (q, qz) in SOFFITS if abs(qz - soff) < 0.02]) if SOFFITS else [sq]):
                    parts.append(prism(Q, soff, soff + 0.012))
                SOFFITS.append((ccw(sq), soff))
            if porch:
                meta = M('roof_cover', 'roof', 'Anthracite fascia, boxed bargeboard and soffit return',
                         ws['drawing'] + ' / measured porch verge, audit 4', 'scaled', 'Porch eaves and verge', False)
                for suffix, mesh in porch:
                    out.append(atom(edge_id + suffix, 'mesh', 'eaves', meta, sig=sig_of(edge_id, suffix, mesh[0]),
                                    mesh=mesh, mat='anthracite_upvc', wing_cat=cat))
            else:
                out.append(atom(edge_id, "mesh", "eaves", meta, sig=sig_of("eave", a, b, soff), mesh=merge_meshes(parts),
                                mat="upvc_white", wing_cat=cat))
            gut = [add(fa, mul(outw, 0.0)), add(fb, mul(outw, 0.0)), add(fb, mul(outw, 0.11)), add(fa, mul(outw, 0.11))]
            meta = M("roof_cover", "roof", "gutters 110mm half round black upvc", cov["drawing"], "exact" if cat == "new" else "assumed",
                     "Gutter", False)
            out.append(atom(f"RG-{sid}-{pl.id}-{tile_a[0]:.2f}-{tile_a[1]:.2f}", "mesh", "eaves", meta, sig=sig_of("gut", a, b), mesh=R.eave_solid(_cut(gut, HP), ztop - 0.07, ztop - 0.005, rakes, gutter=True),
                            mat="black_upvc", wing_cat=cat))
        # abutment flashings (lean-to tops against a wall)
        for (wing, pl, a, b) in R.top_edges(sysm):
            ws = wing.spec
            dd = unit(sub(b, a)); inw = (dd[1], -dd[0])
            if dot(inw, pl.d) < 0: inw = mul(inw, -1)
            S4 = [a, b, add(b, mul(inw, 0.15)), add(a, mul(inw, 0.15))]
            meta = M("roof_cover", "roof", ws.get("abutment_label", self.Vt["structure"]["walls"]["cavity_trays_at_roofs"][0]), cov["drawing"],
                     "exact" if ws.get("category") == "new" else "assumed", "Lead flashing where the roof meets the wall", False)
            out.append(atom(f"RA-{sid}-{pl.id}-{a[0]:.2f}", "mesh", "roof_lead", meta, sig=sig_of("abut", a, b), mesh=slab3d(R.lift(pl, S4), pl.n, 0.0005, 0.0035),
                            mat="lead", wing_cat=ws.get("category", "new")))
        # roof lights
        for h in sysspec.get("rooflights", []):
            pl = next(p for p in sysm.planes() if p.id == h["plane"])
            x0, y0, x1, y1 = h["rect"]
            name=f"RL-{sid}-{slug(h['label'])}"
            meta=M("rooflight","roof",h["label"],h.get("drawing",""),h.get("conf","scaled"),"Roof window",False)
            from hb_geom import prism_varz
            rail=min(.055,(x1-x0)/5,(y1-y0)/5)
            def member(xa,xb,ya,yb,lo,hi):
                return prism_varz([(xa,ya),(xb,ya),(xb,yb),(xa,yb)],
                                  lambda p:pl.z(p)+lo/pl.cos,lambda p:pl.z(p)+hi/pl.cos)
            rails=[member(x0,x1,y0,y0+rail,-R.COVER_T,.055),member(x0,x1,y1-rail,y1,-R.COVER_T,.055),
                   member(x0,x0+rail,y0+rail,y1-rail,-R.COVER_T,.055),member(x1-rail,x1,y0+rail,y1-rail,-R.COVER_T,.055)]
            out.append(atom(name+"-frame","mesh","existing",meta,sig=sig_of("rl-frame",h["rect"]),mesh=merge_meshes(rails),mat="anthracite_upvc",wing_cat=pl.wing.spec.get("category","new")))
            glass=member(x0+rail,x1-rail,y0+rail,y1-rail,.024,.034)
            out.append(atom(name+"-glass","mesh","existing",meta,sig=sig_of("rl-pane",h["rect"]),mesh=glass,mat="glass",wing_cat=pl.wing.spec.get("category","new")))
        # stated extra roof members on a plane (trimmers, doubled rafters, plates)
        return out

    def flat_roof_atoms(self, fr, roofs):
        meta = M("roof_cover", "ground", fr["label"], fr.get("drawing", ""), fr.get("conf", "scaled"), fr.get("plain", "Flat roof"), False)
        P = fr["poly"]
        if fr.get("mat")=="polycarbonate" and "z_house" in fr:
            from hb_conservatory import canopy
            return canopy(fr, roofs)
        if "z_house" in fr:            # lean-to (polycarbonate): plane through the two edge heights
            zh, zr = fr["z_house"], fr["z_rear"]; ya, yb = min(p[1] for p in P), max(p[1] for p in P)
            zf = (zh, zr, ya, yb, 0.016)
            return [atom(fr["id"], "slab", "existing", meta, sig=sig_of("flat", fr["id"]), poly=P, z0=min(zh, zr) - 0.016, z1=max(zh, zr),
                         zfun=zf, mat=fr.get("mat", "felt"), clip_walls=True)]
        return [atom(fr["id"], "slab", "existing", meta, sig=sig_of("flat", fr["id"]), poly=P, z0=fr["z_top"] - fr.get("t", 0.15), z1=fr["z_top"],
                     mat=fr.get("mat", "felt"), clip_walls=True)]

    # -------------------------------------------------------------- wall plates on eaves walls, eaves wall tops
    def eave_systems(self):
        return getattr(self, "systems", [])

    def wall_plate_atoms(self, st):
        out = []
        for ps in st.get("wall_plates", []):
            for W in self.walls:
                if W.id.split("~")[0] not in ps["walls"]: continue
                if abs(W.z1 - ps["z"]) > 0.03 and not W.profile: continue
                L = W.layers()
                core = [l for l in L if not l.get("lining") and not l.get("void")]
                inner = core[-1]
                w_, h_ = ps["section"]
                o_in = inner["o1"]                          # plate flush with the inner face of the inner leaf
                c0, c1 = W.c_of(o_in), W.c_of(o_in - w_)
                if ps.get("position") == "centre":
                    c0, c1 = -w_ / 2, w_ / 2
                ua, ub = W.ua, W.ub
                if W.profile:
                    ub_flat = max(u for u, z in W.profile if abs(z - ps["z"]) < 0.01) if any(abs(z - ps["z"]) < 0.01 for u, z in W.profile) else None
                    if ub_flat is None: continue
                    # plate only on the flat part of a raking wall
                    flat = [u for u, z in W.profile if abs(z - ps["z"]) < 0.01]
                    ua, ub = max(ua, min(flat)), min(ub, max(flat))
                cm = (c0 + c1) / 2
                ua = max(ua, max(W.end_u("a", c0), W.end_u("a", c1))); ub = min(ub, min(W.end_u("b", c0), W.end_u("b", c1)))
                # row 179: a plate only where a roof covers it with room for the plate under the tiles (WP-F-extRear ran on at
                # 5.095 under the catslide, whose tiles are lower: 650 mm of plate stood through the roof)
                if self.eave_systems():
                    def roof_ok(u):
                        zs = []
                        for c_ in (c0, c1):
                            p_ = W.point(u, c_)
                            zz = [sm.z(p_) for (_, sm) in self.eave_systems()]
                            zz = [z for z in zz if z is not None]
                            if not zz: return True                       # no pitched roof over it (flat roof / open)
                            zs.append(max(zz))
                        return min(zs) - R.COVER_T * 1.5 >= ps["z"] + h_ - 0.01
                    N_ = 60
                    ok = [roof_ok(ua + (ub - ua) * k / N_) for k in range(N_ + 1)]
                    def roof_z(u):
                        zz = [sm.z(W.point(u, cm_)) for (_, sm) in self.eave_systems() for cm_ in ((c0 + c1) / 2,)]
                        zz = [z for z in zz if z is not None]
                        return max(zz) if zz else None
                    rz = [z for z in (roof_z(ua + (ub - ua) * k / 12) for k in range(13)) if z is not None]
                    along_slope = bool(rz) and max(rz) - min(rz) > 0.2        # only a plate running UP a roof slope (a raking wall)
                    if not all(ok) and along_slope:
                        runs, cur = [], None
                        for k, o_ in enumerate(ok):
                            if o_ and cur is None: cur = k
                            if (not o_ or k == N_) and cur is not None: runs.append((cur, k if o_ else k - 1)); cur = None
                        if not runs: continue
                        k0, k1 = max(runs, key=lambda r: r[1] - r[0])
                        ua, ub = ua + (ub - ua) * k0 / N_, ua + (ub - ua) * k1 / N_
                        if ub - ua < 0.2: continue
                A3 = (*W.point(ua, cm), ps["z"]); B3 = (*W.point(ub, cm), ps["z"])
                meta = M("wall_plate", "roof", ps["label"], ps.get("drawing", ""), ps.get("conf", "scaled"), "Timber plate the roof sits on", False)
                out.append(atom(f"WP-{W.id}", "member", ps.get("phase", "plate"), meta, sig=sig_of("wp", A3, B3), A=A3, B=B3,
                                section=rect_section(w_, h_), mat="timber" if ps.get("category", "new") == "new" else "timber_existing",
                                plate_wall=W.id, linear=True))
                W.layer_tops[inner["key"]] = ps["z"] - h_
                for l in L:
                    if ps.get("position") == "centre" and not l.get("lining"):
                        W.layer_tops[l["key"]] = ps["z"] - h_
                    elif l is not inner and not l.get("lining"):
                        W.layer_tops[l["key"]] = min(W.layer_tops.get(l["key"], 9), ps.get("outer_top", ps["z"] - h_))
                W.z1 = max(W.z1, ps["z"]) if False else W.z1
        return out

    def walls_up_to_flat_roofs(self, st, reach=0.06):
        """row 179: walls under a flat or lean-to roof stop 1.5 mm under its underside (the outshot's walls stopped 20 mm short:
        a slot under the roof all round, seen from the store and the garden)"""
        for fr in st.get("flat_roofs", []):
            P = fr["poly"]
            if "z_house" in fr:
                zh, zr = fr["z_house"], fr["z_rear"]; ya, yb = min(p[1] for p in P), max(p[1] for p in P)
                under = lambda p, zh=zh, zr=zr, ya=ya, yb=yb: zh + (zr - zh) * (p[1] - ya) / (yb - ya) - 0.016
            else:
                under = lambda p, fr=fr: fr["z_top"] - fr.get("t", 0.15)
            xs = [p[0] for p in P]; ys = [p[1] for p in P]
            inside = lambda p: min(xs) - 0.05 <= p[0] <= max(xs) + 0.05 and min(ys) - 0.05 <= p[1] <= max(ys) + 0.05
            for W in self.walls:
                if fr.get('mat')=='polycarbonate' and 'conservatory side wall' in W.meta.get('type','').lower():
                    # Datum is clear height under the roof. The masonry carrier
                    # is outside the sheet footprint with its inner face on the edge.
                    W.profile=[(u,under(W.point(u,0))+.016) for u in (W.ua,W.ub)]
                    W.z1=max(z for _,z in W.profile);continue
                if W.profile or not (inside(W.point(W.ua, 0)) and inside(W.point(W.ub, 0))): continue
                zu = [under(W.point(u, 0)) for u in (W.ua, (W.ua + W.ub) / 2, W.ub)]
                if all(0 < z - W.z1 <= reach for z in zu):
                    if max(zu) - min(zu) < 1e-4: W.z1 = zu[0] - 0.0015
                    else: W.profile = [(u, under(W.point(u, 0)) - 0.0015) for u in (W.ua, W.ub)]; W.z1 = max(z for _, z in W.profile)
                    W.meta["profile_note"] = f"top up to the underside of the flat roof '{fr['id']}'"

    def apply_eaves_tops(self, st):
        """party wall up to the roof underside (it carries the shared roof as a gable); walls marked
        profile_from_roof get a raking top under the roof planes"""
        for W in self.walls:
            sid = W.meta.get("profile_from_roof") or (st.get("party_profile_roof") if W.ckey == "party" and W.storey == "first" else None)
            if sid and W.ckey == "party" and W.storey == "first": st.setdefault("profile_depth", {}).setdefault(W.id.split("~")[0], 0.10)
            if not sid: continue
            sysm = next((s for (sp, s) in self.eave_systems() if sp["id"] == sid), None)
            if sysm is None: continue
            prof = []
            n = 40
            dep = st.get("profile_depth", {}).get(W.id.split("~")[0], 0.0015)    # row 179: 1.5 mm under the roof (6 mm showed a slot at the verge)
            cfaces = (0.0,) if W.ckey != "massing" else (W.full_extent_c()[0], 0.0, W.full_extent_c()[1])
            for k in range(n + 1):
                u = W.ua + (W.ub - W.ua) * k / n
                tops = []
                # massing walls (No.21) are thick and stand under a slope: their top follows the LOWER face (row 179: the
                # centre-line profile left the outer face 48 mm through No.21's eaves)
                for c_ in cfaces:
                    p = W.point(u, c_)
                    z = sysm.z(p)
                    if z is None: continue
                    pl = max((pl for pl in sysm.planes()), key=lambda q: -abs(q.z(p) - z))
                    tops.append(z - (R.COVER_T + dep) / pl.cos)
                if tops: prof.append((u, min(tops)))
            if prof:
                if W.meta.get("profile_mode") == "min":
                    prof = [(u, min(z, W.top_at(u))) for (u, z) in prof]
                W.profile = prof
                W.z1 = max(z for u, z in prof)
                W.meta["profile_note"] = f"top follows the underside of roof '{sid}'"

    # -------------------------------------------------------------- embedded members -> holes in walls
    def embed_holes(self, A):
        for a in A:
            if a["kind"] not in ("member", "mesh") or a.get("phase") in ("rafter",): continue
            if a["kind"] == "member" and a["meta"]["group"] not in ("steel", "timber_beam", "lintel"): continue
            if a["kind"] == "mesh" and not a.get("embed"): continue
            pts = self._member_pts(a)
            for W in self.walls:
                if W.storey == "first" and max(p[2] for p in pts) < W.z0: continue
                us = [u_of(W, p[:2]) for p in pts]; cs = [dot(sub(p[:2], W.a), W.n) for p in pts]; zs = [p[2] for p in pts]
                cl, ch = -W.t / 2, W.t / 2
                if max(cs) <= cl + 1e-3 or min(cs) >= ch - 1e-3: continue
                if max(us) <= W.ua + 1e-3 or min(us) >= W.ub - 1e-3: continue
                if max(zs) <= W.z0 + 1e-3 or min(zs) >= W.z1 - 1e-3: continue
                # outside offsets of the member's across-range
                o_lo = min(W.t / 2 - W.out * c for c in (min(cs), max(cs))); o_hi = max(W.t / 2 - W.out * c for c in (min(cs), max(cs)))
                W.holes.append((max(min(us), W.ua - 1), min(max(us), W.ub + 1), min(zs), max(zs), o_lo, o_hi))
                a.setdefault("embedded_in", []).append(W.id)

    def _member_pts(self, a):
        if a["kind"] == "mesh": return a["mesh"][0]
        from hb_geom import frame_matrix, apply_matrix, extrude_section
        A3, B3 = a["A"], a["B"]
        Mx = frame_matrix(A3, v3s(B3, A3))
        L = math.dist(A3, B3)
        pts = []
        for sec in [a["section"]] + [s for s, m in a.get("extra_sections", []) if s]:
            V, F = extrude_section(sec, L)
            pts.extend(apply_matrix(Mx, V))
        return pts

    # -------------------------------------------------------------- rooms (no geometry)
    def room_atoms(self, st, gsrc, fsrc):
        out = []
        for stn, V in (("ground", gsrc), ("first", fsrc)):
            for r in V["storeys"][stn]["rooms"]:
                out.append(dict(name=r["name"], poly=r["poly"], storey=stn, floor=self.lv.ffl if stn == "ground" else self.lv.ff,
                                ceiling=val(r.get("ceiling")) if isinstance(val(r.get("ceiling")), (int, float)) else None))
        return out


def ccw_poly_from_hp(hp, big=60.0):
    P = [(-big, -big), (big, -big), (big, big), (-big, big)]
    return clip_convex(P, hp) or [(0, 0), (1e-6, 0), (0, 1e-6)]


def v3s(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def key_in(sel, k, f):
    if sel == "all": return True
    name = f["name"][:12]
    for s in sel:
        if s.get("name", "")[:12] == name and k in s.get("idx", []): return True
    return False


def _convex(P):
    n = len(P)
    s = None
    for i in range(n):
        a, b, c = P[i], P[(i + 1) % n], P[(i + 2) % n]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cr) < 1e-12: continue
        if s is None: s = cr > 0
        elif (cr > 0) != s: return False
    return True
