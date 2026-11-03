/* Geometry is always in the signed planner frame. Position is bottom-centre in
 * Three metres, positive Y is up and yaw zero points into −Z. */
import {buildHouse} from '../planner/data.js';
import {axes, footprint, convexOverlap, pointInPoly, segDist, bbox, rot, add2, sub2,
        scale2, dot2, len2, norm2, normDeg, clamp} from '../planner/util.js';

const EPS=.008, SNAP=.12, BODY=.21, GRID=.15; // walk.js radius .18 + walktest.js .03 clearance.
const safePath = value => /^[a-z0-9][a-z0-9_-]{0,63}$/.test(value);
const finite = a => typeof a==='number' && Number.isFinite(a);
const xyz = p => Array.isArray(p) && p.length===3 && p.every(finite);
const edges = poly => poly.map((a,i)=>[a,poly[(i+1)%poly.length]]);
const mid = (a,b) => scale2(add2(a,b),.5);
const flat = p => [p[0],p[2]];
const cross = (a,b) => a[0]*b[1]-a[1]*b[0];
const same = (a,b) => JSON.stringify(a)===JSON.stringify(b);
const indexed = rows => new Map(rows.map(r=>[r.id,r]));
const polyOf = it => footprint(it.position[0],it.position[2],it.size[0],it.size[1],it.rotation);
const slab = (a,b,half) => { const t=norm2(sub2(b,a)), n=scale2([-t[1],t[0]],half);
  return [add2(a,n),add2(b,n),sub2(b,n),sub2(a,n)]; };
const edgeDistance = (p,poly) => Math.min(...edges(poly).map(([a,b])=>segDist(p,a,b)));
const contains = (p,poly,tol=EPS) => pointInPoly(p,poly)||edgeDistance(p,poly)<=tol;

function fullFootprint(inner,outer,tol=EPS) {
  if (!inner.every(p=>contains(p,outer,tol))) return false;
  // Corners alone miss a thin concave notch. Split at every crossing and
  // classify each intervening open edge, including an edge through a vertex.
  for (const [a,b] of edges(inner)) {
    const ab=sub2(b,a), cuts=[0,1];
    for (const [c,d] of edges(outer)) {
      const cd=sub2(d,c), den=cross(ab,cd);
      if (Math.abs(den)<1e-10) continue;
      const ac=sub2(c,a), t=cross(ac,cd)/den, u=cross(ac,ab)/den;
      if (t>0 && t<1 && u>=-1e-8 && u<=1+1e-8) cuts.push(t);
    }
    cuts.sort((x,y)=>x-y);
    for (let i=1;i<cuts.length;i++)
      if (!contains(add2(a,scale2(ab,(cuts[i-1]+cuts[i])/2)),outer,tol)) return false;
  }
  return true;
}

function roomFaces(room,walls,elements,issuedFaces) {
  const faces=[];
  // The signed boundary is the measured air-side plane. Match collinear,
  // overlapping carrier runs, preserving authored side and clipped intervals.
  for (const [edgeIndex,[a,b]] of edges(room.polygon).entries()) {
    const dir=norm2(sub2(b,a)), length=len2(sub2(b,a)), middle=mid(a,b);
    let inward=[-dir[1],dir[0]];
    if (!contains(add2(middle,scale2(inward,.016)),room.polygon,0)) inward=scale2(inward,-1);
    const candidates=[];
    for (const w of walls) {
      if (w.storey!==room.storey || w.top<=room.floor+.04 || w.base>=room.ceiling-.04 || Math.abs(dot2(dir,w.t))<.99) continue;
      const distance=dot2(sub2(a,w.a),w.n), side=dot2(inward,w.n)>0?1:-1;
      if (distance*side < -.025 || Math.abs(distance-w.T/2*side)>.20) continue;
      const u0=dot2(sub2(w.a,a),dir), u1=dot2(sub2(w.b,a),dir);
      const lo=Math.max(0,Math.min(u0,u1)), hi=Math.min(length,Math.max(u0,u1));
      if (hi-lo<.025) continue;
      const root=w.id.split('~')[0], id=room.id+'/'+root+'/'+side;
      const authored=elements.some(e=>e.id.startsWith('RL-'+w.id+'-'+side+'-'+room.id+'-'));
      if (issuedFaces&&!authored) continue;
      candidates.push({id,room:room.id,type:'wall',wall:w.id,normal:inward,
        a:add2(a,scale2(dir,lo)),b:add2(a,scale2(dir,hi)),edgeIndex,authored,
        bottom:Math.max(room.floor,w.base),top:Math.min(room.ceiling,w.top)});
    }
    for (const f of candidates) {
      if (!f.authored && candidates.some(q=>q.authored && segDist(mid(f.a,f.b),q.a,q.b)<EPS)) continue;
      faces.push(f);
    }
  }
  // Short painted returns at a pier/end may have no full polygon edge. They
  // are paintable by element ID, though not a valid hanging span.
  for (const e of elements) {
    if (!e.id.startsWith('RL-') || !e.id.includes('-'+room.id+'-')) continue;
    const m=e.id.match(/^RL-(.+?)-(end-?1|-?1)-R-/);
    if (!m) continue;
    const id=room.id+'/'+m[1].split('~')[0]+'/'+m[2];
    if (!faces.some(f=>f.id===id)) faces.push({id,type:'wall',room:room.id,wall:m[1],
      edgeIndex:-1,normal:null,a:null,b:null,authored:true});
  }
  return faces;
}

