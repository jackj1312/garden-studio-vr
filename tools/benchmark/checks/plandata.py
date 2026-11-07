"""Load and validate plan-data JSON (docs/benchmark/PLAN-DATA-SCHEMA.md) and derive the geometry the checks use.

Pure Python. Every check module works on a `Version` object built here."""
import json, math, re
from geom import sub, add, mul, unit, length, left_normal, rect, sector, point_in_poly

SCHEMA_ID = "garden-studio/plan-data/1"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ELEMENT_LISTS = ["walls", "openings", "rooms", "stairs", "slabs", "objects"]
DOOR_KINDS = {"door", "opening", "garage_door", "french_door", "bifold_door", "sliding_door"}
FREE_WALL_KINDS = {"boundary", "garden", "fence", "retaining", "dwarf", "screen", "pier", "parapet", "freestanding"}
BLOCKING_OBJECT_KINDS = {"fitted", "kitchen_unit", "appliance", "wardrobe", "bath", "shower", "wc", "basin",
                         "chimney_breast", "hearth", "boiler", "tank", "column", "furniture"}
BOUNDARY_OBJECT_KINDS = {"balustrade", "guard", "rail", "screen", "glass_screen"}


class Result:
    def __init__(self, check, status, subject, detail, version=None):
        self.check, self.status, self.subject, self.detail, self.version = check, status, subject, detail, version

    def as_dict(self):
        return {"check": self.check, "status": self.status, "version": self.version, "subject": self.subject,
                "detail": self.detail}


def load(path):
    with open(path) as f:
        return json.load(f)


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _pt(p):
    return isinstance(p, (list, tuple)) and len(p) == 2 and _num(p[0]) and _num(p[1])


def _poly(p):
    return isinstance(p, list) and len(p) >= 3 and all(_pt(q) for q in p)


