import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {registerHooks} from 'node:module';
import * as T from '../../assets/vendor/three/build/three.module.js';
import {openingPlane,exteriorAperture,openRoomGroups,rankApertures,lampPower} from '../../src/house/room-light-data.mjs';
const root=new URL('../../',import.meta.url);
const hooks=registerHooks({resolve(specifier, context, next){
  if(specifier==='three')return {url:new URL('assets/vendor/three/build/three.module.js',root).href,shortCircuit:true};
  return next(specifier,context);
}});
const {createRoomLighting}=await import('../../src/house/room-lighting.js');
hooks.deregister();
const room={id:'living',floor:0,ceiling:2.5,storey:'ground',polygon:[[0,.15],[4,.15],[4,4],[0,4]]};
const wall={id:'wall',type:'wall',params:{start:[0,0],end:[4,0]}};
const opening={id:'window',type:'opening',params:{host:'wall',offset:1,width:2,sill:.80,head:2}};
const glassFixture={id:'glazed',type:'fixture',params:{opening:opening.id}};
const plane=openingPlane(wall,opening);
function part(id,k,mi,p,materialName='glass') {
  const geometry=new T.BoxGeometry(.09,.055,.09);geometry.computeBoundingBox();
  const matrix0=new T.Matrix4().makeTranslation(...p);
  return {index:mi,group:k==='window'?'window':'fitting',element:id,name:id+'.'+mi,geometry,matrix0,materialName,
    bbox:geometry.boundingBox.clone().applyMatrix4(matrix0),ud:k==='window'?{part:'glass'}:{kit_kind:k,spec_id:id,room_id:room.id}};
}
function view(){
  const glass=part('glazed','window',0,[2,1.4,0]),light=part('ceiling','pendant',1,[3,2.15,2],'BRI.MAT.bulb');
  const rooms={type:'room',id:room.id,params:{floor:0,name:'Living',storey:'ground',polygon:room.polygon}};
  const table=new Map([rooms,wall,opening,glassFixture].map(e=>[e.id,e]));
  return {def:{id:'study'},sidecar:{stages:[{}]},doors:{moving:false},model:{asBuilt:false,stage:1,
    parts:[glass,light],masks:{visible:new Uint8Array([1,1])},table,byElement:new Map([['glazed',[glass]],['ceiling',[light]]])}};
}
const schedule={elements:'study',rooms:[{id:'living',ceiling_y:2.5}],items:[
  {id:'ceiling',category:'lighting',room:'living',asset:{kind:'pendant_drum',lamp:'2700 K 806 lm'}}]};
const options={eye:new T.Vector3(2,1.5,2),stage:1,profile:'on',inXR:false,furnished:true,items:[]};
const source=(id)=>({id,kind:'floor_lamp',room:'living',position:[id==='A'?1:3,0,2],rotation:0,size:[.4,.4,1.3],
  host:{type:'floor',id:'floor/living'},stageIn:1,lampOn:false});
