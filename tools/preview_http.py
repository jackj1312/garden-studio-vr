"""Read-only, inventory-limited preview packages on the studio's dedicated HTTPS port."""
import json
from functools import lru_cache
from pathlib import Path
import re
import shutil
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

from garden_network import public_file

KEY = re.compile(r"[0-9a-f]{20}")
VERSION = re.compile(r"[a-zA-Z0-9_-]{1,64}")


def preview_handler(base, directory, address):
    directory=Path(directory)
    hosts={address,"localhost","127.0.0.1","::1"}

    def load_json(relative,limit):
        with public_file(directory,relative) as f:
            data=f.read(limit+1)
        if len(data)>limit:raise ValueError("Preview registry too large")
        return json.loads(data)

    @lru_cache(maxsize=8)
    def inventory(key):
        record=load_json(key+"/files.json",5*1024*1024)
        if record.get("schema")!=1 or not isinstance(record.get("files"),dict):
            raise ValueError("Invalid preview inventory")
        return record["files"]

    class Preview(base):
        def preview_path(self):
            raw=urlsplit(self.path).path
            return raw=="/preview" or raw.startswith("/preview/")

        def read_preview(self,head):
            try:
                target=urlsplit(self.path);authority=urlsplit("//"+self.headers.get("Host",""))
                if (authority.hostname not in hosts or authority.username is not None or authority.password is not None
                        or authority.path or authority.fragment or authority.query or target.scheme or target.netloc):
                    raise ValueError("Invalid authority")
                _=authority.port
                if self.headers.get("Origin") not in (None,"https://"+self.headers.get("Host","")):
                    raise ValueError("Foreign origin")
                name=unquote(target.path,errors="strict").removeprefix("/preview").strip("/")
                if any(p.startswith(".") or "\\" in p or "%" in p or "\x00" in p for p in name.split("/")):
                    raise ValueError("Invalid preview path")
                if not name:
                    current=load_json("current.json",65536);key=current["key"]
                    if not isinstance(key,str) or not KEY.fullmatch(key):raise ValueError("Invalid preview")
                    q=parse_qs(target.query,max_num_fields=5)
                    version=q.get("version",[None])[0]
                    if version and (not VERSION.fullmatch(version) or version not in current.get("versions",[])):
                        raise ValueError("Invalid version")
                    values={"site":"house-preview","mode":"customer"}
                    if version:values["version"]=version
                    self.send_response(302)
                    self.send_header("Location","/preview/"+key+"/house.html?"+urlencode(values))
                    self.send_header("Cache-Control","no-store");self.send_header("Content-Length","0");self.end_headers()
                    return
                key,sep,relative=name.partition("/")
                if not KEY.fullmatch(key) or not sep or not relative or relative not in inventory(key):raise FileNotFoundError
                with public_file(directory,key+"/"+relative) as file:
                    self.send_response(200);self.send_header("Content-Type",self.guess_type(relative))
                    self.send_header("Content-Length",str(file.seek(0,2)));file.seek(0)
                    self.send_header("Cache-Control","private, max-age=31536000, immutable")
                    self.send_header("X-Content-Type-Options","nosniff");self.send_header("Referrer-Policy","same-origin")
                    self.end_headers()
                    if not head:shutil.copyfileobj(file,self.wfile)
            except (BrokenPipeError,ConnectionResetError):return
            except (OSError,ValueError,KeyError,TypeError,UnicodeError):self.send_error(404)

        def do_HEAD(self):
            if self.preview_path():return self.read_preview(True)
            return super().do_HEAD()

        def do_GET(self):
            if self.preview_path():return self.read_preview(False)
            return super().do_GET()

        def do_POST(self):
            if self.preview_path():return self.send_error(405,"Preview is read-only")
            return super().do_POST()
    return Preview
