"""Adapt the signed studio schedule to the reusable kit. Dimensions in metres."""
from pathlib import Path
import math,sys,re,json,hashlib
KIT=Path(__file__).resolve().parents[1]/'library/kit'
sys.path.insert(0,str(KIT))
import bpy
from mathutils import Matrix, Vector
import studio
from studio import F

ALIASES={
 'bench_box':'bench','hook_rail':'coat_hook','flush_disc':'flush_light','pendant_drum':'pendant','radiator_panel':'radiator',
 'framed_print':'art','throw_drape':'throw','modern_coffee_table_01':'coffee_table','slab':'hearth','tv':'television',
 'curtain_pair':'curtain','book_encyclopedia_set_01':'book_stack','decorative_book_set_01':'books',
 'wooden_candlestick':'candle','standing_picture_frame_01':'art','side_table_01':'side_table','WoodenTable_02':'side_table',
 'hanging_picture_frame_03':'art','wicker_basket_02':'basket','cooker_hood':'extractor','wall_units':'kitchen_wall',
 'tile_band':'splashback','round_wooden_table_02':'side_table','dining_chair_02':'dining_chair','jug_01':'utensils','board':'chopping_board',
 'planter_pot_clay':'plant','steel_frame_shelves_01':'shelf_unit','washing_machine':'washer','table_low':'coffee_table',
 'chest':'dresser','towels':'rail_cloth','downlight_set':'downlight','desk_lamp_arm_01':'table_lamp',
 'island':'kitchen_base','bar_chair_round_01':'stool','modern_ceiling_lamp_01':'pendant','bottle_pair_tray':'bottles',
 'tea_towel':'rail_cloth','mirror_round':'mirror','mirror_rect':'mirror','towel_ring':'hand_towel',
}
def recipe(it):
    asset=it['asset'];source=asset.get('kind') or asset.get('id') or asset.get('source')
    kind=ALIASES.get(source,source); label=it['type'].lower()
    opts={}
    if source.startswith('potted_plant'):kind='plant'
    if source.startswith('ceramic_vase'):kind='vase'
    if source.startswith('wooden_bowl'):kind='bowl'
    if source=='elements':
        if 'wardrobe' in label:kind='wardrobe'
        elif 'shower' in label:kind='shower';opts['walk_in']='walk-in' in label
        elif 'wall-hung wc' in label:kind='wall_wc'
        elif 'wc' in label:kind='toilet'
        elif 'wall-hung vanity' in label:kind='wall_vanity'
        elif 'vanity' in label:kind='vanity'
        else:kind='semi_pedestal'
    if source=='kitchen_unit':
        kind='kitchen_tall' if 'tall' in label else 'kitchen_base'
        if 'fridge' in label:kind='integrated_fridge'
        if 'dishwasher' in label:kind='dishwasher'
        if 'sink' in label:opts.update(sink=True,sink_mount='undermount' if 'undermount' in label else 'inset')
        if 'oven' in label:opts.update(appliance='oven',hob='hob' in label)
        if 'drawer' in label:opts['drawers']=3
    if source=='island':opts.update(island=True,seating_overhang_m=.25)
    if source=='tv':opts['wall_mounted']=True
    if source=='mirror_round':opts['round']=True
    if source=='tile_band':opts['metro']=True
    if kind=='towel_rail':opts['towel']=False
    if kind=='sofa':opts.update(throw=False,scatter=False)
    if kind=='kettle':opts['ellipse']=it['size_mm'][1]/it['size_mm'][0]
    if 'source_sofa' in it:opts['source_sofa']=it['source_sofa']
    return source,kind,opts

def fingerprint(it):
    fields={k:it.get(k) for k in ('asset','type','size_mm','materials','position_m','yaw_deg','source_sofa','fruit_host')}
    return 'GS-'+hashlib.sha256(json.dumps(fields,sort_keys=True).encode()).hexdigest()[:20]

ROLES={'legs':'oak','frame':'oak','rail':'oak','hooks':'black','shade':'linen','fabric':'linen','pole':'bronze',
       'front':'kitchen','cupboard':'kitchen','shelves':'oak','top':'stone','worktop':'stone','upholstery':'upholstery',
       'base':'ceramic','linen':'white_fabric','throw':'throw','glaze':'ceramic'}
PRIMARY={'bench':'oak','coat_hook':'oak','rug':'rug','flush_light':'black','radiator':'white','cushion':'linen',
         'throw':'throw','stove':'black','hearth':'hearth_slate','television':'black','bookcase':'kitchen',
         'splashback':'metro_tile','upstand':'stone','roman_blind':'linen','linear_pendant':'black','mirror':'oak',
         'toilet':'glaze','wall_wc':'glaze','vanity':'glaze','semi_pedestal':'glaze','wall_vanity':'glaze',
         'shower':'glaze','wardrobe':'kitchen','towel_rail':'black','bedside':'oak','dresser':'oak','desk':'oak'}
