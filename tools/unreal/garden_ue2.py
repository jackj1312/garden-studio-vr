"""Unreal 5.8, headless editor: build the site natively from the staged bundle (prepare_ue.py) and render matched stills.
    UnrealEditor Studio.uproject -RenderOffscreen -unattended -nosplash -nosound -ExecCmds="py garden_ue2.py --bundle /tmp/job/bundle
        --out /tmp/job/out [--cams check|all|walk_0013+walk_0037] (lists use '+': -ExecCmds splits on commas) [--reimport] [--ev 0] [--long 1600] [--spp 16] [--clouds 0|1]"
Quits itself from the queue-finished callback (CORRECTIONS-LOG 145); every property set is non-fatal (setp, CORRECTIONS-LOG 139).

Steps: textures -> master materials (scan / scan+displacement / foliage / vertex-colour foliage / flat / glass) and one material
instance per surface (tint, metre tiling, anti-tile, macro variation) -> FBX parts as Nanite static meshes, axis checked against
the export's own bounds and corrected -> library plants/hedge balls placed at the measured spots -> sun at the filmed angle,
SkyAtmosphere, SkyLight (real-time capture), height fog, Lumen GI + reflections on hardware ray tracing, physical exposure ->
one spawnable CineCamera per photo (filmback at the photo's aspect) -> Movie Render Queue PNGs at each photo's own shape."""
import json, math, os, random, sys, time
import unreal

A = sys.argv
def arg(n, d=None): return A[A.index(n) + 1] if n in A else d
BUNDLE = arg("--bundle", "/tmp/job/bundle"); OUT = arg("--out", "/tmp/job/out"); os.makedirs(OUT, exist_ok=True)
SC = json.load(open(os.path.join(BUNDLE, "scene.json")))
CAMSEL = arg("--cams", "check"); EV = float(arg("--ev", "0")); LONG = int(arg("--long", str(SC.get("long_edge_px", 1600))))
SPP = int(arg("--spp", "32")); REIMPORT = "--reimport" in A; CLOUDS = arg("--clouds", "0") == "1"
REMESH = set((arg("--reimport-mesh", "") or "").split("+"))   # '+' lists: -ExecCmds splits on commas (r7: 2nd name lost)          # re-export of a few parts: reimport just those
G = "/Game/Site"
EAS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LES = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
AT = unreal.AssetToolsHelpers.get_asset_tools()
EAL = unreal.EditorAssetLibrary
MEL = unreal.MaterialEditingLibrary
REPORT = {"warnings": [], "t0": time.time()}


def log(*a):
    unreal.log("garden_ue2: " + " ".join(str(x) for x in a))


def warn(msg):
    REPORT["warnings"].append(msg); unreal.log_warning("garden_ue2: " + msg)


def setp(obj, k, v):
    try:
        obj.set_editor_property(k, v); return True
    except Exception as e:
        warn(f"skipped {type(obj).__name__}.{k}: {str(e)[:120]}"); return False


def E(enum, *names):
    """enum member by the first name that exists, or None (setp then skips it) so a renamed enum never ends a paid run"""
    for name in names:
        try: return getattr(getattr(unreal, enum), name)
        except Exception: pass
    try: have = [n for n in dir(getattr(unreal, enum)) if n.isupper()][:30]
    except Exception: have = []
    warn(f"no enum {enum}.{names}; has {have}"); return None


def setp(obj, k, v):
    if v is None: return False
    try:
        obj.set_editor_property(k, v); return True
    except Exception as e:
        warn(f"skipped {type(obj).__name__}.{k}: {str(e)[:120]}"); return False


def step(name):
    log(f"--- {name} ({time.time() - REPORT['t0']:.0f}s)")


# ------------------------------------------------------------------ import
def import_files(files, dest, options=None):
    tasks = []
    for f in files:
        t = unreal.AssetImportTask(); t.filename = f; t.destination_path = dest; t.automated = True; t.save = True; t.replace_existing = True
        if options is not None: t.options = options
        tasks.append(t)
    AT.import_asset_tasks(tasks)
    out = {}
    for f, t in zip(files, tasks):
        paths = list(t.imported_object_paths or [])
        out[f] = paths
        if not paths: warn(f"import produced nothing: {os.path.basename(f)}")
    return out


def asset_path(dest, file):
    stem = os.path.splitext(os.path.basename(file))[0]
    return f"{dest}/{stem}.{stem}"


def load(path):
    try: return unreal.load_asset(path)
    except Exception: return None


