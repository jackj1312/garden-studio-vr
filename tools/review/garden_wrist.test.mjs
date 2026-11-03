/* Controller rays, real Three transforms and the public wrist adapter; no GPU or server required. */
import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../../assets/vendor/three/build/three.module.js';

const wristText = [];
const ink = { measureText: s => ({ width: s.length * 13 }), fillRect(x,y,w,h) {
  if (x === 0 && y === 0 && w === 704 && h === 816) wristText.length = 0;
}, strokeRect() {}, fillText(s) { wristText.push(s); }, drawImage() {} };
globalThis.document = {
  addEventListener() {},
  createElement() { return { width: 0, height: 0, getContext: () => ink }; },
};
globalThis.window = { addEventListener() {} };
const { createGardenWrist } = await import('../../src/garden/wrist.js');
const drawing = await import('../../src/garden/drawing.mjs');

function fixture(bird, selected = null) {
  const scene = new THREE.Scene(), rig = new THREE.Group(), camera = new THREE.PerspectiveCamera();
  rig.position.set(3.8, -.23, -5.7); rig.rotation.y = -.41; scene.add(rig);
  camera.position.set(.03, 1.62, -.08); rig.add(camera);
  const left = new THREE.Group(); left.position.set(-.24, 1.21, -.30); rig.add(left);
  const s = { active: true, bird, tool: 'select', kind: 'patio', method: 'auto', selected,
    objects: selected ? [selected] : [], dirty: false, saving: false, undo: false, redo: false, status: '', conflict: false };
  const acts = [];
  const wrist = createGardenWrist({ THREE, scene, camera, state: () => s,
    action(name, value) {
      acts.push([name, value]);
      if (name === 'view') s.bird = !s.bird;
      if (['kind','method','tool'].includes(name)) s[name] = value;
      if (name === 'field' && s.selected) s.selected = { ...s.selected, [value.key]: value.value };
    },
    bounds: () => ({ x0: -2, x1: 8, z0: -7, z1: 9 }),
    planImage: () => ({ width: 500, height: 800 }),
  });
  wrist.update(left, true, true);
  const hand = new THREE.Vector3(.27, 1.23, -.21); rig.localToWorld(hand);
  const rayTo = point => new THREE.Ray(hand.clone(), point.clone().sub(hand).normalize());
  function pointAtButton(label) {
    const point = wrist.wristWorld(label);
    assert.ok(point, 'Missing wrist action ' + label);
    return rayTo(point);
  }
  function click(label) {
    const ray = pointAtButton(label);
    assert.ok(wrist.hitWrist(ray, true) > 0);
    wrist.hitWrist(ray, false);
  }
  return { wrist, left, s, acts, rayTo, click, pointAtButton };
}

test('tabletop round-trips site metres on the physical inclined plane from an offset right hand', () => {
  const { wrist, left, rayTo } = fixture(true);
  try {
    for (const [x,z] of [[-1.99999,-6.99999],[-1,-6],[1,2],[6,7],[7.99999,8.99999]]) {
      const display = wrist.planWorld([x,z]);
      const hit = wrist.hitPlan(rayTo(display));
      assert.ok(hit);
      assert.ok(Math.hypot(hit.point.x - x, hit.point.z - z) < 1e-8, 'metre round trip');
      assert.deepEqual(hit.normal.toArray(), [0,1,0]);
      assert.ok(hit.displayPoint.distanceTo(display) < 1e-8);
    }
    wrist.update(left, false, true);
    assert.equal(wrist.planWorld([1,2]), null);
    assert.equal(wrist.wristWorld('Home'), null);
  } finally { wrist.dispose(); }
});

test('wrist help, tool selection and whole-plot toggle use the same shared actions', () => {
  const { wrist, left, acts, click, pointAtButton } = fixture(false);
  try {
    click('How to use'); click('Next'); click('Next'); click('Previous'); click('Dismiss help');
    click('Features'); click('Patio'); click('Method'); click('Circle'); click('Home');
    const ray = pointAtButton('Bird’s-eye');
    wrist.hitWrist(ray, true); wrist.hitWrist(ray, true); wrist.hitWrist(ray, false);
    wrist.update(left, true, true);
    assert.deepEqual(acts, [['kind','patio'],['tool','draw'],['method','circle'],['tool','draw'],['view', undefined]]);
    assert.ok(wrist.planWorld([1,2]));
    click('How to use'); click('Dismiss help'); click('Standing view');
    wrist.update(left, true, true);
    assert.equal(wrist.planWorld([1,2]), null);
  } finally { wrist.dispose(); }
});


