"""Walls for the house generator (pure Python): constructions (real layer build-ups), per-layer cell meshes with
openings, embedded members, raking tops and course lifts, and corner joins (per-layer mitres at L corners, butt
trims at T junctions).

Wall local frame: origin at line start a, d = unit(b - a), n = right-hand normal (d.y, -d.x) in plan. c is measured
along n. A wall's `out` (+1/-1) says which side is outside; layers are listed OUTSIDE -> INSIDE."""
import math
from hb_geom import sub, add, mul, dot, unit, length, line_intersect, hexa, merge_meshes, interval_minus

# ---------------------------------------------------------------- constructions
# Each layer: key, t (thickness, None = fills the rest of the drawn thickness), mat, group, label, plain,
# void (no geometry), lining (sits outside the drawn core, room side), z ("core" | "room" = floor..ceiling).
CONSTRUCTIONS = {
    "cav337_new": dict(name="337 cavity wall (new)", layers=[
        dict(key="brick", t=0.102, mat="brick", group="wall_outer", label="102mm face brickwork (to match the existing) external skin",
             plain="Outer brick wall, to match the house"),
        dict(key="cavity", t=0.050, void=True, group="wall_cavity", label="min 50mm clear cavity; austenitic s/s wall ties at 750 h x 450 v"),
        dict(key="pir", t=0.085, mat="pir", group="wall_insulation", label="85mm Celotex CW4000 partial cavity fill insulation",
             plain="Insulation boards in the wall cavity"),
        dict(key="block", t=None, mat="block", group="wall_inner",
             label="100mm internal skin of Thermalite 'shield' blockwork or similar (min 3.5N/mm2)", plain="Inner block wall"),
        dict(key="dabs", t=0.010, void=True, lining=True, group="wall_lining", label="adhesive dabs"),
        dict(key="board", t=0.0155, mat="plasterboard", group="wall_lining", lining=True, z="room", finish=True,
             label="1no. layer 12.5mm Gyproc wallboard plasterboard drylining on dabs with plaster skim coat",
             plain="Plastered inside face of the wall"),
    ]),
    "cav_existing": dict(name="existing cavity wall", layers=[
        dict(key="brick", t=0.1025, mat="existing_brick", group="wall_outer", label="existing brick outer leaf (build-up not drawn; assumed)",
             plain="Existing outer brickwork", conf="assumed"),
        dict(key="cavity", t=None, void=True, group="wall_cavity", label="existing cavity (assumed unfilled)", conf="assumed"),
        dict(key="inner", t=0.1025, mat="existing_brick", group="wall_inner", label="existing brick inner leaf (assumed)",
             plain="Existing inner brickwork", conf="assumed"),
        dict(key="plaster", t=0.013, mat="plaster", group="wall_lining", label="existing plaster finish (assumed)", plain="Existing plaster",
             conf="assumed"),
    ]),
    "party": dict(name="party wall (existing)", layers=[
        dict(key="plaster21", t=0.013, mat="plaster", group="wall_lining", label="plaster, No.21 side (assumed)", conf="assumed"),
        dict(key="leaf21", t=0.1025, mat="existing_brick", group="wall_outer", label="party wall, No.21 leaf (assumed)", conf="assumed"),
        dict(key="cavity", t=None, void=True, group="wall_cavity", label="party wall cavity (assumed)", conf="assumed"),
        dict(key="leaf23", t=0.1025, mat="existing_brick", group="wall_inner", label="party wall, No.23 leaf (assumed)", conf="assumed"),
        dict(key="plaster", t=0.013, mat="plaster", group="wall_lining", label="existing plaster finish (assumed)", conf="assumed"),
    ]),
    "masonry_int": dict(name="existing internal masonry", layers=[
        dict(key="plaster_a", t=0.013, mat="plaster", group="wall_lining", label="existing plaster (assumed)", conf="assumed"),
        dict(key="core", t=None, mat="existing_brick", group="wall_inner", label="existing internal masonry wall 'M'",
             plain="Existing inside wall"),
        dict(key="plaster_b", t=0.013, mat="plaster", group="wall_lining", label="existing plaster (assumed)", conf="assumed"),
    ]),
    "leaf_existing": dict(name="existing single leaf", layers=[
        dict(key="core", t=None, mat="existing_brick", group="wall_inner", label="existing inner leaf kept", plain="Existing inner brickwork kept"),
        dict(key="plaster", t=0.013, mat="plaster", group="wall_lining", label="existing plaster (assumed)", conf="assumed"),
    ]),
    "solid_existing": dict(name="existing solid wall", layers=[
        dict(key="core", t=None, mat="existing_brick", group="wall_outer", label="existing masonry (build-up not drawn; assumed solid)",
             conf="assumed", plain="Existing brick wall"),
    ]),
    "massing": dict(name="neighbour massing", layers=[
        dict(key="core", t=None, mat="existing_brick", group="wall_outer", label="No.21 (neighbour) — massing from the drawings, assumed",
             conf="assumed", plain="Next door (No.21)"),
    ]),
    "block_int": dict(name="100 blockwork partition (new)", layers=[
        dict(key="dabs_a", t=0.010, void=True, lining=True, group="wall_lining", label="dabs"),
        dict(key="board_a", t=0.0155, mat="plasterboard", group="wall_lining", lining=True, z="room", finish=True,
             label="1 layer 12.5mm Gyproc wallboard on dabs, joints taped & sealed, skim", plain="Plastered wall face"),
        dict(key="core", t=None, mat="block", group="wall_inner", label="100mm lightweight blockwork internal partition (min 3.5N/mm2)",
             plain="New inside block wall"),
        dict(key="dabs_b", t=0.010, void=True, lining=True, group="wall_lining", label="dabs"),
        dict(key="board_b", t=0.0155, mat="plasterboard", group="wall_lining", lining=True, z="room", finish=True,
             label="1 layer 12.5mm Gyproc wallboard on dabs, joints taped & sealed, skim", plain="Plastered wall face"),
    ]),
    "stud": dict(name="95 timber stud partition (new)", studs=dict(w=0.045, d=0.095, spacing=0.6, label="95x45mm timber studs at max.600mm centres, 95x45mm treated sw base/soleplates"), layers=[
        dict(key="board_a", t=0.0125, mat="plasterboard", group="wall_lining", lining=True, z="room", finish=True,
             label="12.5mm Gyproc Wallboard TEN lining, joints taped & sealed, skim", plain="Plasterboard wall face"),
        dict(key="core", t=None, void=True, group="wall_inner", label="95x45mm timber studs at max.600mm centres; 50mm Rockwool 'Flexi' insulation within cavity"),
        dict(key="board_b", t=0.0125, mat="plasterboard", group="wall_lining", lining=True, z="room", finish=True,
             label="12.5mm Gyproc Wallboard TEN lining, joints taped & sealed, skim", plain="Plasterboard wall face"),
    ]),
    "stud_existing": dict(name="existing light partition", layers=[
        dict(key="core", t=None, mat="existing_partition", group="wall_inner", label="existing partition (construction not drawn; assumed studwork)",
             conf="assumed", plain="Existing light inside wall"),
    ]),
    "ashlar": dict(name="ashlar studwork", studs=dict(w=0.045, d=0.140, spacing=None,
                                                    label="45x140mm ashlar studwork, 47x100mm treated sw base/soleplate"), layers=[
        dict(key="core", t=None, void=True, group="wall_inner", label="45x140mm ashlar studs with 100mm Celotex GA4000 between"),
        dict(key="pir", t=0.025, mat="pir", group="wall_insulation", lining=True,
             label="25mm Celotex TB4000 on the inner face", plain="Insulation board"),
        dict(key="batten", t=0.025, void=True, lining=True, group="wall_lining", label="25mm battens forming service void"),
        dict(key="board", t=0.0125, mat="plasterboard", group="wall_lining", lining=True, finish=True,
             label="one layer of 12.5mm Gyproc 'Duplex' wallboard, joints taped & sealed prior to skim", plain="Plasterboard wall face"),
    ]),
}


