import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {buildRoomContext,loadRoomContext,checkPlacement,checkGroup,snapPlacement,moveGroup,validateFurnishDelta} from '../../src/furnish/placement.mjs';
import {FurnitureLayout} from '../../src/furnish/layout.mjs';

const root=new URL('../../',import.meta.url);
const json=p=>JSON.parse(fs.readFileSync(new URL(p,root)));
const room={id:'room',label:'Room',storey:'ground',polygon:[[0,0],[6,0],[6,6],[0,6]],floorY:0,ceilingY:2.5,portals:[],wallFaces:[]};
room.wallFaces=[{id:'room/front/1',type:'wall',room:room.id,wall:'front',a:[0,0],b:[6,0],normal:[0,1],bottom:0,top:2.5,edgeIndex:0},
  {id:'room/side/1',type:'wall',room:room.id,wall:'side',a:[0,0],b:[0,6],normal:[1,0],bottom:0,top:2.5,edgeIndex:3}];
const ctx={rooms:[room],walls:[],openings:[],obstacles:[],hosts:[],seedItems:[],variants:{},catalogue:[],floorKeys:['FLR-OAK']};
const item=(id,position,size=[.7,.6,.7],extra={})=>({id,position,size,room:room.id,kind:'side_table',style:'modern',
  variant:'modern.side_table',catalogueId:'modern.side_table',host:{type:'floor',id:'floor/room'},rotation:0,...extra});
const reasons=(r,p)=>{assert.equal(r.ok,false);assert.match(r.reasons.join(', '),p);};

test('the same signed rooms, real front wall side and swept folding doors load for both issued builds',()=>{
  const spec=json('assets/sites/house/spec/spec_v1.json'),doors=json('assets/planner/house/doors.json');
  for (const version of ['as_built_now','approved_2b']) {
    const c=buildRoomContext({site:'house-wip',version,spec,doors,elements:json('assets/sites/house/'+version+'_elements.json')});
    const r=c.rooms.find(r=>r.id==='R-g-living'),face=r.wallFaces.find(f=>f.id==='R-g-living/AB-G-front/-1');
    assert.ok(face);assert.deepEqual(face.normal,[0,-1]);assert.equal(face.a[1],-.3);assert.ok(r.portals.length);
    if (version==='as_built_now') {
      const conservatory=c.rooms.find(r=>r.id.includes('conservatory'));
      assert.equal(conservatory.wallFaces.length,0,'retained exposed construction and glazing have no paint target');
    }
    if (version==='approved_2b') {
      const fold=c.openings.find(o=>o.fixture==='F-G-extRear-bi-fold-doors');
      assert.ok(fold.zones.length>20);
      assert.ok(c.rooms.find(r=>r.id.includes('bedroom-1')).floorY>2.6);
    }
  }
});

