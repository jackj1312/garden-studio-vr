#!/usr/bin/env python3
"""Serve this folder over HTTPS on the home network, so the Quest can open a
private build (WebXR needs a secure origin). Self-signed: the headset shows a
warning once — Advanced, then Proceed. Nothing here is reachable from outside
the wifi.

    python3 tools/https-serve.py [port]       # default 8443

Marks drawn in the headset (src/marks.js):
    GET  /marks?site=<name>        -> assets/sites/<name>/marks.json (or an empty list)
    POST /marks?site=<name>        -> writes that one file, nothing else. The site must
                                      already exist (its site.json); the body is capped
                                      and rebuilt field by field before it is written.
    POST /marks/audio?site=<name>&id=<stroke>
                                   -> a voice note (raw audio body, audio/webm|mp4|ogg|mpeg|wav,
                                      10 MB cap) saved as assets/sites/<name>/marks_audio/<id>.<ext>.
                                      If tools/transcribe.py exists it is run in the background with
                                      ~/splat/bin/python (120 s timeout); its stdout becomes the
                                      stroke's "note" in marks.json (and marks_audio/<id>.txt).
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
        if not os.path.isfile(os.path.join(d, "site.json")):
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


handler = functools.partial(Handler, directory=root)
httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(os.path.join(cert, "cert.pem"), os.path.join(cert, "key.pem"))
httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
print(f"https://0.0.0.0:{port}/", flush=True)
httpd.serve_forever()
