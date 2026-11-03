/* Metre repeats and the 384-pixel tile artwork for both WebGL and baked GLB. */
export function floorRecipe(def){
  const pattern=def.pattern||'tiles',n=384,units=(def.unit_mm||[600,600]).map(x=>Math.max(.04,x/1000));
  const boards=pattern==='planks'||pattern==='herringbone',tiles=pattern==='tiles'||pattern==='pattern';
  const repeat=boards?[units[0]*(pattern==='herringbone'?10:4),units[1]*(pattern==='herringbone'?2:1)]:
    tiles?[units[0]*2,units[1]*2]:[.8,.8];
  const source=boards?'oak_wood_planks_diff_2k.jpg':pattern==='carpet'?'knitted_fleece_diff_1k.jpg':tiles?'Marble019_1K-JPG_Color.jpg':null;
  const lines=[],motifs=[];
  function rect(x,y,w,h){lines.push([[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]]);}
  if(pattern==='planks')for(let col=0;col<4;col++){
    rect(col*n/4,-1,n/4,n+2);const y=(col*137+53)%n;lines.push([[col*n/4,y],[(col+1)*n/4,y]]);
  }
  if(pattern==='herringbone'){
    const a=n/10,b=a*5;
    for(let j=-10;j<12;j++)for(let i=-4;i<5;i++){const x=i*b*2+j*a,y=j*a;rect(x,y,b,a);rect(x+b,y-b+a,a,b);}
    for(const line of lines)for(const p of line){const [x,y]=p;p[0]=n/2+(x-y)*Math.SQRT1_2;p[1]=n/2+(x+y)*Math.SQRT1_2;}
  }
  if(tiles)for(let j=0;j<2;j++)for(let i=0;i<2;i++){
    const x=i*n/2,y=j*n/2;rect(x,y,n/2,n/2);
    if(pattern==='pattern')motifs.push([[x+n/4,y+n/12],[x+n*5/12,y+n/4],[x+n/4,y+n*5/12],[x+n/12,y+n/4]]);
  }
  return {n,repeat,source,base:def.hex||'#aa9983',lines,motifs};
}
