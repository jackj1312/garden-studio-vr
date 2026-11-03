/** Garden plan geometry. All coordinates and absolute control points are [x,z] metres. */
const TAU = Math.PI * 2, EPS = 1e-8, MIN = .001;
const add = (a,b) => [a[0]+b[0],a[1]+b[1]];
const sub = (a,b) => [a[0]-b[0],a[1]-b[1]];
const mul = (a,k) => [a[0]*k,a[1]*k];
const dot = (a,b) => a[0]*b[0]+a[1]*b[1];
const cross = (a,b) => a[0]*b[1]-a[1]*b[0];
const len = a => Math.hypot(...a);
const dist = (a,b) => len(sub(a,b));
const unit = a => len(a)>EPS ? mul(a,1/len(a)) : [0,0];
const lerp = (a,b,t) => add(a,mul(sub(b,a),t));
const polar = t => [Math.cos(t),Math.sin(t)];
const rotate = (p,t) => [Math.cos(t)*p[0]-Math.sin(t)*p[1],Math.sin(t)*p[0]+Math.cos(t)*p[1]];
const mod = x => ((x%TAU)+TAU)%TAU;
const bearing = p => Math.atan2(p[1],p[0]);
const atAngle = (g,t) => add(g.center,mul(polar(t),g.radius));

function check(condition, message) {
  if (!condition) throw new RangeError(message);
}
function checkPoint(p) {
  check(Array.isArray(p) && p.length===2 && p.every(Number.isFinite),'Expected a finite [x,z] point');
}
function bounds(points) {
  const low=[Infinity,Infinity],high=[-Infinity,-Infinity];
  for(const p of points) for(let i=0;i<2;i++){
    low[i]=Math.min(low[i],p[i]); high[i]=Math.max(high[i],p[i]);
  }
  return {low,high,width:high[0]-low[0],depth:high[1]-low[1]};
}
function segmentDistance(p,a,b) {
  const v=sub(b,a),sq=dot(v,v);
  return dist(p,lerp(a,b,sq ? Math.max(0,Math.min(1,dot(sub(p,a),v)/sq)) : 0));
}
function polygonArea(points) {
  if(points.length<3) return 0;
  const a=points[0];
  let sum=0;
  for(let i=1;i<points.length-1;i++) sum+=cross(sub(points[i],a),sub(points[i+1],a));
  return sum/2;
}
function corners(g) {
  return [[-1,-1],[1,-1],[1,1],[-1,1]].map(([x,z])=>
    add(g.center,rotate([x*g.width/2,z*g.depth/2],g.yaw)));
}

export const isClosed = g => g.type==='circle' || g.type==='rectangle' || (g.type==='curve' && g.closed);

