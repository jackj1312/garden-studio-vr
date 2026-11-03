/* Cold arrival through the measured garden door, porch and hall. No site writes. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.PUPPETEER_CORE||'puppeteer-core');
const [name='doorway',site='house']=process.argv.slice(2),origin=process.env.STUDIO_URL||'https://127.0.0.1:8450';
assert(/^[\w-]+$/.test(name)&&['house','house-preview'].includes(site));
const out=path.resolve(__dirname,'../../renders/garden-tool/performance');
async function main(){
 const browser=await puppeteer.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal'],protocolTimeout:90000});
 try{
  const page=await browser.newPage(),errors=[];await page.setViewport({width:1200,height:750,deviceScaleFactor:2});await page.setCacheEnabled(false);
  await page.setRequestInterception(true);page.on('request',r=>r.method()==='GET'&&(r.url().startsWith(origin+'/')||/^(blob:|data:)/.test(r.url()))?r.continue():r.abort());
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.text().startsWith('CROSS '))console.log(m.text());});
  const url=site==='house-preview'?origin+'/preview/?version=approved_2b':origin+'/house.html?site=house&version=approved_2b&mode=review';
  await page.goto(url,{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>window.__house?.V?.model&&!document.querySelector('#startDesktop').disabled,{timeout:150000});
  await page.click('#startDesktop');await page.evaluate(()=>document.exitPointerLock());await page.waitForNetworkIdle({idleTime:250});
  const result=await page.evaluate(async()=>{
    const h=__house,T=h.THREE;await h.furnishing.readyModels;
    h.V.doors.snapAll(true);h.feet.set(2.62,-.231,.94);h.yawPitch.yaw=-Math.PI/2;h.yawPitch.pitch=0;h.step(3);
    const next=()=>new Promise(requestAnimationFrame);for(let i=0;i<25;i++)await next();
    const pts=[[3.40,.94],[4.36,.94],[4.36,-.45],[4.36,-1.02]],rows=[],roomsSeen=new Set(),programs=[];
    let prev=await next();
    for(const [x,z] of pts){
     const start=h.feet.clone(),dist=Math.hypot(x-start.x,z-start.z),n=Math.ceil(dist/.035);
     h.yawPitch.yaw=Math.atan2(start.x-x,start.z-z);
     for(let i=1;i<=n;i++){
      const target=new T.Vector3(start.x+(x-start.x)*i/n,h.feet.y,start.z+(z-start.z)*i/n);
      h.walker.move(h.feet,target.sub(h.feet).setY(0));h.walker.settle(h.feet,1/60);
      const t=await next(),pose=h.camera.getWorldPosition(new T.Vector3()),room=h.V.model.roomAt(pose.x,pose.y,pose.z)?.id||'garden';
      const row={room,ms:Math.round(t-prev),feet:h.feet.toArray().map(v=>+v.toFixed(3)),programs:h.renderer.info.programs.length,
        calls:h.renderer.info.render.calls,lights:h.look.snapshot().windows.length};
      if(!roomsSeen.has(room)){console.log('CROSS '+room+' '+JSON.stringify(row));roomsSeen.add(room);}
      if(!programs.includes(row.programs))programs.push(row.programs);rows.push(row);prev=t;
     }
    }
    return {seen:[...roomsSeen],programs,final:h.feet.toArray(),worst:rows.slice().sort((a,b)=>b.ms-a.ms).slice(0,6),frames:rows.length};
  });
  fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,name+'.json'),JSON.stringify({...result,errors},null,2));
  console.log(JSON.stringify(result));assert.deepEqual(errors,[]);assert(result.seen.includes('R-g-hall'),'Could not walk into the hall');
  if(name!=='doorway-before')assert(result.worst[0].ms<=500,`Doorway frame took ${result.worst[0].ms} ms`);
 }finally{await browser.close();}
}
main().then(()=>process.exit(0),e=>{console.error(e);process.exit(1);});
