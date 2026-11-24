"""Bounded public synthetic compute smoke tests. No external credentials or paid APIs."""
import csv
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

def check(condition, message):
    if not condition:
        raise RuntimeError(message)

def close(actual, expected, tolerance=1e-6):
    check(math.isfinite(float(actual)) and abs(float(actual)-expected) <= tolerance,
          f"Expected {expected}, got {actual}")

def command(args, cwd, timeout=180):
    completed = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=timeout, check=False)
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}): {completed.stdout[-8000:]}")
    return completed.stdout

def run_engine(engine, work):
    work = Path(work).resolve()
    if engine == "coolprop":
        from CoolProp.CoolProp import PropsSI
        density = PropsSI("D", "T", 298.15, "P", 101325, "Water")
        boiling = PropsSI("T", "P", 101325, "Q", 0, "Water")
        close(density, 997.05, 0.2)
        close(boiling, 373.124, 0.1)
        return {"density_kg_m3": density, "boiling_K": boiling}
    if engine == "sympy":
        import sympy as s
        x = s.symbols("x")
        roots = s.solve(x*x-5*x+6, x)
        integral = s.integrate(x*x, (x, 0, 3))
        check(roots == [2, 3] and integral == 9, "Symbolic reference mismatch")
        return {"roots": list(map(int, roots)), "integral": int(integral)}
    if engine == "opencv":
        import cv2
        import numpy as np
        image = np.zeros((100, 100), dtype=np.uint8)
        cv2.rectangle(image, (20, 20), (59, 59), 255, -1)
        count, labels, stats, centers = cv2.connectedComponentsWithStats(image)
        check(count == 2 and int(stats[1, cv2.CC_STAT_AREA]) == 1600, "Wrong segmentation")
        return {"foreground_pixels": int(stats[1, cv2.CC_STAT_AREA]), "components": count-1}
    if engine == "tesseract":
        command(["convert", "-size", "1000x200", "xc:white", "-font",
                 "DejaVu-Sans", "-pointsize", "70", "-fill", "black",
                 "-gravity", "center", "-annotate", "0", "ZEIBAEL 12345",
                 str(work/"ocr.png")], work)
        result = command(["tesseract", str(work/"ocr.png"), "stdout", "-l", "eng", "--psm", "7"], work)
        check("ZEIBAEL 12345" in result, "OCR reference not recognized")
        return {"recognized": "ZEIBAEL 12345"}
    if engine == "duckdb":
        import duckdb
        with duckdb.connect(":memory:") as con:
            result = con.execute("SELECT count(*), sum(i) FROM range(1, 10001) t(i)").fetchone()
        check(result == (10000, 50005000), "SQL reference mismatch")
        return {"rows": result[0], "sum": result[1]}
    if engine == "polars":
        import polars as pl
        values = pl.DataFrame({"group": ["a","a","b"], "x": [2,3,7]})
        result = values.group_by("group").agg(pl.col("x").sum()).sort("group").to_dict(as_series=False)
        check(result == {"group":["a","b"],"x":[5,7]}, "Dataframe reference mismatch")
        return result
    if engine == "quantlib":
        import QuantLib as q
        today = q.Date(1, 1, 2025)
        daycount = q.Actual365Fixed()
        curve = q.FlatForward(today, 0.05, daycount, q.Continuous)
        discount = curve.discount(today+365)
        close(discount, math.exp(-0.05))
        return {"discount_factor": discount, "zero_rate": 0.05}
    if engine == "vectorbt":
        import pandas as pd
        import vectorbt as vbt
        price = pd.Series([10., 11., 12., 13.])
        portfolio = vbt.Portfolio.from_signals(price,
             entries=pd.Series([True,False,False,False]),
             exits=pd.Series([False,False,False,True]), init_cash=100., fees=0., freq="1D")
        result = float(portfolio.total_return())
        close(result, 0.3)
        return {"synthetic_total_return": result, "fees": 0, "not_market_evidence": True}
    if engine == "pytorch":
        import torch
        torch.set_num_threads(1)
        x = torch.tensor([1.,2.,3.], requires_grad=True)
        loss = (x*x).sum()
        loss.backward()
        check(x.grad.tolist() == [2.,4.,6.], "Autograd mismatch")
        return {"loss": loss.item(), "gradient": x.grad.tolist(), "device": "cpu"}
    if engine == "onnxruntime":
        import numpy as np
        import onnx
        from onnx import helper, TensorProto
        import onnxruntime as ort
        inputs = [helper.make_tensor_value_info(n, TensorProto.FLOAT, [2]) for n in ("a","b")]
        outputs = [helper.make_tensor_value_info("c", TensorProto.FLOAT, [2])]
        graph = helper.make_graph([helper.make_node("Add", ["a","b"], ["c"])], "public_add", inputs, outputs)
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=9)
        onnx.checker.check_model(model)
        session = ort.InferenceSession(model.SerializeToString(), providers=["CPUExecutionProvider"])
        result = session.run(None, {"a":np.array([1,2],np.float32),"b":np.array([3,4],np.float32)})[0].tolist()
        check(result == [4.,6.], "ONNX inference mismatch")
        return {"output": result, "provider": "CPUExecutionProvider"}
    if engine == "gmsh":
        (work/"square.geo").write_text('SetFactory("OpenCASCADE"); Rectangle(1) = {0,0,0,1,1}; Mesh.CharacteristicLengthMax=0.3;\n')
        command(["gmsh", "square.geo", "-2", "-format", "msh2", "-o", "square.msh", "-nt", "1"], work)
        mesh = (work/"square.msh").read_text()
        nodes = int(mesh.split("$Nodes\n")[1].splitlines()[0])
        elements = int(mesh.split("$Elements\n")[1].splitlines()[0])
        check(nodes > 4 and elements > 4, "Invalid mesh")
        return {"nodes":nodes,"elements":elements}
    if engine == "lammps":
        (work/"in.smoke").write_text("""units lj
atom_style atomic
lattice fcc 0.8442
region box block 0 2 0 2 0 2
create_box 1 box
create_atoms 1 box
mass 1 1.0
velocity all create 1.44 87287 loop geom
pair_style lj/cut 2.5
pair_coeff 1 1 1.0 1.0 2.5
fix integrator all nve
thermo 5
thermo_style custom step atoms temp etotal
run 10
print "ZEIBAEL_LAMMPS_COMPLETE"
""")
        output = command(["lmp", "-in", "in.smoke", "-log", "none"], work)
        check("ZEIBAEL_LAMMPS_COMPLETE" in output, "LAMMPS did not finish")
        rows = re.findall(r"^\s*(\d+)\s+(\d+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*$", output, re.M)
        check(len(rows)>=3 and rows[-1][0]=="10" and rows[-1][1]=="32", "LAMMPS trajectory mismatch")
        check(abs(float(rows[-1][3])-float(rows[0][3]))<0.05,"Excessive energy drift")
        return {"steps":10,"atoms":32,"energy_initial":float(rows[0][3]),"energy_final":float(rows[-1][3])}
    if engine == "openmodelica":
        (work/"Decay.mo").write_text("model Decay\n Real x(start=1, fixed=true);\n equation der(x)=-x;\nend Decay;\n")
        (work/"smoke.mos").write_text('loadFile("Decay.mo");\nsimulate(Decay, stopTime=1, numberOfIntervals=20, outputFormat="csv");\ngetErrorString();\n')
        command(["docker","run","--rm","--network","none","--user",f"{os.getuid()}:{os.getgid()}",
                 "-e","HOME=/tmp","-v",f"{work}:/work","-w","/work","--entrypoint","omc",
                 "openmodelica/openmodelica:v1.27.1-minimal","smoke.mos"],work,timeout=300)
        with (work/"Decay_res.csv").open() as f:
            rows=list(csv.DictReader(f))
        final=float(rows[-1]["x"])
        close(final,math.exp(-1),0.002)
        return {"x_at_t1":final,"expected":math.exp(-1)}
    if engine == "openfoam":
        return openfoam(work)
    if engine == "dwsim":
        return dwsim(work)
    raise ValueError("Unapproved engine")