def validate(data):
    """Structural validation. Returns a list of error strings (empty = valid)."""
    err = []
    if not isinstance(data, dict):
        return ["top level must be an object"]
    if data.get("schema") != SCHEMA_ID:
        err.append("schema must be %r (got %r)" % (SCHEMA_ID, data.get("schema")))
    if data.get("units", "m") != "m":
        err.append("units must be 'm'")
    vers = data.get("versions")
    if not isinstance(vers, dict) or not vers:
        err.append("versions must be an object with at least one version (before / after)")
        return err
    for s in data.get("sources", []) or []:
        if not isinstance(s, dict) or not s.get("id"):
            err.append("every sources[] entry needs an id"); continue
        if s.get("date") is not None and not DATE_RE.match(str(s.get("date"))):
            err.append("source %s: date must be YYYY-MM-DD" % s.get("id"))
    for vname, v in vers.items():
        P = "version %s: " % vname
        if not isinstance(v, dict):
            err.append(P + "must be an object"); continue
        storeys = v.get("storeys")
        if not isinstance(storeys, list) or not storeys:
            err.append(P + "storeys[] is required"); storeys = []
        sids = set()
        for s in storeys:
            if not s.get("id") or not _num(s.get("level_m")):
                err.append(P + "every storey needs id and level_m"); continue
            sids.add(s["id"])
        ids = {}
        for key in ELEMENT_LISTS:
            items = v.get(key, [])
            if not isinstance(items, list):
                err.append(P + key + " must be a list"); continue
            for e in items:
                if not isinstance(e, dict) or not e.get("id"):
                    err.append(P + "an item in %s has no id" % key); continue
                if e["id"] in ids:
                    err.append(P + "duplicate id %s (%s and %s)" % (e["id"], ids[e["id"]], key))
                ids[e["id"]] = key
        for w in v.get("walls", []):
            if not (_pt(w.get("start")) and _pt(w.get("end"))):
                err.append(P + "wall %s needs start and end [x, y]" % w.get("id")); continue
            if length(sub(w["start"], w["end"])) < 1e-6:
                err.append(P + "wall %s has zero length" % w.get("id"))
            if not _num(w.get("thickness_m")) or w["thickness_m"] <= 0:
                err.append(P + "wall %s needs thickness_m > 0" % w.get("id"))
            if not _num(w.get("base_m")):
                err.append(P + "wall %s needs base_m" % w.get("id"))
            if not _num(w.get("height_m")) and not w.get("top_profile"):
                err.append(P + "wall %s needs height_m or top_profile" % w.get("id"))
            if w.get("storey") not in sids:
                err.append(P + "wall %s: unknown storey %r" % (w.get("id"), w.get("storey")))
        for o in v.get("openings", []):
            if o.get("wall") is None and o.get("slab") is None:
                err.append(P + "opening %s needs a host wall (or slab for rooflights)" % o.get("id")); continue
            if o.get("wall") is not None and ids.get(o["wall"]) != "walls":
                err.append(P + "opening %s: host wall %r not found" % (o.get("id"), o.get("wall")))
            if o.get("slab") is not None and ids.get(o["slab"]) != "slabs":
                err.append(P + "opening %s: host slab %r not found" % (o.get("id"), o.get("slab")))
            need = ["width_m"] + (["offset_m", "sill_m", "head_m"] if o.get("wall") is not None else [])
            for k in need:
                if not _num(o.get(k)):
                    err.append(P + "opening %s needs %s" % (o.get("id"), k))
            sw = o.get("swing")
            if sw is not None and not isinstance(sw, dict):
                err.append(P + "opening %s: swing must be an object or null" % o.get("id"))
            elif isinstance(sw, dict) and sw.get("type", "hinged") == "hinged":
                if sw.get("hinge") not in ("start", "end", "both") or sw.get("side") not in ("left", "right"):
                    err.append(P + "opening %s: hinged swing needs hinge start|end|both and side left|right" % o.get("id"))
        for r in v.get("rooms", []):
            if not _poly(r.get("polygon")):
                err.append(P + "room %s needs a polygon of 3+ points" % r.get("id"))
            if r.get("storey") not in sids:
                err.append(P + "room %s: unknown storey %r" % (r.get("id"), r.get("storey")))
            for d in r.get("doors", []) or []:
                if ids.get(d) != "openings":
                    err.append(P + "room %s lists door %r which is not an opening" % (r.get("id"), d))
            for o in r.get("open_to", []) or []:
                if ids.get(o) not in ("rooms", "stairs"):
                    err.append(P + "room %s: open_to %r is not a room or stair" % (r.get("id"), o))
        for s in v.get("stairs", []):
            if s.get("from_storey") not in sids or s.get("to_storey") not in sids:
                err.append(P + "stair %s needs from_storey and to_storey" % s.get("id"))
            fl = s.get("flights")
            if not isinstance(fl, list) or not fl:
                err.append(P + "stair %s needs flights[]" % s.get("id")); continue
            for i, f in enumerate(fl):
                for k in ("width_m", "rise_m", "going_m", "base_m"):
                    if not _num(f.get(k)):
                        err.append(P + "stair %s flight %d needs %s" % (s.get("id"), i + 1, k))
                if not (_pt(f.get("start")) and _pt(f.get("direction"))) or not isinstance(f.get("risers"), int) or f.get("risers", 0) < 1:
                    err.append(P + "stair %s flight %d needs start, direction and integer risers" % (s.get("id"), i + 1))
            for l in s.get("landings", []) or []:
                if not _poly(l.get("polygon")) or not _num(l.get("z_m")):
                    err.append(P + "stair %s: every landing needs polygon and z_m" % s.get("id"))
        for sl in v.get("slabs", []):
            if sl.get("kind") not in ("floor", "ceiling", "roof"):
                err.append(P + "slab %s: kind must be floor, ceiling or roof" % sl.get("id"))
            if not _poly(sl.get("polygon")) or not _num(sl.get("z_m")) or not _num(sl.get("thickness_m")):
                err.append(P + "slab %s needs polygon, z_m and thickness_m" % sl.get("id"))
            if sl.get("storey") not in sids:
                err.append(P + "slab %s: unknown storey %r" % (sl.get("id"), sl.get("storey")))
            for h in sl.get("holes", []) or []:
                if not _poly(h):
                    err.append(P + "slab %s: every hole must be a polygon" % sl.get("id"))
        for ob in v.get("objects", []):
            if not (_poly(ob.get("footprint")) or (isinstance(ob.get("line"), list) and len(ob["line"]) >= 2) or _pt(ob.get("position"))):
                err.append(P + "object %s needs footprint, line or position" % ob.get("id"))
    return err


