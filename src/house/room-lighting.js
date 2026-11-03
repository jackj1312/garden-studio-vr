import * as T from 'three';
import {progress} from './model.js';
import {bulbMaterial,exteriorAperture,incidentRooms,isLampKind,lampPower,openingPlane,openRoomGroups,
  rankApertures,roomPoint,squared} from './room-light-data.mjs';

const DIST_SQ=.09, FALLBACK_RADIUS=.023;
const keyOf=part=>part?.ud?.spec_id||part?.userData?.spec_id;
const fixedKind=p=>p?.ud?.kit_kind;
const centreOf=box=>box.getCenter(new T.Vector3()).toArray();
const present=(model,p)=>!!model.masks.visible[p.index];
const isGlass=p=>p.ud?.part==='glass'||p.ud?.part==='leaf_glass';
const tags=(node,type,id,room)=>{node.userData.studioLight={type,id,room};node.name='Studio '+type+' · '+id;};
function selectSchedule(V,spec){
  return Object.values(spec?.versions||{}).find(v=>v.elements===V?.def?.id) || (spec?.items?spec:null);
}
function lightColour(kelvin){
  // The schedule uses domestic warm white; interpolate within its 2700–4000 K range.
  const amount=Math.max(0,Math.min(1,(kelvin-2700)/1300));
  return new T.Color(0xffcea1).lerp(new T.Color(0xffecd8),amount);
}
function readings(table,schedule){
  const defined=new Map((schedule?.rooms||[]).map(r=>[r.id,r]));
  return [...table.values()].filter(e=>e.type==='room'&&e.params?.polygon?.length>=3).map(e=>{
    const s=defined.get(e.id),floor=e.params.floor??s?.floor_y??0, ceiling=typeof s?.ceiling_y==='number'?s.ceiling_y:floor+2.65;
    return {id:e.id,polygon:e.params.polygon,floor,ceiling:ceiling-floor>1.5?ceiling:floor+ceiling,storey:e.params.storey};
  });
}
function areaBox(parts){
  const box=new T.Box3();
  for(const p of parts)if(p.bbox)box.union(p.bbox);
  return box.isEmpty()?null:box;
}
function roofAperture(p,rooms) {
  const attr=p.geometry?.getAttribute('position'),indices=p.geometry?.index;
  if(!attr)return null;
  const vertex=i=>new T.Vector3().fromBufferAttribute(attr,indices?indices.getX(i):i).applyMatrix4(p.matrix0);
  const tris=[],length=indices?.count??attr.count;
  for(let i=0;i+2<length;i+=3){
    const a=vertex(i),b=vertex(i+1),c=vertex(i+2),n=b.clone().sub(a).cross(c.clone().sub(a)),area=n.length()/2;
    if(area<.000001)continue;n.normalize();
    if(Math.abs(n.y)<.2)continue;tris.push({n,area,mid:a.add(b).add(c).multiplyScalar(1/3)});
  }
  const top=tris.sort((a,b)=>b.area-a.area)[0];if(!top)return null;
  const normal=top.n.clone();if(normal.y>0)normal.negate();
  const side=tris.filter(t=>t.n.dot(normal)>.995),area=side.reduce((v,t)=>v+t.area,0);
  if(area<=.01)return null;
  const centre=side.reduce((v,t)=>v.addScaledVector(t.mid,t.area/area),new T.Vector3());
  const pos=centre.clone().addScaledVector(normal,.20),owner=roomPoint(rooms,pos.toArray());
  if(!owner)return null; // A rooflight over an unscheduled loft has no lower-storey owner.
  return {id:p.element,fixture:p.element,room:owner.id,centre:centre.toArray(),position:pos.toArray(),inward:normal.toArray(),area,parts:[p]};
}
function readSources(V,spec) {
  const model=V.model,table=model.table,schedule=selectSchedule(V,spec),rooms=readings(table,schedule),apertures=[],walls=[],doorwayLinks=[];
  const specs=new Map((schedule?.items||[]).map(it=>[it.id,it]));
  const all=[...table.values()],fixtures=new Map();
  for(const e of all)if(e.type==='fixture'&&e.params?.opening){
    const id=e.params.opening;if(!fixtures.has(id))fixtures.set(id,[]);fixtures.get(id).push(e);
  }
  for(const op of all) {
    if(op.type!=='opening')continue;
    const w=table.get(op.params.host),plane=openingPlane(w,op);if(!plane)continue;
    walls.push({plane,width:op.params.width,op});
    const owners=fixtures.get(op.id)||[];
    if(!owners.length && ['door','opening'].includes(op.meta?.group)) {
      const [a,b]=incidentRooms(rooms,plane);
      if(a&&b&&a!==b&&Math.abs(a.floor-b.floor)<.03&&op.params.sill<=a.floor+.08&&op.params.head>=a.floor+1.8)
        doorwayLinks.push({a:a.id,b:b.id,op});
    }
    for(const fixture of owners) {
      const parts=(model.byElement.get(fixture.id)||[]).filter(isGlass);
      if(!parts.length)continue;
      const a=exteriorAperture(rooms,plane,op.id,fixture.id);
      if(a)apertures.push({...a,parts});
    }
  }
  const lampParts=new Map();
  for(const p of model.parts) {
    if(p.group==='rooflight'&&/glass|glaz/i.test(p.materialName||p.name)) {
      const a=roofAperture(p,rooms);if(a)apertures.push(a);
    }
    const id=keyOf(p);
    const taskLamp=fixedKind(p)==='extractor'&&bulbMaterial(p.materialName);
    if(!id||!(isLampKind(fixedKind(p))||specs.get(id)?.category==='lighting'||taskLamp))continue;
    if(!lampParts.has(id))lampParts.set(id,[]);lampParts.get(id).push(p);
  }
  const fixed=[];
  for(const [id,parts] of lampParts) {
    const spec=specs.get(id),kind=parts.find(p=>isLampKind(fixedKind(p)))?.ud.kit_kind||
      (parts.some(p=>fixedKind(p)==='extractor')?'extractor_light':'pendant');
    const room=parts.find(p=>p.ud.room_id)?.ud.room_id||spec?.room;
    const bulbs=parts.filter(p=>bulbMaterial(p.materialName)),box=areaBox(bulbs)||areaBox(parts);if(!box||!room)continue;
    const mid=centreOf(box), positions=spec?.asset?.positions_xz;
    const points=positions?.length?positions.map(([x,z])=>[x,mid[1],z]):[mid];
    fixed.push({id,kind,room,parts,bulbs,points,bottom:box.min.y,power:lampPower(kind,spec?.asset)});
  }
  return {rooms,apertures,doorwayLinks,walls,fixed,specs};
}