def fbx_options(nanite):
    o = unreal.FbxImportUI()
    for k, v in (("import_mesh", True), ("import_textures", False), ("import_materials", False), ("import_as_skeletal", False),
                 ("import_animations", False), ("automated_import_should_detect_type", False)):
        setp(o, k, v)
    setp(o, "mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    sm = o.static_mesh_import_data
    for k, v in (("combine_meshes", True), ("generate_lightmap_u_vs", False), ("auto_generate_collision", False), ("build_nanite", nanite),
                 ("import_uniform_scale", 1.0), ("convert_scene", True), ("remove_degenerates", False),
                 ("vertex_color_import_option", unreal.VertexColorImportOption.REPLACE),
                 ("normal_import_method", unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)):
        setp(sm, k, v)
    return o


def ensure_nanite(sm, on):
    try:
        ns = sm.get_editor_property("nanite_settings")
        if ns.enabled == on: return
        ns.enabled = on
        sss = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        if hasattr(sss, "set_nanite_settings"): sss.set_nanite_settings(sm, ns, True)
        else: sm.set_editor_property("nanite_settings", ns)
    except Exception as e:
        warn(f"nanite {sm.get_name()}: {str(e)[:100]}")


# ------------------------------------------------------------------ materials
def fresh(name, folder, cls, factory):
    p = f"{folder}/{name}"
    if EAL.does_asset_exist(p): EAL.delete_asset(p)
    return AT.create_asset(name, folder, cls, factory)


def X(m, cls, x, y, **props):
    e = MEL.create_material_expression(m, cls, x, y)
    for k, v in props.items(): setp(e, k, v)
    return e


def C(a, ao, b, bi):
    for name in ([bi] + (["Input"] if bi == "" else [""] if bi == "Input" else [])):
        try:
            if MEL.connect_material_expressions(a, ao, b, name): return True
        except Exception: pass
    warn(f"connect failed {type(a).__name__}.{ao} -> {type(b).__name__}.{bi}"); return False


def P(e, o, prop):
    if not MEL.connect_material_property(e, o, prop): warn(f"property connect failed {type(e).__name__}.{o} -> {prop}")


def tex_param(m, name, x, y, uv, sampler, default):
    e = X(m, unreal.MaterialExpressionTextureSampleParameter2D, x, y, parameter_name=name, sampler_type=sampler)
    if default: setp(e, "texture", default)
    if uv is not None: C(uv, "", e, "UVs")
    return e


def scalar(m, name, v, x, y): return X(m, unreal.MaterialExpressionScalarParameter, x, y, parameter_name=name, default_value=v)
def vector(m, name, v, x, y): return X(m, unreal.MaterialExpressionVectorParameter, x, y, parameter_name=name, default_value=unreal.LinearColor(*v))


def mul(m, a, b, x, y, ao="", bo=""):
    e = X(m, unreal.MaterialExpressionMultiply, x, y); C(a, ao, e, "A"); C(b, bo, e, "B"); return e


def lerp(m, a, b, t, x, y, ao="", bo="", to=""):
    e = X(m, unreal.MaterialExpressionLinearInterpolate, x, y); C(a, ao, e, "A"); C(b, bo, e, "B"); C(t, to, e, "Alpha"); return e


def mask(m, a, x, y, r=False, g=False, b=False, ao=""):
    e = X(m, unreal.MaterialExpressionComponentMask, x, y, r=r, g=g, b=b, a=False); C(a, ao, e, ""); return e


def build_scan_material(name, defaults, displacement=False):
    """scanned PBR, metre UVs: UV0 / Tile, optional 90 deg swap, anti-tile second sample blended by world noise, macro tint"""
    m = fresh(name, f"{G}/Mat", unreal.Material, unreal.MaterialFactoryNew())
    tc = X(m, unreal.MaterialExpressionTextureCoordinate, -1800, 0)
    tile = vector(m, "Tile", (1, 1, 0, 0), -1800, 150); tile2 = mask(m, tile, -1600, 150, r=True, g=True)
    uv = X(m, unreal.MaterialExpressionDivide, -1450, 0); C(tc, "", uv, "A"); C(tile2, "", uv, "B")
    u = mask(m, uv, -1300, -100, r=True); v = mask(m, uv, -1300, 0, g=True)
    sw = X(m, unreal.MaterialExpressionAppendVector, -1150, 50); C(v, "", sw, "A"); C(u, "", sw, "B")
    rot = scalar(m, "Rot90", 0.0, -1150, 180)
    uvr = lerp(m, uv, sw, rot, -1000, 0)
    # anti-tile: a second sample, rotated/scaled, mixed in by a low-frequency world-space noise
    u2 = mask(m, uvr, -900, 250, r=True); v2 = mask(m, uvr, -900, 330, g=True)
    sw2 = X(m, unreal.MaterialExpressionAppendVector, -760, 280); C(v2, "", sw2, "A"); C(u2, "", sw2, "B")
    k = X(m, unreal.MaterialExpressionConstant, -760, 400, r=0.73)
    uv2a = mul(m, sw2, k, -620, 300)
    off = X(m, unreal.MaterialExpressionConstant2Vector, -620, 420, r=0.31, g=0.57)
    uv2 = X(m, unreal.MaterialExpressionAdd, -480, 320); C(uv2a, "", uv2, "A"); C(off, "", uv2, "B")
    nz = X(m, unreal.MaterialExpressionNoise, -620, 560, scale=0.006, quality=1, levels=3, output_min=0.0, output_max=1.0, turbulence=False)
    at = scalar(m, "AntiTile", 0.0, -620, 700)
    mix = mul(m, nz, at, -480, 600)
    S = unreal.MaterialSamplerType
    def pair(pname, sampler, default, y):
        a = tex_param(m, pname, -350, y, uvr, sampler, default); b = tex_param(m, pname, -350, y + 260, uv2, sampler, default)
        return lerp(m, a, b, mix, -80, y, "RGB", "RGB")
    D = pair("Diffuse", S.SAMPLERTYPE_COLOR, defaults.get("diff"), -900)
    N = pair("Normal", S.SAMPLERTYPE_NORMAL, defaults.get("nor"), -300)
    R = pair("ARM", S.SAMPLERTYPE_MASKS, defaults.get("arm"), 300)
    # base colour: desaturate, tint, macro variation (large world noise)
    ds = X(m, unreal.MaterialExpressionDesaturation, 100, -900); C(D, "", ds, ""); C(scalar(m, "Desat", 0.0, -80, -700), "", ds, "Fraction")
    tint = vector(m, "Tint", (1, 1, 1, 1), 100, -760)
    bc = mul(m, ds, tint, 260, -900)
    mn = X(m, unreal.MaterialExpressionNoise, 100, -620, scale=0.0025, quality=1, levels=4, output_min=-1.0, output_max=1.0, turbulence=False)
    ma = mul(m, mn, scalar(m, "Macro", 0.0, 100, -480), 260, -600)
    one = X(m, unreal.MaterialExpressionConstant, 260, -480, r=1.0)
    mf = X(m, unreal.MaterialExpressionAdd, 400, -560); C(one, "", mf, "A"); C(ma, "", mf, "B")
    bc2 = mul(m, bc, mf, 540, -800)
    P(bc2, "", unreal.MaterialProperty.MP_BASE_COLOR)
    flat = X(m, unreal.MaterialExpressionConstant3Vector, 100, -200, constant=unreal.LinearColor(0, 0, 1, 1))
    nn = lerp(m, flat, N, scalar(m, "NormalStrength", 1.0, 100, -60), 300, -260)
    P(nn, "", unreal.MaterialProperty.MP_NORMAL)
    rr = mul(m, mask(m, R, 120, 300, g=True), scalar(m, "RoughMul", 1.0, 120, 420), 300, 320)
    P(rr, "", unreal.MaterialProperty.MP_ROUGHNESS)
    P(mask(m, R, 120, 500, r=True), "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
    P(X(m, unreal.MaterialExpressionConstant, 300, 600, r=0.0), "", unreal.MaterialProperty.MP_METALLIC)
    if displacement:
        dt = tex_param(m, "Disp", -350, 900, uvr, S.SAMPLERTYPE_MASKS, defaults.get("disp"))
        dm = mul(m, mask(m, dt, -80, 900, r=True, ao="RGB"), scalar(m, "DispAmount", 1.0, -80, 1000), 120, 900)
        try:
            P(dm, "", unreal.MaterialProperty.MP_DISPLACEMENT)
            setp(m, "enable_tessellation", True)
            ds_ = unreal.DisplacementScaling(); setp(ds_, "magnitude", float(defaults.get("disp_cm", 1.5))); setp(ds_, "center", 0.5)
            setp(m, "displacement_scaling", ds_)
        except Exception as e:
            warn(f"displacement unsupported: {e}")
    MEL.recompile_material(m); EAL.save_loaded_asset(m)
    return m


def build_foliage_material(name, defaults, vertex_colour=False):
    m = fresh(name, f"{G}/Mat", unreal.Material, unreal.MaterialFactoryNew())
    setp(m, "two_sided", True)
    setp(m, "shading_model", E("MaterialShadingModel", "MSM_TWO_SIDED_FOLIAGE", "MSM_TWOSIDED_FOLIAGE", "MSM_SUBSURFACE"))
    S = unreal.MaterialSamplerType
    tint = vector(m, "Tint", (1, 1, 1, 1), -400, -300)
    if vertex_colour:
        vc = X(m, unreal.MaterialExpressionVertexColor, -600, -500)
        bc = mul(m, vc, tint, -200, -400)
        P(scalar(m, "Roughness", 0.6, -200, 0), "", unreal.MaterialProperty.MP_ROUGHNESS)
    else:
        setp(m, "blend_mode", E("BlendMode", "BLEND_MASKED"))
        setp(m, "opacity_mask_clip_value", 0.4)
        tc = X(m, unreal.MaterialExpressionTextureCoordinate, -900, 0)
        D = tex_param(m, "Diffuse", -600, -500, tc, S.SAMPLERTYPE_COLOR, defaults.get("diff"))
        N = tex_param(m, "Normal", -600, -200, tc, S.SAMPLERTYPE_NORMAL, defaults.get("nor"))
        R = tex_param(m, "ARM", -600, 100, tc, S.SAMPLERTYPE_MASKS, defaults.get("arm"))
        Al = tex_param(m, "Alpha", -600, 400, tc, S.SAMPLERTYPE_MASKS, defaults.get("alpha"))
        ds = X(m, unreal.MaterialExpressionDesaturation, -380, -500); C(D, "RGB", ds, ""); C(scalar(m, "Desat", 0.0, -560, -350), "", ds, "Fraction")
        bc = mul(m, ds, tint, -200, -400)
        P(N, "RGB", unreal.MaterialProperty.MP_NORMAL)
        P(mask(m, R, -300, 100, g=True, ao="RGB"), "", unreal.MaterialProperty.MP_ROUGHNESS)
        P(mask(m, R, -300, 200, r=True, ao="RGB"), "", unreal.MaterialProperty.MP_AMBIENT_OCCLUSION)
        P(Al, "R", unreal.MaterialProperty.MP_OPACITY_MASK)
    P(bc, "", unreal.MaterialProperty.MP_BASE_COLOR)
    sss = mul(m, bc, scalar(m, "Translucency", 0.55, -200, -150), 0, -200)
    P(sss, "", unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    MEL.recompile_material(m); EAL.save_loaded_asset(m)
    return m


def build_flat_material(name):
    m = fresh(name, f"{G}/Mat", unreal.Material, unreal.MaterialFactoryNew())
    col = vector(m, "Color", (0.5, 0.5, 0.5, 1), -600, -300)
    nz = X(m, unreal.MaterialExpressionNoise, -600, -100, scale=0.05, quality=1, levels=3, output_min=-1.0, output_max=1.0, turbulence=False)
    na = mul(m, nz, scalar(m, "NoiseAmt", 0.0, -600, 50), -400, -100)
    one = X(m, unreal.MaterialExpressionConstant, -400, 50, r=1.0)
    f = X(m, unreal.MaterialExpressionAdd, -250, -50); C(one, "", f, "A"); C(na, "", f, "B")
    P(mul(m, col, f, -100, -250), "", unreal.MaterialProperty.MP_BASE_COLOR)
    P(scalar(m, "Roughness", 0.5, -300, 200), "", unreal.MaterialProperty.MP_ROUGHNESS)
    P(scalar(m, "Metallic", 0.0, -300, 300), "", unreal.MaterialProperty.MP_METALLIC)
    MEL.recompile_material(m); EAL.save_loaded_asset(m)
    return m


def build_glass_material(name):
    m = fresh(name, f"{G}/Mat", unreal.Material, unreal.MaterialFactoryNew())
    setp(m, "blend_mode", E("BlendMode", "BLEND_TRANSLUCENT"))
    setp(m, "translucency_lighting_mode", E("TranslucencyLightingMode", "TLM_SURFACE_PER_PIXEL_LIGHTING", "TLM_SURFACE"))
    P(vector(m, "Color", (0.01, 0.012, 0.013, 1), -400, -200), "", unreal.MaterialProperty.MP_BASE_COLOR)
    P(scalar(m, "Opacity", 0.35, -400, 0), "", unreal.MaterialProperty.MP_OPACITY)
    P(scalar(m, "Roughness", 0.03, -400, 100), "", unreal.MaterialProperty.MP_ROUGHNESS)
    P(X(m, unreal.MaterialExpressionConstant, -400, 200, r=1.0), "", unreal.MaterialProperty.MP_SPECULAR)
    MEL.recompile_material(m); EAL.save_loaded_asset(m)
    return m


def make_instance(name, parent, scal=None, vec=None, tex=None):
    mi = fresh(name, f"{G}/MI", unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, parent)
    for k, v in (scal or {}).items(): MEL.set_material_instance_scalar_parameter_value(mi, k, float(v))
    for k, v in (vec or {}).items(): MEL.set_material_instance_vector_parameter_value(mi, k, unreal.LinearColor(*(list(v) + [1.0])[:4]))
    for k, v in (tex or {}).items():
        if v: MEL.set_material_instance_texture_parameter_value(mi, k, v)
    EAL.save_loaded_asset(mi)
    return mi


# ------------------------------------------------------------------ build
def textures():
    step("textures")
    files = sorted({os.path.join(BUNDLE, "tex", e[k]) for e in SC["materials"].values() for k in ("diff", "nor", "arm", "alpha", "disp") if e.get(k)})
    dest = f"{G}/Tex"
    todo = [f for f in files if REIMPORT or not EAL.does_asset_exist(f"{dest}/{os.path.splitext(os.path.basename(f))[0]}")]
    if todo: import_files(todo, dest)
    T = {}
    for f in files:
        t = load(asset_path(dest, f)); b = os.path.basename(f); T[b] = t
        if not t: continue
        low = b.lower()
        if "nor_dx" in low:
            setp(t, "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP); setp(t, "srgb", False)
        elif "_arm_" in low or "alpha" in low or "opacity" in low or "disp" in low:
            setp(t, "srgb", False); setp(t, "compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        EAL.save_loaded_asset(t)
    log("textures", sum(1 for v in T.values() if v), "of", len(files))
    return T


def materials(T):
    step("materials")
    mats = SC["materials"]
    first = lambda typ, key, cond=lambda e: True: next((T.get(e.get(key)) for e in mats.values() if e["type"] == typ and e.get(key) and cond(e)), None)
    sdef = {"diff": first("scan", "diff"), "nor": first("scan", "nor"), "arm": first("scan", "arm")}
    ddef = dict(sdef); g = mats.get("MI_Gravel", {})
    ddef.update({"disp": T.get(g.get("disp")), "disp_cm": g.get("displace_cm", 1.5)})
    fdef = {"diff": first("foliage", "diff"), "nor": first("foliage", "nor"), "arm": first("foliage", "arm"), "alpha": first("foliage", "alpha")}
    M = {"scan": build_scan_material("M_Scan", sdef), "foliage": build_foliage_material("M_Foliage", fdef),
         "vcfoliage": build_foliage_material("M_FoliageVC", {}, vertex_colour=True), "flat": build_flat_material("M_Flat"),
         "glass": build_glass_material("M_Glass")}
    try: M["scandisp"] = build_scan_material("M_ScanDisp", ddef, displacement=True)
    except Exception as e: warn(f"M_ScanDisp failed: {e}"); M["scandisp"] = M["scan"]
    MI = {}
    for name, e in mats.items():
        t = e["type"]
        if t in ("scan", "foliage"):
            tex = {"Diffuse": T.get(e.get("diff")), "Normal": T.get(e.get("nor")), "ARM": T.get(e.get("arm"))}
            tint = e.get("tint", [1, 1, 1])
            if t == "scan":
                tu, tv = e.get("tile", [1, 1])
                par = M["scandisp"] if e.get("displace_cm") and e.get("disp") else M["scan"]
                if par is M["scandisp"]: tex["Disp"] = T.get(e.get("disp"))
                MI[name] = make_instance(name, par, {"Rot90": e.get("rot90", 0), "AntiTile": e.get("antitile", 0), "Macro": e.get("macro", 0),
                                                     "Desat": e.get("desat", 0), "RoughMul": e.get("rough_mul", 1.0)},
                                         {"Tile": [tu * 100.0 / 100.0, tv, 0, 0], "Tint": tint}, tex)
            else:
                tex["Alpha"] = T.get(e.get("alpha"))
                MI[name] = make_instance(name, M["foliage"], {"Desat": e.get("desat", 0.0)}, {"Tint": tint}, tex)
                if e.get("clip"):
                    try:
                        bpo = MI[name].get_editor_property("base_property_overrides")
                        setp(bpo, "override_opacity_mask_clip_value", True); setp(bpo, "opacity_mask_clip_value", float(e["clip"]))
                        setp(MI[name], "base_property_overrides", bpo); MEL.update_material_instance(MI[name]); EAL.save_loaded_asset(MI[name])
                    except Exception as ex: warn(f"clip {name}: {ex}")
        elif t == "vcfoliage":
            MI[name] = make_instance(name, M["vcfoliage"], {"Roughness": e.get("rough", 0.6)}, {"Tint": [1, 1, 1]})
        elif t == "glass":
            MI[name] = make_instance(name, M["glass"], {"Roughness": e.get("rough", 0.03), "Opacity": e.get("opacity", 0.55)}, {"Color": e.get("color_lin", [0.01, 0.01, 0.01])})
        else:
            MI[name] = make_instance(name, M["flat"], {"Roughness": e.get("rough", 0.5), "Metallic": e.get("metal", 0.0), "NoiseAmt": 0.08 if e.get("noise") else 0.0},
                                     {"Color": e.get("color_lin", [0.5, 0.5, 0.5])})
    log("material instances", len(MI))
    for k in ("MI_Brick", "MI_Pine", "MI_Leaves"):
        if k in MI:
            try: log("check", k, "parent", MI[k].get_editor_property("parent").get_name(), "tex", [str(p.parameter_value.get_name()) if p.parameter_value else None for p in MI[k].get_editor_property("texture_parameter_values")])
            except Exception as e: warn(f"check {k}: {e}")
    return MI


def meshes(MI):
    step("meshes")
    dest = f"{G}/Mesh"; out = {}
    for msh in SC["meshes"]:
        f = os.path.join(BUNDLE, "mesh", msh["fbx"]); p = asset_path(dest, f)
        typ = SC["materials"].get(msh["mi"], {}).get("type")
        nanite = typ not in ("glass",)
        if REIMPORT or os.path.splitext(msh["fbx"])[0] in REMESH or not EAL.does_asset_exist(p.split(".")[0]):
            got = import_files([f], dest, fbx_options(nanite))[f]
            sms = [g for g in got if isinstance(load(g), unreal.StaticMesh)]
            if sms and sms[0].split(".")[0] != p.split(".")[0]: warn(f"imported as {sms[0]}"); p = sms[0]
        sm = load(p)
        if not sm: continue
        ensure_nanite(sm, nanite)
        mi = MI.get(msh["mi"])
        if mi:
            for i in range(len(sm.get_editor_property("static_materials"))): sm.set_material(i, mi)
        EAL.save_loaded_asset(sm); out[msh["mi"]] = (sm, msh)
    # library models (plants, hedge balls, far trees): one mesh per variant
    dest = f"{G}/Lib"; lib = {}
    for mid, var in SC["models"].items():
        for vn, v in var.items():
            f = os.path.join(BUNDLE, "mesh", v["fbx"]); p = asset_path(dest, f)
            if REIMPORT or not EAL.does_asset_exist(p.split(".")[0]): import_files([f], dest, fbx_options(True))
            sm = load(p)
            if sm: ensure_nanite(sm, True); lib.setdefault(mid, {})[vn] = sm
    log("site meshes", len(out), "library variants", sum(len(v) for v in lib.values()))
    return out, lib


def axis_check(meshes_):
    """the importer's axis handling, read from the bounds of a big asymmetric part, so nothing depends on an assumption"""
    step("axis check")
    best = None
    for key in ("MI_Brick", "MI_Roof", "MI_Paving", "MI_Gravel"):
        if key in meshes_: sm, msh = meshes_[key]; break
    else:
        warn("axis check: no reference mesh"); return (1, -1, False)
    bb = sm.get_bounding_box(); umin, umax = bb.min, bb.max
    (bx0, by0, _), (bx1, by1, _) = msh["bounds"]
    cands = []
    for swap in (False, True):
        for sx in (1, -1):
            for sy in (1, -1):
                xs = (by0, by1) if swap else (bx0, bx1); ys = (bx0, bx1) if swap else (by0, by1)
                ex = sorted([sx * xs[0] * 100, sx * xs[1] * 100]); ey = sorted([sy * ys[0] * 100, sy * ys[1] * 100])
                err = abs(ex[0] - umin.x) + abs(ex[1] - umax.x) + abs(ey[0] - umin.y) + abs(ey[1] - umax.y)
                cands.append((err, swap, sx, sy))
    cands.sort(); err, swap, sx, sy = cands[0]
    REPORT["axis"] = {"ue_bounds": [[umin.x, umin.y, umin.z], [umax.x, umax.y, umax.z]], "blender_bounds": msh["bounds"],
                      "detected": {"swap": swap, "sx": sx, "sy": sy, "err_cm": err}, "expected": "x, -y"}
    log("axis detected swap", swap, "sx", sx, "sy", sy, "err cm", round(err, 1), "z", umin.z, umax.z)
    return (sx, sy, swap)


def actor_transform(det):
    """transform that takes the imported mesh frame D to the expected frame E = (x, -y)"""
    sx, sy, swap = det
    # D(b) = (sx*bx, sy*by) or swapped (sx*by, sy*bx); E(b) = (bx, -by); T = E D^-1
    import itertools
    D = [[0, sx], [sy, 0]] if swap else [[sx, 0], [0, sy]]
    Dinv = [[D[0][0], D[1][0]], [D[0][1], D[1][1]]]                 # orthonormal +-1: inverse = transpose
    E = [[1, 0], [0, -1]]
    T = [[sum(E[i][k] * Dinv[k][j] for k in range(2)) for j in range(2)] for i in range(2)]
    det_ = T[0][0] * T[1][1] - T[0][1] * T[1][0]
    s = 1 if det_ > 0 else -1
    Rm = [[T[0][0], T[0][1] * s], [T[1][0], T[1][1] * s]]
    yaw = math.degrees(math.atan2(Rm[1][0], Rm[0][0]))
    return yaw, s


def place(meshes_, lib, MI, det):
    step("place")
    yaw, s = actor_transform(det); REPORT["actor_fix"] = {"yaw": yaw, "scale_y": s}
    for mi, (sm, msh) in meshes_.items():
        a = EAS.spawn_actor_from_object(sm, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, yaw))
        a.set_actor_scale3d(unreal.Vector(1, s, 1)); a.set_actor_label(sm.get_name())
        comp = a.static_mesh_component
        setp(comp, "mobility", unreal.ComponentMobility.STATIC)
        mi_ = MI.get(mi)                                     # per-actor override as well as the asset's slot
        if mi_:
            for i in range(len(sm.get_editor_property("static_materials"))): comp.set_material(i, mi_)
    rnd = random.Random(11); n = 0
    for ins in SC["instances"]:
        var = lib.get(ins["model"], {})
        names = [v for v in (ins.get("variants") or var.keys()) if v in var] or list(var.keys())
        if not names: continue
        sm = var[rnd.choice(sorted(names))]
        bb = sm.get_bounding_box(); hz = max(bb.max.z - bb.min.z, 1e-3); wx = max(bb.max.x - bb.min.x, bb.max.y - bb.min.y, 1e-3)
        sc_ = ins["fit"]["h"] * 100.0 / hz
        w = ins["fit"].get("w")
        if w and wx * sc_ > w * 180: sc_ = max(sc_ * 0.7, w * 180 / wx)      # keep the measured spread (clumps wider than tall)
        x, y, z = ins["loc"]
        # border perennials read as one plant per spot from a library sprig: plant a clump of 3 (r7 vs walk_0053)
        subs = [(0, 0, 1.0)]
        if ins["of"].startswith("Plant2") and ins["model"] == "periwinkle_plant" and w:
            r_ = w * 0.22; subs = [(r_ * math.cos(t_), r_ * math.sin(t_), 0.8) for t_ in (0.3, 2.4, 4.5)] + [(0, 0, 1.0)]
        for dx, dy, f in subs:
            sm_ = sm if (dx, dy) == (0, 0) else var[rnd.choice(sorted(names))]
            a = EAS.spawn_actor_from_object(sm_, unreal.Vector((x + dx) * 100, -(y + dy) * 100, z * 100), unreal.Rotator(0, 0, ins.get("yaw", 0) + rnd.uniform(0, 360) * (dx != 0)))
            a.set_actor_scale3d(unreal.Vector(sc_ * f, sc_ * f, sc_ * f * rnd.uniform(0.92, 1.08))); a.set_actor_label(f"{ins['of']}_{n}")
            comp = a.static_mesh_component
            if ins.get("mi") and MI.get(ins["mi"]):
                for i in range(len(sm_.get_editor_property("static_materials"))): comp.set_material(i, MI[ins["mi"]])
            else:
                slots = SC.get("model_slots", {}).get(ins["model"], {})
                for i, sl in enumerate(sm_.get_editor_property("static_materials")):
                    k = str(sl.material_slot_name); m = MI.get(slots.get(k, ""))
                    if m: comp.set_material(i, m)
            n += 1
    log("instances placed", n)


def lighting():
    step("lighting")
    s = SC["sun"]; d = s["to_sun_ue"]
    sun = EAS.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 2000))
    rot = unreal.MathLibrary.make_rot_from_x(unreal.Vector(-d[0], -d[1], -d[2]))
    sun.set_actor_rotation(rot, False)
    lc = sun.light_component
    setp(lc, "mobility", unreal.ComponentMobility.MOVABLE)
    setp(lc, "intensity", 100000.0)                       # lux, physical; the atmosphere dims and warms it at 22 deg
    setp(lc, "light_color", unreal.Color(255, 255, 255, 255))
    setp(lc, "atmosphere_sun_light", True)
    setp(lc, "light_source_angle", 0.5357)
    setp(lc, "cast_shadows", True)
    setp(lc, "contact_shadow_length", 0.04)                  # pavers, kerbs, bins sit down (judge 2, r8)
    REPORT["sun_rotation"] = [rot.pitch, rot.yaw, rot.roll]
    sky = EAS.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
    sac = sky.get_component_by_class(unreal.SkyAtmosphereComponent)
    if sac:                                                  # clearer, bluer October sky than the default (r6 vs Jack's frames)
        setp(sac, "mie_scattering_scale", float(arg("--mie", "0.0022")))
        k = [float(x) for x in arg("--skylum", "1.1+1.2+1.45").split("+")]
        setp(sac, "sky_luminance_factor", unreal.LinearColor(k[0], k[1], k[2], 1))
    # ground to the horizon (the atmosphere's planet showed as a 'sea' line past the 80 m site ground)
    plane = load("/Engine/BasicShapes/Plane.Plane")
    if plane:
        g = EAS.spawn_actor_from_object(plane, unreal.Vector(0, 0, -15), unreal.Rotator(0, 0, 0))
        g.set_actor_scale3d(unreal.Vector(6000, 6000, 1)); g.set_actor_label("FarGround")
        fm = MATS.get("MI_FarGround")
        if fm: g.static_mesh_component.set_material(0, fm)
    sl = EAS.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 300))
    slc = sl.light_component
    setp(slc, "mobility", unreal.ComponentMobility.MOVABLE); setp(slc, "real_time_capture", True); setp(slc, "intensity", float(arg("--skylight", "1.5")))   # sky fill: shadow sides were near-black (judges r8)
    setp(slc, "source_type", E("SkyLightSourceType", "SLS_CAPTURED_SCENE"))
    if CLOUDS:
        vc = EAS.spawn_actor_from_class(unreal.VolumetricCloud, unreal.Vector(0, 0, 0))
        mat = load("/Engine/EngineSky/VolumetricClouds/m_SimpleVolumetricCloud_Inst.m_SimpleVolumetricCloud_Inst")
        if mat: setp(vc.get_component_by_class(unreal.VolumetricCloudComponent), "material", mat)
    fog = EAS.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0))
    fc = fog.component; setp(fc, "fog_density", float(arg("--fog", "0.0026"))); setp(fc, "fog_height_falloff", 0.2)
    pp = EAS.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
    setp(pp, "unbound", True)
    st = pp.settings
    for k, v in (("override_dynamic_global_illumination_method", True), ("dynamic_global_illumination_method", unreal.DynamicGlobalIlluminationMethod.LUMEN),
                 ("override_reflection_method", True), ("reflection_method", unreal.ReflectionMethod.LUMEN),
                 ("override_lumen_final_gather_quality", True), ("lumen_final_gather_quality", 2.0),
                 ("override_lumen_reflection_quality", True), ("lumen_reflection_quality", 2.0),
                 ("override_lumen_ray_lighting_mode", True), ("lumen_ray_lighting_mode", E("LumenRayLightingModeOverride", "HIT_LIGHTING_FOR_REFLECTIONS")),
                 ("override_auto_exposure_method", True), ("auto_exposure_method", unreal.AutoExposureMethod.AEM_MANUAL),
                 ("override_auto_exposure_apply_physical_camera_exposure", True), ("auto_exposure_apply_physical_camera_exposure", True),
                 ("override_camera_shutter_speed", True), ("camera_shutter_speed", 250.0),
                 ("override_camera_iso", True), ("camera_iso", 100.0),
                 ("override_auto_exposure_bias", True), ("auto_exposure_bias", EV),
                 ("override_vignette_intensity", True), ("vignette_intensity", 0.22),
                 ("override_bloom_intensity", True), ("bloom_intensity", 0.4),
                 ("override_film_slope", True), ("film_slope", 0.82), ("override_film_toe", True), ("film_toe", 0.6),
                 ("override_film_shoulder", True), ("film_shoulder", 0.3),
                 ("override_color_saturation", True), ("color_saturation", unreal.Vector4(0.93, 0.93, 0.93, 1.0)),
                 ("override_color_contrast", True), ("color_contrast", unreal.Vector4(0.97, 0.97, 0.97, 1.0)),
                 ("override_scene_fringe_intensity", True), ("scene_fringe_intensity", 0.3),
                 ("override_grain_intensity", True), ("grain_intensity", 0.08),
                 ("override_ambient_occlusion_intensity", True), ("ambient_occlusion_intensity", 0.6),
                 ("override_motion_blur_amount", True), ("motion_blur_amount", 0.0)):
        if v is not None: setp(st, k, v)
    setp(pp, "settings", st)


