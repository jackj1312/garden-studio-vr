"""Lightweight checks of the actual staged generator atoms at the marked roof interfaces."""
import json
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/house'))
import hb_build as build
import hb_stage as stage
from hb_geom import apply_matrix, area, box, clip_convex, poly_halfplanes


def bounds(mesh):
    return [(min(axis),max(axis)) for axis in zip(*mesh[0])]


class RoofBearingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=Path(os.environ.get('STUDIO_SURVEY_DIR',Path.home()/'Desktop/garden-scans/front-garden/architect'))
        if not (source/'house_drawn.json').is_file():
            raise unittest.SkipTest('Local survey is absent')
        data=json.loads((source/'house_drawn.json').read_text())
        cls.spec=json.loads((source/'build_versions.json').read_text())
        cls.spec['roof_bearings']=json.loads((ROOT/'tools/house/spec/trace_amendments.json').read_text())[data['meta']['property']]['roof_bearings']
        versions={v['id']:v for v in build.resolve_spec(cls.spec['versions'],cls.spec['defs'])}
        issued=versions['approved_2b']
        cls.spec['staging']=cls.spec[issued['staging']]
        builder=build.StateBuilder(data,cls.spec)
        target=builder.build(issued)
        base=build.StateBuilder(data,cls.spec).build(versions[issued['base']])
        atoms=stage.diff(base,target,cls.spec,builder.lv)
        stage.stage_atoms(atoms,cls.spec,builder.lv,'proposal')
        stage.finish_walls(atoms,cls.spec,builder.lv,'proposal')
        headers=stage.lintel_atoms(atoms,cls.spec,builder.lv)
        stage.stage_atoms(headers,cls.spec,builder.lv,'proposal')
        atoms+=headers
        stage.seat_lintel_stages(atoms,cls.spec)
        atoms+=stage.stud_atoms(atoms,builder.lv)
        cls.atoms={a['id']:a for a in atoms}

    def test_full_opening_header_has_two_positive_early_bearings_and_masonry_above(self):
        stem='L-F-rearC-n1-bedroom-3-door-762'
        head,bed,jamb,upper=[self.atoms[stem+suffix] for suffix in ('','-bed','-jamb','-cripple')]
        H,L,R,U=[bounds(a['mesh']) for a in (head,bed,jamb,upper)]
        self.assertAlmostEqual(H[0][0],5.46);self.assertAlmostEqual(H[0][1],6.56)
        self.assertAlmostEqual(L[0][1]-L[0][0],.150);self.assertGreater(L[1][1]-L[1][0],.08)
        self.assertAlmostEqual(R[0][1]-R[0][0],.100);self.assertAlmostEqual(R[2][0],2.6755)
        self.assertAlmostEqual(H[2][0],4.6835);self.assertAlmostEqual(H[2][0],L[2][1]);self.assertAlmostEqual(H[2][0],R[2][1])
        self.assertAlmostEqual(H[2][1],U[2][0]);self.assertAlmostEqual(U[2][1],5.0805)
        self.assertTrue(all(a['meta']['stage_in']==11 for a in (head,bed,jamb,upper)))
        self.assertLess(jamb['meta']['seq'],head['meta']['seq']);self.assertLess(head['meta']['seq'],upper['meta']['seq'])
        wall=self.atoms['F-rearC~n1'];self.assertEqual(wall['wall'].layer_tops['core'],5.05)
        wall_parts=stage.parts_of(wall,{'spec':self.spec})
        above=[p for p in wall_parts if p['props']['group']=='wall_inner' and bounds(p['mesh'])[2][0]>=4.8234]
        self.assertTrue(above);self.assertAlmostEqual(min(bounds(p['mesh'])[2][0] for p in above),H[2][1],places=4)
        self.assertTrue(all(p['props']['seq']>head['meta']['seq'] for p in above))
        for p in wall_parts:
            z0,z1=bounds(p['mesh'])[2]
            self.assertFalse(z1>H[2][0]+.0001 and z0<H[2][1]-.0001)

    def test_flitch_and_joist_ends_have_physical_area_and_correct_sequence(self):
        beam=self.atoms['B-beam-3']
        self.assertAlmostEqual(beam['A'][2],5.08)
        for i in range(1,6):
            name=f'CJ-left-{i:02}'
            with self.subTest(name=name):
                joist,seat,fillet,fixings=[self.atoms[name+s] for s in ('','-seat','-rafter-fillet','-rafter-fixings')]
                rafter=self.atoms[fillet['side_bearing']]
                self.assertEqual(fixings['fastens_to'],(joist['id'],rafter['id']))
                other_rafter=next(a for a in self.atoms if a.startswith('RF-') and a!=rafter['id'])
                self.assertNotIn(other_rafter,fixings['fastens_to'])
                export=stage.parts_of(rafter,{'spec':self.spec})[0]
                vertices,faces=export['local']
                actual=(apply_matrix(export['matrix'],vertices),faces)
                self.assertGreater(stage.vertical_bearing_area(*fillet['mesh'],*actual),.005)
                self.assertGreater(stage.vertical_bearing_area(*fillet['mesh'],*joist['fitted_mesh']),.005)
                heights=bounds(seat['mesh'])[2];self.assertAlmostEqual(heights[1]-heights[0],.015)
                self.assertAlmostEqual(heights[0],beam['A'][2]);self.assertAlmostEqual(heights[1],bounds(joist['fitted_mesh'])[2][0])
                self.assertAlmostEqual(bounds(seat['mesh'])[0][1]-bounds(seat['mesh'])[0][0],.045)
                assembly=(beam,seat,rafter,fillet,joist,fixings)
                self.assertEqual([a['meta']['stage_in'] for a in assembly],[12]*6)
                seq=[a['meta']['seq'] for a in assembly];self.assertEqual(seq,sorted(seq))
        self.assertNotIn('fitted_mesh',self.atoms['CJ-left-00'])
        self.assertNotIn('fitted_mesh',self.atoms['CJ-left-06'])

    def test_board_has_five_precise_recesses_at_the_timber_seats(self):
        board=self.atoms['CL-ff-new']
        self.assertEqual(len(board['seat_cuts']),5)
        mesh=stage.parts_of(board,{'spec':self.spec})[0]['mesh']
        bottoms=[[(mesh[0][i][0],mesh[0][i][1]) for i in f] for f in mesh[1]
                 if all(abs(mesh[0][i][2]-board['z0'])<1e-6 for i in f)]
        removed=sum(abs(area(poly)) for poly in board['seat_cuts'])
        self.assertAlmostEqual(removed,5*.045*.045)
        self.assertAlmostEqual(sum(abs(area(p)) for p in bottoms),abs(area(board['poly']))-removed)
        for cut in board['seat_cuts']:
            for poly in bottoms:
                overlap=clip_convex(poly,poly_halfplanes(cut))
                self.assertLess(abs(area(overlap)) if overlap else 0,1e-8)

    def test_gutter_only_touches_the_named_current_fascia_on_real_side_faces(self):
        gutter=self.atoms['RG-house-ext.left-0.30-8.49'];fascia=self.atoms[gutter['side_bearing']]
        area=stage.vertical_bearing_area(*gutter['mesh'],*fascia['mesh'])
        self.assertAlmostEqual(area,.114185866,places=5)
        left,bottom=box(0,1,0,1,0,1),box(1,2,0,1,0,1)
        mirrored=(bottom[0],[f[::-1] for f in bottom[1]])
        self.assertAlmostEqual(stage.vertical_bearing_area(*left,*mirrored),1.)
        self.assertEqual(stage.vertical_bearing_area(*left,*box(1.01,2,0,1,0,1)),0)
        self.assertEqual(stage.vertical_bearing_area(*left,*box(1,2,1,2,0,1)),0)
        self.assertEqual(stage.vertical_bearing_area(*left,*left),0)


if __name__=='__main__':unittest.main()
