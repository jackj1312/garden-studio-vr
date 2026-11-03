import test from 'node:test';
import assert from 'node:assert/strict';
import {createDrawing} from '../../src/garden/drawing.mjs';
import {GardenStore} from '../../src/garden/store.mjs';
import {outlineMeasurements} from '../../src/garden/geometry.mjs';

function tools() {
  const store=new GardenStore({site:'test',version:'approved'});
  const draw=createDrawing({store:()=>store,pick:()=>null,ground:()=>-.231,changed(){}});
  draw.command('kind','outbuilding-base');return {draw,store};
}
const p=(x,z)=>({x,y:-.231,z});
test('click a measured concave base, preview the next corner, finish and retain the same ID',()=>{
  const {draw,store}=tools();
  for(const q of [[0,0],[4,0],[4,2]])draw.begin(p(...q));
  const id=draw.draft.id;
  draw.hover(p(2,2));assert.match(draw.readout(),/2.000 m/);
  for(const q of [[2,2],[2,3],[0,3]])draw.begin(p(...q));
  const live=outlineMeasurements(draw.draft.geometry);assert.equal(store.objects.length,0);
  draw.finishCorners();const f=store.get(id);assert(f);assert.equal(f.material,'concrete');
  assert.equal(f.height,.15);assert.equal(f.level,.1);assert.equal(f.geometry.knots.length,6);
  const m=outlineMeasurements(f.geometry);assert.equal(m.area,10);assert.equal(m.perimeter,14);assert.deepEqual(m,live);
  draw.command('field',{key:'height',value:.24});assert.equal(store.get(id).height,.24);
  draw.command('undo');assert.equal(store.get(id).height,.15);draw.command('redo');assert.equal(store.get(id).height,.24);
});
test('an outward circle shows its diameter while drawing and the committed slab keeps that radius and ID',()=>{
  const {draw,store}=tools();draw.command('method','circle');draw.begin(p(1,2));draw.move(p(3,2));
  const id=draw.draft.id;assert.equal(outlineMeasurements(draw.draft.geometry).radius,2);
  draw.end();const f=store.get(id);assert.equal(f.geometry.radius,2);
  assert.throws(()=>store.put({...f,height:0}),/positive/);
});

