"""Bounded in-job DAG for reviewed public software fixtures only."""
import hashlib, json, math, os, re, time, tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ID=re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
LIMIT=65536

def canonical(x):
    data=json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    if len(data)>LIMIT: raise ValueError("Result exceeds bounded JSON limit")
    return data

def digest(x): return hashlib.sha256(canonical(x)).hexdigest()

def plan(graph):
    if not isinstance(graph,dict) or not 1<=len(graph)<=20: raise ValueError("Expected 1–20 nodes")
    for n,d in graph.items():
        if not isinstance(n,str) or not ID.fullmatch(n) or not isinstance(d,list) or any(not isinstance(x,str) or x not in graph for x in d) or len(set(d))!=len(d):
            raise ValueError("Invalid node or dependency")
    done=set(); layers=[]
    while len(done)<len(graph):
        layer=sorted(n for n in graph if n not in done and set(graph[n])<=done)
        if not layer: raise ValueError("Dependency cycle")
        layers.append(layer); done.update(layer)
    return layers

def compare(a,b,tol):
    try: return all(math.isfinite(float(v)) for v in (a,b,tol)) and tol>=0 and abs(a-b)<=tol
    except (TypeError,ValueError,OverflowError): return False

def read_checkpoint(path,key):
    try:
        if path.is_symlink() or path.stat().st_size>LIMIT: return None
        x=json.loads(path.read_text())
        if x["key"]!=key or x["digest"]!=digest(x["result"]): return None
        if not isinstance(x["result"],dict): return None
        return x["result"]
    except (OSError,ValueError,TypeError,KeyError): return None

def write_checkpoint(path,key,result):
    content=canonical({"key":key,"digest":digest(result),"result":result})
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
        tmp=Path(f.name); f.write(content)
    try: os.replace(tmp,path)
    finally: tmp.unlink(missing_ok=True)

def execute(graph,functions,directory,version,max_workers=4):
    layers=plan(graph)
    if set(functions)!=set(graph) or not isinstance(version,str) or not version or len(version)>128: raise ValueError("Reviewed fixture contract mismatch")
    if type(max_workers)!=int or not 1<=max_workers<=4: raise ValueError("Worker bound")
    root=Path(directory)
    if root.is_symlink(): raise ValueError("Unsafe checkpoint root")
    root.mkdir(parents=True,exist_ok=True)
    try: cpus=len(os.sched_getaffinity(0))
    except (AttributeError,OSError): cpus=os.cpu_count() or 1
    workers=min(max_workers,max(1,cpus))
    status={}; results={}; cached=[]; timings={}
    for layer in layers:
        pending={}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for node in layer:
                if any(status[d] not in ("success","cached") for d in graph[node]):
                    status[node]="blocked"; continue
                deps={d:results[d] for d in graph[node]}
                key=digest({"version":version,"node":node,"dependencies":deps,"graph":graph})
                path=root/(node+".json")
                r=read_checkpoint(path,key)
                if r is not None: results[node]=r; status[node]="cached"; cached.append(node); timings[node]=0; continue
                start=time.monotonic(); pending[node]=(pool.submit(functions[node],json.loads(canonical(deps))),start,key,path)
            for node,(future,start,key,path) in pending.items():
                try:
                    result=future.result()
                    if not isinstance(result,dict): raise ValueError("Expected JSON object")
                    write_checkpoint(path,key,result)
                    results[node]=result; status[node]="success"
                except Exception:
                    status[node]="failed"
                timings[node]=round(time.monotonic()-start,6)
    return {"status":status,"results":results,"cached":cached,"timings_seconds":timings,"workers":workers,"version":version,"layers":layers}
