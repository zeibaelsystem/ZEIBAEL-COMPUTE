"""Fixed finite local server for Spider language-binding smoke tests."""
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

BASE="http://127.0.0.1:18776"
PAGES={"/":b'<!DOCTYPE html><html><head><title>ZEIBAEL fixture</title></head><body><h1>Local crawler fixture</h1><a href="/a">A</a><a href="/a#dup">Again</a><a href="/blocked">Denied</a></body></html>',
       "/a":b"<html><h1>ZEIBAEL binding</h1></html>"}
requests=[]
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        requests.append(self.path)
        if self.path=="/robots.txt":body,kind,status=b"User-agent: *\nDisallow: /blocked\n","text/plain",200
        elif self.path in PAGES:body,kind,status=PAGES[self.path],"text/html",200
        else:body,kind,status=b"denied","text/plain",403
        self.send_response(status)
        self.send_header("Content-Type",kind)
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*_):pass

def main():
    mode=sys.argv[1]
    with tempfile.TemporaryDirectory() as home,ThreadingHTTPServer(("127.0.0.1",18776),Handler) as server:
        th=threading.Thread(target=server.serve_forever,daemon=True);th.start()
        env={"PATH":"/usr/bin:/bin","HOME":home,"NO_PROXY":"*"}
        try:
            if mode=="python":
                command=[sys.executable,"-c",'''
import json
from spider_rs import Page
page=Page("http://127.0.0.1:18776/a")
page.fetch()
print(json.dumps({"html":page.get_html()}))
''']
                p=subprocess.run(command,env=env,capture_output=True,text=True,timeout=45)
                if p.returncode:raise RuntimeError("Binding failed: "+p.stderr[-3000:])
                data=json.loads(p.stdout.strip().splitlines()[-1])
                assert "ZEIBAEL binding" in data["html"],data
                assert requests==["/a"],requests
                print("ZEIBAEL_SPIDER_BINDING="+json.dumps({"mode":mode,"requests":requests,"scope":"single_page_only","status":"PASS"}),flush=True)
                return
            elif mode=="python_recursive":
                # Preserved stricter diagnostic; not admitted after reproducible
                # upstream recursive failure. Use verified Rust CLI for recursion.
                command=[sys.executable,"-c",'''
import json
from spider_rs import Website
w=Website("http://127.0.0.1:18776/")
w.with_respect_robots_txt(True).with_budget({"*":8}).with_depth(3).with_delay(100).with_subdomains(False).build()
w.crawl()
print(json.dumps(w.get_links()))
''']
            elif mode=="node":
                command=[sys.argv[2],os.path.join(os.path.dirname(__file__),"node.mjs")]
            else:raise ValueError("Unsupported fixture mode")
            p=subprocess.run(command,env=env,capture_output=True,text=True,timeout=45)
            if p.returncode:
                raise RuntimeError("Binding failed: "+p.stderr[-3000:])
            links=json.loads(p.stdout.strip().splitlines()[-1])
            assert BASE+"/a" in links,(links,requests)
            assert requests.count("/a")==1 and requests.count("/")==1,requests
            assert "/robots.txt" in requests and "/blocked" not in requests,requests
            print("ZEIBAEL_SPIDER_BINDING="+json.dumps({"mode":mode,"requests":requests,"links":len(links),"status":"PASS"}),flush=True)
        finally:
            server.shutdown();th.join()
if __name__=="__main__":main()
