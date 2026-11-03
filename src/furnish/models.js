import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { progress } from '../house/model.js?v=furnish2';
import {variantKey,variantModel,partColour} from './asset-recipe.mjs';

const KIT = new URL('../../tools/library/kit/', import.meta.url);
const FOLIAGE = /leaves|branches|VertexPlant|hedge|conifer|foliage|ivy/i;
const MATERIAL_MAPS = ['map','normalMap','aoMap','roughnessMap','metalnessMap','emissiveMap','alphaMap','sheenColorMap','sheenRoughnessMap','specularColorMap','specularIntensityMap'];
function renderedMaterialKey(gltf,material) {
  const parser=gltf.parser,index=parser?.associations.get(material)?.materials,definition=parser?.json.materials?.[index];
  if(!definition)return material.uuid;
  const shape=JSON.stringify(definition,(k,v)=>k==='extras'||k==='name'?undefined:
    v && typeof v==='object' && 'index' in v?{...v,index:'shared-map'}:v);
  return JSON.stringify([shape,material.name,material.vertexColors,...MATERIAL_MAPS.map(k=>material[k]?.uuid)]);
}

function namedTextures(gltf, material, url, shared) {
  // GLTFLoader caches within a document. Share the same fetched map, UV transform
  // and colour space across the small documents in this version as well.
  const parser=gltf.parser;
  if(!parser)return;
  for(const slot of MATERIAL_MAPS){
    const texture=material[slot];if(!texture)continue;
    const index=parser.associations.get(texture)?.textures,definition=parser.json.textures?.[index];
    const source=definition?.extensions?.EXT_texture_webp?.source ?? definition?.extensions?.KHR_texture_basisu?.source ?? definition?.source;
    const uri=parser.json.images?.[source]?.uri;
    if(!uri || uri.startsWith('data:'))continue;
    texture.updateMatrix();
    const key=JSON.stringify([new URL(uri,url).href,texture.colorSpace,texture.channel,texture.matrix.elements,
      texture.wrapS,texture.wrapT,texture.magFilter,texture.minFilter,texture.flipY]);
    if(!shared.has(key))shared.set(key,texture);
    else material[slot]=shared.get(key);
  }
}

