"""Room-owned horizontal finishes from signed room areas and their physical carriers."""
import re
import hb_geom as G

def horizontal(vb,rooms):
    from hb_build import atom,M
    from hb_room_faces import room_zones
    out=[]
    zones=room_zones(vb,rooms)
    stair_rooms=[r for r in zones if r.get('_stair')]
    stairs=[G.ccw([(x,-z) for x,z in r['polygon']]) for r in stair_rooms if r['floor_y']==0]
    walls=[(a,a['wall'].footprint()) for a in vb.walls_live() if not a['meta'].get('stage_out')]
    roofs=[a for a in vb.atoms if a['kind']=='slab' and a.get('mat')=='felt' and not a['meta'].get('stage_out')]
    slopes=[a for a in vb.atoms if a['id'].startswith('CL-') and not a['meta'].get('stage_out')]
    def footprint(room):
        poly=G.ccw([(x,-z) for x,z in room['polygon']])
        return vb._to_walls(poly,walls,room['floor_y'])
    def cover(name,r,polys,top,bottom,role,finish):
        cutters=[f for a,f in walls if a['wall'].z0<top-.0002 and a['wall'].z1>bottom+.0002]
        trimmed=minus(polys,cutters) if cutters else polys
        meshes=[G.prism(p,bottom,top) for p in trimmed if len(p)>2 and abs(G.area(p))>1e-6]
        if not meshes:return
        meta=M('finish_skin',r['storey'],'Signed '+role+' finish in '+r['name'],'room and roof schedule','scaled',r['name']+' '+role,role=='floor')
        meta.update(stage_in=vb.N,seq=.86 if vb.N>1 else 0.,category='finish' if vb.N>1 else 'existing',
                    surface_id=role+'/'+r['id'],surface_role=role,room_id=r['id'])
        out.append(atom(name,'mesh','existing',meta,mesh=G.merge_meshes(meshes),mat='spec_'+finish))
    def minus(polys,cutters):
        return [q for p in polys for q in G.poly_minus_convex(p,cutters,min_area=1e-7)]
    for room in rooms:
        if any(s in room['id'] for s in ('conservatory','porch')):continue
        height=room['ceiling_y']
        poly=footprint(room)
        pieces=G.convex_pieces(poly)
        if not isinstance(height,(int,float)):
            height=vb.lv.fclg if room['storey']=='first' else vb.lv.gclg
            # The ceiling changes line exactly where the measured sloped
            # finish ends, never a flat lid across a sloping room.
            if room['storey']=='first':
                slope=next((a for a in slopes if a['id']=='CL-ff-catslide-slope'),None)
                if slope:
                    knee=max(v[0] for v in slope['mesh'][0])
                    pieces=[Q for P in pieces if (Q:=G.clip_half(P,(-1,0,knee),True))]
            else:
                slope=next((a for a in slopes if a['id']=='CL-gf-catslide'),None)
                if slope and slope.get('poly'):pieces=minus(pieces,G.convex_pieces(slope['poly']))
        if room['storey']=='ground':
            pieces=minus(pieces,stairs)
        for roof in roofs:
            underside=roof['z0']
            if not room['floor_y']+1<underside<height-.03:continue
            cutters=G.convex_pieces(roof['poly'])
            low=[q for p in pieces for cut in cutters if (q:=G.clip_convex(p,G.poly_halfplanes(cut)))]
            cover('RCF-'+room['id']+'-'+roof['id'],room,low,underside-.001,underside-.0135,'ceiling','FIN-CEIL')
            pieces=minus(pieces,cutters)
        cover('RCF-'+room['id'],room,pieces,height-.0008,height-.003,'ceiling','FIN-CEIL')
    if stair_rooms:
        # The stairwell has a ceiling over its lower flights and over any
        # guard that ends below that ceiling. Rooms already own their panels.
        upper=[q for r in rooms if r['storey']=='first' for q in G.convex_pieces(footprint(r))]
        owned=[]
        for r in stair_rooms:
            poly=G.ccw([(x,-z) for x,z in r['polygon']])
            owned.extend(minus([poly],upper+owned))
        height=vb.lv.fclg
        cover('RCF-stairwell',stair_rooms[0],owned,height-.0008,height-.003,'ceiling','FIN-CEIL')
    if stair_rooms:
        from hb_room_faces import active_faces,room_runs
        decks=[q for a in vb.atoms if a.get('poly') and a['meta'].get('group')=='deck' and not a['meta'].get('stage_out') and abs(a.get('z1',-100)-vb.lv.ff)<.035 for q in G.convex_pieces(a['poly'])]
        from hb_joinery import box_uc
        for wall,fp in walls:
            w=wall['wall']
            if w.storey!='ground' or not vb.lv.gclg-.04<=w.z1<vb.lv.ff-.01:continue
            for side,c in zip((-1,1),active_faces(w)):
                runs=[]
                for zone in stair_rooms:
                    if zone['floor_y']>0:continue
                    for a,b in room_runs(w,c,side,zone):
                        runs.extend(G.interval_minus([(a,b)],runs))
                opposite=active_faces(w)[1 if side<0 else 0]
                # A wall between two flights exposes its own top. There is no
                # floor deck on its far side to receive a fascia.
                for zone in stair_rooms:
                    if zone['floor_y']==0:runs=G.interval_minus(runs,room_runs(w,opposite,-side,zone))
                if not runs:continue
                z0=max(vb.lv.gclg,w.z1)
                group=[]
                for a,b in runs:
                    near,far=sorted((c+side*.0003,c+side*.0125))
                    poly=G.ccw([w.point(a,near),w.point(b,near),w.point(b,far),w.point(a,far)])
                    group.extend(G.prism(Q,z0+.0008,vb.lv.ff-.0008) for Q in G.poly_minus_convex(poly,decks,min_area=1e-7))
                if not group:continue
                owner=stair_rooms[0]['id']
                meta=M('finish_skin','ground','Painted edge of the first-floor deck at the stair','measured stair and joist band','scaled','Stair lining',False)
                meta.update(stage_in=vb.N,seq=.86 if vb.N>1 else 0.,category='finish' if vb.N>1 else 'existing',room_id=owner,surface_role='wall',surface_id=f'{owner}/{w.id}/{side}')
                out.append(atom(f'RCF-stair-edge-{w.id}-{side}','mesh','existing',meta,mesh=G.merge_meshes(group),mat='spec_FIN-WALL'))
    # Box the room-facing portion of a plate above a short wall lining.
    # Each face uses its measured section and the adjacent room intervals.
    from hb_room_faces import room_runs
    from hb_walls import Wall
    from hb_joinery import box_uc
    plate_footprints=[]
    for plate in (a for a in vb.atoms if a.get('plate_wall') and not a['meta'].get('stage_out')):
        A,B=plate['A'],plate['B'];width=max(p[0] for p in plate['section'])-min(p[0] for p in plate['section'])
        bottom=A[2]+min(p[1] for p in plate['section']);top=A[2]+max(p[1] for p in plate['section'])
        w=Wall(plate['id'],A[:2],B[:2],width,bottom,top,'stud_existing')
        for side in (-1,1):
            c=side*width/2;covered=[]
            for r in zones:
                if not isinstance(r['ceiling_y'],(int,float)) or not r['floor_y']+.4<bottom<r['ceiling_y']+.001:continue
                head=min(r['ceiling_y'],top)
                if head-bottom<.001:continue
                runs=G.interval_minus(room_runs(w,c,side,r),covered)
                if not runs:continue
                polys=[]
                for a,b in runs:
                    near,far=sorted((c+side*.0003,c+side*.0125))
                    P=G.ccw([w.point(a,near),w.point(b,near),w.point(b,far),w.point(a,far)])
                    prior=[Q for Q,low,high in plate_footprints if abs(low-bottom)<.002 and abs(high-head)<.002]
                    pieces=G.poly_minus_convex(P,prior,min_area=1e-7)
                    polys.extend(G.prism(Q,bottom-.001,head) for Q in pieces)
                    plate_footprints.extend((Q,bottom,head) for Q in pieces)
                if not polys:continue
                meta=M('finish_skin',r['storey'],'Board returning over the roof bearing plate','wall plate section and signed ceiling','scaled','Wall head',False)
                meta.update(stage_in=vb.N,seq=.86 if vb.N>1 else 0.,category='finish' if vb.N>1 else 'existing',room_id=r['id'],surface_role='wall',surface_id=f"{r['id']}/{plate['plate_wall']}/{side}")
                out.append(atom(f"RCF-{plate['id']}-{side}-{r['id']}-{len(covered)}",'mesh','existing',meta,mesh=G.merge_meshes(polys),mat='spec_FIN-WALL'))
                covered.extend(runs)
    cup=next((r for r in rooms if 'under-stair' in r['id']),None)
    if stairs and cup:
        floor=cup['floor_y'];cutters=[q for r in rooms if abs(r['floor_y']-floor)<.001 for q in G.convex_pieces(footprint(r))]
        cutters.extend(f for w,f in walls if w['wall'].z0<=floor+.003<w['wall'].z1)
        areas=[]
        for P in stairs:
            new=minus([P],cutters+areas)
            areas.extend(new)
        finish=re.search(r'FIN-FLR-[A-Z]+',cup['finishes']['floor']).group()
        cover('SPEC-under-stair-floor',cup,areas,floor+.002,floor-.004,'floor',finish)
    return out
