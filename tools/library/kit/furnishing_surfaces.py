"""Original lightweight surface constructions; pure Python, no Blender dependency."""
import math


def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def unit(a):
    n=math.sqrt(dot(a,a))
    if n<1e-12:raise ValueError('Degenerate support surface')
    return tuple(x/n for x in a)


def supported_band(vertices,triangles,uvs,ymin,ymax,clearance=.0010,thickness=.0018):
    """Clip an existing textile top, then make a thin supported offset shell.

    Preserve its exact triangle basis instead of inventing independent waves.
    Offset every vertex far enough along its averaged normal to clear all of
    its incident source planes. This local proof still requires a full mesh
    intersection check for distant folds in the integrated fixture.
    """
    points=[];coords=[];faces=[];lookup={}
    def clip(poly,bound,keep_above):
        out=[]
        for a,b in zip(poly,poly[1:]+poly[:1]):
            ain=a[0][1]>=bound-1e-10 if keep_above else a[0][1]<=bound+1e-10
            bin=b[0][1]>=bound-1e-10 if keep_above else b[0][1]<=bound+1e-10
            if ain:out.append(a)
            if ain!=bin:
                t=(bound-a[0][1])/(b[0][1]-a[0][1]);p=tuple(x+(y-x)*t for x,y in zip(a[0],b[0]));uv=tuple(x+(y-x)*t for x,y in zip(a[1],b[1]));out.append((p,uv))
        clean=[]
        for item in out:
            if not clean or sum((a-b)**2 for a,b in zip(item[0],clean[-1][0]))>1e-18:clean.append(item)
        if len(clean)>1 and sum((a-b)**2 for a,b in zip(clean[0][0],clean[-1][0]))<1e-18:clean.pop()
        return clean
    def index(item):
        key=tuple(round(x,9) for x in item[0])
        if key not in lookup:lookup[key]=len(points);points.append(item[0]);coords.append(item[1])
        return lookup[key]
    for tri in triangles:
        poly=[(tuple(vertices[i]),tuple(uvs[i])) for i in tri]
        poly=clip(clip(poly,ymin,True),ymax,False)
        for j in range(1,len(poly)-1):
            t=[poly[0],poly[j],poly[j+1]]
            if dot(cross(sub(t[1][0],t[0][0]),sub(t[2][0],t[0][0])),cross(sub(t[1][0],t[0][0]),sub(t[2][0],t[0][0])))<1e-20:continue
            faces.append(tuple(index(v) for v in t))
    if not faces:raise ValueError('Empty supported textile band')
    incident=[[] for _ in points];edges={}
    for tri in faces:
        n=unit(cross(sub(points[tri[1]],points[tri[0]]),sub(points[tri[2]],points[tri[0]])))
        for i in tri:incident[i].append(n)
        for a,b in zip(tri,tri[1:]+tri[:1]):edges.setdefault(tuple(sorted((a,b))),[]).append((a,b))
    directions=[]
    for ns in incident:
        n=unit(tuple(sum(p[k] for p in ns) for k in range(3)));projection=min(dot(n,p) for p in ns)
        if projection<.2:raise ValueError('Support fold too sharp for bounded offset')
        directions.append(tuple(x/projection for x in n))
    verts=[]
    for distance in [clearance+thickness,clearance]:
        verts += [tuple(x+distance*n for x,n in zip(p,d)) for p,d in zip(points,directions)]
    count=len(points);closed=list(faces)+[tuple(i+count for i in reversed(t)) for t in faces]
    for witnesses in edges.values():
        if len(witnesses)==1:
            a,b=witnesses[0];closed += [(a,b+count,b),(a,a+count,b+count)]
        elif len(witnesses)!=2:raise ValueError('Nonmanifold textile support')
    return {'vertices':verts,'faces':closed,'uv':coords+coords,'support_vertices':points,'support_faces':faces,'thickness_m':thickness,'clearance_m':clearance}


