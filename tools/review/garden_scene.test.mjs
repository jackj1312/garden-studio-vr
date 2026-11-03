import test from 'node:test';
import assert from 'node:assert/strict';
import * as T from '../../assets/vendor/three/build/three.module.js';
import { createGardenScene } from '../../src/garden/scene.js';
import { KINDS, createFeature } from '../../src/garden/catalogue.mjs';
import { rectangle, circle, point, fitStroke } from '../../src/garden/geometry.mjs';

const close=(a,b,tolerance=1e-6)=>assert.ok(Math.abs(a-b)<=tolerance,`${a} differs from ${b}`);
const line=()=>fitStroke([[0,0],[0,3]],{mode:'straight'});
const fixture=(kind,shape,baseY=0)=>({...createFeature(kind,shape,baseY),id:'test-'+kind});
function stage() {
  const scene=new T.Scene(),garden=createGardenScene(T,scene),group=scene.getObjectByName('Garden proposals');
  return {scene,garden,group};
}
function box(object) {
  object.updateMatrixWorld(true);return new T.Box3().setFromObject(object,true);
}

test('all sixteen object kinds produce finite, pickable geometry and clean up',()=>{
  const {garden,scene,group}=stage();const features=[];
  for(const [i,kind] of Object.keys(KINDS).entries()){
    const x=i*4,form=KINDS[kind].form;
    const shape=form==='point'?point([x,0]):form==='line'?fitStroke([[x,-1],[x,1]],{mode:'straight'}):rectangle([x,0],2.4,2);
    const f=fixture(kind,shape,1);features.push(f);
  }
  garden.set(features,null);
  assert.equal(group.children.length,16);
  for(const [i,f] of features.entries()){
    const rep=group.children.find(c=>c.userData.gardenFeatureId===f.id);
    assert.ok(rep.children.length>0,f.kind);
    assert.equal(garden.pick(i*4,0,.01),f.id);
    const b=box(rep);
    for(const n of [...b.min.toArray(),...b.max.toArray()])assert.ok(Number.isFinite(n),f.kind);
  }
  assert.equal(garden.pick(-50,-30),null);
  garden.dispose();assert.equal(scene.children.length,0);
});

test('a measured excavation opens only its footprint, has a lowered floor and real graded treads',()=>{
  const {garden,group}=stage();
  const sunken=fixture('sunken-area',rectangle([0,0],4,3),1);
  sunken.level=-.60;sunken.steps={at:2/14,count:3,width:1};
  garden.set([sunken],sunken.id);
  const cut=garden.cuts()[0];
  assert.equal(cut.id,sunken.id);close(cut.baseY,1);assert.equal(cut.points.length,4);
  assert.equal(garden.heightAt(0,-1.55),null);
  close(garden.heightAt(0,-1.42),.8);close(garden.heightAt(0,-1.10),.6);close(garden.heightAt(0,-.75),.4);
  close(garden.heightAt(1.95,0),1);close(garden.heightAt(.72,.66),.4);
  const tread=group.getObjectByName('Access treads and risers');
  assert.ok(tread);const ray=new T.Raycaster(new T.Vector3(0,2,-1.10),new T.Vector3(0,-1,0));
  close(ray.intersectObject(tread,false)[0].point.y,.6);
  const wallHit=garden.blockRay(new T.Ray(new T.Vector3(0,.68,.1),new T.Vector3(1,0,0)),3);
  assert.ok(wallHit && wallHit.distance>1.7 && wallHit.distance<2.1);
  garden.dispose();
});

test('standalone steps rise in drawing direction; reselecting does not rebuild unchanged meshes',()=>{
  const {garden,group}=stage();const steps=fixture('steps',line(),.3);
  steps.height=.60;steps.level=.10;steps.steps.count=3;
  const patio=fixture('patio',rectangle([5,2],2,2),0);
  garden.set([steps,patio]);const root=group.children.find(o=>o.userData.gardenFeatureId===steps.id);
  close(garden.heightAt(0,.3),.60);close(garden.heightAt(0,1.4),.80);close(garden.heightAt(0,2.6),1);
  garden.set([steps,patio],steps.id);assert.ok(group.children.includes(root));
  garden.set([steps,{...patio,palette:'warm'}],patio.id);assert.ok(group.children.includes(root));
  assert.equal(garden.heightAt(-.80,1.4),null);
  garden.dispose();
});

