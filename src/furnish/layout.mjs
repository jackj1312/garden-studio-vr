/* The viewer and planner use this same versioned revision and undo stack.
 * Geometry edits use checkGroup before committing the real host + children. */
import {attachLocally,descendants,moveGroup} from './placement.mjs';

const empty=()=>({items:[],wallColours:{},roomFloors:{}});
const copy=v=>structuredClone(v);
function equal(a,b) {
  if (a===b) return true;
  if (!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b)) return false;
  const keys=Object.keys(a);
  return keys.length===Object.keys(b).length&&keys.every(k=>Object.hasOwn(b,k)&&equal(a[k],b[k]));
}
function freeze(v) {
  if (!v||typeof v!=='object'||Object.isFrozen(v)) return v;
  for (const val of Object.values(v)) freeze(val);
  return Object.freeze(v);
}
function snapshot(v) {
  if (!Array.isArray(v?.items)||!v.wallColours||!v.roomFloors) throw new Error('Invalid interior layout');
  return freeze({items:v.items,wallColours:v.wallColours,roomFloors:v.roomFloors});
}
function validItem(v) {
  if (!v?.id||!Array.isArray(v.position)||!Array.isArray(v.size)||!v.host||!Number.isFinite(v.rotation)) throw new Error('Invalid furniture pose');
  return v;
}

export class FurnitureLayout {
  #state=freeze(empty()); #base=this.#state; #undo=[]; #redo=[]; #revision=0;
  #ticket=0; #saving=null; #url; #fetch; #notify; #storage; #draftKey;
  loaded=false; conflict=false;

