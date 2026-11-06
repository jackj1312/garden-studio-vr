/** Metre-based proposal meshes. The host viewer owns the surveyed terrain and its cut mask. */
import { KINDS, MATERIALS, PATTERNS, PALETTES, SPECIES } from './catalogue.mjs';
import { isClosed, sampleGeometry } from './geometry.mjs';

const TAU = 2*Math.PI;
const plus=(a,b)=>[a[0]+b[0],a[1]+b[1]];
const minus=(a,b)=>[a[0]-b[0],a[1]-b[1]];
const times=(a,k)=>[a[0]*k,a[1]*k];
const mix=(a,b,t)=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t];
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1];
const cross=(a,b)=>a[0]*b[1]-a[1]*b[0];
const along=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const unit=v=>times(v,1/(Math.hypot(...v)||1));
const left=v=>[-v[1],v[0]];
const xyz=(p,y)=>[p[0],y,p[1]];
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const wrap=(s,n)=>((s%n)+n)%n;

function signedArea(p) {
  let area=0;
  for(let i=0;i<p.length;i++) area+=cross(p[i],p[(i+1)%p.length]);
  return area/2;
}
function inside(p,polygon) {
  let within=false;
  for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){
    const a=polygon[i],b=polygon[j];
    if((a[1]>p[1])!==(b[1]>p[1]) && p[0]<a[0]+(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])) within=!within;
  }
  return within;
}
function nearLine(p,points,closed) {
  let nearest=Infinity;
  for(let i=0;i<points.length-(closed?0:1);i++){
    const a=points[i],b=points[(i+1)%points.length],v=minus(b,a);
    const t=clamp(dot(minus(p,a),v)/(dot(v,v)||1),0,1);
    nearest=Math.min(nearest,along(p,mix(a,b,t)));
  }
  return nearest;
}
function pathInfo(points,closed){
  const stations=[0];
  for(let i=0;i<points.length-(closed?0:1);i++) stations.push(stations.at(-1)+along(points[i],points[(i+1)%points.length]));
  const total=stations.at(-1);
  function section(s){
    s=closed?wrap(s,total):clamp(s,0,total);
    let i=0;while(i<stations.length-2 && stations[i+1]<s) i++;
    const j=(i+1)%points.length,t=clamp((s-stations[i])/(stations[i+1]-stations[i]||1),0,1);
    return {i,j,t,p:mix(points[i],points[j],t),dir:unit(minus(points[j],points[i]))};
  }
  return {points,closed,stations,total,section};
}
function offsetLine(points,closed,distance){
  return points.map((p,i)=>{
    const prev=points[(i+points.length-1)%points.length],next=points[(i+1)%points.length];
    const a=left(unit(minus(p,prev))),b=left(unit(minus(next,p)));
    if(!closed && i===0)return plus(p,times(b,distance));
    if(!closed && i===points.length-1)return plus(p,times(a,distance));
    const m=unit(plus(a,b));
    return plus(p,times(m,distance/Math.max(.34,dot(m,b))));
  });
}
function stripSections(info,outer,inner,start=0,end=info.total){
  const cuts=[start,...info.stations.filter(v=>v>start+1e-7&&v<end-1e-7),end];
  return cuts.slice(0,-1).map((s,i)=>{
    const mid=info.section((s+cuts[i+1])/2),lo=info.stations[mid.i],hi=info.stations[mid.i+1];
    const t=clamp((s-lo)/(hi-lo||1),0,1),u=clamp((cuts[i+1]-lo)/(hi-lo||1),0,1);
    return [mix(outer[mid.i],outer[mid.j],t),mix(outer[mid.i],outer[mid.j],u),
            mix(inner[mid.i],inner[mid.j],u),mix(inner[mid.i],inner[mid.j],t)];
  });
}
function seedFrom(text) {
  let hash=2166136261;
  for(const c of text){hash^=c.charCodeAt(0);hash=Math.imul(hash,16777619);}
  return hash>>>0;
}
function randomFrom(seed) {
  let x=seed;
  return ()=>{x=(Math.imul(1664525,x)+1013904223)>>>0;return x/4294967296;};
}
function rgb(hex) {
  const n=parseInt(hex.slice(1),16);
  return [(n>>16)&255,(n>>8)&255,n&255];
}