function segments(g) {
  const out=[],knots=g.knots;
  for(let i=0;i<knots.length-(g.closed?0:1);i++){
    const a=knots[i],b=knots[(i+1)%knots.length];
    out.push([a.p,a.out,b.in,b.p]);
  }
  return out;
}
function split([a,b,c,d]) {
  const p=lerp(a,b,.5),q=lerp(b,c,.5),r=lerp(c,d,.5);
  const s=lerp(p,q,.5),t=lerp(q,r,.5),m=lerp(s,t,.5);
  return [[a,p,s,m],[m,t,r,d]];
}
function cubicAt([a,b,c,d],t) {
  const s=1-t;
  return [0,1].map(i=>a[i]*s*s*s+3*b[i]*s*s*t+3*c[i]*s*t*t+d[i]*t*t*t);
}
function cubicDerivative([a,b,c,d],t) {
  const s=1-t;
  return [0,1].map(i=>3*(s*s*(b[i]-a[i])+2*s*t*(c[i]-b[i])+t*t*(d[i]-c[i])));
}
function sampleCubic(seg,tol,out,level=0) {
  const [a,b,c,d]=seg;
  if(level===16 || Math.max(segmentDistance(b,a,d),segmentDistance(c,a,d))<=tol){
    out.push([...d]); return;
  }
  const [left,right]=split(seg);
  sampleCubic(left,tol,out,level+1); sampleCubic(right,tol,out,level+1);
}
export function sampleGeometry(g,tolerance=.02) {
  check(Number.isFinite(tolerance) && tolerance>0,'Sampling tolerance must be positive');
  if(g.type==='point') return [[...g.center]];
  if(g.type==='rectangle') return corners(g);
  if(g.type==='curve'){
    const out=[[...g.knots[0].p]];
    for(const segment of segments(g)) sampleCubic(segment,tolerance,out);
    if(g.closed) out.pop();
    return out;
  }
  check(g.type==='circle'||g.type==='arc','Unknown garden geometry');
  const closed=g.type==='circle',start=closed?0:g.startAngle,sweep=closed?TAU:g.sweepAngle;
  // Limit sagitta error to tolerance. The asin form is stable for small tolerances.
  const step=4*Math.asin(Math.sqrt(Math.min(1,tolerance/(2*g.radius))));
  const count=Math.max(closed?8:2,Math.ceil(Math.abs(sweep)/step));
  check(count<=65536,'Sampling tolerance is too small for this arc');
  return Array.from({length:count+(closed?0:1)},(_,i)=>atAngle(g,start+sweep*i/count));
}
function pointsOnBounds(g) {
  if(g.type==='arc'){
    const ts=[g.startAngle,g.startAngle+g.sweepAngle];
    for(let t=0;t<TAU;t+=Math.PI/2){
      if(mod((t-g.startAngle)*Math.sign(g.sweepAngle))<=Math.abs(g.sweepAngle)+EPS) ts.push(t);
    }
    return ts.map(t=>atAngle(g,t));
  }
  const pts=[];
  for(const seg of segments(g)){
    const [p,q,r,s]=seg;
    pts.push(p,s);
    for(let i=0;i<2;i++){
      // Real derivative roots give exact plan extents between knots.
      const a=-p[i]+3*q[i]-3*r[i]+s[i],b=2*(p[i]-2*q[i]+r[i]),c=q[i]-p[i];
      const discriminant=b*b-4*a*c;
      const roots=Math.abs(a)<EPS ? (Math.abs(b)<EPS?[]:[-c/b]) :
        (discriminant<0?[]:[(-b-Math.sqrt(discriminant))/(2*a),(-b+Math.sqrt(discriminant))/(2*a)]);
      for(const t of roots) if(t>0 && t<1) pts.push(cubicAt(seg,t));
    }
  }
  return pts;
}
export function centerOf(g) {
  if(g.type!=='curve') return [...g.center];
  const {low,high}=bounds(pointsOnBounds(g));
  return lerp(low,high,.5);
}

function lengthOf(seg,level=0) {
  const [a,b,c,d]=seg;
  const chord=dist(a,d),net=dist(a,b)+dist(b,c)+dist(c,d);
  if(level===15 || net-chord<.00001) return (net+chord)/2;
  const [l,r]=split(seg);
  return lengthOf(l,level+1)+lengthOf(r,level+1);
}
export function measureGeometry(g) {
  if(g.type==='point') return {area:0,perimeter:0,width:0,depth:0};
  if(g.type==='circle') return {area:Math.PI*g.radius**2,perimeter:TAU*g.radius,width:2*g.radius,depth:2*g.radius};
  if(g.type==='rectangle') return {area:g.width*g.depth,perimeter:2*(g.width+g.depth),width:g.width,depth:g.depth};
  const {width,depth}=bounds(pointsOnBounds(g));
  if(g.type==='arc') return {area:0,perimeter:Math.abs(g.sweepAngle)*g.radius,width,depth};
  let signed=0,perimeter=0;
  for(const segment of segments(g)){
    perimeter+=lengthOf(segment);
    if(g.closed){
      // Green's integral has a polynomial integrand of degree at most five.
      // A three-point Gauss rule integrates it exactly.
      for(const [t,w] of [[.5-Math.sqrt(3/5)/2,5/18],[.5,4/9],[.5+Math.sqrt(3/5)/2,5/18]]){
        signed+=w*cross(sub(cubicAt(segment,t),g.knots[0].p),cubicDerivative(segment,t))/2;
      }
    }
  }
  return {area:Math.abs(signed),perimeter,width,depth};
}

