"""Tiny target/owner fixtures only. Neither the live site nor a real house GLB is touched."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "house"))
from layout_store import LayoutStore
import publish_candidate


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=3) + "\n")


class PublicationLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "candidate-project/assets/sites/private-build"
        self.client_root = root / "live-project"
        self.client = self.client_root / "assets/sites/client"
        self.seeds = {}
        rows = []
        for version in ["first", "saved", "garden-only"]:
            src = self.source / "furnish" / version
            seed = {"schema": 1, "items": [{"id": version + "-desk", "position": [1, 0, -2]}],
                    "wallColours": {"A/1/1": "#ABCDEF"}, "roomFloors": {"A": "oak"},
                    "appliedChangeIds": [version + "-signed"]}
            self.seeds[version] = seed
            put(src / "seed.json", seed)
            put(src / "variants.json", {"schema": 1, "variants": {}, "hosts": {}})
            rows.append({"id": version, "furnish_runtime": {
                "seed": "furnish/" + version + "/seed.json", "variants": "furnish/" + version + "/variants.json"}})
        put(self.source / "versions.json", {"versions": rows, "layout_source": {"site": "client", "projectRoot": "../live-project"}})
        for f in ["materials.json", "regs_map.json", "regs.json", "summary.json", "spec_check.json",
                  "setting_front.glb", "setting_front_lod.glb"]:
            (self.source / f).write_bytes(b"fixture\n")
        put(self.client / "versions.json", {"versions": [{"id": "saved"}, {"id": "garden-only"}]})
        self.layout = self.client / "layout"
        self.design = {"schema": 1, "site": "client", "version": "saved", "revision": 7, "furnishSeeded": True,
                       "items": [{"id": "client-desk", "future": [3]}], "roomFloors": {"A": "stone"}, "wallColours": {},
                       "garden": {"objects": [{"id": "tree"}], "schema": 1, "future": {"keep": 42}}}
        put(self.layout / "saved.json", self.design)
        put(self.layout / "garden-only.json", {"revision": 4, "items": [], "garden": {"objects": [{"id": "studio-base"}], "schema": 1}})
        self.store = LayoutStore(self.client_root)

    def test_missing_only_uses_complete_seed_and_keeps_every_existing_byte(self):
        kept = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.layout.iterdir()}
        publish_candidate.promote(self.source, self.client)
        p = self.layout / "first.json"
        initialized = self.store.read("client", "first")
        self.assertEqual(initialized, dict(self.seeds["first"], site="client", version="first", revision=0,
                                          furnishSeeded=True, garden={"schema": 1, "objects": []}))
        self.assertEqual(initialized, json.loads(p.read_text()))
        self.assertFalse((self.layout / "changes").exists())
        self.assertFalse((self.layout / "first.previous.json").exists())
        self.assertNotIn("layout_source", json.loads((self.client / "versions.json").read_text()))
        kept[p] = (p.read_bytes(), p.stat().st_mtime_ns)
        publish_candidate.promote(self.source, self.client)
        self.assertEqual({f: (f.read_bytes(), f.stat().st_mtime_ns) for f in self.layout.iterdir()}, kept)
        self.assertEqual(self.design, self.store.read("client", "saved"))
        legacy = self.store.read("client", "garden-only")
        self.assertEqual((legacy["revision"], legacy["items"], legacy["garden"]["objects"]),
                         (4, self.seeds["garden-only"]["items"], [{"id": "studio-base"}]))

    def test_failed_manifest_swap_rolls_back_only_new_seed(self):
        prior = (self.client / "versions.json").read_bytes()
        keep = {p: p.read_bytes() for p in self.layout.iterdir()}
        replace = os.replace
        injected = []
        manifest = (self.client / "versions.json").resolve()
        def fail(src, dest, *args, **kwargs):
            if Path(dest).resolve() == manifest:
                injected.append(manifest)
                raise OSError("fixture interruption before manifest swap")
            return replace(src, dest, *args, **kwargs)
        with patch.object(os, "replace", fail), self.assertRaises(OSError):
            publish_candidate.promote(self.source, self.client)
        self.assertEqual(injected, [manifest])
        self.assertEqual((self.client / "versions.json").read_bytes(), prior)
        self.assertEqual({p: p.read_bytes() for p in self.layout.iterdir()}, keep)
        publish_candidate.promote(self.source, self.client)
        self.assertEqual(self.store.read("client", "first")["revision"], 0)

    def test_wrong_named_client_cannot_be_published(self):
        other = self.client.parent / "someone-else"
        put(other / "versions.json", {"versions": []})
        with self.assertRaisesRegex(ValueError, "destination client"):
            publish_candidate.promote(self.source, other)
        self.assertFalse((other / "layout").exists())

    def test_same_site_name_in_a_different_worktree_is_never_written(self):
        mirror = self.source.parent / "client"
        put(mirror / "versions.json", {"versions": [{"id": "first"}]})
        raw = (mirror / "versions.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "bound client checkout"):
            publish_candidate.promote(self.source, mirror)
        self.assertEqual(list(mirror.iterdir()), [mirror / "versions.json"])
        self.assertEqual((mirror / "versions.json").read_bytes(), raw)



if __name__ == "__main__":
    unittest.main()
