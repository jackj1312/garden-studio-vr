import {previewPrefix} from '../studio-layout-service.js';

export function showHousePreview(){
  if(!previewPrefix())return false;
  document.documentElement.dataset.studioPreview='true';
  const identity='Latest house · preview';
  document.querySelector('.studio-welcome > .studio-kicker').textContent=identity;
  document.querySelector('.studio-identity > .studio-kicker').textContent=identity;
  const garden=new URL('/garden/',location.href);garden.port='8450';
  function link(){
    const a=document.createElement('a');a.href=garden.href;a.className='studio-preview-link';a.textContent='Open editable garden';return a;
  }
  document.querySelector('.studio-welcome .studio-intro').after(link());
  const action=document.querySelector('#baTools [data-garden-open]');if(action)action.after(link());
  return true;
}
