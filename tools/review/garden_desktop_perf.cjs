/* Profile the actual Wi-Fi garden page on this computer. See steady display intervals
 * separately from submitted primitives. Never save or modify an open client session. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.PUPPETEER_CORE||'puppeteer-core');
const [label='baseline',origin='https://192.168.1.118:8450',target='garden']=process.argv.slice(2);
assert(['house','garden','house-fixed','presentation'].includes(target));
assert(/^[a-z0-9-]+$/.test(label));assert(['https://192.168.1.118:8450','https://127.0.0.1:8450'].includes(origin));
const out=path.resolve(__dirname,'../../renders/garden-tool/performance');
async function main(){
 fs.mkdirSync(out,{recursive:true});const report={label,origin,viewport:[1200,750],dpr:2,profiles:{}};
 const browser=await puppeteer.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  args:['--ignore-certificate-errors','--use-angle=metal','--disable-background-networking','--disable-component-update','--disable-sync'],protocolTimeout:300000});
 try{
  const page=await browser.newPage();await page.setViewport({width:1200,height:750,deviceScaleFactor:2});await page.setCacheEnabled(false);await page.bringToFront();
  const models=[],errors=[];page.on('response',r=>{if(r.status()>=400)console.log('HTTP',r.status(),new URL(r.url()).pathname);});page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(new URL(r.url()).pathname.endsWith('.glb'))models.push([new URL(r.url()).pathname,Number(r.headers()['content-length'])]);});
  await page.setRequestInterception(true);page.on('request',r=>r.method()==='GET'&&(r.url().startsWith(origin+'/')||/^(data:|blob:)/.test(r.url()))?r.continue():r.abort());
  const time=Date.now();await page.goto(target==='presentation'&&origin.includes('192.168.')?origin+'/preview/?version=approved_2b':origin+'/house.html?site='+(target!=='garden'?'house':'house-wip')+'&version=approved_2b&mode=review'+(target==='garden'?'&garden=1':''),{waitUntil:'domcontentloaded'});
  await page.waitForFunction(target=>window.__house?.V?.model&&!document.querySelector('#startDesktop').disabled&&(target!=='garden'||__house.garden?.enabled),{timeout:160000},target);
  if(target!=='garden')await page.click('#startDesktop');report.bootMs=Date.now()-time;
  await page.waitForNetworkIdle({idleTime:350,timeout:90000});
  report.renderer=await page.evaluate(async ()=>{
    const h=__house,ctx=h.renderer.getContext(),d=ctx.getExtension('WEBGL_debug_renderer_info');
    const {EffectComposer}=await import('three/addons/postprocessing/EffectComposer.js');
    const composer=EffectComposer.prototype.render,cast=h.THREE.Raycaster.prototype.intersectObject;
    window.gardenMeasure={direct:false,casts:0,castMs:0,composes:0,sample:false};
    EffectComposer.prototype.render=function(...args){const m=gardenMeasure;m.composer=this;if(m.sample)m.composes++;return m.direct?h.renderer.render(h.scene,h.camera):composer.apply(this,args);};
    h.THREE.Raycaster.prototype.intersectObject=function(obj,...args){const m=gardenMeasure,measure=m.sample&&obj===h.V.model.root&&this.ray.direction.y>.999&&this.far===6;
      if(!measure)return cast.call(this,obj,...args);const start=performance.now(),v=cast.call(this,obj,...args);m.casts++;m.castMs+=performance.now()-start;return v;};
    return {gpu:d?ctx.getParameter(d.UNMASKED_RENDERER_WEBGL):ctx.getParameter(ctx.RENDERER),
      size:[h.renderer.domElement.width,h.renderer.domElement.height],browser:navigator.userAgent};
  });
  async function measure(name,direct,turn){
   const m=await page.evaluate(async ({direct,turn})=>{
    const h=__house,m=gardenMeasure;const next=()=>new Promise(resolve=>requestAnimationFrame(resolve));
    m.direct=direct;
    for(let i=0;i<20;i++)await next();m.casts=m.castMs=m.composes=0;m.sample=true;
    const dt=[],calls=[],tri=[],modeCounts={};let prev=await next();const yaw=h.yawPitch.yaw;
    for(let i=0;i<(turn?120:60);i++){
      if(turn)h.yawPitch.yaw=yaw+.045*Math.sin(i*Math.PI/30);
      const t=await next();dt.push(t-prev);prev=t;calls.push(h.renderer.info.render.calls);tri.push(h.renderer.info.render.triangles);const mode=h.desktop?.mode||'normal';modeCounts[mode]=(modeCounts[mode]||0)+1;
    }
    h.yawPitch.yaw=yaw;m.sample=false;
    const values=a=>{const b=[...a].sort((x,y)=>x-y);return {p50:b[Math.floor(b.length*.5)],p95:b[Math.floor(b.length*.95)],max:b.at(-1)};};
    return {ratio:h.renderer.getPixelRatio(),fps:1000*dt.length/dt.reduce((a,b)=>a+b,0),intervalMs:values(dt),drawCalls:values(calls),triangles:values(tri),roofCasts:m.casts,roofCastTotalMs:m.castMs,composes:m.composes,frames:dt.length,renderedFrames:calls.filter(n=>n>0).length,modeCounts};
   },{direct,turn});report.profiles[name]=m;console.log(name,JSON.stringify(m));
  }
  if(target!=='garden'){
    for(const [name,eye,targetPoint] of require('./furnish_cameras.cjs')){
      await page.evaluate(({eye,targetPoint})=>{const h=__house;
        if(!h.walk)h.setWalk(true);h.feet.set(eye[0],eye[1]-1.65,eye[2]);
        const [x,y,z]=targetPoint.map((v,i)=>v-eye[i]);h.yawPitch.yaw=Math.atan2(-x,-z);h.yawPitch.pitch=Math.atan2(y,Math.hypot(x,z));h.step(3);
      },{eye,targetPoint});
      if(target==='presentation'){
        const difference=await page.evaluate(()=>{
          const h=__house,r=h.renderer,g=h.furnishing.runtime.group,gl=r.getContext();
          function frame(on){
            g.userData.portalCull=on;r.render(h.scene,h.camera);
            const rgba=new Uint8Array(gl.drawingBufferWidth*gl.drawingBufferHeight*4);
            gl.readPixels(0,0,gl.drawingBufferWidth,gl.drawingBufferHeight,gl.RGBA,gl.UNSIGNED_BYTE,rgba);return rgba;
          }
          const a=frame(false),b=frame(true);let changed=0;
          for(let i=0;i<a.length;i+=4)if(a[i]!==b[i]||a[i+1]!==b[i+1]||a[i+2]!==b[i+2])changed++;
          return {changed,pixels:a.length/4};
        });
        console.log(name+' matched frames',difference);assert.equal(difference.changed,0,'Culling removed visible furniture at '+name);
        for(const on of [false,true]){
          const button=await page.$('#baAllLamps');if(await button.evaluate(b=>b.getAttribute('aria-pressed'))!==String(on))await button.click();
          await measure(name+(on?'-on':'-off'),false,true);
          const glow=await page.evaluate(()=>{const s=__house.look.snapshot();return {room:s.room,bulbs:s.emitters.map(e=>e.id),lamps:s.lamps.length};});
          if(on)assert(glow.bulbs.includes('LIV-TLAMP'),'The living lamp must glow even from the garden');else assert.equal(glow.bulbs.length,0);
        }
        continue;
      }
      if(target==='house-fixed'){
        await measure(name+'-walking',false,true);
        await measure(name+'-settled',false,false);
        continue;
      }
      const resolution=async(ratio,halfAO)=>page.evaluate(({ratio,halfAO})=>{const h=__house,c=gardenMeasure.composer;
        h.renderer.setPixelRatio(ratio);c?.setPixelRatio(ratio);
        const pass=c?.passes.find(p=>p.constructor.name==='GTAOPass');if(pass&&halfAO)pass.setSize(Math.round(innerWidth*ratio/2),Math.round(innerHeight*ratio/2));
      },{ratio,halfAO});
      await resolution(2,false);await measure(name+'-native',false,true);
      await measure(name+'-native-direct',true,true);
      await resolution(1.25,true);await measure(name+'-scaled-ao',false,true);await measure(name+'-scaled-direct',true,true);
    }
  } else {
  await measure('plan',false,false);
  await page.click('[data-cmd=collapse]');await page.waitForFunction(()=>__house.garden.state().collapsed&&!__house.garden.bird);
  await page.evaluate(()=>{const h=__house;h.feet.set(3.70,-.231,9.80);h.yawPitch.yaw=-.0312;h.yawPitch.pitch=-.0384;h.step(3);});
  await measure('walk',false,true);await measure('directComparison',true,true);
  }
  report.models=models;report.errors=errors;assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,label+'.json'),JSON.stringify(report,null,2));
 }finally{await browser.close();}
}
main().then(()=>process.exit(0),e=>{console.error(e);process.exit(1);});
