import {Ray,Vector3} from 'three';

/* Keep the surveyed garden and its sun pass. The desktop design walk uses the
   native framebuffer; the house's indoor screen effects resume on editor exit. */
export function gardenDesktopRender(renderer,normalRatio) {
  let active=false,restoreRatio=normalRatio,entry=null,bvh=null,key='',mask=null,covered=false;
  const ray=new Ray(new Vector3(),new Vector3(0,1,0)),lastEye=new Vector3(Infinity,Infinity,Infinity);
  function use(on) {
    if(renderer.xr.isPresenting || on===active)return;
    if(on)restoreRatio=renderer.getPixelRatio();
    active=on;
    const ratio=on?Math.min(restoreRatio,1.25):restoreRatio;
    if(renderer.getPixelRatio()!==ratio)renderer.setPixelRatio(ratio);
    key='';lastEye.set(Infinity,Infinity,Infinity);
  }
  function roofCover(view,eye,stage,force=false) {
    const model=view.model,id=[stage,model.asBuilt,...Object.values(model.storeyShown)].join('|');
    const changed=view!==entry||view.bvh!==bvh||id!==key;
    if(changed){
      entry=view;bvh=view.bvh;key=id;
      mask=new Uint8Array(model.parts.length);
      for(const p of model.parts){
        const name=p.name+' '+p.group;
        mask[p.index]=model.masks.visible[p.index] && !p.context &&
          /roof|ceiling|floor|deck|rafter|beam|joist|soffit|porch.*lining/i.test(name)?1:0;
      }
    }
    if(changed||force||eye.distanceToSquared(lastEye)>.015){
      lastEye.copy(eye);ray.origin.copy(eye);
      covered=!!bvh.raycast(ray,6,mask);
    }
    return covered;
  }
  return {use,roofCover,get active(){return active;}};
}