function doorZones(o,measurements) {
  const zones=[];
  // The closed threshold stays passable even where a door has no leaf.
  if (o.kind==='window') return zones;
  zones.push(slab(o.p0,o.p1,Math.max(.25,o.T/2+.13)));
  const raw=measurements?.leaves?.[o.fixture], wallLength=o.width;
  const leaves=raw?.length ? raw.map((r,i)=>{
    const width=wallLength/raw.length, h=r.hinge;
    const closedMid=add2(o.p0,scale2(o.t,(i+.5)*width));
    const sign=dot2(sub2(closedMid,h),o.t)<0?-1:1;
    return {hinge:h,v:scale2(o.t,sign*width),swing:r.swing_deg||0,
      slide:r.slide?.length===3?[r.slide[0],r.slide[2]]:(r.slide||[0,0])};
  }):o.leaves.filter(l=>l.radius).map(l=>({hinge:l.hinge,v:sub2(l.free,l.hinge),swing:l.swing,slide:[0,0]}));
  for (const l of leaves) {
    const steps=Math.max(1,Math.ceil(Math.abs(l.swing)/6)), pose=k=>{
      const h=add2(l.hinge,scale2(l.slide,k));
      return [h,add2(h,rot(l.v,l.swing*k))];
    };
    for (let i=0;i<steps;i++) {
      // Bounding hull of the leaf's two posed slabs spans both rotation and
      // translation, as in house/doors.js poseOf(). 6° chord error <2 mm.
      const points=[...slab(...pose(i/steps),.023),...slab(...pose((i+1)/steps),.023)];
      zones.push(hull(points));
    }
  }
  return zones;
}

function hull(points) {
  const p=[...points].sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
  function chain(seq) {
    const side=[];
    for (const x of seq) {
      while (side.length>1 && cross(sub2(side.at(-1),side.at(-2)),sub2(x,side.at(-1)))<=0) side.pop();
      side.push(x);
    }
    return side.slice(0,-1);
  }
  return [...chain(p),...chain(p.reverse())];
}

function portals(room,rooms,openings) {
  const out=[];
  function add(id,p) {
    if (contains(p,room.polygon,0) && !out.some(q=>len2(sub2(q.point,p))<.22)) out.push({id,point:p});
  }
  for (const o of openings.filter(o=>o.storey===room.storey&&o.kind!=='window')) {
    const p=mid(o.p0,o.p1);
    for (const sign of [-1,1]) add(o.id,add2(p,scale2(o.n,sign*(o.T/2+BODY+.08))));
  }
  // Open-plan room transitions have no leaf. A measured neighbouring polygon
  // across a boundary without a wall is still an entrance for the walk route.
  for (const [a,b] of edges(room.polygon)) {
    const t=norm2(sub2(b,a)), n=[-t[1],t[0]], length=len2(sub2(b,a));
    for (const u of [.25,.5,.75]) {
      const p=add2(a,scale2(t,length*u));
      if (room.wallFaces.some(f=>f.a&&segDist(p,f.a,f.b)<.07)) continue;
      for (const sign of [-1,1]) {
        const near=add2(p,scale2(n,sign*.25)), far=add2(p,scale2(n,-sign*.25));
        const next=rooms.find(r=>r!==room&&r.storey===room.storey&&pointInPoly(far,r.polygon));
        if (next && !out.some(q=>q.id===next.id)) add(next.id,near);
      }
    }
  }
  return out;
}

export function buildRoomContext({site,version,spec,elements,doors={},seed={},variants={},catalogue={},floorCatalogue={}}) {
  const entry=Object.entries(spec.versions).find(([key,v])=>v.elements===version||key===version);
  if (!entry) throw new Error('No signed room schedule for '+version);
  const [key,schedule]=entry, measured=doors.versions?.[key], house=buildHouse(key,schedule,elements,measured,spec);
  const replaced=new Set(elements.elements.filter(e=>e.layer==='as_built').flatMap(e=>e.replaces||[]));
  const live=elements.elements.filter(e=>e.meta?.stage_out==null && !replaced.has(e.id));
  const issuedFaces=live.some(e=>e.id.startsWith('RL-'));
  const rooms=house.rooms.map(r=>({...r,label:r.plain||r.name,floorY:r.floor,ceilingY:r.ceiling,
    wallFaces:roomFaces(r,house.walls,live,issuedFaces)}));
  const openings=house.openings.map(o=>({...o,zones:doorZones(o,measured)}));
  for (const room of rooms) room.portals=portals(room,rooms,openings);
  const hosts=rooms.flatMap(r=>[{type:'floor',id:'floor/'+r.id,room:r.id,y:r.floorY},
    {type:'ceiling',id:'ceiling/'+r.id,room:r.id,y:r.ceilingY},...r.wallFaces]);
  const obstacles=house.fixtures.map(o=>({...o,label:o.id}));
  for (const s of house.stairs) {
    if (s.landing) obstacles.push({id:s.id,poly:s.poly,y0:s.base-.2,y1:s.base+1.8,label:'stairs'});
    else s.treads.forEach((poly,i)=>obstacles.push({id:s.id,poly,y0:s.base+s.rise*i-.18,
      y1:s.base+s.rise*(i+1)+1.8,label:'stairs'}));
  }
  for (const [id,h] of Object.entries(variants.hosts||{})) {
    hosts.push({...h,id,type:h.type||'surface'});
    if (!Array.isArray(h.bounds)||!xyz(h.bounds[0])||!xyz(h.bounds[1])) continue;
    const [a,b]=h.bounds;
    obstacles.push({id,label:h.label||id,room:h.room,y0:a[1],y1:b[1],
      poly:[[a[0],a[2]],[b[0],a[2]],[b[0],b[2]],[a[0],b[2]]]});
  }
  return {site,version,rooms,walls:house.walls,openings,hosts,obstacles,seedItems:seed.items||[],
    variants:variants.variants||{},catalogue:catalogue.items||[],floorKeys:(floorCatalogue.floors||[]).map(f=>f.id)};
}

