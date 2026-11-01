#!/usr/bin/env python3
"""Serve this folder over HTTPS on the home network, so the Quest can open a
private build (WebXR needs a secure origin). Self-signed: the headset shows a
warning once — Advanced, then Proceed. Nothing here is reachable from outside
the wifi.

    python3 tools/https-serve.py [port]       # default 8443

Marks drawn in the headset (src/marks.js):
    GET  /marks?site=<name>        -> assets/sites/<name>/marks.json (or an empty list)
    POST /marks?site=<name>        -> writes that one file, nothing else. The site must
                                      already exist (its site.json, or a house site's versions.json);
                                      the body is capped and rebuilt field by field before it is written.
                                      House marks (house.html?mode=review) also carry version, view
                                      (before | after), stage, stage_name, mode, camera, elements, parts,
                                      room, storey, element_label, version_name: kept, validated.
    POST /marks/audio?site=<name>&id=<stroke>
                                   -> a voice note (raw audio body, audio/webm|mp4|ogg|mpeg|wav,
                                      10 MB cap) saved as assets/sites/<name>/marks_audio/<id>.<ext>.
                                      If tools/transcribe.py exists it is run in the background with
                                      ~/splat/bin/python (120 s timeout); its stdout becomes the
                                      stroke's "note" in marks.json (and marks_audio/<id>.txt).

House viewer (house.html, src/house/) — a separate section at the end of this file; the endpoints above are unchanged.
The site must have assets/sites/<name>/versions.json; <version> is a version id from it.
    GET  /house/requests?site=<name>&version=<v>          -> every change request for that version
    POST /house/requests?site=<name>&version=<v>          -> writes change_requests/<v>/<timestamp>-<id>.json
    POST /house/requests/audio?site=<name>&version=<v>&id=<id>
                                                          -> change_requests/<v>/<id>.<ext>; transcribed like marks
    GET  /house/inspections?site=<name>&version=<v>&stage=<n>
    POST /house/inspections?site=<name>&version=<v>&stage=<n>   -> inspections/<v>/<n>.json (the whole checklist)
    POST /house/perf?site=<name>                          -> appends the headset's frame summary (JSON, <= 256 KB) as one line
                                                             to renders/house-build/perf/<site>-<yyyymmdd>.jsonl
    GET  /house/perf?site=<name>&n=<lines>                -> the last n (default 50) summaries of today's file

Room planner (planner.html, src/planner/) — its own section near the end; nothing above depends on it. Never writes a spec file.
    GET  /spec/changes?site=<name>     -> the base spec name, every change (with its status) and the batches sent so far
    POST /spec/changes?site=<name>     -> {"action": "add", "change": {...}}: one file changes/<stamp>-<id>.json + the running list
                                          {"action": "status", "ids": [...], "status": "undone|active|discarded"}: undo / redo
                                          {"action": "send", "note": "..."}: every active change -> changes/batch-<stamp>.json
                                          (the input for the next spec version); those changes become "sent"
    Files live in assets/sites/<name>/spec/changes/; the site needs assets/sites/<name>/spec/spec_v*.json.
"""
import http.server, ssl, os, sys, functools, json, re, math, urllib.parse, threading, subprocess
from datetime import datetime, timezone

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
root = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
cert = os.path.expanduser("~/.garden-vr-cert")

SITE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SURFACE_RE = re.compile(r"^[A-Za-z0-9_. -]{1,80}$")
AUDIO_FILE_RE = re.compile(r"^marks_audio/[A-Za-z0-9_-]{1,64}\.(webm|m4a|ogg|mp3|wav)$")
MAX_BODY = 8 * 1024 * 1024            # strokes carry 3D points and normals now
MAX_AUDIO = 10 * 1024 * 1024
MAX_STROKES, MAX_POINTS = 2000, 20000
MARK_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
MARK_NAME_RE = re.compile(r"^[^\x00-\x1f]{1,160}$")       # element ids, part names: printable, short
KINDS = {"correction", "proposal"}
NOTE_STATUS = {None, "typed", "awaiting transcription", "transcribed"}
AUDIO_EXT = {"audio/webm": "webm", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "m4a",
             "audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/wav": "wav", "audio/x-wav": "wav"}
