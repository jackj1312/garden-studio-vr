#!/usr/bin/env python3
"""Publish the clean benchmark resources locally; never include completed site output."""
import argparse, hashlib, json, os, re, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
DOCS=REPO/'docs/benchmark'
DEST=Path.home()/'Desktop/Garden Studio Benchmark'
DEST_PROBE=Path.home()/'Desktop/Garden Studio New Model Benchmark'
LIVE=Path.home()/'Garden Studio VR'
# Non-cloud copies (9 Nov 2026, CORRECTIONS-LOG 608): ~/Desktop is iCloud and evicts files. Originals and lesson sources are
# read from REFS when present; the published master is mirrored to MIRROR and a run copies its benchmark-input from there.
REFS=Path.home()/'Projects/Garden Studio References'
MIRROR=REFS/'Garden Studio Benchmark'
def local(rel):
 """Path of a ~/Desktop-relative source, preferring the non-cloud copy (REFS, then REFS/lesson-sources)."""
 for base in (REFS,REFS/'lesson-sources'):
  q=base/rel
  if q.exists():return q
 return Path.home()/'Desktop'/rel
# The studio's own plan of 23 Battle Road ("truth") is unsigned and derived from an earlier run's house. It ships only when
# the owner has signed it AND asked for a production run from it; never to an independent test (Jack, 9 Nov 2026: "old
# houses sealed"). CORRECTIONS-LOG 606.
SHIP_TRUTH=False
DATALESS=0x40000000
CODE={'.py','.js','.mjs','.cjs','.css','.html','.sh','.command','.glsl','.vert','.frag'}
SKIPPED_DATALESS=[]   # dataless (iCloud placeholder) files skipped while collecting; counted and printed, never silent
PENDING=[]            # expected trees not present yet (other stages still landing)
DAMAGED={'4915.2A 1 to 50 and 1 to 100 at A1.pdf':'not a PDF (JSON text at its path); superseded by 4915.2B'}
EXPORT_HINT='Photos > select > File > Export > Export Unmodified Originals to ~/Projects/Garden Studio References/23 Battle Road/sources/exported/'
EXCLUDED_NOTES=['shared-tools/truth (the studio\'s own plan of 23 Battle Road) excluded: unsigned, derived from an earlier run; an independent test derives the house from the originals (SHIP_TRUTH)','tools/benchmark/site/out-* excluded: maintainer-only scenes built from that plan','shared-tools/reference-pass2 excluded: camera stations and frames of the earlier approved house; NORTH-STAR.md is the quality bar','BENCHMARKS.md excluded: names earlier output studies and results (sealed)','docs/pipeline illustrated HTML excluded: embeds earlier result screenshots/renders (sealed)','judges/*.md and master/front-garden-judges-v2.md excluded: verdicts about earlier output; method shipped as JUDGES-METHOD.md instead','tools/benchmark-score excluded: hidden scorer and answer key']
EXCLUDED={'src/garden/front-boundary.js','src/garden/street-frontage.js','src/garden/frontage-survey.js','src/garden/studio-concept.js'}

def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def ready(p):return p.is_file() and not p.is_symlink() and not (p.stat().st_flags & DATALESS)
def add_tree(files,base,prefix,predicate):
 if not base.exists():return
 for d,dirs,names in os.walk(base,followlinks=False):
  dirs[:]=sorted(x for x in dirs if x not in {'__pycache__','.pytest_cache','.git','node_modules','.DS_Store'} and not (Path(d)/x).is_symlink())
  for name in sorted(names):
   p=Path(d)/name
   if not (p.is_file() and not p.is_symlink()):continue
   if p.stat().st_flags & DATALESS:
    if predicate(p):SKIPPED_DATALESS.append(str(p))
    continue
   if predicate(p):files[str(Path(prefix)/p.relative_to(base))]=p
