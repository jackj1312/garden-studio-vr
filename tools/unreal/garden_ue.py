"""Unreal Engine 5.8, headless: import the measured garden and light it like the Airbnb walkthrough.
Run in a headless editor (it renders, so not the -Cmd commandlet):  UnrealEditor Studio.uproject -RenderOffscreen
        -unattended -nosplash -nosound -ExecCmds="py garden_ue.py --usd /job/garden.usdc --site /job/site.json
        --cams /job/cams.json --out /job/out"; quits when Movie Render Queue is done (not -ExecutePythonScript, which
        quits as soon as the script returns, before the queue renders: CORRECTIONS-LOG 145)
Untested until Unreal is reachable (see README.md: access steps are Jack's)."""
import sys, json, math, os
import unreal

def setp(obj, key, value):
    """Set an editor property, or warn and carry on: one renamed property must not end a paid run."""
    try:
        obj.set_editor_property(key, value); return True
    except Exception as e:
        unreal.log_warning(f"garden_ue: skipped {type(obj).__name__}.{key}: {e}"); return False


def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default

USD, SITE, CAMS, OUT = arg("--usd"), arg("--site"), arg("--cams"), arg("--out", "/job/out")
os.makedirs(OUT, exist_ok=True)
site = json.load(open(SITE)) if SITE else {}
EAS = unreal.EditorActorSubsystem(); ELS = unreal.LevelEditorSubsystem()
ELS.new_level("/Game/Garden/L_Garden")

# 1. the measured model (Blender metres -> Unreal centimetres; Blender +y = Unreal +y after USD's axis fix)
stage = EAS.spawn_actor_from_class(unreal.UsdStageActor, unreal.Vector(0, 0, 0))
setp(stage, "root_layer", unreal.FilePath(USD))
setp(stage, "initial_load_set", unreal.UsdInitialLoadSet.LOAD_ALL)

# 2. light: the client's filmed sun, a physical sky, Lumen
sun_cfg = site.get("sun", {"azimuthDeg": -138, "elevationDeg": 22})
sun = EAS.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 1000))
sc = sun.light_component
setp(sc, "intensity", 10.0)                   # lux, physical units
setp(sc, "light_color", unreal.Color(255, 236, 214))
setp(sc, "atmosphere_sun_light", True)
setp(sc, "cast_raytraced_shadow", unreal.CastRayTracedShadow.ENABLED) if hasattr(unreal, "CastRayTracedShadow") else None
setp(sc, "light_source_angle", 0.53) or setp(sc, "source_angle", 0.53)
sun.set_actor_rotation(unreal.Rotator(roll=0, pitch=-sun_cfg.get("elevationDeg", 22), yaw=90 - sun_cfg.get("azimuthDeg", -138)), False)
EAS.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
EAS.spawn_actor_from_class(unreal.VolumetricCloud, unreal.Vector(0, 0, 0))
sky = EAS.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 500))
setp(sky.light_component, "real_time_capture", True)
fog = EAS.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0))
setp(fog.component, "fog_density", 0.004)
setp(fog.component, "enable_volumetric_fog", True) or setp(fog.component, "volumetric_fog", True)

