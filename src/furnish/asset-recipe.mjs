/* The viewer, planner and next build resolve exactly the same published front
 * and finish slots. Site models already face -Z. Stock kit models face +Z. */
export function variantKey(item,stock){
  return item.variant==='standard'&&stock.has(item.catalogueId)?item.catalogueId:item.variant;
}
export function variantModel(key,variants,stock,lite=false){
  const measured=variants[key];
  if(measured)return {file:lite&&measured.questUrl||measured.url,stock:false,frontAngle:0};
  const entry=stock.get(key);
  if(entry?.model)return {file:entry.model,stock:true,frontAngle:Math.PI};
  throw new Error('No furniture model for '+key);
}
const roles={fabric:/FAB-|linen|upholster|fabric|cotton|textile|velvet/i,
  timber:/wood|oak|walnut/i,frame:/frame|wood|oak|steel|iron/i,metal:/metal|steel|black|bronze/i};
export function partColour(item,materialName){
  return Object.entries(item.finishes||{}).find(([role])=>{
    const signed=item.sourceFinishes?.[role];
    return signed?materialName.includes('spec_'+signed+'.'):roles[role]?.test(materialName);
  })?.[1];
}