def classify_construction(wtype, existing, t):
    s = wtype.lower()
    if "new 337" in s: return "cav337_new"
    if "party" in s: return "party"
    if "ashlar" in s: return "ashlar"
    if "inner leaf kept" in s: return "leaf_existing"
    if "100 blockwork" in s or "new internal 100" in s: return "block_int"
    if "timber stud" in s: return "stud"
    if "boundary" in s: return "solid_existing"
    if "outshot" in s: return "cav_existing" if t >= 0.25 else "solid_existing"
    if "external" in s: return "cav_existing"
    if "masonry" in s or "lowered" in s or "thinned" in s or "stub" in s: return "masonry_int"
    if t < 0.11: return "stud_existing" if existing else "stud"
    return "masonry_int"


def layer_stack(ckey, t, both_sides_room=False):
    """Layers outside->inside with absolute 'outside offsets': o0..o1 measured from the drawn OUTSIDE face toward the
    inside (o in [0, t] for core; lining layers continue beyond t on the room side; for constructions whose first
    layers are linings (block_int, stud) those sit at negative o, outside the drawn outside face)."""
    C = CONSTRUCTIONS[ckey]
    L = [dict(l) for l in C["layers"]]
    core = [l for l in L if not l.get("lining")]
    fixed = sum(l["t"] for l in core if l["t"] is not None)
    rest = max(0.0, t - fixed)
    nfill = sum(1 for l in core if l["t"] is None)
    for l in core:
        if l["t"] is None: l["t"] = rest / max(1, nfill)
    # place: leading linings (before the first core layer) go outside o<0
    first_core = next(i for i, l in enumerate(L) if not l.get("lining"))
    o = -sum(l["t"] for l in L[:first_core])
    for l in L:
        l["o0"], l["o1"] = o, o + l["t"]
        o += l["t"]
    return L


