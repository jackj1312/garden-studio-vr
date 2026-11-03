"""Run the studio's existing gates sequentially against a private candidate.

Use the Python environment with numpy. The period of a client's build is
spent in the candidate directory. Promotion is a separate, gated operation.
"""
import argparse,json,os,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def check(site,round_name,only):
    manifest=json.loads((site/'versions.json').read_text())
    versions=[manifest['as_built_now'],manifest['default']]
    logs=ROOT/'renders/house-build/furnishing'/round_name
    logs.mkdir(exist_ok=True,parents=True)
    blender=os.environ.get('BLENDER','/Applications/Blender.app/Contents/MacOS/Blender')
    failed=[]
    def run(name,args,report=None):
        print('Checking',name,flush=True)
        with (logs/(name+'.log')).open('w') as f:
            result=subprocess.run(list(map(str,args)),cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
        ok=result.returncode==0
        if ok and report is not None:
            data=json.loads(report.read_text())
            ok=data.get('passed',False)
            print(name,data.get('counts',{}),flush=True)
        if not ok:failed.append(name)
    def geometry(name,version,layer=None):
        args=[blender,'--background','--factory-startup','-t','2','--python-exit-code','1','--python','tools/house/check_'+name+'.py','--','--site',site,'--version',version,'--spec',site/'spec/spec_v1.json']
        extra='-'+layer if layer=='off' else ''
        report=site/(version+'_'+name+extra+'.json')
        if name=='integrity':args+=['--asbuilt',layer,'--out',report]
        if name=='shell':
            source=os.environ.get('GARDEN_GATE_SOURCE')
            if source:args+=['--garden',source]
        run(version+'-'+name+extra,args,report)
    if only in ('all','model'):
        for version in versions:
            geometry('integrity',version,'on')
            geometry('integrity',version,'off')
            geometry('shell',version)
        run('finish',[sys.executable,'tools/house/check_finish.py',site,'--spec',site/'spec/spec_v1.json'])
        run('spec',[sys.executable,'tools/house/check_spec.py','--site',site,'--spec',site/'spec/spec_v1.json'])
    if only in ('all','compressed'):
        run('meshopt',[sys.executable,'tools/house/quest_meshopt.py',site])
        twins=sorted(site.glob('*_quest_mo.glb'))
        if not twins:failed.append('missing compressed twins')
        else:run('texture-repair',[sys.executable,'tools/house/fix_glb_textures.py',*twins])
        run('export',[sys.executable,'tools/house/check_house_export.py',site,'--finished'])
    if only in ('all','walk'):
        run('walk',['node','tools/review/furnish_views.cjs',round_name,site.name,'--walk'])
    if failed:raise SystemExit('Failed checks: '+', '.join(failed))
    print('Candidate checks passed:',only)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('site',type=Path)
    parser.add_argument('round');parser.add_argument('--only',choices=['all','model','compressed','walk'],default='all')
    parser.add_argument('--publish-to',type=Path,help='local client site; runs every gate before publishing the manifest')
    args=parser.parse_args()
    if args.publish_to and args.only!='all':parser.error('publication requires --only all')
    check(args.site.resolve(),args.round,args.only)
    if args.publish_to:
        subprocess.run([sys.executable,'tools/review/lessons.py','gate','--site',args.publish_to.name],cwd=ROOT,check=True)
        from publish_candidate import promote
        promote(args.site.resolve(),args.publish_to)
