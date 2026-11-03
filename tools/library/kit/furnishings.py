"""Garden Studio metric furnishings. X width, Y depth, Z up, front -Y. Derived from Jack’s independent Battle Road kit."""
from __future__ import annotations

import json
import math
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
CATALOGUE = ROOT / "materials.json"
TAU = 2 * math.pi

DEFAULTS = {
    "sofa": (2.22, 0.97, 0.84), "armchair": (0.79, 0.84, 0.82),
    "dining_chair": (0.49, 0.56, 0.81), "bed": (1.68, 2.18, 1.09),
    "single_bed": (1.00, 2.12, 1.02), "coffee_table": (1.15, 0.65, 0.36),
    "dining_table": (1.85, 0.91, 0.75), "side_table": (0.46, 0.46, 0.49),
    "rug": (2.40, 1.70, 0.012), "cushion": (0.47, 0.47, 0.15),
    "throw": (1.15, 0.76, 0.04), "curtain": (0.65, 0.14, 2.20),
    "roman_blind": (1.50, 0.09, 0.24), "kitchen_base": (0.60, 0.62, 0.91),
    "kitchen_wall": (0.60, 0.33, 0.72), "kitchen_tall": (0.60, 0.62, 2.15),
    "oven": (0.60, 0.59, 0.60), "fridge": (0.60, 0.65, 1.88),
    "hob": (0.59, 0.52, 0.014), "sink": (0.54, 0.46, 0.21),
    "tap": (0.17, 0.25, 0.35), "basin": (0.58, 0.44, 0.16),
    "vanity": (0.80, 0.49, 0.85), "toilet": (0.37, 0.66, 0.80),
    "bath": (0.75, 1.70, 0.57), "shower": (0.90, 0.90, 2.05),
    "radiator": (0.95, 0.10, 0.60), "towel_rail": (0.50, 0.09, 1.10),
    "pendant": (0.36, 0.36, 0.75), "floor_lamp": (0.36, 0.36, 1.53),
    "table_lamp": (0.29, 0.29, 0.46), "wall_light": (0.13, 0.17, 0.28),
    "downlight": (0.085, 0.085, 0.011), "book_stack": (0.26, 0.19, 0.12),
    "books": (0.34, 0.21, 0.28), "vase": (0.18, 0.18, 0.28),
    "bowl": (0.29, 0.29, 0.09), "plant": (0.44, 0.44, 0.72),
    "art": (0.55, 0.035, 0.75), "mirror": (0.58, 0.035, 0.78),
    "wardrobe": (1.60, 0.60, 2.15), "dresser": (1.15, 0.44, 0.79),
    "desk": (1.15, 0.58, 0.75), "bench": (1.15, 0.38, 0.46),
    "stove": (0.45, 0.38, 0.60), "towel": (0.48, 0.28, 0.045),
}
FIXED = {
    "kitchen_base", "kitchen_wall", "kitchen_tall", "oven", "hob", "sink",
    "tap", "basin", "vanity", "toilet", "bath", "shower", "radiator", "fridge", "curtain",
    "towel_rail", "pendant", "wall_light", "downlight", "roman_blind", "stove",
}


