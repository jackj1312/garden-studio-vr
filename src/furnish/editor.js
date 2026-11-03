import * as T from 'three';
import {openLayoutEditor,layoutFetcher,studioAsset,previewPrefix} from '../studio-layout-service.js';
import {FurnitureLayout} from './layout.mjs';
import {loadRoomContext,assessDesign,snapPlacement,fineMove,moveGroup,validateFurnishDelta} from './placement.mjs';
import {createFurnitureModels} from './models.js';
import {createFurniturePanel} from './panel.js';
import {createRoomPlan,containsXZ,itemCorners} from './room-plan.js';
import {createFinishOverrides} from './finishes.js';
import {captureRoom} from './overhead.js';
import {createFurnitureWrist} from './wrist.js';

const fetchAsset=(url,opts)=>fetch(studioAsset(url),opts);
const fetchJSON=async url=>{const r=await fetchAsset(url);if(!r.ok)throw Error('Cannot read '+url);return r.json();};
const degrees=Math.PI/180;
const stockRoom=r=>{const name=(r?.label||r?.name||'').toLowerCase();
 if(/bedroom/.test(name))return 'bedroom';if(/bath|suite|cloak/.test(name))return 'bathroom';if(/kitchen/.test(name))return 'kitchen';
 if(/dining/.test(name))return 'dining';if(/living|lounge|sitting/.test(name))return 'living';if(/utility/.test(name))return 'utility';if(/study|office/.test(name))return 'study';if(/hall|landing|porch/.test(name))return 'hall';return '';
};
const nearest=(v,candidates)=>candidates.reduce((best,item)=>{const a=item.a,b=item.b;if(!a||!b)return best;
 const dx=b[0]-a[0],dz=b[1]-a[1],u=Math.max(0,Math.min(1,((v[0]-a[0])*dx+(v[1]-a[1])*dz)/(dx*dx+dz*dz||1)));
 const d=Math.hypot(v[0]-a[0]-u*dx,v[1]-a[1]-u*dz);return !best||d<best.d?{d,item}:best;},null)?.item;
