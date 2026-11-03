"""Furnishing section uses the exact same lock, revision, previous copy and WAL as the garden."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import layout_store
from layout_store import LayoutError, LayoutStore


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def chair(key="one", x=2, z=2):
    return {"id": key, "kind": "side_table", "catalogueId": "modern.side_table", "variant": "modern.side_table",
            "style": "modern", "size": [.6, .6, .7], "position": [x, 0, z], "rotation": 0,
            "room": "room", "host": {"type": "floor", "id": "floor/room"}}


class FurnishStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = self.root / "assets/sites/house"
        self.file = self.site / "layout/approved.json"
        self.seedfile = self.site / "furnish/approved/seed.json"
        self.store = LayoutStore(self.root)
        self.seed = dict(chair("signed-placement"), variant="site-measured", future={"keep": True})
        write(self.site / "versions.json", {"versions": [{"id": "approved"}, {"id": "before"}]})
        room = {"id": "room", "name": "main room", "storey": "ground", "floor_y": 0, "ceiling_y": 2.5,
                "polygon": [[0, 0], [6, 0], [6, 6], [0, 6]]}
        schedule = {"rooms": [room], "elements": "approved", "items": [], "doors_windows": [], "drawn_fixtures": []}
        write(self.site / "spec/spec_v1.json", {"versions": {"after": schedule}})
        write(self.site / "spec/catalogue_v1.json", {"floors": [{"id": "FLR-OAK"}]})
        elements = [{"type": "wall", "id": "front", "meta": {"storey": "ground"},
                     "params": {"start": [0, -.05], "end": [6, -.05], "base": 0, "height": 2.5,
                                "layers": [{"thickness": .1}]}}]
        write(self.site / "approved_elements.json", {"elements": elements})
        write(self.root / "tools/library/kit/catalogue.json", {"items": [
            {"id": "modern.side_table", "kind": "side_table", "style": "modern", "variant": "standard",
             "size_m": [.6, .6, .7], "host": "floor"}]})
        write(self.site / "furnish/approved/variants.json", {"variants": {
            "site-measured": {"kind": "side_table", "style": "modern", "catalogueId": "modern.side_table",
                              "size": [.6, .6, .7]}}, "hosts": {}})
        write(self.seedfile, {"schema": 1, "items": [self.seed], "wallColours": {"room/front/1": "#334455"},
                              "roomFloors": {"room": "FLR-OAK"}})

    def read(self):
        return self.store.read("house", "approved")

    def furnish(self, items, rev, wall=None, floor=None, **extra):
        return self.store.save("house", "approved", {"section": "furnish", "baseRevision": rev,
            "items": items, "wallColours": {} if wall is None else wall,
            "roomFloors": {} if floor is None else floor, **extra})

    def garden(self, revision):
        return self.store.save("house", "approved", {"section": "garden", "baseRevision": revision,
            "garden": {"schema": 1, "objects": [], "aFutureGardenField": "keep"}})

    def invalid(self, fn, status=400):
        with self.assertRaises(LayoutError) as cm:
            fn()
        self.assertEqual(cm.exception.status, status, cm.exception.response)
        return cm.exception.response

    def test_legacy_garden_seed_once_empty_roundtrip_and_receipt(self):
        original = {"schema": 1, "revision": 4, "items": [], "wallColours": {}, "roomFloors": {},
                    "garden": {"schema": 1, "objects": [], "future": [3]}, "envelopeFuture": [7]}
        write(self.file, original)
        raw = self.file.read_bytes()
        loaded = self.read()
        self.assertEqual(loaded["items"], [self.seed])
        self.assertEqual(loaded["wallColours"], {"room/front/1": "#334455"})
        deleted = self.furnish([], 4)
        self.assertEqual((deleted["revision"], deleted["items"], deleted["furnishSeeded"]), (5, [], True))
        self.assertEqual(deleted["garden"], original["garden"])
        self.assertEqual(deleted["envelopeFuture"], [7])
        self.assertEqual(deleted, self.read())
        self.assertEqual((self.file.parent / "approved.previous.json").read_bytes(), raw)
        receipt = json.loads((self.file.parent / "changes/approved/000000005.json").read_text())
        self.assertEqual((receipt["section"], receipt["removed"], receipt["roomFloors"], receipt["wallColours"]),
                         ("furnish", [self.seed["id"]], {"room": None}, {"room/front/1": None}))
        self.assertEqual(self.furnish([], 5), deleted)
        self.assertEqual(self.store.read("house", "before")["items"], [])

    def test_stock_legacy_label_and_measured_variant_require_real_dimensions(self):
        legacy = dict(chair(x=4, z=3), variant="standard", futureColourSpace="retain")
        loaded = self.furnish([legacy, dict(self.seed, lampOn=True)], 0)
        self.assertEqual(loaded["items"][0]["variant"], "modern.side_table")
        self.assertEqual(loaded["items"][0]["futureColourSpace"], "retain")
        self.assertEqual(loaded["items"][1]["future"], self.seed["future"])
        for change in [{"size": [1, .6, .7]}, {"variant": "site-missing"}, {"catalogueId": "wrong"},
                       {"kind": "wrong"}, {"position": [80, 0, 2]}, {"position": [2, .3, 2]},
                       {"host": {"type": "floor", "id": "floor/elsewhere"}},
                       {"host": {"type": "surface", "id": "missing"}}, {"lampOn": "yes"}]:
            with self.subTest(change=change):
                self.invalid(lambda: self.furnish([dict(legacy, **change)], 1))
        self.invalid(lambda: self.furnish([dict(legacy, variant="site-measured", size=[.7, .6, .7])], 1))
        self.invalid(lambda: self.furnish([legacy, legacy], 1))
        self.assertEqual(self.read(), loaded)

    def test_shared_cas_preserves_both_sections_and_unknown_legacy_fields(self):
        garden = self.garden(0)
        self.assertEqual(garden["items"], [self.seed])
        self.assertEqual(self.invalid(lambda: self.furnish([], 0), 409)["revision"], 1)
        moved = dict(self.seed, position=[3, 0, 3])
        updated = self.furnish([moved], 1, {"room/front/1": "#AACC99"}, {"room": "FLR-OAK"})
        self.assertEqual(updated["garden"], garden["garden"])
        self.invalid(lambda: self.garden(1), 409)
        self.invalid(lambda: self.furnish([moved], 2, {"room/exterior/1": "#114422"}))
        self.invalid(lambda: self.furnish([moved], 2, floor={"room": "not-a-covering"}))
        self.invalid(lambda: self.furnish([moved], 2, version="before"))
        self.assertEqual(updated, self.read())

    def test_older_editor_can_clear_known_finishes_without_erasing_future_item_fields(self):
        initial = dict(self.seed, finishes={"fabric": "#114455"}, lampOn=True)
        self.furnish([initial], 0)
        from_old_client = {key: value for key, value in initial.items() if key not in ("finishes", "future", "lampOn")}
        from_old_client["position"] = [4, 0, 3]
        saved = self.furnish([from_old_client], 1)["items"][0]
        self.assertEqual(saved["future"], self.seed["future"])
        self.assertNotIn("finishes", saved)
        self.assertNotIn("lampOn", saved)
        self.assertEqual(saved["position"], [4, 0, 3])


    def test_recovery_on_interrupted_furniture_publish_and_safe_seed_path(self):
        first = self.garden(0)
        actual = layout_store.write_bytes
        def cut(fd, name, data):
            if name == "approved.json":
                raise OSError("simulated interrupted write")
            return actual(fd, name, data)
        with patch.object(layout_store, "write_bytes", cut), self.assertRaises(OSError):
            self.furnish([], 1)
        recovered = self.read()
        self.assertEqual((recovered["revision"], recovered["items"], recovered["garden"]),
                         (2, [], first["garden"]))
        self.assertEqual(len(list((self.file.parent / "changes/approved").glob("*.json"))), 2)
        self.seedfile.unlink()
        outside = self.root / "outside"
        write(outside, {"schema": 1, "items": []})
        self.seedfile.symlink_to(outside)
        self.invalid(self.read)
        self.assertEqual(outside.read_text(), '{"schema": 1, "items": []}')


if __name__ == "__main__":
    unittest.main()
