// Verify placement, final-stage filtering and metadata removal before a paid import.
const fs=require('node:fs/promises'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const {createRequire}=require('node:module'),{execFileSync}=require('node:child_process'),crypto=require('node:crypto');
const requireTool=createRequire(path.join(os.homedir(),'Documents/ChatGPT/.tools/gltf/package.json'));
(async()=>{
 const {Document,NodeIO}=requireTool('@gltf-transform/core');
 const tmp=await fs.mkdtemp(path.join(os.tmpdir(),'house-unreal-test-'));
 const site=path.join(tmp,'site'),out=path.join(tmp,'out'),folder=path.join(site,'furnish/approved_2b/bakes');
 await fs.mkdir(folder,{recursive:true});
 const doc=new Document(),buffer=doc.createBuffer(),scene=doc.createScene();
 const mesh=doc.createMesh('Private source drawing');
 const p=doc.createPrimitive().setAttribute('POSITION',doc.createAccessor().setType('VEC3').setArray(new Float32Array([0,0,0,1,0,0,0,1,0])).setBuffer(buffer)).setIndices(doc.createAccessor().setType('SCALAR').setArray(new Uint16Array([0,1,2])).setBuffer(buffer));
 mesh.addPrimitive(p);
 scene.addChild(doc.createNode('Private address').setTranslation([2,3,4]).setMesh(mesh).setExtras({element:'keep',drawing:'/private/plan.pdf'}));
 scene.addChild(doc.createNode('Demolished').setTranslation([900,0,0]).setMesh(mesh).setExtras({stage_out:3}));
 scene.addChild(doc.createNode('Replacement').setTranslation([800,0,0]).setMesh(mesh).setExtras({element:'old'}));
 const bytes=await new NodeIO().writeBinary(doc);
 await fs.writeFile(path.join(folder,'model.glb'),bytes);
 await fs.writeFile(path.join(folder,'latest.json'),JSON.stringify({model:'furnish/approved_2b/bakes/model.glb',modelSHA256:crypto.createHash('sha256').update(bytes).digest('hex'),items:[]}));
 await fs.writeFile(path.join(site,'approved_2b_elements.json'),JSON.stringify({elements:[{layer:'as_built',replaces:['old']}]}));
 const result=execFileSync(process.execPath,['tools/unreal/house_bundle.mjs',site,out,'--include-material-textures'],{encoding:'utf8'});
 const data=await fs.readFile(path.join(out,'House.gltf'),'utf8');
 assert(!/Private|private|plan.pdf|Demolished/.test(data));
 const info=JSON.parse(await fs.readFile(path.join(out,'scene.json')));
 assert.deepEqual(Object.values(info.bounds),[[[2,-4,3],[3,-4,4]]]);
 console.log('House render bundle PASS',result.trim());
})().catch(e=>{console.error(e);process.exitCode=1;});
