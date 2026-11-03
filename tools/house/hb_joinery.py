"""Joinery to the bar (Jack, 1 Nov 2026: "internal doors need to look real… down to skirtings, architraves and window boards,
these are the details that matter most"; DETAIL-CHECKLIST "Interior finish"; CORRECTIONS-LOG 183, 191). Pure Python meshes in
the drawing frame (x, y plan, z up), closed solids, built from a wall's own frame (W.point(u, c), W.n, W.full_extent_c()).

Profiles (UK typical, assumed where the spec is silent; listed in the report):
  - architrave 69 x 18 mm moulded (torus: a quirked inner edge, a rounded nose), 8 mm margin showing the lining, mitred heads;
  - skirting 150 x 18 mm moulded (ogee top), mitred at every corner, square-returned where it stops against an architrave;
  - window board 25 mm MDF, 12.5 mm bullnose, 25 mm proud of the plaster, horns 35 mm past each reveal (notched round them);
  - internal door: 4-panel shaker leaf 35 mm (stiles 100, top rail 100, bottom rail 200, mid rails 70, panels 6 mm recessed each
    face), lining full wall depth x 30 mm, 12 x 38 mm stops on the closing side, 3 x 76 mm butt hinges (150 from the top, 230
    from the bottom, one centred), lever on rose both faces at 1.0 m (50 mm rose, 125 mm lever), ~3 mm gaps, 8 mm under the leaf.
Every sweep is an offset of a path by each profile point, so corners are true mitres."""
import math

ARCH = [(0.0, 0.0), (0.0, 0.006), (0.004, 0.0095), (0.009, 0.0125), (0.016, 0.0145), (0.028, 0.0155), (0.042, 0.0165),
        (0.052, 0.018), (0.059, 0.0176), (0.064, 0.0158), (0.0675, 0.0125), (0.069, 0.008), (0.069, 0.0)]
SKIRT = [(0.0, 0.0), (0.018, 0.0), (0.018, 0.118), (0.0172, 0.126), (0.0148, 0.132), (0.0118, 0.136), (0.0105, 0.141),
         (0.0085, 0.1455), (0.0055, 0.1485), (0.0025, 0.1498), (0.0, 0.150)]


def _isect(p, d, q, e):
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-12: return None
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + d[0] * t, p[1] + d[1] * t)


def offset_path(P, w, closed=False):
    """2D polyline offset by w to the LEFT of its direction (mitred corners)"""
    n = len(P); out = []
    segs = []
    for i in range(n if closed else n - 1):
        a, b = P[i], P[(i + 1) % n]
        L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1e-9
        d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L); nl = (-d[1], d[0])
        segs.append(((a[0] + nl[0] * w, a[1] + nl[1] * w), d))
    for i in range(n):
        if not closed and i == 0: out.append(segs[0][0]); continue
        if not closed and i == n - 1:
            p, d = segs[-1]; L = math.hypot(P[-1][0] - P[-2][0], P[-1][1] - P[-2][1]); out.append((p[0] + d[0] * L, p[1] + d[1] * L)); continue
        s0, s1 = segs[i - 1], segs[i % len(segs)]
        q = _isect(s0[0], s0[1], s1[0], s1[1])
        out.append(q if q is not None else s1[0])
    # On a return shorter than the mitre setback the front edge cannot
    # run backwards. End that profile ring at the adjoining mitre.
    for i in range(n if closed else n-1):
        j=(i+1)%n
        dx,dy=P[j][0]-P[i][0],P[j][1]-P[i][1]
        if (out[j][0]-out[i][0])*dx+(out[j][1]-out[i][1])*dy >= -1e-10:continue
        if not closed and i==0:out[i]=out[j]
        elif not closed and j==n-1:out[j]=out[i]
        else:
            joint=((out[i][0]+out[j][0])/2,(out[i][1]+out[j][1])/2)
            out[i]=out[j]=joint
    return out