def vanity_counter(w,d,h,bowl_w,bowl_d,bowl_h=.12,bowl_y=None,thickness=.025):
    """Closed stone annulus around the actual outer basin section through slab."""
    cy=-d*.05 if bowl_y is None else bowl_y;top=h-.08+thickness/2;bottom=top-thickness;base=h-bowl_h
    # Same continuous outer profile as _bowl_shell, evaluated at slab top.
    profile=[(.42,0),(.70,bowl_h*.08),(.89,bowl_h*.40),(1,bowl_h*.92),(.995,bowl_h)]
    relative=top-base
    scale=next(a[0]+(b[0]-a[0])*(relative-a[1])/(b[1]-a[1]) for a,b in zip(profile,profile[1:]) if a[1]<=relative<=b[1])
    power=.48;gap=.0008;rx=bowl_w*scale/2+gap;ry=bowl_d*scale/2+gap;angles=[2*math.pi*i/64 for i in range(64)]
    # Put exact outer rectangle corners into the annulus; inner parameter uses
    # the same signed-power superellipse as the real bowl.
    for x,y in [(-w/2,-d/2-cy),(w/2,-d/2-cy),(w/2,d/2-cy),(-w/2,d/2-cy)]:
        tx=math.copysign(abs(x/rx)**(1/power),x);ty=math.copysign(abs(y/ry)**(1/power),y);angles.append(math.atan2(ty,tx)%(2*math.pi))
    angles=sorted(set(round(a,12) for a in angles));inner=[];outer=[]
    for a in angles:
        x=math.copysign(abs(math.cos(a))**power,math.cos(a))*(bowl_w*scale/2+gap)
        y=math.copysign(abs(math.sin(a))**power,math.sin(a))*(bowl_d*scale/2+gap)
        hits=[]
        if abs(x)>1e-10:hits.append((w/2)/abs(x))
        if y>1e-10:hits.append((d/2-cy)/y)
        elif y< -1e-10:hits.append((-d/2-cy)/y)
        t=min(hits)
        if t<=1:raise ValueError('Basin aperture exceeds counter envelope')
        inner.append((x,cy+y));outer.append((x*t,cy+y*t))
    n=len(angles);verts=[(x,y,z) for z in [top,bottom] for ring in [outer,inner] for x,y in ring];faces=[]
    for i in range(n):
        j=(i+1)%n
        faces += [(i,j,n+j),(i,n+j,n+i),(2*n+i,3*n+j,2*n+j),(2*n+i,3*n+i,3*n+j),
                  (i,2*n+j,j),(i,2*n+i,2*n+j),(n+i,n+j,3*n+j),(n+i,3*n+j,3*n+i)]
    return {'vertices':verts,'faces':faces,'uv':[(x,y) for x,y,z in verts],'aperture_scale':scale,'aperture_clearance_m':gap,'counter_top_m':top,'counter_bottom_m':bottom}


