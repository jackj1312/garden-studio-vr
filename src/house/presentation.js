// The room title is passive. Existing welcome controls, walk input, right-ray
// picking and the headset's own panels keep their original event owners.
const duration=2600;
const capital=s=>s ? s.charAt(0).toUpperCase()+s.slice(1) : '';
function versionLabel(id,name) {
  if(id==='as_built_now')return 'Before';
  if(id==='approved_2b')return 'After';
  return name || '';
}
function detailsOf(room,version) {
  const storey=room.params?.storey || room.meta?.storey || room.storey;
  const floor={ground:'Ground floor',first:'First floor',second:'Second floor'}[storey];
  return [version,floor].filter(Boolean).join(' · ');
}

export function createHousePresentation({onLamp=()=>{},onXRRoom=()=>{}}={}) {
  const id=key=>document.getElementById(key);
  const card=id('studioRoomTitle'),name=card.querySelector('.room-title-name'),detail=card.querySelector('.room-title-detail');
  const start=id('start'),progressTrack=id('loadTrack'),switchCard=id('studioSwitchProgress');
  const toggle=id('baToolsToggle'),tools=id('baTools'),bar=id('baBar');
  const compact=matchMedia('(max-width:1090px), (pointer:coarse)');
  const aborter=new AbortController(), opts={signal:aborter.signal};
  let version='',versionId='',seen='',candidate='',timer=0,hideTimer=0,lastImmersive=false;
  const placeStatus=()=>{
    const b=bar.getBoundingClientRect();
    if(!b.height)return;
    const css=document.documentElement.style;
    css.setProperty('--studio-bar-height',Math.ceil(b.height)+'px');
    css.setProperty('--studio-bar-bottom',Math.ceil(b.bottom)+'px');
  };
  const dockObserver=new ResizeObserver(placeStatus);dockObserver.observe(bar);
  window.addEventListener('resize',placeStatus,opts);
  const setTools=open=>{
    toggle.setAttribute('aria-expanded',String(open));bar.classList.toggle('is-expanded',open);
    tools.inert=compact.matches && !open;
  };
  setTools(false);
  toggle.addEventListener('click',()=>setTools(toggle.getAttribute('aria-expanded')!=='true'),opts);
  compact.addEventListener('change',()=>setTools(false),opts);
  bar.addEventListener('keydown',e=>{if(e.key==='Escape' && bar.classList.contains('is-expanded')){setTools(false);toggle.focus();}},opts);
  function hide(){
    clearTimeout(hideTimer);card.dataset.visible='false';
  }
  function clearCandidate(){
    clearTimeout(timer);timer=0;candidate='';
  }
  function setVersion({siteName,versionName,versionId:nextId}={}) {
    if(siteName){id('studioSiteName').textContent=siteName;document.title=siteName+' · Garden Studio';}
    if(nextId===versionId && versionLabel(nextId,versionName)===version)return;
    versionId=nextId || '';version=versionLabel(nextId,versionName);
    seen='';clearCandidate();hide();
  }
  function progress(fraction,label) {
    if(!Number.isFinite(fraction))return;
    const pct=Math.round(Math.min(1,Math.max(0,fraction))*100);
    progressTrack.setAttribute('aria-valuenow',String(pct));
    id('studioLoadValue').textContent=pct+'%';id('loadBar').style.width=pct+'%';
    if(label)id('loadText').textContent=label;
    switchCard.hidden=!start.hidden || pct===100;
    if(!switchCard.hidden){
      switchCard.querySelector('.studio-switch-label').textContent=label||id('loadText').textContent;
      switchCard.querySelector('.studio-switch-value').textContent=pct+'%';
    }
  }
  function observeRoom(room,{immersive=false,eligible=true}={}) {
    if(immersive!==lastImmersive){lastImmersive=immersive;seen='';clearCandidate();hide();}
    if(!start.hidden || !eligible){clearCandidate();hide();return;}
    const key=room?.id || '';
    if(!key){seen='';clearCandidate();hide();return;}
    if(key===seen || key===candidate)return;
    clearCandidate();candidate=key;
    // A footstep on a doorway's boundary must not flash adjacent room titles.
    timer=setTimeout(()=>{
      if(!start.hidden || candidate!==key)return;
      seen=key;candidate='';timer=0;
      const roomName=capital(room.params?.name || room.name || room.meta?.plain_label || key);
      const sub=detailsOf(room,version);
      card.dataset.roomId=key;name.textContent=roomName;detail.textContent=sub;hide();
      if(immersive) { onXRRoom(roomName,sub); return; }
      card.dataset.visible='true';
      hideTimer=setTimeout(hide,duration);
    },180);
  }
  const lamps=[...document.querySelectorAll('[data-lamp-scope]')];
  for(const button of lamps)button.addEventListener('click',()=>onLamp(button.dataset.lampScope),opts);
  function setLamps({allOn=false}={}) {
    for(const button of lamps){
      button.setAttribute('aria-pressed',String(allOn));
      button.textContent=allOn?'House lights on':'House lights off';
      button.title=allOn?'Switch all house lights off':'Switch all house lights on';
    }
  }
  function dispose(){aborter.abort();dockObserver.disconnect();clearCandidate();hide();switchCard.hidden=true;}
  return {setVersion,progress,observeRoom,setLamps,dispose};
}

/** A short-lived, head-relative title. No mesh, texture or material is allocated
 * until it is needed in an actual immersive walk. */
export function createXRRoomTitle(THREE,camera) {
  let mesh=null,canvas=null,ctx=null,until=0;
  function show(roomName,detail='') {
    if(!roomName)return;
    if(!mesh){
      canvas=document.createElement('canvas');canvas.width=640;canvas.height=150;ctx=canvas.getContext('2d');
      const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
      texture.generateMipmaps=false;texture.minFilter=THREE.LinearFilter;
      const material=new THREE.MeshBasicMaterial({map:texture,transparent:true,depthTest:false,depthWrite:false,toneMapped:false});
      mesh=new THREE.Mesh(new THREE.PlaneGeometry(.55,.129),material);
      mesh.name='Passive studio room title';mesh.renderOrder=1900;mesh.frustumCulled=false;
      mesh.raycast=()=>{};mesh.castShadow=mesh.receiveShadow=false;
      mesh.position.set(0,-.255,-1.35);camera.add(mesh);
    }
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.fillStyle='rgba(34,48,40,.9)';ctx.beginPath();ctx.roundRect(0,0,640,150,15);ctx.fill();
    ctx.fillStyle='#c4d4bd';ctx.font='600 22px system-ui';ctx.fillText(detail,28,44);
    let size=51;do{ctx.font=size+'px Georgia,serif';if(ctx.measureText(roomName).width<=584)break;size--;}while(size>25);
    ctx.fillStyle='#fbf8ed';ctx.fillText(roomName,28,111,584);
    mesh.material.map.needsUpdate=true;mesh.material.opacity=1;mesh.visible=true;
    until=performance.now()+duration;
  }
  function hide(){if(mesh)mesh.visible=false;until=0;}
  function update(now=performance.now(),eligible=true){
    if(!mesh?.visible)return;
    if(!eligible || now>=until){hide();return;}
    mesh.material.opacity=Math.min(1,(until-now)/300);
  }
  function dispose(){
    if(!mesh)return;
    camera.remove(mesh);mesh.geometry.dispose();mesh.material.map.dispose();mesh.material.dispose();
    mesh=canvas=ctx=null;until=0;
  }
  return {show,update,hide,dispose,get mesh(){return mesh;}};
}
