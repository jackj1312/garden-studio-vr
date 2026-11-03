"""Give overlapping, coplanar wall finish prisms one owner at construction time."""
from collections import defaultdict
import math

import hb_geom as G

EPS = 1e-7
AREA_EPS = 1e-9
FACE_TOL = 0.0005  # the coplanarity tolerance used by the house integrity check


def _vertical_faces(mesh):
    """Project each vertical polygon into a canonical (along-wall, height) frame."""
    verts, faces = mesh
    for face in faces:
        if len(face) < 3:
            continue
        points = [verts[i] for i in face]
        p0 = points[0]
        # Newell's area normal also handles a collinear first triplet on a cap.
        normal = [0., 0., 0.]
        for i in range(1, len(points) - 1):
            cross = G.v3cross(G.v3sub(points[i], p0), G.v3sub(points[i+1], p0))
            for j in range(3):
                normal[j] += cross[j]
        length = math.hypot(*normal[:2])
        if length < AREA_EPS or abs(normal[2]) > length * EPS:
            continue
        nx, ny = normal[0]/length, normal[1]/length
        if nx < -EPS or (abs(nx) <= EPS and ny < 0):
            nx, ny = -nx, -ny
        key = round(nx, 8), round(ny, 8)
        nx, ny = G.unit(key)
        distances = [nx*x + ny*y for x,y,z in points]
        if max(distances)-min(distances) > EPS:
            continue
        poly = G.ccw([(-ny*x + nx*y, z) for x,y,z in points])
        yield key, distances[0], poly


def _panel(mesh, faces):
    """Only a true extrusion has matching projections on two parallel caps."""
    verts, _ = mesh
    areas = defaultdict(float)
    for axis, _, poly in faces:
        areas[axis] += G.area(poly)
    for axis in sorted(areas, key=areas.get, reverse=True):
        nx, ny = G.unit(axis)
        depths = [nx*x + ny*y for x,y,z in verts]
        low, high = min(depths), max(depths)
        if not EPS < high-low <= .02 or any(min(d-low, high-d) > EPS for d in depths):
            continue
        # A bevelled or obliquely cut prism must keep its measured edge geometry.
        caps = [set(), set()]
        for (x,y,z), d in zip(verts, depths):
            caps[d > (low+high)/2].add((round(-ny*x+nx*y, 6), round(z, 6)))
        if caps[0] != caps[1]:
            continue
        sides = [[], []]
        for k, d, poly in faces:
            if k == axis:
                sides[d > (low+high)/2].extend(G.convex_pieces(poly))
        if not all(sides):
            continue
        if abs(sum(map(G.area, sides[0]))-sum(map(G.area, sides[1]))) > AREA_EPS:
            continue
        return axis, low, high, sides[1]
    return None


def _bounds(poly):
    return min(p[0] for p in poly), min(p[1] for p in poly), max(p[0] for p in poly), max(p[1] for p in poly)


def _overlap(a, b):
    return min(a[2],b[2])-max(a[0],b[0]) > EPS and min(a[3],b[3])-max(a[1],b[1]) > EPS


def _subtract(polys, cutters):
    changed = False
    for box, cutter in cutters:
        halfplanes = G.poly_halfplanes(cutter)
        kept = []
        for poly in polys:
            if _overlap(box, _bounds(poly)) and abs(G.area(G.clip_convex(poly, halfplanes))) > AREA_EPS:
                kept.extend(G.convex_minus(poly, halfplanes, min_area=AREA_EPS))
                changed = True
            else:
                kept.append(poly)
        polys = kept
        if not polys:
            break
    return polys, changed


def _extrude(axis, low, high, polys):
    """Join all retained convex pieces, including cutouts, without internal caps."""
    from mathutils import Vector
    from mathutils.geometry import delaunay_2d_cdt
    coords, faces = [], []
    for poly in polys:
        faces.append(list(range(len(coords),len(coords)+len(poly))))
        coords.extend(Vector(p) for p in poly)
    uv, _, triangles, _, _, owners = delaunay_2d_cdt(coords, [], faces, 1, EPS, True)
    triangles = [list(t) for t,owner in zip(triangles,owners) if owner]
    return _closed_shell(axis,low,high,uv,triangles)


