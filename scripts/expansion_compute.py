"""Public synthetic capability regression fixtures; never accept private or arbitrary inputs."""
import json, math, os, subprocess, sys, tempfile
from pathlib import Path

def check(condition, message):
    if not condition:
        raise RuntimeError(message)

def close(value, expected, tol=1e-6):
    check(math.isfinite(float(value)) and abs(float(value)-expected)<=tol,
          f"Expected {expected}, got {value}")

def cmd(args, work, timeout=120):
    p=subprocess.run(args,cwd=work,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout,check=False)
    check(p.returncode==0,f"Command failed: {p.stdout[-4000:]}")
    return p.stdout

def download(url, path, cap, digest=None):
    # URLs are fixed in reviewed fixture code, never taken from input.
    import urllib.request, hashlib
    request=urllib.request.Request(url,headers={"User-Agent":"ZEIBAEL-public-fixture"})
    with urllib.request.urlopen(request,timeout=60) as r:
        data=r.read(cap+1)
    check(len(data)<=cap,"Asset size limit exceeded")
    if digest:
        actual=(hashlib.sha512 if len(digest)==128 else hashlib.sha256)(data).hexdigest()
        check(actual==digest,"Public asset digest mismatch")
    path.write_bytes(data)
    return data

def hf(repo, revision, target, allow):
    # Anonymous pinned public files only. No provider inference, no token.
    os.environ["HF_HUB_OFFLINE"]="0"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"]="1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"]="1"
    from huggingface_hub import snapshot_download
    try:
        return snapshot_download(repo_id=repo,revision=revision,local_dir=str(target),allow_patterns=allow,token=False,max_workers=2,local_files_only=False)
    finally:
        os.environ["HF_HUB_OFFLINE"]="1"

