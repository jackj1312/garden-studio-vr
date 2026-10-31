"""Camera solve for a site: stills plus one walk-round video (frames named walk_####.jpg).

    ~/splat/bin/python tools/photogrammetry/sfm_walk.py <image-folder> <work-folder> [frame-step]

Pairs: all stills with each other; each frame with its 10 neighbours; every
3rd frame with every still; every 6th frame with every 6th (closes the loop
when the walk comes back past the same place).
"""
import sys, os, re, time, shutil, sqlite3
import pycolmap as p
src, work = sys.argv[1], sys.argv[2]
step = int(sys.argv[3]) if len(sys.argv) > 3 else 1
os.makedirs(work, exist_ok=True)
allnames = sorted(n for n in os.listdir(src) if n.lower().endswith(".jpg"))
frames = [n for n in allnames if n.startswith("walk_")][::step]
stills = [n for n in allnames if not n.startswith("walk_")]
names = stills + frames
db = os.path.join(work, "database.db")
if os.path.exists(db): os.remove(db)
t0 = time.time()
fe = p.FeatureExtractionOptions(); fe.max_image_size = 1600; fe.sift.max_num_features = 8000
ro = p.ImageReaderOptions(); ro.camera_model = "SIMPLE_RADIAL"
p.extract_features(db, src, image_names=names, camera_mode=p.CameraMode.PER_IMAGE, reader_options=ro, extraction_options=fe)
print(f"features: {len(names)} images in {time.time() - t0:.0f}s", flush=True)
pairs = set()
for i, a in enumerate(stills):
    for b in stills[i + 1:]: pairs.add((a, b))
for i, a in enumerate(frames):
    for b in frames[i + 1:i + 11]: pairs.add((a, b))
for a in frames[::3]:
    for b in stills: pairs.add((a, b))
sub = frames[::6]
for i, a in enumerate(sub):
    for b in sub[i + 2:]: pairs.add((a, b))
pf = os.path.join(work, "pairs.txt")
open(pf, "w").write("\n".join(f"{a} {b}" for a, b in sorted(pairs)))
print(f"{len(pairs)} pairs", flush=True)
po = p.ImportedPairingOptions(); po.match_list_path = pf
p.match_image_pairs(db, pairing_options=po)
print(f"matched in {time.time() - t0:.0f}s", flush=True)
out = os.path.join(work, "sparse"); shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
maps = p.incremental_mapping(db, src, out)
for k, m in maps.items():
    names_k = sorted(img.name for img in m.images.values())
    print(f"model {k}: {m.num_reg_images()} images ({sum(n.startswith('walk_') for n in names_k)} frames, "
          f"{sum(not n.startswith('walk_') for n in names_k)} stills), {m.num_points3D()} points", flush=True)
print(f"done in {time.time() - t0:.0f}s", flush=True)
