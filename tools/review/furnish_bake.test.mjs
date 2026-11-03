import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import * as T from '../../assets/vendor/three/build/three.module.js';
import {io,studioRequire} from '../house/runtime_assets.mjs';
import {bakeVersion,effective} from '../house/bake_layout.mjs';

const {Document}=studioRequire('@gltf-transform/core');
const put=async(p,o)=>{await fs.mkdir(path.dirname(p),{recursive:true});await fs.writeFile(p,JSON.stringify(o));};
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,a+' != '+b);
function make(d,name,dimensions,mat){
  const geometry=new T.BoxGeometry(...dimensions),buffer=d.getRoot().listBuffers()[0]||d.createBuffer();
  const p=d.createPrimitive();
  for(const [semantic,attribute,type] of [['POSITION','position','VEC3'],['NORMAL','normal','VEC3'],['TEXCOORD_0','uv','VEC2']]){
    p.setAttribute(semantic,d.createAccessor().setArray(geometry.attributes[attribute].array).setType(type).setBuffer(buffer));
  }
  p.setIndices(d.createAccessor().setArray(geometry.index.array).setType('SCALAR').setBuffer(buffer));
  return d.createMesh(name).addPrimitive(p.setMaterial(mat));
}
function item(id,variant,xyz,host,rotation=0){
  return {id,kind:'desk',style:'modern',catalogueId:variant.startsWith('site-')?'modern.desk':variant,
    variant,position:xyz,rotation,room:'A',size:[1,1,1],host};
}
test('bake reproduces a saved parent, child and stock instances, isolates finishes, and leaves the layout unchanged',async()=>{
  const site=await fs.mkdtemp(path.join(os.tmpdir(),'studio-bake-')),version='fixture',root=path.join(site,'furnish',version),spec=path.join(site,'spec'),stockRoot=path.join(site,'kit');
  const def={id:version,glb:'fixed.glb',furnish_runtime:{seed:'furnish/fixture/seed.json',variants:'furnish/fixture/variants.json'}};
  try{
    await fs.mkdir(root,{recursive:true});await fs.mkdir(stockRoot);
    const d=new Document(),scene=d.createScene(),paint=d.createMaterial('Signed plaster').setBaseColorFactor([.77,.73,.73,1]),
      stone=d.createMaterial('Signed floor'),wall=make(d,'wall',[2,2,.1],paint),floor=make(d,'floor',[2,.1,2],stone);
    for(const [room,x] of [['A',0],['B',4]]){
      scene.addChild(d.createNode('wall-'+room).setMesh(wall).setTranslation([x,1,0]).setExtras({surface_role:'wall',surface_id:room+'/W/1',room_id:room,stage_in:1}));
      scene.addChild(d.createNode('floor-'+room).setMesh(floor).setTranslation([x,-.05,1]).setExtras({surface_role:'floor',surface_id:'floor/'+room,room_id:room,stage_in:1}));
    }
    await io.write(path.join(site,def.glb),d);
    const measured=new Document(),mScene=measured.createScene(),wood=measured.createMaterial('Oak desktop');
    mScene.addChild(measured.createNode('Measured product').setMesh(make(measured,'mesh',[1,1,1],wood)).setTranslation([0,.5,0]));
    await io.write(path.join(root,'measured.glb'),measured);
    const stock=new Document(),sScene=stock.createScene(),cloth=stock.createMaterial('spec_FAB-CURTAIN.Studio.linen');
    sScene.addChild(stock.createNode('Native front').setMesh(make(stock,'stock',[.2,.2,.2],cloth)).setTranslation([0,.1,.3]));
    await io.write(path.join(stockRoot,'stock.glb'),stock);
    const catalogue={items:[{id:'modern.stool',model:'stock.glb',size_m:[1,1,1]}]},registry={schema:1,variants:{'site-desk':{url:'furnish/fixture/measured.glb',size:[1,1,1]}},hosts:{}};
    await put(path.join(site,def.furnish_runtime.variants),registry);
    const floorHost={type:'floor',id:'floor/A'},parent=item('DESK','site-desk',[0,0,0],floorHost),
      book=item('BOOK','site-desk',[.3,1,0],{type:'surface',id:'DESK'}),
      old=item('OLD','site-desk',[1.5,0,0],floorHost);
    const seed={schema:1,items:[parent,book,old],wallColours:{},roomFloors:{}};
    await put(path.join(site,def.furnish_runtime.seed),seed);
    await put(path.join(spec,'catalogue_v1.json'),{floors:[{id:'check-tile',hex:'#C5AC87',pattern:'tiles',unit_mm:[600,400]}]});
    const moved={...parent,position:[4,0,3],rotation:90},carried={...book,position:[4,1,2.7],rotation:90,hostOffset:[.3,1,0],hostRotation:0};
    const a=item('STOCK-A','modern.stool',[1.8,0,2],floorHost),b=item('STOCK-B','modern.stool',[-.2,0,2],floorHost);
    a.finishes=b.finishes={fabric:'#2E3A55'};a.sourceFinishes=b.sourceFinishes={fabric:'FAB-CURTAIN'};
    const record={schema:1,site:'fixture',version,revision:3,furnishSeeded:true,items:[moved,carried,a,b],
      wallColours:{'A/W/1':'#28513B'},roomFloors:{A:'check-tile'},garden:{schema:1,objects:[{id:'individual-oak'}]}};
    const layout=path.join(site,'layout/fixture.json');await put(layout,record);
    const raw=await fs.readFile(layout),time=(await fs.stat(layout)).mtimeMs,opts={catalogue,kitRoot:stockRoot};
    const first=await bakeVersion(site,def,spec,opts),repeat=await bakeVersion(site,def,spec,opts);
    assert.equal(first.modelSHA256,repeat.modelSHA256);assert.deepEqual(await fs.readFile(layout),raw);assert.equal((await fs.stat(layout)).mtimeMs,time);
    assert.equal(first.layoutRevision,3);assert.equal(first.garden.count,1);assert.deepEqual(first.items,['BOOK','DESK','STOCK-A','STOCK-B']);
    const result=await io.read(path.join(site,first.model)),nodes=new Map(result.getRoot().listNodes().map(n=>[n.getName(),n]));
    const bookNode=nodes.get('Layout/BOOK');assert.equal(bookNode.getParentNode(),nodes.get('Layout/DESK'));
    bookNode.getWorldTranslation().forEach((v,i)=>close(v,carried.position[i]));assert.ok(!nodes.has('Layout/OLD'));
    assert.deepEqual(bookNode.getExtras().host_offset_m,carried.hostOffset);
    const stockMesh=id=>nodes.get('Layout/'+id).listChildren()[0].listChildren()[0];
    assert.equal(stockMesh('STOCK-A').getMesh(),stockMesh('STOCK-B').getMesh());close(stockMesh('STOCK-A').getWorldTranslation()[2],1.7);
    const fabric=stockMesh('STOCK-A').getMesh().listPrimitives()[0].getMaterial();
    assert.deepEqual(fabric.getBaseColorFactor().slice(0,3),new T.Color('#2E3A55').toArray());
    const material=name=>nodes.get(name).getMesh().listPrimitives()[0].getMaterial();
    assert.deepEqual(material('wall-A').getBaseColorFactor().slice(0,3),new T.Color('#28513B').toArray());
    assert.equal(material('wall-B').getName(),'Signed plaster');
    assert.equal(material('floor-B').getName(),'Signed floor');
    assert.ok(material('floor-A').getBaseColorTexture().getImage().length>50);
    const pos=nodes.get('floor-A').getMesh().listPrimitives()[0].getAttribute('POSITION').getElement(0,[]);
    const uv=nodes.get('floor-A').getMesh().listPrimitives()[0].getAttribute('TEXCOORD_0').getElement(0,[]);
    close(uv[0],pos[0]/1.2);close(uv[1],1-(1+pos[2])/.8);
    assert.equal((await io.read(path.join(site,def.glb))).getRoot().listNodes().length,4);
    assert.deepEqual(first.hosts.BOOK,{type:'surface',id:'DESK',offset:[.3,1,0],rotation:0});
  }finally{await fs.rm(site,{recursive:true});}
});
test('garden-only layout gets the seed, while saving an intentionally empty room stays empty',()=>{
  const seed={items:[{id:'kept'}],wallColours:{a:'#123456'},roomFloors:{}};
  const old={schema:1,version:'v',revision:4,items:[],wallColours:{b:'#FFFFFF'},roomFloors:{},garden:{objects:[{id:'bed'}]}};
  assert.deepEqual(effective(null,seed,'v').items,seed.items);
  const garden=effective(Buffer.from(JSON.stringify(old)),seed,'v');
  assert.deepEqual(garden.items,seed.items);assert.deepEqual(garden.wallColours,{...seed.wallColours,...old.wallColours});assert.equal(garden.garden.objects[0].id,'bed');
  assert.deepEqual(effective(Buffer.from(JSON.stringify({...old,furnishSeeded:true})),seed,'v').items,[]);
});