function activeGroups(source,V,stage){
  const links=source.doorwayLinks.filter(({op})=>stage>=(op.meta?.stage_in||1)&&(!op.meta?.stage_out||stage<op.meta.stage_out))
    .map(l=>[l.a,l.b]);
  // Culling discovers genuine knock-throughs by testing the built walls.
  // Its broad portals include doors, windows and stair holes as well; never
  // treat those as an open interior daylight connection.
  if(stage>=V.sidecar?.stages?.length && V.cull?.holes?.done)for(const p of V.cull.portalList()) {
    const a=source.rooms[p.a],b=source.rooms[p.b];
    if(!a||!b||Math.abs(a.floor-b.floor)>.03)continue;
    const corners=p.corners;if(!corners?.length)continue;
    const ys=corners.map(q=>q[1]);
    if(Math.min(...ys)>a.floor+.40||Math.max(...ys)<a.floor+1.70)continue;
    const named=source.walls.some(({op,plane,width})=>{
      if(op.params.head<=a.floor+.2||op.params.sill>a.ceiling) return false;
      const dx=p.ctr[0]-plane.centre[0],dz=p.ctr[2]-plane.centre[2],n=plane.normal;
      return Math.abs(dx*n[0]+dz*n[2])<.38&&Math.abs(dx*n[2]-dz*n[0])<width/2+.12;
    });
    if(!named)links.push([a.id,b.id]);
  }
  return openRoomGroups(source.rooms,links);
}

function runtimeSource(item,spec) {
  const pos=[...item.position], ceiling=['pendant','linear_pendant','flush_light','downlight'].includes(item.kind);
  pos[1]+=item.size[2]*(ceiling?.12:.82);
  return {id:item.id,room:item.room,kind:item.kind,item,parts:[],bulbs:[],points:[pos],bottom:pos[1]-.015,
    power:lampPower(item.kind,spec?.asset)};
}
function geometryMatrix(p) {
  if(p.batch&&p.instanceId>=0) {
    const m=new T.Matrix4();p.batch.getMatrixAt(p.instanceId,m);return m.premultiply(p.batch.matrixWorld);
  }
  return p.mesh?.matrixWorld||p.matrix0;
}

