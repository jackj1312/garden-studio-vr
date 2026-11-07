#!/usr/bin/env python3
"""Unit tests for the shared plan-data checks: a good synthetic house passes; each deliberately faulty house fails the
check that is meant to catch it.  Run:  python3 tests/test_checks.py   (from the checks folder, or any folder)."""
import os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import synthetic as S  # noqa: E402
from run_checks import run_all  # noqa: E402
import overlays, plandata  # noqa: E402

TODAY = "2026-11-07"


def fails(results, prefix=None, subject=None):
    return [r for r in results if r.status == "FAIL" and (prefix is None or r.check.startswith(prefix))
            and (subject is None or r.subject == subject)]


def check(house, gate="1B"):
    return run_all(house, gate=gate, overlay_files=(), today=TODAY)


def no_fails_except_overlays(t, res):
    bad = [r for r in res if r.status == "FAIL" and not r.check.startswith("overlay")]
    t.assertEqual(bad, [], "\n".join("%s %s %s" % (r.check, r.subject, r.detail) for r in bad))


class GoodHouses(unittest.TestCase):
    def test_good_house_passes(self):
        no_fails_except_overlays(self, check(S.good_house()))

    def test_good_loft_house_passes(self):
        no_fails_except_overlays(self, check(S.good_house(loft=True)))

    def test_gate_1a_without_slabs_passes_with_warning(self):
        h = S.good_house()
        for v in h["versions"].values():
            v["slabs"] = []
        res = check(h, gate="1A")
        self.assertEqual(fails(res), [], [r.detail for r in fails(res)])
        self.assertTrue(any(r.status == "WARN" and r.check == "closure.floor" for r in res))

    def test_gate_1b_needs_overlays(self):
        self.assertTrue(fails(check(S.good_house()), "overlay.coverage"))

    def test_schema_errors(self):
        h = S.good_house(); h["versions"]["before"]["openings"][0]["wall"] = "NOPE"
        res = check(h)
        self.assertTrue(fails(res, "schema"))


class FaultyHouses(unittest.TestCase):
    def test_open_room(self):
        res = check(S.open_room())
        self.assertTrue(fails(res, "closure.room-boundary", "R-bed"))
        self.assertTrue(fails(res, "closure.room-boundary", "R-landing"))
        self.assertTrue(fails(res, "closure.wall-joints", "W-F-int"))

    def test_reversed_loft_stair_blocking_main_stair(self):
        res = check(S.reversed_loft_stair())
        self.assertTrue(fails(res, "circulation.stair-clash"), "stair clash not detected")
        self.assertTrue(fails(res, "circulation.headroom", "ST-main"), "headroom over the main stair not detected")

    def test_missing_sill_wall(self):
        res = check(S.missing_sill_wall())
        f = fails(res, "closure.opening-fit", "WIN-liv")
        self.assertTrue(f and "below the sill" in f[0].detail)
        self.assertTrue(fails(res, "closure.room-boundary", "R-living"))

    def test_object_without_source(self):
        f = fails(check(S.object_without_source()), "evidence.cited")
        self.assertTrue(f and "OB-path" in f[0].detail)

    def test_invented_object(self):
        f = fails(check(S.invented_object()), "evidence.cited")
        self.assertTrue(f and "OB-hedge" in f[0].detail)

    def test_floor_gap(self):
        self.assertTrue(fails(check(S.floor_gap()), "closure.floor", "R-living"))

    def test_ceiling_gap(self):
        self.assertTrue(fails(check(S.ceiling_gap()), "closure.ceiling", "R-bed"))

    def test_door_count(self):
        self.assertTrue(fails(check(S.door_count_mismatch()), "closure.doors", "R-living"))

    def test_unreachable_room(self):
        self.assertTrue(fails(check(S.unreachable_room()), "circulation.reachable", "R-bed"))

    def test_wall_gap(self):
        res = check(S.wall_gap())
        self.assertTrue(fails(res, "closure.wall-joints"))
        self.assertTrue(fails(res, "closure.room-boundary", "R-living"))

    def test_low_headroom(self):
        self.assertTrue(fails(check(S.low_headroom()), "circulation.headroom", "ST-main"))

    def test_door_blocked_by_stair(self):
        self.assertTrue(fails(check(S.door_blocked()), "circulation.door-approach", "D-bed"))

    def test_inventory_label_without_room(self):
        self.assertTrue(fails(check(S.inventory_missing_room()), "closure.inventory"))

    def test_unknown_citation(self):
        h = S.good_house(); h["versions"]["before"]["walls"][0]["source"] = "not-in-register.jpg"
        self.assertTrue(fails(check(h), "evidence.register"))

    def test_after_version_checked_too(self):
        h = S.good_house(); h["versions"]["after"] = S.open_room()["versions"]["before"]
        f = fails(check(h), "closure.room-boundary")
        self.assertTrue(f and all(r.version == "after" for r in f))


class Overlays(unittest.TestCase):
    def test_good(self):
        self.assertEqual(fails(overlays.run(S.good_overlays())), [])

    def test_bad(self):
        res = overlays.run(S.bad_overlays())
        self.assertTrue(fails(res, "overlay.rms", "photo-front"))      # 14.1 px RMS
        self.assertTrue(fails(res, "overlay.edges", "photo-front"))    # 22 px edge
        self.assertTrue(fails(res, "overlay.resolution", "frame-12"))  # not full resolution


class Example(unittest.TestCase):
    def test_published_example_passes(self):
        p = os.path.join(os.path.dirname(HERE), "example-plan-data.json")
        if os.path.exists(p):
            no_fails_except_overlays(self, check(plandata.load(p)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
