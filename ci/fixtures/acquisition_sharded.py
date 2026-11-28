"""Finite synthetic development benchmark split across four CI jobs."""
import argparse
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from scripts.acquisition_core import Response
from scripts.acquisition_frontier import Frontier
from scripts.acquisition_shards import aggregate,plan_shards

HOSTS={f"host{i:02d}.example.org" for i in range(20)}
URLS=[f"https://host{i%20:02d}.example.org/record/{i}" for i in range(10000)]
PLAN=plan_shards(URLS,HOSTS,4)

def worker(number,path):
    started=time.perf_counter()
    s=PLAN[number]
    def fixture(url,limit):
        if url.endswith("/robots.txt"):return Response(404,"text/plain",b"")
        return Response(200,"text/plain",url.encode("ascii"))
    with tempfile.TemporaryDirectory() as d:
        db=Path(d)/"queue.db"
        while True:
            with Frontier(db,set(s["hosts"]),s["urls"],max_depth=0,max_urls=len(s["urls"])) as f:
                r=f.run_batch(fixture,batch_size=1000,workers=5,sleep=lambda _:None)
                if not r["pending"]:
                    assert r["complete"] and r["done"]==len(s["urls"]),r
                    records=[{"url":x["url"],"status":x["status"],"sha256":x["sha256"]} for x in f.iter_records()]
                    break
    obj={"id":number,"records":records,"seconds":round(time.perf_counter()-started,3),
         "runner_name":os.environ.get("RUNNER_NAME","unknown")}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj),encoding="utf-8")
    print("ZEIBAEL_SHARD="+json.dumps({k:v for k,v in obj.items() if k!="records"}|{"count":len(records)}))

def combine(directory):
    files=sorted(directory.glob("*.json"))
    outputs=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    result=aggregate(PLAN,outputs)
    for out in outputs:
        for rec in out["records"]:
            assert rec["sha256"]==hashlib.sha256(rec["url"].encode("ascii")).hexdigest()
    assert result=={"shards":4,"records":10000,"failed":0,"unique_content":10000,"complete":True},result
    result["worker_seconds"]=[x["seconds"] for x in outputs]
    result["runner_names"]=[x["runner_name"] for x in outputs]
    result["fixture_only"]=True
    print("ZEIBAEL_SHARDED_RESULT="+json.dumps(result),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=["worker","aggregate"])
    p.add_argument("path",type=Path)
    p.add_argument("--shard",type=int,choices=range(4))
    a=p.parse_args()
    if a.mode=="worker":worker(a.shard,a.path)
    else:combine(a.path)
