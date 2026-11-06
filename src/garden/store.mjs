import { KINDS, newFeatureId, validateFeatureGeometry } from './catalogue.mjs';
import { transformGeometry } from './geometry.mjs';

const permanent = objects => objects.filter(f => !['car-guide','van-guide'].includes(f.kind));

function sameData(a, b) {
  if (a === b) return true;
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object' || Array.isArray(a) !== Array.isArray(b)) return false;
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every(key => Object.hasOwn(b, key) && sameData(a[key], b[key]));
}

function measurable(value, low, high, label) {
  if (!Number.isFinite(value) || value < low || value > high) throw new RangeError('Invalid ' + label);
}

function checkedFeature(value) {
  const f = structuredClone(value);
  if (!f || !Object.hasOwn(KINDS, f.kind)) throw new TypeError('Unknown garden feature kind');
  if (typeof f.id !== 'string' || !/^[a-z\d][a-z\d_-]{0,95}$/i.test(f.id)) throw new TypeError('Invalid garden feature ID');
  for (const key of ['label', 'material', 'pattern', 'palette', 'coping']) {
    if (typeof f[key] !== 'string' || (!f[key] && key !== 'coping') || f[key].length > (key === 'label' ? 160 : 96) || /[\x00-\x1f\x7f]/u.test(f[key])) {
      throw new TypeError('Invalid garden feature ' + key);
    }
  }
  measurable(f.baseY, -1000, 1000, 'base elevation');
  measurable(f.level, -1000, 1000, 'surface level');
  measurable(f.width, 0, 1000, 'width');
  measurable(f.height, 0, 1000, 'height');
  validateFeatureGeometry(f.kind, f.geometry);
  if(f.kind==='outbuilding-base' && (f.material!=='concrete'||f.coping!==''||f.height<=0||f.steps!=null))throw new TypeError('An outbuilding base needs concrete and a positive slab thickness.');
  if (f.species !== undefined && (typeof f.species !== 'string' || !f.species || f.species.length > 96 || /[\x00-\x1f\x7f]/u.test(f.species))) {
    throw new TypeError('Invalid planting species');
  }
  if (f.steps !== undefined) {
    if (!f.steps || !Number.isInteger(f.steps.count)) throw new TypeError('Steps need a whole number of risers');
    measurable(f.steps.count, 1, 32, 'step count');
    measurable(f.steps.at, 0, 1, 'step position');
    measurable(f.steps.width, .001, 1000, 'step width');
  }
  return f;
}

function layoutState(data) {
  if (!data || !Number.isSafeInteger(data.revision) || data.revision < 0) throw new TypeError('Invalid layout revision');
  const garden = data.garden ?? { schema: 1, objects: [] };
  if (garden.schema !== 1 || !Array.isArray(garden.objects) || garden.objects.length > 1024) throw new TypeError('Invalid garden layout');
  const objects = garden.objects.map(checkedFeature);
  if (new Set(objects.map(f => f.id)).size !== objects.length) throw new TypeError('Duplicate feature ID in layout');
  return { objects, revision: data.revision };
}

export class GardenStore {
  #objects = [];
  #baseline = this.#objects;
  #revision = 0;
  #loaded = false;
  #undo = [];
  #redo = [];
  #readTicket = 0;
  #saving = null;
  #url;
  #fetcher;
  #onChange;

  constructor({ site, version, fetcher = fetch, onChange = () => {} }) {
    if (!site || !version) throw new TypeError('A garden needs a site and version');
    this.#url = '/layout?' + new URLSearchParams({ site, version });
    this.#fetcher = fetcher;
    this.#onChange = onChange;
  }

