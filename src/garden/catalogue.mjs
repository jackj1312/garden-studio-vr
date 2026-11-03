import { isClosed, validateGeometry } from './geometry.mjs';

// Colours are sRGB. Scale and pattern units are metres in the garden frame.
export const MATERIALS = {
  paving:    { label: 'Sandstone paving', color: '#bda990', scale: .60, roughness: .84 },
  limestone: { label: 'Pale limestone', color: '#c8c1a8', scale: .60, roughness: .78 },
  slate:     { label: 'Blue slate', color: '#59656b', scale: .60, roughness: .76 },
  brick:     { label: 'Clay brick', color: '#995f49', scale: .215, roughness: .88 },
  render:    { label: 'Lime render', color: '#d7cfc0', scale: 1, roughness: .93 },
  sleepers:  { label: 'Oak sleepers', color: '#89694d', scale: .20, roughness: .88 },
  stone:     { label: 'Walling stone', color: '#979083', scale: .35, roughness: .94 },
  gravel:    { label: 'Pea gravel', color: '#b7a388', scale: .06, roughness: .96 },
  lawn:      { label: 'Mown lawn', color: '#68814f', scale: .40, roughness: .96 },
  decking:   { label: 'Timber decking', color: '#aa8866', scale: .14, roughness: .80 },
  soil:      { label: 'Planting soil', color: '#62503e', scale: .25, roughness: .98 },
  foliage:   { label: 'Foliage', color: '#62784f', scale: .10, roughness: .82 },
  steel:     { label: 'Dark steel', color: '#51534d', scale: .30, roughness: .58 },
};

export const PATTERNS = {
  plain:        { label: 'Plain', unit: [1, 1] },
  grid:         { label: 'Square flags', unit: [.60, .60] },
  'laid-flags': { label: 'Coursed flags', unit: [.60, .40] },
  'running-bond': { label: 'Running bond', unit: [.215, .065] },
  herringbone:  { label: 'Herringbone', unit: [.20, .10] },
  basketweave:  { label: 'Basket weave', unit: [.20, .10] },
  planks:       { label: 'Parallel boards', unit: [1.80, .14] },
  courses:      { label: 'Stone courses', unit: [.40, .16] },
};

// A palette can supply tonal variation without changing the material's joint spacing.
export const PALETTES = {
  natural: { label: 'Natural', colors: ['#b6aa91', '#a59d8a', '#c2b7a1'] },
  warm:    { label: 'Honey and clay', colors: ['#be9e76', '#a3795f', '#cbb28f'] },
  cool:    { label: 'Cool grey', colors: ['#969c9a', '#7c8584', '#b3b7af'] },
  chalk:   { label: 'Chalk and buff', colors: ['#d7cdb8', '#bfb299', '#e1dac8'] },
  green:   { label: 'Garden greens', colors: ['#667e50', '#7c905e', '#546d45'] },
};

// Width and height describe the represented planting specimen, not its mature spread.
export const SPECIES = {
  lavender:  { kind: 'plant', label: 'English lavender', botanical: 'Lavandula angustifolia', width: .65, height: .55, color: '#859180', accent: '#8c7ba6', habit: 'mound' },
  hydrangea: { kind: 'plant', label: 'Panicle hydrangea', botanical: 'Hydrangea paniculata', width: 1.20, height: 1.35, color: '#71845a', accent: '#dfdfc5', habit: 'shrub' },
  fern:      { kind: 'plant', label: 'Male fern', botanical: 'Dryopteris filix-mas', width: .85, height: .75, color: '#668353', habit: 'fronds' },
  grass:     { kind: 'plant', label: 'Feather reed grass', botanical: 'Calamagrostis × acutiflora', width: .70, height: 1.45, color: '#92935e', accent: '#c0ad79', habit: 'upright' },
  apple:     { kind: 'tree', label: 'Apple tree', botanical: 'Malus domestica', width: 2.70, height: 3.20, color: '#688152', habit: 'spreading' },
  birch:     { kind: 'tree', label: 'Silver birch', botanical: 'Betula pendula', width: 2.10, height: 4.50, color: '#8a9f65', habit: 'upright' },
  maple:     { kind: 'tree', label: 'Japanese maple', botanical: 'Acer palmatum', width: 2.25, height: 2.40, color: '#996355', habit: 'spreading' },
  rowan:     { kind: 'tree', label: 'Rowan', botanical: 'Sorbus aucuparia', width: 2.60, height: 3.80, color: '#758859', accent: '#bb694b', habit: 'rounded' },
};

