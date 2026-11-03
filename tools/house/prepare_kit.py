"""Prepare site-specific, measured meshes without loading the building into memory."""
import argparse,json,sys
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
import hb_kit as kit
def prepare(site,spec_path):
    import hashlib
    site,spec_path=Path(site),Path(spec_path)
    addendum=spec_path.with_name('spec_v1_addendum2_details.json')
    inputs=[Path(__file__),Path(kit.__file__),spec_path,*[kit.KIT/f for f in ('studio.py','furnishings.py','furnishing_surfaces.py','fittings.py','materials.json','dimensions.json')]]
    if addendum.exists():inputs.append(addendum)
    revision=hashlib.sha256(b''.join(path.read_bytes() for path in inputs)).hexdigest()
    stamp=site/'kit/revision'
    if stamp.exists() and stamp.read_text()==revision and all(kit.library_path(site,v).exists() for v in ('before','after')):return
    spec=json.loads(spec_path.read_text())
    for vkey,v in spec['versions'].items():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        collection=bpy.context.scene.collection
        meshes=set();failures=[]
        addendum=spec_path.with_name('spec_v1_addendum2_details.json')
        for it in kit.schedule(spec,vkey,json.loads(addendum.read_text())['items'] if addendum.exists() else []):
            if kit.fingerprint(it) in meshes: continue
            try:
                obj=kit.build_item(it,collection)
                if obj:
                    meshes.add(obj.data.name);obj.data.use_fake_user=True
                    bpy.data.objects.remove(obj,do_unlink=True)
            except (ValueError,KeyError,RuntimeError) as exc:
                print('FAILED',vkey,it['id'],str(exc),flush=True);failures.append(it['id'])
                for obj in list(bpy.data.objects):bpy.data.objects.remove(obj,do_unlink=True)
        out=kit.library_path(site,vkey);out.parent.mkdir(exist_ok=True,parents=True)
        if not failures:
            temporary=out.with_suffix('.new.blend')
            bpy.data.libraries.write(str(temporary),{bpy.data.meshes[n] for n in meshes},path_remap='RELATIVE_ALL',fake_user=True,compress=True)
            temporary.replace(out)
        print('STUDIO',vkey,len(meshes),'meshes, failed:',failures,flush=True)
        if failures:raise ValueError(f'{vkey}: {len(failures)} unbuildable items')
    stamp.write_text(revision)

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--site',type=Path,required=True);ap.add_argument('--spec',type=Path,required=True)
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    prepare(args.site,args.spec)
