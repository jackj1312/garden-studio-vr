#!/usr/bin/env python3
"""Serve this folder over HTTPS on the home network, so the Quest can open a
private build (WebXR needs a secure origin). Self-signed: the headset shows a
warning once — Advanced, then Proceed. Nothing here is reachable from outside
the wifi.

    python3 tools/https-serve.py [port]       # default 8443

Marks drawn in the headset (src/marks.js):
    GET  /marks?site=<name>   -> assets/sites/<name>/marks.json (or an empty list)
    POST /marks?site=<name>   -> writes that one file, nothing else. The site must
                                 already exist (its site.json); the body is capped
                                 and rebuilt field by field before it is written.
"""
import http.server, ssl, os, sys, functools, json, re, math, urllib.parse
from datetime import datetime, timezone

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
root = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
cert = os.path.expanduser("~/.garden-vr-cert")

SITE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_BODY = 2 * 1024 * 1024            # a few thousand strokes of 5 cm points is well under this
MAX_STROKES, MAX_POINTS = 2000, 20000
KINDS = {"correction", "proposal"}
PAIR_RE = re.compile(r"\[\s+(-?[0-9.eE+-]+),\s+(-?[0-9.eE+-]+)\s+\]")


def _num(v, lim=100000.0):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > lim:
        raise ValueError("bad number")
    return v


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
        sid, kind, created = s.get("id"), s.get("kind"), s.get("created")
        if not isinstance(sid, str) or not ID_RE.match(sid) or kind not in KINDS:
            raise ValueError("bad id or kind")
        points = []
        for p in pts:
            if not isinstance(p, list) or len(p) != 2:
                raise ValueError("bad point")
            points.append([round(_num(p[0], 10000), 3), round(_num(p[1], 10000), 3)])
        area = s.get("area_m2")
        out.append({
            "id": sid,
            "kind": kind,
            "closed": bool(s.get("closed")),
            "points": points,
            "length_m": round(_num(s.get("length_m", 0)), 2),
            "area_m2": None if area is None else round(_num(area), 2),
            "created": created[:40] if isinstance(created, str) else None,
        })
    return out


class Handler(http.server.SimpleHTTPRequestHandler):
    def _marks_file(self):
        """None when the request is not for /marks; raises ValueError for a bad site."""
        u = urllib.parse.urlsplit(self.path)
        if u.path != "/marks":
            return None
        site = urllib.parse.parse_qs(u.query).get("site", [""])[0]
        if not SITE_RE.match(site):
            raise ValueError("bad site name")
        d = os.path.join(root, "assets", "sites", site)
        if not os.path.isfile(os.path.join(d, "site.json")):
            raise ValueError("unknown site")
        return site, os.path.join(d, "marks.json")

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
            t = self._marks_file()
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        if t is None:
            return super().do_GET()
        site, path = t
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                return self._json(200, json.load(f))
        return self._json(200, {"site": site, "updated": None, "strokes": []})

    def do_POST(self):
        try:
            t = self._marks_file()
            if t is None:
                return self._json(404, {"error": "not found"})
            site, path = t
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                return self._json(413, {"error": "body too large or empty"})
            body = json.loads(self.rfile.read(n).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("body must be an object")
            strokes = clean_strokes(body.get("strokes"))
        except (ValueError, TypeError, IndexError, UnicodeDecodeError) as e:
            return self._json(400, {"error": str(e)})
        out = {"site": site, "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "strokes": strokes}
        tmp = path + ".tmp"
        text = json.dumps(out, indent=2, ensure_ascii=False)
        text = PAIR_RE.sub(r"[\1, \2]", text)          # one [x, y] per line, not four
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        os.replace(tmp, path)
        self.log_message("marks: %d strokes -> %s", len(strokes), os.path.relpath(path, root))
        return self._json(200, {"ok": True, "count": len(strokes), "updated": out["updated"]})


handler = functools.partial(Handler, directory=root)
httpd = http.server.ThreadingHTTPServer(("0.0.0.0", port), handler)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(os.path.join(cert, "cert.pem"), os.path.join(cert, "key.pem"))
httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
print(f"https://0.0.0.0:{port}/", flush=True)
httpd.serve_forever()
