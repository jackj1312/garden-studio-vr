"""The local Quest can load the published house and edit its garden layout."""
import ipaddress
import json
import os
import posixpath
import re
import stat
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

SITE = "house-wip"
SITE_DIR = "assets/sites/" + SITE
PAGES = {"garden/index.html", "house.html", "planner.html", "plan/index.html", "w/index.html"}
GARDEN_NORMALS = {
    "brushed_concrete", "grass_ground", "red_brick", "weathered_plank_siding", "wood_floor_deck",
}
NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
SOURCE = re.compile(r"src/(?:[\w-]+/)*[\w.-]+\.(?:js|mjs|css)")
THREE = re.compile(r"assets/vendor/three/(?:[\w.-]+/)*[\w.-]+\.(?:js|wasm)")
SKIES = {"assets/hdri/sky_midday_2k.jpg", "assets/hdri/sky_midday_4k.jpg",
         "assets/hdri/kloofendal_43d_clear_puresky_2k.exr"}
FLOOR_TEXTURES = {"tools/library/kit/maps/"+n for n in ("oak_wood_planks_diff_2k.jpg", "Marble019_1K-JPG_Color.jpg", "knitted_fleece_diff_1k.jpg")}
SAFE_SPEC = {"assets/sites/house/spec/spec_v1.json", "assets/sites/house/spec/catalogue_v1.json",
             "assets/planner/house/doors.json", SITE_DIR + "/spec/spec_v1.json", SITE_DIR + "/spec/catalogue_v1.json"}
METADATA = {SITE_DIR + "/" + n for n in ("versions.json", "regs.json", "regs_map.json", "materials.json")}