TRANSCRIBE = os.path.join(root, "tools", "transcribe.py")
TRANSCRIBE_PY = os.path.expanduser("~/splat/bin/python")
NUM = r"(-?[0-9.eE+-]+)"
PAIR_RE = re.compile(r"\[\s+" + NUM + r",\s+" + NUM + r"\s+\]")
TRIPLE_RE = re.compile(r"\[\s+" + NUM + r",\s+" + NUM + r",\s+" + NUM + r"\s+\]")
lock = threading.Lock()               # every read-modify-write of a marks.json


def _num(v, lim=100000.0):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > lim:
        raise ValueError("bad number")
    return v


def _vecs(lst, n, dim, lim):
    if not isinstance(lst, list) or len(lst) != n:
        raise ValueError("bad 3d points")
    out = []
    for p in lst:
        if not isinstance(p, list) or len(p) != dim:
            raise ValueError("bad 3d point")
        out.append([round(_num(c, lim), 3) for c in p])
    return out


def _str(v, n):
    return v[:n] if isinstance(v, str) else None


def clean_strokes(strokes):
    if not isinstance(strokes, list) or len(strokes) > MAX_STROKES:
        raise ValueError("strokes must be a list")
    out = []
    for s in strokes:
        if not isinstance(s, dict):
            raise ValueError("bad stroke")
        pts = s.get("points")
        if not isinstance(pts, list) or not 2 <= len(pts) <= MAX_POINTS:
            raise ValueError("bad points")
        sid, kind = s.get("id"), s.get("kind")
        if not isinstance(sid, str) or not ID_RE.match(sid) or kind not in KINDS:
            raise ValueError("bad id or kind")
        points = []
        for p in pts:
            if not isinstance(p, list) or len(p) != 2:
                raise ValueError("bad point")
            points.append([round(_num(p[0], 10000), 3), round(_num(p[1], 10000), 3)])
        area = s.get("area_m2")
        audio, status, surface = s.get("audio"), s.get("note_status"), s.get("surface")
        if audio is not None and not (isinstance(audio, str) and AUDIO_FILE_RE.match(audio)):
            raise ValueError("bad audio")
        if status not in NOTE_STATUS:
            raise ValueError("bad note_status")
        if surface is not None and not (isinstance(surface, str) and SURFACE_RE.match(surface)):
            raise ValueError("bad surface")
        c = {
            "id": sid,
            "kind": kind,
            "closed": bool(s.get("closed")),
            "points": points,
        }
        if s.get("points3d") is not None:
            c["points3d"] = _vecs(s["points3d"], len(points), 3, 10000)
            c["normals"] = _vecs(s.get("normals"), len(points), 3, 2)
        c.update(clean_house_fields(s))
        c.update({
            "surface": surface,
            "length_m": round(_num(s.get("length_m", 0)), 2),
            "area_m2": None if area is None else round(_num(area), 2),
            "created": _str(s.get("created"), 40),
            "note": _str(s.get("note"), 2000),
            "audio": audio,
            "note_status": status,
        })
        out.append(c)
    return out


