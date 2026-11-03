"""Validate catalogue entries, licence/source digests, actual exported files, thumbnails and UVs."""
import hashlib,json,math,struct
from pathlib import Path
from collections import Counter
HERE=Path(__file__).resolve().parent

def main():
    catalogue=json.loads((HERE/'catalogue.json').read_text())
    entries=catalogue['items']
    assert len(set(e['id'] for e in entries))==len(entries)
    materials=json.loads((HERE/'materials.json').read_text())['materials']
    for name,m in materials.items():
        for channel,file in m.get('maps',{}).items():
            assert 'CC0' in m['licence'] and m['source_url'] and m['licence_url'],name
            assert hashlib.sha256((HERE/file).read_bytes()).hexdigest()==m['map_sha256'][channel],file
    for entry in entries:
        model=HERE/entry['model']
        data=json.loads(model.read_text())
        for b in data['buffers']:
            assert (model.parent/b['uri']).stat().st_size==b['byteLength'],model
        for im in data.get('images',[]):assert (model.parent/im['uri']).is_file(),im
        for mesh in data['meshes']:
            for p in mesh['primitives']:assert {'POSITION','NORMAL','TEXCOORD_0'}<=p['attributes'].keys(),model
        assert all(math.isfinite(n) and n>0 for n in entry['size_m']),entry['id']
        thumb=(HERE/entry['thumbnail']).read_bytes()
        assert thumb[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',thumb[16:24])==(256,256),entry
    print(len(entries),'entries,',len({e['kind'] for e in entries}),'kinds',dict(Counter(e['style'] for e in entries)))
if __name__=='__main__':main()
