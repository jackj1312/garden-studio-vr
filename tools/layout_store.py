"""Revision-checked garden and furnishing sections on one versioned house layout."""
import errno
import fcntl
import json
import math
import os
import re
import shutil
import stat
import subprocess
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
OBJECT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}")
KINDS = set("patio path lawn gravel decking wall retaining-wall raised-bed sunken-area "
            "fire-pit steps fence edging planting-bed plant tree outbuilding-base".split())
MAX_BODY = 2 * 1024 * 1024
MAX_LAYOUT = 12 * 1024 * 1024
CATALOGUE = Path(__file__).resolve().parents[1] / "src/garden/catalogue.mjs"
FURNISH_MODULE = Path(__file__).resolve().parents[1] / "src/furnish/placement.mjs"
FURNISH_VALIDATOR = '''
import {readFileSync} from 'node:fs';
const {buildRoomContext,validateFurnishDelta}=await import(process.argv[1]);
const {inputs,previous,next}=JSON.parse(readFileSync(0,'utf8'));
const ctx=buildRoomContext(inputs);
try { validateFurnishDelta(ctx,previous,next); }
catch(e) { process.stderr.write(e.message); process.exit(2); }
'''
VALIDATOR_LOCK = threading.Lock()
VALIDATOR = """
import {readFileSync} from 'node:fs';
const {validateFeatureGeometry} = await import(process.argv[1]);
const entries = JSON.parse(readFileSync(0,'utf8'));
for (const [id,kind,geometry] of entries) {
  try { validateFeatureGeometry(kind, geometry); }
  catch(e) { process.stderr.write(id + ': ' + e.message); process.exit(2); }
}
"""


class LayoutError(Exception):
    def __init__(self, status, message, **details):
        super().__init__(message)
        self.status = status
        self.response = {"error": message, **details}


def invalid(message):
    raise LayoutError(400, message)


