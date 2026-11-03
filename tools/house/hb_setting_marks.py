"""Small repairs to the registered, surveyed 23 Battle Road setting from Jack's walk 2.

All stations written here are viewer (house) metres. Blender geometry uses (X,-Z,Y).
The source model and the signed house brickwork remain independent of these repairs.
"""
from pathlib import Path
import bpy
import bmesh
from mathutils import Matrix, Vector

# Original triangulated paving section at Jack's marked X=4.964 m. Keep the
# surveyed far line and move the bed rim by this exact draw-frame delta.
BED_FRONT = 3.0198919773101807
CROSS_PATH_FAR = 4.1094889640808105
CROSS_PATH_NEAR = CROSS_PATH_FAR - .900
BED_INCREASE = CROSS_PATH_NEAR - BED_FRONT
REAR_PERGOLA = {"Perg_post_3", "Perg_post_4", "Perg_beam_rear"}


def plan_point(vertex):
    return Vector((vertex.x, -vertex.y, vertex.z))


def blender_point(x, z, height):
    return (x, -z, height)


def bounds(ob):
    corners = [plan_point(ob.matrix_world @ Vector(p)) for p in ob.bound_box]
    return tuple((min(p[i] for p in corners), max(p[i] for p in corners)) for i in range(3))


def material(name):
    m = bpy.data.materials.get(name)
    if m is None:
        raise ValueError("Survey material missing: " + name)
    return m


