// Derive shallow joint and wear relief from the existing paving photograph;
// preserve its pattern and UVs rather than substituting different brickwork.
import fs from 'node:fs/promises';import path from 'node:path';
import {studioRequire} from '../house/runtime_assets.mjs';
const sharp=studioRequire('sharp');const [bundle,out]=process.argv.slice(2);
const g=JSON.parse(await fs.readFile(path.join(bundle,'House.gltf')));
const mapping=JSON.parse(await fs.readFile(path.join(bundle,'../material-map.json')));
const identity=mapping.find(m=>m.name==='FG2_paving_units_gltf');
if(!identity)throw Error('Measured paving material identity missing');
const m=g.materials.find(m=>m.name===identity.id);
const t=m.pbrMetallicRoughness.baseColorTexture.index,uri=g.images[g.textures[t].source].uri;
const {data,info}=await sharp(path.join(bundle,uri)).resize(1024,1024).removeAlpha().raw().toBuffer({resolveWithObject:true});
const w=info.width,h=info.height,n=w*h,height=new Float32Array(n),heightBytes=Buffer.alloc(n),norm=Buffer.alloc(n*3),rough=Buffer.alloc(n);
for(let i=0;i<n;i++){const l=(.2126*data[i*3]+.7152*data[i*3+1]+.0722*data[i*3+2])/255;
 // 4 mm mortar recess, plus sub-millimetre texture. This is inferred relief, not a scan.
 const joint=Math.max(0,Math.min(1,(l-.12)/.15));height[i]=joint*.004+Math.max(0,l-.3)*.0008; heightBytes[i]=Math.round(Math.min(1,height[i]/.0046)*255);rough[i]=Math.round(205+(1-joint)*35);}
for(let y=0;y<h;y++)for(let x=0;x<w;x++){let i=y*w+x,dx=(height[y*w+(x+1)%w]-height[y*w+(x+w-1)%w])*w/2,dz=(height[((y+1)%h)*w+x]-height[((y+h-1)%h)*w+x])*h/2;const length=Math.hypot(dx,dz,1);norm[i*3]=Math.round((-.3*dx/length*.5+.5)*255);norm[i*3+1]=Math.round((-.3*dz/length*.5+.5)*255);norm[i*3+2]=Math.round((1/length*.5+.5)*255);}
await fs.mkdir(out,{recursive:true});for(const [name,bytes,channels]of [['PavingHeight',heightBytes,1],['PavingNormal',norm,3],['PavingRoughness',rough,1]])await sharp(bytes,{raw:{width:w,height:h,channels}}).png().toFile(path.join(out,name+'.png'));
await fs.writeFile(path.join(out,'provenance.json'),JSON.stringify({source:uri,method:'Inferred shallow relief from owner-approved paving texture; not measured or scanned displacement',maximumReliefMetres:.0046,pattern:'unchanged'},null,2));console.log('Paving relief maps prepared');