def _linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgba(hex_color):
    text = hex_color.lstrip("#")
    return tuple(_linear(int(text[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (1.0,)


def _catalogue():
    return json.loads(CATALOGUE.read_text())


def _image(path, colour=False):
    image = bpy.data.images.load(str(ROOT / path), check_existing=True)
    image.colorspace_settings.name = "sRGB" if colour else "Non-Color"
    return image


def palette(overrides=None):
    """Create/reuse independent materials. Texture UVs are stored in mesh metres.

    Direct image links retain glTF-exportable colour, roughness and tangent-space
    normal channels. No procedural shader texture or light bake is required.
    """
    definitions = _catalogue()["materials"]
    result = {}
    for key, spec in definitions.items():
        name = "BRI.MAT." + key
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = bpy.data.materials.new(name)
            mat.use_nodes = True
            mat.diffuse_color = _rgba(spec.get("colour", "#e3ded4"))
            mat["asset_source_id"] = spec.get("source_id", "independent-procedural")
            mat["texture_size_m"] = float(spec.get("repeat_m", 1.0))
            mat["physical_repeat_m"] = float(spec.get("physical_repeat_m", spec.get("repeat_m", 1.0)))
            if spec.get("source_url"): mat["source_url"] = spec["source_url"]
            if spec.get("review_note"): mat["appearance_limit"] = spec["review_note"]
            mat["licence"] = spec.get("licence", "original-work")
            for field in ["albedo_gain", "albedo_gain_space", "albedo_gain_source", "albedo_source_max_linear"]:
                if field in spec: mat[field] = spec[field]
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            bsdf.inputs["Base Color"].default_value = mat.diffuse_color
            bsdf.inputs["Roughness"].default_value = spec.get("roughness", 0.55)
            bsdf.inputs["Metallic"].default_value = spec.get("metallic", 0.0)
            if "IOR" in bsdf.inputs:
                bsdf.inputs["IOR"].default_value = spec.get("ior", 1.5)
            if "Sheen Weight" in bsdf.inputs:
                bsdf.inputs["Sheen Weight"].default_value = spec.get("sheen", 0.0)
                bsdf.inputs["Sheen Roughness"].default_value = 0.65
            if "Coat Weight" in bsdf.inputs:
                bsdf.inputs["Coat Weight"].default_value = spec.get("coat", 0.0)
            maps = spec.get("maps", {})
            for channel, socket in (("colour", "Base Color"), ("roughness", "Roughness"), ("metalness", "Metallic")):
                if channel in maps:
                    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
                    node.name = channel
                    node.image = _image(maps[channel], colour=channel == "colour")
                    mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs[socket])
            if "normal" in maps:
                node = mat.node_tree.nodes.new("ShaderNodeTexImage")
                node.name = "normalGL"
                node.image = _image(maps["normal"])
                normal = mat.node_tree.nodes.new("ShaderNodeNormalMap")
                normal.inputs["Strength"].default_value = spec.get("normal_strength", 0.35)
                mat.node_tree.links.new(node.outputs["Color"], normal.inputs["Color"])
                mat.node_tree.links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])
            # Standard glTF occlusion socket, retained if an AO source is selected.
            if "occlusion" in maps:
                group = bpy.data.node_groups.get("glTF Material Output")
                if group is None:
                    group = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
                    group.interface.new_socket(name="Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
                output = mat.node_tree.nodes.new("ShaderNodeGroup")
                output.node_tree = group
                ao = mat.node_tree.nodes.new("ShaderNodeTexImage")
                ao.image = _image(maps["occlusion"])
                mat.node_tree.links.new(ao.outputs["Color"], output.inputs["Occlusion"])
            repeat_xy=spec.get("physical_repeat_xy_m")
            if repeat_xy is not None:
                if len(repeat_xy)!=2 or any(not math.isfinite(float(v)) or float(v)<=0 for v in repeat_xy):
                    raise ValueError("physical_repeat_xy_m needs two finite positive metre lengths")
                repeat=float(spec.get("repeat_m",1.0))
                uv_node=mat.node_tree.nodes.new("ShaderNodeTexCoord")
                uv_node.name="Metric UV coordinates"
                mapping=mat.node_tree.nodes.new("ShaderNodeMapping")
                mapping.name="Measured physical repeat XY"
                mapping.vector_type='POINT'
                mapping.inputs['Scale'].default_value=(repeat/float(repeat_xy[0]),repeat/float(repeat_xy[1]),1.0)
                mat.node_tree.links.new(uv_node.outputs['UV'],mapping.inputs['Vector'])
                for texture in [n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE']:
                    mat.node_tree.links.new(mapping.outputs['Vector'],texture.inputs['Vector'])
                mat['physical_repeat_xy_m']=[float(v) for v in repeat_xy]
            if spec.get("emission"):
                socket = "Emission Color" if "Emission Color" in bsdf.inputs else "Emission"
                bsdf.inputs[socket].default_value = _rgba(spec["emission"])
                if "Emission Strength" in bsdf.inputs:
                    bsdf.inputs["Emission Strength"].default_value = spec.get("emission_strength", 1)
            if spec.get("alpha", 1) < 1:
                bsdf.inputs["Alpha"].default_value = spec["alpha"]
                if hasattr(mat, "surface_render_method"):
                    mat.surface_render_method = "DITHERED"
                elif hasattr(mat, "blend_method"):
                    mat.blend_method = "BLEND"
                mat.use_backface_culling = False
        result[key] = mat
    if overrides:
        result.update(overrides)
    return result


def _uv_project(mesh, repeat=1.0, grain="x"):
    """Six-plane unwrap with metric repeat, independent of object scale."""
    uv = mesh.uv_layers.new(name="UVMap")
    for face in mesh.polygons:
        axis = max(range(3), key=lambda k: abs(face.normal[k]))
        axes = ((1, 2), (0, 2), (0, 1))[axis]
        if grain == "z" and 2 in axes:
            axes = (2, next(a for a in axes if a != 2))
        for li in face.loop_indices:
            v = mesh.vertices[mesh.loops[li].vertex_index].co
            uv.data[li].uv = (v[axes[0]] / repeat, v[axes[1]] / repeat)


def apple_geometry(dimensions=(.081, .079, .076), phase=0.0, rings=20, sides=40):
    """Closed organic fruit, not an upholstery superellipsoid; exact metre bounds.

    Polar caps are single vertices and shoulders have a restrained five-lobed
    silhouette. The top and basal dimples remain real geometry at this scale.
    """
    if len(dimensions) != 3 or min(dimensions) <= 0 or rings < 8 or sides < 12:
        raise ValueError("Apple requires positive dimensions and adequate rings/sides")
    def point(theta, phi):
        c = math.cos(theta)
        radial = math.sin(theta) * (1 + .08*c - .03*c*c)
        radial *= 1 + .025*math.cos(5*phi + phase)*abs(c)**3
        z = c - .12*math.exp(-(theta/.24)**2) + .06*math.exp(-((math.pi-theta)/.22)**2)
        z += .008*math.cos(5*phi + phase)*math.sin(theta)**2*c**3
        return (radial*math.cos(phi), radial*math.sin(phi), z)
    verts = [point(0, 0)]
    verts += [point(math.pi*i/rings, 2*math.pi*j/sides)
              for i in range(1, rings) for j in range(sides)]
    verts.append(point(math.pi, 0)); bottom = len(verts)-1
    lower = [min(p[a] for p in verts) for a in range(3)]
    upper = [max(p[a] for p in verts) for a in range(3)]
    verts = [tuple(((p[a]-lower[a])/(upper[a]-lower[a])-.5)*dimensions[a]
                   for a in range(3)) for p in verts]
    faces = [(0, 1+j, 1+(j+1)%sides) for j in range(sides)]
    for i in range(rings-2):
        a, b = 1+i*sides, 1+(i+1)*sides
        faces += [(a+j, b+j, b+(j+1)%sides, a+(j+1)%sides) for j in range(sides)]
    a = 1+(rings-2)*sides
    faces += [(a+j, bottom, a+(j+1)%sides) for j in range(sides)]
    return verts, faces


def fruit_bowl_inner_height(x, y, width, depth, height=.055, sides=64):
    """Exact convex inner profile of _vase(b, bowl=True), including faceted rings."""
    if min(width, depth, height) <= 0 or sides < 3:
        raise ValueError("Invalid bowl dimensions")
    y *= width/depth
    # A polygon ring is inscribed, so circular radius alone understates its wall.
    r = max(x*math.cos(2*math.pi*(j+.5)/sides) + y*math.sin(2*math.pi*(j+.5)/sides)
            for j in range(sides)) / math.cos(math.pi/sides)
    profile = [(0, height*.13), (width*.25, height*.16),
               (width*.43, height*.78), (width*.47, height)]
    if r > profile[-1][0] + 1e-9:
        raise ValueError("Fruit projects beyond the bowl inner rim")
    for (ra, za), (rb, zb) in zip(profile, profile[1:]):
        if r <= rb:
            return za + (zb-za)*(r-ra)/(rb-ra)
    return height


def fruit_bowl_seating(verts, x, y, width, depth, clearance=.0004):
    """Seat the rounded fruit on the real convex inner bowl, with no floating datum."""
    if not 0 <= clearance <= .001:
        raise ValueError("Fruit support clearance must stay sub-millimetre")
    return max(fruit_bowl_inner_height(x+v[0], y+v[1], width, depth)-v[2]
               for v in verts) + clearance


class _Builder:
    def __init__(self, kind, name, dims, collection, materials, fixed, options):
        self.kind, self.name = kind, name
        self.w, self.d, self.h = dims
        self.collection, self.m, self.options = collection, materials, options
        self.root = bpy.data.objects.new(name, None)
        collection.objects.link(self.root)
        self.root.empty_display_type = "PLAIN_AXES"
        self.root.empty_display_size = 0.08
        self.objects = [self.root]
        self.fixed = fixed
        self.tag(self.root)
        self.root["requested_dimensions_m"] = list(dims)
        self.root["local_front"] = "-Y"
        self.root["anchor"] = "floor_bottom_centre"
        self.root["prototype_revision"] = 3

    def tag(self, obj, collide=True):
        obj["studio_asset"] = True
        obj["asset_source_id"] = "BRI." + self.kind
        obj["asset_kind"] = self.kind
        obj["asset_id"] = self.name
        obj["furnishing"] = not self.fixed
        obj["loose"] = not self.fixed
        obj["fixed"] = self.fixed
        obj["collide"] = bool(collide)
        obj["collider"] = bool(collide)
        obj["room_id"] = self.options.get("room_id", "")
        obj["walkable"] = False
        obj["generator"] = "tools/library/kit/furnishings.py"

    def mesh(self, suffix, verts, faces, mat="white", smooth=False, grain="x", collide=True, uv=None):
        mesh = bpy.data.meshes.new(self.name + "." + suffix)
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        # Explicit normal consistency, including authored revolved and draped forms.
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        for p in mesh.polygons:
            p.use_smooth = smooth
        material = self.m[mat] if isinstance(mat, str) else mat
        mesh.materials.append(material)
        if uv is None:
            _uv_project(mesh, float(material.get("texture_size_m", 1)), grain)
        else:
            layer = mesh.uv_layers.new(name="UVMap")
            for loop in mesh.loops:
                layer.data[loop.index].uv = uv[loop.vertex_index]
        obj = bpy.data.objects.new(self.name + "." + suffix, mesh)
        self.collection.objects.link(obj)
        obj.parent = self.root
        self.tag(obj, collide)
        obj["material_source_id"] = material.get("asset_source_id", "independent-procedural")
        self.objects.append(obj)
        return obj

    def box(self, suffix, dims, centre, mat="white", bevel=0.004, rotation=None, grain="x"):
        x, y, z = (v / 2 for v in dims)
        verts = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
        faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
        obj = self.mesh(suffix, verts, faces, mat, grain=grain)
        if bevel:
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, min(dims) * 0.45), segments=3, affect="EDGES")
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            bm.to_mesh(obj.data)
            bm.free()
            # Recreate metric UVs for newly added bevel loops.
            for layer in list(obj.data.uv_layers):
                obj.data.uv_layers.remove(layer)
            obj.data.update()
            _uv_project(obj.data, float(obj.data.materials[0].get("texture_size_m", 1)), grain)
            for face in obj.data.polygons:
                face.use_smooth = max(abs(v) for v in face.normal) < 0.999
        obj.location = centre
        if rotation:
            obj.rotation_euler = rotation
        return obj

    def tube(self, suffix, points, radius, mat="metal", closed=False, sides=8, collide=False):
        pts = [Vector(p) for p in points]
        n = len(pts)
        verts, uv = [], []
        length = 0.0
        repeat = float(self.m[mat].get("texture_size_m", 1))
        if n < 2 or any((pts[i]-pts[i-1]).length < 1e-8 for i in range(1,n)):
            raise ValueError("Tube path needs distinct consecutive points")
        previous_tangent = previous_a = None
        for i, point in enumerate(pts):
            prev, nxt = pts[(i-1) % n], pts[(i+1) % n]
            if not closed and i == 0: prev = point - (nxt-point)
            if not closed and i == n-1: nxt = point + (point-prev)
            if (nxt-prev).length < 1e-8:
                raise ValueError("Tube path cannot reverse at one ring")
            tangent = (nxt-prev).normalized()
            if previous_tangent is None:
                helper = Vector((0, 0, 1)) if abs(tangent.z) < 0.95 else Vector((1, 0, 0))
                a = tangent.cross(helper).normalized()
            else:
                # Parallel transport keeps the same angular correspondence at
                # elbows; choosing a new helper at each ring can twist by180°.
                a = previous_tangent.rotation_difference(tangent) @ previous_a
                a = (a - tangent*a.dot(tangent)).normalized()
            b = tangent.cross(a).normalized()
            previous_tangent, previous_a = tangent, a
            if i: length += (point-pts[i-1]).length
            for j in range(sides):
                angle = TAU*j/sides
                verts.append(tuple(point + radius*(math.cos(angle)*a + math.sin(angle)*b)))
                uv.append((length/repeat, j/sides*TAU*radius/repeat))
        faces = []
        for i in range(n if closed else n-1):
            ni = (i+1) % n
            for j in range(sides):
                nj = (j+1) % sides
                faces.append((i*sides+j, i*sides+nj, ni*sides+nj, ni*sides+j))
        if not closed:
            faces.extend([tuple(reversed(range(sides))), tuple((n-1)*sides+j for j in range(sides))])
        return self.mesh(suffix, verts, faces, mat, True, collide=collide, uv=uv)

    def rod(self, suffix, start, end, radius, mat="oak", radius_top=None, sides=16):
        start, end = Vector(start), Vector(end)
        t = (end-start).normalized()
        helper = Vector((0,0,1)) if abs(t.z)<0.95 else Vector((1,0,0))
        u, v = t.cross(helper).normalized(), None
        v = t.cross(u).normalized()
        radii = (radius, radius if radius_top is None else radius_top)
        verts = [tuple(p+r*(math.cos(TAU*j/sides)*u+math.sin(TAU*j/sides)*v)) for p,r in zip((start,end),radii) for j in range(sides)]
        faces = [(j,(j+1)%sides,(j+1)%sides+sides,j+sides) for j in range(sides)]
        faces += [tuple(reversed(range(sides))),tuple(range(sides,2*sides))]
        return self.mesh(suffix,verts,faces,mat,True,grain="z")

    def lathe(self, suffix, profile, centre=(0,0,0), mat="ceramic", segments=48, ellipse=1.0):
        # Continuous radius/Z cross-section. A repeated first point means a
        # hollow closed section (e.g. shade): do not fill its central opening.
        profile = list(profile)
        closed_section = profile[0] == profile[-1]
        if closed_section:
            profile.pop()
        verts, rings = [], []
        for r, z in profile:
            if abs(r) < 1e-10:
                rings.append([len(verts)])
                verts.append((centre[0], centre[1], centre[2] + z))
            else:
                ids = []
                for i in range(segments):
                    ids.append(len(verts))
                    a = TAU * i / segments
                    verts.append((centre[0]+r*math.cos(a), centre[1]+r*math.sin(a)*ellipse, centre[2]+z))
                rings.append(ids)
        faces = []
        for k in range(len(rings) if closed_section else len(rings)-1):
            a, c = rings[k], rings[(k+1) % len(rings)]
            if len(a) == 1 and len(c) == 1:
                continue
            for i in range(segments):
                ni = (i+1) % segments
                if len(a) == 1:
                    faces.append((a[0], c[ni], c[i]))
                elif len(c) == 1:
                    faces.append((a[i], a[ni], c[0]))
                else:
                    faces.append((a[i], a[ni], c[ni], c[i]))
        if not closed_section:
            if len(rings[0]) > 1: faces.append(tuple(reversed(rings[0])))
            if len(rings[-1]) > 1: faces.append(tuple(rings[-1]))
        return self.mesh(suffix, verts, faces, mat, True)

    def soft(self, suffix, dims, centre, mat="upholstery", puff=0.35, rotation=None, seam=True):
        """Closed superellipsoid with compressed border, modest irregular upholstery."""
        a,b,c=(v/2 for v in dims)
        rings, sides = 16, 48
        verts = []
        exy, ez = 0.24, 0.46
        def sp(value,power): return math.copysign(abs(value)**power,value)
        # Avoid degenerate poles: single cap vertices close the tiny end rings.
        for i in range(rings+1):
            phi=-math.pi/2+0.002+(math.pi-0.004)*i/rings
            z=c*sp(math.sin(phi),ez)
            radial=abs(math.cos(phi))**ez
            for j in range(sides):
                angle=TAU*j/sides
                x=a*radial*sp(math.cos(angle),exy)
                y=b*radial*sp(math.sin(angle),exy)
                edge=(abs(x/a)**8+abs(y/b)**8)/2
                ripple=puff*0.004*edge*math.sin(angle*9+phi*5)
                z2=z+ripple*math.sin(phi)
                verts.append((x,y,z2))
        faces=[]
        for i in range(rings):
            for j in range(sides):
                nj=(j+1)%sides
                faces.append((i*sides+j,i*sides+nj,(i+1)*sides+nj,(i+1)*sides+j))
        faces += [tuple(reversed(range(sides))),tuple(rings*sides+j for j in range(sides))]
        obj=self.mesh(suffix,verts,faces,mat,True)
        obj.location=centre
        if rotation: obj.rotation_euler=rotation
        if seam:
            points=[]
            # Equatorial piping follows cushion shell exactly, never a floating rectangle.
            for j in range(sides):
                t=TAU*j/sides
                points.append((a*1.002*sp(math.cos(t),exy),b*1.002*sp(math.sin(t),exy),0))
            pipe=self.tube(suffix+"-welt",points,0.0018,"seam",True,6)
            pipe.location=centre
            if rotation: pipe.rotation_euler=rotation
        return obj

    def cloth(self,suffix,w,d,centre,mat="linen",edge_drop=0.0,fold=0.012,seed=0.0,steps=(32,42),thickness=.006,support_width=None,support_front=None,support_z=None,support_profile=None,fold_style="natural"):
        """Closed cloth with real thickness and drapes outside specified support.

        w/d describe unfolded cloth lengths. support_width is centred on centre.x;
        support_front is an absolute local Y edge. A quarter-round bend transitions
        to a vertical fall without driving the cloth through its supporting mesh.
        """
        nx,ny=steps
        top_points,uv,drops=[],[],[]
        repeat=float(self.m[mat].get("texture_size_m",1))
        def drape(excess):
            # A loose textile hangs with a small outward flare. Keeping an
            # actual slope also prevents two-edge corner cells collapsing to
            # a vertical line. The bend radius exceeds the physical thickness.
            radius=max(.024,thickness*1.2)
            angle=min(excess/radius,math.pi/2)
            fall=max(0,excess-radius*math.pi/2)
            horizontal=radius*math.sin(angle)+.12*fall
            drop=radius*(1-math.cos(angle))+fall
            return horizontal,drop
        for j in range(ny+1):
            v=j/ny; raw_y=centre[1]+(v-.5)*d
            for i in range(nx+1):
                u=i/nx; raw_x=(u-.5)*w
                x=centre[0]+raw_x;y=raw_y;dropx=dropy=0.0
                if support_width is not None:
                    excess=max(0,abs(raw_x)-support_width/2)
                    if excess:
                        extension,dropx=drape(excess)
                        x=centre[0]+math.copysign(support_width/2+extension,raw_x)
                if support_front is not None and raw_y<support_front:
                    extension,dropy=drape(support_front-raw_y)
                    y=support_front-extension
                if support_width is None and support_front is None and edge_drop:
                    dropx=edge_drop*max(0,(abs(u-.5)-.38)/.12)
                    dropy=edge_drop*max(0,(.12-v)/.12)
                drop=max(dropx,dropy)
                ripple=fold*(.48*math.sin(19*u+6*v+seed)+.26*math.sin(34*v-11*u+seed)+.18*math.sin(61*u+25*v))
                if fold_style=="thin":ripple=fold*(.55+.35*math.sin(9*u+2*v+seed)+.10*math.sin(17*u-3*v))
                profile_z=support_profile(x,max(y,support_front) if support_front is not None else y) if support_profile else None
                z=(profile_z+thickness if profile_z is not None else centre[2])-drop+ripple
                if support_z is not None and drop<1e-9:
                    z=max(z,support_z+.004)
                top_points.append(Vector((x,y,z)));drops.append(drop)
                uv.append((u*w/repeat,v*d/repeat))
        # Give each draping panel thickness perpendicular to its surface,
        # not vertically: a vertical offset collapses the hems of a falling
        # textile into zero-area faces. Finite differences preserve the folds.
        lower=[]
        stride=nx+1
        for j in range(ny+1):
            for i in range(nx+1):
                k=j*stride+i;p=top_points[k]
                du=top_points[j*stride+min(nx,i+1)]-top_points[j*stride+max(0,i-1)]
                dv=top_points[min(ny,j+1)*stride+i]-top_points[max(0,j-1)*stride+i]
                normal=du.cross(dv)
                if normal.length<1e-10:
                    raise ValueError("Collapsed cloth surface tangent")
                normal.normalize()
                thick=thickness*(.45+.55*max(0,1-drops[k]/.10))
                q=p-normal*thick
                if support_profile is not None and drops[k]<1e-9:
                    q.z=max(q.z,support_profile(p.x,p.y))
                if support_z is not None and drops[k]<1e-9:
                    q.x=p.x;q.y=p.y
                    q.z=support_z if thickness>=.020 else max(q.z,support_z)
                lower.append(q)
        verts=[tuple(p) for p in top_points+lower];uv=uv+uv
        layer=stride*(ny+1);faces=[]
        for k in (0,1):
            for j in range(ny):
                for i in range(nx):
                    a=k*layer+j*stride+i
                    # Explicit triangles avoid ambiguous non-planar quads at
                    # folds while retaining a closed, consistently wound shell.
                    pair=[(a,a+1,a+stride+1),(a,a+stride+1,a+stride)]
                    faces.extend(pair if k==0 else [tuple(reversed(f)) for f in pair])
        border=list(range(nx+1))+[j*stride+nx for j in range(1,ny+1)]+[ny*stride+i for i in range(nx-1,-1,-1)]+[j*stride for j in range(ny-1,0,-1)]
        for i,a in enumerate(border):
            b=border[(i+1)%len(border)]
            faces.extend([(a,b+layer,b),(a,a+layer,b+layer)])
        return self.mesh(suffix,verts,faces,mat,True,collide=False,uv=uv)


def _sofa(b):
    w,d,h=b.w,b.d,b.h
    leg=min(0.15,h*0.18)
    for sx in (-1,1):
        for sy in (-1,1):
            b.rod("leg",(sx*(w/2-0.13),sy*(d/2-0.12),0),(sx*(w/2-0.16),sy*(d/2-0.15),leg+0.02),0.021,"oak",0.026)
    if b.options.get("style") in ("modern","industrial","contemporary"):
        b.box("recessed-plinth",(w-.22,d-.21,leg),(0,0,leg/2),"black",.009)
    base=b.soft("upholstered-base",(w-0.07,d-0.06,h*0.24),(0,0,leg+h*0.12),puff=0.15,seam=False)
    arm=max(0.13,min(0.20,w*0.082))
    for s in (-1,1):
        b.soft("arm",(arm,d-0.03,h*0.54),(s*(w/2-arm/2),0,leg+h*0.35),puff=0.25,seam=False)
        if b.options.get("style") in ("traditional","country"):
            b.soft("rolled-arm",(arm*1.23,d*.97,arm*1.08),(s*(w/2-arm*.62),0,leg+h*.58),puff=.55)
    b.soft("back-frame",(w-0.16,d*0.20,h*0.62),(0,d*0.38,h*0.64),puff=0.1,seam=False)
    seatw=(w-arm*2-0.04)/2
    seatz=leg+h*0.27
    seats=[]
    for s in (-1,1):
        seats.append(b.soft("seat-cushion",(seatw-0.018,d*0.69,h*0.20),(s*(seatw/2+0.008),-d*0.075,seatz),puff=0.45))
        b.soft("back-cushion",(seatw-0.012,h*0.47,d*0.19),(s*(seatw/2+0.008),d*0.25,h*0.67),puff=0.7,rotation=(math.radians(73),0,0))
    for s,mat in ((-1,"linen"),(1,"accent")):
        b.soft("scatter",(0.39,0.39,0.13),(s*(w/2-arm-0.24),-d*0.02,h*0.65),mat,puff=1.0,rotation=(math.radians(64),s*0.1,s*0.12))
    if b.options.get("throw",True):
        _supported_sofa_throw(b,seats[0],base,-seatw/2-.008+.045)


def _supported_sofa_throw(b,seat,base,cx):
    """Thin fabric around the actual convex seat/base support silhouette.

    A textile bridges the concave seat/base junction instead of penetrating the
    wider base. The rear edge stays forward of the separate scatter cushion.
    """
    points=sorted(set((round(p.y,8),round(p.z,8)) for obj in [seat,base] for v in obj.data.vertices for p in [obj.matrix_basis@v.co]))
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower=[]
    for p in points:
        while len(lower)>=2 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    upper=[]
    for p in reversed(points):
        while len(upper)>=2 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    hull=lower[:-1]+upper[:-1]
    def boundary(value,axis,want_max):
        hits=[]
        for a,c in zip(hull,hull[1:]+hull[:1]):
            if min(a[axis],c[axis])-1e-8<=value<=max(a[axis],c[axis])+1e-8:
                if abs(c[axis]-a[axis])<1e-9:hits.extend([a[1-axis],c[1-axis]])
                else:
                    t=(value-a[axis])/(c[axis]-a[axis]);hits.append(a[1-axis]+t*(c[1-axis]-a[1-axis]))
        if not hits:raise ValueError("Textile support envelope has no boundary")
        return (max if want_max else min)(hits)
    rear=-b.d*.21;top=boundary(rear,0,True);bottom=top-.16
    route=[(rear,top)]+[p for p in hull if p[0]<rear and bottom<p[1]<top and abs(p[0]-boundary(p[1],1,False))<1e-6]+[(boundary(bottom,1,False),bottom)]
    route=sorted(set(route),key=lambda p:(-p[1],-p[0]))
    path=[]
    for a,c in zip(route,route[1:]):
        distance=math.hypot(c[0]-a[0],c[1]-a[1]);count=max(1,math.ceil(distance/.010))
        for j in range(count):path.append((a[0]+(c[0]-a[0])*j/count,a[1]+(c[1]-a[1])*j/count))
    path.append(route[-1]);arc=[0.0]
    for a,c in zip(path,path[1:]):arc.append(arc[-1]+math.hypot(c[0]-a[0],c[1]-a[1]))
    def panel(name,width,max_length,inside_offset,thickness):
        usable=[i for i,t in enumerate(arc) if t<=max_length+1e-8]
        if len(usable)<3:raise ValueError("Fold return too short")
        centres=[path[i] for i in usable];lengths=[arc[i] for i in usable];nx=30;stride=nx+1;verts=[];uv=[]
        repeat=float(b.m['throw'].get('texture_size_m',1));normals=[]
        for j,p in enumerate(centres):
            a=centres[max(0,j-1)];c=centres[min(len(centres)-1,j+1)];dy=c[0]-a[0];dz=c[1]-a[1];norm=math.hypot(dy,dz)
            normals.append((dz/norm,-dy/norm))
        for layer in [0,1]:
            for j,(y,z) in enumerate(centres):
                ny,nz=normals[j]
                for i in range(nx+1):
                    u=i/nx;wave=.0007*(1+math.sin(11*u+lengths[j]*3))
                    offset=inside_offset+wave+(thickness if layer==0 else 0)
                    verts.append((cx+(u-.5)*width,y+ny*offset,z+nz*offset));uv.append((u*width/repeat,lengths[j]/repeat))
        layer_size=stride*len(centres);faces=[]
        for k in [0,1]:
            for j in range(len(centres)-1):
                for i in range(nx):
                    a=k*layer_size+j*stride+i;pair=[(a,a+1,a+stride+1),(a,a+stride+1,a+stride)]
                    faces.extend(pair if k==0 else [tuple(reversed(f)) for f in pair])
        border=list(range(stride))+[j*stride+nx for j in range(1,len(centres))]+[(len(centres)-1)*stride+i for i in range(nx-1,-1,-1)]+[j*stride for j in range(len(centres)-2,0,-1)]
        for i,a in enumerate(border):
            c=border[(i+1)%len(border)];faces.extend([(a,c+layer_size,c),(a,a+layer_size,c+layer_size)])
        obj=b.mesh(name,verts,faces,'throw',True,collide=False,uv=uv);obj['textile_thickness_m']=thickness;obj['textile_support']='Actual seat/base vertex convex front envelope';return obj
    panel('thin-draped-throw',.42,arc[-1],.0020,.0016)
    panel('thin-fold-return',.412,.080,.0060,.0016)


def _armchair(b):
    w,d,h=b.w,b.d,b.h
    seat=h*0.48
    for sx in (-1,1):
        for sy in (-1,1):
            b.rod("splayed-leg",(sx*w*0.42,sy*d*0.41,0),(sx*w*0.35,sy*d*0.30,seat),0.022,"oak",0.031)
        b.box("arm-rail",(0.070,d*0.94,0.05),(sx*w*0.43,0,h*0.70),"oak",0.018)
        b.rod("arm-upright",(sx*w*0.42,-d*0.27,seat*0.70),(sx*w*0.43,-d*0.27,h*0.69),0.021)
    b.box("seat-frame",(w*0.85,d*0.81,0.06),(0,-d*0.015,seat-0.065),"oak",0.014)
    b.soft("seat-pad",(w*0.78,d*0.75,0.14),(0,-d*0.04,seat),puff=0.6)
    b.soft("back-pad",(w*0.78,h*0.48,0.13),(0,d*0.27,h*0.73),puff=0.8,rotation=(math.radians(75),0,0))
    b.rod("back-top-rail",(-w*0.37,d*0.35,h*0.91),(w*0.37,d*0.35,h*0.91),0.025)


def _dining_chair(b):
    w,d,h=b.w,b.d,b.h
    sh=float(b.options.get("seat_height_m",h*.56))
    for sx in (-1,1):
        for sy in (-1,1):
            b.rod("leg",(sx*w*0.43,sy*d*0.42,0),(sx*w*0.36,sy*d*0.31,sh-0.025),0.016,"frame",0.023)
    b.soft("seat",(w*0.97,d*0.82,0.060),(0,-d*0.035,sh),"linen",puff=0.1)
    for sx in (-1,1):
        b.rod("back-post",(sx*w*0.36,d*0.31,sh-0.08),(sx*w*0.37,d*0.42,h-0.035),0.020)
    style = b.options.get("style")
    if style in {"country", "traditional"}:
        for n in range(-2,3):
            x = n*w*.125
            b.rod("back-spindle",(x,d*.31,sh),(x,d*.42,h-.045),.008,"oak",.012)
        b.soft("crest-rail",(w*.95,.048,h*.10),(0,d*.41,h*.94),"oak",puff=.08,seam=False)
    elif style == "industrial":
        for s in (-1,1):
            b.rod("steel-brace",(s*w*.36,d*.31,sh),(s*w*.36,d*.42,h*.94),.011,"black")
        b.box("bentwood-rest",(w*.95,.032,h*.21),(0,d*.41,h*.85),"oak",.014,rotation=(-.11,0,0))
    else:
        b.soft("curved-back",(w*0.99,h*0.25,0.055),(0,d*0.41,h*0.85),"upholstery",puff=0.1,rotation=(math.radians(83),0,0))


def _supported_bed_throw(b,duvet):
    import furnishing_surfaces as surfaces
    mesh=duvet.data;count=(32+1)*(42+1)
    vertices=[tuple(duvet.matrix_basis@v.co) for v in mesh.vertices[:count]]
    triangles=[tuple(p.vertices) for p in mesh.polygons[:32*42*2]]
    uv=[None]*count
    for p in mesh.polygons[:32*42*2]:
        for loop_index in p.loop_indices:
            loop=mesh.loops[loop_index];uv[loop.vertex_index]=tuple(mesh.uv_layers.active.data[loop_index].uv)
    ratio=float(b.m['white_fabric'].get('texture_size_m',1))/float(b.m['throw'].get('texture_size_m',1))
    uv=[(u*ratio,v*ratio) for u,v in uv]
    band=surfaces.supported_band(vertices,triangles,uv,-b.d*.425,-b.d*.135)
    obj=b.mesh('foot-throw',band['vertices'],band['faces'],'throw',True,collide=False,uv=band['uv'])
    obj['textile_thickness_m']=band['thickness_m'];obj['textile_support']='Exact clipped duvet triangles, incident-plane bounded offset';obj['textile_clearance_m']=band['clearance_m']
    return obj


def _vanity_counter(b):
    import furnishing_surfaces as surfaces
    g=surfaces.vanity_counter(b.w,b.d,b.h,b.w*.68,b.d*.75)
    repeat=float(b.m['stone'].get('texture_size_m',1))
    obj=b.mesh('counter',g['vertices'],g['faces'],'stone',False,uv=[(u/repeat,v/repeat) for u,v in g['uv']])
    obj['basin_aperture']=True;obj['basin_aperture_clearance_m']=g['aperture_clearance_m'];return obj


def _bed(b):
    w,d,h=b.w,b.d,b.h
    platform=h*0.29; mt=h*0.47
    for x in (-w*0.42,w*0.42):
        for y in (-d*0.40,d*0.40): b.rod("foot",(x,y,0),(x,y,0.12),0.030,"oak")
    b.soft("upholstered-divan",(w-0.03,d-0.04,platform-0.09),(0,0,0.09+(platform-0.09)/2),"linen",puff=0.1)
    b.soft("headboard",(w,0.13,h-0.08),(0,d/2-0.065,(h+0.08)/2),"upholstery",puff=0.12,seam=False)
    b.soft("mattress",(w-0.09,d-0.17,mt-platform),(0,-0.035,(mt+platform)/2),"white_fabric",puff=0.15)
    # Bottom sheet and duvet are separate closed forms. Cloth overhang is supported
    # on the mattress; top folds, falling side edges and front edge have thickness.
    b.cloth("fitted-sheet",w-0.08,d-0.18,(0,-0.035,mt+0.008),"white_fabric",fold=0.005)
    duvet_d=d*0.91
    duvet=b.cloth("duvet",w+.50,duvet_d,(0,-d*.14,mt+.060),"white_fabric",fold=.019,seed=.6,thickness=.055,support_width=w-.09,support_front=-d/2+.05,support_z=mt+.008)
    b.cloth("turned-duvet",w+.50,.24,(0,d*.235,mt+.083),"white_fabric",fold=.012,seed=1.8,steps=(32,14),thickness=.022,support_width=w-.09,support_z=mt+.050)
    pillow_count=1 if w<1.25 else 2
    for i in range(pillow_count):
        x=(i-(pillow_count-1)/2)*(w*0.46)
        b.soft("sleep-pillow",(min(0.70,w*0.84/pillow_count),0.43,0.15),(x,d*0.32,mt+0.10),"white_fabric",puff=0.9,rotation=(0.06,0.04*(-1 if i else 1),0))
        b.soft("linen-pillow",(min(0.55,w*0.72/pillow_count),0.33,0.14),(x,d*0.24,mt+0.20),"linen",puff=0.6,rotation=(0.35,0,0.02*(-1 if i else 1)))
    _supported_bed_throw(b,duvet)


def _table(b,kind):
    w,d,h=b.w,b.d,b.h
    top=0.030 if kind=="coffee_table" else 0.036
    b.box("rounded-top",(w,d,top),(0,0,h-top/2),"oak",0.018)
    style = b.options.get("style")
    if style == "contemporary":
        radius = min(w,d)*.28
        b.lathe("pedestal",[(radius*.88,0),(radius,.018),(radius*.75,h*.35),(radius*.56,h-top)],(0,0,0),"oak",48)
        return
    if style in ("industrial","country","modern"):
        for sx in (-1,1):
            x = sx*w*.34
            material = "black" if style=="industrial" else "oak"
            for sy in (-1,1):
                b.box("trestle-leg",(.038,.042,h-top),(x,sy*d*.32,(h-top)/2),material,.005)
            if style!="modern":
                b.box("trestle-foot",(.048,d*.76,.035),(x,0,.0175),material,.004)
        if style=="country":
            b.box("oak-stretcher",(w*.68,.065,.09),(0,0,h*.32),"oak",.008)
        return
    if kind=="side_table":
        for i in range(3):
            a=TAU*i/3
            b.rod("leg",(math.cos(a)*w*.32,math.sin(a)*d*.32,0),(math.cos(a)*w*.24,math.sin(a)*d*.24,h-top),0.018,"oak",0.027)
    else:
        for sx in (-1,1):
            for sy in (-1,1):
                b.rod("taper-leg",(sx*(w/2-0.10),sy*(d/2-0.075),0),(sx*(w/2-0.14),sy*(d/2-0.12),h-top),0.022 if kind=="coffee_table" else 0.027,"oak",0.036)
        b.box("apron-front",(w-0.24,0.023,0.070),(0,-d/2+0.12,h-top-0.04),"oak",0.004)
        b.box("apron-back",(w-0.24,0.023,0.070),(0,d/2-0.12,h-top-0.04),"oak",0.004)


def _rug(b):
    b.box("woven-body",(b.w,b.d,b.h),(0,0,b.h/2),"rug",min(b.h*0.35,0.005))
    # Sewn border is a narrow solid strip, not an unsupported transparent decal.
    for sy in (-1,1):
        b.box("bound-end",(b.w,0.025,0.003),(0,sy*(b.d/2-0.014),b.h),"linen",0.001)
    for sx in (-1,1):
        b.box("bound-edge",(0.025,b.d,0.003),(sx*(b.w/2-0.014),0,b.h),"linen",0.001)


def _curtain(b,roman=False):
    w,d,h=b.w,b.d,b.h
    if roman:
        b.box("headrail",(w,d*0.74,0.035),(0,d*0.08,h-0.0175),"white",0.003)
        for i in range(5):
            z=(i+0.5)*(h-0.035)/5
            b.soft("raised-fold",(w-0.012,d*(0.78+i*0.04),(h-0.035)/5*1.24),(0,-d*0.08,z),"linen",puff=0.05,seam=False)
        return
    nx,ny=36,18
    verts=[]
    for j in range(ny+1):
        z=h*j/ny
        for i in range(nx+1):
            u=i/nx
            x=(u-.5)*w
            y=math.sin(u*TAU*6)*d*.42+0.008*math.sin(j*.8+u*12)*(1-j/ny)
            z2=z+0.012*math.cos(u*TAU*6)*(1-j/ny)
            verts.append((x,y,max(0,z2)))
    faces=[(j*(nx+1)+i,j*(nx+1)+i+1,(j+1)*(nx+1)+i+1,(j+1)*(nx+1)+i) for j in range(ny) for i in range(nx)]
    obj=b.mesh("linen-falls",verts,faces,"linen",True,collide=False)
    solid=obj.modifiers.new("hem-thickness","SOLIDIFY"); solid.thickness=0.002
    b.rod("curtain-pole",(-w*.56,0,h),(w*.56,0,h),0.012,"bronze")
    for i in range(8):
        x=(i/7-.5)*w
        pts=[(x,math.cos(TAU*k/16)*.021,h+math.sin(TAU*k/16)*.021) for k in range(16)]
        b.tube("ring",pts,.0025,"bronze",True,6)


def available_kinds():
    return tuple(DEFAULTS)


def build(kind,name,width=None,depth=None,height=None,location=(0,0,0),rotation_z=0.0,collection=None,materials=None,**options):
    """Build a new, independently designed asset; never mutates an existing scene."""
    if kind not in DEFAULTS:
        raise ValueError("Unknown furnishing kind: " + kind)
    if collection is None:
        raise ValueError("Pass an explicit collection; the library never chooses a scene.")
    base=DEFAULTS[kind]
    dims=tuple(float(v if v is not None else base[i]) for i,v in enumerate((width,depth,height)))
    if any(v<=0 for v in dims): raise ValueError("Asset dimensions must be positive metres")
    b=_Builder(kind,name,dims,collection,(materials if materials is not None else palette()),options.pop("fixed",kind in FIXED),options)
    if kind=="sofa": _sofa(b)
    elif kind=="armchair": _armchair(b)
    elif kind=="dining_chair": _dining_chair(b)
    elif kind in ("bed","single_bed"): _bed(b)
    elif kind in ("coffee_table","dining_table","side_table"): _table(b,kind)
    elif kind=="rug": _rug(b)
    elif kind=="cushion": b.soft("cushion",dims,(0,0,b.h/2),options.get("material","linen"),puff=1)
    elif kind=="towel":
        # Three folded layers fill the scheduled envelope from the bottom datum.
        for layer in range(3):
            b.soft("folded-towel-layer",(b.w,b.d,b.h/3),(0,0,(layer+.5)*b.h/3),options.get("material","white_fabric"),puff=.02,seam=False)
    elif kind=="throw":b.cloth("folded-linen",b.w,b.d,(0,0,.004),options.get("material","throw"),fold=.0015,steps=(22,18),thickness=.0016,support_z=0,fold_style="thin")
    elif kind in ("curtain","roman_blind"): _curtain(b,kind=="roman_blind")
    else: _build_fitting(b,kind)
    # Bounds include authored drapes, taps and valves beyond nominal body sizes.
    points = [obj.matrix_basis @ v.co for obj in b.objects if obj.type == "MESH" for v in obj.data.vertices]
    if points:
        b.root["built_bounds_min_m"] = [min(p[i] for p in points) for i in range(3)]
        b.root["built_bounds_max_m"] = [max(p[i] for p in points) for i in range(3)]
    b.root.location=location
    b.root.rotation_euler.z=rotation_z
    return b.objects

# The fixed fittings/decor module follows below. All public kinds share build().


def _handle(b,suffix,x,y,z,width=0.14,vertical=False,mat="bronze"):
    r=0.006
    if vertical:
        b.tube(suffix,[(x,y+.020,z-width/2),(x,y,z-width/2),(x,y,z+width/2),(x,y+.020,z+width/2)],r,mat,sides=10)
    else:
        b.tube(suffix,[(x-width/2,y+.020,z),(x-width/2,y,z),(x+width/2,y,z),(x+width/2,y+.020,z)],r,mat,sides=10)


def _cabinet_face(b,suffix,x,z,w,h,y,mat="kitchen",handle=True):
    if b.options.get("style") in ("modern","contemporary","industrial"):
        b.box(suffix+"-flush-front",(w-.004,.020,h-.004),(x,y,z),mat,.004)
        if handle: _handle(b,suffix+"-rail-pull",x,y-.032,z+h*.31,min(.17,w*.43),mat=b.options.get("handle_material","bronze"))
        return
    # Recessed panel has a concealed rebate inside the frame perimeter.
    rail=min(.055,w*.12,h*.20)
    rebate=min(.008,rail*.25)
    b.box(suffix+"-field",(w-.004-2*rebate,.018,h-.004-2*rebate),(x,y+.003,z),mat,.002)
    for s in (-1,1):
        b.box(suffix+"-stile",(rail,.022,h-.004),(x+s*(w-rail-.004)/2,y-.002,z),mat,.002,grain="z")
        b.box(suffix+"-rail",(w-rail*2-.004,.022,rail),(x,y-.002,z+s*(h-rail-.004)/2),mat,.002)
    if handle: _handle(b,suffix+"-handle",x,y-.035,z+h*.31,min(.16,w*.42),mat=b.options.get("handle_material","bronze"))


def _bowl_shell(b,suffix,w,d,h,centre,mat="glaze",segments=64,power=.48):
    # Thick continuous shell: base outside -> rim -> inner basin -> closed floor.
    profile=[(.42,0),(.70,h*.08),(.89,h*.40),(1,h*.92),(.995,h),(.92,h),(.87,h*.87),(.72,h*.31),(.45,h*.15),(.06,h*.13)]
    verts=[]
    for scale,z in profile:
        for i in range(segments):
            a=TAU*i/segments
            ca,sa=math.cos(a),math.sin(a)
            x=math.copysign(abs(ca)**power,ca)*w*.5*scale
            y=math.copysign(abs(sa)**power,sa)*d*.5*scale
            verts.append((centre[0]+x,centre[1]+y,centre[2]+z))
    faces=[]
    for k in range(len(profile)-1):
        for i in range(segments):
            n=(i+1)%segments
            faces.append((k*segments+i,k*segments+n,(k+1)*segments+n,(k+1)*segments+i))
    faces.extend([tuple(reversed(range(segments))),tuple((len(profile)-1)*segments+i for i in range(segments))])
    obj=b.mesh(suffix,verts,faces,mat,True)
    b.lathe(suffix+"-waste",[(.020,0),(.020,.003),(.014,.003),(.014,.001)],(centre[0],centre[1],centre[2]+h*.14),"metal",24)
    return obj


def _tap_at(b,x,y,z,h=.30,reach=.19,mat="metal"):
    b.lathe("tap-base",[(.025,0),(.025,.014),(.019,.019)],(x,y,z),mat,32)
    # Swan neck, genuine curved tube and downward aerator.
    points=[(x,y,z+.012),(x,y,z+h*.66)]
    bend=reach/2
    # The straight segment already ends at arc sample0; append it only once.
    for i in range(1,13):
        a=math.pi*i/12
        points.append((x,y-bend+bend*math.cos(a),z+h*.66+bend*math.sin(a)))
    points.append((x,y-reach,z+h*.60))
    b.tube("swan-neck",points,.012,mat,sides=12)
    b.rod("aerator",(x,y-reach,z+h*.60),(x,y-reach,z+h*.56),.014,mat,sides=20)
    b.rod("lever-pivot",(x+.020,y,z+.055),(x+.043,y,z+.055),.012,mat)
    b.rod("mixer-lever",(x+.043,y,z+.055),(x+.043,y-.055,z+.13),.005,mat)


def _worktop(b,w,d,z,sink=False):
    thick=float(b.options.get("worktop_thickness_m",.030))
    left,right,front,back=b.options.get("worktop_bounds_m",[-w/2-.002,w/2+.002,-d/2-.018,d/2+.002])
    if not(left<right and front<back):raise ValueError("Invalid worktop butt bounds")
    holew=min(.75 if b.options.get("sink_bowls")==1.5 else .60,w*.73);holed=d*.64
    if not b.options.get('skip_worktop_surface'):
        import furnishing_surfaces as surfaces
        holes=b.options.get('worktop_apertures_m',[[-holew/2,holew/2,-holed/2,holed/2]] if sink else [])
        g=surfaces.worktop_slab([left,right,front,back],holes,z,thick)
        obj=b.mesh('counter',g['vertices'],g['faces'],'stone',False)
        obj['construction_run_layout_ids']=b.options.get('worktop_run_ids',[b.name]);obj['true_aperture_count']=len(holes)
    if sink:
        if b.options.get("sink_bowls")==1.5:
            bw=holew*.64;sw=holew*.31
            _bowl_shell(b,"main-sink",bw,holed,.18,(-holew*.18,0,z-.18),"metal",power=.24)
            _bowl_shell(b,"half-sink",sw,holed*.72,.13,(holew*.33,0,z-.13),"metal",power=.24)
            b.box("sink-divider",(.012,holed,.015),(holew*.15,0,z-.0075),"metal",.003)
        else:
            under=b.options.get("sink_mount")=="undermount"
            _bowl_shell(b,"undermount-sink" if under else "inset-sink",holew+.012,holed+.012,.18,(0,0,z-.18-(thick if under else -.009)),"metal",power=.24)
        _tap_at(b,0,d*.40,z,.30,.19,mat=b.options.get("tap_material","metal"))
    b.root['worktop_construction_run']=b.options.get('worktop_run_leader',b.name)


def _kitchen(b,kind):
    w,d,h=b.w,b.d,b.h
    full_depth=d
    island=bool(b.options.get("island",False))
    overhang=min(.30,float(b.options.get("seating_overhang_m",.25))) if island else 0
    d-=overhang; cy=-overhang/2
    wall=kind=="kitchen_wall"; tall=kind=="kitchen_tall"
    bottom=0 if wall else .15
    if not wall:b.root["plinth_datum_m"]=bottom
    top=h if wall or tall else h-.028
    # Back, side, top and bottom boards leave cabinet interior as physical volume.
    back_bottom=.005 if island else bottom
    b.box("back",(w-.002,.012,top-back_bottom),(0,d/2-.006+cy,(top+back_bottom)/2),"kitchen" if island else "white",.002,grain="z")
    side_bottom=0 if wall else (.005 if island else bottom)
    for s in (-1,1): b.box("side",(.018,d,top-side_bottom),(s*(w/2-.0095),cy,(top+side_bottom)/2),"kitchen",.002,grain="z")
    for z in (bottom+.009,top-.009): b.box("carcass-horizontal",(w-.036,d-.025,.018),(0,cy,z),"white",.002)
    if not wall:
        plinth_low=.002;plinth_h=bottom-plinth_low
        b.box("recessed-plinth",(w-.004,.018,plinth_h),(0,-d/2+.075+cy,plinth_low+plinth_h/2),"kitchen",.001)
        if not island:
            # Finished returns meet the front board at its back edge; neighbouring
            # units hide the internal returns. No exposed full-depth side legs.
            return_depth=d-.084
            for sx in [-1,1]:
                b.box("plinth-end-return",(.018,return_depth,plinth_h),(sx*(w/2-.0095),.042+cy,plinth_low+plinth_h/2),"kitchen",.001)
        for x in (-w*.32,w*.32):
            for y in (-d*.28,d*.28): b.rod("adjustable-foot",(x,y+cy,0),(x,y+cy,bottom),.018,"black")
    y=-d/2-.008+cy
    if b.options.get("appliance")=="dishwasher" and not wall:
        b.box("dishwasher-shadow-seal",(w-.010,.012,top-bottom),(0,y+.010,(top+bottom)/2),"black",.001)
        _cabinet_face(b,"integrated-dishwasher-door",0,(top+bottom)/2,w-.016,top-bottom-.008,y)
        b.box("dishwasher-control-edge",(w-.06,.008,.020),(0,y-.005,top-.010),"metal",.001)
        b.root["appliance_type"]="integrated_dishwasher"
    elif island and b.options.get("slab_front",True):
        for i in range(3):
            dh=(top-bottom)/3;zz=bottom+(i+.5)*dh
            b.box("oak-slab-drawer",(w-.004,.020,dh-.003),(0,y,zz),"kitchen",.002,grain="z")
            _handle(b,"slab-pull",0,y-.032,zz+dh*.28,min(.16,w*.45),mat=b.options.get("handle_material","bronze"))
    elif b.options.get("appliance")=="oven" and not wall:
        _oven_front(b,w-.020,min(.60,top-bottom),y,(bottom+min(.60,top-bottom)/2))
        if top-bottom>.62: _cabinet_face(b,"upper-drawer",0,top-.065,w-.004,.12,y)
    elif b.options.get("blind_corner"):
        exposed=0 if b.options.get("blank_front") else float(b.options.get("exposed_front_width_m",max(.30,w-.60)))
        if exposed:exposed=max(.10,exposed-.022) # Physical return-front/corner allowance.
        blank=w-exposed
        if blank>0:b.box("blind-corner-panel",(blank-.004,.020,top-bottom-.004),(-exposed/2,y+.020,(top+bottom)/2),"kitchen",.002)
        if exposed>0:_cabinet_face(b,"accessible-corner-door",blank/2,(top+bottom)/2,exposed-.004,top-bottom-.004,y)
        b.root["corner_access"]="returning cabinet" if exposed==0 else "exposed front segment"
    elif b.options.get("drawers"):
        count=max(2,min(4,int(b.options["drawers"])))
        dh=(top-bottom)/count
        for i in range(count): _cabinet_face(b,"drawer",0,bottom+(i+.5)*dh,w-.004,dh-.003,y)
    elif tall:
        split=h*.36
        _cabinet_face(b,"lower-door",0,(bottom+split)/2,w-.004,split-bottom-.004,y)
        _cabinet_face(b,"upper-door",0,(split+top)/2,w-.004,top-split-.004,y)
    else:
        count=2 if w>.78 else 1
        for i in range(count):
            dw=w/count
            _cabinet_face(b,"door",(i-(count-1)/2)*dw,(bottom+top)/2,dw-.004,top-bottom-.004,y)
    if not wall and not tall:
        _worktop(b,w,full_depth,h,b.options.get("sink",False))
        if b.options.get("hob"):
            _hob_at(b,min(float(b.options.get("hob_width_m",.59)),w-.02),min(.52,d-.03),h+.006)


def _oven_front(b,w,h,y,z):
    b.box("oven-chassis",(w,.025,h),(0,y,z),"metal",.004)
    b.box("oven-glass",(w-.045,.009,h*.71),(0,y-.020,z-h*.08),"dark_glass",.011)
    b.box("oven-window",(w-.14,.004,h*.44),(0,y-.026,z-h*.08),"black",.013)
    _handle(b,"oven-pull",0,y-.064,z+h*.235,w*.72,mat="metal")
    for x in (-w*.32,w*.32):
        obj=b.lathe("oven-knob",[(.024,0),(.024,.020),(.020,.024)],(0,0,0),"black",24)
        obj.rotation_euler.x=math.pi/2
        obj.location=(x,y-.026,z+h*.40)
    b.box("oven-display",(.105,.003,.035),(0,y-.030,z+h*.405),"dark_glass",.002)
    for i in range(5): b.box("oven-vent",(w*.66,.003,.003),(0,y-.018,z-h*.46+i*.006),"black",0)


def _hob_at(b,w,d,z):
    b.box("ceramic-hob",(w,d,.010),(0,0,z),"dark_glass",.007)
    for sx in (-1,1):
        for sy in (-1,1):
            r=min(w,d)*(.145 if sx==sy else .18)
            pts=[(sx*w*.25+r*math.cos(TAU*i/48),sy*d*.24+r*math.sin(TAU*i/48),z+.0056) for i in range(48)]
            b.tube("induction-ring",pts,.0009,"metal",True,6)
    for i in range(4): b.box("touch-control",(.006,.012,.001),((i-1.5)*.023,-d*.43,z+.006),"white",0)


def _fridge(b):
    w,d,h=b.w,b.d,b.h
    b.box("body",(w-.015,d-.035,h-.01),(0,.012,h/2),"white",.014)
    split=h*.34
    for z,dh in (((split-.005)/2,split-.005),((h+split+.005)/2,h-split-.005)):
        b.box("sealed-door",(w,.040,dh),(0,-d/2+.02,z),"white",.012)
        _handle(b,"door-pull",-w*.34,-d/2-.018,z+dh*.12,min(.29,dh*.48),True,"metal")
    b.box("bottom-vent",(w-.08,.010,.045),(0,-d/2+.035,.033),"black",.003)


def _vanity(b):
    w,d,h=b.w,b.d,b.h
    for s in (-1,1):
        for t in (-1,1): b.rod("foot",(s*w*.40,t*d*.34,0),(s*w*.40,t*d*.34,.15),.023)
    b.box("cabinet",(w-.02,d-.01,h*.66),(0,0,.15+h*.33),"oak",.006,grain="z")
    for i in range(2): _cabinet_face(b,"drawer",0,.17+(i+.5)*(h*.59/2),w-.026,h*.59/2-.005,-d/2,"oak")
    _vanity_counter(b)
    _bowl_shell(b,"wash-basin",w*.68,d*.75,.12,(0,-d*.05,h-.12),"glaze")
    _tap_at(b,w*.26,d*.26,h-.067,.22,.13,mat=b.options.get("tap_material","metal"))


def _toilet(b):
    w,d,h=b.w,b.d,b.h
    seat=h*.53
    b.lathe("pedestal",[(w*.30,0),(w*.33,.03),(w*.29,seat*.65),(w*.45,seat*.90)],(0,-d*.11,0),"glaze",48,ellipse=d/w*.48)
    _bowl_shell(b,"wc-pan",w,d*.69,seat*.45,(0,-d*.12,seat*.55),"glaze",power=.70)
    # Seat ring is an open annulus, not a white slab over a hollow-looking graphic.
    profile=[(.94,0),(.98,.012),(.97,.026),(.74,.026),(.73,.012),(.75,0),(.94,0)]
    verts=[];n=64
    for r,z in profile:
        for i in range(n):
            a=TAU*i/n
            verts.append((w*.5*r*math.cos(a),-d*.12+d*.345*r*math.sin(a),seat+z))
    faces=[(k*n+i,k*n+(i+1)%n,(k+1)*n+(i+1)%n,(k+1)*n+i) for k in range(len(profile)-1) for i in range(n)]
    b.mesh("seat-ring",verts,faces,"white",True)
    # The pan flows into a raised rear deck carrying the cistern.
    b.box("rear-pedestal",(w*.58,d*.36,seat*.68),(0,d*.28,seat*.34),"glaze",.042)
    b.box("cistern-deck",(w*.94,d*.39,seat*.15),(0,d*.285,seat*.745),"glaze",.023)
    b.box("cistern",(w*.94,d*.24,h-seat*.82),(0,d*.36,(h+seat*.82)/2),"glaze",.032)
    b.box("cistern-lid",(w*.96,d*.25,.026),(0,d*.36,h-.013),"glaze",.012)
    b.lathe("flush-button",[(.019,0),(.019,.003)],(w*.20,d*.36,h+.001),"metal",24)
    for sx in (-1,1): b.rod("seat-hinge",(sx*w*.28,d*.10,seat+.01),(sx*w*.28,d*.10,seat+.035),.015,"metal")


def _bath(b):
    w,d,h=b.w,b.d,b.h
    _bowl_shell(b,"bath-shell",w,d,h,(0,0,0),"glaze",segments=80,power=.32)
    _tap_at(b,w*.20,d*.40,h,.18,.14)
    # Overflow fitting lies on the actual inner end, below the rim.
    b.box("overflow",(.060,.006,.025),(0,d*.40,h*.77),"metal",.012)


def _shower(b):
    w,d,h=b.w,b.d,b.h;tray=.045;frame=b.options.get("frame_material","black")
    tray_obj=b.box("tray",(w,d,tray),(0,0,tray/2),"glaze",.010);tray_obj['walkable']=True
    b.box("drain-slot",(w*.45,.025,.003),(w*.18,d*.30,tray+.001),"metal",.004)
    if b.options.get("walk_in"):
        length=float(b.options.get("screen_length_m",1.20));xc=w/2-length/2
        b.box("fixed-front-screen",(length,.008,h-tray),(xc,-d/2+.006,(h+tray)/2),"glass",.001)
        for x in [w/2,w/2-length]:b.rod("black-screen-upright",(x,-d/2+.006,tray),(x,-d/2+.006,h),.009,frame)
        b.rod("screen-brace",(w/2-.12,-d/2,h-.05),(w/2-.12,d/2,h-.05),.008,frame)
        side=b.options.get('head_side',1);x=side*(w/2-.10);y=d*.12
        b.rod("riser",(x,y,.80),(x,y,h-.18),.011,"metal")
        b.tube("head-arm",[(x,y,h-.18),(x-side*.25,y,h-.18),(x-side*.25,y,h-.22)],.012,"metal",sides=12)
        head=(x-side*.25,y,h-.24)
        b.rod("mixer",(x,y-.12,.86),(x,y+.12,.86),.026,"metal")
    else:
        # Two glazed exposed faces; closed wall-side edges remain open against the tiled room.
        b.box("fixed-side-pane",(.008,d,h-tray),(w/2-.006,0,(h+tray)/2),"glass",.001)
        #600mm hinged entrance with fixed return: no unapproved sliding hardware.
        leaf_width=.60;hinge_x=-w/2+.018+leaf_width;front_y=-d/2-.006
        fixed_width=w/2-hinge_x-.012
        b.box("fixed-front-return",(fixed_width,.008,h-tray),((hinge_x+.012+w/2)/2,-d/2+.006,(h+tray)/2),"glass",.001)
        door=bpy.data.objects.new(b.name+".hinged-shower-door",None);b.collection.objects.link(door);door.parent=b.root;b.tag(door);b.objects.append(door)
        door["door_id"]=b.name+".hinged-door";door["door_motion"]="ordinary";door["door_local_hinge"]=[hinge_x,front_y,0];door["door_open_deg"]=90
        k=len(b.objects)
        b.box("hinged-front-pane",(leaf_width-.024,.008,h-tray-.024),(hinge_x-leaf_width/2,front_y-.005,(h+tray)/2),"glass",.001)
        _handle(b,"shower-door-pull",hinge_x-leaf_width+.075,front_y-.025,h*.50,.16,True,"metal")
        for obj in b.objects[k:]:
            obj.parent=door
            for key in ['door_id','door_motion','door_local_hinge','door_open_deg']:obj[key]=door[key]
        for z in [.35,h-.35]:
            b.rod("shower-hinge-barrel",(hinge_x,front_y,z-.025),(hinge_x,front_y,z+.025),.009,frame,sides=16)
        b.rod("hinge-side-upright",(hinge_x,-d/2+.006,tray),(hinge_x,-d/2+.006,h),.009,frame)
        for x,y in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2)]:b.rod("black-frame",(x,y,tray),(x,y,h),.009,frame)
        b.rod("top-front-rail",(-w/2,-d/2,h),(w/2,-d/2,h),.009,frame)
        x=-w*.25;y=d/2-.045
        b.rod("riser",(x,y,.80),(x,y,h-.18),.011,"metal")
        b.tube("head-arm",[(x,y,h-.18),(x,y-.23,h-.18),(x,y-.23,h-.22)],.012,"metal",sides=12)
        head=(x,y-.23,h-.24);b.rod("mixer",(x-.12,y,.86),(x+.12,y,.86),.026,"metal")
    b.lathe("250mm-rain-head",[(.125,0),(.125,.012),(.12,.017)],head,"metal",48)
    hose=[(x+.04,y-.035,.85),(x+.09,y-.035,.52),(x+.16,y-.035,.65),(x+.12,y-.035,1.28)]
    b.tube("handset-hose",hose,.006,"metal",sides=8)
    b.rod("handset",(x+.12,y-.035,1.23),(x+.12,y-.055,1.38),.017,"metal")


