import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createRequire,registerHooks} from 'node:module';
import * as T from '../../assets/vendor/three/build/three.module.js';
import {shape,product,fixed,assignHosts,partTable,seatedSeed,checkSeatTriangles} from '../house/runtime_assets.mjs';
const toolkit=process.env.GLTF_TOOLS||path.join(os.homedir(),'Documents/ChatGPT/.tools/gltf');
const req=createRequire(path.join(toolkit,'package.json'));
const {Document,NodeIO}=req('@gltf-transform/core');
const {ALL_EXTENSIONS}=req('@gltf-transform/extensions');
const io=new NodeIO().registerExtensions(ALL_EXTENSIONS);
const root=new URL('../../assets/vendor/three/',import.meta.url);
const res=registerHooks({resolve(k,ctx,next){
  if(k==='three')return {url:new URL('build/three.module.js',root).href,shortCircuit:true};
  if(k.startsWith('three/addons/'))return {url:new URL('examples/jsm/'+k.slice(13),root).href,shortCircuit:true};
  return next(k,ctx);
}});
const {createFurnitureModels}=await import('../../src/furnish/models.js');res.deregister();
const box=(d,buffer,name,size,center,e={})=>{
  const geometry=new T.BoxGeometry(...size).translate(...center);
  const prim=d.createPrimitive();
  for(const [semantic,attr] of [['POSITION','position'],['NORMAL','normal']]){
    prim.setAttribute(semantic,d.createAccessor().setType('VEC3').setArray(geometry.attributes[attr].array).setBuffer(buffer));
  }
  prim.setIndices(d.createAccessor().setType('SCALAR').setArray(geometry.index.array).setBuffer(buffer));
  const mesh=d.createMesh(name).addPrimitive(prim);
  return d.createNode(name).setMesh(mesh).setExtras(e);
};
test('measured noncentral pivot preserves rotated world vertices, fixed metadata, UV-independent hashes and shared bytes',async()=>{
  const d=new Document(),scene=d.createScene(),buf=d.createBuffer();
  const q=new T.Quaternion().setFromAxisAngle(new T.Vector3(0,1,0),1.27);
  const a=box(d,buf,'chair A',[1,.8,.5],[.1,.31,-.04],{spec_id:'A',furnishing:true});
  a.setTranslation([2,-.13,3]).setRotation(q.toArray());scene.addChild(a);
  const bytes=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/9e0AAAAASUVORK5CYII=','base64');
  const image=d.createTexture('shared source').setMimeType('image/png').setImage(bytes);
  const stone=d.createMaterial('checked finish').setBaseColorTexture(image);
  a.getMesh().listPrimitives()[0].setMaterial(stone);
  const raw=box(d,buf,'fixture',[1,1,.3],[0,.5,0],{element:'fixed',stage_in:2,hinge:[1,2,3],swing_deg:95});
  scene.addChild(raw);
  const b=d.createNode('chair B').setMesh(a.getMesh()).setTranslation([-1,.41,2]).setExtras({spec_id:'B',furnishing:true});scene.addChild(b);
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),'studio-runtime-'));
  try{
    const p=await product(d,shape(a),dir),r=await product(d,shape(b),dir);
    assert.equal(p.key,r.key);assert.ok(p.maxError<1e-6);assert.equal(p.vertices,24);
    const files=await fs.readdir(path.join(dir,'furnish/textures'));
    assert.equal(files.length,1);assert.deepEqual(await fs.readFile(path.join(dir,'furnish/textures',files[0])),bytes);
    const named=await fixed(d,dir,'fixture','full',[shape(a),shape(b)]);
    const out=await io.read(path.join(dir,named)),ns=out.getRoot().listNodes();
    assert.equal(ns.length,1);assert.deepEqual(ns[0].getExtras(),raw.getExtras());assert.equal(out.getRoot().listMeshes().length,1);
  }finally{await fs.rm(dir,{recursive:true});}
});

test('support query resolves a raised object onto its actual furniture parent',()=>{
  const d=new Document(),scene=d.createScene(),buf=d.createBuffer();
  const room='R',floor=box(d,buf,'floor',[3,.1,3],[0,-.05,0],{element:'floor/R',surface_id:'floor/R',surface_role:'floor',room_id:room});
  scene.addChild(floor);
  const table=box(d,buf,'table',[1,.7,1],[0,.35,0],{spec_id:'T',kit_kind:'dining_table',room_id:room,furnishing:true});
  const bowl=box(d,buf,'bowl',[.24,.08,.24],[0,.04,0],{spec_id:'C',kit_kind:'bowl',room_id:room,furnishing:true});bowl.setTranslation([.1,.7,.2]);scene.addChild(table).addChild(bowl);
  const neighbour=box(d,buf,'lamp',[.3,.4,.3],[0,.2,0],{spec_id:'L',kit_kind:'table_lamp',room_id:room,furnishing:true});
  neighbour.setTranslation([.13,.7,.21]);scene.addChild(neighbour);
  const shapes=[table,bowl,neighbour].map(shape);
  for(const s of shapes)s.row={id:s.node.getExtras().spec_id,room,kind:s.node.getExtras().kit_kind,position:s.position.toArray(),rotation:s.rotation};
  const ctx=partTable(d,{elements:[]},15);assignHosts(shapes,ctx,[{id:room,floor_y:0}]);
  assert.deepEqual(shapes[0].row.host,{type:'floor',id:'floor/R'});
  assert.deepEqual(shapes[1].row.host,{type:'surface',id:'T'});
  assert.deepEqual(shapes[2].row.host,{type:'surface',id:'T'});
  assert.ok(new T.Vector3().fromArray(shapes[1].row.hostOffset).distanceTo(new T.Vector3(.1,.7,.2))<1e-6);
});