def add_file(files,key,p):
 p=Path(p)
 if p.is_file() and not p.is_symlink() and p.stat().st_flags & DATALESS and not any(ready(k/key) for k in (MIRROR,DEST)):SKIPPED_DATALESS.append(str(p));return False
 if ready(p):files[key]=p;return True
 for kept in (MIRROR/key,DEST/key):   # keep a durable earlier publication rather than dropping the file
  if ready(kept):files[key]=kept;return True
 return False
def add_pending(files,base,prefix,predicate,label):
 n=len(files);add_tree(files,base,prefix,predicate)
 if len(files)==n:PENDING.append(label)

def collect():
 files={p.name:p for p in DOCS.glob('*') if ready(p) and p.suffix in {'.md','.txt'}}
 files['BUILD-ENGINE-RULE.md']=REPO/'BUILD-ENGINE-RULE.md'
 for tag,base in [('claude-live',LIVE),('codex-active',REPO)]:
  for name in ['FIRST-PASS.md','CORRECTIONS-LOG.md','DETAIL-CHECKLIST.md']:
   p=base/name
   if not ready(p):raise RuntimeError('Required lesson source unavailable: '+str(p))
   files[f'lessons/{tag}/{name}']=p
 # Original mistakes remain explicitly allowed, not previous result packs.
 old=local('23 Battle Road/CODEX-MISTAKES.md')
 if ready(old):files['lessons/earlier-codex/CODEX-MISTAKES.md']=old
 for family in ['src','tools']:
  add_tree(files,REPO/family,f'shared-tools/{family}',lambda p:p.suffix in CODE and str(p.relative_to(REPO)) not in EXCLUDED and ('benchmark' not in p.parts or p.name in {'launch_server.py','register_launcher.py'}) and not any(x.startswith('benchmark-score') for x in p.parts))
 # Generic plan-data checks (PLAN-DATA-SCHEMA.md) and source preparation: house-agnostic shared tools.
 add_tree(files,REPO/'tools/benchmark/checks','shared-tools/checks',lambda p:p.suffix in {'.py','.md','.json'} or ('example-v2' in p.parts and p.suffix in {'.glb','.jpg','.png'}))   # the synthetic example ships whole (CORRECTIONS-LOG 609)
 for name in ['prepare_sources.py','extract_frames.swift']:
  if ready(REPO/'tools/benchmark'/name):files['shared-tools/prepare/'+name]=REPO/'tools/benchmark'/name
 # Prepared source register and small preview frames (regenerated by prepare_sources.py; never in git).
 add_tree(files,DOCS/'inputs/prepared','inputs/prepared',lambda p:p.suffix in {'.json','.jpg'})
 # The generic furniture kit is an authorised COMMON asset baseline, not a house.
 add_tree(files,REPO/'tools/library/kit','shared-tools/tools/library/kit',lambda p:p.name not in {'.DS_Store'} and p.suffix not in {'.blend','.blend1','.pyc'})
 add_tree(files,REPO/'assets/vendor','shared-tools/assets/vendor',lambda p:p.suffix in {'.js','.wasm','.json','.txt','.md'})
 for name in ['house.html','planner.html','index.html','splat.html','scan.html']:
  if ready(REPO/name):files['shared-tools/'+name]=REPO/name
 for name in ['plan/index.html','garden/index.html','p/index.html','w/index.html']:
  if ready(REPO/name):files['shared-tools/'+name]=REPO/name
 skills={
 'blender-mcp-workflow':Path.home()/'.codex/skills/blender-mcp-workflow/SKILL.md',
 'imagegen':Path.home()/'.codex/skills/.system/imagegen/SKILL.md',
 'architectural-presentation-stills':Path.home()/'.codex/memories/skills/architectural-presentation-stills/SKILL.md',
 'generated-image-continuity-review':Path.home()/'.codex/memories/skills/generated-image-continuity-review/SKILL.md',
 }
 for name,p in skills.items():
  if ready(p):files[f'skills/{name}/SKILL.md']=p

 # ---- Stage 4: ship every proven positive (BENCHMARK-REBUILD-PLAN.md section 3, Stage 4) ----
 not_ds=lambda p:p.name!='.DS_Store'
 lib='shared-tools/library/'
 add_tree(files,LIVE/'master/phototex',lib+'materials/phototex',not_ds)   # owner-photographed tiles, scales, units, decals, house PBR sets, spec/soft sheets
 add_tree(files,LIVE/'master/ambientcg',lib+'materials/cc0/ambientcg',not_ds)
 add_tree(files,LIVE/'assets/textures',lib+'materials/cc0/textures',not_ds)
 # Poly Haven props (CC0, ~700 MB) ship as an INDEX, not copies: the disk is tight and iCloud evicts; a run re-downloads what it needs.
 ph=LIVE/'master/polyhaven'
 if ph.exists():
  idx=DOCS/'inputs/prepared/polyhaven-index.json';idx.parent.mkdir(parents=True,exist_ok=True)
  entries=[]
  for d,dirs,names in os.walk(ph):
   dirs[:]=sorted(x for x in dirs if not x.startswith('.'))
   for n in sorted(names):
    q=Path(d)/n
    if n.startswith('.') or q.suffix=='.blend':continue
    rel=q.relative_to(ph);slug=rel.parts[0]
    entries.append({'path':str(rel),'asset':slug,'bytes':q.stat().st_size if q.exists() else None,'licence':'CC0 (Poly Haven)','url':'https://polyhaven.com/a/'+slug})
  idx.write_text(json.dumps({'note':'Poly Haven props used by the studio; CC0. Download from url (or the local copy at LIVE/master/polyhaven when working on the studio Mac).','entries':entries},indent=1)+'\n')
  files['shared-tools/library/materials/cc0/POLYHAVEN-INDEX.json']=idx
  for n in ['CREDITS.md','README.md','sources.json']:
   if ready(ph/n):files[lib+'materials/cc0/polyhaven/'+n]=ph/n
 add_tree(files,LIVE/'assets/hdri',lib+'hdri',not_ds)
 add_tree(files,LIVE/'assets/models/veg',lib+'models/veg',not_ds)
 for name in ['LIBRARY.md','SOURCES.md']:add_file(files,lib+'registers/'+name,local('garden-scans/asset-library')/name)
 # Generic material schedule only: verified to hold UV tile sizes and texture-set names, no rooms or geometry.
 sched=LIVE/'assets/sites/house/materials.json'
 if ready(sched):
  try:
   d=json.loads(sched.read_text())
   if set(d)<= {'contract','uv','materials'}:files[lib+'materials-schedule.json']=sched
   else:EXCLUDED_NOTES.append('materials.json has geometry-like top-level keys: '+','.join(d))
  except Exception as e:EXCLUDED_NOTES.append('materials.json unreadable: '+str(e))
 for name in ['LICENCES.md','JUDGES-METHOD.md']:add_file(files,lib+name,REPO/'tools/benchmark/library'/name)
 add_file(files,'shared-tools/judges/JUDGES-METHOD.md',REPO/'tools/benchmark/library/JUDGES-METHOD.md')
 for name in ['setup_env.sh','requirements.txt']:add_file(files,'shared-tools/'+name,REPO/'tools/benchmark/library'/name)
 # Methods (BENCHMARKS.md and the illustrated pipeline hold earlier results/renders: excluded, see EXCLUDED_NOTES).
 for name in ['WORKFLOW.md','PRESENTATION-WORKFLOW.md','AIRBNB-METHOD.md','SURVEY-METHOD.md','CAPTURE.md']:add_file(files,'shared-tools/methods/'+name,LIVE/name)
 # Stage 1-3 tools (other agents are writing them now): tolerant, printed as pending.
 for sub,label in [('readers','shared-tools/readers'),('gate','shared-tools/gate'),('truth','shared-tools/truth'),('tests','shared-tools/tests'),('site','shared-tools/site'),('reference','shared-tools/reference-pass2')]:
  if sub in ('truth','reference') and not SHIP_TRUTH:continue   # 'reference' = frames and camera stations of the earlier approved house
  add_pending(files,REPO/'tools/benchmark'/sub,label,lambda p:p.suffix in {'.py','.md','.json','.txt','.sh','.sha256'} and '__pycache__' not in p.parts and not any(x.startswith('out-') for x in p.parts),label)
 # Lessons: reconcile everything allowed (STUDIO-MEMORY, earlier Codex, benchmark-run mistakes). Snapshots above refresh BOTH live and Codex.
 add_file(files,'lessons/claude-live/STUDIO-MEMORY.md',LIVE/'STUDIO-MEMORY.md')
 b23=local('23 Battle Road/independent')
 add_file(files,'lessons/earlier-codex/viewer-MISTAKES.md',b23/'viewer/MISTAKES.md')
 add_file(files,'lessons/earlier-codex/site-mistakes.md',b23/'tools/site-mistakes.md')
 runs=local('Garden Studio Runs')
 add_file(files,'lessons/benchmark-runs/run02-MISTAKES.md',runs/'opus55-20261107-pass1-run02/MISTAKES.md')
 add_file(files,'lessons/benchmark-runs/run01-MISTAKES.md',runs/'opus55-20261107-pass1-run01/MISTAKES.md')
 add_tree(files,DOCS/'lessons-extra','lessons/extra',lambda p:p.suffix=='.md' and p.name!='README.md')
 # Original owner-supplied references, made durable instead of /tmp links.
 refs={
 '20813-wall.jpg':'/tmp/codex-remote-attachments/01a1a287-48e7-7523-92b0-0e924898f1eb/be76be8a-471f-4f1e-a810-6e7051bbe7ca/1-20813.jpg',
 '20814-sign.jpg':'/tmp/codex-remote-attachments/01a1a287-48e7-7523-92b0-0e924898f1eb/be76be8a-471f-4f1e-a810-6e7051bbe7ca/2-20814.jpg',
 '20817-street.jpg':'/tmp/codex-remote-attachments/01a1a287-48e7-7523-92b0-0e924898f1eb/bf88fb8c-a4c2-4cd5-b85f-db96e6770d18/1-20817.jpg'}
 for name,path in refs.items():
  p=Path(path)
  # Retain original durable copies on subsequent publications.
  if not ready(p):p=next((k/'inputs'/name for k in (MIRROR,DEST) if ready(k/'inputs'/name)),p)
  if ready(p):files['inputs/'+name]=p
 for name in ['ea-battle-road-dtm-1m.tif','ea-battle-road-dsm-1m.tif','ea-battle-road-dtm-url.txt','ea-battle-road-dsm-url.txt','ea-LIDAR_Composite_1m_DTM_2022_extents.json','ea-National_LIDAR_Programme_Index_Catalogue.json']:
  p=REPO/'renders/garden-tool/front-boundary/lidar-source'/name
  if not ready(p):p=next((k/'inputs/public-lidar'/name for k in (MIRROR,DEST) if ready(k/'inputs/public-lidar'/name)),p)   # renders/ did not move with the checkout; keep the published copy
  if ready(p):files['inputs/public-lidar/'+name]=p
 return files

