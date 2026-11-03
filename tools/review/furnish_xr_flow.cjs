/* Run alone on the local QA copy. All furnishing actions use the simulated
 * hand, real right-trigger ownership, and the interactive left wrist meshes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require(process.env.PUPPETEER_CORE || 'puppeteer-core');

const origin = new URL(process.env.STUDIO_URL || 'https://127.0.0.1:8450');
if (origin.protocol !== 'https:' || !['localhost','127.0.0.1','[::1]'].includes(origin.hostname) || origin.port !== '8450') {
  throw Error('Furnishing XR acceptance requires the local loopback test server on 8450.');
}
const site='furnish-qa',version='approved_2b',roomId='R-g-living', stockId='modern.side_table';
const url = new URL('/house.html',origin);
url.search = new URLSearchParams({site,version,mode:'review',edit:'1',xrsim:'1'}).toString();
const api = new URL('/layout?' + new URLSearchParams({site,version}),origin).href;
const output=path.resolve(__dirname,'../../renders/house-build/furnishing/furnish-system/quest-flow');
const near=(a,b,tol=.004)=>a.length===b.length&&a.every((n,i)=>Math.abs(n-b[i])<=tol);
function sameEnvelope(a,b) {
  const omit=({revision,furnishSeeded,...rest})=>rest;
  assert.deepEqual(omit(a),omit(b),'Pre-existing QA content changed');
}

async function run() {
  fs.mkdirSync(output,{recursive:true});
  const browser=await puppeteer.launch({executablePath:process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless:true,protocolTimeout:300000,args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal']});
  const report={site,version,room:roomId,device:'Chrome with the studio simulated Quest controllers',stages:[],frames:{}};
  const errors=[];
  let page,baseline,ownId=null,chosenFloor=null,cleanupDone=false;
  try {
    page=await browser.newPage();
    await page.setViewport({width:1080,height:720,deviceScaleFactor:1});
    await page.setUserAgent('Mozilla/5.0 (X11; Linux x86_64; Quest 3) AppleWebKit/537.36 Chrome/132 Mobile VR OculusBrowser/35.0 Safari/537.36');
    await page.setRequestInterception(true);
    page.on('request',r=>r.url().startsWith(origin.origin+'/')||/^(blob:|data:|about:)/.test(r.url())?r.continue():r.abort());
    page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE ERROR',e.message);});
    page.on('console',m=>{const s=m.text();if(/shader error|validate_status.*false|uncaught \(in promise\)/i.test(s)) errors.push(s.slice(0,240));});
    async function boot() {
      await page.goto(url.href,{waitUntil:'domcontentloaded',timeout:180000});
      await page.waitForFunction(()=>{
        const h=window.__house,f=h?.furnishing;
        return h?.V?.def?.id==='approved_2b'&&h.inVR()&&h.hands.left&&h.hands.right&&
          f?.enabled&&f.bird&&f.layout?.loaded&&f.context?.rooms.length&&f.state().room&&
          f.wrist.wristWorld('Home')&&f.plan.toUV([.6,-.6]);
      },{timeout:200000});
      await page.evaluate(()=>{const h=__house;h.sim.wrist(true);h.step(2);});
    }
    const server=()=>page.evaluate(async url=>{
      const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error('Read layout: '+r.status);return r.json();
    },api);
    const state=()=>page.evaluate(()=>{
      const f=__house.furnishing,s=f.state();
      return {room:s.room.id,bird:f.bird,selected:s.selected,pending:s.pending,dirty:s.dirty,saving:s.saving,
        conflict:s.conflict,revision:s.revision,count:s.items.length,status:s.status,filters:s.filters,verdict:s.verdict,floor:s.floor};
    });
    const get=id=>page.evaluate(id=>__house.furnishing.layout.get(id),id);
    async function stage(name) {
      const s=await state();
      report.stages.push({name,bird:s.bird,revision:s.revision,dirty:s.dirty,selected:s.selected?.id||null,count:s.count,status:s.status});
      console.log(name,JSON.stringify(report.stages.at(-1)));
    }
    async function wrist(label) {
      await page.evaluate(label=>{
        const h=__house,f=h.furnishing;
        h.sim.wrist(true);h.sim.hold('trigger',false);h.step(2);
        const p=f.wrist.wristWorld(label);if(!p) throw Error('No clickable wrist button '+label);
        h.sim.aim(p);h.step(2);h.sim.hold('trigger',true);h.step(2);
        h.sim.hold('trigger',false);h.step(2);
      },label);
    }
    async function paged(label,limit=25) {
      for(let i=0;i<limit;i++) {
        if(await page.evaluate(s=>!!__house.furnishing.wrist.wristWorld(s),label)) {await wrist(label);return;}
        await wrist('Next page');
      }
      throw Error('Missing paged wrist choice '+label);
    }
    async function screenshot(name) {
      const shot=await page.evaluate(()=>{
        const h=__house, f=h.furnishing;
        if(!h.inVR()||!document.body.classList.contains('furniture-immersive')||!document.querySelector('#furnish-plan').hidden||
          getComputedStyle(document.querySelector('.fu-panel')).display!=='none') throw Error('Desktop furniture UI is visible in simulated XR');
        h.step(1);h.renderer.info.reset();h.renderer.render(h.scene,h.camera);
        return {png:h.renderer.domElement.toDataURL('image/png'),width:h.renderer.domElement.width,height:h.renderer.domElement.height,
          calls:h.renderer.info.render.calls,triangles:h.renderer.info.render.triangles,wrist:h.scene.getObjectByName('Furnish · left wrist')?.visible,
          table:h.scene.getObjectByName('Furnish · room plan')?.visible,bird:f.bird};
      });
      assert(shot.wrist&&shot.table===shot.bird&&shot.calls>0&&shot.triangles>0&&shot.png.length>6000,'Empty simulated XR frame '+name);
      const {png,...metadata}=shot;
      fs.writeFileSync(path.join(output,name+'.png'),Buffer.from(png.split(',')[1],'base64'));
      report.frames[name]=metadata;
    }
    async function trigger(points,leaveHeld=false) {
      return page.evaluate(({points,leaveHeld})=>{
        const h=__house,f=h.furnishing;
        h.sim.wrist(false);h.sim.hold('trigger',false);h.step(2);
        function aim(p) {
          const destination=f.wrist.planWorld(p);if(!destination)throw Error('No room tabletop');
          h.sim.aim(destination);h.step(2);
        }
        aim(points[0]);h.sim.hold('trigger',true);h.step(2);
        for(const p of points.slice(1)) aim(p);
        const beforeRelease=f.state().verdict;
        if(!leaveHeld){h.sim.hold('trigger',false);h.step(2);}
        return beforeRelease;
      },{points,leaveHeld});
    }
    async function save() {
      const before=(await state()).revision;
      await wrist('Save layout');
      await page.waitForFunction(previous=>{
        const s=__house.furnishing.state();
        if(s.conflict)throw Error('Another client wrote the QA layout: '+s.status);
        return !s.saving&&!s.dirty&&s.revision>previous;
      },{timeout:30000},before);
      return server();
    }
    await boot();
    baseline=await server();assert.equal(baseline.site,site);assert.equal(baseline.version,version);
    assert.deepEqual(await page.evaluate(()=>__house.furnishing.layout.items),baseline.items);
    const roomLabel=await page.evaluate(id=>__house.furnishing.state().rooms.find(r=>r.id===id)?.label,roomId);
    assert(roomLabel);
    await wrist('Rooms');await paged(roomLabel);assert.equal((await state()).room,roomId);
    await wrist('How to use');await wrist('Next');await screenshot('wrist-help');await wrist('Dismiss help');
    await stage('Opened and dismissed furnishing help on the left wrist');
    await wrist('Catalogue');await wrist('Kind');await paged('side_table');
    await wrist('Style');await paged('modern');
    const choice=await page.evaluate(id=>__house.furnishing.state().filtered.find(i=>i.id===id),stockId);
    assert.equal(choice.kind,'side_table');await paged(choice.name);assert.equal((await state()).pending,stockId);

    // Determine reachable positions from the actual current QA seed. Planning
    // is read-only: the real wrist ray and trigger perform each subsequent edit.
    const fit=await page.evaluate(async ({choice,roomId})=>{
      const h=__house,f=h.furnishing,items=f.layout.items,room=f.context.rooms.find(r=>r.id===roomId);
      const {checkGroup,snapPlacement}=await import('/src/furnish/placement.mjs');
      h.sim.wrist(false);h.sim.hold('trigger',false);h.step(2);
      const origin=h.hands.right.getWorldPosition(new h.THREE.Vector3());
      const clear=p=>{
        const uv=f.plan.toUV(p);if(!uv||uv.some(x=>x<.015||x>.985))return false;
        const world=f.wrist.planWorld(p),ray=new h.THREE.Ray(origin.clone(),world.clone().sub(origin).normalize());
        const hit=f.wrist.hitPlan(ray);
        return f.wrist.hitWrist(ray,false)===null&&hit&&Math.hypot(hit.point.x-p[0],hit.point.z-p[1])<.004;
      };
      const stock={id:'xr-probe',kind:choice.kind,catalogueId:choice.id,variant:choice.id,style:choice.style,
        size:choice.size_m,room:roomId,position:[0,room.floorY,0],rotation:0,host:{type:'floor',id:'floor/'+roomId}};
      const xs=room.polygon.map(p=>p[0]),zs=room.polygon.map(p=>p[1]);
      const [x0,x1,z0,z1]=[Math.min(...xs),Math.max(...xs),Math.min(...zs),Math.max(...zs)];
      const tries=[[.6,-.6]];
      for(let x=x0+.24;x<x1-.2;x+=.22) for(let z=z1-.24;z>z0+.2;z-=.22)tries.push([x,z]);
      const place=(p,base=stock,list=items)=>snapPlacement(f.context,list,{...base,position:[p[0],room.floorY,p[1]]});
      const point=it=>[it.position[0],it.position[2]];
      let add,drag;
      for(const p of tries) {
        if(!clear(p))continue;
        const candidate=place(p);if(!clear(point(candidate))||!checkGroup(f.context,items,candidate).ok)continue;
        const list=[...items,candidate];
        for(const target of tries) {
          if(Math.hypot(target[0]-p[0],target[1]-p[1])<.28||!clear(target))continue;
          const moved=place(target,candidate,list);
          if(Math.hypot(...point(moved).map((n,i)=>n-point(candidate)[i]))<.20||!clear(point(moved)))continue;
          if(!checkGroup(f.context,list,moved).ok||!checkGroup(f.context,list,{...moved,rotation:15}).ok)continue;
          add={aim:p,pose:candidate.position};drag={aim:target,pose:moved.position};break;
        }
        if(drag)break;
      }
      if(!add||!drag) throw Error('No visible, valid pair of lounge positions for a new side table');
      let bad;
      for(const z of [z1-.45,(z1+z0)/2,z0+.45])for(const x of [x0-.16,x1+.16]){
        const p=[x,z];if(clear(p)&&!checkGroup(f.context,items,place(p)).ok){bad=p;break;}
      }
      if(!bad)throw Error('No reachable blocked lounge footprint');
      return {add,drag,bad};
    },{choice,roomId});
    report.points=fit;
    await trigger([fit.add.aim]);
    let s=await state();
    assert.equal(s.count,baseline.items.length+1,'Right trigger must add exactly one piece: '+s.status);
    assert(s.selected&&!baseline.items.some(i=>i.id===s.selected.id));ownId=s.selected.id;
    assert.equal(s.selected.catalogueId,stockId);assert(near(s.selected.position,fit.add.pose));
    await stage('Added the chosen stock side table with the right trigger');
    await trigger([[s.selected.position[0],s.selected.position[2]],fit.drag.aim]);
    s=await state();assert.equal(s.selected.id,ownId);assert(near(s.selected.position,fit.drag.pose),s.status);
    await page.evaluate(()=>{const h=__house;h.sim.stick('right',.9,0);h.step(2);h.sim.stick('right',0,0);h.step(2);});
    const rotated=await get(ownId);assert.equal(rotated.rotation,15);assert(near(rotated.position,fit.drag.pose));
    await stage('Dragged the side table and rotated it with the right thumbstick');

    const at=[rotated.position[0],rotated.position[2]];
    const invalid=await trigger([at,fit.bad],true);assert.equal(invalid?.ok,false,'Blocked preview was never shown');
    await screenshot('blocked-drop');
    await page.evaluate(()=>{const h=__house;h.sim.hold('trigger',false);h.step(2);});
    s=await state();assert.match(s.status,/blocked/i);assert.deepEqual(await get(ownId),rotated);
    await wrist('Undo');assert.equal((await get(ownId)).rotation,0);
    await wrist('Redo');assert.deepEqual(await get(ownId),rotated);
    await stage('Rejected the blocked drop and restored the exact rotation with undo and redo');

    const floors=await page.evaluate(()=>__house.furnishing.state().floors);
    const originalFloor=baseline.roomFloors[roomId], originalChoice=floors.find(f=>f.id===originalFloor);
    if(!originalFloor||originalChoice) {
      const alternate=floors.find(f=>f.id==='FLR-OAK-HB'&&f.id!==originalFloor)||floors.find(f=>f.id!==originalFloor);
      if(alternate){await wrist('Floor covering');await paged(alternate.name);assert.equal((await state()).floor,alternate.id);chosenFloor=alternate.id;}
    }
    await screenshot('furnished-room-plan');
    await wrist('Walking view');assert.equal((await state()).bird,false);
    await wrist('Rooms');await paged(roomLabel);
    await wrist('How to use');await wrist('Dismiss help');
    await page.waitForFunction(id=>{
      const f=__house.furnishing;
      return f.runtime?.group.visible&&f.runtime.group.children.some(b=>b.visible&&b.userData.furnishItems?.some(it=>it.id===id));
    },{timeout:120000},ownId);
    const walkItem=await page.evaluate(id=>{
      const batches=__house.furnishing.runtime.group.children;
      return batches.flatMap(b=>b.visible?b.userData.furnishItems||[]:[]).find(it=>it.id===id);
    },ownId);
    assert.deepEqual(walkItem,rotated);await screenshot('furnished-walking');
    await wrist('Bird’s-eye');assert((await state()).bird);assert.deepEqual(await get(ownId),rotated);
    const saved=await save();
    assert.deepEqual(saved.items.find(i=>i.id===ownId),rotated);
    assert.deepEqual(saved.items.filter(i=>i.id!==ownId),baseline.items);
    if(chosenFloor)assert.equal(saved.roomFloors[roomId],chosenFloor);
    report.saved={id:ownId,position:rotated.position,rotation:rotated.rotation,floor:chosenFloor,revision:saved.revision};
    await stage('Shared storage saved the item pose and chosen room covering');
    await page.goto('about:blank');await boot();
    assert.deepEqual(await get(ownId),rotated);
    if(chosenFloor)assert.equal((await state()).floor,chosenFloor);
    await stage('Fresh headset page reopened the same furniture and finish');

    // Remove only this invocation's generated ID and undo only its own floor
    // choice. The QA room may already hold edits written by desktop/phone tests.
    await trigger([at]);assert.equal((await state()).selected?.id,ownId);
    await wrist('Delete');assert.equal(await get(ownId),undefined);
    if(chosenFloor){await wrist('Floor covering');await paged(originalChoice?.name||'Original covering');}
    const restored=await save();
    sameEnvelope(restored,baseline);cleanupDone=true;
    assert.deepEqual(errors,[]);
    report.restoredRevision=restored.revision;
    fs.writeFileSync(path.join(output,'controller-flow.json'),JSON.stringify(report,null,2)+'\n');
    console.log('PASS simulated Quest furnishing',JSON.stringify(report.saved));
  } finally {
    // If Chrome or a later assertion interrupted a committed sample, recover
    // the test-owned ID without replacing concurrent QA items or finishes.
    if(page&&ownId&&baseline&&!cleanupDone&&!page.isClosed()) {
      try {
        if(!page.url().startsWith(origin.origin+'/'))await page.goto(origin.origin+'/house.html?site='+site,{waitUntil:'domcontentloaded'});
        const result=await page.evaluate(async ({api,ownId,roomId,chosenFloor,oldFloor})=>{
          const res=await fetch(api,{cache:'no-store'});if(!res.ok)throw Error('Cleanup read '+res.status);
          const now=await res.json();if(!now.items.some(it=>it.id===ownId))return 'not committed';
          const roomFloors={...now.roomFloors};
          if(chosenFloor && roomFloors[roomId]===chosenFloor) {
            if(oldFloor==null)delete roomFloors[roomId];else roomFloors[roomId]=oldFloor;
          }
          const write=await fetch(api,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
            section:'furnish',baseRevision:now.revision,items:now.items.filter(it=>it.id!==ownId),wallColours:now.wallColours,roomFloors})});
          if(!write.ok)throw Error('Cleanup did not replace a concurrent revision: '+write.status);
          return 'test item removed';
        },{api,ownId,roomId,chosenFloor,oldFloor:baseline.roomFloors[roomId]??null});
        console.log('QA cleanup',result);
      } catch(e) {console.error('QA cleanup requires review for test ID',ownId,e.message);}
    }
    await browser.close();
  }
}
run().catch(e=>{console.error(e);process.exitCode=1;});
