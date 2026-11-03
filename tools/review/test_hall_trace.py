"""Pure generator-level checks of the signed porch station, doorway and stair (F102/F244)."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools' / 'house'))
import hb_stage
from hb_build import StateBuilder, opening_element_id, resolve_spec
from hb_trace import align_hall_schedule, apply_hall_return, hall_width, hall_export_materials, hall_material_identity


class HallTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('STUDIO_SURVEY_DIR', Path.home() / 'Desktop/garden-scans/front-garden/architect'))
        if not (source / 'house_drawn.json').is_file():
            raise unittest.SkipTest('Local signed survey not available')
        cls.raw = json.loads((source / 'house_drawn.json').read_text())
        cls.data = copy.deepcopy(cls.raw)
        cls.rule = apply_hall_return(cls.data, {})
        cls.signed = json.loads((ROOT / 'assets/sites/house/spec/spec_v1.json').read_text())
        cls.spec = json.loads((source / 'build_versions.json').read_text())
        cls.spec['versions'] = resolve_spec(cls.spec['versions'], cls.spec['defs'])
        builder = StateBuilder(cls.data, cls.spec)
        cls.states = {v['id']: builder.build(v) for v in cls.spec['versions'] if v['id'] in cls.rule['issued_versions']}

    def test_native_clearance_and_unchanged_neighbours(self):
        measured = (173.270333 - 137.075333) * 50 / 1000
        self.assertAlmostEqual(measured, self.rule['native_clear_m'], places=5)
        for key in self.rule['trace_versions']:
            with self.subTest(key=key):
                old, new = [d['versions'][key]['storeys']['ground'] for d in (self.raw, self.data)]
                old_rooms, rooms = [{r['name']:r for r in storey['rooms']} for storey in (old,new)]
                before_poly = old_rooms.pop('hall')['poly']
                after_poly = rooms.pop('hall')['poly']
                self.assertEqual(old_rooms, rooms)
                self.assertEqual(before_poly[4:], after_poly[2:])
                for station in (.31, .70, 1.09):
                    self.assertAlmostEqual(hall_width(before_poly, station), 1.645)
                    self.assertAlmostEqual(hall_width(after_poly, station), measured, delta=.0003)
                self.assertAlmostEqual(hall_width(after_poly, 3.16), .855)
                self.assertAlmostEqual(hall_width(before_poly, 3.16), .855)
                unchanged = lambda storey: [w for w in storey['walls'] if w['id'] not in ('G-wingL','G-hallKit')]
                self.assertEqual(unchanged(old), unchanged(new))
                old_hosts, hosts = [{w['id']:w for w in storey['walls']} for storey in (old,new)]
                self.assertEqual(hosts['G-wingL']['line'][3], hosts['G-hallKit']['line'][1])
                self.assertEqual(hosts['G-wingL']['line'][3], .298)
                original = next(o for o in old_hosts['G-wingL']['openings'] if o['id']=='sitting room door')
                self.assertNotIn(original, hosts['G-wingL']['openings'])
                moved = next(o for o in hosts['G-hallKit']['openings'] if o['id']==original['id'])
                self.assertEqual({k:v for k,v in original.items() if k!='c'},
                                 {k:v for k,v in moved.items() if k not in ('c','identity_host','retained_exterior_frame')})
                for o in hosts['G-hallKit']['openings']:
                    centre = hosts['G-hallKit']['line'][1] + o['c']['v']
                    self.assertAlmostEqual(centre-o['w']['v']/2, o['span'][0], places=3)
                    self.assertAlmostEqual(centre+o['w']['v']/2, o['span'][1], places=3)

    def test_repeatable_schedule_and_isolated_site(self):
        repeat = copy.deepcopy(self.data)
        self.assertEqual(apply_hall_return(repeat, {}), self.rule)
        self.assertEqual(repeat, self.data)
        other = copy.deepcopy(self.raw)
        other['meta']['property'] = 'Another studio client'
        self.assertIsNone(apply_hall_return(other, {}))
        self.assertEqual(other['versions'], self.raw['versions'])
        stale = copy.deepcopy(self.signed)
        for source, issued in zip(self.rule['trace_versions'], self.rule['issued_versions']):
            poly=next(r['poly'] for r in self.raw['versions'][source]['storeys']['ground']['rooms'] if r['name']=='hall')
            room=next(r for v in stale['versions'].values() if v['elements']==issued for r in v['rooms'] if r['id']=='R-g-hall')
            room.update(polygon=[[x,-y] for x,y in poly],area_m2=4.87)
        self.assertTrue(align_hall_schedule(self.data, stale, self.rule))
        self.assertFalse(align_hall_schedule(self.data, stale, self.rule))
        for issued in self.rule['issued_versions']:
            r=next(room for v in stale['versions'].values() if v['elements']==issued for room in v['rooms'] if room['id']=='R-g-hall')
            built=next(r['poly'] for r in self.states[issued]['rooms'] if r['name']=='hall')
            self.assertEqual(r['polygon'], [[x,-y] for x,y in built])
            self.assertEqual(r['area_m2'],5.01)

    def test_retained_leaf_lever_and_pins_on_real_fitted_hinge(self):
        suffix = 'G-wingL-sitting-room-door'
        for version,state in self.states.items():
            with self.subTest(version=version):
                fixture, = [a for a in state['atoms'] if a['id']=='F-'+suffix]
                wall, op = fixture['wall'], fixture['op']
                self.assertEqual(wall.id, 'G-hallKit')
                self.assertEqual([opening_element_id(k,wall.id,op) for k in ('F','O','TH')], [p+'-'+suffix for p in ('F','O','TH')])
                self.assertEqual(op['u0'], 0.)
                self.assertAlmostEqual(op['u1'],.801)
                self.assertAlmostEqual(op['z1'],2.008)
                self.assertEqual(op['leaf'],.755)
                schedule=next(v['doors_windows'] for v in self.signed['versions'].values() if v['elements']==version)
                before=hb_stage.SPEC_DW
                try:
                    hb_stage.SPEC_DW={d['id']:d for d in schedule}
                    parts={p['props']['part']:p for p in hb_stage.fixture_parts(fixture)}
                finally:
                    hb_stage.SPEC_DW=before
                leaf,handle,hinges = (parts[p] for p in ('leaf','handle','hinges'))
                self.assertEqual(parts['frame']['mat'], 'upvc_white' if version=='as_built_now' else 'anthracite_upvc')
                self.assertEqual(leaf['mat'], 'upvc_white')
                self.assertEqual(handle['mat'], 'upvc_white' if version=='as_built_now' else 'ironmongery')
                for moving in (leaf,handle):
                    props=moving['props']
                    self.assertTrue(moving['leaf'] and props['door_leaf'])
                    self.assertEqual(props['door_group'],'F-'+suffix)
                    self.assertEqual(props['hinge'],[5.6125,0.,-1.035])
                    self.assertEqual(props['hinge_axis'],[0.,1.,0.])
                    self.assertEqual(props['swing_deg'],90.)
                zlevels=sorted({round(p[2],4) for p in hinges['mesh'][0]})
                self.assertEqual(sum(b-a>.12 for a,b in zip(zlevels,zlevels[1:]))+1,3)
                xs,ys,_=zip(*hinges['mesh'][0])
                self.assertAlmostEqual((min(xs)+max(xs))/2,leaf['props']['hinge'][0],places=5)
                self.assertAlmostEqual((min(ys)+max(ys))/2,-leaf['props']['hinge'][2],places=5)
                self.assertFalse(hinges.get('leaf'))
                xs,_,_ = zip(*handle['mesh'][0])
                lx,_,_=zip(*leaf['mesh'][0])
                self.assertLess(min(xs),min(lx))
                self.assertGreater(max(xs),max(lx))

class HallExportTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('CHECK_HALL_EXPORT'), 'run after both measured GLBs have been built')
    def test_actual_parts_use_the_four_reviewed_materials(self):
        import struct
        site=ROOT/'assets/sites/house'
        versions=json.loads((site/'spec/spec_v1.json').read_text())['versions']
        for sv in versions.values():
            with self.subTest(version=sv['elements']):
                with (site/(sv['elements']+'.glb')).open('rb') as stream:
                    stream.seek(12)
                    size,kind=struct.unpack('<II',stream.read(8))
                    self.assertEqual(kind,0x4E4F534A)
                    doc=json.loads(stream.read(size))
                fixture='F-G-wingL-sitting-room-door'
                scheduled=next(row for row in sv['doors_windows'] if row['id']==fixture)
                expected=hall_export_materials(scheduled)
                for role,material in expected.items():
                    parts=[n for n in doc['nodes'] if n.get('extras',{}).get('element')==fixture and
                           n['extras'].get('part')==role and 'mesh' in n]
                    self.assertTrue(parts,role)
                    materials=[doc['materials'][p['material']] for n in parts
                               for p in doc['meshes'][n['mesh']]['primitives']]
                    actual={hall_material_identity(m['name'],m.get('extras',{}).get('spec_finish')) for m in materials}
                    self.assertEqual(actual,{material},role)


if __name__ == '__main__':
    unittest.main()