def cameras():
    step("cameras")
    sel = SC["check"] if CAMSEL == "check" else ([c["name"] for c in SC["cameras"]] if CAMSEL == "all" else CAMSEL.split("+"))
    shots = []
    for c in SC["cameras"]:
        if c["name"] not in sel: continue
        loc = unreal.Vector(*c["pos_cm"])
        rot = unreal.MathLibrary.make_rot_from_xz(unreal.Vector(*c["fwd"]), unreal.Vector(*c["up"]))
        cam = EAS.spawn_actor_from_class(unreal.CineCameraActor, loc, rot)
        cc = cam.get_cine_camera_component()
        fb = unreal.CameraFilmbackSettings(); setp(fb, "sensor_width", c["sensor_w_mm"]); setp(fb, "sensor_height", c["sensor_h_mm"])
        setp(cc, "filmback", fb)
        ls = cc.get_editor_property("lens_settings"); setp(ls, "min_focal_length", 4.0); setp(ls, "max_focal_length", 1000.0); setp(ls, "min_f_stop", 1.2); setp(ls, "max_f_stop", 32.0)
        setp(cc, "lens_settings", ls)
        setp(cc, "current_focal_length", c["focal_mm"]); setp(cc, "current_aperture", 11.0)
        fs = cc.get_editor_property("focus_settings"); setp(fs, "focus_method", E("CameraFocusMethod", "DISABLE")); setp(cc, "focus_settings", fs)
        cam.set_actor_label("Cam_" + c["name"])
        k = LONG / max(c["w"], c["h"]); res = (int(round(c["w"] * k / 2)) * 2, int(round(c["h"] * k / 2)) * 2)
        shots.append((cam, res, c)); log("camera", c["name"], res, "f", round(c["focal_mm"], 2), "rot", rot)
    return shots


