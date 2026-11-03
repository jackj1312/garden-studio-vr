import test from 'node:test';
import assert from 'node:assert/strict';
import { registerHooks } from 'node:module';
import * as THREE from '../../assets/vendor/three/build/three.module.js';
import { createGardenScene } from '../../src/garden/scene.js';
import { createFeature } from '../../src/garden/catalogue.mjs';
import { rectangle, fitStroke } from '../../src/garden/geometry.mjs';

// The actual house walker/BVH import "three" through house.html's import map.
// Supply the same local revision when using them in Node without a browser.
const three = new URL('../../assets/vendor/three/build/three.module.js',import.meta.url).href;
const resolution = registerHooks({resolve(specifier,context,next){
  return specifier==='three' ? {url:three,shortCircuit:true} : next(specifier,context);
}});
const {createWalker,BODY}=await import('../../src/house/walk.js');
const {buildBVH}=await import('../../src/house/bvh.js');
resolution.deregister();

function close(actual, expected, epsilon=.0001){
  assert.ok(Number.isFinite(actual) && Math.abs(actual-expected)<=epsilon,`expected ${expected} m, got ${actual}`);
}
const path=([x,z],[u,v])=>fitStroke([[x,z],[u,v]],{mode:'straight'});
function profile(){
  const part=(index,x,y,z,w,h,d)=>({index,geometry:new THREE.BoxGeometry(w,h,d),matrix0:new THREE.Matrix4().makeTranslation(x,y,z)});
  const parts=[
    part(0,0,-.05,0,40,.10,40),             // survey grade, top at 0 m
    part(1,10,2.625,0,4,.15,4),             // first floor, top at 2.7 m
    part(2,-4,1.20,0,.20,2.40,4),           // original fixed wall
  ];
  const bvh=buildBVH(parts);
  const masks={floor:new Uint8Array([1,1,0]),solid:new Uint8Array([1,1,1])};
  const garden=createGardenScene(THREE,new THREE.Scene());
  const candidates=()=>bvh,collision=()=>masks.solid, floors=()=>masks.floor;
  const survey=createWalker(candidates,collision,floors);
  // Same floor proposal contract as the live house viewer. The two storeys
  // occupy this measured footprint even if a proposal crosses its boundary.
  const augmented=createWalker(candidates,collision,floors,{
    height:(x,z)=>garden.heightAt(x,z),base:()=>0,
    indoors:(x,y,z)=>x>=8 && x<=12 && Math.abs(z)<=2 && y>=-.10 && y<5.5,
    barrier:(ray,far)=>garden.blockRay(ray,far),
  });
  const dispose=()=>{garden.dispose();for(const p of parts)p.geometry.dispose();};
  return {garden,survey,augmented,dispose};
}
// Exercise horizontal body probes / slide / drop guard and the separate
// vertical settle step, in the same order as walking in the live viewer.
function travel(walker, feet, direction, metres){
  const steps=Math.ceil(metres/.035),delta=direction.clone().multiplyScalar(metres/steps),heights=[];
  for(let i=0;i<steps;i++){
    walker.move(feet,delta);walker.settle(feet,1/60);
    heights.push(feet.y);
  }
  return heights;
}
function settle(walker, feet) {
  for(let i=0;i<120;i++)walker.settle(feet,1/60);
}

test('empty proposals preserve the original floor, wall collision and upper storey',()=>{
  const p=profile();
  try{
    p.garden.set([]);
    for(const [x,y,z] of [[0,0,0],[10,2.7,0],[10,0,0],[-1,0,.8]]){
      close(p.augmented.floorAt(x,y,z),p.survey.floorAt(x,y,z));
    }
    const x=new THREE.Vector3(-3,0,0),y=x.clone(),left=new THREE.Vector3(-1,0,0);
    travel(p.augmented,x,left,2);travel(p.survey,y,left,2);
    close(x.x,y.x);close(x.y,y.y);close(x.x,-3.9+BODY.radius,.005);
  } finally{p.dispose();}
});

test('a garden proposal crossing a room cannot replace either surveyed indoor floor',()=>{
  const p=profile();
  try{
    const patio=createFeature('decking',rectangle([10,0],6,4));patio.level=.9;
    p.garden.set([patio]);
    close(p.garden.heightAt(10,0),.9);
    close(p.augmented.floorAt(10,0,0),0);
    close(p.augmented.floorAt(10,2.7,0),2.7);
    close(p.augmented.floorAt(7.5,.9,0),.9);
  } finally{p.dispose();}
});

test('a walk up ten drawn treads reaches and keeps a terrace 1.6 m above grade',()=>{
  const p=profile();
  try{
    const stairs=createFeature('steps',path([0,0],[0,4]));
    stairs.height=1.6;stairs.steps.count=10;
    const terrace=createFeature('decking',rectangle([0,5],2,2));terrace.level=1.6;
    p.garden.set([stairs,terrace]);
    const feet=new THREE.Vector3(0,0,-.3);
    const heights=travel(p.augmented,feet,new THREE.Vector3(0,0,1),4.9);
    assert.ok(feet.z>4.5,'reached the raised terrace');
    for(let n=1;n<=10;n++)assert.ok(heights.some(y=>Math.abs(y-n*.16)<.0001),'walked tread '+n);
    settle(p.augmented,feet);close(feet.y,1.6);close(p.augmented.floorAt(0,1.6,4.7),1.6);
  } finally{p.dispose();}
});

test('walking down the access opening reaches the excavated floor and the retaining face blocks sideways movement',()=>{
  const p=profile();
  try{
    const pit=createFeature('sunken-area',rectangle([0,0],4,3));
    pit.level=-.60;pit.steps={at:2/14,count:3,width:1.0};
    p.garden.set([pit]);
    close(p.augmented.floorAt(0,0,-1.44),-.20);
    close(p.augmented.floorAt(0,-.20,-1.12),-.40);
    close(p.augmented.floorAt(0,-.40,-.70),-.60);
    const feet=new THREE.Vector3(0,0,-1.8);
    travel(p.augmented,feet,new THREE.Vector3(0,0,1),1.95);
    settle(p.augmented,feet);close(feet.y,-.60);assert.ok(feet.z>0,'entered through the steps');
    travel(p.augmented,feet,new THREE.Vector3(1,0,0),3);
    close(feet.x,2-pit.width-BODY.radius,.008);close(feet.y,-.60);
    close(p.augmented.floorAt(2.5,0,.2),0); // immediate return to original survey outside the design
  } finally{p.dispose();}
});

test('an outdoor barrier crossing an indoor room cannot block the original indoor walk',()=>{
  const p=profile();
  try{
    const wall=createFeature('wall',path([10,-1.5],[10,1.5]));
    wall.height=1.2;p.garden.set([wall]);
    const a=new THREE.Vector3(9.4,0,0),original=a.clone(),east=new THREE.Vector3(1,0,0);
    travel(p.survey,original,east,1.2);travel(p.augmented,a,east,1.2);
    close(a.x,original.x);close(a.y,original.y);
  }finally{p.dispose();}
});
