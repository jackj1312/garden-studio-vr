"""Native presentation lighting and deterministic animated practical effects.
No survey or browser scene is changed. Rebuildable from house-cinema.json.
"""
import json,math,os,random
import unreal
import garden_ue2 as s
FOLDER='/Game/HouseCinema'
def vec(p):return unreal.Vector(p[0]*100,p[2]*100,p[1]*100)
def flat(name,color,metal=0,rough=.5):
 m=s.fresh(name,FOLDER,unreal.Material,unreal.MaterialFactoryNew())
 s.P(s.vector(m,'Colour',(*color,1),0,0),'',unreal.MaterialProperty.MP_BASE_COLOR)
 s.P(s.scalar(m,'Roughness',rough,0,200),'',unreal.MaterialProperty.MP_ROUGHNESS)
 s.P(s.scalar(m,'Metal',metal,0,300),'',unreal.MaterialProperty.MP_METALLIC)
 s.MEL.recompile_material(m);s.EAL.save_loaded_asset(m);return m
def shape(name,primitive,position,size,mat,rotation=None):
 mesh=s.load('/Engine/BasicShapes/'+primitive+'.'+primitive)
 a=s.EAS.spawn_actor_from_object(mesh,vec(position),rotation or unreal.Rotator(0,0,0));a.set_actor_label('Cinema_'+name)
 a.set_actor_scale3d(unreal.Vector(size[0],size[2],size[1]));a.static_mesh_component.set_material(0,mat)
 return a
def light(name,p,lumen,kelvin,radius=2):
 a=s.EAS.spawn_actor_from_class(unreal.PointLight,vec(p));a.set_actor_label('Cinema_'+name);c=a.point_light_component
 for k,v in [('mobility',unreal.ComponentMobility.MOVABLE),('intensity_units',unreal.LightUnits.LUMENS),('intensity',lumen),('use_temperature',True),('temperature',kelvin),('attenuation_radius',radius*100),('source_radius',.1),('specular_scale',0.)]:s.setp(c,k,v)
 return a

