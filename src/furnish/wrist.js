import {helpPage} from '../editor-help.js';
import {studioAsset} from '../studio-layout-service.js';
const W=672,H=770;
const paints=['#f7f4ed','#e2d5c4','#d3cbbd','#ceb89f','#c3cdbb','#94a69b','#9aaeba','#7b8f98','#555f59','#684c47','#73805d','#c6b5bc'];
export function createFurnitureWrist(T,{scene,camera,state,action,plan}){
 const surface=(w,h,name)=>{
  const c=document.createElement('canvas');c.width=W;c.height=H;const m=new T.CanvasTexture(c);m.colorSpace=T.SRGBColorSpace;m.generateMipmaps=false;m.minFilter=T.LinearFilter;
  const mesh=new T.Mesh(new T.PlaneGeometry(w,h),new T.MeshBasicMaterial({map:m,toneMapped:false,depthWrite:false,depthTest:false}));mesh.name=name;mesh.userData.furnishOverlay=true;mesh.visible=false;mesh.renderOrder=1930;scene.add(mesh);return mesh;
 };
 const wrist=surface(.26,.26*H/W,'Furnish · left wrist'),table=surface(.76,.76,'Furnish · room plan');table.renderOrder=1929;
 const ctx=wrist.material.map.image.getContext('2d'),q=new T.Raycaster(),head=new T.Vector3(),fwd=new T.Vector3();
 const art=new Map();let boxes=[],page='home',offset=0,help=0,cache='',rev=-1,on=false,wasBird=false,latch=false;
 function go(key){page=key;offset=0;cache='';}
 function rect(text,x,y,w,h,callback,img=null,colour=null){
  ctx.fillStyle=colour||'#3a493e';ctx.fillRect(x,y,w,h);ctx.strokeStyle='#738078';ctx.strokeRect(x,y,w,h);
  if(img){const key=img;let im=art.get(key);if(!im){im=new Image();im.onload=()=>{cache='';};im.src=studioAsset('/tools/library/kit/'+key);art.set(key,im);}if(im.complete&&im.naturalWidth)ctx.drawImage(im,x+5,y+4,h-8,h-8);}
  ctx.fillStyle='#f3f1e4';ctx.font='600 24px system-ui';ctx.textAlign='left';ctx.fillText(text,x+(img?h+8:12),y+h*.62,w-(img?h+15:22));boxes.push({text,x,y,w,h,callback});
 }
 function lines(str,x,y,limit,size=25){
  ctx.font=size+'px system-ui';ctx.fillStyle='#e0eadc';let line='';
  for(const word of str.split(' ')){if(ctx.measureText(line+' '+word).width>limit&&line){ctx.fillText(line,x,y);y+=size*1.35;line='';}line+=(line?' ':'')+word;}if(line)ctx.fillText(line,x,y);return y;
 }
 function render(s){
  const signature=JSON.stringify([page,offset,help,s.room?.id,s.detail,s.selected?.id,s.selected?.rotation,s.pending,s.filtered.length,s.filters,s.face,s.floor,s.colour,s.status,s.verdict?.ok,s.undo,s.redo,s.dirty,s.revision]);
  if(signature===cache)return;cache=signature;boxes=[];ctx.fillStyle='#203029';ctx.fillRect(0,0,W,H);ctx.fillStyle='#c2d7ac';ctx.font='600 19px system-ui';ctx.fillText('GARDEN STUDIO',20,36);
  ctx.fillStyle='#fff8e7';ctx.font='600 37px system-ui';ctx.fillText(page==='home'?'Furnish a room':page==='help'?'How to use':page[0].toUpperCase()+page.slice(1),20,83);
  ctx.fillStyle='#c8d6c7';ctx.font='22px system-ui';ctx.fillText(s.room?.label||'Choose a room',22,122,W-44);
  const half=(label,y,col,fn)=>rect(label,20+col*320,y,305,59,fn);
  if(page==='home'){
   [['Catalogue','catalogue'],['Rooms','rooms'],['Wall faces','faces'],['Floor covering','floors']].forEach(([t,k],i)=>half(t,147+Math.floor(i/2)*70,i%2,()=>go(k)));
   half(s.bird?'Walking view':'Bird’s-eye',292,0,()=>action(s.bird?'stand':'bird'));half('Views',292,1,()=>go('views'));
   half('Rotate −15°',362,0,()=>action('rotate-left'));half('Rotate +15°',362,1,()=>action('rotate-right'));
   half('Copy',432,0,()=>action('copy'));half('Delete',432,1,()=>action('delete'));half('Undo',502,0,()=>action('undo'));half('Redo',502,1,()=>action('redo'));
   half('Save layout',572,0,()=>action('save'));half('Garden',572,1,()=>action('garden'));
  }else if(page==='help'){
   const rows=helpPage('furnish')[1],[title,detail]=rows[help%rows.length];ctx.font='bold 30px system-ui';ctx.fillStyle='#fff8e7';ctx.fillText(title,24,195,W-48);lines(detail,24,248,W-52,29);
   half('Next',545,0,()=>{help=(help+1)%rows.length;cache='';});half('Dismiss help',545,1,()=>go('home'));
  }else{
   let choices=[],perPage=5,top=150;
   if(page==='catalogue'){
    half('Kind',143,0,()=>go('kind'));half('Style',143,1,()=>go('style'));half('Room type',211,0,()=>go('roomType'));half('Select item',211,1,()=>action('select'));
    half('Raise 1 cm',277,0,()=>action('PageUp'));half('Lower 1 cm',277,1,()=>action('PageDown'));
    top=345;perPage=3;choices=s.filtered.map(i=>[i.name,()=>{action('add',i.id);go('home');},i.thumbnail]);
   }else if(page==='views')choices=[
     ['Plan',()=>{action('plan-view');go('home');}],['Detailed 3D',()=>{action('detail-view');go('home');}],
     ['Walking view',()=>{action('stand');go('home');}],['Close editor',()=>action('close')]];
   else if(page==='rooms')choices=s.rooms.map(r=>[r.label||r.id,()=>{action('room',r.id);go('home');}]);
   else if(page==='faces')choices=(s.room?.wallFaces||[]).map((f,i)=>[f.label||'Wall '+(i+1),()=>{action('face',f.id);go('colour');}]);
   else if(page==='floors')choices=[['Original covering',()=>{action('floor','');go('home');}],...s.floors.map(f=>[f.name,()=>{action('floor',f.id);go('home');}])];
   else if(page==='colour')choices=paints.map(c=>[c,()=>{action('colour',c);go('home');},null,c]);
   else {const opts=page==='kind'?s.kinds:page==='style'?s.styles:s.roomTypes;choices=[['All',()=>{action(page,'');go('catalogue');}],...opts.map(v=>[v,()=>{action(page,v);go('catalogue');}])];}
   offset=Math.min(offset,Math.max(0,Math.ceil(choices.length/perPage)-1));
   choices.slice(offset*perPage,(offset+1)*perPage).forEach(([t,fn,img,col],i)=>rect(t,20,top+i*65,W-40,58,fn,img,col));
   half('Previous page',572,0,()=>{offset=Math.max(0,offset-1);cache='';});half('Next page',572,1,()=>{offset=Math.min(Math.max(0,Math.ceil(choices.length/perPage)-1),offset+1);cache='';});
  }
  half('Home',655,0,()=>go('home'));half('How to use',655,1,()=>{help=0;go('help');});
  ctx.fillStyle=s.verdict?.ok===false?'#ffaf9e':'#c3d2c0';ctx.font='19px system-ui';ctx.fillText(s.status||s.selected?.label||'Right trigger to place or move',22,749,W-44);wrist.material.map.needsUpdate=true;
 }
 function update(left,enabled){
  if(!enabled){wrist.visible=table.visible=false;on=false;latch=false;wasBird=false;return;}
  const s=state();if(!on){go('home');on=true;}render(s);
  camera.getWorldPosition(head);wrist.visible=!!left;
  if(left){const pos=left.localToWorld(new T.Vector3(.04,.10,-.09));wrist.position.copy(scene.worldToLocal(pos));wrist.lookAt(head);wrist.updateMatrixWorld();}
  table.visible=s.bird;if(s.bird&&!wasBird){
   camera.getWorldDirection(fwd);fwd.y=0;fwd.normalize();const pos=head.clone().addScaledVector(fwd,.95);pos.x-=fwd.z*.20;pos.z+=fwd.x*.20;pos.y-=.04;
   table.position.copy(scene.worldToLocal(pos));table.lookAt(head);table.updateMatrixWorld();
  }
  if(s.bird&&rev!==plan.image.furnishRevision){rev=plan.image.furnishRevision;const c=table.material.map.image;c.width=c.height=768;c.getContext('2d').drawImage(plan.image,0,0);table.material.map.needsUpdate=true;}
  wasBird=s.bird;
 }
 function intersect(ray,mesh){if(!mesh.visible)return null;q.ray.copy(ray);return q.intersectObject(mesh,false)[0];}
 function hitWrist(ray,pressed){
  const h=intersect(ray,wrist);if(!h)return null;const x=h.uv.x*W,y=(1-h.uv.y)*H;
  if(pressed){boxes.find(b=>x>=b.x&&y>=b.y&&x<=b.x+b.w&&y<=b.y+b.h)?.callback?.();cache='';}return h.distance;
 }
 function hitPlan(ray){const h=intersect(ray,table);if(!h)return null;const p=plan.onUV(h.uv.x,h.uv.y);return p?{point:new T.Vector3(p[0],state().room.floorY,p[1]),normal:new T.Vector3(0,1,0),displayPoint:h.point,distance:h.distance}:null;}
 function wristWorld(label){const b=boxes.find(v=>v.text===label);return b?wrist.localToWorld(new T.Vector3(((b.x+b.w/2)/W-.5)*.26,(.5-(b.y+b.h/2)/H)*.26*H/W,0)):null;}
 function planWorld(p){const uv=plan.toUV(p);return uv?table.localToWorld(new T.Vector3((uv[0]-.5)*.76,(uv[1]-.5)*.76,0)):null;}
 return {update,hitWrist,hitPlan,wristWorld,planWorld};
}