def render(shots, extra=None):
    step("render")
    seqs = []
    for cam, res, c in shots:
        name = "S_" + c["name"]
        seq = fresh(name, f"{G}/Seq", unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
        seq.set_display_rate(unreal.FrameRate(24, 1)); seq.set_playback_start(0); seq.set_playback_end(1)
        binding = seq.add_spawnable_from_instance(cam)        # the sequence owns its camera (CORRECTIONS-LOG 140); the editor
                                                             # subsystem's variant left MRQ with "No camera actor found"
        add = getattr(seq, "add_track", None) or getattr(seq, "add_master_track")
        cut = add(unreal.MovieSceneCameraCutTrack); sec = cut.add_section(); sec.set_range(0, 1)
        try: sec.set_camera_binding_id(seq.get_binding_id(binding))
        except Exception: sec.set_camera_binding_id(unreal.MovieSceneSequenceExtensions.get_portable_binding_id(seq, seq, binding))
        EAL.save_loaded_asset(seq); seqs.append((seq, res, "png"))
    seqs += extra or []
    unreal.EditorLoadingAndSavingUtils.save_current_level()
    MQS = unreal.get_editor_subsystem(unreal.MoviePipelineQueueSubsystem)
    q = MQS.get_queue(); q.delete_all_jobs()
    cvars = {"r.Lumen.HardwareRayTracing": 1, "r.Lumen.HardwareRayTracing.LightingMode": 2, "r.Lumen.Reflections.HardwareRayTracing": 1,
             "r.Lumen.TranslucencyReflections.FrontLayer.Enable": 1, "r.Lumen.ScreenProbeGather.DownsampleFactor": 4, "r.Lumen.ScreenProbeGather.ShortRangeAO": 1, "r.ContactShadows": 1,
             "r.Lumen.Reflections.DownsampleFactor": 1, "r.Lumen.Reflections.MaxRoughnessToTrace": 0.6,
             "r.Shadow.Virtual.SMRT.RayCountDirectional": 16, "r.Shadow.Virtual.SMRT.SamplesPerRayDirectional": 8,
             "r.DepthOfFieldQuality": 0, "r.MotionBlurQuality": 0, "r.Tonemapper.Sharpen": 0.2, "r.Nanite.Tessellation": 1,
             "r.ScreenPercentage": 100, "r.Lumen.ScreenProbeGather.TemporalFilterProbes": 1, "r.SkyAtmosphere.SampleCountMax": 64}
    for seq, res, fmt in seqs:
        job = q.allocate_new_job(unreal.MoviePipelineExecutorJob)
        job.sequence = unreal.SoftObjectPath(seq.get_path_name()); job.map = unreal.SoftObjectPath(LEVEL["path"]); job.job_name = seq.get_name()
        cfg = job.get_configuration()
        cfg.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
        cfg.find_or_add_setting_by_class(unreal.MoviePipelineImageSequenceOutput_JPG if fmt == "jpg" else unreal.MoviePipelineImageSequenceOutput_PNG)
        o = cfg.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
        o.output_directory = unreal.DirectoryPath(OUT + ("/film" if fmt == "jpg" else "")); o.output_resolution = unreal.IntPoint(*res)
        o.file_name_format = "{sequence_name}.{frame_number}" if fmt == "jpg" else "{sequence_name}"; o.override_existing_output = True
        aa = cfg.find_or_add_setting_by_class(unreal.MoviePipelineAntiAliasingSetting)
        aa.override_anti_aliasing = True; aa.anti_aliasing_method = unreal.AntiAliasingMethod.AAM_NONE
        aa.spatial_sample_count = 1; aa.temporal_sample_count = SPP; aa.engine_warm_up_count = 48; aa.render_warm_up_count = 96
        try:
            go = cfg.find_or_add_setting_by_class(unreal.MoviePipelineGameOverrideSetting)
            setp(go, "cinematic_quality_settings", True); setp(go, "texture_streaming", E("MoviePipelineTextureStreamingMethod", "DISABLED"))
        except Exception as e: warn(f"game override: {e}")
        try:
            cv = cfg.find_or_add_setting_by_class(unreal.MoviePipelineConsoleVariableSetting)
            for k, v in cvars.items():
                if hasattr(cv, "add_or_update_console_variable"): cv.add_or_update_console_variable(k, float(v))
            if not hasattr(cv, "add_or_update_console_variable"):
                setp(cv, "start_console_commands", [f"{k} {v}" for k, v in cvars.items()])
        except Exception as e: warn(f"cvars: {e}")

    def finished(executor, ok):
        REPORT["render_ok"] = bool(ok); REPORT["seconds"] = time.time() - REPORT["t0"]
        json.dump(REPORT, open(os.path.join(OUT, "report.json"), "w"), indent=1, default=str)
        log("queue finished, success=%s" % ok); unreal.SystemLibrary.quit_editor()
    global EXECUTOR
    EXECUTOR = MQS.render_queue_with_executor(unreal.MoviePipelinePIEExecutor)
    EXECUTOR.on_executor_finished_delegate.add_callable_unique(finished)
    log("queued", len(seqs), "cameras")


LEVEL = {"path": f"{G}/L_Site"}
MATS = {}


def new_level():
    """a fresh level every run: new_level() silently keeps the editor in /Temp/Untitled when the asset already exists, and the
    queue then rendered the previous run's saved level (run r2/r3, 1 Nov)"""
    stamp = time.strftime("%H%M%S"); path = f"{G}/L_Site_{stamp}"
    ok = LES.new_level(path)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    wp = world.get_path_name() if world else ""
    log("level", path, "ok", ok, "world", wp)
    if not wp.startswith(path):
        warn(f"new_level did not open {path} (world {wp}); saving the current level as it")
        unreal.EditorLoadingAndSavingUtils.save_map(world, path)
    LEVEL["path"] = path


def render_video():
    """a walk film: one spawnable CineCamera keyed along the smoothed solved walk, JPG frames (assembled into MP4 locally)"""
    V = SC.get("video")
    if not V: warn("no video in scene.json"); return []
    step("video")
    cam = EAS.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(*V["keys"][0]["pos_cm"]), unreal.Rotator(0, 0, 0))
    cc = cam.get_cine_camera_component(); w, h = V["res"]
    fb = unreal.CameraFilmbackSettings(); setp(fb, "sensor_width", 36.0); setp(fb, "sensor_height", 36.0 * h / w); setp(cc, "filmback", fb)
    setp(cc, "current_focal_length", 18.0 / math.tan(math.radians(V["hfov_deg"]) / 2)); setp(cc, "current_aperture", 11.0)
    fs = cc.get_editor_property("focus_settings"); setp(fs, "focus_method", E("CameraFocusMethod", "DISABLE")); setp(cc, "focus_settings", fs)
    n = int(V["seconds"] * V["fps"]) + 1
    seq = fresh("S_walk_film", f"{G}/Seq", unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
    seq.set_display_rate(unreal.FrameRate(V["fps"], 1)); seq.set_playback_start(0); seq.set_playback_end(n)
    b = seq.add_spawnable_from_instance(cam)
    tr = b.add_track(unreal.MovieScene3DTransformTrack); sec = tr.add_section(); sec.set_range(0, n)
    ch = sec.get_all_channels()
    for k in V["keys"]:
        f = unreal.FrameNumber(int(round(k["t"] * V["fps"])))
        x, y, z = k["pos_cm"]
        for i, v in ((0, x), (1, y), (2, z), (3, 0.0), (4, k["pitch"]), (5, k["yaw"]), (6, 1.0), (7, 1.0), (8, 1.0)):
            ch[i].add_key(f, float(v))
    add = getattr(seq, "add_track", None) or getattr(seq, "add_master_track")
    cut = add(unreal.MovieSceneCameraCutTrack); cs = cut.add_section(); cs.set_range(0, n)
    cs.set_camera_binding_id(seq.get_binding_id(b))
    EAL.save_loaded_asset(seq)
    log("video frames", n, "keys", len(V["keys"]))
    return [(seq, (w, h), "jpg")]


def main():
    try:
        T = textures(); MI = materials(T)
        new_level()
        ms, lib = meshes(MI); det = axis_check(ms)
        MATS.update(MI); place(ms, lib, MI, det); lighting(); shots = cameras()
        unreal.EditorLoadingAndSavingUtils.save_current_level()
        json.dump(REPORT, open(os.path.join(OUT, "report.json"), "w"), indent=1, default=str)
        if "--video" in A:
            render([], extra=render_video()); return
        if "--no-render" in A or not shots:
            log("built, no render"); unreal.SystemLibrary.quit_editor(); return
        render(shots)
    except Exception as e:
        import traceback
        REPORT["fatal"] = traceback.format_exc(); warn("FATAL " + traceback.format_exc())
        json.dump(REPORT, open(os.path.join(OUT, "report.json"), "w"), indent=1, default=str)
        unreal.SystemLibrary.quit_editor()


if __name__ == "__main__":
    main()
