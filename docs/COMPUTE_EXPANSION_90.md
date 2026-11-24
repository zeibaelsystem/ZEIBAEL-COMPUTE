# Compute expansion — 84/90 public smoke-verified candidates (2026-11-25 WIB)

Canonical ledger: [ci/expansion_candidates.json](../ci/expansion_candidates.json). Evidence: [per-engine run/job receipts](../ci/evidence/expansion_2026-11-25.json). Only verified entries have runnable `engine_<id>` manifests. Use existing CI dispatcher only, single task-specific engine by default; expansion batches (max 18) are explicit audit jobs. Standard public Ubuntu x64, CPU only, no private data, no new billing or external inference API. Scope is exactly tested synthetic behavior; no claim of real-world accuracy or general production readiness. Direct dependencies and public model/release sources reviewed, not a guarantee of all transitive licenses. Stop when entitlement, license scope, public download, quota or fixture assumptions are incompatible. No new-chat routing proof.

| Group | Verified | Blocked |
|---|---:|---:|
| chemical | 9 | 1 |
| engineering | 10 | 0 |
| optimization | 10 | 0 |
| finance | 10 | 0 |
| ai | 10 | 0 |
| documents | 9 | 1 |
| multimedia | 8 | 2 |
| data | 10 | 0 |
| software | 8 | 2 |

## Candidate status

