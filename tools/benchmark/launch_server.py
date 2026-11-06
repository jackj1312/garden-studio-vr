#!/usr/bin/env python3
"""Owner launcher: start/reuse only the configured run's server, then open its viewer."""
import argparse,json,os,socket,ssl,subprocess,sys,time,urllib.request
from pathlib import Path

def listeners(port):
 r=subprocess.run(['/usr/sbin/lsof','-nP','-tiTCP:'+str(port),'-sTCP:LISTEN'],capture_output=True,text=True)
 return [int(s) for s in r.stdout.split() if s.isdigit()]
def cwd_of(pid):
 r=subprocess.run(['/usr/sbin/lsof','-a','-p',str(pid),'-d','cwd','-Fn'],capture_output=True,text=True)
 return next((Path(s[1:]).resolve() for s in r.stdout.splitlines() if s.startswith('n')),None)
def owns(port,root):
 pids=listeners(port)
 if pids and any(cwd_of(pid)!=root for pid in pids):raise RuntimeError(f'Port {port} belongs to another run/application. Nothing stopped or replaced; choose a unique port.')
 return bool(pids)
def ready(url):
 try:
  # These local studio servers use the project's existing self-signed certificate.
  with urllib.request.urlopen(url,context=ssl._create_unverified_context(),timeout=2) as r:return r.status==200
 except Exception:return False

def main():
 p=argparse.ArgumentParser();p.add_argument('config',type=Path);p.add_argument('--check',action='store_true');p.add_argument('--no-open',action='store_true');a=p.parse_args();c=json.loads(a.config.read_text());root=Path(c['project_root']).expanduser().resolve();port=int(c['port']);url=c['url']
 if not root.is_dir():raise RuntimeError('Run folder missing: '+str(root))
 if not url.startswith(('https://127.0.0.1:'+str(port)+'/','http://127.0.0.1:'+str(port)+'/')):raise RuntimeError('Launcher must use its declared localhost port')
 running=owns(port,root)
 if not running:
  if a.check:raise RuntimeError('Server is stopped (launcher will start it on normal double-click)')
  # Reject occupied sockets even if lsof cannot identify the owner.
  with socket.socket() as s:
   if s.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Port occupied; cannot verify its owner')
  log=Path(c['log']).expanduser();log.parent.mkdir(parents=True,exist_ok=True)
  with log.open('ab') as out:
   child=subprocess.Popen(c['command'],cwd=root,stdin=subprocess.DEVNULL,stdout=out,stderr=out,start_new_session=True)
  for _ in range(50):
   if child.poll() is not None:raise RuntimeError('Server exited; see '+str(log))
   if ready(url):break
   time.sleep(.2)
  else:raise RuntimeError('Server is starting but not ready; see '+str(log))
  if not owns(port,root):raise RuntimeError('Started process could not be identified; inspect log')
 if not ready(url):raise RuntimeError('Correct server is present but viewer route is not ready: '+url)
 print(c['label']+'\n'+url+'\n'+('Reused existing server.' if running else 'Started this run server.'))
 if not a.check and not a.no_open:subprocess.run(['/usr/bin/open',url],check=True)
if __name__=='__main__':
 try:main()
 except Exception as e:print('Launcher:',e,file=sys.stderr);sys.exit(1)