def source_inventory():
 rows=[]
 home=Path.home();garden=local('garden-scans');src23=local('23 Battle Road/sources')
 bases=[(src23/'bds-originals',{'.pdf'},False,'original architect document'),(src23/'owner-2026-11-07-rear',{'.jpg','.jpeg','.png','.md'},False,'owner photo, back garden and rear of house, sent 7 Nov 2026 (with the owner\'s note)'),(src23/'owner-2026-11-08-loft-stair',{'.jpg','.jpeg','.png','.md'},False,'owner photo, loft conversion and loft stair, sent 8 Nov 2026 (with the owner\'s note)'),(garden,{'.jpg','.jpeg','.png','.mp4','.mov','.usdz'},False,'original owner capture'),(garden/'front-garden',{'.jpg','.jpeg','.mp4','.mov','.usdz'},False,'original garden capture'),(garden/'closeups',{'.jpg','.jpeg','.png'},True,'original closeup'),(garden/'house-scan',{'.usdz','.ply','.obj','.jpg','.jpeg','.json'},True,'original scan input'),(garden/'front-garden/frames4k',{'.jpg','.png'},False,'extracted original video frame')]
 for base,suffixes,recurse,kind in bases:
  if not base.exists():continue
  for p in sorted(base.rglob('*') if recurse else base.iterdir()):
   if p.is_symlink() or not p.is_file() or p.suffix.lower() not in suffixes:continue
   # Annotated/derived PNGs are not raw scene authority.
   if p.name=='planting_marked.png':continue
   if p.name in DAMAGED:
    rows.append({'path':str(p),'kind':kind,'bytes':p.stat().st_size,'availability':'damaged-superseded','status':'EXCLUDED from the allowlist: '+DAMAGED[p.name],'sha256':None});continue
   st=p.stat();off=bool(st.st_flags&DATALESS)
   row={'path':str(p),'kind':kind,'bytes':st.st_size,'availability':'icloud-placeholder' if off else 'local-bytes','sha256':None,'hash_note':'Hash when materialised in a run; do not read prior derived site data.'}
   if off:row['dataless']=True;row['export_instruction']=EXPORT_HINT
   rows.append(row)
 return {'policy':'Use only listed originals, packaged owner inputs and independently obtained public source data. No parent-directory discovery into old results.','files':rows}

