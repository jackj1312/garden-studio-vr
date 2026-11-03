"""Validate catalogue entries, licence/source digests, actual exported files, thumbnails and UVs."""
import hashlib,json,math,struct
from pathlib import Path
from collections import Counter
HERE=Path(__file__).resolve().parent

def metric_upholstery():
    model=HERE/'models/scandinavian.sofa.gltf'
    d=json.loads(model.read_text())
    binary=(model.parent/d['buffers'][0]['uri']).read_bytes()
    def read(index):
        a=d['accessors'][index]; view=d['bufferViews'][a['bufferView']]
        fmt={5126:'f',5125:'I',5123:'H',5121:'B'}[a['componentType']]
        fmt='<'+fmt*{'SCALAR':1,'VEC2':2,'VEC3':3}[a['type']]
        start=view.get('byteOffset',0)+a.get('byteOffset',0)
        stride=view.get('byteStride',struct.calcsize(fmt))
        return [struct.unpack_from(fmt,binary,start+i*stride) for i in range(a['count'])]
    total=bad=0.
    for mesh in d['meshes']:
        for p in mesh['primitives']:
            m=d['materials'][p['material']]
            if 'upholstery' not in m['name']:continue
            repeat=m['extras']['texture_size_m']
            points=read(p['attributes']['POSITION']);uv=read(p['attributes']['TEXCOORD_0']);ix=read(p['indices'])
            for i in range(0,len(ix),3):
                a,b,c=(v[0] for v in ix[i:i+3])
                def edges(rows):return [[n-o for n,o in zip(rows[j],rows[a])] for j in [b,c]]
                v,w=edges(points)
                area=math.sqrt(sum((v[j]*w[(j+1)%3]-v[(j+1)%3]*w[j])**2 for j in range(3)))
                u,t=edges(uv);area_uv=abs(u[0]*t[1]-t[0]*u[1])*repeat**2
                total+=area
                if area_uv < area*.25:bad+=area
    assert total>0 and bad/total < .005, (bad,total)
    print('Sofa upholstery UV area below 25% of metric density:',round(100*bad/total,4),'percent')

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
    metric_upholstery()
    print(len(entries),'entries,',len({e['kind'] for e in entries}),'kinds',dict(Counter(e['style'] for e in entries)))
if __name__=='__main__':main()