test('full rotated footprint detects a concave notch even when all corners fit',()=>{
  const notched={...room,polygon:[[0,0],[6,0],[6,6],[3.04,6],[3.04,3],[2.96,3],[2.96,6],[0,6]]};
  reasons(checkPlacement({...ctx,rooms:[notched]},[],item('wide',[3,0,4],[2,1,.5])) ,/boundary/);
  assert.ok(checkPlacement(ctx,[],item('chair',[3,0,3],[.7,.6,.7],{rotation:37})).ok);
});
test('snap uses both corner normals, finite wall spans and signed front; free still seats the host',()=>{
  const corner=item('cabinet',[.38,.4,.32],[.7,.6,.7]);
  assert.deepEqual(snapPlacement(ctx,[],corner).position,[.35,0,.3]);
  assert.deepEqual(snapPlacement(ctx,[],corner,{free:true}).position,[.38,0,.32]);
  const wall=item('art',[2,1,.18],[.8,.06,.7],{kind:'art',host:{type:'wall',id:'room/front/1'}});
  const snapped=snapPlacement(ctx,[],wall);assert.deepEqual(snapped.position,[2,1,.03]);
  assert.equal(Math.abs(snapped.rotation),180);assert.ok(checkPlacement(ctx,[],snapped).ok);
  reasons(checkPlacement(ctx,[],{...snapped,rotation:0}),/front/);
  reasons(checkPlacement(ctx,[],{...snapped,position:[.1,1,.03]}),/span|boundary/);
});
test('adjacent furniture snaps flush; rug may sit under furniture; solids and the door sector block',()=>{
  const table=item('table',[2,0,2],[1,1,.75]);
  const chair=item('chair',[3.08,0,2],[1,.7,.8]);
  assert.equal(snapPlacement(ctx,[table],chair).position[0],3);
  reasons(checkPlacement(ctx,[table],{...chair,position:[2.6,0,2]}),/Overlaps/);
  const rug=item('rug',[2,0,2],[2,2,.015],{kind:'rug'});assert.ok(checkPlacement(ctx,[table],rug).ok);
  reasons(checkPlacement({...ctx,openings:[{storey:'ground',label:'hall door',sill:0,head:2.05,
    zones:[[[1,1],[3,1],[2,3]]]}]},[],table),/hall door/);
});
test('a fixed obstruction and the walking-body clearance block impossible placements',()=>{
  const obstacle={id:'stack',label:'chimney breast',y0:0,y1:2.5,poly:[[1,1],[2,1],[2,2],[1,2]]};
  reasons(checkPlacement({...ctx,obstacles:[obstacle]},[],item('cabinet',[1.4,0,1.4])),/chimney/);
  const corridor={...room,polygon:[[0,0],[2.5,0],[2.5,6],[0,6]],
    portals:[{id:'front',point:[1.25,.4]},{id:'rear',point:[1.25,5.6]}]};
  reasons(checkPlacement({...ctx,rooms:[corridor]},[],item('cabinet',[1.25,0,3],[2.2,.5,.8])),/walking route/);
});
test('a single entrance retains an actual approach to the occupied bed beyond a proposed dresser',()=>{
  const bedroom={...room,polygon:[[0,0],[2.5,0],[2.5,6],[0,6]],portals:[{id:'entry',point:[1.25,.4]}]};
  const c={...ctx,rooms:[bedroom]}, bed=item('sleep',[1.25,0,5],[1.1,1.5,.75],{kind:'bed'});
  const blocked=item('cabinet',[1.25,0,2.9],[2.2,.6,.75],{kind:'dresser'});
  reasons(checkPlacement(c,[bed],blocked),/walking route/);
  assert.ok(checkPlacement(c,[bed],{...blocked,size:[1.15,.6,.75],position:[.60,0,2.9]}).ok);
});

