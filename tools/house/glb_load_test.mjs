// Load GLBs headless with three's GLTFLoader, the way house.html loads them (meshopt decoder registered), and fail on any
// error (CORRECTIONS-LOG 190: a texture with no image source crashed the Quest at "loading model").
//   node tools/house/glb_load_test.mjs <file.glb> [...]        (THREE_DIR=<path to node_modules/three> to choose the copy)
// Images are not decoded (no DOM): createImageBitmap is stubbed, so the loader runs every step up to the pixels.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const CANDIDATES = [process.env.THREE_DIR, ...fs.readdirSync(path.join(process.env.HOME, "Documents/ChatGPT"), { withFileTypes: true })
  .filter(d => d.isDirectory()).map(d => path.join(process.env.HOME, "Documents/ChatGPT", d.name, "node_modules/three"))].filter(Boolean);
const THREE_DIR = CANDIDATES.find(d => fs.existsSync(path.join(d, "examples/jsm/loaders/GLTFLoader.js")));
if (!THREE_DIR) { console.error("glb_load_test: no local three found (set THREE_DIR); installing one needs Jack's OK"); process.exit(3); }
globalThis.self = globalThis;
globalThis.createImageBitmap = async (blob) => { if (!blob || !(blob.size > 0)) throw new Error("empty image blob"); return { width: 1, height: 1, close() {} }; };
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, opts) => {
  const u = String(url);
  if (u.startsWith("blob:")) { const b = await import("node:buffer"); const blob = b.resolveObjectURL(u); if (!blob) throw new Error("bad blob url"); return new Response(blob); }
  return realFetch(url, opts);
};
const imp = (rel) => import(pathToFileURL(path.join(THREE_DIR, rel)).href);
const THREE = await imp("build/three.module.js");
const { GLTFLoader } = await imp("examples/jsm/loaders/GLTFLoader.js");
const { MeshoptDecoder } = await imp("examples/jsm/libs/meshopt_decoder.module.js");
let bad = 0;
for (const f of process.argv.slice(2)) {
  const buf = fs.readFileSync(f);
  const loader = new GLTFLoader(); loader.setMeshoptDecoder(MeshoptDecoder);
  const errs = [];
  const origErr = console.error, origWarn = console.warn;
  console.error = (...a) => errs.push(a.join(" ")); console.warn = (...a) => { const s = a.join(" "); if (/error|fail|cannot/i.test(s)) errs.push(s); };
  try {
    const g = await new Promise((res, rej) => loader.parse(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength), "", res, rej));
    let meshes = 0, maps = 0; g.scene.traverse(o => { if (o.isMesh) { meshes++; const m = [].concat(o.material); for (const mm of m) for (const k of ["map", "normalMap", "roughnessMap", "metalnessMap", "aoMap"]) if (mm[k]) maps++; } });
    console.error = origErr; console.warn = origWarn;
    if (errs.length) { bad++; console.log(`FAIL ${f}: ${errs.length} loader errors, first: ${errs[0].slice(0, 300)}`); }
    else console.log(`ok   ${f}: ${meshes} meshes, ${maps} texture slots (three ${THREE.REVISION})`);
  } catch (e) {
    console.error = origErr; console.warn = origWarn; bad++;
    console.log(`FAIL ${f}: ${String(e && e.message || e).slice(0, 300)}`);
  }
}
process.exit(bad ? 1 : 0);