test('signed absolute heads and normals classify sky on one side and exclude a glazed interior threshold',()=>{
  assert.equal(plane.area,2.4);assert.deepEqual(plane.centre,[2,1.4,0]);
  const a=exteriorAperture([room],plane,'o','f');
  assert.equal(a.room,room.id);assert.equal(a.inward[2],1);assert.equal(a.position[2],.20);
  const behind={...room,id:'porch',polygon:[[0,-4],[4,-4],[4,-.15],[0,-.15]]};
  assert.equal(exteriorAperture([room,behind],plane,'o','f'),null);
  const first={...room,id:'upper',floor:2.675,ceiling:5.08},upper=openingPlane(wall,{params:{...opening.params,sill:3.4,head:4.5}});
  assert.equal(exteriorAperture([room,first],upper,'fw','ff').room,'upper');
});
test('open-plan membership, selection hysteresis, ceiling and intensity cap',()=>{
  const g=openRoomGroups([room,{...room,id:'dining'}],[['living','dining']]).get(room.id);
  const base=exteriorAperture([room],plane,'a','f');
  const rows=[base,...[1,2,3,4].map(i=>({...base,id:'i'+i,room:'dining',centre:[i,1,0],position:[i,1,.2],area:i===4?60:1}))];
  const found=rankApertures(rows,g,[0,1,1],[],3);assert.equal(found.length,3);
  assert.equal(found.find(a=>a.id==='i4').intensity,80);assert.equal(rankApertures(rows,null,[0,1,1],[],3).length,0);
  assert.equal(lampPower('table_lamp',{lamp:'3000 K 470 lm'}).kelvin,3000);
});
test('actual scene limits standalone sources to the selected room, follows state of built panes, releases resources',()=>{
  const scene=new T.Scene(),v=view(),l=createRoomLighting({scene,desktop:true});l.setView(v,schedule);
  l.update(options);let snapshot=l.snapshot();assert.equal(snapshot.windows[0].id,'window');assert.equal(snapshot.practicals.length,0);
  const active=scene.children[0].children.filter(o=>o.visible&&o.isLight);
  assert.equal(active.length,1);assert.equal(active[0].userData.studioLight.type,'window');assert.equal(active[0].shadow.mapSize.x,512);
  v.model.masks.visible[0]=0;l.invalidate();l.update(options);assert.equal(l.snapshot().windows.length,0);
  assert.equal(l.pick('SPEC-ceiling'),'ceiling');assert.equal(l.toggle('ceiling'),true);snapshot=l.snapshot();
  assert.equal(snapshot.practicals[0].id,'ceiling');assert.equal(snapshot.emitters[0].id,'ceiling');
  const emitter=scene.children[0].children.find(o=>o.userData.studioLight?.type==='emitter');assert.equal(emitter.geometry,v.model.parts[1].geometry);
  assert.equal(l.status('living').roomOn,true);l.update({...options,eye:new T.Vector3(5,1,2)});assert.equal(l.snapshot().practicals.length,0);
  l.dispose();assert.equal(scene.children.length,0);
});
test('XR or phone has no extra draw/light when off. One enabled runtime fixture cannot change a second instance',()=>{
  for(const desktop of [true,false]){
    const scene=new T.Scene(),v=view(),l=createRoomLighting({scene,desktop}),items=[source('A'),source('B')];
    const group=new T.Group();group.userData.furnishRuntime=true;scene.add(group);
    const b=new T.InstancedMesh(new T.SphereGeometry(.023),new T.MeshStandardMaterial(),2);
    b.material.name='BRI.MAT.bulb';b.material.emissive.setHex(0xffddb0);b.material.emissiveIntensity=1.8;b.userData.furnishItems=items;
    b.setMatrixAt(0,new T.Matrix4().makeTranslation(1,1,2));b.setMatrixAt(1,new T.Matrix4().makeTranslation(3,1,2));group.add(b);
    scene.updateMatrixWorld(true);l.setView(v,schedule);const opts={...options,inXR:desktop,items};l.update(opts);
    assert.equal(l.snapshot().windows.length,0);assert.equal(l.snapshot().practicals.length,0);
    const owned=scene.children.find(g=>g.name==='Studio room light');assert.equal(owned.children.length,0);
    assert.equal(l.toggle('A'),true);let snap=l.snapshot();assert.deepEqual(snap.emitters.map(e=>e.id),['A']);
    assert.deepEqual(snap.emitters[0].position,[1,1,2]);assert.equal(b.material.emissiveIntensity,0);
    assert.equal(snap.practicals[0].shadow,false);assert.equal(l.status(room.id).roomOn,false);
    assert.equal(l.toggleRoom(room.id,true),true);assert(l.snapshot().practicals.length<=1);assert.equal(l.status(room.id).allOn,true);
    l.update({...opts,furnished:false});assert.deepEqual(l.snapshot().lamps.map(x=>x.id),['ceiling']);
    l.update({...opts,profile:'off'});assert.equal(l.snapshot().emitters.length,0);
    l.setView(null);assert.equal(b.material.emissiveIntensity,1.8);l.dispose();b.material.dispose();b.geometry.dispose();
  }
});
test('issued room polygons assign the as-built front glazing and exclude the enclosed porch threshold in both houses',()=>{
  const read=p=>JSON.parse(fs.readFileSync(new URL(p,root))),spec=read('assets/sites/house/spec/spec_v1.json');
  for(const [key,ver] of [['before','as_built_now'],['after','approved_2b']]){
    const els=read('assets/sites/house/'+ver+'_elements.json').elements,byId=new Map(els.map(e=>[e.id,e]));
    const rooms=spec.versions[key].rooms.map(r=>({...r,floor:r.floor_y,ceiling:typeof r.ceiling_y==='number'?r.ceiling_y:r.floor_y+2.65}));
    const front=byId.get('AB-F-AB-G-front-LW-ground-as-built'),op=byId.get(front.params.opening);
    const a=exteriorAperture(rooms,openingPlane(byId.get(op.params.host),op),op.id,front.id);
    assert.ok(a);assert.equal(a.room,'R-g-living');assert.ok(a.inward[2]<-.99);
    const inner=byId.get('O-G-front-hall-door-from-porch-internal-type');
    if(inner)assert.equal(exteriorAperture(rooms,openingPlane(byId.get(inner.params.host),inner),inner.id,'hall'),null);
  }
});

test('manual switches retain pending native shadow refresh and include the final settled door pose once',()=>{
  const scene=new T.Scene(),v=view(),lighting=createRoomLighting({scene,desktop:true});lighting.setView(v,schedule);
  assert.equal(lighting.update(options),true);
  assert.equal(lighting.update(options),false);
  lighting.toggle('ceiling',true);
  assert.equal(lighting.update(options),true);
  assert.equal(lighting.update(options),false);
  v.doors.moving=true;assert.equal(lighting.update(options),true);
  v.doors.moving=false;assert.equal(lighting.update(options),true);
  assert.equal(lighting.update(options),false);
  lighting.toggle('ceiling',false);assert.equal(lighting.update(options),true);assert.equal(lighting.update(options),false);
  lighting.dispose();
});

