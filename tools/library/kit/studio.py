"""Garden Studio kit entry point. Model sizes are construction dimensions in metres."""
import json
import math
from pathlib import Path
import bpy
from mathutils import Vector
import furnishings as F
from fittings import _custom, FIXED_CUSTOM

HERE = Path(__file__).resolve().parent
DIMENSIONS = json.loads((HERE / 'dimensions.json').read_text())
# Wood and fabric retain the same reviewed metric scans throughout a family.
# The four swatches tint their albedo in linear space at export.
STYLES = {
    'modern': ('Linear', '#908780', '#566462', '#c8c0b5', '#4d5958'),
    'contemporary': ('Arc', '#aa8260', '#bc9a87', '#e5d7c9', '#827769'),
    'scandinavian': ('Birch', '#b8936a', '#ddd1bd', '#e7dfcc', '#bdb7a8'),
    'country': ('Farmhouse', '#a7835b', '#98a288', '#dfd6c1', '#829080'),
    'industrial': ('Foundry', '#80654f', '#858786', '#acada6', '#4e595b'),
    'traditional': ('Heritage', '#876649', '#9e7471', '#cdb69c', '#9b907f'),
}
CEILING = set('pendant downlight alarm linear_pendant flush_light'.split())
WALL = set('art mirror curtain roman_blind radiator towel_rail kitchen_wall wall_light shelf switch coat_hook wall_vanity wall_wc mirror_cabinet splashback upstand hand_towel coat extractor'.split())
SURFACE = set('cushion throw table_lamp books book_stack vase bowl fruit_bowl diffuser candle kettle soap keys utensils toaster coffee_machine bottles towel chopping_board television tap sink hob basin'.split())
GROUPS = {
    'bedroom': set('bed single_bed bedside wardrobe dresser'.split()),
    'kitchen': set('kitchen_base kitchen_tall kitchen_wall dishwasher oven hob fridge sink tap extractor kettle toaster coffee_machine chopping_board utensils integrated_fridge splashback upstand fruit_bowl stool'.split()),
    'bathroom': set('toilet basin vanity shower bath towel towel_rail semi_pedestal wall_wc wall_vanity mirror_cabinet cistern_box soap hand_towel'.split()),
    'utility': {'washer','dryer','shelf_unit'},
    'living': set('sofa armchair coffee_table side_table floor_lamp television stove bookcase alcove_unit'.split()),
    'dining': {'dining_table','dining_chair'},
}
def host(kind):
    if kind in CEILING: return 'ceiling'
    if kind in WALL: return 'wall'
    if kind in SURFACE: return 'surface'
    return 'floor'

def palette(style):
    m = dict(F.palette())
    _, wood, fabric, linen, colour = STYLES[style]
    for key, tint in dict(oak=wood, upholstery=fabric, linen=linen, rug=linen,
                          throw=fabric, kitchen=colour, accent=colour, seam=linen, ceramic=colour, book_clay=fabric).items():
        name = 'Studio.' + style + '.' + key
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = m[key].copy()
            mat.name = name
            shader = mat.node_tree.nodes.get('Principled BSDF')
            raw = F._rgba(tint)
            mat.diffuse_color = raw
            shader.inputs['Base Color'].default_value = raw
            if shader.inputs['Base Color'].is_linked:
                # Apply once to standard glTF baseColorFactor after export. Preserve the scan.
                mat['studio_tint'] = list(raw[:3]) if key != 'oak' else [min(1, v*q) for v,q in zip(m[key].get('albedo_gain',[1]*3), (a/b for a,b in zip(raw[:3],F._rgba('#b8936a')[:3])))]
        m[key] = mat
    m['stone'] = m['quartz']
    m['frame'] = m['black'] if style == 'industrial' else m['oak']
    m['bronze'] = m['metal'] if style in {'modern','industrial'} else m['bronze']
    return m

def make(kind, style, name, collection, size=None, materials=None, **options):
    """Construct at size, give the finished geometry one bottom-centred placement pivot."""
    if style not in STYLES or kind not in DIMENSIONS:
        raise ValueError(f'Unknown studio item {style}/{kind}')
    dims = tuple(float(n) for n in (size or DIMENSIONS[kind]))
    if len(dims) != 3 or not all(math.isfinite(n) and n > 0 for n in dims):
        raise ValueError('Expected positive finite W/D/H metres')
    options = dict(options, style=style)
    m = materials if materials is not None else palette(style)
    if kind == 'bedside':
        objects = F.build('dresser',name,*dims,collection=collection,materials=m,**options)
    elif kind == 'dishwasher':
        objects = F.build('kitchen_base',name,*dims,collection=collection,materials=m,appliance='dishwasher',**options)
    elif kind in F.DEFAULTS:
        objects = F.build(kind,name,*dims,collection=collection,materials=m,**options)
    else:
        objects = _custom(kind,name,dims,collection,m,options)
    root = objects[0]
    bpy.context.view_layer.update()
    points = [ob.matrix_world @ v.co for ob in objects if ob.type=='MESH' for v in ob.data.vertices]
    lo = [min(v[i] for v in points) for i in range(3)]
    hi = [max(v[i] for v in points) for i in range(3)]
    offset = Vector(((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,lo[2]))
    for child in root.children:
        child.location -= offset
    root['asset_kind'] = kind
    root['style'] = style
    root['host'] = host(kind)
    root['size_m'] = [hi[i]-lo[i] for i in range(3)]
    root['built_bounds_min_m'] = list(Vector(lo)-offset)
    root['built_bounds_max_m'] = list(Vector(hi)-offset)
    return objects

def discard(objects):
    meshes = [obj.data for obj in objects if obj.type == 'MESH']
    for obj in reversed(objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in meshes:
        if mesh.users == 0: bpy.data.meshes.remove(mesh)

def make_at_size(kind, style, name, collection, size, materials=None, tolerance=.001, **options):
    """Rebuild component dimensions until the finished envelope fits. No object scaling.

    Catalogued stock sizes are directly measurable. Unbuildable custom sizes
    (for example a shower narrower than its door) are rejected explicitly.
    """
    target=tuple(float(n) for n in size)
    if len(target)!=3 or any(not math.isfinite(n) or n<=0 for n in target):
        raise ValueError('Expected three positive finished dimensions')
    construction=list(target)
    last_error=None
    for attempt in range(9):
        objects=make(kind,style,name,collection,construction,materials,**options)
        measured=tuple(objects[0]['size_m'])
        error=[t-m for t,m in zip(target,measured)]
        if max(map(abs,error))<=tolerance:
            objects[0]['construction_dimensions_m']=construction
            objects[0]['requested_dimensions_m']=list(target)
            return objects
        discard(objects)
        if last_error is not None and max(abs(e-f) for e,f in zip(error,last_error))<.00005:
            break
        last_error=error
        construction=[max(.001,s*min(1.8,max(.4,t/m))) for s,t,m in zip(construction,target,measured)]
    raise ValueError(f'{kind} cannot fit {target} without changing its construction. Residual metres {error}')