function kind(label, form, material, pattern, palette, extras = {}) {
  return { label, form, material, pattern, palette, width: 0, height: 0, level: 0, coping: '', ...extras };
}
export const KINDS = {
  patio: kind('Patio', 'area', 'paving', 'laid-flags', 'natural'),
  path: kind('Path', 'line', 'paving', 'running-bond', 'natural', { width: .90 }),
  lawn: kind('Lawn', 'area', 'lawn', 'plain', 'green'),
  gravel: kind('Gravel', 'area', 'gravel', 'plain', 'warm'),
  decking: kind('Decking', 'area', 'decking', 'planks', 'warm', { level: .12 }),
  wall: kind('Wall', 'line', 'brick', 'running-bond', 'warm', { width: .215, height: .90, coping: 'stone' }),
  'retaining-wall': kind('Retaining wall', 'line', 'stone', 'courses', 'natural', { width: .30, height: .60, coping: 'stone' }),
  'raised-bed': kind('Raised bed', 'area', 'sleepers', 'planks', 'warm', { width: .10, height: .45, coping: 'sleepers' }),
  'sunken-area': kind('Sunken area', 'area', 'paving', 'laid-flags', 'cool', { width: .20, level: -.45, coping: 'stone' }),
  'fire-pit': kind('Fire pit', 'area', 'brick', 'running-bond', 'warm', { width: .18, height: .40, coping: 'stone' }),
  steps: kind('Steps', 'line', 'paving', 'laid-flags', 'natural', { width: 1.20, height: .45, coping: 'stone' }),
  fence: kind('Fence', 'line', 'sleepers', 'planks', 'warm', { width: .10, height: 1.80 }),
  edging: kind('Edging', 'line', 'stone', 'courses', 'cool', { width: .10, height: .08 }),
  'planting-bed': kind('Planting bed', 'area', 'soil', 'plain', 'natural'),
  plant: kind('Plant', 'point', 'foliage', 'plain', 'green', { width: SPECIES.lavender.width, height: SPECIES.lavender.height, species: 'lavender' }),
  tree: kind('Tree', 'point', 'foliage', 'plain', 'green', { width: SPECIES.apple.width, height: SPECIES.apple.height, species: 'apple' }),
};

export function newFeatureId(kindKey) {
  if (!Object.hasOwn(KINDS, kindKey)) throw new TypeError('Unknown garden feature');
  return kindKey + '-' + globalThis.crypto.randomUUID();
}

export function validateFeatureGeometry(kindKey, geometry) {
  validateGeometry(geometry);
  const { form, label } = KINDS[kindKey];
  if ((form === 'point') !== (geometry.type === 'point') || (form === 'area' && !isClosed(geometry))) {
    throw new TypeError('Geometry does not fit a ' + label.toLowerCase());
  }
  return geometry;
}

export function createFeature(kindKey, geometry, baseY = 0) {
  const id = newFeatureId(kindKey);
  if (!Number.isFinite(baseY) || Math.abs(baseY) > 1000) throw new RangeError('Base elevation must be in metres');
  const { form, ...defaults } = KINDS[kindKey];
  const shape = structuredClone(validateFeatureGeometry(kindKey, geometry));
  const result = { id, kind: kindKey, ...defaults, geometry: shape, baseY };
  if (kindKey === 'steps') result.steps = { at: 0, count: 3, width: result.width };
  return result;
}
