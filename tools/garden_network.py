"""Small, explicit LAN surface for the Quest. Private drawings, marks, scans and voice files stay local."""
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs
import ipaddress
import re


def garden_handler(base, project, address):
    root = Path(project).resolve()
    ip = ipaddress.ip_address(address)
    if ip.is_unspecified or not ip.is_private:
        raise ValueError("Choose the local Wi-Fi address or loopback")
    pages = {"/garden/", "/garden/index.html", "/house.html", "/planner.html", "/plan/", "/plan/index.html", "/w/", "/w/index.html"}
    static = (
        r"/src/(?:[\w-]+/)*[\w.-]+\.(?:js|mjs|css|json)",
        r"/assets/vendor/three/(?:[\w.-]+/)*[\w.-]+\.(?:js|wasm)",
        r"/assets/hdri/(?:sky_midday_[24]k\.jpg|kloofendal_43d_clear_puresky_2k\.exr)",
        r"/assets/sites/house-wip/(?:versions|regs|regs_map|materials|[a-z0-9_]+_elements|approved_2b|as_built_now|existing_2022|single_storey_option)\.json",
        r"/assets/sites/house-wip/[a-z0-9_]+\.glb",
        r"/assets/sites/house/spec/spec_v[0-9]+\.json",
        r"/assets/planner/house/doors\.json",
        r"/tools/library/kit/(?:catalogue\.json|(?:models|thumbs)/[a-zA-Z0-9_.-]+\.(?:png|glb))",
    )

    class GardenNetwork(base):
        def allowed(self):
            target = urlsplit(self.path)
            path = unquote(target.path)
            if target.netloc or ".." in path.split("/") or "\\" in path or "\x00" in path:
                return False
            if self.headers.get("Host", "").split(":")[0] not in {address, "localhost", "127.0.0.1"}:
                return False
            origin = self.headers.get("Origin")
            if origin and origin != "https://" + self.headers["Host"]:
                return False
            if path == "/layout":
                return parse_qs(target.query).get("site") == ["house-wip"]
            if self.command not in ("GET", "HEAD"):
                return False
            if path not in pages and not any(re.fullmatch(pattern, path) for pattern in static):
                return False
            requested = root / path.lstrip("/")
            return requested.resolve().is_relative_to(root) and not any(part.startswith(".") for part in requested.relative_to(root).parts)

        def list_directory(self, path):
            self.send_error(404)
            return None

        def do_GET(self):
            if self.allowed():
                return super().do_GET()
            self.send_error(404)

        def do_HEAD(self):
            if self.allowed():
                return super().do_HEAD()
            self.send_error(404)

        def do_POST(self):
            if self.allowed():
                return super().do_POST()
            self.send_error(404)

    return GardenNetwork

