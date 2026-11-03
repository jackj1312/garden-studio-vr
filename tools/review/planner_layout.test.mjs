import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {App} from '../../src/planner/app.js';
import {applyHistoricalChanges} from '../../src/planner/seed_changes.mjs';
import {catalogueMatch, plannerEntry, projectRoomState, roomTypes} from '../../src/planner/shared.mjs';
import {buildRoomContext,checkGroup} from '../../src/furnish/placement.mjs';
import {FurnitureLayout} from '../../src/furnish/layout.mjs';

const json=async path=>JSON.parse(await readFile(new URL('../../'+path,import.meta.url),'utf8'));
const spec=await json('assets/sites/house/spec/spec_v1.json'), kit=await json('tools/library/kit/catalogue.json');
const floors=await json('assets/sites/house/spec/catalogue_v1.json'), doors=await json('assets/planner/house/doors.json');
const historyDir='assets/sites/house/spec/changes/', historical=await json(historyDir+'changes.json');
const old=await Promise.all(historical.changes.filter(c=>c.at.startsWith('2026-11-01')).map(async row=>({...await json(historyDir+row.file),status:row.status})));
const context=async (version)=>buildRoomContext({site:'house-wip',version,spec,doors,catalogue:kit,floorCatalogue:floors,
  elements:await json('assets/sites/house/'+version+'_elements.json')});

test('the 33 issued November requests seed only their matching layout and preserve measured poses',async()=>{
  const testRow = id=>({id,position:[2.06,.012,-3.49],rotation:-135});
  const bids=['LIV-ARM','B3B-WARD','BD1-CURT','BD1-WARD'], before=await context('as_built_now');
  const b=applyHistoricalChanges(bids.map(testRow),old,{version:'as_built_now',rooms:before.rooms});
  assert.equal(b.appliedChangeIds.length,30);
  assert.deepEqual(b.items[0].position,[2.11,.012,-3.54]); assert.equal(b.items[0].rotation,-135);
  assert.deepEqual(b.items[2].finishes,{fabric:'#2E3A55'});
  assert.deepEqual(b.roomFloors,{'R-f-bedroom-1-front-left':'FLR-CARPET-GREY'});
  const faces=before.rooms.find(r=>r.id==='R-f-bedroom-1-front-left').wallFaces;
  assert.ok(faces.some(f=>f.edgeIndex===3)); assert.ok(faces.some(f=>f.edgeIndex===1));
  for (const face of faces) assert.equal(b.wallColours[face.id],face.edgeIndex===3?'#2C3A4A':'#9EA88E');
  assert.deepEqual(applyHistoricalChanges(b.items,[...old,...old],{...b,version:'as_built_now',rooms:before.rooms}),b);
  const after=await context('approved_2b'), chair=testRow('KA-CHAIR-4');
  const a=applyHistoricalChanges([chair],old,{version:'approved_2b',rooms:after.rooms});
  assert.equal(a.appliedChangeIds.length,3);assert.deepEqual(a.items,[chair]);
});

test('studio entries can be filtered by kind, room and all six styles with exact published thumbnails',()=>{
  const living=roomTypes({name:'kitchen, living and dining (open plan)'});
  assert.deepEqual(living,['living','dining','kitchen']);
  for(const style of kit.styles) {
    const match=kit.items.filter(e=>catalogueMatch(e,{room:living,kind:'sofa',style}));
    assert.ok(match.length && match.every(e=>e.thumbnail && e.model && e.style===style));
    const row=plannerEntry(match[0]);assert.deepEqual(row.size_mm,row.size_m.map(n=>Math.round(n*1000)));
  }
  assert.ok(kit.items.every(e=>catalogueMatch(e,{})));
  assert.ok(!catalogueMatch(kit.items.find(e=>e.kind==='bed'),{room:['bathroom']}));
});

