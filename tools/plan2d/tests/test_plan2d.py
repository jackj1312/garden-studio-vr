"""plan2d helpers on a synthetic sheet (no property values): faces.py strokes, surround.frame_inside, crop.render.
    .venv/bin/python -m pytest -q tools/plan2d/tests"""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import faces, surround  # noqa: E402

try:
    import fitz  # noqa: F401
    HAVE_FITZ = True
except Exception:
    HAVE_FITZ = False


def surround_window(x0=100.0, y0=200.0, x1=140.0, y1=260.0, inset=3.0):
    """An elevation window in a stone surround: outline, head band, frame head, two sill lines (sill + lower cill nose)."""
    L = [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0),     # surround outline
         (x0, y0 + 5, x1, y0 + 5)]                                                     # head band across the surround
    a, b = x0 + inset, x1 - inset
    L += [(a, y0 + 8, b, y0 + 8),        # frame head
          (a, y0 + 30, b, y0 + 30),      # transom
          (a, y1 - 6, b, y1 - 6),        # sill (top of the bottom cluster)
          (a, y1 - 4, b, y1 - 4)]        # cill nose, drawn lower
    return [(*s, 0.35) for s in L]


class Surround(unittest.TestCase):
    def test_frame_gives_sill_and_head(self):
        rect, found, info = surround.frame_inside(surround_window(), (100.0, 200.0, 140.0, 260.0))
        self.assertTrue(found)
        self.assertEqual(rect, (100.0, 208.0, 140.0, 254.0))
        self.assertTrue(info["head_band"])
        self.assertEqual(info["frame_x"], (103.0, 137.0))

    def test_plain_window_keeps_its_outline(self):
        plain = [(100, 200, 140, 200), (140, 200, 140, 260), (140, 260, 100, 260), (100, 260, 100, 200), (100, 230, 140, 230)]
        rect, found, _ = surround.frame_inside(plain, (100.0, 200.0, 140.0, 260.0))
        self.assertFalse(found)
        self.assertEqual(rect, (100.0, 200.0, 140.0, 260.0))


class Strokes(unittest.TestCase):
    def test_merges_spans_and_filters_pens(self):
        lines = [(10, 50, 30, 50, 0.7), (30, 50, 45, 50, 0.5), (60, 50, 70, 50, 0.7),   # one face in two pieces + another
                 (10, 52, 70, 52, 0.18),                                                  # thin hatch: dropped
                 (20, 0, 20, 90, 0.7),                                                    # vertical crossing the box
                 (200, 50, 220, 50, 0.7)]                                                 # outside the box
        H, V = faces.strokes(lines, (0, 40, 100, 60), min_width=0.5)
        self.assertEqual(H, {50.0: [(10.0, 45.0, 0.7), (60.0, 70.0, 0.7)]})
        self.assertEqual(V, {20.0: [(0.0, 90.0, 0.7)]})


@unittest.skipUnless(HAVE_FITZ, "PyMuPDF needed")
class OnAPdf(unittest.TestCase):
    def setUp(self):
        import fitz
        self.dir = tempfile.mkdtemp(); self.pdf = os.path.join(self.dir, "S1 test sheet.pdf")
        doc = fitz.open(); p = doc.new_page(width=300, height=300)
        for x0, y0, x1, y1, w in surround_window():
            p.draw_line((x0, y0), (x1, y1), width=w)
        p.draw_line((20, 100), (280, 100), width=0.72)
        doc.save(self.pdf)

    def test_extract_and_read_the_frame(self):
        lines = faces.extract_lines(self.pdf)
        H, _ = faces.strokes(lines, (0, 90, 300, 110), min_width=0.6)
        self.assertEqual(list(H), [100.0])
        _, found, _ = surround.frame_inside(lines, (100.0, 200.0, 140.0, 260.0))
        self.assertTrue(found)

    def test_crop_by_path_and_by_sheet_number(self):
        import crop
        img = crop.render(self.pdf, 90, 190, 150, 270, z=2, g=10)
        self.assertEqual(img.shape[:2], (160, 120))
        os.environ["DRAWINGS_DIR"] = self.dir
        try:
            self.assertEqual(crop.sheet_path("S1"), self.pdf)
        finally:
            os.environ.pop("DRAWINGS_DIR")


if __name__ == "__main__":
    unittest.main()