def _radiator(b,towel=False):
    w,d,h=b.w,b.d,b.h
    mat=b.options.get("rail_material","black") if towel else "white"
    if towel:
        for sx in (-1,1): b.rod("upright",(sx*w*.44,0,0),(sx*w*.44,0,h),.018,mat)
        for i in range(17):
            # Bigger access gaps every sixth rail are deliberate and repeatable.
            z=h*(.05+.90*i/18)+(.025 if i>5 else 0)+(.025 if i>11 else 0)
            b.rod("towel-bar",(-w*.44,-d*.12,z),(w*.44,-d*.12,z),.011,mat)
        if b.options.get("towel",True):
            # Front and back lengths hang from the same measured rail. The
            # curved crown clears its 11 mm radius by one fabric thickness.
            bar_z = h*(.05+.90*11/18)+.025
            r = .0122
            profile = [(-r,bar_z-h*.32)]
            for j in range(17):
                a = math.pi*j/16
                profile.append((-r*math.cos(a),bar_z+r*math.sin(a)))
            profile.append((r,bar_z-h*.23))
            verts,faces=[],[]
            for j,(y,z) in enumerate(profile):
                for i in range(25):
                    u=i/24
                    fold=.003*math.sin(u*math.pi*8)*min(1,abs(z-bar_z)/(.16*h))
                    verts.append(((u-.5)*w*.57-w*.08,-d*.12+y+fold,z))
                    if j and i:
                        k=j*25+i
                        faces.append((k-26,k-25,k,k-1))
            towel=b.mesh("rail-draped-towel",verts,faces,"white_fabric",True,collide=False)
            towel["support_surface"]="towel-bar-11"
            towel["support_clearance_m"]=r-.011
    else:
        b.box("back-panel",(w-.035,d*.50,h-.015),(0,d*.14,h/2),"white",.006)
        count=max(6,int(w/.033))
        for i in range(count):
            x=(i-(count-1)/2)*(w-.035)/count
            b.box("pressed-channel",((w-.035)/count*.70,d*.42,h-.025),(x,-d*.16,h/2),"white",.006)
        b.box("top-grille",(w,d*.88,.016),(0,0,h-.008),"white",.003)
        for i in range(max(4,int(w/.035))):
            x=-w*.47+i*.035
            b.box("grille-slot",(.020,d*.52,.002),(x,0,h+.0005),"black",.002)
    for sx in (-1,1):
        x=sx*(w*.5+.018)
        b.tube("valve-pipe",[(sx*w*.43,0,.055),(x,0,.055),(x,0,-.065)],.0075,"metal",sides=10)
        b.rod("valve",(x,0,.043),(x,0,.090),.015,"metal")
        if sx<0: b.lathe("thermostat",[(.022,0),(.023,.040),(.018,.046)],(x,0,.09),"white",24)