| Engine | State | Scope or blocker | Evidence |
|---|---|---|---|
| idaes | verified | Property-model material flow only; full process optimization not yet proven | [run 45456441945, job 138667050789](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667050789) |
| watertap | verified | NaCl property model; no RO plant optimization claim | [run 45456441945, job 138667051149](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667051149) |
| phreeqc | verified | Aqueous speciation with checked public USGS database | [run 45457363379, job 138670322361](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457363379/job/138670322361) |
| thermo | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124161](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124161) |
| chemicals | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124467](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124467) |
| fluids | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124204](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124204) |
| ht | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124415](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124415) |
| pybamm | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124258](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124258) |
| rmg_py | blocked | Native kinetics module rmgpy.kinetics.model missing in pinned public container; run 45457951955 job 138672379951 failed after entrypoint repair. | Not admitted |
| rdkit | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124374](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124374) |
| cadquery | verified | public synthetic local smoke; runtime and dependency verification required | [run 45456441945, job 138667050942](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667050942) |
| freecad | verified | Headless CAD fixture | [run 45457363379, job 138670322356](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457363379/job/138670322356) |
| openseespy | verified | Internal research only; public source fixture does not redistribute library or create service; research, education and internal use only; no commercial redistribution. | [run 45457363379, job 138670322151](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457363379/job/138670322151) |
| fenicsx | verified | Finite element integration on public unit mesh | [run 45457363379, job 138670322112](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457363379/job/138670322112) |
| su2 | verified | Pinned public serial CFD executable; uniform Euler flow on synthetic mesh | [run 45457780727, job 138671781228](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457780727/job/138671781228) |
| wntr | verified | public synthetic local smoke; runtime and dependency verification required | [run 45457363379, job 138670321597](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457363379/job/138670321597) |
| pandapower | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124103](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124103) |
| opendss | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124311](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124311) |
| pyvista | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124163](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124163) |
| openmdao | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124314](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124314) |
| ortools | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124347](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124347) |
| pyomo | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124533](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124533) |
| highs | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124542](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124542) |
| cvxpy | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124194](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124194) |
| casadi | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124480](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124480) |
| salib | verified | public synthetic local smoke; runtime and dependency verification required | [run 45456441945, job 138667051077](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667051077) |
| simpy | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124431](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124431) |
| pint | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124462](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124462) |
| pymc | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124432](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124432) |
| deap | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124369](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124369) |
| talib | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124686](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124686) |
| backtrader | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124511](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124511) |
| statsmodels | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124586](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124586) |
| qlib | verified | Qlib quantitative risk analysis; not local historical data pipeline | [run 45457363379, job 138670322205](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457363379/job/138670322205) |
| optuna | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124775](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124775) |
| riskfolio | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664124539](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664124539) |
| arch | verified | public synthetic local smoke; runtime and dependency verification required | [run 45456441945, job 138667050858](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667050858) |
| pyportfolioopt | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664128382](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664128382) |
| statsforecast | verified | public synthetic local smoke; runtime and dependency verification required | [run 45456441945, job 138667050884](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667050884) |
| shap | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664128622](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664128622) |
| scikit_learn | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664128628](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664128628) |
| xgboost | verified | public synthetic local smoke; runtime and dependency verification required | [run 45456441945, job 138667050831](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667050831) |
| lightgbm | verified | public synthetic local smoke; runtime and dependency verification required | [run 45456441945, job 138667050871](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667050871) |
| catboost | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664128469](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664128469) |
| tensorflow | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664128875](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664128875) |
| jax | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664128837](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664128837) |
| llama_cpp | verified | CPU public GGUF inference; no hosted model | [run 45457780727, job 138671780729](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457780727/job/138671780729) |
| transformers | verified | Local pretrained encoder | [run 45456441945, job 138667050258](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667050258) |
| sentence_transformers | verified | Local pretrained embedding | [run 45456441945, job 138667051153](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667051153) |
| faiss | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664128951](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664128951) |
| docling | verified | Document structure on Markdown; no PDF neural layout claim | [run 45456441945, job 138667051006](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667051006) |
| paddleocr | verified | CPU local pretrained OCR | [run 45457780727, job 138671780934](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457780727/job/138671780934) |
| ocrmypdf | verified | public synthetic local smoke; runtime and dependency verification required | [run 45456441945, job 138667050908](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667050908) |
| pdfplumber | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664132695](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664132695) |
| marker | blocked | Code and model weights have separate licensing restrictions; unconditional recurring free eligibility not established. | Not admitted |
| libreoffice | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664132527](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664132527) |
| pandoc | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664132626](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664132626) |
| tika | verified | Local synthetic PDF parsing only | [run 45456441945, job 138667050954](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667050954) |
| tabula | verified | Synthetic ruled PDF table extraction | [run 45457363379, job 138670322049](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457363379/job/138670322049) |
| tesseract_multilingual | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664132495](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664132495) |
| scenedetect | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664132974](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664132974) |
| librosa | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664133023](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664133023) |
| demucs | blocked | Pretrained weight license and reproducible CPU source separation not established. | Not admitted |
| silero_vad | verified | Bundled MIT VAD model on CPU | [run 45456441945, job 138667050881](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667050881) |
| whisperx | blocked | Local CPU alignment failed Wav2Vec2ForCTC import after model download and retry; run 45457780727 job 138671780669. | Not admitted |
| mediapipe | verified | Local bundled hand model inference on synthetic blank frame; negative case only | [run 45457363379, job 138670322101](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457363379/job/138670322101) |
| sam2 | verified | Pinned SAM2.1 local CPU prompted image segmentation; video tracking not verified | [run 45457780727, job 138671780670](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457780727/job/138671780670) |
| imagemagick | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664133123](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664133123) |
| blender | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664132961](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664132961) |
| open3d | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664133334](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664133334) |
| arrow | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664135949](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664135949) |
| dask | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664136107](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664136107) |
| ray | verified | Local ephemeral single-node workers only | [run 45456441945, job 138667051266](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667051266) |
| networkx | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664136531](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664136531) |
| gdal | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664136506](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664136506) |
| geopandas | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664136728](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664136728) |
| xarray | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664136611](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664136611) |
| rasterio | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664136546](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664136546) |
| orjson | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664136623](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664136623) |
| great_expectations | verified | public synthetic local smoke; runtime and dependency verification required | [run 45456441945, job 138667050327](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667050327) |
| hypothesis | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664137806](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664137806) |
| locust | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664139549](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664139549) |
| k6 | verified | Bounded loopback-only load test | [run 45456441945, job 138667051460](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45456441945/job/138667051460) |
| appium | blocked | Run 45457780727 job 138671780514: no KVM access, no preinstalled Android system image or emulator. | Not admitted |
| maestro | blocked | Run 45457780727 job 138671780514: no KVM access, no preinstalled Android system image or emulator. | Not admitted |
| trivy | verified | Offline configuration scan only | [run 45457363379, job 138670322232](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457363379/job/138670322232) |
| semgrep | verified | public synthetic local smoke; runtime and dependency verification required | [run 45457780727, job 138671780968](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45457780727/job/138671780968) |
| z3 | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664139824](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664139824) |
| scrapy | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664139870](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664139870) |
| trafilatura | verified | public synthetic local smoke; runtime and dependency verification required | [run 45455618202, job 138664139752](https://github.com/zeibaelsystem/ZEIBAEL-COMPUTE/actions/runs/45455618202/job/138664139752) |
