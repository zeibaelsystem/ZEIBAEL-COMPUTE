# Extended compute engines — candidate, not yet runtime verified

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

Each candidate writes an engine_result.json only on successful reference checks. Source presence is not runtime verification; use actual run IDs and per-job outcomes before declaring an engine ACTIVE. No GPU or PaddleOCR claim. Existing routes unchanged.
