/* Run the real client routes on port 8450, one browsing profile at a time. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const puppeteer = require(process.env.PUPPETEER_CORE || 'puppeteer-core');
const [round, site='house'] = process.argv.slice(2);
if (![round,site].every(s => typeof s==='string' && /^[a-z\d_-]+$/i.test(s))) throw Error('Expected round and site');
const root = path.resolve(__dirname,'../..');
const local = 'https://127.0.0.1:8450';
const out = path.join(root,'renders/house-build/furnishing',round);
const manifest = JSON.parse(fs.readFileSync(path.join(root,'assets/sites',site,'versions.json')));
const spec = JSON.parse(fs.readFileSync(path.join(root,'assets/sites',site,'spec/spec_v1.json')));
async function main() {
  fs.mkdirSync(out,{recursive:true});
  const browser = await puppeteer.launch({executablePath:process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless:true,args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal'],protocolTimeout:300000});
  const results={};
  try {
    for (const profile of ['desktop','phone','simulated-headset']) {
      const context=await browser.createBrowserContext();
      try {
        const page=await context.newPage();
        const phone=profile==='phone', xr=profile==='simulated-headset', errors=[];
        await page.setViewport({width:phone?390:1000,height:phone?844:640,hasTouch:phone,isMobile:phone,deviceScaleFactor:1});
        if (phone) await page.setUserAgent('Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 Chrome/132 Mobile Safari/537.36');
        await page.setRequestInterception(true);
        page.on('request',r=>r.url().startsWith(local+'/') || /^(blob:|data:)/.test(r.url()) ? r.continue() : r.abort());
        page.on('pageerror',e=>errors.push(e.message));
        const result=results[profile]={};
        if (!xr) {
          const room=spec.versions.after.rooms.find(r=>r.id.endsWith('-living'));
          await page.goto(local+'/planner.html?site='+site+'#after/room/'+encodeURIComponent(room.id),{waitUntil:'domcontentloaded'});
          await page.waitForFunction(id=>window.planner?.room?.id===id,{timeout:120000},room.id);
          await page.click('#threeBtn');
          await page.waitForFunction(()=>!!window.planner.view3d?.renderer?.domElement,{timeout:90000});
          result.planner=await page.evaluate(()=>({room:window.planner.room.id,items:window.planner.state.items.size,
            canvas:window.planner.view3d.renderer.domElement.width,overflows:document.documentElement.scrollWidth>innerWidth+1}));
          assert(result.planner.canvas>0 && result.planner.items>0 && !result.planner.overflows);
        }
        await page.goto(local+'/house.html?mode=customer&site='+site+(xr?'&xrsim=1':''),{waitUntil:'domcontentloaded'});
        await page.waitForFunction(()=>!!window.__house?.V?.model,{timeout:200000});
        if (!xr) {
          for (const [button,version] of [['#baBefore',manifest.as_built_now],['#baAfter',manifest.default]]) {
            await page.click(button);
            await page.waitForFunction(id=>window.__house.V?.def.id===id,{timeout:150000},version);
          }
          await page.click('#baFurnish');
          await page.waitForFunction(()=>window.__house.unfurnished);
          await page.click('#baFurnish');
          await page.waitForFunction(()=>!window.__house.unfurnished);
          const dest=await page.$eval('#baGoto',s=>[...s.options].find(o=>o.value && /living|lounge/i.test(o.text))?.value || [...s.options].find(o=>o.value)?.value);
          if (dest) await page.select('#baGoto',dest);
          result.goto=dest;assert(dest);
        }
        result.viewer=await page.evaluate(()=>{const h=window.__house;return {version:h.V.def.id,stage:h.stage,simulating:h.inVR(),
          furnished:!h.unfurnished,draw:h.stats(),wrist:!!h.wristTab,roomCulling:!!h.cull,doors:!!h.V?.doors};});
        assert(result.viewer.furnished && result.viewer.draw.triangles>0 && result.viewer.roomCulling);
        if (xr) assert(result.viewer.wrist && result.viewer.simulating);
        result.errors=errors;assert.deepEqual(errors,[]);
      } finally { await context.close(); }
    }
  } finally {
    fs.writeFileSync(path.join(out,'devices.json'),JSON.stringify(results,null,2));
    await browser.close();
  }
  console.log('Client route checks passed for desktop, phone, and simulated headset');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
