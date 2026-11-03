/* One local Chrome, one profile at a time. Run:
 * PUPPETEER_CORE=… node tools/review/quest_look_benchmark.cjs ROUND [SITE] [OUTPUT]
 *   [--profiles=off,on] [--reference=prior/benchmark.json] [--sun=afternoon|filmed]
 * Profiles are optional. A requested profile must be acknowledged by __house.look.
 * rAF wall time and render submission are desktop simulator measurements, not GPU time. */
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const path=require('node:path');
const puppeteer=require(process.env.PUPPETEER_CORE||'puppeteer-core');

const root=path.resolve(__dirname,'../..'),width=800,height=450,fov=60,warmFrames=24,frameCount=48;
const origin=new URL(process.env.STUDIO_URL||'https://127.0.0.1:8450');
if(origin.protocol!=='https:'||origin.port!=='8450'||!['localhost','127.0.0.1','[::1]'].includes(origin.hostname))throw Error('Use the loopback HTTPS server on 8450');
const args=process.argv.slice(2), positional=args.filter(a=>!a.startsWith('--')), options=new Map();
for(const arg of args.filter(a=>a.startsWith('--'))) {
  const match=/^--(profiles|reference|sun)=(.+)$/.exec(arg);
  if(!match||options.has(match[1]))throw Error('Invalid or repeated option '+arg);
  options.set(match[1],match[2]);
}
const [round,site='house',outputName='quest-look']=positional;
const valid=v=>typeof v==='string'&&/^[a-z\d][a-z\d_-]{0,63}$/i.test(v);
if(positional.length>3||![round,site,outputName].every(valid))throw Error('Expected ROUND [SITE] [OUTPUT] as simple names');
const profiles=options.has('profiles')?options.get('profiles').split(','):['current'];
if(profiles.length>4||new Set(profiles).size!==profiles.length||!profiles.every(valid))throw Error('Invalid look profiles');
const sun=options.get('sun')||'afternoon';
if(!['afternoon','filmed'].includes(sun))throw Error('Unknown sun preset');
const out=path.join(root,'renders/house-build/furnishing',round,outputName);
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const ua='Mozilla/5.0 (X11; Linux x86_64; Quest 3) AppleWebKit/537.36 Chrome/132 Mobile VR OculusBrowser/35.0 Safari/537.36';
const vectorDelta=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
const quatDot=(a,b)=>Math.min(1,Math.abs(a.reduce((t,v,i)=>t+v*b[i],0))/(Math.hypot(...a)*Math.hypot(...b)));

function canonicalCameras() {
  const table=require('./furnish_cameras.cjs');
  assert.deepEqual(table.map(c=>c[0]),['kitchen-diner','lounge','front-garden']);
  return table.map(([name,eye,target])=>{
    for(const v of [eye,target])assert(Array.isArray(v)&&v.length===3&&v.every(Number.isFinite));
    assert(vectorDelta(eye,target)>.1);return {name,eye,target};
  });
}
const cameras=canonicalCameras(),version=JSON.parse(fs.readFileSync(path.join(root,'assets/sites',site,'versions.json'))).default;
const reference=options.has('reference')?JSON.parse(fs.readFileSync(path.resolve(root,options.get('reference')))):null;
if(reference){
  assert.equal(reference.schema,1);assert.equal(reference.version,version);assert.equal(reference.sun,sun);
  assert.deepEqual(reference.cameras,cameras);assert.deepEqual(reference.viewport,[width,height]);assert.equal(reference.fov,fov);
}

