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
try:
    saved=json.load(open(checkpoint)) if os.path.exists(checkpoint) else {}
    if saved.get('source')==studio.SC['source'] and EAL.does_asset_exist(saved.get('map','')):
        studio.LES.load_level(saved['map'])
        studio.LEVEL['path']=saved['map']
    else:
        task=unreal.AssetImportTask()
        task.filename=os.path.join(studio.BUNDLE,'House.gltf')
        task.destination_path='/Game/House/Assets'
        task.automated=True
        task.replace_existing=True
        task.save=True
        studio.AT.import_asset_tasks([task])
        imported=task.get_objects()
        meshes=[a for a in imported if isinstance(a,unreal.StaticMesh)]
        if not meshes:
            meshes=[EAL.load_asset(p) for p in EAL.list_assets('/Game/House/Assets') if EAL.find_asset_data(p).asset_class_path.asset_name=='StaticMesh']
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
        reference=max(mapping,key=lambda k:sum((b-a)**2 for a,b in zip(*known[k])))
        det=studio.axis_check({'MI_Brick':mapping[reference]})
        if studio.REPORT['axis']['detected']['err_cm']>.5: raise RuntimeError('Imported horizontal dimensions differ from the source')
        mesh,desc=mapping[reference];bb=mesh.get_bounding_box()
        if max(abs(bb.min.z-desc['bounds'][0][2]*100),abs(bb.max.z-desc['bounds'][1][2]*100))>.5:
            raise RuntimeError('Imported vertical dimensions differ from the source')
        studio.new_level()
        yaw,sign=studio.actor_transform(det)
        for mesh,_ in mapping.values():
            actor=studio.EAS.spawn_actor_from_object(mesh,unreal.Vector(0,0,0),unreal.Rotator(0,yaw,0))
            actor.set_actor_scale3d(unreal.Vector(1,sign,1))
        studio.lighting()
        # These are photographic assessment frames. Keep visible texture detail.
        for actor in studio.EAS.get_all_level_actors():
            if actor.get_actor_label()=='FarGround':
                studio.EAS.destroy_actor(actor)
                continue
            if isinstance(actor,unreal.PostProcessVolume):
                settings=actor.settings
                studio.setp(settings,'override_grain_intensity',True);studio.setp(settings,'grain_intensity',0.)
                studio.setp(settings,'override_scene_fringe_intensity',True);studio.setp(settings,'scene_fringe_intensity',0.)
                studio.setp(actor,'settings',settings)
        unreal.EditorLoadingAndSavingUtils.save_current_level()
        EAL.save_directory('/Game/House',only_if_is_dirty=True,recursive=True)
        saved={'source':studio.SC['source'],'map':studio.LEVEL['path'],'meshes':len(meshes),'axis':studio.REPORT['axis']}
        with open(checkpoint+'.part','w') as f:json.dump(saved,f,indent=2)
        os.replace(checkpoint+'.part',checkpoint)
    shots=studio.cameras()
    pending=[]
    for cam,res,description in shots:
        component=cam.get_cine_camera_component()
        studio.setp(component,'post_process_blend_weight',1.)
        pp=component.get_editor_property('post_process_settings')
        studio.setp(pp,'override_auto_exposure_bias',True)
        studio.setp(pp,'auto_exposure_bias',3.5 if description['name']!='Front_left_garden' else 0.)
        studio.setp(component,'post_process_settings',pp)
        target=os.path.join(studio.OUT,'S_'+description['name']+'.png')
        if not os.path.isfile(target) or os.path.getsize(target)<4096:
            pending.append((cam,res,description))
    if pending: studio.render(pending)
    else: unreal.SystemLibrary.quit_editor()
except Exception:
    error=traceback.format_exc()
    with open(os.path.join(studio.OUT,'failure.txt'),'w') as f:f.write(error)
    unreal.log_error(error)
    unreal.SystemLibrary.quit_editor()