# ---------------------------------------------------------------- derived geometry
class Wall:
    def __init__(self, w):
        self.raw = w; self.id = w["id"]; self.storey = w.get("storey")
        self.a = tuple(w["start"]); self.b = tuple(w["end"])
        self.d = unit(sub(self.b, self.a)); self.n = left_normal(self.d); self.L = length(sub(self.b, self.a))
        self.t = float(w["thickness_m"]); self.base = float(w["base_m"])
        self.kind = w.get("kind", "internal"); self.building = w.get("building", "house")
        prof = w.get("top_profile")
        self.profile = sorted((float(u), float(z)) for u, z in prof) if prof else None
        self.h = float(w["height_m"]) if _num(w.get("height_m")) else None
        self.free_ends = set(w.get("free_ends", []) or [])

    def top(self, u):
        if self.profile:
            pr = self.profile
            if u <= pr[0][0]: return pr[0][1]
            if u >= pr[-1][0]: return pr[-1][1]
            for (u0, z0), (u1, z1) in zip(pr, pr[1:]):
                if u0 <= u <= u1:
                    return z0 if u1 == u0 else z0 + (z1 - z0) * (u - u0) / (u1 - u0)
        return self.base + (self.h or 0.0)

    def min_top(self, u0, u1):
        us = [u0, u1] + ([u for u, _ in self.profile if u0 < u < u1] if self.profile else [])
        return min(self.top(u) for u in us)

    def poly(self, extend=0.0):
        a = add(self.a, mul(self.d, -extend)); b = add(self.b, mul(self.d, extend))
        return rect(add(a, (0, 0)), self.d, self.t, self.L + 2 * extend)

    def point(self, u, c=0.0):
        return add(add(self.a, mul(self.d, u)), mul(self.n, c))


class Opening:
    def __init__(self, o, wall, storey_level):
        self.raw = o; self.id = o["id"]; self.kind = o.get("kind", "window"); self.wall = wall
        self.width = float(o["width_m"]); self.leaves = int(o.get("leaves", 1) or 1)
        self.slab = o.get("slab")
        if wall is not None:
            self.u0 = float(o["offset_m"]); self.u1 = self.u0 + self.width
            self.sill = float(o["sill_m"]); self.head = float(o["head_m"])
            self.level = storey_level
            self.sill_z = storey_level + self.sill; self.head_z = storey_level + self.head
        self.swing = o.get("swing")

    @property
    def is_door(self):
        return self.kind in DOOR_KINDS

    def centre(self, c=0.0):
        return self.wall.point((self.u0 + self.u1) / 2, c)

    def probes(self, extra=0.15):
        """Points just beyond each face of the host wall at the opening centre: (left_point, right_point)."""
        h = self.wall.t / 2 + extra
        return self.centre(h), self.centre(-h)

    def swing_regions(self):
        """Polygons swept by hinged leaves (quarter discs on the swing side). Empty for sliding/none."""
        sw = self.swing
        if not isinstance(sw, dict) or sw.get("type", "hinged") != "hinged" or self.wall is None:
            return []
        w = self.wall; side = 1.0 if sw.get("side") == "left" else -1.0
        face = side * w.t / 2
        hinges = ["start", "end"] if sw.get("hinge") == "both" else [sw.get("hinge")]
        leaf = self.width / len(hinges)
        regs = []
        for hg in hinges:
            u = self.u0 if hg == "start" else self.u1
            c = w.point(u, face)
            along = w.d if hg == "start" else mul(w.d, -1)
            norm = mul(w.n, side)
            a0 = math.atan2(along[1], along[0]); a1 = math.atan2(norm[1], norm[0])
            # take the quarter (90 degrees) between the two directions
            da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
            regs.append(sector(c, leaf, a0, a0 + da))
        return regs

    def passage(self, depth=0.6):
        """Clear approach zones in front of a door on each side (width x depth beyond each wall face)."""
        w = self.wall; out = []
        for side in (1.0, -1.0):
            s = w.point(self.u0, side * w.t / 2)
            d = mul(w.n, side)
            out.append(rect(add(s, mul(w.d, self.width / 2)), d, self.width, depth))
        return out


