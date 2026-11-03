import * as THREE from 'three';
import {floorRecipe} from './floor-recipe.mjs';

const cached=new Map();
const maps=new URL('../../tools/library/kit/maps/',import.meta.url);
function floorSwatch(def){
  if(cached.has(def.id))return cached.get(def.id);
  const recipe=floorRecipe(def),c=document.createElement('canvas');c.width=c.height=recipe.n;
  const ctx=c.getContext('2d'),tile=recipe.repeat;
  const texture=new THREE.CanvasTexture(c);texture.colorSpace=THREE.SRGBColorSpace;texture.wrapS=texture.wrapT=THREE.RepeatWrapping;
  const material=new THREE.MeshStandardMaterial({map:texture,roughness:.82,metalness:0});
  material.name='Client floor · '+def.id;
  const paint=image=>{
    const n=c.width;ctx.fillStyle=recipe.base;ctx.fillRect(0,0,n,n);
    if(image){ctx.globalAlpha=.33;ctx.globalCompositeOperation='multiply';ctx.drawImage(image,0,0,n,n);ctx.globalCompositeOperation='source-over';ctx.globalAlpha=1;}
    ctx.lineWidth=1.3;ctx.strokeStyle='#4039326b';ctx.fillStyle='#86766f88';
    for(const line of recipe.lines){ctx.beginPath();line.forEach(([x,y],i)=>ctx[i?'lineTo':'moveTo'](x,y));ctx.stroke();}
    for(const p of recipe.motifs){ctx.beginPath();p.forEach(([x,y],i)=>ctx[i?'lineTo':'moveTo'](x,y));ctx.closePath();ctx.fill();}
    texture.needsUpdate=true;
  };
  paint(null);
  const file=recipe.source;
  if(file){const im=new Image();im.onload=()=>paint(im);im.src=new URL(file,maps);}
  const swatch={material,tile};cached.set(def.id,swatch);return swatch;
}
export function createFinishOverrides(model,floors){
  const active=new Map();
  const parts=model.parts.filter(p=>{
    const id=p.ud?.surface_id,role=p.ud?.surface_role;
    return id && (role==='wall'||role==='floor'||(!role&&!id.startsWith('ceiling/')&&(id.startsWith('floor/')||p.group==='wall_lining'||p.group==='finish_skin')));
  });
  const defs=new Map(floors.map(f=>[f.id,f]));
  function apply(walls={},rooms={}){
    for(const p of parts){
      const id=p.ud.surface_id,isFloor=id.startsWith('floor/'),room=p.ud.room_id||id.slice(6);
      const value=isFloor?(rooms[room]??rooms[id]):walls[id];
      if(value===active.get(p))continue;
      if(isFloor){
        const def=defs.get(typeof value==='string'?value:value?.id);
        if(def){const s=floorSwatch(def);model.coverFloor(p,s.material,s.tile);}else model.coverFloor(p,null);
      }else model.paintPart(p,value||null);
      if(value==null)active.delete(p);else active.set(p,value);
    }
  }
  return {apply,clear(){apply();}};
}