export async function loadRoomContext({site,version,specSite,fetcher=globalThis.fetch}) {
  if (![site,version,specSite||site].every(safePath)) throw new Error('Invalid site or version');
  async function read(url,optional=false) {
    const response=await fetcher(url,{cache:'no-store'});
    if (!response.ok) {
      if (optional && (response.status===403||response.status===404)) return null;
      throw new Error(url+' · '+response.status);
    }
    return response.json();
  }
  const project='/assets/sites/'+site+'/', local='/assets/sites/'+(specSite||site)+'/';
  const projected=site==='house-wip' && local!=='/assets/sites/house/'?'/assets/sites/house/':null;
  async function signed(path) {
    const data=await read(local+path,!!projected);
    return data??await read(projected+path);
  }
  const spec=await signed('spec/spec_v1.json');
  const entry=Object.entries(spec.versions).find(([key,v])=>key===version||v.elements===version);
  if (!entry) throw new Error('No signed room schedule for '+version);
  const basename=entry[1].elements, variantPath=project+'furnish/'+version+'/';
  const [elements,doors,seed,variants,catalogue,floorCatalogue]=await Promise.all([
    read(project+basename+'_elements.json'),(async()=>await read('/assets/planner/'+(specSite||site)+'/doors.json',true)||
      (projected?await read('/assets/planner/house/doors.json',true):null)||{})(),
    read(variantPath+'seed.json',true),read(variantPath+'variants.json',true),
    read('/tools/library/kit/catalogue.json'),signed('spec/catalogue_v1.json')]);
  return buildRoomContext({site,version,spec,elements,doors,seed:seed||{},variants:variants||{},catalogue,floorCatalogue});
}

const isSurface = h => h?.type==='surface'||h?.type==='item';
const isRug = it => /^(rug|mat|runner)$/.test(it.kind);
const isSoft = it => /^(cushion|throw|towel|hand_towel|coat)$/.test(it.kind);
const seated = it => /^(sofa|armchair|bed|single_bed|bench|dining_chair|stool)$/.test(it.kind);
const isDressing = it => /^(curtain|roman_blind|blind)$/.test(it.kind);
const backed = it => /^(sofa|armchair|bed|single_bed|wardrobe|dresser|bedside|bookcase|desk|bench|radiator|shelf_unit|alcove_unit)$/.test(it.kind);
const samePose=(a,b)=>a&&b&&a.room===b.room&&a.kind===b.kind&&a.variant===b.variant&&
  same(a.size,b.size)&&same(a.host,b.host)&&same(a.position,b.position)&&a.rotation===b.rotation;
const overlapY=(a0,a1,b0,b1)=>Math.min(a1,b1)-Math.max(a0,b0)>EPS;
const dimEqual=(a,b)=>xyz(a)&&xyz(b)&&a.every((n,i)=>Math.abs(n-b[i])<=.0006);
const metres=(a,b)=>len2(sub2(a,b));
const wrap = v => normDeg(v);

function localOffset(parent,child) {
  const q=rot(sub2(flat(child.position),flat(parent.position)),-parent.rotation);
  return [q[0],child.position[1]-parent.position[1],q[1]];
}
function closePose(p,q,tolerance=.001) {return xyz(p)&&xyz(q)&&p.every((v,i)=>Math.abs(v-q[i])<=tolerance);}
function angleNear(a,b) {return Math.abs(wrap(a-b))<=.02;}
function contactAfter(old,it,ref,change) {
  if (!xyz(old.hostContact)||!xyz(ref.position)||!xyz(change.position)) return it;
  const q=add2(flat(change.position),rot(sub2(flat(old.hostContact),flat(ref.position)),change.rotation-ref.rotation));
  return {...it,hostContact:[q[0],change.position[1]+old.hostContact[1]-ref.position[1],q[1]]};
}

/** Materialise the local attachment on an individual child edit. Carried
 * siblings retain their issued local numbers when their relative pose is unchanged. */
export function attachLocally(item,parent) {
  if (!parent||!isSurface(item.host)||parent.id!==item.host.id) return item;
  const local=localOffset(parent,item),relative=wrap(item.rotation-parent.rotation);
  return {...item,hostOffset:closePose(item.hostOffset,local)?item.hostOffset:local,
    hostRotation:finite(item.hostRotation)&&angleNear(item.hostRotation,relative)?item.hostRotation:relative};
}

/** Return new poses for the root and every attached descendant, without editing
 * the input. Carry the original relative world pose exactly through the turn. */
export function moveGroup(items,candidate) {
  const old=items.find(it=>it.id===candidate.id);
  const parent=isSurface(candidate.host)?items.find(i=>i.id===candidate.host.id):null;
  let root=attachLocally(candidate,parent);
  if (!old) return [root];
  if (old.host?.id===candidate.host?.id) {
    root=contactAfter(old,root,old,candidate);
    if (!parent&&isSurface(candidate.host)&&xyz(old.hostOffset)&&finite(old.hostRotation)) {
      const hostYaw=old.rotation-old.hostRotation;
      const shift=rot(sub2(flat(candidate.position),flat(old.position)),-hostYaw);
      root={...root,hostOffset:[old.hostOffset[0]+shift[0],old.hostOffset[1]+candidate.position[1]-old.position[1],
        old.hostOffset[2]+shift[1]],hostRotation:wrap(candidate.rotation-hostYaw)};
    }
  }
  const group=[root], ids=new Set([candidate.id]);
  const unchanged=same(old.position,candidate.position)&&old.rotation===candidate.rotation&&old.room===candidate.room;
  for (let j=0;j<group.length;j++) {
    for (const it of items) {
      if (!isSurface(it.host)||it.host.id!==group[j].id||ids.has(it.id)) continue;
      ids.add(it.id);
      if (unchanged) {group.push(it);continue;}
      const xz=add2(flat(candidate.position),rot(sub2(flat(it.position),flat(old.position)),candidate.rotation-old.rotation));
      const carried={...it,room:candidate.room,position:[xz[0],candidate.position[1]+it.position[1]-old.position[1],xz[1]],
        rotation:wrap(it.rotation+candidate.rotation-old.rotation)};
      group.push(contactAfter(it,carried,old,candidate));
    }
  }
  return group;
}