def sweep(P2, prof, to3d, closed=False):
    """P2: path in a 2D frame; prof: [(w, d)] closed profile (w = offset left of the path, d = the third axis);
    to3d(x2, y2, d) -> 3D point. Returns a closed (V, F)."""
    rings = [offset_path(P2, w, closed) for (w, d) in prof]
    m = len(P2); k = len(prof)
    V = [to3d(rings[j][i][0], rings[j][i][1], prof[j][1]) for j in range(k) for i in range(m)]
    F = []
    idx = lambda j, i: j * m + i
    for j in range(k):
        j2 = (j + 1) % k
        for i in range(m if closed else m - 1):
            i2 = (i + 1) % m
            F.append((idx(j, i), idx(j, i2), idx(j2, i2), idx(j2, i)))
    if not closed:
        F.append(tuple(idx(j, 0) for j in range(k)))
        F.append(tuple(idx(j, m - 1) for j in reversed(range(k))))
    return V, F


def box_uc(W, ua, ub, za, zb, ca, cb):
    P = [W.point(ua, ca), W.point(ub, ca), W.point(ub, cb), W.point(ua, cb)]
    V = [(p[0], p[1], za) for p in P] + [(p[0], p[1], zb) for p in P]
    return V, [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def cyl_uc(W, u, c, za, zb, r, seg=12, axis="z"):
    """a small cylinder in the wall frame: axis z (vertical) or 'c' (across the wall)"""
    V, F = [], []
    for k, t in enumerate((za, zb)):
        for i in range(seg):
            a = 2 * math.pi * i / seg
            if axis == "z":
                p = W.point(u + r * math.cos(a), c + r * math.sin(a)); V.append((p[0], p[1], t))
            else:   # along c from za to zb (here za/zb are c values, u/c(=z) centre)
                p = W.point(u + r * math.cos(a), t); V.append((p[0], p[1], c + r * math.sin(a)))
    F.append(tuple(reversed(range(seg)))); F.append(tuple(range(seg, 2 * seg)))
    for i in range(seg): F.append((i, (i + 1) % seg, seg + (i + 1) % seg, seg + i))
    return V, F


def architrave(W, u0, u1, zf, zh, cface, sgn):
    """moulded architrave round an opening on the wall face at c = cface, proud toward sgn*n: legs from the floor zf up,
    head at zh; u0/u1/zh are the LINING's inner edges (the 8 mm margin is applied here)"""
    m = 0.008
    path = [(u0 + m, zf), (u0 + m, zh - m), (u1 - m, zh - m), (u1 - m, zf)]     # (u, z): left of travel = away from the opening
    def to3d(u, z, d):
        p = W.point(u, cface + sgn * d); return (p[0], p[1], z)
    return sweep(path, ARCH, to3d)


def skirting_run(P, prof_room_side, zf):
    """plan polyline P (wall face line, room on the LEFT of travel) -> moulded skirting solid from the floor zf"""
    return sweep(P, SKIRT if prof_room_side else SKIRT, lambda x, y, h: (x, y, zf + h))


def shaker_leaf(W, ua, ub, za, zb, c0, c1):
    """4-panel shaker leaf between u ua..ub, z za..zb, thickness c0..c1 (panels recessed 6 mm each face)"""
    stile=.09; rail=.12; muntin=.07; mid=za+(zb-za)*.48
    left,right=ua+stile,ub-stile;centre=(ua+ub)/2
    parts=[box_uc(W,ua,left,za,zb,c0,c1),box_uc(W,right,ub,za,zb,c0,c1)]
    for low,high in ((za,za+rail),(mid-rail/2,mid+rail/2),(zb-rail,zb)):
        parts.append(box_uc(W,left,right,low,high,c0,c1))
    for low,high in ((za+rail,mid-rail/2),(mid+rail/2,zb-rail)):
        parts.append(box_uc(W,centre-muntin/2,centre+muntin/2,low,high,c0,c1))
        for x0,x1 in ((left,centre-muntin/2),(centre+muntin/2,right)):
            parts.append(box_uc(W,x0,x1,low,high,c0+.006,c1-.006))
    return parts

def porch_leaf(w,lo,hi,z0,z1,c):
    """Photo-led three-light composite leaf, constructed to this measured opening."""
    from hb_porch_motif import stroke_mesh,motif_paths
    width=hi-lo;height=z1-z0;middle=(lo+hi)/2;gw=.23*width;a,b=middle-gw/2,middle+gw/2
    leaf=[box_uc(w,lo,a,z0,z1,c-.0225,c+.0225),box_uc(w,b,hi,z0,z1,c-.0225,c+.0225)]
    glass=[];leading=[];last=z0
    for low,high in ((.15,.245),(.30,.74),(.795,.895),(1,1)):
        low=z0+height*low;high=z0+height*high
        leaf.append(box_uc(w,a,b,last,low,c-.0225,c+.0225))
        if high>low:
            glass.append(box_uc(w,a,b,low,high,c-.006,c+.006))
            for side in (-1,1):
                yy=c+side*.0068
                for path in motif_paths(gw,high-low):
                    stroke=stroke_mesh([(a+u*gw,yy,low+v*(high-low)) for u,v in path])
                    leading.append(([( *w.point(u,t),z) for u,t,z in stroke['vertices']],stroke['faces']))
        last=high
    return leaf,glass,leading


def door_ironmongery(W, ua, ub, za, hinge_u, c0, c1, zh_leaf):
    """(hinges, handles): 3 butt hinges on the hinge edge; lever on rose both faces near the free edge at 1.0 m"""
    free_u = ub if abs(hinge_u - ua) < abs(hinge_u - ub) else ua
    sgn_u = 1 if free_u > hinge_u else -1
    hinges = []
    for zc in (zh_leaf - 0.150 - 0.038, za + 0.230 + 0.038, (zh_leaf + za) / 2):
        hinges.append(cyl_uc(W, hinge_u, (c0 + c1) / 2 + 0.0, zc - 0.038, zc + 0.038, 0.0065, 10))   # knuckle on the hinge axis
    handles = []
    hu = free_u - sgn_u * 0.060; zc = za + 1.0 - (za - za)          # lever centre 1.0 m above the floor line under the leaf
    for face, s in ((c1, 1), (c0, -1)):
        handles.append(cyl_uc(W, hu, za + 1.0, face, face + s * 0.008, 0.025, 16, axis="c"))           # rose
        handles.append(cyl_uc(W, hu, za + 1.0, face + s * 0.008, face + s * 0.058, 0.009, 10, axis="c"))  # neck
        # lever: from the neck toward the hinge side? (UK levers point to the hinge side, i.e. away from the free edge)
        la, lb = sorted((hu, hu - sgn_u * 0.125))
        handles.append(box_uc(W, la, lb, za + 1.0 - 0.009, za + 1.0 + 0.009, face + s * 0.045, face + s * 0.063) if s > 0 else
                       box_uc(W, la, lb, za + 1.0 - 0.009, za + 1.0 + 0.009, face + s * 0.063, face + s * 0.045))
    return hinges, handles


def window_board(W, u0, u1, zs, c_frame_in, c_face, sgn, horn=0.035, proj=0.025, t=0.025, r=0.0125, n_round=5):
    """window board under an internal window: top at zs + t; from the frame's inner face c_frame_in out past the plaster face
    c_face by proj (toward sgn*n); horns past each reveal, notched round them (the horns stop at the plaster face)"""
    cf, cw, cp = c_frame_in, c_face, c_face + sgn * proj
    # plan outline (u, c) going round: frame edge, reveal, horn, front
    outline = [(u0, cf), (u1, cf), (u1, cw), (u1 + horn, cw), (u1 + horn, cp), (u0 - horn, cp), (u0 - horn, cw), (u0, cw)]
    front = {4, 5}                        # indices on the front edge (bullnosed)
    zc = zs + t / 2
    levels = []
    for k in range(n_round + 1):
        a = -math.pi / 2 + math.pi * k / n_round
        z = zc + r * math.sin(a); inset = r - r * math.cos(a)
        ring = []
        for i, (u, c) in enumerate(outline):
            cc = c - sgn * inset if i in front else c
            p = W.point(u, cc); ring.append((p[0], p[1], z))
        levels.append(ring)
    m = len(outline)
    V = [p for ring in levels for p in ring]
    F = [tuple(reversed(range(m))), tuple(range(n_round * m, n_round * m + m))]
    for k in range(n_round):
        for i in range(m):
            i2 = (i + 1) % m
            F.append((k * m + i, k * m + i2, (k + 1) * m + i2, (k + 1) * m + i))
    return V, F
