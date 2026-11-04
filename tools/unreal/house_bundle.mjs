// Export the furnished final stage for Unreal. Only render geometry and material
// maps enter the bundle. Keep the bake receipt and client records on this Mac.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {io,studioRequire,sha} from '../house/runtime_assets.mjs';
const {transformMesh,joinPrimitives,prune,mergeDocuments}=studioRequire('@gltf-transform/functions');
const {getBounds}=studioRequire('@gltf-transform/core');
const sharp=studioRequire('sharp');
const [site,out,permission,sourceHash]=process.argv.slice(2);
assert.equal(permission,'--include-material-textures','Photo-derived render maps require owner consent');
const json=async file=>JSON.parse(await fs.readFile(file,'utf8'));
if(sourceHash)assert.match(sourceHash,/^[a-f0-9]{64}$/);
const receipt=sourceHash?{model:'furnish/approved_2b/bakes/'+sourceHash+'.glb',modelSHA256:sourceHash,items:[]}:await json(path.join(site,'furnish/approved_2b/bakes/latest.json'));
const source=await fs.readFile(path.join(site,receipt.model));
assert.equal(sha(source),receipt.modelSHA256);
const table=await json(path.join(site,'approved_2b_elements.json'));
const replaced=new Set(table.elements.filter(e=>e.layer==='as_built').flatMap(e=>e.replaces||[]));
const doc=await io.readBinary(source), root=doc.getRoot(),scene=root.listScenes()[0];
const presentation=process.argv.includes('--presentation');
const removed=[];
if(presentation){
 for(const n of [...root.listNodes()]){
  if(!n.getMesh())continue;
  const box=getBounds(n);const alcoveLamp=n.getName()==='Product' && Math.abs(box.min[0]-.20497)<.002 && Math.abs(box.min[1]-.9005)<.002 && Math.abs(box.min[2]+4.20003)<.002;
  if(/^(Plant2_|island_tree_02_)/.test(n.getName()) || n.getExtras().spec_id==='LIV-SHELF' || alcoveLamp){
   removed.push({name:n.getName(),...getBounds(n)});n.dispose();
  }else if(n.getExtras().door_leaf && /livHall/.test(n.getName())){
   // Apply the approved open door pose before batching, about its measured hinge.
   const p=n.getExtras(),a=p.swing_deg*Math.PI/180,c=Math.cos(a),s=Math.sin(a),[x,y,z]=p.hinge;
   const rotation=[c,0,-s,0,0,1,0,0,s,0,c,0,x-c*x-s*z,0,z+s*x-c*z,1];
   const mesh=n.getMesh().clone();for(const prim of mesh.listPrimitives())mesh.removePrimitive(prim).addPrimitive(prim.clone());
   transformMesh(mesh,n.getWorldMatrix());transformMesh(mesh,rotation);n.setMesh(mesh).setTranslation([0,0,0]).setRotation([0,0,0,1]).setScale([1,1,1]);
  }
 }
 const other=await io.read('out/unreal-house/alcove/Alcove.gltf');
 const map=mergeDocuments(doc,other);
 for(const child of other.getRoot().listScenes()[0].listChildren())scene.addChild(map.get(child));
 for(const sc of root.listScenes())if(sc!==scene)sc.dispose();
}
const sourceNodes=root.listNodes(), buckets=new Map();
let itemNodes=0, primitives=0;
function visit(node,show){
  const p=node.getExtras();
  show=show && (!p.stage_out || p.stage_out<0 || p.stage_out>15) && (p.stage_in||1)<=15 && !replaced.has(p.element);
  for(const child of node.listChildren())visit(child,show);
  if(!show || !node.getMesh())return;
  const copy=doc.createMesh();
  for(const prim of node.getMesh().listPrimitives())copy.addPrimitive(prim.clone());
  transformMesh(copy,node.getWorldMatrix());
  for(const prim of copy.listPrimitives()){
    const pos=prim.getAttribute('POSITION'),lo=pos.getMin([]),hi=pos.getMax([]);
    const cell=lo.map((x,i)=>Math.floor((x+hi[i])/8)).join('_');
    const key=[cell,root.listMaterials().indexOf(prim.getMaterial()),prim.listSemantics().sort().join(',')].join('|');
    if(!buckets.has(key))buckets.set(key,[]);
    buckets.get(key).push(prim);primitives++;
  }
  itemNodes++;
}
for(const n of scene.listChildren())visit(n,true);
for(const n of sourceNodes)n.dispose();
const cells=new Map();
for(const [key,parts] of buckets){
  const cell=key.split('|')[0];
  if(!cells.has(cell)){
    const mesh=doc.createMesh('Cell_'+cells.size);cells.set(cell,mesh);
    scene.addChild(doc.createNode(mesh.getName()).setMesh(mesh));
  }
  cells.get(cell).addPrimitive(parts.length===1?parts[0]:joinPrimitives(parts));
}
const active=new Set(cells.values());
for(const mesh of root.listMeshes())if(!active.has(mesh))mesh.dispose();
await doc.transform(prune({keepLeaves:false}));
for(const ext of root.listExtensionsUsed())if(ext.extensionName==='EXT_texture_webp')ext.dispose();
// Local-only identity map for native Unreal material rebinding; outside upload bundle.
await fs.mkdir(path.dirname(out),{recursive:true});
await fs.writeFile(path.join(path.dirname(out),'material-map.json'),JSON.stringify(root.listMaterials().map((m,i)=>({id:'Finish_'+i,name:m.getName(),vertex:/VertexPlant/.test(m.getName())})),null,2));
let count=0,averaged=0;
for(const tex of root.listTextures()){
  const name=tex.getName(), bytes=tex.getImage();
  const bitmap=sharp(bytes);
  const file='Surface_'+(++count);
  tex.setImage(await bitmap.png().toBuffer()).setMimeType('image/png').setName(file).setURI(file+'.png');
}
for(const [i,m] of root.listMaterials().entries())m.setName('Finish_'+i).setExtras({});
for(const a of root.listAccessors())a.setName('').setExtras({});
for(const mesh of root.listMeshes())for(const prim of mesh.listPrimitives())prim.setExtras({});
for(const [i,b] of root.listBuffers().entries())b.setName('House'+i).setURI('House'+i+'.bin').setExtras({});
scene.setName('House').setExtras({});root.setExtras({});
await fs.mkdir(out,{recursive:true});await io.write(path.join(out,'House.gltf'),doc);
const written=await json(path.join(out,'House.gltf'));
assert(!JSON.stringify(written).includes('"extras"') || !JSON.stringify(written).includes('drawing'));
const bounds={};
for(const n of scene.listChildren()){
  const {min,max}=getBounds(n);bounds[n.getMesh().getName()]=[[min[0],-max[2],min[1]],[max[0],-min[2],max[1]]];
}
const cameras=[
  ['Lounge',[3.30,1.50,-.75],[1.2,1,-4.2],21],
  ['Kitchen',[7.65,1.50,-4.83],[2.2,1,-7.6],21],
  ['Front_left_garden',[-1.2,2.10,21.2],[4.15,1.6,.15],25]
].map(([name,eye,aim,focal_mm])=>{
  const [x,y,z]=eye,dx=aim[0]-x,dy=aim[1]-y,dz=aim[2]-z;
  return {name,pos_cm:[100*x,100*z,100*y],fwd:[dx,dz,dy],up:[0,0,1],focal_mm,sensor_w_mm:36,sensor_h_mm:20.25,w:2560,h:1440};
});
await fs.writeFile(path.join(out,'scene.json'),JSON.stringify({site:'House',cameras,bounds,check:cameras.map(c=>c.name),sun:{to_sun_ue:[-.45,.60,.66]},source:presentation?sha(Buffer.concat([source,await fs.readFile('out/unreal-house/alcove/Alcove.bin'),await fs.readFile('out/unreal-house/alcove/Alcove.gltf'),Buffer.from('presentation-v2')])):receipt.modelSHA256},null,2));
console.log(JSON.stringify({itemNodes,primitives,cells:cells.size,textures:count,colourOnly:averaged,furnishedItems:receipt.items.length}));

if(presentation)await fs.writeFile(path.join(out,'replacement-placements.json'),JSON.stringify(removed,null,2));
