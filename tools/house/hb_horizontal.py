"""Room-owned horizontal finishes from signed room areas and their physical carriers."""
import re
import hb_geom as G

def horizontal(vb,rooms):
    from hb_build import atom,M
    from hb_room_faces import room_zones
    out=[]
    zones=room_zones(vb,rooms)
    stairs=[G.ccw([(x,-z) for x,z in r['polygon']]) for r in zones if r.get('_stair')]
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
