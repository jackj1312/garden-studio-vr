"""Export corrected shared joinery and a shelf-height-compatible presentation lamp.
Run in an isolated headless Blender, from the project root; source model stays untouched.
"""
import bpy,sys,json,math
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root/'tools/house'))
import hb_kit
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
s=json.load(open(root/'assets/sites/house/spec/spec_v1.json'))
it=next(x for x in s['versions']['after']['items'] if x['id']=='LIV-SHELF')
o=hb_kit.build_item(it,bpy.context.scene.collection)
o.name='AlcoveFixed';o.location=(.355,3.68,0);o.rotation_euler.z=math.radians(90)
lamp=next(x.copy() for x in s['versions']['after']['items'] if x['id']=='LIV-TLAMP')
lamp['size_mm']=[250,250,300]
l=hb_kit.build_item(lamp,bpy.context.scene.collection);l.name='AlcoveLampFit';l.location=(.35,4.05,.9005);l.rotation_euler.z=math.radians(90)
bpy.ops.object.select_all(action='DESELECT');o.select_set(True);l.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(root/'out/unreal-house/alcove/Alcove.gltf'),export_format='GLTF_SEPARATE',use_selection=True,export_yup=True)
print('ALCOVE EXPORTED')
