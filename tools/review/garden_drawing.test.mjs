import assert from 'node:assert/strict';
import test from 'node:test';
import { createDrawing, angleOf } from '../../src/garden/drawing.mjs';
import { createFeature, SPECIES } from '../../src/garden/catalogue.mjs';
import { GardenStore } from '../../src/garden/store.mjs';
import { circle, point, rectangle, handlesOf, measureGeometry } from '../../src/garden/geometry.mjs';

const eps = (a, b, tol = 1e-6) => assert.ok(Math.abs(a-b) < tol, `${a} vs ${b}`);
const loc = ([x,z],y=0) => ({x,y,z});
const knot = p => ({p:[...p], in:[...p], out:[...p], mode:'corner'});
function workspace(existing) {
  const store = existing ?? new GardenStore({ site:'garden-fixture', version:'v1' });
  let picked = null;
  const draw = createDrawing({ store:()=>store, pick:()=>picked, ground:()=>-.231, changed:()=>{} });
  return { store, draw, pick:f=>{ picked=f?.id ?? null; } };
}
function stroke(w, kind, method, pts) {
  w.draw.command('kind',kind); w.draw.command('method',method);
  w.draw.begin(loc(pts[0]), {free:true});
  for (const p of pts.slice(1)) w.draw.move(loc(p));
  w.draw.end();
  return w.store.get(w.draw.state.selectedId);
}

test('circle, rectangle and square preserve exact dimensions and one gesture per history entry', () => {
  const w=workspace();
  const c=stroke(w,'patio','circle',[[1,1],[1.6,1.8],[2.2,2.6]]);
  assert.deepEqual(c.geometry,circle([1,1],2)); eps(c.baseY,-.231);
  const rect=stroke(w,'lawn','rectangle',[[2,3],[3,4],[5,7]]);
  assert.deepEqual(rect.geometry,rectangle([3.5,5],3,4));
  const sq=stroke(w,'gravel','square',[[0,0],[-1,.3],[-2,.5]]);
  assert.deepEqual(sq.geometry,rectangle([0,0],4,4));
  assert.equal(w.store.objects.length,3);
  w.draw.command('undo'); assert.deepEqual(w.store.objects.map(f=>f.id),[c.id,rect.id]);
  w.draw.command('undo'); assert.deepEqual(w.store.objects.map(f=>f.id),[c.id]);
  w.draw.command('redo'); assert.deepEqual(w.store.get(rect.id).geometry,rect.geometry);
});

test('sampled quarter-turn pen stroke fits one analytic arc and retains its radius', () => {
  const w=workspace();
  const points=Array.from({length:41},(_,i)=>{
    const t=i*Math.PI/80;
    return [1+2*Math.cos(t),-.5+2*Math.sin(t)];
  });
  const path=stroke(w,'path','arc',points);
  assert.equal(path.geometry.type,'arc');eps(path.geometry.radius,2,.0001);
  eps(path.geometry.sweepAngle,Math.PI/2,.0001);eps(measureGeometry(path.geometry).perimeter,Math.PI,.0001);
  w.draw.command('angle',45);eps(angleOf(w.store.get(path.id).geometry),45);
  assert.equal(w.store.objects.length,1);
});

test('drawing click corners keeps a transient outline until finish or a closing click', () => {
  const w=workspace();w.draw.command('kind','patio');w.draw.command('method','corners');
  const click=p=>{w.draw.begin(loc(p),{free:true});w.draw.end();};
  click([0,0]);click([3,0]);w.draw.command('finish');
  assert.equal(w.store.objects.length,0);assert.ok(w.draw.state.status);
  click([3,2]);click([0,2]);
  assert.equal(w.draw.corners.length,4);assert.equal(w.store.canUndo,false);
  click([.02,.01]);
  const g=w.store.objects[0].geometry;assert.equal(g.type,'curve');assert.equal(g.closed,true);
  assert.ok(g.knots.every(k=>k.mode==='corner'));eps(measureGeometry(g).area,6);
  w.draw.command('undo');assert.equal(w.store.objects.length,0);assert.equal(w.store.canUndo,false);
  w.draw.command('redo');w.draw.command('kind','path');w.draw.command('method','corners');
  click([6,0]);click([9,0]);w.draw.command('finish');
  assert.equal(w.store.objects[1].geometry.closed,false);eps(measureGeometry(w.store.objects[1].geometry).perimeter,3);
});

test('an unfinished freehand area or cancelled pointer leaves no fragment in the layout', () => {
  const w=workspace();stroke(w,'patio','auto',[[0,0],[2,0],[3,2],[1,3]]);
  assert.equal(w.store.objects.length,0);assert.ok(w.draw.state.status);assert.equal(w.store.canUndo,false);
  w.draw.command('kind','decking');w.draw.command('method','circle');
  w.draw.begin(loc([5,5]));w.draw.move(loc([7,5]));
  assert.ok(w.draw.draft);w.draw.cancel();w.draw.end();
  assert.equal(w.draw.draft,null);assert.equal(w.store.objects.length,0);assert.equal(w.store.canUndo,false);
  w.draw.command('method','corners');w.draw.begin(loc([0,0]));w.draw.begin(loc([2,0]));
  w.draw.command('cancel');w.draw.command('finish');
  assert.equal(w.draw.corners.length,0);assert.equal(w.store.objects.length,0);
});