  // Public objects are detached. A move or recolour only enters history through put().
  get objects() { return structuredClone(this.#objects); }
  get revision() { return this.#revision; }
  get dirty() { return !sameData(permanent(this.#objects), permanent(this.#baseline)); }
  get canUndo() { return this.#undo.length > 0; }
  get canRedo() { return this.#redo.length > 0; }
  get saving() { return this.#saving !== null; }
  get(id) { return structuredClone(this.#objects.find(f => f.id === id)); }

  #notify(label) { this.#onChange(this, label); }

  #replace(objects, label) {
    this.#undo.push({ objects: this.#objects, label });
    this.#redo = [];
    this.#objects = objects;
    ++this.#readTicket;
    this.#notify(label);
  }

  put(feature, label = 'Edit') {
    const value = checkedFeature(feature);
    const i = this.#objects.findIndex(f => f.id === value.id);
    if (i < 0) {
      if (this.#objects.length >= 1024) throw new RangeError('The garden is full');
      this.#replace([...this.#objects, value], label);
    } else if (!sameData(this.#objects[i], value)) {
      const next = this.#objects.slice();
      next[i] = value;
      this.#replace(next, label);
    }
    return structuredClone(value);
  }

  remove(id) {
    const next = this.#objects.filter(f => f.id !== id);
    if (next.length === this.#objects.length) return false;
    this.#replace(next, 'Delete');
    return true;
  }

  duplicate(id, offset = [.35, .35]) {
    const original = this.get(id);
    if (!original) return undefined;
    original.id = newFeatureId(original.kind);
    original.geometry = transformGeometry(original.geometry, { offset });
    original.label = original.label.slice(0, 155) + ' copy';
    return this.put(original, 'Copy');
  }

  #travel(from, to, verb) {
    const next = from.pop();
    if (!next) return false;
    to.push({ objects: this.#objects, label: next.label });
    this.#objects = next.objects;
    ++this.#readTicket;
    this.#notify(verb + ' ' + next.label);
    return true;
  }

  undo() { return this.#travel(this.#undo, this.#redo, 'Undo'); }
  redo() { return this.#travel(this.#redo, this.#undo, 'Redo'); }

  async #request(options) {
    const fetcher = this.#fetcher;
    const response = await fetcher(this.#url, { cache: 'no-store', ...options });
    if (!response.ok) {
      let detail;
      try { detail = await response.json(); } catch { /* No JSON error body. */ }
      const message = detail?.error || (response.status === 409 ? 'Layout changed on another device' : 'Could not access the layout');
      const error = new Error(message);
      error.status = response.status;
      error.currentRevision = detail?.currentRevision ?? detail?.revision;
      throw error;
    }
    return layoutState(await response.json());
  }

  async #read(discard) {
    const ticket = ++this.#readTicket;
    const remote = await this.#request({ method: 'GET' });
    // An edit, a save or a later read started after this GET. Preserve that state.
    if (ticket !== this.#readTicket || this.saving || remote.revision < this.revision) return false;
    const objectsChanged = !sameData(remote.objects, this.#baseline);
    if (discard || objectsChanged) {
      this.#objects = this.#baseline = remote.objects;
      this.#undo = [];
      this.#redo = [];
    }
    const changed = !this.#loaded || this.#revision !== remote.revision || discard || objectsChanged;
    this.#loaded = true;
    this.#revision = remote.revision;
    if (changed) this.#notify('Load');
    return true;
  }

  load({ discard = false } = {}) {
    if (this.saving || (this.dirty && !discard)) {
      return Promise.reject(new Error('Save the garden or explicitly discard its edits before loading'));
    }
    return this.#read(discard);
  }

  refresh() {
    return this.saving || this.dirty ? Promise.resolve(false) : this.#read(false);
  }

  async #write(snapshot) {
    if (sameData(snapshot, this.#baseline)) return false;
    const baseRevision = this.#revision;
    const remote = await this.#request({
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ baseRevision, section: 'garden', garden: { schema: 1, objects: permanent(snapshot) } }),
    });
    if (remote.revision <= baseRevision) throw new Error('The server did not acknowledge this garden revision');
    this.#revision = remote.revision;
    this.#baseline = remote.objects;
    if (this.#objects === snapshot) this.#objects = [...this.#baseline,...snapshot.filter(f => !permanent([f]).length)];
    return true;
  }

  save() {
    if (!this.#loaded) return Promise.reject(new Error('Load the layout successfully before saving'));
    if (!this.saving && !this.dirty) return Promise.resolve(false);
    const snapshot = this.#objects;
    ++this.#readTicket;
    // Each explicit save owns its snapshot. Later pointer edits stay dirty.
    // A failed predecessor also cancels queued writes instead of silently rebasing.
    const pending = (this.#saving ?? Promise.resolve()).then(() => this.#write(snapshot));
    this.#saving = pending;
    this.#notify('Saving');
    return pending.finally(() => {
      if (this.#saving === pending) {
        this.#saving = null;
        this.#notify('Save settled');
      }
    });
  }
}