test('individual specimens follow the new host surface and retain their own IDs and state',()=>{
  const {garden,group}=stage();const bed=fixture('raised-bed',circle([0,0],1.5),.2);
  const a=fixture('plant',point([0,0],.1),.2),b={...fixture('tree',point([3,0],.5),.2),id:'second-tree',species:'birch',width:2,height:3};
  garden.set([bed,a,b]);const plant=group.children.find(o=>o.userData.gardenFeatureId===a.id),tree=group.children.find(o=>o.userData.gardenFeatureId===b.id);
  close(box(plant).min.y,garden.heightAt(0,0));close(box(tree).min.y,.2);close(box(tree).max.y-box(tree).min.y,3,.002);
  assert.equal(garden.pick(0,0),a.id);assert.equal(garden.pick(3,0),b.id);
  const hash=Array.from(bedMesh(group,bed.id).geometry.attributes.position.array.slice(0,60));
  garden.set([{...bed,level:.12},a,b]);assert.ok(group.children.includes(plant));close(box(plant).min.y,garden.heightAt(0,0));
  garden.set([bed,a,b]);assert.deepEqual(Array.from(bedMesh(group,bed.id).geometry.attributes.position.array.slice(0,60)),hash);
  garden.dispose();
});
function bedMesh(group,id) {return group.children.find(x=>x.userData.gardenFeatureId===id).getObjectByName('Planting and dressing');}

test('stonework patterns have physical UV repeat and concave areas keep their recesses',()=>{
  const {garden,group}=stage();
  const patio=fixture('patio',fitStroke([[0,0],[3,0],[3,1],[1,1],[1,3],[0,3]],{mode:'straight',closed:true}));
  garden.set([patio]);
  assert.equal(garden.heightAt(2,2),null);close(garden.heightAt(.5,2),0);
  const floor=group.getObjectByName('Walking surface'),map=floor.material.map;
  close(1/map.repeat.x,4*.60);close(1/map.repeat.y,4*.40);
  const pos=floor.geometry.attributes.position,uv=floor.geometry.attributes.uv;
  for(let i=0;i<pos.count;i++){close(pos.getX(i),uv.getX(i));close(pos.getZ(i),uv.getY(i));}
  garden.dispose();
});

test('oblique rays hit raised decks and cut floors at their visible 3D position',()=>{
  const {garden}=stage(),cut=fixture('sunken-area',rectangle([0,0],5,4),0);
  cut.level=-.60;const deck=fixture('decking',rectangle([10,0],4,3),0);deck.level=.40;
  garden.set([cut,deck]);
  const aim=x=>new T.Ray(new T.Vector3(x,1.6,0),new T.Vector3(1,-1,0).normalize());
  const low=garden.surfaceHit(aim(-1.6)),high=garden.surfaceHit(aim(8.4));
  close(low.point.x,.60);close(low.point.y,-.60);close(low.normal.y,1);assert.equal(low.id,cut.id);
  close(high.point.x,9.60);close(high.point.y,.40);
  assert.ok(garden.masksGround(0,0));assert.ok(!garden.masksGround(3,0));assert.ok(!garden.masksGround(10,0));
  assert.equal(garden.surfaceHit(aim(-1.6),.2),null);
  garden.dispose();
});

test('every descending stair vertex, including risers and cheeks, fits the circular excavation',()=>{
  const {garden,group}=stage(),cut=fixture('sunken-area',circle([0,0],1.5));
  cut.level=-.60;cut.steps={count:3,width:1,at:.23};
  garden.set([cut]);
  const points=group.getObjectByName('Access treads and risers').geometry.attributes.position;
  for(let i=0;i<points.count;i++){
    assert.ok(Math.hypot(points.getX(i),points.getZ(i))<=1.500001,'vertex outside original measured circle');
  }
  const cutData=garden.cuts()[0];
  cutData.points[0][0]=999;
  assert.ok(garden.masksGround(0,0));assert.ok(!garden.masksGround(5,0));
  garden.dispose();
});
