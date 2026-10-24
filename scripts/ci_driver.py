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

TASKS = {"validate", "python_tests", "node_tests", "package", "script"}
IGNORE = {".git", ".github", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".pytest_cache"}
MAX_FILES = 15000
MAX_SOURCE = 250_000_000
MAX_OUTPUT = 20000


def execute(command, directory, timeout=900):
    result = subprocess.run(
        command, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace", timeout=timeout, check=False,
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


def script(root, script_id, output_dir):
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
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1200)
    return completed.returncode, completed.stdout[-MAX_OUTPUT:]


def main():
    task = os.environ.get("ZEIBAEL_CI_TASK", "")
    source = "public"
    script_id = os.environ.get("ZEIBAEL_SCRIPT_ID", "")
    root = Path(os.environ["ZEIBAEL_CI_ROOT"]).resolve()
    output_dir = Path(os.environ["ZEIBAEL_CI_OUTPUT"]).resolve()
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
            rc, detail = execute([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], root)
        elif task == "node_tests":
            manifest = root / "package.json"
            if not manifest.is_file() or "test" not in json.loads(manifest.read_text()).get("scripts", {}):
                raise ValueError("Missing npm test script in package.json")
            if (root / "package-lock.json").is_file():
                rc, detail = execute(["npm", "ci", "--ignore-scripts"], root)
                if rc:
                    raise ValueError("npm ci failed: " + detail[-1200:])
            rc, detail = execute(["npm", "test"], root)
        elif task == "package":
            rc, detail = package(root, output_dir)
        else:
            rc, detail = script(root, script_id, output_dir)
    except Exception as ex:
        rc, detail = 1, type(ex).__name__ + ": " + str(ex)[-3500:]

    report = {
        "schema": 1,
        "source": source, "task": task, "script_id": script_id,
        "status": "success" if rc == 0 else "failure",
        "exit_code": rc, "duration_seconds": round(time.monotonic() - started, 3),
        "details": detail[-MAX_OUTPUT:],
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    }
    (output_dir / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(detail[-4000:])
    print("ZEIBAEL CI job:", task, "|", report["status"], "| details: public")
    return rc


if __name__ == "__main__":
    sys.exit(main())
