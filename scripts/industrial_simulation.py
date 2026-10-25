#!/usr/bin/env python3
"""Three bounded, public-fixture engineering software smoke tests.

These are numerical regression checks, not validated plant/process/electrical/
structural designs. Never load personal, proprietary or production models.
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "ci" / "fixtures" / "industrial"


def _number(value):
    return float(value.replace("D", "E").replace("d", "e"))


def validate_equilibrium(initial_temperature, final_temperature,
                         relative_enthalpy_error, max_element_mass_fraction_delta):
    values = (initial_temperature, final_temperature,
              relative_enthalpy_error, max_element_mass_fraction_delta)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               and math.isfinite(v) for v in values):
        raise ValueError("Nonfinite thermochemistry state")
    if (not 250 <= initial_temperature <= 600
        or not 1000 <= final_temperature <= 3500
        or not final_temperature > initial_temperature
        or not 0 <= relative_enthalpy_error <= 1e-5
        or not 0 <= max_element_mass_fraction_delta <= 1e-8):
        raise ValueError("Cantera equilibrium did not satisfy public numerical check")
    return {
        "passed": True,
        "initial_temperature_kelvin": round(initial_temperature, 6),
        "equilibrium_temperature_kelvin": round(final_temperature, 6),
        "relative_enthalpy_error": relative_enthalpy_error,
        "maximum_element_mass_fraction_delta": max_element_mass_fraction_delta,
    }


def validate_rc_samples(samples, resistance_ohm, capacitance_f):
    if (not isinstance(samples, (list, tuple)) or not 5 <= len(samples) <= 5000
        or not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                   and math.isfinite(v) and v > 0
                   for v in (resistance_ohm, capacitance_f))):
        raise ValueError("Invalid RC fixture or parameters")
    time_constant = resistance_ohm * capacitance_f
    if not 1e-8 <= time_constant <= .1:
        raise ValueError("Out of bounded public RC time constant range")
    previous_t = -1.
    parsed = []
    for t, v in samples:
        if not (math.isfinite(t) and math.isfinite(v) and t > previous_t
                and -.02 <= v <= 1.2):
            raise ValueError("Invalid, nonmonotonic or nonfinite RC transient")
        parsed.append((t, v))
        previous_t = t
    if parsed[0][0] > 0.1 * time_constant or parsed[-1][0] < 5 * time_constant:
        raise ValueError("RC transient does not span the expected time constant")
    tau_index = next((i for i, (t, _) in enumerate(parsed) if t >= time_constant), None)
    if tau_index is None or tau_index == 0:
        raise ValueError("Missing time constant data")
    lo = parsed[tau_index - 1]
    hi = parsed[tau_index]
    voltage_tau = lo[1] + (time_constant - lo[0]) * (hi[1] - lo[1]) / (hi[0] - lo[0])
    if not (abs(voltage_tau - (1-math.exp(-1))) <= 0.08
            and abs(parsed[0][1]) < .1
            and .98 <= parsed[-1][1] <= 1.02):
        raise ValueError("ngspice RC charging trace disagrees with analytical benchmark")
    return {
        "passed": True,
        "resistance_ohm": resistance_ohm,
        "capacitance_farad": capacitance_f,
        "tau_seconds": time_constant,
        "voltage_at_tau": round(voltage_tau, 9),
        "voltage_final": round(parsed[-1][1], 9),
        "sample_count": len(parsed),
    }


def _rows_after_header(dat_text, signature, set_name):
    lines = dat_text.splitlines()
    matches = [i for i, line in enumerate(lines)
               if signature in line.lower() and ("for set " + set_name.lower()) in line.lower()]
    if not matches:
        raise ValueError("CalculiX output missing required set: " + set_name)
    rows = []
    for line in lines[matches[-1] + 1:]:
        parts = line.strip().split()
        if not parts:
            if rows:
                break
            continue
        if len(parts) >= 4 and parts[0].isdigit():
            try:
                values = [_number(x) for x in parts[1:4]]
            except ValueError:
                if rows:
                    break
                continue
            if not all(math.isfinite(v) for v in values):
                raise ValueError("Nonfinite CalculiX result")
            rows.append((int(parts[0]), *values))
        elif rows:
            break
    if not rows:
        raise ValueError("Empty CalculiX results: " + set_name)
    return rows


def parse_calculix_dat(dat_text, target_reaction_n=400):
    if not isinstance(dat_text, str) or len(dat_text) > 2_000_000:
        raise ValueError("Invalid or oversized CalculiX result")
    reactions = _rows_after_header(dat_text, "forces (fx,fy,fz)", "FIX")
    displacement = _rows_after_header(dat_text, "displacements (vx,vy,vz)", "LOADED")
    if len(reactions) != 4 or len(displacement) != 4:
        raise ValueError("Unexpected node count in public FEA fixture")
    fy = sum(row[2] for row in reactions)
    dy = sum(row[2] for row in displacement) / len(displacement)
    if (not math.isfinite(fy) or not math.isfinite(dy)
        or not math.isclose(fy, target_reaction_n, rel_tol=.025, abs_tol=1)
        or not -1 < dy < 0):
        raise ValueError("CalculiX FEA reaction or displacement failed equilibrium/sanity check")
    return {"passed": True, "reaction_y_newton": round(fy, 6),
            "expected_reaction_y_newton": target_reaction_n,
            "mean_loaded_y_mm": round(dy, 9),
            "fixed_nodes": len(reactions), "loaded_nodes": len(displacement),
            "note": "Single-element coarse demonstration only; mesh convergence not demonstrated"}


def _public_output():
    root = os.environ.get("ZEIBAEL_OUTPUT_DIR")
    if not root:
        raise ValueError("ZEIBAEL_OUTPUT_DIR is required")
    folder = Path(root) / "files"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _save_json(folder, name, report):
    (folder / name).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def run_cantera():
    import cantera as ct
    gas = ct.Solution("gri30.yaml")
    gas.TP = 300.0, ct.one_atm
    gas.set_equivalence_ratio(1.0, "CH4", "O2:1,N2:3.76")
    h_initial = gas.enthalpy_mass
    initial_element = {el: gas.elemental_mass_fraction(el) for el in ("C", "H", "O", "N")}
    gas.equilibrate("HP")
    relative_enthalpy_error = abs(gas.enthalpy_mass - h_initial) / max(1.0, abs(h_initial))
    max_element_delta = max(abs(gas.elemental_mass_fraction(el) - initial_element[el])
                            for el in initial_element)
    report = validate_equilibrium(300, gas.T, relative_enthalpy_error, max_element_delta)
    report.update({"engine": "cantera", "engine_version": ct.__version__,
                   "fixture": "gri30 methane/air equilibrium at constant H and P",
                   "pressure_pascal": ct.one_atm,
                   "note": "Software equilibrium regression only; not a certified process design"})
    folder = _public_output()
    _save_json(folder, "thermochemistry_summary.json", report)
    print("ZEIBAEL_THERMOCHEMISTRY_CANTERA_OK " + json.dumps(report, separators=(",", ":")))


def run_ngspice():
    source = FIXTURES / "rc_charge.cir"
    with tempfile.TemporaryDirectory(prefix="zeibael-ngspice-") as tmp:
        work = Path(tmp)
        local = work / "rc_charge.cir"
        shutil.copyfile(source, local)
        proc = subprocess.run(["ngspice", "-b", "-o", "solver.log", local.name],
                              cwd=work, timeout=90, capture_output=True,
                              text=True, errors="replace")
        trace = work / "rc_response.txt"
        if proc.returncode != 0 or not trace.is_file():
            raise ValueError("ngspice solver failed: " + (proc.stderr or proc.stdout)[-700:])
        samples = []
        for line in trace.read_text(encoding="utf-8").splitlines():
            cols = line.strip().split()
            if not cols:
                continue
            if len(cols) != 2:
                raise ValueError("Unexpected ngspice public transient columns")
            samples.append((_number(cols[0]), _number(cols[1])))
        report = validate_rc_samples(samples, resistance_ohm=1000, capacitance_f=1e-6)
        report.update({"engine": "ngspice", "fixture": "1kOhm / 1uF unit-step RC low-pass",
                       "note": "Circuit software regression, not electrical design approval"})
        folder = _public_output()
        _save_json(folder, "circuit_summary.json", report)
        with (folder / "rc_transient.csv").open("w", encoding="utf-8") as out:
            out.write("time_seconds,output_volts\n")
            for time_s, volts in samples:
                out.write(f"{time_s:.10g},{volts:.10g}\n")
    print("ZEIBAEL_CIRCUIT_NGSPICE_OK " + json.dumps(report, separators=(",", ":")))


def run_calculix():
    source = FIXTURES / "cantilever_demo.inp"
    with tempfile.TemporaryDirectory(prefix="zeibael-calculix-") as tmp:
        work = Path(tmp)
        shutil.copyfile(source, work / "cantilever_demo.inp")
        proc = subprocess.run(["ccx", "-i", "cantilever_demo"], cwd=work,
                              timeout=120, capture_output=True,
                              text=True, errors="replace")
        dat = work / "cantilever_demo.dat"
        if proc.returncode != 0 or not dat.is_file():
            raise ValueError("CalculiX solver failed: " + (proc.stderr or proc.stdout)[-700:])
        dat_text = dat.read_text(encoding="utf-8", errors="replace")
        report = parse_calculix_dat(dat_text)
        report.update({"engine": "calculix-ccx", "fixture": "1x1x1 mm C3D8 public test",
                       "young_modulus_n_mm2": 210000, "poisson_ratio": .3,
                       "applied_y_force_newton": -400})
        folder = _public_output()
        _save_json(folder, "fea_summary.json", report)
        (folder / "fea_nodal_results.dat").write_text(dat_text[:200_000], encoding="utf-8")
    print("ZEIBAEL_FINITE_ELEMENT_CALCULIX_OK " + json.dumps(report, separators=(",", ":")))


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"cantera", "ngspice", "calculix"}:
        raise SystemExit("Usage: industrial_simulation.py cantera|ngspice|calculix")
    {"cantera": run_cantera, "ngspice": run_ngspice, "calculix": run_calculix}[sys.argv[1]]()


if __name__ == "__main__":
    main()
