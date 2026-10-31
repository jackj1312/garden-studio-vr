"""Name the model objects at pixels of an ids render (house_audit_render.py): which part is that line?
    ~/splat/bin/python tools/blender/which_object.py <render_dir> <frame> x,y [x,y ...]   (pixels of the cropped render)"""
import sys, os, json
import numpy as np
from PIL import Image
rd, fr = sys.argv[1], sys.argv[2]
names = json.load(open(os.path.join(rd, "ids", "names.json")))
im = np.asarray(Image.open(os.path.join(rd, "ids", fr.replace(".jpg", ".png"))).convert("RGBA")).astype(int)
keys = list(names); cols = np.array([names[k] for k in keys])
for xy in sys.argv[3:]:
    x, y = [int(v) for v in xy.split(",")]; px = im[y, x]
    if px[3] < 128: print(xy, "background"); continue
    d = np.abs(cols - px[:3]).sum(1); i = int(d.argmin()); print(xy, keys[i], "(off %d)" % d[i])
