import test from 'node:test';
import assert from 'node:assert/strict';
import {previewPrefix,studioAsset,openLayoutEditor,layoutFetcher} from '../../src/studio-layout-service.js';
import {createRequests} from '../../src/house/requests.js';

const key='0123456789abcdef0123',root='/preview/'+key+'/',version='approved_2b';
function at(t,path){
  const original=globalThis.location;globalThis.location=new URL(path,'https://studio.local:8450');
  t.after(()=>{if(original)globalThis.location=original;else delete globalThis.location;});
}
test('only a versioned package prefixes studio assets',()=>{
  const live=new URL('https://studio.local:8450/house.html?site=house-wip');
  for(const path of ['/assets/sites/house-preview/versions.json','/tools/library/kit/catalogue.json']){
    assert.equal(studioAsset(path,live),path);
    assert.equal(studioAsset(path,new URL(root+'house.html',live)),root+path.slice(1));
  }
  assert.equal(previewPrefix(new URL('/preview/not-a-release/house.html',live)),'');
});
test('preview reads its own saved layout, preserves edits and rejects every write locally',async t=>{
  at(t,root+'house.html?site=house-preview&mode=architect&edit=1');
  const paths=[],saved={site:'house-wip',revision:7,items:[{id:'client-table'}],garden:{schema:1,objects:[{id:'bed-1'}]}};
  t.mock.method(globalThis,'fetch',async p=>{paths.push(String(p));return Response.json(saved);});
  const get=layoutFetcher('house-preview',version),layout=await (await get('/layout?arbitrary')).json();
  assert.equal(layout.site,'house-preview');assert.equal(layout.revision,7);assert.deepEqual(layout.items,saved.items);
  assert.deepEqual(layout.garden,saved.garden);
  for(const method of ['POST','PUT','DELETE'])assert.equal((await get('/layout',{method})).status,405);
  assert(openLayoutEditor('edit','house-preview',version));
  assert.deepEqual(paths,[root+'assets/sites/house-preview/layout/'+version+'.json']);
});
test('a garden-only preview uses its packaged furnishing seed for the same version',async t=>{
  at(t,root+'house.html?site=house-preview');const paths=[];
  t.mock.method(globalThis,'fetch',async p=>{
    paths.push(p);return p.includes('/layout/')?Response.json({items:[],garden:{objects:['saved garden']},wallColours:{b:'green'}}):
      Response.json({items:[{id:'seed-chair'}],wallColours:{a:'red',b:'blue'}});
  });
  const l=await (await layoutFetcher('house-preview',version)('/layout')).json();
  assert.deepEqual(l.items,[{id:'seed-chair'}]);assert.deepEqual(l.wallColours,{a:'red',b:'green'});
  assert.deepEqual(l.garden,{objects:['saved garden']});assert.deepEqual(paths,[root+'assets/sites/house-preview/layout/'+version+'.json',root+'assets/sites/house-preview/furnish/'+version+'/seed.json']);
});
test('preview requests cannot create a client record or read old requests or inspection notes',async t=>{
  at(t,root+'house.html');t.mock.method(globalThis,'fetch',()=>assert.fail('preview request escaped'));
  const api=createRequests({site:'house-preview',getVersion:()=>version,mode:'customer',readOnly:true});
  assert.deepEqual(await api.list(),[]);assert.deepEqual(await api.loadInspection(15),{checks:{}});
  await assert.rejects(api.submit({}),/read-only/);await assert.rejects(api.uploadAudio('old-id',null),/read-only/);
  await assert.rejects(api.saveInspection(15,{}),/read-only/);
});