# ---------------------------------------------------------------- wall object
class Wall:
    """A wall piece: line a->b (centre of the DRAWN thickness t), u-range [ua, ub] along the line, z-range, optional
    top profile [(u, z)], openings (u0, u1, z0, z1), construction key, outside side."""

    def __init__(self, wid, a, b, t, z0, z1, ckey, out=1, storey="ground"):
        self.id, self.a, self.b, self.t = wid, tuple(a), tuple(b), t
        self.L = length(sub(b, a))
        self.d = unit(sub(b, a))
        self.n = (self.d[1], -self.d[0])
        self.ua, self.ub = 0.0, self.L
        self.z0, self.z1 = z0, z1
        self.profile = None
        self.ckey = ckey
        self.out = out
        self.storey = storey
        self.openings = []           # dicts with u0,u1,z0,z1,id
        self.holes = []              # extra (u0,u1,z0,z1, o_lo, o_hi) holes for embedded members (o = outside offset)
        self.layer_tops = {}         # layer key -> top z override (eaves walls)
        self.layer_z = {}            # layer key -> (z0, z1) override
        self.ends = {"a": (None, 0.0), "b": (None, 0.0)}   # (u at c=0, du/dc) after joins; None = ua/ub
        self.only_layers = None      # partial retention: keep only these layer keys
        self.room_z = {}             # +1/-1 side -> (floor, ceiling) for room-side linings
        self.lifts = []
        self.meta = {}

    # c of a layer edge given an outside offset o (from the drawn outside face)
    def c_of(self, o):
        return self.out * (self.t / 2 - o)

    def point(self, u, c):
        return (self.a[0] + self.d[0] * u + self.n[0] * c, self.a[1] + self.d[1] * u + self.n[1] * c)

    def layers(self):
        L = layer_stack(self.ckey, self.t)
        L = self._plaster_out(L)
        if self.only_layers is not None:
            L = [l for l in L if l["key"] in self.only_layers or l["key"] == "plaster_out"]
        return L

    def _plaster_out(self, L):
        """a room on the old outside face too: a plaster finish there (row 179)"""
        if not getattr(self, "plaster_out", False): return L
        o = min(l["o0"] for l in L)
        return [dict(key="plaster_out", t=0.013, mat="plaster", group="wall_lining", lining=True, z="room", finish=True,
                     o0=o - 0.013, o1=o, conf="assumed",
                     label="plaster on the old outside face, now inside a room (finish assumed)", plain="Plastered wall face")] + L

    def full_extent_c(self):
        L = self._plaster_out(layer_stack(self.ckey, self.t))
        cs = [self.c_of(l["o0"]) for l in L] + [self.c_of(l["o1"]) for l in L]
        return min(cs), max(cs)

    def top_at(self, u):
        if not self.profile: return self.z1
        P = self.profile
        if u <= P[0][0]: return min(self.z1, P[0][1])
        for (u0, z0), (u1, z1) in zip(P, P[1:]):
            if u0 <= u <= u1:
                return min(self.z1, z0 + (z1 - z0) * (u - u0) / (u1 - u0 if u1 > u0 else 1))
        return min(self.z1, P[-1][1])

    def end_u(self, which, c):
        u0, k = self.ends[which]
        base = self.ua if which == "a" else self.ub
        return (base if u0 is None else u0) + k * c

    def footprint(self, full=True):
        """plan polygon of the wall piece (drawn core, or full stack incl. linings)"""
        cl, ch = self.full_extent_c() if full else (-self.t / 2, self.t / 2)
        return [self.point(self.end_u("a", cl), cl), self.point(self.end_u("b", cl), cl),
                self.point(self.end_u("b", ch), ch), self.point(self.end_u("a", ch), ch)]


