import {moveGroup,checkGroup} from '../furnish/placement.mjs';

// Initialise the first room layout from issued paper-spec requests. Client saves
// subsequently own the item positions and finishes. Never replay on a client layout.
export function applyHistoricalChanges(seedItems, changes, {version, rooms, context, wallColours = {}, roomFloors = {}, appliedChangeIds = [], moveReceipts = []}) {
  const legacyVersion = {as_built_now:'before', approved_2b:'after'}[version] || version;
  const items = structuredClone(seedItems);
  const byId = new Map(items.map(item => [item.id, item]));
  const byRoom = new Map(rooms.map(r => [r.id, r]));
  const walls = {...wallColours}, floors = {...roomFloors}, applied = new Set(appliedChangeIds);
  const moved=new Map(), receipts=structuredClone(moveReceipts);
  const basePaint = new Map(), accents = new Map();
  function paint(roomId) {
    const room = byRoom.get(roomId);
    if (!room) throw Error('Cannot resolve the signed wall finish of '+roomId);
    const accent = accents.get(roomId), base = basePaint.get(roomId);
    const accentIds=new Set(room.wallFaces.filter(f=>f.edgeIndex===accent?.edge).map(f=>f.id));
    if (accent && !accentIds.size) throw Error('Cannot match signed wall '+roomId+' edge '+accent.edge);
    for (const face of room.wallFaces) {
      const colour = accentIds.has(face.id) ? accent.hex : base;
      if (colour) walls[face.id] = colour; else delete walls[face.id];
    }
  }
  function updateGroup(next) {
    const updated=moveGroup(items,next);
    for(const item of updated) Object.assign(byId.get(item.id),item);
    return new Set(updated.map(item=>item.id));
  }
  function move(id, before, after, sourceId) {
    const old = byId.get(id);
    if (!old) return new Set(); // A change to fixed architecture remains in the signed request list.
    const it=structuredClone(old);
    if (before?.position_m && after?.position_m) {
      it.position = it.position.map((p,i) => Math.round((p + after.position_m[i] - before.position_m[i]) * 1e8) / 1e8);
    }
    if (Number.isFinite(before?.yaw_deg) && Number.isFinite(after?.yaw_deg) && before.yaw_deg !== after.yaw_deg) {
      it.rotation = ((it.rotation + after.yaw_deg - before.yaw_deg) % 360 + 360) % 360;
    }
    if (after?.room && after.room !== before?.room) {
      it.room = after.room;
      if (it.host?.type === 'floor' || it.host?.type === 'ceiling') it.host.id = it.host.type+'/'+it.room;
    }
    moved.set(id,sourceId);
    return updateGroup(it);
  }
  for (const ch of changes) {
    if (ch.version !== legacyVersion || !['active','sent'].includes(ch.status) || applied.has(ch.id)) continue;
    const id = ch.target?.item, room = ch.target?.room, a = ch.after || {}, b = ch.before || {};
    switch (ch.op) {
      case 'item.move': {
        const carried=move(id,b,a,ch.id);
        for (const child of a.carried || []) if (!carried.has(child.id)) move(child.id,b.carried?.find(c=>c.id===child.id),child,ch.id);
        break;
      }
      case 'item.finish': {
        const item = byId.get(id);
        if (item && a.value?.hex) item.finishes = {...item.finishes,[a.part]:a.value.hex};
        break;
      }
      case 'room.walls': basePaint.set(room,a.value?.hex); paint(room); break;
      case 'room.accent': accents.set(room,a.value); paint(room); break;
      case 'room.floor': if (a.value?.id) floors[room]=a.value.id; else delete floors[room]; break;
      default: continue; // Other signed requests belong to the spec/build queue.
    }
    applied.add(ch.id);
  }
  if(context) for(const [id,sourceId] of moved) {
    const item=byId.get(id), original=seedItems.find(i=>i.id===id);
    const check=checkGroup(context,seedItems,item);
    if(check.ok) continue;
    const requested=item.position.slice();
    // Try only a measured door's two perpendiculars. This preserves placement
    // along the doorway, and keeps its yaw and host height exactly as requested.
    const blocked=context.openings.filter(o=>o.kind!=='window' && check.reasons.includes('Blocks the '+o.label));
    let accepted;
    for(let mm=1;mm<=100 && !accepted;mm++) for(const door of blocked) for(const sign of [1,-1]) {
      const p=[requested[0]+door.n[0]*sign*mm/1000,requested[1],requested[2]+door.n[1]*sign*mm/1000];
      const candidate={...item,position:[Math.round(p[0]*1000)/1000,p[1],Math.round(p[2]*1000)/1000]};
      if(checkGroup(context,seedItems,candidate).ok) {accepted=candidate;break;}
    }
    const placed=accepted || {...item,position:original.position,rotation:original.rotation,host:original.host,room:original.room};
    updateGroup(placed);
    receipts.push({id,sourceId,requested,placed:placed.position.slice(),delta:placed.position.map((v,i)=>Math.round((v-requested[i])*1000)/1000),
      status:accepted?'adjusted':'pending',reason:check.reasons.join('. ')});
  }
  return {items, wallColours:walls, roomFloors:floors, appliedChangeIds:[...applied], moveReceipts:receipts};
}

if (typeof process !== 'undefined' && process.argv[1] && import.meta.url === (await import('node:url')).pathToFileURL(process.argv[1]).href) {
  const fs = await import('node:fs/promises'), path = await import('node:path');
  const {buildRoomContext} = await import('../furnish/placement.mjs');
  const args = process.argv.slice(2);
  const flag = name => { const i=args.indexOf('--'+name); if (i<0 || !args[i+1]) throw Error('Missing --'+name); return args[i+1]; };
  const siteRoot=flag('site-root'), specRoot=flag('spec-root'), version=flag('version'), seedFile=flag('seed');
  const read=async file=>JSON.parse(await fs.readFile(file,'utf8'));
  const [seed,spec,elements,ledger]=await Promise.all([read(seedFile),read(path.join(specRoot,'spec_v1.json')),read(path.join(siteRoot,version+'_elements.json')),read(path.join(specRoot,'changes','changes.json'))]);
  const changes=await Promise.all(ledger.changes.map(async row=>({...await read(path.join(specRoot,'changes',row.file)),status:row.status})));
  const doorsFile=path.join(path.dirname(path.dirname(siteRoot)),'planner',path.basename(path.dirname(specRoot)),'doors.json');
  const doors=await read(doorsFile);
  const variants=await read(path.join(path.dirname(seedFile),'variants.json')).catch(e=>{if(e.code==='ENOENT')return {};throw e;});
  const context=buildRoomContext({site:path.basename(siteRoot),version,spec,elements,doors,seed,variants});
  const result=applyHistoricalChanges(seed.items,changes,{...seed,version,rooms:context.rooms,context});
  process.stdout.write(JSON.stringify({...seed,...result}));
}
