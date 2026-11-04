"""Adapt the signed studio schedule to the reusable kit. Dimensions in metres."""
from pathlib import Path
import math,sys,re,json,hashlib
KIT=Path(__file__).resolve().parents[1]/'library/kit'
sys.path.insert(0,str(KIT))
import bpy
from mathutils import Matrix, Vector
import studio
from hb_countertops import base_units, board_support, rail_drape, splash_segments
from studio import F

FINISH_COLOURS={}
FINISH_ROUGHNESS={}

def constant_roughness(finishes):
    """Single-value, parametric specifications only. Texture-driven/ranged finishes keep their maps."""
    result={}
    for finish in finishes:
        if finish.get('asset',{}).get('source')!='parametric':continue
        note=finish.get('notes','')
        value=re.search(r'\broughness\s+([01](?:\.\d+)?)(?=\s*(?:[,;]|$))',note,re.I)
        if value:result[finish['id']]=float(value.group(1))
    return result

def print_inks(m):
    # Original matte inks for the signed neutral coastal and charcoal drawings.
    for role,colour in [('ink_charcoal','#474744'),('ink_shale','#8B8982'),('ink_mist','#BAB7AE')]:
        name='Studio.print.'+role
        ink=bpy.data.materials.get(name)
        if ink is None:
            ink=m['matboard'].copy();ink.name=name
            rgba=F._rgba(colour);ink.diffuse_color=rgba
            ink.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=rgba
        m[role]=ink

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
    if kind=='shower' and 'walk-in' in label:opts['walk_in']=True;opts['screen']='walk_in'
    if kind=='alcove_unit':
        opts.update(cupboard_h=asset.get('cupboard_h_mm',900)/1000,
                    shelf_t=asset.get('shelf_t_mm',30)/1000,levels=asset.get('shelves_y_m',[]))
    if kind=='sofa':opts.update(throw=False,scatter=False)
    if kind=='art':
        opts.update(motif=asset.get('motif',''),palette=asset.get('palette',''))
        if asset.get('motif'):
            opts['signed_print']=True
            opts['print_variant']=int(hashlib.sha256(it['id'].encode()).hexdigest()[:4],16)
    if kind=='vase':opts['stems']='eucalyptus' if 'eucalyptus' in label else 'dried' if 'dried' in label else ''
    if kind=='sofa' and it.get('materials',{}).get('frame')=='RATTAN':opts['cane']=True
    if kind=='kettle':opts['ellipse']=it['size_mm'][1]/it['size_mm'][0]
    if 'source_sofa' in it:opts['source_sofa']=it['source_sofa']
    return source,kind,opts

def fingerprint(it):
    fields={k:it.get(k) for k in ('asset','type','size_mm','materials','position_m','yaw_deg','source_sofa','fruit_host','splash_segments')}
    if it.get('asset',{}).get('kind') in ('alcove_unit','bookcase','shelf_unit'):fields['joinery_revision']=2
    return 'GS-'+hashlib.sha256(json.dumps(fields,sort_keys=True).encode()).hexdigest()[:20]

ROLES={'legs':'oak','frame':'oak','rail':'oak','hooks':'black','shade':'linen','fabric':'linen','pole':'bronze',
       'front':'kitchen','cupboard':'kitchen','shelves':'oak','top':'stone','worktop':'stone','upholstery':'upholstery',
       'base':'ceramic','linen':'white_fabric','throw':'throw','glaze':'ceramic','glass':'glass','tray':'glaze','vanity':'oak','basin':'glaze','cushions':'upholstery'}
