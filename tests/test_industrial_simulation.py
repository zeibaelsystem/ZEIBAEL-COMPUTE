"""Public industrial-simulation engine regression/contract checks."""
import math
import unittest
from pathlib import Path

from scripts.job_plan import read_manifest
from scripts.industrial_simulation import (
    validate_equilibrium, validate_rc_samples, parse_calculix_dat,
)

ROOT = Path(__file__).resolve().parents[1]


class IndustrialSimulationManifestTests(unittest.TestCase):
    def test_three_engines_use_public_bounded_ubuntu_jobs(self):
        jobs = read_manifest(ROOT, "industrial_simulation_smoke")["jobs"]
        self.assertEqual({j["id"] for j in jobs},
                         {"thermochemistry_cantera", "circuit_ngspice", "structural_calculix"})
        for job in jobs:
            self.assertEqual(job["runtime"], "python")
            self.assertEqual(job["runner"], "ubuntu-24.04")
            self.assertTrue(job["output_files"])
            self.assertEqual(job["requirements"]["os"], "linux")
            self.assertEqual(job["requirements"]["arch"], "x64")
            self.assertLessEqual(job["requirements"]["output_mb"], 3)
            self.assertLessEqual(len(job["commands"]), 4)
            self.assertTrue(any(any(x.endswith("industrial_simulation.py") for x in c)
                                for c in job["commands"]))
        self.assertTrue(any("cantera==3.2.0" in c for c in jobs[0]["commands"]))
        self.assertTrue(any(any(x.endswith("install_industrial_solvers.sh") for x in c)
                            for j in jobs[1:] for c in j["commands"]))

    def test_only_committed_public_fixture_models(self):
        required = ("ci/fixtures/industrial/rc_charge.cir",
                    "ci/fixtures/industrial/cantilever_demo.inp",
                    "ci/jobs/install_industrial_solvers.sh")
        for path in required:
            self.assertTrue((ROOT / path).is_file(), path)
        fixture = (ROOT / "ci/fixtures/industrial/cantilever_demo.inp").read_text()
        self.assertIn("*NODE PRINT", fixture)
        self.assertIn("*STATIC", fixture)
        self.assertIn("*BOUNDARY", fixture)
        self.assertIn("*CLOAD", fixture)


class IndustrialSimulationValidationTests(unittest.TestCase):
    def test_rc_transient_expected_time_constant(self):
        report = validate_rc_samples([
            (0.0, 0.0), (0.0005, .393), (0.001, .632),
            (0.002, .865), (0.005, .993), (.020, 1.0)
        ], resistance_ohm=1000, capacitance_f=1e-6)
        self.assertAlmostEqual(report["tau_seconds"], .001)
        self.assertTrue(report["passed"])

    def test_rc_rejects_nonmonotonic_or_invalid(self):
        with self.assertRaises(ValueError):
            validate_rc_samples([(0, 0), (0.001, .63), (0.001, .9)], 1000, 1e-6)
        with self.assertRaises(ValueError):
            validate_rc_samples([(0, 0), (0.001, float("nan"))], 1000, 1e-6)
        with self.assertRaises(ValueError):
            validate_rc_samples([(0, 0), (0.001, -2), (.02, 1)], 1000, 1e-6)

    def test_equilibrium_checks_enthalpy_and_elements(self):
        report = validate_equilibrium(
            initial_temperature=300, final_temperature=2220,
            relative_enthalpy_error=1e-8, max_element_mass_fraction_delta=1e-9,
        )
        self.assertTrue(report["passed"])
        with self.assertRaises(ValueError):
            validate_equilibrium(300, 2250, 0.1, 1e-9)
        with self.assertRaises(ValueError):
            validate_equilibrium(300, 2250, 1e-10, 0.1)

    def test_calculix_dat_parser_validates_reactions_and_displacements(self):
        content = """\
 forces (fx,fy,fz) for set FIX and time 1.000000E+00

 1  0.0  100.0  0.0
 4  0.0  100.0  0.0
 5  0.0  100.0  0.0
 8  0.0  100.0  0.0

 displacements (vx,vy,vz) for set LOADED and time 1.000000E+00

 2  0.0  -0.012  0.0
 3  0.0  -0.014  0.0
 6  0.0  -0.012  0.0
 7  0.0  -0.014  0.0
"""
        report = parse_calculix_dat(content, target_reaction_n=400)
        self.assertTrue(report["passed"])
        self.assertAlmostEqual(report["reaction_y_newton"], 400.0)
        self.assertLess(report["mean_loaded_y_mm"], 0)

    def test_calculix_dat_parser_fails_closed_on_missing_or_wrong_sign(self):
        with self.assertRaises(ValueError):
            parse_calculix_dat("no simulation results", target_reaction_n=400)
        bad = """\
 forces (fx,fy,fz) for set FIX and time 1.0
 1 0.0 400.0 0.0

 displacements (vx,vy,vz) for set LOADED and time 1.0
 2 0.0 0.01 0.0
"""
        with self.assertRaises(ValueError):
            parse_calculix_dat(bad, target_reaction_n=400)


if __name__ == "__main__":
    unittest.main()
