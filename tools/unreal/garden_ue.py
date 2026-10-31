"""Unreal Engine 5.8, headless: import the measured garden and light it like the Airbnb walkthrough.
Run inside the editor:  UnrealEditor-Cmd <project>.uproject -run=pythonscript -script="garden_ue.py --usd /job/garden.usdc
        --site /job/site.json --cams /job/cams.json --out /job/out" -RenderOffscreen -unattended -nosplash
Untested until Unreal is reachable (see README.md: access steps are Jack's)."""
import sys, json, math, os
import unreal

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
stage.set_editor_property("root_layer", unreal.FilePath(USD))
stage.set_editor_property("initial_load_set", unreal.UsdInitialLoadSet.LOAD_ALL)

# 2. light: the client's filmed sun, a physical sky, Lumen
sun_cfg = site.get("sun", {"azimuthDeg": -138, "elevationDeg": 22})
sun = EAS.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 1000))
sc = sun.light_component
sc.set_editor_property("intensity", 10.0)                   # lux, physical units
sc.set_editor_property("light_color", unreal.Color(255, 236, 214))
sc.set_editor_property("atmosphere_sun_light", True)
sc.set_editor_property("cast_ray_traced_shadows", unreal.CastRayTracedShadow.ENABLED if hasattr(unreal, "CastRayTracedShadow") else True)
sc.set_editor_property("source_angle", 0.53)
sun.set_actor_rotation(unreal.Rotator(roll=0, pitch=-sun_cfg.get("elevationDeg", 22), yaw=90 - sun_cfg.get("azimuthDeg", -138)), False)
EAS.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
EAS.spawn_actor_from_class(unreal.VolumetricCloud, unreal.Vector(0, 0, 0))
sky = EAS.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 500))
sky.light_component.set_editor_property("real_time_capture", True)
fog = EAS.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0))
fog.component.set_editor_property("fog_density", 0.004)
fog.component.set_editor_property("volumetric_fog", True)

# 3. post: Lumen GI + reflections, neutral grade, locked exposure, a little vignette (Airbnb: "dynamic vignette")
pp = EAS.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
pp.set_editor_property("unbound", True)
s = pp.settings
for k, v in (("override_dynamic_global_illumination_method", True), ("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN),
             ("override_reflection_method", True), ("reflection_method", unreal.ReflectionMethod.LUMEN),
             ("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
             ("override_auto_exposure_bias", True), ("auto_exposure_bias", 11.5),
             ("override_vignette_intensity", True), ("vignette_intensity", 0.25),
             ("override_bloom_intensity", True), ("bloom_intensity", 0.35)):
    try: s.set_editor_property(k, v)
    except Exception as e: unreal.log_warning(f"post {k}: {e}")
pp.set_editor_property("settings", s)

# 4. cameras at the client's matched walk-frame poses (cams.json: viewer coords x, y-up, -plan-y; dir; hfov)
cams = json.load(open(CAMS))["refs"] if CAMS else []
shots = []
for r in cams:
    if not r.get("pos"): continue
    x, y, z = r["pos"]; dx, dy, dz = r["dir"]
    loc = unreal.Vector(x * 100, z * 100, y * 100)          # viewer (x, up, -plan y) -> Unreal (x, -plan y as +y? see note)
    rot = unreal.MathLibrary.find_look_at_rotation(loc, unreal.Vector((x + dx) * 100, (z + dz) * 100, (y + dy) * 100))
    cam = EAS.spawn_actor_from_class(unreal.CineCameraActor, loc, rot)
    cc = cam.get_cine_camera_component()
    cc.set_editor_property("current_focal_length", 36.0 / (2 * math.tan(math.radians(r.get("hfov", 60)) / 2)))
    cam.set_actor_label("Cam_" + os.path.basename(r["file"]).split(".")[0]); shots.append(cam)
unreal.EditorLoadingAndSavingUtils.save_current_level()

# 5. stills through each camera (high-res screenshot per camera; MRQ walk sequence is the next pass)
for cam in shots:
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(cam.get_actor_location(), cam.get_actor_rotation())
    unreal.AutomationLibrary.take_high_res_screenshot(1440, 2560, os.path.join(OUT, cam.get_actor_label() + ".png"), camera=cam)
unreal.log("garden_ue: done, %d cameras" % len(shots))
