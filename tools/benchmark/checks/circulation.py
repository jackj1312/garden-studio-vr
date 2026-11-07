"""CIRCULATION checks: stairs rise the right way and arrive on a floor, keep headroom, land clear; no stair, door swing
or fitted item blocks another stair, door or route; every room is reachable from outside.

Check ids (per version):
  circulation.stair-rise      total rise = level difference; flights continuous; riser/going sanity (WARN)
  circulation.stair-ends      clear zone before the bottom riser stands on the lower floor; clear zone after the top
                              riser stands on the upper floor; intermediate flights meet their landings
  circulation.headroom        clear height above the pitch line >= headroom_min_m (default 2.0) along every flight
  circulation.stair-clash     a stair (or its end zones) never overlaps another stair at a clashing height
  circulation.door-swing      door leaves do not sweep over a stair, a stair end zone, another door's swing or a
                              fitted item
  circulation.door-approach   the zone in front of each door (both faces) is not inside a stair flight, a floor hole
                              or a fitted item
  circulation.reachable       every room can be reached from outside through doors, open edges and stairs
"""
from geom import (sub, add, mul, unit, rect, point_in_poly, grid_samples, overlap_points, centroid, fmt)
from plandata import Result, BLOCKING_OBJECT_KINDS
from closure import door_rooms

C = "circulation"


def _on_floor(v, p, storey, z, tol=0.06):
    """p stands on storey `storey` at height z: inside a room (or a landing at z) and not over a floor hole."""
    in_room = bool(v.rooms_at(p, storey))
    floors = [s for s in v.slabs if s.get("kind") == "floor" and s.get("storey") == storey and abs(float(s["z_m"]) - z) <= tol]
    if v.slabs:
        on_slab = any(v.slab_covers(p, s) for s in floors)
    else:
        on_slab = in_room  # GATE 1A without slabs: rooms only
    return in_room and on_slab


def _on_landing(v, p, sid, z, tol=0.03):
    return any(point_in_poly(p, l["polygon"]) and abs(float(l["z_m"]) - z) <= tol for l in v.stairs[sid].get("landings", []) or [])


def _zone_ok(v, zone, test):
    pts = grid_samples(zone, 0.1, 0.03)
    bad = [p for p in pts if not test(p)]
    return bad, len(pts)


def _blocking_objects(v):
    out = []
    for ob in v.objects:
        blocks = ob.get("blocks")
        if blocks is None:
            blocks = ob.get("kind") in BLOCKING_OBJECT_KINDS
        if blocks and isinstance(ob.get("footprint"), list):
            out.append(ob)
    return out