def decode(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("non-finite JSON number")

    return json.loads(data, parse_constant=nonfinite, object_pairs_hook=unique)


def encode(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def number(value, lo, hi):
    return type(value) in (int, float) and lo <= value <= hi and math.isfinite(value)


def string(value, limit, empty=False):
    return (isinstance(value, str) and len(value) <= limit and (bool(value) or empty)
            and all(ch.isprintable() for ch in value))


def vector(v):
    return isinstance(v, list) and len(v) == 2 and all(number(n, -10000, 10000) for n in v)


def bounded_geometry(g):
    if not isinstance(g, dict):
        invalid("geometry must be an object")
    t = g.get("type")
    if t == "curve":
        knots = g.get("knots")
        if (not isinstance(g.get("closed"), bool) or not isinstance(knots, list)
                or not 2 <= len(knots) <= 256):
            invalid("invalid curve")
        if any(not isinstance(k, dict) or k.get("mode") not in ("smooth", "corner")
               or not all(vector(k.get(field)) for field in ("p", "in", "out")) for k in knots):
            invalid("invalid curve control point")
    elif t in ("circle", "arc", "rectangle", "point"):
        if not vector(g.get("center")):
            invalid("invalid centre coordinates")
        if t in ("circle", "arc") and not number(g.get("radius"), .001, 1000):
            invalid("invalid radius")
        if t == "rectangle" and not all(number(g.get(key), .001, 1000) for key in ("width", "depth")):
            invalid("invalid rectangle size")
        if t in ("point", "rectangle") and not number(g.get("yaw"), -10000, 10000):
            invalid("invalid yaw")
        if t == "arc" and not all(number(g.get(key), -10000, 10000) for key in ("startAngle", "sweepAngle")):
            invalid("invalid arc angle")
    else:
        invalid("unknown geometry type")


def validate_garden(garden):
    if (not isinstance(garden, dict) or type(garden.get("schema")) is not int
            or garden["schema"] != 1 or not isinstance(garden.get("objects"), list)):
        invalid("expected garden schema 1 and an objects array")
    objects = garden["objects"]
    if len(objects) > 1024:
        invalid("too many garden objects")
    ids = set()
    for obj in objects:
        if not isinstance(obj, dict) or not isinstance(obj.get("id"), str) or not OBJECT_ID.fullmatch(obj["id"]):
            invalid("invalid object ID")
        if obj["id"] in ids:
            invalid("duplicate object ID")
        ids.add(obj["id"])
        if not isinstance(obj.get("kind"), str) or obj["kind"] not in KINDS:
            invalid("unknown object kind")
        if not string(obj.get("label"), 160):
            invalid("invalid object label")
        for key in ("material", "pattern", "palette", "coping"):
            if not string(obj.get(key), 96, empty=(key == "coping")):
                invalid("invalid " + key)
        if "species" in obj and not string(obj["species"], 96):
            invalid("invalid species")
        for key in ("baseY", "level", "width", "height"):
            if not number(obj.get(key), -1000 if key in ("baseY", "level") else 0, 1000):
                invalid("invalid " + key)
        if obj["kind"] == "outbuilding-base":
            if obj["material"] != "concrete" or obj["height"] <= 0:
                invalid("An outbuilding base needs concrete and a positive slab thickness")
            if obj["coping"] or "steps" in obj:
                invalid("An outbuilding base cannot have garden coping or fitted steps")
        if "steps" in obj:
            s = obj["steps"]
            if (not isinstance(s, dict) or not number(s.get("at"), 0, 1)
                    or type(s.get("count")) is not int or not 1 <= s["count"] <= 32
                    or not number(s.get("width"), .001, 1000)):
                invalid("invalid step placement")
        bounded_geometry(obj.get("geometry"))
    if not objects:
        return
    executable = shutil.which("node") or next((p for p in ("/opt/homebrew/bin/node", "/usr/local/bin/node")
                                               if os.access(p, os.X_OK)), None)
    if not executable:
        raise LayoutError(503, "Garden geometry validation is unavailable")
    with VALIDATOR_LOCK:
        try:
            check = subprocess.run([executable, "--max-old-space-size=96", "--input-type=module",
                                    "-e", VALIDATOR, CATALOGUE.as_uri()],
                                   input=encode([[o["id"], o["kind"], o["geometry"]] for o in objects]),
                                   capture_output=True, timeout=12)
        except (OSError, subprocess.TimeoutExpired):
            raise LayoutError(503, "Garden geometry validation is unavailable") from None
    if check.returncode == 2:
        invalid(check.stderr.decode("utf-8", errors="replace")[:240] or "invalid geometry")
    if check.returncode:
        raise LayoutError(503, "Garden geometry validation is unavailable")


def initial(site, version):
    return {"schema": 1, "site": site, "version": version, "revision": 0,
            "items": [], "wallColours": {}, "roomFloors": {}, "garden": {"schema": 1, "objects": []}}


@contextmanager
def directory(name, parent=None, create=False):
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
            os.fsync(parent)
        except FileExistsError:
            pass
    try:
        fd = os.open(name, os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    except OSError as e:
        if e.errno in (errno.ELOOP, errno.ENOTDIR):
            invalid("unsafe layout directory")
        raise
    try:
        yield fd
    finally:
        os.close(fd)


def regular(fd, name):
    try:
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode):
        invalid("unsafe layout file")
    return True


def read_bytes(fd, name, limit=MAX_LAYOUT):
    if not regular(fd, name):
        return None
    # Pin the directory and the opened file; a concurrent symlink swap cannot escape.
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        handle = os.open(name, flags, dir_fd=fd)
    except OSError as e:
        if e.errno == errno.ELOOP:
            invalid("unsafe layout file")
        raise
    with os.fdopen(handle, "rb") as file:
        if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
            invalid("unsafe layout file")
        data = file.read(limit + 1)
    if len(data) > limit:
        raise LayoutError(500, "Stored file exceeds the layout limit")
    return data


def write_bytes(fd, name, data, *, missing_only=False):
    regular(fd, name)
    temp = ".layout-" + uuid.uuid4().hex + ".tmp"
    handle = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd)
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        if missing_only:
            try:
                os.link(temp, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
            except FileExistsError:
                regular(fd, name)
                return False
        else:
            os.replace(temp, name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
        return True
    finally:
        try:
            os.unlink(temp, dir_fd=fd)
        except FileNotFoundError:
            pass


def stored(data, site, version):
    base = initial(site, version)
    if data is None:
        return base
    try:
        record = decode(data)
        if not isinstance(record, dict):
            raise ValueError("layout")
        base.update(record)
        if (type(base["schema"]) is not int or base["schema"] != 1 or base["site"] != site
                or base["version"] != version or type(base["revision"]) is not int or base["revision"] < 0
                or not isinstance(base["garden"], dict) or not isinstance(base["garden"].get("objects"), list)
                or not isinstance(base["items"], list) or not isinstance(base["wallColours"], dict)
                or not isinstance(base["roomFloors"], dict)):
            raise ValueError("layout")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise LayoutError(500, "Invalid existing layout") from None
    return base


def read_json_asset(fd, path, required=False):
    """Read only named ordinary assets below pinned directories, as on layout reads."""
    try:
        if len(path) > 1:
            with directory(path[0], fd) as inner:
                return read_json_asset(inner, path[1:], required)
        data = read_bytes(fd, path[0])
        if data is not None:
            try:
                return decode(data)
            except (ValueError, UnicodeError, RecursionError):
                raise LayoutError(500, "Invalid furnishing source") from None
    except FileNotFoundError:
        pass
    if required:
        raise LayoutError(503, "Furnishing source is unavailable: " + path[-1])
    return None


def furnishing_seed(fd, version):
    seed = read_json_asset(fd, ("furnish", version, "seed.json"))
    if seed is not None and (not isinstance(seed, dict) or seed.get("schema") != 1
                             or not isinstance(seed.get("items"), list)):
        raise LayoutError(500, "Invalid furnishing seed")
    return seed


def normalise_stock(root, record):
    # Unrecognised future entries are retained verbatim. The expandable legacy
    # label is mapped only using its explicit reviewed catalogue entry.
    if not any(isinstance(it, dict) and it.get("variant") == "standard" for it in record["items"]):
        return record
    with directory(root) as project:
        catalogue = read_json_asset(project, ("tools", "library", "kit", "catalogue.json"))
    entries = {v["id"]: v for v in (catalogue or {}).get("items", [])}
    items = []
    for it in record["items"]:
        key = it.get("catalogueId") if isinstance(it, dict) else None
        product = entries.get(key) if isinstance(key, str) else None
        if product and it.get("variant") == product.get("variant"):
            it = dict(it, variant=product["id"])
        items.append(it)
    return dict(record, items=items)


EDITABLE_ITEM_FIELDS = set("id kind style variant catalogueId room position rotation size host hostOffset "
                           "heightAdjustment hostRotation hostContact finishes lampOn name label".split())


def retain_item_extensions(previous, incoming):
    """A client can clear a known finish/host field; it cannot erase fields it never understood."""
    old = {it["id"]: it for it in previous if isinstance(it, dict) and isinstance(it.get("id"), str)}
    result = []
    for item in incoming:
        key = item.get("id") if isinstance(item, dict) else None
        if isinstance(key, str) and key in old:
            item = {**{k: v for k, v in old[key].items() if k not in EDITABLE_ITEM_FIELDS}, **item}
        result.append(item)
    return result


def effective_furnish(record, seed):
    if not seed or record.get("furnishSeeded") is True or record["items"]:
        return record
    # A garden-only save used to write items:[] as a placeholder. A furniture
    # save sets a permanent marker, even when the user removes the final item.
    return dict(record, items=seed["items"], wallColours={**seed.get("wallColours", {}), **record["wallColours"]},
                roomFloors={**seed.get("roomFloors", {}), **record["roomFloors"]})


def validate_furnish(root, fd, site, version, seed, previous, patch):
    if (not isinstance(patch["items"], list) or len(patch["items"]) > 1024
            or not isinstance(patch["wallColours"], dict) or not isinstance(patch["roomFloors"], dict)):
        invalid("expected bounded items, wallColours and roomFloors")
    project_spec = ("spec", "spec_v1.json")
    project_floors = ("spec", "catalogue_v1.json")
    with directory(root) as project:
        def source(path):
            local = read_json_asset(fd, path)
            if local is not None:
                return local
            if site == "house-wip":
                return read_json_asset(project, ("assets", "sites", "house", *path), required=True)
            raise LayoutError(422, "This site has no signed furnishing spec")
        spec = read_json_asset(fd, project_spec) or source(project_spec)
        floors = read_json_asset(fd, project_floors) or source(project_floors)
        try:
            schedule = next(v for k, v in spec["versions"].items() if k == version or v["elements"] == version)
            basename = schedule["elements"]
            if not NAME.fullmatch(basename):
                raise ValueError()
        except StopIteration:
            invalid("This version has no signed room schedule")
        except (KeyError, TypeError, ValueError):
            raise LayoutError(500, "Invalid room schedule") from None
        elements = read_json_asset(fd, (basename + "_elements.json",), required=True)
        doors = read_json_asset(project, ("assets", "planner", site, "doors.json"))
        if doors is None and site == "house-wip":
            doors = read_json_asset(project, ("assets", "planner", "house", "doors.json"))
        catalogue = read_json_asset(project, ("tools", "library", "kit", "catalogue.json"), required=True)
        variants = read_json_asset(fd, ("furnish", version, "variants.json"))
    inputs = {"site": site, "version": version, "spec": spec, "floorCatalogue": floors, "elements": elements,
              "doors": doors or {}, "catalogue": catalogue, "seed": seed or {}, "variants": variants or {}}
    interior = {k: previous[k] for k in ("items", "wallColours", "roomFloors")}
    executable = shutil.which("node") or next((p for p in ("/opt/homebrew/bin/node", "/usr/local/bin/node")
                                                if os.access(p, os.X_OK)), None)
    if not executable:
        raise LayoutError(503, "Furnishing validation is unavailable")
    with VALIDATOR_LOCK:
        try:
            result = subprocess.run([executable, "--max-old-space-size=128", "--input-type=module",
                                     "-e", FURNISH_VALIDATOR, FURNISH_MODULE.as_uri()],
                                    input=encode({"inputs": inputs, "previous": interior, "next": patch}),
                                    capture_output=True, timeout=25)
        except (OSError, subprocess.TimeoutExpired):
            raise LayoutError(503, "Furnishing validation is unavailable") from None
    if result.returncode == 2:
        invalid(result.stderr.decode("utf-8", errors="replace")[:320] or "Invalid furnishing update")
    if result.returncode:
        raise LayoutError(503, "Furnishing validation is unavailable")


def change_record(previous, after, section="garden"):
    old_items = previous["garden"]["objects"] if section == "garden" else previous["items"]
    new_items = after["garden"]["objects"] if section == "garden" else after["items"]
    old = {x["id"]: x for x in old_items}
    new = {x["id"]: x for x in new_items}
    change = {"section": section, "site": after["site"], "version": after["version"],
              "baseRevision": previous["revision"], "revision": after["revision"],
              "at": datetime.now(timezone.utc).isoformat(),
              "upsert": [obj for key, obj in new.items() if old.get(key) != obj],
              "removed": [key for key in old if key not in new]}
    if list(old) != list(new):
        change["order"] = list(new)
    if section == "furnish":
        for key in ("wallColours", "roomFloors"):
            a, b = previous[key], after[key]
            change[key] = {k: b.get(k) for k in dict.fromkeys([*a, *b]) if a.get(k) != b.get(k)}
    return change


class LayoutStore:
    def __init__(self, root):
        self.root = root

    @contextmanager
    def locked_site(self, site):
        if not isinstance(site, str) or not NAME.fullmatch(site):
            invalid("invalid site")
        try:
            with directory(self.root) as project, directory("assets", project) as assets, \
                    directory("sites", assets) as sites, directory(site, sites) as fd:
                # Publication, GET and updates share the same pinned directory lock.
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield fd
        except FileNotFoundError:
            raise LayoutError(404, "Unknown house site") from None

    @contextmanager
    def site(self, site, version):
        if not isinstance(version, str) or not NAME.fullmatch(version):
            invalid("invalid version")
        with self.locked_site(site) as fd:
            manifest = read_bytes(fd, "versions.json")
            if manifest is None:
                raise LayoutError(404, "Unknown house site")
            try:
                versions = {v["id"] for v in decode(manifest)["versions"]}
            except (KeyError, ValueError, TypeError, UnicodeError):
                raise LayoutError(500, "Invalid site manifest") from None
            if version not in versions:
                raise LayoutError(404, "Unknown house version")
            yield fd

    def initialise_missing(self, fd, site, version, seed):
        """Gated publisher only, while locked_site is held; ordinary GET is read-only."""
        if not NAME.fullmatch(version) or not isinstance(seed, dict) or seed.get("schema") != 1 or not isinstance(seed.get("items"), list):
            raise LayoutError(500, "Invalid published furnishing seed")
        with directory("layout", fd, create=True) as layout:
            self.recover(layout, site, version)
            name = version + ".json"
            if regular(layout, name):
                return False
            value = dict(seed, **{k: v for k, v in initial(site, version).items() if k not in ("items", "wallColours", "roomFloors", "garden")})
            value.setdefault("wallColours", {})
            value.setdefault("roomFloors", {})
            value.setdefault("garden", {"schema": 1, "objects": []})
            value["furnishSeeded"] = True
            data = encode(value)
            if len(data) > MAX_LAYOUT:
                raise LayoutError(413, "Furnishing seed is too large")
            stored(data, site, version)
            return write_bytes(layout, name, data, missing_only=True)

    def build_snapshot(self, site, version):
        """Read a coherent, existing version and exact bytes; never recover/write the client site."""
        with self.site(site, version) as fd:
            manifest = decode(read_bytes(fd, "versions.json"))
            row = next(v for v in manifest["versions"] if v["id"] == version)
            try:
                with directory("layout", fd) as layout:
                    if regular(layout, version + ".pending.json"):
                        raise LayoutError(409, "Layout update awaits server recovery; retry the bake")
                    raw = read_bytes(layout, version + ".json")
                    if raw is not None:
                        stored(raw, site, version)
            except FileNotFoundError:
                raw = None
            return {"layout": raw.decode("utf-8") if raw is not None else None, "version": row}

    def recover(self, layout, site, version):
        pending = read_bytes(layout, version + ".pending.json", 5 * MAX_LAYOUT)
        if pending is None:
            return
        try:
            job = decode(pending)
            before = job["previous"].encode("utf-8")
            previous = stored(before, site, version)
            after = stored(encode(job["next"]), site, version)
            log = job["change"]
            if (after["revision"] != previous["revision"] + 1 or log["revision"] != after["revision"]
                    or log["site"] != site or log["version"] != version):
                raise ValueError("journal")
        except (KeyError, TypeError, ValueError, UnicodeError, RecursionError):
            raise LayoutError(500, "Invalid layout recovery record") from None
        current = stored(read_bytes(layout, version + ".json"), site, version)
        if current != previous and current != after:
            raise LayoutError(409, "Layout changed during recovery", revision=current["revision"],
                              currentRevision=current["revision"])
        with directory("changes", layout, create=True) as changes, directory(version, changes, create=True) as logs:
            receipt = f"{after['revision']:09d}.json"
            data = encode(log)
            existing = read_bytes(logs, receipt)
            if existing is not None and existing != data:
                raise LayoutError(500, "Layout change log conflict")
            write_bytes(layout, version + ".previous.json", before)
            if existing is None:
                write_bytes(logs, receipt, data)
            write_bytes(layout, version + ".json", encode(after))
        os.unlink(version + ".pending.json", dir_fd=layout)
        os.fsync(layout)

    def read(self, site, version):
        with self.site(site, version) as fd:
            try:
                with directory("layout", fd) as layout:
                    self.recover(layout, site, version)
                    record = stored(read_bytes(layout, version + ".json"), site, version)
            except FileNotFoundError:
                record = initial(site, version)
            return normalise_stock(self.root, effective_furnish(record, furnishing_seed(fd, version)))

    def save(self, site, version, patch):
        if not isinstance(patch, dict) or patch.get("section") not in ("garden", "furnish"):
            invalid("expected a garden or furnish section update")
        section = patch["section"]
        fields = {"garden"} if section == "garden" else {"items", "wallColours", "roomFloors"}
        if set(patch) not in (fields | {"baseRevision", "section"}, fields | {"baseRevision", "section", "version"}):
            invalid("invalid section fields")
        if "version" in patch and patch["version"] != version:
            invalid("version does not match layout URL")
        revision = patch["baseRevision"]
        if type(revision) is not int or revision < 0:
            invalid("invalid base revision")
        with self.site(site, version) as fd:
            with directory("layout", fd, create=True) as layout:
                self.recover(layout, site, version)
                raw = read_bytes(layout, version + ".json")
                previous = stored(raw, site, version)
                if revision != previous["revision"]:
                    raise LayoutError(409, "Layout revision is stale", revision=previous["revision"],
                                      currentRevision=previous["revision"])
                seed = furnishing_seed(fd, version)
                before = normalise_stock(self.root, effective_furnish(previous, seed))
                if section == "garden":
                    validate_garden(patch["garden"])
                    if previous["garden"] == patch["garden"]:
                        return before
                    after = dict(previous, revision=revision + 1, garden=patch["garden"])
                else:
                    changes = {k: patch[k] for k in fields}
                    if not isinstance(changes["items"], list):
                        invalid("Expected an item list")
                    changes["items"] = retain_item_extensions(before["items"], changes["items"])
                    changes = normalise_stock(self.root, changes)
                    validate_furnish(self.root, fd, site, version, seed, before, changes)
                    if previous.get("furnishSeeded") is True and all(previous[k] == changes[k] for k in fields):
                        return before
                    after = dict(previous, revision=revision + 1, furnishSeeded=True, **changes)
                if len(encode(after)) > MAX_LAYOUT:
                    raise LayoutError(413, "Layout is too large")
                # Preflight all destinations before recording the intent to commit.
                regular(layout, version + ".previous.json")
                with directory("changes", layout, create=True) as changes, directory(version, changes, create=True) as logs:
                    if regular(logs, f"{after['revision']:09d}.json"):
                        raise LayoutError(500, "Layout change log conflict")
                job = {"previous": (raw or encode(previous)).decode("utf-8"),
                       "next": after, "change": change_record(before, after, section)}
                write_bytes(layout, version + ".pending.json", encode(job))
                self.recover(layout, site, version)
                return normalise_stock(self.root, effective_furnish(after, seed))


def handle_layout(handler, root):
    try:
        query = parse_qs(urlsplit(handler.path).query, keep_blank_values=True, max_num_fields=8)
        if set(query) != {"site", "version"} or not all(len(v) == 1 for v in query.values()):
            invalid("specify one site and one version")
        site, version = query["site"][0], query["version"][0]
        store = LayoutStore(root)
        if handler.command == "GET":
            result = store.read(site, version)
        else:
            lengths = handler.headers.get_all("Content-Length") or []
            if handler.headers.get("Transfer-Encoding") or len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,10}", lengths[0]):
                invalid("invalid content length")
            length = int(lengths[0])
            if length > MAX_BODY:
                raise LayoutError(413, "Layout update is too large")
            if not length:
                invalid("empty layout update")
            data = handler.rfile.read(length)
            if len(data) != length:
                invalid("incomplete layout update")
            result = store.save(site, version, decode(data))
        return handler._json(200, result)
    except LayoutError as e:
        return handler._json(e.status, e.response)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        return handler._json(400, {"error": "Invalid layout request"})
    except OSError:
        return handler._json(500, {"error": "Unable to persist the layout"})

if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Read-only source snapshot for a local furnishing build.")
    parser.add_argument("--build-snapshot", nargs=3, required=True, metavar=("PROJECT", "SITE", "VERSION"))
    project, site, version = parser.parse_args().build_snapshot
    try:
        sys.stdout.buffer.write(encode(LayoutStore(project).build_snapshot(site, version)))
    except LayoutError as exc:
        parser.exit(1, str(exc) + "\n")
