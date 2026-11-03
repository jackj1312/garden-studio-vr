/* Proposal cuts affect only outdoor ground materials. The surveyed mesh and all indoor finishes remain reusable. */
export function createGardenTerrain(T,normalPass) {
  let entry=null,mask=null,extent=null,texture=null,signature='',adopted=[],groundBatches=[];
  const canvas=document.createElement('canvas');canvas.width=canvas.height=1024;
  const ray=new T.Ray();
  const outdoor=p=>p.group==='ground'||(p.storey==='site'&&/paving|patio|grass|turf|ground|gravel|lawn/i.test(p.name+' '+p.materialName));
  function restore(){
    for(const [m,hook,key] of adopted){m.onBeforeCompile=hook;m.customProgramCacheKey=key;m.needsUpdate=true;}
    for (const [b,oldDepth,depth] of groundBatches){b.customDepthMaterial=oldDepth;b.geometry.deleteAttribute('gsTerrainW');depth.dispose();}
    groundBatches=[];adopted=[];texture?.dispose();texture=null;signature='';
  }
  function version(v){
    restore();entry=v;
    mask=Uint8Array.from(v.model.parts,p=>outdoor(p)&&!p.noRay?1:0);
    const box=new T.Box3();
    // The surveyed property excludes the far-field, street and neighbouring drives.
    for(const p of v.model.parts)if(/^(G2_(?:paving|lawn(?:_west)?$|bed_|house_bed|wing_bed)|.*rear[-_ ](?:garden|patio|lawn))/i.test(p.name))box.union(p.bbox);
    for(const e of v.model.table.values())if(e.kind==='room'||e.type==='room'){
      for(const p of e.params?.polygon||[])if(Array.isArray(p)&&p.length===2)box.expandByPoint(new T.Vector3(p[0],0,p[1]));
    }
    for(const s of v.sidecar.spawns||[])if(s.position)box.expandByPoint(new T.Vector3().fromArray(s.position));
    if(box.isEmpty())box.copy(v.model.bounds);
    extent={x0:box.min.x-1.5,x1:box.max.x+1.5,z0:box.min.z-3,z1:box.max.z+1.5};
  }
  function hit(r,far=120){
    if(!entry)return null;
    const h=entry.bvh.raycast(r,far,mask,null); if(!h||h.normal.y<.45 || entry.model.roomAt(h.point.x,h.point.y+1,h.point.z))return null;
    return {point:h.point.clone(),normal:h.normal.clone(),distance:h.distance,surface:'garden'};
  }
  function ground(x,z){ray.origin.set(x,15,z);ray.direction.set(0,-1,0);return hit(ray)?.point.y??null;}
  function cuts(list){
    const key=JSON.stringify(list);if(key===signature)return;
    if(!list.length){restore();signature=key;return;}
    const bounds={...extent};for(const c of list)for(const [x,z] of c.points){bounds.x0=Math.min(bounds.x0,x-.1);bounds.x1=Math.max(bounds.x1,x+.1);bounds.z0=Math.min(bounds.z0,z-.1);bounds.z1=Math.max(bounds.z1,z+.1);}
    const xspan=bounds.x1-bounds.x0,zspan=bounds.z1-bounds.z0,c=canvas.getContext('2d');
    c.fillStyle='#000';c.fillRect(0,0,canvas.width,canvas.height);c.fillStyle='#fff';
    for(const cut of list){c.beginPath();cut.points.forEach(([x,z],i)=>c[i?'lineTo':'moveTo']((x-bounds.x0)*canvas.width/xspan,(z-bounds.z0)*canvas.height/zspan));c.closePath();c.fill();}
    if(!texture){texture=new T.CanvasTexture(canvas);texture.flipY=false;texture.generateMipmaps=false;texture.minFilter=T.LinearFilter;texture.magFilter=T.LinearFilter;}
    texture.needsUpdate=true;
    const rect=new T.Vector4(bounds.x0,bounds.z0,xspan,zspan);
    const parts=entry.model.parts.filter(outdoor), passes=new Set(parts.flatMap(p=>[p.set?.normal,p.set?.xray]).filter(Boolean));
    if (!groundBatches.length) {
      const byBatch=new Map();
      for (const p of parts) if(p.batch){if(!byBatch.has(p.batch))byBatch.set(p.batch,[]);byBatch.get(p.batch).push(p);}
      for (const [batch,entries] of byBatch) {
        const weights=new Uint8Array(batch.geometry.attributes.position.count);
        for(const p of entries){const g=batch.getGeometryRangeAt(batch.getGeometryIdAt(p.instanceId));weights.fill(1,g.vertexStart,g.vertexStart+g.vertexCount);}
        batch.geometry.setAttribute('gsTerrainW',new T.BufferAttribute(weights,1));
        const d=new T.MeshDepthMaterial({depthPacking:T.RGBADepthPacking});groundBatches.push([batch,batch.customDepthMaterial,d]);batch.customDepthMaterial=d;
      }
    }
    for(const [, ,d] of groundBatches)passes.add(d);
    const normals=normalPass?.();if(normals)passes.add(normals);
    for(const m of passes){
      if(adopted.some(([old])=>old===m)){m.userData.gardenMaskRect.copy(rect);continue;}
      const orig=m.onBeforeCompile,keyFn=m.customProgramCacheKey,cacheKey=keyFn.call(m);
      adopted.push([m,orig,keyFn]);m.userData.gardenMaskRect=rect.clone();
      m.onBeforeCompile=function(s,r){orig.call(this,s,r);s.uniforms.gsCut={value:texture};s.uniforms.gsRect={value:m.userData.gardenMaskRect};
        s.vertexShader='attribute float gsTerrainW; varying float gsWeight; varying vec2 gsXZ;\n'+s.vertexShader.replace('#include <project_vertex>',`#include <project_vertex>
gsWeight = gsTerrainW;
vec4 gsP = vec4(transformed, 1.);
#ifdef USE_BATCHING
gsP = batchingMatrix * gsP;
#endif
#ifdef USE_INSTANCING
gsP = instanceMatrix * gsP;
#endif
gsXZ = (modelMatrix * gsP).xz;`);
        s.fragmentShader='varying float gsWeight; varying vec2 gsXZ; uniform sampler2D gsCut; uniform vec4 gsRect;\n'+s.fragmentShader.replace('#include <clipping_planes_fragment>',`#include <clipping_planes_fragment>
vec2 gsUV = (gsXZ - gsRect.xy) / gsRect.zw;
if (gsWeight > 0.5 && all(greaterThanEqual(gsUV, vec2(0.))) && all(lessThanEqual(gsUV, vec2(1.))) && texture2D(gsCut,gsUV).r > 0.5) discard;`);
      };
      m.customProgramCacheKey=()=>cacheKey+'|gardenCut1';m.needsUpdate=true;
    }
    signature=key;
  }
  function surveyOnly(render){
    const rects=adopted.map(([m])=>[m.userData.gardenMaskRect,m.userData.gardenMaskRect.clone()]);
    try{for(const [r] of rects)r.set(1e6,1e6,1,1);return render();}
    finally{for(const [r,old] of rects)r.copy(old);}
  }
  return {version,cuts,hit,ground,surveyOnly,get extent(){return extent;},dispose:restore};
}

