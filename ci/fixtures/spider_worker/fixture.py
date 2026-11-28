"""Fixed local Spider Worker scraper smoke; never a public proxy.

Run as non-root inside a loopback-only network namespace. The only allowed
fixture request uses a known local server; no caller-supplied destination.
"""
import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

BODY=b"<html><body><h1>ZEIBAEL-SPIDER-WORKER</h1><p>Local authorized fixture.</p></body></html>"
requests=[]
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        requests.append(self.path)
        body=BODY if self.path=="/fixture" else b"not found"
        self.send_response(200 if self.path=="/fixture" else 404)
        self.send_header("Content-Type","text/html")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*_):pass

def main(binary):
    with tempfile.TemporaryDirectory() as home, ThreadingHTTPServer(("127.0.0.1",18774),Handler) as srv:
        th=threading.Thread(target=srv.serve_forever,daemon=True)
        th.start()
        env={"PATH":"/usr/bin:/bin","HOME":home,"NO_PROXY":"*",
             "SPIDER_WORKER_SCRAPER_PORT":"18775","SPIDER_WORKER_MAX_CONCURRENCY":"2"}
        # The upstream worker needs its internal target for this isolated fixture.
        # It must not be run on a network with external or sensitive services.
        p=subprocess.Popen([os.path.abspath(binary)],env=env)
        try:
            deadline=time.monotonic()+20
            while True:
                if p.poll() is not None:raise RuntimeError("Worker exited")
                try:
                    with socket.create_connection(("127.0.0.1",18775),.2):break
                except OSError:
                    if time.monotonic()>deadline:raise
                    time.sleep(.1)
            conn=http.client.HTTPConnection("127.0.0.1",18775,timeout=15)
            try:
                conn.request("GET","/fixture",headers={"Host":"127.0.0.1:18774","Connection":"close"})
                response=conn.getresponse()
                body=response.read(8193)
                assert response.status==200 and body==BODY,(response.status,body)
                assert requests==["/fixture"],requests
            finally:conn.close()
            print("ZEIBAEL_SPIDER_WORKER="+json.dumps({"status":"PASS","requests":len(requests),
                "bytes":len(body),"max_connections_configured":2,
                "network":"loopback-only","cloud":False}),flush=True)
        finally:
            p.terminate()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
            srv.shutdown()
            th.join()
if __name__=="__main__":main(sys.argv[1])
