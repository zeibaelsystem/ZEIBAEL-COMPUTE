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
    if engine=="nextflow":
        import hashlib, urllib.request, subprocess
        url="https://github.com/nextflow-io/nextflow/releases/download/v25.10.4/nextflow-25.10.4-dist"
        with urllib.request.urlopen(url,timeout=90) as response: data=response.read(50_000_001)
        check(len(data)<=50_000_000 and hashlib.sha256(data).hexdigest()=="60db869a7618783e3ee60183a2b0c6c50ffc67221eabec60800b904991786aaa","Nextflow digest mismatch")
        exe=work/"nextflow"; exe.write_bytes(data); exe.chmod(0o700)
        (work/"fixture.nf").write_text("nextflow.enable.dsl=2\nprocess PUBLIC_SUM {\n    publishDir 'results', mode: 'copy'\n    output:\n    path 'result.txt'\n    script:\n    '''\n    echo $((2+3)) > result.txt\n    '''\n}\nworkflow { PUBLIC_SUM() }\n")
        env={**os.environ,"NXF_OFFLINE":"true","NXF_DISABLE_CHECK_LATEST":"true","NXF_DISABLE_TELEMETRY":"true","NXF_ANSI_LOG":"false","NXF_HOME":str(work/"nxf-home")}
        r=subprocess.run([str(exe),"run",str(work/"fixture.nf"),"-ansi-log","false"],cwd=work,env=env,capture_output=True,text=True,timeout=120)
        check(r.returncode==0,r.stdout[-3000:]+r.stderr[-3000:])
        v=int((work/"results/result.txt").read_text().strip()); check(v==5,"result mismatch")
        return {"sum":v,"executor":"local","version":"25.10.4"}
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