test('historical moves transfer the assembly and contacts, and record the Before chair door correction (F208/F209)',async()=>{
  const ctx=await context('as_built_now'), room='R-g-living';
  const arm={id:'LIV-ARM',kind:'armchair',room,host:{type:'floor',id:'floor/'+room},rotation:-135.00000418125705,
    position:[1.25,0,-3.700000047683716],hostContact:[1.25,.002,-3.700000047683716],size:[.75967425108,.82000005245,.76000273]};
  // This cushion is a new measured-child fixture that the historical planner did not list under "carried".
  const soft={id:'cushion',kind:'cushion',room,host:{type:'surface',id:arm.id},rotation:arm.rotation,
    position:[1.25,.52,-3.700000047683716],hostContact:[1.25,.52,-3.700000047683716],size:[.15,.15,.1]};
  const seed=[arm,soft];ctx.seedItems=seed;
  const records=old.filter(c=>c.target.item==='LIV-ARM');
  const next=applyHistoricalChanges(seed,records,{version:'as_built_now',rooms:ctx.rooms,context:ctx});
  const [moved,child]=next.items, receipt=next.moveReceipts[0];
  assert.deepEqual(moved.position,[1.3,0,-3.666]);assert.deepEqual(receipt.delta,[0,0,.084]);
  assert.equal(receipt.sourceId,records.at(-1).id);assert.match(receipt.reason,/living -> conservatory double doors/);
  assert.ok(checkGroup(ctx,seed,moved).ok);assert.equal(moved.rotation,arm.rotation);
  for(const it of [moved,child]) {
    assert.ok(Math.abs(it.position[0]-1.3)<1e-7 && Math.abs(it.position[2]+3.666)<1e-7);
    assert.ok(Math.abs(it.hostContact[0]-1.3)<1e-7 && Math.abs(it.hostContact[2]+3.666)<1e-7);
  }
});

test('projection uses shared positions and tombstones, preserving signed fixtures and notes',()=>{
  const room='R-g-living', v='after', ids=['LIV-SOFA','LIV-ARM','FIXED'];
  const H={elements:'approved_2b',rooms:[{id:room}],baseItems:ids.map(id=>({id,room,type:id,position_m:[8,0,8],size_mm:[900,500,800]})),numbers:new Map(ids.map((id,i)=>[id,i+1]))};
  const e=plannerEntry(kit.items.find(i=>i.id==='modern.sofa')), db={versions:{after:H},catalogue:floors,entries:new Map([[e.id,e]])};
  const row={id:'LIV-SOFA',kind:e.kind,catalogueId:e.id,variant:e.id,room,position:[1,.007,2],rotation:-90,size:e.size_m,host:{type:'floor',id:'floor/'+room}};
  const changes=[{id:'old-move',version:v,status:'active',op:'item.move',target:{item:row.id},after:{position_m:[77,0,77]}},
    {id:'note',version:v,status:'active',op:'note',target:{room},at:'today',after:{text:'Keep the architrave'}}];
  const s=projectRoomState(db,v,changes,{ready:true,layout:{items:[row],wallColours:{},roomFloors:{[room]:'FLR-SLATE'}},variants:{sourceIds:ids.slice(0,2)},context:{rooms:[]}});
  assert.deepEqual([...s.items.keys()].sort(),['FIXED','LIV-SOFA']);assert.deepEqual(s.items.get(row.id).position_m,row.position);
  assert.equal(s.items.get(row.id).yaw_deg,-90);assert.equal(s.items.get(row.id).num,1);assert.equal(s.rooms.get(room).floor.id,'FLR-SLATE');
  assert.equal(s.notes.get('room:'+room)[0].text,'Keep the architrave');
});

