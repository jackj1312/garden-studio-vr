"""CLOSURE checks: every room is a closed space bounded by walls that run floor to ceiling, with its door count; every
opening has wall above and below it as drawn; walls meet (no gaps); floors and ceilings have no holes except stairwells.

Check ids (all reported per version):
  closure.room-shape      polygon valid (3+ points, area, no self-intersection)
  closure.room-boundary   every metre of a room's edge is on a wall face (or a declared open edge / balustrade);
                          the wall reaches the floor and the ceiling there
  closure.doors           doors found on the room's boundary == the room's `doors` list (and `drawn_door_count`)
  closure.opening-fit     opening lies within its host wall; wall below a sill; wall (lintel) above the head
  closure.wall-joints     every wall end meets another wall (unless a free-standing kind or listed in free_ends)
  closure.floor           every point of every room stands on a floor slab (stairwell holes allowed)
  closure.ceiling         every point of every room is under a ceiling, roof or the floor above (stairwells allowed)
  closure.inventory       every room label in inventory[] maps to a room (WARN for rooms not in the inventory)
"""
from geom import (sub, add, mul, length, unit, area, self_intersections, seg_closest, edge_samples, grid_samples,
                  point_in_poly, dist_to_boundary, fmt)
from plandata import Result, BOUNDARY_OBJECT_KINDS, FREE_WALL_KINDS

C = "closure"


def _boundary_lines(v):
    lines = []
    for ob in v.objects:
        if ob.get("kind") in BOUNDARY_OBJECT_KINDS and isinstance(ob.get("line"), list):
            t = float(ob.get("thickness_m", 0.05))
            pts = [tuple(p) for p in ob["line"]]
            for a, b in zip(pts, pts[1:]):
                lines.append((ob.get("storey"), a, b, t))
    return lines


def check_rooms(v, tol):
    res = []
    lines = _boundary_lines(v)
    for rid, r in v.rooms.items():
        poly = [tuple(p) for p in r["polygon"]]
        if abs(area(poly)) < 0.05:
            res.append(Result(C + ".room-shape", "FAIL", rid, "room polygon has almost no area (%.3f m2)" % abs(area(poly)), v.name)); continue
        si = self_intersections(poly)
        if si:
            res.append(Result(C + ".room-shape", "FAIL", rid, "room polygon crosses itself at edges %s" % si[:3], v.name)); continue
        res.append(Result(C + ".room-shape", "PASS", rid, "closed polygon, %.2f m2" % abs(area(poly)), v.name))
        if r.get("kind") == "outside":
            continue
        floor = v.room_floor(r); ceil = v.room_ceiling(r)
        open_polys = []
        for oid in r.get("open_to", []) or []:
            if oid in v.rooms: open_polys.append(v.rooms[oid]["polygon"])
            elif oid in v.stairs: open_polys += v.stair_plan(oid, grow=0.05)
        walls = [w for w in v.walls.values() if w.storey == r.get("storey") or (w.base <= floor + tol and w.top(w.L / 2) >= floor + 1.0)]
        problems = []  # (edge, s, reason)
        flags, pos, labels = [], [], []
        for ei, s, p in edge_samples(poly, step=0.05, end_skip=0.02):
            reason = "no wall"
            ok = False
            for w in walls:
                rel = sub(p, w.a)
                u = rel[0] * w.d[0] + rel[1] * w.d[1]; c = rel[0] * w.n[0] + rel[1] * w.n[1]
                # on the wall's face: within its length (no end extension, so collinear gaps are measured fully)
                if -tol <= u <= w.L + tol and abs(c) <= w.t / 2 + tol:
                    if w.base > floor + tol:
                        reason = "wall %s starts %.2f m above the floor (gap below)" % (w.id, w.base - floor); continue
                    if ceil is not None and w.top(min(max(u, 0), w.L)) < ceil[0] - tol:
                        reason = "wall %s stops %.2f m below the ceiling (gap above)" % (w.id, ceil[0] - w.top(min(max(u, 0), w.L))); continue
                    ok = True; break
            if not ok:
                for st, a, b, t in lines:
                    if (st in (None, r.get("storey"))) and seg_closest(p, a, b)[0] <= t / 2 + tol:
                        ok = True; break
            if not ok:
                for op in open_polys:
                    if point_in_poly(p, op) or dist_to_boundary(p, op) <= tol + 0.02:
                        ok = True; break
            flags.append(ok); pos.append((ei, s, p)); labels.append(reason)
        bad = []
        cur = None
        for ok, (ei, s, p), why in zip(flags, pos, labels):
            if not ok:
                if cur and cur[0] == ei and s - cur[2] <= 0.051:
                    cur[2] = s; cur[4] = p
                else:
                    if cur: bad.append(cur)
                    cur = [ei, s, s, p, p, why]
            else:
                if cur: bad.append(cur); cur = None
        if cur: bad.append(cur)
        bad = [b for b in bad if b[2] - b[1] >= 0.05 - 1e-9]
        if bad:
            total = sum(b[2] - b[1] for b in bad)
            det = "; ".join("edge %d %s-%s (%.2f m): %s" % (b[0] + 1, fmt(b[3]), fmt(b[4]), b[2] - b[1], b[5]) for b in bad[:6])
            res.append(Result(C + ".room-boundary", "FAIL", rid, "%.2f m of the room's edge is not closed by a wall: %s" % (total, det), v.name))
        else:
            res.append(Result(C + ".room-boundary", "PASS", rid, "every edge closed by walls floor to ceiling", v.name))
    return res


