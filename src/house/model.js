import * as THREE from "three";
import { makeMaterialSet, xrayClass } from "./section.js?v=h11";
import { regenerate, dependents } from "./geom.js?v=h11";

/* ------------------------------------------------------------------ *
 *  The house model: every mesh node of the GLB becomes a PART (one
 *  piece with the contract's extras), and parts are drawn through a
 *  few BatchedMeshes, one per material x group. A batch is one draw
 *  call however many parts it holds; parts that share a mesh (linked
 *  duplicates in Blender: joists, rafters, props) share one geometry
 *  inside the batch, which is instancing. Every part keeps its own
 *  visibility, matrix and colour, so a stage can be half built:
 *  joists dropped in one by one, wall lifts rising, a demolished wall
 *  tinted then gone.
 *
 *  Parts regenerated after an edit (src/house/edits.js) are plain
 *  meshes with the same material sets, so x-ray, slice, picking and
 *  collision treat them like the baked ones.
 * ------------------------------------------------------------------ */

const STYLE = {                              // how a part arrives
  rise: new Set(["wall_outer", "wall_cavity", "wall_insulation", "wall_inner", "wall_lining", "foundation", "slab_layer", "spoil"]),
  pop: new Set(["ground"]),
};
const DROP = 0.6;                            // members are lowered in from 60 cm up
const FOLIAGE = /leaves|branches|VertexPlant|hedge|conifer|foliage|ivy/i;
/* setting materials that may be single sheets seen from both sides (fences, boards): kept double-sided */
const OPEN_SHEETS = /fence|closeboard|board|timber_pine|timber_pale|cushion|tarp/i;
const easeOut = t => 1 - Math.pow(1 - t, 3);
const clamp01 = t => t < 0 ? 0 : t > 1 ? 1 : t;
const DOOMED = new THREE.Color(1.0, 0.42, 0.36);
const WHITE = new THREE.Color(1, 1, 1);

/* progress of a part through its stage window: stage s is built over v in (s-1, s]; within it a part with
   seq q takes the slot [0.85 q, 0.85 q + 0.15] */
export const progress = (v, stage, seq) => stage <= 1 ? 1 : clamp01((v - (stage - 1) - 0.85 * seq) / 0.15);

export function readExtras(o) {
  /* GLTFLoader puts node extras in userData; a multi-material node becomes a group of meshes */
  for (let x = o; x; x = x.parent) if (x.userData && x.userData.stage_in !== undefined) return x.userData;
  return null;
}

/* a quantized attribute (KHR_mesh_quantization, the Quest's meshopt GLB) as plain floats: a batch copies every
   geometry into one set of arrays typed like its first, so mixed int8 / int16 / float parts must not meet there */
