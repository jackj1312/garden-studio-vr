import {studioAsset} from '../studio-layout-service.js';
const node=(tag,text)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;return n;};
const option=(key,label)=>new Option(label,key);
const clean=s=>String(s||'').replace(/[_-]+/g,' ');
function options(select,entries,current){
 const sig=JSON.stringify(entries);if(select.dataset.options!==sig){select.replaceChildren(...entries.map(([v,t])=>option(v,t)));select.dataset.options=sig;}
 if(current!=null&&select.value!==current)select.value=current;
}
export function createFurniturePanel(action){
 const el=node('aside');el.className='gd-panel fu-panel';el.dataset.furnishPanel='';el.hidden=true;el.setAttribute('aria-label','Furnishing editor');
 el.innerHTML=`<header class="gd-header"><div class="gd-brand"><span class="gd-kicker">Garden Studio</span><h2>Furnish a room</h2><span data-fu-context class="gd-context"></span></div><div class="gd-head-actions"><button type="button" data-editor-help="furnish">How to use</button><button type="button" data-fu="minimise" aria-label="Minimise tools">−</button><button type="button" data-fu="close" aria-label="Close furnishing editor">×</button></div></header>
 <div class="gd-body"><section class="gd-section"><div class="gd-segment"><button data-fu="bird">Bird’s-eye</button><button data-fu="stand">Walking</button><button data-fu="vr" hidden>Enter VR</button></div><label class="gd-field">Room<select data-fu-field="room"></select></label></section>
 <section class="gd-section"><h3>Catalogue</h3><div class="gd-fields"><label class="gd-field">Room type<select data-fu-field="roomType"></select></label><label class="gd-field">Kind<select data-fu-field="kind"></select></label><label class="gd-field">Style<select data-fu-field="style"></select></label><label class="gd-field">Search<input data-fu-field="query" type="search" placeholder="e.g. armchair"></label></div><div class="fu-grid" data-stock></div><p class="gd-caption" data-count></p></section>
 <section class="gd-section"><h3>Selection</h3><select data-fu-field="selected" aria-label="Selected item"></select><label class="gd-field">Angle in degrees<input type="number" step="5" data-fu-field="angle"></label><div class="gd-segment"><button data-fu="rotate-left">↶ 15°</button><button data-fu="rotate-right">↷ 15°</button><button data-fu="PageUp">Raise 1 cm</button><button data-fu="PageDown">Lower 1 cm</button><button data-fu="copy">Copy</button><button data-fu="delete">Delete</button></div></section>
 <section class="gd-section"><h3>Room finishes</h3><label class="gd-field">Individual wall face<select data-fu-field="face"></select></label><label class="gd-field">Wall colour<input data-fu-field="colour" type="color"></label><button data-fu="reset-wall">Original wall colour</button><label class="gd-field">This room’s floor<select data-fu-field="floor"></select></label></section>
 <section class="gd-section"><button data-fu="plants">Place a garden plant or tree</button> <a href="/plan/">Open client room planner</a></section></div>
 <footer class="gd-footer"><div data-status role="status" class="gd-status"></div><div class="gd-segment"><button data-fu="undo">Undo</button><button data-fu="redo">Redo</button><button data-fu="save">Save layout</button><button data-fu="reload" hidden>Reload</button></div></footer>`;
 document.body.append(el);const find=k=>el.querySelector(k);let current=null,key='';
 navigator.xr?.isSessionSupported('immersive-vr').then(ok=>find('[data-fu=vr]').hidden=!ok).catch(()=>{});
 el.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b||b.disabled)return;
  if(b.dataset.stockId){action('add',b.dataset.stockId);return;}const cmd=b.dataset.fu;if(!cmd)return;
  e.stopPropagation();action(cmd);
 });
 el.addEventListener('change',e=>{const field=e.target.dataset.fuField;if(field)action(field,field==='angle'?Number(e.target.value):e.target.value);});
 el.addEventListener('input',e=>{if(e.target.dataset.fuField==='query')action('query',e.target.value);});
 const field=k=>find('[data-fu-field="'+k+'"]');
 function update(s){
   find('[data-fu=minimise]').textContent=s.collapsed?'Show tools':'−';
  current=s;el.hidden=!s.active;if(!s.active)return;
  find('[data-fu-context]').textContent=s.version+' · '+(s.room?.label||s.room?.name||'Choose a room');
  options(field('room'),s.rooms.map(r=>[r.id,r.label||r.name||r.id]),s.room?.id);
  options(field('roomType'),[['current','This room'],['','All rooms'],...s.roomTypes.map(x=>[x,clean(x)])],s.filters.roomType);
  options(field('kind'),[['','All kinds'],...s.kinds.map(x=>[x,clean(x)])],s.filters.kind);
  options(field('style'),[['','All styles'],...s.styles.map(x=>[x,clean(x)])],s.filters.style);
  if(document.activeElement!==field('query'))field('query').value=s.filters.query;
  const signature=JSON.stringify([s.filtered.map(c=>c.id),s.pending]);if(key!==signature){key=signature;
   const buttons=s.filtered.map(c=>{const b=node('button'),img=node('img'),label=node('span',c.name||clean(c.kind));b.type='button';b.dataset.stockId=c.id;img.loading='lazy';img.alt='';img.src=studioAsset('/tools/library/kit/'+c.thumbnail);b.setAttribute('aria-pressed',String(c.id===s.pending));b.title=(c.name||c.kind)+' · '+clean(c.style);b.append(img,label);return b;});
   find('[data-stock]').replaceChildren(...buttons);
  }
  find('[data-count]').textContent=s.filtered.length+' matching catalogue entries';
  const list=s.items.filter(f=>f.room===s.room?.id);options(field('selected'),[['','Choose a piece'],...list.map(f=>[f.id,f.label||f.name||f.id])],s.selected?.id||'');
  if(document.activeElement!==field('angle'))field('angle').value=s.selected?Math.round(s.selected.rotation*10)/10:'';
  field('angle').disabled=!s.selected;
  const faces=s.room?.wallFaces||[];options(field('face'),[['','Select a wall'],...faces.map((f,i)=>[f.id,f.label||f.name||'Wall '+(i+1)])],s.face||'');
  field('colour').disabled=!s.face;field('colour').value=s.colour||'#e6dfd3';
  options(field('floor'),[['','Original covering'],...s.floors.map(f=>[f.id,f.name])],s.floor||'');
  for(const cmd of ['rotate-left','rotate-right','PageUp','PageDown','copy','delete'])find('[data-fu='+cmd+']').disabled=!s.selected;
  find('[data-fu=undo]').disabled=!s.undo;find('[data-fu=redo]').disabled=!s.redo;find('[data-fu=save]').disabled=!s.dirty||s.saving;
  find('[data-fu=reload]').hidden=!s.conflict;find('[data-fu=bird]').setAttribute('aria-pressed',String(s.bird));find('[data-fu=stand]').setAttribute('aria-pressed',String(!s.bird));
  const status=find('[data-status]');status.textContent=s.status||(s.saving?'Saving…':s.dirty?'Unsaved changes':'Saved · revision '+s.revision);status.classList.toggle('fu-blocked',s.verdict?.ok===false);
 }
 return {update,el};
}