def _cells_for_layer(w, lay, lifts):
    """hexahedra (8-point lists) for one layer, grouped by lift index -> {lift: [pts8, ...]}"""
    c_a, c_b = w.c_of(lay["o0"]), w.c_of(lay["o1"])
    c0, c1 = min(c_a, c_b), max(c_a, c_b)
    zl0, zl1 = w.layer_z.get(lay["key"], (w.z0, w.z1))
    zl0, zl1 = max(zl0, w.z0), min(zl1, w.layer_tops.get(lay["key"], w.z1))
    if zl1 - zl0 < 1e-4: return {}
    usa = [w.end_u("a", c0), w.end_u("a", c1)]
    usb = [w.end_u("b", c0), w.end_u("b", c1)]
    u_lo, u_hi = max(usa), min(usb)
    holes = []
    for o in w.openings:
        holes.append((o["u0"], o["u1"], o["z0"], o["z1"]))
    for (hu0, hu1, hz0, hz1, olo, ohi) in w.holes:
        if min(ohi, lay["o1"]) - max(olo, lay["o0"]) > 1e-4:
            holes.append((hu0, hu1, hz0, hz1))
    us = {u_lo, u_hi}
    for h in holes:
        for u in (h[0], h[1]):
            if u_lo < u < u_hi: us.add(u)
    if w.profile:
        for (pu, pz) in w.profile:
            if u_lo < pu < u_hi: us.add(pu)
    zs = {zl0, zl1}
    for z in lifts:
        if zl0 < z < zl1: zs.add(z)
    for h in holes:
        for z in (h[2], h[3]):
            if zl0 < z < zl1: zs.add(z)
    zs = sorted(zs)
    if w.profile:      # u where the raking top crosses a z line
        P = w.profile
        for (pu0, pz0), (pu1, pz1) in zip(P, P[1:]):
            for z in zs:
                if (pz0 - z) * (pz1 - z) < 0:
                    u = pu0 + (pu1 - pu0) * (z - pz0) / (pz1 - pz0)
                    if u_lo < u < u_hi: us.add(u)
    us = sorted(us)
    lift_lines = [zl0] + [z for z in lifts if zl0 < z < zl1] + [zl1]
    out = {}
    for i in range(len(us) - 1):
        u0, u1 = us[i], us[i + 1]
        if u1 - u0 < 1e-5: continue
        um = (u0 + u1) / 2
        for j in range(len(zs) - 1):
            z0, z1 = zs[j], zs[j + 1]
            if z1 - z0 < 1e-5: continue
            zm = (z0 + z1) / 2
            if any(h[0] + 1e-6 < um < h[1] - 1e-6 and h[2] + 1e-6 < zm < h[3] - 1e-6 for h in holes): continue
            t0, t1 = min(z1, w.top_at(u0)), min(z1, w.top_at(u1))
            if max(t0, t1) <= z0 + 1e-5: continue
            t0, t1 = max(t0, z0 + 1e-4), max(t1, z0 + 1e-4)
            # plan corners; the first and last u cells take the (possibly slanted) wall ends
            ua0 = w.end_u("a", c0) if i == 0 else u0
            ua1 = w.end_u("a", c1) if i == 0 else u0
            ub0 = w.end_u("b", c0) if i == len(us) - 2 else u1
            ub1 = w.end_u("b", c1) if i == len(us) - 2 else u1
            P = [w.point(ua0, c0), w.point(ub0, c0), w.point(ub1, c1), w.point(ua1, c1)]
            tops = [max(z0 + 1e-4, min(z1, w.top_at(u))) for u in (ua0, ub0, ub1, ua1)] if w.profile else [t0, t1, t1, t0]
            pts = [(p[0], p[1], z0) for p in P] + [(p[0], p[1], tz) for p, tz in zip(P, tops)]
            lift = max(k for k in range(len(lift_lines) - 1) if lift_lines[k] <= zm + 1e-9)
            out.setdefault(lift, []).append(pts)
    return out