def schedule_palette(it,kind):
    m=studio.palette('scandinavian')
    for role,fid in it.get('materials',{}).items():
        if not isinstance(fid,str) or not re.fullmatch(r'[A-Z0-9-]+',fid):continue
        key=PRIMARY.get(kind,'oak') if role=='all' else ROLES.get(role)
        if role=='frame' and kind=='bed':key='upholstery'
        if role=='base' and kind=='floor_lamp':key='bronze'
        if role=='top' and kind=='alcove_unit':key='oak'
        if key is None:continue
        source=m[key];name='spec_'+fid+'.'+source.name
        mat=bpy.data.materials.get(name)
        if mat is None:
            mat=source.copy();mat.name=name;mat['finish_id']=fid
        m[key]=mat
        if key=='oak':m['frame']=mat
        if key=='upholstery' and kind=='dining_chair':m['linen']=mat
    return m

def merge_objects(objects,collection,name):
    """Flatten the kit's local transforms into a single reusable spec-frame mesh."""
    bpy.context.view_layer.update()
    meshes=[o for o in objects if o.type=='MESH']
    anchor=bpy.data.objects.new(name,bpy.data.meshes.new(name))
    collection.objects.link(anchor)
    with bpy.context.temp_override(active_object=anchor,selected_editable_objects=[anchor,*meshes]):
        bpy.ops.object.join()
    # join removed its mesh arguments, empties are removed by the caller by name.
    anchor.data.transform(Matrix.Rotation(math.pi,4,'Z'))
    anchor.data.update()
    return anchor

