"""Shared, versioned house layouts. The garden editor owns only the garden section."""
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
            "fire-pit steps fence edging planting-bed plant tree".split())
MAX_BODY = 2 * 1024 * 1024
MAX_LAYOUT = 12 * 1024 * 1024
CATALOGUE = Path(__file__).resolve().parents[1] / "src/garden/catalogue.mjs"
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


def write_bytes(fd, name, data):
    regular(fd, name)
    temp = ".layout-" + uuid.uuid4().hex + ".tmp"
    handle = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd)
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
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
                or not isinstance(base["garden"], dict) or not isinstance(base["garden"].get("objects"), list)):
            raise ValueError("layout")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise LayoutError(500, "Invalid existing layout") from None
    return base


def change_record(previous, after):
    old = {x["id"]: x for x in previous["garden"]["objects"]}
    new = {x["id"]: x for x in after["garden"]["objects"]}
    change = {"section": "garden", "site": after["site"], "version": after["version"],
              "baseRevision": previous["revision"], "revision": after["revision"],
              "at": datetime.now(timezone.utc).isoformat(),
              "upsert": [obj for key, obj in new.items() if old.get(key) != obj],
              "removed": [key for key in old if key not in new]}
    if list(old) != list(new):
        change["order"] = list(new)
    return change


class LayoutStore:
    def __init__(self, root):
        self.root = root

    @contextmanager
    def site(self, site, version):
        if not all(isinstance(v, str) and NAME.fullmatch(v) for v in (site, version)):
            invalid("invalid site or version")
        try:
            with directory(self.root) as project, directory("assets", project) as assets, \
                    directory("sites", assets) as sites, directory(site, sites) as fd:
                manifest = read_bytes(fd, "versions.json")
                if manifest is None:
                    raise LayoutError(404, "Unknown house site")
                try:
                    versions = {v["id"] for v in decode(manifest)["versions"]}
                except (KeyError, ValueError, TypeError, UnicodeError):
                    raise LayoutError(500, "Invalid site manifest") from None
                if version not in versions:
                    raise LayoutError(404, "Unknown house version")
                # flock across server threads AND separate server processes.
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield fd
        except FileNotFoundError:
            raise LayoutError(404, "Unknown house site") from None

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
                    return stored(read_bytes(layout, version + ".json"), site, version)
            except FileNotFoundError:
                return initial(site, version)

    def save(self, site, version, patch):
        if not isinstance(patch, dict) or set(patch) != {"baseRevision", "section", "garden"} or patch["section"] != "garden":
            invalid("expected a garden section update")
        revision = patch["baseRevision"]
        if type(revision) is not int or revision < 0:
            invalid("invalid base revision")
        with self.site(site, version) as fd:
            validate_garden(patch["garden"])
            with directory("layout", fd, create=True) as layout:
                self.recover(layout, site, version)
                raw = read_bytes(layout, version + ".json")
                previous = stored(raw, site, version)
                if revision != previous["revision"]:
                    raise LayoutError(409, "Layout revision is stale", revision=previous["revision"],
                                      currentRevision=previous["revision"])
                if previous["garden"] == patch["garden"]:
                    return previous
                after = dict(previous, revision=revision + 1, garden=patch["garden"])
                if len(encode(after)) > MAX_LAYOUT:
                    raise LayoutError(413, "Layout is too large")
                # Preflight all destinations before recording the intent to commit.
                regular(layout, version + ".previous.json")
                with directory("changes", layout, create=True) as changes, directory(version, changes, create=True) as logs:
                    if regular(logs, f"{after['revision']:09d}.json"):
                        raise LayoutError(500, "Layout change log conflict")
                job = {"previous": (raw or encode(previous)).decode("utf-8"),
                       "next": after, "change": change_record(previous, after)}
                write_bytes(layout, version + ".pending.json", encode(job))
                self.recover(layout, site, version)
                return after


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
