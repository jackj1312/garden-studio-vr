/**
 * Bake a viewable, self-contained furnished GLB from the version's fixed house
 * and effective saved layout; the live viewer keeps its fixed GLB + layout.
 *   node tools/house/bake_layout.mjs assets/sites/house [--layout-site house-wip --layout-root <checkout>] [version ...]
 * The normal background generator invokes the same command with --split after
 * writing its full temporary inputs. Artifacts and receipts stay private under
 * furnish/<version>/bakes. No save, history record or published route is changed.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {pathToFileURL} from 'node:url';
import * as T from '../../assets/vendor/three/build/three.module.js';
import {io,studioRequire,ROOT,sha,atomic,immutable,versionData} from './runtime_assets.mjs';
import {variantKey,variantModel,partColour} from '../../src/furnish/asset-recipe.mjs';
import {floorRecipe} from '../../src/furnish/floor-recipe.mjs';

const run=promisify(execFile);
const siteNameOK=id=>typeof id==='string'&&/^[a-z0-9][a-z0-9_-]{0,63}$/.test(id);
const {copyToDocument,dedup,unpartition,prune}=studioRequire('@gltf-transform/functions');
const sharp=studioRequire('sharp');
const up=new T.Vector3(0,1,0),one=new T.Vector3(1,1,1),kitRoot=path.join(ROOT,'tools/library/kit');
const read=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const pretty=o=>JSON.stringify(o,null,2)+'\n';
const rotation=d=>new T.Quaternion().setFromAxisAngle(up,d*Math.PI/180);
const pose=item=>new T.Matrix4().compose(new T.Vector3().fromArray(item.position),rotation(item.rotation),one);
const asciiOrder=(a,b)=>a<b?-1:a>b?1:0;
async function optionalBytes(file){try{return await fs.readFile(file);}catch(e){if(e.code==='ENOENT')return null;throw e;}}
function localFile(root,uri){
  const file=path.resolve(root,uri);
  if(!file.startsWith(root+path.sep))throw Error('Asset outside its declared root: '+uri);
  return file;
}
function effective(bytes,seed,version,siteId=null){
  const saved=bytes?JSON.parse(bytes):null;
  if(saved && (typeof saved!=='object'||Array.isArray(saved)||saved.schema!==undefined&&saved.schema!==1||
      saved.version!==undefined&&saved.version!==version||siteId&&saved.site!==undefined&&saved.site!==siteId||
      saved.items!==undefined&&!Array.isArray(saved.items)||!Number.isSafeInteger(saved.revision??0)||(saved.revision??0)<0))
    throw Error('Invalid saved layout identity or revision for '+(siteId||'candidate')+'/'+version);
  const own=saved && (saved.furnishSeeded===true||saved.items?.length>0);
  const items=own?(saved.items||[]):seed.items,walls=own?saved.wallColours:{...seed.wallColours,...saved?.wallColours},
    floors=own?saved.roomFloors:{...seed.roomFloors,...saved?.roomFloors};
  return {items,wallColours:walls||{},roomFloors:floors||{},source:own?'layout':'seed',revision:saved?.revision||0,hasSaved:!!saved,
    garden:saved?.garden||seed.garden||{schema:1,objects:[]}};
}
function sourceBinding(site,binding){
  if(!binding)return null;
  if(!siteNameOK(binding.site)||typeof (binding.projectRoot??'.')!=='string')throw Error('Invalid candidate layout source binding');
  const project=path.resolve(site,'../../..',binding.projectRoot||'.');
  return {project,site:binding.site,directory:path.join(project,'assets','sites',binding.site)};
}
async function snapshot(owner,site,def){
  if(!owner)return {saved:await optionalBytes(localFile(site,'layout/'+def.id+'.json')),row:def};
  const {stdout}=await run('python3',['-B',path.join(ROOT,'tools/layout_store.py'),'--build-snapshot',owner.project,owner.site,def.id],
    {encoding:'utf8',maxBuffer:32*1024*1024});
  const data=JSON.parse(stdout);
  return {saved:data.layout==null?null:Buffer.from(data.layout),row:data.version};
}
async function safeOwnerBytes(root,file){
  const base=await fs.realpath(root),resolved=await fs.realpath(localFile(root,file));
  if(!resolved.startsWith(base+path.sep))throw Error('Asset escapes its layout owner: '+file);
  return fs.readFile(resolved);
}
async function retainOwnerModels(site,def,registry,owner,sourceRow,items){
  if(!owner||!sourceRow.furnish_runtime?.variants)return registry;
  const uri=sourceRow.furnish_runtime.variants,registered=JSON.parse(await safeOwnerBytes(owner.directory,uri));
  const release=/^(releases\/[a-z0-9_-]+)\//.exec(uri);
  const resourceRoot=release?localFile(owner.directory,release[1]):owner.directory;
  const next={...registry,variants:{...registry.variants}};
  let changed=false;
  const copied=new Set();
  async function transfer(file){
    const match=/^furnish\/(?:models|buffers|textures)\/([a-f0-9]{64})\.(?:gltf|bin|png|jpe?g|webp|ktx2)$/.exec(file);
    if(!match)throw Error('Unregistered client variant resource '+file);
    const target=localFile(site,file),prior=await optionalBytes(target);
    // A model already in the candidate is identical only if its real content
    // matches the immutable name. Missing dependencies are still checked below.
    const bytes=prior||await safeOwnerBytes(resourceRoot,file);
    if(sha(bytes)!==match[1])throw Error('Conflicting immutable client variant '+file);
    if(!prior)await immutable(target,bytes);
    return bytes;
  }
  for(const key of new Set(items.map(i=>i.variant))){
    if(!Object.hasOwn(registered.variants||{},key))continue;
    const record=registered.variants[key];
    if(!/^site-[a-f0-9]{64}$/.test(key)||record.url!=='furnish/models/'+key.slice(5)+'.gltf')throw Error('Invalid immutable client variant '+key);
    for(const model of new Set([record.url,record.questUrl].filter(Boolean))){
      if(copied.has(model))continue;copied.add(model);
      const doc=JSON.parse(await transfer(model));
      for(const file of [...(doc.buffers||[]),...(doc.images||[])].map(x=>x.uri).filter(u=>u&&!u.startsWith('data:'))){
        const local=path.posix.normalize(path.posix.join(path.posix.dirname(model),file));
        if(!copied.has(local)){await transfer(local);copied.add(local);}
      }
    }
    if(!next.variants[key]){next.variants[key]=record;changed=true;}
    else if(next.variants[key].url!==record.url||next.variants[key].catalogueId!==record.catalogueId)
      throw Error('Regenerated variant conflicts with the owning client: '+key);
  }
  if(changed)await atomic(localFile(site,def.furnish_runtime.variants),pretty(next));
  return next;
}
async function floorPNG(def){
  const recipe=floorRecipe(def),{n,base,lines,motifs}=recipe,colour=new T.Color(base).convertLinearToSRGB().toArray().map(x=>Math.round(x*255));
  if(recipe.photo)return {image:await sharp(path.join(kitRoot,'maps',recipe.source)).png().toBuffer(),repeat:recipe.repeat};
  const bytes=Buffer.alloc(n*n*3),photo=recipe.source?await sharp(path.join(kitRoot,'maps',recipe.source)).resize(n,n,{fit:'fill'}).removeAlpha().toColourspace('srgb').raw().toBuffer():null;
  for(let i=0;i<bytes.length;i++)bytes[i]=Math.round(colour[i%3]*(photo ? .67+.33*photo[i]/255 : 1));
  const coords=pts=>pts.map(([x,y])=>x.toFixed(4)+','+y.toFixed(4)).join(' ');
  const svg='<svg xmlns="http://www.w3.org/2000/svg" width="'+n+'" height="'+n+'">'+
    lines.map(p=>'<polyline fill="none" stroke="#403932" stroke-opacity="'+(107/255)+'" stroke-width="1.3" points="'+coords(p)+'"/>').join('')+
    motifs.map(p=>'<polygon fill="#86766f" fill-opacity="'+(136/255)+'" points="'+coords(p)+'"/>').join('')+'</svg>';
  const image=await sharp(bytes,{raw:{width:n,height:n,channels:3}}).composite([{input:Buffer.from(svg)}]).png().toBuffer();
  return {image,repeat:recipe.repeat};
}
function copyMesh(document,mesh,change){
  const copy=document.createMesh(mesh.getName()).setExtras(mesh.getExtras()).setWeights(mesh.getWeights());
  for(const [index,original] of mesh.listPrimitives().entries()){
    const p=original.clone();change(p,index);copy.addPrimitive(p);
  }
  return copy;
}
async function applyFinishes(doc,layout,defs){
  const floors=new Map(),paint=new Map(),wallsFound=new Set(),floorsFound=new Set();
  const detail=new Map();
  async function detailMap(file,packed=false){
    if(detail.has(file))return detail.get(file);
    const bytes=await fs.readFile(path.join(kitRoot,'maps',file));
    let texture;
    if(packed){
      const {data,info}=await sharp(bytes).greyscale().raw().toBuffer({resolveWithObject:true});
      const rgb=Buffer.alloc(data.length*3);
      for(let i=0;i<data.length;i++){rgb[i*3]=255;rgb[i*3+1]=data[i];}
      const png=await sharp(rgb,{raw:{width:info.width,height:info.height,channels:3}}).png().toBuffer();
      texture=doc.createTexture(file).setImage(png).setMimeType('image/png');
    }else texture=doc.createTexture(file).setImage(bytes).setMimeType('image/jpeg');
    detail.set(file,texture);return texture;
  }
  let paintedPrimitives=0,coveredPrimitives=0;
  for(const n of doc.getRoot().listNodes()){
    const mesh=n.getMesh();if(!mesh)continue;
    const node=n.getExtras(),primitives=mesh.listPrimitives();
    const slots=primitives.map(p=>({...p.getExtras(),...p.getMaterial()?.getExtras()}));
    const mixed=primitives.length>1 && slots.some(s=>s.surface_id||s.surface_role);
    const edits=new Map();
    for(const [index,p] of primitives.entries()){
      const slot=slots[index];
      // An untagged brick primitive on a mixed carrier has no room finish.
      // Ordinary single-owner node finishes still supply their room as a default.
      if(mixed && !slot.surface_id && !slot.surface_role)continue;
      const id=slot.surface_id??node.surface_id,role=slot.surface_role??node.surface_role;
      if(!id)continue;
      const room=slot.room_id??node.room_id??(id.startsWith('floor/')?id.slice(6):null);
      if(role==='wall' && Object.hasOwn(layout.wallColours,id)){
        const hex=layout.wallColours[id];if(!/^#[0-9a-f]{6}$/i.test(hex))throw Error('Invalid wall colour '+id);
        const orig=p.getMaterial();if(!paint.has(orig))paint.set(orig,new Map());
        const pool=paint.get(orig);
        if(!pool.has(hex)){
          const tinted=orig.clone().setName(orig.getName()+' · '+hex);
          tinted.setBaseColorFactor([...new T.Color(hex).toArray(),orig.getBaseColorFactor()[3]]);pool.set(hex,tinted);
        }
        edits.set(index,{material:pool.get(hex)});wallsFound.add(id);paintedPrimitives++;
      }else if(role==='floor' && (Object.hasOwn(layout.roomFloors,room)||Object.hasOwn(layout.roomFloors,id))){
        const value=layout.roomFloors[room]??layout.roomFloors[id],key=typeof value==='string'?value:value?.id;
        if(!defs.has(key))throw Error('Unknown saved floor covering '+key);
        if(!floors.has(key)){
          const {image,repeat}=await floorPNG(defs.get(key));
          const texture=doc.createTexture(key).setImage(image).setMimeType('image/png');
          const material=doc.createMaterial('Client floor · '+key).setBaseColorTexture(texture).setRoughnessFactor(floorRecipe(defs.get(key)).roughness??.82).setMetallicFactor(0);
          const recipe=floorRecipe(defs.get(key));
          if(recipe.normal)material.setNormalTexture(await detailMap(recipe.normal)).setNormalScale(recipe.relief??1);
          if(recipe.rough)material.setMetallicRoughnessTexture(await detailMap(recipe.rough,true));
          material.getBaseColorTextureInfo().setWrapS(10497).setWrapT(10497);
          floors.set(key,{material,repeat});
        }
        edits.set(index,floors.get(key));floorsFound.add(room);coveredPrimitives++;
      }
    }
    if(!edits.size)continue;
    const world=new T.Matrix4().fromArray(n.getWorldMatrix());
    n.setMesh(copyMesh(doc,mesh,(p,index)=>{
      const edit=edits.get(index);if(!edit)return;
      p.setMaterial(edit.material);if(!edit.repeat)return;
      const pos=p.getAttribute('POSITION'),array=new Float32Array(pos.getCount()*2),v=new T.Vector3(),xyz=[];
      for(let i=0;i<pos.getCount();i++){
        v.fromArray(pos.getElement(i,xyz)).applyMatrix4(world);
        // PNG image row 0 is top. The live CanvasTexture explicitly flips Y.
        array[i*2]=v.x/edit.repeat[0];array[i*2+1]=1-v.z/edit.repeat[1];
      }
      p.setAttribute('TEXCOORD_0',doc.createAccessor().setType('VEC2').setArray(array).setBuffer(pos.getBuffer()));
    }));
  }
  for(const id of Object.keys(layout.wallColours))if(!wallsFound.has(id))throw Error('Painted room face missing in regenerated house: '+id);
  for(const id of Object.keys(layout.roomFloors))if(!floorsFound.has(id.replace(/^floor\//,'')))throw Error('Covered room floor missing: '+id);
  return {wallFaceIds:[...wallsFound].sort(),floorRoomIds:[...floorsFound].sort(),paintedPrimitives,coveredPrimitives};
}
function includeExtensions(target,source){
  for(const ext of source.getRoot().listExtensionsUsed())target.createExtension(ext.constructor).setRequired(ext.isRequired());
}
async function place(doc,site,layout,registry,stock,fixtureKitRoot=kitRoot){
  const scene=doc.getRoot().getDefaultScene()||doc.getRoot().listScenes()[0],variants=registry.variants||{};
  const byId=new Map(),poses=new Map(),nodes=new Map(),templates=new Map(),meshTints=new Map();
  const rows=layout.items.slice().sort((a,b)=>asciiOrder(a.id,b.id));
  async function template(model){
    const file=localFile(model.stock?fixtureKitRoot:site,model.file);
    if(!templates.has(file)){
      const src=await io.read(file);includeExtensions(doc,src);
      const roots=(src.getRoot().getDefaultScene()||src.getRoot().listScenes()[0]).listChildren();
      // No imported item root becomes a scene root on its own. Each occurrence
      // gets its own node hierarchy and references the same transferred meshes.
      const copied=copyToDocument(doc,src,src.getRoot().listMeshes());templates.set(file,{roots,copied});
    }
    return templates.get(file);
  }
  function instantiate(src,copied,item){
    const node=doc.createNode(src.getName()).setMatrix(src.getMatrix()).setExtras(src.getExtras());
    const mesh=copied.get(src.getMesh());
    if(mesh){
      const colours=mesh.listPrimitives().map(p=>partColour(item,p.getMaterial()?.getName()||'')||null);
      if(!colours.some(Boolean))node.setMesh(mesh);
      else{
        if(!meshTints.has(mesh))meshTints.set(mesh,new Map());
        const kl=JSON.stringify(colours),pool=meshTints.get(mesh);
        if(!pool.has(kl)){
          let index=0;pool.set(kl,copyMesh(doc,mesh,p=>{
            const hex=colours[index++];if(!hex)return;
            if(!/^#[0-9a-f]{6}$/i.test(hex))throw Error('Invalid finish on '+item.id);
            const m=p.getMaterial(),tinted=m.clone().setName(m.getName()+' · '+hex);
            p.setMaterial(tinted.setBaseColorFactor([...new T.Color(hex).toArray(),m.getBaseColorFactor()[3]]));
          }));
        }
        node.setMesh(pool.get(kl));
      }
    }
    for(const child of src.listChildren())node.addChild(instantiate(child,copied,item));
    return node;
  }
  for(const item of rows){
    if(!item.id||byId.has(item.id)||!Array.isArray(item.position)||item.position.length!==3||!item.position.every(Number.isFinite)||!Number.isFinite(item.rotation)||!item.host?.id)
      throw Error('Invalid furniture identity, pose or host '+item.id);
    const key=variantKey(item,stock),model=variantModel(key,variants,stock),def=model.stock?stock.get(key):variants[key];
    const size=def.size||def.size_m;
    if(!Array.isArray(item.size)||item.size.length!==3||!item.size.every((x,i)=>Number.isFinite(x)&&Math.abs(x-size[i])<=.002))throw Error('Layout size does not match the unscaled model for '+item.id);
    const t=await template(model),wrapper=doc.createNode('Layout/'+item.id);
    wrapper.setExtras({element:'SPEC-'+item.id,spec_id:item.id,kit_kind:item.kind,variant:key,catalogue_id:item.catalogueId,room_id:item.room,
      furnishing:true,stage_in:item.stageIn??1,stage_out:item.stageOut??null,seq:item.seq??0,seq_out:item.seqOut??1,group:'fitting',storey:item.storey,
      label:item.name||item.id,collide:!!item.collide,walkable:false,layout_host:item.host,host_offset_m:item.hostOffset,host_rotation_deg:item.hostRotation,
      size_m:item.size,finishes:item.finishes,lamp_on:item.lampOn});
    const frame=model.frontAngle?doc.createNode('Catalogue front').setRotation(rotation(model.frontAngle*180/Math.PI).toArray()):wrapper;
    if(frame!==wrapper)wrapper.addChild(frame);
    for(const n of t.roots)frame.addChild(instantiate(n,t.copied,item));
    byId.set(item.id,item);poses.set(item.id,pose(item));nodes.set(item.id,wrapper);
  }
  for(const item of rows){
    const local=poses.get(item.id).clone(),ownerId=item.host.id,owner=byId.get(ownerId),n=nodes.get(item.id);
    if(owner && ['surface','item'].includes(item.host.type)){
      // glTF forbids cycles; checking the logical graph here also prevents
      // corrupt input from recursing forever inside matrix evaluation.
      const chain=new Set([item.id]);let p=owner;
      while(p){if(chain.has(p.id))throw Error('Cyclic saved attachment '+p.id);chain.add(p.id);p=['surface','item'].includes(p.host.type)?byId.get(p.host.id):null;}
      local.premultiply(poses.get(ownerId).clone().invert());nodes.get(ownerId).addChild(n);
    }else{
      if(['surface','item'].includes(item.host.type)&&!registry.hosts?.[ownerId])throw Error('Missing fixed support '+ownerId+' for '+item.id);
      scene.addChild(n);
    }
    n.setMatrix(local.toArray());
  }
  for(const [id,n] of nodes){
    const m=n.getWorldMatrix(),target=poses.get(id).elements;
    if(m.some((v,i)=>Math.abs(v-target[i])>1e-6))throw Error('World transform mismatch on baked item '+id);
  }
  return {ids:rows.map(i=>i.id),variants:templates.size};
}
async function compile(site,def,layout,registry,defs,stock,ref,opts={}){
  const doc=await io.read(localFile(site,def.glb));
  if(doc.getRoot().listNodes().some(n=>n.getExtras().furnishing===true))throw Error('Baking requires a fixed-only version '+def.id);
  const finishes=await applyFinishes(doc,layout,new Map(defs.map(d=>[d.id,d])));
  const furniture=await place(doc,site,layout,registry,stock,opts.kitRoot);
  const scene=doc.getRoot().getDefaultScene()||doc.getRoot().listScenes()[0];
  scene.setExtras({...scene.getExtras(),furnish_bake:{version:def.id,layout:ref,revision:layout.revision,
    garden:{ref:layout.hasSaved?layout.layoutFile:null,objects:layout.garden.objects?.length||0,sha256:sha(JSON.stringify(layout.garden))}}});
  await doc.transform(unpartition(),dedup({propertyTypes:['Texture','Accessor']}),prune({propertyTypes:['Mesh','Primitive','PrimitiveTarget','Accessor','Material','Texture','Buffer'],keepAttributes:true,keepIndices:true,keepSolidTextures:true}));
  return {bytes:await io.writeBinary(doc),finishes,furniture};
}
async function bakeVersion(site,def,specRoot=path.join(site,'spec'),opts={}){
  if(!def.furnish_runtime)return null;
  const folder=path.join(site,'furnish',def.id,'bakes'),localPath='layout/'+def.id+'.json';
  const config=Object.hasOwn(opts,'layoutSource')?opts.layoutSource:
    await optionalBytes(path.join(site,'versions.json')).then(b=>b?JSON.parse(b).layout_source:null);
  const owner=sourceBinding(site,config),ownerId=owner?.site||path.basename(site);
  if(owner&&await fs.realpath(owner.directory)===await fs.realpath(site))throw Error('A bound client layout needs a distinct private build destination');
  const layoutPath='assets/sites/'+ownerId+'/'+localPath;
  const [seed,variants,floors,catalogue]=await Promise.all([read(localFile(site,def.furnish_runtime.seed)),read(localFile(site,def.furnish_runtime.variants)),
    optionalBytes(path.join(specRoot,'catalogue_v1.json')).then(b=>b?JSON.parse(b):{floors:[]}),opts.catalogue?Promise.resolve(opts.catalogue):read(path.join(kitRoot,'catalogue.json'))]);
  const stock=new Map(catalogue.items.map(i=>[i.id,i]));
  for(let attempt=0;attempt<3;attempt++){
    const input=await snapshot(owner,site,def),saved=input.saved,finger=saved?sha(saved):null;
    const layout=effective(saved,seed,def.id,owner?.site);layout.layoutFile=layoutPath;
    const registry=await retainOwnerModels(site,def,variants,owner,input.row,layout.items);
    const ref=layout.source==='layout'?layoutPath:'assets/sites/'+path.basename(site)+'/'+def.furnish_runtime.seed;
    const out=await compile(site,def,layout,registry,floors.floors,stock,ref,opts);
    const digest=sha(out.bytes),model=path.join(folder,digest+'.glb');
    await immutable(model,out.bytes);
    const receipt={schema:1,version:def.id,fixed:def.glb,source:layout.source,layout:ref,layoutSite:ownerId,layoutFile:layoutPath,
      layoutRevision:layout.revision,savedFileSHA256:finger,sourceRegistry:input.row.furnish_runtime?.variants||null,
      model:path.relative(site,model),modelSHA256:digest,items:out.furniture.ids,uniqueModels:out.furniture.variants,
      ...out.finishes,
      hosts:Object.fromEntries(layout.items.map(i=>[i.id,{...i.host,offset:i.hostOffset,rotation:i.hostRotation}])),
      garden:{ref:saved?layoutPath:null,count:layout.garden.objects?.length||0,sha256:sha(JSON.stringify(layout.garden))}};
    const body=pretty(receipt),stamp=path.join(folder,sha(body)+'.json');
    await immutable(stamp,body);
    const again=await snapshot(owner,site,def),recheck=again.saved;
    if((recheck?sha(recheck):null)!==finger||again.row.furnish_runtime?.variants!==input.row.furnish_runtime?.variants)continue;
    await atomic(path.join(folder,'latest.json'),body);
    console.log(def.id,'baked',receipt.items.length,'items from',receipt.source,'revision',receipt.layoutRevision,'at',receipt.model);
    return receipt;
  }
  throw Error('Layout kept changing during the bake; no new receipt published for '+def.id);
}
async function main(){
  const argv=process.argv.slice(2),siteName=argv.shift();
  if(!siteName)throw Error('Expected candidate site path and optional version IDs');
  const site=path.resolve(siteName);
  function option(k){
    const i=argv.indexOf(k);if(i<0)return null;
    if(!argv[i+1]||argv[i+1].startsWith('--'))throw Error('Missing '+k);
    return argv.splice(i,2)[1];
  }
  const prepared=option('--source-manifest'),specRoot=path.resolve(option('--spec-root')||path.join(site,'spec')),
    specPath=path.resolve(option('--spec-file')||path.join(specRoot,'spec_v1.json'));
  const split=argv.includes('--split');if(split)argv.splice(argv.indexOf('--split'),1);
  if(prepared&&(!split||path.dirname(path.resolve(prepared))!==site||!/^\.runtime-source-[\w-]+\.json$/.test(path.basename(prepared))))
    throw Error('Expected the generator-owned temporary source manifest inside the candidate site');
  const manifest=await read(prepared||path.join(site,'versions.json'));
  const requested=option('--layout-site'),override=option('--layout-root');
  if(requested||override) {
    const binding={...manifest.layout_source,...(requested?{site:requested}:{})};
    if(override)binding.projectRoot=path.relative(await fs.realpath(path.resolve(site,'../../..')),await fs.realpath(override))||'.';
    sourceBinding(site,binding);manifest.layout_source=binding;
  }
  const owner=sourceBinding(site,manifest.layout_source);
  if(owner&&await fs.realpath(owner.directory)===await fs.realpath(site))throw Error('A bound client layout needs a distinct private build destination');
  const spec=split?await read(specPath):null;
  const selected=manifest.versions.filter(v=>!argv.length||argv.includes(v.id));
  if(argv.some(id=>!selected.some(v=>v.id===id)))throw Error('Unknown version requested');
  for(const def of selected){
    const result=split?await versionData(site,def,spec,specRoot,!!owner):null,active=result||def;
    if(result)manifest.versions[manifest.versions.indexOf(def)]=result;
    if(active.furnish_runtime)await bakeVersion(site,active,specRoot,{layoutSource:manifest.layout_source});
  }
  // Only completed runtime assets become the version's live, fixed target.
  // Baked snapshots are deliberately never assigned to def.glb/glb_quest.
  if(split||prepared||requested||override)await atomic(path.join(site,'versions.json'),pretty(manifest));
  if(prepared)await fs.unlink(prepared);
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)await main();
export {bakeVersion,effective,compile};
