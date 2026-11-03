import { createFeature } from '../../src/garden/catalogue.mjs';
import { createDrawing } from '../../src/garden/drawing.mjs';
import { circle, outlineMeasurements } from '../../src/garden/geometry.mjs';
import { createGardenPanel } from '../../src/garden/panel.js';
import { GardenStore } from '../../src/garden/store.mjs';

const footprint = [[0,0], [4,0], [4,2], [1,2], [1,3], [0,3]];
const corners = points => ({ type:'curve', closed:true, knots:points.map(p => ({ p:[...p], in:[...p], out:[...p], mode:'corner' })) });
const check = (value, message) => { if (!value) throw Error(message); };
const equal = (a,b,message) => check(JSON.stringify(a) === JSON.stringify(b), message);
const position = ([x,z]) => ({ x, y:0, z });

function cornerGesture() {
  const store = new GardenStore({ site:'slab-fixture', version:'v1' });
  const draw = createDrawing({ store:()=>store, pick:()=>null, ground:()=>-.231, changed:()=>{} });
  draw.command('kind','outbuilding-base');
  check(draw.state.method === 'corners','Base should start in click-corners mode');
  let previewId;
  for (const [i,p] of footprint.entries()) {
    draw.begin(position(p),{free:true});
    if (i === 1) check(draw.readout().includes('4.000 m'),'Readout measures the first open side');
    if (i > 1) {
      previewId ??= draw.draft.id;
      check(draw.draft.id === previewId,'Closed previews should keep one base ID');
    }
    check(!store.canUndo && !store.objects.length,'Growing the outline must not add history');
  }
  draw.command('finish');
  const f = store.get(previewId), m = outlineMeasurements(f.geometry);
  check(f.id === draw.state.selectedId && f.baseY === -.231,'Finishing retains the measured preview and survey datum');
  equal(f.geometry,corners(footprint),'Source corners survive');
  equal([m.width,m.depth,m.area,m.perimeter],[4,3,9,14],'Concave base extents, area and perimeter');
  equal(m.segments.map(s=>s.length),[4,2,3,1,1,3],'Each actual side is measured separately');
  equal([f.material,f.pattern,f.coping,f.height,f.level],['concrete','plain','',.15,.10],'Default concrete, thickness and top offset');
  draw.command('field',{key:'level',value:-.075});
  draw.command('field',{key:'height',value:.225});
  draw.command('field',{key:'material',value:'brick'});
  check(store.get(previewId).material === 'concrete','Base cannot change to brick');
  draw.command('copy');
  const copy=store.get(draw.state.selectedId);
  check(copy.id !== previewId,'Copy needs its own structural reference');
  check(copy.geometry.knots[0].p.every(v=>Math.abs(v-.35)<1e-7),'Copy translates the base by 0.350 m on both axes');
  equal([copy.level,copy.height],[-.075,.225],'Copy retains independent exact slab levels');
  draw.command('undo'); check(!store.get(copy.id) && store.get(previewId),'Undo removes only the copy');
  draw.command('redo'); check(store.get(copy.id),'Redo restores the exact ID');
}

function circleGesture() {
  const store = new GardenStore({ site:'slab-fixture', version:'v1' });
  const draw = createDrawing({ store:()=>store, pick:()=>null, ground:()=>0, changed:()=>{} });
  draw.command('kind','outbuilding-base'); draw.command('method','circle');
  draw.begin(position([4,2]),{free:true}); draw.move(position([5,2]));
  const id=draw.draft.id;
  draw.move(position([5.5,2]));
  const m=outlineMeasurements(draw.draft.geometry);
  check(draw.draft.id === id && m.radius === 1.5 && m.segments.length === 1,'Circle preserves one ID, radius and curved perimeter');
  draw.end();
  equal(store.get(id).geometry,circle([4,2],1.5),'Circle geometry remains analytic on release');
}

async function curvedRoundTrip() {
  const saved={revision:0,garden:{schema:1,objects:[]}};
  const fetcher=async (_url,opts)=>{
    if (opts.method === 'POST') { saved.garden=JSON.parse(opts.body).garden; saved.revision++; }
    return Response.json(saved);
  };
  const design=()=>new GardenStore({site:'slab-fixture',version:'v1',fetcher});
  const store=design(); await store.load();
  const draw=createDrawing({store:()=>store,pick:()=>null,ground:()=>-.231,changed:()=>{}});
  draw.command('kind','outbuilding-base'); draw.command('method','curve');
  for (let i=0;i<=40;i++) {
    const a=2*Math.PI*i/40, sample=position([3*Math.cos(a),1.6*Math.sin(a)]);
    if (i===0) draw.begin(sample,{free:true}); else draw.move(sample);
  }
  const id=draw.draft.id; draw.end();
  const original=store.get(id), m=outlineMeasurements(original.geometry);
  check(original.geometry.closed && original.geometry.knots.some(k=>k.mode==='smooth'),'Freehand slab has a smooth editable boundary');
  check(m.segments.every(s=>s.label.startsWith('Curve ')),'Curved sides are identified individually');
  await store.save(); const second=design(); await second.load();
  equal(second.get(id),original,'Saved footprint, original control handles and slab heights survive reopen');
  equal(outlineMeasurements(second.get(id).geometry),m,'Reopened freehand slab reproduces the same measured boundary');
}

