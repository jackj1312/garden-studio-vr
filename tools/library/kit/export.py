"""Build one catalogue item at a time. Run with Blender --background --factory-startup --python-exit-code 1 --python this_file -- [--id style.kind]."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import studio
from studio import F

def digest(paths):
    key = hashlib.sha256()
    for path in sorted(paths):
        key.update(path.name.encode())
        key.update(path.read_bytes())
    return key.hexdigest()

def entries():
    shared = set(studio.DIMENSIONS) - set(F.DEFAULTS) - {'bedside','washer','dryer','dishwasher','fruit_bowl','stool','wall_vanity','wall_wc','mirror_cabinet','hand_towel','bookcase'}
    shared.update("oven fridge hob sink tap basin toilet bath shower radiator towel_rail downlight towel washer dryer wall_wc mirror_cabinet hand_towel".split())
    for kind, size in studio.DIMENSIONS.items():
        for style, family in studio.STYLES.items():
            if kind in shared and style != 'scandinavian':
                continue
            offered = 'shared' if kind in shared else style
            label = 'Studio' if kind in shared else family[0]
            yield dict(id=f'{offered}.{kind}', kind=kind, style=offered, family=label,
                       name=f"{label} {kind.replace('_',' ')}", variant='standard',
                       compatibleStyles=list(studio.STYLES) if kind in shared else [style],
                       construction_m=size, host=studio.host(kind),
                       roomTypes=[r for r, kinds in studio.GROUPS.items() if kind in kinds] or ['any'],
                       fixed=kind in F.FIXED or kind in studio.FIXED_CUSTOM or kind=='dishwasher')

def export_one(entry, out, stamp):
    name=entry['id']
    model=out/'models'/(name+'.gltf')
    objects=studio.make(entry['kind'], 'scandinavian' if entry['style']=='shared' else entry['style'],name,bpy.context.scene.collection)
    root=objects[0]
    entry['size_m']=[round(n,5) for n in root['size_m']]
    # Group static components into material primitives. Retain articulated subtrees.
    static=[obj for obj in objects if obj.type=='MESH' and obj.parent==root]
    if len(static)>1:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in static: obj.select_set(True)
        bpy.context.view_layer.objects.active=static[0]
        bpy.ops.object.join()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=str(model), export_format='GLTF_SEPARATE',
        export_texture_dir='../textures', use_selection=True, export_extras=True,
        export_yup=True, export_animations=False, export_cameras=False, export_lights=False)
    doc=json.loads(model.read_text())
    for material in doc.get('materials',[]):
        tint=material.get('extras',{}).get('studio_tint')
        pbr=material.get('pbrMetallicRoughness',{})
        if tint and 'baseColorTexture' in pbr: pbr['baseColorFactor']=[*tint,1.0]
    model.write_text(json.dumps(doc,separators=(',',':'))+'\n')
    entry.update(model='models/'+model.name,thumbnail='thumbs/'+name+'.png',revision=stamp)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for mesh in list(bpy.data.meshes):
        if mesh.users==0: bpy.data.meshes.remove(mesh)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--id',action='append',default=[])
    ap.add_argument('--out',type=Path,default=HERE)
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    out=args.out.resolve()
    for folder in ['models','textures','thumbs','records']: (out/folder).mkdir(parents=True,exist_ok=True)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    code=digest([HERE/f for f in ('export.py','studio.py','furnishings.py','furnishing_surfaces.py','fittings.py','materials.json')])
    catalogue=[]
    items=list(entries())
    unknown=set(args.id)-{e['id'] for e in items}
    if unknown: raise ValueError('Unknown catalogue ids: '+', '.join(sorted(unknown)))
    published=out/'catalogue.json'
    previous={e['id']:e for e in json.loads(published.read_text())['items']} if published.exists() else {}
    for entry in items:
        record=out/'records'/(entry['id']+'.json')
        stamp=hashlib.sha256((code+json.dumps(entry,sort_keys=True)).encode()).hexdigest()[:16]
        cached=json.loads(record.read_text()) if record.exists() else None
        if cached and cached['revision']==stamp and (out/cached['model']).exists():
            catalogue.append(cached)
        elif not args.id or entry['id'] in args.id:
            export_one(entry,out,stamp)
            record.write_text(json.dumps(entry)+'\n');catalogue.append(entry)
            print('STUDIO',entry['id'],entry['size_m'],flush=True)
        elif entry['id'] in previous:
            catalogue.append(previous[entry['id']])
    if len(catalogue)==len(items) or args.id:
        data=dict(schema=1,axes='X width, Y depth, Z up, front -Y, metres; glTF +Z front, Y up',styles=list(studio.STYLES),items=catalogue)
        tmp=out/'catalogue.tmp';tmp.write_text(json.dumps(data,indent=1)+'\n');os.replace(tmp,out/'catalogue.json')

if __name__=='__main__': main()
