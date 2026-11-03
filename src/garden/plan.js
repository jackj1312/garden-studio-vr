import {sampleGeometry, handlesOf, centerOf, isClosed, outlineMeasurements} from './geometry.mjs';
import {KINDS,MATERIALS,SPECIES} from './catalogue.mjs';

const cssColour=(m, fallback='#a38f74')=>m?.color??fallback;
export function createGardenPlan(T,{renderer,scene,canvas,terrain}) {
  const picture=document.createElement('canvas'),base=document.createElement('canvas');
  let full=null,view=null,background=false,objects=[],selection=null,stroke=null,editing=false;
  let lastBox=null;
  const scaledBounds=(b,s,anchor)=>({x0:anchor[0]+(b.x0-anchor[0])*s,x1:anchor[0]+(b.x1-anchor[0])*s,z0:anchor[1]+(b.z0-anchor[1])*s,z1:anchor[1]+(b.z1-anchor[1])*s});
  function version(b){full={...b};view={...b};background=false;lastBox=null;resizePicture();}
  function resizePicture(){
    const aspect=(full.x1-full.x0)/(full.z1-full.z0);
    picture.width=Math.round(Math.min(1024,1024*aspect));picture.height=Math.round(Math.min(1024,1024/aspect));base.width=picture.width;base.height=picture.height;
  }
  function capture(){
    if(background||!full)return;
    const cx=(full.x0+full.x1)/2,cz=(full.z0+full.z1)/2,w=full.x1-full.x0,h=full.z1-full.z0;
    const camera=new T.OrthographicCamera(-w/2,w/2,h/2,-h/2,.1,180);camera.position.set(cx,70,cz);camera.up.set(0,0,-1);camera.lookAt(cx,0,cz);camera.updateMatrixWorld();
    const target=new T.WebGLRenderTarget(base.width,base.height,{colorSpace:T.SRGBColorSpace});
    const old=renderer.getRenderTarget(),xr=renderer.xr.enabled,oldViewport=renderer.getViewport(new T.Vector4()),oldScissor=renderer.getScissor(new T.Vector4()),scissor=renderer.getScissorTest();
    const hidden=scene.children.filter(o=>o.visible&&(o.userData.gardenOverlay||o.name==='Marks'));hidden.forEach(o=>o.visible=false);
    try {
      renderer.xr.enabled=false;renderer.setRenderTarget(target);renderer.setScissorTest(false);renderer.clear();terrain.surveyOnly(()=>renderer.render(scene,camera));
      const bytes=new Uint8Array(base.width*base.height*4);renderer.readRenderTargetPixels(target,0,0,base.width,base.height,bytes);
      const ctx=base.getContext('2d'),img=ctx.createImageData(base.width,base.height),stride=base.width*4;
      for(let y=0;y<base.height;y++)img.data.set(bytes.subarray((base.height-y-1)*stride,(base.height-y)*stride),y*stride);
      ctx.putImageData(img,0,0);background=true;
    }finally{hidden.forEach(o=>o.visible=true);renderer.setRenderTarget(old);renderer.setViewport(oldViewport);renderer.setScissor(oldScissor);renderer.setScissorTest(scissor);renderer.xr.enabled=xr;target.dispose();}
    render();
  }
  function overlay(ctx,width,height,b,showHandles) {
    const sx=width/(b.x1-b.x0),sy=height/(b.z1-b.z0);
    const xy=([x,z])=>[(x-b.x0)*sx,(z-b.z0)*sy];
    for(const f of objects){
      const color=cssColour(MATERIALS[f.material]),sel=showHandles&&f.id===selection;
      const path=sampleGeometry(f.geometry,.018).map(xy);
      ctx.save();ctx.lineJoin='round';ctx.lineCap='round';ctx.strokeStyle=sel?'#ffda85':color;
      if(f.geometry.type==='point'){
        const [x,y]=xy(f.geometry.center),r=Math.max(4,f.width*.5*sx);ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=SPECIES[f.species]?.color||'#729464';ctx.fill();ctx.lineWidth=sel?3:1;ctx.stroke();
      }else{
        ctx.beginPath();path.forEach(([x,y],i)=>ctx[i?'lineTo':'moveTo'](x,y));
        if(isClosed(f.geometry))ctx.closePath();
        if(KINDS[f.kind].form==='area'){ctx.fillStyle=color;ctx.globalAlpha=.82;ctx.fill();ctx.globalAlpha=1;ctx.lineWidth=sel?3:1.4;ctx.stroke();}
        else{ctx.lineWidth=Math.max(2,f.width*sx);ctx.stroke();if(sel){ctx.lineWidth=1;ctx.strokeStyle='#473d2a';ctx.stroke();}}
      }
      if(sel){
        if(f.geometry.type==='curve')for(const k of f.geometry.knots){const a=xy(k.in),q=xy(k.p),c=xy(k.out);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...q);ctx.lineTo(...c);ctx.strokeStyle='#ffecca';ctx.lineWidth=1;ctx.stroke();}
        for(const h of handlesOf(f.geometry)){const [x,y]=xy(h.point);ctx.beginPath();ctx.arc(x,y,h.kind==='tangent'?3.4:5,0,Math.PI*2);ctx.fillStyle=h.kind==='tangent'?'#8cd2da':h.kind==='rotate'?'#efad66':'#fff5d3';ctx.fill();ctx.lineWidth=1.4;ctx.strokeStyle='#433c2e';ctx.stroke();}
      }
      if(sel && f.kind==='outbuilding-base'){
        const m=outlineMeasurements(f.geometry),placed=[];
        const size=Math.max(11,Math.min(18,width/64));
        ctx.font='600 '+size+'px system-ui';ctx.textBaseline='middle';ctx.textAlign='center';
        const label=(p,text)=>{
          const [x,y]=xy(p),w=ctx.measureText(text).width+8,h=size+6;
          if(x<0||x>width||y<0||y>height||placed.some(b=>Math.abs(b.x-x)<(b.w+w)/2+2&&Math.abs(b.y-y)<h+2))return;
          ctx.fillStyle='#17251ee8';ctx.fillRect(x-w/2,y-h/2,w,h);ctx.fillStyle='#fff3c9';ctx.fillText(text,x,y);placed.push({x,y,w});
        };
        const centre=centerOf(f.geometry);
        if(m.radius!=null)label(centre,'Ø '+(2*m.radius).toFixed(3)+' m');
        else label(centre,m.area.toFixed(3)+' m²');
        for(const edge of m.segments)label(edge.at,edge.length.toFixed(3)+' m');
      }
      ctx.restore();
    }
    if(stroke?.length){ctx.beginPath();stroke.map(xy).forEach(([x,y],i)=>ctx[i?'lineTo':'moveTo'](x,y));ctx.strokeStyle='#ffe59d';ctx.lineWidth=3;ctx.stroke();}
  }
  function render(){
    if(!full)return;
    picture.gardenRevision=(picture.gardenRevision||0)+1;
    const c=picture.getContext('2d');c.clearRect(0,0,picture.width,picture.height);c.drawImage(base,0,0);overlay(c,picture.width,picture.height,full,editing);
    if(!canvas.isConnected||canvas.hidden)return;
    const r=canvas.getBoundingClientRect(),ratio=Math.min(2,devicePixelRatio);if(r.width<2||r.height<2)return;
    const w=Math.round(r.width*ratio),h=Math.round(r.height*ratio);if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
    const scale=Math.min(w/(view.x1-view.x0),h/(view.z1-view.z0)),cx=(view.x1+view.x0)/2,cz=(view.z1+view.z0)/2;
    lastBox={x0:cx-w/scale/2,x1:cx+w/scale/2,z0:cz-h/scale/2,z1:cz+h/scale/2};
    const ctx=canvas.getContext('2d');ctx.fillStyle='#29332d';ctx.fillRect(0,0,w,h);
    ctx.drawImage(base,(full.x0-lastBox.x0)*scale,(full.z0-lastBox.z0)*scale,(full.x1-full.x0)*scale,(full.z1-full.z0)*scale);
    overlay(ctx,w,h,lastBox,editing);
    const metres=scale*2<150*ratio?2:1;ctx.strokeStyle='#f5eddb';ctx.fillStyle='#29332ddd';ctx.fillRect(12*ratio,h-41*ratio,metres*scale+26*ratio,31*ratio);ctx.fillStyle='#fff7e4';ctx.font=12*ratio+'px system-ui';ctx.fillText(metres+' m',20*ratio,h-23*ratio);ctx.lineWidth=2*ratio;ctx.beginPath();ctx.moveTo(20*ratio,h-17*ratio);ctx.lineTo(20*ratio+metres*scale,h-17*ratio);ctx.stroke();
  }
  function at(x,y){const r=canvas.getBoundingClientRect(),b=lastBox||view;return [b.x0+(x-r.left)/r.width*(b.x1-b.x0),b.z0+(y-r.top)/r.height*(b.z1-b.z0)];}
  function pan(dx,dz){view={x0:view.x0+dx,x1:view.x1+dx,z0:view.z0+dz,z1:view.z1+dz};render();}
  function zoom(f,anchor){const span=(view.z1-view.z0)*f;if(span>1&&span<130){view=scaledBounds(view,f,anchor);render();}}
  return {version,capture,render,at,pan,zoom,fit(){view={...full};render();},get full(){return full;},get image(){return picture;},update(list,id,points,on){objects=list;selection=id;stroke=points;editing=on;render();},invalidate(){background=false;},get ready(){return background;},metres(px){return px*((lastBox||view).x1-(lastBox||view).x0)/Math.max(1,canvas.clientWidth);}};
}