def run(engine, work):
    work=Path(work).resolve()
    if engine == "thermo":
        from thermo import Chemical
        w = Chemical("water", T=298.15, P=101325)
        close(w.rho, 997, 3)
        return {"water_density_kg_m3": w.rho}
    if engine == "chemicals":
        from chemicals.identifiers import CAS_from_any, MW
        cas=CAS_from_any("water")
        check(cas=="7732-18-5","CAS mismatch")
        mw=MW(cas)
        close(mw,18.01528,0.01)
        return {"cas":cas,"molecular_weight":mw}
    if engine == "fluids":
        from fluids import Reynolds, friction_factor
        r=Reynolds(V=1,D=0.1,rho=1000,mu=0.001)
        close(r,100000)
        f=friction_factor(Re=1000,eD=0)
        close(f,0.064)
        return {"reynolds":r,"darcy_friction_factor":f}
    if engine == "ht":
        from ht import LMTD
        v=LMTD(Thi=100,Tho=80,Tci=20,Tco=40)
        close(v,60)
        return {"lmtd_K":v}
    if engine == "pybamm":
        import pybamm
        model=pybamm.lithium_ion.SPM()
        sim=pybamm.Simulation(model)
        sol=sim.solve([0,60])
        v=float(sol["Voltage [V]"].entries[-1])
        check(2<v<5,"Battery voltage invalid")
        return {"time_s":60,"voltage_V":v}
    if engine == "rdkit":
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
        mol=Chem.MolFromSmiles("CCO")
        check(rdMolDescriptors.CalcMolFormula(mol)=="C2H6O","Formula mismatch")
        v=Descriptors.MolWt(mol)
        close(v,46.069,0.01)
        return {"formula":"C2H6O","molecular_weight":v}
    if engine == "cadquery":
        import cadquery as cq
        part=cq.Workplane("XY").box(2,3,4)
        v=part.val().Volume()
        close(v,24)
        cq.exporters.export(part,str(work/"part.step"))
        check((work/"part.step").stat().st_size>100,"STEP missing")
        return {"volume_mm3":v,"step_bytes":(work/"part.step").stat().st_size}
    if engine == "wntr":
        import wntr
        wn=wntr.network.WaterNetworkModel()
        wn.add_reservoir("R",base_head=30)
        wn.add_junction("J",base_demand=0.001,elevation=0)
        wn.add_pipe("P","R","J",length=100,diameter=0.1,roughness=100)
        wn.options.time.duration=0
        res=wntr.sim.EpanetSimulator(wn).run_sim(file_prefix=str(work/"net"))
        q=float(res.link["flowrate"].iloc[0]["P"])
        close(q,0.001,1e-6)
        return {"flow_m3_s":q}
    if engine == "pandapower":
        import pandapower as pp
        n=pp.create_empty_network()
        b1=pp.create_bus(n,vn_kv=20); b2=pp.create_bus(n,vn_kv=20)
        pp.create_ext_grid(n,b1)
        pp.create_line_from_parameters(n,b1,b2,length_km=1,r_ohm_per_km=.1,x_ohm_per_km=.1,c_nf_per_km=0,max_i_ka=.4)
        pp.create_load(n,b2,p_mw=1,q_mvar=.2)
        pp.runpp(n)
        check(n.converged,"Power flow failed")
        v=float(n.res_bus.vm_pu.loc[b2]); check(.99<v<1,"Voltage mismatch")
        return {"bus_voltage_pu":v}
    if engine == "opendss":
        from dss import DSS
        DSS.Text.Command="new circuit.demo basekv=12.47 pu=1 phases=3"
        DSS.Text.Command="new line.l bus1=sourcebus bus2=loadbus phases=3 length=1 units=km r1=0.1 x1=0.1"
        DSS.Text.Command="new load.ld bus1=loadbus phases=3 kv=12.47 kw=100 pf=0.95"
        DSS.Text.Command="solve"
        check(DSS.ActiveCircuit.Solution.Converged,"Power flow failed")
        p=float(DSS.ActiveCircuit.TotalPower[0])
        check(-110<p<-90,"Power mismatch")
        return {"source_kw":p}
    if engine == "pyvista":
        import pyvista as pv
        mesh=pv.Cube(x_length=2,y_length=3,z_length=4).triangulate()
        close(mesh.volume,24)
        check(mesh.n_cells==12,"Mesh cell count mismatch")
        return {"volume":mesh.volume,"triangles":mesh.n_cells}
    if engine == "openmdao":
        import openmdao.api as om
        p=om.Problem()
        p.model.add_subsystem("f",om.ExecComp("y=(x-3)**2"),promotes=["*"])
        p.driver=om.ScipyOptimizeDriver(optimizer="SLSQP",disp=False)
        p.model.add_design_var("x",lower=-10,upper=10)
        p.model.add_objective("y")
        p.setup(); p.set_val("x",0); p.run_driver()
        v=float(p.get_val("x")[0]); close(v,3,1e-4)
        return {"optimum":v}
    if engine == "ortools":
        from ortools.sat.python import cp_model
        m=cp_model.CpModel(); x=m.NewIntVar(0,10,"x"); y=m.NewIntVar(0,10,"y")
        m.Add(x+y<=5); m.Maximize(3*x+2*y)
        s=cp_model.CpSolver(); s.parameters.num_search_workers=1
        check(s.Solve(m)==cp_model.OPTIMAL,"No optimum")
        close(s.ObjectiveValue(),15)
        return {"objective":s.ObjectiveValue(),"x":s.Value(x),"y":s.Value(y)}
    if engine == "pyomo":
        import pyomo.environ as p
        m=p.ConcreteModel(); m.x=p.Var(bounds=(0,5)); m.obj=p.Objective(expr=3*m.x,sense=p.maximize)
        res=p.SolverFactory("appsi_highs").solve(m)
        check(str(res.solver.termination_condition)=="optimal","Solver failed")
        close(p.value(m.x),5)
        return {"x":p.value(m.x),"objective":p.value(m.obj)}
    if engine == "highs":
        import highspy
        h=highspy.Highs(); h.setOptionValue("output_flag",False)
        x=h.addVariable(lb=0,ub=5,obj=3)
        h.setMaximize(); h.run()
        check(h.getModelStatus()==highspy.HighsModelStatus.kOptimal,"LP failed")
        v=h.getObjectiveValue(); close(v,15)
        return {"objective":v}
    if engine == "cvxpy":
        import cvxpy as cp
        x=cp.Variable(); p=cp.Problem(cp.Minimize(cp.square(x-3)),[x>=4]); p.solve(solver="CLARABEL")
        check(p.status=="optimal","Solver failed")
        close(float(x.value),4,1e-4)
        return {"x":float(x.value),"objective":p.value}
    if engine == "casadi":
        import casadi as ca
        x=ca.MX.sym("x"); f=ca.Function("f",[x],[ca.jacobian(x**3,x)])
        v=float(f(2)); close(v,12)
        solver=ca.nlpsol("s","ipopt",{"x":x,"f":(x-2)**2},{"ipopt.print_level":0,"print_time":False})
        opt=float(solver(x0=0)["x"]); close(opt,2,1e-5)
        return {"derivative":v,"optimum":opt}
    if engine == "salib":
        import numpy as np
        from SALib.sample import sobol as sample
        from SALib.analyze import sobol
        p={"num_vars":2,"names":["x","y"],"bounds":[[0,1],[0,1]]}
        x=sample.sample(p,512,calc_second_order=False,seed=3)
        s=sobol.analyze(p,x[:,0]+2*x[:,1],calc_second_order=False)
        close(float(s["S1"][0]),.2,.06); close(float(s["S1"][1]),.8,.06)
        return {"first_order":s["S1"].tolist()}
    if engine == "simpy":
        import simpy
        env=simpy.Environment(); r=simpy.Resource(env,capacity=1); ends=[]
        def job():
            with r.request() as req:
                yield req; yield env.timeout(2); ends.append(env.now)
        for _ in range(3): env.process(job())
        env.run(); check(ends==[2,4,6],"Queue mismatch")
        return {"completion_times":ends}
    if engine == "pint":
        import pint
        u=pint.UnitRegistry(); value=(1*u.bar).to("pascal").magnitude
        close(value,100000)
        return {"pascal_per_bar":value}
    if engine == "pymc":
        import pymc as pm
        import numpy as np
        with pm.Model():
            x=pm.Normal("x",mu=2,sigma=.5)
            s=pm.draw(x,draws=1000,random_seed=7)
        v=float(np.mean(s)); close(v,2,.1)
        return {"prior_mean":v,"draws":1000}
    if engine == "deap":
        from deap import base, creator, tools
        creator.create("Fit",base.Fitness,weights=(1.0,))
        creator.create("Ind",list,fitness=creator.Fit)
        pop=[creator.Ind([x]) for x in range(5)]
        for i in pop: i.fitness.values=(i[0],)
        best=tools.selBest(pop,1)[0]
        check(best[0]==4,"Selection mismatch")
        return {"best":best[0]}
    if engine == "talib":
        import talib
        import numpy as np
        v=talib.SMA(np.array([1.,2.,3.,4.,5.]),timeperiod=3)
        close(float(v[-1]),4)
        return {"sma_3":float(v[-1])}
    if engine == "backtrader":
        import backtrader as bt
        import pandas as pd
        class S(bt.Strategy):
            def next(self):
                if len(self)==1: self.buy(size=1)
                if len(self)==3: self.close()
        df=pd.DataFrame({"open":[10,11,12,13,14],"high":[10,11,12,13,14],"low":[10,11,12,13,14],"close":[10,11,12,13,14],"volume":[1]*5},index=pd.date_range("2025-01-01",periods=5))
        c=bt.Cerebro(); c.broker.setcash(100); c.adddata(bt.feeds.PandasData(dataname=df)); c.addstrategy(S); c.run()
        v=c.broker.getvalue(); close(v,102)
        return {"synthetic_final_cash":v}
    if engine == "statsmodels":
        import statsmodels.api as sm
        import numpy as np
        x=np.arange(10.); y=2*x+3
        v=sm.OLS(y,sm.add_constant(x)).fit().params
        close(v[0],3); close(v[1],2)
        return {"coefficients":v.tolist()}
    if engine == "optuna":
        import optuna
        s=optuna.create_study(sampler=optuna.samplers.GridSampler({"x":[0,1,2,3]}))
        s.optimize(lambda t:(t.suggest_int("x",0,3)-2)**2,n_trials=4)
        close(s.best_value,0); check(s.best_params["x"]==2,"Optimum mismatch")
        return {"best_params":s.best_params,"objective":s.best_value}
    if engine == "riskfolio":
        import riskfolio as rp
        import pandas as pd
        import numpy as np
        r=pd.DataFrame({"A":[.01,-.02,.03,-.01,.02,.01],"B":[.02,.01,-.01,.02,-.01,.01]})
        p=rp.Portfolio(returns=r); p.assets_stats(method_mu="hist",method_cov="hist")
        w=p.optimization(model="Classic",rm="MV",obj="MinRisk",rf=0,hist=True)
        check(w is not None,"Portfolio failed"); close(float(w.weights.sum()),1,1e-5)
        return {"weights":{str(k):float(v) for k,v in w.weights.items()}}
    if engine == "arch":
        from arch import arch_model
        import numpy as np
        r=np.random.default_rng(4).normal(0,1,200)
        fit=arch_model(r,p=1,q=1).fit(disp="off")
        v=float(fit.forecast(horizon=1).variance.iloc[-1,0]); check(v>0 and np.isfinite(v),"Invalid variance")
        return {"forecast_variance":v}
    if engine == "pyportfolioopt":
        from pypfopt import EfficientFrontier
        import numpy as np
        p=EfficientFrontier(np.array([.1,.2]),np.array([[.04,0],[0,.04]]))
        w=p.min_volatility(); close(w[0],.5,1e-4); close(w[1],.5,1e-4)
        return {"weights":list(w.values())}
    if engine == "statsforecast":
        from statsforecast.models import Naive
        import numpy as np
        v=Naive().fit(np.array([1.,2.,3.])).predict(h=2)["mean"]
        check(v.tolist()==[3.,3.],"Forecast mismatch")
        return {"forecast":v.tolist()}
    if engine == "shap":
        import shap
        from sklearn.linear_model import LinearRegression
        import numpy as np
        x=np.array([[0.],[1.],[2.],[3.]])
        m=LinearRegression().fit(x,2*x[:,0]+1)
        e=shap.LinearExplainer(m,x)
        v=e(x)
        close(float(v.values[-1,0]+v.base_values[-1]),7)
        return {"prediction":7,"shap_value":float(v.values[-1,0])}
    if engine == "scikit_learn":
        from sklearn.linear_model import LinearRegression
        m=LinearRegression().fit([[0],[1],[2]],[1,3,5])
        v=float(m.predict([[3]])[0]); close(v,7)
        return {"prediction":v}
    if engine == "xgboost":
        import xgboost as xgb
        import numpy as np
        x=np.arange(100).reshape(-1,1); y=(x[:,0]>=50).astype(int)
        m=xgb.XGBClassifier(n_estimators=12,max_depth=2,n_jobs=1,random_state=7,device="cpu")
        m.fit(x,y); v=m.predict([[10],[90]]).tolist()
        check(v==[0,1],"Classifier mismatch")
        return {"predictions":v}
    if engine == "lightgbm":
        import lightgbm as lgb
        import numpy as np
        x=np.arange(100).reshape(-1,1); y=(x[:,0]>=50).astype(int)
        m=lgb.LGBMClassifier(n_estimators=12,n_jobs=1,verbosity=-1,random_state=7)
        m.fit(x,y); v=m.predict(np.array([[10],[90]])).tolist()
        check(v==[0,1],"Classifier mismatch")
        return {"predictions":v}
    if engine == "catboost":
        from catboost import CatBoostClassifier
        x=[[i] for i in range(100)]; y=[int(i>=50) for i in range(100)]
        m=CatBoostClassifier(iterations=20,depth=2,thread_count=1,verbose=False,allow_writing_files=False,random_seed=7)
        m.fit(x,y); v=m.predict([[10],[90]]).astype(int).tolist()
        check(v==[0,1],"Classifier mismatch")
        return {"predictions":v}
    if engine == "tensorflow":
        import tensorflow as tf
        x=tf.Variable([1.,2.,3.])
        with tf.GradientTape() as tape: loss=tf.reduce_sum(x*x)
        v=tape.gradient(loss,x).numpy().tolist()
        check(v==[2.,4.,6.],"Gradient mismatch")
        return {"gradient":v,"device":"cpu"}
    if engine == "jax":
        import jax
        import jax.numpy as jnp
        v=jax.grad(lambda x:jnp.sum(x*x))(jnp.array([1.,2.,3.])).tolist()
        check(v==[2.,4.,6.],"Gradient mismatch")
        return {"gradient":v,"device":jax.default_backend()}
    if engine == "faiss":
        import faiss
        import numpy as np
        ix=faiss.IndexFlatL2(2); ix.add(np.array([[0,0],[2,2]],dtype="float32"))
        d,i=ix.search(np.array([[1.9,2]],dtype="float32"),1)
        check(int(i[0,0])==1,"Neighbor mismatch")
        return {"nearest_index":int(i[0,0]),"distance":float(d[0,0])}
    if engine == "pdfplumber":
        import pdfplumber
        from reportlab.pdfgen import canvas
        p=work/"sample.pdf"; c=canvas.Canvas(str(p)); c.drawString(72,720,"ZEIBAEL PUBLIC 123"); c.save()
        with pdfplumber.open(p) as pdf: v=pdf.pages[0].extract_text()
        check(v=="ZEIBAEL PUBLIC 123","Extraction mismatch")
        return {"text":v}
    if engine == "ocrmypdf":
        from PIL import Image,ImageDraw,ImageFont
        import ocrmypdf
        import pypdf
        im=Image.new("RGB",(900,200),"white"); d=ImageDraw.Draw(im)
        d.text((20,40),"ZEIBAEL 12345",font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",55),fill="black")
        im.save(work/"scan.pdf",resolution=150)
        ocrmypdf.ocr(work/"scan.pdf",work/"ocr.pdf",language=["eng"],output_type="pdf",jobs=1,progress_bar=False)
        v=pypdf.PdfReader(work/"ocr.pdf").pages[0].extract_text()
        check("ZEIBAEL" in v and "12345" in v,"OCR PDF mismatch")
        return {"text":v.strip()}
    if engine == "libreoffice":
        (work/"note.txt").write_text("ZEIBAEL PUBLIC 123")
        cmd(["libreoffice","-env:UserInstallation=file://"+str(work/"lo-profile"),"--headless","--convert-to","pdf","--outdir",str(work),str(work/"note.txt")],work)
        v=(work/"note.pdf").read_bytes()
        check(v.startswith(b"%PDF"),"PDF missing")
        return {"pdf_bytes":len(v)}
    if engine == "pandoc":
        (work/"a.md").write_text("# Public\n\n**ZEIBAEL**\n")
        v=cmd(["pandoc","-f","markdown","-t","html","a.md"],work)
        check("<strong>ZEIBAEL</strong>" in v,"HTML mismatch")
        return {"html":v.strip()}
    if engine == "tesseract_multilingual":
        cmd(["convert","-size","1000x200","xc:white","-font","DejaVu-Sans","-pointsize","60","-fill","black","-gravity","center","-annotate","0","Keselamatan kerja","ocr.png"],work)
        v=cmd(["tesseract","ocr.png","stdout","-l","ind","--psm","7"],work)
        check("keselamatan kerja" in v.lower(),"Indonesian text mismatch")
        return {"language":"ind","text":v.strip()}
    if engine == "scenedetect":
        import cv2
        import numpy as np
        from scenedetect import open_video,SceneManager
        from scenedetect.detectors import ContentDetector
        p=work/"demo.avi"; out=cv2.VideoWriter(str(p),cv2.VideoWriter_fourcc(*"MJPG"),10,(64,64))
        for i in range(40):
            out.write(np.full((64,64,3),0 if i<20 else 255,np.uint8))
        out.release()
        s=SceneManager(); s.add_detector(ContentDetector(threshold=20,min_scene_len=5)); s.detect_scenes(open_video(str(p)))
        v=s.get_scene_list(); check(len(v)==2,"Scene count mismatch")
        return {"scene_count":len(v),"cut_frame":v[1][0].get_frames()}
    if engine == "librosa":
        import librosa
        import numpy as np
        sr=8000; y=np.sin(2*np.pi*440*np.arange(sr)/sr)
        s=np.abs(librosa.stft(y,n_fft=1024))
        f=float(librosa.fft_frequencies(sr=sr,n_fft=1024)[np.argmax(s.mean(axis=1))])
        close(f,440,5)
        return {"dominant_hz":f}
    if engine == "imagemagick":
        cmd(["convert","-size","40x20","xc:red","-resize","20x10","output.png"],work)
        v=cmd(["identify","-format","%wx%h","output.png"],work)
        check(v.strip()=="20x10","Image dimensions wrong")
        return {"size":v.strip()}
    if engine == "blender":
        (work/"fixture.py").write_text("import bpy\nbpy.ops.mesh.primitive_cube_add(size=2)\nobj=bpy.context.object\nassert len(obj.data.vertices)==8\nbpy.ops.wm.save_as_mainfile(filepath="+repr(str(work/"scene.blend"))+")\nprint('ZEIBAEL_MESH_OK')\n")
        v=cmd(["blender","-b","--factory-startup","--python",str(work/"fixture.py")],work,timeout=240)
        check("ZEIBAEL_MESH_OK" in v and (work/"scene.blend").is_file(),"Blender fixture missing")
        return {"vertices":8,"blend_bytes":(work/"scene.blend").stat().st_size}
    if engine == "open3d":
        import open3d as o3d
        import numpy as np
        p=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])))
        p.translate((1,2,3)); v=np.asarray(p.points)
        check(np.allclose(v[0],[1,2,3]),"Point translation mismatch")
        return {"points":len(v),"first":v[0].tolist()}
    if engine == "arrow":
        import pyarrow as pa
        import pyarrow.parquet as pq
        t=pa.table({"x":[1,2,3]}); pq.write_table(t,work/"t.parquet"); v=pq.read_table(work/"t.parquet")
        check(v.equals(t),"Parquet roundtrip mismatch")
        return {"rows":v.num_rows}
    if engine == "dask":
        import dask.array as da
        v=int(da.arange(100,chunks=10).sum().compute(scheduler="threads",num_workers=2))
        close(v,4950)
        return {"sum":v,"chunks":10}
    if engine == "networkx":
        import networkx as nx
        g=nx.Graph(); g.add_weighted_edges_from([("a","b",1),("b","c",2),("a","c",10)])
        v=nx.shortest_path(g,"a","c",weight="weight")
        check(v==["a","b","c"],"Shortest path mismatch")
        return {"path":v,"length":nx.shortest_path_length(g,"a","c",weight="weight")}
    if engine == "gdal":
        (work/"point.geojson").write_text('{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[0,0]},"properties":{"id":1}}]}')
        cmd(["ogr2ogr","-f","GPKG","point.gpkg","point.geojson"],work)
        v=cmd(["ogrinfo","-so","point.gpkg","point"],work)
        check("Feature Count: 1" in v,"GDAL feature mismatch")
        return {"feature_count":1}
    if engine == "geopandas":
        import geopandas as gpd
        from shapely.geometry import Point
        g=gpd.GeoSeries([Point(0,0),Point(1,0)],crs=4326).to_crs(3857)
        v=float(g.iloc[0].distance(g.iloc[1]))
        close(v,111319.49,.2)
        return {"projected_distance_m":v}
    if engine == "xarray":
        import xarray as xr
        a=xr.DataArray([[1,2],[3,4]],dims=["time","x"])
        v=a.mean("time").values.tolist()
        check(v==[2.,3.],"Dimension reduction mismatch")
        return {"mean":v}
    if engine == "rasterio":
        import rasterio
        from rasterio.transform import from_origin
        import numpy as np
        a=np.array([[1,2],[3,4]],dtype=np.uint8)
        with rasterio.open(work/"a.tif","w",driver="GTiff",width=2,height=2,count=1,dtype="uint8",crs="EPSG:4326",transform=from_origin(100,1,.1,.1)) as ds: ds.write(a,1)
        with rasterio.open(work/"a.tif") as ds: v=int(ds.read(1).sum())
        close(v,10)
        return {"sum":v,"pixels":4}
    if engine == "orjson":
        import orjson
        a={"text":"public","values":[1,2,3]}
        v=orjson.loads(orjson.dumps(a)); check(a==v,"Roundtrip mismatch")
        return v
    if engine == "great_expectations":
        import great_expectations as gx
        import pandas as pd
        ctx=gx.get_context(mode="ephemeral")
        src=ctx.data_sources.add_pandas("public")
        asset=src.add_dataframe_asset("sample")
        batch=asset.add_batch_definition_whole_dataframe("all").get_batch(batch_parameters={"dataframe":pd.DataFrame({"x":[1,2,3]})})
        r=batch.validate(gx.expectations.ExpectColumnValuesToBeBetween(column="x",min_value=1,max_value=3))
        check(r.success,"Expectation failed")
        return {"success":bool(r.success),"rows":3}
    if engine == "hypothesis":
        from hypothesis import given,settings,strategies as st
        n=[0]
        @settings(max_examples=25,derandomize=True,database=None)
        @given(st.lists(st.integers(),max_size=10))
        def test(xs):
            check(list(reversed(list(reversed(xs))))==xs,"Property violated"); n[0]+=1
        test(); check(n[0]>1,"No examples")
        return {"examples":n[0]}
    if engine == "locust":
        import threading
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
            def log_message(self,*args): pass
        server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            (work/"locustfile.py").write_text("from locust import HttpUser,task,constant\nclass PublicUser(HttpUser):\n    wait_time=constant(.05)\n    @task\n    def get(self): self.client.get('/')\n")
            cmd(["locust","-f","locustfile.py","--headless","-u","1","-r","1","-t","2s","--host",f"http://127.0.0.1:{server.server_port}","--csv","result"],work)
            import csv
            rows=list(csv.DictReader((work/"result_stats.csv").open()))
            total=next(x for x in rows if x["Name"]=="Aggregated")
            check(int(total["Request Count"])>0 and int(total["Failure Count"])==0,"Load fixture failed")
            return {"requests":int(total["Request Count"]),"failures":0}
        finally: server.shutdown(); server.server_close()
    if engine == "semgrep":
        (work/"rule.yml").write_text("rules:\n- id: public-print\n  languages: [python]\n  message: public fixture\n  severity: INFO\n  pattern: print(...)\n")
        (work/"sample.py").write_text("print('public')\n")
        v=json.loads(cmd(["semgrep","scan","--config","rule.yml","--metrics=off","--disable-version-check","--json","sample.py"],work))
        check(len(v["results"])==1,"Rule did not match")
        return {"matches":1}
    if engine == "z3":
        from z3 import Int,Solver,sat
        x=Int("x"); y=Int("y"); s=Solver(); s.add(x+y==7,x-y==1)
        check(s.check()==sat,"Constraint solve failed"); m=s.model()
        v=[m[x].as_long(),m[y].as_long()]; check(v==[4,3],"Solution mismatch")
        return {"solution":v}
    if engine == "scrapy":
        from scrapy.http import HtmlResponse
        r=HtmlResponse(url="https://example.invalid",body=b"<html><h1>ZEIBAEL</h1><a href='/public'>link</a></html>",encoding="utf-8")
        v=r.css("h1::text").get(); check(v=="ZEIBAEL" and r.css("a::attr(href)").get()=="/public","Extraction mismatch")
        return {"heading":v,"scope":"local HTML selector only"}
    if engine == "trafilatura":
        import trafilatura
        html="<html><body><article><h1>Public fixture</h1><p>"+("ZEIBAEL public data processing example. "*30)+"</p></article></body></html>"
        v=trafilatura.extract(html); check(v and "ZEIBAEL public data" in v,"Content extraction failed")
        return {"characters":len(v)}
    if engine == "idaes":
        from pyomo.environ import ConcreteModel,value
        from idaes.core import FlowsheetBlock
        from idaes.models.properties.examples.saponification_thermo import SaponificationParameterBlock
        m=ConcreteModel(); m.fs=FlowsheetBlock(dynamic=False)
        m.fs.props=SaponificationParameterBlock()
        m.fs.state=m.fs.props.build_state_block([0],defined_state=True)
        s=m.fs.state[0]; s.flow_vol.set_value(.01); s.conc_mol_comp["NaOH"].set_value(100)
        v=value(s.get_material_flow_terms("Liq","NaOH")); close(v,1)
        return {"molar_flow_mol_s":v,"scope":"property-model material-flow calculation; not IPOPT process optimization"}
    if engine == "watertap":
        from pyomo.environ import ConcreteModel,value
        from pyomo.util.calc_var_value import calculate_variable_from_constraint
        from idaes.core import FlowsheetBlock
        from watertap.property_models.NaCl_prop_pack import NaClParameterBlock
        m=ConcreteModel(); m.fs=FlowsheetBlock(dynamic=False); m.fs.props=NaClParameterBlock()
        m.fs.state=m.fs.props.build_state_block([0],defined_state=True); s=m.fs.state[0]
        s.flow_mass_phase_comp["Liq","H2O"].set_value(.965); s.flow_mass_phase_comp["Liq","NaCl"].set_value(.035)
        for j in ["H2O","NaCl"]:
            calculate_variable_from_constraint(s.mass_frac_phase_comp["Liq",j],s.eq_mass_frac_phase_comp["Liq",j])
        calculate_variable_from_constraint(s.dens_mass_phase["Liq"],s.eq_dens_mass_phase["Liq"])
        v=value(s.dens_mass_phase["Liq"]); close(value(s.mass_frac_phase_comp["Liq","NaCl"]),.035)
        close(v,1021.46,.05)
        return {"salt_mass_fraction":.035,"density_kg_m3":v,"scope":"NaCl property model only; not treatment flowsheet optimization"}
    if engine == "phreeqc":
        from phreeqpy.iphreeqc.phreeqc_dll import IPhreeqc
        import hashlib
        db=download("https://raw.githubusercontent.com/phreeqc-dev/phreeqc3/v3.7.3/database/phreeqc.dat",work/"phreeqc.dat",1000000)
        blob=hashlib.sha1(b"blob "+str(len(db)).encode()+b"\0"+db).hexdigest()
        check(blob=="9e69a1875801b8fe41c363030e9139bbb635a35c","PHREEQC database blob changed")
        p=IPhreeqc(); p.load_database(str(work/"phreeqc.dat"))
        p.run_string("SOLUTION 1\n temp 25\n pH 7\n units mol/kgw\n Na 0.01\n Cl 0.01\nSELECTED_OUTPUT\n -reset false\n -pH true\n -totals Na Cl\nEND")
        rows=p.get_selected_output_array()
        check(len(rows)>=2,"No speciation output")
        v=[float(x) for x in rows[-1]]; close(v[0],7,.01); close(v[1],.01,1e-6); close(v[2],.01,1e-6)
        return {"pH":v[0],"Na_mol_kg":v[1],"Cl_mol_kg":v[2],"database_blob":blob}
    if engine == "freecad":
        macro=work/"fixture.FCMacro"
        macro.write_text("import FreeCAD, Part\np=Part.makeBox(2,3,4)\nassert abs(p.Volume-24)<1e-6\np.exportStep("+repr(str(work/"part.step"))+")\nopen("+repr(str(work/"proof.txt"))+",'w').write(str(p.Volume))\n")
        import shutil, urllib.request, hashlib
        check(shutil.disk_usage(work).free>5*1024**3,"Insufficient disk for verified AppImage")
        app=work/"freecad.AppImage"; h=hashlib.sha256(); size=0
        with urllib.request.urlopen("https://github.com/FreeCAD/FreeCAD/releases/download/1.1.4/FreeCAD_1.1.4-Linux-x86_64-py311.AppImage",timeout=60) as response, app.open("wb") as output:
            while chunk:=response.read(1024*1024):
                size+=len(chunk); check(size<=850000000,"AppImage exceeds bound")
                h.update(chunk); output.write(chunk)
        check(h.hexdigest()=="f6dc6ba676e5ac96a565ebc8d657232f94c6158e85b4352141bd1a46f6b43434","FreeCAD digest mismatch")
        app.chmod(0o700); cmd([str(app),"--appimage-extract"],work,timeout=240)
        root=work/"squashfs-root"
        os.environ["QT_QPA_PLATFORM"]="offscreen"
        os.environ["LD_LIBRARY_PATH"]=str(root/"usr/lib")
        exe=next((x for x in root.rglob("*") if x.name.lower() in ("freecadcmd","freecadcmd.bin") and x.is_file()),None)
        check(exe is not None,"FreeCAD headless CLI absent from AppImage")
        cmd([str(exe),str(macro)],work,timeout=180)
        v=float((work/"proof.txt").read_text()); close(v,24)
        check((work/"part.step").stat().st_size>100,"STEP missing")
        return {"volume_mm3":v,"step_bytes":(work/"part.step").stat().st_size}
    if engine == "openseespy":
        import openseespy.opensees as o
        o.wipe(); o.model("basic","-ndm",1,"-ndf",1)
        o.node(1,0); o.node(2,1); o.fix(1,1)
        o.uniaxialMaterial("Elastic",1,1000.); o.element("truss",1,1,2,1.,1)
        o.timeSeries("Linear",1); o.pattern("Plain",1,1); o.load(2,10.)
        o.system("BandGeneral"); o.numberer("Plain"); o.constraints("Plain")
        o.integrator("LoadControl",1); o.algorithm("Linear"); o.analysis("Static")
        check(o.analyze(1)==0,"Structural solve failed"); v=o.nodeDisp(2,1); close(v,.01,1e-8); o.wipe()
        return {"displacement":v,"license_scope":"research/education/internal use only; no redistribution"}
    if engine == "fenicsx":
        f=work/"fenics.py"
        f.write_text("from mpi4py import MPI\nfrom dolfinx import mesh,fem\nimport ufl\nm=mesh.create_unit_square(MPI.COMM_WORLD,4,4)\nv=fem.assemble_scalar(fem.form(1*ufl.dx(domain=m)))\nprint(float(v))\n")
        image="dolfinx/dolfinx@sha256:61f17eb5de64721e8bbfc06b0e715bd8d0c3b6f8ec37d30f6985016c6ac68472"
        v=float(cmd(["docker","run","--rm","--network","none","--entrypoint","python",image,"-c",f.read_text()],work,timeout=180).strip().splitlines()[-1])
        close(v,1,1e-9)
        return {"integrated_unit_square_area":v}
    if engine == "qlib":
        from qlib.contrib.evaluate import risk_analysis
        import pandas as pd
        v=risk_analysis(pd.Series([.01,-.02,.03,.02]),freq="day")
        mean=float(v.loc["mean","risk"]); close(mean,.01)
        return {"mean_return":mean,"scope":"synthetic risk metric; not trading performance"}
    if engine == "llama_cpp":
        import tarfile
        archive=work/"llama.tar.gz"
        download("https://github.com/ggml-org/llama.cpp/releases/download/b11865/llama-b11865-bin-ubuntu-x64.tar.gz",archive,30000000,"b59572aebe7df4de33b87d58a84a183d4ee0be4d5c8fe82df77b68ea65bc8bd6")
        with tarfile.open(archive) as a: a.extractall(work/"llama",filter="data")
        binary=next((work/"llama").rglob("llama-cli"))
        model=hf("bartowski/SmolLM2-135M-Instruct-GGUF","09816acd5d99df7be770d85ea30822623dab342c",work/"model",["SmolLM2-135M-Instruct-Q4_K_M.gguf"])
        gguf=Path(model)/"SmolLM2-135M-Instruct-Q4_K_M.gguf"
        os.environ["LD_LIBRARY_PATH"]=str(binary.parent)
        v=cmd([str(binary),"-m",str(gguf),"-p","The capital of France is","-n","8","-t","2","-ngl","0","-no-cnv","--temp","0"],work,timeout=180)
        check("Paris" in v,"Expected token absent")
        return {"model":"SmolLM2-135M-Instruct Q4_K_M","answer_has_paris":True,"cpu_only":True}
    if engine == "transformers":
        model=hf("sentence-transformers/all-MiniLM-L6-v2","1110a243fdf4706b3f48f1d95db1a4f5529b4d41",work/"model",["*.json","*.txt","model.safetensors","1_Pooling/config.json"])
        from transformers import AutoModel,AutoTokenizer
        import torch
        t=AutoTokenizer.from_pretrained(model,local_files_only=True,trust_remote_code=False)
        m=AutoModel.from_pretrained(model,local_files_only=True,trust_remote_code=False,use_safetensors=True).eval()
        with torch.no_grad(): v=m(**t("Public synthetic compute",return_tensors="pt")).last_hidden_state
        check(v.shape[-1]==384 and torch.isfinite(v).all().item(),"Invalid embedding")
        return {"hidden_size":v.shape[-1],"token_count":v.shape[1],"device":"cpu"}
    if engine == "sentence_transformers":
        model=hf("sentence-transformers/all-MiniLM-L6-v2","1110a243fdf4706b3f48f1d95db1a4f5529b4d41",work/"model",["*.json","*.txt","model.safetensors","1_Pooling/config.json"])
        from sentence_transformers import SentenceTransformer
        import numpy as np
        m=SentenceTransformer(model,device="cpu",local_files_only=True,trust_remote_code=False)
        v=m.encode(["public chemical process","public chemical process","blue sky"],normalize_embeddings=True)
        close(float(v[0]@v[1]),1,1e-5); check(float(v[0]@v[2])<.9,"Similarity reference failed")
        return {"dimension":v.shape[1],"same_text_similarity":float(v[0]@v[1]),"different_text_similarity":float(v[0]@v[2])}
    if engine == "docling":
        from docling.document_converter import DocumentConverter
        from docling.datamodel.base_models import InputFormat
        p=work/"sample.md"; p.write_text("# Public fixture\n\n| Name | Value |\n|---|---|\n| ZEIBAEL | 123 |\n")
        v=DocumentConverter(allowed_formats=[InputFormat.MD]).convert(p).document
        text=v.export_to_markdown()
        check("ZEIBAEL" in text and "123" in text and len(v.tables)==1,"Markdown structure mismatch")
        return {"tables":len(v.tables),"scope":"Markdown structured document; PDF neural layout not yet tested"}
    if engine == "paddleocr":
        from PIL import Image,ImageDraw,ImageFont
        im=Image.new("RGB",(1000,200),"white"); d=ImageDraw.Draw(im); d.text((50,60),"ZEIBAEL 12345",font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",60),fill="black"); im.save(work/"sample.png")
        det=hf("PaddlePaddle/PP-OCRv5_mobile_det","0d63e78e2b680928f6b1747d76a08db6e645efb7",work/"det",["inference.*","*.json","*.yml"])
        rec=hf("PaddlePaddle/PP-OCRv5_mobile_rec","682f20538d8c086cb2128e5cfac775e6c4904e85",work/"rec",["inference.*","*.json","*.yml"])
        from paddleocr import PaddleOCR
        m=PaddleOCR(text_detection_model_name="PP-OCRv5_mobile_det",text_detection_model_dir=det,text_recognition_model_name="PP-OCRv5_mobile_rec",text_recognition_model_dir=rec,use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,device="cpu")
        v=" ".join(str(t) for x in m.predict(str(work/"sample.png")) for t in x.json["res"]["rec_texts"])
        check("ZEIBAEL" in v.upper() and "12345" in v,"OCR text mismatch")
        return {"text":v,"device":"cpu"}
    if engine == "tika":
        from reportlab.pdfgen import canvas
        p=work/"sample.pdf"; c=canvas.Canvas(str(p)); c.drawString(72,720,"ZEIBAEL PUBLIC 123"); c.save()
        download("https://archive.apache.org/dist/tika/3.1.0/tika-app-3.1.0.jar",work/"tika.jar",150000000,"66ae3805a3888bdf48dacd849ca15e51b35dae480495a41df9886deabb2475b4d58c7a2c336f18de0d2dac1cf449eee0cc9dde4f82441e3a42b8193175a3247f")
        v=cmd(["java","-Xmx512m","-jar",str(work/"tika.jar"),"-t",str(p)],work,timeout=180)
        check("ZEIBAEL PUBLIC 123" in v,"PDF extraction mismatch")
        return {"text":"ZEIBAEL PUBLIC 123","scope":"synthetic local PDF only; no untrusted parser input"}
    if engine == "silero_vad":
        import torch
        from silero_vad import load_silero_vad,get_speech_timestamps,read_audio
        m=load_silero_vad(onnx=True)
        silence=torch.zeros(16000)
        check(not get_speech_timestamps(silence,m,sampling_rate=16000),"Silence falsely classified")
        cmd(["espeak-ng","-w",str(work/"speech.wav"),"This is a public synthetic speech fixture."],work)
        cmd(["ffmpeg","-v","error","-y","-i",str(work/"speech.wav"),"-ar","16000","-ac","1",str(work/"speech16.wav")],work)
        a=read_audio(str(work/"speech16.wav"),sampling_rate=16000)
        v=get_speech_timestamps(a,m,sampling_rate=16000)
        check(len(v)>0,"Generated speech not detected")
        return {"speech_segments":len(v),"silence_segments":0}
    if engine == "ray":
        import ray
        os.environ["RAY_USAGE_STATS_ENABLED"]="0"
        ray.init(num_cpus=2,include_dashboard=False,object_store_memory=80*1024*1024,_temp_dir=str(work/"ray"),_node_ip_address="127.0.0.1",log_to_driver=False)
        try:
            @ray.remote
            def f(x): return x*x
            v=ray.get([f.remote(x) for x in range(4)],timeout=60)
            check(v==[0,1,4,9],"Parallel result mismatch")
            return {"results":v,"cpus":2,"scope":"single ephemeral runner"}
        finally: ray.shutdown()
    if engine == "k6":
        import tarfile
        download("https://github.com/grafana/k6/releases/download/v1.0.0/k6-v1.0.0-linux-amd64.tar.gz",work/"k6.tar.gz",40000000,"5eb2236bc76a3c5cced12aaf0fd76c4b1ceac5ea040c70388a3d272b46595b59")
        with tarfile.open(work/"k6.tar.gz") as a: a.extractall(work/"k6dir",filter="data")
        binary=next((work/"k6dir").rglob("k6"))
        import threading
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
            def log_message(self,*args): pass
        server=ThreadingHTTPServer(("127.0.0.1",0),Handler); threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            (work/"test.js").write_text("import http from 'k6/http'; import {check} from 'k6'; export const options={vus:1,iterations:3,thresholds:{checks:['rate==1']}}; export default function(){check(http.get('http://127.0.0.1:"+str(server.server_port)+"/'),{'status 200':r=>r.status===200});}")
            os.environ["K6_NO_USAGE_REPORT"]="true"
            cmd([str(binary),"run","--summary-export",str(work/"summary.json"),str(work/"test.js")],work)
            v=json.loads((work/"summary.json").read_text())["metrics"]["checks"]["value"]; close(v,1)
            return {"check_rate":v,"iterations":3}
        finally: server.shutdown(); server.server_close()
    if engine == "trivy":
        import tarfile
        download("https://github.com/aquasecurity/trivy/releases/download/v0.76.2/trivy_0.76.2_Linux-64bit.tar.gz",work/"trivy.tar.gz",60000000,"bc0fc726e017b8927a62b2d3531d7a84ee01769daf5c99ed866dced54089fdbf")
        with tarfile.open(work/"trivy.tar.gz") as a: a.extractall(work/"trivybin",filter="data")
        binary=next((work/"trivybin").rglob("trivy"))
        sample=work/"sample"; sample.mkdir()
        (sample/"Dockerfile").write_text("FROM ubuntu:latest\nRUN apt-get update\n")
        cmd([str(binary),"config","--skip-check-update","--skip-version-check","--format","json","--output",str(work/"trivy.json"),str(sample)],work,timeout=120)
        v=json.loads((work/"trivy.json").read_text())
        n=sum(len(x.get("Misconfigurations") or []) for x in v.get("Results",[])); check(n>0,"No fixture misconfiguration detected")
        return {"misconfigurations":n,"scope":"offline misconfiguration; vulnerability DB scan not tested"}
    if engine == "tabula":
        from reportlab.pdfgen import canvas
        p=work/"table.pdf"; c=canvas.Canvas(str(p))
        for x in (72,172,272): c.line(x,650,x,710)
        for y in (650,680,710): c.line(72,y,272,y)
        for x,y,t in [(85,690,"A"),(185,690,"B"),(85,660,"1"),(185,660,"2")]: c.drawString(x,y,t)
        c.save()
        download("https://github.com/tabulapdf/tabula-java/releases/download/v1.0.5/tabula-1.0.5-jar-with-dependencies.jar",work/"tabula.jar",20000000,"2161e3fff65939d7ce0812479cf9ca36860db5697f7fc1fa01161ed4092a0745")
        v=cmd(["java","-Xmx512m","-jar",str(work/"tabula.jar"),"-l","-p","1","-f","CSV",str(p)],work)
        check("A,B" in v and "1,2" in v,"Table extraction mismatch: "+v[-500:])
        return {"columns":["A","B"],"row":[1,2]}
    if engine == "mediapipe":
        import mediapipe as mp, numpy as np
        with mp.solutions.hands.Hands(static_image_mode=True,max_num_hands=1) as m:
            v=m.process(np.zeros((128,128,3),dtype=np.uint8))
        check(not v.multi_hand_landmarks,"Unexpected hand on blank frame")
        return {"blank_frame_hands":0,"local_inference":True}
    if engine == "sam2":
        import torch
        from PIL import Image,ImageDraw
        from transformers import Sam2Model,Sam2Processor
        model=hf("facebook/sam2.1-hiera-tiny","de431c4043854a71d8101e17995dfe596bf101a5",work/"model",["*.json","model.safetensors"])
        im=Image.new("RGB",(128,128),"white"); ImageDraw.Draw(im).rectangle((32,32,96,96),fill="red")
        p=Sam2Processor.from_pretrained(model,local_files_only=True)
        m=Sam2Model.from_pretrained(model,local_files_only=True).eval()
        with torch.inference_mode():
            out=m(**p(images=im,input_boxes=[[[30,30,98,98]]],return_tensors="pt"))
        check(out.pred_masks.numel()>0 and torch.isfinite(out.pred_masks).all().item(),"Invalid segmentation masks")
        check(torch.isfinite(out.iou_scores).all().item(),"Invalid scores")
        return {"mask_shape":list(out.pred_masks.shape),"device":"cpu"}
    if engine == "whisperx":
        import whisperx
        model=hf("facebook/wav2vec2-base-960h","22aad52d435eb6dbaf354bdad9b0da84ce7d6156",work/"align",["*.json","model.safetensors","vocab.json"])
        cmd(["espeak-ng","-w",str(work/"speech.wav"),"hello world"],work)
        cmd(["ffmpeg","-loglevel","error","-i",str(work/"speech.wav"),"-ar","16000","-ac","1",str(work/"audio.wav")],work)
        audio=whisperx.load_audio(str(work/"audio.wav")); duration=len(audio)/16000
        m,meta=whisperx.load_align_model(language_code="en",device="cpu",model_name=model)
        v=whisperx.align([{"start":0.0,"end":duration,"text":"hello world"}],m,meta,audio,"cpu",return_char_alignments=False)
        words=[w for w in v["word_segments"] if "start" in w and "end" in w]
        check(len(words)>=1 and all(0<=w["start"]<=w["end"]<=duration+.1 for w in words),"Invalid alignment")
        return {"words":len(words),"duration_s":duration,"device":"cpu"}
    if engine == "rmg_py":
        image="reactionmechanismgenerator/rmg@sha256:30ef9094a74b090cd6623747dfff85bf9d763429544f75f26515d4d61804fde8"
        code="from rmgpy.kinetics import Arrhenius; print(Arrhenius(A=(1e7,'s^-1'),n=0,Ea=(0,'J/mol'),T0=(1,'K')).get_rate_coefficient(300))"
        v=float(cmd(["docker","run","--rm","--network","none",image,"python","-c",code],work,timeout=180).strip().splitlines()[-1])
        close(v,1e7,.01)
        return {"arrhenius_rate_s_inv":v}
    if engine == "su2":
        import zipfile
        download("https://github.com/su2code/SU2/releases/download/v8.3.0/SU2-v8.3.0-linux64.zip",work/"su2.zip",100000000,"7fabe31817f42eb2b96ffe540d0693b7087b31fcc0547033e2a6db3a64360424")
        with zipfile.ZipFile(work/"su2.zip") as z:
            check(all((work/"su2"/n).resolve().is_relative_to(work/"su2") for n in z.namelist()),"Invalid archive")
            z.extractall(work/"su2")
        exe=next((work/"su2").rglob("SU2_CFD")); exe.chmod(0o700)
        os.environ["LD_LIBRARY_PATH"]=str(exe.parent)+":"+str(exe.parent.parent/"lib")
        (work/"mesh.su2").write_text("NDIME= 2\nNELEM= 4\n9 0 1 4 3 0\n9 1 2 5 4 1\n9 3 4 7 6 2\n9 4 5 8 7 3\nNPOIN= 9\n0 0 0\n1 0 1\n2 0 2\n0 1 3\n1 1 4\n2 1 5\n0 2 6\n1 2 7\n2 2 8\nNMARK= 1\nMARKER_TAG= far\nMARKER_ELEMS= 8\n3 0 1\n3 1 2\n3 2 5\n3 5 8\n3 8 7\n3 7 6\n3 6 3\n3 3 0\n")
        (work/"flow.cfg").write_text("SOLVER= EULER\nMATH_PROBLEM= DIRECT\nMACH_NUMBER= 0.3\nAOA= 0\nFREESTREAM_TEMPERATURE= 288.15\nFREESTREAM_PRESSURE= 101325\nMARKER_FAR= ( far )\nNUM_METHOD_GRAD= GREEN_GAUSS\nCONV_NUM_METHOD_FLOW= ROE\nMUSCL_FLOW= NO\nTIME_DISCRE_FLOW= EULER_IMPLICIT\nITER= 5\nCFL_NUMBER= 1\nMESH_FILENAME= mesh.su2\nMESH_FORMAT= SU2\nOUTPUT_FILES= ( RESTART )\nHISTORY_OUTPUT= ( ITER, RMS_RES )\nCONV_FILENAME= history\n")
        v=cmd([str(exe),"flow.cfg"],work,timeout=120)
        check((work/"history.csv").is_file(),"Missing CFD convergence history")
        return {"history_bytes":(work/"history.csv").stat().st_size,"cells":4}
    raise ValueError("Unapproved engine")

def main():
    if len(sys.argv)!=2:
        raise SystemExit("One reviewed engine ID required")
    os.environ.update(OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1",NUMBA_NUM_THREADS="1",TF_NUM_INTRAOP_THREADS="1",TF_NUM_INTEROP_THREADS="1",CUDA_VISIBLE_DEVICES="",PYBAMM_DISABLE_TELEMETRY="true",HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1",DO_NOT_TRACK="1")
    with tempfile.TemporaryDirectory(prefix="zeibael-expansion-") as path:
        values=run(sys.argv[1],Path(path))
    result={"engine":sys.argv[1],"status":"success","input":"public_synthetic","values":values}
    out=Path(os.environ["ZEIBAEL_OUTPUT_DIR"])/"files"; out.mkdir(parents=True,exist_ok=True)
    (out/"engine_result.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print("ZEIBAEL_ENGINE_RESULT="+json.dumps(result,allow_nan=False))

if __name__=="__main__":
    main()