// A 2 m square with a 1.8 m stock sofa offers no legal copy on either axis.
test('a blocked duplicate creates no layout entry and does not enter Undo (F199)',async()=>{
  const name='r', sofa=kit.items.find(e=>e.id==='modern.sofa'), size=[1.8,.8,.8];
  const row={id:'signed-sofa',kind:'sofa',style:'modern',variant:'site-fitted',catalogueId:sofa.id,
    size,position:[1,0,1],rotation:0,room:name,host:{type:'floor',id:'floor/'+name}};
  const state={site:'probe',version:'approved_2b',revision:1,items:[row],wallColours:{},roomFloors:{}};
  const layout=new FurnitureLayout({site:state.site,version:state.version,storage:null,fetcher:async()=>Response.json(state)});await layout.load();
  const app=new App(), room={id:name,polygon:[[0,0],[2,0],[2,2],[0,2]],floorY:0,ceilingY:2.5,wallFaces:[],portals:[]};
  const ctx={rooms:[room],walls:[],openings:[],obstacles:[],hosts:[],seedItems:[row],catalogue:kit.items,
    variants:{'site-fitted':{size,kind:'sofa',style:'modern',catalogueId:sofa.id}},floorKeys:[]};
  app.sessions.set('after',{ready:true,layout,context:ctx});let issue='';app.toast=msg=>{issue=msg;};
  app.copyFurniture({id:row.id,shared:row});
  assert.deepEqual(layout.items,[row]);assert.equal(layout.canUndo,false);assert.ok(issue);
});

test('planner furniture, paint and floor save together for a walkthrough client without spec writes',async()=>{
  const version='approved_2b', room='R-test',face=room+'/G-wall/1',pos=[2,.004,2];
  const sofa=kit.items.find(e=>e.id==='modern.sofa');
  const row={id:'P-example',kind:'sofa',style:'modern',variant:sofa.id,catalogueId:sofa.id,position:pos,rotation:0,size:sofa.size_m,room,host:{type:'floor',id:'floor/'+room}};
  const server={site:'probe',version,revision:0,items:[row],wallColours:{},roomFloors:{},garden:{schema:1,objects:[]}};
  const calls=[];
  const fetcher=async (url,opt)=>{
    calls.push([url,opt.method]); assert.equal(url,'/layout?site=probe&version='+version);
    if(opt.method==='POST') {
      const body=JSON.parse(opt.body); assert.equal(body.section,'furnish');
      if(body.baseRevision!==server.revision) return Response.json({error:'Changed',currentRevision:server.revision},{status:409});
      Object.assign(server,{items:body.items,wallColours:body.wallColours,roomFloors:body.roomFloors,revision:server.revision+1});
    }
    return Response.json(server);
  };
  const make=()=>new FurnitureLayout({site:'probe',version,fetcher,storage:null});
  const editor=make(), walk=make(), stale=make();
  await Promise.all([editor.load(),walk.load(),stale.load()]);
  const app=new App(), r={id:room,name:'Test room',polygon:[[0,0],[5,0],[5,5],[0,5]],floorY:0,ceilingY:2.5,wallFaces:[{id:face}],portals:[]};
  const ctx={rooms:[r],walls:[],openings:[],obstacles:[],hosts:[],seedItems:[row],catalogue:kit.items,variants:{},floorKeys:['FLR-SLATE']};
  app.state={house:{name:'After',roomById:new Map([[room,r]]),roomAt:()=>r},context:ctx,rooms:new Map(),items:new Map([[row.id,{id:row.id,room,shared:row}]])};
  app.sessions.set('after',{ready:true,layout:editor,context:ctx});
  app.afterChange=()=>{};app.renderTop=()=>{};app.toast=()=>{};
  app.setRoom(r,'floor',{id:'FLR-SLATE'});app.setRoom(r,'walls',{hex:'#678697'});
  app.commit({op:'item.finish',target:{item:row.id},after:{part:'upholstery',value:{hex:'#6A4B3A'}}});
  await app.undo();assert.equal(editor.get(row.id).finishes,undefined);await app.redo();
  assert.equal(editor.get(row.id).finishes.upholstery,'#6A4B3A');
  assert.ok(calls.every(c=>c[1]==='GET'));await app.saveLayout();await walk.refresh();
  assert.deepEqual(walk.items,editor.items);assert.deepEqual(walk.wallColours,{[face]:'#678697'});assert.deepEqual(walk.roomFloors,{[room]:'FLR-SLATE'});
  stale.setWall(face,'#C09887');await assert.rejects(stale.save(),e=>e.status===409);
  assert.ok(stale.conflict && stale.dirty);assert.equal(stale.wallColours[face],'#C09887');assert.deepEqual(server.garden,{schema:1,objects:[]});
});
