# Rust expansion — public standard-runner probes

The existing Rust foundation remains the offline, dependency-free `rust_hpc`
route. Expansion probes are independently dispatchable as
`rust_rayon`, `rust_tokio`, `rust_ndarray`, `rust_polars`, `rust_criterion`,
`rust_pyo3`, `rust_tooling`, `rust_simd`, `rust_wasm`, and `rust_backtest`.
`rust_expansion` is the explicit audit batch, not a default task.
Five additional manifests probe native hosts: `rust_linux_arm64`,
`rust_windows_x64`, `rust_windows_arm64`, `rust_macos_arm64`,
`rust_macos_x64`. All five native probes passed run 45985551586. The reviewed resource router
now admits these hosts plus Ubuntu 24.04 x64 for the Rust standard-library
fixture; the default remains Ubuntu 24.04 x64. Crate-backed probes remain
Linux x64 only.

All inputs and source are public synthetic fixtures. Do not send private
market records or source to the public runner. Standard GitHub-hosted public
runners only, no paid fallback, new dispatcher, account, cloud inference, or
billing. Public crates.io acquisition uses no credentials or account.
Direct dependency versions are exact pins verified against crates.io metadata:
Rayon 1.10.0, Tokio 1.44.2, ndarray 0.16.1, Polars 0.46.0, Criterion 0.5.1,
PyO3 0.23.5. The selected releases were non-yanked and MIT/Apache licensed.
All six crate-backed routes reuse byte-identical reviewed lockfiles, with
pinned SHA-256 checks. Polars was recovered in run 45987073960 (111 registry
dependencies, filter/sum = 50); the other five were reverified with committed
locks in run 45986606377. Missing locks fail closed. SPDX alternatives are
parsed as license choices, while conjunctions require every obligation to
be admitted. Fetch public registry packages by lock, verify registry checksums,
source and reviewed license evidence, and execute with `--offline --locked`.
Lockfile, receipt and dependency metadata are uploaded as one-day public
output artifacts. No vulnerability or production
security audit is claimed. Unknown licenses or source, network or quota
failures stop that route.

Fixture scope:
- Rayon: deterministic parallel reduction; Tokio: bounded async channel.
- ndarray: matrix product and axis reduction; Polars: in-memory filter/sum.
- Criterion: actual short microbenchmark; PyO3: Python loads a Rust extension.
- Tooling: rustfmt check, Clippy warnings denied and Cargo test.
- SIMD: x86-64 SSE2 integer vector addition; WASM: compile a freestanding
  WebAssembly export and execute through local Node.js.
- Backtest: synthetic, integer-price, long-only, next-bar entry, one-bar
  exit, TP/SL/EOD, fixed per-side fee and conservative stop-first policy if
  both barriers are touched. No strategy alpha, profit guarantee, real market
  data, slippage or production execution claim.
- Platform probes: verify actual native OS/architecture, Cargo test and
  run the existing one-million-sample Rust foundation on each host.

All capability promotion requires actual per-job log markers, status and
aggregate evidence. The default Rust runner remains Ubuntu 24.04 x64; reviewed OS/architecture
requirements may select one of the five newly verified hosts. Historical
first-batch evidence: `ci/evidence/rust_expansion_2026-11-27.json` (14/15
jobs succeeded; Polars correctly stopped on license metadata). The exact
polars-arrow-format 0.1.0 archive was separately verified as Apache-2.0
via its published license file and crates.io checksum; no general exception.

The recovery receipt is `ci/evidence/rust_expansion_recovery_2026-11-27.json`.
It records 15 successful route receipts across the batch and recovery runs;
this is not a claim of a single all-green batch before final rerun.
