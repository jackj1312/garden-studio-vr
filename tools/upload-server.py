#!/usr/bin/env python3
"""A drop box on the local network, for getting video off a phone.

Phone and Mac on the same wifi; the file goes straight between them and
never touches a cloud service. Streams the body to disk in chunks rather
than buffering, because a gigabyte will not fit comfortably in 8 GB of
RAM alongside everything else running.

    python3 tools/upload-server.py [port]

Stop it with ctrl-c, or by killing the process. It is open to anything on
your local network while it runs, so do not leave it up.
"""
import http.server, socket, socketserver, os, sys, time, urllib.parse

DEST = os.path.expanduser("~/Desktop/garden-scans")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
CHUNK = 1024 * 1024

os.makedirs(DEST, exist_ok=True)

PAGE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Send a scan</title>
<style>
  :root{color-scheme:dark}
  body{margin:0;min-height:100dvh;display:flex;flex-direction:column;justify-content:center;
       gap:22px;padding:28px;background:#15171a;color:#eceae3;
       font:16px/1.5 -apple-system,BlinkMacSystemFont,system-ui,sans-serif}
  h1{font-size:21px;margin:0;font-weight:600;letter-spacing:-.01em}
  p{margin:0;color:#9ea39a;font-size:14px}
  label{display:block;padding:26px;border:1.5px dashed #3c4147;border-radius:14px;
        text-align:center;color:#c6c9c2}
  input[type=file]{display:none}
  button{font:inherit;font-weight:600;padding:15px;border:0;border-radius:11px;
         background:#7aa86a;color:#10140e;width:100%}
  button:disabled{opacity:.45}
  #bar{height:7px;background:#272b30;border-radius:4px;overflow:hidden;display:none}
  #fill{height:100%;width:0;background:#7aa86a;transition:width .15s}
  #msg{font-size:14px;color:#9ea39a;min-height:20px}
</style>
<h1>Send a scan to the Mac</h1>
<p>Straight over your wifi. Nothing is uploaded to the internet.</p>
<label for="f" id="drop">Choose a video</label>
<input id="f" type="file" accept="video/*,image/*">
<div id="bar"><div id="fill"></div></div>
<div id="msg"></div>
<button id="go" disabled>Send</button>
<script>
const f=document.getElementById('f'),go=document.getElementById('go'),
      bar=document.getElementById('bar'),fill=document.getElementById('fill'),
      msg=document.getElementById('msg'),drop=document.getElementById('drop');
let file=null;
f.onchange=()=>{file=f.files[0];if(!file)return;
  drop.textContent=file.name+'  ('+(file.size/1048576).toFixed(0)+' MB)';
  go.disabled=false;msg.textContent='';};
go.onclick=()=>{
  if(!file)return;
  go.disabled=true;bar.style.display='block';
  const t0=Date.now();
  const x=new XMLHttpRequest();
  x.open('PUT','/upload?name='+encodeURIComponent(file.name));
  x.upload.onprogress=e=>{
    if(!e.lengthComputable)return;
    const pct=e.loaded/e.total;
    fill.style.width=(pct*100)+'%';
    const mb=(e.loaded/1048576).toFixed(0), tot=(e.total/1048576).toFixed(0);
    const rate=e.loaded/1048576/((Date.now()-t0)/1000);
    msg.textContent=mb+' / '+tot+' MB   '+rate.toFixed(1)+' MB/s';
  };
  x.onload=()=>{msg.textContent=x.status===200?'Done. '+x.responseText:'Failed: '+x.status;
                go.disabled=false;};
  x.onerror=()=>{msg.textContent='Connection lost.';go.disabled=false;};
  x.send(file);
};
</script>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        sys.stderr.write("  %s\n" % (fmt % a))

    def do_GET(self):
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = os.path.basename(q.get("name", ["upload.mov"])[0]) or "upload.mov"
        path = os.path.join(DEST, name)
        n = 1
        while os.path.exists(path):
            stem, ext = os.path.splitext(name)
            path = os.path.join(DEST, f"{stem}-{n}{ext}")
            n += 1

        total = int(self.headers.get("Content-Length", 0))
        got, t0 = 0, time.time()
        with open(path, "wb") as fh:
            while got < total:
                chunk = self.rfile.read(min(CHUNK, total - got))
                if not chunk:
                    break
                fh.write(chunk)
                got += len(chunk)

        ok = got == total
        secs = max(time.time() - t0, 0.001)
        print(f"{'received' if ok else 'INCOMPLETE'}: {path}  "
              f"{got/1048576:.0f} MB in {secs:.0f}s ({got/1048576/secs:.1f} MB/s)", flush=True)
        reply = (os.path.basename(path) if ok else "incomplete").encode()
        self.send_response(200 if ok else 500)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))       # no packets sent; just picks the route
        return s.getsockname()[0]
    finally:
        s.close()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    ip = lan_ip()
    print(f"drop box running — open this on your phone:\n\n    http://{ip}:{PORT}\n")
    print(f"saving to {DEST}\nctrl-c to stop", flush=True)
    Server(("0.0.0.0", PORT), Handler).serve_forever()
