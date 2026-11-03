"""Apply reviewed, project-local trace amendments in memory. External survey files stay read-only."""


import json
import re
from pathlib import Path


def _close(a, b, tolerance=.0021):
    return abs(a - b) <= tolerance


def _outline(polygon, old_x, face_x, front, step):
    """Replace just the stepped front run; leave all surveyed stair-side vertices untouched."""
    for i, p in enumerate(polygon):
        if not (_close(p[0], old_x) and _close(p[1], front)):
            continue
        if (i + 2 >= len(polygon) or not _close(polygon[i + 1][0], old_x) or
                not _close(polygon[i + 1][1], step) or not _close(polygon[i + 2][0], face_x) or
                not _close(polygon[i + 2][1], step)):
            raise ValueError('Hall polygon does not match the signed survey amendment')
        return polygon[:i] + [[face_x, front]] + polygon[i + 3:]
    if not any(_close(p[0], face_x) and _close(p[1], front) for p in polygon):
        raise ValueError('Hall front run is missing')
    return polygon


def apply_hall_return(trace, interfaces):
    rule = interfaces.get('hall_return')
    if rule is None:
        # The amendment belongs to this surveyed property. Other studio clients
        # need neither its wall IDs nor copies of its drawings.
        registry = Path(__file__).parent / 'spec' / 'trace_amendments.json'
        rules = json.loads(registry.read_text()).get(trace.get('meta', {}).get('property'), {})
        rule = rules.get('hall_return')
    if not rule:
        return None
    for version in rule['trace_versions']:
        ground = trace['versions'][version]['storeys']['ground']
        walls = {w['id']: w for w in ground['walls']}
        wing, part = (walls[rule[key]] for key in ('exterior_wall', 'partition'))
        room = next(r for r in ground['rooms'] if r['name'] == rule['room_name'])
        left = max(walls[rule['opposite_wall']]['faces']['x'])
        face = min(part['faces']['x'])
        neighbour = max(wing['faces']['x'])
        if (not _close(face-left, rule['native_clear_m']) or
                not _close(neighbour, max(part['faces']['x'])) or
                not _close(face-max(walls[rule['stair_wall']]['faces']['x']), rule['stair_clear_m'])):
            raise ValueError('Measured hall/stair face chain does not match its signed source')
        wing_ops, part_ops = wing.get('openings', []), part['openings']
        matching = [o for o in wing_ops + part_ops if o['id'] == rule['door']]
        if len(matching) != 1:
            raise ValueError('Expected the one traced sitting-room doorway')
        door = matching[0]
        # Use the actual leading jamb as the common join. It is 2 mm ahead of
        # the traced y=.300 room datum: respect both, without narrowing the opening.
        join, end = door['span']
        if (not _close(join, rule['front_depth_m']) or not _close(end, rule['old_step_depth_m']) or
                not _close(end-join, door['w']['v']) or
                not all(_close(w['line'][0], w['line'][2]) and w['line'][3] > w['line'][1] for w in (wing, part))):
            raise ValueError('Door or carriers differ from the surveyed hall junction')
        if door in wing_ops:
            wing_ops.remove(door)
            part_ops.append(door)
        wing['line'][3] = part['line'][1] = join
        # Offsets are local to the host's start; the far kitchen/cloaks doorway
        # must remain at its original world jambs when the partition is extended.
        for opening in part_ops:
            opening['c']['v'] = round(sum(opening['span'])/2 - join, 7)
        door['identity_host'] = wing['id']
        door['retained_exterior_frame'] = True
        room['poly'] = _outline(room['poly'], min(wing['faces']['x']), face, rule['front_depth_m'], rule['old_step_depth_m'])

    return rule


def align_hall_schedule(trace, spec, rule):
    if not rule or not spec:
        return False
    changed = False
    for trace_version, issued in zip(rule['trace_versions'], rule['issued_versions']):
        version = next((v for v in spec['versions'].values() if v['elements'] == issued), None)
        if not version:
            continue
        room = next(r for r in version['rooms'] if r['id'] == rule['room_id'])
        ground = trace['versions'][trace_version]['storeys']['ground']
        poly = next(r['poly'] for r in ground['rooms'] if r['name'] == rule['room_name'])
        signed = [[x,-y] for x,y in poly]
        area = round(abs(sum(x*signed[(i+1)%len(signed)][1]-z*signed[(i+1)%len(signed)][0]
                             for i,(x,z) in enumerate(signed)))/2,2)
        if room['polygon']!=signed or room['area_m2']!=area:
            room.update(polygon=signed, area_m2=area)
            changed=True
    return changed


def hall_material_identity(name, spec_finish=None):
    """The signed finish survives Blender's per-version material instance suffix."""
    return 'spec_' + spec_finish if spec_finish else re.sub(r'\.\d+$', '', name)


def hall_export_materials(scheduled):
    """Material identities bound by the generator for this retained uPVC leaf."""
    hardware = scheduled['ironmongery'].lower()
    if 'white letter-plate-free leaf' not in hardware or not hardware.startswith(('white lever','black lever')):
        raise ValueError('Retained hall door finish has changed in the signed schedule')
    black = 'spec_METAL-BLACK'
    frame = 'anthracite_upvc' if '7016' in scheduled['frame_outside'] else 'upvc_white'
    return {'frame':frame, 'leaf':'upvc_white', 'hinges':black,
            'handle':'upvc_white' if hardware.startswith('white lever') else black}


def hall_width(polygon, depth):
    """Clear room interval at a drawing Y station (positive to the rear)."""
    intersections = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if min(a[1], b[1]) <= depth < max(a[1], b[1]):
            t = (depth - a[1])/(b[1] - a[1])
            intersections.append(a[0] + t*(b[0] - a[0]))
    if len(intersections) != 2:
        raise ValueError('Expected a single clear interval through the hall')
    return max(intersections) - min(intersections)