  constructor({site,version,onChange=()=>{},fetcher=globalThis.fetch,storage}={}) {
    if (![site,version].every(v=>typeof v==='string'&&/^[a-z0-9][a-z0-9_-]{0,63}$/.test(v))) throw new Error('Choose a site and version');
    this.site=site; this.version=version; this.#fetch=fetcher; this.#notify=onChange;
    this.#url='/layout?'+new URLSearchParams({site,version});
    this.#draftKey='garden-studio/furnish/1/'+site+'/'+version;
    try {this.#storage=storage===undefined?globalThis.localStorage:storage;} catch {this.#storage=null;}
  }
  get items() {return this.#state.items;}
  get wallColours() {return this.#state.wallColours;}
  get roomFloors() {return this.#state.roomFloors;}
  get revision() {return this.#revision;}
  get dirty() {return !equal(this.#state,this.#base);}
  get canUndo() {return !!this.#undo.length;}
  get canRedo() {return !!this.#redo.length;}
  get saving() {return this.#saving!==null;}
  get(id) {const it=this.items.find(v=>v.id===id); return it?copy(it):undefined;}

  #remember() {
    try {
      if (this.dirty) this.#storage?.setItem(this.#draftKey,JSON.stringify({revision:this.#revision,base:this.#base,state:this.#state}));
      else this.#storage?.removeItem(this.#draftKey);
    } catch { /* A full or disabled device store leaves the in-memory draft intact. */ }
  }
  #draft() {
    try {
      const raw=this.#storage?.getItem(this.#draftKey); if (!raw) return null;
      const v=JSON.parse(raw);
      if (!Number.isSafeInteger(v.revision)||v.revision<0) return null;
      return {revision:v.revision,base:snapshot(v.base),state:snapshot(v.state)};
    } catch {return null;}
  }
  #change(next,label) {
    if (!this.loaded) throw new Error('Load this version before editing');
    if (equal(next,this.#state)) return false;
    this.#undo.push({state:this.#state,label}); if (this.#undo.length>80) this.#undo.shift();
    this.#redo=[]; this.#state=freeze(next);this.#ticket++;
    this.#remember();this.#notify(this,label);return true;
  }
  put(item,label='Edit furniture') {return this.putMany(moveGroup(this.items,validItem(item)),label);}
  putMany(items,label='Edit group') {
    const values=new Map(items.map(i=>[i.id,copy(validItem(i))]));
    if (values.size!==items.length) throw new Error('Duplicate furniture ID');
    const list=this.items.map(it=>{
      if (!values.has(it.id)) return it;
      const next=values.get(it.id);values.delete(it.id);return next;
    });
    const merged=[...list,...values.values()], supplied=new Set(items.map(it=>it.id));
    const attached=merged.map(it=>supplied.has(it.id)?attachLocally(it,merged.find(p=>p.id===it.host?.id)):it);
    return this.#change({...this.#state,items:attached},label);
  }
  remove(id,label='Delete furniture') {
    const ids=descendants(this.items,id);
    return this.#change({...this.#state,items:this.items.filter(it=>!ids.has(it.id))},label);
  }
  setWalls(ids,colour) {
    if (colour!=null && !/^#[\da-f]{6}$/i.test(colour)) throw new Error('Use a six-digit wall colour');
    const walls={...this.wallColours};
    for (const id of ids) {if (colour==null) delete walls[id]; else walls[id]=colour;}
    return this.#change({...this.#state,wallColours:walls},'Wall colour');
  }
  setWall(id,colour) {return this.setWalls([id],colour);}
  setFloor(id,key) {
    const floors={...this.roomFloors};
    if (key==null) delete floors[id]; else floors[id]=key;
    return this.#change({...this.#state,roomFloors:floors},'Floor covering');
  }
  #travel(from,to,verb) {
    const entry=from.pop(); if (!entry) return false;
    to.push({state:this.#state,label:entry.label});this.#state=entry.state;this.#ticket++;
    this.#remember();this.#notify(this,verb+' '+entry.label);return true;
  }
  undo() {return this.#travel(this.#undo,this.#redo,'Undo');}
  redo() {return this.#travel(this.#redo,this.#undo,'Redo');}

  async #request(method,body) {
    const fetcher=this.#fetch;
    const response=await fetcher(this.#url,{method,cache:'no-store',...(body?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
    if (!response.ok) {
      let data; try {data=await response.json();} catch { /* may be a plain HTTP error */ }
      const e=new Error(data?.error||'Could not '+method.toLowerCase()+' the layout ('+response.status+')');
      e.status=response.status;e.currentRevision=data?.currentRevision??data?.revision;throw e;
    }
    const v=await response.json();
    if (v.site!==this.site||v.version!==this.version||!Number.isSafeInteger(v.revision)||v.revision<0) throw new Error('Wrong site, version or revision');
    return v;
  }
  async load({discardDraft=false}={}) {
    if (this.#saving) await this.#saving;
    const ticket=++this.#ticket;
    const draft=discardDraft?null:(this.dirty?{state:this.#state,base:this.#base,revision:this.#revision}:this.#draft());
    let remote;
    try {remote=await this.#request('GET');}
    catch(e) {if (!draft||e.status) throw e;}
    if (ticket!==this.#ticket) return this;
    this.#undo=[];this.#redo=[];
    if (draft) {
      this.#base=draft.base;this.#state=draft.state;this.#revision=draft.revision;
      this.conflict=!!remote&&remote.revision!==draft.revision;
    } else {
      this.#state=snapshot(remote);this.#base=this.#state;this.#revision=remote.revision;this.conflict=false;
    }
    this.loaded=true;this.#remember();this.#notify(this,this.conflict?'Layout changed on another device':'Load furniture');return this;
  }
  async refresh() {
    if (!this.loaded || this.dirty || this.#saving) return false;
    const ticket=++this.#ticket,remote=await this.#request('GET');
    if (ticket!==this.#ticket || this.dirty || this.#saving || remote.revision===this.#revision) return false;
    this.#state=snapshot(remote);this.#base=this.#state;this.#revision=remote.revision;
    this.#undo=[];this.#redo=[];this.conflict=false;this.#remember();this.#notify(this,'Refresh furniture');
    return true;
  }
  save() {
    if (this.#saving) return this.#saving;
    if (!this.loaded) return Promise.reject(new Error('Load this version before saving'));
    if (!this.dirty) return Promise.resolve(this);
    const submitted=this.#state,revision=this.#revision;
    this.#saving=(async()=>{
      try {
        const remote=await this.#request('POST',{section:'furnish',baseRevision:revision,...submitted});
        this.#base=snapshot(remote);
        if (this.#state===submitted) this.#state=this.#base;
        this.#revision=remote.revision;this.conflict=false;this.#ticket++;this.#remember();return this;
      } catch(e) {if(e.status===409) this.conflict=true;throw e;}
      finally {this.#saving=null;this.#notify(this,this.conflict?'Layout changed on another device':'Save furniture');}
    })();
    this.#notify(this,'Saving furniture');return this.#saving;
  }
}
