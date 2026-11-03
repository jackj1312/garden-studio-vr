/**
 * Split checked, furnished generator output into fixed house GLBs and editable
 * products, without opening Blender or changing the original source files.
 * node tools/house/runtime_assets.mjs assets/sites/<private-candidate> [version ...]
 * node tools/house/runtime_assets.mjs --check assets/sites/<private-candidate>
 * Then run quest_meshopt.py, fix_glb_textures.py and the candidate gates.
 * GLTF_TOOLS may point to an existing gltf-transform installation's directory.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createRequire,registerHooks} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import assert from 'node:assert/strict';
import * as T from '../../assets/vendor/three/build/three.module.js';

const ROOT=fileURLToPath(new URL('../../',import.meta.url));
const toolkit=process.env.GLTF_TOOLS || path.join(os.homedir(),'Documents/ChatGPT/.tools/gltf');
const require=createRequire(path.join(toolkit,'package.json'));
const {Document,NodeIO,Logger}=require('@gltf-transform/core');
const {ALL_EXTENSIONS}=require('@gltf-transform/extensions');
const {copyToDocument,prune}=require('@gltf-transform/functions');
const resolution=registerHooks({resolve(specifier,context,next){
  return specifier==='three'?{url:pathToFileURL(path.join(ROOT,'assets/vendor/three/build/three.module.js')).href,shortCircuit:true}:next(specifier,context);
}});
const {buildBVH}=await import('../../src/house/bvh.js');
resolution.deregister();
const io=new NodeIO().registerExtensions(ALL_EXTENSIONS).setLogger(new Logger(Logger.Verbosity.WARN));
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const json=async p=>JSON.parse(await fs.readFile(p,'utf8'));
const pretty=obj=>JSON.stringify(obj,null,2)+'\n';
const xyz=p=>p.toArray();
const v3=a=>new T.Vector3().fromArray(a);
const VUP=new T.Vector3(0,1,0),DOWN=new T.Vector3(0,-1,0);
const kit=await json(path.join(ROOT,'tools/library/kit/catalogue.json'));
const loose=n=>n.getExtras().furnishing===true||n.getExtras().lived_in===true;
const warnMissing=key=>{throw Error('No catalogue geometry for '+key);};
const kindMap={rail_cloth:'towel'};
const cache=new WeakMap();
const atomic=async(file,data)=>{const tmp=file+'.'+process.pid+'.tmp';await fs.mkdir(path.dirname(file),{recursive:true});await fs.writeFile(tmp,data);await fs.rename(tmp,file);};
async function immutable(file,data){
  try{await fs.access(file);return;}
  catch{await atomic(file,data);}
}
function stock(extra){
  const kind=kindMap[extra.kit_kind]||extra.kit_kind;
  const entry=kit.items.find(i=>i.kind===kind && i.style==='scandinavian')||kit.items.find(i=>i.kind===kind && i.style==='shared');
  return entry||warnMissing(kind);
}
function shape(node){
  const mesh=node.getMesh(),box=new T.Box3();
  for(const p of mesh.listPrimitives()){
    const a=p.getAttribute('POSITION');box.expandByPoint(v3(a.getMin([])));box.expandByPoint(v3(a.getMax([])));
  }
  const pivot=box.getCenter(new T.Vector3());pivot.y=box.min.y;
  const matrix=new T.Matrix4().fromArray(node.getWorldMatrix()),position=pivot.clone().applyMatrix4(matrix);
  const q=new T.Quaternion(),s=new T.Vector3();matrix.decompose(new T.Vector3(),q,s);
  const rotation=(2*Math.atan2(q.y,q.w)*180/Math.PI+540)%360-180;
  const size=box.getSize(new T.Vector3());
  return {node,box,pivot,matrix,position,rotation,size:[size.x,size.z,size.y],scale:s,pureYaw:Math.hypot(q.x,q.z)<1e-6};
}
function catalogueInfo(item,definition){
  const extra=item.node.getExtras(),k=stock(extra);
  return {id:extra.spec_id||extra.element,kind:extra.kit_kind||k.kind,style:k.style==='shared'?'scandinavian':k.style,
    catalogueId:k.id,name:extra.label||k.name,room:extra.room_id,position:xyz(item.position),rotation:item.rotation,size:item.size,
    storey:extra.storey,stageIn:extra.stage_in,stageOut:extra.stage_out||null,seq:extra.seq||0,seqOut:extra.seq_out??1,
    collide:!!extra.collide,sourceElement:extra.element,sourceKind:extra.spec_kind,
    ...(definition?.materials?{sourceFinishes:definition.materials}:{})};
}
function materialAsset(source,mesh){
  const asset=new Document();
  for(const ext of source.getRoot().listExtensionsUsed())asset.createExtension(ext.constructor).setRequired(ext.isRequired());
  const local=copyToDocument(asset,source,[mesh]).get(mesh);local.setName('Furniture');
  return {asset,local};
}
async function product(source,s,site){
  const {asset,local}=materialAsset(source,s.node.getMesh());
  const root=asset.createNode('Product').setMesh(local).setTranslation(s.pivot.clone().negate().toArray());
  asset.createScene('Item').addChild(root);
  for(const t of asset.getRoot().listTextures()){
    const data=t.getImage();if(!data)throw Error('Missing source image '+t.getName());
    if(!cache.has(data))cache.set(data,sha(data));
    const mime=t.getMimeType(),ext=({'image/webp':'webp','image/jpeg':'jpg','image/png':'png','image/ktx2':'ktx2'})[mime];
    if(!ext)throw Error('Unknown texture type '+mime);
    const uri='../textures/'+cache.get(data)+'.'+ext;t.setURI(uri);t.setName('');
  }
  for(const b of asset.getRoot().listBuffers())b.setURI('mesh.bin');
  const {json:j,resources}=await io.writeJSON(asset);
  for(const image of j.images||[])if(image.uri)await immutable(path.resolve(site,'furnish/models',image.uri),resources[image.uri]);
  for(const buffer of j.buffers||[]){
    const data=resources[buffer.uri];buffer.uri='../buffers/'+sha(data)+'.bin';
    await immutable(path.resolve(site,'furnish/models',buffer.uri),data);
  }
  const text=JSON.stringify(j),key=sha(text),url='furnish/models/'+key+'.gltf';
  await immutable(path.join(site,url),text);
  // Read the actual serialized product, including its content-addressed buffers.
  // Compare every exported vertex after applying the layout pose.
  const read=await io.read(path.join(site,url)),child=read.getRoot().listNodes()[0];
  const placement=new T.Matrix4().compose(s.position,new T.Quaternion().setFromAxisAngle(VUP,s.rotation*Math.PI/180),new T.Vector3(1,1,1));
  placement.multiply(new T.Matrix4().fromArray(child.getWorldMatrix()));
  const original=s.node.getMesh().listPrimitives(),result=child.getMesh().listPrimitives();
  if(original.length!==result.length)throw Error('Primitive mismatch: '+s.node.getName());
  let maxError=0,vertices=0;
  for(let i=0;i<original.length;i++){
    const a=original[i],b=result[i];
    for(const semantic of a.listSemantics()){
      const aa=a.getAttribute(semantic),bb=b.getAttribute(semantic);
      if(!bb||!Buffer.from(aa.getArray().buffer,aa.getArray().byteOffset,aa.getArray().byteLength).equals(
        Buffer.from(bb.getArray().buffer,bb.getArray().byteOffset,bb.getArray().byteLength)))throw Error('Attribute mismatch: '+semantic);
    }
    const indices=a.getIndices()?.getArray(),verified=b.getIndices()?.getArray();
    if(indices?.length!==verified?.length || indices?.some((n,j)=>n!==verified[j]))throw Error('Triangle index mismatch');
    const positions=a.getAttribute('POSITION').getArray(),copied=b.getAttribute('POSITION').getArray(),v=new T.Vector3(),u=new T.Vector3();
    for(let j=0;j<positions.length;j+=3){
      v.fromArray(positions,j).applyMatrix4(s.matrix);u.fromArray(copied,j).applyMatrix4(placement);maxError=Math.max(maxError,v.distanceTo(u));vertices++;
    }
  }
  if(maxError>.00001)throw Error('World pose differs by '+maxError+' m for '+s.node.getName());
  return {key:'site-'+key,url,maxError,vertices};
}
function partTable(doc,elements,stage){
  const table=new Map(elements.elements.map(e=>[e.id,e])),parts=[],infos=new Map();
  for(const n of doc.getRoot().listNodes()){
    const e=n.getExtras();if(!n.getMesh()||e.context||e.stage_out&&e.stage_out<=stage||table.get(e.element)?.layer==='as_built')continue;
    if(!e.spec_id&&!e.surface_role&&!/window|board|sill|floor|wall_|ceiling|joinery/i.test(e.group+' '+n.getName()))continue;
    const s=shape(n);infos.set(n,s);
    for(const p of n.getMesh().listPrimitives()){
      const position=p.getAttribute('POSITION');if(!position)continue;
      const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.BufferAttribute(position.getArray(),3));
      if(p.getIndices())geometry.setIndex(new T.BufferAttribute(p.getIndices().getArray(),1));
      parts.push({index:parts.length,node:n,e,geometry,matrix0:s.matrix});
    }
  }
  const bvh=buildBVH(parts);
  return {parts,infos,bvh};
}
const board=(n,e)=>/board|window_sill|sill.board/i.test(n.getName()+' '+(e.label||''));
function lowSamples(s){
  const points=[],v=new T.Vector3(),all=s.node.getMesh().listPrimitives().map(p=>p.getAttribute('POSITION').getArray());
  let stride=0,total=0;
  // Match the source validator: centre + evenly spaced footing vertices.
  for(const a of all)for(let j=0;j<a.length;j+=3)if(a[j+1]<=s.box.min.y+.01001)total++;
  const step=Math.max(1,Math.floor(total/10)),mean=new T.Vector3();
  for(const a of all)for(let j=0;j<a.length;j+=3)if(a[j+1]<=s.box.min.y+.01001){
    v.fromArray(a,j).applyMatrix4(s.matrix);mean.add(v);
    if(stride++%step===0 && points.length<12)points.push(v.clone());
  }
  if(total)points.unshift(mean.divideScalar(total));return points;
}
function localOffset(parent,p){
  const q=new T.Quaternion().setFromAxisAngle(VUP,-parent.rotation*Math.PI/180);
  return v3(p).sub(v3(parent.position)).applyQuaternion(q).toArray();
}
function fixedHost(s,type,room,id){
  const world=s.box.clone().applyMatrix4(s.matrix);
  return {id,type,room,position:xyz(s.position),rotation:s.rotation,bounds:[xyz(world.min),xyz(world.max)],size:s.size};
}
function assignHosts(rows,ctx,rooms){
  const hosts={},byNode=new Map(rows.map(r=>[r.node,r])),byId=new Map([...ctx.infos.keys()].map(n=>[n.getExtras().spec_id,n]));
  const floorY=new Map(rooms.map(r=>[r.id,r.floor_y])),ray=new T.Ray();
  const mask=new Uint8Array(ctx.parts.length);
  function closest(s,origins,dir,allowed,far){
    ctx.parts.forEach((p,i)=>{mask[i]=p.node!==s.node&&allowed(p)?1:0;});
    let best=null;
    for(const o of origins){
      ray.set(o,dir);const h=ctx.bvh.raycast(ray,far,mask,null,dir===DOWN);
      if(!h)continue;
      if(dir===DOWN && h.normal.y<.15)continue;
      if(!best||h.distance<best.distance)best={node:ctx.parts[h.part].node,distance:h.distance,point:h.point.clone()};
    }
    return best;
  }
  for(const s of rows){
    const row=s.row,e=s.node.getExtras(),r=row.room,entry=stock(e);
    let host,owner,contact;
    const explicit=e.host_id;
    if(explicit && byId.has(explicit)){owner=byId.get(explicit);host={type:'surface',id:explicit};}
    const wall=entry.host==='wall'&&e.spec_kind!=='standing_picture_frame_01';
    if(!host && wall){
      const front=new T.Vector3(0,0,-1).applyAxisAngle(VUP,row.rotation*Math.PI/180);
      const sideways=new T.Vector3(1,0,0).applyAxisAngle(VUP,row.rotation*Math.PI/180);
      const origins=[];
      for(const offset of [0,-.46,.46,-.58,.58])for(const level of [.5,.94,.06]){
        const p=s.position.clone().addScaledVector(sideways,offset*s.size[0]);p.y+=s.size[2]*level;origins.push(p);
      }
      const allowed=p=>p.e.surface_role==='wall'&&p.e.room_id===r&&p.e.surface_id;
      let hit=closest(s,origins,front.clone().negate(),allowed,.85);
      if(!hit)hit=closest(s,origins,front,allowed,.85);
      // A blind inside an opening is fastened to its head. Its wall has no
      // opaque face in the opening; probe at the pocket and jamb level too.
      if(!hit){
        const ends=origins.map(p=>{p=p.clone();p.y=(floorY.get(r)??0)+.16;return p;});
        hit=closest(s,ends,front.clone().negate(),allowed,.9)||closest(s,ends,front,allowed,.9);
      }
      if(hit){owner=hit.node;contact=hit.point;host={type:'wall',id:owner.getExtras().surface_id};}
    }
    if(!host && entry.host==='ceiling'){host={type:'ceiling',id:'ceiling/'+r};}
    if(!host && !wall){
      const origins=lowSamples(s).map(p=>new T.Vector3(p.x,s.position.y+.01,p.z));
      const closeEnough=s.position.y-(floorY.get(r)??0)<.06;
      const eligible=p=>(!p.e.room_id||p.e.room_id===r)&&p.e.surface_role!=='ceiling'&&p.e.surface_role!=='wall'&&
        (!loose(p.node)||ctx.infos.get(p.node).position.y<s.position.y-.001)&&
        (!explicit || board(p.node,p.e)) && (p.e.spec_id || p.e.surface_role==='floor' || board(p.node,p.e));
      let hit=closest(s,origins,DOWN,eligible,closeEnough?.09:.26);
      // The source snap could stop on the underside of a 36 mm desktop.
      // Probe through its thickness from above before accepting a lower face.
      const rigid=!['cushion','throw','rug','rail_cloth'].includes(row.kind);
      if(!closeEnough && rigid){
        const upper=origins.map(p=>p.clone().addScaledVector(VUP,.06));
        const above=closest(s,upper,DOWN,eligible,.135);
        if(above && above.point.y>s.position.y+.010 && above.point.y<s.position.y+.061)hit=above;
      }
      if(hit){
        owner=hit.node;contact=hit.point;const meta=owner.getExtras();
        if(meta.surface_role==='floor')host={type:'floor',id:'floor/'+r};
        else host={type:'surface',id:meta.spec_id||owner.getName()};
      }else if(closeEnough&&!explicit){host={type:'floor',id:'floor/'+r};}
    }
    if(!host)throw Error('No measured host for '+row.id+' ('+row.kind+', '+r+', '+explicit+'); check original surface and signed evidence.');
    row.host=host;
    if(host.type==='surface'){
      const other=byNode.get(owner)?.row||fixedHost(ctx.infos.get(owner),'surface',r,host.id);
      row.hostOffset=localOffset(other,row.position);row.hostRotation=row.rotation-other.rotation;
      if(!byNode.has(owner))hosts[host.id]=other;
    }else if(owner&&host.type==='wall'&&!hosts[host.id]){
      hosts[host.id]=fixedHost(ctx.infos.get(owner),'wall',r,host.id);
    }
    if(contact)row.hostContact=xyz(contact);
  }
  // Offer the actual fixed cabinet, joinery and sanitary shapes for future
  // supported decorations, including fixtures that have no current child.
  for(const [node,s] of ctx.infos){
    const e=node.getExtras();if(!e.spec_id||loose(node)||hosts[e.spec_id]||!e.room_id)continue;
    hosts[e.spec_id]=fixedHost(s,'surface',e.room_id,e.spec_id);
  }
  // No implicit cycles are permitted in a released support hierarchy.
  const all=new Map(rows.map(e=>[e.row.id,e.row]));
  for(const r of all.values()){
    const seen=new Set([r.id]);let p=r;
    while(p.host.type==='surface' && all.has(p.host.id)){
      if(seen.has(p.host.id))throw Error('Cyclic host at '+p.host.id);
      seen.add(p.host.id);p=all.get(p.host.id);
    }
  }
  return hosts;
}
function seatedSeed(raw){
  const input=new Map(raw.map(r=>[r.id,r])),deltas=new Map(),seating=[];
  function displacement(row){
    if(deltas.has(row.id))return deltas.get(row.id);
    let local=0;
    if(row.host.type==='surface' && row.hostContact && !['cushion','throw','rug','rail_cloth'].includes(row.kind)){
      const d=row.hostContact[1]-row.position[1];
      if(Math.abs(d)>.010 && Math.abs(d)<=.061)local=d;
    }
    const parent=input.get(row.host.id),inherited=parent?displacement(parent).total:0;
    const result={local,total:local+inherited};deltas.set(row.id,result);return result;
  }
  const items=raw.map(row=>{
    const d=displacement(row);if(!d.total)return row;
    const position=row.position.slice();position[1]+=d.total;
    const local=row.hostOffset?.slice();if(local)local[1]+=d.local;
    seating.push({id:row.id,host:row.host.id,original:row.position,position,contact:row.hostContact,localDeltaY:d.local,deltaY:d.total});
    return {...row,originalPosition:row.position,position,seatDeltaY:d.total,...(local?{hostOffset:local}:{})};
  });
  return {items,seating};
}
async function checkSeatTriangles(site,raw,variants,seating){
  const byId=new Map(raw.map(row=>[row.id,row])),loaded=new Map();
  for(const e of seating){
    const parent=byId.get(e.host);
    if(!e.localDeltaY||!parent)continue;
    const v=variants[parent.variant];
    for(const url of new Set([v.url,v.questUrl].filter(Boolean))){
      if(!loaded.has(url))loaded.set(url,await io.read(path.join(site,url)));
      const n=loaded.get(url).getRoot().listNodes()[0];
      const m=new T.Matrix4().compose(v3(parent.position),new T.Quaternion().setFromAxisAngle(VUP,parent.rotation*Math.PI/180),new T.Vector3(1,1,1));
      m.multiply(new T.Matrix4().fromArray(n.getWorldMatrix()));
      const point=v3(e.contact),ray=new T.Ray(point.clone().addScaledVector(VUP,.005),DOWN),hit=new T.Vector3();
      let gap=Infinity;
      for(const p of n.getMesh().listPrimitives()){
        const pos=p.getAttribute('POSITION').getArray(),ix=p.getIndices()?.getArray();
        const verts=[new T.Vector3(),new T.Vector3(),new T.Vector3()];
        for(let i=0;i<(ix?.length??pos.length/3);i+=3){
          for(let j=0;j<3;j++)verts[j].fromArray(pos,3*(ix?ix[i+j]:i+j)).applyMatrix4(m);
          if(ray.intersectTriangle(...verts,true,hit))gap=Math.min(gap,hit.distanceTo(point));
        }
      }
      if(gap>.0001)throw Error('Unseated emitted parent triangle '+e.host+' under '+e.id+': '+gap+' m');
    }
  }
}
async function fixed(doc,site,version,profile,rows){
  for(const s of rows)s.node.dispose();
  const properties=['Mesh','Primitive','PrimitiveTarget','Accessor','Material','Texture','Buffer'];
  await doc.transform(prune({propertyTypes:properties,keepAttributes:true,keepIndices:true,keepSolidTextures:true}));
  if(doc.getRoot().listNodes().some(loose))throw Error('A loose item remained in the fixed house');
  const target=path.join(site,'furnish',version,profile==='full'?'fixed.glb':'fixed_quest.glb');
  await atomic(target,await io.writeBinary(doc));
  return path.relative(site,target);
}
async function versionData(site,def,spec,specRoot=path.join(site,'spec')){
  const vkey=Object.keys(spec.versions).find(k=>spec.versions[k].elements===def.id);
  if(!vkey)return null;
  const specVersion=spec.versions[vkey],items=new Map(specVersion.items.map(i=>[i.id,i]));
  const out=path.join(site,'furnish',def.id),variants={},raw=[],report={version:def.id,profiles:{},maxWorldErrorM:0};
  const elements=await json(path.join(site,def.elements)),stage=(await json(path.join(site,def.stages))).stages.length;
  const fixedPaths={};let hosts;
  for(const [profile,file] of [['full',def.id+'.glb'],['quest',def.id+'_quest.glb']]){
    const source=path.join(site,file);
    const doc=await io.read(source);
    const nodes=doc.getRoot().listNodes(),rows=nodes.filter(loose).map(shape);
    if(!rows.length)throw Error('No furnished source at '+source);
    for(const s of rows){
      if(!s.pureYaw||s.scale.distanceTo(new T.Vector3(1,1,1))>.00001)throw Error('Unsupported scaled or tilted loose item: '+s.node.getName());
      const e=s.node.getExtras();s.row=catalogueInfo(s,items.get(e.spec_id));
    }
    if(new Set(rows.map(s=>s.row.id)).size!==rows.length)throw Error('Duplicate loose item id');
    if(profile==='full'){
      const ctx=partTable(doc,elements,stage);hosts=assignHosts(rows,ctx,specVersion.rooms);
    }
    for(const s of rows){
      const built=await product(doc,s,site),r=s.row;
      report.maxWorldErrorM=Math.max(report.maxWorldErrorM,built.maxError);
      if(profile==='full'){
        r.variant=built.key;
        variants[r.variant]={url:built.url,size:r.size,kind:r.kind,catalogueId:r.catalogueId,style:r.style,front:'-Z'};
        raw.push(r);
      }else{
        const original=raw.find(old=>old.id===r.id);
        if(!original||original.position.some((x,i)=>Math.abs(x-r.position[i])>1e-5)||original.size.some((x,i)=>Math.abs(x-r.size[i])>1e-5))
          throw Error('Quest variant differs from the measured desktop pose: '+r.id);
        variants[original.variant].questUrl=built.url;
      }
    }
    if(profile==='quest'&&rows.length!==raw.length)throw Error('Desktop and Quest loose sets differ');
    const fileKey=profile==='full'?'glb':'glb_quest';
    fixedPaths[fileKey]=await fixed(doc,site,def.id,profile,rows);
    report.profiles[profile]={source:file,fixed:fixedPaths[fileKey],sourceNodes:nodes.length,items:rows.length,fixedNodes:doc.getRoot().listNodes().length};
  }
  await fs.mkdir(out,{recursive:true});
  const measured=pretty({schema:1,items:raw}),rawPath=path.join(out,'measured-'+sha(measured)+'.json');
  await immutable(rawPath,measured);report.measuredSeed=path.relative(site,rawPath);
  const seated=seatedSeed(raw);report.seating=seated.seating;
  await checkSeatTriangles(site,raw,variants,seated.seating);
  const input=path.join(out,'seed.seated.json');await atomic(input,pretty({schema:1,items:seated.items}));
  // A version may still have an older measured product in its live client
  // layout. Its content-addressed model stays immutable across regenerations.
  const optional=async file=>{try{return await json(file);}catch(err){if(err.code!=='ENOENT')throw err;return null;}};
  const saved=await optional(path.join(site,'layout',def.id+'.json'));
  const old=await optional(path.join(out,'variants.json'));
  for(const row of saved?.items||[])if(!variants[row.variant] && old?.variants?.[row.variant])variants[row.variant]=old.variants[row.variant];
  // The historical placement gate needs the actual measured fixed hosts
  // even on the first build, before any earlier index exists.
  await atomic(path.join(out,'variants.json'),pretty({schema:1,variants,hosts,sourceIds:raw.map(i=>i.id)}));
  const history=await optional(path.join(specRoot,'changes/changes.json'));
  const merged=history?JSON.parse(execFileSync(process.execPath,[path.join(ROOT,'src/planner/seed_changes.mjs'),
    '--site-root',site,'--spec-root',specRoot,'--version',def.id,'--seed',input],{encoding:'utf8',maxBuffer:16e6})):
    {schema:1,items:seated.items,wallColours:{},roomFloors:{},appliedChangeIds:[]};
  if(!Array.isArray(merged.items))throw Error('Legacy seed migration returned no furniture');
  await atomic(path.join(out,'seed.json'),pretty(merged));report.variants=Object.keys(variants).length;
  await atomic(path.join(out,'split-check.json'),pretty(report));
  console.log(def.id,report.profiles.full.items,'measured items;',report.variants,'site variants;',report.maxWorldErrorM,'m maximum world-space error');
  const result={...def,...fixedPaths,furnish_runtime:{seed:'furnish/'+def.id+'/seed.json',variants:'furnish/'+def.id+'/variants.json'}};
  delete result.glb_quest_meshopt;return result;
}
async function glbHeader(file){
  const fd=await fs.open(file);
  try{
    const head=Buffer.alloc(20);await fd.read(head,0,20,0);
    assert.equal(head.toString('ascii',0,4),'glTF');assert.equal(head.toString('ascii',16,20),'JSON');
    const data=Buffer.alloc(head.readUInt32LE(12));await fd.read(data,0,data.length,20);return JSON.parse(data);
  }finally{await fd.close();}
}
async function audit(site){
  const manifest=await json(path.join(site,'versions.json')),files=new Map();
  async function asset(file){
    if(!files.has(file)){
      const bytes=await fs.readFile(file),digest=path.basename(file).split('.')[0];
      assert.equal(sha(bytes),digest,'Content changed under its immutable asset URL: '+file);files.set(file,bytes);
    }
    return files.get(file);
  }
  for(const v of manifest.versions.filter(v=>v.furnish_runtime)){
    const dir=path.join(site,'furnish',v.id),report=await json(path.join(dir,'split-check.json')),
      variants=await json(path.join(site,v.furnish_runtime.variants)),seed=await json(path.join(site,v.furnish_runtime.seed));
    assert.ok(report.maxWorldErrorM<=.00001);
    const measured=await fs.readFile(path.join(site,report.measuredSeed));
    assert.equal(path.basename(report.measuredSeed),'measured-'+sha(measured)+'.json');
    const rows=JSON.parse(measured).items;
    assert.deepEqual(rows.map(i=>i.id).sort(),[...variants.sourceIds].sort());
    assert.equal(new Set(seed.items.map(i=>i.id)).size,seed.items.length);
    for(const profile of Object.values(report.profiles)){
      const source=await glbHeader(path.join(site,profile.source)),fixed=await glbHeader(path.join(site,profile.fixed));
      const keep=source.nodes.filter(n=>!n.extras?.furnishing&&!n.extras?.lived_in);
      const fixedByName=new Map(fixed.nodes.map(n=>[n.name,n]));
      assert.equal(fixed.nodes.length,keep.length,'fixed node count');assert.equal(fixedByName.size,keep.length,'fixed names');
      for(const a of keep){
        const b=fixedByName.get(a.name);assert.ok(b,'Missing fixed node '+a.name);
        // Both are parsed JSON objects. A JSON round trip canonicalises -0
        // to 0 without relaxing any other numerical value, field or array.
        assert.deepEqual(JSON.parse(JSON.stringify(b.extras??{})),JSON.parse(JSON.stringify(a.extras??{})),'Fixed extras changed: '+a.name);
      }
    }
    for(const info of Object.values(variants.variants))for(const uri of new Set([info.url,info.questUrl])){
      const file=path.resolve(site,uri);assert.ok(file.startsWith(path.join(site,'furnish/models/') ));
      const model=JSON.parse(await asset(file));
      for(const dep of [...model.buffers||[], ...model.images||[]]){
        const linked=path.resolve(path.dirname(file),dep.uri);assert.ok(linked.startsWith(path.join(site,'furnish/') ));
        await asset(linked);
      }
    }
    for(const row of rows)assert.ok(variants.variants[row.variant],'No variant for '+row.id);
    await checkSeatTriangles(site,rows,variants.variants,report.seating);
    console.log(v.id,rows.length,'measured placements, fixed metadata and content-addressed dependencies verified');
  }
  console.log(files.size,'unique item model, texture and geometry resources verified');
}
async function main(){
  if(!process.argv[2])throw Error('Usage: node tools/house/runtime_assets.mjs <private candidate site> [version ...]');
  if(process.argv[2]==='--check'){await audit(path.resolve(process.argv[3]));return;}
  const site=path.resolve(process.argv[2]),manifest=await json(path.join(site,'versions.json')),spec=await json(path.join(site,'spec/spec_v1.json'));
  const wanted=process.argv.slice(3);
  for(let i=0;i<manifest.versions.length;i++){
    const v=manifest.versions[i];if(wanted.length&&!wanted.includes(v.id))continue;
    manifest.versions[i]=await versionData(site,v,spec)||v;
  }
  await atomic(path.join(site,'versions.json'),pretty(manifest));
}
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href)await main();
export {shape,product,assignHosts,partTable,fixed,seatedSeed,checkSeatTriangles,versionData,io,require as studioRequire,ROOT,sha,atomic,immutable};
