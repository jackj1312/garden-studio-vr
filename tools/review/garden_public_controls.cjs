/* Regression checks for entry into immersion, the original review wrist and survey-only plan captures. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const pp=require(process.env.PUPPETEER_CORE||'puppeteer-core'),root=path.resolve(__dirname,'../..');
(async()=>{
 const origin='https://127.0.0.1:8450',browser=await pp.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args:['--ignore-certificate-errors','--use-angle=metal','--disable-background-networking']});
 try{
  const p=await browser.newPage();
  await p.evaluateOnNewDocument(()=>{const system=new EventTarget();system.isSessionSupported=async v=>v==='immersive-vr';system.requestSession=async mode=>{window.__requestedXR=mode;throw Error('No physical session in this test');};Object.defineProperty(navigator,'xr',{configurable:true,value:system});});
  await p.goto(origin+'/garden/?site=garden-qa-house');
  await p.waitForFunction(()=>window.__house?.garden?.plan.ready,{timeout:180000});
  await p.click('[data-garden-panel] [data-cmd=vr]');assert.equal(await p.evaluate(()=>window.__requestedXR),'immersive-vr');
  const isolation=await p.evaluate(()=>{
    const a=__house.garden,t=a.terrain,root=__house.scene.getObjectByName('Garden proposals'),old=t.surveyOnly.bind(t);
    let result;t.surveyOnly=fn=>old(()=>{const world=__house.V.model.parts.map(p=>p.set?.normal?.userData.gardenMaskRect).filter(Boolean);result={hidden:!root.visible,disabled:world.length>0&&world.every(r=>r.x>1e5)};return fn();});a.plan.invalidate();a.plan.capture();t.surveyOnly=old;result.restored=root.visible;return result;
  });assert.deepEqual(isolation,{hidden:true,disabled:true,restored:true});console.log('VR entry and survey-only plan passed',isolation);await p.close();
  const rev=await browser.newPage();await rev.setRequestInterception(true);
  rev.on('request',r=>{
    if(new URL(r.url()).pathname!=='/src/app.js')return r.continue();
    const src=fs.readFileSync(path.join(root,'src/app.js'),'utf8');
    r.respond({status:200,contentType:'text/javascript',body:src+`
      window.__reviewWristCheck=()=>{
        const L=new THREE.Group(),R=new THREE.Group(),head=camera.getWorldPosition(new THREE.Vector3());
        const forward=camera.getWorldDirection(new THREE.Vector3());
        scene.add(L,R);hands.left=L;hands.right=R;L.add(panel);
        panel.position.copy(head).addScaledVector(forward,.55);panel.lookAt(head);panel.material.opacity=1;L.updateMatrixWorld(true);
        const raw=R.userData.source={gamepad:{buttons:[{pressed:false}]}};
        const u=(HIT.how.x+HIT.how.w/2)/PW,v=(HIT.how.y+HIT.how.h/2)/PH;
        const goal=panel.localToWorld(new THREE.Vector3((u-.5)*.26,(.5-v)*.189,0));
        R.position.copy(head);R.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,-1),goal.sub(head).normalize());R.updateMatrixWorld(true);
        const n=marks.strokes.length;marks.setActive(true);updatePointer();raw.gamepad.buttons[0].pressed=true;updatePointer();const open=wristHelp;
        raw.gamepad.buttons[0].pressed=false;updatePointer();raw.gamepad.buttons[0].pressed=true;updatePointer();const closed=wristHelp;
        return {open,closed,marksUnchanged:n===marks.strokes.length,drawing:marks.drawing};
      };`});
  });
  await rev.goto(origin+'/index.html?site=front-garden-model');await rev.waitForFunction(()=>typeof window.__reviewWristCheck==='function',{timeout:150000});
  const hand=await rev.evaluate(()=>__reviewWristCheck());assert.deepEqual(hand,{open:0,closed:-1,marksUnchanged:true,drawing:false});console.log('Original mark-mode left wrist help passed',hand);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
