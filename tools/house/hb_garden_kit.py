"""Dress the surveyed lawn in place. All fruit contacts the existing lawn mesh."""
import json,random,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
KIT=Path(__file__).resolve().parents[1]/'library/kit'
sys.path.insert(0,str(KIT))
from furnishings import apple_geometry

def apply():
    lawns=[ob for ob in bpy.data.objects if ob.type=='MESH' and ob.name.split('.')[0] in {'G2_lawn','G2_lawn_west'}]
    trunk=next((ob for ob in bpy.data.objects if ob.name.startswith('island_tree') and 'trunk' in ob.name),None)
    if not lawns or not trunk:return
    mat=bpy.data.materials.new('Studio turf Grass001');mat.use_nodes=True;nt=mat.node_tree;bs=nt.nodes.get('Principled BSDF')
    for record in json.loads((KIT/'garden/sources.json').read_text()):
        node=nt.nodes.new('ShaderNodeTexImage');node.image=bpy.data.images.load(str(KIT/'garden'/record['file']),check_existing=True)
        channel=record['channel'];src=node.outputs['Color']
        if channel!='Color':node.image.colorspace_settings.name='Non-Color'
        if channel=='NormalGL':
            n=nt.nodes.new('ShaderNodeNormalMap');n.inputs['Strength'].default_value=.45;nt.links.new(src,n.inputs['Color']);src=n.outputs['Normal']
        nt.links.new(src,bs.inputs[{'Color':'Base Color','NormalGL':'Normal','Roughness':'Roughness'}[channel]])
    mat['licence']='CC0-1.0';mat['source_url']='https://ambientcg.com/a/Grass001';mat['physical_repeat_m']=1.4
    for ob in lawns:
        me=ob.data;me.materials.clear();me.materials.append(mat)
        uv=me.uv_layers.active or me.uv_layers.new()
        for loop in me.loops:
            p=ob.matrix_world@me.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(p.x/1.4,p.y/1.4)
    centre=trunk.matrix_world.translation
    rng=random.Random(73);verts=[];faces=[];colours=[]
    for _ in range(80):
        a=rng.random()*2*math.pi;r=rng.uniform(.45,1.82)
        top=Vector((centre.x+math.cos(a)*r,centre.y+math.sin(a)*r,centre.z+2))
        for lawn in lawns:
            inv=lawn.matrix_world.inverted();hit,co,normal,_=lawn.ray_cast(inv@top,inv.to_3x3()@Vector((0,0,-1)))
            if not hit:continue
            p=lawn.matrix_world@co;size=rng.uniform(.059,.081);v,f=apple_geometry((size,size*.96,size*.92),rng.random()*6.28,rings=10,sides=18)
            n=len(verts);verts.extend((p.x+x,p.y+y,p.z+z+size*.46) for x,y,z in v);faces.extend(tuple(n+i for i in tri) for tri in f)
            colours.extend([rng.randrange(2)]*len(f));break
        if len(verts)>=12*164:break
    if verts:
        mesh=bpy.data.meshes.new('Fallen garden apples');mesh.from_pydata(verts,[],faces);mesh.update()
        for shade,rgba in [('russet',(.37,.088,.040,1)),('green',(.33,.37,.095,1))]:
            m=bpy.data.materials.new('Studio apple '+shade);m.use_nodes=True;shader=m.node_tree.nodes.get('Principled BSDF')
            shader.inputs['Base Color'].default_value=rgba;shader.inputs['Roughness'].default_value=.32;mesh.materials.append(m)
        for face,idx in zip(mesh.polygons,colours):face.material_index=idx;face.use_smooth=True
        ob=bpy.data.objects.new('Garden-fallen-apples',mesh);bpy.context.scene.collection.objects.link(ob)
        for k,v in dict(element=ob.name,group='fitting',storey='site',stage_in=1,seq=0.,category='existing',collide=False,context=True,plain_label='Fallen apples').items():ob[k]=v