/** May run directly in a local HTTPS browser module, including the phone and iPad profiles. */
export function runSlabPanelChecks() {
  const f=createFeature('outbuilding-base',corners(footprint),-.231);
  const calls=[];
  const panel=createGardenPanel({ action:(name,value)=>calls.push([name,value]) });
  const root=[...document.querySelectorAll('[data-garden-panel]')].at(-1);
  const find=s=>root.querySelector(s);
  const field=k=>find('[data-field="'+k+'"]');
  const reference=find('[data-cmd=base-reference]');
  const metrics=()=>Object.fromEntries([...root.querySelectorAll('.gd-slab-summary > div')].map(pair=>[pair.firstChild.textContent,pair.lastChild.textContent]));
  const state={active:true,bird:true,kind:f.kind,method:'corners',tool:'select',selected:f,objects:[f],site:'slab-fixture',version:'v1',dirty:false,saving:false,undo:false,redo:false,status:'',conflict:false};
  try {
    panel.update(state);
    check(field('kind').querySelector('optgroup[label=Structures] [value=outbuilding-base]'),'Base is available in Structures');
    check(!find('[data-base-measurements]').hidden && !reference.hidden,'Committed base shows its reference action');
    check(find('.gd-base-id code').textContent === f.id,'Inspector shows the exact saved ID');
    const selected=metrics();
    equal([selected.Width,selected.Depth,selected.Area,selected.Perimeter],['4.000 m','3.000 m','9.000 m²','14.000 m'],'Metric summary of concave base');
    equal([...root.querySelectorAll('.gd-slab-edges tbody td')].map(e=>e.textContent),['4.000 m','2.000 m','3.000 m','1.000 m','1.000 m','3.000 m'],'Table follows real edges in order');
    check(field('material').disabled && field('material').value === 'concrete' && field('coping').disabled && !field('coping').value,'Fixed concrete and no coping');
    check(!field('pattern') && !find('[data-cmd=steps]'),'No decorative pattern or attached steps on this slab');
    reference.click(); check(calls.at(-1)?.[0] === 'base-reference','Copy action requests the current reference');
    for (const [key,value] of [['height',.215],['level',-.08]]) {
      const input=field(key);
      input.value=String(value); input.dispatchEvent(new Event('change',{bubbles:true}));
      equal(calls.at(-1),['field',{key,value}],'Editable '+key+' sends a numeric metre value');
    }
    panel.update({...state,selected:{...f,height:.215,level:-.08}});
    const edited=metrics();
    equal([edited['Slab thickness'],edited['Slab top offset']],['0.215 m','-0.080 m'],'Vertical dimensions update without a geometry change');
    panel.update({...state,tool:'draw',selected:null,objects:[],draft:null,drawingId:f.id,drawingReadout:'Last segment 4.000 m'});
    check(find('.gd-slab-readout').textContent === 'Last segment 4.000 m' && find('.gd-slab-summary').hidden,'Open contour shows its live readout');
    check(find('.gd-base-id code').textContent === f.id,'The reserved structural ID appears from the first corner');
    const round={...f,geometry:circle([2,2],1.5)};
    panel.update({...state,tool:'draw',selected:null,objects:[],draft:round,drawingReadout:'X 3.500 m'});
    check(metrics().Radius === '1.500 m' && find('.gd-slab-edges tbody th').textContent === 'Circumference','Round preview shows radius and circumference');
    check(find('.gd-base-id code').textContent === f.id && reference.hidden,'Draft carries its stable ID and hides copy until complete');
    panel.update({...state,selected:round,objects:[round]});
    check(find('.gd-base-id code').textContent === f.id && !reference.hidden,'Finishing the same ID enables its reference');
    panel.update({...state,tool:'draw',kind:'patio',selected:null,draft:createFeature('patio',circle([0,0],1)),objects:[]});
    check(find('[data-base-measurements]').hidden,'Leaving the base tool hides its dimensions');
  } finally { panel.dispose(); }
  return 'Passed selected, edited, open, circle preview and committed base inspector states';
}

if (globalThis.process?.versions?.node) {
  const { test } = await import('node:test');
  test('a growing concave slab keeps one physical reference and its exact sides and levels',cornerGesture);
  test('a circular slab keeps an analytic radius through preview and release',circleGesture);
  test('a closed freehand slab reopens with every curved edge, control point and level',curvedRoundTrip);
}
