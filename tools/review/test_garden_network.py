"""Exercise actual SimpleHTTP GET/HEAD dispatch in memory, without starting a service."""
import io
import json
import sys
import tempfile
import unittest
from email.message import Message
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from garden_network import garden_handler


class MemoryHTTP(SimpleHTTPRequestHandler):
    def __init__(self, method, path, host, origin):
        self.command = method
        self.path = path
        self.headers = Message()
        self.headers["Host"] = host
        if origin is not None:
            self.headers["Origin"] = origin
        self.wfile = io.BytesIO()
        self.status = 0
        self.response_headers = {}

    def send_response(self, code, message=None):
        self.status = code

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass

    def send_error(self, code, *args):
        self.status = code

    def do_GET(self):
        if urlsplit(self.path).path == "/layout":
            self.send_response(200)
            self.wfile.write(b"LAYOUT READ")
        else:
            super().do_GET()

    def do_POST(self):
        self.send_response(200)
        self.wfile.write(b"LAYOUT WRITE")


class GardenNetworkTests(unittest.TestCase):
    address = "192.168.1.118"
    host = address + ":8450"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.server = garden_handler(MemoryHTTP, self.root, self.address)
        self.site = "assets/sites/house-wip/"
        self.write(self.site + "versions.json", json.dumps({"versions": [{
            "id": "approved_2b", "glb": "approved_2b.glb", "glb_quest": "approved_2b_quest.glb",
            "glb_quest_meshopt": "approved_2b_quest_mo.glb",
            "elements": "approved_2b_elements.json", "stages": "approved_2b.json"}]}).encode())
        self.write(self.site + "approved_2b.glb", b"published model")
        self.write(self.site + "approved_2b_quest_mo.glb", b"published mobile model")
        self.write(self.site + "approved_2b_elements.json", b"published elements")
        self.write("assets/sites/house/approved_2b_elements.json", b"private candidate")
        self.write("src/garden/editor.js", b"viewer source")
        self.write("garden/index.html", b"garden page")
        self.write("layout", b"STATIC FILE MUST NOT REPLACE API")
        self.private = self.root / "drawings/plan.pdf"
        self.write("drawings/plan.pdf", b"private drawing")

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def request(self, method, path, host=None, origin=None):
        handler = self.server(method, path, self.host if host is None else host, origin)
        getattr(handler, "do_" + method)()
        return handler

    def deny(self, path, method="GET", **headers):
        response = self.request(method, path, **headers)
        self.assertEqual(response.status, 404, (method, path, headers))
        self.assertEqual(response.wfile.getvalue(), b"")

    def test_layout_methods_site_version_origin(self):
        url = "/layout?site=house-wip&version=approved_2b"
        for method, body in (("GET", b"LAYOUT READ"), ("POST", b"LAYOUT WRITE")):
            result = self.request(method, url, origin="https://" + self.host)
            self.assertEqual((result.status, result.wfile.getvalue()), (200, body))
            for query in ["site=house&version=approved_2b", "site=house-wip&version=unlisted",
                          "site=house-wip", "site=house-wip&site=house&version=approved_2b"]:
                self.deny("/layout?" + query, method)
            self.deny(url, method, origin="https://attacker.invalid")
            self.deny(url, method, origin="null")
            self.deny(url, method, host="attacker.invalid")
        self.deny(url, "HEAD")  # Must not read the static file named "layout".

    def test_only_manifest_model_and_published_planner_table_are_served(self):
        for path, body in [("/garden/", b"garden page"), ("/src/garden/editor.js?v=7", b"viewer source"),
                           ("/" + self.site + "approved_2b.glb", b"published model"),
                           ("/" + self.site + "approved_2b_quest_mo.glb", b"published mobile model"),
                           ("/assets/sites/house/approved_2b_elements.json", b"published elements")]:
            for method in ("GET", "HEAD"):
                result = self.request(method, path)
                self.assertEqual(result.status, 200, path)
                self.assertEqual(result.wfile.getvalue(), body if method == "GET" else b"")
                self.assertEqual(int(result.response_headers["Content-Length"]), len(body))
        for name in ["private_scan.glb", "private_elements.json", "approved_2b.previous.json", "marks.json"]:
            self.write(self.site + name, b"must not be served")
            for method in ("GET", "HEAD", "POST"):
                self.deny("/" + self.site + name, method)
        self.deny("/src/garden/editor.js", "POST")
        self.deny("/src/garden/editor.js", origin="https://attacker.invalid")

    def test_active_immutable_release_only_serves_its_signed_planner_files(self):
        active = "0123456789abcdef0123"
        previous = "a123456789abcdef0123"
        release = self.site + "releases/" + active + "/"
        previous_release = self.site + "releases/" + previous + "/"
        elements = "approved_2b_elements.json"
        manifest = {"furnish_release":active, "versions":[{"id":"approved_2b",
                    "elements":"releases/" + active + "/" + elements}]}
        self.write(self.site + "versions.json", json.dumps(manifest).encode())
        files = {"spec/spec_v1.json":b"signed room geometry", "spec/catalogue_v1.json":b"signed finishes",
                 elements:b"released elements"}
        for name,body in files.items():
            self.write(release+name, body)
            self.write(previous_release+name, b"retired release")
            for method in ("GET","HEAD"):
                result = self.request(method, "/"+release+name)
                self.assertEqual((result.status,int(result.response_headers["Content-Length"])), (200,len(body)))
                self.assertEqual(result.wfile.getvalue(),body if method=="GET" else b"")
                self.deny("/"+previous_release+name, method)
            self.deny("/"+release+name, "POST")
        for name in ["spec/spec_v1_addendum2_details.json","spec/finish_interfaces.json","spec/changes/changes.json",
                     "spec/marks_audio/note.webm","spec/photos/reference.jpg","spec/drawings/plan.pdf",
                     "spec/spec_v1.previous.json","as_built_now_elements.json","spec/SIGNOFF.md"]:
            self.write(release+name,b"private source")
            for method in ("GET","HEAD","POST"):
                self.deny("/"+release+name,method)
        self.deny("/"+release+"spec/%2e%2e/review/findings.json")
        self.deny("/"+release+"spec/")
        signed = self.root/release/"spec/spec_v1.json"
        signed.unlink()
        signed.symlink_to(self.private)
        self.deny("/"+release+"spec/spec_v1.json")
        self.deny("/"+release+"spec/spec_v1.json","HEAD")

    def test_deny_private_paths_direct_layout_history_and_encoded_traversal(self):
        for path in ["/drawings/plan.pdf", "/.git/config", "/assets/sites/house-wip/review/findings.json",
                     "/assets/sites/house-wip/marks_audio/voice.webm", "/assets/sites/house-wip/refs.json",
                     "/assets/sites/house-wip/layout/approved_2b.json", "/assets/sites/house-wip/layout/approved_2b.previous.json",
                     "/assets/sites/house-wip/layout/changes/approved_2b/000000001.json",
                     "/src/garden/%2e%2e/%2e%2e/drawings/plan.pdf", "/src/garden/%252e%252e/x.js",
                     "/src/garden/%5cprivate.js", "/src/%00x.js", "/%2fdrawings/plan.pdf",
                     "//attacker.invalid/src/garden/editor.js", "/marks?site=house-wip",
                     "/marks/audio?site=house-wip&id=1", "/spec/changes?site=house", "/house/requests?site=house-wip"]:
            for method in ("GET", "HEAD", "POST"):
                self.deny(path, method)

    def test_directory_pages_and_file_symlinks_cannot_alias_private_files(self):
        # Private paths inside the repository are as sensitive as paths outside it.
        (self.root / "src/garden/alias.js").symlink_to(self.private)
        outside = Path(self.temp.name) / "external.js"
        outside.write_text("outside")
        (self.root / "src/escape.js").symlink_to(outside)
        (self.root / "src/garden/hidden").symlink_to(self.root / "drawings", target_is_directory=True)
        self.write("drawings/record.js", b"private")
        (self.root / "garden/index.html").unlink()
        (self.root / "garden/index.html").symlink_to(self.private)
        for path in ["/src/garden/alias.js", "/src/escape.js", "/src/garden/hidden/record.js",
                     "/garden/", "/garden/index.html", "/src/", "/src/garden/", "/assets/sites/house-wip/"]:
            for method in ("GET", "HEAD"):
                self.deny(path, method)

    def test_only_named_garden_maps_and_catalogue_assets_are_exposed(self):
        self.write("assets/textures/wood_floor_deck/normal.jpg", b"reviewed normal")
        self.write("assets/textures/wood_floor_deck/private_photo.jpg", b"private")
        self.write("tools/library/kit/catalogue.json", b'{"items":[{"model":"models/modern.sofa.gltf","thumbnail":"thumbs/modern.sofa.png"}]}')
        self.write("tools/library/kit/materials.json", b'{"materials":{"oak":{"maps":{"colour":"maps/oak_scan.jpg"}}}}')
        for rel in ["models/modern.sofa.gltf", "models/modern.sofa.bin", "thumbs/modern.sofa.png", "textures/oak_scan.jpg"]:
            self.write("tools/library/kit/" + rel, b"asset")
            self.assertEqual(self.request("GET", "/tools/library/kit/" + rel).wfile.getvalue(), b"asset")
        self.assertEqual(self.request("GET", "/assets/textures/wood_floor_deck/normal.jpg").wfile.getvalue(), b"reviewed normal")
        for path in ["/assets/textures/wood_floor_deck/private_photo.jpg", "/tools/library/kit/thumbs/private_photo.png",
                     "/tools/library/kit/models/private.glb", "/tools/library/kit/textures/private_photo.jpg"]:
            self.write(path.lstrip("/"), b"private")
            self.deny(path)

    def test_unspecified_or_public_binding_refused(self):
        for address in ["0.0.0.0", "::", "8.8.8.8"]:
            with self.assertRaises(ValueError):
                garden_handler(MemoryHTTP, self.root, address)


if __name__ == "__main__":
    unittest.main()