def write_offline(inventory):
 off=[r for r in inventory['files'] if r.get('dataless')]
 lines=['# Offline originals (iCloud placeholders)','','Generated by tools/benchmark/publish.py; do not edit by hand. Listed files have metadata but no bytes on this Mac.','',
  'Export instruction: '+EXPORT_HINT+'.','A run must say which of these it could not read, and must not call older frames "today" in their place.','',
  f'{len(off)} offline of {len(inventory["files"])} original source records.','']
 lines+=[f'- {Path(r["path"]).name}  ({r["bytes"]} bytes, {r["kind"]})' for r in sorted(off,key=lambda r:r['path'])]
 dm=[r for r in inventory['files'] if r['availability']=='damaged-superseded']
 if dm:lines+=['','## Damaged / superseded (excluded)','']+[f'- {Path(r["path"]).name}: {r["status"]}' for r in dm]
 text='\n'.join(lines)+'\n';t=DOCS/'OFFLINE-ORIGINALS.md'
 if not t.exists() or t.read_text()!=text:t.write_text(text)

SEALED_KEY=[r'assets/sites/',r'(^|/)renders?/',r'screenshot',r'CODEX-COMPARISON',r'benchmark-score',r'answer-key',r'(^|/)[^/]*scores?[^/]*\.(json|md|csv|png)$',r'\.blend1?$',r'(^|/)(approved_2b|as_built_now|existing_2022|single_storey_option|setting_front)',r'(^|/)BENCHMARKS\.md$',r'(^|/)judges/\d{4}',r'front-garden-judges',r'(^|/)out-[^/]+/',r'(^|/)site/(before|after)[^/]*\.json$']+([] if SHIP_TRUTH else [r'^shared-tools/truth/'])
GLB_OK=('shared-tools/library/','shared-tools/tools/library/kit/','shared-tools/checks/example-v2/')
def sealed_violations(files):
 bad=[]
 for k,src in files.items():
  s=str(src)
  if k.startswith('shared-tools/reference-pass2/'):continue  # approved-walkthrough frames: sealed for Pass 1 by SOURCE-POLICY, opened for Pass 2 as the quality bar
  if any(re.search(x,k,re.I) for x in SEALED_KEY) or ('/assets/sites/' in s and k!='shared-tools/library/materials-schedule.json'):bad.append(k);continue
  if k.lower().endswith('.glb') and not k.startswith(GLB_OK):bad.append(k);continue
  if re.search(r'layout|geometry',Path(k).name,re.I) and k.endswith('.json') and not k.startswith(('shared-tools/library/','shared-tools/truth/','shared-tools/checks/','shared-tools/tests/')):bad.append(k)
 return bad

