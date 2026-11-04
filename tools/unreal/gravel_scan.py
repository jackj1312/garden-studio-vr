"""Native metre-calibrated CC0 gravel, with real scan height displacement."""
import os,unreal
import garden_ue2 as s

def material(key='dry_river_pebbles',repeat_cm=25.,relief_cm=.45):
 folder='/Game/GardenGolden/Scan_'+key
 m=s.fresh('Scanned_'+key,folder,unreal.Material,unreal.MaterialFactoryNew())
 wp=s.X(m,unreal.MaterialExpressionWorldPosition,-900,0)
 xy=s.mask(m,wp,-750,0,r=True,g=True)
 uv=s.X(m,unreal.MaterialExpressionDivide,-550,0);s.C(xy,'',uv,'A');s.C(s.scalar(m,'ScanWidthCm',repeat_cm,-750,150),'',uv,'B')
 def tex(suffix,normal=False):
  file='/tmp/job/'+('gravel-scan' if key=='dry_river_pebbles' else key)+'/'+key+'_'+suffix+'_2k.jpg';dest=folder+'/Maps';target=s.asset_path(dest,file)
  if not s.EAL.does_asset_exist(target):s.import_files([file],dest)
  t=s.load(target)
  if normal:s.setp(t,'compression_settings',unreal.TextureCompressionSettings.TC_NORMALMAP);s.setp(t,'srgb',False)
  elif suffix!='diff':s.setp(t,'compression_settings',unreal.TextureCompressionSettings.TC_MASKS);s.setp(t,'srgb',False)
  sm=unreal.MaterialSamplerType
  return s.tex_param(m,suffix,-350,0,uv,sm.SAMPLERTYPE_NORMAL if normal else sm.SAMPLERTYPE_COLOR if suffix=='diff' else sm.SAMPLERTYPE_MASKS,t)
 col=tex('diff');normal=tex('nor_dx',True);arm=tex('arm');height=tex('disp') if relief_cm else s.scalar(m,'NoDisplacement',.5,0,800)
 attrs=s.X(m,unreal.MaterialExpressionMakeMaterialAttributes,300,0);names=s.MEL.get_material_expression_input_names(attrs)
 for node,output,key in [(col,'RGB','BaseColor'),(normal,'RGB','Normal'),(arm,'G','Roughness'),(arm,'R','AmbientOcclusion'),(height,'R' if relief_cm else '','Displacement')]:
  pin=next(str(n) for n in names if str(n).replace(' ','').lower()==key.lower());s.C(node,output,attrs,pin)
 s.setp(m,'use_material_attributes',True);s.P(attrs,'',unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
 s.setp(m,'enable_tessellation',bool(relief_cm));ds=unreal.DisplacementScaling();s.setp(ds,'magnitude',relief_cm);s.setp(ds,'center',.5);s.setp(m,'displacement_scaling',ds)
 s.MEL.recompile_material(m);s.EAL.save_loaded_asset(m);return m