def _closed_shell(axis, low, high, uv, triangles):
    # Join triangle corners only through a shared edge. Two islands which
    # touch at a single coordinate keep distinct vertical edges at that point.
    parents = list(range(3*len(triangles)))
    def representative(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    edges = {}
    for index,tri in enumerate(triangles):
        if G.area([uv[i] for i in tri]) < 0:
            tri.reverse()
        for j in range(3):
            k = (j+1)%3
            a,b = tri[j],tri[k]
            c,e = 3*index+j,3*index+k
            neighbour = edges.pop((b,a),None)
            if neighbour is None:
                edges[a,b] = (c,e)
            else:
                p,q = neighbour
                parents[representative(c)] = representative(q)
                parents[representative(e)] = representative(p)
    verts2, corner_ids, by_root = [], [], {}
    for index,tri in enumerate(triangles):
        for j,vertex in enumerate(tri):
            root = representative(3*index+j)
            if root not in by_root:
                by_root[root] = len(verts2)
                verts2.append(uv[vertex])
            corner_ids.append(by_root[root])
    nx,ny = G.unit(axis)
    size = len(verts2)
    verts = [(d*nx-u*ny,d*ny+u*nx,z) for d in (low,high) for u,z in verts2]
    faces = []
    for i in range(0,len(corner_ids),3):
        tri = corner_ids[i:i+3]
        faces.extend((tuple(reversed(tri)),tuple(j+size for j in tri)))
    for c,e in edges.values():
        a,b = corner_ids[c],corner_ids[e]
        faces.append((a,b,b+size,a+size))
    return verts,faces


def _priority(part):
    name = part['id']
    surface = str(part.get('meta', {}).get('surface_id',''))
    if surface.rsplit('/',1)[-1] in ('end1','end-1') or '-end1-' in name or '-end-1-' in name:
        return 2
    return 1 if '-return-' in name else 0


def _visibility(part):
    meta = part.get('meta', {})
    layer = part.get('as_built')
    return (bool(layer),tuple(sorted(layer.get('replaces',()))) if isinstance(layer,dict) else (),
            meta.get('stage_in',1),meta.get('seq',0),meta.get('stage_out'),meta.get('seq_out'))


def deduplicate(parts):
    """Return finish atoms in input order; preserve each surviving atom's ID, material and metadata."""
    parts = list(parts)
    result = list(parts)
    owners = defaultdict(list)
    for i in sorted(range(len(parts)), key=lambda i: (_priority(parts[i]), str(parts[i]['id']), i)):
        part = parts[i]
        mesh = part.get('mesh')
        if not mesh or not mesh[0] or part.get('meta',{}).get('surface_role','wall') != 'wall':
            continue
        mask = _visibility(part)
        faces = list(_vertical_faces(mesh))
        panel = _panel(mesh, faces)
        if panel is None:
            # A U-shaped opening return stays intact. Its planar outside edge
            # still owns that strip where a lower-priority wall end meets it.
            if _priority(part) == 1:
                ranges = {}
                for axis, d, poly in faces:
                    if axis not in ranges:
                        nx,ny = G.unit(axis)
                        depths = [nx*x+ny*y for x,y,z in mesh[0]]
                        ranges[axis] = min(depths),max(depths)
                    for side, limit in enumerate(ranges[axis]):
                        if abs(d-limit) < EPS:
                            owners[mask,axis,side].extend((d,ranges[axis][1-side],_bounds(p),p)
                                                          for p in G.convex_pieces(poly))
            continue
        axis, low, high, polys = panel
        cutters = [(box,poly) for side,limit in enumerate((low,high))
                   for d,other,box,poly in owners[mask,axis,side] if abs(d-limit) < FACE_TOL
                   and min(high,max(d,other))-max(low,min(d,other)) > EPS]
        polys, changed = _subtract(polys, cutters)
        if not polys:
            result[i] = None
            continue
        if changed:
            result[i] = dict(part, mesh=_extrude(axis, low, high, polys))
        for side,limit in enumerate((low,high)):
            opposite = high if side == 0 else low
            owners[mask,axis,side].extend((limit,opposite,_bounds(p),p) for p in polys)
    return [part for part in result if part is not None]
