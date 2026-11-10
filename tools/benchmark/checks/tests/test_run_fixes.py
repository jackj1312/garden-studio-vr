#!/usr/bin/env python3
"""Regressions for two check corrections found on a real run (23 Battle Road CAD upgrade, 10 Nov 2026, MISTAKES P03 and
the ceiling-departure fix): plan overlays must not score wall faces buried inside a junction, and a room's ceiling must
honour a cited `ceiling_departure.underside_plane` when the room takes the storey plane.
    .venv/bin/python -m pytest tools/benchmark/checks/tests -q"""
import os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import synthetic as S  # noqa: E402
import overlays, plandata  # noqa: E402
from test_checks import check, fails  # noqa: E402


def _face_runs(lines, wall_id, axis, value):
    """Face segments of one wall lying on the line coordinate[axis] == value."""
    return [(p0, p1) for i, p0, p1 in lines if i == wall_id and abs(p0[axis] - value) < 1e-6 and abs(p1[axis] - value) < 1e-6]


class BuriedFaces(unittest.TestCase):
    """A drawing has no line where a wall face runs inside the wall it meets (L-corners, T-junctions, breast backs).
    Before the fix every face was sampled over its full length and every 300 mm L-corner scored t/2 against the sheet."""

    def setUp(self):
        v = plandata.versions(S.good_house(), "before")[0]
        self.lines = overlays.model_lines(v, {"kind": "plan", "storey": "G"})

    def test_inner_face_stops_at_the_corner_walls(self):
        inner = _face_runs(self.lines, "W-G-S", 1, 0.15)      # south wall, room-side face; corners buried in W/E walls
        self.assertTrue(inner)
        xs = [p[0] for seg in inner for p in seg]
        self.assertGreaterEqual(min(xs), 0.15 - overlays.STEP_M / 2)
        self.assertLessEqual(max(xs), 7.85 + overlays.STEP_M / 2)

    def test_outer_face_is_kept_whole(self):
        outer = _face_runs(self.lines, "W-G-S", 1, -0.15)
        xs = [p[0] for seg in outer for p in seg]
        self.assertAlmostEqual(min(xs), 0.0, places=6)
        self.assertAlmostEqual(max(xs), 8.0, places=6)

    def test_t_junction_stud_skips_the_external_wall(self):
        for x in (2.95, 3.05):
            ys = [p[1] for seg in _face_runs(self.lines, "W-G-int", 0, x) for p in seg]
            self.assertTrue(ys)
            self.assertGreaterEqual(min(ys), 0.15 - overlays.STEP_M / 2)
            self.assertLessEqual(max(ys), 5.85 + overlays.STEP_M / 2)


def _sloped_bedroom(kneewall=False):
    """R-bed takes the storey plane (no ceiling_m) and cites a sloped underside: 2.4 m at x = 3.05 down to 1.55 m at
    x = 7.85. With kneewall=True the east wall stops at 1.55 m, as the slope meets it, and its window is removed."""
    h = S.good_house(); ver = S._v(h)
    r = S._get(ver["rooms"], "R-bed"); r.pop("ceiling_m")
    a = -0.85 / 4.8; c0 = S.F + 2.4 - a * 3.05
    r["ceiling_departure"] = {"kind": "sloped", "underside_plane": [a, 0.0, c0], "source": "D1",
                              "note": "section: ceiling follows the rafters down to the east kneewall"}
    if kneewall:
        S._get(ver["walls"], "W-F-E")["height_m"] = 1.55
        ver["openings"] = [o for o in ver["openings"] if o["id"] != "WIN-bed"]
    return h


class CeilingDeparturePlane(unittest.TestCase):
    def test_room_ceiling_honours_underside_plane(self):
        v = plandata.versions(_sloped_bedroom(), "before")[0]
        lo, hi = v.room_ceiling(v.rooms["R-bed"])
        self.assertAlmostEqual(lo, S.F + 1.55, places=6)
        self.assertAlmostEqual(hi, S.F + 2.4, places=6)

    def test_room_without_departure_keeps_the_storey_plane(self):
        h = S.good_house(); S._get(S._v(h)["rooms"], "R-bed").pop("ceiling_m")
        v = plandata.versions(h, "before")[0]
        self.assertEqual(v.room_ceiling(v.rooms["R-bed"]), (S.F + 2.4, S.F + 2.4))

    def test_kneewall_under_a_cited_slope_is_not_a_gap(self):
        res = check(_sloped_bedroom(kneewall=True), with_mesh=False, gate="1A")
        bad = [r for r in fails(res, "closure", "R-bed") if "gap above" in r.detail]
        self.assertEqual(bad, [], [r.detail for r in bad])


if __name__ == "__main__":
    unittest.main()
