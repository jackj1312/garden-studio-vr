"""Write the light maps a bake produced (lm_*.json beside site.json) into site.json "lightmaps"."""
import json, sys, glob, os
d = sys.argv[1]
s = json.load(open(os.path.join(d, "site.json")))
s["lightmaps"] = []
for f in sorted(glob.glob(os.path.join(d, "lm_*.json"))):
    lm = json.load(open(f))
    s["lightmaps"].append({k: lm[k] for k in ("file", "scale", "materials") if k in lm} | {"flipY": False})
json.dump(s, open(os.path.join(d, "site.json"), "w"), indent=1)
print([ (l["file"], len(l["materials"])) for l in s["lightmaps"]])