def openfoam(work):
    # Small 1D diffusion problem; cell-centre values approach linear profile.
    for folder in ("system","constant","0"):
        (work/folder).mkdir()
    def put(path, body, cls="dictionary"):
        name=Path(path).name
        (work/path).write_text(f"FoamFile {{ version 2.0; format ascii; class {cls}; object {name}; }}\n"+body)
    put("system/blockMeshDict", """convertToMeters 1;
vertices ((0 0 0) (1 0 0) (1 0.1 0) (0 0.1 0) (0 0 0.1) (1 0 0.1) (1 0.1 0.1) (0 0.1 0.1));
blocks (hex (0 1 2 3 4 5 6 7) (10 1 1) simpleGrading (1 1 1));
edges ();
boundary (left {type patch; faces ((0 4 7 3));} right {type patch; faces ((1 2 6 5));} sides {type wall; faces ((0 1 5 4) (3 7 6 2) (0 3 2 1) (4 5 6 7));});
mergePatchPairs ();
""")
    put("system/controlDict", """application laplacianFoam; startFrom startTime; startTime 0; stopAt endTime; endTime 2; deltaT 0.1; writeControl timeStep; writeInterval 20; writeFormat ascii; runTimeModifiable false;""")
    put("system/fvSchemes", """ddtSchemes {default Euler;} gradSchemes {default Gauss linear;} divSchemes {default none;} laplacianSchemes {default Gauss linear corrected;} interpolationSchemes {default linear;} snGradSchemes {default corrected;}""")
    put("system/fvSolution", """solvers { T {solver PCG; preconditioner DIC; tolerance 1e-10; relTol 0;} } SIMPLE {nNonOrthogonalCorrectors 0;}""")
    put("constant/transportProperties","DT DT [0 2 -1 0 0 0 0] 1;")
    put("0/T", """dimensions [0 0 0 1 0 0 0]; internalField uniform 0; boundaryField {left {type fixedValue; value uniform 0;} right {type fixedValue; value uniform 1;} sides {type zeroGradient;}}""","volScalarField")
    script=work/"run_foam.sh"
    script.write_text("""#!/bin/bash
set -e
if [ -f /usr/share/openfoam/etc/bashrc ]; then
  source /usr/share/openfoam/etc/bashrc
fi
blockMesh
laplacianFoam
""")
    command(["bash",str(script)],work,timeout=300)
    output=(work/"2"/"T").read_text()
    match=re.search(r"internalField\s+nonuniform\s+List<scalar>\s+10\s*\(([^)]+)\)",output,re.S)
    check(match is not None,"Missing calculated temperature field")
    values=[float(v) for v in match.group(1).split()]
    check(len(values)==10 and all(0<v<1 for v in values),"Invalid diffusion field")
    check(abs(min(values)-0.05)<0.02 and abs(max(values)-0.95)<0.02,"Diffusion reference mismatch")
    return {"cells":10,"min":min(values),"max":max(values),"fixture":"1D diffusion"}

