/* Stage 4 look and control acceptance. One local Chrome, profiles run serially.
 * node tools/review/look_flow.cjs [ROUND=look] [SITE=house] [desktop|phone|xr|all]
 * All requests that could write are blocked, including marks, layouts and telemetry.
 */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const puppeteer=require(process.env.PUPPETEER_CORE||'puppeteer-core');
const [round='look',site='house',mode='all']=process.argv.slice(2);
if(![round,site].every(v=>/^[\w-]+$/.test(v))||!['desktop','phone','xr','all'].includes(mode))throw Error('Expected ROUND SITE [desktop|phone|xr|all]');
const ROOT=path.resolve(__dirname,'../..'),out=path.join(ROOT,'renders/house-build/furnishing',round,'look-flow');
const origin=new URL(process.env.STUDIO_URL||'https://127.0.0.1:8450');
if(origin.protocol!=='https:'||!['127.0.0.1','localhost','[::1]'].includes(origin.hostname)||origin.port!=='8450')throw Error('Use the local test server on port 8450');
const def=JSON.parse(fs.readFileSync(path.join(ROOT,'assets/sites',site,'versions.json')));
const living='R-g-living',bedroom='R-f-bedroom-1-front-left';
const wait={timeout:150000},near=(a,b,t)=>Math.abs(a-b)<=t;