// Only the GLB scene JSON and accessor bounds are read. No mesh buffer, image,
// GPU or renderer is needed to exercise the issued element/fixture associations.
function issuedSources(version,asBuilt) {
  const base=new URL('assets/sites/house/',root),read=name=>JSON.parse(fs.readFileSync(new URL(name,base)));
  const manifest=read('versions.json'),def=manifest.versions.find(v=>v.id===version),elements=read(def.elements).elements;
  const fd=fs.openSync(new URL(def.glb,base),'r');let gltf;
  try {
    const header=Buffer.alloc(20);fs.readSync(fd,header,0,20,0);
    const json=Buffer.alloc(header.readUInt32LE(12));fs.readSync(fd,json,0,json.length,20);gltf=JSON.parse(json);
  } finally {fs.closeSync(fd);}
  const table=new Map(elements.map(e=>[e.id,e])),byElement=new Map(),parts=[],visible=[];
  const materials=gltf.materials.map(src=>{
    const m=new T.MeshStandardMaterial();m.name=src.name||'';
    m.emissive.fromArray(src.emissiveFactor||[0,0,0]);m.emissiveIntensity=src.extensions?.KHR_materials_emissive_strength?.emissiveStrength??1;
    return m;
  });
  const replaced=new Set(elements.filter(e=>e.layer==='as_built').flatMap(e=>e.replaces||[]));
  for(const node of gltf.nodes){
    const u=node.extras;if(!u||node.mesh==null||!(isGlazed(u)||u.spec_id))continue;
    const mat=new T.Matrix4();
    if(node.matrix)mat.fromArray(node.matrix);
    else mat.compose(new T.Vector3().fromArray(node.translation||[0,0,0]),new T.Quaternion().fromArray(node.rotation||[0,0,0,1]),new T.Vector3().fromArray(node.scale||[1,1,1]));
    for(const prim of gltf.meshes[node.mesh].primitives){
      const accessor=gltf.accessors[prim.attributes.POSITION],materialName=gltf.materials[prim.material]?.name||'';
      const bbox=new T.Box3(new T.Vector3().fromArray(accessor.min),new T.Vector3().fromArray(accessor.max)).applyMatrix4(mat);
      const p={index:parts.length,ud:u,element:u.element,group:u.group,name:node.name,materialName,bbox,set:{normal:materials[prim.material]}};
      parts.push(p);const element=table.get(p.element),actual=!!u.as_built||element?.layer==='as_built';
      visible.push(!u.stage_out&&(asBuilt?(actual||!replaced.has(p.element)):!actual));
      if(!byElement.has(p.element))byElement.set(p.element,[]);byElement.get(p.element).push(p);
    }
  }
  function isGlazed(u){return u.part==='glass'||u.part==='leaf_glass';}
  return {def,sidecar:read(def.stages),model:{table,parts,byElement,masks:{visible},asBuilt},
    spec:read('spec/spec_v1.json'),items:read('furnish/'+version+'/seed.json').items,materials};
}
test('released model masks select the actual housing layer, complete fixture inventory and no outdoor light',()=>{
  for(const [version,expected] of [['as_built_now',21],['approved_2b',31]])for(const asBuilt of [false,true]){
    const V=issuedSources(version,asBuilt),scene=new T.Scene(),l=createRoomLighting({scene,desktop:true});
    const bulb=V.materials.find(m=>m.name==='BRI.MAT.bulb'),original=bulb.emissiveIntensity;
    const unaffected=V.materials.filter(m=>m!==bulb).map(m=>m.emissiveIntensity);
    assert.ok(original>1.79&&original<1.81);l.setView(V,V.spec);assert.equal(bulb.emissiveIntensity,0);
    assert.deepEqual(V.materials.filter(m=>m!==bulb).map(m=>m.emissiveIntensity),unaffected);
    const opts={...options,eye:new T.Vector3(1.0,1.4,-1.1),stage:V.sidecar.stages.length,items:V.items};
    l.update(opts);const s=l.snapshot();
    assert.equal(s.room,'R-g-living');assert.equal(s.lamps.length,expected);
    if(version==='as_built_now')assert.equal(s.lamps.find(r=>r.id==='KB-HOOD').kind,'extractor_light');
    const front=s.windows.find(a=>a.inward[2]<-.99);assert(front,'Missing actual front aperture in '+version);
    assert.equal(front.fixture.startsWith('AB-'),asBuilt);
    assert.ok(front.position[2]<front.centre[2]);
    if(version==='approved_2b'){
      l.update({...opts,eye:new T.Vector3(3.5,1.4,-7.1)});
      assert(l.snapshot().windows.some(w=>w.fixture==='F-G-extRear-bi-fold-doors'),'Rear kitchen glazing missing');
    }
    l.update({...opts,eye:new T.Vector3(3.7,1.369,9.8)});assert.equal(l.snapshot().windows.length,0);
    l.dispose();assert.equal(bulb.emissiveIntensity,original);
    V.materials.forEach(m=>m.dispose());
  }
});
