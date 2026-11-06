// Owner wall uses the continuous hedge frontage, not historical clipped blocks.
export function boundaryEnvelope(parts){
 const owner=parts.filter(p=>p.name.startsWith('B_street_hedge')&&p.bbox.min.x>0);
 if(!owner.length)return null;
 return {left:Math.min(...owner.map(p=>p.bbox.min.x)),right:Math.max(...owner.map(p=>p.bbox.max.x)),
  ground:Math.min(...owner.map(p=>p.bbox.min.y)),top:Math.max(...owner.map(p=>p.bbox.max.y)),
  front:Math.max(...owner.map(p=>p.bbox.max.z)),back:Math.min(...owner.map(p=>p.bbox.min.z))};
}
export function createFrontBoundary(T,scene){
 const group=new T.Group();group.name='Front boundary wall proposal';scene.add(group);let current=null;let barriers=[];const raycaster=new T.Raycaster();
 const colours=[0xe4c5af,0xeacbb7,0xdfbca6,0xe7c7b0,0xdbc0ac];
 const tex=new T.TextureLoader().load('/assets/textures/red_brick/diffuse.jpg');tex.colorSpace=T.SRGBColorSpace;
 const rough=new T.TextureLoader().load('/assets/textures/red_brick/rough.jpg');
 const normal=new T.TextureLoader().load('/assets/textures/red_brick/normal.jpg');
 const mats=colours.map(color=>new T.MeshStandardMaterial({color,map:tex,roughnessMap:rough,normalMap:normal,normalScale:new T.Vector2(.35,.35),roughness:.95}));
 const mortar=new T.MeshStandardMaterial({color:0x958d7b,roughness:1});
 const cap=new T.MeshStandardMaterial({color:0xb4b0a4,roughness:.83});
 const metal=new T.MeshStandardMaterial({color:0x191c1c,roughness:.6});
 function update(entry){
  group.visible=true;if(current===entry)return;current=entry;barriers=[];
  for(const m of [...group.children]){m.geometry?.dispose();group.remove(m);}
  const source=entry.model.parts.filter(p=>p.name.startsWith('B_street_hedge'));
  const envelope=boundaryEnvelope(source);if(!envelope)return;
  for(const p of source.filter(p=>p.bbox.min.x>0)){p.hidden=true;if(p.batch)p.batch.setVisibleAt(p.instanceId,false);if(p.mesh)p.mesh.visible=false;}
  const parts=[...source.filter(p=>p.bbox.max.x<=0),{bbox:new T.Box3(new T.Vector3(envelope.left,envelope.ground,envelope.back),new T.Vector3(envelope.right,envelope.top,envelope.front))}];
  group.userData.envelope=envelope;group.userData.wallRuns=[];
  const rows=colours.map(()=>[]);let count=0;
  function brick(w,h,d,x,y,z,angle=0){rows[count++%rows.length].push({w,h,d,x,y,z,angle});}
  function box(w,h,d,x,y,z,mat){const m=new T.Mesh(new T.BoxGeometry(w,h,d),mat);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;group.add(m);return m;}
  function clip(poly,axis,limit,sign){const out=[];for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length],ia=sign*(a[axis]-limit)>=0,ib=sign*(b[axis]-limit)>=0;if(ia)out.push(a);if(ia!==ib){const t=(limit-a[axis])/(b[axis]-a[axis]);out.push([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]);}}return out;}
  const panelVertices=[],panelUV=[];
  function panel(lo,hi,bottom,top,z){
   const u=.074,rot=Math.PI/4,c=Math.cos(rot),s=Math.sin(rot),cx=(lo+hi)/2,cy=(bottom+top)/2;
   for(let a=-25;a<25;a++)for(let b=-25;b<25;b++)for(const [ox,oy,w,h] of [[0,0,3,1],[3,0,1,3]]){
    let p=[[.05,.05],[w-.05,.05],[w-.05,h-.05],[.05,h-.05]].map(([x,y])=>{x=(x+3*a+b+ox)*u;y=(y+3*a-b+oy)*u;return[cx+x*c-y*s,cy+x*s+y*c];});
    for(const [ax,n,sign] of [[0,lo,1],[0,hi,-1],[1,bottom,1],[1,top,-1]]){if(!p.length)break;p=clip(p,ax,n,sign);}
    for(let k=1;k<p.length-1;k++)for(const q of [p[0],p[k],p[k+1]]){
     panelVertices.push(q[0],q[1],z);
     const dx=q[0]-cx,dy=q[1]-cy,xx=(dx*c+dy*s)/u-(3*a+b+ox),yy=(-dx*s+dy*c)/u-(3*a-b+oy);
     panelUV.push(.055+.13*(w>h?xx/w:yy/h),.958+.025*(w>h?yy/h:xx/w));
    }
   }
  }
  for(const p of parts){
   const b=p.bbox,lo=b.min.x,hi=b.max.x,z=b.max.z-.1775,ground=b.min.y;
   if(hi<=0){
    const leafMat=new T.MeshStandardMaterial({color:0xffffff,roughness:1});
    const geo=new T.IcosahedronGeometry(1,0), clusters=[];
    let seed=17;const rand=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296;};
    for(let x=Math.min(lo,-9.37);x<hi;x+=.10)for(let y=ground+.10;y<b.max.y-.03;y+=.11)for(const zz of [b.min.z+.08,b.max.z-.08])clusters.push([x+(rand()-.5)*.09,y+(rand()-.5)*.09,zz+(rand()-.5)*.10]);
    for(let x=-9.37;x<hi;x+=.10)for(let zz=b.min.z+.08;zz<b.max.z;zz+=.12)clusters.push([x,b.max.y-.07+(rand()-.5)*.08,zz]);
    const leaves=new T.InstancedMesh(geo,leafMat,clusters.length),m=new T.Matrix4(),q=new T.Quaternion();
    clusters.forEach((v,i)=>{m.compose(new T.Vector3(...v),q,new T.Vector3(.095,.09,.10));leaves.setMatrixAt(i,m);leaves.setColorAt(i,new T.Color().setHSL(.22+rand()*.04,.35+rand()*.15,.14+rand()*.10));});
    leaves.castShadow=true;leaves.receiveShadow=true;leaves.name='Neighbour hedge irregular closed foliage';group.add(leaves);continue;
   }
   const height=b.max.y-ground,pier=.34,capWidth=.42,span=hi-lo,sections=Math.max(1,Math.ceil(span/3.0));
   const wallHeight=height-.14,bodyTop=wallHeight-.215;
   const core=box(span,wallHeight,.215,(lo+hi)/2,ground+wallHeight/2,z,mortar);core.name='Continuous owner wall core';barriers.push(core);
   for(let row=0;row*.075<wallHeight;row++){
    const h=Math.min(.065,wallHeight-row*.075-.005);if(h<=0)continue;
    for(const x of [lo+.02,hi-.02])brick(.04,h,.235,x,ground+row*.075+.005+h/2,z);
   }
   const pierXs=Array.from({length:sections+1},(_,i)=>lo+capWidth/2+(span-capWidth)*i/sections);
   for(const x of pierXs){
    const shaft=height-.07;
    barriers.push(box(pier,shaft,.34,x,ground+shaft/2,z,mortar));
    for(let row=0;row*.075<shaft;row++)for(let j=0;j<2;j++){
     const h=Math.min(.065,shaft-row*.075-.005);if(h>0)brick(.158,h,.355,x+(j-.5)*.17,ground+row*.075+h/2+.005,z);
    }
    box(capWidth,.07,.355,x,b.max.y-.035,z,cap);
    box(.075,.17,.055,x,ground+wallHeight-.15,z+.205,metal);
   }
   for(let sec=0;sec<sections;sec++){
    const left=pierXs[sec]+pier/2,right=pierXs[sec+1]-pier/2;
    group.userData.wallRuns.push([left,right]);
    const bottom=.375,top=bodyTop-.15;
    for(let row=0;row*.075<bodyTop;row++)for(let x=left-.225;x<right;x+=.225){
     const a=Math.max(left,x+(row%2)*.1125),bb=Math.min(right,x+(row%2)*.1125+.215);if(bb<=a)continue;
     const h=Math.min(.065,bodyTop-row*.075-.005);if(h<=0)continue;const y=ground+row*.075+.005+h/2;
     // Back is fully faced. Front has an exactly bounded inset, with no projecting teeth.
     brick(bb-a,h,.015,(a+bb)/2,y,z-.11);
     if(row*.075<bottom||row*.075>=top)brick(bb-a,h,.015,(a+bb)/2,y,z+.11);
     else for(const [l,r] of [[a,Math.min(bb,left+.17)],[Math.max(a,right-.17),bb]])if(r>l)brick(r-l,h,.015,(l+r)/2,y,z+.11);
    }
    panel(left+.17,right-.17,ground+bottom,ground+top,z+.109);
    for(let x=left;x<right;x+=.075){const w=Math.min(.065,right-x);if(w>0)brick(w,.205,.235,x+w/2,ground+wallHeight-.1075,z);}
   }
   group.userData.wallDimensions={length:span,height,thickness:.215,wallHeight,pierXs,source:'Continuous original hedge extent; Jack correction 6 November'};
  }
  const geom=new T.BoxGeometry(1,1,1);const uv=geom.attributes.uv;for(let i=0;i<uv.count;i++)uv.setXY(i,.055+uv.getX(i)*.13,.958+uv.getY(i)*.025);const matrix=new T.Matrix4(),pos=new T.Vector3(),scale=new T.Vector3(),q=new T.Quaternion();
  rows.forEach((list,i)=>{const mesh=new T.InstancedMesh(geom.clone(),mats[i],list.length);list.forEach((r,k)=>{pos.set(r.x,r.y,r.z);scale.set(r.w,r.h,r.d);matrix.compose(pos,q,scale);mesh.setMatrixAt(k,matrix);});mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);});geom.dispose();
  if(panelVertices.length){const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(panelVertices,3));g.setAttribute('uv',new T.Float32BufferAttribute(panelUV,2));g.computeVertexNormals();const mat=mats[1].clone();mat.side=T.DoubleSide;group.add(new T.Mesh(g,mat));}
  group.userData.source='20813.jpg';
 }
 function blockRay(ray,far=Infinity){
  if(!group.visible)return null;group.updateMatrixWorld(true);raycaster.ray.copy(ray);raycaster.near=.0001;raycaster.far=far;
  const h=raycaster.intersectObjects(barriers,false)[0];if(!h)return null;
  return {distance:h.distance,point:h.point,normal:h.face.normal.clone().transformDirection(h.object.matrixWorld)};
 }
 return {update,group,blockRay};
}
