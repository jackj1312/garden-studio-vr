"""Clear multiwall conservatory sheet and 700mm typical white framing.

Pure geometry generator; original roof bounds/plane/75mm clearance envelope stay
fixed. Web10mm/0.4mm and skin0.8mm are declared typical optical-detail assumptions.
"""
import math

BAR_PITCH=.7
BAR_WIDTH=.045
EDGE_WIDTH=.055
BAR_DEPTH=.075
SHEET=.016
SKIN=.0008
WEB=.0004
WEB_PITCH=.01

def bar_spans(lo,hi,metric=1):
 if hi-lo<=EDGE_WIDTH*2:raise ValueError('Roof too small for source frame')
 first,last=lo+EDGE_WIDTH/2,hi-EDGE_WIDTH/2
 centres=[first];step=BAR_PITCH/metric
 while centres[-1]+step<last-1e-9:centres.append(centres[-1]+step)
 # An extremely narrow edge remainder is split into two honest partial bays.
 if last-centres[-1]<BAR_WIDTH+EDGE_WIDTH and len(centres)>1:centres.pop()
 centres.append(last)
 spans=[(lo,lo+EDGE_WIDTH)]+[(x-BAR_WIDTH/2,x+BAR_WIDTH/2) for x in centres[1:-1]]+[(hi-EDGE_WIDTH,hi)]
 return centres,spans

def prism(x0,x1,y0,y1,plane,top_offset,bottom_offset):
 if x1-x0<=1e-8 or y1-y0<=1e-8 or bottom_offset-top_offset<=1e-8:raise ValueError('Degenerate multiwall prism')
 a,b,c=plane;xy=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
 verts=[(x,y,a*x+b*y+c-offset) for offset in [bottom_offset,top_offset] for x,y in xy]
 faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
 return verts,faces

def geometry(source):
 x0,y0,x1,y1=source['roof_bounds_xy'];plane=source['roof_plane'];a,b,c=plane
 if abs(a)>1e-9:raise ValueError('Expected original conservatory transverse level roof')
 xc,xs=bar_spans(x0,x1);yc,ys=bar_spans(y0,y1,math.sqrt(1+b*b))
 groups={name:{'vertices':[],'faces':[],'prisms':[]} for name in ['bars','skins','webs']}
 def add(group,bounds,top,bottom):
  v,f=prism(*bounds,plane,top,bottom);g=groups[group];offset=len(g['vertices']);g['vertices']+=v;g['faces'] += [tuple(i+offset for i in face) for face in f];g['prisms'].append({'bounds':list(bounds),'offsets':[top,bottom]})
 # Continuous lengthwise bars; crossbars terminate precisely at their side faces.
 for lo,hi in xs:add('bars',(lo,hi,y0,y1),0,BAR_DEPTH)
 xgaps=[(left[1],right[0]) for left,right in zip(xs,xs[1:])]
 ygaps=[(left[1],right[0]) for left,right in zip(ys,ys[1:])]
 for lo,hi in ys:
  for xa,xb in xgaps:add('bars',(xa,xb,lo,hi),0,BAR_DEPTH)
 # Each clear frame bay has two separate outer skins and true internal webs;
 # bars occupy their own volume, avoiding glass/opaque coplanarity at joints.
 for xa,xb in xgaps:
  for ya,yb in ygaps:
   add('skins',(xa,xb,ya,yb),0,SKIN);add('skins',(xa,xb,ya,yb),SHEET-SKIN,SHEET)
   count=max(1,math.floor((xb-xa)/WEB_PITCH))
   for i in range(1,count):
    x=xa+i*WEB_PITCH
    if x+WEB/2<xb:add('webs',(x-WEB/2,x+WEB/2,ya,yb),SKIN,SHEET-SKIN)
 return {'groups':groups,'bounds':source['roof_bounds_xy'],'plane':plane,'bar_centres_x':xc,'bar_centres_y':yc,
  'bar_pitch_m':BAR_PITCH,'bar_depth_m':BAR_DEPTH,'sheet_thickness_m':SHEET,'clear_bays':len(xgaps)*len(ygaps),
  'assumption':'Typical clear twin-wall structure; web/skin sizes are not surveyed. Original outer plane/outline and white75mm frame depth retained.'}