export function createFurnishingEditor({scene,camera,renderer,site,inVR,houseHit,prepare,walkPreview,goRoom,openGarden,changedShadow,lite=false}){
 const stores=new Map(),canvas=document.createElement('canvas');canvas.id='furnish-plan';canvas.hidden=true;canvas.setAttribute('aria-label','Bird’s-eye furniture plan');document.body.append(canvas);
 const plan=createRoomPlan(canvas);
 const line=new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(1,1,1)),new T.LineBasicMaterial({color:0xb4e59b,depthTest:false,toneMapped:false}));line.userData.furnishOverlay=true;line.renderOrder=995;line.visible=false;scene.add(line);
 let entry=null,ctx=null,layout=null,models=null,finish=null,kit=[],floors=[],catalogueData=null,versionTicket=0,ready=null,modelReady=Promise.resolve();
 let collapsed=false,resumeBird=true,detail=false,detailDirty=true,detailBusy=false,detailTime=0;
 function invalidateView(){detailDirty=true;}
 function updateDetail(now){
   const room=getRoom(),version=entry;
   if(!active||!bird||!detail||!room||!entry||!detailDirty||detailBusy||now-detailTime<(inVR()?200:70))return;
   detailBusy=true;detailDirty=false;detailTime=now;
   captureRoom(renderer,scene,entry,room,inVR()?512:1000).then(frame=>{
     if(detail&&version===entry&&room.id===getRoom()?.id)plan.background(frame);
   }).catch(error=>{detail=false;status='Detailed view unavailable · '+error.message;sync();}).finally(()=>{detailBusy=false;});
 }
 let active=false,bird=true,roomId='',selectedId='',face='',pending='',draft=null,verdict=null,drag=null,stage=0,furnished=true,status='',vrWas=false,retry=false,indoorLite=false;
 const filters={kind:'',style:'',roomType:'current',query:''};
 const raycaster=new T.Raycaster(),ndc=new T.Vector2();
 const getRoom=()=>ctx?.rooms.find(r=>r.id===roomId)||ctx?.rooms[0]||null;
 const panel=createFurniturePanel(action),wrist=createFurnitureWrist(T,{scene,camera,state,action,plan});
 const typedRooms=()=>[...new Set(kit.flatMap(c=>c.roomTypes||[]))].sort();
 function state(){
   const room=getRoom(),roomType=filters.roomType==='current'?stockRoom(room):filters.roomType;
   const allowedByRoom=c=>!roomType||!c.roomTypes?.length||c.roomTypes.includes('any')||c.roomTypes.includes(roomType)||
     (roomType==='kitchen' && c.roomTypes.includes('dining'))||(roomType==='hall'&&c.roomTypes.includes('entry'));
   const filtered=kit.filter(c=>allowedByRoom(c)&&(!filters.kind||c.kind===filters.kind)&&(!filters.style||c.style===filters.style||c.style==='shared')&&(!filters.query||[c.name,c.kind,c.style].join(' ').toLowerCase().includes(filters.query.toLowerCase())));
   return {active,collapsed,bird,detail,site,version:entry?.def.id||'',room,rooms:ctx?.rooms||[],selected:layout?.get(selectedId)||null,pending,filtered,filters,
     kinds:[...new Set(kit.map(c=>c.kind))].sort(),styles:[...new Set(kit.map(c=>c.style))].filter(s=>s!=='shared').sort(),roomTypes:typedRooms(),
     items:layout?.items||[],floors,face,colour:layout?.wallColours?.[face]||'',floor:layout?.roomFloors?.[room?.id]||'',
     status:verdict?.reasons.length?verdict.reasons.join(' · '):status,verdict,dirty:layout?.dirty,undo:layout?.canUndo,redo:layout?.canRedo,
     saving:layout?.saving,conflict:layout?.conflict||retry,revision:layout?.revision||0};
 }
 function sync(){
   invalidateView();
   const s=state(),items=s.items;
   if(models){
     let display=items;if(draft){const group=moveGroup(items,draft),ids=new Set(group.map(f=>f.id));display=[...items.filter(f=>!ids.has(f.id)),...group];}
     // In Quest garden mode only indoor loose pieces are suppressed. The scene, fixed joinery and glazing remain present.
     const visible=furnished&&!indoorLite;modelReady=models.set(display,{visible,stage});modelReady.catch(e=>{status=e.message;if(active)panel.update(state());});
     finish?.apply(layout.wallColours,layout.roomFloors);
   }
   const outline=draft||s.selected;line.visible=active&&!!outline&&furnished;
   if(line.visible){line.position.set(outline.position[0],outline.position[1]+outline.size[2]/2,outline.position[2]);line.rotation.y=outline.rotation*degrees;
      line.scale.set(outline.size[0]+.018,outline.size[2]+.018,outline.size[1]+.018);line.material.color.setHex(verdict?.ok===false?0xf05c52:0xa8e29d);}
   if(active){plan.set(s.room,items,selectedId,draft,verdict,{floor:floors.find(f=>f.id===s.floor),walls:layout?.wallColours,face,openings:ctx?.openings,detail});panel.update(s);}else panel.update(s);
   changedShadow?.();
 }
 async function useVersion(v,{force=false}={}){
   if(entry===v&&ready&&(!force||ctx))return ready;
   const ticket=++versionTicket;entry=v;ctx=null;models?.dispose();models=null;finish?.clear();finish=null;layout=null;draft=null;drag=null;selectedId='';face='';pending='';status='';
   ready=null;const runtime=v.def.furnish_runtime;
   if(!runtime&&!force&&!active){sync();return;}
   ready=(async()=>{
     try{
       const specSite=previewPrefix()?site:v.def.spec_site||(site==='house-wip'?'house':site);
       const [context,stock,choices,variants]=await Promise.all([loadRoomContext({site,version:v.def.id,specSite,fetcher:fetchAsset}),catalogueData??(catalogueData=fetchJSON('/tools/library/kit/catalogue.json')),fetchJSON('/assets/sites/'+specSite+'/spec/catalogue_v1.json'),runtime?fetchJSON('/assets/sites/'+site+'/'+runtime.variants):Promise.resolve({variants:{}})]);
       if(ticket!==versionTicket)return;ctx=context;kit=stock.items;floors=choices.floors||[];
       if(!stores.has(v.def.id))stores.set(v.def.id,new FurnitureLayout({site,version:v.def.id,fetcher:layoutFetcher(site,v.def.id),onChange:()=>{if(layout===stores.get(v.def.id))sync();}}));
       layout=stores.get(v.def.id);await layout.load();if(ticket!==versionTicket)return;
       roomId=ctx.rooms.find(r=>r.id===roomId)?.id||ctx.rooms.find(r=>stockRoom(r)==='living')?.id||ctx.rooms[0]?.id||'';
       models=createFurnitureModels({THREE:T,scene,site,version:v.def.id,variants,catalogue:kit,lite,onChange:()=>{changedShadow?.();invalidateView();}});
       finish=createFinishOverrides(v.model,floors,invalidateView);
       if(!runtime&&(!layout.items.length))status='This version has no movable-item seed yet. The house still shows its built-in furnishings.';
       sync();
     }catch(e){if(ticket===versionTicket){status=e.message;sync();}}
   })();return ready;
 }
 function fit(){
   if(canvas.hidden)return;const b=panel.el.getBoundingClientRect(),w=document.documentElement.clientWidth;
   if(b.width>w*.7)Object.assign(canvas.style,{left:'0px',top:'0px',width:w+'px',height:Math.max(100,b.top-3)+'px'});
   else Object.assign(canvas.style,{left:(b.right+8)+'px',top:'0px',width:Math.max(120,w-b.right-8)+'px',height:innerHeight+'px'});
   plan.resize();
 }
 const observer=new ResizeObserver(()=>requestAnimationFrame(fit));observer.observe(panel.el);addEventListener('resize',fit);
 function view(planView){bird=planView;canvas.hidden=!active||!bird||inVR();if(document.pointerLockElement)document.exitPointerLock();sync();requestAnimationFrame(fit);}
 async function enter(){
   if(!entry||openLayoutEditor('edit',site,entry.def.id))return;active=true;document.body.classList.add('furniture-editing');prepare(true);view(true);
   if(!ctx)await useVersion(entry,{force:true});if(!ctx){sync();return;}
   view(true);
 }
 function collapse(on){
   collapsed=on;panel.el.classList.toggle('gd-collapsed',on);document.body.classList.toggle('furniture-walking',on);
   if(on){resumeBird=bird;cancel();view(false);document.activeElement?.blur?.();walkPreview(true);}
   else{walkPreview(false);view(resumeBird);}
 }
 function leave(){if(collapsed)collapse(false);active=false;pending='';drag=draft=verdict=null;canvas.hidden=true;line.visible=false;document.body.classList.remove('furniture-editing','furniture-immersive');prepare(false);sync();}
 function stockItem(id){
   const c=kit.find(k=>k.id===id),room=getRoom();if(!c||!room)return null;
   const type=({wall:'wall',ceiling:'ceiling',surface:'surface',terrain:'ground'})[c.host]||'floor';
   return {id:'item-'+crypto.randomUUID(),kind:c.kind,style:c.style,catalogueId:c.id,variant:c.id,
     label:c.name,size:[...c.size_m],room:room.id,rotation:0,position:[0,room.floorY,0],host:{type,id:type==='floor'||type==='ceiling'?type+'/'+room.id:''}};
 }
 function ownerAt(f,p){
   const all=(layout?.items||[]).filter(o=>o.id!==f.id && o.room===f.room&&containsXZ([p.x,p.z],itemCorners(o)));
   const fixed=(ctx?.hosts||[]).filter(h=>h.type==='surface'&&h.room===f.room&&h.bounds&&p.x>=h.bounds[0][0]&&p.x<=h.bounds[1][0]&&p.z>=h.bounds[0][2]&&p.z<=h.bounds[1][2]);
   return [...all.map(o=>({id:o.id,y:o.position[1]+o.size[2]})),...fixed.map(h=>({id:h.id,y:h.bounds[1][1]}))].sort((a,b)=>Math.abs(a.y-p.y)-Math.abs(b.y-p.y))[0];
 }
 function previewAt(h,free=false){
   if(!h||!ctx||!layout)return;
   let f=drag?.original?structuredClone(drag.original):draft?structuredClone(draft):pending?stockItem(pending):null;
   const room=getRoom();if(!f||!room)return;
   const p=h.point,off=drag?.offset||[0,0],heightOffset=drag?.heightOffset||0;f.position=[p.x+off[0],f.position[1],p.z+off[1]];f.room=room.id;
   if(f.host.type==='wall'){
      const wall=nearest([p.x,p.z],room.wallFaces||[]);f.host.id=wall?.id||'';
      if(!bird)f.position[1]=p.y+heightOffset;else if(pending)f.position[1]=room.floorY+Math.max(.15,(room.ceilingY-room.floorY-f.size[2])/2);
   }else if(f.host.type==='surface'&&!drag?.original){const owner=ownerAt(f,p);f.host.id=owner?.id||'';if(owner)f.position[1]=owner.y;}
   f=snapPlacement(ctx,layout.items,f,{free});draft=f;verdict=assessDesign(ctx,layout.items,f);sync();
 }
 function pick(h){return h?.item|| (bird&&h?plan.pick([h.point.x,h.point.z]):null);}
 function select(id){pending='';draft=drag=verdict=null;selectedId=id||'';if(selectedId){const f=layout?.get(id);if(f)roomId=f.room;}sync();}
 function start(h,free=false){
   if(!layout||!ctx||!h)return;
   if(pending){previewAt(h,free);drag={new:true,offset:[0,0]};return;}
   const wallAtPointer=bird&&plan.wallAt([h.point.x,h.point.z]);
   if(wallAtPointer){face=wallAtPointer;select(null);return;}
   const item=pick(h);if(!item){
     const faceId=h.part?.ud?.surface_id;
     if(faceId&&getRoom()?.wallFaces.some(f=>f.id===faceId))face=faceId;
     select(null);return;
   }
   select(item.id);drag={original:item,offset:[item.position[0]-h.point.x,item.position[2]-h.point.z],heightOffset:item.position[1]-h.point.y,initial:[h.point.x,h.point.y,h.point.z]};status='';sync();
 }
 function move(h,free=false){
   if(!h)return;if(!drag&&!pending)return;
   if(drag?.initial&&!draft && Math.hypot(h.point.x-drag.initial[0],h.point.y-drag.initial[1],h.point.z-drag.initial[2])<.016)return;
   previewAt(h,free);
 }
 function drop(){
   if(!drag)return;
   if(draft&&verdict?.ok){selectedId=draft.id;layout.put(draft,drag.new?'Add furniture':'Move furniture');pending='';status='';}
   else if(draft){status='Blocked · '+(verdict?.reasons||[]).join(' · ');}
   draft=drag=verdict=null;sync();
 }
 function cancel(){pending='';drag=draft=verdict=null;status='';sync();}
 function turn(n,absolute=false){
   const f=draft||layout?.get(selectedId);if(!f||!ctx)return;const candidate=structuredClone(f);
   candidate.rotation=((absolute?n:candidate.rotation+n)%360+360)%360;
   const v=assessDesign(ctx,layout.items,candidate);
   if(drag||pending){draft=candidate;verdict=v;if(drag?.original)drag.original={...drag.original,rotation:candidate.rotation};}
   else if(v.ok){layout.put(candidate,'Rotate furniture');status='';}else status='Blocked · '+v.reasons.join(' · ');
   sync();
 }
 async function action(name,value){
   try{
    if(name==='plan-view'||name==='detail-view'){detail=name==='detail-view';view(true);return;}
    if(name==='close'){leave();return;}if(name==='bird'||name==='stand'){view(name==='bird');if(name==='stand'&&!inVR()&&getRoom())goRoom(getRoom());return;}
    if(name==='minimise'){collapse(!collapsed);return;}if(name==='resize'){fit();return;}if(name==='vr'){document.querySelector('#vr').click();return;}if(name==='plants'||name==='garden'){leave();openGarden(name==='plants');return;}
    if(!layout||!ctx){status='This version has no editable room schedule.';sync();return;}
    if(Object.hasOwn(filters,name)){filters[name]=value;sync();return;}
    status='';
    if(name==='room'){if(!ctx.rooms.some(r=>r.id===value))return;cancel();roomId=value;selectedId=face='';if(!bird)goRoom(getRoom());}
    else if(name==='add'){cancel();selectedId='';pending=value;status='Point where the new piece should go.';}
    else if(name==='selected'||name==='select'){select(value);if(name==='selected')document.activeElement?.blur?.();}
    else if(name==='rotate-left'||name==='rotate-right'||name==='angle'){turn(name==='angle'?value:name==='rotate-left'?-15:15,name==='angle');return;}
    else if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','PageUp','PageDown'].includes(name)&&selectedId){
      const row=fineMove(layout.get(selectedId),name,value===true),check=assessDesign(ctx,layout.items,row);
      if(check.ok)layout.put(row,'Fine adjustment');else status=check.reasons.join(' · ');
    }
    else if(name==='delete'&&selectedId){layout.remove(selectedId);select(null);}
    else if(name==='copy'&&selectedId){
     const f=layout.get(selectedId);if(!f)return;const copies=moveGroup(layout.items,f),ids=new Map(copies.map(o=>[o.id,'item-'+crypto.randomUUID()]));let match=null;
     for(const [dx,dz] of [[f.size[0]+.05,0],[-f.size[0]-.05,0],[0,f.size[1]+.05],[0,-f.size[1]-.05]]){
       const list=copies.map(o=>{const q=structuredClone(o);q.id=ids.get(o.id);q.label=(q.label||q.kind)+' copy';q.position[0]+=dx;q.position[2]+=dz;if(ids.has(q.host.id))q.host.id=ids.get(q.host.id);return q;});
       try {
         validateFurnishDelta(ctx,{items:layout.items,wallColours:layout.wallColours,roomFloors:layout.roomFloors},{items:[...layout.items,...list],wallColours:layout.wallColours,roomFloors:layout.roomFloors});
         match=list;break;
       }catch{ /* The next side of the original piece may have a legal placement. */ }
     }if(match){layout.putMany(match,'Copy furniture');selectedId=ids.get(f.id);}else status='No clear place beside this piece for a copy.';
    }else if(name==='undo'||name==='redo'){cancel();layout[name]();}
    else if(name==='face')face=value;
    else if(name==='colour'||name==='reset-wall'){if(face)layout.setWall(face,name==='reset-wall'?null:value);else status='Choose one wall face first.';}
    else if(name==='floor')layout.setFloor(getRoom().id,value||null);
    else if(name==='save'){await layout.save();status='Saved · revision '+layout.revision;retry=false;}
    else if(name==='reload'){if(!inVR()&&layout.dirty&&!confirm('Replace this local draft with the last saved layout?'))return;await layout.load({discardDraft:true});retry=false;status='Loaded revision '+layout.revision;}
   }catch(e){status=e.message;if(e.status===409)retry=true;}sync();
 }
 function surface(ray){
   if(bird&&inVR())return wrist.hitPlan(ray);
   const room=getRoom();if(!room)return null;
   if(drag?.initial && drag.original.host.type!=='wall'){
     const origin=new T.Vector3(...drag.initial);
     // A vertical screen-facing plane stays well-conditioned even when looking level at a table.
     const normal=drag.normal||(drag.normal=Math.abs(ray.direction.y)>.28?new T.Vector3(0,1,0):camera.getWorldDirection(new T.Vector3()));
     if(Math.abs(ray.direction.dot(normal))<.12)return null;
     const point=ray.intersectPlane(new T.Plane().setFromNormalAndCoplanarPoint(normal,origin),new T.Vector3());
     if(!point)return null;
     point.y=origin.y;return {point,normal};
   }
   const item=models?.pick(ray),wall=houseHit(ray);
   if(!drag&&!pending && item&&(!wall||item.distance<wall.distance+.025))return item;
   const f=drag?.original||draft||(pending?kit.find(c=>c.id===pending):null),type=f?.host?.type||f?.host;
   if(type==='wall'&&wall)return wall;
   if(!drag?.original&&type==='surface'&&item&&item.id!==selectedId)return item;
   const ceiling=type==='ceiling',y=drag?.initial?.[1]??(ceiling?room.ceilingY:room.floorY);
   const plane=new T.Plane(new T.Vector3(0,1,0),-y),p=ray.intersectPlane(plane,new T.Vector3());
   if(!p)return drag?.original?null:wall||null;const d=ray.origin.distanceTo(p);
   if(!drag&&!pending && wall&&wall.distance<d-.05)return wall;
   return {point:p,normal:new T.Vector3(0,ceiling?-1:1,0),distance:d,surface:ceiling?'ceiling':'floor'};
 }
 function pointerHit(e,el){
   if(el===canvas){const p=plan.point(e.clientX,e.clientY);return p?{point:new T.Vector3(p[0],getRoom()?.floorY||0,p[1]),normal:new T.Vector3(0,1,0)}:null;}
   const b=el.getBoundingClientRect();ndc.set((e.clientX-b.left)*2/b.width-1,1-(e.clientY-b.top)*2/b.height);camera.updateMatrixWorld();raycaster.setFromCamera(ndc,camera);return surface(raycaster.ray);
 }
 const touches=new Map();let primary=null,twist=null;
 function attach(el){
   const blocked=()=>!active||collapsed||inVR()||(bird&&el!==canvas);
   function consume(e){e.preventDefault();e.stopImmediatePropagation();}
   el.addEventListener('pointerdown',e=>{
     if(blocked()||e.button!==0)return;consume(e);el.setPointerCapture(e.pointerId);
     touches.set(e.pointerId,[e.clientX,e.clientY]);if(touches.size===2){const [a,b]=[...touches.values()],f=draft||layout?.get(selectedId);if(f){twist={base:f.rotation,a:Math.atan2(b[1]-a[1],b[0]-a[0])};if(!drag)drag={original:f,offset:[0,0]};draft={...f};}return;}
     primary=e.pointerId;start(pointerHit(e,el),e.altKey||e.shiftKey);
   },true);
   el.addEventListener('pointermove',e=>{
     if(blocked())return;if(!touches.has(e.pointerId)&&!pending)return;consume(e);
     if(touches.has(e.pointerId))touches.set(e.pointerId,[e.clientX,e.clientY]);
     if(twist&&touches.size===2){const [a,b]=[...touches.values()];turn(twist.base-(Math.atan2(b[1]-a[1],b[0]-a[0])-twist.a)/degrees,true);return;}
     move(pointerHit(e,el),e.altKey||e.shiftKey);
   },true);
   function up(e,abort){if(!touches.has(e.pointerId))return;consume(e);touches.delete(e.pointerId);
     if(abort)cancel();else if(twist){if(touches.size===0){drop();twist=null;}}else if(primary===e.pointerId){drop();}
     if(!touches.size)primary=null;if(el.hasPointerCapture(e.pointerId))el.releasePointerCapture(e.pointerId);
   }
   el.addEventListener('pointerup',e=>up(e,false),true);el.addEventListener('pointercancel',e=>up(e,true),true);
   el.addEventListener('click',e=>{if(active&&!collapsed)consume(e);},true);
 }
 attach(canvas);attach(renderer.domElement);
 addEventListener('keydown',e=>{if(!active||inVR()||document.querySelector('dialog[open]')||e.target.closest?.('input,textarea,select'))return;
  if(collapsed){if(e.key==='Tab'){e.preventDefault();e.stopImmediatePropagation();collapse(false);}else if(e.key==='Escape'&&document.pointerLockElement)document.exitPointerLock();return;}
  if(selectedId&&!drag&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','PageUp','PageDown'].includes(e.key)){
    e.preventDefault();e.stopImmediatePropagation();action(e.key,e.shiftKey);return;
  }
  const k=e.key.toLowerCase(),mod=e.metaKey||e.ctrlKey,cmd=mod&&k==='z'?(e.shiftKey?'redo':'undo'):mod&&k==='s'?'save':k==='q'?'rotate-left':k==='e'?'rotate-right':k==='delete'||k==='backspace'?'delete':k==='escape'?'cancel':'';
  if(cmd){e.preventDefault();e.stopImmediatePropagation();if(cmd==='cancel')cancel();else action(cmd);}
 },true);
 addEventListener('focus',()=>{if(layout&&!layout.dirty)layout.refresh?.().catch(()=>{});});
 let stickLatch=false;
 function stick(x){if(!active||(!selectedId&&!pending)||Math.abs(x)<.36){stickLatch=false;return false;}if(!stickLatch&&Math.abs(x)>.6){stickLatch=true;turn(Math.sign(x)*15);}return true;}
 const consumer={project:surface,hover:h=>{if(pending)move(h);},begin:h=>start(h),move:h=>move(h),end:()=>drop(),cancel};
 function frame(left){updateDetail(performance.now());const vr=inVR();if(!active){wrist.update(left,false);return;}
  document.body.classList.toggle('furniture-immersive',vr);if(vr!==vrWas){vrWas=vr;view(bird);}wrist.update(left,vr);
 }
 return {enter,leave,action,state,useVersion,frame,invalidateView,consumer,wrist,stick,plan,releaseView(v){if(v===entry){models?.dispose();models=null;finish?.clear();finish=null;}},get enabled(){return active;},get bird(){return active&&bird;},get dragging(){return !!draft;},get runtime(){return models;},get layout(){return layout;},get context(){return ctx;},get readyModels(){return modelReady;},
  setStage(n){if(n!==stage){stage=n;if(layout)sync();}},setFurnished(on){if(furnished!==on){furnished=on;if(layout)sync();}},gardenLite(on){if(on!==indoorLite){indoorLite=on;if(layout)sync();}}};
}