function installPageChecks(){
  const h=window.__house,T=h.THREE,v=()=>new T.Vector3();
  function active(o){for(let p=o;p;p=p.parent)if(!p.visible)return false;return true;}
  function modelBox(id){
    const box=new T.Box3();
    for(const p of h.V.model.parts)if(p.now.visible&&(p.ud.spec_id===id||p.element==='SPEC-'+id))box.union(p.bbox);
    for(const b of h.furnishing?.runtime?.group.children||[]){
      if(!b.isInstancedMesh||!active(b))continue;
      const i=b.userData.furnishItems?.findIndex(x=>x.id===id);
      if(!(i>=0&&i<b.count))continue;
      b.geometry.computeBoundingBox();const m=new T.Matrix4();b.getMatrixAt(i,m);m.premultiply(b.matrixWorld);
      box.union(b.geometry.boundingBox.clone().applyMatrix4(m));
    }
    return box.isEmpty()?null:box;
  }
  function snapshot(){
    const s=h.look.snapshot(),eye=h.camera.getWorldPosition(v()),room=h.V.model.roomAt(eye.x,eye.y,eye.z)?.id||null;
    const effects=[],extraPointLights=[];
    h.scene.updateMatrixWorld(true);
    h.scene.traverse(o=>{
      if(!active(o))return;
      const tag=o.userData.studioLight;
      const direct=!!(o.isPointLight||o.isSpotLight);
      if(direct&&!tag)extraPointLights.push({name:o.name,intensity:o.intensity});
      if(!tag)return;
      const at=o.getWorldPosition(v()).toArray(),bounds=o.isMesh?new T.Box3().setFromObject(o,true):null,owner=tag.type==='emitter'?modelBox(tag.id):null;
      effects.push({type:tag.type,id:tag.id,room:tag.room,at,intensity:o.intensity??null,direct,lightType:o.type,mesh:!!o.isMesh,
        shadow:!!o.castShadow,isBasic:!!o.material?.isMeshBasicMaterial,colour:o.material?.color?.toArray()||o.color?.toArray()||null,
        emissive:o.material?.emissive?.toArray()||null,ownerDistance:bounds&&owner?owner.distanceToPoint(bounds.getCenter(v())):null});
    });
    const windows=(s.windows||s.apertures||[]).map(a=>{
      const fixture=h.V.model.table.get(a.fixture)||[...h.V.model.table.values()].find(e=>e.type==='fixture'&&e.params?.opening===a.id);
      const opening=h.V.model.table.get(fixture?.params?.opening||a.id),host=h.V.model.table.get(opening?.params?.host);
      const geometry=h.V.model.parts.filter(p=>p.element===(fixture?.id||a.fixture)&&p.now.visible&&/glass|glaz/i.test(p.materialName+' '+p.name));
      const centre=a.centre,position=a.position,axis=a.inward;
      let station=null;
      if(host?.params?.start&&centre){
        const [x,z]=host.params.start,[u,v]=host.params.end,len=Math.hypot(u-x,v-z);
        if(len)station=((centre[0]-x)*(u-x)+(centre[2]-z)*(v-z))/len;
      }
      const roof=geometry.find(p=>p.group==='rooflight'),roofDistance=roof&&centre?roof.bbox.distanceToPoint(v().fromArray(centre)):null;
      return {...a,fixtureId:fixture?.id||geometry[0]?.element,openingId:opening?.type==='opening'?opening.id:null,opening:opening?.type==='opening'?opening.params:null,roofDistance,
        storeyBase:host?.params?.base,station,visibleFixtureParts:geometry.length,
        positiveInset:centre&&position&&axis?axis.reduce((n,x,i)=>n+x*(position[i]-centre[i]),0):null,
        inside:position?h.V.model.roomAt(...position)?.id:null};
    });
    return {version:h.V.def.id,room,announcedRoom:s.room,eye:eye.toArray(),profile:s.profile,ao:s.gtao,neutral:h.renderer.toneMapping===T.NeutralToneMapping,
      exposure:h.renderer.toneMappingExposure,windows,effects,extraPointLights,
      lamps:s.lamps.map(x=>({id:x.id,room:x.room,kind:x.kind,on:x.on,visible:x.visible})),budget:s.budget,
      terrainVisible:h.V.model.root.visible,cullEnabled:!!h.cull?.enabled,
      furniture:h.unfurnished?0:(h.furnishing?.runtime?.group.children.filter(o=>active(o)&&o.count>0).length||0),
      title:{id:document.querySelector('#studioRoomTitle')?.dataset.roomId,name:document.querySelector('.room-title-name')?.textContent?.trim(),
        visible:document.querySelector('#studioRoomTitle')?.dataset.visible}};
  }
  function tracePass(){
    const r=h.renderer,orig=r.renderBufferDirect,p={normal:0,ao:0,uniforms:null,lit:0};
    r.renderBufferDirect=function(cam,scene,geom,mat,obj,g){
      const before=r.info.render.calls,res=orig.call(r,cam,scene,geom,mat,obj,g),draws=r.info.render.calls-before;
      if(draws>0){
        if(mat.isMeshNormalMaterial)p.normal+=draws;
        if(mat.isShaderMaterial && mat.uniforms?.tDepth && mat.uniforms?.tNormal && mat.uniforms?.distanceExponent && mat.uniforms?.radius){
          p.ao+=draws;p.uniforms={radius:mat.uniforms.radius.value,distanceExponent:mat.uniforms.distanceExponent.value,thickness:mat.uniforms.thickness.value};
        }
        if(mat.isMeshStandardMaterial)p.lit+=draws;
      }
      return res;
    };
    try{h.step(1);}finally{r.renderBufferDirect=orig;}
    return p;
  }
  function aimLamp(xr){
    const s=h.look.snapshot(),source=xr?h.hands.right.getWorldPosition(v()):h.camera.getWorldPosition(v());
    const lamps=s.lamps.filter(l=>l.room===h.V.model.roomAt(...h.camera.getWorldPosition(v()).toArray())?.id && l.visible!==false);
    for(const l of lamps){
      const box=modelBox(l.id);if(!box)continue;
      const c=box.getCenter(v()),size=box.getSize(v());
      for(const a of [.35,0,-.28,.46]){
        const p=c.clone().addScaledVector(new T.Vector3(0,1,0),size.y*a);
        const ray=new T.Ray(source.clone(),p.clone().sub(source).normalize()),solid=h.pickRay(ray);
        const piece=h.furnishing?.runtime?.pick(ray,solid?.distance??Infinity);
        const id=piece?.id||h.V.model.parts[solid?.part]?.ud.spec_id;
        if(id!==l.id)continue;
        if(xr){h.sim.aim(p);h.step(2);}
        else{
          h.camera.lookAt(p);h.camera.updateMatrixWorld(true);
          const e=new T.Euler().setFromQuaternion(h.camera.getWorldQuaternion(new T.Quaternion()),'YXZ');
          h.yawPitch.yaw=e.y;h.yawPitch.pitch=e.x;
        }
        return {id:l.id,point:p.toArray()};
      }
    }
    return null;
  }
  window.lookChecks={snapshot,tracePass,aimLamp};
}
async function assertPass(page,device){
  const actual=await page.evaluate(()=>lookChecks.tracePass()),snap=await page.evaluate(()=>lookChecks.snapshot());
  assert.equal(snap.neutral,true);assert.equal(snap.profile,'on');assert(snap.exposure>0&&Number.isFinite(snap.exposure));
  assert(actual.lit>0,'No house materials drew');
  if(device==='desktop'){
    assert(snap.ao.enabled&&actual.normal>0&&actual.ao>0,'Desktop frame did not submit the GTAO geometry + shader passes');
    for(const k of ['radius','distanceExponent','thickness'])assert(near(actual.uniforms[k],snap.ao[k],1e-5),'GTAO '+k+' was not applied');
  }else{assert.equal(snap.ao.enabled,false);assert.equal(actual.normal,0);assert.equal(actual.ao,0);}
  return actual;
}
function assertEffects(s,device,{on=false,windows=true}={}){
  assert.equal(s.room,s.announcedRoom,'Lighting selection differs from the real room geometry');
  assert(s.cullEnabled&&s.terrainVisible,'Expected the normal staged walkthrough');
  const wins=s.effects.filter(x=>x.type==='window'&&x.direct&&x.intensity>0),direct=s.effects.filter(x=>x.type==='practical'&&x.direct&&x.intensity>0),
    emit=s.effects.filter(x=>x.type==='emitter'&&x.mesh);
  if(device==='desktop'&&windows){
    assert(s.windows.length>0&&s.windows.length<=3,'Expected 1–3 actual window sources in '+s.room);
    for(const a of s.windows){
      assert(a.fixtureId&&a.visibleFixtureParts>0,'A window light has no built glazed fixture: '+a.id);
      assert(a.area>0&&a.positiveInset>.015&&a.inside===a.room,'Daylight must face into its measured room: '+a.id);
      if(a.openingId){
        assert(a.station>=a.opening.offset-.08&&a.station<=a.opening.offset+a.opening.width+.08,'Daylight centre is outside its measured opening: '+a.id);
        assert(a.centre[1]>=a.opening.sill-.04&&a.centre[1]<=a.opening.head+.04,'Daylight source height is outside its measured opening: '+a.id);
      }else assert(a.roofDistance!=null&&a.roofDistance<.02,'No measured opening or roof glazing at '+a.id);
      const actual=wins.find(x=>x.id===a.id);assert(actual&&Math.hypot(...actual.at.map((v,i)=>v-a.position[i]))<.005&&actual.intensity>0,'No active source at '+a.id);
    }
  }else if(device!=='desktop'){assert.equal(wins.length,0);assert.equal(s.windows.length,0);}
  assert(direct.length<=(device==='desktop'?2:1),'Practical light budget exceeded');
  if(on){
    assert(direct.some(x=>x.room===s.room),'No practical light reached the lamp room');
    assert(emit.length>0,'No visible physical lamp emitter');
    for(const e of emit){
      assert(s.lamps.some(l=>l.id===e.id&&l.on),'Unswitched lamp emissive: '+e.id);
      assert(e.ownerDistance!=null && e.ownerDistance<.12,'Emitter is detached from its real fitting: '+e.id);
      assert(e.colour && e.colour[0]>e.colour[2] && e.colour[0]>0,'Lamp has no warm visible emission: '+e.id);
    }
    if(device!=='desktop')assert(direct.every(x=>!x.shadow),'Mobile/Quest lamp casts an extra shadow');
  }else{assert.equal(direct.length,0);assert.equal(emit.length,0);}
  if(device==='xr'&&!on)assert.equal(s.extraPointLights.filter(p=>p.intensity>0).length,0,'Extra untagged Quest PointLight');
}
async function profile(browser,device){
  const context=await browser.createBrowserContext(),page=await context.newPage(),state={},errors=[],posts=[];
  let blockedGLB=null,blockedFurnish=null,hold=device==='desktop',holdFurnish=hold;
  const base='/assets/sites/'+site+'/',selected=def.versions.find(v=>v.id===def.default);
  const shellRequest=req=>new URL(req.url()).pathname===base+selected.glb;
  const furnitureRequest=req=>{const path=new URL(req.url()).pathname;return path.startsWith(base+'furnish/models/')&&path.endsWith('.gltf');};
  const url=new URL('/house.html',origin);
  url.search=new URLSearchParams({mode:'review',site,version:def.default,look:'on',...(device==='xr'?{xrsim:'1',glb:'meshopt'}:{})}).toString();
  async function snap(){return page.evaluate(()=>lookChecks.snapshot());}
  async function ui(selector){
    const visible=()=>page.$eval(selector,e=>!e.hidden&&e.getBoundingClientRect().height>0&&getComputedStyle(e).visibility==='visible');
    if(!(await visible())){
      await page.waitForSelector('#baToolsToggle',{visible:true,timeout:8000});
      if(device==='phone')await page.tap('#baToolsToggle');else await page.click('#baToolsToggle');
    }
    await page.waitForFunction(sel=>{
      const e=document.querySelector(sel),r=e?.getBoundingClientRect();
      return r&&r.width>0&&r.height>0&&r.left>=-1&&r.top>=-1&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1&&e.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));
    },{timeout:12000},selector);
  }
  async function click(selector){
    await ui(selector);if(device==='phone')await page.tap(selector);else await page.click(selector);
  }
  async function release(){
    await page.keyboard.press('Escape');await page.evaluate(()=>{if(document.pointerLockElement)document.exitPointerLock();document.activeElement?.blur?.();});
  }
  async function waitRoom(room){
    await page.waitForFunction(r=>{
      const h=window.__house,s=h.look.snapshot(),p=h.camera.getWorldPosition(new h.THREE.Vector3());
      return s.room===r&&h.V.model.roomAt(p.x,p.y,p.z)?.id===r;
    },wait,room);
  }
  async function visibleTitle(room){
    const result=await page.waitForFunction(({room,before,after})=>{
      const h=window.__house,measured=h.V.model.table.get(room),card=document.querySelector('#studioRoomTitle');
      if(!measured||!card||card.dataset.roomId!==room||card.dataset.visible!=='true')return false;
      const name=measured.params.name,storey=measured.params.storey,version=h.V.def.id;
      const label=version===before?'Before':version===after?'After':h.V.def.name;
      const floor={ground:'Ground floor',first:'First floor',second:'Second floor'}[storey];
      const title=card.querySelector('.room-title-name').textContent.trim(),detail=card.querySelector('.room-title-detail').textContent.trim();
      if(!floor||title!==name.charAt(0).toUpperCase()+name.slice(1)||detail!==label+' · '+floor)return false;
      const bounds=card.getBoundingClientRect(),style=getComputedStyle(card);
      if(style.display==='none'||style.visibility!=='visible'||Number(style.opacity)<.5||bounds.width<=0||bounds.height<=0||
        bounds.left<0||bounds.right>innerWidth||bounds.top<0||bounds.bottom>innerHeight)return false;
      return {room,version,storey,title,detail,visible:true};
    },{timeout:12000},{room,before:def.as_built_now,after:def.default});
    (state.titles??=[]).push(await result.jsonValue());await result.dispose();
  }
  async function headsetTitle(room){
    const title=await page.waitForFunction(r=>{
      const h=__house,mesh=h.camera.getObjectByName('Passive studio room title'),card=document.querySelector('#studioRoomTitle');
      if(!mesh?.visible||mesh.parent!==h.camera||mesh.material.opacity<.5||!mesh.material.map?.isCanvasTexture||
        card.dataset.roomId!==r||h.sim.wristUp||h.card.mesh.visible||h.gotoMenu.isOpen)return false;
      return {room:r,label:card.querySelector('.room-title-name').textContent,detail:card.querySelector('.room-title-detail').textContent,
        headRelative:mesh.position.toArray()};
    },{timeout:10000},room);
    const result=await title.jsonValue();await title.dispose();
    if(room===living){
      result.hiddenByWrist=await page.evaluate(()=>{
        const h=__house;h.sim.wrist(true);h.step(2);
        return !!(h.baPanel.visible&&!h.camera.getObjectByName('Passive studio room title').visible);
      });
      assert(result.hiddenByWrist,'A visible wrist panel did not suppress the passive room title');
    }else{
      await page.waitForFunction(()=>{
        const h=__house;return !h.sim.wristUp&&!h.card.mesh.visible&&!h.gotoMenu.isOpen&&!h.camera.getObjectByName('Passive studio room title').visible;
      },{timeout:7000});result.faded=true;
    }
    (state.titles??=[]).push(result);
  }
  async function screenshot(){
    const file=path.join(out,device+'-room-lamps.png');
    if(device!=='xr'){await page.screenshot({path:file});return;}
    const {url,...frame}=await page.evaluate(()=>{
      const h=__house;h.step(2);h.renderer.info.reset();h.renderer.render(h.scene,h.camera);
      const canvas=h.renderer.domElement,pos=h.camera.getWorldPosition(new h.THREE.Vector3());
      const buttons=['roomlamps','alllamps'].map(id=>{
        const p=h.sim.wristPoint(id).project(h.camera);
        return {id,x:(p.x+1)*canvas.width/2,y:(1-p.y)*canvas.height/2,depth:p.z};
      });
      return {url:canvas.toDataURL('image/png'),width:canvas.width,height:canvas.height,draws:h.renderer.info.render.calls,
        triangles:h.renderer.info.render.triangles,wrist:h.sim.wristUp&&h.baPanel.visible,room:h.V.model.roomAt(pos.x,pos.y,pos.z)?.id,buttons};
    });
    assert(frame.wrist&&frame.room===living&&frame.draws>0&&frame.triangles>0&&url.length>6000,'Missing live headset wrist or framebuffer');
    for(const b of frame.buttons)assert(b.depth>-1&&b.depth<1&&b.x>0&&b.x<frame.width&&b.y>0&&b.y<frame.height,
      'Wrist button outside the actual headset framebuffer: '+JSON.stringify(b));
    fs.writeFileSync(file,Buffer.from(url.split(',')[1],'base64'));state.frame=frame;
  }
  async function aimWrist(id,type='wrist'){
    await page.evaluate(({id,type})=>{
      const h=__house;h.sim.wrist(type==='wrist');h.sim.hold('trigger',false);h.step(2);
      const p=type==='wrist'?h.sim.wristPoint(id):h.sim.gotoPoint(id);
      if(!p)throw Error('Missing accessible '+type+' target '+id);
      h.sim.aim(p);h.step(2);h.sim.press('trigger','right',2);h.step(4);h.sim.hold('trigger',false);h.step(2);
    },{id,type});
  }
  async function visit(room){
    const ix=await page.evaluate(r=>__house.places().findIndex(p=>p.room===r),room);assert(ix>=0,'No Go to place for '+room);
    if(device==='xr'){
      await aimWrist('goto');await page.waitForFunction(()=>__house.gotoMenu.isOpen,{timeout:12000});
      await aimWrist(ix,'goto');
    }else{
      await release();await ui('#baGoto');await page.select('#baGoto',String(ix));
    }
    await waitRoom(room);
    if(device==='xr')await headsetTitle(room);else await visibleTitle(room);
  }
  async function go(room){
    // Changing the house version can leave the visitor in the requested room.
    // Cross its boundary again to exercise a fresh entry and its short-lived title.
    if(device!=='xr'&&await page.evaluate(r=>lookChecks.snapshot().room===r,room))await visit(room===living?bedroom:living);
    await visit(room);
  }
  async function litRoom(room,on){
    await page.waitForFunction(({r,on})=>{
      const list=lookChecks.snapshot().lamps.filter(x=>x.room===r&&x.visible!==false);
      return list.length>0&&list.every(x=>x.on===on);
    },{timeout:10000},{r:room,on});
    return snap();
  }
  try{
    const phone=device==='phone',xr=device==='xr';
    await page.setViewport({width:phone?390:1000,height:phone?844:640,deviceScaleFactor:1,isMobile:phone,hasTouch:phone});
    if(phone)await page.setUserAgent('Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 Chrome/132 Mobile Safari/537.36');
    if(xr)await page.setUserAgent('Mozilla/5.0 (Linux; Android; Quest 3) AppleWebKit/537.36 OculusBrowser/35.0 Chrome/132 Mobile VR Safari/537.36');
    await page.setCacheEnabled(false);await page.setRequestInterception(true);
    page.on('request',req=>{
      const u=new URL(req.url());
      if(u.protocol==='blob:'||u.protocol==='data:')return req.continue();
      if(u.origin!==origin.origin)return req.abort();
      if(!['GET','HEAD'].includes(req.method())){posts.push(u.pathname);return req.respond({status:204,body:''});}
      if(hold&&!blockedGLB&&shellRequest(req)){blockedGLB=req;return;}
      if(holdFurnish&&!blockedFurnish&&furnitureRequest(req)){blockedFurnish=req;return;}
      return req.continue();
    });
    page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(/GL_INVALID|GL_OUT_OF_MEMORY|Shader Error|VALIDATE_STATUS|CONTEXT_LOST_WEBGL/.test(m.text()))errors.push(m.text().slice(0,260));});
    await page.goto(url,{waitUntil:'domcontentloaded',timeout:180000});
    if(hold){
      await page.waitForSelector('#loadTrack[role=progressbar]',{visible:true,timeout:90000});
      state.loading=await page.$eval('#start',el=>({brand:el.querySelector('.studio-wordmark')?.innerText,progress:el.querySelector('[role=progressbar]')?.getAttribute('aria-valuenow')}));
      assert(/garden studio/i.test(state.loading.brand),'Loading screen has no studio identity');
      assert(state.loading.progress!==null&&Number.isFinite(Number(state.loading.progress)));
      if(!blockedGLB)await page.waitForRequest(shellRequest,wait);hold=false;await blockedGLB.continue();blockedGLB=null;
      if(!blockedFurnish)await page.waitForRequest(furnitureRequest,wait);
      state.lateLoading=await page.$eval('#start',start=>{
        const track=start.querySelector('#loadTrack'),loading=start.querySelector('#loading');
        return {visible:!start.hidden&&!loading.hidden&&track.getBoundingClientRect().width>0,
          progress:track.getAttribute('aria-valuenow'),label:start.querySelector('#loadText').innerText,
          displayed:start.querySelector('#studioLoadValue').innerText,exploreDisabled:start.querySelector('#startDesktop').disabled};
      });
      state.lateLoading.held=new URL(blockedFurnish.url()).pathname;
      const {visible,progress,displayed,exploreDisabled,label}=state.lateLoading;
      assert(visible&&exploreDisabled&&progress!==null&&Number(progress)>=0&&Number(progress)<100&&displayed===progress+'%'&&!/^ready$/i.test(label),
        'Welcome completed before the visible furniture model loaded: '+JSON.stringify(state.lateLoading));
      holdFurnish=false;await blockedFurnish.continue();blockedFurnish=null;
    }
    await page.waitForFunction(()=>window.__house?.V?.model&&__house.look?.snapshot&&__house.furnishing?.layout&&
      !document.querySelector('#startDesktop')?.disabled&&document.querySelector('#loading')?.hidden,wait);
    await page.evaluate(installPageChecks);await page.evaluate(()=>__house.furnishing.readyModels);
    if(xr){
      await page.waitForFunction(()=>__house.inVR()&&__house.hands.left&&__house.hands.right&&document.querySelector('#start').hidden,wait);
      await page.evaluate(()=>{const h=__house;h.sim.wrist(false);h.sim.aim(null);
        for(let i=0;i<2&&h.card.mesh.visible;i++){h.sim.press('trigger','right',2);h.step(4);h.sim.hold('trigger',false);h.step(2);}
      });
    }else{await page.click('#startDesktop');await release();}
    if(phone){
      state.identity=await page.$eval('#title',e=>{
        const s=getComputedStyle(e),r=e.getBoundingClientRect();
        return {name:e.innerText.trim(),display:s.display,visibility:s.visibility,opacity:Number(s.opacity),width:r.width,height:r.height,
          inView:r.x>=0&&r.y>=0&&r.right<=innerWidth&&r.bottom<=innerHeight,welcomeHidden:document.querySelector('#start').hidden};
      });
      const e=state.identity;assert(e.name===def.name&&e.display!=='none'&&e.visibility==='visible'&&e.opacity>0&&e.width>0&&e.height>0&&e.inView&&e.welcomeHidden,
        'The phone visitor cannot see the property name: '+JSON.stringify(e));
    }
    await go(living);state.initial=await snap();
    assert.equal(state.initial.version,def.default);assert(state.initial.furniture>0);assertEffects(state.initial,device);state.pass=await assertPass(page,device);
    const unrelatedBefore=state.initial.lamps.filter(l=>l.room!==living).map(l=>[l.id,l.on]);
    if(xr)await aimWrist('roomlamps');else await click('#baRoomLamps');
    state.roomOn=await litRoom(living,true);assertEffects(state.roomOn,device,{on:true});
    assert.deepEqual(state.roomOn.lamps.filter(l=>l.room!==living).map(l=>[l.id,l.on]),unrelatedBefore,'Room switch affected another room');
    if(!xr){
      state.status=await page.evaluate(()=>{
        const toast=document.querySelector('#toast'),toolbar=document.querySelector('#baBar'),button=document.querySelector('#baRoomLamps');
        const a=toast.getBoundingClientRect(),b=toolbar.getBoundingClientRect(),c=button.getBoundingClientRect(),s=getComputedStyle(toast);
        return {text:toast.textContent,visible:!toast.hidden&&s.display!=='none'&&s.visibility==='visible'&&a.width>0&&a.height>0,
          pointerEvents:s.pointerEvents,toast:[a.top,a.bottom],toolbar:[b.top,b.bottom],
          buttonHittable:button.contains(document.elementFromPoint(c.x+c.width/2,c.y+c.height/2))};
      });
      const t=state.status;assert(t.visible&&t.text==='Room lamps on'&&t.pointerEvents==='none'&&t.buttonHittable&&
        (t.toast[1]<=t.toolbar[0]||t.toast[0]>=t.toolbar[1]),'Lamp status covers the active toolbar: '+JSON.stringify(t));
    }
    await screenshot();
    if(xr)await aimWrist('roomlamps');else await click('#baRoomLamps');
    state.roomOff=await litRoom(living,false);assertEffects(state.roomOff,device);
    if(device==='desktop'||xr){
      if(xr)await page.evaluate(()=>{__house.sim.wrist(false);__house.step(2);});else await release();
      const target=await page.evaluate(x=>lookChecks.aimLamp(x),xr);assert(target,'No unobstructed lamp to point at in the selected real room');
      if(xr)await page.evaluate(()=>{__house.sim.press('trigger','right',2);__house.step(4);});
      else await page.keyboard.press('KeyE');
      await page.waitForFunction(id=>lookChecks.snapshot().lamps.some(l=>l.id===id&&l.on),{timeout:8000},target.id);
      state.target=target;const individual=await snap();
      assert.deepEqual(individual.lamps.filter(l=>l.on).map(l=>l.id),[target.id],'Target input switched more than one lamp');
      assertEffects(individual,device,{on:true});
      if(xr)await page.evaluate(()=>{__house.sim.press('trigger','right',2);__house.step(4);});
      else await page.keyboard.press('KeyE');
      await litRoom(living,false);
    }
    if(xr)await aimWrist('alllamps');else if(phone)await click('#baAllLamps');else{await release();await page.keyboard.press('KeyL');}
    await litRoom(living,true);
    const whole=await snap();assert(whole.lamps.some(x=>x.room!==living&&x.on),'All lamps did not reach a different measured room');
    await go(bedroom);const upstairs=await litRoom(bedroom,true);assertEffects(upstairs,device,{on:true});
    if(xr)await aimWrist('alllamps');else if(phone)await click('#baAllLamps');else{await release();await page.keyboard.press('KeyL');}
    await litRoom(bedroom,false);
    if(xr){await aimWrist('furnish');await aimWrist('furnish');}
    else{
      await click('#baFurnish');await page.waitForFunction(()=>__house.unfurnished&&!__house.furnishing.runtime.group.visible,{timeout:15000});
      await click('#baFurnish');await page.waitForFunction(()=>!__house.unfurnished&&__house.furnishing.runtime.group.visible,{timeout:15000});
      await click('#baMark');await page.waitForFunction(()=>__house.marks.active,{timeout:12000});
      await page.keyboard.press('m');await page.waitForFunction(()=>!__house.marks.active,{timeout:12000});
    }
    if(device==='desktop'){
      await click('#baBefore');await page.waitForFunction(id=>__house.V?.def.id===id&&document.querySelector('#baBefore').getAttribute('aria-pressed')==='true',wait,def.as_built_now);
      await go(living);state.before=await snap();assertEffects(state.before,device);
      await click('#baAfter');await page.waitForFunction(id=>__house.V?.def.id===id&&document.querySelector('#baAfter').getAttribute('aria-pressed')==='true',wait,def.default);
      await go(living);state.returned=await snap();assert.equal(state.returned.version,def.default);assertEffects(state.returned,device);
    }
    if(xr){assert((await snap()).furniture>0,'Furnishings did not return from normal wrist operation');}
    assert.deepEqual(posts.filter(p=>p==='/layout'||p.startsWith('/marks')),[],'Look controls attempted to modify a client record');
    assert.deepEqual(errors,[]);console.log('PASS look',device,'windows',state.initial.windows.length,'lamp',state.target?.id||'group');
  }catch(e){
    state.failure=e.message;
    if(!page.isClosed())state.last=await page.evaluate(()=>window.lookChecks?.snapshot()).catch(()=>null);
    throw e;
  }finally{
    hold=holdFurnish=false;for(const pending of [blockedGLB,blockedFurnish])if(pending)await pending.continue().catch(()=>{});state.errors=errors;state.blockedWrites=posts;
    fs.writeFileSync(path.join(out,device+'.json'),JSON.stringify(state,null,2));await context.close();
  }
}
async function main(){
  fs.mkdirSync(out,{recursive:true});
  const browser=await puppeteer.launch({headless:true,executablePath:process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal'],protocolTimeout:300000});
  try{for(const device of mode==='all'?['desktop','phone','xr']:[mode])await profile(browser,device);}
  finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
