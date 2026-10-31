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
<p>Straight over your wifi. Nothing is uploaded to the internet. Keep this page open; if it drops, press Send again and it carries on.</p>
<label for="f" id="drop">Choose photos and videos</label>
<input id="f" type="file" accept="video/*,image/*" multiple>
<div id="bar"><div id="fill"></div></div>
<div id="msg"></div>
<button id="go" disabled>Send</button>
<script>
const f=document.getElementById('f'),go=document.getElementById('go'),
      bar=document.getElementById('bar'),fill=document.getElementById('fill'),
      msg=document.getElementById('msg'),drop=document.getElementById('drop');
let files=[];
f.onchange=()=>{files=[...f.files];if(!files.length)return;
  const mb=files.reduce((a,b)=>a+b.size,0)/1048576;
  drop.textContent=files.length+' file'+(files.length>1?'s':'')+'  ('+mb.toFixed(0)+' MB)';
  go.disabled=false;msg.textContent='';};
const CH=8*1048576;
let lock=null;
async function keepAwake(){ try{ lock=await navigator.wakeLock.request('screen'); }catch(e){} }
document.addEventListener('visibilitychange',()=>{ if(document.visibilityState==='visible'&&go.disabled) keepAwake(); });
async function have(name,size){
  try{ const r=await fetch('/status?name='+encodeURIComponent(name)+'&total='+size); return parseInt(await r.text())||0; }catch(e){ return 0; }
}
function putSlice(file,off,i){
  return new Promise(res=>{
    const x=new XMLHttpRequest(), t0=Date.now(), end=Math.min(file.size,off+CH);
    x.open('PUT','/upload?name='+encodeURIComponent(file.name)+'&offset='+off+'&total='+file.size);
    x.upload.onprogress=e=>{
      const done=off+e.loaded; fill.style.width=(done/file.size*100)+'%';
      msg.textContent=(i+1)+' of '+files.length+'   '+file.name+'   '+(done/1048576).toFixed(0)+' / '+(file.size/1048576).toFixed(0)+' MB';
    };
    x.onload=()=>res(x.status===200);
    x.onerror=()=>res(false); x.ontimeout=()=>res(false); x.timeout=120000;
    x.send(file.slice(off,end));
  });
}
async function sendOne(file,i){
  let off=await have(file.name,file.size), fails=0;
  while(off<file.size){
    const ok=await putSlice(file,off,i);
    if(ok){ off=Math.min(file.size,off+CH); fails=0; }
    else{
      fails++; if(fails>30) return false;
      msg.textContent='Connection dropped, retrying… ('+fails+')';
      await new Promise(r=>setTimeout(r,2000+fails*500));
      off=await have(file.name,file.size);           // carry on from what actually arrived
    }
  }
  return true;
}
go.onclick=async()=>{
  if(!files.length)return;
  keepAwake();
  go.disabled=true;bar.style.display='block';
  let ok=0,bad=[];
  for(let i=0;i<files.length;i++){ if(await sendOne(files[i],i))ok++; else bad.push(files[i].name); }
  msg.textContent='Done: '+ok+' of '+files.length+' sent.'+(bad.length?' Failed: '+bad.join(', '):'');
  go.disabled=false;files=[];f.value='';drop.textContent='Choose photos and videos';
};
</script>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        sys.stderr.write("  %s\n" % (fmt % a))

    def do_GET(self):
        if self.path.startswith("/status"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            name = os.path.basename(q.get("name", [""])[0]); total = q.get("total", ["0"])[0]
            part = self.part_path(name, total)
            body = str(os.path.getsize(part) if os.path.exists(part) else 0).encode()
            self.send_response(200); self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            return
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # the viewer on another port can post stills here (judges, captures)
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def part_path(self, name, total):
        return os.path.join(DEST, f".{name}.{total}.part")

    def do_PUT(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        name = os.path.basename(q.get("name", ["upload.mov"])[0]) or "upload.mov"
        length = int(self.headers.get("Content-Length", 0))
        if "offset" not in q:                        # old single-request upload
            q["offset"], q["total"] = ["0"], [str(length)]
        offset, total = int(q["offset"][0]), int(q["total"][0])
        part = self.part_path(name, total)
        have = os.path.getsize(part) if os.path.exists(part) else 0
        if offset != have:                           # out of step: tell the client where we are
            self.send_response(409); self.send_header("Content-Length", "0")
            self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
            self.rfile.read(length)
            return
        got = 0
        with open(part, "ab") as fh:
            while got < length:
                chunk = self.rfile.read(min(CHUNK, length - got))
                if not chunk:
                    break
                fh.write(chunk); got += len(chunk)
        if got < length:                             # dropped mid-slice: keep only whole slices
            with open(part, "r+b") as fh: fh.truncate(offset)
        ok = got == length
        path = None
        if ok and offset + got == total:
            path = os.path.join(DEST, name); n = 1
            while os.path.exists(path):
                stem, ext = os.path.splitext(name); path = os.path.join(DEST, f"{stem}-{n}{ext}"); n += 1
            os.rename(part, path)
            print(f"received: {path}  {total/1048576:.0f} MB", flush=True)
        reply = (os.path.basename(path) if path else "ok").encode() if ok else b"incomplete"
        self.send_response(200 if ok else 500)
        self.send_header("Access-Control-Allow-Origin", "*")
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
