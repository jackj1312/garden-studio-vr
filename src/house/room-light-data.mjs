/* Three world metres. Wall sill/head are absolute Y, and normals are signed
 * toward a measured room on the air side of a glazed opening. */
import {pointInPoly} from '../planner/util.js';

const clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
export const isLampKind=kind=>['floor_lamp','table_lamp','pendant','linear_pendant','wall_light','downlight','flush_light','extractor_light'].includes(kind);
export const bulbMaterial=name=>/\b(bulb|emitter|diffuser|opal)\b/i.test((name||'').replace(/_/g,' '));

export function roomPoint(rooms,p) {
  let found=null;
  for(const r of rooms)if(p[1]>=r.floor-.035&&p[1]<=r.ceiling+.04&&pointInPoly([p[0],p[2]],r.polygon)&&(!found||r.floor>found.floor))found=r;
  return found;
}
export function openingPlane(w,op) {
  const a=w?.params?.start,b=w?.params?.end,p=op?.params;
  if(!a||!b||![p?.offset,p?.width,p?.sill,p?.head].every(Number.isFinite)||p.width<=0||p.head<=p.sill)return null;
  const dx=b[0]-a[0],dz=b[1]-a[1],length=Math.hypot(dx,dz);if(length<.01)return null;
  const t=[dx/length,dz/length],mid=p.offset+p.width/2;
  return {centre:[a[0]+t[0]*mid,(p.sill+p.head)/2,a[1]+t[1]*mid],normal:[-t[1],0,t[0]],area:p.width*(p.head-p.sill)};
}
const offset=(p,n,d)=>p.map((v,i)=>v+n[i]*d);
export function incidentRooms(rooms,plane) {
  return [-1,1].map(sign=>{
    for(const d of [.08,.15,.25,.35]) {
      const r=roomPoint(rooms,offset(plane.centre,plane.normal,sign*d));
      if(r)return r;
    }
    return null;
  });
}
export function exteriorAperture(rooms,plane,id,fixture) {
  if(!plane)return null;
  const sides=incidentRooms(rooms,plane);
  if(Boolean(sides[0])===Boolean(sides[1]))return null;
  const r=sides[0]||sides[1],inward=plane.normal.map(v=>v*(sides[0]?-1:1));
  for(let cm=20;cm<=35;cm++) {
    const position=offset(plane.centre,inward,cm/100);
    if(!pointInPoly([position[0]-.025*inward[0],position[2]-.025*inward[2]],r.polygon))continue;
    return {id,fixture,room:r.id,centre:plane.centre,inward,position,area:plane.area};
  }
  return null;
}
export function openRoomGroups(rooms,links) {
  const parent=new Map(rooms.map(r=>[r.id,r.id]));
  function root(id){while(parent.get(id)!==id)id=parent.get(id);return id;}
  for(const [a,b] of links)if(parent.has(a)&&parent.has(b))parent.set(root(b),root(a));
  const groups=new Map();
  for(const r of rooms){
    const key=root(r.id);if(!groups.has(key))groups.set(key,{rooms:[],min:[Infinity,Infinity,Infinity],max:[-Infinity,-Infinity,-Infinity]});
    const g=groups.get(key);g.rooms.push(r.id);
    for(const [x,z] of r.polygon)for(const [i,lo,hi] of [[0,x,x],[1,r.floor,r.ceiling],[2,z,z]]) {
      g.min[i]=Math.min(g.min[i],lo);g.max[i]=Math.max(g.max[i],hi);
    }
  }
  const result=new Map();
  for(const g of groups.values()) {
    g.distance=clamp(Math.hypot(...g.max.map((v,i)=>v-g.min[i]))+1,3,12);
    for(const id of g.rooms)result.set(id,g);
  }
  return result;
}
export const squared=(a,b)=>a.reduce((d,n,i)=>d+(n-b[i])**2,0);
export function rankApertures(apertures,group,eye,previous,max=3) {
  if(!group||!max)return [];
  const used=new Set();
  return apertures.filter(a=>group.rooms.includes(a.room)).map(a=>({a,score:a.area/(1+squared(a.position,eye))*(previous.includes(a.id)?1.1:1)}))
    .sort((x,y)=>y.score-x.score||x.a.id.localeCompare(y.a.id)).filter(({a})=>{
      // The emitted owner and as-built replacement can share the same aperture.
      const key=[a.room,...a.centre.map(n=>Math.round(n*100)),Math.round(a.area*100)].join('/');
      if(used.has(key))return false;used.add(key);return true;
    }).slice(0,max).map(({a})=>({...a,intensity:Math.min(80,a.area*2),distance:group.distance}));
}
export function lampPower(kind,asset={}) {
  const text=asset.lamp||'',lm=Number(/([\d.]+)\s*lm/i.exec(text)?.[1])||
    ({table_lamp:470,floor_lamp:806,downlight:550,linear_pendant:1600,extractor_light:300}[kind]||806);
  const kelvin=Number(/([\d.]+)\s*K\b/i.exec(text)?.[1])||2700;
  const spot=['downlight','linear_pendant','flush_light','pendant','extractor_light'].includes(kind);
  // Lamp flux comes from the signed schedule; the interactive intensity is
  // bounded for this scene. Spot intensity accounts for its solid angle.
  const angle=50*Math.PI/180;
  const candela=lm/(spot?2*Math.PI*(1-Math.cos(angle)):4*Math.PI);
  return {spot,kelvin,lumens:lm,intensity:clamp(candela*.12,1,45),angle,range:clamp(2.4+Math.sqrt(lm)/24,3,6)};
}
