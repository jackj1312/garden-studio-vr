"""Check the released, movable Stage 5 dressing on the same variants the viewer loads.

    python3 tools/house/check_signed_dressing.py assets/sites/house
"""
import argparse
import json
import math
from pathlib import Path
import struct


def primitives(site, variants, item):
    path=site/variants[item['variant']]['url']
    model=json.loads(path.read_text())
    buf=(path.parent/model['buffers'][0]['uri']).read_bytes()
    def values(i):
        a=model['accessors'][i]; v=model['bufferViews'][a['bufferView']]
        fmt='<'+{5126:'f',5125:'I',5123:'H',5121:'B'}[a['componentType']]*{'SCALAR':1,'VEC3':3}[a['type']]
        o=a.get('byteOffset',0)+v.get('byteOffset',0)
        return [struct.unpack_from(fmt,buf,o+j*v.get('byteStride',struct.calcsize(fmt))) for j in range(a['count'])]
    node=model['nodes'][0]
    tx,ty,tz=node.get('translation',(0,0,0))
    ox,oy,oz=item['position']
    r=math.radians(item['rotation'])
    result=[]
    for prim in model['meshes'][node['mesh']]['primitives']:
        pts=[]
        for x,y,z in values(prim['attributes']['POSITION']):
            x,y,z=x+tx,y+ty,z+tz
            pts.append((ox+x*math.cos(r)+z*math.sin(r),oy+y,oz-x*math.sin(r)+z*math.cos(r)))
        indices=[n[0] for n in values(prim['indices'])]
        tris=[tuple(pts[j] for j in indices[k:k+3]) for k in range(0,len(indices),3)]
        result.append((model['materials'][prim['material']],pts,tris))
    return result


def highest_surface(tris,x,z):
    surfaces=[]
    for a,b,c in tris:
        ax,az=b[0]-a[0],b[2]-a[2]; bx,bz=c[0]-a[0],c[2]-a[2]
        dx,dz=x-a[0],z-a[2]; determinant=ax*bz-az*bx
        if abs(determinant)<1e-10:continue
        u,v=(dx*bz-dz*bx)/determinant,(ax*dz-az*dx)/determinant
        if u>=-1e-6 and v>=-1e-6 and u+v<=1+1e-6:surfaces.append(a[1]+u*(b[1]-a[1])+v*(c[1]-a[1]))
    assert surfaces,"Fruit's contact point is outside its bowl"
    return max(surfaces)