export function descendants(items,id) {
  const out=new Set([id]);
  for (const key of out) for (const it of items)
    if (isSurface(it.host)&&it.host.id===key) out.add(it.id);
  return out;
}

function parentShape(ctx,items,host) {
  const owner=items.find(it=>it.id===host.id);
  if (owner?.position&&owner.size) return {id:owner.id,room:owner.room,poly:polyOf(owner),
    bottom:owner.position[1],top:owner.position[1]+owner.size[2],item:owner};
  const fixed=ctx.hosts.find(h=>h.id===host.id&&h.bounds);
  if (!fixed) return null;
  const [a,b]=fixed.bounds;
  return {id:fixed.id,room:fixed.room,bottom:a[1],top:b[1],
    poly:[[a[0],a[2]],[b[0],a[2]],[b[0],b[2]],[a[0],b[2]]],item:null};
}

export function fineMove(item, key, precise=false) {
  const step=precise ? .001 : .01;
  const axis={ArrowLeft:[0,-1],ArrowRight:[0,1],ArrowUp:[2,-1],ArrowDown:[2,1],PageUp:[1,1],PageDown:[1,-1]}[key];
  if (!axis) return null;
  const [i,sign]=axis, result={...item,position:[...item.position]};
  result.position[i]+=sign*step;
  if (i===1 && item.host.type!=='wall') result.heightAdjustment=(item.heightAdjustment||0)+sign*step;
  return result;
}

function fitsSupport(item,owner) {
  if (['table_lamp','bowl','vase','plant'].includes(item.kind))
    return contains(flat(item.position),owner.poly,0) && contains(flat(item.hostContact||item.position),owner.poly,0);
  return isSoft(item)?contains(flat(item.position),owner.poly,.015):fullFootprint(polyOf(item),owner.poly,.024);
}

function supportHeight(ctx,candidate,owner) {
  return baseSupportHeight(ctx,candidate,owner)+(candidate.heightAdjustment||0);
}
function baseSupportHeight(ctx,candidate,owner) {
  // Reviewed kit seats/cloth may sit below an owner's overall top. Use the
  // exported local seat datum, never an arbitrary child-supplied world height.
  const signed=ctx.seedItems.find(it=>it.id===candidate.id&&it.host?.id===owner.id);
  const signedParent=ctx.seedItems.find(it=>it.id===owner.id);
  if (signed&&signedParent&&xyz(signed.position)&&xyz(signedParent.position))
    return owner.bottom+signed.position[1]-signedParent.position[1];
  if (signed&&!signedParent&&xyz(signed.position)) return signed.position[1];
  if (isSoft(candidate)&&owner.item&&seated(owner.item)) {
    const h=owner.item.size[2], kind=owner.item.kind;
    if (kind==='sofa'||kind==='armchair') return owner.bottom+h*.51;
    if (kind==='bed'||kind==='single_bed') return owner.bottom+h*.48;
  }
  return owner.top;
}

function faceCandidates(ctx,candidate) {
  const p=flat(candidate.position);
  return (ctx.rooms.find(r=>r.id===candidate.room)?.wallFaces||[]).filter(f=>f.a&&f.b&&f.normal)
    .map(f=>({face:f,distance:segDist(p,f.a,f.b)})).sort((a,b)=>a.distance-b.distance);
}

function projectRange(poly,axis) { const p=poly.map(v=>dot2(v,axis)); return [Math.min(...p),Math.max(...p)]; }

