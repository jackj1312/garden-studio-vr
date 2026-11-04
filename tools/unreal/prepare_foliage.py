"""Stage reviewed CC0 source assets, including alpha and DirectX normal conversion."""
import json,shutil
from pathlib import Path
from PIL import Image,ImageOps
root=Path('/Users/Jack/Desktop/garden-scans/asset-library/polyhaven/models')
out=Path('out/unreal-house/foliage');out.mkdir(parents=True,exist_ok=True)
for key in ['island_tree_02','shrub_sorrel_01','periwinkle_plant','grass_medium_01']:
 src=root/key;dst=out/key;dst.mkdir(exist_ok=True)
 g=json.load(open(src/(key+'.gltf')))
 for b in g['buffers']:shutil.copy2(src/b['uri'],dst/Path(b['uri']).name);b['uri']=Path(b['uri']).name
 for i in g['images']:
  name=Path(i['uri']).name;candidate=src/name
  if not candidate.exists():candidate=src/i['uri']
  if not candidate.exists() and '_nor_gl_' in name:
   candidate=src/name.replace('_nor_gl_','_nor_dx_');im=Image.open(candidate).convert('RGB');r,green,b=im.split();im=Image.merge('RGB',(r,ImageOps.invert(green),b))
  else: im=Image.open(candidate).convert('RGB')
  if '_diff_' in name:
   alpha=src/name.replace('_diff_','_alpha_')
   if alpha.exists():im.putalpha(Image.open(alpha).convert('L').resize(im.size))
  name=Path(name).stem+'.png';im.save(dst/name);i['uri']=name;i['mimeType']='image/png'
 for m in g['materials']:
  if 'leav' in m.get('name','').lower() or key in ['shrub_sorrel_01','periwinkle_plant','grass_medium_01']:
   m['doubleSided']=True;m['alphaMode']='MASK';m['alphaCutoff']=.4
 (dst/(key+'.gltf')).write_text(json.dumps(g));shutil.copy2(src/'asset.json',dst/'asset.json')
 print(key,'ready')