function intersects(a,b,c,d) {
  if([0,1].some(i=>Math.max(a[i],b[i])+EPS<Math.min(c[i],d[i]) ||
                    Math.max(c[i],d[i])+EPS<Math.min(a[i],b[i]))) return false;
  const sign=(p,q,r)=>Math.sign(Math.abs(cross(sub(q,p),sub(r,p)))<EPS*dist(p,q)?0:cross(sub(q,p),sub(r,p)));
  return sign(a,b,c)*sign(a,b,d)<=0 && sign(c,d,a)*sign(c,d,b)<=0;
}
function checkSimpleLoop(points) {
  const n=points.length;
  for(let i=0;i<n;i++){
    const a=points[i],b=points[(i+1)%n],c=points[(i+2)%n];
    check(dist(a,b)>EPS,'Coincident contour points');
    const incoming=unit(sub(a,b)),outgoing=unit(sub(c,b));
    check(Math.abs(cross(incoming,outgoing))>EPS || dot(incoming,outgoing)<0,'Contour doubles back on itself');
    for(let j=i+2;j<n;j++){
      if(i===0 && j===n-1) continue;
      check(!intersects(a,b,points[j],points[(j+1)%n]),'The contour crosses or touches itself');
    }
  }
}
export function validateGeometry(g) {
  check(g && typeof g==='object','Expected garden geometry');
  if(g.type!=='curve') checkPoint(g.center);
  if(g.type==='circle'||g.type==='arc') check(Number.isFinite(g.radius)&&g.radius>=MIN,'Radius must be at least 1 mm');
  switch(g.type){
    case 'point': check(Number.isFinite(g.yaw),'Point yaw must be finite'); break;
    case 'rectangle':
      check([g.width,g.depth].every(n=>Number.isFinite(n)&&n>=MIN),'Rectangle dimensions must be at least 1 mm');
      check(Number.isFinite(g.yaw),'Rectangle yaw must be finite'); break;
    case 'arc':
      check(Number.isFinite(g.startAngle) && Number.isFinite(g.sweepAngle) &&
        Math.abs(g.sweepAngle)>EPS && Math.abs(g.sweepAngle)<TAU,'An arc needs a nonzero sweep under one turn'); break;
    case 'circle': break;
    case 'curve': {
      check(typeof g.closed==='boolean' && Array.isArray(g.knots) &&
        g.knots.length>=(g.closed?3:2) && g.knots.length<=128,'Invalid curve knot count');
      for(const [i,k] of g.knots.entries()){
        check(k && ['smooth','corner'].includes(k.mode),'Unknown knot mode');
        for(const p of [k.p,k.in,k.out]) checkPoint(p);
        if(i>0 || g.closed) check(dist(k.p,g.knots[(i+g.knots.length-1)%g.knots.length].p)>=MIN,'Adjacent knots must be at least 1 mm apart');
        if(k.mode==='smooth' && (g.closed || (i>0 && i<g.knots.length-1))){
          const u=sub(k.in,k.p),v=sub(k.out,k.p);
          check((len(u)<=EPS && len(v)<=EPS) ||
            (len(u)>EPS && len(v)>EPS && dot(u,v)<0 && Math.abs(cross(unit(u),unit(v)))<.00001),'Smooth handles must share a tangent');
        }
      }
      if(g.closed){
        const box=bounds(g.knots.map(k=>k.p));
        const tol=Math.max(.000005,Math.min(.0005,Math.max(box.width,box.depth)*.0002));
        checkSimpleLoop(sampleGeometry(g,tol));
        check(measureGeometry(g).area>=MIN*MIN,'Contour encloses no measurable area');
      }
      break;
    }
    default: throw new RangeError('Unknown garden geometry');
  }
  return g;
}
export const circle = (center,radius) => validateGeometry({type:'circle',center:[...center],radius});
export const rectangle = (center,width,depth,yaw=0) => validateGeometry({type:'rectangle',center:[...center],width,depth,yaw});
export const arc = (center,radius,startAngle,sweepAngle) => validateGeometry({type:'arc',center:[...center],radius,startAngle,sweepAngle});
export const point = (center,yaw=0) => validateGeometry({type:'point',center:[...center],yaw});

