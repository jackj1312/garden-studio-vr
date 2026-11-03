// Compare the same kitchen view on the last walking frame and the first settled frame.
const assert = require('node:assert/strict');
const puppeteer = require(process.env.PUPPETEER_CORE || 'puppeteer-core');
const [url] = process.argv.slice(2);
async function main() {
  const browser = await puppeteer.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args:['--use-angle=metal','--ignore-certificate-errors','--disable-background-networking'],protocolTimeout:180000});
  try {
    const page = await browser.newPage();
    await page.setViewport({width:1200,height:750,deviceScaleFactor:2});
    await page.goto(url,{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>window.__house?.V && !document.querySelector('#startDesktop').disabled,{timeout:180000});
    await page.click('#startDesktop');
    await page.waitForNetworkIdle({idleTime:600,timeout:90000});
    const result = await page.evaluate(async ([,eye,target])=>{
      const h=window.__house, renderer=h.renderer, gl=renderer.getContext();
      if (!h.walk) h.setWalk(true);
      h.feet.set(eye[0],eye[1]-1.65,eye[2]);
      const [x,y,z]=target.map((v,i)=>v-eye[i]);
      h.yawPitch.yaw=Math.atan2(-x,-z); h.yawPitch.pitch=Math.atan2(y,Math.hypot(x,z));
      const frame=()=>new Promise(resolve=>requestAnimationFrame(resolve));
      for (let i=0;i<60;i++) await frame();
      const original=renderer.render;
      const records={}, crops={};
      const sheet=document.createElement('canvas');
      sheet.width=1024; sheet.height=512;
      const ctx=sheet.getContext('2d');

      renderer.render=function(...args){
        const ret=original.apply(this,args), mode=h.desktop.mode;
        if (!this.getRenderTarget() && ['moving','contact'].includes(mode) && !records[mode] && (mode==='moving'||records.moving)) {
          const width=gl.drawingBufferWidth,height=gl.drawingBufferHeight,n=512;
          const data=new Uint8Array(n*n*4);
          gl.readPixels((width-n)>>1,(height-n)>>1,n,n,gl.RGBA,gl.UNSIGNED_BYTE,data);
          const pixels=ctx.createImageData(n,n);
          for(let row=0;row<n;row++) pixels.data.set(data.subarray((n-row-1)*n*4,(n-row)*n*4),row*n*4);
          crops[mode]=pixels;
          let energy=0;
          for (let y=1;y<n-1;y++) for(let x=1;x<n-1;x++){
            const i=(y*n+x)*4;
            for(let c=0;c<3;c++) energy+=Math.abs(4*data[i+c]-data[i-4+c]-data[i+4+c]-data[i-n*4+c]-data[i+n*4+c]);
          }
          records[mode]={edgeEnergy:energy/(3*(n-2)**2),pose:h.camera.matrixWorld.toArray(),size:[width,height]};
        }
        return ret;
      };
      try {
        h.yawPitch.yaw+=.008;
        for(let i=0;i<200&&!records.contact;i++) await frame();
        if (crops.moving && crops.contact) {
          ctx.putImageData(crops.moving,0,0); ctx.putImageData(crops.contact,512,0);
        }
        return {records,movement:h.desktop.movementSize,inspection:h.desktop.inspectionSize,image:sheet.toDataURL('image/jpeg',.95)};
      } finally {renderer.render=original;}
    },require('./furnish_cameras.cjs')[0]);
    const image=result.image; delete result.image;
    console.log(JSON.stringify(result));
    const {moving,contact}=result.records;
    assert(moving&&contact,'both walking and settled frames rendered');
    assert.deepEqual(moving.pose,contact.pose);
    assert.deepEqual(result.inspection,[2400,1500]);
    assert.deepEqual(contact.size,result.inspection);
    assert(result.movement[0]<result.inspection[0]);
    assert(contact.edgeEnergy>=moving.edgeEnergy && moving.edgeEnergy>0,'settling must preserve fine detail');
    if(process.argv[3]) require('node:fs').writeFileSync(process.argv[3],Buffer.from(image.split(',')[1],'base64'));
  } finally {await browser.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
