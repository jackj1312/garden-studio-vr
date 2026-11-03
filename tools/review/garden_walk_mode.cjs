/* Exercise the real garden page and the native pointer lock, without writing a client design. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.PUPPETEER_CORE||'puppeteer-core');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'renders/garden-tool');
const origin=new URL(process.env.STUDIO_URL||'https://127.0.0.1:8450');
assert(origin.protocol==='https:' && origin.port==='8450' && ['127.0.0.1','localhost','192.168.1.118'].includes(origin.hostname));
const site='house-wip',version='approved_2b',stage=origin.hostname==='192.168.1.118'?'lan':'mac';
async function main(){
 fs.mkdirSync(out,{recursive:true});
 const browser=await puppeteer.launch({headless:true,executablePath:process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
   args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal'],protocolTimeout:300000});
 try{
  const page=await browser.newPage();await page.setViewport({width:1100,height:700});await page.setCacheEnabled(false);
  const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setRequestInterception(true);page.on('request',r=>{
   if(!['GET','HEAD'].includes(r.method())){writes.push(new URL(r.url()).pathname);return r.abort();}
   return r.url().startsWith(origin.origin+'/')||/^(blob:|data:)/.test(r.url())?r.continue():r.abort();
  });
  await page.goto(origin.origin+'/house.html?'+new URLSearchParams({site,version,mode:'review',garden:'1'}),{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__house?.garden?.enabled&&__house.garden.bird&&!document.querySelector('#startDesktop').disabled,{timeout:160000});
  const state=()=>page.evaluate(()=>{const h=__house,g=h.garden,s=g.state();return {bird:g.bird,collapsed:s.collapsed,locked:document.pointerLockElement===h.renderer.domElement,
     foot:h.feet.toArray(),yaw:h.yawPitch.yaw,pitch:h.yawPitch.pitch,design:JSON.stringify(s.objects),revision:g.store.revision,tool:s.tool,method:s.method};});
  const initial=await state(),collapse='[data-garden-panel] [data-cmd=collapse]';
  await page.click(collapse);await page.waitForFunction(()=>__house.garden.state().collapsed&&!__house.garden.bird&&document.pointerLockElement===__house.renderer.domElement,{timeout:12000});
  const enter=await state();await page.mouse.move(515,339);await page.mouse.move(568,352,{steps:4});
  await page.waitForFunction(([y,p])=>Math.abs(__house.yawPitch.yaw-y)>.01&&Math.abs(__house.yawPitch.pitch-p)>.002,{},[enter.yaw,enter.pitch]);
  await page.keyboard.down('w');await new Promise(r=>setTimeout(r,480));await page.keyboard.up('w');
  const walked=await state();assert(Math.hypot(walked.foot[0]-enter.foot[0],walked.foot[2]-enter.foot[2])>.12,'The garden walker did not move');
  await page.screenshot({path:path.join(out,'garden-walk-'+stage+'.jpg'),type:'jpeg',quality:85});
  await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.pointerLockElement,{timeout:5000});assert((await state()).collapsed);
  await new Promise(r=>setTimeout(r,1150));await page.mouse.click(720,330);
  await page.waitForFunction(()=>document.pointerLockElement===__house.renderer.domElement,{timeout:7000});
  await page.keyboard.press('Tab');await page.waitForFunction(()=>!document.pointerLockElement&&__house.garden.bird&&!__house.garden.state().collapsed,{timeout:7000});
  const restored=await state();assert.equal(restored.design,initial.design);assert.equal(restored.revision,initial.revision);assert.equal(restored.method,initial.method);
  await page.click('[data-garden-panel] [data-cmd=view][data-val=stand]');
  await page.click(collapse);await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.pointerLockElement);
  await page.click(collapse);const standing=await state();assert.equal(standing.bird,false);assert.equal(standing.collapsed,false);
  assert.deepEqual(errors,[]);assert(!writes.includes('/layout'),'Navigation attempted to save a client layout');
  const result={page:page.url(),walkedMetres:Math.hypot(walked.foot[0]-enter.foot[0],walked.foot[2]-enter.foot[2]),yawChange:walked.yaw-enter.yaw,pitchChange:walked.pitch-enter.pitch,
    pointerLock:true,escape:true,recaptured:true,restoredPlan:true,restoredStanding:true,revision:initial.revision,designUnchanged:true};
  fs.writeFileSync(path.join(out,'garden-walk-'+stage+'.json'),JSON.stringify(result,null,2));console.log('PASS garden navigation',JSON.stringify(result));
 }finally{await browser.close();}
}
main().then(()=>process.exit(0),e=>{console.error(e);process.exit(1);});