class Flight:
    def __init__(self, f, stair_id, index):
        self.raw = f; self.stair = stair_id; self.index = index
        self.start = tuple(f["start"]); self.d = unit(tuple(f["direction"]))
        self.width = float(f["width_m"]); self.risers = int(f["risers"]); self.rise = float(f["rise_m"])
        self.going = float(f["going_m"]); self.base = float(f["base_m"])
        self.run = max(0, self.risers - 1) * self.going
        self.top_z = self.base + self.risers * self.rise
        self.waist = float(f.get("waist_m", 0.2))

    def footprint(self):
        return rect(self.start, self.d, self.width, max(self.run, 0.05))

    def top_point(self):
        return add(self.start, mul(self.d, self.run))

    def bottom_zone(self, depth):
        return rect(add(self.start, mul(self.d, -depth)), self.d, self.width, depth)

    def top_zone(self, depth):
        return rect(self.top_point(), self.d, self.width, depth)

    def pitch_z(self, p):
        """Height of the pitch line (nosing line) above plan point p, or None if p is not over the flight."""
        rel = sub(p, self.start); s = rel[0] * self.d[0] + rel[1] * self.d[1]
        c = rel[0] * -self.d[1] + rel[1] * self.d[0]
        if s < -1e-6 or s > self.run + 1e-6 or abs(c) > self.width / 2 + 1e-6:
            return None
        return self.base + self.rise + (s / self.going) * self.rise if self.going > 0 else self.top_z

    def nosings(self):
        """(plan point, tread z) at every nosing, centre and both edges (90% of the width)."""
        n = left_normal(self.d); pts = []
        for k in range(1, self.risers):
            s = (k - 1) * self.going; z = self.base + k * self.rise
            for c in (0.0, 0.45 * self.width, -0.45 * self.width):
                pts.append((add(add(self.start, mul(self.d, s)), mul(n, c)), z))
        return pts


class Version:
    def __init__(self, name, v, data=None):
        self.name = name; self.raw = v; self.data = data or {}
        self.storeys = sorted(v.get("storeys", []), key=lambda s: s["level_m"])
        self.level = {s["id"]: float(s["level_m"]) for s in self.storeys}
        self.storey = {s["id"]: s for s in self.storeys}
        self.walls = {w["id"]: Wall(w) for w in v.get("walls", [])}
        self.openings = {}
        for o in v.get("openings", []):
            wall = self.walls.get(o.get("wall"))
            lvl = self.level.get(wall.storey, 0.0) if wall else 0.0
            self.openings[o["id"]] = Opening(o, wall, lvl)
        self.rooms = {r["id"]: r for r in v.get("rooms", [])}
        self.stairs = {s["id"]: s for s in v.get("stairs", [])}
        self.flights = {sid: [Flight(f, sid, i) for i, f in enumerate(s.get("flights", []))] for sid, s in self.stairs.items()}
        self.slabs = v.get("slabs", []) or []
        self.objects = v.get("objects", []) or []

    def above(self, storey_id):
        lv = self.level.get(storey_id)
        ups = [s for s in self.storeys if s["level_m"] > lv + 1e-6]
        return ups[0]["id"] if ups else None

    def room_floor(self, r):
        return self.level.get(r.get("storey"), 0.0) + float(r.get("floor_offset_m", 0.0) or 0.0)

    def room_ceiling(self, r):
        """(min, max) absolute ceiling height of a room, or None if not given."""
        c = r.get("ceiling_m"); f = self.room_floor(r)
        if isinstance(c, str):
            return None  # described only (e.g. "vaulted"): give min_m/max_m to have walls checked up to the eaves
        if _num(c): return (f + c, f + c)
        if isinstance(c, dict) and _num(c.get("min_m")):
            return (f + c["min_m"], f + float(c.get("max_m", c["min_m"])))
        st = self.storey.get(r.get("storey"), {})
        if _num(st.get("ceiling_m")): return (f + st["ceiling_m"], f + st["ceiling_m"])
        return None

    def stair_plan(self, sid, grow=0.0):
        """Plan polygons of a stair: flights and landings."""
        polys = [f.footprint() if not grow else rect(add(f.start, mul(f.d, -grow)), f.d, f.width + 2 * grow, f.run + 2 * grow)
                 for f in self.flights.get(sid, [])]
        polys += [l["polygon"] for l in self.stairs[sid].get("landings", []) or []]
        return polys

    def rooms_at(self, p, storey_id):
        return [rid for rid, r in self.rooms.items() if r.get("storey") == storey_id and point_in_poly(p, r["polygon"])]

    def slab_covers(self, p, slab):
        if not point_in_poly(p, slab["polygon"]):
            return False
        return not any(point_in_poly(p, h) for h in slab.get("holes", []) or [])

    def slab_underside(self, p, slab):
        pl = slab.get("underside_plane")
        if isinstance(pl, list) and len(pl) == 3:
            return pl[0] * p[0] + pl[1] * p[1] + pl[2]
        return float(slab["z_m"]) - float(slab["thickness_m"])


def versions(data, only=None):
    out = []
    for name, v in data.get("versions", {}).items():
        if only and name != only:
            continue
        out.append(Version(name, v, data))
    return out


def all_elements(v):
    for key in ELEMENT_LISTS:
        for e in v.raw.get(key, []) or []:
            yield key, e