def effects_material(name,mode):
 m=s.fresh(name,FOLDER,unreal.Material,unreal.MaterialFactoryNew())
 s.setp(m,'two_sided',True);s.setp(m,'blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT)
 s.setp(m,'shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
 uv=s.X(m,unreal.MaterialExpressionTextureCoordinate,-600,0);tm=s.X(m,unreal.MaterialExpressionTime,-600,200)
 custom=s.X(m,unreal.MaterialExpressionCustom,-300,0)
 inputs=[]
 for n in ['UV','T','Phase']+(['SmokeTex'] if mode=='fire' else []):
  q=unreal.CustomInput();q.set_editor_property('input_name',n);inputs.append(q)
 s.setp(custom,'inputs',inputs);s.setp(custom,'output_type',unreal.CustomMaterialOutputType.CMOT_FLOAT4)
 # Smooth coherent turbulent detail; deterministic at Sequencer time.
 noise="""float2 p=UV; float y=saturate(1-p.y); float t=T+Phase;
 float sway=(sin(t*2.3+y*5)*.045+sin(t*4.1+y*8)*.018)*y;
 float x=p.x-.5-sway;
 """
 if mode=='fire':
  code="""float time=T*18+Phase*11;float frame=fmod(floor(time),64);float next=fmod(frame+1,64);
  float2 flameUV=float2(UV.x,1-UV.y);float2 uv0=(flameUV+float2(fmod(frame,8),floor(frame/8)))/8;float2 uv1=(flameUV+float2(fmod(next,8),floor(next/8)))/8;
  float density=lerp(Texture2DSample(SmokeTex,SmokeTexSampler,uv0).a,Texture2DSample(SmokeTex,SmokeTexSampler,uv1).a,frac(time));
  float y=1-UV.y;float envelope=smoothstep(0,.08,y)*(1-smoothstep(.82,1,y));
  float taper=1-smoothstep(.43-.19*y,.50-.12*y,abs(UV.x-.5));
  float a=smoothstep(.04+y*.10,.28+y*.20,density)*envelope*taper;float core=saturate((density-.18)*2.8)*(1-y*.6);
  return float4(500+core*2500,50+core*900,5+core*150,a*.90);"""
 elif mode=='flame':code=noise+"""float width=.28*pow(max(.001,1-y),.65)+.012; float body=1-smoothstep(width*.55,width,abs(x));
 float a=body*smoothstep(0,.06,y)*(1-smoothstep(.85,1,y)); float core=(1-smoothstep(width*.08,width*.65,abs(x)))*(1-y);
 return float4(7000,950+core*4300,45+core*1300,a);"""
 else:code=noise+"""float width=.09+y*.23; float a=exp(-x*x/(width*width))*smoothstep(0,.12,y)*(1-y)*(1-y);
 a*=.75+.25*sin(y*8-t*1.3+sin(p.x*5+y*3));return float4(160,165,170,a*.28);"""
 if mode=='fire':
  tex=s.load('/Engine/Tutorial/SubEditors/TutorialAssets/T_SmokeSubUV_8X8.T_SmokeSubUV_8X8')
  if not tex:raise RuntimeError('Required Epic smoke atlas missing')
  texture=s.X(m,unreal.MaterialExpressionTextureObjectParameter,-600,600,parameter_name='SmokeAtlas',texture=tex)
  s.C(texture,'',custom,'SmokeTex')
 s.setp(custom,'code',code);s.C(uv,'',custom,'UV');s.C(tm,'',custom,'T');s.C(s.scalar(m,'Phase',0,-600,400),'',custom,'Phase')
 col=s.mask(m,custom,0,0,r=True,g=True,b=True)
 s.P(col,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
 alpha=s.X(m,unreal.MaterialExpressionComponentMask,0,200,r=False,g=False,b=False,a=True);s.C(custom,'',alpha,'Input');s.P(alpha,'',unreal.MaterialProperty.MP_OPACITY)
 s.MEL.recompile_material(m);s.EAL.save_loaded_asset(m);return m

def effects(config):
 folder=FOLDER+'/Geometry'
 meshes=[d.get_asset() for d in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(folder,recursive=True) if str(d.asset_class_path.asset_name)=='StaticMesh']
 if not meshes:
  task=unreal.AssetImportTask();task.filename='/tmp/job/EffectCard.gltf';task.destination_path=folder;task.automated=True;task.save=True;s.AT.import_asset_tasks([task])
  meshes=[d.get_asset() for d in unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_path(folder,recursive=True) if str(d.asset_class_path.asset_name)=='StaticMesh']
 if len(meshes)!=1:raise RuntimeError('Expected one metrically defined upright effect quad')
 effect_mesh=meshes[0];s.ensure_nanite(effect_mesh,False)
 flame=effects_material('LivingFlame','flame');fire=effects_material('LogFireAtlas','fire');steam=effects_material('CookingVapour','steam')
 wax=flat('WarmWax',(.75,.68,.50));iron=flat('Cookware',(.06,.065,.07),.8,.24)
 # Flame and steam cards are authored effects, deliberately confined to their source.
 def card(name,p,width,height,mat,yaw):
  phase=sum(ord(ch) for ch in name)*.37
  mi=s.make_instance('Phase_'+name+'_'+str(yaw),mat,scal={'Phase':phase})
  rotation=unreal.Rotator(roll=0,pitch=0,yaw=yaw)
  assert abs(rotation.pitch)<.001 and abs(rotation.roll)<.001 and abs(rotation.yaw-yaw)<.001
  a=s.EAS.spawn_actor_from_object(effect_mesh,vec(p),rotation);a.set_actor_label('Cinema_'+name);a.static_mesh_component.set_material(0,mi)
  a.set_actor_scale3d(unreal.Vector(width,1,height));s.setp(a.static_mesh_component,'cast_shadow',False);return a
 for i,c in enumerate(config['candles']+[dict(position=config['window_candle']['position'],height=.025)]):
  p=c['position']
  if i==len(config['candles']):shape('Candle'+str(i),'Cylinder',[p[0],p[1]-.04,p[2]],(.047,.08,.047),wax)
  for yaw in [0,90]:card('CandleFlame'+str(i),[p[0],p[1]+.012,p[2]],.018,.035,flame,yaw)
  light('CandleGlow'+str(i),[p[0],p[1]+.02,p[2]],5,1900,.65)
 st=config['stove']['position']
 for i,(width,height) in enumerate([(.16,.23),(.17,.30),(.14,.21)]):
  card('LogFlame'+str(i),[st[0]+.025-i*.008,st[1]-.055+height/2,st[2]+(i-1)*.075],width,height,fire,90)
 light('FireGlow',[st[0]+.10,st[1]+.07,st[2]],65,1900,1.8)
 p=config['pot']['position'];h=config['pot']['height'];r=config['pot']['radius']
 shape('Saucepan','Cylinder',[p[0],p[1]+h/2,p[2]],(r*2,h,r*2),iron)
 shape('Lid','Sphere',[p[0],p[1]+h+.004,p[2]],(r*2+.006,.018,r*2+.006),iron)
 shape('LidKnob','Cylinder',[p[0],p[1]+h+.021,p[2]],(.036,.025,.036),iron)
 shape('SaucepanHandle','Cube',[p[0]+r+.11,p[1]+h*.75,p[2]],(.23,.025,.025),iron)
 p=list(config['steam']['position']);p[0]-=.045;p[1]+=.006
 for yaw in [0,65,125]:card('HobSteam',[p[0],p[1]+.17,p[2]],.23,.35,steam,yaw)
 # Small motes use animated world-position offsets; restrained density, no fog blanket.
 dust=flat('DustMote',(.65,.60,.48),0,.8)
 tm=s.X(dust,unreal.MaterialExpressionTime,-500,400);sin=s.X(dust,unreal.MaterialExpressionSine,-300,400);s.C(tm,'',sin,'Input')
 drift=s.mul(dust,sin,s.vector(dust,'DriftCm',(1.2,.5,1.5,0),-300,500),-100,400);s.P(drift,'',unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET);s.MEL.recompile_material(dust)
 rng=random.Random(947)
 for i in range(90):
  p=[rng.uniform(.8,7.5),rng.uniform(.7,2.25),rng.uniform(-7.6,-.6)]
  shape('Mote'+str(i),'Sphere',p,(.0015,.0015,.0015),dust)
 s.REPORT['effects']={'fire':'animated Epic engine smoke-density atlas with warm emissive shading','candles':'animated flames with static warm practical lights','steam':'animated translucent vapour cards','dust':'90 gently moving motes','limits':'Not a fluid simulation; no birds or candle extinguishing smoke in this test'}

def apply(mode):
 config=json.load(open('/tmp/job/house-cinema.json'));look=config['garden' if mode=='garden' else 'interior']
 for a in list(s.EAS.get_all_level_actors()):
  if isinstance(a,unreal.StaticMeshActor):
   c=a.static_mesh_component
   if any(c.get_material(i) and c.get_material(i).get_name()=='GoldenClearGlass' for i in range(c.get_num_materials())):s.setp(c,'disallow_nanite',True)
  if a.get_actor_label().startswith('Cinema_'):s.EAS.destroy_actor(a);continue
  if isinstance(a,unreal.DirectionalLight):
   d=look['sun_to_ue'];a.set_actor_rotation(unreal.MathLibrary.make_rot_from_x(unreal.Vector(*[-x for x in d])),False)
   c=a.light_component
   for k,v in [('intensity',look['sun_lux']),('use_temperature',True),('temperature',look['sun_kelvin']),('light_source_angle',.7),('volumetric_scattering_intensity',1.2)]:s.setp(c,k,v)
  if isinstance(a,unreal.SkyLight):s.setp(a.light_component,'intensity',look['sky_intensity'])
  if isinstance(a,unreal.ExponentialHeightFog):
   s.setp(a.component,'fog_density',look['fog_density']);s.setp(a.component,'enable_volumetric_fog',True);s.setp(a.component,'volumetric_fog_scattering_distribution',.3)
  if isinstance(a,unreal.PostProcessVolume):
   pp=a.settings
   for k,v in [('override_auto_exposure_bias',True),('auto_exposure_bias',1.5 if mode=='garden' else 6.0),('override_film_toe',True),('film_toe',.4),('override_color_saturation',True),('color_saturation',unreal.Vector4(1,1,1,1)),('override_film_grain_intensity',True),('film_grain_intensity',0.),('override_lens_flare_intensity',True),('lens_flare_intensity',0.)]:s.setp(pp,k,v)
   s.setp(a,'settings',pp)
 if mode=='garden':
  light('TreeUplight',[4.5,-.12,10.1],180,2700,5)
 else:
  for i,f in enumerate(look['window_fills']):
   a=s.EAS.spawn_actor_from_class(unreal.RectLight,vec(f['position']));a.set_actor_label('Cinema_WindowFill'+str(i));d=[b-a for a,b in zip(f['position'],f['aim'])];a.set_actor_rotation(unreal.MathLibrary.make_rot_from_x(vec(d)),False)
   c=a.rect_light_component
   for k,v in [('mobility',unreal.ComponentMobility.MOVABLE),('intensity_units',unreal.LightUnits.LUMENS),('intensity',f['lumens']),('source_width',f['width']*100),('source_height',f['height']*100),('use_temperature',True),('temperature',4800),('attenuation_radius',1000)]:s.setp(c,k,v)
  effects(config['effects'])
 s.EAL.save_directory(FOLDER,only_if_is_dirty=True,recursive=True)
 s.REPORT['lighting_profile']=mode+' golden hour'