export function createFurnitureModels({THREE:T,scene,site,version,variants={},catalogue=[],lite=false,onChange=()=>{},loader}){
  const group=new T.Group();group.name='Furniture '+version;group.userData.furnishRuntime=true;scene.add(group);
  const records=variants.variants||variants,itemsByKind=new Map((catalogue.items||catalogue).map(x=>[x.id,x]));
  const base=new URL('../../assets/sites/'+encodeURIComponent(site)+'/',import.meta.url);
  const gltfLoader=loader||new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  const promises=new Map(),prototypes=new Map(),batches=new Map(),sharedTextures=new Map(),sharedMaterials=new Map(),resources=new Set();
  const raycaster=new T.Raycaster(),matrix=new T.Matrix4(),yaw=new T.Quaternion(),up=new T.Vector3(0,1,0),tint=new T.Color();
  const pos=new T.Vector3(),one=new T.Vector3(1,1,1);let visibleItems=new Map(),generation=0,dead=false;
  const queue=[],parallel=lite?2:4;let inflight=0;
  function startNext(){
    while(queue.length && inflight<parallel){
      const job=queue.shift();
      if(dead){job.resolve(null);continue;}
      inflight++;
      gltfLoader.loadAsync(job.url).then(job.resolve,job.reject).finally(()=>{inflight--;startNext();});
    }
  }
  function fetchModel(url){
    return new Promise((resolve,reject)=>{queue.push({url,resolve,reject});startNext();});
  }

  function load(key){
    if(promises.has(key))return promises.get(key);
    const model=variantModel(key,records,itemsByKind,lite),url=new URL(model.file,model.stock?KIT:base).href;
    const job=fetchModel(url).then(gltf=>{
      if(!gltf)return;
      const resourcesHere=new Set(),parts=[];
      gltf.scene.updateMatrixWorld(true);
      const adapter=new T.Matrix4().makeRotationY(model.frontAngle);
      gltf.scene.traverse(o=>{
        if(!o.isMesh)return;
        if(Array.isArray(o.material))throw new Error('Furniture primitive has multiple materials: '+key);
        const m=o.material;resourcesHere.add(o.geometry);resourcesHere.add(m);
        for(const v of Object.values(m))if(v?.isTexture)resourcesHere.add(v);
        if(!dead){
          namedTextures(gltf,m,url,sharedTextures);
          // Follow the house material preparation: textured colours come from
          // their map and opaque closed furniture draws its outward faces.
          if(m.map && m.vertexColors)m.vertexColors=false;
          if(!FOLIAGE.test(m.name))m.side=T.FrontSide;
          if(m.transparent)m.depthWrite=false;
          if(FOLIAGE.test(m.name)&&m.transparent){m.transparent=false;m.depthWrite=true;m.alphaTest=Math.max(.5,m.alphaTest);m.alphaToCoverage=true;}
          if(m.aoMap)m.aoMapIntensity=1;
          for(const slot of MATERIAL_MAPS)if(m[slot])m[slot].anisotropy=4;
          const materialKey=renderedMaterialKey(gltf,m);
          if(!sharedMaterials.has(materialKey))sharedMaterials.set(materialKey,m);
          parts.push({geometry:o.geometry,material:sharedMaterials.get(materialKey),local:adapter.clone().multiply(o.matrixWorld)});
        }
      });
      if(dead){for(const resource of resourcesHere)resource.dispose();return;}
      for(const resource of resourcesHere)resources.add(resource);
      prototypes.set(key,parts);refresh(key);onChange();
    }).catch(err=>{promises.delete(key);throw err;});
    promises.set(key,job);return job;
  }
  function removeBatches(key){
    for(const b of batches.get(key)||[]){group.remove(b);b.dispose();}
    batches.delete(key);
  }
  function refresh(key){
    if(dead||!prototypes.has(key))return;
    const rows=visibleItems.get(key)||[];
    if(!rows.length){for(const b of batches.get(key)||[])b.visible=false;return;}
    let list=batches.get(key);
    if(!list||list.some(b=>b.instanceMatrix.count<rows.length)){
      removeBatches(key);
      list=prototypes.get(key).map(p=>{
        const count=2**Math.ceil(Math.log2(rows.length));
        const b=new T.InstancedMesh(p.geometry,p.material,count);b.castShadow=!p.material.transparent;b.receiveShadow=true;
        b.name='Furniture '+key;b.instanceMatrix.setUsage(T.DynamicDrawUsage);
        b.userData.furnishVariant=key;group.add(b);return b;
      });
      batches.set(key,list);
    }
    for(const [j,b] of list.entries()){
      const {local,material}=prototypes.get(key)[j];b.count=rows.length;b.visible=true;b.userData.furnishItems=rows.map(r=>r.item);
      const hadTint=!!b.instanceColor;
      rows.forEach(({item,lift},index)=>{
        pos.fromArray(item.position);pos.y+=lift;yaw.setFromAxisAngle(up,(item.rotation||0)*Math.PI/180);
        matrix.compose(pos,yaw,one).multiply(local);b.setMatrixAt(index,matrix);
        const colour=partColour(item,material.name);
        if(colour && /^#[a-f0-9]{6}$/i.test(colour)){
          tint.set(colour);
          for(const c of ['r','g','b'])tint[c]/=Math.max(.001,material.color?.[c]??1);
          b.setColorAt(index,tint);
        } else if(b.instanceColor)b.setColorAt(index,tint.setRGB(1,1,1));
      });
      if(b.instanceColor){b.instanceColor.needsUpdate=true;if(!hadTint)b.material.needsUpdate=true;}
      b.instanceMatrix.needsUpdate=true;b.computeBoundingSphere();
    }
  }
  function set(items,{visible=true,stage=Infinity,room=null,rooms=null}={}){
    if(dead)return Promise.resolve();
    const previous=visibleItems;const token=++generation;group.visible=visible;visibleItems=new Map();
    if(visible)for(const item of items){
      if(room && item.room!==room || rooms && !rooms.has(item.room))continue;
      const inc=progress(stage,item.stageIn??item.stage_in??1,item.seq??0);
      const end=item.stageOut??item.stage_out;
      if(inc<=.001 || end && progress(stage,end,item.seqOut??item.seq_out??1)>=.999)continue;
      const key=variantKey(item,itemsByKind);
      if(!visibleItems.has(key))visibleItems.set(key,[]);
      visibleItems.get(key).push({item,lift:.6*(1-inc)**3});
    }
    for(const key of batches.keys()){
      const before=previous.get(key)||[],after=visibleItems.get(key)||[];
      if(before.length!==after.length||after.some((r,i)=>r.item!==before[i].item||r.lift!==before[i].lift))refresh(key);
    }
    let jobs;
    try{jobs=[...visibleItems.keys()].filter(key=>!prototypes.has(key)).map(load);}
    catch(e){return Promise.reject(e);}
    group.updateMatrixWorld(true);onChange();
    return Promise.all(jobs).then(()=>{if(!dead&&token===generation)group.updateMatrixWorld(true);});
  }
  function pick(ray,far=Infinity){
    if(dead||!group.visible)return null;
    raycaster.ray.copy(ray);raycaster.near=.0001;raycaster.far=far;group.updateMatrixWorld(true);
    for(const hit of raycaster.intersectObjects(group.children.filter(b=>b.visible),false)){
      const item=hit.object.userData.furnishItems[hit.instanceId];if(!item)continue;
      hit.object.getMatrixAt(hit.instanceId,matrix);matrix.premultiply(hit.object.matrixWorld);
      const normal=hit.face.normal.clone().applyNormalMatrix(new T.Matrix3().getNormalMatrix(matrix));
      return {id:item.id,item,point:hit.point,normal,distance:hit.distance};
    }
    return null;
  }
  function clear(){return set([]);}
  function dispose(){
    dead=true;generation++;scene.remove(group);for(const key of batches.keys())removeBatches(key);
    for(const job of queue.splice(0))job.resolve(null);
    for(const r of resources)r.dispose();resources.clear();sharedTextures.clear();sharedMaterials.clear();prototypes.clear();promises.clear();
  }
  return {group,set,pick,clear,dispose};
}