def check_stairs(v, landing_depth, tol):
    res = []
    for sid, s in v.stairs.items():
        fl = v.flights[sid]
        lo = v.level.get(s["from_storey"]); hi = v.level.get(s["to_storey"])
        msgs = []; warns = []
        total = sum(f.risers * f.rise for f in fl)
        if hi <= lo:
            msgs.append("to_storey %s (%.3f) is not above from_storey %s (%.3f)" % (s["to_storey"], hi, s["from_storey"], lo))
        if abs(total - (hi - lo)) > 0.015:
            msgs.append("risers add up to %.3f m but the storeys are %.3f m apart" % (total, hi - lo))
        if abs(fl[0].base - lo) > 0.015:
            msgs.append("first flight starts at %.3f, not at the %s floor %.3f" % (fl[0].base, s["from_storey"], lo))
        for a, b in zip(fl, fl[1:]):
            if abs(b.base - a.top_z) > 0.015:
                msgs.append("flight %d starts at %.3f but flight %d ends at %.3f" % (b.index + 1, b.base, a.index + 1, a.top_z))
        for f in fl:
            if not (0.1 <= f.rise <= 0.22): warns.append("flight %d rise %.0f mm outside 100-220" % (f.index + 1, f.rise * 1000))
            if f.going < 0.22 and f.risers > 1: warns.append("flight %d going %.0f mm under 220" % (f.index + 1, f.going * 1000))
        st = "FAIL" if msgs else ("WARN" if warns else "PASS")
        res.append(Result(C + ".stair-rise", st, sid, "; ".join(msgs + warns) if (msgs or warns) else
                          "%d risers, %.3f m, flights continuous" % (sum(f.risers for f in fl), total), v.name))
        # ends
        msgs = []
        first, last = fl[0], fl[-1]
        warns = []
        bad, n = _zone_ok(v, first.bottom_zone(landing_depth), lambda p: _on_floor(v, p, s["from_storey"], lo) or _on_landing(v, p, sid, lo))
        if bad and len(bad) * 3 < n:
            warns.append("bottom: %d/%d points of the zone before the first riser are off the floor (tight landing?)" % (len(bad), n))
        elif bad:
            msgs.append("bottom: %d/%d points of the %.1f m zone before the first riser are not on the %s floor (e.g. %s): the stair may run the wrong way or start over a void"
                        % (len(bad), n, landing_depth, s["from_storey"], fmt(bad[0])))
        bad, n = _zone_ok(v, last.top_zone(landing_depth), lambda p: _on_floor(v, p, s["to_storey"], hi) or _on_landing(v, p, sid, hi))
        if bad and len(bad) * 3 < n:
            warns.append("top: %d/%d points of the zone after the top riser are off the floor (tight landing?)" % (len(bad), n))
        elif bad:
            msgs.append("top: %d/%d points of the %.1f m zone after the top riser are not on the %s floor (e.g. %s): the stair may run the wrong way"
                        % (len(bad), n, landing_depth, s["to_storey"], fmt(bad[0])))
        for a, b in zip(fl, fl[1:]):
            pa = add(a.top_point(), mul(a.d, 0.1)); pb = add(b.start, mul(b.d, -0.1))
            if not _on_landing(v, pa, sid, a.top_z):
                msgs.append("flight %d does not arrive on a landing at %.3f (%s)" % (a.index + 1, a.top_z, fmt(pa)))
            if not _on_landing(v, pb, sid, b.base):
                msgs.append("flight %d does not start from a landing at %.3f (%s)" % (b.index + 1, b.base, fmt(pb)))
        res.append(Result(C + ".stair-ends", "FAIL" if msgs else ("WARN" if warns else "PASS"), sid,
                          "; ".join(msgs + warns) if (msgs or warns) else "bottom and top zones on the floors", v.name))
        # headroom
        need = float(s.get("headroom_min_m", 2.0))
        worst = None
        for f in fl:
            for p, z in f.nosings():
                c = _clearance(v, p, z, sid)
                if c is not None and (worst is None or c < worst[0]):
                    worst = (c, p, z, f.index + 1)
        if worst and worst[0] < need - 0.005:
            res.append(Result(C + ".headroom", "FAIL", sid, "headroom %.2f m (< %.2f) above flight %d at %s, tread %.2f" % (worst[0], need, worst[3], fmt(worst[1]), worst[2]), v.name))
        else:
            note = "min clear %.2f m" % worst[0] if worst else "nothing above the flights"
            st = "WARN" if need < 2.0 else "PASS"
            res.append(Result(C + ".headroom", st, sid, note + (" (headroom_min_m %.2f below 2.0: state why)" % need if need < 2.0 else ""), v.name))
    return res


def _clearance(v, p, z, own_sid):
    """Smallest clear height above (p, z): slab undersides, other stairs' soffits and landings, objects above."""
    best = None
    for s in v.slabs:
        if v.slab_covers(p, s):
            u = v.slab_underside(p, s)
            if u > z + 0.05:
                best = u - z if best is None else min(best, u - z)
    for sid, flights in v.flights.items():
        for f in flights:  # includes the stair's own upper flights (a dog-leg over its lower flight)
            pz = f.pitch_z(p)
            if pz is None:
                continue
            soffit = pz - f.rise - f.waist
            if soffit > z + 0.05:
                best = soffit - z if best is None else min(best, soffit - z)
        for l in v.stairs[sid].get("landings", []) or []:
            if point_in_poly(p, l["polygon"]):
                u = float(l["z_m"]) - float(l.get("thickness_m", 0.2))
                if u > z + 0.05:
                    best = u - z if best is None else min(best, u - z)
    for ob in v.objects:
        if isinstance(ob.get("footprint"), list) and "base_m" in ob and point_in_poly(p, ob["footprint"]):
            u = float(ob["base_m"])
            if u > z + 0.05:
                best = u - z if best is None else min(best, u - z)
    return best


