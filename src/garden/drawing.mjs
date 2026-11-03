import {arc, circle, rectangle, point, fitStroke, measureGeometry, transformGeometry, centerOf, handlesOf, moveHandle, isClosed, sampleGeometry, validateGeometry} from './geometry.mjs';
import {KINDS, MATERIALS, PALETTES, PATTERNS, SPECIES, createFeature} from './catalogue.mjs';

const rad = Math.PI / 180;
const distance = (a,b) => Math.hypot(a[0]-b[0],a[1]-b[1]);
const groundPoint = p => [p.x,p.z];
const round = n => Math.round(n*1000)/1000;
export function angleOf(g) {
  if (g.yaw !== undefined) return g.yaw/rad;
  if (g.type === 'arc') return g.startAngle/rad;
  if (g.type === 'curve') {
    const [a,b]=g.knots; return Math.atan2(b.p[1]-a.p[1],b.p[0]-a.p[0])/rad;
  }
  return 0;
}
export function drawnGeometry(kind,method,coords,finish=false) {
  const form=KINDS[kind].form, start=coords[0], end=coords.at(-1);
  if (form==='point') return point(end);
  if (method==='circle') return circle(start,distance(start,end));
  if (method==='rectangle') return rectangle([(start[0]+end[0])/2,(start[1]+end[1])/2],Math.abs(end[0]-start[0]),Math.abs(end[1]-start[1]));
  if (method==='square') { const side=2*Math.max(Math.abs(end[0]-start[0]),Math.abs(end[1]-start[1]));return rectangle(start,side,side); }
  const closed=form==='area'||(coords.length>=4 && distance(start,end)<.25);
  if (form==='area' && !finish && distance(start,end)>.65) throw Error('Bring the outline back to its start to close this area.');
  if (method==='corners') {
    const points=coords.filter((p,i)=>i===0||distance(p,coords[i-1])>.005);
    if (points.length>1 && distance(points.at(-1),points[0])<.01) points.pop();
    return validateGeometry({type:'curve',closed,knots:points.map(p=>({p,in:[...p],out:[...p],mode:'corner'}))});
  }
  return fitStroke(coords,{closed,mode:method});
}

