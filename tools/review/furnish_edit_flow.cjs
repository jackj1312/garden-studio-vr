// Serial desktop/touch client acceptance. Only the disposable QA layout can receive a write.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const puppeteer=require(process.env.PUPPETEER_CORE || 'puppeteer-core');
const plannerClient=require('./planner_client.cjs');
const ORIGIN='https://127.0.0.1:8450', SITE='furnish-qa', VERSION='approved_2b', ROOM='R-g-living', STOCK='modern.side_table';
const output=path.resolve(__dirname,'../../renders/house-build/furnishing/furnish-system');
const layoutUrl='/layout?'+new URLSearchParams({site:SITE,version:VERSION});
const houseUrl=ORIGIN+'/house.html?'+new URLSearchParams({mode:'customer',site:SITE,version:VERSION,edit:'1'});
const plannerUrl=ORIGIN+'/plan/?'+new URLSearchParams({site:SITE,version:VERSION})+'#after/room/'+ROOM;
const sel=k=>'[data-furnish-panel] [data-fu-field="'+k+'"]', cmd=k=>'[data-furnish-panel] [data-fu="'+k+'"]';
const distance=(a,b)=>Math.hypot(a[0]-b[0],a[2]-b[2]);
const angle=(a,b)=>((a-b+540)%360)-180;

