"""The capture server: serves the project folder to ONE local browser tab and receives the frames the sweep driver posts.

    python3 tools/review/capture_server.py 8780

Static files as `python3 -m http.server` would (127.0.0.1 only, no caching), plus
    POST /save   {"dir": "renders/house-build/first-build/round-1/sweep/<space>/<version>", "files": {"<name>.jpg": "<data URL>"}}
Frames are only ever written under renders/ (never anywhere else), as raw bytes, so a hidden browser tab can capture a whole
sweep without the images passing through the conversation. The headset server (tools/https-serve.py, port 8443) is separate
and untouched. A reusable tool: nothing here knows about 23 Battle Road."""
import base64, json, os, sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WRITE_UNDER = os.path.join(ROOT, "renders")


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".mjs": "text/javascript",
                      ".glb": "model/gltf-binary", ".json": "application/json", ".exr": "application/octet-stream", ".webp": "image/webp"}

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *a):          # quiet: a sweep posts thousands of frames
        if "--verbose" in sys.argv:
            super().log_message(fmt, *a)

    def do_POST(self):
        if self.path.split("?")[0] != "/save":
            self.send_error(404)
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            d = os.path.realpath(os.path.join(ROOT, body["dir"]))
            if not (d + os.sep).startswith(WRITE_UNDER + os.sep):
                raise ValueError("outside renders/")
            os.makedirs(d, exist_ok=True)
            n = 0
            for name, data in body["files"].items():
                if "/" in name or name.startswith("."):
                    raise ValueError("bad file name " + name)
                raw = base64.b64decode(data.split(",", 1)[1] if data.startswith("data:") else data)
                with open(os.path.join(d, name), "wb") as f:
                    f.write(raw)
                n += 1
            out = json.dumps({"saved": n}).encode()
            self.send_response(200)
        except Exception as ex:               # report to the page, never crash the server
            out = json.dumps({"error": str(ex)}).encode()
            self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


if __name__ == "__main__":
    port = int(next((a for a in sys.argv[1:] if a.isdigit()), "8780"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=ROOT))
    print(f"capture server on http://127.0.0.1:{port}/ (serving {ROOT}; writes only under renders/)", flush=True)
    srv.serve_forever()