# 3. post: Lumen GI + reflections, neutral grade, locked exposure, a little vignette (Airbnb: "dynamic vignette")
pp = EAS.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
setp(pp, "unbound", True)
s = pp.settings
for k, v in (("override_dynamic_global_illumination_method", True), ("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN),
             ("override_reflection_method", True), ("reflection_method", unreal.ReflectionMethod.LUMEN),
             ("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
             ("override_auto_exposure_bias", True), ("auto_exposure_bias", 11.5),
             ("override_vignette_intensity", True), ("vignette_intensity", 0.25),
             ("override_bloom_intensity", True), ("bloom_intensity", 0.35)):
    try: setp(s, k, v)
    except Exception as e: unreal.log_warning(f"post {k}: {e}")
setp(pp, "settings", s)

# 4. cameras at the client's matched walk-frame poses (cams.json: viewer coords x, y-up, -plan-y; dir; hfov)
cams = [r for r in (json.load(open(CAMS))["refs"] if CAMS else []) if r.get("pos")]
PICK = arg("--pick")                                      # comma list of frame names, else N spread along the walk
if PICK: cams = [r for r in cams if os.path.basename(r["file"]).split(".")[0] in PICK.split(",")]
else:
    n = int(arg("--cams-n", 6)); cams = [cams[round(i * (len(cams) - 1) / max(1, n - 1))] for i in range(min(n, len(cams)))]
shots = []; sizes = {}
for r in cams:
    if not r.get("pos"): continue
    x, y, z = r["pos"]; dx, dy, dz = r["dir"]
    loc = unreal.Vector(x * 100, z * 100, y * 100)          # viewer (x, up, -plan y) -> Unreal (x, -plan y as +y? see note)
    rot = unreal.MathLibrary.find_look_at_rotation(loc, unreal.Vector((x + dx) * 100, (z + dz) * 100, (y + dy) * 100))
    cam = EAS.spawn_actor_from_class(unreal.CineCameraActor, loc, rot)
    cc = cam.get_cine_camera_component()
    setp(cc, "current_focal_length", 36.0 / (2 * math.tan(math.radians(r.get("hfov", 60)) / 2)))
    cam.set_actor_label("Cam_" + os.path.basename(r["file"]).split(".")[0]); shots.append(cam)
    w, h = r.get("w", 1080), r.get("h", 1920); k = 2560 / max(w, h); sizes[cam.get_actor_label()] = (round(w * k), round(h * k))
unreal.EditorLoadingAndSavingUtils.save_current_level()

# 5. stills: one 1-frame level sequence per camera, rendered by Movie Render Queue in this editor session (a
# commandlet cannot render). Run as: UnrealEditor Studio.uproject -RenderOffscreen -unattended -nosplash -nosound
#   -ExecCmds="py garden_ue.py --usd ... --out ..."; the editor quits when the queue finishes.
AT = unreal.AssetToolsHelpers.get_asset_tools()
level_path = "/Game/Garden/L_Garden"
seqs = []
for cam in shots:
    name = "S_" + cam.get_actor_label()
    seq = AT.create_asset(name, "/Game/Garden/Seq", unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    seq.set_display_rate(unreal.FrameRate(24, 1)); seq.set_playback_start(0); seq.set_playback_end(1)
    binding = seq.add_spawnable_from_instance(cam)       # the sequence owns its camera, so the render (PIE) world has it
    add = getattr(seq, "add_track", None) or getattr(seq, "add_master_track")
    cut = add(unreal.MovieSceneCameraCutTrack)
    sec = cut.add_section(); sec.set_range(0, 1)
    try: sec.set_camera_binding_id(seq.get_binding_id(binding))
    except Exception: sec.set_camera_binding_id(unreal.MovieSceneSequenceExtensions.get_portable_binding_id(seq, seq, binding))
    unreal.EditorAssetLibrary.save_loaded_asset(seq); seqs.append(seq)
unreal.EditorLoadingAndSavingUtils.save_current_level()

MQS = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
queue = MQS.get_queue(); queue.delete_all_jobs()
for seq in seqs:
    job = queue.allocate_new_job(unreal.MoviePipelineExecutorJob)
    job.sequence = unreal.SoftObjectPath(seq.get_path_name()); job.map = unreal.SoftObjectPath(level_path)
    job.job_name = seq.get_name()
    cfg = job.get_configuration()
    cfg.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_PNG)
    o = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    o.output_directory = unreal.DirectoryPath(OUT); o.output_resolution = unreal.IntPoint(*sizes[seq.get_name()[2:]])
    o.file_name_format = "{sequence_name}"; o.override_existing_output = True
    aa = cfg.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
    aa.override_anti_aliasing = True; aa.anti_aliasing_method = unreal.AntiAliasingMethod.AAM_NONE
    aa.spatial_sample_count = 1; aa.temporal_sample_count = 8
    aa.engine_warm_up_count = 64; aa.render_warm_up_count = 64       # Lumen settles over the first frames

def finished(executor, ok):
    unreal.log("garden_ue: queue finished, success=%s" % ok)
    unreal.SystemLibrary.quit_editor()

EXECUTOR = MQS.render_queue_with_executor(unreal.MoviePipelinePIEExecutor)
EXECUTOR.on_executor_finished_delegate.add_callable_unique(finished)
unreal.log("garden_ue: queued %d cameras" % len(seqs))