def wall_parts(w, lifts=None):
    """-> list of (layer_index, layer_dict, lift, nlifts, mesh) for every non-void layer"""
    L = w.layers()
    lifts = sorted(lifts if lifts is not None else w.lifts)
    res = []
    for li, lay in enumerate(L):
        if lay.get("void"): continue
        cells = _cells_for_layer(w, lay, lifts)
        if not cells: continue
        nl = 1 + len([z for z in lifts if w.z0 < z < w.z1])
        for lift, cs in sorted(cells.items()):
            res.append((li, lay, lift, nl, merge_meshes([hexa(p) for p in cs])))
    return res


# ---------------------------------------------------------------- joins
def _face_line(w, c):
    return w.point(0, c), w.d


def resolve_joins(walls, coexist, tol=0.035):
    """Trim/mitre wall ends where walls meet. coexist(a, b) -> True if the two pieces stand at the same time.
    Mitres at L corners (both ends inside each other's footprint), butt trims at T junctions."""
    log = []
    W = list(walls)
    for A in W:
        for which in ("a", "b"):
            uA = A.ua if which == "a" else A.ub
            P = A.point(uA, 0.0)
            other_end_P = A.point(A.ub if which == "a" else A.ua, 0.0)
            for B in W:
                if B is A or not coexist(A, B): continue
                if min(A.z1, B.z1) - max(A.z0, B.z0) < 0.05: continue
                if (B.z1 - B.z0) < 0.8 * (A.z1 - A.z0): continue      # a part-height piece does not cut back a full-height wall
                if abs(dot(A.d, B.d)) > 0.94:
                    # parallel walls overlapping end-on (a wall drawn running into another's thickness): stop A where B ends
                    rel = sub(P, B.a); uB, cB = dot(rel, B.d), dot(rel, B.n)
                    cl, ch = B.full_extent_c()
                    if cl + 0.005 < cB < ch - 0.005 and B.ua + 0.005 < uB < B.ub - 0.005:
                        ends = [dot(sub(B.point(u, 0), A.a), A.d) for u in (B.ua, B.ub)]
                        inside = [e for e in ends if A.ua + 0.01 < e < A.ub - 0.01]
                        if inside:
                            A.ends[which] = (inside[0], 0.0)
                            log.append(("parallel", A.id, B.id, round(inside[0] - uA, 4)))
                    continue
                # P relative to B
                rel = sub(P, B.a)
                uB, cB = dot(rel, B.d), dot(rel, B.n)
                cl, ch = B.full_extent_c()
                if not (cl - tol <= cB <= ch + tol and B.ua - tol <= uB <= B.ub + tol): continue
                if not (min(abs(cB - cl), abs(cB - ch), 0 if cl <= cB <= ch else 9) <= max(B.t, 0.4)): continue
                # is an end of B also inside A's footprint near P? -> L corner
                Bend = None
                for wb in ("a", "b"):
                    Q = B.point(B.ua if wb == "a" else B.ub, 0.0)
                    rq = sub(Q, A.a)
                    uQ, cQ = dot(rq, A.d), dot(rq, A.n)
                    al, ah = A.full_extent_c()
                    if al - 0.005 <= cQ <= ah + 0.005 and abs(uQ - uA) <= max(A.t, B.t) * 0.75 and cl - 0.005 <= cB <= ch + 0.005:
                        Bend = wb
                if Bend is not None:
                    # a third wall continuing A's line on the far side of B -> B runs through: a T, not an L
                    Qb = B.point(B.ua if Bend == "a" else B.ub, 0.0)
                    for C in W:
                        if C is A or C is B or not coexist(B, C) or abs(dot(C.d, A.d)) < 0.94: continue
                        if min(C.z1, A.z1) - max(C.z0, A.z0) < 0.05: continue           # another storey
                        if abs(dot(sub(C.a, A.a), A.n)) > 0.05: continue
                        rq = sub(Qb, C.a); uq, cq = dot(rq, C.d), dot(rq, C.n)
                        c_l, c_h = C.full_extent_c()
                        if c_l - 0.005 <= cq <= c_h + 0.005 and C.ua - 0.2 <= uq <= C.ub + 0.2:
                            Bend = None; break
                if Bend is not None and min(A.ub - A.ua, B.ub - B.ua) < 1.5 * max(A.t, B.t):
                    Bend = None          # a short piece of a wall cut up by the diff butts; a mitre would cut its neighbours
                if Bend is not None and getattr(A, "_life", None) != getattr(B, "_life", None):
                    Bend = None          # one of the two goes (or comes) at another stage: the survivor runs through, no mitre
                if Bend is not None and (B.ckey == A.ckey or {A.ckey, B.ckey} <= {"cav_existing", "solid_existing"}):
                    _mitre(A, which, B, Bend, other_end_P)
                    log.append(("mitre", A.id, B.id))
                else:
                    # butt: trim A to the face of B on A's side (full stack face)
                    if getattr(A, "_life", (1, 99)) > getattr(B, "_life", (1, 99)) and False: pass
                    # the longer-lived wall runs through: a wall that stays is not cut back to one that goes
                    la, lb = getattr(A, "_life", (1, 99)), getattr(B, "_life", (1, 99))
                    if (la[1] - la[0]) > (lb[1] - lb[0]) and la[0] <= lb[0]: continue
                    sideA = dot(sub(other_end_P, B.a), B.n)
                    cface = ch if sideA > cB else cl
                    if abs(cB - cface) > max(B.t, 0.4) + tol: continue
                    # A's end u where A's centre line meets B's face line
                    fp, fd = _face_line(B, cface)
                    X = line_intersect(A.a, A.d, fp, fd)
                    if X is None: continue
                    u_new = dot(sub(X, A.a), A.d)
                    # slope so every layer of A ends ON B's face (non-perpendicular junctions)
                    k = -dot(A.n, B.n) / dot(A.d, B.n) if abs(dot(A.d, B.n)) > 1e-6 else 0.0
                    if abs(u_new - uA) < 0.6:
                        A.ends[which] = (u_new, k)
                        log.append(("butt", A.id, B.id, round(u_new - uA, 4)))
    return log