test('generator handoff splits and bakes the completed version, preserves its sibling, and never creates a user save',async()=>{
  const site=await fs.mkdtemp(path.join(os.tmpdir(),'studio-build-')),k='v';
  try{
    const def={id:k,glb:'v.glb',glb_quest:'v_quest.glb',elements:'v_elements.json',stages:'v.json'};
    const sibling={id:'old',glb:'old.glb',glb_quest:'old_quest.glb'};
    const pending=path.join(site,'.runtime-source-fixture.json');
    await put(pending,{versions:[def,sibling]});
    await put(path.join(site,'versions.json'),{versions:[{id:'prior'}]});
    await put(path.join(site,'spec/spec_v1.json'),{versions:{before:{elements:k,rooms:[{id:'A',floor_y:0}],items:[]}}});
    await put(path.join(site,'v_elements.json'),{elements:[]});await put(path.join(site,'v.json'),{stages:[{}]});
    const d=new Document(),scene=d.createScene(),wood=d.createMaterial('oak'),g=make(d,'solid',[1,.5,.5],wood);
    scene.addChild(d.createNode('floor').setMesh(g).setTranslation([0,-.25,0])
      .setExtras({element:'floor',room_id:'A',surface_role:'floor',surface_id:'floor/A',stage_in:1}));
    scene.addChild(d.createNode('SPEC-test-table').setMesh(g).setTranslation([0,.25,0])
      .setExtras({element:'SPEC-test-table',spec_id:'test-table',room_id:'A',kit_kind:'side_table',furnishing:true,stage_in:1,storey:'ground'}));
    await io.write(path.join(site,def.glb),d);await io.write(path.join(site,def.glb_quest),d);
    const cli=fileURLToPath(new URL('../house/bake_layout.mjs',import.meta.url));
    execFileSync(process.execPath,[cli,site,'--split','--source-manifest',pending,k],{stdio:'pipe'});
    const manifest=JSON.parse(await fs.readFile(path.join(site,'versions.json')));
    assert.deepEqual(manifest.versions[1],sibling);
    assert.equal(manifest.versions[0].glb,'furnish/v/fixed.glb');assert.equal(manifest.versions[0].glb_quest,'furnish/v/fixed_quest.glb');
    const receipt=JSON.parse(await fs.readFile(path.join(site,'furnish/v/bakes/latest.json')));
    assert.equal(receipt.source,'seed');assert.deepEqual(receipt.items,['test-table']);
    const fixed=await io.read(path.join(site,manifest.versions[0].glb));assert.deepEqual(fixed.getRoot().listNodes().map(n=>n.getName()),['floor']);
    await assert.rejects(fs.stat(pending),{code:'ENOENT'});await assert.rejects(fs.stat(path.join(site,'layout/v.json')),{code:'ENOENT'});
  }finally{await fs.rm(site,{recursive:true});}
});
