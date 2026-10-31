"""Run find_views.py for every element in a site's element_boxes.json (WORKFLOW G1 step 8).
    ~/splat/bin/python tools/photogrammetry/find_all_views.py <aligned.json> <element_boxes.json> <out_dir> [dirs]"""
import json, os, subprocess, sys
aligned, boxes, out = sys.argv[1:4]; dirs = sys.argv[4] if len(sys.argv) > 4 else ""
os.makedirs(out, exist_ok=True)
here = os.path.dirname(os.path.abspath(__file__))
for name, box in json.load(open(boxes)).items():
    if name.startswith("_"): continue
    cmd = [sys.executable, os.path.join(here, "find_views.py"), aligned, os.path.join(out, name + ".jpg"),
           "--box", *map(str, box), "--name", name.replace("_", " "), "--n", "8"] + (["--dirs", dirs] if dirs else [])
    print(subprocess.run(cmd, capture_output=True, text=True).stdout.strip())
