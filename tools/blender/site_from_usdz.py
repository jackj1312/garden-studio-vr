"""Blender helpers for turning an Apple photogrammetry USDZ into a site GLB.

Run inside Blender (MCP exec or `blender -b -P`). Steps, each a function:
  load(path)            import the USDZ into a scene called "Site", join into one mesh
  level(obj)            find the ground plane by RANSAC over a vertex sample and rotate /
                        translate so it is z = 0 (XY centred)
  measure(obj)          print dimensions so a known distance can set the scale
  finish(obj, scale, out_glb, tex=4096)   scale, shrink textures, export Draco+WebP GLB
"""
import bpy, bmesh, random, math, os
from mathutils import Vector, Matrix

def load(path):
    if "Site" not in bpy.data.scenes:
        bpy.data.scenes.new("Site")
    sc = bpy.data.scenes["Site"]
    bpy.context.window.scene = sc
    before = set(bpy.data.objects)
    bpy.ops.wm.usd_import(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == 'MESH']
    for o in new: o.select_set(o in meshes)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = "Site"
    for e in [o for o in new if o.type == 'EMPTY']:
        bpy.data.objects.remove(e)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print("loaded", obj.name, "verts", len(obj.data.vertices), "dims", [round(d, 2) for d in obj.dimensions])
    return obj

def level(obj, sample=20000, iters=400, tol=0.04):
    """RANSAC plane fit on a vertex sample; the ground is the plane with the most inliers
    whose normal is within 35 degrees of the mesh's thinnest axis."""
    verts = obj.data.vertices
    pts = [verts[i].co.copy() for i in random.sample(range(len(verts)), min(sample, len(verts)))]
    best = (0, None, None)
    for _ in range(iters):
        a, b, c = random.sample(pts, 3)
        n = (b - a).cross(c - a)
        if n.length < 1e-6: continue
        n.normalize()
        d = -n.dot(a)
        inl = sum(1 for p in pts if abs(n.dot(p) + d) < tol)
        if inl > best[0]: best = (inl, n, d)
    inl, n, d = best
    if n.z < 0: n, d = -n, -d
    print("ground plane inliers", inl, "of", len(pts), "normal", [round(x, 3) for x in n])
    rot = n.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()
    obj.matrix_world = rot @ obj.matrix_world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # plane to z = 0 (use the inlier median height after rotation)
    zs = sorted((rot @ Vector((*p, 1.0))).z for p in pts if abs(n.dot(p) + d) < tol)
    z0 = zs[len(zs) // 2]
    bb = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    cx = sum(v.x for v in bb) / 8; cy = sum(v.y for v in bb) / 8
    obj.matrix_world = Matrix.Translation((-cx, -cy, -z0)) @ obj.matrix_world
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print("levelled; dims", [round(x, 2) for x in obj.dimensions])

def measure(obj):
    print("dims x,y,z:", [round(x, 3) for x in obj.dimensions])

def finish(obj, scale, out_glb, tex=4096):
    obj.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(scale=True)
    for img in bpy.data.images:
        if img.size[0] > tex:
            img.scale(tex, tex)
    for sc in bpy.data.scenes:
        for o in sc.objects: o.select_set(False, view_layer=sc.view_layers[0])
    obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', use_selection=True, use_active_scene=True,
        export_apply=True, export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
        export_image_format='WEBP', export_image_quality=85, export_normals=True, export_texcoords=True,
        export_materials='EXPORT', export_animations=False, export_yup=True)
    print("wrote", out_glb, os.path.getsize(out_glb) // 1024, "KB")
