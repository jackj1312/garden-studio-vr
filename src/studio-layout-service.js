/* The pre-existing walkthrough daemon keeps its review/voice APIs. Its static
   site files can show the same saved design while the editor writes on 8450. */
export function previewPrefix(location=globalThis.location){
 return location?.pathname?.match(/^\/preview\/[0-9a-f]{20}\//)?.[0]||'';
}
export function studioAsset(path,location=globalThis.location){
 const prefix=previewPrefix(location);
 return prefix&&/^\/(assets|tools)\//.test(path)?prefix+path.slice(1):path;
}
export function openLayoutEditor(mode,site,version){
 if(previewPrefix())return true;
 if(location.protocol!=='https:'||location.port!=='8443')return false;
 const url=new URL('house.html',location.href);url.port='8450';
 url.search=new URLSearchParams({site,version,mode:'review',[mode]:'1'});location.assign(url);return true;
}
export function layoutFetcher(site,version){
 return async (url,opts={})=>{
   const preview=previewPrefix(),method=(opts.method||'GET').toUpperCase();
   if(preview&&method!=='GET')return new Response('Latest house preview is read-only',{status:405,headers:{Allow:'GET'}});
   if(!preview&&(location.port!=='8443'||location.protocol!=='https:'||method!=='GET'))return fetch(url,opts);
   const base=studioAsset('/assets/sites/'+encodeURIComponent(preview?'house-preview':site)+'/'),v=encodeURIComponent(version);
   async function optional(file){const r=await fetch(base+file,{cache:'no-store'});if(r.status===404)return null;if(!r.ok)throw Error('Layout read failed ('+r.status+')');return r.json();}
   const saved=await optional('layout/'+v+'.json')||{};
   const needsSeed=!saved.furnishSeeded&&!(preview&&saved.items?.length);
   const seed=needsSeed?await optional('furnish/'+v+'/seed.json'):null;
   const result={schema:1,site,version,revision:0,items:[],garden:{schema:1,objects:[]},wallColours:{},roomFloors:{},...saved};
   if(preview){result.site='house-preview';result.version=version;}
   if(seed){result.items=seed.items||[];result.wallColours={...seed.wallColours,...result.wallColours};result.roomFloors={...seed.roomFloors,...result.roomFloors};}
   return new Response(JSON.stringify(result),{status:200,headers:{'Content-Type':'application/json'}});
 };
}

