//! Deterministic, bounded, dependency-free numerical workload.
use std::{env, process, thread, time::Instant};

const MAX_SAMPLES: u64 = 20_000_000;
const MAX_WORKERS: usize = 16;

fn mix(mut x: u64) -> u64 {
    x = x.wrapping_add(0x9e3779b97f4a7c15);
    x = (x ^ (x >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    x = (x ^ (x >> 27)).wrapping_mul(0x94d049bb133111eb);
    x ^ (x >> 31)
}

fn coordinate(index: u64) -> f64 {
    ((mix(index) >> 11) as f64) * (1.0 / 9007199254740992.0)
}

fn count_hits(start: u64, end: u64) -> u64 {
    (start..end)
        .map(|i| {
            let x = coordinate(2 * i);
            let y = coordinate(2 * i + 1);
            u64::from(x * x + y * y <= 1.0)
        })
        .sum()
}

fn parallel_hits(samples: u64, workers: usize) -> Result<u64, &'static str> {
    if !(1..=MAX_SAMPLES).contains(&samples) || !(1..=MAX_WORKERS).contains(&workers) {
        return Err("samples or workers out of bounds");
    }
    thread::scope(|scope| {
        let handles: Vec<_> = (0..workers)
            .map(|w| {
                let lo = samples * w as u64 / workers as u64;
                let hi = samples * (w + 1) as u64 / workers as u64;
                scope.spawn(move || count_hits(lo, hi))
            })
            .collect();
        handles.into_iter().try_fold(0, |total, handle| {
            handle.join().map(|hits| total + hits).map_err(|_| "worker failed")
        })
    })
}

fn run() -> Result<(), &'static str> {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.len() != 2 {
        return Err("usage: zeibael-rust-hpc <samples 1..20000000> <workers 1..16>");
    }
    let samples: u64 = args[0].parse().map_err(|_| "invalid samples")?;
    let workers: usize = args[1].parse().map_err(|_| "invalid workers")?;
    if !(1..=MAX_SAMPLES).contains(&samples) || !(1..=MAX_WORKERS).contains(&workers) {
        return Err("samples or workers out of bounds");
    }
    let start = Instant::now();
    let serial = count_hits(0, samples);
    let serial_ns = start.elapsed().as_nanos();
    let start = Instant::now();
    let parallel = parallel_hits(samples, workers)?;
    let parallel_ns = start.elapsed().as_nanos();
    if serial != parallel {
        return Err("serial and parallel results differ");
    }
    let pi = 4.0 * serial as f64 / samples as f64;
    println!(
        "{{\"schema\":1,\"samples\":{},\"workers\":{},\"serial_hits\":{},\"parallel_hits\":{},\"pi\":{},\"serial_ns\":{},\"parallel_ns\":{}}}",
        samples, workers, serial, parallel, pi, serial_ns, parallel_ns
    );
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        process::exit(2);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn serial_and_parallel_are_identical_for_uneven_chunks() {
        let expected = count_hits(0, 100_003);
        for workers in [1, 2, 3, 4, 16] {
            assert_eq!(parallel_hits(100_003, workers), Ok(expected));
        }
    }

    #[test]
    fn tiny_workload_with_more_workers_than_samples_is_exact() {
        assert_eq!(parallel_hits(3, 16), Ok(count_hits(0, 3)));
    }

    #[test]
    fn rejects_invalid_resource_requests() {
        for (samples, workers) in [(0, 1), (MAX_SAMPLES + 1, 1), (1, 0), (1, MAX_WORKERS + 1)] {
            assert!(parallel_hits(samples, workers).is_err());
        }
    }

    #[test]
    fn deterministic_estimate_is_close_to_pi() {
        let n = 1_000_000;
        let estimate = 4.0 * count_hits(0, n) as f64 / n as f64;
        assert!((estimate - std::f64::consts::PI).abs() < 0.015);
    }
}
