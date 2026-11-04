"""Render the current furnished house using the studio's existing Unreal cameras and MRQ."""
import json
import math
import os
import sys
import traceback
import unreal

sys.path.insert(0,os.path.dirname(__file__))
import garden_ue2 as studio

checkpoint=os.path.join(studio.OUT,'checkpoint.json')
EAL=studio.EAL
asset_root="/Game/House/Revision_"+studio.SC["source"][:12]+"/Assets"
try:
    saved=json.load(open(checkpoint)) if os.path.exists(checkpoint) else {}
    restored=False
    if saved.get('source')==studio.SC['source'] and saved.get('assetRoot')==asset_root and saved.get('axisVerified') and EAL.does_asset_exist(saved.get('map','')):
        loaded=studio.LES.load_level(saved['map'])
        actors=studio.EAS.get_all_level_actors()
        restored=bool(loaded) and sum(isinstance(a,unreal.StaticMeshActor) for a in actors)>=saved.get('meshes',113) and any(isinstance(a,unreal.DirectionalLight) for a in actors)
        if restored: studio.LEVEL['path']=saved['map']
        else: studio.warn('Saved map did not restore the house; reconstructing from persistent imported meshes')
    if not restored:
        if saved.get('source')==studio.SC['source'] and saved.get('assetRoot')==asset_root:
            imported=[data.get_asset() for data in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(asset_root,recursive=True)
                      if str(data.asset_class_path.asset_name)=='StaticMesh']
        else:
            task=unreal.AssetImportTask()
            task.filename=os.path.join(studio.BUNDLE,'House.gltf')
            task.destination_path=asset_root
            task.automated=True
            task.replace_existing=True
            task.save=True
            studio.AT.import_asset_tasks([task])
            imported=task.get_objects()
        meshes=[a for a in imported if isinstance(a,unreal.StaticMesh)]
        if not meshes:
            meshes=[EAL.load_asset(p) for p in EAL.list_assets(asset_root) if EAL.find_asset_data(p).asset_class_path.asset_name=='StaticMesh']
        if not meshes: raise RuntimeError('The glTF importer produced no house meshes')
        known=studio.SC['bounds']
        mapping={}
        for mesh in meshes:
            key=mesh.get_name()
            match=next((n for n in known if key==n or key.endswith('_'+n)),None)
            if match: mapping[match]=(mesh,{'bounds':known[match]})
        if len(mapping)!=len(known):
            raise RuntimeError('Imported mesh count/name mismatch: '+repr((len(mapping),len(known),[m.get_name() for m in meshes[:12]])))
        # Reuse the FBX/Unreal basis detector against the actual glTF import,
        # then verify the vertical metric as well before positioning cameras.
        def basis_separation(key):
            lo,hi=known[key]
            variants=[]
            for swap in (False,True):
                for sx in (-1,1):
                    for sy in (-1,1):
                        a,b=(1,0) if swap else (0,1)
                        variants.append(sorted((sx*lo[a],sx*hi[a]))+sorted((sy*lo[b],sy*hi[b])))
            return min(sum(abs(a-b) for a,b in zip(v,w)) for i,v in enumerate(variants) for w in variants[i+1:])
        reference=max(mapping,key=basis_separation)
        if basis_separation(reference)<.01: raise RuntimeError('No asymmetric reference available for import-axis verification')
        det=studio.axis_check({'MI_Brick':mapping[reference]})
        if studio.REPORT['axis']['detected']['err_cm']>.5: raise RuntimeError('Imported horizontal dimensions differ from the source')
        mesh,desc=mapping[reference];bb=mesh.get_bounding_box()
        if max(abs(bb.min.z-desc['bounds'][0][2]*100),abs(bb.max.z-desc['bounds'][1][2]*100))>.5:
            raise RuntimeError('Imported vertical dimensions differ from the source')
        studio.new_level()
        yaw,sign=studio.actor_transform(det)
        for mesh,_ in mapping.values():
            actor=studio.EAS.spawn_actor_from_object(mesh,unreal.Vector(0,0,0),unreal.Rotator(roll=0,pitch=0,yaw=yaw))
            actor.set_actor_scale3d(unreal.Vector(1,sign,1))
        studio.lighting()
        # These are photographic assessment frames. Keep visible texture detail.
        for actor in studio.EAS.get_all_level_actors():
            if actor.get_actor_label()=='FarGround':
                studio.EAS.destroy_actor(actor)
                continue
            if isinstance(actor,unreal.PostProcessVolume):
                settings=actor.settings
                studio.setp(settings,'override_film_grain_intensity',True);studio.setp(settings,'film_grain_intensity',0.)
                studio.setp(settings,'override_scene_fringe_intensity',True);studio.setp(settings,'scene_fringe_intensity',0.)
                studio.setp(actor,'settings',settings)
        unreal.EditorLoadingAndSavingUtils.save_current_level()
        EAL.save_directory('/Game/House',only_if_is_dirty=True,recursive=True)
        saved={'source':studio.SC['source'],'assetRoot':asset_root,'map':studio.LEVEL['path'],'meshes':len(meshes),'axis':studio.REPORT['axis'],'axisVerified':True}
        with open(checkpoint+'.part','w') as f:json.dump(saved,f,indent=2)
        os.replace(checkpoint+'.part',checkpoint)
    if '--garden-detail' in sys.argv:
        import garden_look
        garden_look.apply()
    mode=studio.arg('--look','interior')
    if '--cinema' in sys.argv:
        import house_cinema
        house_cinema.apply(mode)
    shots=studio.cameras()
    pending=[]
    for cam,res,description in shots:
        component=cam.get_cine_camera_component()
        studio.setp(component,'post_process_blend_weight',1.)
        pp=component.get_editor_property('post_process_settings')
        studio.setp(pp,'override_auto_exposure_bias',True)
        studio.setp(pp,'auto_exposure_bias',(1.5 if mode=='garden' else 6.0) if '--cinema' in sys.argv else (5.5 if description['name']!='Front_left_garden' else .35))
        studio.setp(component,'post_process_settings',pp)
        target=os.path.join(studio.OUT,'S_'+description['name']+'.png')
        if not os.path.isfile(target) or os.path.getsize(target)<4096:
            pending.append((cam,res,description))
    extra=studio.render_video() if '--film' in sys.argv else []
    if pending or extra: studio.render(pending,extra=extra)
    else: unreal.SystemLibrary.quit_editor()
except Exception:
    error=traceback.format_exc()
    with open(os.path.join(studio.OUT,'failure.txt'),'w') as f:f.write(error)
    unreal.log_error(error)
    unreal.SystemLibrary.quit_editor()