async function run(){
  fs.mkdirSync(out,{recursive:true});
  const browser=await puppeteer.launch({headless:true,executablePath:process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    protocolTimeout:300000,args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal',
      '--disable-background-timer-throttling','--disable-backgrounding-occluded-windows']});
  const report={schema:1,round,site,version,sun,viewport:[width,height],fov,cameras,
    cameraSource:'tools/review/furnish_cameras.cjs',cameraTableSha256:hash(JSON.stringify(cameras)),
    sample:{renderer:'Studio real xrsim input/frame loop; desktop headless Chrome, one simulated eye',userAgent:ua,
      warmFrames,frameCount,frameInterval:'Consecutive requestAnimationFrame timestamps; all slow intervals included',
      submission:'Host renderMs measured around renderer.render, CPU submission only',draws:'reset once per normal app frame; separate explicit framebuffer draw'},
    poses:{},profiles:{},browser:await browser.version()};
  try {
    for(const profile of profiles) {
      const context=await browser.createBrowserContext();
      try {
        const page=await context.newPage(),errors=[],responses=new Map();
        await page.setViewport({width,height,deviceScaleFactor:1});
        await page.setUserAgent(ua);await page.bringToFront();
        await page.setRequestInterception(true);
        page.on('request',r=>{
          const u=r.url();
          if(!u.startsWith(origin.origin+'/')&&!/^(?:blob:|data:|about:)/.test(u))return r.abort();
          if(r.method()==='POST' && new URL(u).pathname==='/house/perf')return r.respond({status:204});
          if(!['GET','HEAD'].includes(r.method()))return r.abort();
          return r.continue();
        });
        page.on('response',r=>{if(new URL(r.url()).pathname.endsWith('.glb'))responses.set(r.url(),{status:r.status(),bytes:r.headers()['content-length']||null});});
        page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE ERROR',e.message);});
        page.on('console',m=>{if(/shader error|validate_status.*false|uncaught \(in promise\)/i.test(m.text()))errors.push(m.text().slice(0,240));});
        const url=new URL('/house.html',origin);
        url.search=new URLSearchParams({site,version,mode:'review',capture:'1',xrsim:'1',sun,...(profile==='current'?{}:{look:profile})}).toString();
        await page.goto(url.href,{waitUntil:'domcontentloaded',timeout:180000});
        await page.waitForFunction(version=>{
          const h=window.__house;
          return h?.V?.def.id===version&&h.captureState().ready&&h.inVR()&&h.hands.left&&h.hands.right&&
            h.autoHeightAt===0&&h.V.file&&!document.hidden;
        },{timeout:200000},version);
        const meta=await page.evaluate(async ({profile,width,height,fov})=>{
          const h=__house;
          if(profile!=='current'&&(h.look?.snapshot?.()?.profile??h.look?.profile)!==profile)
            throw Error('Viewer did not acknowledge requested room-light profile '+profile);
          h.sim.wrist(false);h.sim.aim(null);h.sim.stick('left',0,0);h.sim.stick('right',0,0);
          h.card.hide();h.setStage(h.stageN);h.setUnfurnished(false);h.V.doors?.snapAll(false);
          if(h.furnishing) await h.furnishing.readyModels;
          if(h.V.def.furnish_runtime&&(!h.furnishing?.layout?.loaded||!h.furnishing.runtime?.group.visible))
            throw Error('Runtime furnishing was not loaded');
          h.renderer.setPixelRatio(1);h.renderer.setSize(width,height,false);
          h.camera.fov=fov;h.camera.aspect=width/height;h.camera.updateProjectionMatrix();h.step(2);
          if(!h.V.def.glb_quest_meshopt||h.V.file!==h.V.def.glb_quest_meshopt)throw Error('Quest meshopt twin not loaded: '+h.V.file);
          if(!h.cull?.enabled||!h.cull.state.active||h.section.active||h.xray||h.garden?.enabled||h.furnishing?.enabled)throw Error('Benchmark requires the ordinary finished, culled walk');
          const items=h.furnishing?.layout?.items??[];
          const rendered=new Set(h.furnishing?.runtime?.group.children.flatMap(b=>b.visible&&b.count?b.userData.furnishItems?.map(v=>v.id)||[]:[])||[]);
          if(h.V.def.furnish_runtime&&items.length&&!rendered.size)throw Error('No furnished runtime instances');
          const baked=new Set(h.V.model.parts.filter(p=>h.isLoose(p)&&p.now.visible).map(p=>p.ud.spec_id||p.element));
          return {loadedMeshopt:h.V.file,itemCount:h.V.def.furnish_runtime?items.length:baked.size,
            runtimeRenderedItemCount:rendered.size,looseBakedItemCount:baked.size,layoutRevision:h.furnishing?.layout?.revision??null,
            layout:{items:items.map(i=>[i.id,i.catalogueId,i.variant,i.position,i.rotation,i.room,i.size,i.host,i.finishes,i.lampOn]),
              wallColours:h.furnishing?.layout?.wallColours??{},roomFloors:h.furnishing?.layout?.roomFloors??{}},
            asBuilt:h.V.model.asBuilt??h.V.asBuilt??null,stage:h.stage,stageN:h.stageN,
            shadowEnabled:h.renderer.shadowMap.enabled,pixelRatio:h.renderer.getPixelRatio(),multiDraw:h.renderer.extensions.has('WEBGL_multi_draw'),
            rendererViewport:[h.renderer.domElement.width,h.renderer.domElement.height],floorOffset:h.floorOffset,
            geometryCount:h.renderer.info.memory.geometries,textureCount:h.renderer.info.memory.textures};
        },{profile,width,height,fov});
        assert.deepEqual(meta.rendererViewport,[width,height]);assert.equal(meta.stage,meta.stageN);
        const meshUrl=new URL('/assets/sites/'+site+'/'+meta.loadedMeshopt,origin).href,meshResponse=responses.get(meshUrl);
        assert(meshResponse&&meshResponse.status>=200&&meshResponse.status<300,'No successful meshopt response for '+meshUrl);
        await page.waitForNetworkIdle({idleTime:650,timeout:120000});
        meta.loadedResponse={url:meshUrl,...meshResponse};
        meta.layout.items.sort((a,b)=>a[0].localeCompare(b[0]));
        meta.layoutSha256=hash(JSON.stringify(meta.layout));delete meta.layout;
        const priorProfiles=reference?.profiles||report.profiles;
        const priorName=Object.hasOwn(priorProfiles,profile)?profile:Object.hasOwn(priorProfiles,'current')?'current':Object.keys(priorProfiles)[0];
        if(reference && !Object.hasOwn(priorProfiles,profile)&&!Object.hasOwn(priorProfiles,'current')&&Object.keys(priorProfiles).length>1)
          throw Error('Reference has several look profiles and none match '+profile);
        const comparable=priorProfiles[priorName];
        if(comparable) {
          assert.equal(meta.itemCount,comparable.meta.itemCount,'Comparisons need the same furnishing count');
          assert.equal(meta.layoutSha256,comparable.meta.layoutSha256,'Comparisons need the same furnishing and finish state');
          assert.equal(meta.asBuilt,comparable.meta.asBuilt);assert.deepEqual(meta.rendererViewport,comparable.meta.rendererViewport);
        }
        const result=report.profiles[profile]={meta,comparison:comparable?{round:reference?.round||round,output:reference?options.get('reference'):outputName,profile:priorName}:null,scenes:{}};
        for(const camera of cameras){
          const savedPose=report.poses[camera.name]||reference?.poses?.[camera.name]||null;
          const shot=await page.evaluate(async ({definition,restore,warmFrames,frameCount,width,height,fov,profile})=>{
            const h=__house,T=h.THREE, {eye,target}=definition;
            const poseOf=o=>({position:o.position.toArray(),quaternion:o.quaternion.toArray(),scale:o.scale.toArray()});
            const install=(o,s)=>{o.position.fromArray(s.position);o.quaternion.fromArray(s.quaternion);o.scale.fromArray(s.scale);o.updateMatrix();};
            function pose(){
              h.player.updateMatrixWorld(true);h.camera.updateMatrixWorld(true);
              return {rig:poseOf(h.player),camera:poseOf(h.camera),feet:h.feet.toArray(),yaw:h.yawPitch.yaw,pitch:h.yawPitch.pitch,
                eye:h.camera.getWorldPosition(new T.Vector3()).toArray(),orientation:h.camera.getWorldQuaternion(new T.Quaternion()).toArray()};
            }
            if(restore) {
              h.feet.fromArray(restore.feet);h.yawPitch.yaw=restore.yaw;h.yawPitch.pitch=restore.pitch;
              install(h.player,restore.rig);install(h.camera,restore.camera);
            }else{
              const [x,y,z]=eye, direction=new T.Vector3().fromArray(target).sub(new T.Vector3().fromArray(eye)).normalize();
              const yaw=Math.atan2(-direction.x,-direction.z),pitch=Math.asin(direction.y);
              // Let the real walker settle on the measured floor; retain the
              // exact authored world eye even if a room's FFL differs from −0.10.
              const floor=h.walker.supportAt(x,y-1.6,z,1.2)??y-1.6;
              h.feet.set(x,floor,z);h.yawPitch.yaw=yaw;h.yawPitch.pitch=pitch;
              h.player.position.set(x,floor+h.floorOffset,z);h.player.quaternion.setFromAxisAngle(new T.Vector3(0,1,0),yaw);
              h.camera.position.set(0,y-h.player.position.y,0);h.camera.rotation.set(pitch,0,0,'YXZ');
            }
            h.camera.fov=fov;h.camera.aspect=width/height;h.camera.updateProjectionMatrix();h.card.hide();h.sim.wrist(false);
            const initial=pose(), eyedelta=(a,b)=>Math.hypot(...a.map((n,i)=>n-b[i]));
            if(eyedelta(initial.eye,eye)>.0005)throw Error('Could not place the signed eye '+definition.name);
            const aim=new T.Vector3().fromArray(target).sub(new T.Vector3().fromArray(eye)).normalize();
            if(h.camera.getWorldDirection(new T.Vector3()).dot(aim)<.999999)throw Error('Wrong signed camera orientation '+definition.name);
            // Refresh cached illumination at the new position before timings.
            h.renderer.shadowMap.needsUpdate=true;
            const rows=[];
            await new Promise((resolve,reject)=>{
              let prev=null,passed=0,previousRender=-1;
              function sample(time) {
                try {
                  if(document.hidden||!h.inVR()||!h.cull.state.active||h.V.doors?.moving||h.furnishing?.enabled)throw Error('Lost ordinary culled XR frame');
                  const stats=h.renderer.info.render;
                  if(passed>=warmFrames&&prev!==null) {
                    if(!stats.calls||!stats.triangles||stats.frame===previousRender)throw Error('Animation loop did not draw a new XR frame');
                    const interval=time-prev;
                    if(!Number.isFinite(interval)||interval<=0||!Number.isFinite(h.renderMs))throw Error('Invalid frame timing');
                    rows.push({interval,submission:h.renderMs,calls:stats.calls,triangles:stats.triangles});
                  }
                  previousRender=stats.frame;prev=time;passed++;
                  if(rows.length===frameCount)return resolve();
                  requestAnimationFrame(sample);
                } catch(e) {reject(e);}
              }
              requestAnimationFrame(sample);
            });
            const final=pose();
            const dot=Math.min(1,Math.abs(initial.orientation.reduce((s,n,i)=>s+n*final.orientation[i],0)));
            if(eyedelta(final.eye,eye)>.001||eyedelta(final.rig.position,initial.rig.position)>.001||dot<.999999)
              throw Error('Rig drifted during '+definition.name+' sample '+JSON.stringify({initial:initial.eye,final:final.eye,dot}));
            // Capture immediately after a single explicit native render. The
            // JPEG serialization and extra draw are outside the timing samples.
            h.renderer.info.reset();h.renderer.render(h.scene,h.camera);
            const jpeg=h.renderer.domElement.toDataURL('image/jpeg',.90);
            const thumb=document.createElement('canvas');thumb.width=20;thumb.height=12;
            const pixels=thumb.getContext('2d');pixels.drawImage(h.renderer.domElement,0,0,thumb.width,thumb.height);
            const rgba=pixels.getImageData(0,0,thumb.width,thumb.height).data,luma=[];
            for(let i=0;i<rgba.length;i+=4)luma.push(Math.round((.2126*rgba[i]+.7152*rgba[i+1]+.0722*rgba[i+2])));
            if(Math.max(...luma)-Math.min(...luma)<9)throw Error('Nearly uniform simulator framebuffer');
            const info=h.renderer.info.render;
            function stats(key) {
              const data=rows.map(r=>r[key]).sort((a,b)=>a-b), mid=data.length/2;
              return {median:(data[mid-1]+data[mid])/2,p95:data[Math.ceil(data.length*.95)-1],min:data[0],max:data[data.length-1]};
            }
            return {jpeg,initial,final,frames:rows.length,lumaRange:[Math.min(...luma),Math.max(...luma)],frameIntervalMs:stats('interval'),renderSubmitMs:stats('submission'),
              frameDrawCalls:stats('calls'),frameTriangles:stats('triangles'),captureDrawCalls:info.calls,captureTriangles:info.triangles,
              culling:{active:h.cull.state.active,cells:[...h.cull.state.cells]},look:h.look?.snapshot?.()??h.look?.profile??null,
              visibleRuntimeObjects:h.furnishing?.runtime?.group.children.filter(b=>b.visible&&b.count).length??0};
          },{definition:camera,restore:savedPose,warmFrames,frameCount,width,height,fov,profile});
          const {jpeg,initial,final,...metrics}=shot;
          assert.equal(metrics.frames,frameCount);assert(metrics.captureDrawCalls>0&&metrics.captureTriangles>0);
          assert(nearPose(initial,final));if(savedPose)assert(nearPose(savedPose,initial),'Restored pose differs');
          report.poses[camera.name]??=initial;
          const bytes=Buffer.from(jpeg.split(',')[1],'base64');assert(bytes.length>3500);assert.equal(bytes.readUInt16BE(0),0xffd8);
          const file=profile+'-'+camera.name+'.jpg';fs.writeFileSync(path.join(out,file),bytes);
          const entry=result.scenes[camera.name]={...metrics,eye:final.eye,orientation:final.orientation,frame:{file,sha256:hash(bytes),bytes:bytes.length}};
          const prior=comparable?.scenes?.[camera.name];
          if(prior)entry.delta={captureDrawCalls:entry.captureDrawCalls-prior.captureDrawCalls,captureTriangles:entry.captureTriangles-prior.captureTriangles,
            medianFrameIntervalMs:entry.frameIntervalMs.median-prior.frameIntervalMs.median,p95FrameIntervalMs:entry.frameIntervalMs.p95-prior.frameIntervalMs.p95,
            medianSubmitMs:entry.renderSubmitMs.median-prior.renderSubmitMs.median,p95SubmitMs:entry.renderSubmitMs.p95-prior.renderSubmitMs.p95,
            sameEncodedFrame:entry.frame.sha256===prior.frame.sha256};
          console.log(profile,camera.name,entry.captureDrawCalls,'draws',entry.captureTriangles,'triangles;',
            'rAF median/p95',entry.frameIntervalMs.median.toFixed(2),entry.frameIntervalMs.p95.toFixed(2),'ms');
        }
        assert.equal(new Set(Object.values(result.scenes).map(s=>s.frame.sha256)).size,cameras.length,'Repeated framebuffer at different room poses');
        assert.deepEqual(errors,[]);
      } finally {await context.close();}
    }
    fs.writeFileSync(path.join(out,'benchmark.json'),JSON.stringify(report,null,2)+'\n');
    console.log('PASS simulated Quest benchmark',out);
  }finally{await browser.close();}
}
function nearPose(a,b) {
  return ['eye','feet'].every(k=>vectorDelta(a[k],b[k])<.001)&&quatDot(a.orientation,b.orientation)>.999999&&
    ['rig','camera'].every(k=>vectorDelta(a[k].position,b[k].position)<.001&&quatDot(a[k].quaternion,b[k].quaternion)>.999999);
}
run().catch(e=>{console.error(e);process.exitCode=1;});