function makeSwatch(T,materialName,patternName,paletteName) {
  const mat=MATERIALS[materialName]||MATERIALS.stone,pat=PATTERNS[patternName]||PATTERNS.plain;
  const colors=(PALETTES[paletteName]||PALETTES.natural).colors.map(rgb),base=rgb(mat.color);
  const pattern=PATTERNS[patternName]?patternName:'plain',size=192;
  const module=pat.unit,width=pattern==='plain'?mat.scale:4*module[0],depth=pattern==='plain'?mat.scale:4*module[1];
  const pixels=new Uint8Array(size*size*4),rng=randomFrom(seedFrom(materialName+pattern+paletteName));
  const stone=['concrete','paving','limestone','slate','stone','brick','gravel'].includes(materialName);
  const wood=['sleepers','decking'].includes(materialName);
  for(let j=0;j<size;j++) for(let i=0;i<size;i++){
    const x=(i+.5)*width/size,z=(j+.5)*depth/size;
    const u=pattern==='herringbone'||pattern==='basketweave'?module[1]:module[0],v=module[1];
    let row=Math.floor(z/v),col=Math.floor(x/u),fx=wrap(x,u),fz=wrap(z,v);
    let joint=Infinity;
    if(pattern==='running-bond'||pattern==='laid-flags'||pattern==='planks'||pattern==='courses'){
      const shifted=x+((row%2)*u/2);
      fx=wrap(shifted,u);col=Math.floor(shifted/u);
      joint=Math.min(fx,u-fx,fz,v-fz);
    }else if(pattern==='grid') joint=Math.min(fx,u-fx,fz,v-fz);
    else if(pattern==='herringbone'||pattern==='basketweave'){
      let vertical,localLong;
      if(pattern==='herringbone'){
        const parity=wrap(col+row,4);
        vertical=parity>=2;
        localLong=vertical ? (parity===3?v:0)+fz : (parity===1?u:0)+fx;
        if(parity===1)col--;if(parity===3)row--;
      }else{
        vertical=(Math.floor(col/2)+Math.floor(row/2))%2===1;
        localLong=vertical?(row%2)*v+fz:(col%2)*u+fx;
        if(vertical)row-=row%2;else col-=col%2;
      }
      const short=vertical?fx:fz;
      joint=Math.min(short,u-short,localLong,2*u-localLong);
    }
    const color=colors[wrap(col*17+row*31,colors.length)];
    const seam=Number.isFinite(joint)?clamp((.0035+Math.max(width,depth)/size*.5-joint)*size/Math.max(width,depth),0,1):0;
    let detail=(rng()-.5)*(stone?19:11);
    if(wood)detail+=5*Math.sin((z/v+Math.sin(x*4)*.035)*42)+2*Math.sin(z*265);
    if(materialName==='lawn')detail+=4*Math.sin(z/mat.scale*TAU);
    if(materialName==='soil'||materialName==='gravel')detail+=9*Math.sin(i*.61+j*.31)*Math.cos(i*.37-j*.72);
    const k=(j*size+i)*4;
    for(let c=0;c<3;c++){
      const tint=['lawn','soil','foliage','steel'].includes(materialName)?.12:.32;
      pixels[k+c]=clamp((base[c]*(1-tint)+color[c]*tint+detail)*(1-seam*.48),0,255);
    }
    pixels[k+3]=255;
  }
  const map=new T.DataTexture(pixels,size,size,T.RGBAFormat);
  map.wrapS=map.wrapT=T.RepeatWrapping;map.repeat.set(1/width,1/depth);
  if(pattern==='herringbone')map.rotation=Math.PI/4;
  map.colorSpace=T.SRGBColorSpace;map.generateMipmaps=true;map.magFilter=T.LinearFilter;
  map.minFilter=T.LinearMipmapLinearFilter;map.anisotropy=4;map.needsUpdate=true;
  const material=new T.MeshStandardMaterial({map,roughness:mat.roughness,metalness:materialName==='steel'?.48:0,side:T.DoubleSide});
  material.polygonOffset=true;material.polygonOffsetFactor=-1;material.polygonOffsetUnits=-1;
  material.name='Garden '+mat.label+' · '+pat.label;
  return material;
}

// Batches one material's polygons into one mesh; positions and UVs are in metres.
class Batch {
  constructor(T){this.T=T;this.positions=[];this.uvs=[];this.colors=[];}
  tri(a,b,c,uv,color){
    this.positions.push(...a,...b,...c);
    this.uvs.push(...(uv||[a[0],a[2],b[0],b[2],c[0],c[2]]));
    if(color)this.colors.push(...color,...color,...color);
  }
  top(poly,y,upward=true){
    if(poly.length<3)return;
    const ts=this.T.ShapeUtils.triangulateShape(poly.map(p=>new this.T.Vector2(...p)),[]);
    for(const ids of ts){
      const [a,b,c]=ids.map(i=>poly[i]);
      if((cross(minus(b,a),minus(c,a))>0)===upward)this.tri(xyz(a,y),xyz(c,y),xyz(b,y));
      else this.tri(xyz(a,y),xyz(b,y),xyz(c,y));
    }
  }
  sides(poly,low,high,skip=new Set()){
    if(high-low<.0001)return;
    const ccw=signedArea(poly)>0;
    let station=0;
    for(let i=0;i<poly.length;i++){
      const a=poly[i],b=poly[(i+1)%poly.length],end=station+along(a,b);
      if(!skip.has(i)){
        const side=[[...xyz(a,low)],[...xyz(a,high)],[...xyz(b,high)],[...xyz(b,low)]];
        const uv=[[station,low],[station,high],[end,high],[end,low]];
        for(const f of (ccw?[[0,1,2],[0,2,3]]:[[0,2,1],[0,3,2]])){
          this.tri(...f.map(k=>side[k]),f.flatMap(k=>uv[k]));
        }
      }
      station=end;
    }
  }
  solid(poly,low,high,skip){
    this.top(poly,high);
    this.sides(poly,low,high,skip);
  }
  mesh(material,name,group,block=false){
    if(!this.positions.length)return null;
    const T=this.T,geo=new T.BufferGeometry();
    geo.setAttribute('position',new T.Float32BufferAttribute(this.positions,3));
    geo.setAttribute('uv',new T.Float32BufferAttribute(this.uvs,2));
    if(this.colors.length)geo.setAttribute('color',new T.Float32BufferAttribute(this.colors,3));
    geo.computeVertexNormals();geo.computeBoundingSphere();
    const mesh=new T.Mesh(geo,material);
    mesh.name=name;mesh.castShadow=true;mesh.receiveShadow=true;
    mesh.userData.gardenFeatureId=group.userData.gardenFeatureId;mesh.userData.gardenBarrier=block;
    group.add(mesh);return mesh;
  }
}

function placeRing(batch,info,outer,inner,low,high,gate,withTop=true) {
  const interval=gate?gate.width/2:0;
  for(let i=0;i<info.stations.length-1;i++){
    const lo=info.stations[i],hi=info.stations[i+1];
    const cuts=[lo,hi];
    if(gate)for(const q of [gate.at-interval,gate.at+interval]){
      const s=wrap(q,info.total);if(s>lo && s<hi)cuts.push(s);
    }
    cuts.sort((a,b)=>a-b);
    for(let k=0;k<cuts.length-1;k++){
      const a=cuts[k],b=cuts[k+1],mid=(a+b)/2;
      const fromGate=gate?Math.abs(wrap(mid-gate.at+info.total/2,info.total)-info.total/2):Infinity;
      if(fromGate<interval)continue;
      const t=(a-lo)/(hi-lo),u=(b-lo)/(hi-lo),j=(i+1)%outer.length;
      const poly=[mix(outer[i],outer[j],t),mix(outer[i],outer[j],u),mix(inner[i],inner[j],u),mix(inner[i],inner[j],t)];
      const hidden=new Set([1,3]); // adjoining ring sections have a shared cross-section
      if(gate && Math.abs(fromGate-interval)<(b-a)/2+.000001){
        if(Math.abs(wrap(a-gate.at+info.total/2,info.total)-info.total/2)<=interval+.000001)hidden.delete(3);
        if(Math.abs(wrap(b-gate.at+info.total/2,info.total)-info.total/2)<=interval+.000001)hidden.delete(1);
      }
      if(withTop)batch.top(poly,high);
      batch.sides(poly,low,high,hidden);
    }
  }
}