def _mitre(A, wa, B, wb, A_far):
    """per-layer mitre: A's end on the line through the outer and inner corners of the two walls"""
    al, ah = A.full_extent_c(); bl, bh = B.full_extent_c()
    B_far = B.point(B.ub if wb == "a" else B.ua, 0.0)
    # side of A where B's body lies, and vice versa
    sA = 1 if dot(sub(B_far, A.a), A.n) > dot(sub(A.point(0, 0), A.a), A.n) else -1
    sB = 1 if dot(sub(A_far, B.a), B.n) > 0 else -1
    cA_in, cA_out = (ah, al) if sA > 0 else (al, ah)
    cB_in, cB_out = (bh, bl) if sB > 0 else (bl, bh)
    Po = line_intersect(*_face_line(A, cA_out), *_face_line(B, cB_out))
    Pi = line_intersect(*_face_line(A, cA_in), *_face_line(B, cB_in))
    if Po is None or Pi is None: return
    for W_, which, (c_out, c_in) in ((A, wa, (cA_out, cA_in)), (B, wb, (cB_out, cB_in))):
        uo = dot(sub(Po, W_.a), W_.d); ui = dot(sub(Pi, W_.a), W_.d)
        k = (uo - ui) / (c_out - c_in) if abs(c_out - c_in) > 1e-9 else 0.0
        u0 = uo - k * c_out
        W_.ends[which] = (u0, k)