def clean_house_fields(s):
    """The house viewer's extra fields on a mark (src/house/viewer.js, review mode); absent ones stay absent."""
    out = {}
    v = s.get("version")
    if v is not None:
        if not (isinstance(v, str) and MARK_VERSION_RE.match(v)):
            raise ValueError("bad version")
        out["version"] = v
    if s.get("view") is not None:
        if s["view"] not in ("before", "after"):
            raise ValueError("bad view")
        out["view"] = s["view"]
    if s.get("stage") is not None:
        out["stage"] = int(_num(s["stage"], 1000))
    for k, n in (("version_name", 120), ("stage_name", 160), ("mode", 20), ("room", 120), ("storey", 20), ("element_label", 300)):
        if s.get(k) is not None:
            out[k] = _str(s[k], n)
    if s.get("camera") is not None:
        cam = s["camera"]
        if not isinstance(cam, list) or len(cam) != 3:
            raise ValueError("bad camera")
        out["camera"] = [round(_num(x, 10000), 3) for x in cam]
    for k in ("elements", "parts"):
        lst = s.get(k)
        if lst is None:
            continue
        if not isinstance(lst, list) or len(lst) > 20 or not all(isinstance(x, str) and MARK_NAME_RE.match(x) for x in lst):
            raise ValueError("bad " + k)
        out[k] = lst
    return out


def read_marks(path, site):
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"site": site, "updated": None, "strokes": []}


