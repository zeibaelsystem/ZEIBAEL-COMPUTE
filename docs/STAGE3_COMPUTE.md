# Stage 3 capability expansion

66 verified public synthetic capability routes; 24 blocked; separate verified DAG smoke manifest. Prior 99 capability routes unchanged. Routes include extensions and overlapping dependencies, not 165 distinct software packages.

[Candidate ledger](../ci/stage3_candidates.json) · [Run and job evidence](../ci/evidence/stage3_2026-11-25.json).

DAG: single standard runner, max 20 nodes / four threads; local checkpoint/cache only; isolated Python environments; fresh repeat verified. No cross-run persistence, paid fallback, private inputs or production solver certification.

## Capability status

| ID | Group | Status | Scope or blocker |
|---|---|---|---|
| biosteam | chemical | blocked | Pinned ThermoSTEAM source requires colorpalette>=0.3.3 without compatible wheel. |
| qsdsan | chemical | blocked | Blocked by the same ThermoSTEAM/colorpalette dependency. |
| foqus | chemical | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| reaktoro | chemical | verified | Equilibrium solver on neutral salt solution |
| pyomo_dae | chemical | verified | DAE discretization fixture; extension, not independent engine |
| openpnm | chemical | verified | reviewed public synthetic fixture only |
| porespy | chemical | verified | reviewed public synthetic fixture only |
| fipy | chemical | verified | reviewed public synthetic fixture only |
| pyromat | chemical | verified | Air heat capacity fixture |
| phasepy | chemical | verified | Mixture property fixture |
| precice | mechanical | verified | Two-process local coupling fixture; not production OpenFOAM/CalculiX coupling |
| code_aster | mechanical | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| elmer_fem | mechanical | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| moose | mechanical | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| deal_ii | mechanical | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| mfem | mechanical | verified | Local finite element mesh integration |
| project_chrono | mechanical | verified | Local rigid body free fall |
| mbdyn | mechanical | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| pyelastica | mechanical | verified | Rod geometry/rest length fixture |
| sfepy | mechanical | blocked | Conda install passed; functional subprocess returned nonzero; cause not captured. |
| omsimulator | control | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| fmpy | control | verified | FMU metadata parsing only |
| python_control | control | verified | reviewed public synthetic fixture only |
| gekko | control | verified | reviewed public synthetic fixture only |
| pysindy | control | verified | reviewed public synthetic fixture only |
| do_mpc | control | verified | Local dynamic model simulation |
| pypsa | control | verified | reviewed public synthetic fixture only |
| gridcal | control | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| openems | control | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| pyspice | control | verified | Netlist construction only |
| sundials | math | verified | Native CVODE ODE solve |
| petsc | math | verified | Native PETSc KSP linear solve |
| trilinos | math | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| openturns | math | verified | reviewed public synthetic fixture only |
| gemseo | math | verified | Design-space fixture |
| nevergrad | math | verified | reviewed public synthetic fixture only |
| pymoo | math | verified | reviewed public synthetic fixture only |
| numba | math | verified | JIT capability; existing transitive dependency may overlap |
| mpmath | math | verified | Arbitrary-precision capability; existing transitive dependency may overlap |
| mpi4py | math | verified | reviewed public synthetic fixture only |
| lean | trading | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| nautilus_trader | trading | verified | Synthetic order-book fixture; not strategy backtest |
| zipline_reloaded | trading | verified | SMA factor fixture; not full backtest |
| backtesting_py | trading | verified | Synthetic strategy fixture; AGPL conditions apply |
| sktime | trading | verified | reviewed public synthetic fixture only |
| mlforecast | trading | verified | reviewed public synthetic fixture only |
| neuralforecast | trading | verified | Local CPU training/prediction |
| pytorch_forecasting | trading | verified | Synthetic dataset windows |
| hmmlearn | trading | verified | reviewed public synthetic fixture only |
| ruptures | trading | verified | reviewed public synthetic fixture only |
| openvino | ai | verified | reviewed public synthetic fixture only |
| ncnn | ai | verified | Locally constructed CPU ReLU inference |
| mnn | ai | verified | Local tensor operations only |
| ctranslate2 | ai | blocked | Already a dependency of existing faster-whisper path; standalone fixture not yet qualified. |
| mlflow | ai | verified | Local experiment metadata and metric persistence |
| dvc | ai | verified | Local versioned data restore, no remote |
| pyod | ai | verified | reviewed public synthetic fixture only |
| river | ai | verified | reviewed public synthetic fixture only |
| pyg | ai | verified | CPU graph convolution |
| tsfresh | ai | verified | reviewed public synthetic fixture only |
| pymupdf | media | verified | Local PDF fixture; AGPL conditions apply |
| pyav | media | verified | reviewed public synthetic fixture only |
| gstreamer | media | verified | Generated local audio pipeline |
| mediainfo | media | verified | Local metadata extraction |
| essentia | media | blocked | AGPL scope and CPU distribution wheel not yet qualified. |
| opensmile | media | blocked | Commercial use license restriction; not unconditional free. |
| easyocr | media | blocked | Model weights and CPU runtime not qualified. |
| rapidocr | media | blocked | Model weight/license and runtime need separate validation. |
| layoutparser | media | verified | Local document geometry |
| opentimelineio | media | verified | reviewed public synthetic fixture only |
| spark | data | verified | Local Spark aggregation |
| flink | data | blocked | Dependency resolution blocked by Apache Beam dill<0.3.2 requirement. |
| datafusion | data | verified | reviewed public synthetic fixture only |
| ibis | data | verified | reviewed public synthetic fixture only |
| zarr | data | verified | reviewed public synthetic fixture only |
| hdf5 | data | verified | reviewed public synthetic fixture only |
| vaex | data | verified | Local dataframe aggregation |
| nats | data | verified | Local loopback messaging |
| snakemake | data | verified | reviewed public synthetic fixture only |
| nextflow | data | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| quantum_espresso | science | blocked | No reviewed executable distribution and functional fixture admitted yet. |
| cp2k | science | blocked | Ubuntu package unavailable on reviewed runner. |
| gromacs | science | verified | Trajectory-distance fixture |
| openmm | science | verified | reviewed public synthetic fixture only |
| ase | science | verified | reviewed public synthetic fixture only |
| pyscf | science | verified | Local H2 RHF energy |
| psi4 | science | blocked | Conda install passed; functional subprocess returned nonzero; cause not captured. |
| pymatgen | science | verified | reviewed public synthetic fixture only |
| mdanalysis | science | verified | reviewed public synthetic fixture only |
| gpaw | science | verified | Local DFT with public GPL dataset |
