/* Open the actual pinned Wi-Fi package. No writes to client layouts or review records. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const puppeteer=require(process.env.PUPPETEER_CORE||'puppeteer-core');
const origin=process.env.STUDIO_URL||'https://192.168.1.118:8450';
assert(['https://127.0.0.1:8450','https://192.168.1.118:8450'].includes(origin));
const out=path.resolve(__dirname,'../../renders/house-build/furnishing/preview');fs.mkdirSync(out,{recursive:true});
async function main(){
 const browser=await puppeteer.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal'],protocolTimeout:300000});
 try{
  for(const xr of [false,true]){
   const profile=xr?'quest':'desktop',context=await browser.createBrowserContext(),page=await context.newPage(),errors=[],failed=[],writes=[];
   try{
    await page.setViewport({width:920,height:575});await page.setCacheEnabled(false);await page.setRequestInterception(true);
    page.on('pageerror',e=>{errors.push(e.message);console.error('Page error',e.message);});
    page.on('response',r=>{if(r.status()>=400 && !r.url().endsWith('/favicon.ico')){failed.push([r.status(),r.url()]);console.error('Resource',r.status(),r.url());}});
    page.on('request',r=>{const u=r.url();if(!['GET','HEAD'].includes(r.method())){writes.push(new URL(u).pathname);return r.abort();}
     return u.startsWith(origin+'/')||/^(blob:|data:)/.test(u)?r.continue():r.abort();});
    if(xr)await page.setUserAgent('Mozilla/5.0 (Linux; Android; Quest 3) AppleWebKit/537.36 OculusBrowser/35.0 Chrome/132 Mobile VR Safari/537.36');
    await page.goto(origin+'/preview/?version=approved_2b',{waitUntil:'domcontentloaded'});
    if(xr){const u=new URL(page.url());u.searchParams.set('xrsim','1');await page.goto(u.href,{waitUntil:'domcontentloaded'});}
    await page.waitForFunction(()=>__house?.V?.def.id==='approved_2b'&&!document.querySelector('#startDesktop').disabled&&!!__house.furnishing?.layout?.loaded,{timeout:160000});
    if(!xr)await page.click('#startDesktop');else await page.waitForFunction(()=>__house.inVR()&&__house.hands.left&&__house.hands.right);
    const details=await page.evaluate(async ()=>{
     const h=__house;await h.furnishing.readyModels;const row=()=>({id:h.V.def.id,items:h.furnishing.layout.items.length,file:h.V.file,
       instances:h.furnishing.runtime.group.children.filter(c=>c.visible&&c.count).length,rooms:h.places().filter(p=>p.room).length});
     const after=row();await h.beforeAfter(false);await h.furnishing.readyModels;const before=row();
     return {after,before,preview:document.documentElement.dataset.studioPreview,garden:document.querySelector('.studio-preview-link')?.href,
       badge:document.querySelector('.studio-identity .studio-kicker')?.textContent,url:location.pathname};
    });
    assert.equal(details.after.items,152);assert.equal(details.before.items,121);assert(details.before.instances&&details.after.instances);assert.equal(details.preview,'true');
    if(xr){assert(details.after.file.includes('_mo.glb'));assert(details.before.file.includes('_mo.glb'));}
    assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);assert.deepEqual(failed,[]);
    fs.writeFileSync(path.join(out,profile+'.json'),JSON.stringify(details,null,2));console.log('PASS published preview',profile,details);
   }finally{await context.close();}
  }
 }finally{await browser.close();}
}
main().then(()=>process.exit(0),e=>{console.error(e);process.exit(1);});
