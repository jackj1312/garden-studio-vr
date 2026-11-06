#!/usr/bin/env python3
"""Register a unique owner-facing launcher; never overwrite another run."""
import argparse,json,re,shlex,shutil
from pathlib import Path
from datetime import date

def main():
 p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--run',required=True);p.add_argument('--date',default=date.today().isoformat());p.add_argument('--root',type=Path,required=True);p.add_argument('--port',type=int,required=True);p.add_argument('--path',default='/house.html');p.add_argument('--protocol',choices=['https','http'],default='https');p.add_argument('--command-json',required=True);p.add_argument('--provenance',required=True);p.add_argument('--legacy',action='store_true');a=p.parse_args()
 if not 1024<=a.port<=65535:raise ValueError('Choose an unprivileged unique port')
 root=a.root.expanduser().resolve();command=json.loads(a.command_json)
 if not root.is_dir() or not isinstance(command,list) or not command or not all(isinstance(x,str) for x in command):raise ValueError('Valid existing root and argument-array command required')
 target=Path.home()/'Desktop/Garden Studio Launchers';support=target/'.support';configs=support/'runs';configs.mkdir(parents=True,exist_ok=True)
 label=f'{a.model} — {a.date} — {a.run}';slug=re.sub(r'[^A-Za-z0-9_.-]+','-',label).strip('-')
 config=configs/(slug+'.json');launcher=target/(label+'.command')
 if config.exists() or launcher.exists():raise ValueError('Run already registered; use a distinct run number/date')
 for f in configs.glob('*.json'):
  c=json.loads(f.read_text())
  if c['port']==a.port:raise ValueError('Port is already assigned to '+c['label'])
 helper=support/'launch_server.py';shutil.copy2(Path(__file__).with_name('launch_server.py'),helper)
 c={'label':label,'model':a.model,'date':a.date,'run':a.run,'project_root':str(root),'port':a.port,'url':f'{a.protocol}://127.0.0.1:{a.port}'+a.path,'command':command,'log':str(support/'logs'/(slug+'.log')),'provenance':a.provenance,'legacy_live_project':a.legacy}
 config.write_text(json.dumps(c,indent=2)+'\n')
 # No interpolation into executable shell code except POSIX shell-quoted paths.
 launcher.write_text('#!/bin/bash\n# Opens only this named run. No server is stopped or replaced.\n/usr/bin/python3 '+shlex.quote(str(helper))+' '+shlex.quote(str(config))+'\nstatus=$?\nif [ "$status" -ne 0 ]; then read -r -p "Press Return to close..."; fi\nexit "$status"\n');launcher.chmod(0o755)
 print(launcher)
if __name__=='__main__':main()
