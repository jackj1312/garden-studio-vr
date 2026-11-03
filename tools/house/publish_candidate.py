"""Publish a verified local build while clients continue reading the previous manifest."""
import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

MODEL_FIELDS = ('glb','glb_quest','glb_quest_meshopt','stages','elements')
SPEC_FILES = ('spec_v1.json','spec_v1_addendum2_details.json','furnishing_plan.json',
              'catalogue_v1.json','finish_interfaces.json','SCHEMA.md','SIGNOFF.md')


def payload(site, manifest):
    paths=set()
    for row in manifest['versions']:
        for key in MODEL_FIELDS:
            if row.get(key):
                paths.add(Path(row[key]))
        paths.update(p.relative_to(site) for p in site.glob(row['id']+'_*.json'))
        runtime=row.get('furnish_runtime') or {}
        for field in ('seed','variants'):
            if runtime.get(field):paths.add(Path(runtime[field]))
        if runtime.get('variants'):
            variants=json.loads((site/runtime['variants']).read_text())['variants']
            for item in variants.values():
                for field in ('url','questUrl'):
                    if not item.get(field):continue
                    model=Path(item[field]);paths.add(model)
                    if model.suffix=='.gltf':
                        document=json.loads((site/model).read_text())
                        for resource in document.get('buffers',[])+document.get('images',[]):
                            uri=resource.get('uri')
                            if uri and not uri.startswith('data:'):
                                paths.add((site/model.parent/uri).resolve().relative_to(site.resolve()))
    paths.update(Path(name) for name in ('materials.json','regs_map.json','regs.json','summary.json',
                                         'setting_front.glb','setting_front_lod.glb','spec_check.json'))
    paths.update(Path('spec')/name for name in SPEC_FILES if (site/'spec'/name).is_file())
    for p in paths:
        if p.is_absolute() or '..' in p.parts or not (site/p).is_file():
            raise ValueError(f'Missing or invalid candidate payload {p}')
    return sorted(paths)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for piece in iter(lambda:stream.read(1024*1024),b''):
            h.update(piece)
    return h.hexdigest()


def promote(site,destination):
    dest=destination.resolve()
    if dest==site or dest.parent.name!='sites' or not (dest/'versions.json').is_file():
        raise ValueError('Expected an existing, distinct local studio site')
    manifest=json.loads((site/'versions.json').read_text())
    paths=payload(site,manifest)
    hashes={p:digest(site/p) for p in paths}
    key=hashlib.sha256((json.dumps(manifest,sort_keys=True)+''.join(str(p)+sha for p,sha in hashes.items())).encode()).hexdigest()[:20]
    releases=dest/'releases';releases.mkdir(exist_ok=True)
    release=releases/key
    with (dest/'.furnish-publish.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        # All reader-visible model URLs change together with versions.json.
        if not release.exists():
            with tempfile.TemporaryDirectory(prefix='.prepare-',dir=releases) as stage:
                incoming=Path(stage)/'build';incoming.mkdir()
                for p,sha in hashes.items():
                    (incoming/p).parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(site/p,incoming/p)
                    if digest(incoming/p)!=sha:raise ValueError(f'Changed during publication: {p}')
                os.replace(incoming,release)
        else:
            for p,sha in hashes.items():
                if digest(release/p)!=sha:raise ValueError(f'Incomplete prior release: {p}')
        for row in manifest['versions']:
            for field in MODEL_FIELDS:
                if row.get(field):row[field]=(Path('releases')/key/row[field]).as_posix()
            for field,value in (row.get('furnish_runtime') or {}).items():
                if field in ('seed','variants'):row['furnish_runtime'][field]=(Path('releases')/key/value).as_posix()
        manifest['furnish_release']=key
        with tempfile.TemporaryDirectory(prefix='.publish-',dir=dest) as tmp:
            rollback=Path(tmp)/'previous';rollback.mkdir()
            changed=[]
            try:
                for p in paths:
                    target=dest/p;target.parent.mkdir(parents=True,exist_ok=True)
                    if target.exists() and target.samefile(release/p):continue
                    if target.exists():
                        (rollback/p).parent.mkdir(parents=True,exist_ok=True)
                        os.link(target,rollback/p)
                    link=Path(tmp)/'next'
                    os.link(release/p,link);os.replace(link,target);changed.append(p)
                new_manifest=Path(tmp)/'versions.json'
                new_manifest.write_text(json.dumps(manifest,indent=1)+'\n')
                os.replace(new_manifest,dest/'versions.json')
            except BaseException:
                for p in reversed(changed):
                    if (rollback/p).exists():os.replace(rollback/p,dest/p)
                    else:
                        with contextlib.suppress(FileNotFoundError):(dest/p).unlink()
                raise
    print(f'Published local release {key} to {dest}')