test('inspectors change materials, levels, coping and step geometry without losing the source shape', () => {
  const w=workspace(),f=stroke(w,'sunken-area','rectangle',[[0,0],[3,2]]);
  const set=(key,value)=>w.draw.command('field',{key,value});
  set('material','slate');set('pattern','grid');set('palette','cool');set('coping','stone');set('level',-.48);
  w.draw.command('steps');
  let s=w.store.get(f.id);assert.deepEqual(s.steps,{at:0,count:3,width:1});assert.equal(s.level,-.48);
  set('steps',{at:.40,count:4,width:1.20});w.draw.command('angle',35);w.draw.command('size',{width:4.20,depth:2.30});
  s=w.store.get(f.id);eps(angleOf(s.geometry),35);eps(s.geometry.width,4.20);eps(s.geometry.depth,2.30);assert.deepEqual(s.steps,{at:.40,count:4,width:1.20});
  const old=structuredClone(s);
  set('material','not-in-catalogue');assert.equal(w.store.get(f.id).material,'slate');assert.ok(w.draw.state.status);
  w.draw.command('copy');const copy=w.store.get(w.draw.state.selectedId);assert.notEqual(copy.id,f.id);
  eps(copy.geometry.center[0],old.geometry.center[0]+.35);eps(copy.geometry.center[1],old.geometry.center[1]+.35);
  assert.deepEqual(w.store.get(f.id),old);w.draw.command('delete');assert.deepEqual(w.store.get(f.id),old);
  w.draw.command('undo');assert.deepEqual(w.store.get(copy.id),copy);
});

test('plants and trees are individual specimens and use the selected stock dimensions', () => {
  const w=workspace(),f=stroke(w,'plant','auto',[[1,2]]);
  assert.equal(f.geometry.type,'point');assert.deepEqual(f.geometry.center,[1,2]);
  w.draw.command('field',{key:'species',value:'fern'});
  const s=w.store.get(f.id);assert.equal(s.width,SPECIES.fern.width);assert.equal(s.height,SPECIES.fern.height);
  w.draw.command('copy');const copy=w.store.get(w.draw.state.selectedId);
  assert.equal(copy.species,'fern');assert.notEqual(copy.id,f.id);
  const tree=stroke(w,'tree','circle',[[9,2]]);
  w.draw.command('field',{key:'species',value:'maple'});assert.equal(w.store.get(tree.id).height,SPECIES.maple.height);
});

test('the nearest handle wins inside a shared tolerance and a selected handle beats another body', () => {
  const w=workspace();const disk=createFeature('patio',circle([0,0],.18)),tree=createFeature('tree',point([.2,0]));
  w.store.put(disk);w.store.put(tree);w.pick(tree);w.draw.command('select',disk.id);
  // Both centre and radius are within 250 mm, but the radius is only 10 mm away.
  w.draw.begin(loc([.17,0]),{tolerance:.25,free:true});w.draw.move(loc([.36,0]));w.draw.end();
  const g=w.store.get(disk.id).geometry;eps(g.radius,.36);assert.deepEqual(g.center,[0,0]);
  assert.deepEqual(w.store.get(tree.id).geometry.center,[.2,0]);
});

test('a coincident interior knot can be edited independently of the whole-curve move handle', () => {
  const w=workspace(),g={type:'curve',closed:false,knots:[[0,0],[2,0],[4,0]].map(knot)};
  const path=createFeature('path',g);w.store.put(path);w.draw.command('select',path.id);
  w.draw.begin(loc([2,0]),{free:true});w.draw.move(loc([2,1]));w.draw.end();
  assert.deepEqual(w.store.get(path.id).geometry.knots.map(k=>k.p),[[0,0],[2,1],[4,0]]);
});

test('release on an invalid resize preserves the original instead of committing a stale preview', () => {
  const w=workspace(),original=createFeature('patio',rectangle([0,0],2,2));w.store.put(original);w.draw.command('select',original.id);
  const corners=handlesOf(original.geometry).filter(h=>h.kind==='corner');
  w.draw.begin(loc(corners[0].point),{free:true});w.draw.move(loc([-1.5,-1.5]));
  assert.ok(w.draw.draft);w.draw.move(loc(corners[2].point));w.draw.end();
  assert.deepEqual(w.store.get(original.id).geometry,original.geometry);
  assert.ok(w.draw.state.status,'The invalid release must be explained');
  w.store.undo();assert.equal(w.store.get(original.id),undefined,'Only the original addition should be in history');
});

test('a handle can recover within the same gesture after an invalid intermediate position', () => {
  const w=workspace(),f=createFeature('patio',rectangle([0,0],2,2));w.store.put(f);w.draw.command('select',f.id);
  w.draw.begin(loc([-1,-1]),{free:true});w.draw.move(loc([1,1]));
  assert.equal(w.draw.draft,null);assert.ok(w.draw.state.status);
  w.draw.move(loc([-2,-2]));w.draw.end();
  assert.deepEqual(w.store.get(f.id).geometry,rectangle([-.5,-.5],3,3));
  assert.equal(w.draw.state.status,'');w.draw.command('undo');assert.deepEqual(w.store.get(f.id),f);
});

test('level drag, selection and undo are shared between bird and standing controllers', () => {
  const bird=workspace();const f=stroke(bird,'decking','rectangle',[[0,0],[3,2]]);
  const standing=workspace(bird.store);standing.pick(f);standing.draw.command('tool','level');
  standing.draw.begin(loc([.8,.6]),{screenY:180});standing.draw.move(loc([.8,.6]),{screenY:150});
  assert.equal(bird.store.get(f.id).level,.12,'Unreleased level is only a preview');
  standing.draw.end();eps(bird.store.get(f.id).level,.42);
  bird.draw.command('undo');eps(standing.store.get(f.id).level,.12);
  standing.draw.command('redo');eps(bird.store.get(f.id).level,.42);
  standing.draw.command('field',{key:'level',value:-.10});bird.draw.command('undo');eps(standing.store.get(f.id).level,.42);
});
