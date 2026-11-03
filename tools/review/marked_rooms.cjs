/* Verify actual Go to destinations, plus the shelf, art and finishes named in earlier reviews.
 * PUPPETEER_CORE=… node tools/review/marked_rooms.cjs ROUND [SITE]
 */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.PUPPETEER_CORE||'puppeteer-core');
const [round,site='house']=process.argv.slice(2),root=path.resolve(__dirname,'../..'),origin='https://127.0.0.1:8450';
assert([site,round].every(s=>s&&/^[\w-]+$/.test(s)));const out=path.join(root,'renders/house-build/furnishing',round,'rooms');
const save=(name,url)=>fs.writeFileSync(path.join(out,name+'.jpg'),Buffer.from(url.split(',')[1],'base64'));
async function main(){
 fs.mkdirSync(out,{recursive:true});const report={rooms:[],details:[]},errors=[];
 const browser=await puppeteer.launch({executablePath:process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless:true,args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal'],protocolTimeout:300000});
 try{
  const page=await browser.newPage();await page.setViewport({width:800,height:450});await page.setCacheEnabled(false);await page.setRequestInterception(true);
  page.on('request',r=>r.method()==='GET'&&(r.url().startsWith(origin+'/')||/^(data:|blob:)/.test(r.url()))?r.continue():r.abort());
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+'/house.html?'+new URLSearchParams({site,mode:'review',capture:'1'}),{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__house?.captureState?.().ready,{timeout:180000});
  const versions=await page.evaluate(()=>[__house.manifest().as_built_now,__house.manifest().default]);
  for(const version of versions){
   const places=await page.evaluate(async id=>{
    const h=__house;await h.useVersion(id);h.setStage(h.stageN);h.furnished(true);h.step(2);await h.furnishing?.readyModels;
    return h.places().filter(p=>p.room).map(p=>p.room);
   },version);
   for(const roomId of places){
    const shot=await page.evaluate(id=>{
     const h=__house,T=h.THREE,place=h.places().find(p=>p.room===id);
     h.goToPlace(place);const feet=place.feet;let good=0,clear=0;const w=480,hgt=270;
     const frame=h.captureAt({x:feet.x,y:feet.y,z:feet.z,eye:1.65,yawDeg:place.yaw*180/Math.PI,fov:50,w,h:hgt,post:true});
     const pos=h.camera.getWorldPosition(new T.Vector3()),rc=new T.Raycaster(),model=h.V.model;
     for(let i=0;i<7;i++)for(let j=0;j<5;j++){
       rc.setFromCamera({x:(i-3)/3*.75,y:(j-2)/2*.65},h.camera);
       const hit=h.V.bvh.raycast(rc.ray,60,model.masks.visible);if(!hit)continue;
       const loose=h.furnishing?.runtime?.pick(rc.ray,hit.distance),dist=loose?.distance||hit.distance;
       if(dist>.55)clear++;
       const through=rc.ray.at(Math.min(.55,dist*.9),new T.Vector3());
       if(dist>.4 && model.roomAt(through.x,through.y,through.z)?.id===id)good++;
     }
     return {url:frame.url,room:id,standing:model.roomAt(pos.x,pos.y,pos.z)?.id,clear,good,total:35,from:place.from};
    },roomId);
    const {url,...facts}=shot;report.rooms.push({version,...facts});
    if(/hall|landing|bedroom-3/.test(roomId)||facts.good<=17)save(version+'-'+roomId,url);
   }
   const targets=['SIT-DEC-1','LIV-ART-1','LIV-ART-2','LIV-DEC-2','BTH-BASIN','BTH-BATH','KA-ISLAND'];
   for(const target of targets){
    const d=await page.evaluate(id=>{
      const h=__house,T=h.THREE,m=h.V.model,row=h.furnishing?.layout?.items.find(i=>i.id===id);
      const parts=m.parts.filter(p=>p.now.visible&&p.ud.spec_id===id);if(!row&&!parts.length)return null;
      const centre=new T.Vector3(),roomId=row?.room||parts[0].ud.room_id,room=m.table.get(roomId);
      if(!room)return null;
      if(row)centre.fromArray(row.position).y+=row.size[2]*.54;
      else {const box=new T.Box3();for(const p of parts)box.union(p.bbox);box.getCenter(centre);}
      const poly=room.params.polygon,c=new T.Vector3(poly.reduce((s,q)=>s+q[0],0)/poly.length,centre.y,poly.reduce((s,q)=>s+q[1],0)/poly.length);
      const toward=c.sub(centre);if(toward.length()<.01)toward.set(0,0,1);
      const eye=centre.clone().addScaledVector(toward.normalize(),1.30);eye.y=Math.min(room.params.floor+1.72,Math.max(room.params.floor+1.15,centre.y+.19));
      if(m.roomAt(eye.x,eye.y,eye.z)?.id!==roomId)return null;
      const [dx,dy,dz]=centre.clone().sub(eye).toArray(),deg=180/Math.PI;
      const frame=h.captureAt({x:eye.x,z:eye.z,y:eye.y-1.6,eye:1.6,yawDeg:Math.atan2(-dx,-dz)*deg,pitchDeg:Math.atan2(dy,Math.hypot(dx,dz))*deg,fov:48,w:480,h:270,post:true});
      return {url:frame.url,id,room:roomId,variant:row?.variant,size:row?.size,host:row?.host,eye:eye.toArray()};
    },target);
    if(d){const {url,...facts}=d;report.details.push({version,...facts});save(version+'-'+target,url);}
   }
  }
  fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify(report,null,1));
  assert.deepEqual(errors,[]);const failures=report.rooms.filter(r=>r.standing!==r.room||r.good<=r.total/2);
  if(failures.length)throw Error('Go-to views need inspection: '+JSON.stringify(failures));
  console.log('PASS',report.rooms.length,'measured Go-to views;',report.details.length,'detail frames');
 }finally{await browser.close();}
}
main().then(()=>process.exit(0),e=>{console.error(e);process.exit(1);});
