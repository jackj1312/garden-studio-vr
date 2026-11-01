"""Read an architect's vector drawing at true scale: crop a region of the sheet, draw a real-world grid on it and list
every text label with its real-world position, so dimensions are read from the drawing, not estimated.
    uv run --with pymupdf --with pillow python tools/plan/read_drawing.py <drawing.pdf> <scale> <x0 y0 x1 y1 paper-mm> <out.png> [grid_m] [dpi]
Example (a 1:100 elevation): ... 4915.1.pdf 100 627 139 727 229 east_existing.png 0.5 400
Real-world origin is the region's bottom-left corner; x to the right, y up (elevations) or up the sheet (plans).
For tracing walls/openings to JSON and overlay checks use trace_drawing.py (same frame handling, vector segments)."""
import sys, json
import pymupdf

pdf, scale = sys.argv[1], float(sys.argv[2])
x0, y0, x1, y1 = map(float, sys.argv[3:7])
out = sys.argv[7]
grid = float(sys.argv[8]) if len(sys.argv) > 8 else 0.5
dpi = int(sys.argv[9]) if len(sys.argv) > 9 else 400
PT = 72 / 25.4                                     # points per paper mm

page = pymupdf.open(pdf)[0]
clip = pymupdf.Rect(x0 * PT, y0 * PT, x1 * PT, y1 * PT)
real = lambda px, py: ((px / PT - x0) * scale / 1000, (y1 - py / PT) * scale / 1000)   # paper pt -> real metres

# render the region, then draw the grid on the image: pixels map linearly to real metres whatever the PDF's rotation
pix = page.get_pixmap(dpi=dpi, clip=clip)
from PIL import Image, ImageDraw
img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
dr = ImageDraw.Draw(img, "RGBA")
ppm = pix.width / ((x1 - x0) * scale / 1000)           # image pixels per real metre
k = 0
while k * grid * ppm <= pix.width:
    gx = k * grid * ppm
    dr.line([(gx, 0), (gx, pix.height)], fill=(30, 140, 255, 110), width=1)
    dr.text((gx + 2, pix.height - 12), f"{k * grid:g}", fill=(20, 90, 220, 255)); k += 1
k = 0
while k * grid * ppm <= pix.height:
    gy = pix.height - k * grid * ppm
    dr.line([(0, gy), (pix.width, gy)], fill=(30, 140, 255, 110), width=1)
    dr.text((2, gy - 12), f"{k * grid:g}", fill=(20, 90, 220, 255)); k += 1
img.save(out)

labels = []
# get_text returns UNROTATED coordinates on a /Rotate page (PyMuPDF 1.28) while the pixmap clip is in the displayed frame:
# map each word through rotation_matrix and filter here. (Before 1 Nov 2026 this used clip= and listed the wrong area's labels.)
for w in page.get_text("words"):
    r = pymupdf.Rect(w[:4]) * page.rotation_matrix
    cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
    if not clip.contains(pymupdf.Point(cx, cy)):
        continue
    rx, ry = real(cx, cy)
    labels.append({"text": w[4], "x": round(rx, 3), "y": round(ry, 3)})
json.dump({"pdf": pdf, "scale": scale, "region_mm": [x0, y0, x1, y1], "grid_m": grid,
           "size_m": [round((x1 - x0) * scale / 1000, 3), round((y1 - y0) * scale / 1000, 3)], "labels": labels},
          open(out.rsplit(".", 1)[0] + ".json", "w"), indent=1)
print(out, "labels", len(labels))
