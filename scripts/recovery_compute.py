"""Stage-three public synthetic software regression fixtures."""
import math, json, os, sys, subprocess, tempfile
from pathlib import Path

def check(condition,message):
    if not condition: raise RuntimeError(message)

def close(value,target,tol=1e-6):
    check(math.isfinite(float(value)) and abs(float(value)-target)<=tol,f"Expected {target}, got {value}")

def cmd(args,work):
    p=subprocess.run(args,cwd=work,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
    check(p.returncode==0,p.stdout[-3000:]); return p.stdout

def run(engine,work):
    if engine=="flink":
        from pyflink.table import EnvironmentSettings,TableEnvironment
        env=TableEnvironment.create(EnvironmentSettings.in_batch_mode())
        with env.execute_sql("SELECT SUM(x) FROM (VALUES (1),(2),(3)) AS t(x)").collect() as it: v=int(next(it)[0])
        close(v,6); return {"sum":v,"scope":"local JVM batch"} 
    if engine=="biosteam":
        import biosteam as b
        b.settings.set_thermo(["Water"])
        a=b.Stream("a",Water=2); c=b.Stream("c",Water=3)
        m=b.Mixer("m",ins=(a,c)); m.simulate(); v=float(m.outs[0].imol["Water"]); close(v,5)
        return {"water_kmol_h":v}
    if engine=="qsdsan":
        import qsdsan as q
        c=q.Component("H2O",search_ID="Water",particle_size="Soluble",degradability="Undegradable",organic=False)
        v=float(c.MW); close(v,18.015,.01)
        return {"water_molecular_weight":v,"scope":"sanitation component property only"}
    raise ValueError("Unapproved engine")

def main():
    if len(sys.argv)!=2: raise SystemExit("One reviewed engine ID required")
    os.environ.update(OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",NUMBA_NUM_THREADS="1",CUDA_VISIBLE_DEVICES="",DO_NOT_TRACK="1",HF_HUB_OFFLINE="1")
    with tempfile.TemporaryDirectory(prefix="stage3-") as d:
        values=run(sys.argv[1],Path(d))
    result={"engine":sys.argv[1],"status":"success","input":"public_synthetic","values":values}
    p=Path(os.environ["ZEIBAEL_OUTPUT_DIR"])/"files"; p.mkdir(parents=True,exist_ok=True)
    (p/"engine_result.json").write_text(json.dumps(result,allow_nan=False,indent=2)+"\n")
    print("ZEIBAEL_ENGINE_RESULT="+json.dumps(result,allow_nan=False))

if __name__=="__main__": main()