def _lampshade(b,suffix,radius,height,z):
    # Double-sided physical shade wall and rolled edges with open top/bottom.
    ratio = {"modern":.98, "contemporary":.94, "industrial":.33, "traditional":.55}.get(b.options.get("style"),.69)
    shade_mat = "black" if b.options.get("style")=="industrial" else "linen"
    shade=b.lathe(suffix,[(radius,0),(radius*ratio,height),(radius*ratio-.003,height),(radius-.003,0),(radius,0)],(0,0,z),shade_mat,48)
    shade["shade_transmission"]=.55;shade["shade_fixture"]=b.name
    for r,zz in ((radius,z),(radius*ratio,z+height)):
        b.tube(suffix+"-rolled-edge",[(r*math.cos(TAU*i/48),r*math.sin(TAU*i/48),zz) for i in range(48)],.002,"seam",True,6)
    b.lathe("bulb",[(.012,0),(.022,.020),(.022,.045),(.008,.060)],(0,0,z+.025),"bulb",24)


def _light(b,kind):
    w,d,h=b.w,b.d,b.h
    if kind=="downlight":
        b.lathe("bezel",[(w/2,0),(w/2,.009),(w*.38,.011),(w*.36,0),(w/2,0)],(0,0,0),"white",32)
        b.lathe("lens",[(w*.35,0),(w*.35,.004)],(0,0,.001),"bulb",32)
    elif kind=="pendant":
        b.lathe("ceiling-rose",[(.048,0),(.048,.024),(.040,.028)],(0,0,h-.028),"white",32)
        shade=h*.30
        b.rod("flex",(0,0,shade),(0,0,h-.022),.0028,"black")
        _lampshade(b,"linen-shade",w/2,shade,0)
    elif kind=="wall_light":
        b.box("wall-plate",(w*.55,.025,h*.65),(0,d*.45,h*.50),"bronze",.015)
        b.tube("arm",[(0,d*.43,h*.44),(0,0,h*.44),(0,-d*.10,h*.65)],.008,"bronze",sides=10)
        _lampshade(b,"shade",w*.5,h*.50,h*.50)
    else:
        floor=kind=="floor_lamp"
        b.lathe("foot",[(w*.38,0),(w*.43,.010),(w*.43,.021),(w*.35,.028)],(0,0,0),"bronze",48)
        sh=h*(.19 if floor else .49)
        b.rod("stem",(0,0,.025),(0,0,h-sh+.025),.009 if floor else .014,"bronze")
        if not floor:
            b.lathe("ceramic-body",[(w*.20,0),(w*.29,h*.10),(w*.24,h*.27),(w*.09,h*.40)],(0,0,.025),"ceramic",48)
        _lampshade(b,"linen-shade",w*.5,sh,h-sh)
    b.root["fixture_emissive"] = True
    b.root["realtime_light_created"] = False
    # Renderer owns a bounded light pool; geometry does not spawn many lights.


