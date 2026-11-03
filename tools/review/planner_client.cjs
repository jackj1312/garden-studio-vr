// Runs inside the owner's existing browser slot. Opens only read-only UI paths.
const assert=require('node:assert/strict');
module.exports=async function checkPlanner(page,base='https://127.0.0.1:8450',site='house-wip'){
  const url=new URL('/plan/',base);url.searchParams.set('site',site);url.searchParams.set('version','as_built_now');url.hash='before/room/R-g-living';
  await page.goto(url.href,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.planner?.session?.ready && window.planner.room?.id==='R-g-living');
  const data=await page.evaluate(()=>({site:planner.db.site,room:planner.room.id,version:planner.session.version,
    count:planner.db.kit.items.length,shared:planner.state.runtime,selected:planner.selected,dirty:planner.session.layout.dirty,
    location:location.href,wallOptions:document.querySelector('[aria-label="Wall face to paint"]').options.length}));
  assert.equal(data.site,site);assert.equal(data.version,'as_built_now');assert.equal(data.shared,true);assert.ok(data.wallOptions>1);
  assert.ok(data.location.endsWith('#before/room/R-g-living'));
  await page.click('#addBtn');await page.waitForSelector('.kit-filters');
  const filters=await page.$$('.kit-filters select');
  await filters[0].select('');const count=await page.$$eval('.kit-tile',nodes=>nodes.length);assert.equal(count,data.count);
  await filters[1].select('sofa');await filters[2].select('industrial');
  assert.ok(await page.$('.kit-tile[data-catalogue-id="industrial.sofa"]'));
  const picture=await page.$eval('[data-catalogue-id="industrial.sofa"] img',async img=>{await img.decode();return [img.naturalWidth,img.naturalHeight];});
  assert.ok(picture[0]>=240 && picture[1]>=240);
  await page.keyboard.press('Escape'); await page.click('[data-editor-help="planner"]');
  await page.waitForSelector('#studio-help-dialog[open]'); await page.keyboard.press('Escape');
  await page.click('#threeBtn');
  await page.waitForFunction(()=>planner.view3d?.furniture?.group.children.some(o=>o.visible && o.count>0),{timeout:120000});
  const meshes=await page.evaluate(()=>planner.view3d.furniture.group.children.filter(x=>x.visible).length);
  assert.equal(await page.evaluate(()=>planner.session.layout.dirty),data.dirty);
  return {...data,catalogueCount:count,picture,meshBatches:meshes};
};