def build_item(it,collection):
    source,kind,opts=recipe(it);dims=[x/1000 for x in it['size_mm']]
    m=schedule_palette(it,kind);name=fingerprint(it)
    made=[]
    def add(k,ds,pos=(0,0,0),exact=False,**settings):
        fn=studio.make_at_size if exact else studio.make
        objects=fn(k,'scandinavian',it['id'],collection,ds,m,**settings)
        objects[0].location=pos;made.extend(objects)
        return objects
    w,d,h=dims
    if source=='note_only':return None
    if it.get('fruit_host'):
        # The original bowl remains the measured host. Only the seated fruit
        # and stems of its kit assembly are exported at the host datum.
        host=it['fruit_host']
        w,d,_=host['size_mm'];w/=1000;d/=1000
        objects=studio.make('fruit_bowl','scandinavian',it['id'],collection,(max(.24,w),max(.24,d),.12),m)
        keep=[objects[0]]+[o for o in objects[1:] if '.apple' in o.name or 'fruit-stem' in o.name]
        for o in objects[1:]:
            if o not in keep:bpy.data.objects.remove(o,do_unlink=True)
        made=keep
    elif it['asset'].get('source')=='addendum':
        made=studio.make(kind,'scandinavian',it['id'],collection,dims,m)

    elif kind=='hearth' or kind=='rail_cloth' or source=='throw_drape':
        b=F._Builder(kind,it['id'],dims,collection,m,False,{})
        if kind=='hearth':b.box('slate-hearth',dims,(0,0,h/2),'hearth_slate',.003)
        elif source=='throw_drape':
            # This scheduled size is the unfolded cloth. Its seated geometry
            # is produced together with its host sofa using the actual seat silhouette.
            bpy.data.objects.remove(b.root,do_unlink=True)
            host=opts['source_sofa'];host_dims=[n/1000 for n in host['size_mm']]
            ref=studio.make_at_size('sofa','scandinavian','support',collection,host_dims,m,throw=False,scatter=False)
            frame=tuple(ref[0]['construction_dimensions_m']);studio.discard(ref)
            ref=studio.make('sofa','scandinavian','support',collection,frame,m,throw=True,scatter=False)
            delta=[a-b for a,b in zip(host['position_m'],it['position_m'])]
            yaw=math.radians(it['yaw_deg'])
            # Root is authored front -Y. Offsets are transformed into its frame.
            ref[0].location=Matrix.Rotation(-yaw-math.pi,3,'Z') @ Vector((delta[0],-delta[2],delta[1]))
            bpy.context.view_layer.update()
            made=[ref[0]]+[o for o in ref[1:] if o.get('textile_support')]
            for o in ref[1:]:
                if o not in made:bpy.data.objects.remove(o,do_unlink=True)
        else:
            # A towel folds over its host bar. The long dimension runs down.
            rad=min(.012,d*.32);verts=[];faces=[]
            for j in range(15):
                a=max(0,min(math.pi,(j-1)*math.pi/12))
                for i in range(25):
                    u=i/24;y=-rad*math.cos(a);z=h-rad+rad*math.sin(a)
                    if j==0 or j==14:z=(.002 if j==0 else h*.17)+.002*math.sin(u*math.pi*4)
                    verts.append(((u-.5)*w,y+.002*math.sin(u*math.pi*6),z))
                    if i and j:
                        n=j*25+i;faces.append((n-26,n-25,n,n-1))
            b.mesh('fold-over-bar',verts,faces,'white_fabric',True)
        if source!='throw_drape':made=b.objects
    elif it['asset'].get('source')=='polyhaven' and kind not in ('plant','mirror'):
        # Source product boxes permit uniform fit-inside. Rebuild the new
        # components at a shorter construction length until the limiting axis fits.
        construction=list(dims)
        for attempt in range(8):
            objects=studio.make(kind,'scandinavian',it['id'],collection,construction,m,**opts)
            ratio=max(n/t for n,t in zip(objects[0]['size_m'],dims))
            if abs(1-ratio)<.005:break
            studio.discard(objects);construction=[n/ratio for n in construction]
        else:raise ValueError('No fit-inside solution for '+it['id'])
        made=objects
    elif source=='downlight_set':
        for x,z in it['asset']['positions_xz']:
            add('downlight',dims,(it['position_m'][0]-x,z-it['position_m'][2],0))
    elif source=='curtain_pair':
        stack=it['asset'].get('stacked_each_side_mm',280)/1000
        for sign in [-1,1]:
            panel=add('curtain',(stack,d,h-.024),(sign*(w-stack)/2,0,0))
            for o in list(panel[1:]):
                if '.curtain-pole' in o.name:made.remove(o);bpy.data.objects.remove(o,do_unlink=True)
        b=F._Builder('curtain',it['id']+'-rail',dims,collection,m,True,{})
        b.rod('full-span-pole',(-w/2,0,h-.024),(w/2,0,h-.024),.0125,'bronze');made.extend(b.objects)
    elif source=='wall_units':
        a=it['asset'];px,_,pz=it['position_m']
        spans=a.get('segments_x') or a.get('segments_z') or []
        yaw=math.radians(it['yaw_deg'])
        for start,end in spans:
            length=abs(end-start);count=max(1,round(length/.60))
            for i in range(count):
                v=start+(end-start)*(i+.5)/count
                offset=-(v-px)*math.cos(yaw) if 'segments_x' in a else (v-pz)*math.sin(yaw)
                add('kitchen_wall',(length/count,d,h),(offset,0,0),exact=True)
    elif kind in ('kitchen_base','kitchen_tall','integrated_fridge','dishwasher'):
        # The signed H is the worktop datum. Taps, hob rings and pulls may project.
        opts['worktop_bounds_m']=[-w/2,w/2,-d/2,d/2]
        add(kind,dims,**opts)
    elif source in ('linear_pendant','pendant_drum'):
        drop=(it['asset'].get('drop_mm',0)/1000+h) if source=='pendant_drum' else max(h,it['position_m'][1]-it['asset'].get('bottom_y',it['position_m'][1]))
        add(kind,(w,d,drop),**opts)
    elif kind=='kettle':
        for _ in range(7):
            objects=studio.make(kind,'scandinavian',it['id'],collection,(w,d,h),m,**opts)
            mw,md,mh=tuple(objects[0]['size_m'])
            if max(abs(m-t) for m,t in zip((mw,md,mh),dims))<.001:break
            studio.discard(objects)
            w*=dims[0]/mw;h*=dims[2]/mh;opts['ellipse']*=dims[1]/md
        else:raise ValueError('Kettle body cannot fit its measured worktop envelope')
        made=objects
    elif kind in ('toilet','shower','semi_pedestal','vanity','wall_vanity','wall_wc','towel_rail','radiator','coat_hook','curtain','chopping_board','television','stool','mirror','plant','extractor','fruit_bowl','hand_towel','tap','downlight'):
        add(kind,dims,**opts)
    else:
        add(kind,dims,exact=True,**opts)
    empties=[o.name for o in made if o.type=='EMPTY']
    anchor=merge_objects(made,collection,name)
    for key in empties:
        obj=bpy.data.objects.get(key)
        if obj:bpy.data.objects.remove(obj,do_unlink=True)
    anchor.data.name=name
    return anchor

def library_path(site,vkey):return Path(site)/'kit'/f'{vkey}.blend'

def load_meshes(site,vkey):
    path=library_path(site,vkey)
    if not path.is_file():raise FileNotFoundError(f'Prepare studio variants first: {path}')
    with bpy.data.libraries.load(str(path)) as (source,target):
        names=tuple(source.meshes);target.meshes=list(names)
    return dict(zip(names,target.meshes))


