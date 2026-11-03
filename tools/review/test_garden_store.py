"""Local persistence regressions. Run with python3 -B tools/review/test_garden_store.py."""
import concurrent.futures
import io
import json
import sys
import tempfile
import threading
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import layout_store
from layout_store import LayoutError, LayoutStore


def patio(name="patio-1"):
    return {"id": name, "kind": "patio", "label": "Garden terrace", "baseY": -.231,
            "level": -.35, "width": .18, "height": .12, "material": "paving",
            "pattern": "laid-flags", "palette": "cool", "coping": "stone",
            "geometry": {"type": "rectangle", "center": [2.1, -1.4], "width": 3, "depth": 2.2, "yaw": .4},
            "steps": {"at": .4, "count": 3, "width": 1.2}}


def update(*objects, revision=0):
    return {"section": "garden", "baseRevision": revision, "garden": {"schema": 1, "objects": list(objects)}}


class Request:
    def __init__(self, method, url, data=b""):
        self.command, self.path, self.rfile = method, url, io.BytesIO(data)
        self.headers = Message()
        self.headers["Content-Length"] = str(len(data))

    def _json(self, code, result):
        return code, result


class GardenStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = self.root / "assets/sites/house"
        self.site.mkdir(parents=True)
        (self.site / "versions.json").write_text('{"versions":[{"id":"approved_2b"},{"id":"before"}]}')
        self.layout = self.site / "layout"
        self.file = self.layout / "approved_2b.json"
        self.store = LayoutStore(self.root)

    def save(self, *objects, revision=0):
        return self.store.save("house", "approved_2b", update(*objects, revision=revision))

    def read(self):
        return self.store.read("house", "approved_2b")

    def error(self, function, status):
        with self.assertRaises(LayoutError) as caught:
            function()
        self.assertEqual(status, caught.exception.status)
        return caught.exception.response

    def test_default_and_allowlist(self):
        self.assertEqual(self.read(), {"schema": 1, "site": "house", "version": "approved_2b", "revision": 0,
                                      "items": [], "wallColours": {}, "roomFloors": {},
                                      "garden": {"schema": 1, "objects": []}})
        self.assertFalse(self.layout.exists())
        for site, version, status in [("house", "../other", 400), ("../house", "before", 400),
                                      ("house", "not-listed", 404), ("missing", "before", 404)]:
            with self.subTest(site=site, version=version):
                self.error(lambda: self.store.read(site, version), status)

    def test_section_only_roundtrip_keeps_legacy_furniture_and_backup(self):
        self.layout.mkdir()
        legacy = {"items": [{"id": "bed-1", "extras": {"future": "keep me"}}],
                  "wallColours": {"hall/left": "#ccddee"}, "roomFloors": {"hall": "oak"},
                  "future": {"deck": [9, 2]}}
        original = json.dumps(legacy, indent=3).encode()
        self.file.write_bytes(original)
        result = self.save(patio())
        self.assertEqual(result, self.read())
        self.assertEqual(result["revision"], 1)
        self.assertEqual(result["garden"]["objects"][0], patio())
        for k, value in legacy.items():
            self.assertEqual(result[k], value)
        self.assertEqual((self.layout / "approved_2b.previous.json").read_bytes(), original)
        log = json.loads((self.layout / "changes/approved_2b/000000001.json").read_text())
        self.assertEqual((log["baseRevision"], log["revision"], log["upsert"], log["removed"]),
                         (0, 1, [patio()], []))
        self.assertEqual(self.save(patio(), revision=1), result)
        self.assertEqual(len(list((self.layout / "changes/approved_2b").glob("*.json"))), 1)
        self.error(lambda: self.save(patio()), 409)
        self.assertEqual(self.save(revision=1)["garden"], {"schema": 1, "objects": []})
        log = json.loads((self.layout / "changes/approved_2b/000000002.json").read_text())
        self.assertEqual(log["removed"], ["patio-1"])
        self.assertEqual(self.store.read("house", "before")["revision"], 0)

    def test_simultaneous_and_replayed_saves_produce_one_revision(self):
        barrier = threading.Barrier(2)
        def writer(index):
            barrier.wait()
            try:
                return 200, self.save(patio("terrace-" + str(index)))["revision"]
            except LayoutError as e:
                return e.status, e.response.get("currentRevision")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = sorted(pool.map(writer, [1, 2]))
        self.assertEqual(results, [(200, 1), (409, 1)])
        self.assertEqual(self.read()["revision"], 1)
        self.assertEqual(len(list((self.layout / "changes/approved_2b").glob("*.json"))), 1)

    def test_pending_commit_recovers_with_one_receipt(self):
        first = self.save(patio())
        real_write = layout_store.write_bytes
        def cut_power(fd, name, data):
            if name == "approved_2b.json":
                raise OSError("simulated interruption immediately before publication")
            return real_write(fd, name, data)
        with patch.object(layout_store, "write_bytes", cut_power), self.assertRaises(OSError):
            self.save(patio("second"), revision=1)
        self.assertTrue((self.layout / "approved_2b.pending.json").exists())
        recovered = self.read()
        self.assertEqual((recovered["revision"], recovered["garden"]["objects"][0]["id"]), (2, "second"))
        self.assertEqual(json.loads((self.layout / "approved_2b.previous.json").read_text()), first)
        self.assertFalse((self.layout / "approved_2b.pending.json").exists())
        self.assertEqual(len(list((self.layout / "changes/approved_2b").glob("*.json"))), 2)
        self.error(lambda: self.save(patio("second"), revision=1), 409)

    def test_bad_geometry_or_metadata_never_changes_layout(self):
        original = self.save(patio())
        candidate = patio("bad")
        bad_shapes = [
            {"type": "circle", "center": [0, 0], "radius": -1},
            {"type": "rectangle", "center": [float("nan"), 0], "width": 3, "depth": 4, "yaw": 0},
            {"type": "arc", "center": [0, 0], "radius": 1, "startAngle": 0, "sweepAngle": 0},
            {"type": "curve", "closed": True, "knots": [
                {"p": q, "in": q, "out": q, "mode": "corner"} for q in ([0, 0], [1, 1], [0, 1], [1, 0])]},
        ]
        for shape in bad_shapes:
            with self.subTest(shape=shape.get("type")):
                self.error(lambda: self.save(dict(candidate, geometry=shape), revision=1), 400)
        for entry in [dict(candidate, kind="unknown"), dict(candidate, height=True),
                      dict(candidate, steps={"at": .5, "count": 0, "width": 1}), dict(candidate, id="../bad")]:
            self.error(lambda: self.save(entry, revision=1), 400)
        self.error(lambda: self.save(candidate, candidate, revision=1), 400)
        self.assertEqual(original, self.read())

    def test_feature_form_is_identical_to_the_client_catalogue(self):
        point = {"type": "point", "center": [1, 2], "yaw": .3}
        arc = {"type": "arc", "center": [1, 2], "radius": 1, "startAngle": 0, "sweepAngle": 1}
        tree = dict(patio("tree-1"), kind="tree", geometry=point, species="apple")
        terrace = patio()
        for child in [dict(terrace, geometry=point), dict(terrace, geometry=arc),
                      dict(terrace, kind="tree")]:
            self.error(lambda: self.save(child), 400)
        self.assertFalse(self.file.exists())
        self.assertEqual(self.save(tree)["garden"]["objects"], [tree])

    def test_symlinked_sites_manifest_layout_files_and_history(self):
        outside = self.root / "protected"
        outside.mkdir()
        target = outside / "private.json"
        target.write_text('{"secret":"preserve"}')
        (self.site.parent / "alias").symlink_to(self.site, target_is_directory=True)
        self.error(lambda: self.store.read("alias", "approved_2b"), 400)
        self.layout.symlink_to(outside, target_is_directory=True)
        self.error(self.read, 400)
        self.error(lambda: self.save(patio()), 400)
        self.layout.unlink()
        self.layout.mkdir()
        for name in ("approved_2b.json", "approved_2b.previous.json", "approved_2b.pending.json", "changes"):
            link = self.layout / name
            link.symlink_to(outside if name == "changes" else target)
            self.error(lambda: self.save(patio()), 400)
            self.assertEqual(target.read_text(), '{"secret":"preserve"}')
            link.unlink()
        (self.layout / "changes").mkdir()
        (self.layout / "changes/approved_2b").symlink_to(outside, target_is_directory=True)
        self.error(lambda: self.save(patio()), 400)
        self.assertFalse((self.layout / "approved_2b.pending.json").exists())
        (self.site / "versions.json").unlink()
        (self.site / "versions.json").symlink_to(target)
        self.error(self.read, 400)
        self.assertEqual(list(outside.iterdir()), [target])

    def test_http_bounds_conflict_and_malformed_requests_without_server(self):
        url = "/layout?site=house&version=approved_2b"
        send = lambda request: layout_store.handle_layout(request, self.root)
        self.assertEqual(send(Request("GET", url))[1]["revision"], 0)
        body = json.dumps(update(patio())).encode()
        self.assertEqual(send(Request("POST", url, body))[0], 200)
        code, response = send(Request("POST", url, body))
        self.assertEqual((code, response["currentRevision"]), (409, 1))
        self.assertEqual(send(Request("GET", url + "&site=house"))[0], 400)
        self.assertEqual(send(Request("POST", url, b'{"baseRevision":0,"baseRevision":1}'))[0], 400)
        large = Request("POST", url)
        large.headers.replace_header("Content-Length", str(layout_store.MAX_BODY + 1))
        self.assertEqual(send(large)[0], 413)
        self.assertEqual(self.read()["revision"], 1)


if __name__ == "__main__":
    unittest.main()