test('rotating a support carries each descendant once, and deleting it is a single undo operation',async()=>{
  const table=item('table',[2,0,2],[1.6,1.2,.75]);
  const bowl=item('bowl',[2.3,.75,2],[.4,.4,.18],{host:{type:'surface',id:'table'}});
  const fruit=item('fruit',[2.3,.93,2],[.1,.1,.1],{host:{type:'surface',id:'bowl'}});
  const list=[table,bowl,fruit],turn={...table,position:[3,0,3],rotation:90};
  assert.deepEqual(moveGroup(list,table).map(it=>it.id),['table','bowl','fruit']);
  const group=moveGroup(list,turn);assert.equal(group.length,3);
  assert.ok(Math.abs(group[2].position[2]-2.7)<1e-8);
  assert.ok(checkGroup(ctx,list,turn).ok);
  reasons(checkPlacement(ctx,list,{...bowl,position:[4,.75,2]}),/support/);
  const layout=new FurnitureLayout({site:'house',version:'before',storage:null,fetcher:async()=>response(list)});
  await layout.load();layout.put(turn);assert.equal(layout.get('bowl').rotation,90);
  layout.remove('table');assert.equal(layout.items.length,0);layout.undo();assert.equal(layout.items.length,3);
  layout.undo();assert.deepEqual(layout.items,list);assert.equal(layout.dirty,false);
  layout.redo();assert.equal(layout.get('fruit').rotation,90);
});
test('the save gate rejects even a 10 mm parent-only shift and accepts a measured carried child',()=>{
  const table=item('table',[2,0,2],[1,1,.75]);
  const lamp=item('lamp',[2.3,.75,2],[.2,.2,.25],{kind:'table_lamp',catalogueId:'modern.table_lamp',variant:'modern.table_lamp',
    host:{type:'surface',id:'table'},hostOffset:[.3,.75,0],hostRotation:0,hostContact:[2.3,.75,2]});
  const catalogue=[{id:table.catalogueId,kind:table.kind,style:table.style,variant:'standard',size_m:table.size,host:'floor'},
    {id:lamp.catalogueId,kind:lamp.kind,style:lamp.style,variant:'standard',size_m:lamp.size,host:'surface'}];
  const c={...ctx,catalogue,seedItems:[table,lamp]}, before={items:[table,lamp],wallColours:{},roomFloors:{}};
  const shift={...table,position:[2.01,0,2]};
  assert.throws(()=>validateFurnishDelta(c,before,{...before,items:[shift,lamp]}),/carry/);
  const carried=moveGroup(before.items,shift);
  assert.deepEqual(carried[1].hostOffset,lamp.hostOffset);
  assert.ok(Math.abs(carried[1].hostContact[0]-2.31)<1e-7);
  assert.deepEqual(validateFurnishDelta(c,before,{...before,items:carried}),{ok:true,reasons:[]});
  assert.throws(()=>validateFurnishDelta(c,before,{...before,items:[carried[0],{...carried[1],hostOffset:[.24,.75,0]}]}),/attachment/);
  assert.throws(()=>validateFurnishDelta(c,before,{...before,items:[lamp]}),/removed/);
});
test('a signed pre-existing exception can be left alone but cannot be moved outside its measured room',()=>{
  const signed=item('signed',[-.25,0,2]), valid=item('valid',[3,0,3]);
  assert.ok(checkPlacement({...ctx,seedItems:[signed]},[signed],valid).ok);
  reasons(checkPlacement({...ctx,seedItems:[signed]},[signed],{...signed,position:[-.4,0,2]}),/boundary/);
});
const response=(items,revision=0,extra={})=>({ok:true,status:200,json:async()=>({schema:1,site:'house',version:'before',
  items,revision,wallColours:{},roomFloors:{},...extra})});
test('dirty drafts keep the original revision on stale saves; saving during a change retains the newer edit',async()=>{
  const data=new Map(),storage={getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};
  let revision=2, sent, release, waiting;
  const request=async (_url,o)=>{
    if (o.method==='GET') return response([],revision);
    sent=JSON.parse(o.body);
    if (sent.baseRevision!==revision) return {ok:false,status:409,json:async()=>({error:'stale',currentRevision:revision})};
    if (waiting) await new Promise(resolve=>{release=resolve;});
    return response(sent.items,++revision,{wallColours:sent.wallColours,roomFloors:sent.roomFloors});
  };
  const options={site:'house',version:'before',storage,fetcher:request};
  const a=new FurnitureLayout(options);await a.load();a.put(item('one',[2,0,2]));revision++;
  await assert.rejects(a.save(),e=>e.status===409);assert.ok(a.dirty&&a.conflict);
  const b=new FurnitureLayout(options);await b.load();assert.ok(b.dirty&&b.conflict);assert.equal(b.revision,2);
  await b.load({discardDraft:true});b.put(item('other',[3,0,3]));waiting=true;
  const write=b.save();b.setWalls(['room/front/1','room/side/1'],'#112233');release();await write;
  assert.ok(b.dirty);assert.equal(sent.section,'furnish');b.undo();assert.equal(b.dirty,false);
});