def schedule(spec,vkey,addendum):
    items=[dict(i) for i in spec['versions'][vkey]['items']]
    for it in items:
        if it['asset'].get('kind')=='throw_drape':
            sofas=[i for i in items if i['room']==it['room'] and i['asset'].get('kind')=='sofa']
            it['source_sofa']=min(sofas,key=lambda i:math.dist(it['position_m'],i['position_m']))
    for ad in addendum:
        if vkey not in ad['versions']:continue
        kind=next((value for word,value in [('keys dish','bowl'),('keys','keys'),('fruit','fruit_bowl'),('soap','soap'),('candle','candle'),('diffuser','diffuser'),('book','book_stack')] if word in ad['type'].lower()),None)
        if not kind:raise ValueError('Unmapped addendum '+ad['id'])
        item=dict(ad,asset={'kind':kind,'source':'addendum'},category='decor',status='signed addendum',materials={})
        if kind=='fruit_bowl':
            host=next(i for i in items if i['id']==ad['host'])
            # The signed bowl holds the fitted fruit. Replace both with the seated assembly.
            item.update(fruit_host=host,position_m=host['position_m'],yaw_deg=host['yaw_deg'])
        items.append(item)
    return items

def place_schedule(spec,vkey,N,coll,house_objs,site,spec_path,log):
    from mathutils.bvhtree import BVHTree
    from hb_items import place,SHELL_HOLD_CATS,SOLID_CATS
    from hb_furnish import snap_loose,validate
    version=spec['versions'][vkey]
    extra=Path(spec_path).with_name('spec_v1_addendum2_details.json')
    items=schedule(spec,vkey,json.loads(extra.read_text())['items'] if extra.exists() else [])
    meshes=load_meshes(site,vkey)
    stage=N if N>1 else 1
    placed=[];by_id={}
    verts,faces=[],[]
    for ob,p in house_objs:
        if p.get('context') or ob.type!='MESH':continue
        start=len(verts);verts.extend(ob.matrix_world@v.co for v in ob.data.vertices)
        faces.extend(tuple(start+i for i in pl.vertices) for pl in ob.data.polygons)
    shell=BVHTree.FromPolygons(verts,faces)
    for it in items:
        source,kind,opts=recipe(it);pos=list(it['position_m']);yaw=it['yaw_deg']
        key=fingerprint(it)
        if source=='note_only':mesh=None
        else:
            mesh=meshes.get(key)
            if mesh is None:raise ValueError('Missing measured kit variant '+vkey+' '+it['id'])
        if source=='elements':
            target=it['asset']['element']
            replaced=[ob for ob,p in house_objs if p['props'].get('element')==target]
            house_objs[:]=[(ob,p) for ob,p in house_objs if p['props'].get('element')!=target]
            for old in replaced:bpy.data.objects.remove(old,do_unlink=True)
        if 'drop_to_bottom_y' in it['asset']:pos[1]=it['asset']['drop_to_bottom_y']
        if source=='linear_pendant':pos[1]=it['asset'].get('bottom_y',pos[1])
        if source=='flush_disc' and 'ray-cast' in it['asset'].get('place',''):
            hit=shell.ray_cast(Vector((pos[0],-pos[2],1.2)),Vector((0,0,1)),4)[0]
            if hit:pos[1]=hit.z-.002
        obj=bpy.data.objects.new('SPEC-'+it['id'],mesh)
        coll.objects.link(obj);place(obj,pos,yaw)
        host=it.get('host') or ''
        movable=it['category'] in SHELL_HOLD_CATS or kind in {'table_lamp','floor_lamp','washer','dryer','fridge'}
        room=next(r for r in version['rooms'] if r['id']==it['room'])
        props=dict(element='SPEC-'+it['id'],spec_id=it['id'],spec_kind=source,kit_kind=kind,kit_variant=key,
                   room_id=it['room'],host_id=host,furnishing=movable,stage_in=stage,seq=.95 if N>1 else 0.,
                   category='finish' if N>1 else 'existing',group='fitting',storey=room['storey'],label=it['type'],plain_label=it['type'],
                   drawing='studio schedule',conf='scaled',provenance='studio kit',collide=it['category'] in SOLID_CATS,
                   walkable=False)
        for k,v in props.items():obj[k]=v
        placed.append((obj,dict(props=props,atom=dict(id=props['element'],kind='spec',meta=props,provenance='studio kit'))))
        by_id[it['id']]=obj
    snap_loose(placed,house_objs,N,log,items)
    validate(vkey,placed,house_objs,log)
    return placed