// Transient gestures generate previews. A completed gesture enters the shared layout history exactly once.
export function createDrawing({store,pick,ground,changed}) {
  const state={tool:'draw',kind:'patio',method:'circle',selectedId:null,status:'',conflict:false};
  let gesture=null,draft=null,corners=[],cornerY=0;
  const selected=()=>store().get(state.selectedId);
  const show=(feature=null,points=null)=>{draft=feature; changed(points);};
  const set=(feature,label)=>{state.selectedId=feature.id; return store().put(feature,label);};
  function snap(p,skip) {
    let best=.105,found=null;
    for(const f of store().objects) if(f.id!==skip) for(const h of handlesOf(f.geometry)) {
      if(h.kind==='tangent'||h.kind==='rotate') continue;
      const d=distance(h.point,p); if(d<best){best=d;found=h.point;}
    }
    return found?[...found]:p.map(round);
  }
  function begin(pos,{screenY=0,tolerance=.25,free=false}={}) {
    if(gesture) return;
    const p=groundPoint(pos);
    if(state.tool==='draw') {
      const first=free?p:snap(p,null);
      if(state.method==='corners'&&KINDS[state.kind].form!=='point'){
        if(!corners.length)cornerY=ground(first[0],first[1])??pos.y;
        if(corners.length>=3 && distance(first,corners[0])<tolerance){ finishCorners(); return; }
        corners.push(first); show(null,corners); return;
      }
      gesture={start:first,coords:[first],base:ground(first[0],first[1])??pos.y,free};show(null,[first]);return;
    }
    let f=selected(),handle=null;
    if(f && state.tool!=='level'){
      // A knot at the bounds centre must still be directly editable.
      handle=handlesOf(f.geometry).map(h=>({...h,d:distance(h.point,p)})).filter(h=>h.d<tolerance)
        .sort((a,b)=>Math.abs(a.d-b.d)>1e-8 ? a.d-b.d : Number(a.id==='center')-Number(b.id==='center'))[0];
    }
    const id=handle?f.id:pick(...p,tolerance);
    state.selectedId=id||null;f=selected();
    if(f) gesture={start:p,original:f,handle,screenY,free};
    show();
  }
  function move(pos,{screenY=0,deltaY=null}={}) {
    if(!gesture) return;
    let p=groundPoint(pos);
    if(!gesture.original){
      if(distance(p,gesture.coords.at(-1))>=.012 && gesture.coords.length<4096)gesture.coords.push(p);
      if(['circle','rectangle','square'].includes(state.method) && KINDS[state.kind].form!=='point') {
        try { const geometry=drawnGeometry(state.kind,state.method,gesture.coords); const feature=gesture.preview||createFeature(state.kind,geometry,gesture.base);feature.geometry=geometry;gesture.preview=feature;show(feature); }
        catch {show(null,gesture.coords);}
      } else show(null,gesture.coords);
      return;
    }
    const f=structuredClone(gesture.original);
    if(state.tool==='level') f.level=round(f.level+(deltaY??(gesture.screenY-screenY)*.01));
    else {
      const h=gesture.handle;
      if(h && h.id!=='center'){
        if(!gesture.free)p=snap(p,f.id);
        try {
          f.geometry=moveHandle(f.geometry,h.id,p);
          gesture.invalid='';state.status='';
        } catch(e) {
          gesture.invalid=e.message;state.status=e.message;
          show();return;
        }
      }else{
        let offset=[p[0]-gesture.start[0],p[1]-gesture.start[1]];
        if(!gesture.free){
          const center=centerOf(f.geometry), target=snap([center[0]+offset[0],center[1]+offset[1]],f.id);
          offset=[target[0]-center[0],target[1]-center[1]];
        }
        f.geometry=transformGeometry(f.geometry,{offset});
      }
    }
    show(f);
  }
  function end() {
    if(!gesture) return;
    const stroke=gesture,preview=draft;gesture=null;draft=null;
    if(stroke.invalid){state.status=stroke.invalid;show();return;}
    try {
      if(stroke.original){ if(preview)set(preview,state.tool==='level'?'Change level':'Move or resize'); }
      else {const geometry=drawnGeometry(state.kind,state.method,stroke.coords);set(createFeature(state.kind,geometry,stroke.base),'Draw '+KINDS[state.kind].label);state.tool='select';}
      state.status='';
    }catch(e){state.status=e.message;}
    show();
  }
  function finishCorners(){
    if(!corners.length)return;
    try{set(createFeature(state.kind,drawnGeometry(state.kind,'corners',corners,true),cornerY),'Draw corners'); corners=[];state.tool='select';state.status='';}
    catch(e){state.status=e.message;}
    show(null,corners);
  }
  function cancel(){gesture=null;corners=[];show();}
  function changeField(f,key,value){
    const options={material:MATERIALS,coping:MATERIALS,pattern:PATTERNS,palette:PALETTES,species:SPECIES};
    if(key in options && (key!=='coping'||value!=='' ) && !Object.hasOwn(options[key],value))throw Error('Unknown '+key);
    if(!['label','level','width','height','material','coping','pattern','palette','species','steps','geometry'].includes(key)) throw Error('Unknown field');
    if(key==='species'){const species=SPECIES[value];if(species.kind!==f.kind)throw Error('Choose a '+f.kind); f.width=species.width;f.height=species.height;}
    f[key]=value;set(f,'Change '+key);
  }
  function command(name,value){
    const f=selected();
    try{
      state.status='';
      if(name==='kind'){if(!KINDS[value])throw Error('Unknown feature');cancel();state.kind=value;state.tool='draw';state.selectedId=null;if(KINDS[value].form==='line'&&['circle','square','rectangle'].includes(state.method))state.method='auto';}
      else if(name==='method'){cancel();state.method=value;state.tool='draw';}
      else if(name==='tool'){cancel();state.tool=value;}
      else if(name==='select'){cancel();state.selectedId=value;state.tool='select';}
      else if(name==='finish') finishCorners();
      else if(name==='cancel')cancel();
      else if(name==='undo'||name==='redo'){cancel();store()[name]();}
      else if(name==='delete'&&f){state.selectedId=null;store().remove(f.id);}
      else if(name==='copy'&&f){state.selectedId=store().duplicate(f.id).id;}
      else if(name==='field'&&f)changeField(f,value.key,value.value);
      else if(name==='angle'&&f){f.geometry=transformGeometry(f.geometry,{angle:(value-angleOf(f.geometry))*rad});set(f,'Rotate');}
      else if(name==='size'&&f){
        if(f.geometry.type==='point'){f.width=value.width;f.height=value.depth;}
        else{const m=measureGeometry(f.geometry);f.geometry=transformGeometry(f.geometry,{scale:[m.width>1e-6?value.width/m.width:1,m.depth>1e-6?value.depth/m.depth:1]});}
        set(f,'Resize');
      }
      else if(name==='steps'&&f){
        if(!isClosed(f.geometry))throw Error('Select an enclosed area for perimeter steps.');
        if(Math.abs(f.level)<.02 && f.kind!=='raised-bed'){state.status='Set a raised or sunken level first.';}
        else {if(f.steps)delete f.steps;else f.steps={at:0,count:Math.max(1,Math.min(32,Math.ceil(Math.abs(f.level||f.height)/.16))),width:1};set(f,'Change steps');}
      }
    }catch(e){state.status=e.message;}
    changed(corners.length?corners:null);
  }
  return {state,begin,move,end,cancel,command,finishCorners,get draft(){return draft;},get drawing(){return !!gesture;},get corners(){return corners;}};
}