function randColor(T,hex,amount,rng){
  const c=new T.Color(hex);c.multiplyScalar(1+amount*(rng()-.5));return [c.r,c.g,c.b];
}
function stem(batch,a,b,r0,r1,color,sides=7){
  const T=batch.T,A=new T.Vector3(...a),B=new T.Vector3(...b),dir=B.clone().sub(A).normalize();
  if(!dir.lengthSq())return;
  const u=new T.Vector3().crossVectors(dir,Math.abs(dir.y)>.85?new T.Vector3(1,0,0):new T.Vector3(0,1,0)).normalize();
  const v=new T.Vector3().crossVectors(dir,u),bottom=[],top=[];
  for(let i=0;i<sides;i++){
    const t=TAU*i/sides,off=u.clone().multiplyScalar(Math.cos(t)).addScaledVector(v,Math.sin(t));
    bottom.push(A.clone().addScaledVector(off,r0).toArray());top.push(B.clone().addScaledVector(off,r1).toArray());
  }
  for(let i=0;i<sides;i++){
    const j=(i+1)%sides;
    batch.tri(bottom[i],bottom[j],top[j],null,color);
    batch.tri(bottom[i],top[j],top[i],null,color);
    batch.tri(b,top[i],top[j],null,color);
  }
}
function leaf(batch,p,angle,length,width,rise,color){
  const dx=Math.cos(angle),dz=Math.sin(angle),mid=[p[0]+dx*length*.47,p[1]+rise*.57+width*.06,p[2]+dz*length*.47];
  const l=[mid[0]-dz*width/2,mid[1]-width*.18,mid[2]+dx*width/2];
  const r=[mid[0]+dz*width/2,mid[1]-width*.18,mid[2]-dx*width/2];
  const tip=[p[0]+length*dx,p[1]+rise,p[2]+length*dz];
  for(const [a,b,c] of [[p,mid,l],[p,r,mid],[l,mid,tip],[mid,r,tip]])batch.tri(a,b,c,null,color);
}
function bud(batch,p,r,color){
  const a=[p[0],p[1]+r,p[2]],b=[p[0],p[1]-r,p[2]];
  for(let i=0;i<6;i++){
    const l=TAU*i/6,h=TAU*(i+1)/6;
    const c=[p[0]+r*Math.cos(l),p[1],p[2]+r*Math.sin(l)],d=[p[0]+r*Math.cos(h),p[1],p[2]+r*Math.sin(h)];
    batch.tri(a,d,c,null,color);batch.tri(b,c,d,null,color);
  }
}
function specimen(batch,species,seed,width,height,center,yaw){
  const T=batch.T,rng=randomFrom(seed),s=SPECIES[species]||SPECIES.lavender;
  const first=batch.positions.length,green=()=>randColor(T,s.color,.36,rng),flower=()=>randColor(T,s.accent||s.color,.18,rng);
  const bark=randColor(T,species==='birch'?'#ccc4aa':'#716349',.18,rng);
  if(s.kind==='tree'){
    const h=1,slim=s.habit==='upright',trunkBase=.024;
    const crotch=[.03,.39,0];stem(batch,[0,0,0],crotch,trunkBase,.016,bark);
    for(let branch=0;branch<15;branch++){
      const angle=branch*2.399+rng()*.37,level=branch/15;
      const start=[crotch[0]*(1-level),.30+level*.45,0];
      const radius=(.26+.14*rng())*(1-.48*level)*(slim?.7:1);
      const end=[Math.cos(angle)*radius,Math.min(h-.09,start[1]+.13+rng()*.17),Math.sin(angle)*radius];
      const elbow=[(start[0]+end[0])*.5,start[1]+.09,(start[2]+end[2])*.42];
      stem(batch,start,elbow,.014*(1-level*.45),.008,bark);
      stem(batch,elbow,end,.008,.003,bark);
      // A lateral spur, rather than a single spherical canopy, carries each spray.
      for(let j=0;j<7;j++){
        const az=angle+(rng()-.5)*2.9,length=.08+rng()*.12;
        const tip=[end[0]+Math.cos(az)*length,end[1]+.03+rng()*.07,end[2]+Math.sin(az)*length];
        stem(batch,end,tip,.0035,.0015,bark,4);
        for(let k=1;k<=5;k++){
          const t=k/6,base=tip.map((v,i)=>end[i]+(v-end[i])*t);
          leaf(batch,base,az+(k%2?1.15:-1.15),.05+rng()*.055,species==='maple'?.068:.046,(rng()-.35)*.05,green());
        }
        if((species==='apple'||species==='rowan') && j%4===0)bud(batch,[tip[0],tip[1]-.018,tip[2]],species==='apple'?.014:.008,randColor(T,species==='apple'?'#ac7251':'#af6248',.25,rng));
      }
    }
    stem(batch,crotch,[.004,.75,0],.016,.009,bark);
    stem(batch,[.004,.75,0],[.04,.94,0],.009,.0015,bark);
  }else if(species==='fern'){
    for(let i=0;i<11;i++){
      const a=TAU*i/11+rng()*.25,L=.28+rng()*.24,h=.25+rng()*.35;
      let prev=[0,0,0];
      for(let j=1;j<=9;j++){
        const f=j/9,mid=[Math.cos(a)*L*f,Math.sin(f*Math.PI*.74)*h,Math.sin(a)*L*f];
        stem(batch,prev,mid,.004*(1.05-f),.002,green(),4);prev=mid;
        const l=(.06+.095*Math.sin(Math.PI*f))*(1-f*.42);
        for(const side of [-1,1])leaf(batch,mid,a+side*1.1,l,l*.26,.016,green());
      }
    }
  }else if(species==='grass'||species==='lavender'){
    for(let i=0;i<(species==='grass'?76:55);i++){
      const a=rng()*TAU,h=.36+rng()*.61,reach=.12+rng()*.40;
      const p=[(rng()-.5)*.12,0,(rng()-.5)*.12],mid=[p[0]+Math.cos(a)*reach*.33,h*.68,p[2]+Math.sin(a)*reach*.33];
      const tip=[p[0]+Math.cos(a)*reach,h,p[2]+Math.sin(a)*reach];
      if(species==='grass'){
        const w=.008+rng()*.013,l=[mid[0]+Math.sin(a)*w,mid[1],mid[2]-Math.cos(a)*w];
        batch.tri(p,mid,l,null,green());batch.tri(mid,tip,l,null,green());
        if(i%5===0)leaf(batch,tip,a,.045,.017,.11,flower());
      }else{
        stem(batch,p,mid,.004,.0025,green(),4);stem(batch,mid,tip,.0025,.0018,green(),4);
        leaf(batch,mid,a+1.2,.065,.017,.055,green());
        for(let j=0;j<4;j++)bud(batch,[tip[0],tip[1]+.018*j,tip[2]],.013-j*.0013,flower());
      }
    }
  }else{
    for(let i=0;i<22;i++){
      const a=i*2.399,reach=.16+rng()*.24,h=.42+rng()*.32,tip=[reach*Math.cos(a),h,reach*Math.sin(a)];
      stem(batch,[0,0,0],tip,.009,.003,bark,5);
      for(let j=2;j<7;j++){
        const p=tip.map(n=>n*j/7);
        leaf(batch,p,a+(j%2?1.6:-1.6),.14,.083,.033,green());
      }
      for(let j=0;j<13;j++){
        const az=j*2.399,r=.081*Math.sqrt(j/13);
        bud(batch,[tip[0]+Math.cos(az)*r,tip[1]+.04*(1-r/.081),tip[2]+Math.sin(az)*r],.033,flower());
      }
    }
  }
  let radius=0,low=Infinity,high=-Infinity;
  for(let i=first;i<batch.positions.length;i+=3){
    radius=Math.max(radius,Math.hypot(batch.positions[i],batch.positions[i+2]));
    low=Math.min(low,batch.positions[i+1]);high=Math.max(high,batch.positions[i+1]);
  }
  for(let i=first;i<batch.positions.length;i+=3){
    const x=batch.positions[i]*width/(2*radius),z=batch.positions[i+2]*width/(2*radius);
    batch.positions[i]=center[0]+x*Math.cos(yaw)-z*Math.sin(yaw);
    batch.positions[i+1]=center[1]+(batch.positions[i+1]-low)*height/(high-low);
    batch.positions[i+2]=center[2]+x*Math.sin(yaw)+z*Math.cos(yaw);
  }
}

