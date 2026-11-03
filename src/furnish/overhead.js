import * as T from 'three';

// Capture the actual room below its ceiling. The saved walking camera and XR framebuffer stay independent.
export async function captureRoom(renderer,scene,entry,room,limit){
  const xs=room.polygon.map(p=>p[0]),zs=room.polygon.map(p=>p[1]);
  const x=Math.min(...xs),z=Math.min(...zs),w=Math.max(...xs)-x,d=Math.max(...zs)-z;
  const camera=new T.OrthographicCamera(-w/2,w/2,d/2,-d/2,.03,room.ceilingY-room.floorY+.1);
  camera.position.set(x+w/2,room.ceilingY-.04,z+d/2);camera.up.set(0,0,-1);
  camera.lookAt(x+w/2,room.floorY,z+d/2);camera.updateMatrixWorld();
  const scale=limit/Math.max(w,d),width=Math.max(1,Math.round(w*scale)),height=Math.max(1,Math.round(d*scale));
  const target=new T.WebGLRenderTarget(width,height,{colorSpace:T.SRGBColorSpace});
  const old=renderer.getRenderTarget(),xr=renderer.xr.enabled,viewport=renderer.getViewport(new T.Vector4());
  const scissor=renderer.getScissor(new T.Vector4()),test=renderer.getScissorTest(),cull=entry.cull,enabled=cull?.enabled;
  const shadow=renderer.shadowMap.needsUpdate;
  const hidden=scene.children.filter(o=>o.visible&&(o.userData.furnishOverlay||o.userData.gardenOverlay||o.name==='Marks'));
  const bytes=new Uint8Array(width*height*4);
  try{
    let read;
    try{
      if(cull)cull.enabled=false;
      for(const o of hidden)o.visible=false;
      renderer.xr.enabled=false;renderer.shadowMap.needsUpdate=false;renderer.setRenderTarget(target);
      renderer.setScissorTest(false);renderer.clear();renderer.render(scene,camera);
      read=renderer.readRenderTargetPixelsAsync(target,0,0,width,height,bytes);
    }finally{
      renderer.setRenderTarget(old);renderer.setViewport(viewport);renderer.setScissor(scissor);renderer.setScissorTest(test);
      renderer.xr.enabled=xr;renderer.shadowMap.needsUpdate=shadow;
      if(cull)cull.enabled=enabled;
      for(const o of hidden)o.visible=true;
    }
    await read;
    const image=document.createElement('canvas');image.width=width;image.height=height;
    const ctx=image.getContext('2d'),data=ctx.createImageData(width,height),stride=width*4;
    for(let row=0;row<height;row++)data.data.set(bytes.subarray((height-row-1)*stride,(height-row)*stride),row*stride);
    ctx.putImageData(data,0,0);
    return {image,x,z,w,d,room:room.id};
  }finally{target.dispose();}
}
