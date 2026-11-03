import { helpPage } from '../editor-help.js';
import { KINDS, MATERIALS, PATTERNS, PALETTES, SPECIES } from './catalogue.mjs';
import { measureGeometry } from './geometry.mjs';
import { angleOf } from './drawing.mjs';

const W = 704, H = 816, WRIST_W = .265, WRIST_H = WRIST_W * H / W;
const METHODS = {
  auto: 'Fit my stroke', straight: 'Straight run', curve: 'Smooth curve', arc: 'Circular arc',
  circle: 'Circle', rectangle: 'Rectangle', square: 'Square', corners: 'Corner points',
};
const fields = { material: MATERIALS, pattern: PATTERNS, palette: PALETTES, coping: MATERIALS, species: SPECIES };
const titles = {
  home: 'Garden design', draw: 'Drawing tools', kinds: 'Choose a feature', methods: 'Drawing method',
  edit: 'Edit selection', finish: 'Materials & planting', levels: 'Levels & steps', objects: 'Garden objects',
  options: 'Choose a finish', value: 'Enter a number', help: 'How to use',
};
const display = n => Number(n.toFixed(3)).toString();
const titleCase = t => t[0].toUpperCase() + t.slice(1);
const clock = () => performance.now();

// The host owns the renderer, real camera, terrain picks, history and catalogue state.
// This panel only sends editor actions and converts picks on its map into site metres.
export function createGardenWrist({ THREE, scene, camera, action, state, planImage, bounds }) {
  const canvas = document.createElement('canvas'); canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  const planCanvas = document.createElement('canvas'); planCanvas.width = planCanvas.height = 512;
  const planCtx = planCanvas.getContext('2d');
  function surface(image, width = 1, height = 1) {
    const texture = new THREE.CanvasTexture(image);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.generateMipmaps = false; texture.minFilter = THREE.LinearFilter;
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, height),
      new THREE.MeshBasicMaterial({ map: texture, toneMapped: false, depthTest: false, depthWrite: false }));
    mesh.visible = false; mesh.userData.gardenOverlay = true;
    scene.add(mesh); return mesh;
  }
  const wrist = surface(canvas, WRIST_W, WRIST_H), table = surface(planCanvas);
  wrist.name = 'Garden · left wrist'; table.name = 'Garden · whole plot';
  wrist.renderOrder = 1910; table.renderOrder = 1900;
  const dot = new THREE.Mesh(new THREE.CircleGeometry(.004, 14), new THREE.MeshBasicMaterial({
    color: 0xf8ae55, depthTest: false, depthWrite: false, toneMapped: false,
  }));
  dot.visible = false; dot.renderOrder = 1912; wrist.add(dot);
  const pick = new THREE.Raycaster(), head = new THREE.Vector3(), forward = new THREE.Vector3();
  const position = new THREE.Vector3(), grabOffset = new THREE.Vector3(.045, .10, -.095);
  let page = 'home', listPage = 0, helpReturn = 'home', optionKey = 'material', valuePage = null;
  let localNotice = '', buttons = [], cached = null, key = '', nextUpdate = 0, nextPlan = 0;
  let held = false, activeBefore = false, birdBefore = false, recenter = true, extent = null, disposed = false;

  function go(to) { page = to; listPage = 0; localNotice = ''; key = ''; nextUpdate = 0; }
  function send(name, value) {
    const result = action(name, value);
    if (result?.catch) result.catch(e => { localNotice = e.message; key = ''; });
    key = ''; nextUpdate = nextPlan = 0;
  }
  function text(str, x, y, size = 23, color = '#f3f0e6', weight = 500, maxWidth = W - 48) {
    ctx.font = weight + ' ' + size + 'px system-ui, sans-serif'; ctx.fillStyle = color;
    let s = String(str);
    if (ctx.measureText(s).width > maxWidth) {
      while (s.length && ctx.measureText(s + '…').width > maxWidth) s = s.slice(0, -1);
      s += '…';
    }
    ctx.fillText(s, x, y);
  }
  function wrapped(str, x, y, width, size = 29, line = 42) {
    ctx.font = '500 ' + size + 'px system-ui, sans-serif'; ctx.fillStyle = '#edece2';
    let words = '';
    for (const word of str.split(/\s+/)) {
      const next = words ? words + ' ' + word : word;
      if (words && ctx.measureText(next).width > width) { ctx.fillText(words, x, y); y += line; words = word; }
      else words = next;
    }
    if (words) ctx.fillText(words, x, y);
  }
  function button(label, x, y, w, h, run, { selected = false, enabled = true } = {}) {
    ctx.fillStyle = enabled ? selected ? '#44806a' : '#243a33' : '#202b26';
    ctx.fillRect(x, y, w, h); ctx.strokeStyle = selected ? '#a9d3a5' : '#496259';
    ctx.strokeRect(x + .5, y + .5, w - 1, h - 1);
    text(label, x + 14, y + h / 2 + 8, 24, enabled ? '#f4f3e8' : '#919c93', 540, w - 28);
    buttons.push({ label, x, y, w, h, run: enabled ? run : null });
  }
  const input = (label, run, options) => ({ label, run, options });
  const nav = (label, to, options) => input(label, () => go(to), options);
  const op = (label, name, value, options) => input(label, () => send(name, value), options);
  function row(y, ...entries) {
    const gap = 9, width = (W - 48 - gap * (entries.length - 1)) / entries.length;
    entries.forEach(({ label, run, options }, i) => button(label, 24 + i * (width + gap), y, width, 56, run, options));
  }
  function list(items) {
    const count = Math.max(1, Math.ceil(items.length / 8));
    listPage = Math.max(0, Math.min(listPage, count - 1));
    const visible = items.slice(listPage * 8, listPage * 8 + 8);
    for (let i = 0; i < visible.length; i += 2) row(184 + i / 2 * 68, ...visible.slice(i, i + 2));
    if (count > 1) row(483,
      input('Previous', () => { listPage--; key = ''; }, { enabled: listPage > 0 }),
      input((listPage + 1) + ' / ' + count, null, { enabled: false }),
      input('Next', () => { listPage++; key = ''; }, { enabled: listPage + 1 < count }));
  }
  function showHelp() { helpReturn = page; go('help'); }
  function options(keyName) { optionKey = keyName; go('options'); }
  function sizeOf(feature) {
    const g = feature.geometry;
    if (g.type === 'rectangle') return { width: g.width, depth: g.depth };
    if (g.type === 'point') return { width: feature.width, depth: feature.width };
    return measureGeometry(g);
  }
  function numberPad(label, value, cmd, optionalKey) {
    const item = cached?.selected;
    if (!item) return;
    valuePage = { label, value: display(value), replace: true, id: item.id, cmd, field: optionalKey,
      back: page, size: sizeOf(item), steps: item.steps };
    go('value');
  }
  function digit(s) {
    let v = valuePage.value;
    if (s === '⌫') v = valuePage.replace ? '' : v.slice(0, -1);
    else if (s === '±') v = v.startsWith('-') ? v.slice(1) : '-' + v;
    else {
      if (valuePage.replace) v = '';
      if ((s === '.' && v.includes('.')) || v.length > 10) return;
      v += s;
    }
    valuePage.value = v; valuePage.replace = false; key = '';
  }
  function applyNumber() {
    const v = Number(valuePage.value), { cmd, field, back } = valuePage;
    if (!valuePage.value.trim() || !Number.isFinite(v) || cached?.selected?.id !== valuePage.id) {
      localNotice = 'Choose a feature and enter a number'; key = ''; return;
    }
    if (cmd === 'size') send(cmd, { width: field === 'width' ? v : valuePage.size.width,
                                    depth: field === 'depth' ? v : valuePage.size.depth });
    else if (cmd === 'stepField') send('field', { key: 'steps', value: { ...valuePage.steps, [field]: v } });
    else if (cmd === 'field') send(cmd, { key: field, value: v });
    else send(cmd, v);
    go(back);
  }
  function draw(s) {
    const item = s.selected;
    // The compact signature avoids uploading wrist pixels when only the tracked hand moves.
    const signature = JSON.stringify([page, listPage, optionKey, valuePage?.value, localNotice,
      s.tool, s.method, s.kind, s.bird, s.dirty, s.saving, s.undo, s.redo, s.status, !!s.conflict,
      item, page === 'objects' ? s.objects.map(o => [o.id, o.label]) : s.objects.length]);
    if (key === signature) return;
    key = signature; buttons = [];
    ctx.fillStyle = '#13271f'; ctx.fillRect(0, 0, W, H);
    text('GARDEN STUDIO  /  QUEST', 24, 41, 20, '#a8c8a6', 650);
    text(page === 'options' ? titleCase(optionKey) : titles[page], 24, 103, 43, '#fff9eb', 620);
    const sub = page === 'value' ? valuePage.label :
      page === 'help' ? 'Garden design • controller guide' :
      item ? 'Selected · ' + item.label : 'Right trigger · point, draw or select';
    text(sub, 24, 146, 24, '#c1cfc2');
    const enabled = Boolean(item), hasItem = { enabled }, dirty = Boolean(s.dirty);
    switch (page) {
      case 'home':
        row(184, nav('Drawing tools', 'draw'), nav('Features', 'kinds'));
        row(252, nav('Edit selection', 'edit', hasItem), nav('Garden objects', 'objects'));
        row(320, op(s.bird ? 'Standing view' : 'Bird’s-eye', 'view'), nav('Levels & steps', 'levels', hasItem));
        row(388, op('Undo', 'undo', undefined, { enabled: s.undo }), op('Redo', 'redo', undefined, { enabled: s.redo }));
        row(456, op('Save layout', 'save', undefined, { enabled: dirty && !s.saving && !s.conflict }),
                 op('Reload', 'reload', undefined, { enabled: !s.saving }));
        row(524, nav('Materials', 'finish', hasItem), op('Close editor', 'close'));
        if (s.bird) row(592, input('Centre plan', () => { recenter = true; }));
        break;
      case 'draw':
        row(184, op('Select', 'tool', 'select', { selected: s.tool === 'select' }),
                 op('Draw', 'tool', 'draw', { selected: s.tool === 'draw' }),
                 op('Level', 'tool', 'level', { selected: s.tool === 'level' }));
        row(252, nav('Feature · ' + (KINDS[s.kind]?.label || 'Choose'), 'kinds'),
                 nav('Method · ' + (METHODS[s.method] || 'Auto'), 'methods'));
        row(320, op('Finish stroke', 'finish'), op('Cancel stroke', 'cancel'));
        row(388, op(s.bird ? 'Standing view' : 'Bird’s-eye', 'view'), nav('Edit selection', 'edit', hasItem));
        break;
      case 'kinds':
        list(Object.entries(KINDS).map(([k, f]) => input(f.label, () => {
          send('kind', k); send('tool', 'draw'); go('draw');
        }, { selected: s.kind === k }))); break;
      case 'methods':
        list(Object.entries(METHODS).map(([k, label]) => input(label, () => {
          send('method', k); send('tool', 'draw'); go('draw');
        }, { selected: s.method === k }))); break;
      case 'objects':
        if (!s.objects.length) wrapped('Your drawn features and planting will appear here.', 24, 236, W - 55, 26);
        list(s.objects.map(o => input(o.label, () => { send('select', o.id); go('edit'); }, { selected: item?.id === o.id })));
        break;
      case 'edit':
        if (!item) { row(184, nav('Choose an object', 'objects')); break; }
        {
          const g = item.geometry, size = sizeOf(item), angle = s.angle ?? angleOf(g);
          row(184, input('Width ' + display(size.width) + ' m', () => numberPad('Width (metres)', size.width,
                g.type === 'point' ? 'field' : 'size', 'width')),
            g.type === 'point' ? input('Height ' + display(item.height) + ' m', () => numberPad('Height (metres)', item.height, 'field', 'height')) :
              input('Depth ' + display(size.depth) + ' m', () => numberPad('Depth (metres)', size.depth, 'size', 'depth')));
          row(252, input('Angle ' + display(angle) + '°', () => numberPad('Absolute angle (degrees)', angle, 'angle')),
                   nav('Levels & steps', 'levels'));
          row(320, nav('Materials', 'finish'), nav('Garden objects', 'objects'));
          row(388, op('Copy', 'copy'), op('Delete', 'delete'));
          row(456, op('Undo', 'undo', undefined, { enabled: s.undo }), op('Redo', 'redo', undefined, { enabled: s.redo }));
        }
        break;
      case 'levels':
        if (!item) { row(184, nav('Choose an object', 'objects')); break; }
        row(184, input('Level ' + display(item.level) + ' m', () => numberPad('Level above host (metres)', item.level, 'field', 'level')),
                 input('Height ' + display(item.height) + ' m', () => numberPad('Height (metres)', item.height, 'field', 'height')));
        row(252, op('Lower 10 cm', 'field', { key: 'level', value: +(item.level - .1).toFixed(3) }),
                 op('Raise 10 cm', 'field', { key: 'level', value: +(item.level + .1).toFixed(3) }));
        row(320, op('Fit steps', 'steps'), nav('Materials', 'finish'));
        if (item.steps) row(388, input(item.steps.count + ' treads', () => numberPad('Tread count', item.steps.count, 'stepField', 'count')),
          input('Stair width ' + display(item.steps.width), () => numberPad('Stair width (metres)', item.steps.width, 'stepField', 'width')));
        if (item.steps) row(456, input('Boundary position ' + display(item.steps.at), () => numberPad('Position on boundary (0 to 1)', item.steps.at, 'stepField', 'at')));
        break;
      case 'finish':
        if (!item) { row(184, nav('Choose an object', 'objects')); break; }
        row(184, input('Material', () => options('material')), input('Pattern', () => options('pattern')));
        row(252, input('Palette', () => options('palette')), input('Coping', () => options('coping')));
        if (item.kind === 'plant' || item.kind === 'tree') row(320, input('Species', () => options('species')));
        break;
      case 'options': {
        const choices = Object.entries(fields[optionKey]).filter(([,v]) => optionKey !== 'species' || v.kind === item?.kind);
        if (optionKey === 'coping') choices.unshift(['', { label: 'None' }]);
        list(choices.map(([k,v]) => input(v.label, () => { send('field', { key: optionKey, value: k }); go('finish'); },
                                        { selected: item?.[optionKey] === k, enabled })));
        break;
      }
      case 'value':
        text(valuePage.value || '0', 26, 211, 39);
        for (const [i, keys] of [['7','8','9'], ['4','5','6'], ['1','2','3'], ['±','0','.']].entries())
          row(234 + i * 65, ...keys.map(k => input(k, () => digit(k))));
        row(498, input('⌫', () => digit('⌫')), input('Apply', applyNumber), nav('Cancel', valuePage.back));
        break;
      case 'help': {
        const [, steps] = helpPage('garden');
        const [heading, body] = steps[listPage];
        text((listPage + 1) + ' / ' + steps.length, 24, 218, 26, '#b6cda7');
        text(heading, 24, 290, 37);
        wrapped(body, 24, 351, W - 58);
        row(564, input('Previous', () => { listPage--; key = ''; }, { enabled: listPage > 0 }),
                 input('Next', () => { listPage++; key = ''; }, { enabled: listPage + 1 < steps.length }));
        row(632, nav('Dismiss help', helpReturn)); break;
      }
    }
    const status = localNotice || (s.conflict ? 'Save conflict • reload the current design' :
      s.saving ? 'Saving layout…' : s.status || (dirty ? 'Changes to save' : 'Layout saved'));
    text(status, 24, 725, 22, '#c3d7b8');
    row(744, nav('Home', 'home'), input('How to use', showHelp, { enabled: page !== 'help' }));
    wrist.material.map.needsUpdate = true;
  }

  function planPosition() {
    camera.getWorldPosition(head); camera.getWorldDirection(forward); forward.y = 0;
    if (forward.lengthSq() < .001) forward.set(0, 0, -1);
    forward.normalize(); position.copy(head).addScaledVector(forward, .91);
    position.x -= forward.z * .245; position.z += forward.x * .245; position.y -= .045;
    table.position.copy(scene.worldToLocal(position));
    table.lookAt(head); table.rotateX(-.17); table.updateMatrixWorld(true);
  }
  let paintedRevision=null;
  function refreshPlan() {
    const b = bounds();
    if (!b || ![b.x0,b.x1,b.z0,b.z1].every(Number.isFinite) || b.x1 <= b.x0 || b.z1 <= b.z0) return;
    extent = { ...b };
    const ratio = (b.x1 - b.x0) / (b.z1 - b.z0);
    const w = Math.min(1.10, .92 * ratio), h = w / ratio;
    table.scale.set(w, h, 1); table.updateMatrixWorld(true);
    // Hide our own surfaces for a host that renders the orthographic snapshot here.
    const wristShown = wrist.visible; table.visible = wrist.visible = false;
    let source;
    try { source = planImage(); } finally { wrist.visible = wristShown; table.visible = true; }
    if(source?.gardenRevision!=null && paintedRevision===source.gardenRevision)return;
    paintedRevision=source?.gardenRevision ?? null;
    if (source && (source.width || source.videoWidth || source.naturalWidth)) {
      const width = ratio >= 1 ? 768 : Math.max(1, Math.round(768 * ratio));
      const height = ratio >= 1 ? Math.max(1, Math.round(768 / ratio)) : 768;
      if (planCanvas.width !== width || planCanvas.height !== height) { planCanvas.width = width; planCanvas.height = height; }
      planCtx.drawImage(source, 0, 0, width, height);
    } else {
      planCtx.fillStyle = '#284137'; planCtx.fillRect(0, 0, planCanvas.width, planCanvas.height);
      planCtx.fillStyle = '#edf4e8'; planCtx.font = '24px system-ui';
      planCtx.fillText('Preparing garden plan…', 16, 48);
    }
    table.material.map.needsUpdate = true;
  }
  function update(left, active, inVR) {
    if (disposed) return;
    const enabled = Boolean(active && inVR);
    if (!enabled) {
      wrist.visible = table.visible = dot.visible = false; held = activeBefore = birdBefore = false;
      recenter = true; return;
    }
    const now = clock();
    if (!activeBefore) { go('home'); nextPlan = 0; }
    activeBefore = true;
    if (!cached || now >= nextUpdate) {
      cached = state(); draw(cached); nextUpdate = now + 110;
    }
    wrist.visible = !!left && cached.active;
    if (wrist.visible) {
      camera.getWorldPosition(head); position.copy(grabOffset); left.localToWorld(position);
      wrist.position.copy(scene.worldToLocal(position)); wrist.lookAt(head); wrist.updateMatrixWorld(true);
    }
    table.visible = Boolean(cached.active && cached.bird);
    if (table.visible) {
      if (!birdBefore || recenter) { planPosition(); recenter = false; nextPlan = 0; }
      if (now >= nextPlan) { refreshPlan(); nextPlan = now + 250; }
    }
    birdBefore = table.visible;
  }
  function intersect(ray, mesh) {
    if (!ray || !mesh.visible) return null;
    pick.ray.copy(ray.ray || ray); mesh.updateWorldMatrix(true, false);
    return pick.intersectObject(mesh, false)[0] || null;
  }
  function hitWrist(ray, pressed = false) {
    const edge = !!pressed && !held; held = !!pressed;
    const h = intersect(ray, wrist); dot.visible = !!h;
    if (!h) return null;
    const x = h.uv.x * W, y = (1 - h.uv.y) * H;
    dot.position.set((h.uv.x - .5) * WRIST_W, (h.uv.y - .5) * WRIST_H, .001);
    if (edge) {
      const hit = buttons.find(b => x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h);
      if (hit?.run) {
        try { hit.run(); } catch (e) { localNotice = e.message; }
        cached = state(); key = ''; draw(cached);
      }
    }
    return h.distance;
  }
  function hitPlan(ray) {
    const h = intersect(ray, table);
    if (!h || !extent) return null;
    const { x0, x1, z0, z1 } = extent;
    return { point: new THREE.Vector3(x0 + h.uv.x * (x1 - x0), 0, z1 - h.uv.y * (z1 - z0)),
      normal: new THREE.Vector3(0,1,0), distance: h.distance, displayPoint: h.point.clone() };
  }
  function planWorld(point) {
    if (!extent || !table.visible) return null;
    const { x0, x1, z0, z1 } = extent;
    const x = Array.isArray(point) ? point[0] : point.x, z = Array.isArray(point) ? point[1] : point.z;
    return table.localToWorld(new THREE.Vector3((x - x0) / (x1 - x0) - .5, (z1 - z) / (z1 - z0) - .5, 0));
  }
  function wristWorld(label) {
    if (!wrist.visible) return null;
    const target = String(label).trim().toLowerCase();
    const b = buttons.find(v => v.label.toLowerCase() === target) || buttons.find(v => v.label.toLowerCase().startsWith(target));
    return b ? wrist.localToWorld(new THREE.Vector3(((b.x + b.w / 2) / W - .5) * WRIST_W,
                                                  (.5 - (b.y + b.h / 2) / H) * WRIST_H, .001)) : null;
  }
  function dispose() {
    disposed = true; buttons = []; cached = null; extent = null;
    for (const m of [dot, table, wrist]) {
      m.removeFromParent(); m.material.map?.dispose(); m.material.dispose(); m.geometry.dispose();
    }
  }
  return { update, hitWrist, hitPlan, planWorld, wristWorld, dispose };
}
