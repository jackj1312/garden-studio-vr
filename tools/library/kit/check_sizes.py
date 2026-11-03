"""Run with headless Blender to exercise actual custom geometry, without exporting a house."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy, studio
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
for kind,size in [('sofa',(2.03,.91,.87)),('washer',(.60,.60,.85)),('bed',(1.60,2.10,1.20)),('bedside',(.40,.40,.55)),('towel_rail',(.50,.09,1.20))]:
    objs=studio.make_at_size(kind,'scandinavian',kind,bpy.context.scene.collection,size)
    root=objs[0]
    assert max(abs(a-b) for a,b in zip(size,root['size_m']))<=.001
    assert abs(root['built_bounds_min_m'][2])<1e-7
    assert all(abs(scale-1)<1e-7 for o in objs for scale in o.scale)
    print('PASS',kind,list(root['size_m']))
    studio.discard(objs)