export function snapPlacement(ctx,items,candidate,{free=false}={}) {
  const room=ctx.rooms.find(r=>r.id===candidate.room);
  if (!room||!xyz(candidate.position)||!xyz(candidate.size)||!finite(candidate.rotation)) return candidate;
  const out={...candidate,position:[...candidate.position],host:{...candidate.host}};
  function translate(v) { out.position[0]+=v[0]; out.position[2]+=v[1]; }
  const host=out.host;
  if (host.type==='free') return out;
  function detach() {
    out.host={type:'free',id:'room/'+room.id};
    delete out.hostOffset;delete out.hostRotation;delete out.hostContact;
    return out;
  }
  if (host.type==='floor'||host.type==='ground') {
    out.position[1]=room.floorY+(out.heightAdjustment||0); host.id='floor/'+room.id;
  } else if (host.type==='ceiling') {
    out.position[1]=room.ceilingY-out.size[2]+(out.heightAdjustment||0); host.id='ceiling/'+room.id;
  } else if (isSurface(host)) {
    const owner=parentShape(ctx,items,host);
    if (!owner || !contains(flat(out.position),owner.poly,.02)) return detach();
    out.position[1]=supportHeight(ctx,out,owner);
    return out;
  } else if (host.type==='wall') {
    // Prefer the face near the pointing position, switching at a room corner.
    const faces=faceCandidates(ctx,out), first=faces[0], old=faces.find(f=>f.face.id===host.id);
    const face=(old && (!first||old.distance<=first.distance+.035)?old:first)?.face;
    if (!face || first.distance>out.size[1]/2+SNAP+.05) return detach();
    host.id=face.id; out.rotation=wrap(Math.atan2(-face.normal[0],-face.normal[1])*180/Math.PI);
    const t=norm2(sub2(face.b,face.a)), length=len2(sub2(face.b,face.a));
    const along=dot2(sub2(flat(out.position),face.a),t);
    // Keep the wall-plane constraint even during free movement. Do not clamp an
    // over-wide object into a short wall; checkPlacement will mark it blocked.
    const u=free?along:clamp(along,Math.min(out.size[0]/2,length/2),Math.max(length-out.size[0]/2,length/2));
    const p=add2(add2(face.a,scale2(t,u)),scale2(face.normal,out.size[1]/2));
    out.position[0]=p[0]; out.position[2]=p[1]; return out;
  }
  if (free || host.type==='ceiling') return out;
  const adjustments=[];
  for (const {face:f,distance} of faceCandidates(ctx,out)) {
    if (distance>Math.max(out.size[0],out.size[1])+SNAP) continue;
    const fp=polyOf(out), center=dot2(f.a,f.normal), clearance=projectRange(fp,f.normal)[0]-center;
    const t=norm2(sub2(f.b,f.a)), along=projectRange(fp,t), span=projectRange([f.a,f.b],t);
    if (along[1]<span[0]||along[0]>span[1]||Math.abs(clearance)>SNAP) continue;
    adjustments.push({axis:f.normal,delta:-clearance,score:Math.abs(clearance)});
  }
  for (const other of items) {
    if (other.id===out.id||other.room!==out.room||!xyz(other.size)||!xyz(other.position)||isSurface(other.host)||isRug(other)) continue;
    const A=polyOf(out), B=polyOf(other);
    for (const ax of Object.values(axes(other.rotation))) {
      const perpendicular=[-ax[1],ax[0]], pa=projectRange(A,ax),pb=projectRange(B,ax);
      const ta=projectRange(A,perpendicular),tb=projectRange(B,perpendicular);
      if (ta[1]<tb[0]-SNAP||ta[0]>tb[1]+SNAP) continue;
      for (const delta of [pb[0]-pa[1],pb[1]-pa[0]])
        if (Math.abs(delta)<=SNAP) adjustments.push({axis:ax,delta,score:Math.abs(delta)});
    }
  }
  const used=[];
  for (const a of adjustments.sort((a,b)=>a.score-b.score)) {
    if (!used.length || (used.length===1&&Math.abs(dot2(a.axis,used[0]))<.03)) {
      translate(scale2(a.axis,a.delta)); used.push(a.axis);
    }
  }
  return out;
}

const routeCache=new WeakMap();
function routeGrid(room) {
  let grid=routeCache.get(room);
  if (grid) return grid;
  const b=bbox(room.polygon), nx=Math.max(1,Math.ceil(b.w/GRID)), nz=Math.max(1,Math.ceil(b.d/GRID));
  if (nx*nz>200000) throw new Error('Room is too large for the walk grid');
  const cells=Array.from({length:nx*nz},(_,i)=>{
    const p=[b.x0+(Math.floor(i/nz)+.5)*GRID,b.z0+(i%nz+.5)*GRID];
    return pointInPoly(p,room.polygon)&&edgeDistance(p,room.polygon)>=BODY-EPS?p:null;
  });
  grid={cells,nx,nz,x0:b.x0,z0:b.z0}; routeCache.set(room,grid); return grid;
}

function approaches(it) {
  const frontOnly=/^(sofa|armchair|dining_chair|desk|dresser|wardrobe|bookcase|shelf_unit|alcove_unit|stove|vanity|toilet)$/;
  const multiSide=/^(bed|single_bed|dining_table|coffee_table|bench|stool)$/;
  if (!frontOnly.test(it.kind)&&!multiSide.test(it.kind)) return [];
  if (it.host?.type!=='floor' && it.host?.type!=='ground') return [];
  const {u,f}=axes(it.rotation), p=flat(it.position),[width,depth]=it.size, pad=BODY+.055;
  const points=[];
  function side(normal,along,extent,span) {
    const edge=add2(p,scale2(normal,extent/2+pad));
    for (const factor of [-.3,0,.3]) points.push(add2(edge,scale2(along,span*factor)));
  }
  side(f,u,depth,width);
  if (multiSide.test(it.kind)) {
    side(u,f,width,depth);side(scale2(u,-1),f,width,depth);
    if (it.kind==='dining_table'||it.kind==='coffee_table') side(scale2(f,-1),u,depth,width);
  }
  return points;
}

