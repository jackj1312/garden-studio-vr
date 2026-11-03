// The same suite runs in Node and in a browser module on the local HTTPS server.
import { KINDS, MATERIALS, PALETTES, PATTERNS, SPECIES, createFeature } from '../../src/garden/catalogue.mjs';
import { GardenStore } from '../../src/garden/store.mjs';
import { arc, circle, point, rectangle } from '../../src/garden/geometry.mjs';

const checks = [];
function test(name, run) { checks.push({ name, run }); }
function assert(value, message) { if (!value) throw new Error(message); }
function equal(a, b, message) { assert(JSON.stringify(a) === JSON.stringify(b), message); }
function throws(fn, message) {
  let issue;
  try { fn(); } catch (e) { issue = e; }
  assert(issue, message);
}
async function rejects(work, message) {
  let issue;
  try { await work; } catch (e) { issue = e; }
  assert(issue, message);
  return issue;
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const clone = structuredClone;
const reply = (status, data) => new Response(JSON.stringify(data), { status });
const patio = () => createFeature('patio', rectangle([1, 2], 3, 2));
const nursery = () => createFeature('tree', point([.2, 1]));

function endpoint() {
  const state = { revision: 0, furnishing: [{ id: 'existing-sofa' }] };
  const requests = [];
  const intercept = {};
  const fetcher = async (url, options) => {
    requests.push({ url, method: options.method, body: options.body && JSON.parse(options.body) });
    if (options.method === 'GET') {
      const snapshot = clone(state);
      if (intercept.get) await intercept.get.promise;
      return reply(200, snapshot);
    }
    const patch = JSON.parse(options.body);
    if (intercept.post) await intercept.post.promise;
    if (intercept.fail) throw new TypeError('Offline');
    if (patch.baseRevision !== state.revision) {
      return reply(409, { error: 'Layout changed', currentRevision: state.revision });
    }
    equal(Object.keys(patch).sort(), ['baseRevision', 'garden', 'section'], 'Only garden data should be posted');
    assert(patch.section === 'garden' && patch.garden.schema === 1, 'Section contract');
    state.garden = clone(patch.garden);
    state.revision++;
    return reply(200, state);
  };
  return { state, requests, fetcher, intercept };
}
const makeStore = (api, onChange) => new GardenStore({ site: 'front-garden', version: 'existing_2022', fetcher: api.fetcher, onChange });

test('all tools have usable material, pattern and planting defaults', () => {
  const expected = ['outbuilding-base','patio','path','lawn','gravel','decking','wall','retaining-wall','raised-bed','sunken-area','fire-pit','steps','fence','edging','planting-bed','plant','tree'];
  equal(Object.keys(KINDS).sort(), expected.sort(), 'Catalogue coverage');
  const ids = new Set();
  for (const [k, defaults] of Object.entries(KINDS)) {
    const g = defaults.form === 'point' ? point([1, 2]) : defaults.form === 'area' ? circle([1, 2], 1) : arc([1, 2], 2, 0, .9);
    const f = createFeature(k, g, -.231);
    assert(MATERIALS[f.material] && PATTERNS[f.pattern] && PALETTES[f.palette], 'Missing finish for ' + k);
    assert(f.coping === '' || MATERIALS[f.coping], 'Missing coping for ' + k);
    assert(f.baseY === -.231 && f.geometry !== g && !ids.has(f.id), 'Independent feature');
    ids.add(f.id);
    if (f.species) {
      const plant = SPECIES[f.species];
      assert(plant.kind === k && plant.height === f.height && plant.width === f.width && plant.botanical, 'Unusable specimen');
    }
  }
});

test('open analytic arcs may be paths but cannot be area features (F158)', () => {
  const bend = arc([0, 0], 2, 0, Math.PI / 2);
  for (const [key, value] of Object.entries(KINDS)) {
    if (value.form === 'area') throws(() => createFeature(key, bend), 'Open arc accepted as ' + key);
  }
  assert(createFeature('path', bend).geometry.type === 'arc', 'A path can follow an arc');
  const store = makeStore(endpoint());
  const p = patio();
  throws(() => store.put({ ...p, geometry: bend }), 'Store must validate an edited shape again');
  assert(!store.canUndo && !store.dirty, 'Rejected drops create no history');
});

test('copy, delete, undo and redo preserve independent IDs and exact shapes', async () => {
  const api = endpoint(), labels = [];
  const s = makeStore(api, (_, label) => labels.push(label));
  await s.load();
  const plant = nursery();
  s.put(plant, 'Plant apple');
  const copy = s.duplicate(plant.id, [1.25, -.5]);
  assert(copy.id !== plant.id && copy.species === plant.species && s.objects.length === 2, 'Independent specimen');
  equal(copy.geometry.center, [1.45, .5], 'Copy offset');
  copy.width = 99;
  s.objects[0].geometry.center[0] = 33;
  assert(s.get(plant.id).geometry.center[0] === .2 && s.get(copy.id).width !== 99, 'Detached state');
  assert(s.remove(plant.id) && !s.remove('absent'), 'Delete only the selected instance');
  s.undo(); equal(s.objects.map(f => f.id), [plant.id, copy.id], 'Undo delete');
  s.undo(); equal(s.objects.map(f => f.id), [plant.id], 'Undo copy');
  s.redo(); equal(s.objects.map(f => f.id), [plant.id, copy.id], 'Redo copy with the same ID');
  s.undo(); s.put({ ...s.get(plant.id), level: .20 });
  assert(!s.canRedo && labels.includes('Undo Copy') && api.requests.every(r => r.method === 'GET'), 'Fresh edits branch history');
  s.undo(); s.undo(); assert(!s.dirty && !s.canUndo, 'Undo all edits returns to saved state');
});

test('a curve copy translates every control point without moving the original', async () => {
  const s = makeStore(endpoint());
  await s.load();
  const curve = {
    type: 'curve', closed: false,
    knots: [{ p:[0,0], in:[0,0], out:[1,0], mode:'corner' }, { p:[3,2], in:[3,1], out:[3,2], mode:'corner' }],
  };
  const original = createFeature('path', curve);
  s.put(original);
  const copy = s.duplicate(original.id, [2,1]);
  equal(copy.geometry.knots[0].out, [3,1], 'Outgoing tangent');
  equal(copy.geometry.knots[1].in, [5,2], 'Incoming tangent');
  equal(s.get(original.id).geometry, curve, 'Source shape is intact');
});

test('only explicit saves persist and history survives a save and a clean refresh', async () => {
  const api = endpoint(), s = makeStore(api);
  await s.load();
  const p = patio();
  s.put(p); assert(await s.save(), 'Expected save acknowledgement');
  assert(s.revision === 1 && !s.dirty && s.canUndo, 'Saved baseline and history');
  equal(api.state.furnishing, [{ id: 'existing-sofa' }], 'Other layout sections survive');
  assert(api.requests[0].url === '/layout?site=front-garden&version=existing_2022', 'Site/version endpoint');
  const second = makeStore(api); await second.load();
  equal(second.objects, s.objects, 'Reload exact placement from another view');
  await s.refresh(); s.undo();
  assert(s.objects.length === 0 && s.dirty, 'Undo after persist');
  s.redo(); assert(!s.dirty && !await s.save(), 'Restoring the saved snapshot is clean');
});

test('a stale writer keeps every local edit until an explicit discard', async () => {
  const api = endpoint(), a = makeStore(api), b = makeStore(api);
  await Promise.all([a.load(), b.load()]);
  a.put(patio()); await a.save();
  const tree = nursery();
  b.put(tree);
  const conflict = await rejects(b.save(), 'Conflict was ignored');
  assert(conflict.status === 409 && conflict.currentRevision === 1 && b.revision === 0, 'Conflict revision');
  assert(b.dirty && b.canUndo && !b.saving && b.get(tree.id), 'Local edit preserved');
  assert(!await b.refresh(), 'Background refresh cannot discard edits');
  await rejects(b.load(), 'Reload discarded an unsaved draft');
  await b.load({ discard: true });
  equal(b.objects, a.objects, 'Explicit discard reloads the remote design');
  assert(!b.dirty && !b.canUndo, 'Discard drops stale history');
});

test('an offline save leaves the draft available for retry', async () => {
  const api = endpoint(), s = makeStore(api); await s.load();
  const f = patio(); s.put(f); api.intercept.fail = true;
  await rejects(s.save(), 'Offline request claimed success');
  equal([s.revision, s.objects.length, s.dirty], [0, 1, true], 'Offline draft survived');
  api.intercept.fail = false; await s.save();
  assert(api.state.garden.objects[0].id === f.id && s.revision === 1 && !s.dirty, 'Retry saves exact draft');
});

test('in-flight saves serialize explicit snapshots and preserve later edits', async () => {
  const api = endpoint(), s = makeStore(api); await s.load();
  const f = patio(), hold = deferred(); api.intercept.post = hold;
  s.put(f);
  const first = s.save();
  s.put({ ...f, level: .20 });
  const second = s.save();
  s.put({ ...f, level: .40 });
  assert(s.saving && !await s.refresh(), 'No background reload during a write');
  hold.resolve(); await Promise.all([first, second]);
  const posts = api.requests.filter(r => r.method === 'POST');
  equal(posts.map(r => [r.body.baseRevision, r.body.garden.objects[0].level]), [[0, 0], [1, .20]], 'Queued revisions and snapshots');
  assert(s.get(f.id).level === .40 && s.dirty && !s.saving, 'Late drag is still a draft');
  s.undo(); assert(!s.dirty && s.get(f.id).level === .20, 'Undo matches accepted revision');
});

test('a late GET cannot overwrite a drag or a newer load', async () => {
  const api = endpoint(), s = makeStore(api); await s.load();
  const wait = deferred(); api.intercept.get = wait;
  const reading = s.refresh(), fresh = patio();
  s.put(fresh); wait.resolve();
  assert(!await reading && s.get(fresh.id) && s.dirty, 'Late refresh overwrote local geometry');
  const wait2 = deferred(); api.intercept.get = wait2;
  const earlier = s.load({ discard: true });
  api.intercept.get = null;
  const remote = nursery();
  api.state.garden = { schema: 1, objects: [remote] }; api.state.revision = 1;
  await s.load({ discard: true }); wait2.resolve();
  assert(!await earlier && s.get(remote.id) && s.revision === 1, 'Late read rewound accepted revision');
});

export async function runGardenHistoryTests() {
  const passed = [];
  for (const entry of checks) { await entry.run(); passed.push(entry.name); }
  return passed;
}

if (globalThis.process?.versions?.node) {
  const { test: nodeTest } = await import('node:test');
  for (const { name, run } of checks) nodeTest(name, run);
}
