/* Local Quest controller acceptance. Run alone. This writes only to the disposable garden-qa-house layout. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require(process.env.PUPPETEER_CORE || 'puppeteer-core');

const origin = new URL(process.env.STUDIO_URL || 'https://127.0.0.1:8450');
if (origin.protocol !== 'https:' || !['127.0.0.1','localhost','[::1]'].includes(origin.hostname) || origin.port !== '8450') {
  throw new Error('Use the loopback Garden Studio test server on 8450.');
}
const site = 'garden-qa-house', version = 'approved_2b';
const url = new URL('/house.html', origin);
url.search = new URLSearchParams({ site, version, mode: 'review', garden: '1', xrsim: '1' }).toString();
const api = new URL('/layout?' + new URLSearchParams({ site, version }), origin).href;
const output = path.resolve(__dirname, '../../renders/garden-tool/quest-flow');
const close = (a,b,t=.002) => Math.abs(a-b) <= t;
const positionDelta = (a,b) => Math.hypot(...a.map((n,i)=>n-b[i]));
// q and −q encode the same orientation.
const orientationDot = (a,b) => Math.min(1, Math.abs(a.reduce((sum,n,i)=>sum+n*b[i],0))/(Math.hypot(...a)*Math.hypot(...b)));

async function run() {
  fs.mkdirSync(output, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true, protocolTimeout: 300000,
    args: ['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal'],
  });
  const errors = [], evidence = {
    device: 'Desktop Chrome, Quest user-agent and studio simulated XR controllers',
    site, version, camera: 'Same standing pose for the full-house and garden detail comparisons',
    timings: 'Measured requestAnimationFrame intervals and studio render submission time in desktop simulation',
    stages: [], profiles: {},
  };
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1100, height: 740, deviceScaleFactor: 1 });
    await page.setUserAgent('Mozilla/5.0 (X11; Linux x86_64; Quest 3) AppleWebKit/537.36 Chrome/132 Mobile VR OculusBrowser/35.0 Safari/537.36');
    await page.setRequestInterception(true);
    page.on('request', request => {
      const u = request.url();
      if (u.startsWith(origin.origin + '/') || /^(?:blob:|data:|about:)/.test(u)) return request.continue();
      return request.abort();
    });
    page.on('pageerror', e => { errors.push(e.message); console.error('PAGE ERROR', e.message); });
    page.on('console', m => {
      const t = m.text();
      if (/Shader Error|VALIDATE_STATUS.*false|Uncaught \(in promise\)/i.test(t)) errors.push(t.slice(0,240));
    });
    async function boot() {
      await page.goto(url.href, { waitUntil: 'domcontentloaded', timeout: 180000 });
      await page.waitForFunction(() => {
        const h = window.__house;
        return h?.V?.def.id === 'approved_2b' && h.inVR() && h.hands.left && h.hands.right &&
          h.garden?.enabled && h.garden.bird && h.garden.plan.ready && h.garden.wrist.wristWorld('Home');
      }, { timeout: 180000 });
      await page.evaluate(() => { __house.sim.wrist(true); __house.step(3); });
    }
    const current = () => page.evaluate(() => {
      const g = __house.garden, s = g.state();
      return { active:g.enabled, bird:g.bird, selected:s.selected, kind:s.kind, method:s.method, tool:s.tool,
        revision:g.store.revision, dirty:s.dirty, saving:s.saving, status:s.status,
        ids:g.objects.map(o => o.id), eye:__house.camera.getWorldPosition(new __house.THREE.Vector3()).toArray() };
    });
    const mark = async name => {
      const s = await current();
      evidence.stages.push({ name, revision:s.revision, objects:s.ids.length, bird:s.bird, selected:s.selected?.id || null });
      console.log(name, JSON.stringify({ ...s, ids:undefined }));
    };
    async function wrist(label, host = false) {
      // Use the actual controller pose, gamepad button edge and host frame loop.
      await page.evaluate(({label,host}) => {
        const h=__house; h.sim.wrist(true); h.sim.hold('trigger',false); h.step(2);
        const p=host ? h.sim.wristPoint(label) : h.garden.wrist.wristWorld(label);
        if (!p) throw Error('Unreachable wrist button '+label);
        h.sim.aim(p); h.step(2); h.sim.hold('trigger',true); h.step(2);
        h.sim.hold('trigger',false); h.step(2);
      }, { label, host });
    }
    async function screenshot(filename) {
      // Immersive WebXR displays the 3D scene only. Capture the real simulator
      // camera's framebuffer immediately after its render, with all wrist/plan
      // meshes visible; the page DOM is outside that framebuffer.
      const shot = await page.evaluate(() => {
        const h=__house;
        if (!h.inVR() || !document.body.classList.contains('in-vr')) throw Error('No simulator headset pose');
        h.step(1);
        h.renderer.info.reset(); h.renderer.render(h.scene,h.camera);
        return { url:h.renderer.domElement.toDataURL('image/png'), width:h.renderer.domElement.width,
          height:h.renderer.domElement.height, calls:h.renderer.info.render.calls, triangles:h.renderer.info.render.triangles,
          wrist:h.scene.getObjectByName('Garden · left wrist')?.visible, table:h.scene.getObjectByName('Garden · whole plot')?.visible };
      });
      assert(shot.calls > 0 && shot.triangles > 0 && shot.url.length > 6000, 'empty headset framebuffer: '+filename);
      fs.writeFileSync(path.join(output, filename), Buffer.from(shot.url.split(',')[1],'base64'));
      evidence[filename] = { width:shot.width,height:shot.height,calls:shot.calls,triangles:shot.triangles,wrist:shot.wrist,table:shot.table };
    }
    const measuredPose = () => page.evaluate(() => {
      const h=__house;
      h.player.updateMatrixWorld(true); h.camera.updateMatrixWorld(true);
      const transform=o=>({position:o.position.toArray(),quaternion:o.quaternion.toArray(),scale:o.scale.toArray()});
      return { player:transform(h.player), camera:transform(h.camera), feet:h.feet.toArray(),
        yaw:h.yawPitch.yaw, pitch:h.yawPitch.pitch, eye:h.camera.getWorldPosition(new h.THREE.Vector3()).toArray(),
        orientation:h.camera.getWorldQuaternion(new h.THREE.Quaternion()).toArray() };
    });
    async function profile(name, pose=null) {
      evidence.profiles[name] = await page.evaluate(async pose => {
        const h=__house, samples=[];
        if(pose) {
          function restore(o,snapshot) {
            o.position.fromArray(snapshot.position);o.quaternion.fromArray(snapshot.quaternion);
            o.scale.fromArray(snapshot.scale);o.updateMatrix();
          }
          h.feet.fromArray(pose.feet); h.yawPitch.yaw=pose.yaw; h.yawPitch.pitch=pose.pitch;
          restore(h.player,pose.player); restore(h.camera,pose.camera);
          h.player.updateMatrixWorld(true); h.camera.updateMatrixWorld(true);
        }
        const initialEye=h.camera.getWorldPosition(new h.THREE.Vector3()).toArray();
        const initialOrientation=h.camera.getWorldQuaternion(new h.THREE.Quaternion()).toArray();
        let previous=null;
        await new Promise(resolve => {
          function frame(t) {
            if (previous !== null) samples.push({dt:t-previous,render:h.renderMs,calls:h.renderer.info.render.calls,
                                               triangles:h.renderer.info.render.triangles});
            previous=t; if(samples.length<28) requestAnimationFrame(frame); else resolve();
          }
          requestAnimationFrame(frame);
        });
        const rows=samples.slice(4);
        const q=(key,part)=>{const sort=rows.map(v=>v[key]).sort((a,b)=>a-b);
          return Math.round(sort[Math.min(sort.length-1,Math.ceil(part*sort.length)-1)]*100)/100;};
        return { initialEye, initialOrientation, sampleFrames:rows.length, medianIntervalMs:q('dt',.5), p95IntervalMs:q('dt',.95),
          medianRenderSubmitMs:q('render',.5), medianCalls:q('calls',.5), medianTriangles:q('triangles',.5),
          eye:h.camera.getWorldPosition(new h.THREE.Vector3()).toArray(),orientation:h.camera.getWorldQuaternion(new h.THREE.Quaternion()).toArray(),
          outputPixels:[h.renderer.domElement.width,h.renderer.domElement.height], active:h.garden.enabled,bird:h.garden.bird };
      }, pose);
    }
    await boot();
    const first = await current();
    assert(first.active && first.bird);
    await wrist('How to use'); await wrist('Next'); await screenshot('wrist-help.png'); await wrist('Dismiss help');
    const birdPose=await measuredPose();
    await wrist('Standing view'); assert.equal((await current()).bird,false);
    const standingPose=await measuredPose();
    const switchPose={before:birdPose, after:standingPose, rigMetres:positionDelta(birdPose.player.position,standingPose.player.position),
      eyeMetres:positionDelta(birdPose.eye,standingPose.eye), rigQuatDot:orientationDot(birdPose.player.quaternion,standingPose.player.quaternion)};
    evidence.viewSwitch=switchPose;
    assert(switchPose.rigMetres<.003 && switchPose.eyeMetres<.003 && switchPose.rigQuatDot>.999999,
      'Switching from tabletop to standing moved the rig: '+JSON.stringify(switchPose));
    await wrist('How to use'); await wrist('Dismiss help');
    await mark('Help dismissed in both plan and standing views');
    await wrist('Close editor');
    assert(!(await current()).active);
    evidence.profileReference=standingPose;
    await profile('fullHouse',standingPose);
    await wrist('garden',true);
    await page.waitForFunction(() => __house.garden.enabled && __house.garden.bird, {timeout:15000});
    await wrist('Standing view');
    await profile('gardenStanding',standingPose);
    const full=evidence.profiles.fullHouse, lean=evidence.profiles.gardenStanding;
    assert(full.medianCalls>0 && lean.medianCalls>0 && full.medianTriangles>0 && lean.medianTriangles>0);
    const match={initialMetres:positionDelta(full.initialEye,lean.initialEye),
      initialQuatDot:orientationDot(full.initialOrientation,lean.initialOrientation), finalMetres:positionDelta(full.eye,lean.eye),
      finalQuatDot:orientationDot(full.orientation,lean.orientation), fullQuaternion:full.orientation, gardenQuaternion:lean.orientation};
    evidence.profileMatch=match;console.log('Profile pose match',JSON.stringify(match));
    assert(match.initialMetres<.001 && match.initialQuatDot>.999999 && match.finalMetres<.012 && match.finalQuatDot>.99999,
      'Different measured poses in detail profiles: '+JSON.stringify(match));
    await wrist('Bird’s-eye');
    await wrist('Features'); await wrist('Patio'); await wrist('Method'); await wrist('Circle');
    const tool=await current(); assert.deepEqual([tool.kind,tool.method,tool.tool],['patio','circle','draw']);

    const lawn = await page.evaluate(() => {
      const h=__house,T=h.THREE,g=h.garden,parts=h.V.model.parts;
      h.sim.wrist(false);h.sim.hold('trigger',false);h.step(3);
      const mask=Uint8Array.from(parts,p=>/^G2_lawn(?:_west)?(?:\.\d+)?$/.test(p.name)?1:0);
      const box=new T.Box3();for(const p of parts)if(mask[p.index])box.union(p.bbox);
      if(box.isEmpty())throw Error('The measured lawn is absent');
      const from=h.hands.right.getWorldPosition(new T.Vector3());
      const down=new T.Vector3(0,-1,0);
      const lawnHeight=(x,z)=>{
        const hit=h.V.bvh.raycast(new T.Ray(new T.Vector3(x,15,z),down),30,mask,null);
        const terrain=g.terrain.ground(x,z);
        return hit&&terrain!==null&&Math.abs(hit.point.y-terrain)<.02?hit.point.y:null;
      };
      const uncovered=(x,z)=>{
        const dest=g.wrist.planWorld([x,z]);
        if(!dest)return false;
        const ray=new T.Ray(from.clone(),dest.clone().sub(from).normalize());
        return g.wrist.hitWrist(ray,false)===null && !!g.wrist.hitPlan(ray);
      };
      // Every centre and rim sample must lie on the surveyed lawn itself.
      for(const radius of [.46,.34,.25]) for(let x=Math.ceil(box.min.x*4)/4;x<=box.max.x;x+=.25) {
        for(let z=Math.ceil(box.min.z*4)/4;z<=box.max.z;z+=.25){
          if(g.objects.some(o=>o.geometry.center && Math.hypot(o.geometry.center[0]-x,o.geometry.center[1]-z)<radius+1))continue;
          const level=lawnHeight(x,z);
          if(level===null||![0,radius,radius+.20].every(offset=>uncovered(x+offset,z)))continue;
          if(!Array.from({length:12},(_,i)=>i*Math.PI/6).every(a=>lawnHeight(x+(radius+.20)*Math.cos(a),z+(radius+.20)*Math.sin(a))!==null))continue;
          return {x,z,radius,baseY:level};
        }
      }
      throw Error('No clear measured lawn footprint could be hit on the whole-garden tabletop');
    });
    evidence.lawn = lawn;
    async function drag(points) {
      await page.evaluate(points => {
        const h=__house,g=h.garden;
        h.sim.wrist(false);h.sim.hold('trigger',false);h.step(3);
        const aim=p=>{const q=g.wrist.planWorld(p);if(!q)throw Error('Tabletop is unavailable');h.sim.aim(q);h.step(2);};
        aim(points[0]);h.sim.hold('trigger',true);h.step(2);
        for(const point of points.slice(1))aim(point);
        h.sim.hold('trigger',false);h.step(2);
      },points);
    }
    const {x,z,radius:r}=lawn;
    await drag([[x,z],[x+r*.3,z],[x+r*.6,z],[x+r,z]]);
    let s=await current();
    assert.equal(s.ids.length, first.ids.length+1, 'one trigger sweep must add exactly one feature: '+s.status);
    const f=s.selected;
    assert(f && !first.ids.includes(f.id) && f.kind==='patio' && f.geometry.type==='circle');
    assert(close(f.geometry.radius,r) && close(f.geometry.center[0],x) && close(f.geometry.center[1],z));
    assert(close(f.baseY,lawn.baseY,.004));
    await mark('Measured front-lawn circle drawn with right trigger');
    await wrist('Select');
    await drag([[x+r,z],[x+r+.09,z],[x+r+.18,z]]);
    s=await current();
    assert.equal(s.selected.id,f.id);assert(close(s.selected.geometry.radius,r+.18));
    assert(close(s.selected.geometry.center[0],x) && close(s.selected.geometry.center[1],z),'Radius handle moved the whole patio');
    await mark('Radius handle resized circle without moving its centre');
    await page.evaluate(() => {
      const h=__house;
      for(let i=0;i<3;i++){h.sim.stick('right',0,1);h.step(2);h.sim.stick('right',0,0);h.step(2);}
    });
    assert(close((await current()).selected.level,-.15,.001));
    await wrist('Home');await wrist('Levels & steps');await wrist('Fit steps');
    s=await current();assert(s.selected.steps && s.selected.steps.count>0);
    const steps=s.selected.steps;
    await wrist('Home');await wrist('Undo');assert(!(await current()).selected.steps);
    await wrist('Redo');assert.deepEqual((await current()).selected.steps,steps);
    await mark('Three stick level increments, fitted steps, undo and redo');
    await screenshot('whole-garden-plan.png');
    await profile('gardenTabletop');
    await wrist('Save layout');
    await page.waitForFunction(start=>__house.garden.store.revision>start && !__house.garden.store.dirty && !__house.garden.store.saving,
                              {timeout:20000},first.revision);
    const record = await page.evaluate(async api=>{const r=await fetch(api,{cache:'no-store'});if(!r.ok)throw Error('Layout HTTP '+r.status);return r.json();},api);
    assert.equal(record.site,site);assert.equal(record.version,version);
    const saved=record.garden.objects.find(o=>o.id===f.id);
    assert(saved && close(saved.geometry.radius,r+.18) && close(saved.level,-.15) && saved.steps.count===steps.count);
    evidence.saved={id:f.id,revision:record.revision,geometry:saved.geometry,baseY:saved.baseY,level:saved.level,steps:saved.steps};
    await wrist('Standing view'); await screenshot('garden-standing.png');
    await wrist('Bird’s-eye'); assert((await current()).bird);
    await wrist('Close editor'); assert(!(await current()).active);
    await page.goto('about:blank');
    await boot();
    const reopened = await page.evaluate(id=>__house.garden.objects.find(f=>f.id===id),f.id);
    assert.deepEqual(reopened,saved);
    await mark('New walkthrough load reopened the exact saved geometry, level and steps');
    assert.deepEqual(errors, []);
    fs.writeFileSync(path.join(output,'simulated-headset.json'), JSON.stringify(evidence,null,2)+'\n');
    console.log('PASS simulated headset flow',JSON.stringify(evidence.profiles));
  } finally {
    await browser.close();
  }
}
run().catch(error=>{console.error(error);process.exitCode=1;});
