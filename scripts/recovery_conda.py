"""Reviewed public conda-forge installation + functional regression only."""
import hashlib,json,os,sys,subprocess,tarfile,tempfile,urllib.request,shutil
from pathlib import Path
SPECS=json.loads("{\"sfepy\":{\"packages\":[\"python=3.12\",\"sfepy=2026.3\"],\"body\":\"from sfepy.discrete.fem import Mesh,FEDomain\\nimport numpy as np\\nm=Mesh.from_data(\\\"public\\\",np.array([[0.,0.],[1.,0.],[0.,1.]]),None,[np.array([[0,1,2]],dtype=np.int32)],[np.array([0],dtype=np.int32)],[\\\"2_3\\\"])\\ndomain=FEDomain(\\\"domain\\\",m); reg=domain.create_region(\\\"Omega\\\",\\\"all\\\")\\nassert m.n_nod==3 and m.n_el==1\\nreturn {\\\"nodes\\\":int(m.n_nod),\\\"elements\\\":int(m.n_el),\\\"scope\\\":\\\"FEM domain and region construction\\\"}\"},\"psi4\":{\"packages\":[\"python=3.12\",\"psi4=1.11\"],\"body\":\"import psi4\\npsi4.set_num_threads(1); psi4.set_memory(\\\"500 MB\\\"); psi4.core.be_quiet()\\nm=psi4.geometry(\\\"0 1\\\\nH 0 0 0\\\\nH 0 0 0.74\\\\nunits angstrom\\\")\\npsi4.set_options({\\\"reference\\\":\\\"rhf\\\",\\\"scf_type\\\":\\\"pk\\\",\\\"e_convergence\\\":1e-10,\\\"d_convergence\\\":1e-10})\\nv=float(psi4.energy(\\\"scf/sto-3g\\\",molecule=m)); assert abs(v+1.1167593)<1e-5, f\\\"energy={v:.12f}\\\"\\nreturn {\\\"energy_hartree\\\":v}\"},\"cp2k\":{\"packages\":[\"python=3.10\",\"cp2k=2024.1=openblas_nompi_py310h273ff43_1000\"],\"body\":\"import os,sys,subprocess,shutil,re\\nfrom pathlib import Path\\np=Path.cwd()\\nbase=next((x for x in Path(sys.prefix).rglob(\\\"BASIS_MOLOPT\\\") if x.is_file()),None)\\npotential=next((x for x in Path(sys.prefix).rglob(\\\"GTH_POTENTIALS\\\") if x.is_file()),None)\\nassert base is not None and potential is not None,\\\"CP2K data files missing\\\"\\nbinary=next((x for x in (shutil.which(\\\"cp2k\\\"),shutil.which(\\\"cp2k.psmp\\\"),shutil.which(\\\"cp2k.ssmp\\\"),shutil.which(\\\"cp2k.sopt\\\")) if x),None)\\nassert binary,\\\"CP2K binary missing\\\"\\ninp=p/\\\"h2.inp\\\"\\ninp.write_text(f\\\"\\\"\\\"&GLOBAL\\n PROJECT h2\\n RUN_TYPE ENERGY\\n PRINT_LEVEL LOW\\n&END GLOBAL\\n&FORCE_EVAL\\n METHOD Quickstep\\n &DFT\\n  BASIS_SET_FILE_NAME {base}\\n  POTENTIAL_FILE_NAME {potential}\\n  &SCF\\n   MAX_SCF 60\\n   EPS_SCF 1.0E-6\\n  &END SCF\\n  &XC\\n   &XC_FUNCTIONAL PBE\\n   &END XC_FUNCTIONAL\\n  &END XC\\n  &MGRID\\n   CUTOFF 100\\n   REL_CUTOFF 30\\n  &END MGRID\\n &END DFT\\n &SUBSYS\\n  &CELL\\n   ABC 8 8 8\\n  &END CELL\\n  &COORD\\n   H 4 4 3.63\\n   H 4 4 4.37\\n  &END COORD\\n  &KIND H\\n   BASIS_SET DZVP-MOLOPT-SR-GTH\\n   POTENTIAL GTH-PBE-q1\\n  &END KIND\\n &END SUBSYS\\n&END FORCE_EVAL\\n\\\"\\\"\\\")\\nr=subprocess.run([binary,\\\"-i\\\",str(inp)],capture_output=True,text=True,timeout=120,env={**os.environ,\\\"OMP_NUM_THREADS\\\":\\\"1\\\",\\\"OPENBLAS_NUM_THREADS\\\":\\\"1\\\"})\\nassert r.returncode==0,r.stdout[-3000:]+r.stderr[-3000:]\\nvals=re.findall(r\\\"ENERGY\\\\| Total FORCE_EVAL.*?([-+]\\\\d+\\\\.\\\\d+)\\\",r.stdout)\\nassert vals,\\\"No energy output\\\"\\nv=float(vals[-1]); assert -2<v<-.5,v\\nreturn {\\\"energy_hartree\\\":v,\\\"scope\\\":\\\"coarse public H2 DFT calculation, not production convergence\\\"}\"}}")

