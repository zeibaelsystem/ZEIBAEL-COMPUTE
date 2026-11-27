# Rust HPC foundation — Stage 1

The reviewed `rust_hpc` manifest runs a public synthetic deterministic Monte Carlo
workload on the existing Ubuntu 24.04 x64 Rust runner. No external crates, billing,
new credentials, dispatcher or paid fallback. The public runner must never process
private market data or private code.

Dispatch via the existing authorized route: workflow=ci, task=script,
script_id=rust_hpc. The manifest runs offline Cargo tests, a locked release build,
and a 1,000,000-sample serial/parallel comparison with four workers. For local
public fixture testing: cargo test --offline --locked --manifest-path
ci/fixtures/rust_hpc/Cargo.toml.

Output is JSON containing samples, workers, serial_hits, parallel_hits, pi,
serial_ns and parallel_ns. Equal integer counts are required; invalid inputs
(samples outside 1–20 million or workers outside 1–16) fail with exit 2.
The pseudorandom stream is fixed and indexed independently of worker partition.
Timing is illustrative, not a speed guarantee or a scientific-quality random
number generator certification. No production trading claim follows from this
synthetic workload. Debug and release builds are separate.

Status: proposed foundation until GitHub CI and dedicated dispatch provide
evidence. Do not enable other Rust OS targets, dependency-backed crates, WASM,
PyO3 or production routing without separate verification. 
