"""Metric oak rows adapted to the studio clipped floor outlines."""
import math,hashlib,json
WIDTH=.190
LENGTH=1.900
THICKNESS=.012
BEVEL=.001
GRID=.000001
ROUGHNESSES=[.45,.525,.60]

def digest(*values):
    return int.from_bytes(hashlib.sha256('|'.join(map(str,values)).encode()).digest()[:8],'big')

def row_phase(row):
    phase=173
    if row>=0:
        for i in range(1,row+1):phase=(phase+300+digest('oak-phase',i)%1301)%1900
    else:
        for i in range(-1,row-1,-1):phase=(phase+300+digest('oak-phase',i)%1301)%1900
    return phase/1000

def stagger(a,b):
    delta=abs(row_phase(a)-row_phase(b))
    return min(delta,LENGTH-delta)

def board_bounds(row,column):
    y=row_phase(row)+column*LENGTH
    return (row*WIDTH,y,(row+1)*WIDTH,y+LENGTH)

def top_height(x,y,bounds,level):
    x0,y0,x1,y1=bounds
    distance=min(x-x0,x1-x,y-y0,y1-y)
    return level-max(0.,BEVEL-distance)


def floor_mesh(pieces,z0,z1):
    import hb_geom as G
    out=[]
    for poly in pieces:
        xs=[x for x,y in poly];ys=[y for x,y in poly]
        for row in range(math.floor(min(xs)/WIDTH),math.ceil(max(xs)/WIDTH)):
            phase=row_phase(row)
            for col in range(math.floor((min(ys)-phase)/LENGTH),math.ceil((max(ys)-phase)/LENGTH)):
                x,y,ex,ey=board_bounds(row,col)
                hp=G.poly_halfplanes([(x,y),(ex,y),(ex,ey),(x,ey)])
                part=G.clip_convex(poly,hp)
                if not part:continue
                # A bevel slopes only at a true board edge. Clipping the bevel
                # zones at room edges preserves the neighbouring board height.
                zones=[[(x+BEVEL,y+BEVEL),(ex-BEVEL,y+BEVEL),(ex-BEVEL,ey-BEVEL),(x+BEVEL,ey-BEVEL)],
                       [(x,y),(x+BEVEL,y+BEVEL),(x+BEVEL,ey-BEVEL),(x,ey)],
                       [(ex-BEVEL,y+BEVEL),(ex,y),(ex,ey),(ex-BEVEL,ey-BEVEL)],
                       [(x,y),(ex,y),(ex-BEVEL,y+BEVEL),(x+BEVEL,y+BEVEL)],
                       [(x,ey),(x+BEVEL,ey-BEVEL),(ex-BEVEL,ey-BEVEL),(ex,ey)]]
                for zone in zones:
                    clip=G.clip_convex(part,G.poly_halfplanes(G.ccw(zone)))
                    if clip:out.append(G.prism_varz(clip,lambda p:z0,lambda p:top_height(*p,(x,y,ex,ey),z1)))
    return G.merge_meshes(out)
