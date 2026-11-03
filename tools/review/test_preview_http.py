import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from preview_http import preview_handler


class Base:
    def __init__(self,path):
        self.path=path;self.headers={"Host":"192.168.1.118:8450"};self.output={};self.wfile=io.BytesIO()
    def send_response(self,status):self.status=status
    def send_error(self,status,message=None):self.status=status
    def send_header(self,k,v):self.output[k]=v
    def end_headers(self):pass
    def guess_type(self,path):return "text/html" if path.endswith(".html") else "application/octet-stream"
    def do_GET(self):self.status=299


class PreviewRoute(unittest.TestCase):
    def setUp(self):
        d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup)
        self.root=Path(d.name);self.key="1234567890abcdef1234";release=self.root/self.key;release.mkdir()
        (self.root/"current.json").write_text(json.dumps({"schema":1,"key":self.key,"versions":["after"]}))
        (release/"house.html").write_bytes(b"house")
        (release/"private.json").write_bytes(b"private")
        (release/"alias.js").symlink_to(release/"private.json")
        (release/"files.json").write_text(json.dumps({"schema":1,"files":{"house.html":"example","alias.js":"example"}}))
        self.handler=preview_handler(Base,self.root,"192.168.1.118")

    def test_current_and_pinned_files(self):
        x=self.handler("/preview/?version=after");x.do_GET()
        self.assertEqual(x.status,302);self.assertEqual(x.output["Cache-Control"],"no-store")
        self.assertEqual(x.output["Location"],f"/preview/{self.key}/house.html?site=house-preview&mode=customer&version=after")
        y=self.handler(x.output["Location"]);y.do_GET();self.assertEqual(y.wfile.getvalue(),b"house")
        y=self.handler(x.output["Location"]);y.do_HEAD();self.assertEqual(y.status,200);self.assertEqual(y.wfile.getvalue(),b"")
        z=self.handler("/garden/");z.do_GET();self.assertEqual(z.status,299)

    def test_not_a_general_file_server(self):
        for name in ["private.json","alias.js","files.json","../current.json","%2e%2e/current.json","%252e%252e/current.json"]:
            x=self.handler(f"/preview/{self.key}/"+name);x.do_GET();self.assertEqual(x.status,404,name)
        for field,value in [("Host","elsewhere.invalid"),("Origin","https://elsewhere.invalid")]:
            x=self.handler("/preview/");x.headers[field]=value;x.do_GET();self.assertEqual(x.status,404)
        x=self.handler("/preview/?version=missing");x.do_GET();self.assertEqual(x.status,404)
        x=self.handler("/preview/");x.do_POST();self.assertEqual(x.status,405)


if __name__=="__main__":unittest.main()