PRIMARY={'extractor':'metal','bench':'oak','coat_hook':'oak','rug':'rug','flush_light':'black','radiator':'white','cushion':'linen',
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
        if role=='frame' and kind=='shower':key='black'
        if role=='base' and kind=='floor_lamp':key='bronze'
        if role=='top' and kind=='alcove_unit':key='oak'
        if key is None:continue
        source=m['oak'] if fid=='KIT-ISLAND' else m[key];name='spec_'+fid+'.'+source.name
        mat=bpy.data.materials.get(name)
        if mat is None:
            mat=source.copy();mat.name=name;mat['finish_id']=fid
            hex_colour=FINISH_COLOURS.get(fid)
            if hex_colour:
                colour=F._rgba(hex_colour);shader=mat.node_tree.nodes.get('Principled BSDF')
                mat.diffuse_color=colour;shader.inputs['Base Color'].default_value=colour
                if shader.inputs['Base Color'].is_linked and fid!='KIT-ISLAND':
                    mat['studio_tint']=list(colour[:3])
        if key=='ceramic' and fid in FINISH_ROUGHNESS:
            rough=mat.node_tree.nodes.get('Principled BSDF').inputs['Roughness']
            if not rough.is_linked:rough.default_value=FINISH_ROUGHNESS[fid]
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
    if source.startswith('wooden_bowl'):
        # Use the same turned profile as the independently seated fruit. Only
        # the shell material changes, including its actual oak grain and normal map.
        m['ceramic']=m['oak']
    if opts.get('signed_print'):print_inks(m)
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
        w,d,h=tuple(n/1000 for n in host['size_mm'])
        b=F._Builder('fruit_bowl',it['id'],(w,d,h),collection,m,False,{})
        positions=[(-.052,-.025),(.045,-.026),(0,.047)] if min(w,d)>.24 else [(0,0)]
        for i,(x,y) in enumerate(positions):
            v,f=F.apple_geometry((.074,.074,.072),i*.73)
            z=max(F.fruit_bowl_inner_height(x+px,y+py,w,d,height=h)-pz for px,py,pz in v)+.0004
            b.mesh('apple',[(px+x,py+y,pz+z) for px,py,pz in v],f,'apple_red' if i==0 else 'apple',True)
            top=v[0][2]+z
            b.rod('stem',(x,y,top-.001),(x+.003,y,top+.012),.0018,'oak',sides=7)
        made=b.objects
    elif it.get('splash_segments'):
        b=F._Builder(kind,it['id'],dims,collection,m,False,{})
        x0,y0,z0=it['position_m'];angle=math.radians(it['yaw_deg'])
        inv=Matrix.Rotation(-angle-math.pi,3,'Z')
        for run in it['splash_segments']:
            at=inv@Vector((run['x']-x0,-(run['z']-z0),0))
            b.box('quartz-return',(run['width'],d,run['height']),
                  (at.x,at.y,run['base']-y0+run['height']/2),'stone',.0015,
                  rotation=(0,0,math.radians(run['yaw'])-angle-math.pi))
        made=b.objects
    elif source=='board' and it['asset'].get('leaning'):
        b=F._Builder(kind,it['id'],dims,collection,m,False,{})
        grip=min(.027,w*.1);corner=.012;shoulder=h-.065
        outline=[(-w/2+corner,0),(w/2-corner,0),(w/2,corner),(w/2,shoulder-corner),(w/2-corner,shoulder),
                 (grip+.016,shoulder),(grip,shoulder+.014)]
        outline.extend((grip*math.cos(a),h-grip+grip*math.sin(a)) for a in [math.pi*j/12 for j in range(13)])
        outline.extend([(-grip,shoulder+.014),(-grip-.016,shoulder),(-w/2+corner,shoulder),(-w/2,shoulder-corner),(-w/2,corner)])
        n=len(outline);verts=[(x,y,z) for y in (-d/2,d/2) for x,z in outline]
        faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        b.mesh('one-piece-oak-paddle',verts,faces,'oak',grain='z')
        made=b.objects
        made[0].rotation_euler.x=-math.radians(6)
        bpy.context.view_layer.update()
        lowest=min((o.matrix_world@v.co).z for o in made if o.type=='MESH' for v in o.data.vertices)
        made[0].location.z-=lowest
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
        elif source=='tea_towel':
            radius=.007;front,back=rail_drape(h,radius)
            # Distances along the cut cloth furnish a metric weave through both hems and the rounded crown.
            rows=[]
            for j in range(7):
                t=j/7;rows.append((-radius,front*t,front*t,1-t))
            for j in range(13):
                a=math.pi*j/12
                rows.append((-radius*math.cos(a),front+radius*math.sin(a),front+radius*a,0))
            for j in range(1,8):
                t=j/7;rows.append((radius,front-back*t,front+math.pi*radius+back*t,t))
            m['stripe']=m['white_fabric'].copy();m['stripe'].name='Studio towel · woven sage stripe'
            for key,tint in [('white_fabric','#eee5d4'),('stripe','#82917c')]:
                if key=='white_fabric':
                    m[key]=m[key].copy();m[key].name='Studio towel · natural cotton'
                colour=F._rgba(tint);mat=m[key];mat['studio_tint']=list(colour[:3])
                mat.diffuse_color=colour;mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=colour
            verts=[];faces=[];uv=[];columns=65;tile=float(m['white_fabric'].get('texture_size_m',1))
            for j,(depth,z,length,free) in enumerate(rows):
                for i in range(columns):
                    u=i/(columns-1);wave=math.sin(u*math.pi*6+.4)
                    verts.append(((u-.5)*w,depth+wave*(.0012+.010*free),z+.003*free*math.cos(u*math.pi*6)))
                    uv.append((u*w/tile,length/tile))
                    if i and j:
                        n=j*columns+i;faces.append((n-columns-1,n-columns,n,n-1))
            textile=b.mesh('woven-rail-towel',verts,faces,'white_fabric',True,uv=uv)
            textile.data.materials.append(m['stripe'])
            for face in textile.data.polygons:
                distance=min(abs(verts[k][0]) for k in face.vertices)/w
                face.material_index=int(.35<distance<.38 or .408<distance<.434)
        else:
            # A towel folds over its host bar. The long dimension runs down.
            rad=.007 if source=='tea_towel' else .012;verts=[];faces=[]
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
    elif kind in ('kitchen_base','kitchen_tall','integrated_fridge','dishwasher','alcove_unit','towel_rail'):
        # Custom-size the component construction in plan. The signed top
        # datum governs H for counters with a tap, oven or hob above it.
        shape=list(dims)
        for attempt in range(10):
            cw,cd,ch=shape
            if kind in ('kitchen_base','dishwasher'):
                opts['worktop_bounds_m']=[-cw/2,cw/2,-cd/2,cd/2]
            objects=studio.make(kind,'scandinavian',it['id'],collection,shape,m,**opts)
            observed=tuple(objects[0]['size_m'])
            active=3 if kind=='towel_rail' else 2
            if max(abs(observed[k]-dims[k]) for k in range(active))<.001:break
            studio.discard(objects)
            for k in range(active):shape[k]=max(.001,shape[k]*dims[k]/observed[k])
        else:raise ValueError('Cabinet/rail cannot fit measured opening: '+it['id']+' '+str(observed))
        made=objects
    elif source in ('linear_pendant','pendant_drum'):
        drop=(it['asset'].get('drop_mm',0)/1000+h) if source=='pendant_drum' else max(h,it['position_m'][1]-it['asset'].get('bottom_y',it['position_m'][1]))
        add(kind,(w,d,drop),(0,0,-drop),**opts)
    elif kind=='wall_wc':
        add(kind,(w,d*.72,.32),(0,-d*.14,.17))
        add('cistern_box',(w,d*.28,h),(0,d*.36,0))
    elif kind=='semi_pedestal':
        add(kind,dims,(0,0,max(0,h-.44)),**opts)
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
    bpy.context.view_layer.update()
    bars=[o for o in made if o.type=='MESH' and ('.oven-pull' in o.name or '.towel-bar' in o.name)]
    bar=None
    if bars:
        rows=[(o,[o.matrix_world@v.co for v in o.data.vertices]) for o in bars]
        if kind=='towel_rail':
            o,verts=min(rows,key=lambda pair:abs(sum(p.z for p in pair[1])/len(pair[1])-.62*h))
            bar=sum(verts,Vector())/len(verts)
        else:
            o,verts=rows[0]
            bar=Vector(((min(v.x for v in verts)+max(v.x for v in verts))/2,min(v.y for v in verts)+.006,(min(v.z for v in verts)+max(v.z for v in verts))/2))
    empties=[o.name for o in made if o.type=='EMPTY']
    anchor=merge_objects(made,collection,name)
    if source in ('pendant_drum','linear_pendant'):
        crown=max(v.co.z for v in anchor.data.vertices)
        anchor.data.transform(Matrix.Translation((0,0,-crown)));anchor.data.update()
    for key in empties:
        obj=bpy.data.objects.get(key)
        if obj:bpy.data.objects.remove(obj,do_unlink=True)
    if bar is not None:anchor.data["textile_bar_local"]=list(Matrix.Rotation(math.pi,3,"Z")@bar)
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
        asset=it['asset']
        if asset.get('leaning') and asset.get('kind')=='board':
            units=base_units(items,it['room'])
            if units:
                support,pos=board_support(it,units,items);it['host']=support['id'];it['yaw_deg']=support['yaw_deg'];it['position_m']=pos
        if asset.get('kind')=='upstand' and asset.get('hob_splash'):
            it['splash_segments']=splash_segments(it,base_units(items,it['room']))
            if not it['splash_segments']:raise ValueError('No worktop backs for '+it['id'])
        if it['asset'].get('kind') in ('towels','tea_towel'):
            towel=it['asset']['kind']=='towels'
            carriers=[i for i in items if i['room']==it['room'] and (i['asset'].get('kind')=='towel_rail' if towel else 'oven' in i['type'].lower() and i['asset'].get('kind')=='kitchen_unit')]
            if carriers:it['host']=min(carriers,key=lambda i:math.dist(i['position_m'],it['position_m']))['id']
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
    from hb_furnish import snap_loose,validate,bvh_of
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
        if source=='flush_disc' and 'ray-cast' in it['asset'].get('place',''):
            hit=shell.ray_cast(Vector((pos[0],-pos[2],1.2)),Vector((0,0,1)),4)[0]
            if hit:pos[1]=hit.z-.002
        obj=bpy.data.objects.new('SPEC-'+it['id'],mesh)
        coll.objects.link(obj);place(obj,pos,yaw)
        host=it.get('host') or (it.get('source_sofa') or {}).get('id','')
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
    for it in items:
        child=by_id.get(it['id']);host=by_id.get(child.get('host_id','')) if child else None
        if host is None:continue
        if it['asset'].get('kind') in ('towels','tea_towel') and host.data and 'textile_bar_local' in host.data:
            radius=.007 if it['asset']['kind']=='tea_towel' else .012
            height=it['size_mm'][2]/1000
            bar=Vector(host.data['textile_bar_local'])
            drop=rail_drape(height,radius)[0] if it['asset']['kind']=='tea_towel' else height-radius
            local=bar-Vector((0,0,drop))
            child.matrix_world=host.matrix_world@Matrix.Translation(local)
            # Published host mounting datum, expressed in glTF metre axes.
            child['host_offset_m']=[local.x,local.z,-local.y]
            child['host_bar_m']=[bar.x,bar.z,-bar.y]
            host['textile_bar_m']=child['host_bar_m']
        elif it.get('fruit_host'):
            child.matrix_world=host.matrix_world.copy()
        elif it.get('source_sofa'):
            # The drape was authored on this exact host in the schedule frame.
            original=it['source_sofa']['position_m'];delta=host.matrix_world.translation-Vector((original[0],-original[2],original[1]))
            child.matrix_world=Matrix.Translation(delta)@Matrix.Translation(Vector((it['position_m'][0],-it['position_m'][2],it['position_m'][1])))@Matrix.Rotation(math.radians(it['yaw_deg']),4,'Z')
        elif it['asset'].get('source')=='addendum' and not it.get('fruit_host'):
            # Select a real upward facing surface of the named host near the
            # scheduled point. Avoid lowering a bottle through a basin aperture.
            tree=bvh_of(host);centre=child.matrix_world.translation;best=None
            for radius in (0,.025,.05,.075,.105,.14):
                for k in range(1 if radius==0 else 12):
                    x=centre.x+radius*math.cos(k*math.pi/6);y=centre.y+radius*math.sin(k*math.pi/6)
                    hit=tree.ray_cast(Vector((x,y,centre.z+.16)),Vector((0,0,-1)),.65)
                    if hit[0] is None or hit[1].z<.70:continue
                    score=radius+abs(hit[0].z-centre.z)
                    if best is None or score<best[0]:best=(score,Vector((x,y,hit[0].z+.0003)))
            if best:child.matrix_world=Matrix.Translation(best[1]-centre)@child.matrix_world
    validate(vkey,placed,house_objs,log)
    return placed
