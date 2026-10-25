#!/usr/bin/env python3
"""Validate committed public CI jobs and build a bounded GitHub Actions matrix.

Only a reviewed filename, not a shell command or untrusted runtime parameter,
comes from workflow_dispatch. The manifest is committed to this public repo.
"""
import json
import os
import re
from pathlib import Path
try:
    from scripts.runtime_router import BUILTIN_RUNNERS, resolve_language, select_runner
except ModuleNotFoundError:
    from runtime_router import BUILTIN_RUNNERS, resolve_language, select_runner

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
RUNTIMES = set(BUILTIN_RUNNERS)
# Internally approved combinations for NEW runtimes. Provider runners may
# support more combinations; do not claim this ZEIBAEL policy is a GitHub limit.
NEW_RUNTIME_RUNNERS = {
    "php": {"ubuntu-24.04", "ubuntu-24.04-arm", "windows-2022",
            "windows-11-arm", "macos-15-intel"},
    "ruby": {"ubuntu-24.04", "ubuntu-24.04-arm", "windows-2022",
             "windows-11-arm", "macos-15-intel", "macos-15"},
    "dotnet": {"ubuntu-24.04", "ubuntu-24.04-arm", "windows-2022",
               "windows-11-arm", "macos-15-intel", "macos-15"},
    "kotlin": {"ubuntu-24.04", "ubuntu-24.04-arm", "windows-2022",
               "windows-11-arm", "macos-15-intel", "macos-15"},
    "swift": {"ubuntu-24.04", "ubuntu-24.04-arm", "macos-15-intel", "macos-15"},
    # Conservatively approved built-in tools only. These are ZEIBAEL caps.
    "powershell": {"ubuntu-24.04"},
    "perl": {"ubuntu-24.04"},
    "julia": {"ubuntu-24.04"},
    "haskell": {"ubuntu-24.04"},
    "fortran": {"ubuntu-24.04"},
    "r": {"windows-2022"},
    "scala": {"windows-2022"},
}
RUNNERS = {"ubuntu-24.04", "ubuntu-24.04-arm", "windows-2022", "windows-11-arm",
           "macos-15", "macos-15-intel", "ubuntu-slim"}
TIMEOUTS = {"short": 10, "standard": 30, "long": 120, "extended": 330}
TASKS = {"validate", "python_tests", "node_tests", "package", "script"}
MAX_JOBS = 20
MAX_COMMANDS = 12