function boxOnLine(center,dir,length,width){
  const u=times(dir,length/2),n=times(left(dir),width/2);
  return [minus(minus(center,u),n),minus(plus(center,u),n),plus(plus(center,u),n),plus(minus(center,u),n)];
}
function bounds2(points){
  let x=Infinity,z=Infinity,X=-Infinity,Z=-Infinity;
  for(const p of points){x=Math.min(x,p[0]);X=Math.max(X,p[0]);z=Math.min(z,p[1]);Z=Math.max(Z,p[1]);}
  return {x,z,X,Z};
}
function fillBed(batch,f,poly,y){
  const box=bounds2(poly),area=Math.abs(signedArea(poly)),rng=randomFrom(seedFrom(f.id));
  const accepted=[],count=Math.min(28,Math.round(area*1.8));
  const kinds=f.species&&SPECIES[f.species]?.kind==='plant'?[f.species]:['lavender','grass','fern','hydrangea'];
  for(let i=0;i<count*12 && accepted.length<count;i++){
    const p=[box.x+rng()*(box.X-box.x),box.z+rng()*(box.Z-box.z)];
    if(!inside(p,poly) || nearLine(p,poly,true)<.10 || accepted.some(q=>along(q,p)<.37))continue;
    accepted.push(p);
    const key=kinds[Math.floor(rng()*kinds.length)],s=SPECIES[key],k=.49+rng()*.30;
    specimen(batch,key,Math.floor(rng()*0xffffffff),s.width*k,s.height*k,[p[0],y,p[1]],rng()*TAU);
  }
}
// The footprint can be nonconvex. Clip each tread into the triangulated area
// so even a curved edge or tight corner never puts a step on retained paving.
function clipConvex(poly,triangle){
  const orientation=Math.sign(signedArea(triangle));
  for(let i=0;i<3;i++){
    const a=triangle[i],b=triangle[(i+1)%3],edge=minus(b,a),next=[];
    for(let j=0;j<poly.length;j++){
      const p=poly[j],q=poly[(j+1)%poly.length];
      const u=orientation*cross(edge,minus(p,a)),v=orientation*cross(edge,minus(q,a));
      if(u>=-1e-9)next.push(p);
      if((u<0)!==(v<0) && Math.abs(u-v)>1e-12)next.push(mix(p,q,u/(u-v)));
    }
    poly=next;
  }
  return poly;
}
function depthInside(p,dir,poly){
  let end=Infinity;
  for(let i=0;i<poly.length;i++){
    const a=poly[i],edge=minus(poly[(i+1)%poly.length],a),delta=minus(a,p),den=cross(dir,edge);
    if(Math.abs(den)<1e-9)continue;
    const t=cross(delta,edge)/den,u=cross(delta,dir)/den;
    if(t>.001 && u>=0 && u<=1)end=Math.min(end,t);
  }
  return end;
}
function gateFor(f,info) {
  if(!f.steps || Math.abs(f.level)<.001)return null;
  let at=info.total*clamp(f.steps.at,0,1);if(at>=info.total)at=0;
  let part=info.section(at),width=Math.min(f.steps.width,info.total*.30);
  const a=info.stations[part.i],b=info.stations[part.i+1];
  if(b-a>width+.02){
    at=clamp(at,a+width/2,b-width/2);part=info.section(at);
  }
  const inner=times(left(part.dir),Math.sign(signedArea(info.points)));
  return {at,width,center:part.p,tangent:part.dir,inner};
}
function insideSegments(a,b,poly){
  const dir=minus(b,a),stations=[0,1];
  for(let i=0;i<poly.length;i++){
    const c=poly[i],d=poly[(i+1)%poly.length],edge=minus(d,c),den=cross(dir,edge);
    if(Math.abs(den)<1e-10)continue;
    const delta=minus(c,a),t=cross(delta,edge)/den,u=cross(delta,dir)/den;
    if(t>0 && t<1 && u>=0 && u<=1)stations.push(t);
  }
  stations.sort((a,b)=>a-b);
  const pieces=[];
  for(let i=1;i<stations.length;i++){
    const lo=stations[i-1],hi=stations[i],mid=mix(a,b,(hi+lo)/2);
    if(hi-lo>1e-8 && (inside(mid,poly)||nearLine(mid,poly,true)<1e-7)){
      pieces.push([mix(a,b,lo),mix(a,b,hi)]);
    }
  }
  return pieces;
}
function upright(batch,p,q,low,high,clip){
  const pieces=clip?insideSegments(p,q,clip):[[p,q]];
  for(const [a,b] of pieces){
    const u=along(a,b);
    batch.tri(xyz(a,low),xyz(b,low),xyz(b,high),[0,low,u,low,u,high]);
    batch.tri(xyz(a,low),xyz(b,high),xyz(a,high),[0,low,u,high,0,high]);
  }
}
function gateEdges(info,gate){
  const breaks=[0,...info.stations.slice(1,-1),info.total,
                wrap(gate.at-gate.width/2,info.total),wrap(gate.at+gate.width/2,info.total)].sort((a,b)=>a-b);
  const edges=[];
  for(let i=0;i<breaks.length-1;i++){
    const a=breaks[i],b=breaks[i+1],dist=wrap((a+b)/2-gate.at+info.total/2,info.total)-info.total/2;
    if(b-a>1e-8 && Math.abs(dist)<gate.width/2)edges.push([info.section(a).p,info.section(b).p]);
  }
  return edges;
}
function attachedSteps(batch,entry,info,gate,base,floor){
  if(!gate)return;
  const count=entry.feature.steps.count,delta=floor-base,up=delta>0;
  const available=up?Infinity:depthInside(plus(gate.center,times(gate.inner,.0001)),gate.inner,info.points);
  const going=Math.min(.29,available*.85/Math.max(1,count-1));
  const triangles=batch.T.ShapeUtils.triangulateShape(info.points.map(p=>new batch.T.Vector2(...p)),[])
                    .map(ids=>ids.map(i=>info.points[i]));
  const pointAt=(depth,u)=>plus(plus(gate.center,times(gate.inner,depth)),times(gate.tangent,u));
  const mouth=up?[]:gateEdges(info,gate);
  for(let i=0;i<count-1;i++){
    const a=up?-(count-1-i)*going:i*going,b=a+going;
    const poly=[pointAt(a,-gate.width/2),pointAt(a,gate.width/2),pointAt(b,gate.width/2),pointAt(b,-gate.width/2)];
    const top=base+(i+1)*delta/count;
    const pieces=up?[poly]:triangles.map(tri=>clipConvex(poly,tri)).filter(v=>v.length>=3&&Math.abs(signedArea(v))>1e-8);
    for(const piece of pieces){batch.top(piece,top);entry.treads.push({poly:piece,y:top});}
    // Only the pieces inside the actual cut may have below-grade cheeks.
    for(const side of [-1,1]){
      const p=pointAt(a,side*gate.width/2),q=pointAt(b,side*gate.width/2);
      upright(batch,p,q,up?base:floor,top,up?null:info.points);
    }
    // A curved excavation has a curved mouth. Its first visible riser follows
    // that perimeter, rather than a tangent chord outside the excavation.
    for(const [p,q] of mouth)upright(batch,p,q,top,base,poly);
  }
  for(let i=0;i<count;i++){
    if(!up && i===0)continue;
    const at=up?-(count-1-i)*going:i*going,from=base+i*delta/count,to=base+(i+1)*delta/count;
    upright(batch,pointAt(at,-gate.width/2),pointAt(at,gate.width/2),from,to,up?null:info.points);
  }
  if(!up && count===1)for(const [p,q] of mouth)upright(batch,p,q,floor,base);

}

