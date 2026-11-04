"""Reversible Unreal garden material and geometry pass; uses the saved house scene."""
import json, os, re
import unreal
import garden_ue2 as s

def apply():
    folder='/Game/GardenLook'
    mapping=json.load(open('/tmp/job/material-map.json'))
    gltf=json.load(open(os.path.join(s.BUNDLE,'House.gltf')))
    selected={r['id']:r for r in mapping if r['vertex'] or any(k in r['name'] for k in ['FG2_timber','FG2_paving','FG_gravel','Studio turf','Surveyed leaves','island_tree'])}
    tex_cache={}
    def texture(info,normal=False,mask=False):
        if not info:return None
        index=info['index'];key=(index,normal,mask)
        if key in tex_cache:return tex_cache[key]
        src=gltf['images'][gltf['textures'][index]['source']]['uri']
        path=os.path.join(s.BUNDLE,src)
        dest=folder+('/Normals' if normal else '/Masks' if mask else '/Colours')
        target=s.asset_path(dest,path)
        if not s.EAL.does_asset_exist(target):s.import_files([path],dest)
        t=s.load(target)
        if not t:raise RuntimeError('Missing garden texture '+src)
        if normal:
            s.setp(t,'compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP)
            s.setp(t,'srgb',False);s.setp(t,'flip_green_channel',True)
        elif mask:
            s.setp(t,'compression_settings',unreal.TextureCompressionSettings.TC_MASKS);s.setp(t,'srgb',False)
        s.EAL.save_loaded_asset(t);tex_cache[key]=t;return t
    def make(name,desc,vertex=False,foliage=False):
        m=s.fresh(name,folder+'/Materials',unreal.Material,unreal.MaterialFactoryNew())
        s.setp(m,'two_sided',desc.get('doubleSided',False) or foliage)
        if foliage:s.setp(m,'shading_model',unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
        pbr=desc.get('pbrMetallicRoughness',{})
        def sample(info,normal=False,mask=False):
            t=texture(info,normal,mask)
            if not t:return None
            uv=s.X(m,unreal.MaterialExpressionTextureCoordinate,-800,0)
            tr=info.get('extensions',{}).get('KHR_texture_transform',{})
            scale=tr.get('scale',[1,1]);off=tr.get('offset',[0,0])
            s.setp(uv,'u_tiling',scale[0]);s.setp(uv,'v_tiling',scale[1])
            if off!=[0,0]:
                c=s.X(m,unreal.MaterialExpressionConstant2Vector,-700,200,r=off[0],g=off[1]);add=s.X(m,unreal.MaterialExpressionAdd,-500,0);s.C(uv,'',add,'A');s.C(c,'',add,'B');uv=add
            typ=unreal.MaterialSamplerType
            return s.tex_param(m,'Texture_'+str(info['index']),-400,0,uv,typ.SAMPLERTYPE_NORMAL if normal else typ.SAMPLERTYPE_MASKS if mask else typ.SAMPLERTYPE_COLOR,t)
        base=sample(pbr.get('baseColorTexture'));factor=pbr.get('baseColorFactor',[1,1,1,1])
        tint=s.vector(m,'Tint',factor,-300,300)
        bc=s.mul(m,base,tint,0,0,'RGB','RGB') if base else tint
        if vertex:
            vc=s.X(m,unreal.MaterialExpressionVertexColor,-400,-300);bc=s.mul(m,bc,vc,100,0,'','')
        s.P(bc,'',unreal.MaterialProperty.MP_BASE_COLOR)
        if foliage:
            sub=s.mul(m,bc,s.scalar(m,'Transmission',.35,-100,400),200,200);s.P(sub,'',unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
        rough=sample(pbr.get('metallicRoughnessTexture'),mask=True)
        if rough:s.P(rough,'G',unreal.MaterialProperty.MP_ROUGHNESS)
        else:s.P(s.scalar(m,'Roughness',pbr.get('roughnessFactor',.8),0,300),'',unreal.MaterialProperty.MP_ROUGHNESS)
        normal=sample(desc.get('normalTexture'),normal=True)
        if normal:s.P(normal,'RGB',unreal.MaterialProperty.MP_NORMAL)
        if desc.get('alphaMode')=='MASK' and base:
            s.setp(m,'blend_mode',unreal.BlendMode.BLEND_MASKED);s.setp(m,'opacity_mask_clip_value',desc.get('alphaCutoff',.5));s.P(base,'A',unreal.MaterialProperty.MP_OPACITY_MASK)
        s.MEL.recompile_material(m);s.EAL.save_loaded_asset(m);return m
    replacements={}
    for key,row in selected.items():
        desc=gltf['materials'][int(key.split('_')[1])]
        replacements[key]=make('Garden_'+key,desc,row['vertex'],row['vertex'] or 'leaves' in row['name'])
    changed=0
    seen=[]
    for actor in s.EAS.get_all_level_actors():
        if not isinstance(actor,unreal.StaticMeshActor):continue
        c=actor.static_mesh_component
        for i in range(c.get_num_materials()):
            old=c.get_material(i)
            if old and len(seen)<20:seen.append(old.get_name())
            match=re.search(r'Finish_\d+',old.get_name()) if old else None
            if match and match.group() in replacements:c.set_material(i,replacements[match.group()]);changed+=1
    if not changed: raise RuntimeError('No garden materials rebound; seen '+repr(seen))
    # Separate new detail assets: original surveyed meshes and boundaries remain intact.
    if not any(a.get_actor_label().startswith('GardenDetail_') for a in s.EAS.get_all_level_actors()):
        task=unreal.AssetImportTask();task.filename='/tmp/job/detail/GardenDetail.gltf';task.destination_path=folder+'/Detail';task.automated=True;task.save=True;s.AT.import_asset_tasks([task])
        detailmats={k:make('GardenDetail_'+k,{'doubleSided':True,'pbrMetallicRoughness':{'roughnessFactor':.85}},True,k=='Grass') for k in ['Grass','Gravel']}
        for data in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(folder+'/Detail',recursive=True):
            if str(data.asset_class_path.asset_name)!='StaticMesh':continue
            mesh=data.get_asset();actor=s.EAS.spawn_actor_from_object(mesh,unreal.Vector(0,0,0),unreal.Rotator(0,0,0));actor.set_actor_label('GardenDetail_'+mesh.get_name())
            c=actor.static_mesh_component
            mat=detailmats['Grass' if 'grass' in mesh.get_name().lower() else 'Gravel']
            for i in range(c.get_num_materials()):c.set_material(i,mat)
    for a in s.EAS.get_all_level_actors():
        if isinstance(a,unreal.SkyLight):s.setp(a.light_component,'intensity',2.2)
        if isinstance(a,unreal.DirectionalLight):s.setp(a.light_component,'light_source_angle',1.2)
    unreal.EditorLoadingAndSavingUtils.save_current_level()
    s.EAL.save_directory(folder,only_if_is_dirty=True,recursive=True)
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True)
    s.REPORT['garden_detail']={'material_slots':changed,'material_count':len(replacements),'geometry':'survey-surface sampled grass and gravel'}
    s.log('Garden look applied',s.REPORT['garden_detail'])
