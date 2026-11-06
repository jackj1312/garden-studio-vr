import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as THREE from '../../assets/vendor/three/build/three.module.js';
import {createFrontBoundary,boundaryEnvelope} from '../../src/garden/front-boundary.js';
import {createStreetFrontage} from '../../src/garden/street-frontage.js';
import {frontageSurvey as S,grassEdge,kerbEdge} from '../../src/garden/frontage-survey.js';
const T={...THREE,TextureLoader:class{load(){return new THREE.Texture();}}};
const file=fs.readFileSync('assets/sites/house-wip/furnish/approved_2b/fixed.glb');
const gltf=JSON.parse(file.subarray(20,20+file.readUInt32LE(12)));
const parts=[],contextMaterials=new Map();
for(const n of gltf.nodes){
 if(n.mesh===undefined)continue;
 const m=n.matrix?new T.Matrix4().fromArray(n.matrix):new T.Matrix4().compose(new T.Vector3().fromArray(n.translation||[0,0,0]),new T.Quaternion().fromArray(n.rotation||[0,0,0,1]),new T.Vector3().fromArray(n.scale||[1,1,1]));
 for(const pr of gltf.meshes[n.mesh].primitives){const a=gltf.accessors[pr.attributes.POSITION];if(!a.min)continue;const p={name:n.name,element:n.extras?.element||n.name,bbox:new T.Box3(new T.Vector3(...a.min),new T.Vector3(...a.max)).applyMatrix4(m),materialName:gltf.materials[pr.material]?.name||'',hidden:false};
  if(/^G-(site|dug|reinstated|final)$/.test(n.name)){p.name=n.name+'_primitive';p.set={normal:new T.MeshStandardMaterial(),xray:new T.MeshStandardMaterial()};p.mesh={material:p.set.normal,visible:true};}
  if(/^Opp_/.test(n.name)){
   // Actual GLB bounds and transforms, with a cheap box standing in for the
   // context mesh; this catches accidental loss of the assigned transform.
   if(!contextMaterials.has(pr.material))contextMaterials.set(pr.material,new T.MeshStandardMaterial());
   p.geometry=new T.BoxGeometry(...a.max.map((v,i)=>v-a.min[i]));p.geometry.translate(...a.max.map((v,i)=>(v+a.min[i])/2));p.matrix0=m;p.mesh={material:contextMaterials.get(pr.material),visible:true};
  }parts.push(p);
 }
}
const scene=new T.Scene(),entry={model:{parts}},wall=createFrontBoundary(T,scene),street=createStreetFrontage(T,scene);
const expected=boundaryEnvelope(parts);wall.update(entry);street.update(entry);scene.updateMatrixWorld(true);
for(const p of parts.filter(p=>/^G-(site|dug|reinstated|final)$/.test(p.element)))for(const m of [p.set.normal,p.set.xray,p.mesh.customDepthMaterial,p.mesh.customDistanceMaterial])assert(m.userData.frontageMask,'Loaded ground primitive escaped replacement mask');
const core=wall.group.getObjectByName('Continuous owner wall core');assert(core);
const box=new T.Box3().setFromObject(core);assert(Math.abs(box.min.x-expected.left)<1e-6);assert(Math.abs(box.max.x-expected.right)<1e-6);
const actual=new T.Box3();for(const child of wall.group.children)if(!child.name.startsWith('Neighbour hedge'))actual.expandByObject(child);
assert(Math.abs(actual.min.x-expected.left)<1e-5);assert(Math.abs(actual.max.x-expected.right)<1e-5);assert(Math.abs(actual.max.y-expected.top)<1e-5,'Actual cap top differs from hedge');
const dims=wall.group.userData.wallDimensions;assert(Math.abs(dims.height-(expected.top-expected.ground))<1e-7);
assert.equal(dims.pierXs.length,2,'Exactly two end piers required');assert.equal(wall.group.userData.wallRuns.length,1,'Infill must be uninterrupted');
const ray=(x)=>new T.Ray(new T.Vector3(x,expected.ground+.8,expected.front+2),new T.Vector3(0,0,-1));
for(let x=expected.left+.02;x<expected.right;x+=.05)assert(wall.blockRay(ray(x),3),`Wall hole at ${x}`);
assert.equal(wall.blockRay(ray(.2),3),null,'Pedestrian opening blocked');assert.equal(wall.blockRay(ray(10),3),null,'Driveway blocked');
assert.equal(parts.find(p=>p.name.includes('west_block')).hidden,false,'Neighbour hedge hidden');
assert.equal(parts.find(p=>p.name==='Opp_wall').hidden,true,'Old context wall remains in the recovered road');
const context=street.group.children.filter(m=>m.userData.contextOnly);assert(context.length);
for(const m of context)assert(new T.Box3().setFromObject(m).min.z>43,'Context transform lost while batching');
assert.equal(street.surfaceAt(4,24).kind,'verge','Grass must separate wall and public path');
assert.equal(street.surfaceAt(10,24).kind,'drive','Drive crossing missing');
assert.equal(street.surfaceAt(4,28).kind,'path','Public path must be beyond the verge');
assert(Math.abs(street.heightAt(10,S.start+.001)-S.ground)<.001,'Retained driveway datum changed');
assert(street.heightAt(10,27)<street.heightAt(10,24)-.04,'Approach fall flattened');
assert(street.heightAt(1,30)>street.heightAt(8,30)+.15,'LiDAR lateral road fall lost');
assert(street.heightAt(4,34)<street.heightAt(4,30)-.07,'LiDAR road crossfall lost');
const dx=-4.575,dz=grassEdge(-4.35)-S.wall,len=Math.hypot(dx,dz),cx=(.225-4.35)/2,cz=(S.wall+grassEdge(-4.35))/2;
for(const side of [-1,1])assert.equal(street.surfaceAt(cx+side*.435*dz/len,cz-side*.435*dx/len)?.kind,'access','Diagonal approach loses retained path width');
// The rendered ground and the walker must agree, with one visible surface per
// sampled point. This catches overlapping triangles, holes and plane fallbacks.
const down=new T.Raycaster(),surfaces=street.group.children.filter(c=>!c.userData.contextOnly);
assert(surfaces.length<=4,'Street geometry is not batched by material');
let samples=0,maxHeightError=0;
for(let x=-25.13;x<34.4;x+=.53)for(let z=S.start+.07;z<kerbEdge(x)+S.kerbWidth+S.roadWidth+1.4;z+=.37){
 down.set(new T.Vector3(x,5,z),new T.Vector3(0,-1,0));const hits=down.intersectObjects(surfaces,false),heights=[...new Set(hits.map(h=>h.point.y.toFixed(4)))];
 assert.equal(heights.length,1,`Overlapping or missing street surface at ${x},${z}: ${hits.map(h=>h.object.name+':'+h.point.y)}`);
 const actual=hits[0].point.y,expected=street.heightAt(x,z);assert(expected!==null,`No walking level at ${x},${z}`);
 maxHeightError=Math.max(maxHeightError,Math.abs(actual-expected));samples++;
}
assert(maxHeightError<.004,`Rendered/walker terrain mismatch ${maxHeightError}`);
for(let x=-25.37;x<34.63;x+=.5)assert(kerbEdge(x)-grassEdge(x)>.75,'Context path folded or narrowed');
for(const x of [1,4,8]){assert(grassEdge(x)-S.wall>4,'Verge compressed again');assert(kerbEdge(x)-grassEdge(x)>.9,'Public path too narrow');}
const layout=JSON.parse(fs.readFileSync('assets/sites/house-wip/layout/approved_2b.json'));const saved=JSON.parse(fs.readFileSync('renders/garden-tool/studio-concept/backup-before-latest/layout/approved_2b.json'));assert.deepEqual(layout.garden,saved.garden);
wall.group.visible=false;assert.equal(wall.blockRay(ray(4),3),null);wall.update(entry);assert(wall.blockRay(ray(4),3));
street.setVisible(false);assert.equal(street.heightAt(4,24),null);street.update(entry);assert(street.heightAt(4,24)!==null);
const out={pass:true,envelope:expected,wallDimensions:dims,street:street.group.userData.dimensions,terrain:{samples,maxHeightError},checks:['continuous core and body ray sweep every 50mm','exactly two end piers','hedge maximum height','pedestrian gap and actual driveway clear','neighbour source retained','grass between wall and public path','retained threshold datum','non-flat approach and road crossfalls','one surface per sampled location','rendered and walking levels agree','version visibility round trip','saved garden exactly unchanged']};
fs.mkdirSync('renders/garden-tool/front-boundary',{recursive:true});fs.writeFileSync('renders/garden-tool/front-boundary/check.json',JSON.stringify(out,null,2));console.log(JSON.stringify(out,null,2));