function evenSamples(points,closed) {
  const path=closed?[...points,points[0]]:points;
  const distances=[0];
  for(let i=1;i<path.length;i++) distances.push(distances[i-1]+dist(path[i-1],path[i]));
  const length=distances.at(-1);
  const count=Math.max(24,Math.min(192,Math.ceil(length/.045)));
  const result=[];
  let j=1;
  for(let i=0;i<(closed?count:count+1);i++){
    const station=length*i/count;
    while(j<distances.length-1 && distances[j]<station) j++;
    result.push(lerp(path[j-1],path[j],(station-distances[j-1])/(distances[j]-distances[j-1])));
  }
  return result;
}
function circularFit(points,samples,closed,force) {
  // Mouse/controller event density is variable. Weight actual samples by the
  // adjoining lengths; fitting points interpolated on straight chords would
  // pull the circle inward, especially for a three-point arc.
  const weights=points.map((p,i)=>{
    const before=i>0?points[i-1]:(closed?points.at(-1):p);
    const after=i+1<points.length?points[i+1]:(closed?points[0]:p);
    return (dist(before,p)+dist(p,after))/2;
  });
  const weight=weights.reduce((sum,w)=>sum+w,0);
  const mean=mul(points.reduce((sum,p,i)=>add(sum,mul(p,weights[i])),[0,0]),1/weight);
  let xx=0,xz=0,zz=0,xr=0,zr=0;
  for(let i=0;i<points.length;i++){
    const [x,z]=sub(points[i],mean),rr=x*x+z*z,w=weights[i];
    xx+=w*x*x; xz+=w*x*z; zz+=w*z*z; xr+=w*x*rr; zr+=w*z*rr;
  }
  const det=xx*zz-xz*xz;
  if(det<(xx+zz)**2*1e-7) return null;
  const center=add(mean,[(xr*zz-zr*xz)/(2*det),(zr*xx-xr*xz)/(2*det)]);
  const radius=points.reduce((n,p,i)=>n+dist(p,center)*weights[i],0)/weight;
  if(radius<MIN) return null;
  const rays=samples.map(p=>sub(p,center));
  const errors=rays.map(r=>Math.abs(len(r)-radius)/radius);
  if(!force && (Math.hypot(...errors)/Math.sqrt(errors.length)>.042 || Math.max(...errors)>.105)) return null;
  let sweep=0,travel=0;
  for(let i=1;i<rays.length+(closed?1:0);i++){
    const a=rays[i-1],b=rays[i%rays.length],delta=Math.atan2(cross(a,b),dot(a,b));
    sweep+=delta; travel+=Math.abs(delta);
  }
  if(travel-Math.abs(sweep)>.24) return null;
  if(closed) return Math.abs(Math.abs(sweep)-TAU)<.18?circle(center,radius):null;
  if(Math.abs(sweep)>TAU-.20 && dist(points[0],points.at(-1))<radius*.18) return circle(center,radius);
  if(Math.abs(sweep)>=(force ? .02 : Math.PI/6) && Math.abs(sweep)<TAU-EPS) return arc(center,radius,bearing(rays[0]),sweep);
  return null;
}
function rectangleFit(points) {
  // A weighted fourfold direction averages the axes of both pairs of sides.
  const axis=[0,0];
  for(let i=0;i<points.length;i++){
    const d=sub(points[(i+1)%points.length],points[i]),v=mul(polar(4*bearing(d)),len(d));
    axis[0]+=v[0]; axis[1]+=v[1];
  }
  const yaw=bearing(axis)/4,local=points.map(p=>rotate(p,-yaw)),box=bounds(local);
  const short=Math.min(box.width,box.depth);
  if(short<MIN || Math.abs(polygonArea(local))<box.width*box.depth*.88) return null;
  const deviations=local.map(([x,z])=>Math.min(x-box.low[0],box.high[0]-x,z-box.low[1],box.high[1]-z));
  if(Math.max(...deviations)>short*.10 || deviations.reduce((a,b)=>a+b,0)/local.length>short*.035) return null;
  return rectangle(rotate(lerp(box.low,box.high,.5),yaw),box.width,box.depth,yaw);
}

