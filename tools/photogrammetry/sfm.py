"""Camera positions for every photo of a site (structure from motion).

    ~/splat/bin/python tools/photogrammetry/sfm.py <image-folder> <work-folder> [exclude-substring ...]

Writes <work>/database.db and <work>/sparse/<n>/ (COLMAP model: cameras, images, points).
Each photo keeps its own camera (phones switch lenses), SIMPLE_RADIAL for lens distortion.
"""
import sys, os, time, shutil
import pycolmap as p

src, work = sys.argv[1], sys.argv[2]
exclude = sys.argv[3:]
os.makedirs(work, exist_ok=True)
names = sorted(n for n in os.listdir(src) if n.lower().endswith((".jpg", ".jpeg", ".png")) and not any(e in n for e in exclude))
db = os.path.join(work, "database.db")
if os.path.exists(db):
    os.remove(db)
t0 = time.time()
fe = p.FeatureExtractionOptions(); fe.max_image_size = 2000; fe.sift.max_num_features = 12000
ro = p.ImageReaderOptions(); ro.camera_model = "SIMPLE_RADIAL"
p.extract_features(db, src, image_names=names, camera_mode=p.CameraMode.PER_IMAGE, reader_options=ro, extraction_options=fe)
print(f"features: {len(names)} images in {time.time() - t0:.0f}s", flush=True)
p.match_exhaustive(db)
print(f"matched in {time.time() - t0:.0f}s", flush=True)
out = os.path.join(work, "sparse")
shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
maps = p.incremental_mapping(db, src, out)
for k, m in maps.items():
    print(f"model {k}: {m.num_reg_images()} images, {m.num_points3D()} points", flush=True)
    print("   ", sorted(img.name for img in m.images.values())[:200], flush=True)
print(f"done in {time.time() - t0:.0f}s", flush=True)
