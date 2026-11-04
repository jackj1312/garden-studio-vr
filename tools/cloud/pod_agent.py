"""A tiny HTTP agent that runs inside a rented pod whose image has no SSH server (Epic's Unreal images): the pod's
start command writes this file from an env var and runs it with whatever python3 the image has. Standard library only.
Every request needs the header X-Token = $AGENT_TOKEN (a random value made per job); reached through RunPod's HTTPS
proxy (https://<pod>-8000.proxy.runpod.net), whose 100 s limit is why long commands run in the background.
    GET  /ping                     who/where: user, python, engine path, GPU, disk
    PUT  /upload?path=<file>       write the request body to a file
    POST /run                      body = a bash command; returns {"id"}; output goes to <work>/run-<id>.log
    GET  /status?id=<id>&tail=<n>  {"done", "code", "tail"}
    GET  /download?path=<file>     stream a file back"""
import http.server, json, os, shutil, subprocess, threading, urllib.parse, uuid

TOKEN = os.environ.get("AGENT_TOKEN", "")
WORK = os.environ.get("AGENT_WORK", "/tmp/job")
os.makedirs(WORK, exist_ok=True)
jobs = {}


def sh(cmd):
    try: return subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e: return f"error: {e}"


class Agent(http.server.BaseHTTPRequestHandler):
    def _ok(self):
        if not TOKEN or self.headers.get("X-Token") != TOKEN:
            self.send_response(403); self.end_headers(); return False
        return True

    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _q(self):
        u = urllib.parse.urlparse(self.path)
        return u.path, {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}

    def do_GET(self):
        if not self._ok(): return
        path, q = self._q()
        if path == "/ping":
            return self._json({"user": sh("whoami"), "home": os.path.expanduser("~"), "work": WORK,
                               "python": sh("command -v python3"), "sudo": sh("sudo -n true 2>&1 && echo yes || echo no"),
                               "engine": sh("ls -d /home/*/UnrealEngine /opt/*/UnrealEngine 2>/dev/null | head -1"),
                               "gpu": sh("nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader"),
                               "vulkan": sh("ls /usr/share/vulkan/icd.d /etc/vulkan/icd.d 2>/dev/null"),
                               "disk": sh(f"df -h {WORK} | tail -1")})
        if path == "/status":
            j = jobs.get(q.get("id"))
            if not j: return self._json({"error": "no such job"}, 404)
            tail = sh(f"tail -n {int(q.get('tail', 40))} {j['log']}")
            return self._json({"done": j["proc"].poll() is not None, "code": j["proc"].poll(), "tail": tail})
        if path == "/download":
            f = q.get("path", "")
            if not os.path.isfile(f): return self._json({"error": "no such file"}, 404)
            self.send_response(200); self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(os.path.getsize(f))); self.end_headers()
            with open(f, "rb") as fh: shutil.copyfileobj(fh, self.wfile, 1 << 20)
            return
        self._json({"error": "unknown"}, 404)

    def do_PUT(self):
        if not self._ok(): return
        path, q = self._q()
        f = q.get("path") or os.path.join(WORK, "upload.bin")
        os.makedirs(os.path.dirname(f), exist_ok=True)
        n = int(self.headers.get("Content-Length", 0)); left = n
        with open(f, "wb") as fh:
            while left > 0:
                chunk = self.rfile.read(min(left, 1 << 20))
                if not chunk: break
                fh.write(chunk); left -= len(chunk)
        self._json({"path": f, "bytes": n - left})

    def do_POST(self):
        if not self._ok(): return
        path, _ = self._q()
        if path != "/run": return self._json({"error": "unknown"}, 404)
        cmd = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        jid = uuid.uuid4().hex[:16]; log = os.path.join(WORK, f"run-{jid}.log")
        proc = subprocess.Popen(["bash", "-o", "pipefail", "-c", cmd], stdout=open(log, "w"), stderr=subprocess.STDOUT, cwd=WORK)
        jobs[jid] = {"proc": proc, "log": log}
        self._json({"id": jid, "log": log})

    def log_message(self, *a): pass


if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("AGENT_PORT", 8000))), Agent)
    print("pod agent listening", flush=True)
    srv.serve_forever()