function simplified(points,closed,tolerance){
  const path=closed?[...points,points[0]]:points;
  const ids=[0,path.length-1];
  // Split the largest departure first; the cap keeps jitter and long gestures editable.
  while(ids.length<(closed?13:12)){
    let best=tolerance,next=-1,after=-1;
    for(let i=0;i<ids.length-1;i++) for(let j=ids[i]+1;j<ids[i+1];j++){
      const error=segmentDistance(path[j],path[ids[i]],path[ids[i+1]]);
      if(error>best){best=error;next=j;after=i;}
    }
    if(next<0) break;
    ids.splice(after+1,0,next);
  }
  return closed?ids.slice(0,-1):ids;
}
function fromAnchors(anchors,closed,modes) {
  const knots=anchors.map((p,i)=>{
    const prev=anchors[(i+anchors.length-1)%anchors.length],next=anchors[(i+1)%anchors.length];
    if(modes[i]==='corner'){
      return {p:[...p],in:[...p],out:[...p],mode:'corner'};
    }
    const dir=unit(add(unit(sub(p,prev)),unit(sub(next,p))));
    return {p:[...p],in:sub(p,mul(dir,dist(p,prev)/3)),out:add(p,mul(dir,dist(p,next)/3)),mode:'smooth'};
  });
  return {type:'curve',closed,knots};
}
export function fitStroke(points,{closed=false,mode='auto'}={}) {
  check(Array.isArray(points) && typeof closed==='boolean' && ['auto','straight','curve','arc'].includes(mode),'Invalid stroke options');
  const clean=[];
  for(const p of points){
    checkPoint(p);
    if(!clean.length || dist(clean.at(-1),p)>=MIN) clean.push([...p]);
  }
  if(closed && clean.length>1 && dist(clean[0],clean.at(-1))<MIN) clean.pop();
  check(clean.length>=(closed?3:2),'Draw a longer stroke');
  const b=bounds(clean),span=Math.max(b.width,b.depth);
  check(span>=MIN,'Draw a longer stroke');
  const samples=evenSamples(clean,closed);
  if(closed) checkSimpleLoop(clean);
  if(mode==='arc'||mode==='auto'){
    const round=circularFit(clean,samples,closed,mode==='arc');
    if(round) return round;
    check(mode!=='arc','Draw a curved sweep for an arc');
  }
  if(closed && mode!=='curve'){
    const rect=rectangleFit(samples);
    if(rect) return rect;
  }
  const ids=simplified(clean,closed,Math.max(.012,span*(mode==='straight'?.018:.032)));
  check(!closed||ids.length>=3,'Contour encloses no measurable area');
  const anchors=ids.map(i=>clean[i]);
  const modes=ids.map((i,k)=>{
    if(mode==='straight' || (!closed && (k===0||k===ids.length-1))) return 'corner';
    const prev=clean[(i+clean.length-1)%clean.length],next=clean[(i+1)%clean.length];
    const bend=dot(unit(sub(clean[i],prev)),unit(sub(next,clean[i])));
    return mode==='auto' && bend<.65?'corner':'smooth';
  });
  return validateGeometry(fromAnchors(anchors,closed,modes));
}

/** Scale in rectangle-local axes; a single-axis diameter change scales a circle uniformly. */
export function transformGeometry(g,{offset=[0,0],angle=0,scale=[1,1],origin=centerOf(g)}={}) {
  checkPoint(offset); checkPoint(origin); checkPoint(scale);
  check(scale.every(n=>n>0)&&Number.isFinite(angle),'Transform needs a finite angle and positive scales');
  let [sx,sz]=scale;
  if(g.type==='circle'||g.type==='arc'){
    if(Math.abs(sx-sz)>EPS){
      if(Math.abs(sx-1)<EPS) sx=sz;
      else if(Math.abs(sz-1)<EPS) sz=sx;
      else throw new RangeError('Circular geometry needs the same scale on both axes');
    }
  }
  const axis=g.type==='rectangle'?g.yaw:0;
  const apply=p=>{
    const local=rotate(sub(p,origin),-axis);
    return add(add(origin,offset),rotate([local[0]*sx,local[1]*sz],axis+angle));
  };
  if(g.type==='curve'){
    return validateGeometry({...g,knots:g.knots.map(k=>({...k,p:apply(k.p),in:apply(k.in),out:apply(k.out)}))});
  }
  const out={...g,center:apply(g.center)};
  if(g.type==='circle'||g.type==='arc') out.radius*=sx;
  if(g.type==='arc') out.startAngle+=angle;
  if(g.type==='point'||g.type==='rectangle') out.yaw+=angle;
  if(g.type==='rectangle'){out.width*=sx;out.depth*=sz;}
  return validateGeometry(out);
}

