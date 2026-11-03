import * as T from 'three';
import {openLayoutEditor,layoutFetcher} from '../studio-layout-service.js';
import {GardenStore} from './store.mjs';
import {createGardenPanel} from './panel.js?v=walk1';
import {createGardenScene} from './scene.js';
import {createGardenTerrain} from './terrain.js';
import {createGardenPlan} from './plan.js';
import {createGardenWrist} from './wrist.js';
import {createDrawing,angleOf} from './drawing.mjs';
import {createFeature} from './catalogue.mjs';
import {fitStroke,handlesOf,outlineMeasurements} from './geometry.mjs';

export function createGardenEditor({scene,camera,renderer,site,marks,inVR,prepare,look,walkPreview,indoor,occlusion,normalPass}) {
  const canvas=document.createElement('canvas');canvas.id='garden-plan';canvas.hidden=true;canvas.setAttribute('aria-label','Measured garden drawing plan');document.body.append(canvas);
  const terrain=createGardenTerrain(T,normalPass), garden=createGardenScene(T,scene), plan=createGardenPlan(T,{renderer,scene,canvas,terrain});
  const stores=new Map();let active=false,bird=false,collapsed=false,resumeBird=false,version='',store=null,loaded=false,oldPen=false,vrWas=false;
  const overlay=new T.Group();overlay.name='Garden edit handles';overlay.userData.gardenOverlay=true;scene.add(overlay);
  const handleGeo=new T.SphereGeometry(1,8,6),handleMat=new T.MeshBasicMaterial({color:0xffdc91,depthTest:false,toneMapped:false});
  const strokeMat=new T.LineBasicMaterial({color:0xffdd87,depthTest:false,toneMapped:false});
  let strokes=null,status='',screenTick=0,cacheObjects=[],lastControlsState=null,refreshQueued=false;
  const draw=createDrawing({store:()=>store,pick:(x,z,t)=>garden.pick(x,z,t),ground:terrain.ground,changed:sync});
  function state(){
    const selected=store?.get(draw.state.selectedId)||null;
    return {...draw.state,draft:draw.draft,drawingId:draw.drawingId,drawingReadout:draw.readout(),active,bird,collapsed,site,version,selected,angle:selected?angleOf(selected.geometry):0,objects:cacheObjects,dirty:store?.dirty,saving:store?.saving,undo:store?.canUndo,redo:store?.canRedo,status:draw.state.status||status,conflict:draw.state.conflict};
  }
  const panel=createGardenPanel({action}),wrist=createGardenWrist({THREE:T,scene,camera,action,state,planImage:()=>plan.image,bounds:()=>plan.full});
  function sync(points){
    if(!store)return;
    strokes=points||null;cacheObjects=store.objects;
    const draft=collapsed?null:draw.draft,objects=draft?[...cacheObjects.filter(f=>f.id!==draft.id),draft]:cacheObjects;
    const id=active&&!collapsed?draw.state.selectedId:null;
    overlay.visible=active&&!collapsed;
    garden.set(objects,id);terrain.cuts(garden.cuts());
    plan.update(objects,active && draft?.kind==='outbuilding-base'?draft.id:id,strokes,active);
    for(const o of [...overlay.children]){overlay.remove(o);if(o.isLine)o.geometry.dispose();}
    const f=objects.find(f=>f.id===id);
    if(active&&f)for(const h of handlesOf(f.geometry)){const mesh=new T.Mesh(handleGeo,handleMat);mesh.scale.setScalar(.052);mesh.position.set(h.point[0],f.baseY+f.level+.085,h.point[1]);mesh.renderOrder=991;overlay.add(mesh);}
    if(active&&strokes?.length>1){const geom=new T.BufferGeometry().setFromPoints(strokes.map(([x,z])=>new T.Vector3(x,(terrain.ground(x,z)??0)+.04,z)));const line=new T.Line(geom,strokeMat);line.renderOrder=991;overlay.add(line);}
    lastControlsState=state();panel.update(lastControlsState);
  }
  async function useVersion(entry){
    if(version===entry.def.id)return;
    if(store){draw.cancel();if(store.dirty)status='The previous version still has an unsaved draft.';}
    version=entry.def.id;draw.state.selectedId=null;terrain.version(entry);plan.version(terrain.extent);
    if(!stores.has(version))stores.set(version,new GardenStore({site,version,fetcher:layoutFetcher(site,version),onChange:(s)=>{if(s===store)sync();}}));
    store=stores.get(version);const target=store;loaded=false;
    try{if(!target.dirty)await target.refresh();if(target===store){loaded=true;status='';}}
    catch(e){if(target===store){status='Layout service unavailable. Open this editor on port 8450. '+e.message;}}
    if(target===store)sync();
  }
  function fitPlanToDock() {
    if(canvas.hidden)return;
    const dock=document.querySelector('[data-garden-panel]').getBoundingClientRect();
    const width=document.documentElement.clientWidth,height=innerHeight;
    if(dock.width>width*.7){
      Object.assign(canvas.style,{left:'0px',top:'0px',width:width+'px',height:Math.max(120,dock.top-3)+'px'});
    }else{
      const left=Math.ceil(dock.right+8);Object.assign(canvas.style,{left:left+'px',top:'0px',width:Math.max(120,width-left)+'px',height:height+'px'});
    }
    plan.render();
  }
  const observer=new ResizeObserver(()=>requestAnimationFrame(fitPlanToDock));observer.observe(document.querySelector('[data-garden-panel]'));
  function view(on){
    bird=on;canvas.hidden=!active||!bird||inVR();if(document.pointerLockElement)document.exitPointerLock();
    sync();if(bird)requestAnimationFrame(()=>{if(active){fitPlanToDock();plan.capture();plan.render();}});
  }
  function collapse(on){
    if(!active||on===collapsed)return;
    collapsed=on;document.body.classList.toggle('garden-walking',on);
    if(on){
      resumeBird=bird;
      for(const [id,p] of pointers){if(p.el?.hasPointerCapture?.(id))p.el.releasePointerCapture(id);}
      pointers.clear();primary=null;pan=null;
      if(draw.drawing)draw.cancel();
      view(false);
      document.activeElement?.blur?.();
      if(!inVR())walkPreview?.(true);
    }else{
      walkPreview?.(false);view(resumeBird);
    }
    sync();
  }
  function enter(){
    if(!store||openLayoutEditor('garden',site,version))return;
    active=true;document.body.classList.add('garden-editing');marks?.setActive(false);prepare(true);
    view(true);status=loaded?'Draw a shape or select one to edit.':status;sync();
  }
  function leave(){
    if(collapsed)walkPreview?.(false);collapsed=false;
    active=false;draw.cancel();document.body.classList.remove('garden-editing','garden-immersive','garden-walking');canvas.hidden=true;bird=false;indoor(false);prepare(false);sync();
  }
  async function importMark(){
    let ref=marks?.strokes.filter(s=>s.kind==='proposal'&&marks.isShown(s)).map(s=>({id:s.id,p:s.pts.map(q=>[q.x,q.y,q.z]),closed:s.closed,label:s.note||s.id}))||[];
    if(site==='house-wip'){
      try{const r=await fetch('/marks?site=front-garden-model');if(r.ok){const data=await r.json();
        for(const s of data.strokes||[])if(s.kind==='proposal'){
          const raw=s.points3d||s.points?.map(([x,z])=>[x,0,-z]);if(raw)ref.push({id:s.id,p:raw.map(([x,y,z])=>[x+4.63,y-.231,z+3.09]),closed:s.closed,label:'Surveyed garden · '+(s.note||s.id)});
        }}}
      catch{/* Local house proposals remain available independently. */}
    }
    if(!ref.length)throw Error('There are no proposal marks for this version. Draw one in Mark mode first.');
    const box=document.createElement('dialog');box.className='garden-mark-choice';const title=document.createElement('h3');title.textContent='Use a proposal mark';box.append(title);
    for(const row of ref){const b=document.createElement('button');b.textContent=row.label;b.onclick=()=>{try{const g=fitStroke(row.p.map(([x,y,z])=>[x,z]),{closed:row.closed});const f=createFeature(row.closed?'patio':'path',g,row.p[0][1]);draw.state.selectedId=f.id;draw.state.tool='select';store.put(f,'Use proposal mark');}catch(e){status=e.message;}box.close();sync();};box.append(b);}
    const close=document.createElement('button');close.textContent='Cancel';close.onclick=()=>box.close();box.append(close);box.onclose=()=>box.remove();document.body.append(box);box.showModal();
  }
  async function copyBase(){
    const f=store.get(draw.state.selectedId);if(f?.kind!=='outbuilding-base')throw Error('Select an outbuilding base first.');
    const m=outlineMeasurements(f.geometry),top=f.baseY+f.level;
    const reference=['Garden Studio · outbuilding base',f.label+' · '+f.id,
      'Layout file: assets/sites/'+site+'/layout/'+version+'.json',store.dirty?'Unsaved draft':'Saved revision '+store.revision,
      'Footprint '+m.width.toFixed(3)+' × '+m.depth.toFixed(3)+' m; area '+m.area.toFixed(3)+' m²; perimeter '+m.perimeter.toFixed(3)+' m.',
      ...m.segments.map(s=>s.label+' '+s.length.toFixed(3)+' m'),
      'Concrete slab: top Y '+top.toFixed(3)+' m, underside '+(top-f.height).toFixed(3)+' m, thickness '+f.height.toFixed(3)+' m.',
      'Measured footprint in house X/Z metres: '+JSON.stringify(f.geometry)].join('\n');
    if(navigator.clipboard?.writeText){try{await navigator.clipboard.writeText(reference);status='Base reference copied.';return;}catch{}}
    const box=document.createElement('dialog'),t=document.createElement('textarea'),b=document.createElement('button');
    box.className='garden-mark-choice';t.setAttribute('aria-label','Base reference');t.value=reference;t.readOnly=true;t.rows=12;t.cols=45;
    b.textContent='Close';b.onclick=()=>box.close();box.onclose=()=>box.remove();box.append(t,b);document.body.append(box);box.showModal();t.focus();t.select();
  }
  async function action(name,value){
    try{
      if(name==='vr'){document.getElementById('vr').click();return;}
      if(name==='collapse'){collapse(!collapsed);return;}
      if(name==='view'){view(!bird);return;} if(name==='close'){leave();return;}
      if(name==='save'){await store.save();status='Saved · revision '+store.revision;draw.state.conflict=false;}
      else if(name==='reload'){
        if(store.dirty && !window.confirm('Discard this unsaved garden draft and load the saved design?'))return;
        await store.load({discard:true});loaded=true;status='Loaded revision '+store.revision;draw.state.conflict=false;
      }else if(name==='base-reference')await copyBase();
      else if(name==='import')await importMark();
      else{draw.command(name,value);return;}
      draw.state.status='';
    }catch(e){status=e.message;draw.state.status='';if(e.status===409){draw.state.conflict=true;status='Another device saved a newer revision. Your draft is still here. Reload to use the saved version.';}}
    sync();
  }
  function surface(ray){
    if(bird&&inVR()){const h=wrist.hitPlan(ray);if(h){h.point.y=terrain.ground(h.point.x,h.point.z)??0;}return h;}
    const existing=terrain.hit(ray),added=garden.surfaceHit?.(ray,120);
    const uncovered=existing&&!garden.masksGround?.(existing.point.x,existing.point.z)?existing:null;
    const h=added && (!uncovered||added.distance<uncovered.distance)?added:uncovered;if(!h)return null;
    const obstacle=occlusion(ray);
    if(obstacle&&obstacle.distance+.08<h.distance && obstacle.part!=null && !occlusion.isOutdoor?.(obstacle.part))return null;
    return h;
  }
  const pointerRay=new T.Raycaster(),ndc=new T.Vector2();
  function at(e,el){
    if(el===canvas){const [x,z]=plan.at(e.clientX,e.clientY),y=terrain.ground(x,z);return y==null?null:new T.Vector3(x,y,z);}
    const r=el.getBoundingClientRect();ndc.set((e.clientX-r.left)*2/r.width-1,1-(e.clientY-r.top)*2/r.height);camera.updateMatrixWorld();pointerRay.setFromCamera(ndc,camera);return surface(pointerRay.ray)?.point||null;
  }
  const pointers=new Map();let pan=null,primary=null;
  const pair=()=>{const a=[...pointers.values()];if(!a.length)return null;const b=a[1]||a[0];return {x:(a[0].x+b.x)/2,y:(a[0].y+b.y)/2,d:Math.hypot(a[0].x-b.x,a[0].y-b.y)};};
  function pointer(el){
    const consume=e=>{e.stopImmediatePropagation();e.preventDefault();};
    el.addEventListener('pointerdown',e=>{
      if(!active||collapsed||inVR()||el===renderer.domElement&&bird)return;
      consume(e);
      if(e.pointerType==='touch' && primary!=null && pointers.get(primary)?.type==='pen')return;
      if(e.pointerType==='pen' && pointers.size){pointers.clear();pan=null;draw.cancel();}
      el.setPointerCapture?.(e.pointerId);
      if(e.pointerType==='pen')oldPen=true;
      pointers.set(e.pointerId,{x:e.clientX,y:e.clientY,type:e.pointerType,el});
      if(el===canvas&&(pointers.size>1||e.button!==0||(oldPen&&e.pointerType==='touch'))){
        draw.cancel();primary=null;pan=pair();return;
      }
      if(el!==canvas&&e.button!==0){pan=pair();return;}
      const p=at(e,el);if(!p)return;primary=e.pointerId;
      draw.begin(p,{screenY:e.clientY,free:e.altKey||e.shiftKey,tolerance:el===canvas?Math.max(.08,plan.metres(e.pointerType==='mouse'?8:13)):.22});
    },true);
    el.addEventListener('pointermove',e=>{
      if(!active||collapsed||inVR())return;
      if(!pointers.has(e.pointerId)){if(draw.corners.length)draw.hover(at(e,el));return;}consume(e);
      pointers.set(e.pointerId,{x:e.clientX,y:e.clientY,type:e.pointerType,el});
      if(pan){const next=pair();if(el===canvas){const a=plan.at(pan.x,pan.y),b=plan.at(next.x,next.y);plan.pan(a[0]-b[0],a[1]-b[1]);if(pan.d&&next.d)plan.zoom(pan.d/next.d,plan.at(next.x,next.y));}else look(next.x-pan.x,next.y-pan.y);
        pan=next;return;}
      if(primary!==e.pointerId)return;
      const samples=e.pointerType==='pen'&&e.getCoalescedEvents?e.getCoalescedEvents():[];
      for(const v of samples.length?samples:[e]){const p=at(v,el);if(p)draw.move(p,{screenY:v.clientY});}
    },true);
    function up(e,cancelled){
      if(!pointers.has(e.pointerId))return;consume(e);
      if(primary===e.pointerId){if(cancelled)draw.cancel();else{const p=at(e,el);if(p)draw.move(p,{screenY:e.clientY});draw.end();}primary=null;}
      pointers.delete(e.pointerId);if(pan)pan=pointers.size?pair():null;
      if(el.hasPointerCapture?.(e.pointerId))el.releasePointerCapture(e.pointerId);
    }
    el.addEventListener('pointerup',e=>up(e,false),true);el.addEventListener('pointercancel',e=>up(e,true),true);
    el.addEventListener('click',e=>{if(active&&!collapsed)consume(e);},true);
    el.addEventListener('contextmenu',e=>{if(active&&!collapsed)consume(e);});
  }
  pointer(canvas);pointer(renderer.domElement);
  canvas.addEventListener('wheel',e=>{if(!active)return;e.preventDefault();plan.zoom(Math.exp(Math.max(-1,Math.min(1,e.deltaY*.0018))),plan.at(e.clientX,e.clientY));},{passive:false});
  addEventListener('keydown',e=>{
    if(!active||inVR()||document.querySelector('dialog[open]')||e.target.closest?.('input,textarea,select,[contenteditable]'))return;
    const k=e.key.toLowerCase(),mod=e.metaKey||e.ctrlKey;
    if(collapsed){
      if(k==='escape' && document.pointerLockElement){e.preventDefault();document.exitPointerLock();}
      if(k==='tab'&&!mod&&!e.shiftKey){e.preventDefault();e.stopImmediatePropagation();collapse(false);}
      return;
    }
    const cmd=mod&&k==='z'?(e.shiftKey?'redo':'undo'):mod&&k==='s'?'save':mod&&k==='d'?'copy':k==='delete'||k==='backspace'?'delete':k==='escape'?'cancel':k==='enter'?'finish':null;
    if(cmd){e.preventDefault();e.stopImmediatePropagation();action(cmd);}
  },true);
  addEventListener('resize',fitPlanToDock);
  addEventListener('focus',()=>{if(store&&!store.dirty)store.refresh().catch(()=>{});});
  addEventListener('beforeunload',e=>{if([...stores.values()].some(s=>s.dirty)){e.preventDefault();e.returnValue='';}});
  document.querySelectorAll('[data-garden-open]').forEach(b=>b.addEventListener('click',enter));
  const consumer={project:surface,hover(h){draw.hover(h?.point);},begin(h){draw.begin(h.point,{tolerance:bird ? .30 : .21});},move(h){draw.move(h.point,{deltaY:h.verticalDelta});},end(){draw.end();},cancel(){draw.cancel();}};
  function frame(left,now){
    const vr=inVR();document.body.classList.toggle('garden-immersive',active&&vr);if(vr!==vrWas){vrWas=vr;if(vr&&collapsed)collapse(false);canvas.hidden=!active||!bird||vr;indoor(active&&vr);}
    if(!active){wrist.update(left,false,vr);return;}
    if(!plan.ready&&bird)plan.capture();
    if(vr)indoor(true);
    wrist.update(left,true,vr);
    if(vr&&!draw.drawing&&++screenTick%240===0&&!store?.dirty){if(!refreshQueued){refreshQueued=true;store.refresh().catch(()=>{}).finally(()=>refreshQueued=false);}}
  }
  let stickLatch=false;
  function stickLevel(v){
    if(!active||!draw.state.selectedId)return false;
    if(Math.abs(v)<.35){stickLatch=false;return false;}
    if(Math.abs(v)>.6&&!stickLatch){stickLatch=true;const f=store.get(draw.state.selectedId);if(f)action('field',{key:'level',value:Math.round((f.level-Math.sign(v)*.05)*100)/100});}
    return Math.abs(v)>.35;
  }
  return {enter,leave,action,state,useVersion,frame,wrist,consumer,stickLevel,plan,garden,terrain,draw,get enabled(){return active;},get bird(){return active&&bird;},get store(){return store;},get objects(){return cacheObjects;}};
}