def check(site,version):
    data=site/'furnish'/version
    seed=json.loads((data/'seed.json').read_text())
    items={it['id']:it for it in seed['items']}
    manifest=json.loads((data/'variants.json').read_text()); variants=manifest['variants']
    report={}
    asset=lambda name:primitives(site,variants,items[name])
    for name in ('LIV-TLAMP','LIV-DEC-2'):
        ms=[m for m,_,_ in asset(name)]
        ceramic=next(m for m in ms if m['name'].startswith('spec_CER-CREAM.'))
        p=ceramic['pbrMetallicRoughness']
        rgb=''.join(f'{round(255*(1.055*n**(1/2.4)-.055)):02x}' for n in p['baseColorFactor'][:3])
        assert abs(p['roughnessFactor']-.60)<1e-5 and rgb=='e9e2d6',(version,name,p)
        report[name]={'colour':rgb,'roughness':round(p['roughnessFactor'],2)}
    bowl=asset('LIV-DEC-3')
    assert len(bowl)==1
    m,pts,_=bowl[0]; shelf=manifest['hosts']['LIV-SHELF']
    assert 'oak' in m['name'].lower() and 'baseColorTexture' in m['pbrMetallicRoughness'] and 'normalTexture' in m
    assert items['LIV-DEC-3']['host']['id']==shelf['id']
    level=min(p[1] for p in pts); foot=[p for p in pts if p[1]<=level+.001]
    assert abs(level-1.25)<.001 and all(shelf['bounds'][0][k]<=p[k]<=shelf['bounds'][1][k] for p in foot for k in (0,2))
    report['shelf_bowl']={'material':m['name'],'foot_height':round(level,4)}
    prints={name:items[name]['variant'] for name in ('LIV-ART-1','LIV-ART-2','SIT-ART-1','HAL-ART-1','HAL-ART-2','BD1-ART','BD2-ART','LAN-ART','B3B-ART') if name in items}
    if 'KA-ART-2' in items:
        prints.update({k:items[k]['variant'] for k in ('KA-ART-1','KA-ART-2','LAN2-ART-1','LAN2-ART-2','B3A-ART-1','B3A-ART-2')})
    assert len(set(prints.values()))==len(prints),'Different signed prints share geometry/inks'
    inks=lambda key:{m['name'] for m,_,_ in asset(key)}
    assert {'Studio.print.ink_charcoal','Studio.print.ink_mist','Studio.print.ink_shale'}<=inks('SIT-ART-1')
    assert 'BRI.MAT.art_sage' in inks('LIV-ART-1') and {'BRI.MAT.art_sage','BRI.MAT.art_sand'}<=inks('LIV-ART-2')
    if 'KA-ART-1' in items:
        assert {'BRI.MAT.art_clay','BRI.MAT.paper','BRI.MAT.art_sand'}<=inks('KA-ART-1')
        assert 'BRI.MAT.art_sage' in inks('KA-ART-2') and 'BRI.MAT.art_clay' not in inks('KA-ART-2')
        assert len({items['KA-CHAIR-'+str(i)]['variant'] for i in range(1,7)})==1
        mats=asset('KA-CHAIR-1')
        assert all(any(slot in m['name'] and 'baseColorTexture' in m['pbrMetallicRoughness'] for m,_,_ in mats) for slot in ('spec_FAB-SOFA','spec_WOOD-OAK-FURN'))
    report['distinct_scheduled_prints']=len(prints)
    for key,role in (('LIV-DEC-2','BRI.MAT.art_sand'),('KA-DEC-6','BRI.MAT.leaf_light')):
        if key not in items:continue
        mats=asset(key)
        ceramic_top=max(p[1] for m,points,_ in mats if 'ceramic' in m['name'] for p in points)
        crown_top=max(p[1] for m,points,_ in mats if m['name']==role for p in points)
        assert crown_top>ceramic_top+.07,(key,'stems end inside vase')
        report[key+'_foliage_above_rim_mm']=round(1000*(crown_top-ceramic_top))
    books=asset('SIT-DEC-1')
    points=[pt for _,part,_ in books for pt in part]
    spans=[max(p[i] for p in points)-min(p[i] for p in points) for i in (2,0,1)]
    assert items['SIT-DEC-1']['host']['id']=='SIT-BOOKCASE'
    assert all(abs(s-t)<.005 for s,t in zip(spans,(.800,.220,.260))),(version,spans)
    report['bookcase_row_mm']=[round(n*1000) for n in spans]
    if 'ADD-KA-FRUIT' in items:
        assert items['ADD-KA-FRUIT']['host']['id']=='KA-DEC-5'
        m,_,shell=asset('KA-DEC-5')[0]
        assert 'oak' in m['name'].lower() and 'baseColorTexture' in m['pbrMetallicRoughness']
        contact=[]
        for mat,body,_ in asset('ADD-KA-FRUIT'):
            if 'apple' not in mat['name']:continue
            bottom=min(v[1] for v in body)
            gap=min(y-highest_surface(shell,x,z) for x,y,z in body if y<bottom+.002)
            assert -.001<gap<.001,(version,mat['name'],gap)
            contact.append(round(1000*gap,2))
        assert len(contact)==2
        report['fruit_contact_mm']=contact
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('site',type=Path)
    ap.add_argument('versions',nargs='*',default=['as_built_now','approved_2b'])
    args=ap.parse_args()
    print(json.dumps({v:check(args.site,v) for v in args.versions},indent=2))
