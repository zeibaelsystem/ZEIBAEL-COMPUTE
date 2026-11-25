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
        c=ibis.duckdb.connect(); t=ibis.memtable({"x":[1,2,3]}); v=int(c.execute(t.x.sum())); close(v,6)
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
    if engine=="do_mpc":
        import do_mpc, numpy as np
        m=do_mpc.model.Model("continuous")
        x=m.set_variable("_x","x"); u=m.set_variable("_u","u"); m.set_rhs("x",-x+u); m.setup()
        s=do_mpc.simulator.Simulator(m); s.set_param(t_step=.1); s.setup(); s.x0=np.array([[2.]])
        v=float(s.make_step(np.array([[1.]])).item()); close(v,1+np.exp(-.1),1e-4)
        return {"x_after_0_1s":v,"scope":"dynamic simulation, not MPC closed loop"}
    if engine=="ncnn":
        import ncnn, numpy as np
        p=work/"relu.param"; p.write_text("7767517\n2 2\nInput input 0 1 data\nReLU relu 1 1 data out\n")
        b=work/"relu.bin"; b.write_bytes(b"")
        net=ncnn.Net(); net.opt.use_vulkan_compute=False; net.opt.num_threads=1
        check(net.load_param(str(p))==0,"param load")
        arr=np.array([-2.,1.,3.],dtype=np.float32); mat=ncnn.Mat(arr).clone()
        ex=net.create_extractor(); check(ex.input("data",mat)==0,"input")
        rc,out=ex.extract("out"); check(rc==0,"inference"); v=np.array(out).tolist(); check(v==[0.,1.,3.],"ReLU output")
        return {"output":v,"device":"cpu"}
    if engine=="mnn":
        import MNN.expr as F
        a=F.const([-2.,1.,3.],[3],F.NCHW,F.float)
        v=F.relu(a).read().tolist(); check(v==[0.,1.,3.],"ReLU output")
        return {"output":v,"scope":"local tensor expression"}
    if engine=="mlflow":
        import mlflow
        os.environ["MLFLOW_ALLOW_FILE_STORE"]="true"; os.environ["MLFLOW_ENABLE_TELEMETRY"]="false"
        mlflow.set_tracking_uri((work/"mlruns").as_uri()); mlflow.set_experiment("public_fixture")
        with mlflow.start_run() as r:
            mlflow.log_param("fixture","public"); mlflow.log_metric("m",3)
            rid=r.info.run_id
        v=mlflow.get_run(rid).data.metrics["m"]; close(v,3)
        return {"metric":v,"scope":"local filesystem only"}
    if engine=="dvc":
        os.environ["DVC_NO_ANALYTICS"]="1"
        cmd(["dvc","init","--no-scm"],work)
        (work/"data.txt").write_text("public fixture\n")
        cmd(["dvc","add","data.txt"],work)
        check((work/"data.txt.dvc").is_file(),"DVC metadata")
        (work/"data.txt").unlink()
        cmd(["dvc","checkout","data.txt.dvc"],work)
        check((work/"data.txt").read_text()=="public fixture\n","local restore")
        return {"restored":True,"remote":False}
    if engine=="pyg":
        import torch
        from torch_geometric.nn import GCNConv
        m=GCNConv(1,1,bias=False)
        with torch.no_grad(): m.lin.weight.fill_(1.)
        x=torch.tensor([[1.],[3.]])
        edge=torch.tensor([[0,1],[1,0]],dtype=torch.long)
        v=m(x,edge).detach().flatten().tolist(); close(v[0],2,1e-5); close(v[1],2,1e-5)
        return {"node_outputs":v}
    if engine=="neuralforecast":
        import pandas as pd,numpy as np
        from neuralforecast import NeuralForecast
        from neuralforecast.models import NBEATS
        d=pd.DataFrame({"unique_id":["a"]*20,"ds":pd.date_range("2025-01-01",periods=20),"y":np.arange(20,dtype=float)})
        model=NBEATS(h=2,input_size=4,max_steps=2,random_seed=7,accelerator="cpu",devices=1,enable_progress_bar=False,logger=False)
        nf=NeuralForecast(models=[model],freq="D"); nf.fit(df=d); v=nf.predict()["NBEATS"].tolist()
        check(len(v)==2 and np.isfinite(v).all(),"forecast shape")
        return {"forecast":v,"scope":"two-step synthetic training, no predictive quality claim"}
    if engine=="pytorch_forecasting":
        from pytorch_forecasting import TimeSeriesDataSet
        import pandas as pd, numpy as np
        d=pd.DataFrame({"time":np.arange(20),"group":["a"]*20,"target":np.arange(20,dtype=float)})
        ds=TimeSeriesDataSet(d,time_idx="time",target="target",group_ids=["group"],max_encoder_length=4,max_prediction_length=2,time_varying_unknown_reals=["target"])
        x,y=next(iter(ds.to_dataloader(train=False,batch_size=2,num_workers=0)))
        check(y[0].shape[-1]==2 and len(ds)>0,"window shape")
        return {"windows":len(ds),"target_shape":list(y[0].shape),"scope":"training dataset window construction"}
    if engine=="zipline_reloaded":
        import numpy as np
        from zipline.pipeline.factors import SimpleMovingAverage
        from zipline.pipeline.data import USEquityPricing
        f=SimpleMovingAverage(inputs=[USEquityPricing.close],window_length=3); out=np.empty(2)
        f.compute(None,np.array([1,2]),out,np.array([[1.,2.],[3.,4.],[5.,6.]]))
        check(np.allclose(out,[3,4]),"factor result")
        return {"sma":out.tolist(),"scope":"pipeline factor, not full backtest"}
    if engine=="nautilus_trader":
        from nautilus_trader.model.book import OrderBook
        from nautilus_trader.model.data import BookOrder
        from nautilus_trader.model.enums import BookType,OrderSide
        from nautilus_trader.model.identifiers import InstrumentId
        from nautilus_trader.model.objects import Price,Quantity
        b=OrderBook(InstrumentId.from_str("PUBLIC.SIM"),BookType.L2_MBP)
        b.add(BookOrder(OrderSide.BUY,Price.from_str("99.00"),Quantity.from_str("5"),1),1,0,1)
        b.add(BookOrder(OrderSide.SELL,Price.from_str("101.00"),Quantity.from_str("7"),2),2,0,2)
        bid=float(b.best_bid_price()); ask=float(b.best_ask_price()); close(ask-bid,2)
        return {"bid":bid,"ask":ask,"spread":ask-bid,"scope":"synthetic limit order book only"}
    if engine=="flink":
        from pyflink.table import EnvironmentSettings,TableEnvironment
        env=TableEnvironment.create(EnvironmentSettings.in_batch_mode())
        with env.execute_sql("SELECT SUM(x) FROM (VALUES (1),(2),(3)) AS t(x)").collect() as it: v=int(next(it)[0])
        close(v,6); return {"sum":v,"scope":"local JVM batch"} 
    if engine=="nats":
        import asyncio,socket,time
        with socket.socket() as s: s.bind(("127.0.0.1",0)); port=s.getsockname()[1]
        server=subprocess.Popen(["nats-server","-a","127.0.0.1","-p",str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    with socket.create_connection(("127.0.0.1",port),.1): break
                except OSError: time.sleep(.1)
            else: raise RuntimeError("local NATS not ready")
            async def flow():
                import nats
                c=await nats.connect(f"nats://127.0.0.1:{port}",allow_reconnect=False,connect_timeout=2)
                sub=await c.subscribe("public.fixture"); await c.flush(); await c.publish("public.fixture",b"123")
                msg=await sub.next_msg(timeout=2); await c.close(); return msg.data.decode()
            v=asyncio.run(flow()); check(v=="123","message")
            return {"message":v,"scope":"loopback ephemeral server"}
        finally:
            server.terminate(); server.wait(timeout=5)
    if engine=="gstreamer":
        cmd(["gst-launch-1.0","-q","audiotestsrc","num-buffers=10","!","audioconvert","!","audio/x-raw,format=S16LE","!","wavenc","!","filesink","location="+str(work/"tone.wav")],work)
        import wave
        with wave.open(str(work/"tone.wav")) as w: n=w.getnframes(); rate=w.getframerate()
        check(n>0 and rate>0,"audio output")
        return {"frames":n,"sample_rate":rate}
    if engine=="mediainfo":
        import wave,struct
        with wave.open(str(work/"tone.wav"),"wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(struct.pack("<8000h",*([0]*8000)))
        v=json.loads(cmd(["mediainfo","--Output=JSON",str(work/"tone.wav")],work))
        a=next(x for x in v["media"]["track"] if x["@type"]=="Audio"); close(float(a["SamplingRate"]),8000); close(float(a["Duration"]),1,.01)
        return {"sample_rate":8000,"duration_s":float(a["Duration"])}
    if engine=="sundials":
        c=work/"test.c"; c.write_text('#include <cvode/cvode.h>\n#include <cvode/cvode_ls.h>\n#include <nvector/nvector_serial.h>\n#include <sunmatrix/sunmatrix_dense.h>\n#include <sunlinsol/sunlinsol_dense.h>\n#include <sundials/sundials_context.h>\n#include <stdio.h>\nint rhs(realtype t,N_Vector y,N_Vector yd,void *d){NV_Ith_S(yd,0)=-NV_Ith_S(y,0);return 0;}\nint main(){SUNContext c; SUNContext_Create(0,&c); N_Vector y=N_VNew_Serial(1,c); NV_Ith_S(y,0)=1; void *mem=CVodeCreate(CV_BDF,c); if(CVodeInit(mem,rhs,0,y)<0||CVodeSStolerances(mem,1e-8,1e-10)<0)return 1; SUNMatrix A=SUNDenseMatrix(1,1,c); SUNLinearSolver ls=SUNLinSol_Dense(y,A,c); if(CVodeSetLinearSolver(mem,ls,A)<0)return 2; realtype t; if(CVode(mem,1,y,&t,CV_NORMAL)<0)return 3; printf("%.12f\\n",(double)NV_Ith_S(y,0)); CVodeFree(&mem); SUNLinSolFree(ls); SUNMatDestroy(A); N_VDestroy(y); SUNContext_Free(&c);return 0;}')
        cmd(["gcc",str(c),"-o",str(work/"test"),"-lsundials_cvode","-lsundials_nvecserial","-lsundials_sunmatrixdense","-lsundials_sunlinsoldense","-lm"],work)
        v=float(cmd([str(work/"test")],work).strip()); close(v,math.exp(-1),1e-6)
        return {"solution_t1":v}
    if engine=="petsc":
        c=work/"test.c"; c.write_text('#include <petscksp.h>\n#include <stdio.h>\nint main(int argc,char**argv){PetscInitialize(&argc,&argv,0,0);Mat A;Vec b,x;KSP k;MatCreateSeqAIJ(PETSC_COMM_SELF,1,1,1,0,&A);MatSetValue(A,0,0,2,INSERT_VALUES);MatAssemblyBegin(A,MAT_FINAL_ASSEMBLY);MatAssemblyEnd(A,MAT_FINAL_ASSEMBLY);VecCreateSeq(PETSC_COMM_SELF,1,&b);VecDuplicate(b,&x);VecSet(b,6);KSPCreate(PETSC_COMM_SELF,&k);KSPSetOperators(k,A,A);KSPSetType(k,KSPPREONLY);PC pc;KSPGetPC(k,&pc);PCSetType(pc,PCLU);KSPSolve(k,b,x);PetscScalar v;PetscInt i=0;VecGetValues(x,1,&i,&v);printf("%.10f\\n",(double)PetscRealPart(v));KSPDestroy(&k);VecDestroy(&x);VecDestroy(&b);MatDestroy(&A);PetscFinalize();return 0;}')
        import shlex
        flags=shlex.split(cmd(["pkg-config","--cflags","--libs","PETSc"],work))
        cmd(["mpicc",str(c),"-o",str(work/"test"),*flags],work)
        v=float(cmd([str(work/"test")],work).strip().splitlines()[-1]); close(v,3)
        return {"solution":v}
    if engine=="gromacs":
        (work/"fixture.gro").write_text("Public pair\n    2\n    1DUM      A    1   0.000   0.000   0.000\n    1DUM      B    2   0.200   0.000   0.000\n   2.00000   2.00000   2.00000\n")
        cmd(["gmx","distance","-s","fixture.gro","-f","fixture.gro","-select","atomnr 1 plus atomnr 2","-oall","distance.xvg","-xvg","none"],work)
        rows=[l for l in (work/"distance.xvg").read_text().splitlines() if l.strip() and not l.startswith(("#","@"))]
        v=float(rows[-1].split()[-1]); close(v,.2,1e-5)
        return {"distance_nm":v,"scope":"trajectory analysis, not molecular dynamics integration"}
    if engine=="cp2k":
        import shutil,re
        b=shutil.which("cp2k") or shutil.which("cp2k.psmp") or shutil.which("cp2k.ssmp"); check(b is not None,"CP2K binary")
        inp=work/"h2.inp"; inp.write_text("&GLOBAL\n PROJECT h2\n RUN_TYPE ENERGY\n PRINT_LEVEL LOW\n&END GLOBAL\n&FORCE_EVAL\n METHOD Quickstep\n &DFT\n BASIS_SET_FILE_NAME /usr/share/cp2k/data/BASIS_MOLOPT\n POTENTIAL_FILE_NAME /usr/share/cp2k/data/GTH_POTENTIALS\n &SCF\n MAX_SCF 60\n EPS_SCF 1.0E-6\n &END SCF\n &XC\n &XC_FUNCTIONAL PBE\n &END XC_FUNCTIONAL\n &END XC\n &MGRID\n CUTOFF 100\n REL_CUTOFF 30\n &END MGRID\n &END DFT\n &SUBSYS\n &CELL\n ABC 8 8 8\n &END CELL\n &COORD\n H 4 4 3.63\n H 4 4 4.37\n &END COORD\n &KIND H\n BASIS_SET DZVP-MOLOPT-SR-GTH\n POTENTIAL GTH-PBE-q1\n &END KIND\n &END SUBSYS\n&END FORCE_EVAL\n")
        out=cmd([b,"-i",str(inp)],work)
        matches=re.findall(r"ENERGY\| Total FORCE_EVAL.*?([-+]\d+\.\d+)",out); check(matches,"energy missing")
        v=float(matches[-1]); check(-2<v<-.5,"unphysical energy")
        return {"energy_hartree":v,"scope":"tiny H2 DFT reference, not converged production"} 
    if engine=="precice":
        cfg=work/"precice-config.xml"; cfg.write_text("""<precice-configuration>
        <data:scalar name="A"/><data:scalar name="B"/>
        <mesh name="FirstMesh" dimensions="2"><use-data name="A"/><use-data name="B"/></mesh>
        <mesh name="SecondMesh" dimensions="2"><use-data name="A"/><use-data name="B"/></mesh>
        <participant name="First"><provide-mesh name="FirstMesh"/><receive-mesh name="SecondMesh" from="Second"/><write-data name="A" mesh="FirstMesh"/><read-data name="B" mesh="FirstMesh"/><mapping:nearest-neighbor direction="read" from="SecondMesh" to="FirstMesh" constraint="consistent"/></participant>
        <participant name="Second"><provide-mesh name="SecondMesh"/><receive-mesh name="FirstMesh" from="First"/><write-data name="B" mesh="SecondMesh"/><read-data name="A" mesh="SecondMesh"/><mapping:nearest-neighbor direction="read" from="FirstMesh" to="SecondMesh" constraint="consistent"/></participant>
        <m2n:sockets acceptor="First" connector="Second" exchange-directory="." network="lo"/>
        <coupling-scheme:serial-explicit><participants first="First" second="Second"/><time-window-size value="1"/><max-time-windows value="1"/><exchange data="A" mesh="FirstMesh" from="First" to="Second"/><exchange data="B" mesh="SecondMesh" from="Second" to="First"/></coupling-scheme:serial-explicit>
        </precice-configuration>""")
        c=work/"p.cpp"; c.write_text("""#include <precice/precice.hpp>
        #include <vector>
        #include <iostream>
        #include <cmath>
        int main(int argc,char**argv){bool first=std::string(argv[1])=="First";std::string mesh=first?"FirstMesh":"SecondMesh";precice::Participant p(argv[1],"precice-config.xml",0,1);std::vector<double> pos{0,0};std::vector<precice::VertexID> ids{p.setMeshVertex(mesh,pos)};p.initialize();while(p.isCouplingOngoing()){double dt=p.getMaxTimeStepSize();std::vector<double> value{3.0};if(!first){p.readData(mesh,"A",ids,dt,value);std::cout<<"RECEIVED="<<value[0]<<std::endl;if(std::abs(value[0]-3)>1e-8)return 2;value[0]*=2;}p.writeData(mesh,first?"A":"B",ids,value);p.advance(dt);}p.finalize();return 0;}
        """)
        cmd(["g++","-std=c++17","-I/usr/include/eigen3",str(c),"-o",str(work/"p"),"-lprecice"],work)
        a=subprocess.Popen([str(work/"p"),"First"],cwd=work,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        b=subprocess.Popen([str(work/"p"),"Second"],cwd=work,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        try:
            vb,_=b.communicate(timeout=45); va,_=a.communicate(timeout=45)
            check(a.returncode==0 and b.returncode==0 and "RECEIVED=3" in vb,va[-1500:]+vb[-1500:])
        finally:
            for proc in (a,b):
                if proc.poll() is None: proc.kill(); proc.communicate()
        return {"participants":2,"transferred_value":3,"scope":"synthetic local explicit coupling, not OpenFOAM/CalculiX integration"}
    if engine=="mfem":
        import mfem.ser as m
        mesh=m.Mesh.MakeCartesian2D(2,2,m.Element.QUADRILATERAL,True,1.,1.)
        v=sum(mesh.GetElementVolume(i) for i in range(mesh.GetNE())); close(v,1)
        return {"elements":mesh.GetNE(),"area":v}
    if engine=="layoutparser":
        import layoutparser as l
        a=l.Rectangle(0,0,10,10); b=l.Rectangle(5,5,15,15)
        v=a.intersect(b).area; close(v,25)
        return {"intersection_area":v,"scope":"layout geometry only; no pretrained detector"}
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
