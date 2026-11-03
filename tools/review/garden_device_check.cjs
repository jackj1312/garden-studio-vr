/* Run sequentially on Jack's 8 GB Mac. The disposable test site shares only published model bytes. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.PUPPETEER_CORE||'puppeteer-core');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'renders/garden-tool');
const stage=process.argv[2]||'desktop',site=process.env.GARDEN_QA_SITE||'garden-qa-house',origin=process.env.STUDIO_URL||'https://127.0.0.1:8450';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await puppeteer.launch({executablePath:process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal'],protocolTimeout:300000});
 const errors=[];
 try{
  const page=await browser.newPage();page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});
  page.on('console',c=>{if(['error','warn'].includes(c.type())){const v=c.text();if(!v.includes('404')&&!v.includes('WebGL:')&&!v.includes('THREE.Clock'))console.log(c.type(),v.slice(0,310));if(/Shader Error|VALIDATE_STATUS|Unhandled/.test(v))errors.push(v.slice(0,250));}});
  const tablet=stage==='ipad',phone=stage==='phone',xr=stage==='quest';
  await page.setViewport(tablet?{width:1024,height:768,hasTouch:true,isMobile:true,deviceScaleFactor:1}:phone?{width:390,height:844,hasTouch:true,isMobile:true,deviceScaleFactor:1}:{width:1280,height:800,deviceScaleFactor:1});
  if(tablet||phone)await page.setUserAgent(tablet?'Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1':'Mozilla/5.0 (Linux; Android 14; Pixel) AppleWebKit/537.36 Chrome/134 Mobile Safari/537.36');
  const url=origin+'/house.html?'+new URLSearchParams({site,version:'approved_2b',mode:'review',garden:'1',capture:'1',...(xr?{xrsim:'1'}:{})});
  await page.goto(url,{waitUntil:'domcontentloaded',timeout:180000});
  await page.waitForFunction(()=>window.__house?.garden?.enabled&&window.__house.garden.plan.ready,{timeout:180000});
  const info=await page.evaluate(()=>({state:__house.garden.state().status,full:__house.garden.plan.full,plan:document.querySelector('#garden-plan').getBoundingClientRect().toJSON(),controls:document.querySelector('[data-garden-panel]').getBoundingClientRect().toJSON()}));
  console.log(stage,JSON.stringify(info));const g=(cb,...a)=>page.evaluate(cb,...a);
  const action=(n,v)=>page.evaluate(([n,v])=>__house.garden.action(n,v),[n,v]);
  const name=label=>'qa-'+stage+'-'+label;
  const tag=label=>action('field',{key:'label',value:name(label)});
  async function xy(x,z){return g(([x,z])=>{const c=document.querySelector('#garden-plan'),b=c.getBoundingClientRect(),p=__house.garden.plan,a=p.at(b.left,b.top),q=p.at(b.right,b.bottom);return {x:b.left+(x-a[0])/(q[0]-a[0])*b.width,y:b.top+(z-a[1])/(q[1]-a[1])*b.height};},[x,z]);}
  const client=await page.createCDPSession();
  async function gesture(points,type='mouse'){
    if(type==='mouse'){await page.mouse.move(points[0].x,points[0].y);await page.mouse.down();for(const p of points.slice(1))await page.mouse.move(p.x,p.y,{steps:4});await page.mouse.up();return;}
    if(type==='pen'){
      const send=(type,p,buttons)=>client.send('Input.dispatchMouseEvent',{type,x:p.x,y:p.y,pointerType:'pen',button:'left',buttons,force:buttons?.65:0});
      await send('mousePressed',points[0],1);
      if(points.length>1){
        await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:points[0].x+7,y:points[0].y+15,id:5}]});
        await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
      }
      for(const p of points.slice(1))await send('mouseMoved',p,1);
      await send('mouseReleased',points.at(-1),0);return;
    }
    const touch=(type,p)=>client.send('Input.dispatchTouchEvent',{type,touchPoints:p?[{x:p.x,y:p.y,id:0}]:[]});
    await touch('touchStart',points[0]);for(const p of points.slice(1))await touch('touchMove',p);await touch('touchEnd');
  }
  if(!xr){
    await page.click('[data-garden-panel] [data-editor-help=garden]');assert.match(await page.$eval('#studio-help-dialog',e=>e.innerText),/Apple Pencil/);await page.keyboard.press('Escape');
    for(const f of await g(()=>__house.garden.objects.filter(f=>f.label.startsWith('qa-')).map(f=>f.id))){await action('select',f);await action('delete');}
    await action('kind','sunken-area');await action('method','circle');
    const start=await xy(5.4,15.3),edge=await xy(6.75,15.3);
    await gesture([start,edge],tablet?'pen':phone?'touch':'mouse');
    const f=await g(()=>__house.garden.state().selected);assert.equal(f?.geometry.type,'circle','Pointer entry should create a circle');assert(Math.abs(f.geometry.radius-1.35)<.12);
    await tag('court');await action('field',{key:'level',value:-.6});await action('steps');
    const result=await g(()=>{const a=__house.garden,s=a.state().selected;return {floor:a.garden.heightAt(...s.geometry.center),base:s.baseY,cuts:a.garden.cuts().length,steps:s.steps};});assert(Math.abs(result.floor-result.base+.6)<.012);assert(result.cuts>=1&&result.steps?.count>=3);
    await action('kind','tree');await gesture([await xy(7.9,14.1)],tablet?'pen':phone?'touch':'mouse');await tag('tree');assert.equal((await g(()=>__house.garden.state().selected)).kind,'tree');
    await action('kind','planting-bed');await action('method','rectangle');await gesture([await xy(2.2,14),await xy(3.6,16.6)],tablet?'pen':phone?'touch':'mouse');await tag('bed');await action('field',{key:'palette',value:'warm'});
    await action('kind','wall');await action('method','curve');const samples=[];for(let j=0;j<=14;j++){const t=j/14;samples.push(await xy(1.1+4.1*t,18.1+.6*Math.sin(t*Math.PI)));}await gesture(samples,tablet?'pen':phone?'touch':'mouse');await tag('wall');
    const wall=await g(()=>__house.garden.state().selected);assert.equal(wall.geometry.type,'curve');await action('copy');await action('delete');await action('undo');await action('redo');
    await action('save');assert.equal(await g(()=>__house.garden.store.dirty),false);
    await action('select',f.id);await page.screenshot({path:path.join(out,stage+'-plan.png')});
    if(tablet||phone){
      const before=await g(()=>__house.garden.objects.length),target=await xy(4,9);
      await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:target.x-28,y:target.y,id:1},{x:target.x+28,y:target.y,id:2}]});
      await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:target.x-54,y:target.y,id:1},{x:target.x+54,y:target.y,id:2}]});
      await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});assert.equal(await g(()=>__house.garden.objects.length),before);
      if(tablet){await page.setViewport({width:768,height:1024,hasTouch:true,isMobile:true,deviceScaleFactor:1});await sleep(150);await page.screenshot({path:path.join(out,'ipad-portrait.png')});}
    }
    await action('view');await g(()=>{const h=__house;h.captureAt?.({x:7.1,z:18.2,y:-.231,yawDeg:32,pitchDeg:-29,eye:1.75,w:1024,h:650});});await sleep(250);
    await page.screenshot({path:path.join(out,stage+'-standing.png')});
    if(stage==='desktop'){
      const other=await browser.newPage();const api='/layout?site='+site+'&version=approved_2b';await other.goto(origin+api);const read=await other.evaluate(async()=>JSON.parse(document.body.innerText));assert(read.garden.objects.some(o=>o.id===f.id));await other.close();
      console.log('cross page saved objects',read.garden.objects.length,'revision',read.revision);
    }
  }else{
    await g(()=>__house.sim.wrist(true));await sleep(250);
    const actions=await g(()=>{const h=__house,a=h.garden;return {plan:a.plan.ready,wrist:!!a.wrist.wristWorld('How to use'),bird:a.bird};});console.log('XR',actions);
    const poke=async label=>{let dest=await g(label=>__house.garden.wrist.wristWorld(label)?.toArray(),label);assert(dest,'Wrist button '+label);await g(p=>__house.sim.aim(new __house.THREE.Vector3(...p)),dest);await sleep(100);await g(()=>__house.sim.press('trigger'));await sleep(140);};
    await page.screenshot({path:path.join(out,'quest-plan.png')});await poke('How to use');await page.screenshot({path:path.join(out,'quest-help.png')});
    console.log('wrist help opened');
  }
  assert.deepEqual(errors,[]);console.log('PASS',stage);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
