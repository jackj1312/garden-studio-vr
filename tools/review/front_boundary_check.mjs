import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as THREE from '../../assets/vendor/three/build/three.module.js';
import {createFrontBoundary,boundaryEnvelope} from '../../src/garden/front-boundary.js';
import {createStreetFrontage} from '../../src/garden/street-frontage.js';
const T={...THREE,TextureLoader:class{load(){return new THREE.Texture();}}};
const file=fs.readFileSync('assets/sites/house-wip/furnish/approved_2b/fixed.glb');
const gltf=JSON.parse(file.subarray(20,20+file.readUInt32LE(12)));
const parts=[];
for(const n of gltf.nodes){
 if(n.mesh===undefined)continue;
 const m=n.matrix?new T.Matrix4().fromArray(n.matrix):new T.Matrix4().compose(new T.Vector3().fromArray(n.translation||[0,0,0]),new T.Quaternion().fromArray(n.rotation||[0,0,0,1]),new T.Vector3().fromArray(n.scale||[1,1,1]));
 for(const pr of gltf.meshes[n.mesh].primitives){const a=gltf.accessors[pr.attributes.POSITION];if(!a.min)continue;parts.push({name:n.name,bbox:new T.Box3(new T.Vector3(...a.min),new T.Vector3(...a.max)).applyMatrix4(m),materialName:gltf.materials[pr.material]?.name||'',hidden:false});}
}
const scene=new T.Scene(),entry={model:{parts}},wall=createFrontBoundary(T,scene),street=createStreetFrontage(T,scene);
const expected=boundaryEnvelope(parts);wall.update(entry);street.update(entry);scene.updateMatrixWorld(true);
const core=wall.group.getObjectByName('Continuous owner wall core');assert(core);
const box=new T.Box3().setFromObject(core);assert(Math.abs(box.min.x-expected.left)<1e-6);assert(Math.abs(box.max.x-expected.right)<1e-6);
const actual=new T.Box3();for(const child of wall.group.children)if(!child.name.startsWith('Neighbour hedge'))actual.expandByObject(child);
assert(Math.abs(actual.min.x-expected.left)<1e-5);assert(Math.abs(actual.max.x-expected.right)<1e-5);assert(Math.abs(actual.max.y-expected.top)<1e-5,'Actual cap top differs from hedge');
const dims=wall.group.userData.wallDimensions;assert(Math.abs(dims.height-(expected.top-expected.ground))<1e-7);
const ray=(x)=>new T.Ray(new T.Vector3(x,expected.ground+.8,expected.front+2),new T.Vector3(0,0,-1));
for(let x=expected.left+.02;x<expected.right;x+=.05)assert(wall.blockRay(ray(x),3),`Wall hole at ${x}`);
assert.equal(wall.blockRay(ray(.2),3),null,'Pedestrian opening blocked');assert.equal(wall.blockRay(ray(10),3),null,'Driveway blocked');
assert.equal(parts.find(p=>p.name.includes('west_block')).hidden,false,'Neighbour hedge hidden');
assert(street.heightAt(4,24)>-.25,'Former central gap not surfaced');assert(street.heightAt(10,24)>-.25,'Drive crossing missing');
const layout=JSON.parse(fs.readFileSync('assets/sites/house-wip/layout/approved_2b.json'));const saved=JSON.parse(fs.readFileSync('renders/garden-tool/studio-concept/backup-before-latest/layout/approved_2b.json'));assert.deepEqual(layout.garden,saved.garden);
wall.group.visible=false;assert.equal(wall.blockRay(ray(4),3),null);wall.update(entry);assert(wall.blockRay(ray(4),3));
street.group.visible=false;assert.equal(street.heightAt(4,24),null);street.update(entry);assert(street.heightAt(4,24)!==null);
const out={pass:true,envelope:expected,wallDimensions:dims,street:street.group.userData.dimensions,checks:['continuous core and body ray sweep every 50mm','hedge maximum height','pedestrian gap and actual driveway clear','neighbour source retained','street floor heights','version visibility round trip','saved garden exactly unchanged']};
fs.mkdirSync('renders/garden-tool/front-boundary',{recursive:true});fs.writeFileSync('renders/garden-tool/front-boundary/check.json',JSON.stringify(out,null,2));console.log(JSON.stringify(out,null,2));
