// First-iteration boundary proposal. House masonry and neighbour hedge are untouched.
export function createFrontBoundary(T,scene){
 const group=new T.Group();group.name='Front boundary wall proposal';scene.add(group);let current=null;
 const colours=[0x8e5741,0xa46b50,0x865747,0xad7359,0x765345];
 const mats=colours.map(color=>new T.MeshStandardMaterial({color,roughness:.94}));
 const mortar=new T.MeshStandardMaterial({color:0x958d7b,roughness:1});
 const cap=new T.MeshStandardMaterial({color:0xb4b0a4,roughness:.83});
 const metal=new T.MeshStandardMaterial({color:0x191c1c,roughness:.6});
 function update(entry){
  group.visible=true;if(current===entry)return;current=entry;
  for(const m of [...group.children]){m.geometry?.dispose();group.remove(m);}
  const parts=entry.model.parts.filter(p=>p.name.startsWith('B_street_hedge'));
  const rows=colours.map(()=>[]);let count=0;
  function brick(w,h,d,x,y,z,angle=0){rows[count++%rows.length].push({w,h,d,x,y,z,angle});}
  function box(w,h,d,x,y,z,mat){const m=new T.Mesh(new T.BoxGeometry(w,h,d),mat);m.position.set(x,y,z);m.castShadow=true;m.receiveShadow=true;group.add(m);return m;}
  function clip(poly,axis,limit,sign){const out=[];for(let i=0;i<poly.length;i++){const a=poly[i],b=poly[(i+1)%poly.length],ia=sign*(a[axis]-limit)>=0,ib=sign*(b[axis]-limit)>=0;if(ia)out.push(a);if(ia!==ib){const t=(limit-a[axis])/(b[axis]-a[axis]);out.push([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])]);}}return out;}
  const panelVertices=[];
  function panel(lo,hi,bottom,top,z){
   const u=.074,rot=Math.PI/4,c=Math.cos(rot),s=Math.sin(rot),cx=(lo+hi)/2,cy=(bottom+top)/2;
   for(let a=-25;a<25;a++)for(let b=-25;b<25;b++)for(const [ox,oy,w,h] of [[0,0,2,1],[2,0,1,2]]){
    let p=[[.05,.05],[w-.05,.05],[w-.05,h-.05],[.05,h-.05]].map(([x,y])=>{x=(x+2*a+b+ox)*u;y=(y+2*a-b+oy)*u;return[cx+x*c-y*s,cy+x*s+y*c];});
    for(const [ax,n,sign] of [[0,lo,1],[0,hi,-1],[1,bottom,1],[1,top,-1]]){if(!p.length)break;p=clip(p,ax,n,sign);}
    for(let k=1;k<p.length-1;k++)for(const q of [p[0],p[k],p[k+1]])panelVertices.push(q[0],q[1],z);
   }
  }
  for(const p of parts){
   const b=p.bbox,lo=b.min.x,hi=b.max.x,z=b.max.z-.20,ground=b.min.y;
   if(hi<=0){
    // Keep the photographed outer hedge; add a closed leaf-textured core only inside its measured bounds.
    const mat=new T.MeshStandardMaterial({color:0x35512a,roughness:1});
    mat.onBeforeCompile=()=>{};mat.side=T.DoubleSide;mat.transparent=false;mat.alphaTest=0;
    const m=box(hi-lo-.04,b.max.y-ground-.08,b.max.z-b.min.z-.04,(lo+hi)/2,(ground+b.max.y)/2,(b.min.z+b.max.z)/2,mat);m.name='Neighbour hedge repaired core';continue;
   }
   p.hidden=true;p.collide=false;if(p.batch)p.batch.setVisibleAt(p.instanceId,false);if(p.mesh)p.mesh.visible=false;
   const height=1.2,pier=.34,span=hi-lo,sections=Math.max(1,Math.ceil(span/2.5));
   box(span,height,.215,(lo+hi)/2,ground+height/2,z,mortar);
   for(let i=0;i<=sections;i++){
    const x=lo+pier/2+(span-pier)*i/sections;
    box(pier,1.38,.34,x,ground+.69,z,mortar);
    for(let row=0;row<18;row++)for(let j=0;j<2;j++)brick(.158,.065,.355,x+(j-.5)*.17,ground+.038+row*.075,z);
    box(.42,.07,.42,x,ground+1.415,z,cap);
    box(.075,.17,.075,x,ground+1.12,z+.21,metal);
   }
   for(let sec=0;sec<sections;sec++){
    const left=lo+pier+(span-pier)*sec/sections,right=lo+(span-pier)*(sec+1)/sections;
    if(right-left<.2)continue;
    // Surrounding running bond plus inset panel at the road-facing side.
    for(let row=0;row<13;row++)for(let x=left-.215;x<right;x+=.225){
     const a=Math.max(left,x+(row%2)*.1125),b=Math.min(right,x+(row%2)*.1125+.215);if(b<=a)continue;
     const y=ground+.0375+row*.075;
     if(row<4||row>10)brick(b-a,.065,.235,(a+b)/2,y,z);
     else{const edge=.16;if(a<left+edge||b>right-edge)brick(b-a,.065,.235,(a+b)/2,y,z);}
    }
    panel(left+.17,right-.17,ground+.32,ground+.81,z+.112);
    for(let x=left+.0325;x<right;x+=.075)brick(Math.min(.065,right-x+.0325),.205,.235,x,ground+1.09,z);
   }
  }
  const geom=new T.BoxGeometry(1,1,1),matrix=new T.Matrix4(),pos=new T.Vector3(),scale=new T.Vector3(),q=new T.Quaternion();
  rows.forEach((list,i)=>{const mesh=new T.InstancedMesh(geom.clone(),mats[i],list.length);list.forEach((r,k)=>{pos.set(r.x,r.y,r.z);scale.set(r.w,r.h,r.d);matrix.compose(pos,q,scale);mesh.setMatrixAt(k,matrix);});mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);});geom.dispose();
  if(panelVertices.length){const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(panelVertices,3));g.computeVertexNormals();const mat=mats[1].clone();mat.side=T.DoubleSide;group.add(new T.Mesh(g,mat));}
  group.userData.source='20813.jpg';group.userData.provisionalHeights={wall:1.2,piers:1.45};
 }
 return {update,group};
}