def _end_dist(p, w):
    """Distance from p to the wall's rectangle extended by half its thickness at each end (corner zones)."""
    rel = sub(p, w.a); s = rel[0] * w.d[0] + rel[1] * w.d[1]; c = rel[0] * w.n[0] + rel[1] * w.n[1]
    ds = max(-w.t / 2 - s, 0.0, s - w.L - w.t / 2); dc = max(abs(c) - w.t / 2, 0.0)
    return (ds * ds + dc * dc) ** 0.5


def door_rooms(v, o):
    """Rooms on each side of a door opening (lists), using probes just beyond each wall face."""
    st = o.wall.storey
    pl, pr = o.probes()
    return v.rooms_at(pl, st), v.rooms_at(pr, st)


def check_doors(v):
    res = []
    found = {rid: set() for rid in v.rooms}
    for oid, o in v.openings.items():
        if o.wall is None or not o.is_door:
            continue
        L, R = door_rooms(v, o)
        for rid in set(L + R):
            found[rid].add(oid)
    for rid, r in v.rooms.items():
        if r.get("kind") == "outside":
            continue
        declared = set(r.get("doors", []) or [])
        missing = declared - found[rid]; extra = found[rid] - declared
        msgs = []
        if missing: msgs.append("listed but not on this room's boundary: %s" % ", ".join(sorted(missing)))
        if extra: msgs.append("on the boundary but not listed: %s" % ", ".join(sorted(extra)))
        dc = r.get("drawn_door_count")
        if isinstance(dc, int) and dc != len(found[rid]):
            msgs.append("drawing shows %d door(s), model has %d" % (dc, len(found[rid])))
        res.append(Result(C + ".doors", "FAIL" if msgs else "PASS", rid,
                          "; ".join(msgs) if msgs else "%d door(s) match" % len(found[rid]), v.name))
    return res


def check_openings(v, tol):
    res = []
    for oid, o in v.openings.items():
        if o.wall is None:
            continue
        w = o.wall; msgs = []
        if o.u0 < -tol or o.u1 > w.L + tol:
            msgs.append("lies outside its wall %s (offset %.2f..%.2f, wall length %.2f)" % (w.id, o.u0, o.u1, w.L))
        if o.head <= o.sill:
            msgs.append("head %.2f is not above sill %.2f" % (o.head, o.sill))
        if o.sill > tol and w.base > o.level + tol:
            msgs.append("no wall below the sill: host wall %s starts %.2f m above the floor" % (w.id, w.base - o.level))
        if o.sill > tol and w.base > o.sill_z - tol:
            msgs.append("no wall below the sill: wall base %.2f is at or above the sill %.2f" % (w.base, o.sill_z))
        top = w.min_top(max(o.u0, 0.0), min(o.u1, w.L))
        if not o.raw.get("full_height") and top < o.head_z + 0.02:
            msgs.append("no wall/lintel above the head: wall top %.2f vs head %.2f" % (top, o.head_z))
        res.append(Result(C + ".opening-fit", "FAIL" if msgs else "PASS", oid, "; ".join(msgs) if msgs else "within wall %s, wall below and above" % w.id, v.name))
    return res


def check_wall_joints(v, tol):
    res = []
    for wid, w in v.walls.items():
        if w.kind in FREE_WALL_KINDS:
            continue
        msgs = []
        for end, p in (("start", w.a), ("end", w.b)):
            if end in w.free_ends:
                continue
            best = None
            for w2 in v.walls.values():
                if w2 is w:
                    continue
                if min(w.top(0), w.top(w.L), w2.top(0), w2.top(w2.L)) - max(w.base, w2.base) < 0.1:
                    continue  # no real vertical overlap (e.g. a wall on the storey above)
                d = _rect_dist(p, w2)
                best = d if best is None else min(best, d)
            if best is None or best > w.t / 2 + tol:
                msgs.append("%s end %s is %s from any other wall (gap)" % (end, fmt(p), "%.2f m" % best if best is not None else "far"))
        res.append(Result(C + ".wall-joints", "FAIL" if msgs else "PASS", wid, "; ".join(msgs) if msgs else "both ends meet walls", v.name))
    return res


