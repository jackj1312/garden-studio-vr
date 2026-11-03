import { KINDS, MATERIALS, PALETTES, PATTERNS, SPECIES } from './catalogue.mjs';
import { centerOf, measureGeometry, outlineMeasurements, transformGeometry } from './geometry.mjs';
import { angleOf } from './drawing.mjs';

const methods = {
  auto: 'Auto-fit stroke', straight: 'Straight runs', curve: 'Smooth curve', arc: 'Circular arc',
  circle: 'Circle', rectangle: 'Rectangle', square: 'Square', corners: 'Click corners',
};
const groups = {
  Surfaces: ['patio','path','lawn','gravel','decking'],
  Structures: ['outbuilding-base','wall','retaining-wall','raised-bed','sunken-area','fire-pit','steps','fence','edging'],
  Planting: ['planting-bed','plant','tree'],
};
const precise = new Intl.NumberFormat('en-GB', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
const numberFormat = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 2 });
const display = n => Number.isFinite(n) ? String(Math.round(n * 1000) / 1000) : '';

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function option(parent, value, text) {
  const node = el('option', '', text);
  node.value = value;
  parent.append(node);
}
function button(text, cmd, val = '') {
  const node = el('button', '', text);
  node.type = 'button';
  node.dataset.cmd = cmd;
  node.dataset.val = val;
  return node;
}
function section(parent, title) {
  const node = el('section', 'gd-section');
  node.append(el('h3', 'gd-heading', title));
  parent.append(node);
  return node;
}
function box(parent) {
  const grid = el('div', 'gd-fields');
  parent.append(grid);
  return grid;
}
function field(parent, key, caption, { choices, type = 'number', unit, min, max, wide = false } = {}) {
  const label = el('label', wide ? 'gd-field gd-wide' : 'gd-field');
  label.append(el('span', 'gd-caption', caption));
  const wrap = el('span', 'gd-input-wrap');
  const input = el(choices ? 'select' : 'input');
  if (choices) {
    for (const [key, value] of Object.entries(choices)) option(input, key, typeof value === 'string' ? value : value.label);
  } else {
    input.type = type;
    if (type === 'number') {
      input.step = 'any';
      input.inputMode = 'decimal';
      if (min !== undefined) input.min = String(min);
      if (max !== undefined) input.max = String(max);
    } else input.maxLength = 160;
  }
  input.dataset.field = key;
  wrap.append(input);
  if (unit) { wrap.classList.add('gd-unit'); wrap.append(el('span', 'gd-unit-label', unit)); }
  label.append(wrap); parent.append(label);
  return input;
}
export function createGardenPanel({ action }) {
  if (!document.querySelector('link[data-garden-panel-style]')) {
    const link = el('link');
    link.rel = 'stylesheet'; link.href = new URL('./garden.css', import.meta.url).href;
    link.dataset.gardenPanelStyle = '';
    document.head.append(link);
  }
  const root = el('aside', 'gd-panel');
  root.dataset.gardenPanel = '';
  root.setAttribute('aria-label', 'Garden design tools');
  root.hidden = true;
  root.innerHTML = `
    <header class="gd-header">
      <div class="gd-brand"><span class="gd-kicker">Garden Studio</span><h2>Garden design</h2><span class="gd-context"></span></div>
      <div class="gd-head-actions"><a class="gd-return-house" href="/preview/">Furnished house</a>
        <button type="button" class="gd-help" data-editor-help="garden">How to use</button>
        <button type="button" class="gd-collapse" data-cmd="collapse" aria-expanded="true" aria-label="Collapse garden tools" title="Collapse tools">Minimise</button>
        <button type="button" data-cmd="close" aria-label="Close garden design" title="Close garden design">×</button>
      </div>
    </header>
    <div class="gd-walk-hint"><span class="gd-mouse-walk">WASD to walk · Mouse to look · Esc releases · Tab shows tools</span><span class="gd-touch-walk">Use the thumb controls to walk and look. Tap Show tools to draw again.</span></div>
    <div class="gd-body"><p><a href="/plan/">Wi-Fi room planner</a> · <a data-mac-furniture href="https://127.0.0.1:8450/house.html?site=house&amp;version=approved_2b&amp;mode=review&amp;edit=1">3D furniture editor on studio Mac</a></p>
      <div class="gd-view-row">
        <button type="button" data-cmd="vr" hidden>Enter VR</button>
        <div class="gd-segment gd-views" aria-label="Garden view">
          <button type="button" data-cmd="view" data-val="bird">Bird’s-eye</button>
          <button type="button" data-cmd="view" data-val="stand">Standing</button>
        </div>
      </div>
      <section class="gd-section gd-draw-section">
        <h3 class="gd-heading">Tools</h3>
        <div class="gd-segment gd-modes" aria-label="Edit mode">
          <button type="button" data-cmd="tool" data-val="select">Select</button>
          <button type="button" data-cmd="tool" data-val="draw">Draw</button>
          <button type="button" data-cmd="tool" data-val="level">Level</button>
        </div>
        <div class="gd-fields gd-tool-fields"></div>
        <div class="gd-drawing-actions"></div>
      </section>
      <section class="gd-section gd-slab" data-base-measurements hidden aria-label="Outbuilding base measurements">
        <div class="gd-section-heading"><h3 class="gd-heading">Base measurements</h3><span class="gd-slab-state"></span></div>
        <p class="gd-slab-readout"></p>
        <dl class="gd-slab-summary"></dl>
        <details class="gd-slab-edges" open><summary>Edges</summary>
          <table aria-label="Measured lengths of the base edges"><thead><tr><th scope="col">Edge</th><th scope="col">Length</th></tr></thead><tbody></tbody></table>
        </details>
        <div class="gd-base-id"><span class="gd-caption">Base ID</span><code></code></div>
        <button type="button" class="gd-reference" data-cmd="base-reference">Copy base reference</button>
      </section>
      <section class="gd-section gd-selection">
        <div class="gd-section-heading"><h3 class="gd-heading">Objects</h3><span class="gd-count"></span></div>
        <select class="gd-object-list" aria-label="Select a garden object"></select>
        <div class="gd-inspector"></div>
      </section>
      <div class="gd-extra"><button type="button" data-cmd="import">Use a proposal mark</button></div>
    </div>
    <footer class="gd-footer">
      <div class="gd-status" role="status"><span class="gd-dot"></span><span class="gd-status-text"></span></div>
      <div class="gd-save-row">
        <button type="button" data-cmd="undo">Undo</button><button type="button" data-cmd="redo">Redo</button>
        <button type="button" class="gd-primary" data-cmd="save">Save garden</button>
      </div>
      <button type="button" class="gd-reload" data-cmd="reload" hidden>Discard edits and reload saved garden</button>
    </footer>`;
  document.body.append(root);
  const find = selector => root.querySelector(selector);
  const context = find('.gd-context'), status = find('.gd-status-text'), list = find('.gd-object-list');
  const inspector = find('.gd-inspector'), count = find('.gd-count');
  navigator.xr?.isSessionSupported('immersive-vr').then(ok => { find('[data-cmd=vr]').hidden=!ok; }).catch(()=>{});
  const slabCard = find('[data-base-measurements]');
  const slabSummary = find('.gd-slab-summary'), edgeList = find('.gd-slab-edges');
  const edgeBody = edgeList.querySelector('tbody'), slabId = find('.gd-base-id code');
  let measuredKey = '';
  const toolFields = find('.gd-tool-fields');
  const kind = field(toolFields, 'kind', 'Object type', { choices: {} });
  for (const [groupName, ids] of Object.entries(groups)) {
    const group = el('optgroup'); group.label = groupName;
    for (const key of ids) option(group, key, KINDS[key].label);
    kind.append(group);
  }
  const method = field(toolFields, 'method', 'Drawing method', { choices: methods });
  const drawActions = find('.gd-drawing-actions');
  drawActions.append(button('Finish shape', 'finish'), button('Cancel drawing', 'cancel'));
  const collapse = find('[data-cmd=collapse]');
  const siteQuery = new URLSearchParams(location.search);
  let state, inspectorKey = '', listKey = '';

  function updateSlab() {
    const preview = state.draft?.kind === 'outbuilding-base' ? state.draft : null;
    const picked = state.selected?.kind === 'outbuilding-base' ? state.selected : null;
    const drawing = state.tool === 'draw' && state.kind === 'outbuilding-base';
    const base = preview || picked;
    slabCard.hidden = !base && !drawing;
    if (slabCard.hidden) return;
    find('.gd-slab-state').textContent = drawing ? 'Drawing' : preview ? 'Editing' : 'Selected';
    find('.gd-slab-readout').textContent = state.drawingReadout || (base ? '' : 'Draw a closed footprint to measure the base.');
    slabId.textContent = base?.id || state.drawingId || 'Assigned on finish';
    find('[data-cmd=base-reference]').hidden = !picked || !!preview;
    const key = base ? JSON.stringify([base.geometry, base.height, base.level]) : '';
    if (key !== measuredKey) {
      measuredKey = key;
      slabSummary.replaceChildren(); edgeBody.replaceChildren();
      if (base) {
        const m = outlineMeasurements(base.geometry);
        const totals = [['Width',m.width,'m'],['Depth',m.depth,'m'],['Area',m.area,'m²'],['Perimeter',m.perimeter,'m']];
        if (Number.isFinite(m.radius)) totals.push(['Radius',m.radius,'m']);
        totals.push(['Slab thickness',base.height,'m'],['Slab top offset',base.level,'m']);
        for (const [label, value, unit] of totals) {
          const pair = el('div');
          pair.append(el('dt','',label), el('dd','',precise.format(value) + ' ' + unit));
          slabSummary.append(pair);
        }
        for (const segment of m.segments) {
          const row = el('tr'), label = el('th','',segment.label);
          label.scope = 'row';
          row.append(label, el('td','',precise.format(segment.length) + ' m'));
          edgeBody.append(row);
        }
      }
    }
    slabSummary.hidden = !base;
    edgeList.hidden = !base;
  }

  function setupInspector(f) {
    inspector.replaceChildren();
    if (!f) {
      inspector.append(el('p', 'gd-hint', 'Select an object in the garden or choose one above to edit it.'));
      return;
    }
    const intro = el('div', 'gd-object-heading');
    intro.append(el('span', 'gd-kind-tag', KINDS[f.kind].label), el('span', 'gd-metrics'));
    inspector.append(intro);
    const details = box(inspector);
    field(details, 'label', 'Name', { type: 'text', wide: true });
    if (f.kind === 'tree' || f.kind === 'plant') {
      const choices = Object.fromEntries(Object.entries(SPECIES).filter(([, s]) => s.kind === f.kind));
      field(details, 'species', 'Species', { choices, wide: true });
    }
    const dims = box(section(inspector, 'Geometry'));
    if (f.geometry.type === 'arc' || f.geometry.type === 'circle') {
      field(dims, 'radius', 'Radius', { unit: 'm', min: .001 });
    } else if (f.geometry.type !== 'point') {
      field(dims, 'sizeX', 'Plan width', { unit: 'm', min: .001 });
      field(dims, 'sizeZ', 'Plan depth', { unit: 'm', min: .001 });
    }
    if (f.geometry.type !== 'circle') field(dims, 'angle', 'Rotation', { unit: '°' });
    field(dims, 'positionX', 'Centre X', { unit: 'm' });
    field(dims, 'positionZ', 'Centre Z', { unit: 'm' });
    const elevation = box(section(inspector, 'Level and construction'));
    const isBase = f.kind === 'outbuilding-base';
    field(elevation, 'level', isBase ? 'Slab top offset' : 'Level offset', { unit: 'm', min: -1000, max: 1000 });
    const isPlant = f.kind === 'plant' || f.kind === 'tree';
    if (f.width > 0 || KINDS[f.kind].width > 0) field(elevation, 'width', isPlant ? 'Spread' : 'Width', { unit: 'm', min: .001 });
    if (f.height > 0 || KINDS[f.kind].height > 0) field(elevation, 'height', isBase ? 'Slab thickness' : isPlant ? 'Specimen height' : 'Height', { unit: 'm', min: .001 });
    const finish = box(section(inspector, 'Finish'));
    if (isBase) {
      field(finish, 'material', 'Slab material', { choices: { concrete: MATERIALS.concrete } }).disabled = true;
      field(finish, 'coping', 'Coping', { choices: { '': 'None' } }).disabled = true;
    } else {
      field(finish, 'material', 'Material', { choices: MATERIALS });
      field(finish, 'pattern', 'Pattern', { choices: PATTERNS });
      field(finish, 'palette', 'Palette', { choices: PALETTES });
      if (!isPlant) field(finish, 'coping', 'Coping', { choices: { '': 'None', ...MATERIALS } });
    }
    if (!isBase && (f.steps || ['patio','decking','raised-bed','sunken-area'].includes(f.kind))) {
      const stair = section(inspector, 'Steps');
      if (f.kind !== 'steps') stair.append(button(f.steps ? 'Remove steps' : 'Add steps', 'steps'));
      if (f.steps) {
        const sf = box(stair);
        const risers = field(sf, 'stepCount', 'Risers', { min: 1, max: 32 }); risers.step = '1';
        field(sf, 'stepWidth', 'Stair width', { unit: 'm', min: .001 });
        field(sf, 'stepAt', 'Position along boundary', { unit: '%', min: 0, max: 100, wide: true });
      }
    }
    const row = el('div', 'gd-object-actions');
    row.append(button('Copy object', 'copy'), button('Delete object', 'delete'));
    inspector.append(row);
  }

  function edit(input) {
    const key = input.dataset.field;
    if (key === 'kind' || key === 'method') { action(key, input.value); return; }
    const selected = state?.selected;
    if (!selected) return;
    if (!input.checkValidity() || (input.type === 'number' && !Number.isFinite(input.valueAsNumber))) {
      input.reportValidity(); return;
    }
    const value = input.type === 'number' ? input.valueAsNumber : input.value;
    const g = selected.geometry, centre = centerOf(g);
    if (key === 'sizeX' || key === 'sizeZ') {
      const m = measureGeometry(g);
      action('size', { width: key === 'sizeX' ? value : m.width, depth: key === 'sizeZ' ? value : m.depth });
    } else if (key === 'radius') {
      action('field', { key: 'geometry', value: { ...g, radius: value } });
    } else if (key === 'angle') action('angle', value);
    else if (key === 'positionX' || key === 'positionZ') {
      const offset = key === 'positionX' ? [value - centre[0], 0] : [0, value - centre[1]];
      action('field', { key: 'geometry', value: transformGeometry(g, { offset }) });
    } else if (['stepCount','stepWidth','stepAt'].includes(key)) {
      const stepKey = { stepCount:'count', stepWidth:'width', stepAt:'at' }[key];
      action('field', { key:'steps', value:{ ...selected.steps, [stepKey]:key === 'stepAt' ? value / 100 : value } });
    } else action('field', { key, value });
  }

  root.addEventListener('change', event => {
    if (event.target === list) action('select', list.value || null);
    else if (event.target.dataset.field) edit(event.target);
  });
  root.addEventListener('click', event => {
    const control = event.target.closest('button[data-cmd]');
    if (!control || control.disabled || !state?.active) return;
    event.stopPropagation();
    const cmd = control.dataset.cmd, val = control.dataset.val;
    if (cmd === 'collapse') {
      action('collapse');
    } else if (cmd === 'view') {
      if ((val === 'bird') !== !!state.bird) action('view');
    } else if (cmd === 'tool') action('tool', val);
    else action(cmd);
  });
  // Keep canvas drag, wheel and walking handlers away from native controls.
  for (const type of ['pointerdown','pointermove','pointerup','touchstart','touchmove','touchend','wheel','keydown']) {
    root.addEventListener(type, e => e.stopPropagation(), { passive: true });
  }

  function update(next) {
    const home=new URL('/preview/',location.href);home.port='8450';
    if(next.version)home.searchParams.set('version',next.version);
    root.querySelector('.gd-return-house').href=home.href;
    const furniture=new URL('https://127.0.0.1:8450/house.html');
    furniture.search=new URLSearchParams({site:'house',version:next.version||'approved_2b',mode:'review',edit:'1'});
    root.querySelector('[data-mac-furniture]').href=furniture.href;
    state = next; root.hidden = !state.active;
    if (!state.active) return;
    root.classList.toggle('gd-collapsed',!!state.collapsed);
    collapse.textContent=state.collapsed?'Show tools':'Minimise';
    collapse.setAttribute('aria-expanded',String(!state.collapsed));
    collapse.setAttribute('aria-label',state.collapsed?'Show garden tools and resume drawing':'Minimise garden tools and walk');
    const selected = state.selected;
    const site = state.site || siteQuery.get('site');
    const version = state.version || siteQuery.get('version');
    context.textContent = [site, version].filter(Boolean).join(' · ') || 'Measured garden';
    const listSignature = JSON.stringify(state.objects.map(f => [f.id, f.label]));
    if (listSignature !== listKey) {
      listKey = listSignature;
      list.replaceChildren(); option(list, '', 'Choose an object…');
      for (const [i, f] of state.objects.entries()) option(list, f.id, (i + 1) + ' · ' + f.label);
    }
    list.value = selected?.id || '';
    count.textContent = String(state.objects.length);
    for (const b of root.querySelectorAll('button[data-cmd=tool]')) b.setAttribute('aria-pressed', String(b.dataset.val === state.tool));
    for (const b of root.querySelectorAll('button[data-cmd=view]')) b.setAttribute('aria-pressed', String((b.dataset.val === 'bird') === !!state.bird));
    kind.value = state.kind; method.value = state.method;
    method.disabled = KINDS[state.kind]?.form === 'point';
    drawActions.hidden = state.tool !== 'draw';
    find('[data-cmd=finish]').hidden = state.method !== 'corners';
    updateSlab();
    const signature = JSON.stringify([selected?.id, selected?.kind, selected?.geometry.type, !!selected?.steps]);
    if (signature !== inspectorKey) { inspectorKey = signature; setupInspector(selected); }
    if (selected) {
      const g = selected.geometry, measure = measureGeometry(g), centre = centerOf(g);
      const areaType = KINDS[selected.kind].form === 'area';
      const metric = find('.gd-metrics');
      metric.textContent = g.type === 'point' ? (SPECIES[selected.species]?.botanical || 'Specimen') :
        areaType ? numberFormat.format(measure.area) + ' m²' : numberFormat.format(measure.perimeter) + ' m long';
      const values = { ...selected, sizeX:measure.width, sizeZ:measure.depth, radius:g.radius, angle:state.angle ?? angleOf(g),
        positionX:centre[0], positionZ:centre[1], stepCount:selected.steps?.count, stepWidth:selected.steps?.width,
        stepAt:selected.steps ? selected.steps.at * 100 : undefined };
      for (const input of inspector.querySelectorAll('[data-field]')) {
        if (input === document.activeElement) continue;
        const value = values[input.dataset.field];
        input.value = typeof value === 'number' ? display(value) : value ?? '';
        if (input.dataset.field === 'sizeX') input.disabled = measure.width < .001;
        if (input.dataset.field === 'sizeZ') input.disabled = measure.depth < .001;
      }
    }
    find('[data-cmd=undo]').disabled = !state.undo;
    find('[data-cmd=redo]').disabled = !state.redo;
    const save = find('[data-cmd=save]');
    save.disabled = !state.dirty || state.saving || !!state.conflict;
    save.textContent = state.saving ? 'Saving…' : 'Save garden';
    root.dataset.saveState = state.conflict ? 'conflict' : state.dirty ? 'draft' : 'saved';
    status.textContent = state.status || (state.conflict ? 'Changed on another device. Your draft is still here.' :
      state.saving ? 'Saving garden…' : state.dirty ? 'Unsaved edits' : 'Garden saved');
    find('[data-cmd=reload]').hidden = !state.conflict;
  }
  return { update, dispose() { root.remove(); } };
}
