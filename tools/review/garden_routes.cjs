/* Normal entry points, using the published house and its ordinary navigation. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const puppeteer=require(process.env.PUPPETEER_CORE||'puppeteer-core');
(async()=>{
 const url='https://127.0.0.1:8450',browser=await puppeteer.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal'],protocolTimeout:300000});
 try{
  for(const route of ['plan/','index.html?site=front-garden-model','house.html?site=house-wip&mode=architect','house.html?site=house-wip&mode=review&test=walk']){
    const p=await browser.newPage(),errors=[];p.on('pageerror',e=>{errors.push(e.message);console.error('page error',e.message);});await p.setViewport({width:1050,height:720});
    await p.goto(url+'/'+route,{waitUntil:'domcontentloaded',timeout:120000});
    if(route==='plan/'){
      await p.waitForSelector('#plan .room, #plan [data-room]',{timeout:60000});
      await p.click('[data-editor-help=planner]');assert.match(await p.$eval('#studio-help-dialog',n=>n.textContent),/Undo/);await p.click('#studio-help-dialog button');
      await p.$eval('#plan [data-room]',e=>{const r=e.getBoundingClientRect();const send=(type)=>e.dispatchEvent(new PointerEvent(type,{pointerId:7,clientX:r.x+r.width/2,clientY:r.y+r.height/2,bubbles:true})); send('pointerdown');send('pointerup');}).catch(()=>{});
      console.log('Planner controls and room geometry present');
    }else if(route.startsWith('index')){
      await p.waitForSelector('#startDesktop:not([disabled])',{timeout:150000});
      await p.click('#startDesktop');await p.click('[data-editor-help=site]');assert.match(await p.$eval('#studio-help-dialog',n=>n.textContent),/Mark/);await p.keyboard.press('Escape');
      assert.match(await p.$eval('.garden-entry',a=>a.href),/house-wip/);console.log('Original surveyed garden and shared help ready');
    }else if(route.includes('test=walk')){
      await p.waitForFunction(()=>window.__walkTest,{timeout:300000});const r=await p.evaluate(()=>__walkTest);
      for(const v of r.versions)console.log('walk version',v.id||v.version,(v.rooms||[]).map(x=>x.ok));
      const out=path.resolve(__dirname,'../../renders/garden-tool/walk-summary.json');fs.writeFileSync(out,JSON.stringify(r,null,1));
      assert(r.pass,'Published house walk failed. See '+out);console.log('Published house walk passed',r.versions.length,'versions',r.seconds,'seconds');
    }else{
      await p.waitForSelector('#startDesktop:not([disabled])',{timeout:180000});await p.click('#startDesktop');
      await p.click('#top [data-editor-help=house]');assert.match(await p.$eval('#studio-help-dialog',n=>n.textContent),/Architect/);await p.keyboard.press('Escape');
      assert(!await p.evaluate(()=>__house.garden.enabled));await p.click('#top [data-garden-open]');await p.waitForFunction(()=>__house.garden.enabled);
      await p.click('[data-garden-panel] [data-cmd=close]');assert(!await p.evaluate(()=>__house.garden.enabled));console.log('House architect, help, garden entry and return passed');
    }
    assert.deepEqual(errors,[]);await p.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
