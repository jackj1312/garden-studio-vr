// Scanned leaf cards within the existing columnar shrub envelopes; no shell edits.
import fs from 'node:fs/promises';
import {io,studioRequire} from '../house/runtime_assets.mjs';
const {Document}=studioRequire('@gltf-transform/core');
const rows=JSON.parse(await fs.readFile('out/unreal-house/golden/bundle/replacement-placements.json')).filter(r=>r.name.startsWith('Plant2_door_shrub'));
const doc=new Document(),buf=doc.createBuffer(),scene=doc.createScene('DoorFoliage'),mat=doc.createMaterial('ScannedLeaf').setDoubleSided(true);
let seed=410;const rnd=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296);
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],norm=a=>{let l=Math.hypot(...a);return a.map(v=>v/l)};
const atlas=[[.01,.24,.01,.49],[.245,.415,.01,.46],[.425,.625,.01,.49],[.64,.82,.01,.46],[.825,.995,.01,.43]];
for(const row of rows){
 const lo=row.min,hi=row.max,w=hi[0]-lo[0],h=hi[1]-lo[1],d=hi[2]-lo[2],p=[],n=[],uv=[];
 for(let i=0;i<2500;i++){
  const y=.14+.84*rnd(),ang=rnd()*Math.PI*2,r=(.76+.23*rnd())*Math.sqrt(Math.max(0,1-((y-.53)/.48)**2));
  const center=[(lo[0]+hi[0])/2+Math.cos(ang)*(w*.5-.045)*r,lo[1]+h*y,(lo[2]+hi[2])/2+Math.sin(ang)*(d*.5-.045)*r];
  const normal=norm([Math.cos(ang)+.5*(rnd()-.5),.7*(rnd()-.5),Math.sin(ang)+.5*(rnd()-.5)]),right=norm(cross([0,1,0],normal)),up=norm(cross(normal,right));
  const lw=.035+rnd()*.022,lh=.075+rnd()*.035,points=[[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]].map(([x,y])=>center.map((v,k)=>v+right[k]*x*lw+up[k]*y*lh));
  const [u0,u1,v0,v1]=atlas[i%atlas.length],tex=[[u0,v1],[u1,v1],[u1,v0],[u0,v0]];
  for(const j of [0,1,2,0,2,3]){p.push(...points[j]);n.push(...normal);uv.push(...tex[j]);}
 }
 const acc=(type,values)=>doc.createAccessor().setType(type).setArray(new Float32Array(values)).setBuffer(buf);
 const prim=doc.createPrimitive().setMaterial(mat).setAttribute('POSITION',acc('VEC3',p)).setAttribute('NORMAL',acc('VEC3',n)).setAttribute('TEXCOORD_0',acc('VEC2',uv));
 scene.addChild(doc.createNode(row.name).setMesh(doc.createMesh(row.name).addPrimitive(prim)));
}
await fs.mkdir('out/unreal-house/door-foliage',{recursive:true});await io.write('out/unreal-house/door-foliage/DoorFoliage.gltf',doc);
await fs.writeFile('out/unreal-house/door-foliage/source.json',JSON.stringify({texture:'Poly Haven island_tree_02 leaves',licence:'CC0 1.0',geometry:'Original deterministic leaf-card canopy',count:rows.length*2500,seed:410}));console.log('Scanned leaf canopy',rows.length*2500);