function routeSignature(ctx,room,items) {
  const blockers=ctx.obstacles.filter(o=>(!o.room||o.room===room.id)&&overlapY(room.floorY+.035,room.floorY+1.8,o.y0,o.y1)).map(o=>o.poly);
  for (const it of items) {
    if (it.room!==room.id||!xyz(it.position)||!xyz(it.size)||isRug(it)||isSoft(it)) continue;
    if (overlapY(room.floorY+.035,room.floorY+1.8,it.position[1],it.position[1]+it.size[2])) blockers.push(polyOf(it));
  }
  const bounds=blockers.map(poly=>({poly,b:bbox(poly)})), {cells,nx,nz,x0,z0}=routeGrid(room);
  const comp=new Int32Array(cells.length).fill(-1);
  for (let i=0;i<cells.length;i++) {
    const p=cells[i];
    if (!p || bounds.some(({b,poly})=>p[0]>b.x0-BODY&&p[0]<b.x1+BODY&&p[1]>b.z0-BODY&&p[1]<b.z1+BODY&&
        (pointInPoly(p,poly)||edgeDistance(p,poly)<BODY-EPS))) comp[i]=-2;
  }
  const counts=[];
  for (let i=0;i<comp.length;i++) {
    if (comp[i]!==-1) continue;
    const n=counts.length,q=[i];comp[i]=n;
    for (let k=0;k<q.length;k++) {
      const j=q[k],x=Math.floor(j/nz),z=j%nz;
      for (const v of [x?j-nz:-1,x+1<nx?j+nz:-1,z?j-1:-1,z+1<nz?j+1:-1]) {
        if (v>=0&&comp[v]===-1) {comp[v]=n;q.push(v);}
      }
    }
    counts.push(q.length);
  }
  function componentNear(p,radius) {
    let nearest=-1,best=radius;
    const minX=Math.max(0,Math.floor((p[0]-radius-x0)/GRID)),maxX=Math.min(nx-1,Math.floor((p[0]+radius-x0)/GRID));
    const minZ=Math.max(0,Math.floor((p[1]-radius-z0)/GRID)),maxZ=Math.min(nz-1,Math.floor((p[1]+radius-z0)/GRID));
    for (let x=minX;x<=maxX;x++) for (let z=minZ;z<=maxZ;z++) {
      const i=x*nz+z;if (comp[i]<0) continue;
      const d=metres(p,cells[i]);if (d<best) {nearest=comp[i];best=d;}
    }
    return nearest;
  }
  const anchors=room.portals.map(port=>componentNear(port.point,.36));
  const entries=new Set(anchors.filter(a=>a>=0)), occupied=new Map();
  for (const it of items) {
    if (it.room!==room.id||!xyz(it.size)||!xyz(it.position)) continue;
    const points=approaches(it);
    if (points.length) occupied.set(it.id,points.some(p=>entries.has(componentNear(p,GRID*1.22))));
  }
  const max=Math.max(0,...counts);
  // A doorway must still connect to occupiable interior floor, not merely
  // retain a single unblocked point on the jamb side.
  return {max,anchors,occupied,interior:anchors.map(a=>a>=0&&counts[a]>=Math.min(12,max))};
}
function breaksRoute(ctx,room,previous,next) {
  const a=routeSignature(ctx,room,previous), b=routeSignature(ctx,room,next);
  if (a.max>=12 && b.max<12) return true;
  // A single entrance can still be cut off from a bed/desk beyond an item.
  // Compare usable approaches only, preserving reviewed unreachable seed poses.
  for (const [id,reachable] of b.occupied) {
    if (!reachable && (a.occupied.get(id) || !a.occupied.has(id)&&a.anchors.some(c=>c>=0))) return true;
  }
  for (let i=0;i<a.anchors.length;i++) {
    if (a.interior[i]&&!b.interior[i]) return true;
    for (let j=0;j<i;j++) if (a.anchors[i]>=0&&a.anchors[i]===a.anchors[j]&&b.anchors[i]!==b.anchors[j]) return true;
  }
  return false;
}

function overlapsWall(ctx,item,fp) {
  for (const w of ctx.walls) {
    const bottom=item.position[1],top=bottom+item.size[2];
    if (!overlapY(bottom,top,w.base,w.top)) continue;
    const range=projectRange(fp,w.t), wa=dot2(w.a,w.t);
    if (range[1]<wa||range[0]>wa+w.L||convexOverlap(fp,slab(w.a,w.b,w.T/2))<=.018) continue;
    // Room edges are the signed lining (some have an asymmetric wall stack).
    // Only test a wall which actually cuts the polygon interior.
    const r=ctx.rooms.find(r=>r.id===item.room);
    const wallPoint=add2(w.a,scale2(w.t,clamp(dot2(sub2(flat(item.position),w.a),w.t),0,w.L)));
    if (!pointInPoly(wallPoint,r.polygon)||edgeDistance(wallPoint,r.polygon)<.02) continue;
    if (!ctx.openings.some(o=>o.wall===w.id&&bottom>=o.sill-EPS&&top<=o.head+EPS&&
        range[0]>=dot2(o.p0,w.t)-EPS&&range[1]<=dot2(o.p1,w.t)+EPS)) return true;
  }
  return false;
}