def public_file(root, relative):
    """Open a regular file beneath the root. Pin each ancestor to close symlink races."""
    parts = relative.split("/")
    if not all(p and not p.startswith(".") and "\\" not in p and "\x00" not in p for p in parts):
        raise FileNotFoundError
    fd = os.open(root, os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            os.close(file_fd)
            raise FileNotFoundError
        return os.fdopen(file_fd, "rb")
    finally:
        os.close(fd)


def garden_handler(base, project, address):
    root = Path(project).resolve()
    ip = ipaddress.ip_address(address)
    if ip.is_unspecified or not ip.is_private:
        raise ValueError("Choose the local Wi-Fi address or loopback")
    hosts = {str(ip), "localhost", "127.0.0.1", "::1"}

    @lru_cache(maxsize=4)
    def registry(path, signature):
        with public_file(root, path) as f:
            raw = f.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("oversized registry")
            data = json.loads(raw)
        if path == SITE_DIR + "/versions.json":
            versions, files, elements = set(), set(), set()
            release_id = data.get("furnish_release", "")
            if isinstance(release_id,str) and re.fullmatch(r"[0-9a-f]{20}",release_id):
                files.update(f"{SITE_DIR}/releases/{release_id}/spec/{name}" for name in ("spec_v1.json","catalogue_v1.json"))
            for item in data["versions"]:
                version = item["id"]
                if not isinstance(version, str) or not NAME.fullmatch(version):
                    continue
                versions.add(version)
                for field, suffix in (("glb", ".glb"), ("glb_quest", "_quest.glb"),
                                      ("glb_quest_meshopt", "_quest_mo.glb"), ("stages", ".json"),
                                      ("elements", "_elements.json")):
                    filename = item.get(field)
                    if filename == version + suffix:
                        files.add(SITE_DIR + "/" + filename)
                        if field == "elements":
                            elements.add(filename)
                # Only named outputs of this published version. Asset documents
                # refer to content-addressed sibling buffers and textures.
                release=r"(?:releases/[0-9a-f]{20}/)?"
                for field,suffix in (("glb",".glb"),("glb_quest","_quest.glb"),("glb_quest_meshopt","_quest_mo.glb"),("elements","_elements.json"),("stages",".json")):
                    name=item.get(field,"")
                    forms=[re.escape(version+suffix)]
                    if field in ("glb","glb_quest","glb_quest_meshopt"):
                        forms.append("furnish/"+version+"/fixed"+re.escape(suffix))
                    if re.fullmatch(release+"(?:"+"|".join(forms)+")",name):
                        files.add(SITE_DIR+"/"+name);files.add(SITE_DIR+"/"+version+suffix) if field in ("elements","stages") else None
                        if field=="elements":elements.add(version+suffix)
                runtime=item.get("furnish_runtime",{})
                for field in ("seed","variants"):
                    name=runtime.get(field,"")
                    if not re.fullmatch(release+"furnish/"+version+"/"+field+r"\.json",name):continue
                    files.update([SITE_DIR+"/"+name,SITE_DIR+"/furnish/"+version+"/"+field+".json"])
                    if field!="variants":continue
                    with public_file(root,SITE_DIR+"/"+name) as vfile: records=json.load(vfile).get("variants",{})
                    for record in records.values():
                        for key in ("url","questUrl"):
                            uri=record.get(key,"")
                            if not re.fullmatch(r"furnish/models/[a-f0-9]{64}\.gltf",uri):continue
                            files.add(SITE_DIR+"/"+uri)
                            with public_file(root,SITE_DIR+"/"+uri) as mfile:gltf=json.load(mfile)
                            for resource in gltf.get("buffers",[])+gltf.get("images",[]):
                                dep=resource.get("uri","")
                                if re.fullmatch(r"\.\./(?:buffers/[a-f0-9]{64}\.bin|textures/[a-f0-9]{64}\.(?:jpg|png|webp|ktx2))",dep):
                                    files.add(SITE_DIR+"/"+posixpath.normpath(posixpath.join(posixpath.dirname(uri),dep)))
            return versions, files, elements
        if path == "tools/library/kit/materials.json":
            # The exporter may repack a reviewed roughness JPEG as a PNG. Its
            # image name stays bound to the source map in the material manifest.
            return {"tools/library/kit/textures/" + Path(raw).stem + ext
                    for material in data["materials"].values()
                    for raw in material.get("maps", {}).values()
                    if re.fullmatch(r"maps/[\w.-]+\.(?:jpg|png)", raw)
                    for ext in (".jpg", ".png")}
        # Item pictures, meshes and buffers are named by the catalogue itself.
        files = {"tools/library/kit/catalogue.json"}
        for item in data["items"]:
            for key, pattern in (("thumbnail", r"thumbs/[\w.-]+\.png"), ("model", r"models/[\w.-]+\.(?:gltf|glb)")):
                name = item.get(key, "")
                if re.fullmatch(pattern, name) and not name.split("/")[-1].startswith("."):
                    files.add("tools/library/kit/" + name)
                    if name.endswith(".gltf"):
                        files.add("tools/library/kit/" + name[:-5] + ".bin")
        return files

    def registered(path):
        with public_file(root, path) as f:
            info = os.fstat(f.fileno())
        return registry(path, (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size))

    def static_resource(path):
        rel = path[1:]
        if rel in {"garden/", "w/", "plan/"}:
            rel += "index.html"
        if rel in PAGES | METADATA | SAFE_SPEC | SKIES or SOURCE.fullmatch(rel) or THREE.fullmatch(rel):
            return rel
        if rel in {"assets/textures/" + s + "/normal.jpg" for s in GARDEN_NORMALS}:
            return rel
        if rel.startswith(("assets/sites/house/", SITE_DIR + "/")):
            _, published, elements = registered(SITE_DIR + "/versions.json")
            if rel in published:
                return rel
            # The existing planner uses the canonical house URL. Use the published
            # element table, never the unpublished version in the generator site.
            name = rel.removeprefix("assets/sites/house/")
            if name in elements:
                return SITE_DIR + "/" + name
        if rel.startswith("tools/library/kit/textures/"):
            return rel if rel in registered("tools/library/kit/materials.json") else None
        if rel.startswith("tools/library/kit/") and rel in registered("tools/library/kit/catalogue.json"):
            return rel
        return None

    class GardenNetwork(base):
        def route(self):
            try:
                host = self.headers.get("Host", "")
                authority = urlsplit("//" + host)
                if (not host or authority.hostname not in hosts or authority.username is not None
                        or authority.password is not None or authority.path or authority.query or authority.fragment):
                    return None
                _ = authority.port  # Reject malformed authority ports.
                origin = self.headers.get("Origin")
                if origin is not None and origin != "https://" + host:
                    return None
                target = urlsplit(self.path)
                path = unquote(target.path, errors="strict")
                if (target.scheme or target.netloc or not path.startswith("/") or path.startswith("//")
                        or "\\" in path or "\x00" in path or any(p.startswith(".") for p in path.split("/"))):
                    return None
                if path=="/spec/changes":
                    q=parse_qs(target.query,keep_blank_values=True,max_num_fields=3)
                    return path if (self.command in ("GET","POST") and q=={"site":["house"],"view":["planner"]}) else None
                if path == "/layout":
                    q = parse_qs(target.query, keep_blank_values=True, max_num_fields=4)
                    if (self.command not in ("GET", "POST") or set(q) != {"site", "version"}
                            or q["site"] != [SITE] or len(q["version"]) != 1):
                        return None
                    versions, _, _ = registered(SITE_DIR + "/versions.json")
                    return "/layout" if q["version"][0] in versions else None
                if self.command not in ("GET", "HEAD"):
                    return None
                return static_resource(path)
            except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError):
                return None

        def allowed(self):
            route = self.route()
            if route in ("/layout","/spec/changes"):
                return True
            if route is None:
                return False
            try:
                with public_file(root, route):
                    return True
            except OSError:
                return False

        def _json(self, code, obj):
            if self.route()=="/spec/changes" and isinstance(obj,dict) and "changes" in obj:
                # The LAN client can reconstruct geometry and materials without receiving
                # free-text notes or build-report filenames from other review workflows.
                safe=[]
                for row in obj["changes"]:
                    if not isinstance(row,dict) or "note" in str(row.get("op","")).lower():continue
                    record={k:row[k] for k in ("id","version","room","op","target","before","after","status","created") if k in row}
                    for k in ("before","after","target"):
                        if isinstance(record.get(k),dict):
                            record[k]={key:v for key,v in record[k].items() if key not in ("note","audio","author","photo","photos")}
                    record["summary"]=str(record.get("op","Edit"))+" · "+str(record.get("room") or "Room")
                    safe.append(record)
                obj={"site":obj.get("site","house"),"changes":safe,"batches":[]}
            return super()._json(code,obj)

        def list_directory(self, path):
            self.send_error(404)
            return None

        def send_head(self):
            route = self.route()
            if route is None or route == "/layout":
                self.send_error(404)
                return None
            try:
                f = public_file(root, route)
            except OSError:
                self.send_error(404)
                return None
            try:
                info = os.fstat(f.fileno())
                self.send_response(200)
                self.send_header("Content-Type", self.guess_type(route))
                self.send_header("Content-Length", str(info.st_size))
                self.send_header("Last-Modified", self.date_time_string(info.st_mtime))
                self.end_headers()
            except BaseException:
                f.close()
                raise
            return f

        def do_GET(self):
            if self.allowed():
                return super().do_GET()
            self.send_error(404)

        def do_HEAD(self):
            if self.allowed():
                return super().do_HEAD()
            self.send_error(404)

        def do_POST(self):
            if self.route() in ("/layout","/spec/changes"):
                return super().do_POST()
            self.send_error(404)

    return GardenNetwork
