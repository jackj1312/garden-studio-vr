"""Cut every individual unit (brick, block) out of a straight-on close-up, as a library of real faces
(WORKFLOW G4; CORRECTIONS-LOG 53). Modelled bricks/blocks then each wear one of the client's own faces.

    ~/splat/bin/python tools/phototex/unit_library.py <photo> <out_dir> --kind brick|block [--crop x0 y0 x1 y1]
        [--min-frac 0.004] [--size 256]
Units are found by colour against the joints (bricks: saturated red vs pale mortar; blocks: light faces vs dark
joints), cleaned, and each kept unit is cut out slightly inside its edge and saved as <out_dir>/<kind>_NN.jpg,
plus library.json with each unit's pixel size and aspect (so units can be matched to the modelled sizes)."""
import argparse, json, os
import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage as nd

ap = argparse.ArgumentParser(); ap.add_argument("photo"); ap.add_argument("out"); ap.add_argument("--kind", required=True)
ap.add_argument("--crop", type=int, nargs=4); ap.add_argument("--min-frac", type=float, default=0.004); ap.add_argument("--size", type=int, default=256)
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
im = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB")
if a.crop: im = im.crop(tuple(a.crop))
x = np.asarray(im).astype(np.float32) / 255
mx, mn = x.max(2), x.min(2); sat = (mx - mn) / np.maximum(mx, 1e-3); val = mx
if a.kind == "brick":
    unit = (sat > 0.28) & (x[..., 0] > x[..., 1] * 1.08)              # red-purple brick vs cream/grey mortar
else:
    lum = nd.gaussian_filter(x.mean(2), 2); loc = nd.uniform_filter(lum, 61)
    unit = lum > loc - 0.04                                            # block faces vs the darker joints
unit = nd.binary_opening(unit, iterations=3); unit = nd.binary_fill_holes(unit); unit = nd.binary_erosion(unit, iterations=2)
lab, n = nd.label(unit); H, W = unit.shape
out = []
for i, sl in enumerate(nd.find_objects(lab), 1):
    if sl is None: continue
    hgt, wid = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
    area = (lab[sl] == i).sum()
    if area < a.min_frac * H * W or area < 0.72 * hgt * wid: continue          # too small, or not a clean rectangle
    if sl[0].start < 3 or sl[1].start < 3 or sl[0].stop > H - 3 or sl[1].stop > W - 3: continue   # cut by the photo edge
    m = max(2, int(0.04 * min(hgt, wid)))
    face = im.crop((sl[1].start + m, sl[0].start + m, sl[1].stop - m, sl[0].stop - m))
    asp = face.width / face.height
    face = face.resize((a.size, max(16, int(a.size / asp))) if asp >= 1 else (max(16, int(a.size * asp)), a.size), Image.LANCZOS)
    name = f"{a.kind}_{len(out):02d}.jpg"; face.save(os.path.join(a.out, name), quality=92)
    out.append({"file": name, "px": [wid, hgt], "aspect": round(wid / hgt, 3)})
json.dump({"kind": a.kind, "source": os.path.basename(a.photo), "units": out}, open(os.path.join(a.out, "library.json"), "w"), indent=1)
print(f"{a.kind}: {len(out)} units cut from {n} candidates; aspects {sorted(u['aspect'] for u in out)}")
