/* Capture the owner's actual recorded eye and look toward the centroid of that stroke.
 * No owner record is written. The candidate and original marks can be different local sites.
 * PUPPETEER_CORE=... node tools/review/marked_views.cjs ROUND [modelSite] [markSite] [F84,F85,...]
 */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.PUPPETEER_CORE||'puppeteer-core');
const root=path.resolve(__dirname,'../..'),origin='https://127.0.0.1:8450';
const [round,site='house',marked='house-wip',subset='']=process.argv.slice(2);
for(const k of [round,site,marked])assert(/^[a-z\d_-]+$/i.test(k),'Expected local round/site names');
const out=path.join(root,'renders/house-build/furnishing',round,'marks');
const dataDir=path.join(root,'assets/sites',marked),read=file=>JSON.parse(fs.readFileSync(path.join(dataDir,file)));
const marks=new Map(read('marks.json').strokes.map(m=>[m.id,m])),ids=new Set(subset.split(','));
const jobs=read('review/findings.json').findings.filter(f=>marks.has(f.mark)&&
  (subset?ids.has(f.id):f.status!=='fixed')).map(f=>({id:f.id,mark:marks.get(f.mark)}));
assert(jobs.length,'No original marks found');
async function main(){
 fs.mkdirSync(out,{recursive:true});const report={},errors=[];
 const browser=await puppeteer.launch({executablePath:process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,
   args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal'],protocolTimeout:300000});
 try{
  const page=await browser.newPage();await page.setViewport({width:800,height:450});await page.setCacheEnabled(false);
  await page.setRequestInterception(true);page.on('request',r=>{
   const u=r.url();if(r.method()!=='GET'||!(u.startsWith(origin+'/')||/^(data:|blob:)/.test(u)))return r.abort();return r.continue();
  });page.on('pageerror',e=>errors.push(e.message));
  await page.goto(origin+'/house.html?'+new URLSearchParams({site,mode:'review',capture:1}),{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__house?.captureState?.().ready,{timeout:180000});
  for(const {id,mark} of jobs){
    const shot=await page.evaluate(async m=>{
      const h=__house,T=h.THREE,eye=m.camera,pts=m.points3d;
      if(!eye?.length||!pts?.length)throw Error('Missing original eye/stroke '+m.id);
      if(h.V.def.id!==m.version)await h.useVersion(m.version);
      h.furnished(true);h.setStage(m.stage);h.step(1);
      if(h.furnishing){h.furnishing.setStage(m.stage);await h.furnishing.readyModels;}
      const target=pts.reduce((a,p)=>a.map((v,i)=>v+p[i]/pts.length),[0,0,0]);
      const [dx,dy,dz]=target.map((n,i)=>n-eye[i]),deg=180/Math.PI;
      const pose={x:eye[0],y:eye[1]-1.6,z:eye[2],eye:1.6,yawDeg:Math.atan2(-dx,-dz)*deg,pitchDeg:Math.atan2(dy,Math.hypot(dx,dz))*deg,
        w:640,h:360,fov:60,post:true,quality:.92};
      const frame=h.captureAt(pose),v=h.V,from=new T.Vector3(...eye);
      const indices=pts.length<=64?pts.map((_,i)=>i):Array.from({length:64},(_,i)=>Math.round(i*(pts.length-1)/63));
      const hits=indices.map(i=>{const p=pts[i];
        const goal=new T.Vector3(...p),distance=from.distanceTo(goal),ray=new T.Ray(from.clone(),goal.clone().sub(from).normalize());
        const hit=v.bvh.raycast(ray,60,v.model.masks.visible),part=hit&&v.model.parts[hit.part];
        const loose=h.furnishing?.runtime?.pick(ray,hit?.distance??Infinity);
        const at=loose||hit;return {i,target:p,distance:+distance.toFixed(3),id:loose?.id||part?.element||null,part:loose?.item?.kind||part?.name||null,
          material:loose?.item?.variant||part?.materialName||null,hit:at?.point?.toArray(),deltaMm:at?Math.round((at.distance-distance)*1000):null};
      });
      const diagnosticPixels={
        'mmvzv3hjknwe':[[80,216],[87,213],[86,222],[320,180],[327,185],[365,202],[366,211],[230,152]],
        'mmvzv3ov538u':[[280,190],[279,190],[274,190],[284,190],[271,230],[266,231],[282,225],[370,84],[210,36],[300,179]],
        'mmvzv3tgv13j':[[50,124],[50,128],[50,134],[250,156],[250,161],[250,169],[326,239],[324,239],[322,239],[317,250]],
      };
      const pixels=(diagnosticPixels[m.id]||[]).map(([x,y])=>{const rc=new T.Raycaster();
        rc.setFromCamera({x:2*(x+.5)/pose.w-1,y:1-2*(y+.5)/pose.h},h.camera);
        const hit=v.bvh.raycast(rc.ray,60,v.model.masks.visible),p=hit&&v.model.parts[hit.part];return {x,y,
          part:p?.name,material:p?.materialName,point:hit?.point?.toArray(),normal:hit?.normal?.toArray()};});
      return {url:frame.url,eye,pose,target,mark:m.id,version:v.def.id,stage:h.stage,originalParts:m.parts,strokePoints:pts.length,hits,pixels};
    },mark);
    const {url,...facts}=shot;fs.writeFileSync(path.join(out,id+'.jpg'),Buffer.from(url.split(',')[1],'base64'));report[id]=facts;
    console.log(id,mark.id,new Set(facts.hits.map(h=>h.id)).size,'hit owners');
  }
  assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'rays.json'),JSON.stringify(report,null,1));
 } finally {await browser.close();}
}
main().then(()=>process.exit(0),e=>{console.error(e);process.exit(1);});
