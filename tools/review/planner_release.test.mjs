import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {mkdir, mkdtemp, readFile, rename, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {loadAll} from '../../src/planner/data.js';
import {ChangeStore} from '../../src/planner/store.js';

const root=fileURLToPath(new URL('../../',import.meta.url)), site='house-wip', version='approved_2b';
const local='assets/sites/'+site+'/', legacy='assets/sites/house/', specFile='spec/spec_v1.json';
const catalogueFile='spec/catalogue_v1.json', elementFile=version+'_elements.json';
const hall=id=>({id:'R-g-hall',storey:'ground',polygon:[[0,0],[id,0],[id,-1],[0,-1]]});
const signed=width=>({versions:{after:{elements:version,rooms:[hall(width)],items:[]}},finishes:[]});
const catalogue=id=>({entries:[{id}]});
const manifest={versions:[{id:version,elements:elementFile}]};
const shared={'assets/planner/house/doors.json':{versions:{}},'tools/library/kit/catalogue.json':{items:[]}};
const tables=id=>({elements:[],source:id});
function stub(t,files) {
  const requests=[];
  t.mock.method(globalThis,'fetch',async(url,options={})=>{
    const u=new URL(url,'https://studio.test/'),resource=u.pathname.slice(1);
    requests.push({url:u.pathname+u.search,resource,method:options.method||'GET',body:options.body});
    const value=await files(resource,options);
    return typeof value==='number'||!value?new Response(null,{status:value||404}):Response.json(value);
  });
  return requests;
}

test('planner opens a real promoted release even if both mutable copies change; client requests retain their existing owner',async t=>{
  const project=await mkdtemp(path.join(tmpdir(),'planner-release-'));
  t.after(()=>rm(project,{recursive:true,force:true}));
  async function write(relative,data) {
    const file=path.join(project,relative);
    await mkdir(path.dirname(file),{recursive:true});
    await writeFile(file+'.new',typeof data==='string'?data:JSON.stringify(data));
    await rename(file+'.new',file); // Preserve any hard link to the immutable release.
  }
  const candidate='assets/sites/private-build/';
  await write(candidate+'versions.json',manifest); await write(local+'versions.json',{versions:[]});
  await write(candidate+specFile,signed(1.810)); await write(candidate+catalogueFile,catalogue('released-oak'));
  await write(candidate+elementFile,tables('issued-elements'));
  for(const name of ['materials.json','regs_map.json','regs.json','summary.json','spec_check.json','setting_front.glb','setting_front_lod.glb']){
    await write(candidate+name,'{}');
  }
  execFileSync('python3',['-B','-c',[
    'import sys','from pathlib import Path','sys.path.insert(0,sys.argv[1])',
    'from publish_candidate import promote','promote(Path(sys.argv[2]),Path(sys.argv[3]))',
  ].join('\n'),path.join(root,'tools/house'),path.join(project,candidate),path.join(project,local)]);
  const published=JSON.parse(await readFile(path.join(project,local+'versions.json')));
  const release=local+'releases/'+published.furnish_release+'/';
  assert.equal(published.versions[0].elements,'releases/'+published.furnish_release+'/'+elementFile);
  for(const prefix of [local,legacy]) {
    await write(prefix+specFile,signed(1.645)); await write(prefix+catalogueFile,catalogue('old-oak'));
    await write(prefix+elementFile,tables('old-elements'));
  }
  const requests=stub(t,async resource=>{
    if(resource==='spec/changes')return {changes:[]};
    if(Object.hasOwn(shared,resource))return shared[resource];
    try{return JSON.parse(await readFile(path.join(project,resource)));}catch(e){if(e.code==='ENOENT')return 404;throw e;}
  });
  const data=await loadAll(site),h=data.versions.after.roomById.get('R-g-hall');
  assert.equal(h.polygon[1][0],1.810);
  assert.equal(data.elements.after.source,'issued-elements');
  assert.ok(data.entries.has('released-oak'));
  assert.deepEqual(requests.filter(r=>/spec_v1|catalogue_v1|_elements\.json/.test(r.resource)).map(r=>r.resource),
    [release+specFile,release+catalogueFile,release+elementFile]);
  assert.equal(data.site,site);
  const history=new ChangeStore(data.specSite);
  await history.load();
  const added=await history.add({version:'after',op:'room.walls',target:{room:'R-g-hall'},after:{colour:'#888888'}});
  assert.equal(history.mode,'server'); assert.equal(added.site,'house');
  const api=requests.filter(r=>r.resource==='spec/changes');
  assert.deepEqual(api.map(r=>[r.url,r.method]),[
    ['/spec/changes?site=house&view=planner','GET'],['/spec/changes?site=house&view=planner','POST']]);
  assert.equal(JSON.parse(api[1].body).change.site,'house');
});

for(const status of [403,404])test('legacy Battle Road resolves its signed fallback on '+status,async t=>{
  const files={...shared,[local+'versions.json']:manifest,[local+specFile]:status,[local+elementFile]:tables('local geometry'),
    [legacy+specFile]:signed(1.645),[legacy+catalogueFile]:catalogue('legacy-oak')};
  const requests=stub(t,k=>files[k]),result=await loadAll(site);
  assert.ok(result.entries.has('legacy-oak'));assert.equal(result.elements.after.source,'local geometry');
  assert.deepEqual(requests.filter(r=>r.resource.endsWith(specFile)).map(r=>r.resource),[local+specFile,legacy+specFile]);
});

test('an unversioned site takes its own signed spec and catalogue when they are present',async t=>{
  const other='other-client',own='assets/sites/'+other+'/',files={...shared,[own+'versions.json']:manifest,
    [own+specFile]:signed(2.4),[own+catalogueFile]:catalogue('client-oak'),[own+elementFile]:tables('client')};
  const requests=stub(t,k=>files[k]),data=await loadAll(other);
  assert.equal(data.versions.after.rooms[0].polygon[1][0],2.4);
  assert.equal(new ChangeStore(data.specSite).url(),'/spec/changes?site=other-client&view=planner');
  assert.ok(data.entries.has('client-oak'));assert.ok(!requests.some(r=>r.resource.startsWith(legacy)));
});

for(const [label,client,release,status] of [
  ['unavailable activated release',site,'deadc0dedeadc0dedead',404],
  ['failed legacy site service',site,null,500],['other missing client','other-client',null,403],
]){
  test(label+' does not open the different candidate design',async t=>{
    const home='assets/sites/'+client+'/',own=release?home+'releases/'+release+'/':home;
    const files={...shared,[home+'versions.json']:{...manifest,furnish_release:release},
      [own+specFile]:status,[legacy+specFile]:signed(1.645),[legacy+catalogueFile]:catalogue('wrong')};
    const requests=stub(t,k=>files[k]);
    await assert.rejects(loadAll(client),e=>e.status===status&&e.message.includes(own+specFile));
    assert.ok(!requests.some(r=>r.resource.startsWith(legacy)));
  });
}
