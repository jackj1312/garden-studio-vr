"""Construct each room's visible wall interval and returns from the measured wall and room plan."""
import copy,math
from hb_geom import point_in_poly,merge_meshes,hexa,dot,sub,interval_minus
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

def active_faces(w):
    layers=[l for l in w.layers() if not l.get('void')]
    cs=[w.c_of(l[k]) for l in layers for k in ('o0','o1')]
    return (min(cs),max(cs)) if cs else w.full_extent_c()

def room_runs(w,c,side,room):
    # Classify ownership on the air side, but keep the real slanted miter
    # endpoints at the finish plane. A clipped inner leaf can be recessed
    # behind the old cavity face specified in the signed room polygon.
    result=[]
    for delta in ([.025,.07,.13,.19] if w.only_layers else [.025]):
        probe=c+side*delta
        for a,b in intervals(w,probe,room):
            if abs(a-w.end_u('a',probe))<.0001:a=w.end_u('a',c)
            if abs(b-w.end_u('b',probe))<.0001:b=w.end_u('b',c)
            result.extend(interval_minus([(a,b)],result))
    return sorted(result)

def room_zones(vb,rooms):
    out=[]
    vault=next((a for a in vb.atoms if a['id']=='CL-porch-vault'),None)
    for room in rooms:
        r=dict(room);out.append(r)
        if 'porch' in r['id'] and vault:
            verts=vault['mesh'][0]
            y0,y1=min(p[1] for p in verts),max(p[1] for p in verts)
            z0,z1=[min(p[2] for p in verts if abs(p[1]-y)<.00001) for y in (y0,y1)]
            r['_top']=lambda pt:z0+(z1-z0)*(pt[1]-y0)/(y1-y0)
            r['_multilevel']=True
    landing=next((r for r in rooms if 'landing' in r['name']),None)
    if landing:
        for stair in [a['stair'] for a in vb.atoms if 'stair' in a and a['stair'].get('half_landing')]:
            polys=[stair['half_landing']['poly']]
            for f in stair.get('flights',[]):
                x,y=f['start'];dx,dy=f['direction'];cross=(-dy*f['width']/2,dx*f['width']/2)
                # Include the landing end, from the first nosing to the last.
                run=(f['risers']-1)*f['going'];end=(x+dx*run,y+dy*run)
                polys.append([(x+cross[0],y+cross[1]),(end[0]+cross[0],end[1]+cross[1]),
                              (end[0]-cross[0],end[1]-cross[1]),(x-cross[0],y-cross[1])])
            for i,poly in enumerate(polys):
                out.append(dict(landing,polygon=[(x,-y) for x,y in poly],floor_y=0,_multilevel=True,
                                _zone='stair'+str(i),_stair=True))
    return out

def clipped_conservatory_lining(w,lay,lift,rooms,original):
    if not lay.get('lining'):return original
    side=1 if w.c_of((lay['o0']+lay['o1'])/2)>0 else -1
    face=w.full_extent_c()[1 if side==1 else 0]
    cuts=[cut for r in rooms if r['storey']==w.storey and 'conservator' in r['id']
          for cut in intervals(w,face+side*.025,r)]
    if not cuts:return original
    kept=[]
    for a,b in interval_minus([(w.ua,w.ub)],cuts):
        q=copy.copy(w);q.ua=a;q.ub=b;q.ends={'a':(a,0),'b':(b,0)}
        kept += _cells_for_layer(q,lay,q.lifts).get(lift,[])
    return merge_meshes([hexa(cell) for cell in kept]) if kept else None

