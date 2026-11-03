"""Finish the interior cut faces of a carrier at construction, preserving its outer masonry."""
from hb_geom import point_in_poly
from hb_room_faces import room_zones

class CarrierFaces:
    def __init__(self,vb,rooms):
        self.zones=[]
        self.materials={}
        for room in room_zones(vb,rooms):
            if 'conservator' in room['id']:continue
            poly=[(x,-z) for x,z in room['polygon']]
            self.zones.append((room,poly,(min(x for x,y in poly),min(y for x,y in poly),max(x for x,y in poly),max(y for x,y in poly))))
        self.N=vb.N

    def inside(self,q,direction,wall):
        x,y,z=q; nx,ny,nz=direction
        # Extend across the thickness for a cut end or stair bearing.
        # A vertical exterior face is never classified by a sideways probe.
        offsets=(0,) if abs(nz)<.7 and abs(nx*wall.n[0]+ny*wall.n[1])>.85 else (0,.10,-.10,.18,-.18)
        for dist in (.012,.08,.22,.36):
            for offset in offsets:
                tx=x+nx*dist+wall.n[0]*offset;ty=y+ny*dist+wall.n[1]*offset;tz=z+nz*.01
                for r,poly,(x0,y0,x1,y1) in self.zones:
                    if tx<x0 or tx>x1 or ty<y0 or ty>y1 or tz<r['floor_y']-.015:continue
                    head=r['_top']((tx,ty)) if '_top' in r else r['ceiling_y'] if isinstance(r['ceiling_y'],(float,int)) else r['floor_y']+2.405
                    if tz>head+.015 or not point_in_poly((tx,ty),poly):continue
                    return r
        return None

    def assign(self,part,mesh,materials):
        wall=part['atom']['wall']
        outer=wall.out*wall.t/2
        external=wall.ckey in ('cav337_new','cav_existing','solid_existing','leaf_existing','party','massing')
        original=mesh.materials[0]
        changes=[]
        for face in mesh.polygons:
            n=face.normal;p=face.center
            along=n.x*wall.d[0]+n.y*wall.d[1]
            across=n.x*wall.n[0]+n.y*wall.n[1]
            c=(p.x-wall.a[0])*wall.n[0]+(p.y-wall.a[1])*wall.n[1]
            # Protect the studio's entire exterior leaf, including its
            # outward-facing mitres and the part of a reveal before the frame.
            if external and across*wall.out>.3 and (outer-c)*wall.out<.018:continue
            if external and abs(along)>.8 and (outer-c)*wall.out<.055:continue
            # Longitudinal faces already have their authored finish intervals.
            # The rule here also owns revealed inner leaves behind a frame.
            room=self.inside(p,n,wall)
            if room is None:continue
            # On outer faces a single triangle can extend beyond an occupied
            # room or above a vault. Their clipped room panels own that surface.
            if external and across*wall.out>.85:
                if not all(self.inside(mesh.vertices[i].co,n,wall) for i in face.vertices):continue
            role='ceiling' if n.z<-.7 else 'wall'
            side=1 if across>=0 else -1
            if abs(along)>.7:side='end'+str(1 if along>0 else -1)
            identifier=f"{room['id']}/{wall.id.split('~')[0]}/{side}"
            key=(role,identifier,original.name)
            if key not in self.materials:
                finish=materials['spec_FIN-CEIL' if role=='ceiling' else 'spec_FIN-WALL'].copy()
                finish.name=('Room ceiling ' if role=='ceiling' else 'Room wall ')+identifier
                finish['surface_role']=role;finish['surface_id']=identifier;finish['room_id']=room['id']
                finish['substrate']=original.name
                finish['finish_stage']=self.N
                finish['substrate_colour']=list(original.diffuse_color[:3])
                self.materials[key]=finish
            changes.append((face,self.materials[key]))
        if not changes:return None
        slots={}
        for face,finish in changes:
            if finish.name not in slots:
                slots[finish.name]=len(mesh.materials);mesh.materials.append(finish)
            face.material_index=slots[finish.name]