export function createRoomLighting({scene,desktop=true}) {
  const root=new T.Group();root.name='Studio room light';scene.add(root);
  const windows=[],lampSlots=[],emitterMeshes=new Map(),emitterMaterials=new Map();
  const fallbackGeometry=new T.SphereGeometry(FALLBACK_RADIUS,10,8),matrix=new T.Matrix4();
  const originalEmission=new Map();
  let houseOn=false,emitterKey='',emitterItems=null,emitterRuntime=null,practicalSources=[];
  function bulbGlow(m,on,kelvin=2700){
    if(!m?.emissive||!bulbMaterial(m.name))return false;
    if(!originalEmission.has(m))originalEmission.set(m,[m.emissive.clone(),m.emissiveIntensity]);
    if(on)m.emissive.copy(lightColour(kelvin));
    m.emissiveIntensity=on?1:0;return true;
  }
  function restoreEmission(){
    for(const [m,[colour,power]] of originalEmission){m.emissive.copy(colour);m.emissiveIntensity=power;}
    originalEmission.clear();
  }
  let view=null,source=null,groups=null,groupsKey='',last=null,dirty=true,previousMotion=false,pendingShadow=false;
  let currentRoom=null,profile='on',lite=!desktop,selectedWindows=[],activePracticals=[],activeEmitters=[];
  let records=new Map(),priorItems=null,loose=[],lastEye=null,lastContext='',previousRuntime=null;
  function shadow(light,normalBias) {
    light.castShadow=true;light.shadow.mapSize.set(512,512);light.shadow.camera.near=.04;
    light.shadow.bias=-.001;light.shadow.normalBias=normalBias;
    light.shadow.autoUpdate=false;light.shadow.needsUpdate=true;
  }
  function windowSlot(i) {
    if(!windows[i]){
      const l=new T.SpotLight(0xffffff,0,12,75*Math.PI/180,.8,2);shadow(l,.020);
      root.add(l,l.target);windows[i]=l;
    }
    return windows[i];
  }
  function practicalSlot(i,spot) {
    let l=lampSlots[i];
    if(!l || Boolean(l.isSpotLight)!==spot) {
      if(l){l.removeFromParent();l.target?.removeFromParent();l.dispose();}
      l=spot?new T.SpotLight(0xffffff,0,5,50*Math.PI/180,.6,2):new T.PointLight(0xffffff,0,5,2);
      root.add(l);if(l.target)root.add(l.target);lampSlots[i]=l;
    }
    return l;
  }
  function aimWindow(l,a){
    l.userData.opening=a;l.distance=a.distance;l.shadow.camera.far=a.distance;
    l.position.fromArray(a.position);l.target.position.copy(l.position).add(new T.Vector3().fromArray(a.inward));
    tags(l,'window',a.id,a.room);l.shadow.needsUpdate=true;
  }
  function fadeWindows(dt){
    let moved=false;
    for(const l of windows){
      const a=l.userData.destination,old=l.userData.opening;
      if(!l.visible||!old||!a)continue;
      if(a.id!==old.id){
        l.intensity=Math.max(0,l.intensity-Math.max(.01,old.intensity)*dt/.32);
        if(l.intensity===0){aimWindow(l,a);l.userData.rising=true;moved=true;}
      }else if(l.userData.rising){
        l.intensity=Math.min(a.intensity,l.intensity+a.intensity*dt/.4);
        if(l.intensity>=a.intensity)l.userData.rising=false;
      }
    }
    if(moved)selectedWindows=windows.filter(l=>l.visible).map(l=>l.userData.opening);
    return moved;
  }
  function removeEmitters(keep) {
    for(const [key,m] of emitterMeshes)if(!keep.has(key)){m.removeFromParent();emitterMeshes.delete(key);}
  }
  function clear() {
    for(const light of [...windows,...lampSlots]){
      light.removeFromParent();light.target?.removeFromParent();light.dispose();
    }
    windows.length=lampSlots.length=0;removeEmitters(new Set());selectedWindows=[];activePracticals=[];activeEmitters=[];
  }
  function setView(V,spec) {
    restoreEmission();clear();view=V;source=V?readSources(V,spec):null;
    for(const r of source?.fixed||[])for(const p of r.bulbs)bulbGlow(p.set?.normal||p.mesh?.material,houseOn,r.power.kelvin);
    emitterKey='';emitterItems=null;emitterRuntime=null;practicalSources=[];
    groups=null;groupsKey='';last=null;dirty=true;
    records=new Map();currentRoom=null;priorItems=null;loose=[];lastEye=null;lastContext='';previousRuntime=null;previousMotion=false;pendingShadow=false;
  }
  function refreshRecords(items,stage,furnished) {
    if(items!==priorItems) {
      loose=items.filter(i=>isLampKind(i.kind)&&Array.isArray(i.position)&&Array.isArray(i.size)).map(it=>{
        return runtimeSource(it,source.specs.get(it.id));
      });
      priorItems=items;
    }
    const active=source.fixed.filter(r=>r.parts.some(p=>present(view.model,p)));
    if(furnished)for(const r of loose){
      const i=r.item,end=i.stageOut??i.stage_out;
      if(progress(stage,i.stageIn??i.stage_in??1,i.seq??0)>.001&&(!end||progress(stage,end,i.seqOut??i.seq_out??1)<.999))active.push(r);
    }
    records=new Map(active.map(r=>[r.id,r]));
  }
  function runtimeBulbs(id,runtime){
    const out=[];
    if(!runtime?.visible)return out;
    for(const mesh of runtime.children){
      if(!mesh.visible||!mesh.isInstancedMesh||!bulbMaterial(mesh.material?.name))continue;
      const index=mesh.userData.furnishItems?.findIndex(i=>i.id===id);
      if(index==null||index<0||index>=mesh.count)continue;
      mesh.getMatrixAt(index,matrix);const transform=matrix.clone().premultiply(mesh.matrixWorld);
      out.push({geometry:mesh.geometry,matrix:transform,material:mesh.material});
    }
    return out;
  }
  function calculateEmitters(r,runtime){
    const pieces=r.item?runtimeBulbs(r.id,runtime):r.bulbs.filter(p=>present(view.model,p))
      .map(p=>({geometry:p.geometry,matrix:geometryMatrix(p),material:p.set?.normal||p.mesh?.material}));
    let points=r.points,bottom=r.bottom;
    if(r.item&&pieces.length){
      const box=new T.Box3();
      for(const piece of pieces){if(!piece.geometry.boundingBox)piece.geometry.computeBoundingBox();
        box.union(piece.geometry.boundingBox.clone().applyMatrix4(piece.matrix));}
      points=[centreOf(box)];bottom=box.min.y;
    }
    return {pieces,points,bottom};
  }
  function showEmitter(key,r,geometry,transform,keep) {
    keep.add(key);
    if(!emitterMaterials.has(r.power.kelvin))emitterMaterials.set(r.power.kelvin,new T.MeshBasicMaterial({
      color:lightColour(r.power.kelvin),toneMapped:false,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-1,polygonOffsetUnits:-1,side:T.DoubleSide}));
    let mesh=emitterMeshes.get(key);
    if(!mesh){mesh=new T.Mesh(geometry,emitterMaterials.get(r.power.kelvin));mesh.matrixAutoUpdate=false;mesh.renderOrder=3;root.add(mesh);emitterMeshes.set(key,mesh);}
    mesh.geometry=geometry;mesh.material=emitterMaterials.get(r.power.kelvin);mesh.matrix.copy(transform);mesh.matrixWorldNeedsUpdate=true;
    tags(mesh,'emitter',r.id,r.room);
  }
  function update(input) {
    if(!view||!source)return false;
    last=input;profile=input.profile==='off'?'off':'on';lite=!desktop||!!input.inXR;
    const eye=input.eye?.isVector3?input.eye.toArray():input.eye;
    if(!Array.isArray(eye)||eye.length<3)return false;
    const stage=input.stage??view.model.stage??1,items=input.items||EMPTY;
    currentRoom=(view.model.roomAt?.(...eye)?.id)||roomPoint(source.rooms,eye)?.id||null;
    const sourceKey=[stage,view.model.asBuilt,VHoles(view)].join('|');
    if(sourceKey!==groupsKey){groups=activeGroups(source,view,stage);groupsKey=sourceKey;dirty=true;}
    const runtime=scene.children.find(n=>n.userData.furnishRuntime&&n.visible);
    const runtimeKey=runtime?runtime.children.length:0,ctx=[stage,view.model.asBuilt,currentRoom,profile,lite,input.daylight??1,input.furnished!==false,runtimeKey].join('|');
    const runtimeChanged=runtime!==previousRuntime;
    previousRuntime=runtime;
    const motion=!!view.doors?.moving,doorChanged=motion||previousMotion;
    const carry=pendingShadow;pendingShadow=false;
    if(!dirty&&!runtimeChanged&&lastContext===ctx&&items===priorItems&&!motion&&!previousMotion&&lastEye&&squared(lastEye,eye)<DIST_SQ)return carry&&!lite;
    lastEye=[...eye];lastContext=ctx;previousMotion=motion;
    refreshRecords(items,stage,input.furnished!==false);
    const enabled=profile==='on',oldWindows=selectedWindows.map(a=>a.id);
    const usable=enabled&&!lite?source.apertures.filter(a=>a.parts.some(p=>present(view.model,p))):[];
    const allRooms={rooms:source.rooms.map(r=>r.id),distance:8};
    // The full site always has the physical sun. Supplement nearby openings smoothly,
    // including on their garden side, without shading distant grass with indoor spot maps.
    const nearby=usable.filter(a=>squared(a.position,eye)<64);
    const nextWindows=rankApertures(nearby,allRooms,eye,oldWindows,2).map(a=>{
      const fade=T.MathUtils.smoothstep(Math.sqrt(squared(a.position,eye)),3.5,8);
      return {...a,distance:groups.get(a.room)?.distance??8,intensity:a.intensity*(1-fade)*(input.daylight??1)};
    });
    let shadows=carry||((dirty||doorChanged)&&nextWindows.length>0);
    const assigned=new Set(),targets=new Map();
    // Keep each surviving aperture in its current GPU light slot.
    for(const [i,l] of windows.entries()){
      const keep=nextWindows.find(a=>a.id===l.userData.destination?.id);
      if(keep){targets.set(i,keep);assigned.add(keep.id);}
    }
    for(const a of nextWindows)if(!assigned.has(a.id)){
      let i=0;while(targets.has(i))i++;targets.set(i,a);
    }
    for(const [i,a] of targets){
      const l=windowSlot(i);l.color.setHex(input.daylightColour??0xffffff);l.userData.destination=a;
      if(!l.visible||!l.userData.opening||!usable.some(op=>op.id===l.userData.opening.id)){
        aimWindow(l,a);l.intensity=a.intensity;shadows=true;
      }
      l.visible=true;
      if(l.userData.opening.id===a.id){l.userData.opening=a;if(!l.userData.rising)l.intensity=a.intensity;}
      if(shadows)l.shadow.needsUpdate=true;
    }
    for(const [i,l] of windows.entries())if(!targets.has(i)){l.visible=false;l.userData.opening=l.userData.destination=null;}
    selectedWindows=windows.filter(l=>l.visible).map(l=>l.userData.opening);
    const inventory=[stage,view.model.asBuilt,enabled,houseOn,input.furnished!==false,runtimeKey].join('|');
    if(inventory!==emitterKey||items!==emitterItems||runtime!==emitterRuntime){
      emitterKey=inventory;emitterItems=items;emitterRuntime=runtime;
      const keep=new Set();activeEmitters=[];practicalSources=[];
      for(const r of records.values()){
        const {pieces,points,bottom}=calculateEmitters(r,runtime);
        const on=enabled&&houseOn;
        for(const [j,piece] of pieces.entries()){
          const lit=bulbGlow(piece.material,on,r.power.kelvin);
          if(on&&!lit)showEmitter(r.id+'/part'+j,r,piece.geometry,piece.matrix,keep);
        }
        if(!on)continue;
        for(const [i,p] of points.entries()){
          if(!pieces.length)showEmitter(r.id+'/bulb'+i,r,fallbackGeometry,new T.Matrix4().makeTranslation(...p),keep);
          activeEmitters.push({id:r.id,room:r.room,position:[...p]});
          practicalSources.push({id:r.id,key:r.id+'/'+i,room:r.room,power:r.power,position:[p[0],bottom-.035,p[2]]});
        }
      }
      removeEmitters(keep);
    }
    const near=practicalSources.map(r=>({...r,d2:squared(eye,r.position)})).sort((a,b)=>a.d2-b.d2||a.key.localeCompare(b.key));
    const next=lite?near.slice(0,1):[near.find(r=>!r.power.spot),near.find(r=>r.power.spot)].filter(Boolean);
    activePracticals=next;
    for(const [i,r] of next.entries()){
      const l=practicalSlot(i,r.power.spot);l.visible=true;l.color.copy(lightColour(r.power.kelvin));
      l.position.fromArray(r.position);l.intensity=r.power.intensity;l.distance=r.power.range;
      if(l.target)l.target.position.copy(l.position).y-=1;
      if(l.castShadow){l.shadow.camera.far=l.distance;if(shadows||dirty||motion)l.shadow.needsUpdate=true;}
      tags(l,'practical',r.id,r.room);
    }
    for(let i=next.length;i<lampSlots.length;i++)lampSlots[i].visible=false;
    dirty=false;
    return Boolean(!lite&&shadows);
  }
  function invalidate(){dirty=true;}
  function status(){return {allOn:houseOn};}
  function toggleAll(on=!houseOn){
    houseOn=Boolean(on);lastContext='';
    if(last)pendingShadow=update(last)||pendingShadow;
    return houseOn;
  }
  function snapshot(){
    return {profile,room:currentRoom,lite,budget:{windows:lite?0:3,practicals:lite?1:2},
      windows:selectedWindows.map(({id,fixture,room,centre,inward,position,area,intensity,distance})=>({id,fixture,room,centre,inward,position,area,intensity,distance})),
      lamps:[...records.values()].map(r=>({id:r.id,room:r.room,kind:r.kind,on:houseOn,visible:true,position:r.points[0],points:r.points})),
      practicals:activePracticals.map((r,i)=>({id:r.id,room:r.room,position:r.position,intensity:r.power.intensity,shadow:!!lampSlots[i]?.castShadow})),
      emitters:activeEmitters.map(e=>({...e})),version:view?.def?.id??null};
  }
  async function prepareDaylight(renderer,camera,entry,items=[],postTarget=null) {
    if(!desktop||renderer.xr.isPresenting||entry!==view||!source)return;
    if(entry.preparedDaylight)return entry.preparedDaylight;
    // Compile the real fixed and instanced materials against the same light and
    // environment defines, without temporarily lighting or reparenting the live scene.
    const apertures=source.apertures;
    const limit=Math.min(2,apertures.length);
    const objects=new T.Group();
    objects.children=[entry.model.root,...scene.children.filter(o=>o.userData.furnishRuntime)];
    const target=new T.Scene();target.environment=scene.environment;target.environmentIntensity=scene.environmentIntensity;target.fog=scene.fog;
    for(const light of scene.children.filter(o=>o.isLight&&o.visible))target.add(light.clone(false));
    entry.preparedDaylight=(async()=>{
      try {
        // Identical light counts share a program, regardless of room, colour or position.
        const lamps=[...source.fixed,...items.filter(it=>isLampKind(it.kind)).map(it=>runtimeSource(it,source.specs.get(it.id)))];
        const hasPoint=lamps.some(l=>!l.power.spot),hasSpot=lamps.some(l=>l.power.spot);
        const configs=[];
        for(let n=0;n<=limit;n++){
          if(n)configs.push([n,false]);
          if(hasPoint||hasSpot)configs.push([n,true]);
        }
        for(const [windows,on] of configs){
          if(entry!==view)break;
          const extras=[];
          for(let i=0;i<windows+(on?Number(hasSpot)+Number(hasPoint):0);i++){
            const light=i<windows||on&&hasSpot&&i===windows?new T.SpotLight():new T.PointLight();
            if(i<windows)shadow(light,.02);target.add(light);extras.push(light);
          }
          try{
            await renderer.compileAsync(objects,camera,target);
            if(postTarget){
              const previous=renderer.getRenderTarget();let compiling;
              try{renderer.setRenderTarget(postTarget);compiling=renderer.compileAsync(objects,camera,target);}
              finally{renderer.setRenderTarget(previous);}
              await compiling;
            }
          }
          finally{for(const l of extras){target.remove(l);l.dispose();}}
        }
      }finally{
        objects.children=[];for(const o of target.children)if(o.isLight)o.dispose?.();
        target.clear();
      }
    })().catch(error=>{delete entry.preparedDaylight;throw error;});
    return entry.preparedDaylight;
  }
  function dispose(){setView(null);root.removeFromParent();fallbackGeometry.dispose();for(const m of emitterMaterials.values())m.dispose();emitterMaterials.clear();}
  return {setView,update,fadeWindows,get transitioning(){return windows.some(l=>l.visible&&(l.userData.rising||l.userData.opening?.id!==l.userData.destination?.id));},invalidate,status,toggleAll,snapshot,prepareDaylight,dispose};
}
const EMPTY=Object.freeze([]);
const VHoles=v=>v.cull?.holes?.done?1:0;