function slabObject({T,material},e){
  const f=e.feature,top=f.baseY+f.level,bottom=top-f.height;
  if(!Number.isFinite(bottom) || f.height<=0)throw new RangeError('A concrete base needs positive thickness');
  const block=new Batch(T);
  block.top(e.points,top);
  block.top(e.points,bottom,false);
  block.sides(e.points,bottom,top);
  const mesh=block.mesh(material(f.material,f.pattern,f.palette),'Concrete outbuilding base',e.group,true);
  mesh.userData.gardenSupport=true;
  e.floor=top;e.outlineY=top;
  if(top<f.baseY)e.cuts.push({id:f.id,points:e.points,baseY:f.baseY});
}
function areaObject(state,e) {
  const f=e.feature,p=e.points,info=pathInfo(p,true),base=f.baseY,surface=base+f.level;
  const {T,material,vegetation}=state;
  const top=new Batch(T),sides=new Batch(T),cap=new Batch(T),stairs=new Batch(T),plants=new Batch(T);
  const isBed=f.kind==='raised-bed',isPit=f.kind==='fire-pit',isSunken=f.level<0;
  const framed=isBed||isPit||isSunken,box=bounds2(p);
  const width=clamp(f.width||.075,.012,Math.max(.012,Math.min(box.X-box.x,box.Z-box.z)*.24));
  const inner=framed?offsetLine(p,true,Math.sign(signedArea(p))*width):p;
  const upper=isBed||isPit?surface+f.height:base;
  const innerY=isBed?Math.max(surface,upper-.045):surface;
  e.floor=innerY;e.cap=framed?{inner,y:upper}:null;
  const gate=gateFor(f,info);e.gate=gate;e.rimWidth=width;
  top.top(framed?inner:p,innerY);
  // Extend to the mouth of a flight: the floor continues below the lowest tread.
  if(gate && framed){
    for(const q of stripSections(info,p,inner))top.top(q,surface);
  }
  if(framed){
    const low=Math.min(surface,base),capHeight=f.coping?Math.min(.04,Math.max(0,upper-low)/3):0;
    placeRing(sides,info,p,inner,low,upper-capHeight,gate,capHeight===0);
    if(capHeight>0)placeRing(cap,info,p,inner,upper-capHeight,upper,gate);
  }else if(surface>base){
    const below=offsetLine(p,true,Math.sign(signedArea(p))*.001);
    // The raised walk surface has a vertical fascia, open where stairs meet it.
    placeRing(sides,info,p,below,base,surface,gate,false);
  }
  attachedSteps(stairs,e,info,gate,base,surface);
  if(isBed||f.kind==='planting-bed') fillBed(plants,f,inner,innerY);
  if(isPit){
    const c=e.center,r=Math.min(box.X-box.x,box.Z-box.z)*.25,wood=randColor(T,'#514334',.1,()=>.5);
    for(let i=0;i<4;i++){
      const a=i*1.56,p1=[c[0]-r*.67*Math.cos(a),surface+.045,c[1]-r*.67*Math.sin(a)];
      const p2=[c[0]+r*.70*Math.cos(a),surface+.10+i*.012,c[1]+r*.70*Math.sin(a)];
      stem(plants,p1,p2,Math.min(.052,r*.15),Math.min(.039,r*.12),wood);
    }
  }
  const floorMat=isBed?'soil':isPit?'steel':f.material;
  const floorMesh=top.mesh(material(floorMat,isBed||isPit?'plain':f.pattern,f.palette),'Walking surface',e.group);
  if(floorMesh)floorMesh.userData.gardenSupport=true;
  const returns=sides.mesh(material(f.material,f.pattern,f.palette),'Retaining faces',e.group,true);
  if(returns)returns.userData.gardenSupport=true;
  const coping=cap.mesh(material(f.coping||f.material,'plain',f.palette),'Coping',e.group,true);
  if(coping)coping.userData.gardenSupport=true;
  const access=stairs.mesh(material(f.material,f.pattern,f.palette),'Access treads and risers',e.group,true);
  if(access)access.userData.gardenSupport=true;
  plants.mesh(vegetation,'Planting and dressing',e.group);
  if(isSunken)e.cuts.push({id:f.id,points:p,baseY:base});
  e.outlineY=framed?upper:surface;
}

