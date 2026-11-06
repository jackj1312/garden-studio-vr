// Reversible street reconstruction, registered to the retained hedge/frontage.
// Widths outside the surveyed garden remain photo estimates, not survey dimensions.
export function createStreetFrontage(T,scene){
 const group=new T.Group();group.name='Reference street frontage';scene.add(group);let current;let regions=[];
 function update(entry){
  group.visible=true;if(current===entry)return;current=entry;regions=[];
  for(const m of [...group.children]){m.geometry?.dispose();group.remove(m);}
  const parts=entry.model.parts;
  function material(pattern,fallback){const p=parts.find(p=>pattern.test(p.materialName));const source=p?.batch?.material||p?.mesh?.material;const m=source?.clone()||new T.MeshStandardMaterial({color:fallback,roughness:1});m.onBeforeCompile=()=>{};m.side=T.DoubleSide;return m;}
  const grass=material(/turf_neighbour/,0x667447),asphalt=material(/road/,0x575653),concrete=material(/kerb/,0xaaa795);
  function surface(name,x0,x1,z0,z1,y,mat){if(x1<=x0||z1<=z0)return;const g=new T.PlaneGeometry(x1-x0,z1-z0);g.rotateX(-Math.PI/2);const uv=g.attributes.uv;for(let i=0;i<uv.count;i++)uv.setXY(i,uv.getX(i)*(x1-x0)/2,uv.getY(i)*(z1-z0)/2);const m=new T.Mesh(g,mat);m.position.set((x0+x1)/2,y,(z0+z1)/2);m.name=name;m.receiveShadow=true;group.add(m);regions.push({x0,x1,z0,z1,y});}
  const hedges=parts.filter(p=>p.name.startsWith('B_street_hedge')),owner=hedges.filter(p=>p.bbox.min.x>0).sort((a,b)=>a.bbox.min.x-b.bbox.min.x);
  if(owner.length<2)return;
  const front=Math.max(...hedges.map(p=>p.bbox.max.z)),start=Math.min(...hedges.map(p=>p.bbox.min.z))-.25;
  const pathEnd=front+.85,kerb=pathEnd+1.8,road=kerb+.15;
  const x0=-9.37,x1=20.63,drive0=Math.max(...owner.map(p=>p.bbox.max.x)),drive1=parts.find(p=>p.name==='G2_gravel')?.bbox.max.x??11.82;
  for(const p of parts.filter(p=>/^G2_(pavement|road|kerb)(_|$)/.test(p.name))){p.hidden=true;if(p.batch)p.batch.setVisibleAt(p.instanceId,false);if(p.mesh)p.mesh.visible=false;}
  // Narrow public footpath at the hedge, then broad grass verge to the carriageway.
  for(const [a,b] of [[x0,drive0],[drive1,x1]])surface('Public footpath',a,b,front,pathEnd,-.211,asphalt);
  for(const [a,b] of [[x0,drive0],[drive1,x1]])surface('Street grass verge',a,b,pathEnd,kerb,-.210,grass);
  surface('Drive crossing',drive0,drive1,start,road,-.211,asphalt);
  surface('Pedestrian asphalt threshold',-.35,.75,start,front,-.211,asphalt);
  surface('Retained pale path threshold',-.207,.657,start-.12,start,-.225,concrete);
  surface('Carriageway',x0,x1,road,road+7.55,-.311,asphalt);
  for(let x=x0;x<x1;x+=.91){const end=Math.min(x+.90,x1),dropped=x<drive1&&end>drive0;const h=dropped?.035:.12;const m=new T.Mesh(new T.BoxGeometry(end-x,h,.15),concrete);m.position.set((x+end)/2,-.311+h/2,kerb+.075);m.name=dropped?'Dropped kerb':'Kerb stone';m.receiveShadow=true;group.add(m);}
  group.userData.dimensions={source:'20817 + walk_0001/0133/0153',footpath:.85,verge:1.8,status:'photo-estimated outside surveyed garden',front,kerb,drive:[drive0,drive1]};
 }
 function heightAt(x,z){if(!group.visible)return null;const r=regions.find(r=>x>=r.x0&&x<=r.x1&&z>=r.z0&&z<=r.z1);return r?.y??null;}
 return {group,update,heightAt};
}
