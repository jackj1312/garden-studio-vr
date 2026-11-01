"""Take fallen leaves (and other non-grass specks) out of a seamless lawn tile, so they do not repeat visibly every
tile (audit-3: the same leaves recurred every 0.8 m across the lawn). Leaf pixels (not green enough, or too pale),
dilated 3 px, are filled from shifted copies of clean grass in the same tile (np.roll keeps it seamless).
    ~/splat/bin/python tools/phototex/remove_leaves.py <tile.jpg> <out.jpg>"""
import sys
import numpy as np
from PIL import Image
a = np.asarray(Image.open(sys.argv[1]).convert("RGB")).astype(np.float32) / 255
leaf = (a[..., 1] < a[..., 0] * 1.10) | (a.mean(-1) > 0.6)
m = leaf.copy()
for d in (1, 2, 3):
    for dy, dx in ((d, 0), (-d, 0), (0, d), (0, -d)): m |= np.roll(np.roll(leaf, dy, 0), dx, 1)
out = a.copy(); todo = m.copy(); ok0 = ~m
for k in (6, 11, 17, 23, 31, 41, 53, 67, 89, 113):
    for dy, dx in ((k, 0), (-k, 0), (0, k), (0, -k), (k, k), (-k, k), (k, -k), (-k, -k)):
        f = todo & np.roll(np.roll(ok0, dy, 0), dx, 1)
        out[f] = np.roll(np.roll(a, dy, 0), dx, 1)[f]; todo &= ~f
Image.fromarray((out * 255).astype(np.uint8)).save(sys.argv[2], quality=93)
print(sys.argv[2], "leaf pixels %.0f%% filled, %.2f%% left" % (100 * m.mean(), 100 * todo.mean()))
