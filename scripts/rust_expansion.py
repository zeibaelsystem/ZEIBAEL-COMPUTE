"""Bounded, reviewed public Rust expansion fixtures, with no credentials or paid services.

Each invocation selects one constant case, constructs an isolated temporary crate,
acquires public crates.io packages only when necessary, checks the resolved
package sources/licenses, then runs locked offline Cargo commands.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

CASES = {
    "rayon": {
        "dependencies": {"rayon": "=1.10.0"},
        "source": r'''
use rayon::prelude::*;
#[test]
fn deterministic_parallel_reduction() {
    let pool = rayon::ThreadPoolBuilder::new().num_threads(4).build().unwrap();
    let serial: u64 = (0..100_003u64).map(|x| x*x).sum();
    let parallel: u64 = pool.install(|| (0..100_003u64).into_par_iter().map(|x| x*x).sum());
    assert_eq!(serial, parallel);
    println!("RAYON_REDUCTION={parallel}");
}
'''},
    "tokio": {
        "dependencies": {"tokio": "=1.44.2"},
        "features": {"tokio": ["rt-multi-thread", "sync", "time"]},
        "source": r'''
#[test]
fn bounded_async_channel_and_tasks() {
    let rt = tokio::runtime::Builder::new_multi_thread().worker_threads(2).enable_time().build().unwrap();
    rt.block_on(async {
        let (tx, mut rx) = tokio::sync::mpsc::channel::<u64>(4);
        let mut tasks = Vec::new();
        for n in 1..=16u64 {
            let tx = tx.clone();
            tasks.push(tokio::spawn(async move { tx.send(n*n).await.unwrap(); }));
        }
        drop(tx);
        let total = tokio::time::timeout(std::time::Duration::from_secs(5), async {
            let mut total = 0;
            while let Some(n) = rx.recv().await { total += n; }
            total
        }).await.unwrap();
        for task in tasks { task.await.unwrap(); }
        assert_eq!(total, 1496);
        println!("TOKIO_ASYNC_SUM={total}");
    });
}
'''},
    "ndarray": {
        "dependencies": {"ndarray": "=0.16.1"},
        "source": r'''
use ndarray::array;
#[test]
fn matrix_product_and_axis_reduction() {
    let a = array![[1., 2., 3.], [4., 5., 6.]];
    let b = array![[7., 8.], [9., 10.], [11., 12.]];
    let c = a.dot(&b);
    assert_eq!(c, array![[58., 64.], [139., 154.]]);
    assert_eq!(c.sum_axis(ndarray::Axis(0)), array![197., 218.]);
    println!("NDARRAY_MATRIX_OK");
}
'''},
    "polars": {
        "dependencies": {"polars": "=0.46.0"},
        "default_off": ["polars"],
        "source": r'''
use polars::prelude::*;
#[test]
fn tabular_filter_and_aggregation() -> PolarsResult<()> {
    let df = df!("ticker" => ["AAA", "BBB", "CCC"], "price" => [100i64, 200, 300], "volume" => [10i64, 20, 30])?;
    let filtered = df.filter(&df.column("price")?.i64()?.gt(150))?;
    assert_eq!(filtered.height(), 2);
    assert_eq!(filtered.column("volume")?.i64()?.sum(), Some(50));
    println!("POLARS_FILTER_SUM=50");
    Ok(())
}
'''},
    "criterion": {
        "dependencies": {"criterion": "=0.5.1"},
        "default_off": ["criterion"],
        "mode": "bench",
        "source": r'''
use criterion::{criterion_group, criterion_main, Criterion};
use std::hint::black_box;
fn bench(c: &mut Criterion) {
    let values: Vec<u64> = (0..10_000u64).collect();
    assert_eq!(values.iter().map(|x| x*x).sum::<u64>(), 333283335000);
    c.bench_function("zeibael_sum_squares", |b| b.iter(|| {
        let data = black_box(values.as_slice());
        black_box(data.iter().map(|x| x*x).sum::<u64>())
    }));
}
criterion_group!(benches, bench);
criterion_main!(benches);
'''},
    "pyo3": {
        "dependencies": {"pyo3": "=0.23.5"},
        "features": {"pyo3": ["extension-module"]},
        "mode": "python",
        "source": r'''
use pyo3::prelude::*;
#[pyfunction]
fn sum_squares(values: Vec<i64>) -> PyResult<i64> {
    values.into_iter().try_fold(0i64, |acc, x| {
        x.checked_mul(x).and_then(|y| acc.checked_add(y))
            .ok_or_else(|| pyo3::exceptions::PyOverflowError::new_err("integer overflow"))
    })
}
#[pymodule]
fn zeibael_probe(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sum_squares, m)?)?;
    Ok(())
}
'''},
    "tooling": {
        "mode": "tooling",
        "source": r'''
pub fn square(x: i64) -> i64 {
    x * x
}

#[test]
fn test_square() {
    assert_eq!(square(5), 25);
}
'''.lstrip()},
    "simd": {
        "source": r'''
#[cfg(target_arch = "x86_64")]
#[test]
fn sse2_vector_add_matches_scalar() {
    use std::arch::x86_64::*;
    assert!(is_x86_feature_detected!("sse2"));
    let a = [1i32, 2, 3, 4];
    let b = [10i32, 20, 30, 40];
    let expected = [11i32, 22, 33, 44];
    let mut result = [0i32; 4];
    // SAFETY: the CPU supports SSE2, each buffer contains 16 bytes, and
    // unaligned load/store intrinsics permit their addresses.
    unsafe {
        let av = _mm_loadu_si128(a.as_ptr().cast());
        let bv = _mm_loadu_si128(b.as_ptr().cast());
        _mm_storeu_si128(result.as_mut_ptr().cast(), _mm_add_epi32(av, bv));
    }
    assert_eq!(result, expected);
    println!("SSE2_VECTOR_OK");
}
'''},
    "wasm": {
        "mode": "wasm",
        "source": r'''
#[no_mangle]
pub extern "C" fn square(x: i32) -> i32 { x.wrapping_mul(x) }
'''},
    "backtest": {
        "source": r'''
#[derive(Clone, Copy)]
struct Bar { open: i64, high: i64, low: i64, close: i64 }
#[derive(Debug, PartialEq)]
struct Trade { entry: i64, exit: i64, net: i64, reason: &'static str }
// Prices and fees are integers in synthetic price units, one share per trade.
// Signal is evaluated on bar t, entry at bar t+1 open; exit at the entry bar close
// or a barrier. Gap before entry is not counted as profit. If both barriers are
// touched, intrabar chronology is unknown and the conservative stop-first rule applies.
fn trade(bars: &[Bar], signal_index: usize, tp: i64, sl: i64, fee_per_side: i64) -> Result<Option<Trade>, &'static str> {
    if tp <= 0 || sl <= 0 || fee_per_side < 0 { return Err("invalid parameters"); }
    if bars.iter().any(|b| b.low <= 0 || b.open < b.low || b.open > b.high || b.close < b.low || b.close > b.high) { return Err("invalid OHLC"); }
    let next = signal_index.checked_add(1).ok_or("index overflow")?;
    let Some(b) = bars.get(next) else { return Ok(None); };
    let stop = b.open.checked_sub(sl).ok_or("stop overflow")?;
    if stop <= 0 { return Err("invalid stop price"); }
    let target = b.open.checked_add(tp).ok_or("target overflow")?;
    let (exit, reason) = if b.low <= stop { (stop, "SL") } else if b.high >= target { (target, "TP") } else { (b.close, "EOD") };
    let cost = fee_per_side.checked_mul(2).ok_or("fee overflow")?;
    let net = exit.checked_sub(b.open).and_then(|x| x.checked_sub(cost)).ok_or("net overflow")?;
    Ok(Some(Trade { entry: b.open, exit, net, reason }))
}
fn signal() -> Bar { Bar { open: 90, high: 120, low: 80, close: 110 } }
#[test]
fn no_lookahead_and_next_open_entry() {
    let bars = [signal(), Bar { open: 100, high: 105, low: 98, close: 103 }];
    assert_eq!(trade(&bars, 0, 10, 5, 1).unwrap(), Some(Trade { entry: 100, exit: 103, net: 1, reason: "EOD" }));
    assert_eq!(trade(&bars, 1, 10, 5, 1).unwrap(), None);
}
#[test]
fn both_barriers_stop_first() {
    let bars = [signal(), Bar { open: 100, high: 115, low: 90, close: 110 }];
    assert_eq!(trade(&bars, 0, 10, 5, 1).unwrap().unwrap().reason, "SL");
    assert_eq!(trade(&bars, 0, 10, 5, 1).unwrap().unwrap().net, -7);
}
#[test]
fn transaction_cost_and_take_profit() {
    let bars = [signal(), Bar { open: 100, high: 115, low: 98, close: 110 }];
    assert_eq!(trade(&bars, 0, 10, 5, 2).unwrap().unwrap().net, 6);
}
#[test]
fn invalid_bar_and_parameters_fail_closed() {
    assert!(trade(&[signal()], 0, 0, 5, 1).is_err());
    assert!(trade(&[Bar {open:100, high:99, low:90, close:95}], 0, 10, 5, 1).is_err());
}
'''},
}

PERMITTED_LICENSES = {
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib",
    "Unicode-3.0", "Unicode-DFS-2016", "CC0-1.0", "Unlicense", "0BSD",
    "BSL-1.0", "MPL-2.0", "OpenSSL", "LLVM-exception", "Apache-2.0-with-LLVM-exception",
}
CRATES_SOURCE = "registry+https://github.com/rust-lang/crates.io-index"

LOCK_HASHES = {
    "criterion": "1695ba30f7c30731689ca47ec12032a2d23edc3915370665be4a26f93c977352",
    "ndarray": "19a2ed5583fd0834021bf6a7099463ee229d5b48cddbc438737f8fa5b7a53889",
    "pyo3": "e810a468af353e462e08a68e3944268ffa84efff044603984dba46fd6fbf74c9",
    "rayon": "a05e4d7f50b5e95c2bfd5e0f692cc8b20a5dc7ae1c0b313ec5bdda4d787666c0",
    "tokio": "daa7a3909407ed8cae6692651f60a7e1a91519cb9bc8e6e7a9e5b57eb70c58b3"
}
LOCK_ROOT = Path(__file__).resolve().parents[1] / "ci/fixtures/rust_expansion/locks"

def run_command(argv, root, *, capture=False):
    result = subprocess.run(argv, cwd=root, text=True, encoding="utf-8", errors="replace",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=420)
    if not capture or result.returncode:
        print(result.stdout[-12000:], flush=True)
    if result.returncode:
        raise RuntimeError("command failed: " + " ".join(argv[:3]))
    return result.stdout

# Exact independently reviewed crate archive; no general license-file bypass.
# https://docs.rs/crate/polars-arrow-format/0.1.0/source/LICENSE
# https://crates.io/api/v1/crates/polars-arrow-format/0.1.0
ARROW_FORMAT_CHECKSUM = "19b0ef2474af9396b19025b189d96e992311e6a47f90c53cd998b36c4c64b84c"

def permitted_license_expression(expression):
    """Evaluate reviewed license choices; every mandatory AND branch must pass."""
    if not isinstance(expression, str) or len(expression) > 2048:
        return False
    tokens = re.findall(r"\(|\)|/|[A-Za-z0-9][A-Za-z0-9.+-]*", expression)
    if not tokens or len(tokens) > 128 or "".join(tokens) != re.sub(r"\s+", "", expression):
        return False
    index = 0
    def peek():
        return tokens[index] if index < len(tokens) else None
    def pop():
        nonlocal index
        if index >= len(tokens):
            raise ValueError("unexpected end of license expression")
        token = tokens[index]
        index += 1
        return token
    def atom():
        token = pop()
        if token == "(":
            accepted = alternative()
            if pop() != ")":
                raise ValueError("unclosed license group")
            return accepted
        if token in {"AND","OR","WITH","/","(",")"}:
            raise ValueError("expected license identifier")
        if peek() == "WITH":
            pop()
            exception = pop()
            if exception in {"AND","OR","WITH","/","(",")"}:
                raise ValueError("expected exception identifier")
            return (token, exception) == ("Apache-2.0","LLVM-exception")
        return token in PERMITTED_LICENSES and token != "LLVM-exception"
    def conjunction():
        accepted = atom()
        while peek() == "AND":
            pop()
            right = atom()
            accepted = accepted and right
        return accepted
    def alternative():
        accepted = conjunction()
        while peek() in {"OR","/"}:
            pop()
            right = conjunction()
            accepted = accepted or right
        return accepted
    try:
        accepted = alternative()
        return index == len(tokens) and accepted
    except (ValueError, RecursionError):
        return False

def review_package_license(pkg, checksum):
    license = pkg.get("license") or ""
    if permitted_license_expression(license):
        return license
    if (not license and pkg["name"] == "polars-arrow-format" and pkg["version"] == "0.1.0"
            and checksum == ARROW_FORMAT_CHECKSUM and pkg.get("license_file")):
        root = Path(pkg["manifest_path"]).resolve().parent
        path = (root / pkg["license_file"]).resolve()
        if path == root / "LICENSE" and path.is_file():
            content = path.read_text(encoding="utf-8")
            if ("Apache License" in content and "Version 2.0, January 2004" in content
                    and "END OF TERMS AND CONDITIONS" in content):
                return "Apache-2.0"
    raise ValueError("unreviewed license: " + pkg["name"] + " " + license)

def check_dependencies(root):
    raw = run_command(["cargo","metadata","--locked","--offline","--format-version","1"], root, capture=True)
    packages = json.loads(raw)["packages"]
    checksums = {(p["name"],p["version"]):p.get("checksum") for p in tomllib.loads((root/"Cargo.lock").read_text(encoding="utf-8"))["package"]}
    reviewed = []
    license_errors = []
    for pkg in packages:
        if pkg.get("source") is None:
            if pkg["name"] != "zeibael-probe":
                raise ValueError("unexpected local package")
            continue
        if pkg["source"] != CRATES_SOURCE:
            raise ValueError("non-crates.io dependency: " + pkg["name"])
        checksum = checksums.get((pkg["name"],pkg["version"]))
        if not checksum or not re.fullmatch(r"[a-f0-9]{64}",checksum):
            raise ValueError("missing registry checksum: " + pkg["name"])
        try:
            license = review_package_license(pkg,checksum)
        except ValueError as error:
            license_errors.append(str(error))
            continue
        reviewed.append({"name":pkg["name"],"version":pkg["version"],"license":license,"checksum":checksum})
    if license_errors:
        raise ValueError("dependency license review failed: " + "; ".join(license_errors))
    return sorted(reviewed, key=lambda x:(x["name"], x["version"]))

def prepare(case, root):
    mode = case.get("mode","test")
    source_dir = root / ("benches" if mode == "bench" else "src")
    source_dir.mkdir()
    (source_dir / ("probe.rs" if mode == "bench" else "lib.rs")).write_text(case["source"].strip()+"\n", encoding="utf-8")
    if mode == "bench":
        (root / "src").mkdir()
        (root / "src/lib.rs").write_text("// Criterion probe\n", encoding="utf-8")
    manifest = ['[package]', 'name = "zeibael-probe"', 'version = "0.1.0"', 'edition = "2021"', 'publish = false']
    if mode in {"python","wasm"}:
        manifest += ["[lib]",'name = "zeibael_probe"','crate-type = ["cdylib"]']
    if mode == "bench":
        manifest += ["[[bench]]",'name = "probe"',"harness = false"]
    # Limit memory pressure in the CPU-only Polars smoke job.
    manifest += ["[profile.dev]", "debug = 0", "[profile.test]", "debug = 0", "[dependencies]"]
    for name, version in sorted(case.get("dependencies",{}).items()):
        if not re.fullmatch(r"=\d+\.\d+\.\d+",version):
            raise ValueError("dependency version must be exact")
        fields = ['version = "'+version+'"']
        if name in case.get("default_off", []):
            fields.append("default-features = false")
        if name in case.get("features",{}):
            fields.append("features = "+json.dumps(case["features"][name]))
        manifest.append(name+" = { "+", ".join(fields)+" }")
    (root / "Cargo.toml").write_text("\n".join(manifest)+"\n",encoding="utf-8")
    (root / ".cargo").mkdir()
    (root / ".cargo/config.toml").write_text('[build]\njobs = 2\n', encoding="utf-8")
    return mode

def execute_case(name, output):
    case = CASES[name]
    with tempfile.TemporaryDirectory(prefix="zeibael-rust-") as directory:
        root = Path(directory)
        mode = prepare(case,root)
        if mode == "wasm":
            run_command(["rustup","target","add","wasm32-unknown-unknown"],root)
        if mode == "tooling":
            run_command(["rustup","component","add","rustfmt","clippy"],root)
        if case.get("dependencies"):
            if name in LOCK_HASHES:
                lock = (LOCK_ROOT / (name + ".lock")).read_bytes()
                if hashlib.sha256(lock).hexdigest() != LOCK_HASHES[name]:
                    raise ValueError("reviewed lockfile hash mismatch: " + name)
                (root / "Cargo.lock").write_bytes(lock)
            elif name == "polars":
                # Only this not-yet-promoted recovery probe may resolve a fresh lock.
                run_command(["cargo","generate-lockfile"],root)
            else:
                raise ValueError("missing reviewed lockfile: " + name)
            run_command(["cargo","fetch","--locked"],root)
        else:
            run_command(["cargo","generate-lockfile","--offline"],root)
        packages = check_dependencies(root)
        locked = ["--offline","--locked"]
        if mode == "bench":
            out = run_command(["cargo","bench",*locked,"--bench","probe","--","--sample-size","10","--warm-up-time","1","--measurement-time","1","--noplot"],root)
            if "zeibael_sum_squares" not in out or "time:" not in out:
                raise ValueError("Criterion did not report a measured benchmark")
        elif mode == "python":
            run_command(["cargo","build",*locked,"--release"],root)
            path = root / "target/release/libzeibael_probe.so"
            check = "import importlib.util,sys; s=importlib.util.spec_from_file_location('zeibael_probe',sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); assert m.sum_squares([1,2,3,4])==30; print('PYO3_EXTENSION_OK')"
            run_command([sys.executable,"-c",check,str(path)],root)
        elif mode == "wasm":
            run_command(["cargo","build",*locked,"--release","--target","wasm32-unknown-unknown"],root)
            path = root / "target/wasm32-unknown-unknown/release/zeibael_probe.wasm"
            check = "const fs=require('fs'); (async()=>{const {instance}=await WebAssembly.instantiate(fs.readFileSync(process.argv[1])); if(instance.exports.square(7)!==49) throw Error('wrong WASM result'); console.log('WASM_EXECUTION_OK')})().catch(e=>{console.error(e);process.exit(1)})"
            run_command(["node","-e",check,str(path)],root)
        else:
            if mode == "tooling":
                run_command(["cargo","fmt","--","--check"],root)
                run_command(["cargo","clippy",*locked,"--all-targets","--","-D","warnings"],root)
            out = run_command(["cargo","test",*locked,"--","--nocapture"],root)
            if not re.search(r"test result: ok\. [1-9]\d* passed;",out):
                raise ValueError("no executed Rust test")
        lock = (root / "Cargo.lock").read_bytes()
        receipt = {"case":name,"status":"success","mode":mode,"direct_dependencies":case.get("dependencies",{}),"resolved_packages":len(packages),"lock_sha256":hashlib.sha256(lock).hexdigest(),"scope":"PUBLIC_SYNTHETIC_FIXTURE_ONLY"}
        output.mkdir(parents=True,exist_ok=True)
        (output / "Cargo.lock").write_bytes(lock)
        (output / "receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
        (output / "dependency-licenses.json").write_text(json.dumps(packages,indent=2)+"\n",encoding="utf-8")
        print("ZEIBAEL_RUST_EXPANSION="+json.dumps(receipt,sort_keys=True),flush=True)

def main():
    if len(sys.argv)!=2 or sys.argv[1] not in CASES:
        raise SystemExit("unreviewed Rust case")
    if sys.platform!="linux":
        raise SystemExit("Rust expansion dependencies are Linux x64 scope only")
    output = Path(os.environ["ZEIBAEL_OUTPUT_DIR"]) / "files"
    execute_case(sys.argv[1],output)

if __name__ == "__main__":
    main()