def labelled_mesh(name, verts, faces, template, label, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for key in template.keys():
        ob[key] = template[key]
    ob["element"] = "SET-" + name
    ob["label"] = ob["plain_label"] = label
    me.materials.append(mat)
    return ob


def map_faces(ob, repeat, vertical=False):
    """Real-metre dominant-axis coordinates (also on end grain/returns)."""
    me = ob.data
    uv = me.uv_layers.active or me.uv_layers.new()
    for face in me.polygons:
        axis = max(range(3), key=lambda i: abs(face.normal[i]))
        for j in face.loop_indices:
            p = me.vertices[me.loops[j].vertex_index].co
            u, v = ((p.x, p.y), (p.x, p.z), (p.y, p.z))[(2, 1, 0).index(axis)]
            if vertical and axis != 2:
                u, v = v, -u
            uv.data[j].uv = (u / repeat[0], v / repeat[1])


def rectangular_member(name, x, depth, height, source, label, mat, repeat=(.47, .47), vertical=False):
    left, right = x
    back, front = depth
    bottom, top = height
    verts = [blender_point(xx, zz, yy) for yy in (bottom, top) for zz in (back, front) for xx in (left, right)]
    # Depth grows towards the road (-Blender Y). Winding is outward on each side.
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    ob = labelled_mesh(name, verts, faces, source, label, mat)
    map_faces(ob, repeat, vertical)
    return ob


def edging_runs(me):
    # A glTF import splits points at UV/normal seams. The bevelled units touch
    # end-to-end, forming three distinct welded runs, one per side of this bed.
    parent = list(range(len(me.vertices)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    positions = {}
    for v in me.vertices:
        key = tuple(round(k, 5) for k in v.co)
        parent[find(v.index)] = find(positions.setdefault(key, v.index))
    for edge in me.edges:
        a, b = edge.vertices
        parent[find(a)] = find(b)
    groups = {}
    for v in me.vertices:
        groups.setdefault(find(v.index), []).append(v)
    return groups.values()


def bed_and_paving(grey):
    bed = bpy.data.objects["G2_house_bed"]
    paving = bpy.data.objects["G2_paving"]
    for ob in (bed, paving):
        me = ob.data
        mw = ob.matrix_world
        inv = mw.inverted()
        moved = set()
        for v in me.vertices:
            w = mw @ v.co
            if 2.879 <= w.x <= 6.481 and abs(-w.y - BED_FRONT) < .003:
                w.y -= BED_INCREASE
                v.co = inv @ w
                moved.add(v.index)
        if not moved:
            raise ValueError("Expected the front bed edge in " + ob.name)
        # The two ground planes already have affine real-metre UVs. Continue their original
        # slope into the altered footprint instead of stretching a texture across a triangle.
        uv = me.uv_layers.active
        if uv:
            flat = [(mw @ me.vertices[lp.vertex_index].co, uv.data[lp.index].uv.copy()) for lp in me.loops if lp.vertex_index not in moved]
            p, pu = flat[0]
            delta = None
            for q, qu in flat[1:]:
                for r, ru in flat[2:]:
                    dx, dy = q.x - p.x, q.y - p.y
                    ex, ey = r.x - p.x, r.y - p.y
                    det = dx * ey - ex * dy
                    if abs(det) > .01:
                        delta = ((ru - pu) * dx - (qu - pu) * ex) * (-BED_INCREASE / det)
                        break
                if delta is not None:
                    break
            if delta is None:
                raise ValueError("Cannot recover real-metre UV basis on " + ob.name)
            for lp in me.loops:
                if lp.vertex_index in moved:
                    uv.data[lp.index].uv += delta
        me.update()
    edging = bpy.data.objects["G2_house_bed_edging"]
    mw = edging.matrix_world
    vector = mw.inverted().to_3x3() @ Vector((0, -BED_INCREASE, 0))
    runs = []
    for group in edging_runs(edging.data):
        pts = [plan_point(mw @ v.co) for v in group]
        runs.append((group, (min(p.x for p in pts), max(p.x for p in pts),
                             min(p.y for p in pts), max(p.y for p in pts))))
    if len(runs) != 3:
        raise ValueError("Expected three measured bed edging runs")
    runs.sort(key=lambda entry: entry[1][0])
    (_, left), (front_points, front), (_, right) = runs
    if front[1] - front[0] < 3 or max(left[1]-left[0], right[1]-right[0]) > .12:
        raise ValueError("Front bed edging run identity changed")
    for v in front_points:
        v.co += vector
    edging.data.update()
    near, far = front[2] + BED_INCREASE, front[3] + BED_INCREASE
    for side, run in (("left", left), ("right", right)):
        for_end = near - .001
        if not .06 < for_end - run[3] < .24:
            raise ValueError("Unexpected front bed return distance on " + side)
        rectangular_member("G2_house_bed_return_" + side, run[:2], (run[3]+.001, for_end),
                           (-.281, -.225), edging, "Cut grey sett at the house bed", grey, (.45, .45))
    # The first transverse sett starts just beyond the outside edge of the left side.
    # This is its actual cut, rather than an extra square over the corner of either run.
    rectangular_member("G2_house_bed_corner_left", (left[0], front[0]-.001), (near, far),
                       (-.281, -.225), edging, "House bed return corner", grey, (.45, .45))


def close_kerb_corner(grey):
    # Source kerb and paving are laid in real separated units. At the gate-side turn the
    # kerb continuation needs one end-cut, not a stretch of its entire run (F92).
    foot = bpy.data.objects["G2_border_foot_to_fence"]
    kerb = bpy.data.objects["G2_lawn_kerb"]
    points = [plan_point(kerb.matrix_world @ v.co) for v in kerb.data.vertices]
    start = min(p.y for p in points)
    end = bounds(foot)[1][1]
    xs = [p.x for p in points if p.y < start + .011]
    if not .080 < start - end < .120 or not .085 < max(xs) - min(xs) < .105:
        raise ValueError("Unrecognised gate-side paving cut")
    rectangular_member("G2_lawn_kerb_terminal", (min(xs), max(xs)), (end, start),
                       (-.281, -.225), kerb, "Grey block joining the drive and lawn edgings", grey, (.45, .45))


def shed_doors():
    facade = bpy.data.objects["Shed_front"]
    (left, right), (back, front), (bottom, top) = bounds(facade)
    boards, iron = material("FG_shed_red_gltf"), material("FG2_drain_grate_gltf")
    def part(suffix, x, z, y, mat=boards, vertical=False):
        return rectangular_member("Shed_" + suffix, x, z, y, facade, suffix.replace("_", " "), mat,
                                  (.45, .45), vertical)
    # Registered crop (shed_front_nobroom, walk_0077/79/83): cladding reaches
    # x~.205 in the image; meeting stile at .505, right jamb at ~.946.
    w = right - left
    xa, seam, xb = (left + w * (u - .106) / (1 - .106) for u in (.205, .505, .946))
    jamb = .031
    part("front_siding_house", (left, xa-jamb), (back, front), (bottom, top))
    part("front_siding_fence", (xb+jamb, right), (back, front), (bottom, top))
    part("front_jamb_left", (xa-jamb, xa), (back, front+.009), (bottom, top), vertical=True)
    part("front_jamb_right", (xb, xb+jamb), (back, front+.009), (bottom, top), vertical=True)
    part("front_door_head", (xa, xb), (back, front+.009), (top-.036, top))
    part("front_door_sill", (xa, xb), (back, front+.009), (bottom, bottom+.024))
    door_y = (bottom+.029, top-.040)
    door_z = (back-.005, front-.011)
    for side, span in (("left", (xa+.004, seam-.0025)), ("right", (seam+.0025, xb-.004))):
        part("door_" + side, span, door_z, door_y, vertical=True)
        for suffix, y in (("top", door_y[1]-.18), ("foot", door_y[0]+.10)):
            outer = (span[0]+.005, span[0]+.64*(span[1]-span[0])) if side == "left" else (span[0]+.36*(span[1]-span[0]), span[1]-.005)
            part("hinge_"+side+"_"+suffix, outer, (door_z[1], door_z[1]+.006), (y, y+.020), iron)
    y = bottom + .83
    part("door_latch_plate", (seam-.051, seam+.049), (door_z[1], door_z[1]+.010), (y, y+.035), iron)
    part("door_latch_spindle", (seam-.041, seam-.019), (door_z[1]+.010, door_z[1]+.047), (y+.004, y+.026), iron)
    part("door_latch_grip", (seam-.041, seam-.019), (door_z[1]+.035, door_z[1]+.047), (y-.079, y+.004), iron)
    bpy.data.objects.remove(facade, do_unlink=True)


def pavement_entrance(grey):
    """Replace surface faces on the measured pavement, never layer coplanar additions onto it."""
    ob = bpy.data.objects["G2_pavement"]
    xx, zz, yy = bounds(ob)
    start, end = zz
    edge_l = bounds(bpy.data.objects["G2_edge_path_edging_left"])[0][0]
    edge_r = bounds(bpy.data.objects["G2_edge_path_edging_right_and_lawn_kerb"])[0][0] + .10
    left, right = -.35, .75  # retained opening between the two signed hedge ends
    inside_y, top_y = -.231, yy[1]
    outside = ob.data.materials[0]
    grass = material("FG_turf_neighbour_gltf")
    asphalt = material("FG_road_gltf")
    concrete = material("FG_kerb_gltf").copy()
    concrete.name = "Surveyed pale concrete footpath threshold"
    concrete.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (.57, .55, .48, 1)
    # walk_0001/0003 show the local sequence across the entrance. The apron's dimensions
    # beyond the measured path end are photo estimates inside the existing pavement bounds.
    xcuts = (xx[0], -1.60, left, edge_l, edge_r, right, 2.60, xx[1])
    zcuts = (start, start+.19, start+1.08, end)
    verts, faces, assigned = [], [], []
    mats = [outside, grass, asphalt, concrete]
    for xa, xb in zip(xcuts, xcuts[1:]):
        for za, zb in zip(zcuts, zcuts[1:]):
            xc, zc = (xa+xb)/2, (za+zb)/2
            patch = -1.60 < xc < 2.60
            on_path = edge_l < xc < edge_r
            m = outside
            if patch:
                m = grass
                if on_path and zc < zcuts[1]:
                    m = concrete
                elif left < xc < right and zc < zcuts[2]:
                    m = asphalt
            i = len(verts)
            def level(x,z):
                return inside_y if -1.60 < x < 2.60 and z < zcuts[1]-.001 else top_y
            verts.extend(blender_point(x,z,level(x,z)) for x,z in ((xa,za),(xa,zb),(xb,zb),(xb,za)))
            faces.append(tuple(range(i,i+4)))
            assigned.append(mats.index(m))
    me = bpy.data.meshes.new("Street paving with the surveyed pedestrian entrance")
    me.from_pydata(verts, [], faces)
    me.update()
    for m in mats:
        me.materials.append(m)
    for p, slot in zip(me.polygons, assigned):
        p.material_index = slot
    ob.data = me
    ob.matrix_world = Matrix.Identity(4)
    map_faces(ob, (1.2, 1.2))
    # Carry the original 1.8 m survey texture and its registration through every
    # retained pavement face; the local road/verge materials have their own UVs.
    uv = me.uv_layers.active
    for face in me.polygons:
        if face.material_index:
            continue
        for li in face.loop_indices:
            p = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((p.x-4.63)/1.8, (p.y+3.09)/1.8)
    # Use the existing paving surface inside the two straight border runs for the last
    # transverse course of light-grey setts, rather than an overlapping top plane.
    paving = bpy.data.objects["G2_paving"]
    me = paving.data
    bm = bmesh.new()
    bm.from_mesh(me)
    mw = paving.matrix_world
    bm.transform(mw)
    for point, normal in (((edge_l,0,0),(1,0,0)), ((edge_r,0,0),(1,0,0)), ((0,-(start-.10),0),(0,1,0))):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=point, plane_no=normal, dist=.00001)
    index = len(me.materials)
    me.materials.append(grey)
    for f in bm.faces:
        c = f.calc_center_median()
        if edge_l <= c.x <= edge_r and start-.10 < -c.y < start+.0001:
            f.material_index = index
    bm.transform(mw.inverted())
    bm.to_mesh(me)
    bm.free()
    me.update()


def apply_hardscape(grey):
    bed_and_paving(grey)
    close_kerb_corner(grey)
    shed_doors()
    pavement_entrance(grey)
    for ob in bpy.data.objects:
        if ob.name.startswith("Bench_") and not ob.name.startswith("Bench_stone_"):
            ob.location.y -= .150
        if ob.name in REAR_PERGOLA:
            ob.location.y -= .020


def street_sections(sections):
    # GF-1 is signed for three sections and the pedestrian gap. The later registered
    # points and walk_0143/0153 measure the *same driveway block* beginning at X5.63.
    west, middle, drive = sections
    return [west, middle, (min(drive[0], 5.63), drive[1])]


def surveyed_foliage():
    """Keep all registered footprints, species forms and contact heights. Supply the
    missing surface detail to just the recorded shrubs and the house border plants."""
    import numpy as np
    root = Path(__file__).resolve().parents[2] / "master"
    # Crops are interiors of real scanned blades, leaf veins and petals, not an entire
    # atlas projected across a plant. Coordinates are on a 256-unit top-left image grid.
    patches = {
        "privet": (None, None, None, (.46, .46)),
        "blade": ("grass_medium_01", (200, 97, 202, 139), (.27, .29, .17), (.022, .24)),
        "leaf": ("periwinkle_plant", (103, 222, 126, 231), (.18, .25, .11), (.035, .055)),
        "silver": ("periwinkle_plant", (103, 222, 126, 231), (.32, .36, .27), (.028, .055)),
        "petal": ("periwinkle_plant", (80, 72, 98, 82), (.35, .20, .47), (.028, .033)),
    }
    cache = {}
    def cropped_image(path, box, key, normal, tint):
        # Blender has the same reader as the main import. Use only the chosen pixels
        # in the output, so the mobile build never carries whole 2K botanical atlases.
        source = bpy.data.images.load(str(path), check_existing=False)
        if normal:
            source.colorspace_settings.name = "Non-Color"
        w,h=source.size
        pixels=np.empty(w*h*4, dtype=np.float32)
        source.pixels.foreach_get(pixels)
        pixels=pixels.reshape((h,w,4))
        x0,y0,x1,y1=box
        rgba=pixels[round(h*(1-y1/256)):round(h*(1-y0/256)),
                    round(w*x0/256):round(w*x1/256)].copy()
        bpy.data.images.remove(source)
        if tint is not None and not normal:
            mean=np.maximum(rgba[:,:,:3].mean(axis=(0,1)), .01)
            rgba[:,:,:3]=np.clip(rgba[:,:,:3] / mean * np.array(tint), 0, 1)
        h,w=rgba.shape[:2]
        image=bpy.data.images.new("Garden "+key+(" normal" if normal else " colour"), w,h,alpha=False)
        if normal:
            image.colorspace_settings.name = "Non-Color"
        image.pixels.foreach_set(rgba.flatten())
        image.pack()
        return image
    def shader(key):
        if key in cache:
            return cache[key]
        asset, box, tint, repeat=patches[key]
        m=bpy.data.materials.new("Surveyed leaves "+key)
        m.use_nodes=True
        m.use_backface_culling=False
        m["foliage"]=True
        m["quest_cast_shadow"]=False
        m["repeat_m"]=list(repeat)
        if not asset:
            # The registered clipped hedge's existing normal map corresponds to its
            # photographic face. The small leaf tile is from this garden's presentation library.
            m["source"]="Jack's garden / master/phototex/hedge_leaf.jpg"
            m["licence"]="Client's private garden photography"
            diffuse=bpy.data.images.load(str(root/"phototex"/"hedge_leaf.jpg"),check_existing=True)
            source=material("FG_hedge_face_gltf").node_tree
            normal=next(n.image for n in source.nodes if n.type=="TEX_IMAGE" and n.image and n.image.colorspace_settings.name=="Non-Color")
        else:
            m["source"]="https://polyhaven.com/a/"+asset
            m["licence"]="CC0-1.0"
            folder=root/"polyhaven"/asset/"textures"
            diffuse=cropped_image(folder/(asset+"_diff_2k.jpg"),box,key,False,tint)
            normal=cropped_image(folder/(asset+"_nor_gl_2k.jpg"),box,key,True,None)
        nt=m.node_tree
        bs=nt.nodes.get("Principled BSDF")
        bs.inputs["Roughness"].default_value=.78
        tex=nt.nodes.new("ShaderNodeTexImage"); tex.image=diffuse
        norm=nt.nodes.new("ShaderNodeTexImage"); norm.image=normal
        n=nt.nodes.new("ShaderNodeNormalMap"); n.inputs["Strength"].default_value=.35
        nt.links.new(tex.outputs["Color"],bs.inputs["Base Color"])
        nt.links.new(norm.outputs["Color"],n.inputs["Color"])
        nt.links.new(n.outputs["Normal"],bs.inputs["Normal"])
        cache[key]=m
        return m
    for ob in list(bpy.data.objects):
        nm=ob.name
        if not nm.startswith(("Plant2_house_", "Plant2_door_shrub_")):
            continue
        me=ob.data.copy()
        ob.data=me
        col=me.color_attributes.active_color
        keys=("privet",) if nm.startswith("Plant2_door_") or "box_ball" in nm else ("blade",) if "stipa" in nm else ("silver" if "lavender" in nm else "leaf","petal")
        me.materials.clear()
        for key in keys:
            me.materials.append(shader(key))
        uv=me.uv_layers.active or me.uv_layers.new()
        mw=ob.matrix_world
        normal_transform=mw.inverted_safe().transposed().to_3x3()
        for f in me.polygons:
            if len(keys)>1 and col is not None:
                rgb=[0.,0.,0.]
                for li in f.loop_indices:
                    idx=me.loops[li].vertex_index if col.domain=="POINT" else li
                    sample=col.data[idx].color
                    for ch in range(3):
                        rgb[ch]+=sample[ch]
                f.material_index=int(rgb[2] > rgb[1]*1.12)
            key=keys[f.material_index]
            ru,rv=patches[key][3]
            normal=normal_transform @ f.normal
            axis=max(range(3),key=lambda i:abs(normal[i]))
            for li in f.loop_indices:
                p=mw @ me.vertices[me.loops[li].vertex_index].co
                u,v=(p.x,p.y) if axis==2 else (p.x if axis==1 else p.y,p.z)
                uv.data[li].uv=(u/ru,v/rv)
        # Base colour/veins now come from recorded materials. Removing the old
        # proxy's near-black multipliers also keeps generic glTF clients consistent.
        if col is not None:
            me.color_attributes.remove(col)
        me.update()