function floats(a) {
  if (!a || (a.array instanceof Float32Array && !a.normalized && !a.isInterleavedBufferAttribute)) return a;
  const out = new Float32Array(a.count * a.itemSize);
  for (let i = 0; i < a.count; i++) for (let c = 0; c < a.itemSize; c++) out[i * a.itemSize + c] = a.getComponent ? a.getComponent(i, c) : [a.getX, a.getY, a.getZ, a.getW][c].call(a, i);
  return new THREE.BufferAttribute(out, a.itemSize);
}
function normaliseGeometry(g, wantUV, wantColor = false) {
  const out = new THREE.BufferGeometry();
  out.setAttribute("position", floats(g.attributes.position));
  if (g.attributes.normal) out.setAttribute("normal", floats(g.attributes.normal));
  /* vertex-coloured materials (the VertexPlant plants: their green is only in COLOR_0) keep it through the batch (row 296) */
  if (wantColor) {
    const c = floats(g.attributes.color), n = g.attributes.position.count, rgb = new Float32Array(n * 3).fill(1);
    if (c && c.itemSize >= 3) for (let i = 0; i < n; i++) { rgb[i * 3] = c.getX(i); rgb[i * 3 + 1] = c.getY(i); rgb[i * 3 + 2] = c.getZ(i); }
    out.setAttribute("color", new THREE.Float32BufferAttribute(rgb, 3));   // always RGB floats, so every geometry in the batch matches
  }
  if (wantUV) out.setAttribute("uv", floats(g.attributes.uv) || new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
  if (g.index) out.setIndex(g.index);
  else out.setIndex([...Array(g.attributes.position.count).keys()]);
  if (!g.attributes.normal) out.computeVertexNormals();
  out.computeBoundingBox();
  return out;
}

// Older GLBs identify furnishings by their spec fitting rather than a walkable flag.
function carriesFeet(p) {
  return p.now.solid && p.ud.walkable !== false && !p.ud.furnishing && !(p.group==="fitting" && p.ud.spec_id);
}

export function surfaceExtras(node, material, hasTaggedSlots=false) {
  const face=material?.userData;
  if(!face?.surface_id || !['wall','ceiling','floor'].includes(face.surface_role)){
    if(hasTaggedSlots && node?.surface_id){
      const result={...node};delete result.surface_id;delete result.surface_role;return result;
    }
    return node;
  }
  return {...node,surface_id:face.surface_id,room_id:face.room_id,surface_role:face.surface_role};
}

function partFromExtras(index, name, ud, geometry, matrix0, materialName) {
  const bbox = geometry.boundingBox.clone().applyMatrix4(matrix0);
  const so = ud.stage_out;
  return {
    index, name, ud: { ...ud }, geometry, matrix0: matrix0.clone(), bbox, materialName,
    element: ud.element || name,
    group: ud.group || "fitting", category: ud.category || "existing", storey: ud.storey || "ground",
    stage_in: Number(ud.stage_in) || 1, stage_out: so === null || so === undefined || so === 0 || so === -1 ? null : Number(so),
    seq: Number(ud.seq) || 0, seq_out: ud.seq_out === undefined || ud.seq_out === null ? 1 : Number(ud.seq_out),
    collide: !!ud.collide,
    style: STYLE.pop.has(ud.group) || ud.context ? "pop" : STYLE.rise.has(ud.group) ? "rise" : "drop",   // the setting appears, it is not lowered in
    batch: null, instanceId: -1, mesh: null,
    hidden: false,                           // removed or replaced by an edit
    asBuilt: !!ud.as_built,                  // an as-built record (CONTRACT.md section 6)
    last: { inT: -1, outT: -1, vis: null, doomed: null },
    now: { visible: false, solid: false, doomed: false },
  };
}

export function createModel({ gltf, sidecar, elements, section, onBuildProgress, materials = null }) {
  const root = new THREE.Group();
  root.name = `house_${sidecar.version}`;
  const parts = [];
  const sets = new Map();                    // `${material}|${group}` -> material set
  const byElement = new Map();               // element id -> [part]
  const table = new Map((elements?.elements || []).map(e => [e.id, e]));
  const setting = new THREE.Group();
  setting.name = "setting";
  root.add(setting);
  const generated = new THREE.Group();
  generated.name = "edited";
  root.add(generated);

  /* one batch (and one material set) per material x x-ray class: the group stays per part, so the
     approved scheme's 67 material x group pairs come down to ~45 draw calls (VIEWER-LOOK.md) */
  /* the static setting (nodes with extras.context: the front garden, trees, the houses opposite) never changes by
     stage: it is batched apart from the house, one batch per material, so the house keeps its own budget */
  const batchKey = (source, group, ctx) => ctx ? `ctx|${source.name}` : `${source.name}|${xrayClass(group, source.name) || "skin"}`;
  /* Round 6c (the Quest frame rate): every GLB material arrives double-sided (Blender's default), so every back face
     was rasterised and shaded. The house's parts are closed solids (CONTRACT §3), so they draw their FRONT faces only
     (the slice still paints the inside of a cut: section.js turns both sides on while a cut is active). Foliage keeps
     both sides; its leaves are alpha-tested (not blended) and drawn after the rest of the opaque scene, so the GPU's
     early depth rejection stays on for everything before them. */
  function materialSet(source, group, ctx = false) {
    const key = batchKey(source, group, ctx);
    if (!sets.has(key)) {
      const s = makeMaterialSet(source, group);
      s.foliage = FOLIAGE.test(source.name || "");
      if (!s.foliage && !(ctx && OPEN_SHEETS.test(source.name || ""))) { s.normal.side = THREE.FrontSide; s.xray.side = THREE.FrontSide; }
      if (s.foliage && s.normal.transparent) {
        s.normal.transparent = false; s.normal.depthWrite = true;
        s.normal.alphaTest = Math.max(0.5, s.normal.alphaTest || 0); s.normal.alphaToCoverage = true;
      }
      s.late = s.foliage || s.normal.alphaTest > 0;
      section.adopt(s); sets.set(key, s);
    }
    return sets.get(key);
  }
  const hasTex = m => !!(m.map || m.normalMap || m.aoMap || m.roughnessMap || m.metalnessMap || m.alphaMap);
  const materialsByName = new Map();

  /* ---------- collect the baked parts ---------- */
  gltf.scene.updateMatrixWorld(true);
  const pending = [];
  gltf.scene.traverse(o => {
    if (!o.isMesh) return;
    const mat = Array.isArray(o.material) ? o.material[0] : o.material;
    const meshId=gltf.parser?.associations?.get(o)?.meshes;
    const document=gltf.parser?.json;
    const slots=document?.meshes?.[meshId]?.primitives||[];
    const tagged=slots.length>1 && slots.some(p=>document.materials?.[p.material]?.extras?.surface_id);
    const ud = surfaceExtras(readExtras(o),mat,tagged);
    if (!ud) { console.warn(`house: mesh ${o.name} has no stage extras; shown as existing`); }
    materialsByName.set(mat.name, mat);
    pending.push({ o, ud: ud || { stage_in: 1, category: "existing", group: "fitting", storey: "ground", label: o.name }, mat });
  });

  /* group by batch, count vertices of the UNIQUE geometries */
  const batchDefs = new Map();
  for (const p of pending) {
    const ctx = !!p.ud.context;
    const set = materialSet(p.mat, p.ud.group || "fitting", ctx);
    const substrate = p.mat.userData.substrate;
    if (substrate && !set.finishStage && p.mat.userData.finish_stage > 1) {
      const raw = materialsByName.get(substrate) || new THREE.MeshStandardMaterial({
        name: substrate, color: new THREE.Color().fromArray(p.mat.userData.substrate_colour || [.6,.6,.6]), roughness: .9
      });
      set.finishStage = p.mat.userData.finish_stage;
      set.finished = set.normal;
      set.roughCarrier = materialSet(raw,p.ud.group || "fitting",ctx).normal;
    }
    const key = batchKey(p.mat, p.ud.group || "fitting", ctx);
    if (!batchDefs.has(key)) batchDefs.set(key, { set, items: [], geoms: new Map(), ctx });
    const b = batchDefs.get(key);
    b.items.push(p);
    if (!b.geoms.has(p.o.geometry.uuid)) b.geoms.set(p.o.geometry.uuid, normaliseGeometry(p.o.geometry, hasTex(p.mat), !!p.mat.vertexColors));
  }
  let done = 0;
  const batchMeshes = [];
  for (const [key, b] of batchDefs) {
    let nv = 0, ni = 0;
    for (const g of b.geoms.values()) { nv += g.attributes.position.count; ni += g.index.count; }
    const mesh = new THREE.BatchedMesh(b.items.length, nv, ni, b.set.normal);
    mesh.name = key;
    mesh.receiveShadow = true;
    mesh.castShadow = !b.set.normal.transparent;            // glass lets the sun through (round-1: a glazed opening threw a solid shadow, so no sun reached any floor)
    mesh.perObjectFrustumCulled = true;
    /* per-instance sorting cost 0.6 ms a render on a laptop for the approved scheme (x2 eyes, and a slower CPU on the
       Quest); opaque parts don't need it, only transparent ones (glass, x-ray) */
    mesh.sortObjects = !!b.set.normal.transparent;
    if (b.set.late) mesh.renderOrder = 10;                  // alpha-tested (leaves, mesh fencing, rebar): after the solid scene
    b.set.targets.add(mesh);
    const gid = new Map();
    for (const [uuid, g] of b.geoms) gid.set(uuid, mesh.addGeometry(g));
    for (const it of b.items) {
      const geom = b.geoms.get(it.o.geometry.uuid);
      const part = partFromExtras(parts.length, it.o.name || it.o.parent?.name, it.ud, geom, it.o.matrixWorld, it.mat.name);
      part.batch = mesh;
      part.context = b.ctx;
      part.noRay = /leaves|branches|VertexPlant/i.test(it.mat.name);       // foliage: millions of leaves, no use to a ray
      part.set = b.set;
      part.instanceId = mesh.addInstance(gid.get(it.o.geometry.uuid));
      mesh.setMatrixAt(part.instanceId, part.matrix0);
      mesh.setColorAt(part.instanceId, WHITE);
      parts.push(part);
      if (!byElement.has(part.element)) byElement.set(part.element, []);
      byElement.get(part.element).push(part);
    }
    (b.ctx ? setting : root).add(mesh);
    batchMeshes.push(mesh);
    onBuildProgress?.(++done / batchDefs.size);
  }
  /* geometry from the GLB is now inside the batches */
  gltf.scene.traverse(o => { if (o.isMesh) o.geometry.dispose(); });

  /* ---------- stage, storey and edit state -> each part ---------- */
  const storeyShown = { site: true, ground: true, first: true, roof: true };
  /* the as-built layer: records of what was really built, each replacing drawn elements */
  let asBuiltOn = false;
  const asBuiltEls = [...table.values()].filter(e => e.layer === "as_built");
  const replacedByAsBuilt = new Set(asBuiltEls.flatMap(e => e.replaces || []));
  for (const p of parts) if (table.get(p.element)?.layer === "as_built") p.asBuilt = true;
  const layerHidden = p => asBuiltOn ? replacedByAsBuilt.has(p.element) : p.asBuilt;
  const _m = new THREE.Matrix4(), _s = new THREE.Matrix4(), _t = new THREE.Matrix4();
  let stageValue = 1;

  function placePart(p, inT, outT) {
    const m = _m.copy(p.matrix0);
    if (inT < 1) {
      const e = easeOut(inT);
      if (p.style === "rise") {
        const y0 = p.bbox.min.y;
        _t.makeTranslation(0, y0, 0); _s.makeScale(1, Math.max(0.001, e), 1);
        m.premultiply(_t.clone().multiply(_s).multiply(_t.makeTranslation(0, -y0, 0)));
      } else if (p.style === "drop") {
        m.premultiply(_t.makeTranslation(0, (1 - e) * DROP, 0));
      }
    }
    if (outT > 0) {                          // coming out: sinks and flattens to its base
      const e = easeOut(outT), y0 = p.bbox.min.y;
      _t.makeTranslation(0, y0, 0); _s.makeScale(1, Math.max(0.001, 1 - e), 1);
      m.premultiply(_t.clone().multiply(_s).multiply(_t.makeTranslation(0, -y0, 0)));
    }
    if (p.pose) m.premultiply(p.pose);       // a door swung on its hinge (doors.js), in the viewer frame
    if (p.finishMesh) { p.finishMesh.matrix.copy(m); p.finishMesh.matrixWorldNeedsUpdate=true; }
    if (p.batch) p.batch.setMatrixAt(p.instanceId, m);
    else if (p.mesh) { p.mesh.matrix.copy(m); p.mesh.matrixWorldNeedsUpdate = true; }
  }

  function setVisible(p, vis) {
    if (p.finishMesh) p.finishMesh.visible=vis;
    if (p.batch) p.batch.setVisibleAt(p.instanceId, vis && !p.finishMesh);
    else if (p.mesh) p.mesh.visible = vis;
  }
  function setDoomed(p, on) {
    if (p.batch) p.batch.setColorAt(p.instanceId, on ? DOOMED : (p.clientTint || WHITE));
  }

  function paintPart(p,hex) {
    if(!p.batch)return;
    if(hex){const tint=new THREE.Color(hex),base=p.set.normal.color;
      tint.setRGB(tint.r/Math.max(.001,base.r),tint.g/Math.max(.001,base.g),tint.b/Math.max(.001,base.b));p.clientTint=tint;
    }else p.clientTint=null;
    setDoomed(p,p.now.doomed);
  }
  function coverFloor(p,material,tile) {
    if(!p.batch)return;
    if(p.finishMesh){p.finishMesh.removeFromParent();p.finishMesh.geometry.dispose();p.finishMesh=null;}
    if(material){
      const g=p.geometry.clone(),pos=g.attributes.position,uv=new Float32Array(pos.count*2),v=new THREE.Vector3();
      for(let i=0;i<pos.count;i++){v.fromBufferAttribute(pos,i).applyMatrix4(p.matrix0);uv[2*i]=v.x/tile[0];uv[2*i+1]=v.z/tile[1];}
      g.setAttribute('uv',new THREE.BufferAttribute(uv,2));
      const mesh=new THREE.Mesh(g,material);mesh.name=p.name;mesh.matrixAutoUpdate=false;
      p.batch.getMatrixAt(p.instanceId,mesh.matrix);mesh.matrixWorldNeedsUpdate=true;mesh.castShadow=p.batch.castShadow;mesh.receiveShadow=true;
      root.add(mesh);p.finishMesh=mesh;
    }
    setVisible(p,p.now.visible);
  }
  function applyStage(v, force = false) {
    stageValue = v;
    for (const set of sets.values()) {
      if (!set.finishStage) continue;
      const normal = progress(v, set.finishStage, .84) > .5 ? set.finished : set.roughCarrier;
      if (normal === set.normal) continue;
      const wasNormal = set.current !== set.xray;
      set.normal = normal;
      if (wasNormal) { set.current = normal; for (const mesh of set.targets) mesh.material = normal; }
    }
    let doomedCount = 0;
    for (const p of parts) {
      const inT = progress(v, p.stage_in, p.seq);
      const outT = p.stage_out ? progress(v, p.stage_out, p.seq_out) : 0;
      const built = inT > 0.001 && outT < 0.999;
      const vis = built && !p.hidden && !p.viewHidden && !layerHidden(p) && storeyShown[p.storey] !== false;   // viewHidden: "Hide doors"
      const doomed = vis && p.stage_out !== null && v > p.stage_out - 1 && outT < 1;
      p.now.visible = vis;
      p.now.solid = vis && p.collide && !p.passable && inT >= 0.999 && outT <= 0.001;      // passable: an open door
      p.now.present = built && !p.hidden && !layerHidden(p);                // built now, whatever is hidden from view
      p.now.doomed = doomed;
      if (doomed) doomedCount++;
      const L = p.last;
      if (force || vis !== L.vis) { setVisible(p, vis); L.vis = vis; }
      if (vis && (force || inT !== L.inT || outT !== L.outT)) { placePart(p, inT, outT); L.inT = inT; L.outT = outT; }
      if (force || doomed !== L.doomed) { setDoomed(p, doomed); L.doomed = doomed; }
    }
    /* a batch with nothing visible at this stage is switched off entirely: no draw call, no shadow pass. The house
       has ~74 materials across all 12 stages, but only the ones in use at a stage cost anything. */
    const live = new Map();
    for (const p of parts) if (p.batch && p.now.visible) live.set(p.batch, true);
    for (const b of batchMeshes) b.visible = live.has(b);
    if (masks.visible.length !== parts.length) resizeMasks();
    for (const p of parts) {
      masks.visible[p.index] = p.now.visible ? 1 : 0;
      masks.solid[p.index] = p.now.solid ? 1 : 0;
      masks.floor[p.index] = carriesFeet(p) ? 1 : 0;
      masks.present[p.index] = p.now.present && p.collide ? 1 : 0;
    }
    return doomedCount;
  }

  const masks = { floor: new Uint8Array(0), visible: new Uint8Array(0), solid: new Uint8Array(0), present: new Uint8Array(0), structural: new Uint8Array(0) };
  function resizeMasks() {
    masks.visible = new Uint8Array(parts.length);
    masks.solid = new Uint8Array(parts.length);
    masks.floor = new Uint8Array(parts.length);
    masks.present = new Uint8Array(parts.length);
    masks.structural = new Uint8Array(parts.length);
  }
  resizeMasks();

  /* ---------- edits: regenerate elements from parameters ---------- */
  /* catalogue names -> what the generator's GLBs call them */
  const ALIAS = { frame_grey: ["aluminium", "black_upvc", "frame_grey"], frame_white: ["upvc_white", "joinery", "frame_white"],
                  door_leaf: ["door_leaf", "joinery", "upvc_white"] };
  function materialFor(name, group) {
    /* materials.json glb_material: the shared GLB material a catalogue / element material name is drawn with */
    const mapped = materials?.[name]?.glb_material;
    const found = [mapped, ...(ALIAS[name] || []), name].filter(Boolean).find(n => materialsByName.has(n));
    if (found) name = found;
    const src = materialsByName.get(name) || materialsByName.values().next().value;
    if (!materialsByName.has(name)) console.warn(`house: material ${name} not in the GLB; using ${src?.name}`);
    return materialSet(src, group);
  }

  /* everything an element's geometry is made from: its own parameters, its openings (a removed opening is
     bricked up), and for a lintel or fixture its opening and host wall */
  function signature(id, tbl) {
    const el = tbl.get(id);
    if (!el) return "none";
    const rel = [];
    if (el.type === "wall") for (const o of el.openings || []) rel.push(tbl.get(o)?.removed ? "removed" : tbl.get(o)?.params);
    if (el.params?.opening) { const op = tbl.get(el.params.opening); rel.push(op?.params, op && tbl.get(op.params.host)?.params); }
    return JSON.stringify([el.params, el.openings || [], rel]);
  }

  /* what exists in the finished proposal (last stage), whatever is hidden from view: for the rules */
  function finalMask() {
    const N = sidecar.stages?.length || 1;
    const m = new Uint8Array(parts.length);
    for (const p of parts) m[p.index] = !p.hidden && !layerHidden(p) && progress(N, p.stage_in, p.seq) > 0.999 && !(p.stage_out && p.stage_out <= N) ? 1 : 0;
    return m;
  }

  /* current: Map id -> element after the edits (edits.js). Rebuilds what changed. */
  function applyElements(current, changedIds) {
    const touched = new Set();
    for (const id of changedIds) for (const d of dependents(id, current)) touched.add(d);
    for (const id of touched) {
      const el = current.get(id);
      // drop the previously generated parts of this element
      const old = byElement.get(id) || [];
      for (const p of old.filter(p => p.generated)) {
        p.mesh.removeFromParent(); p.mesh.geometry.dispose();
        p.set.targets.delete(p.mesh);
        p.dead = true;
      }
      const baked = old.filter(p => !p.generated);
      byElement.set(id, baked);
      if (!el || el.removed) { for (const p of baked) p.hidden = true; continue; }
      const same = signature(id, table) === signature(id, current);
      const gen = same ? null : regenerate(el, current);
      if (!gen) { for (const p of baked) p.hidden = false; continue; }
      for (const p of baked) p.hidden = true;
      for (const g of gen) {
        const set = materialFor(g.material, g.props.group || el.meta.group);
        const mesh = new THREE.Mesh(g.geometry, set.normal);
        mesh.name = g.name;
        mesh.matrixAutoUpdate = false;
        mesh.castShadow = mesh.receiveShadow = true;
        set.targets.add(mesh);
        generated.add(mesh);
        const p = partFromExtras(parts.length, g.name, g.props, g.geometry, new THREE.Matrix4(), g.material);
        p.mesh = mesh; p.set = set; p.generated = true;
        p.asBuilt = el.layer === "as_built";
        mesh.material = set.current || set.normal;
        mesh.userData.part = p.index;
        parts.push(p);
        byElement.get(id).push(p);
      }
    }
    // compact away dead generated parts so indices stay dense
    const alive = parts.filter(p => !p.dead);
    parts.length = 0;
    alive.forEach((p, i) => { p.index = i; p.last = { inT: -1, outT: -1, vis: null, doomed: null }; parts.push(p); });
    resizeMasks();
    applyStage(stageValue, true);
    return touched;
  }

  /* a part's pose changed (a door opening): re-place it with its stage state, and its solid flag */
  function repose(p) {
    if (p.now.visible) placePart(p, p.last.inT < 0 ? 1 : p.last.inT, p.last.outT < 0 ? 0 : p.last.outT);
    p.now.solid = p.now.visible && p.collide && !p.passable && progress(stageValue, p.stage_in, p.seq) >= 0.999
      && !(p.stage_out && progress(stageValue, p.stage_out, p.seq_out) > 0.001);
    if (masks.solid.length === parts.length) {
      masks.solid[p.index] = p.now.solid ? 1 : 0;
      masks.floor[p.index] = carriesFeet(p) ? 1 : 0;
    }
  }

  /* free the GPU and the memory a version holds (the Quest keeps one version at a time) */
  function dispose() {
    root.removeFromParent();
    const textures = new Set();
    for(const p of parts)if(p.finishMesh){p.finishMesh.removeFromParent();p.finishMesh.geometry.dispose();p.finishMesh=null;}
    for (const b of batchMeshes) b.dispose();
    for (const m of generated.children) m.geometry?.dispose();
    for (const s of sets.values()) for (const m of [s.normal, s.xray]) {
      for (const k of ["map", "normalMap", "aoMap", "roughnessMap", "metalnessMap", "alphaMap", "emissiveMap"]) if (m[k]) textures.add(m[k]);
      m.dispose();
    }
    for (const t of textures) t.dispose();
    for (const m of materialsByName.values()) m.dispose();
    parts.length = 0;
  }

  /* the room a point is in (rooms are elements with a plan polygon and a floor level) */
  function roomAt(x, y, z) {
    let best = null;
    for (const el of table.values()) {
      if (el.type !== "room") continue;
      const poly = el.params.polygon, fy = el.params.floor;
      if (y < fy - 0.35 || y > fy + 2.7) continue;
      let inside = false;
      for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const [xi, zi] = poly[i], [xj, zj] = poly[j];
        if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) inside = !inside;
      }
      if (inside && (!best || fy > best.params.floor)) best = el;
    }
    return best;
  }

  const bounds = new THREE.Box3();
  for (const p of parts) if (p.group !== "ground" && p.storey !== "site" && !p.context) bounds.union(p.bbox);      // the house, not the street
  if (bounds.isEmpty()) for (const p of parts) bounds.union(p.bbox);

  return {
    root, parts, sets, table, byElement, masks, storeyShown, sidecar, bounds,
    applyStage, applyElements, roomAt, finalMask, repose, dispose, paintPart, coverFloor,
    get stage() { return stageValue; },
    setStorey(s, on) { storeyShown[s] = on; applyStage(stageValue, true); },
    get hasAsBuilt() { return asBuiltEls.length > 0; },
    get asBuilt() { return asBuiltOn; },
    setAsBuilt(on) { asBuiltOn = on; applyStage(stageValue, true); },
    drawCalls() { return root.children.filter(c => c.isBatchedMesh).length + generated.children.length; },
    liveCalls() { return root.children.filter(c => c.isBatchedMesh && c.visible).length + generated.children.filter(c => c.visible).length; },
    settingCalls() { return setting.children.length; },
  };
}
