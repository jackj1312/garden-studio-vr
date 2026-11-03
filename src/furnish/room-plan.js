import {floorRecipe} from './floor-recipe.mjs';
const vec=(p)=>Array.isArray(p)?[p[0],p.length>2?p[2]:p[1]]:[p.x,p.z];
const ring=r=>(r?.polygon||[]).map(vec);
const sizeOf=f=>f.size||[.4,.4,.4];
export function itemCorners(f){
 const [w,d]=sizeOf(f),[cx,,cz]=f.position,t=(f.rotation||0)*Math.PI/180,a=Math.cos(t),b=Math.sin(t);
 return [[-1,-1],[1,-1],[1,1],[-1,1]].map(([x,z])=>[cx+x*w*a/2+z*d*b/2,cz-x*w*b/2+z*d*a/2]);
}
export function containsXZ(p,polygon){
 let inside=false;for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){
  const a=polygon[i],b=polygon[j];if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
 }return inside;
}
export function createRoomPlan(canvas){
 let room=null,items=[],selected=null,preview=null,verdict=null,objects=[],fit=null,dirty=true,appearance={};
 const photos=new Map();
 const picture=document.createElement('canvas');picture.width=picture.height=768;
 const poly=(ctx,list,map,close=true)=>{ctx.beginPath();list.map(map).forEach(([x,z],i)=>ctx[i?'lineTo':'moveTo'](x,z));if(close)ctx.closePath();};
 function draw(el){
  const points=ring(room);if(points.length<3)return;
  const w=el.width,h=el.height,c=el.getContext('2d');c.fillStyle='#23312a';c.fillRect(0,0,w,h);
  const xs=points.map(p=>p[0]),zs=points.map(p=>p[1]),x0=Math.min(...xs)-.4,x1=Math.max(...xs)+.4,z0=Math.min(...zs)-.4,z1=Math.max(...zs)+.4;
  const m=Math.min(w/(x1-x0),h/(z1-z0))*.91,ox=(w-(x1-x0)*m)/2-x0*m,oz=(h-(z1-z0)*m)/2-z0*m;
  const xy=([x,z])=>[ox+x*m,oz+z*m];
  poly(c,points,xy);c.fillStyle=appearance.floor?.hex||'#d7c9ad';c.fill();
  const recipe=appearance.floor&&floorRecipe(appearance.floor);
  if(recipe?.photo){
    let im=photos.get(recipe.source);
    if(!im){im=new Image();photos.set(recipe.source,im);im.onload=()=>{dirty=true;render();};im.src=new URL('../../tools/library/kit/maps/'+recipe.source,import.meta.url);}
    if(im.naturalWidth){const pat=c.createPattern(im,'repeat');pat.setTransform(new DOMMatrix().translate(ox,oz).scale(m*recipe.repeat[0]/im.width,m*recipe.repeat[1]/im.height));c.fillStyle=pat;c.fill();}
  }
  c.strokeStyle='#4a5147';c.lineWidth=Math.max(5,m*.12);c.stroke();
  c.save();poly(c,points,xy);c.clip();c.strokeStyle='#7b7f702e';c.lineWidth=1;
  for(let z=Math.floor(z0*2)/2;z<z1;z+=.5){poly(c,[[x0,z],[x1,z]],xy,false);c.stroke();}
  for(let x=Math.floor(x0*2)/2;x<x1;x+=.5){poly(c,[[x,z0],[x,z1]],xy,false);c.stroke();}c.restore();
  const arr=items.filter(f=>f.room===room.id&&f.id!==preview?.id);
  if(preview)arr.push(preview);
  const low=f=>/rug|carpet|runner|mat/.test(f.kind)?-1000:f.position[1]-room.floorY+(f.host.type==='surface'?.001:0);
  arr.sort((a,b)=>low(a)-low(b));objects=arr;
  const drawnLabels=[];
  for(const f of arr){
    const on=selected===f.id||f===preview, rug=low(f)<0,blocked=f===preview&&!verdict?.ok;
    const pos=xy([f.position[0],f.position[2]]),w=sizeOf(f)[0]*m,d=sizeOf(f)[1]*m;
    c.save();c.translate(...pos);c.rotate(-(f.rotation||0)*Math.PI/180);
    c.strokeStyle=on?'#254a36':'#56594c';c.lineWidth=on?3:1.5;
    c.fillStyle=blocked?'#ca635b':on?'#a8b787':rug?'#b39a7a':/sofa|chair|bed|cushion|throw/.test(f.kind)?'#b7ab97':'#a69983';
    if(/plant|lamp|vase/.test(f.kind)){
      c.beginPath();c.ellipse(0,0,Math.max(2,w/2),Math.max(2,d/2),0,0,2*Math.PI);c.fill();c.stroke();
    }else{
      c.fillRect(-w/2,-d/2,w,d);c.strokeRect(-w/2,-d/2,w,d);
      if(rug){c.setLineDash([4,3]);c.strokeRect(-w*.46,-d*.46,w*.92,d*.92);}
      if(/sofa|armchair|dining_chair|chair/.test(f.kind)){
        c.beginPath();c.moveTo(-w*.44,d*.34);c.lineTo(w*.44,d*.34);c.moveTo(-w*.41,-d*.43);c.lineTo(-w*.41,d*.35);c.moveTo(w*.41,-d*.43);c.lineTo(w*.41,d*.35);
        if(/sofa/.test(f.kind)){c.moveTo(0,-d*.42);c.lineTo(0,d*.35);}c.stroke();
      }else if(/bed/.test(f.kind)){c.strokeRect(-w*.42,d*.18,w*.36,d*.23);c.strokeRect(w*.06,d*.18,w*.36,d*.23);}
    }
    c.restore();
    if(on || (Math.min(w,d)>38 && w>66 && !rug && f.host.type!=='surface')){
      const size=Math.max(12,Math.min(17,w*.14));c.font=(on?'600 ':'')+size+'px system-ui';c.textAlign='center';
      let title=f.label||f.name||f.kind;const limit=Math.max(36,on?145:w-6);while(title.length>2&&c.measureText(title).width>limit)title=title.slice(0,-2)+'…';
      if(c.measureText(title).width<=limit)drawnLabels.push({on,title,x:pos[0],y:pos[1],size});
    }
  }
  for(const face of room.wallFaces||[]){const colour=appearance.walls?.[face.id];if(!colour||!face.a||!face.b)continue;poly(c,[face.a,face.b],xy,false);c.lineWidth=Math.max(4,m*.08);c.strokeStyle=colour;c.stroke();}
  for(const o of appearance.openings||[]){if(!room.wallFaces?.some(f=>f.wall===o.wall))continue;poly(c,[o.p0,o.p1],xy,false);c.lineWidth=Math.max(6,m*.13);c.strokeStyle=o.kind==='window'?'#aec4c0':'#eadfca';c.stroke();}
  for(const f of room.wallFaces||[])if(f.id===appearance.face&&f.a&&f.b){
    poly(c,[f.a,f.b],xy,false);c.strokeStyle='#173744';c.lineWidth=10;c.stroke();c.strokeStyle='#59e5fd';c.lineWidth=5;c.stroke();
  }
  const occupied=[];
  for(const t of drawnLabels.sort((a,b)=>Number(b.on)-Number(a.on))){
    c.font=(t.on?'600 ':'')+t.size+'px system-ui';const w=c.measureText(t.title).width+8,h=t.size+5;
    if(occupied.some(o=>Math.abs(t.x-o.x)<(w+o.w)/2&&Math.abs(t.y-o.y)<h))continue;
    c.fillStyle=t.on?'#233e31e6':'#e7dcc794';c.fillRect(t.x-w/2,t.y-h/2,w,h);c.fillStyle=t.on?'#faf6e7':'#28342b';c.textAlign='center';c.fillText(t.title,t.x,t.y+t.size*.34);occupied.push({...t,w});
  }
  const active=arr.find(f=>f.id===selected||f===preview);
  if(active){poly(c,itemCorners(active),xy);c.strokeStyle=verdict?.ok===false?'#ca4137':'#335942';c.lineWidth=3;c.stroke();}
  c.fillStyle='#edece3';c.font='600 '+Math.max(14,w/42)+'px system-ui';c.textAlign='left';c.fillText(room.label||room.name||room.id,16,30);
  const scale=Math.max(24,m);c.fillRect(16,h-18,scale,2);c.font='13px system-ui';c.fillText('1 m',16,h-23);
  if(el===canvas)fit={m,ox,oz};
  return {m,ox,oz,w,h};
 }
 let pictureFit=null;
 function render(){
  if(!dirty)return;dirty=false;pictureFit=draw(picture);picture.furnishRevision=(picture.furnishRevision||0)+1;
  if(!canvas.hidden){const b=canvas.getBoundingClientRect();canvas.width=Math.max(1,Math.round(b.width));canvas.height=Math.max(1,Math.round(b.height));draw(canvas);}
 }
 function point(x,y){const b=canvas.getBoundingClientRect();if(!fit)return null;return [(x-b.left-fit.ox)/fit.m,(y-b.top-fit.oz)/fit.m];}
 function onUV(u,v){return pictureFit?[(u*picture.width-pictureFit.ox)/pictureFit.m,((1-v)*picture.height-pictureFit.oz)/pictureFit.m]:null;}
 function pick(p){return [...objects].reverse().find(f=>containsXZ(p,itemCorners(f)))||null;}
 return {set(r,list,id,d,v,surface={}){room=r;items=list;selected=id;preview=d;verdict=v;appearance=surface;dirty=true;render();},resize(){dirty=true;render();},point,onUV,pick,wallAt(p){
   let id=null,limit=Math.max(.1,10/(fit?.m||pictureFit?.m||100));
   for(const f of room?.wallFaces||[]){
     if(!f.a||!f.b)continue;
     const [x,z]=f.a,dx=f.b[0]-x,dz=f.b[1]-z,t=Math.max(0,Math.min(1,((p[0]-x)*dx+(p[1]-z)*dz)/(dx*dx+dz*dz||1)));
     const d=Math.hypot(p[0]-x-t*dx,p[1]-z-t*dz);if(d<limit){limit=d;id=f.id;}
   }
   return id;
 },toUV(p){return pictureFit?[(pictureFit.ox+p[0]*pictureFit.m)/picture.width,1-(pictureFit.oz+p[1]*pictureFit.m)/picture.height]:null;},get image(){return picture;},get room(){return room;}};
}

