# Extended compute engines — 15 runtime smoke checks passed

Existing public modular CI only; each `engine_<id>` manifest selects a single engine and uses a synthetic public fixture. `extended_compute_smoke` runs 15 jobs together. Use the existing dispatcher, not a new service. Install packages only on temporary standard public Ubuntu runners. CPU-only PyTorch/ONNX. Docker images run without networking after anonymous pull, no registry login, no billing; stop if the public pull fails. The DWSIM 10.2 image is a mutable upstream release-series tag: do not treat it as immutable; resolve and record digest during validation. Do not use Patreon, licensed services, paid compute or arbitrary input. OpenModelica is the public upstream minimal image; DWSIM official headless GPL-3 engine: https://dwsim.org/download/ . No production plant data, private strategies, customer files or credentials.

| Engine ID | Reference calculation |
|---|---|
| openfoam | finite-volume 1D diffusion, ten-cell reference field |
| coolprop | water density and boiling point |
| dwsim | headless MCP Water → Mixer, mass and temperature |
| sympy | exact polynomial roots and integral |
| opencv | synthetic image segmentation |
| tesseract | fixed public text OCR |
| duckdb | SQL count/sum |
| polars | grouped aggregation |
| quantlib | continuously compounded discount factor |
| vectorbt | four-point synthetic portfolio, not market performance |
| pytorch | CPU autograd |
| onnxruntime | CPU Add model inference |
| openmodelica | first-order ODE decay |
| gmsh | square mesh |
| lammps | 32-atom Lennard-Jones energy drift |

Each candidate writes an engine_result.json only on successful reference checks. All 15 reference checks passed on the tested commit. Use the individual manifest for the matching task; custom production models require a separate reviewed public-safe job. No GPU or PaddleOCR claim. Existing routes unchanged.

## Runtime evidence

[Run #45453112160](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45453112160) — 15/15 engines passed, all exit code 0. [Structured evidence](../ci/evidence/extended_compute_2026-11-25.json) contains per-engine job IDs and numerical results. Regression job passed (165 Python tests discovered: 163 passed, 2 pre-existing skips; 14 Node tests passed). The temporary PR matrix was removed after verification; the original modular CI workflow is unchanged. No always-on service or new dispatcher. Tested on Linux x64 only. Image tags are recorded with their observed digest; future pulls must be treated as a new dependency version if the digest changes.
