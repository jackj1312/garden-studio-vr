import {frontageSurvey as S,grassEdge,kerbEdge,frontageLevel} from './frontage-survey.js';
// Reversible, shared visual/walking reconstruction. No saved garden is modified.
export function createStreetFrontage(T,scene){
 const group=new T.Group();group.name='Reference street frontage';scene.add(group);
 let current,regions=[],materials=[],patched=[];const mask={value:1};
 const extent={x0:-25.37,x1:34.63,z0:S.start,z1:kerbEdge(-25.37)+S.kerbWidth+S.roadWidth+1.5};
 function setVisible(on){group.visible=on;mask.value=on?1:0;}
 function hide(p){p.hidden=true;if(p.batch)p.batch.setVisibleAt(p.instanceId,false);if(p.mesh)p.mesh.visible=false;}
 function inside(x,z,poly){let hit=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){
  const a=poly[i],b=poly[j];if((a[1]>z)!==(b[1]>z)&&x<(b[0]-a[0])*(z-a[1])/(b[1]-a[1])+a[0])hit=!hit;
 }return hit;}
 function patchGround(parts){
  // Cut the old, too-short far-field mask at fragment level. Applies only within
  // the replacement street rectangle, so the house and retained garden are intact.
  const groundParts=parts.filter(p=>/^G-(site|dug|reinstated|final)$/.test(p.element||p.ud?.element||p.name)||/^G-(site|dug|reinstated|final)(?:_\d+)?$/.test(p.name)||p.name==='G2_soil');
  function applyMask(m){
   if(!m||m.userData.frontageMask)return;
   const before=m.onBeforeCompile,key=m.customProgramCacheKey;
   m.onBeforeCompile=function(shader,...args){before?.call(this,shader,...args);
    shader.uniforms.frontageActive=mask;
    shader.vertexShader='varying vec3 frontageWorld;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <project_vertex>',`#include <project_vertex>
     vec4 frontageP=vec4(transformed,1.0);
     #ifdef USE_BATCHING
      frontageP=batchingMatrix*frontageP;
     #endif
     #ifdef USE_INSTANCING
      frontageP=instanceMatrix*frontageP;
     #endif
     frontageWorld=(modelMatrix*frontageP).xyz;`);
    shader.fragmentShader='uniform float frontageActive; varying vec3 frontageWorld;\n'+shader.fragmentShader;
    shader.fragmentShader=shader.fragmentShader.replace('#include <clipping_planes_fragment>',`#include <clipping_planes_fragment>
     if(frontageActive>.5 && frontageWorld.x>=${extent.x0} && frontageWorld.x<=${extent.x1} && frontageWorld.z>=${extent.z0} && frontageWorld.z<=${extent.z1}) discard;`);
   };
   m.customProgramCacheKey=()=>key.call(m)+'|frontage-terrain-v1';m.userData.frontageMask=true;m.needsUpdate=true;patched.push(m.name);
  }
  const batches=new Set();for(const p of groundParts){for(const m of [p.set?.normal,p.set?.xray,p.batch?.material,p.mesh?.material])applyMask(m);if(p.batch||p.mesh)batches.add(p.batch||p.mesh);}
  for(const mesh of batches){
   // The discarded old terrain must disappear from shadow maps as well.
   if(!mesh.customDepthMaterial)mesh.customDepthMaterial=new T.MeshDepthMaterial({depthPacking:T.RGBADepthPacking});
   if(!mesh.customDistanceMaterial)mesh.customDistanceMaterial=new T.MeshDistanceMaterial();
   applyMask(mesh.customDepthMaterial);applyMask(mesh.customDistanceMaterial);
  }
 }
 function update(entry){
  setVisible(true);if(current===entry)return;current=entry;regions=[];
  for(const m of [...group.children]){if(!m.userData.borrowedGeometry)m.geometry?.dispose();group.remove(m);}
  materials.forEach(m=>m.dispose());materials=[];
  const parts=entry.model.parts;
  function material(pattern,fallback){const p=parts.find(p=>pattern.test(p.materialName));const source=p?.batch?.material||p?.mesh?.material;const m=source?.clone()||new T.MeshStandardMaterial({color:fallback,roughness:1});m.onBeforeCompile=()=>{};m.side=T.DoubleSide;materials.push(m);return m;}
  const grass=material(/turf_neighbour/,0x667447),asphalt=material(/FG_road/,0x575653),concrete=material(/FG_kerb/,0xaaa795);
  const path=asphalt.clone();materials.push(path);path.color.multiplyScalar(1.14);
  const owner=parts.filter(p=>p.name.startsWith('B_street_hedge')&&p.bbox.min.x>0);
  if(!owner.length)return;
  const drive0=Math.max(...owner.map(p=>p.bbox.max.x)),drive1=parts.find(p=>p.name==='G2_gravel')?.bbox.max.x??11.82;
  for(const p of parts.filter(p=>/^G2_(pavement|road|kerb)(_|$)/.test(p.name)||p.name==='Opp_wall'))hide(p);
  patchGround(parts);
  // The old generic opposite houses stood in the recovered carriageway. Retain
  // those context models beyond it; their architecture/placement is provisional.
  for(const p of parts.filter(p=>/^Opp_/.test(p.name)&&p.name!=='Opp_wall')){
   if(p.geometry){const m=new T.Mesh(p.geometry,p.batch?.material||p.mesh?.material);m.matrixAutoUpdate=false;m.matrix.copy(p.matrix0);m.matrix.premultiply(new T.Matrix4().makeTranslation(0,0,16));m.name='Retained context '+p.name;m.userData.borrowedGeometry=true;group.add(m);}
   hide(p);
  }
  function surface(name,poly,kind,mat,level=(x,z)=>frontageLevel(x,z,kind)){
   const vertices=[],uv=[];const faces=T.ShapeUtils.triangulateShape(poly.map(p=>new T.Vector2(...p)),[]);
   function tri(a,b,c,depth=0){
    const ab=(a[0]-b[0])**2+(a[1]-b[1])**2,bc=(b[0]-c[0])**2+(b[1]-c[1])**2,ca=(c[0]-a[0])**2+(c[1]-a[1])**2;
    if(Math.max(ab,bc,ca)>.16&&depth<18){
     if(bc>=ab&&bc>=ca){const t=a;a=b;b=c;c=t;}else if(ca>=ab&&ca>=bc){const t=a;a=c;c=b;b=t;}
     const mid=[(a[0]+b[0])/2,(a[1]+b[1])/2];tri(a,mid,c,depth+1);tri(mid,b,c,depth+1);return;
    }
    for(const [x,z] of [a,b,c]){vertices.push(x,level(x,z),z);uv.push(x/1.8,z/1.8);}
   }
   for(const f of faces)tri(...f.map(i=>poly[i]));
   const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute(vertices,3));geometry.setAttribute('uv',new T.Float32BufferAttribute(uv,2));geometry.computeVertexNormals();
   const m=new T.Mesh(geometry,mat);m.name=name;m.receiveShadow=true;group.add(m);regions.push({name,kind,poly,level});return m;
  }
  const a=extent.x0,b=extent.x1,start=S.start;
  // Diagonal private approach from the retained 900 mm path to the public path.
  // Its uncaptured outer alignment comes from Street View, not survey control.
  const accessBack=[-.21,.66],accessFront=[-5.04,-3.66];
  const turnLeft=-.465,turnRight=.915;
  const driveFlare=drive0-.45;
  surface('West grass verge',[[a,start],[accessBack[0],start],[accessBack[0],start+.16],[turnLeft,S.wall],[accessFront[0],grassEdge(accessFront[0])],[-9.37,grassEdge(-9.37)],[a,grassEdge(a)]],'verge',grass);
  surface('Retained pale threshold',[[accessBack[0],start],[accessBack[1],start],[accessBack[1],start+.16],[accessBack[0],start+.16]],'threshold',concrete,(x,z)=>S.paving+(S.ground-S.paving)*(z-start)/.16);
  surface('Angled pedestrian approach',[[accessBack[0],start+.16],[accessBack[1],start+.16],[turnRight,S.wall],[accessFront[1],grassEdge(accessFront[1])],[accessFront[0],grassEdge(accessFront[0])],[turnLeft,S.wall]],'access',path);
  surface('Owner grass verge',[[accessBack[1],start],[drive0,start],[drive0,S.wall],[driveFlare,grassEdge(driveFlare)],[accessFront[1],grassEdge(accessFront[1])],[turnRight,S.wall],[accessBack[1],start+.16]],'verge',grass);
  surface('East grass verge',[[drive1,start],[b,start],[b,grassEdge(b)],[drive1,grassEdge(drive1)]],'verge',grass);
  surface('Drive crossing',[[drive0,start],[drive1,start],[drive1,kerbEdge(drive1)],[driveFlare,kerbEdge(driveFlare)],[driveFlare,grassEdge(driveFlare)],[drive0,S.wall]],'drive',asphalt);
  surface('Public footpath west',[[a,grassEdge(a)],[-9.37,grassEdge(-9.37)],[driveFlare,grassEdge(driveFlare)],[driveFlare,kerbEdge(driveFlare)],[a,kerbEdge(a)]],'path',path);
  surface('Public footpath east',[[drive1,grassEdge(drive1)],[b,grassEdge(b)],[b,kerbEdge(b)],[drive1,kerbEdge(drive1)]],'path',path);
  const near=x=>kerbEdge(x)+S.kerbWidth,far=x=>near(x)+S.roadWidth;
  surface('Carriageway',[[a,near(a)],[b,near(b)],[b,far(b)],[a,far(a)]],'road',asphalt);
  surface('Opposite footpath context',[[a,far(a)],[b,far(b)],[b,far(b)+1.5],[a,far(a)+1.5]],'road',path);
  // Each kerb shares exact road and path edge positions, with a dropped crossing.
  for(let x=a;x<b;x+=.9){const end=Math.min(x+.9,b),dropped=x<drive1&&end>driveFlare;
   const level=(xx,z)=>{const top=frontageLevel(xx,kerbEdge(xx),'kerb'),low=frontageLevel(xx,near(xx),'road');return dropped?top+(low-top)*(z-kerbEdge(xx))/S.kerbWidth:top;};
   surface(dropped?'Dropped kerb':'Kerb stone',[[x,kerbEdge(x)],[end,kerbEdge(end)],[end,near(end)],[x,near(x)]],'kerb',concrete,level);
   if(!dropped){const geo=new T.BufferGeometry();const l=frontageLevel(x,near(x),'road'),r=frontageLevel(end,near(end),'road'),lt=level(x,near(x)),rt=level(end,near(end));geo.setAttribute('position',new T.Float32BufferAttribute([x,l,near(x),end,r,near(end),end,rt,near(end),x,l,near(x),end,rt,near(end),x,lt,near(x)],3));geo.computeVertexNormals();const mesh=new T.Mesh(geo,concrete);mesh.name='Kerb face';group.add(mesh);}
  }
  // Share four material draws for the street; retain region polygons for the
  // walking API. Context meshes share material batches as well.
  const batches=new Map();
  for(const m of [...group.children]){
   const key=m.material;let row=batches.get(key);if(!row){row={position:[],normal:[],uv:[],color:[],context:!!m.userData.borrowedGeometry};batches.set(key,row);}
   if(m.matrixAutoUpdate)m.updateMatrix();const g=m.geometry,ps=g.attributes.position,ns=g.attributes.normal,uv=g.attributes.uv,cs=g.attributes.color,normalMatrix=new T.Matrix3().getNormalMatrix(m.matrix);
   const v=new T.Vector3(),n=new T.Vector3();
   for(let i=0;i<(g.index?.count??ps.count);i++){
    const j=g.index?g.index.getX(i):i;v.fromBufferAttribute(ps,j).applyMatrix4(m.matrix);row.position.push(v.x,v.y,v.z);
    if(ns)n.fromBufferAttribute(ns,j).applyMatrix3(normalMatrix).normalize();else n.set(0,1,0);row.normal.push(n.x,n.y,n.z);
    row.uv.push(uv?uv.getX(j):v.x/1.8,uv?uv.getY(j):v.y/1.8);
    row.color.push(cs?cs.getX(j):1,cs?cs.getY(j):1,cs?cs.getZ(j):1);
   }
   if(!m.userData.borrowedGeometry)g.dispose();group.remove(m);
  }
  for(const [mat,row] of batches){
   const g=new T.BufferGeometry();for(const [key,size] of [['position',3],['normal',3],['uv',2],['color',3]])g.setAttribute(key,new T.Float32BufferAttribute(row[key],size));
   const m=new T.Mesh(g,mat);m.name=row.context?'Retained opposite context':'Street '+(mat===grass?'grass':mat===path?'footpaths':mat===asphalt?'asphalt':'kerbs');m.userData.contextOnly=row.context;m.receiveShadow=true;group.add(m);
  }
  group.userData.dimensions={source:S.revision,status:'video/LiDAR reconstruction; uncertainty in frontage_v1.json',front:S.wall,grassEdge:[grassEdge(.75),grassEdge(drive0)],kerb:[kerbEdge(.75),kerbEdge(drive0)],drive:[drive0,drive1],crossfall:[S.crossfallX,S.crossfallZ],retainedThreshold:S.ground,roadWidth:S.roadWidth,groundMask:extent,patchedGroundMaterials:patched};
 }
 function surfaceAt(x,z){if(!group.visible)return null;return regions.find(r=>inside(x,z,r.poly))||null;}
 function heightAt(x,z){const r=surfaceAt(x,z);return r?r.level(x,z):null;}
 return {group,update,heightAt,surfaceAt,setVisible};
}
