"""Construct each room's visible wall interval and returns from the measured wall and room plan."""
import copy,re
from hb_geom import point_in_poly,merge_meshes,hexa,dot,sub
from hb_walls import _cells_for_layer
from hb_joinery import box_uc

def intervals(wall,c,room):
    poly=[(x,-z) for x,z in room['polygon']]
    local=[(dot(sub(p,wall.a),wall.d),dot(sub(p,wall.a),wall.n)-c) for p in poly]
    lo,hi=wall.end_u('a',c),wall.end_u('b',c)
    cuts={lo,hi}
    for (x,y),(u,v) in zip(local,local[1:]+local[:1]):
        if (y>0)!=(v>0):
            at=x+(u-x)*y/(y-v)
            if lo<at<hi:cuts.add(at)
    cuts=sorted(cuts)
    return [(a,b) for a,b in zip(cuts,cuts[1:]) if b-a>.003 and point_in_poly(wall.point((a+b)/2,c),poly)]

def build(vb,rooms,items):
    from hb_build import atom,M
    out=[]
    fittings={a['op']['id']:a for a in vb.atoms if a['kind']=='fixture' and not a['meta'].get('stage_out')}
    for carrier in vb.walls_live():
        if carrier['meta'].get('stage_out') or carrier['meta'].get('context'):continue
        w=carrier['wall']
        if w.only_layers is not None or w.meta.get('context'):continue
        for side,c in zip((-1,1),w.full_extent_c()):
            for r in rooms:
                if r['storey']!=w.storey or 'conservator' in r['id']:continue
                floor=r['floor_y'];ceiling=r['ceiling_y'] if isinstance(r['ceiling_y'],(int,float)) else w.z1
                for n,(lo,hi) in enumerate(intervals(w,c+side*.025,r)):
                    zz=max(w.z0,floor);head=min(w.z1,ceiling)
                    if head<=zz+.005:continue
                    name=f"RL-{carrier['id']}-{side}-{r['id']}-{n}"
                    face_id=f"{r['id']}/{w.id.split('~')[0]}/{side}"
                    base=dict(stage_in=vb.N,seq=.85 if vb.N>1 else 0,category='finish' if vb.N>1 else 'existing',surface_id=face_id,room_id=r['id'],surface_role='wall')
                    meta=M('wall_lining',w.storey,'Room finish '+r['name'],'signed room schedule','scaled','Finished wall',False,**base)
                    def emit(suffix,mesh,finish):
                        if not mesh[0]:return
                        a=atom(name+suffix,'mesh','existing',meta,mat='spec_'+finish,mesh=mesh)
                        if carrier.get('as_built'):a['as_built']=True
                        out.append(a)
                    # Partition by the real drawn openings at the construction step.
                    face=copy.copy(w);face.ua=lo;face.ub=hi;face.ends={'a':(lo,0),'b':(hi,0)}
                    face.z0=zz;face.z1=head
                    def band(z0,z1,finish,suffix):
                        q=copy.copy(face);q.z0=z0;q.z1=z1
                        near,far=c+side*.0003,c+side*.0025
                        offsets=sorted(w.t/2-p/w.out for p in (near,far))
                        layer={'key':'room_finish','o0':offsets[0],'o1':offsets[1]}
                        cells=_cells_for_layer(q,layer,[])
                        meshes=[hexa(points) for row in cells.values() for points in row]
                        if meshes:emit(suffix,merge_meshes(meshes),finish)
                    wet_zone='FIN-TILE-WALL' in r['finishes']['walls'] and any(
                        a['room']==r['id'] and a['category']=='sanitary' and
                        abs(dot(sub((a['position_m'][0],-a['position_m'][2]),w.a),w.n)-c)<.95
                        for a in items)
                    clay='FIN-WALL-CLAY' in r['finishes']['walls'] and abs(w.d[1])>.95 and (
                        abs(w.point((lo+hi)/2,c)[0]-2.7925)<.1 if 'ashlar' in r['finishes']['walls'] else w.point((lo+hi)/2,c)[0]<.51)
                    top_finish='FIN-WALL-CLAY' if clay else 'FIN-WALL'
                    tile_head=min(head,floor+1.2) if wet_zone else zz
                    if tile_head>zz+.002:band(zz,tile_head,'FIN-TILE-WALL','-tile')
                    if head>tile_head+.002:band(tile_head,head,top_finish,'-paint')
                    for op in w.openings:
                        a,b=op['u0'],op['u1'];bottom,top=op['z0'],op['z1']
                        if b<=lo or a>=hi or top<=zz or bottom>=head:continue
                        fitting=fittings.get(op['id'])
                        if fitting and fitting.get('internal') and op['kind']=='door':continue
                        start=(fitting['c_plane']+side*.035) if fitting else 0
                        face_c=c+side*.0025
                        if (face_c-start)*side<=.003:continue
                        section=sorted((start,face_c));bits=[]
                        if lo-.003<=a<=hi+.003:bits.append(box_uc(w,a,a+.003,bottom,top,*section))
                        if lo-.003<=b<=hi+.003:bits.append(box_uc(w,b-.003,b,bottom,top,*section))
                        ua=max(lo,a);ub=min(hi,b)
                        if ub-ua>.007:bits.append(box_uc(w,ua,ub,top-.003,top,*section))
                        if bits:emit('-return-'+op['id'],merge_meshes(bits),top_finish)
    return out
