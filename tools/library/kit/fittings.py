"""Detailed appliances, fittings and styling from the independent interior library."""
import math
import furnishings as F
FIXED_CUSTOM={'shelf','washer','dryer','switch','alarm','coat_hook','extractor','semi_pedestal','wall_vanity','wall_wc','cistern_box','mirror_cabinet','integrated_fridge','bookcase','alcove_unit','shelf_unit','splashback','upstand','flue','flush_light','linear_pendant','hand_towel','joinery_backing'}

def _custom(kind,name,dims,collection,m,options):
    b=F._Builder(kind,name,dims,collection,m,options.get('fixed',kind in FIXED_CUSTOM),options)
    w,d,h=dims
    if kind=='stool':
        b.options['seat_height_m']=.65
        F._dining_chair(b)
        for sx in [-1,1]:
            b.rod('footrest',(sx*w*.39,-d*.34,.29),(sx*w*.39,d*.34,.29),.013,'oak')
        b.rod('front-footrail',(-w*.39,-d*.34,.29),(w*.39,-d*.34,.29),.013,'oak')
    elif kind=='joinery_backing':
        b.box('finished-support-packer',(w,d,h),(0,0,h/2),'kitchen',.002)
    elif kind=='shelf':
        b.box('solid-oak-board',(w,d,h),(0,0,h/2),'oak',.002)
        for sx in [-1,1]:b.box('concealed-bracket',(.025,d*.80,.035),(sx*w*.32,d*.10,-.0175),'white',.002)
    elif kind in ['washer','dryer']:
        b.box('appliance-case',(w-.02,d-.025,h-.045),(0,.010,(h-.045)/2),'white',.012)
        b.box('worktop',(w,d,.026),(0,0,h-.013),'quartz',.003)
        b.box('control-panel',(w-.025,.026,.095),(0,-d/2+.006,h-.10),'white',.004)
        b.box('display',(.145,.005,.033),(w*.17,-d/2-.010,h-.10),'dark_glass',.002)
        knob=b.lathe('selector',[(.027,0),(.027,.018),(.023,.023)],(0,0,0),'metal',32)
        knob.rotation_euler.x=math.pi/2;knob.location=(-w*.22,-d/2-.007,h-.10)
        ring=b.lathe('door-ring',[(w*.295,0),(w*.307,.018),(w*.29,.035),(w*.237,.035),(w*.228,.020),(w*.237,0),(w*.295,0)],(0,0,0),'metal',64)
        ring.rotation_euler.x=math.pi/2;ring.location=(0,-d/2-.001,h*.46)
        glass=b.lathe('round-door-glass',[(0,0),(w*.23,0),(w*.225,.018),(w*.19,.034),(0,.042)],(0,0,0),'dark_glass',64)
        glass.rotation_euler.x=math.pi/2;glass.location=(0,-d/2-.017,h*.46)
        b.box('pull',(.023,.024,.115),(w*.257,-d/2-.038,h*.46),'white',.007)
        b.box('plinth',(w-.055,.012,.060),(0,-d/2+.018,.045),'white',.003)
    elif kind=='switch':
        b.box('plate',(w,d,h),(0,0,h/2),'white',.003)
        b.box('rocker',(.029,.005,.044),(0,-d/2-.001,h/2),'white',.001)
        for x in [-w*.37,w*.37]:
            b.rod('screw',(x,-d/2-.001,h/2),(x,-d/2-.002,h/2),.002,'metal',sides=8)
    elif kind=='alarm':
        b.lathe('body',[(w*.44,0),(w*.50,.008),(w*.48,h*.77),(w*.35,h),(0,h)],(0,0,0),'white',40)
        for i in range(10):
            a=i*math.pi*2/10
            b.rod('vent',(math.cos(a)*w*.36,math.sin(a)*w*.36,.008),(math.cos(a)*w*.36,math.sin(a)*w*.36,.012),.003,'black',sides=6)
    elif kind=='television':
        # Freestanding screen and two real feet, within declared overall height.
        base=0 if options.get('wall_mounted') else .055
        screen_h=h-base
        b.box('back',(w,d,screen_h),(0,d*.30,base+screen_h/2),'black',.007)
        b.box('screen',(w-.016,.003,screen_h-.016),(0,-d*.28,base+screen_h/2),'dark_glass',.004)
        for x in ([] if options.get('wall_mounted') else [-w*.31,w*.31]):
            b.rod('stand',(x,0,.065),(x-.035,-.095,.006),.006,'black')
            b.rod('rear-foot',(x,0,.065),(x+.035,.065,.006),.006,'black')
    elif kind=='fruit_bowl':
        bh=b.h;b.h=.055;F._vase(b,True);b.h=bh
        for i,(x,y) in enumerate([(-.052,-.025),(.045,-.026),(0,.047)]):
            verts,faces=F.apple_geometry((.081,.079,.076),phase=i*.63)
            z=F.fruit_bowl_seating(verts,x,y,w,d)
            apple=b.mesh('apple',[(x+a,y+c,z+e) for a,c,e in verts],faces,'apple_red' if i==1 else 'apple',True)
            apple['fruit_profile']='rounded-five-lobed-with-stem-dimple'
            apple['support_surface']='actual64-sided-bowl-inner-profile'
            apple['support_clearance_m']=.0004
            top=verts[0][2]
            b.rod('fruit-stem',(x,y,z+top-.001),(x+.003,y,z+top+.015),.002,'oak',sides=7)
    elif kind=='diffuser':
        radius=min(w,d)*.43
        b.lathe('scent-bottle',[(radius*.78,0),(radius,.008),(radius,h*.42),(radius*.46,h*.52),(radius*.43,h*.56),(0,h*.56)],(0,0,0),'dark_glass',32)
        b.lathe('collar',[(radius*.47,0),(radius*.47,.015),(radius*.31,.015),(radius*.31,0),(radius*.47,0)],(0,0,h*.53),'bronze',24)
        for i in range(6):
            a=i*math.pi/3
            b.rod('reed',(math.cos(a)*radius*.16,math.sin(a)*radius*.16,h*.54),(math.cos(a)*radius*.72,math.sin(a)*radius*.72,h*(.92+.08*(i%2))),.0011,'oak',sides=6)
    elif kind=='candle':
        b.lathe('jar',[(w*.44,0),(w*.50,.006),(w*.50,h),(w*.46,h),(w*.46,.012),(0,.012)],(0,0,0),'ceramic',40)
        b.lathe('wax',[(0,0),(w*.45,0),(w*.45,.008),(0,.008)],(0,0,h-.020),'wax',32)
        b.rod('wick',(0,0,h-.012),(0,0,h-.002),.0009,'wax_wick',sides=6)
    elif kind=='coat_hook':
        b.box('oak-rail',(w,.025,.055),(0,d*.30,h*.46),'oak',.007)
        for i in range(int(options.get('hook_count',4))):
            x=(i-(int(options.get('hook_count',4))-1)/2)*w*.24
            b.tube('black-hook',[(x,d*.16,h*.47),(x,-d*.18,h*.22),(x,-d*.38,h*.26),(x,-d*.38,h*.46)],.0045,'black',sides=10)
    elif kind=='basket':
        b.box('woven-bottom',(w-.02,d-.02,.015),(0,0,.0075),'rug',.005)
        for x in [-1,1]:b.box('woven-side',(.014,d,h),(x*(w/2-.007),0,h/2),'rug',.004)
        for y in [-1,1]:b.box('woven-end',(w-.028,.014,h),(0,y*(d/2-.007),h/2),'rug',.004)
        for z in [.025,h-.009]:
            b.tube('bound-edge',[(-w/2,-d/2,z),(w/2,-d/2,z),(w/2,d/2,z),(-w/2,d/2,z)],.006,'basket',True,8)
        for x in [-1,1]:
            b.tube('handle',[(x*w*.50,-d*.14,h*.70),(x*w*.52,-d*.14,h*.82),(x*w*.52,d*.14,h*.82),(x*w*.50,d*.14,h*.70)],.005,'basket',sides=8)
    elif kind=='extractor':
        b.box('hood',(w,d,h if options.get('integrated') else .055),(0,0,h/2 if options.get('integrated') else .032),'metal',.004)
        if not options.get('integrated'):b.box('flue',(w*.38,d*.49,max(.004,h-.055)),(0,d*.22,(h+.055)/2),'metal',.005)
        b.box('filter',(w*.72,d*.64,.004),(0,-d*.1,.003),'black',.002)
        for x in [-w*.34,w*.34]:b.lathe('worklight',[(.020,0),(.020,.003)],(x,-d*.30,.001),'bulb',20)
    elif kind=='kettle':
        b.lathe('base',[(w*.42,0),(w*.45,.009),(w*.42,.016)],(0,0,0),'black',32,ellipse=options.get('ellipse',1))
        b.lathe('body',[(w*.39,0),(w*.43,.020),(w*.40,h*.60),(w*.28,h*.80),(w*.24,h*.82),(0,h*.82)],(0,0,.016),'metal',48,ellipse=.88*options.get('ellipse',1))
        b.lathe('lid',[(w*.25,0),(w*.26,.007),(0,.014)],(0,0,h*.82+.016),'black',32,ellipse=options.get('ellipse',1))
        b.tube('handle',[(w*.28,0,h*.72),(w*.49,0,h*.70),(w*.52,0,h*.30),(w*.33,0,h*.20)],.012,'black',sides=12)
        b.tube('spout',[(-w*.29,0,h*.57),(-w*.46,0,h*.69),(-w*.49,0,h*.80)],.020,'metal',sides=16)
    else:_signed_custom(b,kind)
    points=[o.matrix_basis@v.co for o in b.objects if o.type=='MESH' for v in o.data.vertices]
    if points:
        b.root['built_bounds_min_m']=[min(p[i] for p in points) for i in range(3)]
        b.root['built_bounds_max_m']=[max(p[i] for p in points) for i in range(3)]
    return b.objects