function geometryReasons(ctx,items,item) {
  const reasons=[],room=ctx.rooms.find(r=>r.id===item.room), p=item.position, size=item.size;
  if (!room||!xyz(p)||!xyz(size)||!size.every(n=>n>0&&n<=100)||!finite(item.rotation)) return ['Invalid room, dimensions or pose'];
  const h=item.host;
  if (!h||typeof h.id!=='string') return ['Choose a measured host surface'];
  const fp=polyOf(item),bottom=p[1],top=bottom+size[2];
  if (!fullFootprint(fp,room.polygon)) reasons.push('The footprint crosses the room boundary');
  if (bottom<room.floorY-.015||top>room.ceilingY+.018) reasons.push('Outside the finished floor or ceiling');
  if (h.type==='floor'||h.type==='ground') {
    if (h.id!=='floor/'+room.id||Math.abs(bottom-room.floorY-(item.heightAdjustment||0))>.012) reasons.push('The base must sit on this room’s floor');
    if (backed(item)) {
      const front=axes(item.rotation).f;
      for (const {face:f} of faceCandidates(ctx,item)) {
        const distance=projectRange(fp,f.normal)[0]-dot2(f.a,f.normal);
        if (Math.abs(distance)<.04 && dot2(front,f.normal)<-.35) {reasons.push('Turn the front into the room');break;}
      }
    }
  } else if (h.type==='ceiling') {
    if (h.id!=='ceiling/'+room.id||Math.abs(top-room.ceilingY-(item.heightAdjustment||0))>.018) reasons.push('Seat the fitting on this room’s ceiling');
  } else if (h.type==='wall') {
    const segments=room.wallFaces.filter(f=>f.id===h.id&&f.a), f=segments.find(f=>{
      const t=norm2(sub2(f.b,f.a)), span=projectRange([f.a,f.b],t), range=projectRange(fp,t);
      return range[0]>=span[0]-.015&&range[1]<=span[1]+.015&&bottom>=f.bottom-.02&&top<=f.top+.02;
    });
    if (!f) reasons.push('The whole item needs a finished wall span');
    else {
      if (Math.abs(projectRange(fp,f.normal)[0]-dot2(f.a,f.normal))>.015) reasons.push('Place the mounting face against the wall');
      if (dot2(axes(item.rotation).f,f.normal)<.985) reasons.push('Turn the front into the room');
      const windowDressing=isDressing(item);
      for (const o of ctx.openings) {
        if (o.wall.split('~')[0]!==f.wall.split('~')[0]||!overlapY(bottom,top,o.sill,o.head)) continue;
        const along=projectRange(fp,o.t),opening=projectRange([o.p0,o.p1],o.t);
        if (Math.min(along[1],opening[1])-Math.max(along[0],opening[0])>EPS && !(windowDressing&&o.kind==='window')) {
          reasons.push('The wall item covers the '+o.label);break;
        }
      }
    }
  } else if (isSurface(h)) {
    const owner=parentShape(ctx,items,h);
    if (!owner||owner.room&&owner.room!==room.id||descendants(items,item.id).has(h.id)) reasons.push('Choose an existing support in this room');
    else {
      if (Math.abs(bottom-supportHeight(ctx,item,owner))>.018) reasons.push('Seat the base on its support');
      if (!fitsSupport(item,owner)) reasons.push('The item extends beyond its support');
    }
  } else if(h.type!=='free') reasons.push('Unknown host surface');
  if (overlapsWall(ctx,item,fp)) reasons.push('The footprint hits a wall');
  for (const o of ctx.obstacles) {
    if (o.id===h.id||o.room&&o.room!==room.id||!overlapY(bottom,top,o.y0,o.y1)) continue;
    if (convexOverlap(fp,o.poly)>.014) {reasons.push('Hits '+o.label);break;}
  }
  for (const other of items) {
    if (other.id===item.id||other.id===h.id||other.host?.id===item.id||other.room!==room.id||!xyz(other.size)||!xyz(other.position)) continue;
    if (isRug(item)!==isRug(other) && (isRug(item)||isRug(other))) continue;
    if (!overlapY(bottom,top,other.position[1],other.position[1]+other.size[2])) continue;
    if (convexOverlap(fp,polyOf(other))>.014) {
      const a=ctx.seedItems.find(s=>s.id===item.id), b=ctx.seedItems.find(s=>s.id===other.id);
      if (a&&b&&a.variant===item.variant&&b.variant===other.variant&&
          closePose(localOffset(other,item),localOffset(b,a),.003)&&angleNear(item.rotation-other.rotation,a.rotation-b.rotation)) continue;
      reasons.push('Overlaps '+(other.label||other.id));break;
    }
  }
  if (!isRug(item)) for (const o of ctx.openings) {
    if (o.storey!==room.storey||!overlapY(bottom,top,o.sill,o.head)) continue;
    if (o.zones.some(poly=>convexOverlap(fp,poly)>.008)) {reasons.push('Blocks the '+o.label);break;}
  }
  return reasons;
}

function changedChecks(ctx,previous,next,changed) {
  const reasons=[],affected=new Set(), seed=indexed(ctx.seedItems), old=indexed(previous);
  for (const it of changed) {
    if (samePose(old.get(it.id),it)||samePose(seed.get(it.id),it)) continue;
    const found=geometryReasons(ctx,next,it);
    if (found.length) reasons.push(...found);
    if (!isSoft(it)&&!isRug(it)&&it.host?.type!=='ceiling') affected.add(it.room);
  }
  if (!reasons.length) for (const id of affected) {
    const room=ctx.rooms.find(r=>r.id===id);
    if (room&&breaksRoute(ctx,room,previous,next)) reasons.push('Keep a walking route from the room’s entrances');
  }
  return {ok:!reasons.length,reasons:[...new Set(reasons)]};
}

export function checkGroup(ctx,items,candidate) {
  const group=moveGroup(items,candidate), ids=new Set(group.map(i=>i.id));
  return changedChecks(ctx,items,[...items.filter(it=>!ids.has(it.id)),...group],group);
}
export const checkPlacement=checkGroup;
// The planner shows spatial advice; only the record and attachment graph constrain saving.
export function assessDesign(ctx,items,candidate) {
  const advice=checkGroup(ctx,items,candidate);
  return {ok:true,reasons:advice.reasons};
}