def transverse_parts(carrier,rooms,others,N):
    from hb_build import atom,M
    w=carrier['wall'];out=[];cl,ch=active_faces(w)
    for direction,u in [(-1,w.ua),(1,w.ub)]:
        # A free wall end backs onto room air. Partition its cap by room
        # polygon crossings at this measured station, including clipped piers.
        station=u+direction*.018
        for room in rooms:
            if room['storey']!=w.storey or 'conservator' in room['id']:continue
            poly=[(x,-z) for x,z in room['polygon']]
            def local(p):return dot(sub(p,w.a),w.d)-station,dot(sub(p,w.a),w.n)
            cuts={cl,ch}
            neighbours=[other['wall'] for other in others if other['wall'].id.split('~')[0]!=w.id.split('~')[0] and other['wall'].storey==w.storey]
            for boundary in [poly,*[other.footprint() for other in neighbours]]:
                local_poly=list(map(local,boundary))
                for (a,c),(b,e) in zip(local_poly,local_poly[1:]+local_poly[:1]):
                    if (a>0)!=(b>0):
                        v=c+(e-c)*a/(a-b)
                        if cl<v<ch:cuts.add(v)
            bounds=sorted(cuts)
            for j,(ca,cb) in enumerate(zip(bounds,bounds[1:])):
                sample=w.point(station,(ca+cb)/2)
                if cb-ca<.003 or not point_in_poly(sample,poly):continue
                occlusion=[(other.z0,other.top_at(dot(sub(sample,other.a),other.d)))
                           for other in neighbours if point_in_poly(sample,other.footprint())]
                lo=max(w.z0,room['floor_y']);hi=min(w.top_at(u),room['ceiling_y'] if isinstance(room['ceiling_y'],(int,float)) else w.z1)
                if hi<=lo+.01:continue
                ua,ub=sorted((u+direction*.0003,u+direction*.003))
                name=f"RL-{carrier['id']}-end{direction}-{room['id']}-{j}"
                meta=M('wall_lining',w.storey,'Finished wall end in '+room['name'],'signed room schedule','scaled','Plastered wall return',False,
                       stage_in=N,seq=.85 if N>1 else 0,category='existing' if N==1 else 'finish',surface_role='wall',room_id=room['id'],surface_id=f"{room['id']}/{w.id.split('~')[0]}/end{direction}")
                bands=[box_uc(w,ua,ub,z0,z1,ca,cb) for z0,z1 in interval_minus([(lo,hi)],occlusion) if z1-z0>.003]
                if not bands:continue
                part=atom(name,'mesh','existing',meta,mesh=merge_meshes(bands),mat='spec_FIN-WALL')
                part['carrier']=carrier['id']
                if carrier.get('as_built'):part['as_built']={'replaces':list(carrier['as_built']['replaces'])}
                out.append(part)
    # An elevated retained wall can span the passage where the old wall was
    # removed. Finish its physical underside once, over its actual room intervals.
    claimed=[]
    for room in rooms:
        if room['storey']!=w.storey or w.z0-room['floor_y']<1.8 or 'conservator' in room['id']:continue
        for side,c in zip((-1,1),(cl,ch)):
            for lo,hi in intervals(w,c+side*.025,room):
                open_runs=interval_minus([(lo,hi)],claimed)
                for a,b in open_runs:
                    if b-a<.006:continue
                    mid=w.point((a+b)/2,0)
                    if any(other['wall'].z0<w.z0 and other['wall'].top_at(dot(sub(mid,other['wall'].a),other['wall'].d))>=w.z0-.01 and point_in_poly(mid,other['wall'].footprint()) for other in others):continue
                    name=f"RL-{carrier['id']}-soffit-{room['id']}-{len(claimed)}"
                    meta=M('finish_skin',w.storey,'Finished soffit above open passage','signed room schedule','scaled','Painted opening soffit',False,stage_in=N,seq=.85 if N>1 else 0,category='finish' if N>1 else 'existing',room_id=room['id'],surface_role='ceiling')
                    part=atom(name,'mesh','existing',meta,mesh=box_uc(w,a,b,w.z0-.003,w.z0-.0003,cl,ch),mat='spec_FIN-CEIL')
                    part['carrier']=carrier['id']
                    if carrier.get('as_built'):part['as_built']={'replaces':list(carrier['as_built']['replaces'])}
                    out.append(part);claimed.append((a,b))
    return out