def _books(b,stack=False):
    w,d,h=b.w,b.d,b.h
    colours=("book_sage","book_ochre","book_clay","linen","black")
    n=3 if stack else 7
    for i in range(n):
        if stack:
            z=h/n; ww=w*(1-.045*i); dd=d*(1-.035*i)
            obj=b.box("pages",(ww-.006,dd-.005,z-.007),(0,0,i*z+z/2),"paper",.001)
            for s in (-1,1): b.box("cover",(ww,dd,.0028),(0,0,i*z+z/2+s*(z/2-.0014)),colours[i%len(colours)],.0007)
            b.box("spine",(ww,.0035,z),(0,-dd/2+.0017,i*z+z/2),colours[i%len(colours)],.001)
        else:
            bw=w/n*.93;bh=h*(.83+.15*math.sin(i*2.2)**2);bd=d*(.84+.13*math.cos(i*1.4)**2)
            x=(i-(n-1)/2)*w/n
            b.box("pages",(bw-.005,bd-.006,bh-.006),(x,0,bh/2),"paper",.001)
            for s in (-1,1): b.box("cover",(.002,bd,bh),(x+s*(bw/2-.001),0,bh/2),colours[i%len(colours)],.0006)
            b.box("spine",(bw,.003,bh),(x,-bd/2,bh/2),colours[i%len(colours)],.001)
            for z in (.20,.79): b.box("spine-rule",(bw*.62,.0008,.002),(x,-bd/2-.0019,bh*z),"paper",0)