async function profile(browser,name) {
  const context=await browser.createBrowserContext(),page=await context.newPage(),touch=name==='phone';
  const result={profile:name,site:SITE,version:VERSION,errors:[]}, writes=[];
  fs.mkdirSync(output,{recursive:true});page.setDefaultTimeout(90000);page.setDefaultNavigationTimeout(180000);
  await page.setViewport({width:touch?390:1220,height:touch?844:800,deviceScaleFactor:1,hasTouch:touch,isMobile:touch});
  if(touch) await page.setUserAgent('Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 Chrome/132 Mobile Safari/537.36');
  await page.setRequestInterception(true);
  page.on('request',r=>{
    if (/^(data:|blob:|about:)/.test(r.url())) return r.continue();
    const u=new URL(r.url());
    if (u.origin!==ORIGIN) return r.abort();
    if (!['GET','HEAD','OPTIONS'].includes(r.method())) {
      if (r.method()!=='POST' || u.pathname!=='/layout' || u.searchParams.get('site')!==SITE || u.searchParams.get('version')!==VERSION) {
        result.errors.push('Unexpected write '+r.method()+' '+u.pathname);return r.abort();
      }
      writes.push(u.pathname+u.search);
    }
    return r.continue();
  });
  page.on('pageerror',e=>result.errors.push(e.message));
  const client=touch ? await page.createCDPSession() : null;
  const current=()=>page.evaluate(()=>{
    const f=__house.furnishing,s=f.state();
    return {active:s.active,bird:s.bird,room:s.room?.id,selected:s.selected,ids:s.items.map(i=>i.id),revision:s.revision,dirty:s.dirty,status:s.status,
      pending:s.pending,verdict:s.verdict,wallColours:f.layout?.wallColours,roomFloors:f.layout?.roomFloors};
  });
  const click=async selector=>{const handle=await page.waitForSelector(selector,{visible:true});await handle.scrollIntoView();await (touch?handle.tap():handle.click());};
  async function boot() {
    await page.goto(houseUrl,{waitUntil:'domcontentloaded'});
    await page.waitForFunction((site,v)=>window.__house?.V?.def.id===v && __house.furnishing?.state().site===site &&
      __house.furnishing?.layout?.loaded && __house.furnishing.enabled && !document.querySelector('#furnish-plan').hidden,{timeout:180000},SITE,VERSION);
    await page.select(sel('room'),ROOM);
    await page.waitForFunction(id=>__house.furnishing.state().room?.id===id && __house.furnishing.bird &&
      __house.furnishing.plan.point(0,0) !== null,{},ROOM);
  }
  async function screen(p) {
    return page.evaluate(p=>{
      const c=document.getElementById('furnish-plan'),b=c.getBoundingClientRect(),plan=__house.furnishing.plan;
      const lo=plan.point(b.left,b.top),hi=plan.point(b.right,b.bottom);
      const q={x:b.left+b.width*(p[0]-lo[0])/(hi[0]-lo[0]),y:b.top+b.height*(p[1]-lo[1])/(hi[1]-lo[1])};
      if(document.elementFromPoint(q.x,q.y)!==c) throw Error('Plan coordinate is outside the drawing surface '+JSON.stringify({p,q,b:[b.left,b.top,b.width,b.height]}));
      return q;
    },p);
  }
  async function touchEvent(type,points) {
    return client.send('Input.dispatchTouchEvent',{type,touchPoints:points.map(({x,y,id=1})=>({x,y,id,radiusX:3,radiusY:3,force:.8}))});
  }
  async function start(q) {
    if(touch) return touchEvent('touchStart',[q]);
    await page.mouse.move(q.x,q.y);await page.mouse.down();
  }
  const move=q=>touch?touchEvent('touchMove',[q]):page.mouse.move(q.x,q.y,{steps:5});
  const end=()=>touch?touchEvent('touchEnd',[]):page.mouse.up();
  async function save() {
    const s=await current(); assert.equal(s.dirty,true,s.status);await click(cmd('save'));
    await page.waitForFunction(rev=>{const s=__house.furnishing.state();return !s.dirty && !s.saving && s.revision>rev;},{timeout:45000},s.revision);
    return (await current()).revision;
  }
  async function record() {
    return page.evaluate(async url=>{const r=await fetch(url,{cache:'no-store'});if (!r.ok)throw Error('GET layout '+r.status);return r.json();},layoutUrl);
  }
  async function chooseWallColour(colour) {
    await page.$eval(sel('colour'),(el,hex)=>{el.value=hex;el.dispatchEvent(new Event('change',{bubbles:true}));},colour);
  }
  async function spots() {
    return page.evaluate(async ({STOCK,ROOM})=>{
      const {checkGroup,snapPlacement}=await import('/src/furnish/placement.mjs'), f=__house.furnishing,s=f.state();
      const stock=s.filtered.find(i=>i.id===STOCK);if(!stock)throw Error('Side table is hidden by the current catalogue filters');
      const candidate={id:'qa-geometric-probe',room:ROOM,kind:stock.kind,style:stock.style,catalogueId:stock.id,variant:stock.id,
        size:stock.size_m,host:{type:'floor',id:'floor/'+ROOM}};
      const tryAt=(p,r=0)=>{const a=snapPlacement(f.context,f.layout.items,{...candidate,position:[p[0],0,p[1]],rotation:r});
        return {row:a,...checkGroup(f.context,f.layout.items,a)};};
      const options=[[.6,-.6],[.8,-.85],[1,-.95],[.9,-1.1],[1.16,-.8],[.7,-1.1],[1.18,-1.22],[.95,-1.38]];
      const valid=options.filter(p=>[0,15,30,45,345].every(turn=>tryAt(p,turn).ok));
      const a=valid[0],b=a && valid.find(p=>Math.hypot(p[0]-a[0],p[1]-a[1])>.29);
      if(!a||!b)throw Error('No two legal side-table placements in the disposable room');
      const issue=tryAt([1.8,-2.35]);if(issue.ok)throw Error('Expected the signed coffee table to block this spot');
      const doors=f.context.openings.filter(o=>o.storey===s.room.storey && o.kind!=='window'), door=[];
      for(const o of doors) {
        const mid=[(o.p0[0]+o.p1[0])/2,(o.p0[1]+o.p1[1])/2];
        for(const sign of [1,-1])for(const d of [.29,.4,.6]) {
          const p=[mid[0]+o.n[0]*sign*d,mid[1]+o.n[1]*sign*d],check=tryAt(p);
          if(check.reasons.some(s=>s.includes('Blocks the ')) && __house.furnishing.plan.toUV(p)?.every(v=>v>.04 && v<.96))door.push(p);
        }
      }
      if(!door.length)throw Error('Cannot target a measured door sweep inside this room');
      return {a,b,overlap:[1.8,-2.35],door:door[0]};
    },{STOCK,ROOM});
  }
  async function blocked(from,to,expected) {
    const p=await screen([from.position[0],from.position[2]]),q=await screen(to);await start(p);await move(q);
    const report=await page.evaluate(()=>{
      const s=__house.furnishing.state(),c=document.getElementById('furnish-plan'),ctx=c.getContext('2d');
      const pixels=ctx.getImageData(0,0,c.width,c.height).data;let redPixels=0;
      for(let i=0;i<pixels.length;i+=4)if(pixels[i]===202&&pixels[i+1]===99&&pixels[i+2]===91)redPixels++;
      return {reasons:s.verdict?.reasons,ok:s.verdict?.ok,redPixels,panel:document.querySelector('[data-furnish-panel] [data-status]').classList.contains('fu-blocked')};
    });
    await end();
    assert.equal(report.ok,false,JSON.stringify(report));assert.ok(report.redPixels>10 && report.panel,JSON.stringify(report));
    assert.match(report.reasons.join(' '),expected);
    const after=await current();assert.deepEqual(after.selected.position,from.position);return report;
  }
  let itemId=null,faceId=null,initial=null,chosenPaint=null,chosenFloor=null;
  try {
    if(!touch)result.catalogue=await plannerClient(page,ORIGIN,SITE);
    await boot();initial=await record();assert.equal(initial.site,SITE);assert.equal(initial.version,VERSION);
    const startState=await current();assert.ok(!startState.dirty);const places=await spots();
    await page.select(sel('kind'),'side_table');await page.select(sel('style'),'modern');
    await click('[data-furnish-panel] [data-stock-id="'+STOCK+'"]');
    const add=await screen(places.a);await start(add);await end();
    await page.waitForFunction((ids,stock)=>{const s=__house.furnishing.state();return s.selected?.catalogueId===stock && !ids.includes(s.selected.id);},{timeout:10000},startState.ids,STOCK);
    const placed=(await current()).selected;itemId=placed.id;assert.equal(placed.host.id,'floor/'+ROOM);
    const first=await screen([placed.position[0],placed.position[2]]),dest=await screen(places.b);
    await start(first);await move(dest);await end();const moved=(await current()).selected;assert.ok(distance(moved.position,placed.position)>.20,'Drag did not move this side table');
    if(!touch) {
      await page.keyboard.press('e');assert.ok(Math.abs(angle((await current()).selected.rotation,moved.rotation)-15)<.001,'E should turn right');
      await page.keyboard.press('q');assert.ok(Math.abs(angle((await current()).selected.rotation,moved.rotation))<.001,'Q should reverse the turn');
      await page.keyboard.press('e');
    } else {
      const p=await screen([moved.position[0],moved.position[2]]),r=32;
      await touchEvent('touchStart',[{...p,id:1}]);
      await touchEvent('touchStart',[{...p,id:1},{x:p.x+r,y:p.y,id:2}]);
      await touchEvent('touchMove',[{...p,id:1},{x:p.x+r*Math.cos(Math.PI/6),y:p.y-r*.5,id:2}]);
      await touchEvent('touchEnd',[]);
    }
    const turned=(await current()).selected;assert.ok(Math.abs(angle(turned.rotation,moved.rotation)-(touch?30:15))<2,'Rotation gesture lost its measured angle');
    result.rotation=turned.rotation; result.overlap=await blocked(turned,places.overlap,/overlap/i);result.door=await blocked(turned,places.door,/Blocks the /);
    await click(cmd('delete'));assert.ok(!(await current()).ids.includes(itemId));await click(cmd('undo'));assert.ok((await current()).ids.includes(itemId));
    await click(cmd('redo'));assert.ok(!(await current()).ids.includes(itemId));await click(cmd('undo'));assert.ok((await current()).ids.includes(itemId));
    faceId=await page.$eval(sel('face'),select=>[...select.options].find(o=>o.value)?.value);
    assert.ok(faceId && faceId.startsWith(ROOM+'/'));const paint=initial.wallColours[faceId]==='#526b64'?'#657b75':'#526b64';
    const floor=initial.roomFloors[ROOM]==='FLR-OAK-PALE'?'FLR-SLATE':'FLR-OAK-PALE';chosenPaint=paint;chosenFloor=floor;
    await page.select(sel('face'),faceId);await chooseWallColour(paint);await page.select(sel('floor'),floor);
    await page.select(sel('selected'),itemId);const revision=await save();const saved=await record(),row=saved.items.find(i=>i.id===itemId);
    assert.deepEqual(row.position,turned.position);assert.equal(row.rotation,turned.rotation);
    const physical=await page.evaluate(({faceId,room})=>{
      const {V}=__house,faces=V.model.parts.filter(p=>p.ud.surface_id===faceId),floor=V.model.parts.filter(p=>p.ud.surface_id==='floor/'+room && p.now.visible);
      return {painted:faces.filter(p=>p.clientTint).length,floors:floor.length,covered:floor.filter(p=>p.finishMesh?.visible && !p.batch.getVisibleAt(p.instanceId)).length,
        neighborFloor:V.model.parts.find(p=>p.ud.surface_id?.startsWith('floor/')&&p.ud.room_id!==room)?.ud.room_id};
    },{faceId,room:ROOM});assert(physical.painted>0 && physical.floors>0 && physical.covered===physical.floors,'Actual visible finish assignment '+JSON.stringify(physical));
    assert.deepEqual(saved.wallColours,{...initial.wallColours,[faceId]:paint});assert.deepEqual(saved.roomFloors,{...initial.roomFloors,[ROOM]:floor});
    assert.deepEqual(saved.garden,initial.garden);assert.equal(saved.items.length,initial.items.length+1);
    result.saved={id:itemId,position:row.position,rotation:row.rotation,wall:faceId,colour:paint,floor,revision};
    // A clean saved state with the added table visible in plan and the selection kept.
    await page.screenshot({path:path.join(output,name+'-room-edit.png')});
    await page.goto(plannerUrl,{waitUntil:'domcontentloaded'});
    await page.waitForFunction(id=>window.planner?.session?.ready && planner.state.items.has(id),{timeout:150000},itemId);
    const fromPlanner=await page.evaluate(({id,face,room})=>({row:planner.state.items.get(id).shared,wall:planner.session.layout.wallColours[face],
      floor:planner.session.layout.roomFloors[room],site:planner.db.site,version:planner.session.version}),{id:itemId,face:faceId,room:ROOM});
    assert.deepEqual(fromPlanner,{row,wall:paint,floor,site:SITE,version:VERSION});
    const badge='#plan .badge[data-id="'+itemId+'"]';await click(badge);
    await page.waitForFunction(id=>planner.selected===id,{},itemId);
    await click('#inspector button[title="Turn right 15° (])"]');
    await page.waitForFunction((id,rot)=>planner.session.layout.get(id).rotation!==rot,{},itemId,row.rotation);
    const returned=await page.evaluate(id=>planner.session.layout.get(id),itemId);await click('#saveLayout');
    await page.waitForFunction(rev=>!planner.session.layout.dirty && planner.session.layout.revision>rev,{},revision);
    await boot();const fetched=await record();assert.deepEqual(fetched.items.find(it=>it.id===itemId),returned);
    assert.deepEqual(await page.evaluate(id=>__house.furnishing.layout.get(id),itemId),returned);
    result.reopened={revision:fetched.revision,rotation:returned.rotation};
    await page.select(sel('selected'),itemId);await click(cmd('delete'));
    await page.select(sel('face'),faceId);
    if(initial.wallColours[faceId])await chooseWallColour(initial.wallColours[faceId]);else await click(cmd('reset-wall'));
    await page.select(sel('floor'),initial.roomFloors[ROOM]||'');await save();
    const restored=await record();
    // Every pre-existing object and finish, including all other QA records, survives.
    assert.deepEqual(restored.items,initial.items);assert.deepEqual(restored.wallColours,initial.wallColours);
    assert.deepEqual(restored.roomFloors,initial.roomFloors);assert.deepEqual(restored.garden,initial.garden);
    result.cleanupRevision=restored.revision;result.count=initial.items.length;result.writeCount=writes.length;assert.deepEqual(result.errors,[]);
    console.log('PASS '+name+' furniture edit flow',JSON.stringify(result.saved),result.reopened);
  } catch(e) {result.failure=e.message;throw e;}
  finally {
    if(result.failure && itemId && initial) {
      // Clean up a failed run only if this specific temporary ID reached the
      // disposable site. Keep unrelated fresh changes and let a concurrent
      // writer win the revision check.
      try {
        result.fixtureCleanup=await page.evaluate(async data=>{
          const saved=await (await fetch(data.url,{cache:'no-store'})).json();
          if(saved.site!=='furnish-qa'||saved.version!=='approved_2b'||!saved.items?.some(i=>i.id===data.itemId))return 'No saved probe item';
          const items=saved.items.filter(i=>i.id!==data.itemId),wallColours={...saved.wallColours},roomFloors={...saved.roomFloors};
          if(data.faceId && wallColours[data.faceId]===data.paint) {
            if(data.oldPaint)wallColours[data.faceId]=data.oldPaint;else delete wallColours[data.faceId];
          }
          if(roomFloors[data.room]===data.floor) {
            if(data.oldFloor)roomFloors[data.room]=data.oldFloor;else delete roomFloors[data.room];
          }
          const r=await fetch(data.url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({section:'furnish',baseRevision:saved.revision,items,wallColours,roomFloors})});
          return 'Cleanup HTTP '+r.status;
        },{url:layoutUrl,itemId,faceId,room:ROOM,paint:chosenPaint,floor:chosenFloor,oldPaint:initial.wallColours[faceId],oldFloor:initial.roomFloors[ROOM]});
      } catch(e) {result.fixtureCleanup=e.message;}
    }
    fs.writeFileSync(path.join(output,name+'-room-edit.json'),JSON.stringify(result,null,2)+'\n');await context.close();
  }
}

async function run(){
  const only=process.argv[2]||'both';if(!['desktop','phone','both'].includes(only))throw Error('Choose desktop, phone or both');
  const browser=await puppeteer.launch({executablePath:process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless:true,protocolTimeout:300000,args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal']});
  try { for(const name of only==='both'?['desktop','phone']:[only]) await profile(browser,name); } finally {await browser.close();}
}
if(require.main===module)run().then(()=>process.exit(0),e=>{console.error(e);process.exit(1);});
