// Reversible massing reference on Jack's saved slab; not construction drawings.
export const STUDIO_BASE_ID='outbuilding-base-9a8d5ad5-6bbf-4bad-9a46-c2d96c151976';
export function createStudioConcept(T,scene){
 const group=new T.Group();group.name='Tattoo studio geometry reference';scene.add(group);
 const wall=new T.MeshStandardMaterial({color:0xc7c5b9,roughness:.85});
 const roof=new T.MeshStandardMaterial({color:0x444b50,roughness:.88,side:T.DoubleSide});
 const glass=new T.MeshStandardMaterial({color:0x79959b,metalness:.25,roughness:.22});
 const trim=new T.MeshStandardMaterial({color:0x303638,roughness:.65});
 let signature='';
 function box(w,h,d,x,y,z,mat=wall){const m=new T.Mesh(new T.BoxGeometry(w,h,d),mat);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;group.add(m);return m;}
 function update(objects){
  const f=objects.find(f=>f.id===STUDIO_BASE_ID),key=JSON.stringify(f);
  if(key===signature)return;signature=key;
  for(const o of [...group.children]){o.geometry?.dispose();group.remove(o);}
  if(!f||f.geometry.type!=='rectangle'){group.visible=false;return;}group.visible=true;
  const {width:w,depth:d,center,yaw}=f.geometry,h=2.4,t=.12,over=.2,rise=.8;
  group.position.set(center[0],f.baseY+f.level,center[1]);group.rotation.y=-yaw;
  // Back and ends. The long east facade faces the existing drive.
  box(t,h,d,-w/2+t/2,h/2,0);box(w,h,t,0,h/2,-d/2+t/2);box(w,h,t,0,h/2,d/2-t/2);
  const x=w/2-t/2,doorZ=-d*.25,doorW=1,doorH=2.1,winZ=d*.20,winW=Math.min(2.2,d*.36),sill=.65,winH=1.45;
  const openings=[{lo:doorZ-doorW/2,hi:doorZ+doorW/2,sill:0,top:doorH},{lo:winZ-winW/2,hi:winZ+winW/2,sill,top:sill+winH}];
  let start=-d/2;
  for(const o of openings){if(o.lo>start)box(t,h,o.lo-start,x,h/2,(start+o.lo)/2);box(t,h-o.top,o.hi-o.lo,x,(h+o.top)/2,(o.lo+o.hi)/2);if(o.sill)box(t,o.sill,o.hi-o.lo,x,o.sill/2,(o.lo+o.hi)/2);box(.035,o.top-o.sill,o.hi-o.lo,x,(o.top+o.sill)/2,(o.lo+o.hi)/2,glass);for(const z of [o.lo,o.hi])box(.16,o.top-o.sill,.055,x,(o.top+o.sill)/2,z,trim);start=o.hi;}
  if(start<d/2)box(t,h,d/2-start,x,h/2,(start+d/2)/2);
  box(.16,.06,doorW,x,doorH,doorZ,trim);box(.16,.06,winW,x,sill+winH,winZ,trim);box(.16,.06,winW,x,sill,winZ,trim);
  // Simple interior equipment blocks; all dimensions are metres.
  const fit=(name,w,h,d,x,y,z,mat=wall)=>{const m=box(w,h,d,x,y,z,mat);m.name=name;return m;};
  fit('Studio floor',w-.24,.04,d-.24,0,.02,0);
  const wcWidth=1.35,wcDepth=1.65,wcx=-w/2+wcWidth/2,wcz=-d/2+wcDepth/2;
  fit('WC partition east',.10,2.35,wcDepth,-w/2+wcWidth,1.175,wcz);
  // 750 mm opening in the south partition, shown with a closed simple door.
  fit('WC partition south',wcWidth-.8,2.35,.1,-w/2+(wcWidth-.8)/2,1.175,-d/2+wcDepth);
  fit('WC door',.75,2.05,.04,-w/2+wcWidth-.4,1.025,-d/2+wcDepth,trim);
  fit('Toilet pedestal',.38,.43,.62,wcx,.215,-d/2+.52);
  fit('Toilet cistern',.40,.68,.18,wcx,.34,-d/2+.24);
  fit('WC basin',.38,.80,.32,-w/2+.34,.4,-d/2+1.25);
  for(const [index,z] of [[1,-.28],[2,1.86]]){
    fit('Tattoo bed '+index+' base',.5,.65,1.3,-.45,.365,z,trim);
    fit('Tattoo bed '+index+' cushion',.78,.15,1.9,-.45,.765,z,glass);
    fit('Tattoo bed '+index+' headrest',.60,.10,.40,-.45,.89,z-.68,glass);
    fit('Setup trolley '+index,.38,.8,.55,.30,.4,z-.2,trim);
  }
  fit('Cleaning counter',1.9,.9,.55,.75,.45,-d/2+.4);
  fit('Cleaning sink',.50,.05,.38,.25,.93,-d/2+.4,glass);
  fit('Drawing desk',.50,.76,1.1,-w/2+.37,.38,.15);
  fit('Drawing chair',.45,.48,.45,-w/2+.90,.24,.15,trim);
  fit('Welcome desk',.55,1.05,1.15,w/2-.42,.525,2.25);
  // Four planes: two trapezoids and two triangular hips; ridge follows the long axis.
  const a=w/2+over,b=d/2+over,r=Math.max(0,b-a),v=[[-a,h,-b],[a,h,-b],[a,h,b],[-a,h,b],[0,h+rise,-r],[0,h+rise,r]];
  const faces=[0,1,4,1,2,5,1,5,4,2,3,5,3,0,4,3,4,5];
  const geo=new T.BufferGeometry();geo.setAttribute('position',new T.Float32BufferAttribute(faces.flatMap(i=>v[i]),3));geo.computeVertexNormals();const m=new T.Mesh(geo,roof);m.name='Studio hipped roof';m.castShadow=true;m.receiveShadow=true;group.add(m);
  group.userData.reference={baseId:f.id,width:w,depth:d,eaves:h,roofRise:rise,front:'+X / drive',status:'provisional geometry for image generation'};
 }
 return {update,group};
}