const idOK=s=>typeof s==='string' && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$/.test(s);
const colourOK=s=>typeof s==='string' && /^#[\da-f]{6}$/i.test(s);
const dict=v=>v&&typeof v==='object'&&!Array.isArray(v);
// An old stock style label only has meaning together with its reviewed product ID.
export function normaliseVariant(item,catalogue) {
  const stock=catalogue.find(c=>c.id===item.catalogueId);
  return stock&&item.variant===stock.variant ? {...item,variant:stock.id} : item;
}
function itemContract(ctx,item) {
  if (!idOK(item.id)||!idOK(item.kind)||!idOK(item.style)||!idOK(item.variant)||!idOK(item.catalogueId))
    return 'Invalid item identity, kind, style or variant';
  if (!xyz(item.position)||item.position.some(n=>Math.abs(n)>10000)||!xyz(item.size)||item.size.some(n=>n<=0||n>100)||
      !finite(item.rotation)||Math.abs(item.rotation)>36000||!ctx.rooms.some(r=>r.id===item.room)) return 'Invalid item dimensions, position or room';
  if (!dict(item.host)||!['floor','ceiling','wall','ground','surface','item','free'].includes(item.host.type)||
      typeof item.host.id!=='string'||!item.host.id.length||item.host.id.length>192) return 'Invalid host surface';
  const expected={floor:'floor',ground:'floor',ceiling:'ceiling',free:'room'}[item.host.type];
  if(expected && item.host.id!==expected+'/'+item.room)return 'Unknown host in this room';
  if ('lampOn' in item&&typeof item.lampOn!=='boolean') return 'Invalid lamp switch';
  if ('finishes' in item&&(!dict(item.finishes)||Object.keys(item.finishes).length>32||
      Object.entries(item.finishes).some(([k,v])=>!idOK(k)||!colourOK(v)))) return 'Invalid item finish';
  if ('heightAdjustment' in item&&(!finite(item.heightAdjustment)||Math.abs(item.heightAdjustment)>100)) return 'Invalid height adjustment';
  if ('hostOffset' in item&&(!xyz(item.hostOffset)||item.hostOffset.some(n=>Math.abs(n)>100))) return 'Invalid attachment offset';
  if ('hostRotation' in item&&!finite(item.hostRotation)) return 'Invalid attachment rotation';
  const stock=ctx.catalogue.find(c=>c.id===item.catalogueId), variant=Object.hasOwn(ctx.variants,item.variant)?ctx.variants[item.variant]:null;
  const signed=ctx.seedItems.find(s=>s.variant===item.variant&&s.catalogueId===item.catalogueId);
  if (variant) {
    if (!dimEqual(item.size,variant.size)||(variant.catalogueId||signed?.catalogueId)!==item.catalogueId||
        (variant.kind||signed?.kind)!==item.kind||(variant.style||signed?.style)!==item.style) return 'Unknown measured item or altered dimensions';
  } else if (!stock||item.kind!==stock.kind||(item.style!==stock.style&&!stock.compatibleStyles?.includes(item.style))||
      normaliseVariant(item,ctx.catalogue).variant!==stock.id||!dimEqual(item.size,stock.size_m))
    return 'Unknown catalogue item or altered dimensions';
  const mount=stock?.host, actual=item.host.type;
  if (mount&&actual!=='free'&&actual!==mount&&!(mount==='surface'&&isSurface(item.host))&&!(actual==='ground'&&mount==='floor')&&
      !(signed&&signed.host.type===actual)&&!(mount==='floor'&&isSurface(item.host)&&item.kind==='plant')) return 'Incompatible mounting surface';
  return null;
}

/** Interior write gate. Compare only edited placements, but catch orphaning on
 * delete/reparent and route changes against the complete before/after layout. */
export function validateFurnishDelta(ctx,previous,next) {
  if (!Array.isArray(next.items)||next.items.length>1024||!dict(next.wallColours)||!dict(next.roomFloors))
    throw new Error('Expected bounded items, wallColours and roomFloors');
  const old=indexed(previous.items), current=new Map(), changed=[];
  for (const item of next.items) {
    if (!dict(item)||!idOK(item.id)||current.has(item.id)) throw new Error('Invalid or duplicate item ID');
    current.set(item.id,item);
    if (same(old.get(item.id),item)) continue;
    const issue=itemContract(ctx,item); if (issue) throw new Error(item.id+': '+issue);
    changed.push(item);
  }
  for (const it of next.items) {
    if (!isSurface(it.host)) continue;
    const was=old.get(it.id);
    if (old.has(it.host.id)&&!current.has(it.host.id)) throw new Error(it.id+': its supporting furniture was removed');
    const owner=current.get(it.host.id),oldOwner=old.get(it.host.id);
    if(!owner&&!ctx.hosts.some(h=>h.id===it.host.id))throw new Error(it.id+': unknown supporting item');
    const ownerMoved=owner&&oldOwner&&(!closePose(owner.position,oldOwner.position)||!angleNear(owner.rotation,oldOwner.rotation)||owner.room!==oldOwner.room);
    if (was&&same(was,it)&&!ownerMoved) continue;
    if (ownerMoved && was?.host?.id===it.host.id && samePose(was,it) &&
        (!closePose(localOffset(owner,it),localOffset(oldOwner,was)) ||
         !angleNear(it.rotation-owner.rotation,was.rotation-oldOwner.rotation)))
      throw new Error(it.id+': carry the supported item with its owner');
    const frame=owner||ctx.hosts.find(h=>h.id===it.host.id&&xyz(h.position)&&finite(h.rotation));
    if (frame&&((xyz(it.hostOffset)&&!closePose(it.hostOffset,localOffset(frame,it),.003))||
        (finite(it.hostRotation)&&!angleNear(it.hostRotation,it.rotation-frame.rotation))))
      throw new Error(it.id+': attachment does not match its support');
    const seen=new Set([it.id]); let at=it;
    while (isSurface(at.host)&&current.has(at.host.id)) {
      if (seen.has(at.host.id)) throw new Error(it.id+': cyclic support');
      seen.add(at.host.id);at=current.get(at.host.id);
    }

  }
  const walls=new Set(ctx.rooms.flatMap(r=>r.wallFaces.map(f=>f.id))), rooms=new Set(ctx.rooms.map(r=>r.id));
  for (const [key,value] of Object.entries(next.wallColours))
    if (value!==previous.wallColours[key]&&(!walls.has(key)||!colourOK(value))) throw new Error('Unknown wall face or colour');
  for (const [key,value] of Object.entries(next.roomFloors))
    if (value!==previous.roomFloors[key]&&(!rooms.has(key)||!ctx.floorKeys.includes(value))) throw new Error('Unknown room or floor covering');
  const result=changedChecks(ctx,previous.items,next.items,changed);
  return {ok:true,reasons:result.reasons};
}
