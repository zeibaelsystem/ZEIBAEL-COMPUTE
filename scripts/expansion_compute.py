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