def _reflection(b,w,h,y,z):
    face=b.mesh('reflection-plane',[(-w/2,y,z),(w/2,y,z),(w/2,y,z+h),(-w/2,y,z+h)],[(0,1,2,3)],'mirror',False,collide=False)
    face['mirror']=True;face['mirror_id']=b.name+'.reflection';face['cast_shadow']=False

def _signed_custom(b,kind):
    w,d,h=b.w,b.d,b.h
    if kind=='semi_pedestal':
        F._bowl_shell(b,'ceramic-basin',w,d,.16,(0,0,h-.16),'glaze')
        b.lathe('semi-pedestal',[(w*.20,0),(w*.30,.18),(w*.34,.28)],(0,d*.18,h-.44),'glaze',40,ellipse=.70)
        F._tap_at(b,0,d*.30,h-.025,.16,.12,mat=b.options.get("tap_material","metal"))
        b.box('wall-bracket',(w*.58,.025,.09),(0,d/2-.014,h-.21),'metal',.008)
    elif kind=='wall_vanity':
        b.box('wall-hung-cabinet',(w-.018,d-.012,h-.12),(0,0,(h-.12)/2),'oak',.006)
        for i in range(2):F._cabinet_face(b,'oak-drawer',0,(i+.5)*(h-.12)/2,w-.024,(h-.12)/2-.004,-d/2,'oak')
        # Basin rim and shallow counter geometry match the existing vanity support datum.
        F._vanity_counter(b)
        F._bowl_shell(b,'wash-basin',w*.68,d*.75,.12,(0,-d*.05,h-.12),'glaze')
        F._tap_at(b,w*.26,d*.26,h-.067,.22,.13,mat=b.options.get("tap_material","metal"))
    elif kind=='wall_wc':
        # Origin is the actual lowest pan surface; concealed service casing is separate.
        F._bowl_shell(b,'wall-hung-pan',w,d*.78,h*.82,(0,-d*.09,0),'glaze',power=.70)
        b.lathe('seat-ring',[(w*.44,0),(w*.49,.014),(w*.36,.028),(w*.35,.012),(w*.44,0)],(0,-d*.09,h*.82),'white',48,ellipse=d/w*.78)
        b.box('wall-mount-back',(w*.74,.065,h*.65),(0,d*.40,h*.41),'glaze',.025)
    elif kind=='cistern_box':
        b.box('concealed-cistern',(w,d,h),(0,0,h/2),'wall',.004)
        b.box('black-flush-plate',(.21,.012,.14),(0,-d/2-.006,h-.23),'black',.005)
        for x in [-.049,.049]:b.box('dual-flush',(.085,.005,.105),(x,-d/2-.014,h-.23),'black',.004)
    elif kind=='mirror_cabinet':
        b.box('cabinet-back',(w,d,h),(0,0,h/2),'white',.004)
        _reflection(b,w-.024,h-.024,-d/2-.002,.012)
        for x in [-w/2+.007,w/2-.007]:b.box('side-frame',(.014,.017,h),(x,-d/2-.006,h/2),'white',.002)
        for z in [.007,h-.007]:b.box('end-frame',(w,.017,.014),(0,-d/2-.006,z),'white',.002)
        b.rod('finger-pull',(w*.34,-d/2-.02,.05),(w*.34,-d/2-.02,.16),.004,'metal')
    elif kind=='integrated_fridge':
        F._kitchen(b,'kitchen_tall')
        b.root['appliance_type']='integrated_fridge_freezer'
        b.box('refrigerator-seal',(w-.045,.007,h*.02),(0,-d/2-.019,h*.36),'black',.002)
        for x in [-w*.32,w*.32]:b.box('vent-slot',(.12,.004,.010),(x,-d/2-.023,.040),'black',.001)
    elif kind in ['bookcase','alcove_unit','shelf_unit']:
        steel=kind=='shelf_unit';mat='metal' if steel else 'kitchen';shelf='metal' if steel else 'oak'
        for x in [-w/2+.015,w/2-.015]:b.box('upright',(.030,d,h),(x,0,h/2),mat,.002)
        b.box('back',(w,.014,h),(0,d/2-.007,h/2),mat,.002)
        low=.72 if kind=='alcove_unit' else .06
        if kind=='alcove_unit':
            b.box('lower-carcass',(w-.04,d-.025,low),(0,0,low/2),mat,.003)
            for x in [-w/4,w/4]:F._cabinet_face(b,'lower-door',x,low/2,w/2-.008,low-.008,-d/2,mat)
        for j in range(5):
            z=low+(h-low-.025)*j/4
            b.box('shelf',(w-.03,d,.025),(0,0,z+.0125),shelf,.002)
    elif kind in ['splashback','upstand']:
        if b.options.get('metro'):
            # 75x150 running bond with narrow recessed grout.
            b.box('grout-back',(w,d*.55,h),(0,d*.22,h/2),'metro_grout',.001)
            for row in range(math.ceil(h/.075)):
                shift=.075*(row%2)
                for col in range(-1,math.ceil(w/.15)+1):
                    a=max(-w/2,-w/2+col*.15+shift);c=min(w/2,-w/2+(col+1)*.15+shift)
                    z0=row*.075;z1=min(h,(row+1)*.075)
                    if c-a>.004 and z1-z0>.004:b.box('metro-tile',(c-a-.002,d,z1-z0-.002),((a+c)/2,0,(z0+z1)/2),'metro_tile',.002)
        else:b.box('quartz-splash',(w,d,h),(0,0,h/2),'stone',.002)
    elif kind=='flue':
        b.rod('black-flue',(0,0,0),(0,0,h),w/2,'black',sides=32)
        for z in [.015,h-.015]:b.lathe('flue-collar',[(w*.52,0),(w*.52,.015)],(0,0,z),'black',32)
    elif kind=='flush_light':
        b.lathe('mount',[(w*.48,0),(w*.50,h*.68),(w*.42,h),(0,h)],(0,0,0),'black',48)
        b.lathe('opal-lens',[(0,0),(w*.44,0),(w*.44,.008),(0,.008)],(0,0,.001),'bulb',48)
    elif kind=='linear_pendant':
        b.box('black-linear-body',(w,d,.048),(0,0,.024),'black',.008)
        b.box('opal-lens',(w-.025,d-.020,.004),(0,0,.002),'bulb',.001)
        for x in [-w*.30,w*.30]:b.rod('suspension',(x,0,.048),(x,0,h),.0018,'black',sides=6)
        b.box('ceiling-canopy',(w*.65,.060,.025),(0,0,h-.0125),'black',.005)
    elif kind=='soap':
        b.lathe('bottle',[(w*.36,0),(w*.48,.010),(w*.46,h*.65),(w*.22,h*.72),(0,h*.72)],(0,0,0),'ceramic',32)
        b.rod('pump-stem',(0,0,h*.71),(0,0,h*.93),.008,'metal')
        b.tube('pump-spout',[(0,0,h*.92),(0,-d*.40,h*.92),(0,-d*.42,h*.87)],.006,'metal',sides=8)
    elif kind=='keys':
        b.tube('key-ring',[(w*.17*math.cos(i*math.pi/12),d*.17*math.sin(i*math.pi/12),.003) for i in range(24)],.0016,'metal',True,6)
        for i in range(2):
            x=(-.15+i*.30)*w;b.box('key-shaft',(.007,d*.58,.003),(x,-d*.18,.002),'metal',.001)
            b.box('key-head',(.018,.020,.004),(x,d*.16,.003),'metal',.004)
            for j in range(3):b.box('key-tooth',(.011,.004,.003),(x+.004,-d*.42+j*.006,.002),'metal',.0005)
    elif kind=='hand_towel':
        radius=w*.39
        centre=h-radius-.007
        rear=d/2
        ring_y=-rear+.011
        b.box('wall-mount',(w*.22,.015,.05),(0,rear-.0075,h-.027),'black',.006)
        b.rod('bracket',(0,rear-.014,h-.013),(0,ring_y,h-.013),.009,'black')
        b.tube('black-ring',[(radius*math.cos(i*math.pi/24),ring_y,centre+radius*math.sin(i*math.pi/24)) for i in range(48)],.007,'black',True,8)
        verts,faces=[],[]
        for j in range(15):
            a=max(0,min(math.pi,(j-1)*math.pi/12))
            for i in range(25):
                u=i/24
                x=(u-.5)*radius*1.12
                bar_z=centre-math.sqrt(radius**2-x**2)
                y=ring_y-.008*math.cos(a)
                z=bar_z+.008*math.sin(a)
                if j in (0,14):
                    z=(.004 if j==0 else h*.15)+.003*math.sin(u*math.pi*4)
                    y+=.0018*math.sin(u*math.pi*6)
                verts.append((x,y,z))
                if i and j:
                    k=j*25+i
                    faces.append((k-26,k-25,k,k-1))
        towel=b.mesh('ring-draped-towel',verts,faces,'white_fabric',True,collide=False)
        towel['support_surface']='lower-ring-arc'
    elif kind=='chopping_board':
        b.box('oak-board',(w,d,h),(0,0,h/2),'oak',.012,grain='z')
        b.rod('handle',(0,0,h),(0,0,h+.045),.022,'oak',sides=16)
    elif kind=='utensils':
        b.lathe('crock',[(w*.34,0),(w*.48,h*.43),(w*.45,h*.48),(w*.37,h*.48),(w*.32,.025),(0,.025)],(0,0,0),'ceramic',32)
        for i in range(4):
            x=(i-1.5)*w*.17;b.rod('wooden-handle',(x,0,h*.10),(x*.85,0,h*.84),.004,'oak',sides=8)
            b.soft('spoon-head',(w*.18,.012,h*.20),(x*.85,0,h*.87),'oak',puff=.05,seam=False)
    elif kind in ['toaster','coffee_machine']:
        b.box('body',(w,d,h),(0,0,h/2),'metal' if kind=='toaster' else 'black',.018)
        if kind=='toaster':
            for y in [-d*.20,d*.20]:b.box('bread-slot',(w*.72,d*.10,.005),(0,y,h+.001),'black',.004)
            b.rod('lever',(w*.51,0,h*.35),(w*.51,0,h*.70),.007,'black')
        else:
            b.box('coffee-face',(w*.75,.010,h*.68),(0,-d/2-.005,h*.56),'metal',.005)
            b.box('drip-tray',(w*.82,d*.35,.020),(0,-d*.40,.030),'metal',.003)
            b.rod('spout',(0,-d/2-.02,h*.60),(0,-d/2-.02,h*.47),.010,'metal')
    elif kind=='bottles':
        b.box('tray',(w,d,.016),(0,0,.008),'oak',.005)
        for x in [-w*.22,w*.22]:b.lathe('glass-bottle',[(w*.12,0),(w*.15,.02),(w*.15,h*.67),(w*.07,h*.79),(w*.06,h),(0,h)],(x,0,.016),'dark_glass',32)
    elif kind=='coat':
        import furnishing_surfaces as surfaces
        garment=surfaces.hanging_garment(w,d,h);repeat=float(b.m['accent'].get('texture_size_m',1));depth=garment['depth_function']
        for part in garment['parts']:
            obj=b.mesh(part['name'],part['vertices'],part['faces'],'accent',True,collide=True,uv=[(u/repeat,v/repeat) for u,v in part['uv']]);obj['textile_thickness_m']=garment['thickness_m']
        for i,path in enumerate(garment['seam_paths']):b.tube('stitched-seam-%02d'%i,path,.00055,'accent',sides=5)
        for side in [-1,1]:
            pts=[(side*w*.125,h*.81),(side*w*.19,h*.765),(side*w*.07,h*.64),(side*w*.025,h*.70)]
            vs=[(x,depth(x,z,True)-.0012,z) for x,z in pts]+[(x,depth(x,z,True)-.0024,z) for x,z in pts]
            b.mesh('folded-lapel',vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],'accent',True,collide=False)
        for i in range(4):
            z=h*(.56-i*.11);b.rod('sewn-button',(w*.032,depth(w*.032,z,True)-.001,z),(w*.032,depth(w*.032,z,True)-.0025,z),.0035,'bronze',sides=12)
        b.tube('front-placket',[(0,depth(0,h*t,True)-.001,h*t) for t in [.07,.18,.29,.40,.51,.62,.70]],.0010,'accent',sides=6)
        b.root['garment_construction']='connected sleeve/shoulder cutting pattern, thin front/back skins, sewn side gussets, open neck/cuffs/hem'
    else:raise ValueError('Unknown independent styling kind '+kind)