def _stair_zones(v, sid, depth):
    fl = v.flights[sid]
    return fl[0].bottom_zone(depth), fl[-1].top_zone(depth)


def _z_at(v, sid, p):
    """Walking surface height of stair sid over plan point p (flight pitch or landing), or None."""
    for f in v.flights[sid]:
        z = f.pitch_z(p)
        if z is not None:
            return z
    for l in v.stairs[sid].get("landings", []) or []:
        if point_in_poly(p, l["polygon"]):
            return float(l["z_m"])
    return None


def check_clashes(v, depth):
    res = []
    sids = list(v.stairs)
    for i, a in enumerate(sids):
        msgs = []
        for b in sids:
            if a == b:
                continue
            need = max(float(v.stairs[a].get("headroom_min_m", 2.0)), float(v.stairs[b].get("headroom_min_m", 2.0)))
            # stair a's flights/landings over or under stair b's
            for pa in v.stair_plan(a):
                for pb in v.stair_plan(b):
                    for p in overlap_points(pa, pb, 0.1, 0.02):
                        za, zb = _z_at(v, a, p), _z_at(v, b, p)
                        if za is not None and zb is not None and abs(za - zb) < need:
                            msgs.append("overlaps stair %s at %s with only %.2f m between them" % (b, fmt(p), abs(za - zb))); break
                    else:
                        continue
                    break
            # a's end zones must not sit on b
            fa = v.flights[a]
            for label, zone, zz in (("bottom zone", fa[0].bottom_zone(depth), fa[0].base), ("top zone", fa[-1].top_zone(depth), fa[-1].top_z)):
                for pb in v.stair_plan(b):
                    hit = [p for p in overlap_points(zone, pb, 0.1, 0.02) if _z_at(v, b, p) is not None and abs(_z_at(v, b, p) - zz) < need]
                    if hit:
                        msgs.append("its %s is over/under stair %s at %s" % (label, b, fmt(hit[0]))); break
        msgs = sorted(set(msgs))
        res.append(Result(C + ".stair-clash", "FAIL" if msgs else "PASS", a, "; ".join(msgs[:6]) if msgs else "no clash with other stairs", v.name))
    return res


