"""
Publish a splat test to the local viewer (splat.html?site=<name>): copies the web files from <site>/splat-test/out into
assets/sites/<name>/ (gitignored) and writes splat.json with named viewpoints taken from solved walk frames.
Light work, runs on the Mac.

    ~/splat/bin/python tools/cloud/splat_site.py <site>/splat-test front-garden-splat "Front garden · as it is today" \
        Path=f_0035 Porch=f_0081 ...
"""
import json, os, shutil, sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
src, name, title = sys.argv[1], sys.argv[2], sys.argv[3]
dst = os.path.join(ROOT, 'assets', 'sites', name); os.makedirs(dst, exist_ok=True)


def qrot(w, x, y, z):
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


cams = {}
for l in open(f'{src}/data/sparse/txt/images.txt'):
    t = l.split()
    if l.startswith('#') or len(t) != 10 or not t[9].lower().endswith('.jpg'): continue
    R = qrot(*map(float, t[1:5])); tv = np.array(list(map(float, t[5:8])))
    cams[t[9]] = (-R.T @ tv, R[2])            # centre, viewing direction (camera +z) in the site's metres
views = []
for arg in sys.argv[4:]:
    label, fr = arg.split('=')
    fr = fr if fr.endswith('.jpg') else fr + '.jpg'
    c, f = cams[fr]
    views.append({'name': label, 'frame': fr, 'eye': c.round(3).tolist(), 'look': (c + 4 * f).round(3).tolist()})
files, sizes = {}, {}
for tier, stem in (('desktop', 'splat_raw'), ('quest', 'splat_quest')):
    for ext in ('.sog', '.compressed.ply'):
        p = f'{src}/out/{stem}{ext}'
        if os.path.exists(p):
            shutil.copy(p, f'{dst}/{stem}{ext}'); files[tier] = stem + ext; sizes[tier] = f'{os.path.getsize(p) / 1e6:.0f} MB'; break
for f in os.listdir(dst):
    if f.startswith('test_points'): os.remove(f'{dst}/{f}')
man = {'title': title, 'up': 'z', 'files': files, 'sizes': sizes, 'start': views[0]['name'] if views else None, 'views': views}
json.dump(man, open(f'{dst}/splat.json', 'w'), indent=1)
print(json.dumps(man, indent=1))