test('stock variants and legacy standard records share one adapted model without changing a rod finish',async()=>{
  const scene=new T.Scene(),standing=new T.Group(),geometry=new T.BoxGeometry(.1,.1,.1);
  const fabric=new T.MeshStandardMaterial({name:'spec_FAB-CURTAIN.Studio.scandinavian.linen'});
  const rod=new T.MeshStandardMaterial({name:'BRI.MAT.bronze'});
  const textile=new T.Mesh(geometry,fabric);textile.position.z=.3;standing.add(textile,new T.Mesh(geometry,rod));
  let count=0;
  const m=createFurnitureModels({THREE:T,scene,site:'test',version:'v',catalogue:[{id:'modern.curtain',model:'demo.gltf'}],
    loader:{async loadAsync(){count++;return {scene:standing};}}});
  const a={id:'modern.blind.1',variant:'modern.curtain',catalogueId:'modern.curtain',position:[0,0,0],rotation:0,
    finishes:{fabric:'#2E3A55'},sourceFinishes:{fabric:'FAB-CURTAIN'}};
  await m.set([a,{...a,id:'old-record',variant:'standard',position:[1,0,0]}]);
  assert.equal(count,1);assert.equal(m.group.children.length,2);
  const [ cloth, rail ]=m.group.children;assert.ok(cloth.instanceColor);assert.equal(rail.instanceColor,null);
  const mat=new T.Matrix4();cloth.getMatrixAt(0,mat);assert.ok(Math.abs(mat.elements[14]+.3)<1e-6);
  m.dispose();
});

test('desk lamp originally penetrating the top by 35.5 mm retains its measured pose and seats on the exported triangle',async()=>{
  const d=new Document(),scene=d.createScene(),buf=d.createBuffer(),room='R';
  scene.addChild(box(d,buf,'floor',[3,.1,3],[0,-.05,0],{surface_id:'floor/R',surface_role:'floor',room_id:room}));
  const desk=box(d,buf,'desk',[1,.75,1],[0,.375,0],{spec_id:'desk',kit_kind:'desk',room_id:room,furnishing:true});
  const lamp=box(d,buf,'lamp',[.2,.3,.2],[0,.15,0],{spec_id:'lamp',kit_kind:'table_lamp',room_id:room,furnishing:true});
  lamp.setTranslation([.2,.7145,0]);scene.addChild(desk).addChild(lamp);
  const rows=[desk,lamp].map(shape);
  for(const s of rows)s.row={id:s.node.getExtras().spec_id,kind:s.node.getExtras().kit_kind,room,position:s.position.toArray(),rotation:s.rotation};
  const ctx=partTable(d,{elements:[]},1);assignHosts(rows,ctx,[{id:room,floor_y:0}]);
  const raw=rows.map(r=>r.row),dir=await fs.mkdtemp(path.join(os.tmpdir(),'studio-seat-'));
  try {
    const p=await product(d,rows[0],dir);raw[0].variant=p.key;
    const revised=seatedSeed(raw);
    assert.equal(revised.seating.length,1);assert.ok(Math.abs(revised.items[1].position[1]-.75)<1e-6);
    assert.ok(Math.abs(revised.items[1].seatDeltaY-.0355)<1e-6);assert.deepEqual(revised.items[1].originalPosition,raw[1].position);
    assert.ok(Math.abs(raw[1].position[1]-.7145)<1e-6);
    await checkSeatTriangles(dir,raw,{[p.key]:{url:p.url}},revised.seating);
  } finally {await fs.rm(dir,{recursive:true});}
});

test('shared loader instances products at unit scale, picks stable IDs, and ignores a late load after disposal',async()=>{
  const scene=new T.Scene(), geometry=new T.BoxGeometry(1,1,1).translate(0,.5,0),material=new T.MeshStandardMaterial();
  const model=new T.Group();model.add(new T.Mesh(geometry,material));
  let loads=0,done;
  const loader={loadAsync(){loads++;return new Promise(r=>{done=()=>r({scene:model});});}};
  const records={variants:{'site-ref':{url:'furnish/models/ref.gltf'}}};
  const m=createFurnitureModels({THREE:T,scene,site:'fixture',version:'first',variants:records,loader});
  const a={id:'a',variant:'site-ref',room:'r',position:[0,0,0],rotation:0,stageIn:3,seq:1};
  const b={...a,id:'b',position:[3,0,0]};
  await m.set([a,b],{stage:1});assert.equal(loads,0);
  const ready=m.set([a,b],{stage:3});done();await ready;assert.equal(loads,1);
  const batch=m.group.children[0];assert.equal(batch.count,2);
  const ray=new T.Ray(new T.Vector3(3,2,0),new T.Vector3(0,-1,0));
  assert.equal(m.pick(ray).id,'b');assert.equal(m.pick(ray).point.y,1);
  await m.set([a,b],{visible:false});assert.equal(m.pick(ray),null);
  await m.set([a,b],{room:'other'});assert.equal(m.pick(ray),null);
  m.dispose();assert.equal(scene.children.length,0);
  const late=createFurnitureModels({THREE:T,scene,site:'fixture',version:'second',variants:records,loader});
  const wait=late.set([a]);late.dispose();done();await wait;assert.equal(scene.children.length,0);
});