def canopy(fr):
    """Map the independent twin-wall construction onto this survey's rectangle and clear heights."""
    from hb_build import atom,M,sig_of
    poly=fr['poly'];x0,x1=min(p[0] for p in poly),max(p[0] for p in poly)
    y0,y1=min(p[1] for p in poly),max(p[1] for p in poly)
    slope=(fr['z_rear']-fr['z_house'])/(y1-y0)
    plane=[0,slope,fr['z_house']-slope*y0+BAR_DEPTH]
    data=geometry({'roof_bounds_xy':[x0,y0,x1,y1],'roof_plane':plane})
    out=[]
    for group,mat in [('bars','upvc_white'),('skins','multiwall_skin'),('webs','multiwall_web')]:
        mesh=data['groups'][group];name=fr['id']+'-'+group
        meta=M('roof_cover','ground',fr['label']+' / '+group,fr['drawing'],fr['conf'],'Conservatory roof '+group,False)
        out.append(atom(name,'mesh','existing',meta,sig=sig_of(name,poly,plane),mat=mat,mesh=(mesh['vertices'],mesh['faces'])))
    return out

def elevations(records,roof):
    from hb_build import atom,M,sig_of,slug,dref
    from hb_geom import box
    from hb_walls import Wall
    out=[];doors=[f for f in records if 'door' in f['name'].lower()]
    bounds=lambda p:(min(x for x,y in p),max(x for x,y in p),min(y for x,y in p),max(y for x,y in p))
    y0=min(y for x,y in roof['poly']);y1=max(y for x,y in roof['poly'])
    def ceiling(y):return roof['z_house']+(roof['z_rear']-roof['z_house'])*(y-y0)/(y1-y0)
    for f in records:
        x0,x1,ya,yb=bounds(f['poly']);along_x=x1-x0>=yb-ya
        centre=(ya+yb)/2 if along_x else (x0+x1)/2
        start,end=(x0,x1) if along_x else (ya,yb)
        thickness=yb-ya if along_x else x1-x0
        isdoor=f in doors
        intervals=[(start,end)]
        if not isdoor:
            for door in doors:
                ax,bx,ay,by=bounds(door['poly'])
                if along_x and ay<=centre<=by:
                    intervals=[r for a,b in intervals for r in [(a,min(b,ax)),(max(a,bx),b)] if r[1]-r[0]>.02]
            if not along_x:
                # Butt the side frame against the inner face of the rear run.
                intervals=[(a,min(b,min(bounds(r['poly'])[2] for r in records if bounds(r['poly'])[1]-bounds(r['poly'])[0] > bounds(r['poly'])[3]-bounds(r['poly'])[2]))) for a,b in intervals]
        for i,(a,b) in enumerate(intervals):
            if b-a<=.02:continue
            aa,bb=((a,centre),(b,centre)) if along_x else ((centre,a),(centre,b))
            wall=Wall(slug(f['name']),aa,bb,thickness,0,ceiling(max(aa[1],bb[1])),'solid_existing',-1 if along_x else 1)
            id_=f"FT-{slug(f['name'])}-{i+1}"; sill=0 if isdoor else f.get('sill_z',.59)
            meta=M('door' if isdoor else 'window','ground',f['name'],dref(f['src']),'scaled','Conservatory '+('garden doors' if isdoor else 'framed glazing'),isdoor)
            if not isdoor:
                v=box(a,b,ya,yb,0,sill) if along_x else box(x0,x1,a,b,0,sill)
                out.append(atom(id_+'-dwarf','mesh','existing',dict(meta,group='wall_outer'),sig=sig_of(id_,a,b,sill),mesh=v,mat='existing_brick'))
            op=dict(id=id_,kind='door' if isdoor else 'window',u0=0,u1=b-a,z0=sill,z1=wall.z1,swing='pair, outward (+y)' if isdoor else '')
            out.append(atom(id_+'-frame','fixture','door' if isdoor else 'window',meta,sig=sig_of(id_,op),wall=wall,op=op,c_plane=0,nlights=2 if isdoor else max(1,round((b-a)/.70)),internal=False,rooms=[],frame_mat='upvc_white',sill_mat='upvc_white',conservatory=True))
            if not along_x and abs(ceiling(a)-ceiling(b))>.004:
                from hb_geom import prism_varz
                P=[(x0,a),(x1,a),(x1,b),(x0,b)]
                # Close the wedge between the straight sash rail and the pitched roof.
                v=prism_varz(P,lambda p:wall.z1-.001,lambda p:ceiling(p[1]))
                out.append(atom(id_+'-raked-head','mesh','existing',meta,sig=sig_of(id_,a,b,wall.z1),mesh=v,mat='upvc_white'))
    return out
