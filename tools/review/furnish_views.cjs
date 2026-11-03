/* Capture the signed room cameras at a private candidate site on port 8450.
 * PUPPETEER_CORE=<installed module> node tools/review/furnish_views.cjs ROUND [SITE] [--xr] [--walk]
 */
const fs=require('node:fs'),path=require('node:path');
const puppeteer=require(process.env.PUPPETEER_CORE||'puppeteer-core');
const root=path.resolve(__dirname,'../..'),local='https://127.0.0.1:8450';
const [round,site='house',...opts]=process.argv.slice(2);
if(!round || !/^[\w-]+$/.test(round)||!/^[\w-]+$/.test(site))throw Error('Expected a local round and site ID');
const out=path.join(root,'renders/house-build/furnishing',round);
const cameras=[
 ['kitchen-diner',[7.65,1.50,-4.83],[2.2,1,-7.6]],
 ['lounge',[3.30,1.50,-.75],[1.2,1,-4.2]],
 ['front-garden',[3.7,1.369,9.8],[4,1,.2]],
];
async function main(){
 fs.mkdirSync(out,{recursive:true});
 const browser=await puppeteer.launch({executablePath:process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,
   args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal'],protocolTimeout:300000});
 try{
  const page=await browser.newPage();await page.setViewport({width:840,height:500});
  await page.setRequestInterception(true);
  page.on('request',r=>r.url().startsWith(local+'/')||/^(blob:|data:)/.test(r.url())?r.continue():r.abort());
  page.on('pageerror',e=>console.error(e.message));
  const query=new URLSearchParams({site,mode:'customer',capture:'1'});
  if(opts.includes('--xr'))query.set('xrsim','1');
  if(opts.includes('--walk'))query.set('test','walk');
  await page.goto(local+'/house.html?'+query,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.__house?.captureState?.().ready,{timeout:180000});
  if(opts.includes('--walk')){
    await page.waitForFunction(()=>Boolean(window.__walkTest),{timeout:900000});
    const result=await page.evaluate(()=>window.__walkTest);
    fs.writeFileSync(path.join(out,'walk.json'),JSON.stringify(result,null,1));
    console.log(result.pass?'Walk PASS':'Walk FAIL',result.seconds);
    if(!result.pass)process.exitCode=1;
    return;
  }
  const manifest=JSON.parse(fs.readFileSync(path.join(root,'assets/sites',site,'versions.json')));
  const hashes=new Set(),stats={};
  async function select(version){
    await page.evaluate(async id=>{let h=window.__house;if(h.V.def.id!==id)await h.useVersion(id);h.setStage(h.stageN);h.furnished(true);h.step(1);},version);
  }
  async function shoot(name,point){
    const shot=await page.evaluate(v=>{
      const h=window.__house,r=h.captureAt(v),stats=h.stats();
      return {url:r.url,hash:r.hash,stats,version:h.V.def.id,stage:h.stage};
    },{w:800,h:450,post:true,...point});
    if(hashes.has(shot.hash))throw Error('Duplicate camera frame: '+name);
    hashes.add(shot.hash);stats[name]={version:shot.version,stage:shot.stage,...shot.stats};
    fs.writeFileSync(path.join(out,name+'.jpg'),Buffer.from(shot.url.split(',')[1],'base64'));
  }
  await select(manifest.default);
  for(const [name,eye,target] of cameras){
    const [dx,dy,dz]=target.map((n,i)=>n-eye[i]),deg=180/Math.PI;
    await shoot(name,{x:eye[0],z:eye[2],y:eye[1]-1.6,eye:1.6,yawDeg:Math.atan2(-dx,-dz)*deg,pitchDeg:Math.atan2(dy,Math.hypot(dx,dz))*deg});
  }
  if(opts.includes('--conservatory')){
    await select(manifest.as_built_now);
    for(const [name,x,z,yawDeg,pitchDeg] of [['conservatory-inside',2.65,-4.92,26,7],['conservatory-roof',1.35,-7.45,170,34],['conservatory-outside',2.8,-11.25,185,6]])
      await shoot(name,{x,z,y:0,eye:1.5,yawDeg,pitchDeg});
  }
  fs.writeFileSync(path.join(out,'draws.json'),JSON.stringify(stats,null,1));
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
