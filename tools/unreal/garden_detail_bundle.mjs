// Deterministic metre-scale relief sampled only inside the surveyed garden surfaces.
import fs from 'node:fs/promises';
import {io,studioRequire} from '../house/runtime_assets.mjs';
const {Document}=studioRequire('@gltf-transform/core');
const source=process.argv[2],out=process.argv[3];
const src=await io.read(source),d=new Document(),buf=d.createBuffer(),scene=d.createScene('GardenDetail');
let seed=1847;const rnd=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);
const groups=new Map(),counts={grass:0,gravel:0};
function triangle(key,material,a,b,c,color){
 if(!groups.has(key))groups.set(key,{material,p:[],n:[],c:[]});const g=groups.get(key);
 const u=b.map((v,i)=>v-a[i]),v=c.map((v,i)=>v-a[i]);let n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],l=Math.hypot(...n);n=n.map(x=>x/(l||1));
 g.p.push(...a,...b,...c);for(let i=0;i<3;i++){g.n.push(...n);g.c.push(...color);}
}
const grass=d.createMaterial('Detail_Grass').setBaseColorFactor([1,1,1,1]).setRoughnessFactor(.85).setMetallicFactor(0).setDoubleSided(true);
const gravel=d.createMaterial('Detail_Gravel').setBaseColorFactor([1,1,1,1]).setRoughnessFactor(.87).setMetallicFactor(0);
for(const node of src.getRoot().listNodes()){
 const kind=/^G2_lawn(_west)?$/.test(node.getName())?'grass':node.getName()==='G2_gravel'?'gravel':null;if(!kind)continue;
 for(const p of node.getMesh().listPrimitives()){
 // Copy positions with source world transform; source attributes stay read-only.
 const pa=p.getAttribute('POSITION'),arr=new Float32Array(pa.getArray());const m=node.getWorldMatrix();
 const points=[];for(let i=0;i<arr.length;i+=3){let x=arr[i],y=arr[i+1],z=arr[i+2];points.push([m[0]*x+m[4]*y+m[8]*z+m[12],m[1]*x+m[5]*y+m[9]*z+m[13],m[2]*x+m[6]*y+m[10]*z+m[14]]);}
 const ind=p.getIndices()?.getArray()||points.map((_,i)=>i);
 for(let i=0;i<ind.length;i+=3){const a=points[ind[i]],b=points[ind[i+1]],c=points[ind[i+2]];
 const area=Math.abs((b[0]-a[0])*(c[2]-a[2])-(b[2]-a[2])*(c[0]-a[0]))/2;
 if(area<1e-9||Math.max(a[1],b[1],c[1])-Math.min(a[1],b[1],c[1])>.15)continue;
 const density=kind==='grass'?1900:1250;let n=Math.floor(area*density)+(rnd()<area*density%1?1:0);
 for(let j=0;j<n;j++){let u=Math.sqrt(rnd()),v=rnd();const q=a.map((x,k)=>(1-u)*x+u*(1-v)*b[k]+u*v*c[k]);if(q[2]<0||q[2]>23)continue;
 const key=kind+'_'+Math.floor(q[0]/3)+'_'+Math.floor(q[2]/3);counts[kind]++;
 if(kind==='grass'){
 const patch=.5+.25*Math.sin(q[0]*3.1+Math.sin(q[2]*1.7))+.25*Math.sin(q[2]*4.3-q[0]);
 const h=.038+rnd()*.037+patch*.025,w=.0015+rnd()*.0018,angle=rnd()*Math.PI*2,dx=Math.cos(angle)*w,dz=Math.sin(angle)*w,lean=h*(.2+rnd()*.45),f=.65+rnd()*.35+patch*.3;
 const col=[.075*f,.135*f,.023*f];q[1]+=.0005;
 const a=[q[0]-dx,q[1],q[2]-dz],b=[q[0]+dx,q[1],q[2]+dz];
 const mid=[q[0]+Math.sin(angle)*lean*.25,q[1]+h*.55,q[2]+Math.cos(angle)*lean*.25];
 const ml=[mid[0]-dx*.6,mid[1],mid[2]-dz*.6],mr=[mid[0]+dx*.6,mid[1],mid[2]+dz*.6];
 const tip=[q[0]+Math.sin(angle)*lean,q[1]+h,q[2]+Math.cos(angle)*lean];
 triangle(key,grass,a,b,mr,col);triangle(key,grass,a,mr,ml,col);triangle(key,grass,ml,mr,tip,col);
 }else{
 const r=.009+rnd()*.012,h=.005+rnd()*.009,angle=rnd()*Math.PI*2,f=.55+rnd()*.85,col=[.26*f,.21*f,.145*f];
 const top=[q[0],q[1]+h,q[2]],ring=[];for(let k=0;k<6;k++){const t=angle+k*Math.PI/3;ring.push([q[0]+Math.cos(t)*r,q[1]+.001,q[2]+Math.sin(t)*r*.72]);}
 for(let k=0;k<6;k++)triangle(key,gravel,ring[k],top,ring[(k+1)%6],col);
 }
 }
 }
 }
}
for(const [key,g]of groups){const attr=(type,array)=>d.createAccessor().setType(type).setArray(new Float32Array(array)).setBuffer(buf);const p=d.createPrimitive().setAttribute('POSITION',attr('VEC3',g.p)).setAttribute('NORMAL',attr('VEC3',g.n)).setAttribute('COLOR_0',attr('VEC3',g.c)).setMaterial(g.material);scene.addChild(d.createNode(key).setMesh(d.createMesh(key).addPrimitive(p)));}
await fs.mkdir(out,{recursive:true});await io.write(out+'/GardenDetail.gltf',d);await fs.writeFile(out+'/detail-receipt.json',JSON.stringify({seed:1847,counts,cells:groups.size,source,units:'metres',licence:'Original procedural geometry; no external asset'},null,2));console.log(counts,groups.size);
