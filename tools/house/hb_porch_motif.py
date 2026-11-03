"""Photo-informed current porch details. Native photo is evidence, never a texture.
Motif coordinates are independent approximate tracing of closeup_20505, not survey.
"""
import math
SOURCE='project/assets/sites/front-garden-model/refs/closeup_20505.jpg'

def _bezier(a,b,c,d,segments=12):
 return [tuple((1-t)**3*a[j]+3*(1-t)**2*t*b[j]+3*(1-t)*t*t*c[j]+t**3*d[j] for j in range(2)) for t in [i/segments for i in range(segments+1)]]

def motif_paths(width,height):
 """Normalized paths inside the existing glass aperture; circles are metric-round."""
 if width<=.05 or height<=.05:raise ValueError('Porch motif needs a real glass aperture')
 def circle(u,v,r=.10):return [(u+r*math.cos(i*math.tau/20),v+r*width/height*math.sin(i*math.tau/20)) for i in range(21)]
 border=[(.09,.05),(.09,.95),(.91,.95),(.91,.05)]
 if height>width*2:
  sweep=_bezier((.12,.82),(.96,.69),(.90,.62),(.12,.49))+_bezier((.12,.49),(.09,.34),(.91,.31),(.89,.11))[1:]
  paths=[border,sweep,circle(.32,.40,.11),[(.12,.87),(.87,.98)],[(.12,.83),(.87,.94)],[(.12,.31),(.87,.35)],[(.12,.27),(.87,.31)],[(.12,.02),(.12,.17),(.87,.29)],[(.84,.02),(.84,.21)]]
 else:
  paths=[border,circle(.57,.53,.105),_bezier((.08,.20),(.16,.65),(.83,.30),(.93,.75),12),[(.13,.77),(.13,.93),(.50,.93)],[(.82,.06),(.82,.23),(.54,.23)]]
 if any(not(-1e-10<=q<=1+1e-10) for p in paths for v in p for q in v):raise ValueError('Motif exceeds aperture')
 return paths

def stroke_mesh(points,radius=.0011,sides=6):
 """Continuous round lead tube, with no independent capped cylinder at each sample."""
 points=[tuple(p) for p in points];closed=math.dist(points[0],points[-1])<1e-10
 if closed:points.pop()
 if len(points)<2 or radius<=0 or sides<3:raise ValueError('Invalid lead stroke')
 vertices=[]
 for i,p in enumerate(points):
  a=points[(i-1)%len(points)] if i or closed else p;b=points[(i+1)%len(points)] if i+1<len(points) or closed else p
  dx,dz=b[0]-a[0],b[2]-a[2];length=math.hypot(dx,dz)
  if length<1e-10:raise ValueError('Repeated lead tangent')
  vx,vz=-dz/length,dx/length
  for j in range(sides):
   theta=math.tau*j/sides;vertices.append((p[0]+vx*radius*math.sin(theta),p[1]+radius*math.cos(theta),p[2]+vz*radius*math.sin(theta)))
 faces=[]
 for i in range(len(points) if closed else len(points)-1):
  ni=(i+1)%len(points)
  for j in range(sides):faces.append((i*sides+j,i*sides+(j+1)%sides,ni*sides+(j+1)%sides,ni*sides+j))
 if not closed:faces+=[tuple(reversed(range(sides))),tuple(range((len(points)-1)*sides,len(points)*sides))]
 return {'vertices':vertices,'faces':faces,'closed':closed}