function lineObject(state,e) {
  const {T,material}=state,f=e.feature,info=pathInfo(e.points,e.closed);
  const base=f.baseY,low=base+f.level,w=Math.max(.015,f.width);
  const a=offsetLine(e.points,e.closed,w/2),b=offsetLine(e.points,e.closed,-w/2);
  const polys=stripSections(info,a,b),body=new Batch(T),cap=new Batch(T),isPath=f.kind==='path';
  e.lineWidth=w;
  if(f.kind==='fence'){
    const h=Math.max(.02,f.height),post=Math.min(.12,w);
    const spans=Math.max(1,Math.ceil(info.total/1.8));
    for(let i=0;i<spans+(e.closed?0:1);i++){
      const q=info.section(info.total*i/spans);
      body.solid(boxOnLine(q.p,q.dir,post,post),low,low+h);
    }
    // Closed boards have small light gaps; two rails are set back behind them.
    const boards=Math.max(1,Math.ceil(info.total/.135));
    for(let i=0;i<boards;i++){
      const q=info.section((i+.5)*info.total/boards);
      body.solid(boxOnLine(plus(q.p,times(left(q.dir),-.025)),q.dir,Math.max(.008,info.total/boards-.008),.022),low+.04,low+h-.045);
    }
    const rear=offsetLine(e.points,e.closed,.011),far=offsetLine(e.points,e.closed,.044);
    for(const height of [.24,.76])for(const q of stripSections(info,rear,far)){
      body.solid(q,low+h*height,low+h*height+.048,new Set([1,3]));
    }
  }else if(f.kind==='steps'){
    const count=f.steps?.count||Math.max(1,Math.ceil(f.height/.16));
    for(let i=0;i<count;i++){
      const start=info.total*i/count,end=info.total*(i+1)/count,top=low+(i+1)*f.height/count;
      for(const poly of stripSections(info,a,b,start,end)){
        body.top(poly,top);body.sides(poly,low,top,new Set([1,3]));
        e.treads.push({poly,y:top});
      }
      const s=info.section(start),p=mix(a[s.i],a[s.j],s.t),q=mix(b[s.i],b[s.j],s.t);
      const z0=top-f.height/count;
      body.tri(xyz(p,z0),xyz(q,z0),xyz(q,top));body.tri(xyz(p,z0),xyz(q,top),xyz(p,top));
    }
    if(!e.closed){
      const p=a.at(-1),q=b.at(-1),top=low+f.height;
      body.tri(xyz(q,low),xyz(p,low),xyz(p,top));body.tri(xyz(q,low),xyz(p,top),xyz(q,top));
    }
  }else{
    const high=isPath?low:low+Math.max(.006,f.height);
    const lower=isPath?Math.min(base,low-.025):Math.min(base,low);
    const capH=!isPath && f.coping?Math.min(.04,(high-lower)/3):0;
    for(const [i,poly] of polys.entries()){
      const edges=new Set([1,3]);
      if(!e.closed && i===0)edges.delete(3);
      if(!e.closed && i===polys.length-1)edges.delete(1);
      if(!capH)body.top(poly,high);
      body.sides(poly,lower,high-capH,edges);
      if(capH)cap.solid(poly,high-capH,high,edges);
    }
    if(isPath){
      e.treads.push(...polys.map(poly=>({poly,y:low})));
      // Include vertical sides of an excavated path up to retained grade.
      if(low<base)for(const poly of polys)body.sides(poly,low,base,new Set([1,3]));
    }
  }
  const mesh=body.mesh(material(f.material,f.pattern,f.palette),f.kind==='steps'?'Step flight':f.label,e.group,!isPath);
  if(mesh && (isPath || f.kind==='steps'))mesh.userData.gardenSupport=true;
  cap.mesh(material(f.coping||f.material,'plain',f.palette),'Wall coping',e.group,true);
  if(low<base){
    if(e.closed)for(const p of polys)e.cuts.push({id:f.id,points:p,baseY:base});
    else e.cuts.push({id:f.id,points:[...a,...b.slice().reverse()],baseY:base});
  }
  e.outlineY=low+(isPath?0:f.height);
}

