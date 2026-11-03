/* Metre repeats and the scanned material channels for both WebGL and baked GLB. */
export function floorRecipe(def){
  const pattern=def.pattern||'tiles',n=1024,units=(def.unit_mm||[600,600]).map(x=>Math.max(.04,x/1000));
  const boards=pattern==='planks'||pattern==='herringbone',tiles=pattern==='tiles'||pattern==='pattern';
  const repeat=boards?[units[0]*(pattern==='herringbone'?10:4),units[1]*(pattern==='herringbone'?2:1)]:
    tiles?[units[0]*2,units[1]*2]:[.8,.8];
  const slate=def.id==='FLR-SLATE';
  const source=slate?'slate_floor_diff_1k.jpg':boards?'oak_wood_planks_diff_2k.jpg':pattern==='carpet'?'knitted_fleece_diff_1k.jpg':tiles?'Marble019_1K-JPG_Color.jpg':null;
  const lines=[],motifs=[];
  function rect(x,y,w,h){lines.push([[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]]);}
  if(pattern==='planks')for(let col=0;col<4;col++){
    rect(col*n/4,-1,n/4,n+2);const y=((col*137+53)*n/384)%n;lines.push([[col*n/4,y],[(col+1)*n/4,y]]);
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
  const photo=['FLR-CARPET-OAT','FLR-CARPET-GREY','FLR-SISAL','FLR-CONCRETE'].includes(def.id);
  const concrete=pattern==='concrete',sisal=def.id==='FLR-SISAL';
  const fibre=sisal?'hessian_380':'curly_teddy_natural';
  if(photo)return {n,repeat:pattern==='concrete'?[1.6,1.6]:sisal?[.60,.60]:[.27,.27],source:def.id+'-photo.jpg',photo:true,
    normal:concrete?'Concrete030_1K-JPG_NormalGL.jpg':fibre+'_nor_gl_1k.jpg',
    rough: (concrete?'Concrete030':fibre)+'-floor-rough.jpg', relief:concrete ? .14 : sisal ? .60 : .72,roughness:1,base:def.hex,lines,motifs};
  const normal=slate?'slate_floor_nor_gl_2k.jpg':boards?'oak_wood_planks_nor_gl_2k.jpg':tiles?'Marble019_1K-JPG_NormalGL.jpg':null;
  const rough=slate?null:boards?'oak_wood_planks_rough_2k.jpg':tiles?'Marble019_1K-JPG_Roughness.jpg':null;
  return {n,repeat,source,normal,rough,relief:boards ? .32 : .45,roughness:slate ? .78 : 1,base:def.hex||'#aa9983',lines,motifs};
}
