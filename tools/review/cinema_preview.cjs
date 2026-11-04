/* Local viewer camera rehearsal. No Unreal lighting or effects, no model edits. */
const fs=require('node:fs'),path=require('node:path');
const puppeteer=require(process.env.PUPPETEER_CORE||'/Users/Jack/Documents/ChatGPT/.tools/qa/node_modules/puppeteer-core');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'renders/unreal/house-stills/camera-preview-v2'),base='https://127.0.0.1:8450';
const spec=JSON.parse(fs.readFileSync(path.join(root,'tools/unreal/house-cinema.json'))),v=spec.video,keys=v.waypoints;
function sample(t,field){let i=0;while(i<keys.length-2&&t>keys[i+1].t)i++;const a=keys[i],b=keys[i+1],p=keys[Math.max(0,i-1)],q=keys[Math.min(keys.length-1,i+2)],dt=b.t-a.t,u=(t-a.t)/dt;
return a[field].map((x,k)=>{const m0=(b[field][k]-p[field][k])/(b.t-p.t),m1=(q[field][k]-a[field][k])/(q.t-a.t);return (2*u**3-3*u*u+1)*x+(u**3-2*u*u+u)*dt*m0+(-2*u**3+3*u*u)*b[field][k]+(u**3-u*u)*dt*m1;});}
(async()=>{fs.mkdirSync(out,{recursive:true});const browser=await puppeteer.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--ignore-certificate-errors','--disable-background-networking','--disable-sync','--use-angle=metal'],protocolTimeout:300000});
try{const page=await browser.newPage();await page.setViewport({width:960,height:540});page.on('pageerror',e=>console.error(e.message));
await page.goto(base+'/house.html?site=house&version=approved_2b&mode=customer&capture=1',{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>window.__house?.captureState?.().ready,{timeout:180000});
await page.evaluate(async()=>{const h=window.__house;await h.useVersion('approved_2b');h.setStage(h.stageN);h.furnished(true);h.step(1);if(h.furnishing)await h.furnishing.readyModels;h.setHover(null);});
const poses=[];for(let frame=0;frame<v.fps*v.seconds;frame++){const t=frame/v.fps,eye=sample(t,'eye'),aim=sample(t,'aim'),[dx,dy,dz]=aim.map((x,k)=>x-eye[k]);const pose={x:eye[0],z:eye[2],y:eye[1]-1.6,eye:1.6,yawDeg:Math.atan2(-dx,-dz)*180/Math.PI,pitchDeg:Math.atan2(dy,Math.hypot(dx,dz))*180/Math.PI,fov:2*Math.atan(Math.tan(v.hfov_deg*Math.PI/360)/(960/540))*180/Math.PI,w:960,h:540,post:false,quality:.9};
const file=path.join(out,String(frame).padStart(4,'0')+'.jpg');if(!fs.existsSync(file)){const url=await page.evaluate(p=>window.__house.captureAt(p).url,pose);fs.writeFileSync(file,Buffer.from(url.split(',')[1],'base64'));}
poses.push({frame,t,eye,aim});if(frame%48===0)console.log('Captured',frame,'/',v.fps*v.seconds);}
fs.writeFileSync(path.join(out,'poses.json'),JSON.stringify(poses,null,2));console.log('Camera frames ready',out);
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