def _vase(b,bowl=False):
    w,d,h=b.w,b.d,b.h
    if bowl:
        b.lathe("stoneware",[(w*.24,0),(w*.30,h*.08),(w*.48,h*.78),(w*.50,h),(w*.47,h),(w*.43,h*.78),(w*.25,h*.16),(0,h*.13)],(0,0,0),"ceramic",64,ellipse=d/w)
    else:
        b.lathe("stoneware",[(w*.27,0),(w*.40,h*.06),(w*.50,h*.34),(w*.44,h*.64),(w*.24,h*.86),(w*.23,h),(w*.19,h),(w*.19,h*.86),(w*.39,h*.62),(w*.44,h*.34),(w*.34,h*.10),(0,h*.08)],(0,0,0),"ceramic",64,ellipse=d/w)


def _leaf(b,suffix,start,end,width,mat):
    start,end=Vector(start),Vector(end)
    axis=(end-start).normalized();length=(end-start).length
    helper=Vector((0,0,1)) if abs(axis.z)<.92 else Vector((1,0,0))
    across=axis.cross(helper).normalized();normal=across.cross(axis).normalized()
    verts=[];nu=12;nv=4
    for i in range(nu+1):
        u=i/nu
        envelope=math.sin(math.pi*u)**.85
        centre=start+(end-start)*u+normal*(.08*length*math.sin(math.pi*u))
        for j in range(nv+1):
            v=(j/nv-.5)*2
            p=centre+across*(width*.5*envelope*v)+normal*(width*.09*abs(v)*envelope)
            verts.append(tuple(p))
    faces=[(i*(nv+1)+j,i*(nv+1)+j+1,(i+1)*(nv+1)+j+1,(i+1)*(nv+1)+j) for i in range(nu) for j in range(nv)]
    obj=b.mesh(suffix,verts,faces,mat,True,collide=False)
    # Original geometric leaf has no alpha texture, avoiding transparent overdraw.
    return obj


