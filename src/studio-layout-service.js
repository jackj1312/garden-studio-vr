/* The pre-existing walkthrough daemon keeps its review/voice APIs. Its static
   site files can show the same saved design while the editor writes on 8450. */
export function openLayoutEditor(mode,site,version){
 if(location.protocol!=='https:'||location.port!=='8443')return false;
 const url=new URL('house.html',location.href);url.port='8450';
 url.search=new URLSearchParams({site,version,mode:'review',[mode]:'1'});location.assign(url);return true;
}
export function layoutFetcher(site,version){
 return async (url,opts={})=>{
   if(location.port!=='8443'||location.protocol!=='https:'||opts.method&&opts.method!=='GET')return fetch(url,opts);
   const base='/assets/sites/'+encodeURIComponent(site)+'/',v=encodeURIComponent(version);
   async function optional(file){const r=await fetch(base+file,{cache:'no-store'});if(r.status===404)return null;if(!r.ok)throw Error('Layout read failed ('+r.status+')');return r.json();}
   const saved=await optional('layout/'+v+'.json')||{};
   const seed=saved.furnishSeeded?null:await optional('furnish/'+v+'/seed.json');
   const result={schema:1,site,version,revision:0,items:[],garden:{schema:1,objects:[]},wallColours:{},roomFloors:{},...saved};
   if(seed&&!saved.furnishSeeded){result.items=seed.items||[];result.wallColours={...seed.wallColours,...result.wallColours};result.roomFloors={...seed.roomFloors,...result.roomFloors};}
   return new Response(JSON.stringify(result),{status:200,headers:{'Content-Type':'application/json'}});
 };
}