def run_tests():
 t=REPO/'tools/benchmark'
 dirs=[d for d in [t/'tests',t/'checks/tests',t/'readers',t/'gate',REPO/'tools/plan2d/tests'] if d.exists() and any(d.rglob('test_*.py'))]
 if not dirs:print('Tests: none found yet (pending)');return
 py=REPO/'.venv/bin/python';py=str(py) if py.exists() else sys.executable
 if subprocess.run([py,'-c','import pytest'],capture_output=True).returncode:print('Tests: pytest unavailable in',py,'- NOT RUN (run shared-tools/setup_env.sh); publishing without a green run is not verified');return
 for d in dirs:   # one process per folder: checks and readers both have a geom.py (CORRECTIONS-LOG 607)
  r=subprocess.run([py,'-m','pytest','-q','-p','no:cacheprovider',str(d)],cwd=str(REPO),capture_output=True,text=True)
  print('Tests',d.relative_to(REPO),':',r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-200:])
  if r.returncode:raise RuntimeError('Pack tests failing in '+str(d)+'; refusing to continue:\n'+r.stdout[-1500:])

PROBE_KEEP_PREFIX=('inputs/','shared-tools/checks/','shared-tools/gate/','shared-tools/library/','shared-tools/reference-pass2/','shared-tools/tools/library/kit/','shared-tools/assets/vendor/','skills/')
PROBE_KEEP_FILES={'REQUIREMENTS.md','PROJECT-BRIEF.md','AS-BUILT-NOTES.md','NORTH-STAR.md','PLAN-DATA-SCHEMA.md','ACCEPTANCE.md','BUILD-ENGINE-RULE.md','LIDAR-SOURCE.md','OFFLINE-ORIGINALS.md','SERVERS.md','NEW-MODEL-BENCHMARK-PROMPT.txt','shared-tools/setup_env.sh','shared-tools/requirements.txt'}
PROBE_DROP_PREFIX=('shared-tools/readers/','shared-tools/site/','shared-tools/truth/','shared-tools/tests/','shared-tools/methods/','shared-tools/judges/','shared-tools/src/','lessons/')
PROBE_ONLY_FILES={'README-NEW-MODEL.md','SOURCE-POLICY-NEW-MODEL.md','NEW-MODEL-BENCHMARK-PROMPT.txt'}
def probe_filter(files):
 """New-model probe: sources, owner facts, quality bar, checks, gate, library. No method code, lessons or truth (plan, 8 Nov 2026)."""
 out={}
 for k,v in files.items():
  if k.startswith(PROBE_DROP_PREFIX):continue
  if k in PROBE_KEEP_FILES or k.startswith(PROBE_KEEP_PREFIX):out[k]=v
 if ready(DOCS/'README-NEW-MODEL.md'):out['README.md']=DOCS/'README-NEW-MODEL.md'
 if ready(DOCS/'SOURCE-POLICY-NEW-MODEL.md'):out['SOURCE-POLICY.md']=DOCS/'SOURCE-POLICY-NEW-MODEL.md'
 return out