def _plant(b):
    w,d,h=b.w,b.d,b.h
    ph=min(h*.31,w*.72);pr=min(w,d)*.24
    b.lathe("pot",[(pr*.68,0),(pr*.74,.015),(pr,ph*.96),(pr,ph),(pr-.008,ph),(pr*.68,ph*.12),(0,ph*.10)],(0,0,0),"ceramic",48)
    b.lathe("soil",[(0,0),(pr*.91,0),(pr*.91,.003),(0,.003)],(0,0,ph-.020),"soil",32)
    for i in range(7):
        a=i*2.399
        tip=Vector((math.cos(a)*w*.22,math.sin(a)*d*.22,ph+(h-ph)*(.62+.38*(i%3)/2)))
        start=Vector((math.cos(a)*pr*.20,math.sin(a)*pr*.20,ph-.012))
        mid=start.lerp(tip,.50)+Vector((-.015*math.sin(a),.015*math.cos(a),0))
        b.tube("stem",[start,mid,tip],.003 if h<1 else .005,"leaf",sides=6)
        for j in range(3):
            attach=start.lerp(tip,.36+j*.22)
            theta=a+j*1.4
            end=attach+Vector((math.cos(theta)*w*.28,math.sin(theta)*d*.28,(.08-j*.018)*h))
            _leaf(b,"leaf",attach,end,w*.18,"leaf_light" if (i+j)%3==0 else "leaf")