def triangulate_polygon(points):
    """Deterministic ear clipping for a simple X/Z garment cutting pattern."""
    pts=[tuple(p) for p in points]
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(pts,pts[1:]+pts[:1]))
    if abs(area)<1e-12:raise ValueError('Empty garment pattern')
    order=list(range(len(pts))) if area>0 else list(reversed(range(len(pts))))
    def side(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def inside(p,a,b,c):return min(side(a,b,p),side(b,c,p),side(c,a,p))>=-1e-12
    tris=[]
    while len(order)>3:
        for j,b in enumerate(order):
            a,c=order[j-1],order[(j+1)%len(order)]
            if side(pts[a],pts[b],pts[c])<=1e-12:continue
            if any(inside(pts[k],pts[a],pts[b],pts[c]) for k in order if k not in (a,b,c)):continue
            tris.append((a,b,c));order.pop(j);break
        else:raise ValueError('Non-simple garment pattern')
    tris.append(tuple(order));return tris


def hanging_garment(w,d,h):
    """A sewn coat cutting pattern, thin front/back cloth and folded seam walls.

    Sleeves join the shoulder in the actual pattern; the neckline, cuffs and
    hem remain open. Meshes are physical cloth skins, never upholstery boxes.
    All dimensions stay inside the pre-existing hanging-coat envelope.
    """
    outline=[(-.32,.04),(.32,.04),(.315,.33),(.27,.58),(.285,.60),(.34,.27),(.45,.245),(.46,.30),(.405,.68),(.32,.77),(.23,.80),(.125,.81),(.105,.77),(0,.705),(-.105,.77),(-.125,.81),(-.23,.80),(-.32,.77),(-.405,.68),(-.46,.30),(-.45,.245),(-.34,.27),(-.285,.60),(-.27,.58),(-.315,.33)]
    points=[(x*w,z*h) for x,z in outline];tris=triangulate_polygon(points)
    # Subdivide the actual cutting pattern uniformly so folds are curved
    # surfaces with stable UVs, rather than a triangle-sized shading gradient.
    for _ in range(3):
        mids={};new=[]
        def mid(a,b):
            key=tuple(sorted((a,b)))
            if key not in mids:mids[key]=len(points);points.append(tuple((x+y)/2 for x,y in zip(points[a],points[b])))
            return mids[key]
        for a,b,c in tris:
            ab,bc,ca=mid(a,b),mid(b,c),mid(c,a);new += [(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)]
        tris=new
    edges={}
    for f in tris:
        for a,b in zip(f,f[1:]+f[:1]):edges.setdefault(tuple(sorted((a,b))),[]).append((a,b))
    boundary=[v[0] for v in edges.values() if len(v)==1]
    thickness=.0012
    def depth(x,z,front=True):
        # Narrow gravity folds taper towards the shoulder; sleeve and body
        # wrinkles share the same cloth, so they cannot detach from each other.
        u=x/w;v=z/h;relief=(.040*math.sin(30*u+1.2*v)+.024*math.sin(55*u-3*v))*max(.15,1-v)
        return (-1 if front else 1)*d*(.29+.055*math.sin(math.pi*v)+relief)
    parts=[]
    for front in [True,False]:
        outer=[(x,depth(x,z,front),z) for x,z in points];inner=[(x,y+(thickness if front else -thickness),z) for x,y,z in outer]
        n=len(points);fs=list(tris) if front else [tuple(reversed(f)) for f in tris]
        fs += [tuple(i+n for i in reversed(f)) for f in (tris if front else [tuple(reversed(f)) for f in tris])]
        for a,b in boundary:fs += [(a,b+n,b),(a,a+n,b+n)] if front else [(a,b,b+n),(a,b+n,a+n)]
        parts.append({'name':'front-cloth' if front else 'back-cloth','vertices':outer+inner,'faces':fs,'uv':points+points})
    # Real side/shoulder gussets are thin folded cloth. Opening segments are
    # deliberately excluded: lower hem, two cuffs, and the whole V neckline.
    open_segments={0,5,20,11,12,13,14}
    seam_paths=[]
    for i,(a,b) in enumerate(zip(outline,outline[1:]+outline[:1])):
        if i in open_segments:continue
        ax,az=a[0]*w,a[1]*h;bx,bz=b[0]*w,b[1]*h
        length=math.hypot(bx-ax,bz-az);nx,nz=-(bz-az)/length,(bx-ax)/length
        # Pattern is CCW: 1.6mm inward seam allowance, slightly inside skins.
        verts=[];steps=max(2,math.ceil(length/.025))
        for k in range(steps+1):
            t=k/steps;x=ax+(bx-ax)*t;z=az+(bz-az)*t
            for inset in [0,.0016]:
                xx,zz=x+nx*inset,z+nz*inset
                yf=depth(xx,zz,True)+thickness+.0001;yb=depth(xx,zz,False)-thickness-.0001
                verts += [(xx,yf,zz),(xx,yb,zz)]
        faces=[]
        for k in range(steps):
            a0=k*4;b0=(k+1)*4
            for q,r in [(0,1),(1,3),(3,2),(2,0)]:faces += [(a0+q,b0+q,b0+r),(a0+q,b0+r,a0+r)]
        faces += [(0,2,3),(0,3,1)];j=steps*4;faces += [(j,j+1,j+3),(j,j+3,j+2)]
        parts.append({'name':'sewn-edge-%02d'%i,'vertices':verts,'faces':faces,'uv':[(x,z) for x,y,z in verts]})
        seam_paths.append([(ax+(bx-ax)*k/steps,depth(ax+(bx-ax)*k/steps,az+(bz-az)*k/steps,True)-.0005,az+(bz-az)*k/steps) for k in range(steps+1)])
    return {'parts':parts,'outline':outline,'seam_paths':seam_paths,'thickness_m':thickness,'depth_function':depth}


def worktop_slab(bounds,holes,top,thickness):
    """One watertight slab with genuine rectangular apertures and no unit seams."""
    left,right,front,back=bounds
    if not(left<right and front<back and thickness>0):raise ValueError('Invalid slab envelope')
    for x0,x1,y0,y1 in holes:
        if not(left<x0<x1<right and front<y0<y1<back):raise ValueError('Slab aperture crosses exposed perimeter')
    xs=sorted(set([left,right]+[q for h in holes for q in h[:2]]));ys=sorted(set([front,back]+[q for h in holes for q in h[2:]]))
    verts=[];lookup={};faces=[]
    def vertex(x,y):
        k=(x,y)
        if k not in lookup:lookup[k]=len(verts);verts.append((x,y,top))
        return lookup[k]
    for x0,x1 in zip(xs,xs[1:]):
        for y0,y1 in zip(ys,ys[1:]):
            x,y=(x0+x1)/2,(y0+y1)/2
            if any(a<x<b and c<y<d for a,b,c,d in holes):continue
            a,b,c,d=[vertex(*p) for p in [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]]
            faces += [(a,b,c),(a,c,d)]
    n=len(verts);verts += [(x,y,z-thickness) for x,y,z in verts];edges={}
    for f in faces:
        for a,b in zip(f,f[1:]+f[:1]):edges.setdefault(tuple(sorted((a,b))),[]).append((a,b))
    closed=list(faces)+[tuple(i+n for i in reversed(f)) for f in faces]
    for es in edges.values():
        if len(es)==1:
            a,b=es[0];closed += [(a,b+n,b),(a,a+n,b+n)]
        elif len(es)!=2:raise ValueError('Non-manifold slab surface')
    return {'vertices':verts,'faces':closed,'holes':holes}
