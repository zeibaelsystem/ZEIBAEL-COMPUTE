#!/usr/bin/env python3
"""ZEIBAEL CI driver for public-safe software development tasks.

Private repository data never enter this runner. Grace uses the GitHub native
plugin to transfer only approved public-safe work and to store results privately.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

try:
    from scripts.job_plan import read_manifest, TIMEOUTS
except ModuleNotFoundError:
    from job_plan import read_manifest, TIMEOUTS

TASKS = {"validate", "python_tests", "node_tests", "package", "script"}
IGNORE = {".git", ".github", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".pytest_cache"}
MAX_FILES = 15000
MAX_SOURCE = 250_000_000
MAX_OUTPUT = 20000
MAX_PUBLIC_OUTPUT_BYTES = 50_000_000
MAX_PUBLIC_OUTPUT_FILES = 100


def inspect_public_files(directory):
    """Verify the isolated public output folder before GitHub artifact upload."""
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Opted-in output files directory missing or unsafe")
    count = 0
    total = 0
    for path in directory.rglob("*"):
        relative = path.relative_to(directory)
        if path.is_symlink() or any(part.startswith(".") for part in relative.parts):
            raise ValueError("Hidden file or symlink in public output")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("Unsupported public output entry")
        count += 1
        total += path.stat().st_size
        if count > MAX_PUBLIC_OUTPUT_FILES or total > MAX_PUBLIC_OUTPUT_BYTES:
            raise ValueError("Public output exceeds 100 files or 50 MB")
    if not count:
        raise ValueError("Opted-in output files directory is empty")
    return count, total


def execute(command, directory, timeout=900, env=None):
    result = subprocess.run(
        command, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace", timeout=timeout, check=False, env=env,
    )
    return result.returncode, result.stdout[-MAX_OUTPUT:]


def files_under(root):
    count = 0
    for path in sorted(root.rglob("*")):
        if any(p in IGNORE for p in path.relative_to(root).parts):
            continue
        if path.is_symlink():
            continue
        if not path.is_file():
            continue
        count += 1
        if count > MAX_FILES:
            raise ValueError("Too many source files for one bounded CI job")
        yield path


def validate(root):
    checked = {"python": 0, "json": 0, "shell": 0}
    for path in files_under(root):
        if path.suffix == ".py":
            import ast
            ast.parse(path.read_bytes(), filename=str(path))
            checked["python"] += 1
        elif path.suffix == ".json":
            with path.open("r", encoding="utf-8") as f:
                json.load(f)
            checked["json"] += 1
        elif path.suffix == ".sh":
            rc, output = execute(["bash", "-n", str(path)], root, timeout=30)
            if rc:
                raise ValueError("Bash syntax check failed: " + output[-1200:])
            checked["shell"] += 1
    return 0, "Validated file types: " + json.dumps(checked)


def package(root, output_dir):
    destination = output_dir / "zeibael-source.zip"
    total = 0
    n = 0
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files_under(root):
            size = path.stat().st_size
            total += size
            if total > MAX_SOURCE:
                raise ValueError("Package source exceeds 250 MB budget")
            archive.write(path, arcname=path.relative_to(root).as_posix())
            n += 1
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return 0, json.dumps({"files": n, "zip_bytes": destination.stat().st_size, "sha256": digest})


def script(root, script_id, output_dir, timeout=1200):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", script_id or ""):
        raise ValueError("Invalid script identifier")
    base = root / "ci" / "jobs"
    py = base / (script_id + ".py")
    sh = base / (script_id + ".sh")
    if py.is_file() and not py.is_symlink():
        cmd = [sys.executable, str(py)]
    elif sh.is_file() and not sh.is_symlink():
        cmd = ["bash", str(sh)]
    else:
        raise ValueError("Job script is not present in ci/jobs")
    # Never inherit unexpected environment variables in a project job.
    safe = {k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "CI", "TMPDIR"}}
    safe["ZEIBAEL_SOURCE_ROOT"] = str(root)
    safe["ZEIBAEL_OUTPUT_DIR"] = str(output_dir)
    completed = subprocess.run(cmd, cwd=root, env=safe, text=True, errors="replace",
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    return completed.returncode, completed.stdout[-MAX_OUTPUT:]



def manifest_job(root, script_id, job_id, output_dir, timeout):
    manifest = read_manifest(root, script_id)
    if manifest is None:
        return script(root, script_id, output_dir, timeout)
    jobs = [job for job in manifest["jobs"] if job["id"] == job_id]
    if len(jobs) != 1:
        raise ValueError("Job id does not occur uniquely in committed manifest")
    job = jobs[0]
    if os.environ.get("ZEIBAEL_JOB_RUNTIME") != job["runtime"]:
        raise ValueError("Runner runtime differs from reviewed manifest")
    safe_names = {"PATH", "HOME", "LANG", "CI", "TMPDIR", "TMP", "TEMP",
                  "SYSTEMROOT", "WINDIR", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
                  "JAVA_HOME", "GOPATH", "GOROOT", "RUSTUP_HOME", "CARGO_HOME",
                  "RUNNER_OS", "RUNNER_ARCH"}
    safe = {k: v for k, v in os.environ.items() if k in safe_names}
    safe.update(ZEIBAEL_SOURCE_ROOT=str(root), ZEIBAEL_OUTPUT_DIR=str(output_dir),
                ZEIBAEL_JOB_ID=job_id)
    deadline = time.monotonic() + timeout
    logs = []
    for argv in job["commands"]:
        command = [sys.executable if a in ("python", "python3") and i == 0 else a
                   for i, a in enumerate(argv)]
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout)
        rc, detail = execute(command, root, timeout=remaining, env=safe)
        logs.append("$ " + command[0] + " ...\n" + detail[-MAX_OUTPUT:])
        if rc:
            return rc, "\n".join(logs)[-MAX_OUTPUT:]
    if job.get("output_files", False):
        nfiles, nbytes = inspect_public_files(output_dir / "files")
        logs.append(f"ZEIBAEL_PUBLIC_OUTPUT_OK {nfiles} files / {nbytes} bytes")
    return 0, "\n".join(logs)[-MAX_OUTPUT:]

def main():
    task = os.environ.get("ZEIBAEL_CI_TASK", "")
    source = "public"
    script_id = os.environ.get("ZEIBAEL_SCRIPT_ID", "")
    root = Path(os.environ["ZEIBAEL_CI_ROOT"]).resolve()
    output_dir = Path(os.environ["ZEIBAEL_CI_OUTPUT"]).resolve()
    job_id = os.environ.get("ZEIBAEL_JOB_ID", task)
    runtime = os.environ.get("ZEIBAEL_JOB_RUNTIME", "python")
    timeout_minutes = int(os.environ.get("ZEIBAEL_JOB_TIMEOUT", "30"))
    if timeout_minutes not in TIMEOUTS.values():
        raise SystemExit("Invalid timeout profile")
    job_budget = max(60, timeout_minutes * 60 - 90)
    if task not in TASKS or not root.is_dir():
        raise SystemExit("Invalid CI task/root")
    if task != "script" and script_id:
        raise SystemExit("script_id is supported only for script jobs")
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    rc, detail = 1, ""
    try:
        if task == "validate":
            rc, detail = validate(root)
        elif task == "python_tests":
            if not (root / "tests").is_dir():
                raise ValueError("Missing tests/ directory")
            rc, detail = execute([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], root, timeout=job_budget)
        elif task == "node_tests":
            manifest = root / "package.json"
            if not manifest.is_file() or "test" not in json.loads(manifest.read_text()).get("scripts", {}):
                raise ValueError("Missing npm test script in package.json")
            if (root / "package-lock.json").is_file():
                rc, detail = execute(["npm", "ci", "--ignore-scripts"], root, timeout=job_budget)
                if rc:
                    raise ValueError("npm ci failed: " + detail[-1200:])
            rc, detail = execute(["npm", "test"], root, timeout=job_budget)
        elif task == "package":
            rc, detail = package(root, output_dir)
        else:
            rc, detail = manifest_job(root, script_id, job_id, output_dir, job_budget)
    except Exception as ex:
        rc, detail = 1, type(ex).__name__ + ": " + str(ex)[-3500:]

    report = {
        "schema": 1,
        "source": source, "task": task, "script_id": script_id,
        "job_id": job_id, "runtime": runtime, "timeout_minutes": timeout_minutes,
        "status": "success" if rc == 0 else "failure",
        "exit_code": rc, "duration_seconds": round(time.monotonic() - started, 3),
        "details": detail[-MAX_OUTPUT:],
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    }
    (output_dir / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(detail[-4000:])
    print("ZEIBAEL_RESULT_JSON=" + json.dumps({k: v for k, v in report.items() if k != "details"}, separators=(",", ":")))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("### ZEIBAEL job result\n\n")
            f.write(f"- Task: `{task}` / Job: `{job_id}`\n")
            f.write(f"- Runtime: `{runtime}` / Timeout: {timeout_minutes}m\n")
            f.write(f"- Status: **{report['status']}** / Exit: {rc}\n")
    print("ZEIBAEL CI job:", task, "|", report["status"], "| details: public")
    return rc


if __name__ == "__main__":
    sys.exit(main())
