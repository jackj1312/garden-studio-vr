import {computeState} from './data.js?v=p8';

export const styleName = s => ({scandinavian:'Scandinavian',country:'Country / farmhouse'}[s] || s.charAt(0).toUpperCase()+s.slice(1));
const names = {
  single_bed:['bed','bed'], dining_chair:['dining_chair','chair'], dining_table:['dining_table','table'],
  coffee_table:['coffee_table','table'], side_table:['side_table','table'], dresser:['chest','cabinet'],
  bedside:['bedside','cabinet'], wardrobe:['wardrobe','tall_cabinet'], stool:['counter_stool','stool'],
  curtain:['window_dressing','curtains'],roman_blind:['window_dressing','curtains'],art:['art','frame'],
  plant:['plant_floor','plant'], television:['tv','tv'],shelf:['shelving','shelving'],desk:['desk','table'],
  kitchen_base:['kitchen_unit','kitchen_unit'], kitchen_wall:['kitchen_wall_units','wall_cabinet'],
  kitchen_tall:['kitchen_unit','tall_cabinet'], linear_pendant:['pendant','pendant'],flush_light:['ceiling_light','flush'],
  toilet:['wc','wc'], wall_wc:['wc','wc'],wall_vanity:['basin','basin'],downlight:['downlights','downlights'],
};
const lights = new Set(['pendant','floor_lamp','table_lamp','wall_light','flush_light','downlight','linear_pendant']);
const text = k => k?.replaceAll('_',' ') || '';
export function plannerEntry(entry) {
  const [slot,shape] = names[entry.kind] || [entry.kind,entry.kind];
  return {...entry, slot,shape,mount:entry.host,styles:[styleName(entry.style)],size_mm:entry.size_m.map(n=>Math.round(n*1000)),
    category:lights.has(entry.kind)?'lighting':entry.kind==='plant'?'plant':entry.fixed?'fitting':'furniture',
    source:{source:'studio',kind:entry.kind}, model:true, kit:true,
    description:(entry.family ? entry.family+' · ' : '')+text(entry.kind)};
}
export function roomTypes(room) {
  const name = (room?.name || '').toLowerCase();
  const tests = {living:/living|sitting|lounge/,dining:/dining/,kitchen:/kitchen/,bedroom:/bedroom/,
    bathroom:/bath|cloak|wc|en.?suite|shower/,utility:/utility|laundry/,hall:/hall|landing|lobby|porch/,outdoor:/garden|outside/};
  return Object.keys(tests).filter(k=>tests[k].test(name));
}
export function catalogueMatch(e,{kind='',style='',room='',search=''}={}) {
  const wanted=Array.isArray(room)?room:room?[room]:[];
  return (!kind || e.kind===kind) && (!style || e.style===style) &&
    (!wanted.length || e.roomTypes.includes('any') || wanted.some(k=>e.roomTypes.includes(k))) &&
    (!search || [e.name,e.kind,e.style,e.family,e.id].map(text).join(' ').toLowerCase().includes(search.toLowerCase().trim()));
}
export function plannerItem(row, original, entry, num) {
  return {...original, id:row.id,room:row.room,catalogue:row.catalogueId, shared:row, type:(row.variant===row.catalogueId && entry?.name) || original?.type || entry?.name || text(row.kind),
    num:original?.num || num, category:original?.category || entry?.category || 'furniture', size_mm:row.size.map(m=>Math.round(m*1000)),
    position_m:row.position.slice(),yaw_deg:row.rotation, materials:{...original?.materials,...row.finishes},
    lampOn:row.lampOn ?? original?.lampOn ?? false, added:!original,
    provenance:original?.provenance || 'proposed',status:original?.status || 'placed in shared layout'};
}

export function projectRoomState(db,vkey,changes,session) {
  if (!session?.ready) return computeState(db,vkey,changes);
  const sourceIds=new Set([...(session.variants.sourceIds||[]),...session.layout.items.map(r=>r.id)]);
  const state=computeState(db,vkey,changes.filter(c=>!(c.op.startsWith('item.') && sourceIds.has(c.target?.item))));
  const {layout,variants,context} = session, surviving=state.items, base=new Map(surviving);
  for (const id of sourceIds) surviving.delete(id);
  let next=state.nextNum;
  for (const row of layout.items) {
    const original=base.get(row.id), entry=db.entries.get(row.catalogueId);
    surviving.set(row.id,plannerItem(row,original,entry,original?.num || next++));
  }
  state.nextNum=next; state.runtime=true; state.layoutItems=layout.items; state.variants=variants;
  state.wallColours=layout.wallColours; state.context=context;
  for (const room of state.house.rooms) {
    const overrides={...(state.rooms.get(room.id)||{})};
    // The layout contains the migrated result. A later client edit or explicit clear wins.
    delete overrides.walls; delete overrides.accent; delete overrides.floor;
    const floor=db.catalogue.floors.find(f=>f.id===layout.roomFloors[room.id]);
    if (floor) overrides.floor=floor;
    state.rooms.set(room.id,overrides);
  }
  return state;
}
export function wallFaces(state,roomId,edgeIndex) {
  const faces=state.context?.rooms.find(r=>r.id===roomId)?.wallFaces || [];
  return faces.filter(f=>edgeIndex===undefined || f.edgeIndex===edgeIndex);
}
