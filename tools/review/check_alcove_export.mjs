import {io,studioRequire} from '../house/runtime_assets.mjs';
const {getBounds}=studioRequire('@gltf-transform/core');const d=await io.read('out/unreal-house/alcove/Alcove.gltf');const rows=[];
for(const n of d.getRoot().listNodes())if(n.getMesh()){const b=getBounds(n);rows.push({name:n.getName(),...b});if(n.getName()==='AlcoveLampFit'&&b.max[1]>1.22)throw Error('Lamp reaches first shelf');}
console.log(JSON.stringify(rows));
const n=d.getRoot().listNodes().find(n=>n.getName()==='AlcoveFixed'),M=n.getWorldMatrix();let oak=0,paint=0;
for(const p of n.getMesh().listPrimitives()){const a=p.getAttribute('POSITION'),idx=p.getIndices()?.getArray()||Array.from({length:a.getCount()},(_,i)=>i);for(let j=0;j<idx.length;j+=3){const vs=[];for(const k of [idx[j],idx[j+1],idx[j+2]]){const v=a.getElement(k,[]);vs.push([M[0]*v[0]+M[4]*v[1]+M[8]*v[2]+M[12],M[1]*v[0]+M[5]*v[1]+M[9]*v[2]+M[13],M[2]*v[0]+M[6]*v[1]+M[10]*v[2]+M[14]]);}if(vs.every(v=>Math.abs(v[1]-.9)<1e-5)){if(/oak/i.test(p.getMaterial().getName()))oak++;else paint++;}}}
if(!oak||paint)throw Error('Top face ownership failed '+JSON.stringify({oak,paint}));
console.log(JSON.stringify({topY:.9,oakTriangles:oak,otherTriangles:paint,lampTopBelowShelf:true}));