def _rect_dist(p, w):
    """Distance from p to the wall's body (centreline +- t/2, no end extension)."""
    rel = sub(p, w.a); s = rel[0] * w.d[0] + rel[1] * w.d[1]; c = rel[0] * w.n[0] + rel[1] * w.n[1]
    ds = max(-s, 0.0, s - w.L); dc = max(abs(c) - w.t / 2, 0.0)
    return (ds * ds + dc * dc) ** 0.5


def _stairwell_ok(v, p, storey_arriving):
    """True if p is over a stair that arrives at `storey_arriving` (a stairwell hole is expected there)."""
    for sid, s in v.stairs.items():
        if s.get("to_storey") != storey_arriving and s.get("from_storey") != storey_arriving:
            continue
        for poly in v.stair_plan(sid, grow=0.1):
            if point_in_poly(p, poly):
                return True
    return False


def check_floors_ceilings(v, gate):
    res = []
    floors = [s for s in v.slabs if s.get("kind") == "floor"]
    if not v.slabs:
        st = "WARN" if gate == "1A" else "FAIL"
        res.append(Result(C + ".floor", st, "-", "no slabs[]: floors and ceilings cannot be checked%s" % (" (allowed at GATE 1A)" if gate == "1A" else ""), v.name))
        return res
    for rid, r in v.rooms.items():
        if r.get("kind") in ("outside", "void"):
            continue
        st = r.get("storey"); pts = grid_samples([tuple(p) for p in r["polygon"]], 0.1, 0.03)
        floor_z = v.room_floor(r)
        # floor
        gaps = []
        for p in pts:
            if any(s.get("storey") == st and v.slab_covers(p, s) and abs(float(s["z_m"]) - floor_z) <= 0.06 for s in floors):
                continue
            if _stairwell_ok(v, p, st):
                continue
            gaps.append(p)
        if gaps:
            res.append(Result(C + ".floor", "FAIL", rid, "%d of %d sample points have no floor (e.g. %s)" % (len(gaps), len(pts), ", ".join(fmt(g) for g in gaps[:4])), v.name))
        else:
            res.append(Result(C + ".floor", "PASS", rid, "floor continuous (%d points)" % len(pts), v.name))
        # ceiling
        if r.get("ceiling") == "open":
            res.append(Result(C + ".ceiling", "WARN", rid, "declared open to above (double height): not checked", v.name)); continue
        up = v.above(st)
        cands = [s for s in v.slabs if (s.get("kind") in ("ceiling", "roof") and s.get("storey") == st) or
                 (s.get("kind") == "floor" and up is not None and s.get("storey") == up)]
        gaps = []
        for p in pts:
            if any(v.slab_covers(p, s) and v.slab_underside(p, s) > floor_z + 1.0 for s in cands):
                continue
            if up is not None and _stairwell_ok(v, p, up):
                continue
            gaps.append(p)
        if gaps:
            res.append(Result(C + ".ceiling", "FAIL", rid, "%d of %d sample points have no ceiling above (e.g. %s)" % (len(gaps), len(pts), ", ".join(fmt(g) for g in gaps[:4])), v.name))
        else:
            res.append(Result(C + ".ceiling", "PASS", rid, "ceiling continuous (%d points)" % len(pts), v.name))
    return res


def check_inventory(v):
    inv = v.raw.get("inventory") or []
    if not inv:
        return [Result(C + ".inventory", "WARN", "-", "no inventory[]: the drawing's room labels are not cross-checked", v.name)]
    res = []
    bad = [e.get("label", "?") + " -> " + str(e.get("room")) for e in inv if e.get("room") not in v.rooms]
    listed = {e.get("room") for e in inv}
    unlisted = [rid for rid, r in v.rooms.items() if rid not in listed and r.get("kind") not in ("outside", "void")]
    res.append(Result(C + ".inventory", "FAIL" if bad else "PASS", "-", ("labels with no room: " + ", ".join(bad)) if bad else "%d labels all map to rooms" % len(inv), v.name))
    if unlisted:
        res.append(Result(C + ".inventory", "WARN", "-", "rooms not in the drawing inventory (as-built or owner additions? say so): " + ", ".join(unlisted), v.name))
    return res


def run(v, tol=0.03, gate="1B"):
    out = check_inventory(v)
    out += check_rooms(v, tol)
    out += check_doors(v)
    out += check_openings(v, tol)
    out += check_wall_joints(v, tol)
    out += check_floors_ceilings(v, gate)
    return out