test('clean refresh keeps an unchanged history and cannot overwrite an edit while its GET is in flight',async()=>{
  let rev=1,remote=[],waiting,release;
  const fetcher=async(_url,o)=>{
    if(o.method==='POST'){const q=JSON.parse(o.body);remote=q.items;return response(remote,++rev);}
    if(waiting) await new Promise(resolve=>{release=resolve;});
    return response(remote,rev);
  };
  const layout=new FurnitureLayout({site:'house',version:'before',fetcher,storage:null});
  await layout.load();layout.put(item('a',[2,0,2]));await layout.save();
  assert.equal(await layout.refresh(),false);assert.equal(layout.canUndo,true);
  remote=[...remote,item('b',[4,0,4])];rev++;waiting=true;
  const check=layout.refresh();layout.setFloor('room','FLR-OAK');release();assert.equal(await check,false);
  assert.equal(layout.items.length,1);layout.undo();waiting=false;assert.equal(await layout.refresh(),true);
  assert.equal(layout.items.length,2);assert.equal(layout.canUndo,false);
});

test('unpublished optional spec aliases can be denied by LAN policy and use the signed house fallback',async()=>{
  const calls=[];
  const fetcher=async url=>{
    calls.push(url); const fake='/assets/sites/house-wip/';
    if(url.startsWith(fake+'spec/')||url.startsWith('/assets/planner/house-wip/'))return {ok:false,status:403};
    if(url.startsWith(fake+'furnish/'))return {ok:false,status:404};
    if(url.includes('house-wip/approved_2b_elements.json'))url='/assets/sites/house/approved_2b_elements.json';
    const data=json(url.slice(1));return {ok:true,status:200,json:async()=>data};
  };
  const result=await loadRoomContext({site:'house-wip',version:'approved_2b',fetcher});
  assert.ok(calls.includes('/assets/sites/house/spec/catalogue_v1.json'));
  assert.ok(calls.includes('/assets/planner/house/doors.json'));
  assert.ok(result.rooms.length>12&&result.openings.length>20);
  await assert.rejects(loadRoomContext({site:'house-wip',version:'approved_2b',fetcher:async url=>
    url.includes('/house/spec/')?{ok:false,status:403}:fetcher(url)}),/403/);
});

test('the issued sofa and coffee table keep every accessory and restore the reviewed poses on undo',async()=>{
  for (const version of ['as_built_now','approved_2b']) {
    const path='assets/sites/house/',seed=json(path+'furnish/'+version+'/seed.json'),ctx=buildRoomContext({
      site:'house',version,spec:json(path+'spec/spec_v1.json'),elements:json(path+version+'_elements.json'),
      doors:json('assets/planner/house/doors.json'),variants:json(path+'furnish/'+version+'/variants.json'),seed,
      catalogue:json('tools/library/kit/catalogue.json'),floorCatalogue:json(path+'spec/catalogue_v1.json')});
    const layout=new FurnitureLayout({site:'house',version,storage:null,fetcher:async()=>response(seed.items,0,{...seed,version})});
    await layout.load();
    for(const [id,count,delta] of [['LIV-SOFA',6,-.04],['LIV-COFFEE',4,.04]]) {
      const anchor=seed.items.find(i=>i.id===id),pos=anchor.position, candidate={...anchor,position:[pos[0]+delta,pos[1],pos[2]]};
      const copied=moveGroup(seed.items,anchor), moved=moveGroup(seed.items,candidate), replacement=new Map(moved.map(it=>[it.id,it]));
      assert.equal(copied.length,count);assert.equal(moved.length,count);
      assert.ok(checkGroup(ctx,seed.items,candidate).ok);
      assert.ok(validateFurnishDelta(ctx,seed,{...seed,items:seed.items.map(it=>replacement.get(it.id)||it)}).ok);
      for (const it of moved.slice(1)) assert.deepEqual(it.hostOffset,seed.items.find(i=>i.id===it.id).hostOffset);
      layout.put(candidate);const edited={...seed,items:layout.items};
      assert.ok(layout.undo());assert.deepEqual(layout.items,seed.items);assert.equal(layout.dirty,false);
      assert.ok(validateFurnishDelta(ctx,edited,{...seed,items:layout.items}).ok);
    }
  }
});