def verify(dest):
 record=json.loads((dest/'release.json').read_text());bad=[]
 for name,h in record['files'].items():
  p=dest/name
  if not ready(p) or digest(p)!=h:bad.append(name)
 if bad:raise RuntimeError('Publication changed or incomplete; reconcile before publishing: '+', '.join(bad[:12]))
 return record

def main():
 parser=argparse.ArgumentParser();g=parser.add_mutually_exclusive_group(required=True);g.add_argument('--check',action='store_true');g.add_argument('--publish',action='store_true');g.add_argument('--verify',action='store_true');parser.add_argument('--destination',type=Path,default=None);parser.add_argument('--probe',action='store_true',help='build the New Model Benchmark pack (sources, facts, quality bar, checks, gate, library; no method code, lessons or truth)');args=parser.parse_args();dest=args.destination or (DEST_PROBE if args.probe else DEST)
 if args.verify:
  r=verify(dest);print('Verified',r['release_id'],len(r['files']),'files');return
 inventory=source_inventory();write_offline(inventory);files=collect()
 if args.probe:files=probe_filter(files)
 else:files={k:v for k,v in files.items() if k not in PROBE_ONLY_FILES and not k.endswith('.draft.txt')}   # one front door: no drafts, no second prompt
 required=['README.md','NEW-MODEL-BENCHMARK-PROMPT.txt','REQUIREMENTS.md','PROJECT-BRIEF.md','AS-BUILT-NOTES.md','PLAN-DATA-SCHEMA.md','SOURCE-POLICY.md','shared-tools/checks/run_checks.py','shared-tools/gate/run_gate.py','shared-tools/library/LICENCES.md','shared-tools/setup_env.sh','OFFLINE-ORIGINALS.md'] if args.probe else ['PASTE-THIS-PROMPT.txt','REQUIREMENTS.md','PROJECT-BRIEF.md','SOURCE-POLICY.md','ACCEPTANCE.md','MCP-AND-SKILLS.md','MAINTAINING.md','COVERAGE-AUDIT.md','AGENTS.md','CLAUDE.md','PLAN-DATA-SCHEMA.md','shared-tools/checks/run_checks.py','shared-tools/setup_env.sh','shared-tools/requirements.txt','shared-tools/judges/JUDGES-METHOD.md','shared-tools/library/LICENCES.md','shared-tools/library/materials-schedule.json','shared-tools/library/materials/phototex/scales.json','shared-tools/library/models/veg/plants.json','shared-tools/methods/WORKFLOW.md','shared-tools/methods/PRESENTATION-WORKFLOW.md','lessons/claude-live/STUDIO-MEMORY.md','lessons/claude-live/FIRST-PASS.md','lessons/codex-active/FIRST-PASS.md','OFFLINE-ORIGINALS.md']
 assert all(x in files for x in required),[x for x in required if x not in files]
 bad_sealed=sealed_violations(files)
 if bad_sealed:raise RuntimeError('Sealed-pattern test FAILED; refusing to publish: '+', '.join(bad_sealed[:15]))
 # The hidden scorer and its answer key must never reach a contestant.
 assert not any('benchmark-score' in x or 'answer-key' in x or 'benchmark-score' in str(s) or 'answer-key' in str(s) for x,s in files.items())
 placeholders=sum(x['availability']=='icloud-placeholder' for x in inventory['files'])
 print('Ready:',len(files),'common files;',len(inventory['files']),'original source records;',placeholders,'iCloud placeholders')
 groups={}
 for k in files:
  parts=k.split('/');depth=5 if k.startswith('shared-tools/library/materials/') else 3;g='/'.join(parts[:min(depth,len(parts)-1)]) if len(parts)>1 else k
  groups[g]=groups.get(g,0)+1
 for g in sorted(groups):
  if g.startswith(('shared-tools/library','shared-tools/methods','shared-tools/judges','lessons','shared-tools/readers','shared-tools/gate','shared-tools/truth')):print('  ',g,groups[g],'files, %.1f MB'%(sum(files[k].stat().st_size for k in files if k==g or k.startswith(g+'/'))/1e6))
 sz=lambda pre:sum(files[k].stat().st_size for k in files if k.startswith(pre))
 print('Library size: %.0f MB'%(sz('shared-tools/library')/1e6))
 print('Dataless files skipped (hydrate first):',len(SKIPPED_DATALESS))
 for x in SKIPPED_DATALESS[:25]:print('   dataless:',x)
 for x in sorted(set(PENDING)):print('Pending (not landed yet):',x)
 for x in EXCLUDED_NOTES:print('Excluded:',x)
 print('Sealed-pattern test: PASS (',len(files),'paths checked )')
 for x in inventory['files']:
  if x['availability']=='damaged-superseded':print('Source damaged/superseded, excluded:',Path(x['path']).name)
 run_tests()
 if args.check:return
 marker=DOCS/('.published-release-probe.json' if args.probe else '.published-release.json' if dest==DEST else '.published-release-'+hashlib.sha256(str(dest).encode()).hexdigest()[:8]+'.json')
 if (dest/'release.json').exists():
  existing=verify(dest)
  if marker.exists() and json.loads(marker.read_text())['release_id']!=existing['release_id']:raise RuntimeError('Another agent published a newer Desktop release. Reconcile its docs first; preserve additions before updating the local publication marker.')
 dest.mkdir(parents=True,exist_ok=True)
 tools=[]
 for name,source in sorted(files.items()):
  target=dest/name;target.parent.mkdir(parents=True,exist_ok=True)
  if source.resolve()!=target.resolve() and (not target.exists() or digest(target)!=digest(source)):
   temp=target.with_name(target.name+'.incoming');shutil.copy2(source,temp);temp.replace(target)
  if name.startswith(('shared-tools/','skills/','lessons/')):tools.append({'file':name,'source':str(source),'sha256':digest(target)})
 # Exact owner-authored footprint only; no prior generated house or placements.
 base_source=REPO/'assets/sites/house-wip/layout/approved_2b.json'
 if ready(base_source):
  data=json.loads(base_source.read_text());garden=data.get('garden',{});items=garden.get('objects',garden.get('items',[])) if isinstance(garden,dict) else garden
  owner=[x for x in items if x.get('id')=='outbuilding-base-9a8d5ad5-6bbf-4bad-9a46-c2d96c151976']
  if not owner:raise RuntimeError('Owner footprint missing; do not publish a fabricated replacement')
  (dest/'inputs/owner-base.json').write_text(json.dumps({'authority':'Owner-drawn footprint only, explicitly preserved for later structure design. Not prior model geometry.','objects':owner},indent=2)+'\n')
 else:raise RuntimeError('Owner base source unavailable')
 for name,data in [('source-manifest.json',inventory),('tool-manifest.json',{'excluded_site_overlays':sorted(EXCLUDED),'excluded_notes':EXCLUDED_NOTES,'dataless_skipped':len(SKIPPED_DATALESS),'pending':sorted(set(PENDING)),'resources':tools})]: (dest/name).write_text(json.dumps(data,indent=2)+'\n')
 # Hash only this explicitly managed release; no run/results folder traversal.
 names=set(files)|{'source-manifest.json','tool-manifest.json','inputs/owner-base.json'}
 hashes={name:digest(dest/name) for name in sorted(names)}
 rid=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()[:16]
 record={'release_id':rid,'created_utc':datetime.now(timezone.utc).isoformat(),'protocol':'optional shared tools; independent house; comparison only after presented submission','files':hashes}
 temp=dest/'release.json.incoming';temp.write_text(json.dumps(record,indent=2)+'\n');temp.replace(dest/'release.json')
 marker.write_text(json.dumps({'release_id':rid,'destination':str(dest)},indent=2)+'\n')
 verify(dest);print('Published and verified:',dest,'release',rid)
if __name__=='__main__':
 try:main()
 except Exception as e:print('ERROR:',e,file=sys.stderr);sys.exit(1)
