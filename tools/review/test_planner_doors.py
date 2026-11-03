"""A mesh with a door's hinge transform need not be another door leaf (F251)."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/planner'))
from make_doors import glb_json, physical_leaves, latest_full_spec


class PlannerDoorTests(unittest.TestCase):
    def test_numbered_complete_spec_ignores_addenda(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            (folder/'spec_v12_addendum2_details.json').touch()
            (folder/'spec_v13.json').mkdir()
            with self.assertRaisesRegex(FileNotFoundError,'complete numbered spec'):
                latest_full_spec(folder)
            for name in ('spec_v1.json','spec_v2.json','spec_v10.json','spec_v10_draft.json'):
                (folder/name).touch()
            self.assertEqual(latest_full_spec(folder),'spec_v10.json')

    def test_legacy_names_and_single_physical_pivot(self):
        pivot = dict(element='one',hinge=[1,0,2],swing_deg=90)
        def node(name,**extra):
            return dict(name=name,extras=dict(pivot,**extra))
        nodes = [node('one_leaf'),node('one_leaf.001'),node('one_leaf_handle'),
                 node('one_leaf_leading',part='lead motif'),node('one_leaf_glass',part='leaf_glass'),
                 node('old-pair_leaf1',element='pair',hinge=[2,0,2]),node('old-pair_leaf0',element='pair')]
        leaves=physical_leaves(dict(nodes=nodes))
        self.assertEqual([r['node'] for r in leaves['one']],['one_leaf'])
        self.assertEqual([r['leaf_index'] for r in leaves['pair']],[0,1])
        with self.assertRaisesRegex(ValueError,'inconsistent movement'):
            physical_leaves(dict(nodes=nodes+[node('motion-error',part='leaf',hinge=[3,0,2])]))

    def test_real_gate_preserves_paired_and_bifold_leaves_and_planner_radius(self):
        site=ROOT/'assets/sites/house'
        if not (site/'versions.json').exists():
            self.skipTest('Private site GLBs not present')
        manifest=json.loads((site/'versions.json').read_text())
        spec=json.loads((site/'spec/spec_v1.json').read_text())
        by_id={v['id']:v for v in manifest['versions']}
        versions={}
        for key,sv in spec['versions'].items():
            vid=sv['elements']
            doc=glb_json(site/by_id[vid]['glb'])
            leaves=physical_leaves(doc)
            moving=[n.get('extras',{}) for n in doc['nodes'] if isinstance(n.get('extras',{}).get('hinge'),list)]
            self.assertTrue(any(e.get('part')=='handle' for e in moving))
            self.assertTrue(any(e.get('part')=='lead motif' for e in moving))
            wanted={(e['door_group'],e['leaf_index']) for e in moving if e.get('part')=='leaf'}
            self.assertEqual({(fid,r['leaf_index']) for fid,rows in leaves.items() for r in rows},wanted)
            self.assertEqual(len(leaves['F-G-wingL-sitting-room-door']),1)
            self.assertEqual(len(leaves['F-G-rearL-living-conservatory-double-doors']),2)
            if key=='after':
                self.assertEqual(len(leaves['F-G-extRear-bi-fold-doors']),4)
            versions[key]=dict(leaves=leaves)
        if not shutil.which('node'):
            self.skipTest('Node required for direct planner radius check')
        code="""
import {readFileSync} from 'node:fs';
import {buildHouse} from './src/planner/data.js';
const all=JSON.parse(readFileSync(0,'utf8')),site='assets/sites/house/';
const spec=JSON.parse(readFileSync(site+'spec/spec_v1.json','utf8')),result={};
for(const [key,sv] of Object.entries(spec.versions)){
  const elements=JSON.parse(readFileSync(site+sv.elements+'_elements.json','utf8'));
  const house=buildHouse(key,sv,elements,all[key],spec);
  const o=house.openings.find(o=>o.fixture==='F-G-wingL-sitting-room-door');
  result[key]=o.leaves.map(l=>l.radius);
}
process.stdout.write(JSON.stringify(result));
"""
        result=subprocess.run(['node','--input-type=module','-e',code],cwd=ROOT,check=True,
                              input=json.dumps(versions),capture_output=True,text=True)
        for radii in json.loads(result.stdout).values():
            self.assertEqual(len(radii),1)
            self.assertAlmostEqual(radii[0],.801,places=4)


if __name__=='__main__':
    unittest.main()
