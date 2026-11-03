/* Use the project's local HTTPS test server. One catalogue model occupies the renderer at a time. */
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const puppeteer = require(process.env.PUPPETEER_CORE || 'puppeteer-core');
const here=__dirname, local='https://127.0.0.1:8450', base='/tools/library/kit/';
async function main(){
 const catalogue=JSON.parse(fs.readFileSync(path.join(here,'catalogue.json')));
 const stampPath=path.join(here,'thumbs','revisions.json'),previous=fs.existsSync(stampPath)?JSON.parse(fs.readFileSync(stampPath)):{};
 const light=fs.readFileSync(path.join(here,'studio-light.html'));
 const browser=await puppeteer.launch({executablePath:process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless:true, args:['--ignore-certificate-errors','--disable-background-networking','--disable-component-update','--disable-sync','--use-angle=metal'], protocolTimeout:120000});
 try{
  const page=await browser.newPage();
  page.on('pageerror',e=>console.error(e.message));
  await page.goto(local+base+'studio-light.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>typeof window.photograph==='function');
  for(const entry of catalogue.items){
   const source=path.join(here,entry.model), json=fs.readFileSync(source), model=JSON.parse(json);
   const digest=crypto.createHash('sha256').update(light).update(json);
   for(const part of [...model.buffers,...model.images||[]]){
    digest.update(fs.readFileSync(path.resolve(path.dirname(source),decodeURIComponent(part.uri))));
   }
   const hash=digest.digest('hex');
   const dest=path.join(here,entry.thumbnail);
   if(previous[entry.id]===hash && fs.existsSync(dest))continue;
   const png=await page.evaluate(url=>window.photograph(url),base+entry.model+'?v='+entry.revision);
   fs.writeFileSync(dest+'.tmp',Buffer.from(png.split(',')[1],'base64'));fs.renameSync(dest+'.tmp',dest);
   previous[entry.id]=hash;fs.writeFileSync(stampPath+'.tmp',JSON.stringify(previous,null,1));fs.renameSync(stampPath+'.tmp',stampPath);
  }
 }finally{await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
