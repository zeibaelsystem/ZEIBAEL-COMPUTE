"""Cross-solver public regression fixture; separate isolated Python environments."""
import hashlib,json,os,sys,subprocess,tempfile
from pathlib import Path
from workflow_dag import execute,compare

def run():
    with tempfile.TemporaryDirectory(prefix="dag-") as td:
        root=Path(td)
        envs={}
        for name,packages in {"symbolic":["sympy==1.14.0"],"numeric":["numpy==2.2.6","scipy==1.16.2"]}.items():
            path=root/name
            subprocess.run([sys.executable,"-m","venv",str(path)],check=True,timeout=60)
            python=path/"bin/python"
            subprocess.run([str(python),"-m","pip","install","--disable-pip-version-check","--no-input","--only-binary=:all:",*packages],check=True,timeout=240)
            envs[name]=python
        graph={"input":[],"symbolic":["input"],"numeric":["input"],"validation":["symbolic","numeric"]}
        def input_data(_): return {"c":2}
        def solver(name,source):
            def f(d):
                p=subprocess.run([str(envs[name]),"-c",source,str(d["input"]["c"])],capture_output=True,text=True,check=True,timeout=30)
                return json.loads(p.stdout)
            return f
        def validate(d):
            a=d["symbolic"]["root"]; b=d["numeric"]["root"]
            if not compare(a,b,1e-10): raise ValueError("Solver mismatch")
            return {"root":a,"absolute_error":abs(a-b)}
        funcs={"input":input_data,"symbolic":solver("symbolic","import sympy as s,sys,json; print(json.dumps({'root':float(s.sqrt(int(sys.argv[1]))),'version':s.__version__}))"),"numeric":solver("numeric","import scipy,sys,json; from scipy.optimize import brentq; c=int(sys.argv[1]); print(json.dumps({'root':brentq(lambda x:x*x-c,0,2),'version':scipy.__version__}))"),"validation":validate}
        version=hashlib.sha256(Path(__file__).read_bytes()+Path(__file__).with_name("workflow_dag.py").read_bytes()).hexdigest()
        first=execute(graph,funcs,root/"checkpoints",version,max_workers=2)
        if any(v!="success" for v in first["status"].values()): raise RuntimeError("DAG fixture failed")
        second=execute(graph,funcs,root/"checkpoints",version,max_workers=2)
        if len(second["cached"])!=4: raise RuntimeError("Resume failed")
        result={"scope":"single-runner, isolated venvs, synthetic root comparison","first":first,"resume":second,"result_digest":hashlib.sha256(json.dumps(first["results"],sort_keys=True).encode()).hexdigest()}
        p=Path(os.environ["ZEIBAEL_OUTPUT_DIR"])/"files"; p.mkdir(parents=True,exist_ok=True)
        (p/"workflow_result.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
        print("ZEIBAEL_DAG_RESULT="+json.dumps(result,allow_nan=False))

if __name__=="__main__": run()
