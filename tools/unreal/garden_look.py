"""Reversible Unreal garden material and geometry pass; uses the saved house scene."""
import json, os, re
import unreal
import garden_ue2 as s

def apply():
    folder='/Game/GardenGolden'
    mapping=json.load(open(os.path.join(os.path.dirname(s.BUNDLE),'material-map.json')))
    basepath=s.BUNDLE
    gltf=json.load(open(os.path.join(s.BUNDLE,'House.gltf')))
    selected={r['id']:r for r in mapping if r['vertex'] or any(k in r['name'] for k in ['FG2_timber','FG2_paving','FG_gravel','Studio turf','Surveyed leaves','island_tree'])}
    tex_cache={}
    def texture(info,normal=False,mask=False):
        if not info:return None
        index=info['index'];key=(index,normal,mask)
        if key in tex_cache:return tex_cache[key]
        src=gltf['images'][gltf['textures'][index]['source']]['uri']
        path=os.path.join(basepath,src)
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
        if name.endswith('Finish_213') and os.path.exists('/tmp/job/paving/PavingNormal.png'):
            def relief(file,normalmap=False):
                target=s.asset_path(folder+'/Relief',file)
                if not s.EAL.does_asset_exist(target):s.import_files([file],folder+'/Relief')
                tx=s.load(target);s.setp(tx,'srgb',False)
                if normalmap:s.setp(tx,'compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP)
                else:s.setp(tx,'compression_settings',unreal.TextureCompressionSettings.TC_MASKS)
                uv=s.X(m,unreal.MaterialExpressionTextureCoordinate,-900,600)
                tr=pbr.get('baseColorTexture',{}).get('extensions',{}).get('KHR_texture_transform',{})
                scale=tr.get('scale',[1,1]);s.setp(uv,'u_tiling',scale[0]);s.setp(uv,'v_tiling',scale[1])
                return s.tex_param(m,file.split('/')[-1],-600,600,uv,unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL if normalmap else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS,tx)
            normal=relief('/tmp/job/paving/PavingNormal.png',True)
            rr=relief('/tmp/job/paving/PavingRoughness.png');s.P(rr,'R',unreal.MaterialProperty.MP_ROUGHNESS)
            hh=relief('/tmp/job/paving/PavingHeight.png')
            attrs=s.X(m,unreal.MaterialExpressionMakeMaterialAttributes,400,600)
            names=s.MEL.get_material_expression_input_names(attrs)
            def attribute(node,output,key):
                pin=next((str(n) for n in names if str(n).replace(' ','').lower()==key.lower()),None)
                if pin is None:raise RuntimeError('Missing material attribute '+key+'; available '+repr(names))
                s.C(node,output,attrs,pin)
            attribute(bc,'','BaseColor');attribute(normal,'RGB','Normal');attribute(rr,'R','Roughness');attribute(hh,'R','Displacement')
            s.setp(m,'use_material_attributes',True);s.P(attrs,'',unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
            s.setp(m,'enable_tessellation',True)
            ds=unreal.DisplacementScaling();s.setp(ds,'magnitude',.46);s.setp(ds,'center',1.0);s.setp(m,'displacement_scaling',ds)
        if normal:s.P(normal,'RGB',unreal.MaterialProperty.MP_NORMAL)
        if desc.get('alphaMode')=='MASK' and base:
            s.setp(m,'blend_mode',unreal.BlendMode.BLEND_MASKED);s.setp(m,'opacity_mask_clip_value',desc.get('alphaCutoff',.5));s.P(base,'A',unreal.MaterialProperty.MP_OPACITY_MASK)
        if foliage and name.startswith('Native_'):
            tm=s.X(m,unreal.MaterialExpressionTime,-700,900);wave=s.X(m,unreal.MaterialExpressionSine,-500,900);s.C(tm,'',wave,'Input')
            wind=s.mul(m,wave,s.vector(m,'LeafBreezeCm',(.7,.35,.12,0),-500,1100),-200,900);s.P(wind,'',unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
        s.MEL.recompile_material(m);s.EAL.save_loaded_asset(m);return m
    replacements={}
    for key,row in selected.items():
        desc=gltf['materials'][int(key.split('_')[1])]
        replacements[key]=make('Garden_'+key,desc,row['vertex'],row['vertex'] or 'leaves' in row['name'])
    glass=s.build_glass_material('GoldenClearGlass')
    # Only clear glazing, not glazed ceramics or black appliance panels.
    for row in mapping:
        if row['name'] in ['glass','spec_GLASS-CLEAR.BRI.MAT.glass','BRI.MAT.glass','FG_glass_roof_gltf']:replacements[row['id']]=glass
    import gravel_scan
    replacements['Finish_210']=gravel_scan.material()
    replacements['Finish_208']=gravel_scan.material('granular_concrete',200.,0.)
    changed=0
    required_bindings={k:0 for k in ['Finish_208','Finish_210','Finish_213']}
    seen=[]
    for actor in s.EAS.get_all_level_actors():
        if not isinstance(actor,unreal.StaticMeshActor):continue
        c=actor.static_mesh_component
        for i in range(c.get_num_materials()):
            old=c.get_material(i)
            if old and len(seen)<20:seen.append(old.get_name())
            slots=c.static_mesh.static_materials if c.static_mesh else []
            identity=str(slots[i].material_slot_name) if i<len(slots) else ''
            match=re.search(r'Finish_\d+',identity+' '+(old.get_name() if old else ''))
            if match and match.group() in replacements:
                c.set_material(i,replacements[match.group()]);changed+=1
                if match.group() in required_bindings:required_bindings[match.group()]+=1
                if match.group() in ('Finish_210','Finish_213'):s.ensure_nanite(c.static_mesh,True)
    if not all(required_bindings.values()):raise RuntimeError('Missing ground material bindings '+repr(required_bindings))
    s.REPORT['ground_material_bindings']=required_bindings
    if not changed: raise RuntimeError('No garden materials rebound; seen '+repr(seen))
    for actor in list(s.EAS.get_all_level_actors()):
        if actor.get_actor_label().startswith('GardenDetail_') and 'gravel' in actor.get_actor_label().lower():s.EAS.destroy_actor(actor)
    # Separate new detail assets: original surveyed meshes and boundaries remain intact.
    if not any(a.get_actor_label().startswith('GardenDetail_') for a in s.EAS.get_all_level_actors()):
        task=unreal.AssetImportTask();task.filename='/tmp/job/detail-natural/GardenDetail.gltf';task.destination_path=folder+'/Detail';task.automated=True;task.save=True;s.AT.import_asset_tasks([task])
        detailmats={k:make('GardenDetail_'+k,{'doubleSided':True,'pbrMetallicRoughness':{'roughnessFactor':.85}},True,k=='Grass') for k in ['Grass','Gravel']}
        for data in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(folder+'/Detail',recursive=True):
            if str(data.asset_class_path.asset_name)!='StaticMesh':continue
            mesh=data.get_asset()
            if 'gravel' in mesh.get_name().lower():continue
            actor=s.EAS.spawn_actor_from_object(mesh,unreal.Vector(0,0,0),unreal.Rotator(0,0,0));actor.set_actor_label('GardenDetail_'+mesh.get_name())
            s.ensure_nanite(mesh,True)
            c=actor.static_mesh_component
            mat=detailmats['Grass' if 'grass' in mesh.get_name().lower() else 'Gravel']
            for i in range(c.get_num_materials()):c.set_material(i,mat)
    # Native library assets replace, rather than cover, removed presentation plants.
    for actor in list(s.EAS.get_all_level_actors()):
        if actor.get_actor_label().startswith('NativePlant_'):s.EAS.destroy_actor(actor)
    rows=json.load(open(os.path.join(s.BUNDLE,'replacement-placements.json')))
    trees=[r for r in rows if r['name'].startswith('island_tree')]
    if trees:
        rows.append({'name':'HeroTree','min':[min(r['min'][i] for r in trees) for i in range(3)],'max':[max(r['max'][i] for r in trees) for i in range(3)]})
    libraries={}
    for key in ['island_tree_02','shrub_sorrel_01','periwinkle_plant','grass_medium_01']:
        basepath='/tmp/job/foliage/'+key;gltf=json.load(open(basepath+'/'+key+'.gltf'));tex_cache.clear()
        dest=folder+'/Plants/'+key
        s.import_files([basepath+'/'+key+'.gltf'],dest)
        mats={}
        for i,desc in enumerate(gltf['materials']):
            leaf=desc.get('alphaMode')=='MASK'
            mats[desc.get('name','Material_'+str(i))]=make('Native_'+key+'_'+str(i),desc,False,leaf)
        meshes=[]
        for data in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(dest,recursive=True):
            if str(data.asset_class_path.asset_name)!='StaticMesh':continue
            mesh=data.get_asset();s.ensure_nanite(mesh,True)
            for i,slot in enumerate(mesh.static_materials):
                old=str(slot.material_slot_name)+' '+(slot.material_interface.get_name() if slot.material_interface else '')
                match=next((mats[name] for name in sorted(mats,key=len,reverse=True) if name in old),None)
                if match is None and len(mats)==1:match=next(iter(mats.values()))
                if match is None:raise RuntimeError('Unmatched native plant material '+key+' '+old)
                mesh.set_material(i,match)
                s.REPORT.setdefault('plant_slot_bindings',[]).append({'asset':key,'slot':old,'material':match.get_name()})
            s.EAL.save_loaded_asset(mesh);meshes.append(mesh)
        if not meshes:raise RuntimeError('No native plant meshes '+key)
        libraries[key]=meshes
    placed=0
    for row in rows:
        name=row['name']
        if not name.startswith('Plant2_') and name!='HeroTree':continue
        key='island_tree_02' if name=='HeroTree' or 'door_shrub' in name else 'grass_medium_01' if 'stipa' in name else 'shrub_sorrel_01' if 'box_ball' in name else 'periwinkle_plant'
        mesh=libraries[key][placed%len(libraries[key])];bb=mesh.get_bounding_box()
        lo,hi=row['min'],row['max'];size=[(hi[0]-lo[0])*100,(hi[2]-lo[2])*100,(hi[1]-lo[1])*100]
        scale=[size[0]/max(1,bb.max.x-bb.min.x),size[1]/max(1,bb.max.y-bb.min.y),size[2]/max(1,bb.max.z-bb.min.z)]
        loc=unreal.Vector((lo[0]+hi[0])*50-(bb.min.x+bb.max.x)*scale[0]/2,(lo[2]+hi[2])*50-(bb.min.y+bb.max.y)*scale[1]/2,lo[1]*100-bb.min.z*scale[2])
        a=s.EAS.spawn_actor_from_object(mesh,loc,unreal.Rotator(0,0,0));a.set_actor_scale3d(unreal.Vector(*scale));a.set_actor_label('NativePlant_'+name);placed+=1
        if name.startswith('Plant2_') and 'door_shrub' not in name:
            # Additional low clumps sit inside the original measured footprint.
            for j,(dx,dy) in enumerate([(-.18,-.12),(.17,.15)]):
                extra=s.EAS.spawn_actor_from_object(mesh,unreal.Vector(loc.x+dx*size[0],loc.y+dy*size[1],loc.z),unreal.Rotator(0,0,0))
                extra.set_actor_scale3d(unreal.Vector(scale[0]*.65,scale[1]*.65,scale[2]*.85))
                # Re-seat each scaled specimen on the recorded soil level.
                extra.set_actor_location(unreal.Vector((lo[0]+hi[0])*50+dx*size[0]-(bb.min.x+bb.max.x)*scale[0]*.65/2,(lo[2]+hi[2])*50+dy*size[1]-(bb.min.y+bb.max.y)*scale[1]*.65/2,lo[1]*100-bb.min.z*scale[2]*.85),False,False)
                extra.set_actor_label('NativePlant_'+name+'_clump'+str(j))

    dest=folder+'/DoorCanopies';s.import_files(['/tmp/job/door-foliage/DoorFoliage.gltf'],dest)
    leaf=s.load(folder+'/Materials/Native_island_tree_02_1')
    if not leaf:raise RuntimeError('Scanned canopy leaf material missing')
    for data in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(dest,recursive=True):
        if str(data.asset_class_path.asset_name)!='StaticMesh':continue
        mesh=data.get_asset();s.ensure_nanite(mesh,True)
        a=s.EAS.spawn_actor_from_object(mesh,unreal.Vector(0,0,0),unreal.Rotator(0,0,0));a.set_actor_label('NativePlant_LeafCanopy_'+mesh.get_name())
        for i in range(a.static_mesh_component.get_num_materials()):a.static_mesh_component.set_material(i,leaf)
    s.REPORT['gravel']='Poly Haven dry_river_pebbles CC0; 0.25 m repeat selected for 20–30 mm gravel; 4.5 mm relief; proxy stones removed'
    s.REPORT['native_plants']={'instances':placed,'source':'reviewed Poly Haven CC0 full-detail assets','botanical_limit':'Periwinkle substitutes for flowering bed varieties in this presentation test'}
    for a in s.EAS.get_all_level_actors():
        if isinstance(a,unreal.SkyLight):s.setp(a.light_component,'intensity',2.2)
        if isinstance(a,unreal.DirectionalLight):s.setp(a.light_component,'light_source_angle',1.2)
    unreal.EditorLoadingAndSavingUtils.save_current_level()
    s.EAL.save_directory(folder,only_if_is_dirty=True,recursive=True)
    unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True)
    s.REPORT['garden_detail']={'material_slots':changed,'material_count':len(replacements),'geometry':'survey-surface sampled grass and gravel'}
    s.log('Garden look applied',s.REPORT['garden_detail'])
