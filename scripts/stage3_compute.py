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
    if engine=="pyomo_dae":
        from pyomo.environ import ConcreteModel, TransformationFactory, value, Var, Constraint
        from pyomo.dae import ContinuousSet, DerivativeVar
        m=ConcreteModel(); m.t=ContinuousSet(bounds=(0,1)); m.x=Var(m.t); m.dx=DerivativeVar(m.x,wrt=m.t)
        m.eq=Constraint(m.t,rule=lambda m,t:m.dx[t]==2)
        TransformationFactory("dae.finite_difference").apply_to(m,nfe=4,wrt=m.t,scheme="BACKWARD")
        for t in m.t: m.x[t].set_value(2*t); m.dx[t].set_value(2)
        check(len(m.t)==5,"grid"); close(value(m.x[1]),2)
        return {"grid_points":len(m.t),"endpoint":value(m.x[1]),"scope":"discretization extension, not independent engine"}
    if engine=="openpnm":
        import openpnm as op
        n=op.network.Cubic(shape=[3,3,3],spacing=1e-5)
        check(n.Np==27 and n.Nt==54,"network topology")
        return {"pores":n.Np,"throats":n.Nt}
    if engine=="porespy":
        import porespy as ps
        import numpy as np
        a=np.zeros((10,10,10),dtype=bool); a[:4]=True
        v=float(ps.metrics.porosity(a)); close(v,.4)
        return {"porosity":v}
    if engine=="fipy":
        from fipy import Grid1D,CellVariable,DiffusionTerm
        mesh=Grid1D(nx=10,dx=.1); v=CellVariable(mesh=mesh); v.constrain(0,mesh.facesLeft); v.constrain(1,mesh.facesRight); DiffusionTerm().solve(var=v)
        close(float(v.value[0]),.05,1e-6); close(float(v.value[-1]),.95,1e-6)
        return {"first":float(v.value[0]),"last":float(v.value[-1])}
    if engine=="pyromat":
        import pyromat as pm
        v=float(pm.get("ig.air").cp(T=300)[0]); check(.95<v<1.1,"air heat capacity")
        return {"cp_kJ_kg_K":v}
    if engine=="phasepy":
        from phasepy import component, mixture
        w=component(name="water",Tc=647.1,Pc=220.55,Zc=.229,Ant=[11.6834,3816.44,-46.13])
        e=component(name="ethanol",Tc=514.,Pc=61.4,Zc=.241,Ant=[12.8521,3316.49,-46.02])
        m=mixture(w,e); check(m.nc==2,"binary mixture")
        return {"components":m.nc,"scope":"mixture construction only"}
    if engine=="pyelastica":
        from elastica import CosseratRod
        import numpy as np
        r=CosseratRod.straight_rod(10,np.zeros(3),np.array([0.,0.,1.]),np.array([1.,0.,0.]),1.,.01,1000.,youngs_modulus=1e6)
        close(float(r.rest_lengths.sum()),1); check(r.n_elems==10,"elements")
        return {"elements":r.n_elems,"rest_length_m":float(r.rest_lengths.sum())}
    if engine=="fmpy":
        from fmpy import read_model_description
        import zipfile
        xml='<fmiModelDescription fmiVersion="2.0" modelName="Public" guid="{demo}" numberOfEventIndicators="0"><CoSimulation modelIdentifier="demo"/><ModelVariables><ScalarVariable name="x" valueReference="1" causality="output" variability="continuous" initial="calculated"><Real/></ScalarVariable></ModelVariables><ModelStructure><Outputs><Unknown index="1"/></Outputs><InitialUnknowns><Unknown index="1"/></InitialUnknowns></ModelStructure></fmiModelDescription>'
        p=work/"public.fmu"
        with zipfile.ZipFile(p,"w") as z: z.writestr("modelDescription.xml",xml)
        v=read_model_description(p,validate=False)
        check(v.modelName=="Public" and v.modelVariables[0].name=="x","FMU metadata")
        return {"fmi_version":v.fmiVersion,"variable":v.modelVariables[0].name,"scope":"FMU metadata parser only"}
    if engine=="python_control":
        import control as c
        import numpy as np
        s=c.tf([1],[1,1]); t,y=c.step_response(s,T=np.linspace(0,5,101))
        close(float(y[-1]),1-np.exp(-5),1e-6)
        return {"step_t5":float(y[-1])}
    if engine=="gekko":
        from gekko import GEKKO
        m=GEKKO(remote=False); x=m.Var(value=0,lb=-10,ub=10); m.Minimize((x-3)**2); m.solve(disp=False)
        close(float(x.value[0]),3,1e-4)
        return {"local_optimum":float(x.value[0]),"remote":False}
    if engine=="pysindy":
        import numpy as np
        import pysindy as ps
        t=np.linspace(0,2,101); x=np.exp(-t).reshape(-1,1)
        m=ps.SINDy(optimizer=ps.STLSQ(threshold=.05),feature_library=ps.PolynomialLibrary(degree=1))
        m.fit(x,t=t,x_dot=-x); v=float(m.coefficients()[0,1]); close(v,-1,1e-3)
        return {"identified_coefficient":v}
    if engine=="pypsa":
        import pypsa
        n=pypsa.Network(); n.add("Bus","b"); n.add("Generator","g",bus="b",p_nom=10,marginal_cost=2); n.add("Load","l",bus="b",p_set=3)
        status,condition=n.optimize(solver_name="highs")
        check(status=="ok","optimization"); close(float(n.generators_t.p["g"].iloc[0]),3)
        return {"generation_MW":float(n.generators_t.p["g"].iloc[0]),"objective":float(n.objective)}
    if engine=="pyspice":
        from PySpice.Spice.Netlist import Circuit
        c=Circuit("Public resistor"); c.V("s","in",c.gnd,10); c.R(1,"in",c.gnd,1000)
        v=str(c); check("1000" in v and "10" in v,"netlist")
        return {"netlist":v,"scope":"netlist generation; ngspice solver separate"}
    if engine=="openturns":
        import openturns as ot
        v=ot.Normal(3,2); close(v.computeCDF(3),.5); close(v.getStandardDeviation()[0],2)
        return {"cdf_at_mean":v.computeCDF(3)}
    if engine=="gemseo":
        from gemseo import create_design_space
        d=create_design_space(); d.add_variable("x",lower_bound=0,upper_bound=2,value=1)
        close(float(d.get_current_value()[0]),1)
        return {"design_dimension":d.dimension,"scope":"design space construction only"}
    if engine=="nevergrad":
        import nevergrad as ng
        p=ng.p.Scalar(init=0.).set_bounds(-5,5); p.random_state.seed(7)
        o=ng.optimizers.OnePlusOne(parametrization=p,budget=100,num_workers=1)
        r=o.minimize(lambda x:(x-2)**2); close(float(r.value),2,.2)
        return {"optimum":float(r.value)}
    if engine=="pymoo":
        from pymoo.problems import get_problem
        from pymoo.algorithms.moo.nsga2 import NSGA2
        from pymoo.optimize import minimize
        p=get_problem("zdt1"); r=minimize(p,NSGA2(pop_size=30),("n_gen",10),seed=7,verbose=False)
        check(len(r.F)>2 and r.F.shape[1]==2,"Pareto result")
        return {"pareto_points":len(r.F),"objectives":2}
    if engine=="numba":
        import numba
        @numba.njit
        def square(x): return x*x
        close(square(7),49); check(len(square.signatures)>0,"not compiled")
        return {"result":49,"scope":"direct JIT route; previously transitive"}
    if engine=="mpmath":
        import mpmath as m
        m.mp.dps=60; v=m.sqrt(2); check(abs(v*v-2)<m.mpf("1e-55"),"precision")
        return {"digits":60,"sqrt2":str(v),"scope":"direct precision route; previously transitive"}
    if engine=="mpi4py":
        import subprocess
        v=subprocess.check_output(["mpiexec","-n","2",sys.executable,"-c","from mpi4py import MPI; c=MPI.COMM_WORLD; x=c.allreduce(c.rank+1); assert x==3; print(x)"],cwd=work,text=True,timeout=30)
        check(v.split().count("3")==2,"MPI reduction")
        return {"ranks":2,"sum":3}
    if engine=="backtesting_py":
        import pandas as pd
        from backtesting import Backtest, Strategy
        class S(Strategy):
            def init(self): pass
            def next(self):
                if len(self.data)==2: self.buy(size=1)
                if len(self.data)==4: self.position.close()
        v=[10.,11.,12.,13.,14.,15.]
        df=pd.DataFrame({k:v for k in ["Open","High","Low","Close"]},index=pd.date_range("2025-01-01",periods=6))
        r=Backtest(df,S,cash=100,commission=0).run()
        close(float(r["Equity Final [$]"]),102)
        return {"synthetic_equity":float(r["Equity Final [$]"])}
    if engine=="sktime":
        from sktime.forecasting.naive import NaiveForecaster
        import pandas as pd
        v=NaiveForecaster(strategy="last").fit(pd.Series([1.,2.,3.])).predict(fh=[1,2]).tolist()
        check(v==[3.,3.],"naive forecast")
        return {"forecast":v}
    if engine=="mlforecast":
        import pandas as pd
        from mlforecast import MLForecast
        from sklearn.linear_model import LinearRegression
        d=pd.DataFrame({"unique_id":["a"]*12,"ds":pd.date_range("2025-01-01",periods=12),"y":list(range(12))})
        m=MLForecast(models=[LinearRegression()],freq="D",lags=[1]); m.fit(d)
        v=m.predict(2)["LinearRegression"].tolist(); close(v[0],12,1e-5); close(v[1],13,1e-5)
        return {"forecast":v}
    if engine=="hmmlearn":
        from hmmlearn.hmm import GaussianHMM
        import numpy as np
        m=GaussianHMM(n_components=2,covariance_type="diag",init_params="",params="")
        m.startprob_=np.array([.5,.5]); m.transmat_=np.array([[.9,.1],[.1,.9]])
        m.means_=np.array([[0.],[10.]]); m.covars_=np.array([[1.],[1.]])
        v=m.predict([[0.],[0.],[10.],[10.]]).tolist(); check(v==[0,0,1,1],"state decode")
        return {"states":v}
    if engine=="ruptures":
        import numpy as np
        import ruptures as r
        x=np.r_[np.zeros(50),np.ones(50)*10]
        v=r.Binseg(model="l2",jump=1,min_size=2).fit(x).predict(n_bkps=1); check(v==[50,100],"change point")
        return {"breakpoints":v}
    if engine=="openvino":
        import openvino as ov
        import numpy as np
        p=ov.opset8.parameter([2],np.float32); m=ov.Model([ov.opset8.add(p,p)],[p])
        c=ov.Core().compile_model(m,"CPU"); v=c([np.array([2,3],np.float32)])[c.output(0)].tolist(); check(v==[4.,6.],"CPU inference")
        return {"output":v,"device":"CPU"}
    if engine=="pyod":
        from pyod.models.knn import KNN
        import numpy as np
        x=np.array([[0.],[.1],[.2],[.3],[.4],[10.]])
        m=KNN(n_neighbors=2,contamination=1/6).fit(x); check(int(m.labels_[-1])==1,"outlier")
        return {"outlier_index":int(np.argmax(m.decision_scores_))}
    if engine=="river":
        from river import stats
        m=stats.Mean()
        for x in [1,2,3]: m.update(x)
        close(m.get(),2)
        return {"stream_mean":m.get()}
    if engine=="tsfresh":
        from tsfresh.feature_extraction.feature_calculators import mean, absolute_sum_of_changes
        import numpy as np
        v=np.array([1.,2.,4.]); close(mean(v),7/3); close(absolute_sum_of_changes(v),3)
        return {"mean":float(mean(v)),"sum_changes":float(absolute_sum_of_changes(v))}
    if engine=="pymupdf":
        import pymupdf as p
        d=p.open(); a=d.new_page(); a.insert_text((72,72),"PUBLIC FIXTURE"); d.save(work/"sample.pdf"); d.close()
        with p.open(work/"sample.pdf") as d: v=d[0].get_text().strip()
        check(v=="PUBLIC FIXTURE","PDF text")
        return {"text":v}
    if engine=="pyav":
        import av
        import numpy as np
        p=work/"demo.mkv"
        with av.open(str(p),"w") as o:
            st=o.add_stream("ffv1",rate=10); st.width=32; st.height=32; st.pix_fmt="yuv420p"
            for i in range(3):
                for q in st.encode(av.VideoFrame.from_ndarray(np.full((32,32,3),i*50,np.uint8),format="rgb24")): o.mux(q)
            for q in st.encode(): o.mux(q)
        with av.open(str(p)) as o: frames=list(o.decode(video=0))
        check(len(frames)==3,"decode count")
        return {"frames":len(frames),"pts":[f.pts for f in frames]}
    if engine=="opentimelineio":
        import opentimelineio as o
        t=o.schema.Timeline("public"); tr=o.schema.Track(); t.tracks.append(tr)
        tr.append(o.schema.Clip(name="sample",source_range=o.opentime.TimeRange(o.opentime.RationalTime(0,24),o.opentime.RationalTime(48,24))))
        close(t.duration().to_seconds(),2)
        return {"duration_s":t.duration().to_seconds()}
    if engine=="datafusion":
        from datafusion import SessionContext
        import pyarrow as pa
        c=SessionContext(); c.register_record_batches("t",[[pa.record_batch({"x":[1,2,3]})]])
        v=c.sql("SELECT SUM(x) AS s FROM t").collect()[0].column(0)[0].as_py(); close(v,6)
        return {"sum":v}
    if engine=="ibis":
        import ibis
        c=ibis.duckdb.connect(); t=c.create_table("t",obj={"x":[1,2,3]}); v=int(t.x.sum().execute()); close(v,6)
        return {"sum":v}
    if engine=="zarr":
        import zarr, numpy as np
        a=zarr.open_array(str(work/"a.zarr"),mode="w",shape=(4,),chunks=(2,),dtype="i4"); a[:]=np.arange(4)
        v=zarr.open_array(str(work/"a.zarr"),mode="r")[:].tolist(); check(v==[0,1,2,3],"roundtrip")
        return {"values":v}
    if engine=="hdf5":
        import h5py
        with h5py.File(work/"a.h5","w") as f: f["x"]=[1,2,3]
        with h5py.File(work/"a.h5","r") as f: v=int(f["x"][:].sum())
        close(v,6); return {"sum":v}
    if engine=="snakemake":
        (work/"Snakefile").write_text("rule all:\n    input: 'result.txt'\nrule compute:\n    output: 'result.txt'\n    run:\n        open(output[0], 'w').write(str(2+3))\n")
        cmd(["snakemake","--cores","1","--snakefile","Snakefile"],work)
        check((work/"result.txt").read_text()=="5","workflow result")
        return {"output":5}
    if engine=="openmm":
        import openmm as m
        from openmm import unit
        sy=m.System(); sy.addParticle(1); f=m.CustomExternalForce("0.5*k*x*x"); f.addGlobalParameter("k",2); f.addParticle(0,[]); sy.addForce(f)
        i=m.VerletIntegrator(.001); c=m.Context(sy,i,m.Platform.getPlatformByName("Reference")); c.setPositions([[2,0,0]])
        v=c.getState(getEnergy=True).getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole); close(v,4)
        return {"energy_kJ_mol":v,"platform":"Reference"}
    if engine=="ase":
        from ase import Atoms
        a=Atoms("H2",positions=[[0,0,0],[0,0,.74]])
        v=a.get_distance(0,1); close(v,.74)
        return {"bond_angstrom":v}
    if engine=="pymatgen":
        from pymatgen.core import Structure,Lattice
        st=Structure(Lattice.cubic(4),["Na","Cl"],[[0,0,0],[.5,.5,.5]])
        close(st.volume,64); check(st.composition.reduced_formula=="NaCl","composition")
        return {"volume_A3":st.volume,"formula":st.composition.reduced_formula}
    if engine=="mdanalysis":
        import MDAnalysis as m
        import numpy as np
        u=m.Universe.empty(2,trajectory=True); u.atoms.positions=np.array([[0,0,0],[1,0,0]])
        v=float(np.linalg.norm(u.atoms.positions[1]-u.atoms.positions[0])); close(v,1)
        return {"distance_A":v}
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