export function handlesOf(g) {
  const handles=[{id:'center',kind:'move',point:centerOf(g)}];
  const handle=(id,p,kind)=>handles.push({id,kind,point:[...p]});
  if(g.type==='circle') handle('radius',atAngle(g,0),'radius');
  if(g.type==='rectangle'){
    corners(g).forEach((p,i)=>handle('corner:'+i,p,'corner'));
    handle('rotate',add(g.center,rotate([0,-g.depth/2-Math.max(.15,.12*g.depth)],g.yaw)),'rotate');
  }
  if(g.type==='arc'){
    handle('start',atAngle(g,g.startAngle),'endpoint');
    handle('end',atAngle(g,g.startAngle+g.sweepAngle),'endpoint');
    handle('radius',atAngle(g,g.startAngle+g.sweepAngle/2),'radius');
  }
  if(g.type==='point') handle('rotate',add(g.center,mul(polar(g.yaw),.4)),'rotate');
  if(g.type==='curve'){
    g.knots.forEach((k,i)=>{
      handle('knot:'+i,k.p,'knot');
      for(const field of ['in','out']){
        if((i>0 || g.closed || field==='out') && (i<g.knots.length-1 || g.closed || field==='in') && dist(k[field],k.p)>EPS){
          handle(field+':'+i,k[field],'tangent');
        }
      }
    });
  }
  return handles;
}

export function moveHandle(g,id,p) {
  checkPoint(p);
  if(id==='center') return transformGeometry(g,{offset:sub(p,centerOf(g))});
  if(id==='radius' && (g.type==='circle'||g.type==='arc')) return validateGeometry({...g,radius:dist(g.center,p)});
  if(id==='rotate' && (g.type==='point'||g.type==='rectangle')){
    check(dist(p,g.center)>=MIN,'Rotation handle needs a direction');
    return {...g,yaw:bearing(sub(p,g.center))+(g.type==='rectangle'?Math.PI/2:0)};
  }
  if(g.type==='rectangle'){
    const m=/^corner:([0-3])$/.exec(id); check(m,'Unknown rectangle handle');
    const index=Number(m[1]),opposite=corners(g)[(index+2)%4],delta=rotate(sub(p,opposite),-g.yaw);
    const xSign=[-1,1,1,-1][index],zSign=[-1,-1,1,1][index];
    return rectangle(lerp(opposite,p,.5),xSign*delta[0],zSign*delta[1],g.yaw);
  }
  if(g.type==='arc' && (id==='start'||id==='end')){
    check(dist(p,g.center)>=MIN,'Arc endpoint needs a direction');
    const t=bearing(sub(p,g.center)),sign=Math.sign(g.sweepAngle);
    const start=id==='start'?t:g.startAngle,end=id==='end'?t:g.startAngle+g.sweepAngle;
    return arc(g.center,g.radius,start,sign*mod(sign*(end-start)));
  }
  if(g.type==='curve'){
    const m=/^(knot|in|out):(\d+)$/.exec(id);
    check(m && Number(m[2])<g.knots.length,'Unknown curve handle');
    const index=Number(m[2]),field=m[1],original=g.knots[index];
    const knot={...original},knots=g.knots.slice();
    if(field==='knot'){
      const delta=sub(p,knot.p);
      knot.in=add(knot.in,delta);knot.out=add(knot.out,delta);knot.p=[...p];
    }else{
      knot[field]=[...p];
      if(knot.mode==='smooth'){
        const opposite=field==='in'?'out':'in',direction=sub(knot.p,p);
        const length=dist(original[opposite],knot.p) || len(direction);
        knot[opposite]=add(knot.p,mul(unit(direction),length));
      }
    }
    knots[index]=knot;
    return validateGeometry({...g,knots});
  }
  throw new RangeError('Unknown garden handle');
}