def main():
    if len(sys.argv)!=2 or sys.argv[1] not in SPECS: raise SystemExit("Unapproved conda fixture")
    engine=sys.argv[1]; spec=SPECS[engine]
    with tempfile.TemporaryDirectory(prefix="stage3-conda-") as td:
        root=Path(td)
        if shutil.disk_usage(root).free<6*1024**3: raise RuntimeError("Insufficient disk")
        url="https://conda.anaconda.org/conda-forge/linux-64/micromamba-2.10.0-0.tar.bz2"
        with urllib.request.urlopen(url,timeout=60) as response: data=response.read(10_000_001)
        if len(data)>10_000_000 or hashlib.sha256(data).hexdigest()!="9a97976244929bbae28fb1fae504e74a3e7e6d1932870e3a03321f01b7fbd07b": raise RuntimeError("micromamba digest mismatch")
        archive=root/"m.tar.bz2"; archive.write_bytes(data)
        with tarfile.open(archive) as t: t.extractall(root,members=[t.getmember("bin/micromamba")],filter="data")
        exe=root/"bin/micromamba"; prefix=root/"env"
        env=os.environ.copy()
        env.update(OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",CUDA_VISIBLE_DEVICES="",MAMBA_ROOT_PREFIX=str(root/"mamba"),DO_NOT_TRACK="1")
        base=[str(exe),"--no-rc","--root-prefix",str(root/"mamba")]
        subprocess.run([*base,"create","-y","-p",str(prefix),"--override-channels","-c","https://conda.anaconda.org/conda-forge","--strict-channel-priority",*spec["packages"]],cwd=root,env=env,timeout=900,check=True)
        fixture=root/"fixture.py"
        fixture.write_text("import json\ndef run():\n"+"\n".join("    "+l for l in spec["body"].splitlines())+"\nprint('RESULT='+json.dumps(run(),allow_nan=False))\n")
        p=subprocess.run([*base,"run","-p",str(prefix),"python",str(fixture)],cwd=root,env=env,timeout=180,check=False,capture_output=True,text=True)
        if p.returncode:
            raise RuntimeError("Public fixture subprocess failed:\n"+p.stdout[-4000:]+"\n"+p.stderr[-4000:])
        vals=json.loads(next(l[7:] for l in p.stdout.splitlines() if l.startswith("RESULT=")))
        result={"engine":engine,"input":"public_synthetic","status":"success","values":vals,"distribution":"conda-forge only","package_specs":spec["packages"]}
        out=Path(os.environ["ZEIBAEL_OUTPUT_DIR"])/"files"; out.mkdir(parents=True,exist_ok=True)
        (out/"engine_result.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
        print("ZEIBAEL_ENGINE_RESULT="+json.dumps(result,allow_nan=False))
if __name__=="__main__": main()
