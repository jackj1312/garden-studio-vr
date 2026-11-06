import importlib.util,json,os,signal,socket,subprocess,sys,tempfile
from pathlib import Path
module=Path(__file__).with_name('launch_server.py');s=importlib.util.spec_from_file_location('launcher',module);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
with tempfile.TemporaryDirectory(prefix='benchmark-launch-test-') as directory:
 root=Path(directory);(root/'index.html').write_text('<title>Isolated launcher fixture</title>')
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 config=root/'server.json';data={'label':'Test model — isolated fixture','project_root':str(root),'port':port,'url':f'http://127.0.0.1:{port}/','command':[sys.executable,'-m','http.server',str(port),'--bind','127.0.0.1'],'log':str(root/'server.log')};config.write_text(json.dumps(data));owned=[]
 try:
  cmd=[sys.executable,str(module),str(config),'--no-open']
  a=subprocess.run(cmd,capture_output=True,text=True,timeout=20);assert a.returncode==0,a.stderr
  owned=m.listeners(port);assert len(owned)==1
  b=subprocess.run(cmd,capture_output=True,text=True,timeout=10);assert b.returncode==0 and m.listeners(port)==owned,b.stderr
  other=root/'different-run';other.mkdir();data['project_root']=str(other);config.write_text(json.dumps(data))
  c=subprocess.run(cmd,capture_output=True,text=True,timeout=10);assert c.returncode!=0 and 'another run/application' in c.stderr,c.stderr
  assert m.listeners(port)==owned
  print('PASS: cold start, repeated click reuses same PID, foreign run refused, no existing server stopped')
 finally:
  for pid in owned:
   if m.cwd_of(pid)==root:os.kill(pid,signal.SIGTERM)