def _art(b,mirror=False):
    w,d,h=b.w,b.d,b.h
    rail=.018
    if mirror and b.options.get('round'):
        radius=min(w,h)/2
        ring=b.lathe('round-oak-frame',[(radius-rail,0),(radius,0),(radius,d),(radius-rail,d),(radius-rail,0)],(0,0,0),'oak',64)
        ring.rotation_euler.x=math.pi/2;ring.location=(0,0,h/2)
        y=-d-.0015;rr=radius-rail
        face=b.mesh('round-reflection-plane',[(rr*math.cos(TAU*i/64),y,h/2+rr*math.sin(TAU*i/64)) for i in range(64)],[tuple(range(64))],'mirror',False,collide=False)
        face['mirror']=True;face['mirror_id']=b.name+'.reflection';face['cast_shadow']=False
        return
    b.box("backing",(w,d*.43,h),(0,d*.25,h/2),"oak",.002)
    for sx in (-1,1): b.box("frame-side",(rail,d,h),(sx*(w-rail)/2,0,h/2),"oak",.002,grain="z")
    for sy in (-1,1): b.box("frame-end",(w-rail*2,d,rail),(0,0,(rail/2 if sy<0 else h-rail/2)),"oak",.002)
    b.box("mounted-print" if not mirror else "mirror-surface",(w-rail*2,.003,h-rail*2),(0,-d*.26,h/2),"matboard",.001)
    if mirror:
        yy=-d*.26-.0016
        face=b.mesh("reflection-plane",[(-w/2+rail,yy,rail),(w/2-rail,yy,rail),(w/2-rail,yy,h-rail),(-w/2+rail,yy,h-rail)],[(0,1,2,3)],"mirror",False,collide=False)
        face["mirror"]=True;face["mirror_id"]=b.name+".reflection";face["cast_shadow"]=False
        return
    # Original abstract print built as thin coloured polygons, no empty frame.
    iw,ih=w*.72,h*.74;y=-d*.26-.0022
    def shape(suffix,points,mat):
        verts=[(x*iw,y,z*ih+h/2) for x,z in points]
        return b.mesh(suffix,verts,[tuple(range(len(verts)))],mat,False,collide=False)
    shape("sand-field",[(-.50,-.50),(.50,-.50),(.50,-.12),(.31,.01),(-.15,-.09),(-.50,.03)],"art_sand")
    circle=[(math.cos(TAU*i/48)*.20+.16,math.sin(TAU*i/48)*.20+.19) for i in range(48)]
    shape("clay-disc",circle,"art_clay")
    shape("sage-arch",[(-.34,-.31),(-.08,-.31),(-.08,.09),(-.12,.24),(-.22,.31),(-.32,.24),(-.37,.09)],"art_sage")
    # Fine botanical stems give scale; each branch remains within the paper.
    points=[(-iw*.15,y-.001,h*.24),(-iw*.06,y-.001,h*.42),(iw*.02,y-.001,h*.62)]
    b.tube("ink-stem",points,.0012,"black",sides=6)
    for i in range(4):
        z=h*(.32+i*.07);x=iw*(-.12+i*.025)
        b.tube("ink-leaf",[(x,y-.001,z),(x+iw*.10,y-.001,z+h*.055),(x+iw*.03,y-.001,z+h*.025)],.001,"black",sides=5)


def _casework(b,kind):
    w,d,h=b.w,b.d,b.h
    if kind in ("desk","bench"):
        _table(b,"dining_table" if kind=="desk" else "coffee_table")
        if kind=="desk": _cabinet_face(b,"pencil-drawer",0,h-.095,w*.55,.10,-d*.50,"oak")
        else:b.soft("bench-pad",(w*.92,d*.92,.045),(0,0,h+.025),"linen",puff=.05)
        return
    plinth=.08
    b.box("carcass",(w,d,h-plinth),(0,0,(h+plinth)/2),"oak",.005,grain="z")
    b.box("recessed-base",(w-.09,d-.09,plinth),(0,0,plinth/2),"black",.003)
    if kind=="wardrobe":
        count=max(2,round(w/.55))
        for i in range(count):
            dw=w/count
            x=(i-(count-1)/2)*dw
            _cabinet_face(b,"door",x,(h+plinth)/2,dw-.004,h-plinth-.006,-d/2-.010,"kitchen",False)
            _handle(b,"oak-pull",x+(dw*.27 if i%2==0 else -dw*.27),-d/2-.045,h*.46,.20,True,"oak")
    else:
        for i in range(3):
            dh=(h-plinth-.03)/3
            _cabinet_face(b,"drawer",0,plinth+.01+(i+.5)*dh,w-.020,dh-.004,-d/2-.009,"oak")


def _stove(b):
    w,d,h=b.w,b.d,b.h
    legs=.065
    for sx in (-1,1):
        for sy in (-1,1): b.box("foot",(.035,.035,legs),(sx*w*.38,sy*d*.35,legs/2),"black",.004)
    body=h-legs
    # Firebox back/sides/top, visibly hollow front, with heavy cast frame.
    b.box("back",(w,.025,body),(0,d/2-.0125,legs+body/2),"black",.008)
    for sx in (-1,1): b.box("side",(.025,d,body),(sx*(w/2-.0125),0,legs+body/2),"black",.008)
    for z in (legs+.015,h-.015):b.box("top-bottom",(w,d,.030),(0,0,z),"black",.008)
    openingw=w*.76;openingh=body*.67;y=-d/2-.008;zc=legs+body*.53
    for sx in (-1,1): b.box("door-side",(.035,.030,openingh+.060),(sx*(openingw/2+.0175),y,zc),"black",.006)
    for sz in (-1,1): b.box("door-rail",(openingw,.030,.030),(0,y,zc+sz*(openingh/2+.015)),"black",.006)
    # Transparent glazing lets the individually modelled logs remain discernible.
    b.box("door-glass",(openingw,.003,openingh),(0,y+.004,zc),"glass",.004)
    for i in range(3):
        b.rod("split-log",(-w*.26,-d*.05+i*.055,legs+.055+i*.025),(w*.23,-d*.05+i*.055,legs+.10+i*.025),.027,"oak",sides=9)
    b.box("ash-bed",(w*.70,d*.65,.012),(0,0,legs+.026),"black",.003)
    _handle(b,"door-latch",w*.38,y-.035,zc,.105,True,"black")
    b.box("air-control",(w*.35,.018,.012),(0,y-.015,legs+.048),"metal",.003)
    b.root["fire_glow"]="off_daytime"
    # Root must route the flue into the measured chimney recess; no guessed pipe.


def _build_fitting(b,kind):
    if kind.startswith("kitchen_"): _kitchen(b,kind)
    elif kind=="oven":
        b.box("oven-body",(b.w-.02,b.d-.035,b.h-.02),(0,.012,b.h/2),"black",.006)
        _oven_front(b,b.w,b.h,-b.d/2,b.h/2)
    elif kind=="fridge":_fridge(b)
    elif kind=="hob":_hob_at(b,b.w,b.d,b.h/2)
    elif kind in ("sink","basin"):_bowl_shell(b,"basin",b.w,b.d,b.h,(0,0,0),"metal" if kind=="sink" else "glaze",power=.26 if kind=="sink" else .48)
    elif kind=="tap":_tap_at(b,0,b.d*.38,0,b.h,b.d*.76)
    elif kind=="vanity":_vanity(b)
    elif kind=="toilet":_toilet(b)
    elif kind=="bath":_bath(b)
    elif kind=="shower":_shower(b)
    elif kind in ("radiator","towel_rail"):_radiator(b,kind=="towel_rail")
    elif kind in ("pendant","floor_lamp","table_lamp","wall_light","downlight"):_light(b,kind)
    elif kind in ("books","book_stack"):_books(b,kind=="book_stack")
    elif kind in ("vase","bowl"):_vase(b,kind=="bowl")
    elif kind=="plant":_plant(b)
    elif kind in ("art","mirror"):_art(b,kind=="mirror")
    elif kind in ("wardrobe","dresser","desk","bench"):_casework(b,kind)
    elif kind=="stove":_stove(b)
    else:raise NotImplementedError(kind)