test('curve angle on the wrist keypad matches the drawing bearing', () => {
  const { angleOf } = drawing;
  const points = [[1,2], [3,4], [6,2]];
  const geometry = { type: 'curve', closed: false,
    knots: points.map(p => ({ p, in: p, out: p, mode: 'corner' })) };
  const bearing = angleOf(geometry);
  assert.ok(Math.abs(bearing) > 10);
  const pen = fixture(false, { id: 'path-1', label: 'Path', kind: 'path', width: .9,
    height: 0, level: 0, geometry });
  try {
    pen.click('Edit selection');
    pen.click('Angle ' + Number(bearing.toFixed(3)) + '°');
    pen.click('Apply');
    const last = pen.acts.at(-1);
    assert.equal(last[0], 'angle');
    assert.ok(Math.abs(last[1] - bearing) < .001);
  } finally { pen.wrist.dispose(); }
});


test('outbuilding wrist selects the catalogue tool and reads exact concave and circular slab outlines', () => {
  const knots = [[1,1],[5,1],[5,2],[3,2],[3,4],[1,4]].map(p => ({p,in:p,out:p,mode:'corner'}));
  const feature = {id:'base-1', label:'Studio slab', kind:'outbuilding-base', height:.15, level:.10,
    geometry:{type:'curve',closed:true,knots}};
  const pen = fixture(false, feature);
  try {
    pen.click('Features');
    for (let i = 0; !pen.wrist.wristWorld('Outbuilding base') && i < 3; i++) pen.click('Next');
    pen.click('Outbuilding base');
    assert.deepEqual(pen.acts.slice(-2), [['kind','outbuilding-base'],['tool','draw']]);
    pen.click('Slab measurements');
    for (const value of ['Width 4 m','Depth 3 m','Area 8 m²','Perimeter 14 m'])
      assert.ok(wristText.includes(value), value);
    assert.ok(wristText.some(t => /4 m$/.test(t) && t.includes(' · ')), 'side 1 readout');
    pen.click('Next edges');
    assert.ok(wristText.some(t => /3 m$/.test(t) && t.includes(' · ')), 'sixth side readout');
    pen.click('Slab thickness'); pen.click('0'); pen.click('.'); pen.click('2'); pen.click('2'); pen.click('Apply');
    assert.deepEqual(pen.acts.at(-1), ['field', {key:'height',value:.22}]);
    assert.equal(pen.s.selected.id, 'base-1');
    assert.equal(pen.s.selected.level, .10);
    pen.s.selected.geometry = {type:'circle',center:[2,2],radius:1.5};
    pen.click('Home'); pen.click('Slab measurements');
    assert.ok(wristText.includes('Diameter 3 m') && wristText.includes('Radius 1.5 m'));
    assert.ok(wristText.includes('Circumference · 9.425 m'));
    pen.click('Home'); pen.click('Levels & steps');
    assert.equal(pen.wrist.wristWorld('Fit steps'), null);
  } finally { pen.wrist.dispose(); }
});

test('wrist shows an in-progress slab and a partial stroke without saving either', () => {
  const pen = fixture(false);
  try {
    pen.click('Drawing tools'); pen.s.kind='outbuilding-base'; pen.s.tool='draw';
    pen.s.drawingReadout = 'Stroke 2.35 m';
    pen.click('Home'); pen.click('Drawing tools');
    assert.ok(wristText.includes('Stroke 2.35 m'));
    pen.s.draft={id:'preview',kind:'outbuilding-base',geometry:{type:'rectangle',center:[1,0],width:3,depth:2,yaw:.4}};
    pen.click('Home'); pen.click('Drawing tools');
    assert.ok(wristText.includes('Width 3 m · Depth 2 m'));
    pen.click('Slab measurements');
    assert.ok(wristText.includes('Area 6 m²') && wristText.includes('Perimeter 10 m'));
    assert.equal(pen.s.objects.length, 0);
  } finally { pen.wrist.dispose(); }
});