export function createGardenScene(THREE, scene){
  const T=THREE,root=new T.Group();root.name='Garden proposals';root.userData.gardenOverlay=true;scene.add(root);
  const entries=new Map(),materials=new Map(),normals=new Map();
  const vegetation=new T.MeshStandardMaterial({vertexColors:true,roughness:.84,side:T.DoubleSide});
  const selectionMaterial=new T.LineBasicMaterial({color:0xedbd63});
  const raycaster=new T.Raycaster();
  let selection=null,highlightSignature=null;
  let ordered=[],cutAreas=[],uncutAreas=[],cutEntries=[],barriers=[],supportMeshes=[];
  const normalMatrix=new T.Matrix3();
  function within(p,b,tolerance=.00005){
    return p[0]>=b.x-tolerance && p[0]<=b.X+tolerance && p[1]>=b.z-tolerance && p[1]<=b.Z+tolerance;
  }
  function material(key,pattern,palette){
    const id=[key,pattern,palette].join('/');
    if(!materials.has(id)){
      const m=makeSwatch(T,key,pattern,palette);
      const source=({brick:'red_brick',sleepers:'weathered_plank_siding',decking:'wood_floor_deck',
                     lawn:'grass_ground',concrete:'brushed_concrete',paving:'brushed_concrete',limestone:'brushed_concrete',
                     slate:'brushed_concrete',stone:'brushed_concrete'})[key];
      if(source && typeof document!=='undefined'){
        if(!normals.has(source)){
          const map=new T.TextureLoader().load(new URL('../../assets/textures/'+source+'/normal.jpg',import.meta.url).href);
          map.wrapS=map.wrapT=T.RepeatWrapping;map.repeat.set(1,1);map.anisotropy=4;normals.set(source,map);
        }
        m.normalMap=normals.get(source);m.normalScale.set(.15,.15);
      }
      materials.set(id,m);
    }
    return materials.get(id);
  }
  const state={T,material,vegetation};
  function erase(entry){
    entry.group.traverse(obj=>obj.geometry?.dispose());root.remove(entry.group);
  }
  function build(f,signature){
    const group=new T.Group();group.name=f.label;group.userData.gardenFeatureId=f.id;
    const points=sampleGeometry(f.geometry,f.kind==='outbuilding-base'?.0005:.008),box=bounds2(points);
    const e={feature:f,group,points,signature,box,closed:isClosed(f.geometry),form:KINDS[f.kind].form,
             center:[(box.x+box.X)/2,(box.z+box.Z)/2],treads:[],cuts:[],cap:null,floor:null};
    if(f.kind==='car-guide'||f.kind==='van-guide'){
      e.form='guide'; e.outlineY=f.baseY+f.level;
      const vehicle=new T.Group(),g=f.geometry,w=g.width,d=g.depth,h=f.height;
      vehicle.position.set(g.center[0],f.baseY+f.level,g.center[1]);vehicle.rotation.y=-g.yaw;group.add(vehicle);
      const bodyMat=material('steel','plain','cool'),glassMat=material('slate','plain','cool');
      const box=(width,height,length,x,y,z,mat)=>{const m=new T.Mesh(new T.BoxGeometry(width,height,length),mat);m.position.set(x,y,z);vehicle.add(m);};
      box(w*.9,h*.43,d,0,h*.35,0,bodyMat);
      box(w*.82,h*.45,d*(f.kind==='van-guide'?.78:.53),0,h*.775,d*.05,glassMat);
      for(const x of [-1,1])for(const z of [-1,1])box(w*.12,h*.25,d*.12,x*w*.44,h*.125,z*d*.32,bodyMat);
      // Full rectangular envelope is the clearance reference, including mirrors.
      box(w,.04,.20,0,h*.5,-d*.17,bodyMat);
    }
    else if(f.kind==='outbuilding-base')slabObject(state,e);
    else if(e.form==='area')areaObject(state,e);
    else if(e.form==='line')lineObject(state,e);
    else{
      const s=SPECIES[f.species]||SPECIES[f.kind==='tree'?'apple':'lavender'],plants=new Batch(T);
      const species=SPECIES[f.species]?f.species:(f.kind==='tree'?'apple':'lavender');
      e.point=f.geometry.center;e.radius=(f.width||s.width)/2;e.outlineY=0;
      specimen(plants,species,seedFrom(f.id),e.radius*2,f.height||s.height,[...xyz(e.point,0)],f.geometry.yaw);
      plants.mesh(vegetation,s.label,group);
    }
    for(const tread of e.treads)tread.box=bounds2(tread.poly);
    root.add(group);return e;
  }
  function heightAt(x,z){
    const p=[x,z];
    // The independent tread geometry owns its footprint, even over an area or path.
    for(const e of ordered)for(const t of e.treads){
      if(within(p,t.box)&&(inside(p,t.poly)||nearLine(p,t.poly,true)<.00005))return t.y;
    }
    for(const list of [cutAreas,uncutAreas])for(const e of list){
      if(!within(p,e.box)||(!inside(p,e.points)&&nearLine(p,e.points,true)>.00005))continue;
      if(e.cap && !inside(p,e.cap.inner)){
        const gate=e.gate,local=gate?minus(p,gate.center):null;
        if(!gate || Math.abs(dot(local,gate.tangent))>gate.width/2 || Math.abs(dot(local,gate.inner))>e.rimWidth*1.5) return e.cap.y;
      }
      return e.floor;
    }
    return null;
  }
  function placePoints(){
    for(const e of entries.values())if(e.point){
      const y=(heightAt(...e.point)??e.feature.baseY)+e.feature.level;
      e.group.position.y=y;e.outlineY=y;
    }
  }
  function highlight(id){
    const e=entries.get(id),signature=e?e.signature+'|'+e.outlineY:null;
    if(signature===highlightSignature)return;
    if(selection){root.remove(selection);selection.geometry.dispose();selection=null;}
    highlightSignature=signature;
    if(!e)return;
    let pts=e.points;
    if(e.point) pts=Array.from({length:32},(_,i)=>plus(e.point,times([Math.cos(TAU*i/32),Math.sin(TAU*i/32)],e.radius)));
    const loop=e.closed||e.point,positions=pts.map(p=>new T.Vector3(p[0],e.outlineY+.012,p[1]));
    selection=loop?new T.LineLoop(new T.BufferGeometry().setFromPoints(positions),selectionMaterial):
      new T.Line(new T.BufferGeometry().setFromPoints(positions),selectionMaterial);
    selection.name='Selected garden object';selection.userData.gardenFeatureId=id;root.add(selection);
  }
  function set(objects,selectedId=null){
    const ids=new Set(objects.map(f=>f.id));
    for(const [id,e] of entries)if(!ids.has(id)){erase(e);entries.delete(id);}
    for(const f of objects){
      const signature=JSON.stringify(f),last=entries.get(f.id);
      if(last?.signature===signature)continue;
      if(last)erase(last);
      entries.set(f.id,build(f,signature));
    }
    // Geometry and material instances of unedited objects survive palette, handle and selection changes.
    ordered=objects.map(f=>entries.get(f.id)).reverse();
    cutAreas=ordered.filter(e=>e.form==='area'&&e.cuts.length);
    uncutAreas=ordered.filter(e=>e.form==='area'&&!e.cuts.length);
    cutEntries=ordered.flatMap(e=>e.cuts.map(c=>({points:c.points,box:bounds2(c.points)})));
    placePoints();highlight(selectedId);
    const used=new Set();barriers=[];supportMeshes=[];
    root.traverse(o=>{
      if(o.isMesh)used.add(o.material);
      if(o.userData.gardenBarrier)barriers.push(o);
      if(o.userData.gardenSupport)supportMeshes.push(o);
    });
    for(const [key,m] of materials)if(!used.has(m)){m.map.dispose();m.dispose();materials.delete(key);}
    root.updateMatrixWorld(true);
  }
  function cuts(){
    return [...entries.values()].flatMap(e=>e.cuts.map(c=>({...c,points:c.points.map(p=>[...p])})));
  }
  function masksGround(x,z){
    const p=[x,z];
    return cutEntries.some(c=>within(p,c.box)&&(inside(p,c.points)||nearLine(p,c.points,true)<.00005));
  }
  function surfaceHit(ray,far=Infinity){
    raycaster.ray.copy(ray);raycaster.near=.0001;raycaster.far=far;
    for(const h of raycaster.intersectObjects(supportMeshes,false)){
      const normal=h.face.normal.clone().applyNormalMatrix(normalMatrix.getNormalMatrix(h.object.matrixWorld));
      if(normal.y>=.5 && normal.dot(ray.direction)<0){
        return {id:h.object.userData.gardenFeatureId,distance:h.distance,normal,point:h.point,surface:'garden-proposal'};
      }
    }
    return null;
  }
  function pick(x,z,tolerance=.10){
    const p=[x,z];
    for(const e of ordered)if(e.point && along(p,e.point)<=e.radius+tolerance)return e.feature.id;
    for(const e of ordered)if(e.form==='line' && nearLine(p,e.points,e.closed)<=e.lineWidth/2+tolerance)return e.feature.id;
    for(const e of ordered)if((e.form==='area'||e.form==='guide') && (inside(p,e.points)||nearLine(p,e.points,true)<=tolerance||
      e.treads.some(t=>inside(p,t.poly))))return e.feature.id;
    return null;
  }
  function blockRay(ray,far=Infinity){
    raycaster.ray.copy(ray);raycaster.near=.0001;raycaster.far=far;
    const h=raycaster.intersectObjects(barriers,false)[0];
    if(!h)return null;
    const normal=h.face.normal.clone().applyNormalMatrix(normalMatrix.getNormalMatrix(h.object.matrixWorld));
    if(normal.dot(ray.direction)>0)normal.negate();
    return {distance:h.distance,normal,point:h.point};
  }
  function dispose(){
    for(const e of entries.values())erase(e);entries.clear();
    ordered=[];cutAreas=[];uncutAreas=[];cutEntries=[];barriers=[];supportMeshes=[];
    if(selection){root.remove(selection);selection.geometry.dispose();selection=null;}
    for(const m of materials.values()){m.map.dispose();m.dispose();}materials.clear();
    for(const map of normals.values())map.dispose();normals.clear();
    selectionMaterial.dispose();vegetation.dispose();scene.remove(root);
  }
  return {set,heightAt,cuts,masksGround,surfaceHit,pick,blockRay,dispose};
}
