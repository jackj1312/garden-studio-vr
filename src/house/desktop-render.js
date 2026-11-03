import {Quaternion,Vector3} from 'three';

/* Walking and inspection share the same scene. While the camera moves it uses
   the native colour pass. A stationary view gets contact shadows and can keep
   its displayed frame between visible changes. XR owns its own framebuffer. */
export function createDesktopRender() {
  const position=new Vector3(),rotation=new Quaternion(),lastPosition=new Vector3(),lastRotation=new Quaternion();
  let previousView=null,lastMotion=-Infinity,lastPaint=-Infinity,lastKey='',lastExposure=NaN,mode='contact';
  function choose({now,camera,view,key,active,cacheable,shadow,exposure}) {
    camera.getWorldPosition(position);camera.getWorldQuaternion(rotation);
    const changed=view!==previousView||position.distanceToSquared(lastPosition)>.00000016 ||
      1-Math.abs(rotation.dot(lastRotation))>.00000002;
    if(changed||active)lastMotion=now;
    previousView=view;lastPosition.copy(position);lastRotation.copy(rotation);
    if(now-lastMotion<350){mode='moving';return mode;}
    const dirty=shadow||key!==lastKey||Math.abs(exposure-lastExposure)>.018;
    if(mode==='moving'||dirty||!cacheable||now-lastPaint>500){
      mode='contact';lastPaint=now;lastKey=key;lastExposure=exposure;return mode;
    }
    mode='held';return mode;
  }
  return {choose,get mode(){return mode;}};
}
