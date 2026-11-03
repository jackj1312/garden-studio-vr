"""Private preview source boundary, snapshot retention and reviewed catalogue regression."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"house"))
import prepare_preview as preview


class PrivatePreview(unittest.TestCase):
    def test_real_catalogue_resources_have_recorded_digests(self):
        package=preview.Package()
        stock=package.catalogue(preview.FRONTEND)
        self.assertGreaterEqual(len(stock),280)
        for path,expected in package.expected.items():
            with preview.regular(package.files[path]) as f:
                self.assertEqual(preview.file_hash(f),expected,path)
        self.assertTrue(all(k.startswith(preview.KIT+"/") for k in package.files))
        self.assertFalse(any(k.endswith((".py",".blend",".pdf")) for k in package.files))

    def test_snapshot_is_atomic_and_detached_from_owner_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            dest=root/"assets/previews"
            source=root/"source";source.write_text("one")
            def package():
                result=preview.Package()
                result.add("src/probe.js",source)
                result.add("house.html",b"constant")
                return result
            one,_=preview.write_snapshot(package(),dest)
            source.write_text("two")
            two,_=preview.write_snapshot(package(),dest)
            self.assertNotEqual(one,two)
            self.assertEqual((dest/one/"src/probe.js").read_text(),"one")
            self.assertEqual((dest/two/"src/probe.js").read_text(),"two")
            self.assertEqual((dest/one/"house.html").stat().st_ino,(dest/two/"house.html").stat().st_ino)
            self.assertEqual(preview.write_snapshot(package(),dest)[0],two)
            source.unlink()
            secret=root/"secret";secret.write_text("never copy")
            source.symlink_to(secret)
            with self.assertRaises(OSError):preview.write_snapshot(package(),dest)
            self.assertEqual(json.loads((dest/"current.json").read_text())["key"],two)
            self.assertEqual({k.name for k in dest.iterdir() if not k.name.startswith(".")},{one,two,"current.json"})

    def test_layout_keeps_empty_furnished_or_garden_only_client_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()/"house-wip";(root/"layout").mkdir(parents=True)
            path=root/"layout/approved_2b.json"
            record=preview.initial("house-wip","approved_2b")
            record.update(revision=4,garden={"schema":1,"objects":[{"id":"client-patio"}]},
                          wallColours={"face":"#abc"},log="private note",appliedChangeIds=["private change"])
            path.write_text(json.dumps(record))
            seed={"items":[{"id":"sofa"}],"roomFloors":{"room":"oak"}}
            view=preview.read_layout(root,"approved_2b",seed)
            self.assertEqual([i["id"] for i in view["items"]],["sofa"])
            self.assertEqual(view["roomFloors"],{"room":"oak"})
            self.assertEqual(view["garden"],record["garden"]);self.assertEqual(view["revision"],4)
            self.assertNotIn("log",view);self.assertNotIn("appliedChangeIds",view)
            record["furnishSeeded"]=True;path.write_text(json.dumps(record))
            self.assertEqual(preview.read_layout(root,"approved_2b",seed)["items"],[])
            self.assertEqual(json.loads(path.read_text()),record)

    def test_traversal_and_symlinked_ancestor(self):
        for name in ("../x","x/../y","/absolute","a/%2e%2e","https://site/x","x/.secrets",r"a\b"):
            with self.assertRaises(ValueError):preview.relative(name)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();(root/"real").mkdir();(root/"real/secret").write_text("secret")
            (root/"alias").symlink_to(root/"real")
            with self.assertRaises(OSError):
                with preview.regular(root/"alias/secret"):pass


if __name__=="__main__":
    unittest.main()