def read_manifest(root, script_id):
    if not IDENTIFIER.fullmatch(script_id or ""):
        raise ValueError("Invalid script_id")
    path = root / "ci" / "jobs" / (script_id + ".json")
    if not path.is_file() or path.is_symlink():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "jobs"} or manifest["schema"] != 1:
        raise ValueError("Manifest must contain schema=1 and jobs")
    jobs = manifest["jobs"]
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= MAX_JOBS:
        raise ValueError("Expected 1–20 jobs")
    seen = set()
    for job in jobs:
        if not isinstance(job, dict) or not {"id", "timeout_profile", "commands"}.issubset(job) or set(job) - {"id", "runtime", "runner", "language", "timeout_profile", "commands", "output_files"}:
            raise ValueError("Invalid job fields")
        if not isinstance(job.get("output_files", False), bool):
            raise ValueError("output_files must be true or false")
        name = job["id"]
        if not isinstance(name, str) or not IDENTIFIER.fullmatch(name) or name in seen:
            raise ValueError("Job ids must be unique safe identifiers")
        seen.add(name)
        if "language" in job:
            inferred = resolve_language(job["language"])
            if job.get("runtime", "auto") not in ("auto", inferred):
                raise ValueError("Explicit runtime conflicts with reviewed language")
            job["runtime"] = inferred
        if job.get("runtime") not in RUNTIMES and job.get("runtime") != "auto":
            raise ValueError("Unsupported ZEIBAEL runtime")
        if job.get("runtime") in (None, "auto"):
            raise ValueError("A supported runtime or language is required")
        if job.get("runner") in (None, "auto"):
            job["runner"] = select_runner(job["runtime"])
        if job["runtime"] not in RUNTIMES or job["runner"] not in RUNNERS or job["timeout_profile"] not in TIMEOUTS:
            raise ValueError("Unsupported runtime/runner/timeout_profile")
        if job["runtime"] in NEW_RUNTIME_RUNNERS and job["runner"] not in NEW_RUNTIME_RUNNERS[job["runtime"]]:
            raise ValueError("Unsupported runtime/runner combination in ZEIBAEL internal allowlist")
        if job["runner"] == "ubuntu-slim" and (job["timeout_profile"] != "short" or job["runtime"] != "python"):
            raise ValueError("ubuntu-slim requires short Python jobs (max 10 minutes)")
        if job["runtime"] == "docker" and job["runner"] != "ubuntu-24.04":
            raise ValueError("Docker requires Ubuntu")
        commands = job["commands"]
        if not isinstance(commands, list) or not 1 <= len(commands) <= MAX_COMMANDS:
            raise ValueError("Commands must contain 1–12 argv arrays")
        for argv in commands:
            if not isinstance(argv, list) or not 1 <= len(argv) <= 30:
                raise ValueError("Each command must be an argv array")
            if any(not isinstance(a, str) or not a or len(a) > 512 or "\x00" in a or "\n" in a or "\r" in a for a in argv):
                raise ValueError("Invalid argv argument")
            # No shell=True: arguments cannot inject shell control operators.
            if argv[0] not in {"python", "python3", "node", "npm", "go", "cargo", "rustc", "java", "javac", "docker", "bash", "gcc", "g++", "php", "ruby", "dotnet", "kotlinc", "swift", "pwsh", "perl", "julia", "ghc", "runghc", "gfortran", "Rscript", "sbt"}:
                raise ValueError("Command executable not on approved runtime list")
            if argv[0] == "bash" and (len(argv) < 2 or argv[1].startswith("-")):
                raise ValueError("Bash must run a reviewed script file, not -c")
    return manifest

def build_plan(root, task, script_id):
    if task not in TASKS or (task != "script" and script_id):
        raise ValueError("Invalid CI task or script_id")
    if task == "script":
        manifest = read_manifest(root, script_id)
        if manifest:
            jobs = manifest["jobs"]
        else:
            if not IDENTIFIER.fullmatch(script_id or ""):
                raise ValueError("Invalid script_id")
            base = root / "ci" / "jobs"
            if not any((base / (script_id + ext)).is_file() for ext in (".py", ".sh")):
                raise ValueError("Script file is not present in ci/jobs")
            jobs = [{"id": "script", "runtime": "python", "runner": "ubuntu-24.04",
                     "timeout_profile": "standard", "commands": []}]
    else:
        jobs = [{"id": task, "runtime": "node" if task == "node_tests" else "python",
                 "runner": "ubuntu-24.04", "timeout_profile": "standard", "commands": []}]
    return {"include": [
        {"id": j["id"], "runtime": j["runtime"], "runner": j["runner"],
         "timeout": TIMEOUTS[j["timeout_profile"]], "output_files": j.get("output_files", False), "index": index}
        for index, j in enumerate(jobs)
    ]}

def main():
    root = Path(os.environ["ZEIBAEL_CI_ROOT"]).resolve()
    task = os.environ.get("ZEIBAEL_CI_TASK", "")
    script_id = os.environ.get("ZEIBAEL_SCRIPT_ID", "")
    plan = build_plan(root, task, script_id)
    value = json.dumps(plan, separators=(",", ":"))
    print("ZEIBAEL_MATRIX=" + value)
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write("matrix=" + value + "\n")
        f.write("job_count=" + str(len(plan["include"])) + "\n")
        f.write("job_ids=" + "|".join(item["id"] for item in plan["include"]) + "\n")

if __name__ == "__main__":
    main()
