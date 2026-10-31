"""Second half of sfm.py with a smarter pair list, for when exhaustive matching
is too slow on a laptop: all stills against each other, each video frame
against its 8 neighbours, and every 3rd frame against every still.

    ~/splat/bin/python tools/photogrammetry/sfm_pairs.py <image-folder> <work-folder>
(expects <work>/database.db with features already extracted)
"""
import sys, os, time, shutil, sqlite3
import pycolmap as p
src, work = sys.argv[1], sys.argv[2]
db = os.path.join(work, "database.db")
con = sqlite3.connect(db)
names = sorted(r[0] for r in con.execute("select name from images"))
con.execute("delete from matches"); con.execute("delete from two_view_geometries"); con.commit(); con.close()
stills = [n for n in names if "_185423_" not in n]
frames = [n for n in names if "_185423_" in n]
pairs = set()
for i, a in enumerate(stills):
    for b in stills[i + 1:]: pairs.add((a, b))
for i, a in enumerate(frames):
    for b in frames[i + 1:i + 9]: pairs.add((a, b))
for a in frames[::3]:
    for b in stills: pairs.add((a, b))
pf = os.path.join(work, "pairs.txt")
open(pf, "w").write("\n".join(f"{a} {b}" for a, b in sorted(pairs)))
print(f"{len(pairs)} pairs (exhaustive would be {len(names) * (len(names) - 1) // 2})", flush=True)
t0 = time.time()
po = p.ImportedPairingOptions(); po.match_list_path = pf
p.match_image_pairs(db, pairing_options=po)
print(f"matched in {time.time() - t0:.0f}s", flush=True)
out = os.path.join(work, "sparse"); shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
maps = p.incremental_mapping(db, src, out)
for k, m in maps.items():
    print(f"model {k}: {m.num_reg_images()} images, {m.num_points3D()} points", flush=True)
    print("   ", sorted(img.name for img in m.images.values()), flush=True)
print(f"done in {time.time() - t0:.0f}s", flush=True)