def write_marks(path, site, strokes):
    out = {"site": site, "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "strokes": strokes}
    text = json.dumps(out, indent=2, ensure_ascii=False)
    text = TRIPLE_RE.sub(r"[\1, \2, \3]", text)        # one point per line, not four or five
    text = PAIR_RE.sub(r"[\1, \2]", text)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    os.replace(tmp, path)
    return out["updated"]


def transcript_for(site_dir, sid):
    p = os.path.join(site_dir, "marks_audio", sid + ".txt")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            return f.read().strip()[:2000] or None
    return None


def transcribe(site, site_dir, marks_path, sid, audio_path):
    """Background: run the hook, keep the text beside the clip and in marks.json."""
    if not (os.path.isfile(TRANSCRIBE) and os.path.isfile(TRANSCRIBE_PY)):
        return
    try:
        r = subprocess.run([TRANSCRIBE_PY, TRANSCRIBE, audio_path], cwd=root, capture_output=True,
                           text=True, timeout=120)
        text = (r.stdout or "").strip()[:2000]
        if r.returncode != 0:
            print(f"transcribe {sid}: exit {r.returncode}: {(r.stderr or '').strip()[-300:]}", flush=True)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"transcribe {sid}: {e}", flush=True)
        return
    if not text:
        return                                          # model not installed yet: stays "awaiting transcription"
    with open(os.path.join(site_dir, "marks_audio", sid + ".txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    with lock:
        data = read_marks(marks_path, site)
        for s in data.get("strokes", []):
            if s.get("id") == sid:
                s["note"], s["note_status"] = text, "transcribed"
                write_marks(marks_path, site, data["strokes"])
                break
    print(f"transcribe {sid}: {text[:80]}", flush=True)


class Handler(http.server.SimpleHTTPRequestHandler):
    def _site(self, want_path):
        """(site, site_dir, query) when the request is for want_path; None otherwise.
        Raises ValueError for a bad or unknown site."""
        u = urllib.parse.urlsplit(self.path)
        if u.path != want_path:
            return None
        q = urllib.parse.parse_qs(u.query)
        site = q.get("site", [""])[0]
        if not SITE_RE.match(site):
            raise ValueError("bad site name")
        d = os.path.join(root, "assets", "sites", site)
        # a garden site has site.json; a house site (house, house-wip, house-preview…) has versions.json
        if not (os.path.isfile(os.path.join(d, "site.json")) or os.path.isfile(os.path.join(d, "versions.json"))):
            raise ValueError("unknown site")
        return site, d, q

    def _json(self, code, obj):
        body = json.dumps(obj, indent=1, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urllib.parse.urlsplit(self.path).path.startswith("/scan/"):
            return scan_get(self)
        if urllib.parse.urlsplit(self.path).path.startswith("/house/"):
            return house_get(self)
        if urllib.parse.urlsplit(self.path).path.startswith("/spec/"):
            return spec_get(self)
        try:
            t = self._site("/marks")
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        if t is None:
            return super().do_GET()
        site, d, _ = t
        with lock:
            return self._json(200, read_marks(os.path.join(d, "marks.json"), site))

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        if path.startswith("/scan/"):
            return scan_post(self)
        if path.startswith("/house/"):
            return house_post(self)
        if path.startswith("/spec/"):
            return spec_post(self)
        try:
            if path == "/marks":
                return self._post_marks(*self._site("/marks"))
            if path == "/marks/audio":
                return self._post_audio(*self._site("/marks/audio"))
        except (ValueError, TypeError, IndexError, UnicodeDecodeError) as e:
            return self._json(400, {"error": str(e)})
        return self._json(404, {"error": "not found"})

    def _post_marks(self, site, d, _q):
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            return self._json(413, {"error": "body too large or empty"})
        body = json.loads(self.rfile.read(n).decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("body must be an object")
        strokes = clean_strokes(body.get("strokes"))
        path = os.path.join(d, "marks.json")
        with lock:
            # a transcript can land between the viewer's polls: never let a full-list save wipe it
            old = {s.get("id"): s for s in read_marks(path, site).get("strokes", [])}
            for s in strokes:
                if s["note_status"] != "awaiting transcription":
                    continue
                o = old.get(s["id"])
                if o and o.get("note_status") == "transcribed" and o.get("note"):
                    s["note"], s["note_status"] = o["note"], "transcribed"
                else:
                    text = transcript_for(d, s["id"])
                    if text:
                        s["note"], s["note_status"] = text, "transcribed"
            updated = write_marks(path, site, strokes)
        self.log_message("marks: %d strokes -> %s", len(strokes), os.path.relpath(path, root))
        return self._json(200, {"ok": True, "count": len(strokes), "updated": updated})

    def _post_audio(self, site, d, q):
        sid = q.get("id", [""])[0]
        if not ID_RE.match(sid):
            raise ValueError("bad id")
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        ext = AUDIO_EXT.get(ctype)
        if not ext:
            return self._json(415, {"error": "audio/webm, audio/mp4, audio/ogg, audio/mpeg or audio/wav only"})
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_AUDIO:
            return self._json(413, {"error": "audio too large or empty"})
        data = self.rfile.read(n)
        adir = os.path.join(d, "marks_audio")
        os.makedirs(adir, exist_ok=True)
        rel = f"marks_audio/{sid}.{ext}"
        apath = os.path.join(d, rel)
        tmp = apath + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, apath)
        stale = os.path.join(adir, sid + ".txt")             # a new clip replaces the old words
        if os.path.isfile(stale):
            os.remove(stale)
        marks_path = os.path.join(d, "marks.json")
        with lock:
            m = read_marks(marks_path, site)
            for s in m.get("strokes", []):
                if s.get("id") == sid:
                    s["audio"], s["note_status"] = rel, "awaiting transcription"
                    write_marks(marks_path, site, m["strokes"])
                    break
        threading.Thread(target=transcribe, args=(site, d, marks_path, sid, apath), daemon=True).start()
        self.log_message("marks: voice note %s (%d bytes)", rel, n)
        return self._json(200, {"ok": True, "file": rel, "note_status": "awaiting transcription"})


# ==================================================================================================
#  House viewer endpoints (house.html). Self-contained: nothing above depends on this section.
# ==================================================================================================
VERSION_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
HOUSE_MAX_BODY = 2 * 1024 * 1024
house_lock = threading.Lock()


def _house_args(h, need_version=True):
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(h.path).query)
    site, version = q.get("site", [""])[0], q.get("version", [""])[0]
    if not SITE_RE.match(site):
        raise ValueError("bad site name")
    d = os.path.join(root, "assets", "sites", site)
    vf = os.path.join(d, "versions.json")
    if not os.path.isfile(vf):
        raise ValueError("unknown house site")
    if need_version:
        with open(vf, encoding="utf-8") as f:
            ids = {v.get("id") for v in json.load(f).get("versions", [])}
        if not VERSION_RE.match(version) or version not in ids:
            raise ValueError("unknown version")
    return site, d, version, q


def _clean_json(v, depth=0):
    """Plain JSON only, bounded: strings capped, numbers finite, nesting shallow."""
    if depth > 8:
        raise ValueError("too deep")
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return _num(v, 1e7)
    if isinstance(v, str):
        return v[:4000]
    if isinstance(v, list):
        if len(v) > 5000: raise ValueError("list too long")
        return [_clean_json(x, depth + 1) for x in v]
    if isinstance(v, dict):
        if len(v) > 200: raise ValueError("object too big")
        return {str(k)[:64]: _clean_json(x, depth + 1) for k, x in v.items()}
    raise ValueError("bad value")


def _read_body(h):
    n = int(h.headers.get("Content-Length") or 0)
    if n <= 0 or n > HOUSE_MAX_BODY:
        raise ValueError("body too large or empty")
    body = json.loads(h.rfile.read(n).decode("utf-8"))
    if not isinstance(body, dict):
        raise ValueError("body must be an object")
    return _clean_json(body)


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def _request_files(d, version):
    rd = os.path.join(d, "change_requests", version)
    return sorted(os.path.join(rd, f) for f in os.listdir(rd) if f.endswith(".json")) if os.path.isdir(rd) else []


PERF_DIR = os.path.join(root, "renders", "house-build", "perf")
PERF_MAX_BODY = 256 * 1024


def _perf_file(site):
    return os.path.join(PERF_DIR, f"{site}-{datetime.now().strftime('%Y%m%d')}.jsonl")


def house_perf_post(h):
    site, _d, _v, _q = _house_args(h, need_version=False)
    n = int(h.headers.get("Content-Length") or 0)
    if n <= 0 or n > PERF_MAX_BODY:
        raise ValueError("body too large or empty")
    body = json.loads(h.rfile.read(n).decode("utf-8"))
    if not isinstance(body, dict):
        raise ValueError("body must be an object")
    body = _clean_json(body)
    body.update(site=site, received=datetime.now(timezone.utc).isoformat(timespec="seconds"), client=h.client_address[0])
    os.makedirs(PERF_DIR, exist_ok=True)
    with house_lock:
        with open(_perf_file(site), "a", encoding="utf-8") as f:
            f.write(json.dumps(body, ensure_ascii=False) + "\n")
    lf = body.get("long_frames") or []
    h.log_message("house perf: %s fps %s, worst %s ms, %d long frames", site, body.get("fps"), (body.get("frame_ms") or {}).get("worst"), len(lf))
    return h._json(200, {"ok": True})


def house_perf_get(h):
    site, _d, _v, q = _house_args(h, need_version=False)
    want = max(1, min(500, int(q.get("n", ["50"])[0] or 50)))
    p = _perf_file(site)
    lines = []
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            lines = f.readlines()[-want:]
    return h._json(200, {"site": site, "file": os.path.relpath(p, root), "summaries": [json.loads(l) for l in lines if l.strip()]})


def house_get(h):
    path = urllib.parse.urlsplit(h.path).path
    try:
        if path == "/house/perf":
            return house_perf_get(h)
        site, d, version, q = _house_args(h)
        if path == "/house/requests":
            out = []
            for p in _request_files(d, version):
                with open(p, encoding="utf-8") as f:
                    out.append(json.load(f))
            return h._json(200, {"site": site, "version": version, "requests": out})
        if path == "/house/inspections":
            stage = q.get("stage", [""])[0]
            if not re.match(r"^[a-z0-9_-]{1,32}$", stage):
                raise ValueError("bad stage")
            p = os.path.join(d, "inspections", version, stage + ".json")
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    return h._json(200, json.load(f))
            return h._json(200, {"site": site, "version": version, "stage": stage, "checks": {}})
    except (ValueError, OSError) as e:
        return h._json(400, {"error": str(e)})
    return h._json(404, {"error": "not found"})


def house_post(h):
    path = urllib.parse.urlsplit(h.path).path
    try:
        if path == "/house/perf":
            return house_perf_post(h)
        site, d, version, q = _house_args(h)
        if path == "/house/requests":
            body = _read_body(h)
            rid = body.get("id")
            if not isinstance(rid, str) or not ID_RE.match(rid):
                raise ValueError("bad id")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            body.update(site=site, version=version, received=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            with house_lock:
                old = [p for p in _request_files(d, version) if p.endswith(f"-{rid}.json")]
                p = old[0] if old else os.path.join(d, "change_requests", version, f"{stamp}-{rid}.json")
                _write_json(p, body)
            h.log_message("house: change request %s", os.path.relpath(p, root))
            return h._json(200, {"ok": True, "file": os.path.relpath(p, d)})
        if path == "/house/requests/audio":
            rid = q.get("id", [""])[0]
            if not ID_RE.match(rid):
                raise ValueError("bad id")
            ext = AUDIO_EXT.get((h.headers.get("Content-Type") or "").split(";")[0].strip().lower())
            if not ext:
                return h._json(415, {"error": "audio/webm, audio/mp4, audio/ogg, audio/mpeg or audio/wav only"})
            n = int(h.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_AUDIO:
                return h._json(413, {"error": "audio too large or empty"})
            rel = f"change_requests/{version}/{rid}.{ext}"
            apath = os.path.join(d, rel)
            os.makedirs(os.path.dirname(apath), exist_ok=True)
            with open(apath + ".tmp", "wb") as f:
                f.write(h.rfile.read(n))
            os.replace(apath + ".tmp", apath)
            threading.Thread(target=_house_transcribe, args=(d, version, rid, apath), daemon=True).start()
            return h._json(200, {"ok": True, "file": rel, "note_status": "awaiting transcription"})
        if path == "/house/inspections":
            stage = q.get("stage", [""])[0]
            if not re.match(r"^[a-z0-9_-]{1,32}$", stage):
                raise ValueError("bad stage")
            body = _read_body(h)
            body.update(site=site, version=version, stage=stage, saved=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            with house_lock:
                _write_json(os.path.join(d, "inspections", version, stage + ".json"), body)
            return h._json(200, {"ok": True})
    except (ValueError, TypeError, OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return h._json(400, {"error": str(e)})
    return h._json(404, {"error": "not found"})


def _house_transcribe(d, version, rid, apath):
    """Background: the same transcribe hook as marks; the text goes into the request's note."""
    if not (os.path.isfile(TRANSCRIBE) and os.path.isfile(TRANSCRIBE_PY)):
        return
    try:
        r = subprocess.run([TRANSCRIBE_PY, TRANSCRIBE, apath], cwd=root, capture_output=True, text=True, timeout=120)
        text = (r.stdout or "").strip()[:4000]
    except (subprocess.TimeoutExpired, OSError):
        return
    if not text:
        return
    with house_lock:
        for p in _request_files(d, version):
            if p.endswith(f"-{rid}.json"):
                with open(p, encoding="utf-8") as f:
                    req = json.load(f)
                if not req.get("note"):
                    req["note"] = text
                req["note_status"] = "transcribed"
                req["transcript"] = text
                _write_json(p, req)
                break

# ---------------------------------------------------------------------------------------------------------------
# Room scans from the Quest (scan.html): one JSON per saved room, kept OUT of the repo because it is the inside of a
# client's home. POST /scan/room?site=<s>&room=<slug>  (planes + meshes + furniture boxes, <= 64 MB)
#                GET  /scan/rooms?site=<s>               -> what has been saved so far
SCAN_ROOT = os.path.expanduser("~/Desktop/garden-scans/house-scan")
SCAN_MAX = 64 * 1024 * 1024
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")


def _scan_args(h):
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(h.path).query)
    site = q.get("site", ["house"])[0]
    if not SLUG_RE.match(site):
        raise ValueError("bad site")
    return site, os.path.join(SCAN_ROOT, site), q


def scan_get(h):
    try:
        site, d, _q = _scan_args(h)
        rooms = []
        if os.path.isdir(d):
            for name in sorted(os.listdir(d)):
                if name.endswith(".json"):
                    with open(os.path.join(d, name), encoding="utf-8") as f:
                        r = json.load(f)
                    rooms.append({"file": name, "room": r.get("room"), "saved": r.get("received"),
                                  "planes": len(r.get("planes") or []), "meshes": len(r.get("meshes") or [])})
        return h._json(200, {"site": site, "rooms": rooms})
    except (ValueError, OSError) as e:
        return h._json(400, {"error": str(e)})


def scan_post(h):
    try:
        if urllib.parse.urlsplit(h.path).path != "/scan/room":
            return h._json(404, {"error": "not found"})
        site, d, q = _scan_args(h)
        room = q.get("room", [""])[0]
        if not SLUG_RE.match(room):
            raise ValueError("bad room name")
        n = int(h.headers.get("Content-Length") or 0)
        if n <= 0 or n > SCAN_MAX:
            raise ValueError("empty or too large")
        body = json.loads(h.rfile.read(n).decode("utf-8"))
        body.update(site=site, room=room, received=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        os.makedirs(d, exist_ok=True)
        name = f"{room}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            json.dump(body, f)
        h.log_message("scan: %s/%s %d planes, %d meshes", site, room, len(body.get("planes") or []), len(body.get("meshes") or []))
        return h._json(200, {"ok": True, "file": name, "planes": len(body.get("planes") or []), "meshes": len(body.get("meshes") or [])})
    except (ValueError, OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return h._json(400, {"error": str(e)})


# ---------------------------------------------------------------------------------------------------------------
# Room planner change list (planner.html). Additive: one JSON file per change and a running list, under
# assets/sites/<site>/spec/changes/. It only ever writes inside that folder, with names it makes itself; the signed-off
# spec_v*.json files are read for their names only and never opened for writing.
SPEC_CHANGE_DIR = "changes"
SPEC_OP_RE = re.compile(r"^[a-z][a-z_.]{1,40}$")
SPEC_STATUS = {"active", "undone", "discarded"}
SPEC_MAX_CHANGES = 5000
spec_lock = threading.Lock()


def _spec_args(h):
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(h.path).query)
    site = q.get("site", [""])[0]
    if not SITE_RE.match(site):
        raise ValueError("bad site name")
    d = os.path.join(root, "assets", "sites", site, "spec")
    specs = sorted((f for f in os.listdir(d) if re.match(r"^spec_v[0-9]+\.json$", f)),
                   key=lambda f: int(f[6:-5])) if os.path.isdir(d) else []
    if not specs:
        raise ValueError("unknown site (no spec)")
    return site, d, specs[-1], q


def _spec_list(cd, site, base):
    p = os.path.join(cd, "changes.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"site": site, "base_spec": base, "updated": None, "changes": [], "batches": []}


def _spec_save_list(cd, lst):
    lst["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _write_json(os.path.join(cd, "changes.json"), lst)


def spec_get(h):
    try:
        if urllib.parse.urlsplit(h.path).path != "/spec/changes":
            return h._json(404, {"error": "not found"})
        site, d, base, _q = _spec_args(h)
        cd = os.path.join(d, SPEC_CHANGE_DIR)
        with spec_lock:
            lst = _spec_list(cd, site, base)
            out = []
            for row in lst.get("changes", []):
                p = os.path.join(cd, row["file"])
                if os.path.isfile(p):
                    with open(p, encoding="utf-8") as f:
                        c = json.load(f)
                    c["status"], c["batch"] = row.get("status"), row.get("batch")
                    out.append(c)
        return h._json(200, {"site": site, "base_spec": base, "updated": lst.get("updated"), "changes": out,
                             "batches": lst.get("batches", [])})
    except (ValueError, OSError, json.JSONDecodeError) as e:
        return h._json(400, {"error": str(e)})


def spec_post(h):
    try:
        if urllib.parse.urlsplit(h.path).path != "/spec/changes":
            return h._json(404, {"error": "not found"})
        site, d, base, _q = _spec_args(h)
        body = _read_body(h)
        cd = os.path.join(d, SPEC_CHANGE_DIR)
        action = body.get("action")
        now = datetime.now(timezone.utc)
        with spec_lock:
            lst = _spec_list(cd, site, base)
            rows = lst.setdefault("changes", [])
            if action == "add":
                c = body.get("change")
                if not isinstance(c, dict):
                    raise ValueError("change must be an object")
                cid, op = c.get("id"), c.get("op")
                if not isinstance(cid, str) or not ID_RE.match(cid):
                    raise ValueError("bad change id")
                if not isinstance(op, str) or not SPEC_OP_RE.match(op):
                    raise ValueError("bad op")
                if any(r["id"] == cid for r in rows):
                    return h._json(200, {"ok": True, "id": cid, "duplicate": True})
                if len(rows) >= SPEC_MAX_CHANGES:
                    raise ValueError("too many changes: send a batch first")
                c.pop("status", None); c.pop("batch", None)
                c.update(site=site, base_spec=base, received=now.isoformat(timespec="seconds"),
                         client=h.client_address[0])
                name = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{cid}.json"
                _write_json(os.path.join(cd, name), c)
                rows.append({"id": cid, "file": name, "op": op, "summary": str(c.get("summary") or "")[:300],
                             "at": c.get("at"), "status": "active", "batch": None})
                _spec_save_list(cd, lst)
                h.log_message("planner: change %s %s", cid, op)
                return h._json(200, {"ok": True, "id": cid, "file": f"spec/{SPEC_CHANGE_DIR}/{name}"})
            if action == "status":
                ids, status = body.get("ids"), body.get("status")
                if status not in SPEC_STATUS or not isinstance(ids, list):
                    raise ValueError("bad status request")
                want, n = set(i for i in ids if isinstance(i, str)), 0
                for r in rows:
                    if r["id"] in want and r.get("status") != "sent":
                        r["status"] = status; n += 1
                _spec_save_list(cd, lst)
                return h._json(200, {"ok": True, "changed": n})
            if action == "send":
                active = [r for r in rows if r.get("status") == "active"]
                if not active:
                    raise ValueError("nothing to send")
                bname = f"batch-{now.strftime('%Y%m%dT%H%M%SZ')}.json"
                changes = []
                for r in active:
                    with open(os.path.join(cd, r["file"]), encoding="utf-8") as f:
                        changes.append(json.load(f))
                batch = {"site": site, "base_spec": base, "made": now.isoformat(timespec="seconds"),
                         "made_by": "planner.html 'Send to build'", "note": str(body.get("note") or "")[:2000],
                         "purpose": f"the change list the next spec version (after {base}) is made from; one rebuild",
                         "count": len(changes), "summary": [c.get("summary") for c in changes], "changes": changes}
                _write_json(os.path.join(cd, bname), batch)
                for r in active:
                    r["status"], r["batch"] = "sent", bname
                lst.setdefault("batches", []).append({"file": bname, "made": batch["made"], "count": len(changes)})
                _spec_save_list(cd, lst)
                h.log_message("planner: sent %d changes -> %s", len(changes), bname)
                return h._json(200, {"ok": True, "file": f"spec/{SPEC_CHANGE_DIR}/{bname}", "count": len(changes)})
        raise ValueError("unknown action")
    except (ValueError, TypeError, OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return h._json(400, {"error": str(e)})


handler = functools.partial(Handler, directory=root)
httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(os.path.join(cert, "cert.pem"), os.path.join(cert, "key.pem"))
httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
print(f"https://0.0.0.0:{port}/", flush=True)
httpd.serve_forever()
