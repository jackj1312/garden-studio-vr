"""Render a region of a PDF sheet (displayed page points) at high dpi with a point grid labelled in sheet points.

    python crop.py SHEET x0 y0 x1 y1 out.png [zoom=6] [grid_pt=10]

SHEET is a PDF path, or a sheet number matched as '<SHEET> *.pdf' in $DRAWINGS_DIR (default: the current folder; read
originals from the copy on the Mac, never from an iCloud folder). Grid lines every grid_pt, labelled every 5th line;
grid_pt 0 renders the crop without a grid. 2026-11-10: PDF paths, grid pitch, no house folder default (Claude Opus 5.5)."""
import fitz, sys, glob, os, cv2, numpy as np


def sheet_path(n):
    if os.path.isfile(n):
        return n
    S = os.environ.get('DRAWINGS_DIR', '.')
    hits = sorted(glob.glob(os.path.join(S, f'{n} *.pdf')))
    if not hits:
        sys.exit(f'no sheet {n!r}: pass a PDF path or set DRAWINGS_DIR to the folder of the sheet PDFs')
    return hits[0]


def render(pdf, x0, y0, x1, y1, z=6.0, g=10.0):
    p = fitz.open(pdf)[0]
    pix = p.get_pixmap(matrix=fitz.Matrix(z, z), clip=fitz.Rect(x0, y0, x1, y1))
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3].copy()
    if g > 0:
        k = int(x0 // g) + 1
        while k * g < x1:
            X = int((k * g - x0) * z); major = k % 5 == 0
            cv2.line(img, (X, 0), (X, img.shape[0]), (255, 0, 255) if major else (255, 180, 180), 1)
            if major: cv2.putText(img, f'{k * g:g}', (X + 2, 14), 0, 0.45, (200, 0, 200), 1)
            k += 1
        k = int(y0 // g) + 1
        while k * g < y1:
            Y = int((k * g - y0) * z); major = k % 5 == 0
            cv2.line(img, (0, Y), (img.shape[1], Y), (255, 0, 255) if major else (255, 180, 180), 1)
            if major: cv2.putText(img, f'{k * g:g}', (2, Y - 3), 0, 0.45, (200, 0, 200), 1)
            k += 1
    return img


if __name__ == '__main__':
    if len(sys.argv) < 7:
        sys.exit(__doc__)
    n, x0, y0, x1, y1, out = sys.argv[1], *map(float, sys.argv[2:6]), sys.argv[6]
    z = float(sys.argv[7]) if len(sys.argv) > 7 else 6
    g = float(sys.argv[8]) if len(sys.argv) > 8 else 10
    img = render(sheet_path(n), x0, y0, x1, y1, z, g)
    cv2.imwrite(out, img[:, :, ::-1]); print(img.shape)