def build(vb,rooms,items):
    from hb_build import atom,M
    out=[]
    fittings={a['op']['id']:a for a in vb.atoms if a['kind']=='fixture' and not a['meta'].get('stage_out')}
    rooms=room_zones(vb,rooms)
    for carrier in vb.walls_live():
        if carrier['meta'].get('stage_out') or carrier['meta'].get('context'):continue
        w=carrier['wall']
        if w.meta.get('context') or not any(not lay.get('void') for lay in w.layers()):continue
        neighbours=[a for a in vb.walls_live() if a is not carrier and not a['meta'].get('stage_out') and not a.get('as_built') and not a['wall'].only_layers]
        out.extend(transverse_parts(carrier,[r for r in rooms if not r.get('_stair')],neighbours,vb.N))
        for side,c in zip((-1,1),active_faces(w)):
            claimed=[]
            for r in rooms:
                if (r['storey']!=w.storey and not r.get('_multilevel')) or 'conservator' in r['id']:continue
                floor=r['floor_y'];ceiling=r['ceiling_y'] if isinstance(r['ceiling_y'],(int,float)) else w.z1
                for n,(lo,hi) in enumerate(room_runs(w,c,side,r)):
                    zz=max(w.z0,floor);head=min(w.z1,ceiling)
                    if '_top' in r:head=min(w.z1,max(r['_top'](w.point(u,c)) for u in (lo,hi)))
                    if head<=zz+.005:continue
                    name=f"RL-{carrier['id']}-{side}-{r['id']}-{n}"+r.get('_zone','')
                    face_id=f"{r['id']}/{w.id.split('~')[0]}/{side}"
                    base=dict(stage_in=vb.N,seq=.85 if vb.N>1 else 0,category='finish' if vb.N>1 else 'existing',surface_id=face_id,room_id=r['id'],surface_role='wall')
                    meta=M('wall_lining',w.storey,'Room finish '+r['name'],'signed room schedule','scaled','Finished wall',False,**base)
                    def emit(suffix,mesh,finish):
                        if not mesh[0]:return
                        a=atom(name+suffix,'mesh','existing',meta,mat='spec_'+finish,mesh=mesh)
                        if carrier.get('as_built'):
                            a['as_built']={'replaces':list(carrier['as_built']['replaces'])}
                        a['carrier']=carrier['id'];out.append(a)
                    # Partition by the real drawn openings at the construction step.
                    face=copy.copy(w);face.ua=lo;face.ub=hi;face.ends={'a':(lo,0),'b':(hi,0)}
                    face.z0=zz;face.z1=head
                    if '_top' in r:
                        us=sorted({lo,hi,*[u for u,z in (w.profile or []) if lo<u<hi]})
                        face.profile=[(u,min(w.top_at(u),r['_top'](w.point(u,c)))) for u in us]
                    def band(z0,z1,finish,suffix):
                        q=copy.copy(face);q.z0=z0;q.z1=z1
                        near,far=c+side*.0003,c+side*.0025
                        offsets=sorted(w.t/2-p/w.out for p in (near,far))
                        layer={'key':'room_finish','o0':offsets[0],'o1':offsets[1]}
                        cuts=sorted({q.ua,q.ub,*[u for a,b,z,h in claimed for u in (a,b) if q.ua<u<q.ub]})
                        meshes=[]
                        for a,b in zip(cuts,cuts[1:]):
                            occupied=[(l,h) for u,v,l,h in claimed if u<(a+b)/2<v]
                            for bot,top in interval_minus([(z0,z1)],occupied):
                                cell=copy.copy(q);cell.ua=a;cell.ub=b;cell.ends={'a':(a,0),'b':(b,0)}
                                cell.z0=bot;cell.z1=top
                                cells=_cells_for_layer(cell,layer,[])
                                meshes.extend(hexa(points) for row in cells.values() for points in row)
                        if meshes:
                            emit(suffix,merge_meshes(meshes),finish)
                            claimed.append((q.ua,q.ub,z0,z1))
                    tile_zones=[]
                    if 'FIN-TILE-WALL' in r['finishes']['walls']:
                        for fixture in items:
                            if fixture['room']!=r['id'] or fixture['category']!='sanitary':continue
                            x,y,z=fixture['position_m'];delta=sub((x,-z),w.a)
                            width,depth=[n/1000 for n in fixture['size_mm'][:2]]
                            if abs(dot(delta,w.n)-c)>max(width,depth)/2+.18:continue
                            angle=math.radians(fixture['yaw_deg'])
                            fixture_x=(math.cos(angle),math.sin(angle));fixture_y=(-fixture_x[1],fixture_x[0])
                            half=(width*abs(dot(fixture_x,w.d))+depth*abs(dot(fixture_y,w.d)))/2+.08
                            centre=dot(delta,w.d)
                            high=head if 'shower' in fixture['type'].lower() else min(head,floor+1.2)
                            tile_zones.append((max(lo,centre-half),min(hi,centre+half),high))
                    clay='FIN-WALL-CLAY' in r['finishes']['walls'] and abs(w.d[1])>.95 and (
                        abs(w.point((lo+hi)/2,c)[0]-2.7925)<.1 if 'ashlar' in r['finishes']['walls'] else w.point((lo+hi)/2,c)[0]<.51)
                    top_finish='FIN-WALL-CLAY' if clay else 'FIN-WALL'
                    boundaries=sorted({lo,hi,*[v for a,b,h in tile_zones if a<b for v in (a,b)]})
                    for j,(left,right) in enumerate(zip(boundaries,boundaries[1:])):
                        if right-left<.001:continue
                        face.ua=left;face.ub=right;face.ends={'a':(left,0),'b':(right,0)}
                        tile_head=max([zz]+[v for a,b,v in tile_zones if a<(left+right)/2<b])
                        if tile_head>zz+.002:band(zz,tile_head,'FIN-TILE-WALL',f'-tile-{j}')
                        if head>tile_head+.002:band(tile_head,head,top_finish,f'-paint-{j}')
                    if r.get('_stair'):continue
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
                        if ub-ua>.007:
                            bits.append(box_uc(w,ua,ub,top-.003,top,*section))
                            if op['kind']=='window':bits.append(box_uc(w,ua,ub,bottom,bottom+.003,*section))
                        if bits:emit('-return-'+op['id'],merge_meshes(bits),top_finish)
    # As-built window boards and finishes replace their drawn counterpart as
    # a family, including split intervals and differently named measured returns.
    for a in [*vb.atoms,*out]:
        if not a.get('as_built'):continue
        replacements=set(a['as_built']['replaces'])
        replacements.update(d['id'] for d in out if not d.get('as_built') and d['carrier'] in replacements)
        a['as_built']['replaces']=sorted(replacements)
    return out