def dwsim(work):
    # Official headless server, stdio only: no published port or network.
    import selectors
    process=subprocess.Popen(["docker","run","--rm","-i","--network","none",
                             "ghcr.io/danwbr/dwsim-mcp:10.2","--stdio"],
                             cwd=work,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL,bufsize=0)
    buffer=b""
    counter=0
    def request(method, params=None, notification=False):
        nonlocal buffer,counter
        counter+=1
        payload={"jsonrpc":"2.0","method":method}
        if params is not None: payload["params"]=params
        if not notification: payload["id"]=counter
        process.stdin.write((json.dumps(payload)+"\n").encode())
        if notification: return None
        import time
        deadline=time.monotonic()+90
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout,selectors.EVENT_READ)
            while time.monotonic()<deadline:
                if b"\n" in buffer:
                    line,buffer=buffer.split(b"\n",1)
                    try: message=json.loads(line)
                    except ValueError: continue
                    if message.get("id")!=counter: continue
                    check("error" not in message,f"MCP {method}: {message.get('error')}")
                    return message["result"]
                events=selector.select(max(0,deadline-time.monotonic()))
                check(bool(events),"MCP response timeout")
                chunk=os.read(process.stdout.fileno(),65536)
                check(bool(chunk),"MCP closed stdout")
                buffer+=chunk
                check(len(buffer)<2_000_000,"MCP response too large")
        raise RuntimeError("MCP response timeout")
    def call(name,**kwargs):
        result=request("tools/call",{"name":name,"arguments":kwargs})
        check(not result.get("isError"),f"DWSIM tool {name} failed: {result}")
        value=result.get("structuredContent")
        if value is None:
            value=json.loads(next(c["text"] for c in result["content"] if c["type"]=="text"))
        check(isinstance(value,dict),f"Unexpected result from {name}")
        check(value.get("ok") is not False and not value.get("error"),f"{name}: {value}")
        return value
    try:
        request("initialize",{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"zeibael-smoke","version":"1"}})
        request("notifications/initialized",notification=True)
        listed=request("tools/list")
        names={t["name"] for t in listed["tools"]}
        check("dwsim_solve_run" in names,"Missing DWSIM solver")
        created=call("dwsim_flowsheet_create",name="Public water mixer")
        flow=created.get("flowsheet_id") or created.get("id")
        check(isinstance(flow,str) and bool(flow),"Missing flowsheet ID")
        call("dwsim_thermo_add_compounds",flowsheet_id=flow,names=["Water"])
        call("dwsim_thermo_set_property_package",flowsheet_id=flow,name="Steam Tables (IAPWS-IF97)")
        call("dwsim_stream_add_material",flowsheet_id=flow,name="Feed",temperature_K=298.15,pressure_Pa=101325,mass_flow_kg_s=1.0,composition={"Water":1.0})
        call("dwsim_stream_add_material",flowsheet_id=flow,name="Product")
        call("dwsim_unitop_add",flowsheet_id=flow,type="Mixer",name="M1")
        call("dwsim_unitop_connect",flowsheet_id=flow,unitop="M1",feed_stream="Feed",feed_port=0,product_stream="Product",product_port=0)
        ready=call("dwsim_flowsheet_check",flowsheet_id=flow)
        check(ready.get("ready") is True,"Flowsheet not ready")
        solved=call("dwsim_solve_run",flowsheet_id=flow,timeout_s=30)
        check(solved.get("ok") is True,"Flowsheet solve failed")
        product=call("dwsim_stream_get_results",flowsheet_id=flow,name="Product")
        # Exact API field variants are intentionally fail-closed.
        mass=product.get("mass_flow_kg_s")
        temp=product.get("temperature_K")
        close(mass,1.0,1e-4)
        close(temp,298.15,0.5)
        call("dwsim_flowsheet_close",flowsheet_id=flow)
        return {"mass_flow_kg_s":mass,"temperature_K":temp,"tool_count":len(names)}
    finally:
        process.stdin.close()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)

def main():
    if len(sys.argv)!=2:
        raise SystemExit("One reviewed engine ID required")
    engine=sys.argv[1]
    with tempfile.TemporaryDirectory(prefix="zeibael-engine-") as directory:
        values=run_engine(engine, Path(directory))
    output=Path(os.environ["ZEIBAEL_OUTPUT_DIR"])/"files"
    output.mkdir(parents=True,exist_ok=True)
    result={"engine":engine,"status":"success","input":"public_synthetic","values":values}
    (output/"engine_result.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    print("ZEIBAEL_ENGINE_RESULT="+json.dumps(result,allow_nan=False))

if __name__=="__main__":
    main()
