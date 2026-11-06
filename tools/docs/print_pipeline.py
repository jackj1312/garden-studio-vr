#!/usr/bin/env python3
"""Print a self-contained local guide; preserve the previous PDF on failure."""
import base64, mimetypes, re, subprocess, sys, tempfile
from pathlib import Path
from urllib.parse import unquote

source=Path(sys.argv[1]).resolve();output=Path(sys.argv[2]).resolve()
html=source.read_text();count=0

def embed(match):
 global count
 value=match.group(1)
 if value.startswith('data:'):return match.group(0)
 if '://' in value:raise RuntimeError('Remote image must be retained locally before printing: '+value)
 image=(source.parent/unquote(value)).resolve()
 if not image.is_file() or image.stat().st_flags & 0x40000000:raise RuntimeError('Missing or iCloud-only guide illustration: '+str(image))
 data=base64.b64encode(image.read_bytes()).decode();mime=mimetypes.guess_type(image.name)[0] or 'application/octet-stream';count+=1
 return 'src="data:'+mime+';base64,'+data+'"'
html=re.sub(r'src="([^"]+)"',embed,html)
# Use local system fonts, with no network dependency during document export.
html=re.sub(r'<link[^>]+href="https://fonts\.[^"]+"[^>]*>','',html)
with tempfile.TemporaryDirectory(prefix='studio-pipeline-') as folder:
 folder=Path(folder);page=folder/'pipeline.html';pdf=folder/'pipeline.pdf';page.write_text(html)
 command=['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless=new','--disable-gpu','--no-pdf-header-footer','--no-first-run','--virtual-time-budget=3000','--timeout=20000','--user-data-dir='+str(folder/'profile'),'--print-to-pdf='+str(pdf),page.as_uri()]
 try:r=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45)
 except subprocess.TimeoutExpired:raise RuntimeError('PDF printer timed out; previous PDF retained')
 if r.returncode!=0:raise RuntimeError('PDF printer failed; previous PDF retained: '+r.stderr.decode(errors='replace')[-400:])
 if not pdf.is_file() or not pdf.read_bytes().startswith(b'%PDF-') or b'%%EOF' not in pdf.read_bytes()[-100:]:raise RuntimeError('Incomplete PDF; previous PDF retained')
 # Atomic replacement in the destination directory; no half-written guide.
 temp=output.with_name(output.name+'.incoming');temp.write_bytes(pdf.read_bytes());temp.replace(output)
 print('Printed',count,'embedded illustrations:',output)