def check_doors(v, depth):
    res = []
    blockers = _blocking_objects(v)
    doors = [o for o in v.openings.values() if o.wall is not None and o.is_door]
    for o in doors:
        msgs, warns = [], []
        st = o.wall.storey; lvl = v.level.get(st, 0.0)
        regs = o.swing_regions()
        for reg in regs:
            for sid in v.stairs:
                for f in v.flights[sid]:
                    if abs(f.base - lvl) < 2.0 or abs(f.top_z - lvl) < 2.0 or (f.base < lvl < f.top_z):
                        hit = [p for p in overlap_points(reg, f.footprint(), 0.05, 0.01) if abs((f.pitch_z(p) or lvl) - lvl) < 2.0]
                        if hit:
                            msgs.append("swing sweeps over stair %s flight %d at %s" % (sid, f.index + 1, fmt(hit[0])))
                bz, tz = _stair_zones(v, sid, depth)
                fl = v.flights[sid]
                if abs(fl[-1].top_z - lvl) < 0.05 and overlap_points(reg, tz, 0.05, 0.01):
                    msgs.append("swing crosses the top landing zone of stair %s" % sid)
                if abs(fl[0].base - lvl) < 0.05 and overlap_points(reg, bz, 0.05, 0.01):
                    warns.append("swing crosses the bottom zone of stair %s (keep 400 mm clear)" % sid)
            for o2 in doors:
                if o2 is o or o2.wall.storey != st:
                    continue
                for r2 in o2.swing_regions():
                    if overlap_points(reg, r2, 0.05, 0.02):
                        msgs.append("swing clashes with door %s" % o2.id)
            for ob in blockers:
                if ob.get("storey") not in (None, st):
                    continue
                if overlap_points(reg, ob["footprint"], 0.05, 0.01):
                    msgs.append("swing hits %s" % ob["id"])
        msgs = sorted(set(msgs)); warns = sorted(set(warns))
        status = "FAIL" if msgs else ("WARN" if warns else "PASS")
        res.append(Result(C + ".door-swing", status, o.id, "; ".join(msgs + warns) if (msgs or warns) else ("swing clear" if regs else "no hinged leaf"), v.name))
        # approach zones
        msgs = []
        L, R = door_rooms(v, o)
        for zone, rooms in zip(o.passage(depth), (L, R)):
            if not rooms:
                continue  # outside face: garden/street not checked here
            for sid in v.stairs:
                for f in v.flights[sid]:
                    hit = [p for p in overlap_points(zone, f.footprint(), 0.05, 0.02) if f.pitch_z(p) is not None and lvl - 0.05 < f.pitch_z(p) < lvl + 2.0]
                    if hit:
                        msgs.append("approach blocked by stair %s at %s" % (sid, fmt(hit[0])))
            for ob in blockers:
                if ob.get("storey") in (None, st) and overlap_points(zone, ob["footprint"], 0.05, 0.02):
                    msgs.append("approach blocked by %s" % ob["id"])
            if v.slabs:
                holes = [p for p in grid_samples(zone, 0.1, 0.03) if rooms and not _on_floor(v, p, st, lvl)]
                if holes:
                    msgs.append("approach over a void/no floor at %s" % fmt(holes[0]))
        msgs = sorted(set(msgs))
        res.append(Result(C + ".door-approach", "FAIL" if msgs else "PASS", o.id, "; ".join(msgs) if msgs else "approach clear both sides", v.name))
    return res


def check_reachable(v, depth):
    graph = {rid: set() for rid in v.rooms}; graph["OUTSIDE"] = set()

    def link(a, b):
        graph.setdefault(a, set()).add(b); graph.setdefault(b, set()).add(a)
    for o in v.openings.values():
        if o.wall is None or not o.is_door:
            continue
        L, R = door_rooms(v, o)
        Ls = L or ["OUTSIDE"]; Rs = R or ["OUTSIDE"]
        for a in Ls:
            for b in Rs:
                if a != b: link(a, b)
    for rid, r in v.rooms.items():
        if r.get("kind") == "outside":
            link(rid, "OUTSIDE")
        for o in r.get("open_to", []) or []:
            if o in v.rooms: link(rid, o)
    for sid, s in v.stairs.items():
        fl = v.flights[sid]
        bz = centroid(fl[0].bottom_zone(depth)); tz = centroid(fl[-1].top_zone(depth))
        bottoms = v.rooms_at(bz, s["from_storey"]) + [rid for rid, r in v.rooms.items() if sid in (r.get("open_to") or []) and r.get("storey") == s["from_storey"]]
        tops = v.rooms_at(tz, s["to_storey"]) + [rid for rid, r in v.rooms.items() if sid in (r.get("open_to") or []) and r.get("storey") == s["to_storey"]]
        for a in bottoms:
            for b in tops:
                link(a, b)
    seen = {"OUTSIDE"}; todo = ["OUTSIDE"]
    while todo:
        n = todo.pop()
        for m in graph.get(n, ()):
            if m not in seen:
                seen.add(m); todo.append(m)
    res = []
    if not graph["OUTSIDE"]:
        res.append(Result(C + ".reachable", "FAIL", "-", "no external door: the house cannot be entered", v.name))
    for rid, r in v.rooms.items():
        if r.get("kind") in ("void", "duct"):
            continue
        ok = rid in seen
        res.append(Result(C + ".reachable", "PASS" if ok else "FAIL", rid, "reachable from outside" if ok else "cannot be reached from outside (no door, open edge or stair leads here)", v.name))
    return res


def run(v, landing_depth=0.6, tol=0.03, gate="1B"):
    out = []
    out += check_stairs(v, landing_depth, tol)
    out += check_clashes(v, landing_depth)
    out += check_doors(v, landing_depth)
    out += check_reachable(v, landing_depth)
    return out
