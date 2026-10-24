#!/usr/bin/env python3
"""Publish one bounded, inspectable JSON summary from GitHub Actions job reports."""
import json
import os
import sys
from pathlib import Path

def aggregate(root, expected_jobs=None, expected_ids=None):
    reports = []
    seen = set()
    for path in sorted(root.rglob("result.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("schema") != 1 or doc.get("status") not in {"success", "failure"}:
            raise ValueError("Unsupported result report")
        job_id = doc.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ValueError("Missing job identifier")
        if job_id in seen:
            raise ValueError("Duplicate job id in result reports: " + job_id)
        seen.add(job_id)
        if doc.get("exit_code") is not None and (doc["status"] == "success") != (doc["exit_code"] == 0):
            raise ValueError("Inconsistent report status and exit code for " + job_id)
        if doc.get("run_id") and os.environ.get("GITHUB_RUN_ID") and doc["run_id"] != os.environ["GITHUB_RUN_ID"]:
            raise ValueError("Report belongs to a different GitHub Actions run")
        reports.append({
            "job_id": job_id,
            "runtime": doc.get("runtime"),
            "task": doc.get("task"),
            "status": doc.get("status"),
            "exit_code": doc.get("exit_code"),
            "duration_seconds": doc.get("duration_seconds"),
            "run_id": doc.get("run_id"),
        })
    if not reports:
        raise ValueError("No job reports were produced")
    if expected_jobs is not None and len(reports) != expected_jobs:
        raise ValueError(f"Expected {expected_jobs} reports but received {len(reports)}; possible missing job report")
    if expected_ids is not None and set(expected_ids) != seen:
        raise ValueError("Expected job ids differ from received reports")
    return {
        "schema": 1,
        "status": "success" if all(r["status"] == "success" for r in reports) else "failure",
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "job_count": len(reports),
        "expected_jobs": expected_jobs,
        "jobs": reports,
    }

def main():
    raw_count = os.environ.get("ZEIBAEL_EXPECTED_JOBS")
    output_dir = Path(os.environ["ZEIBAEL_SUMMARY_DIR"])
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        expected = int(raw_count) if raw_count else None
        if expected is not None and not 1 <= expected <= 8:
            raise ValueError("Invalid expected job count")
        raw_ids = os.environ.get("ZEIBAEL_EXPECTED_JOB_IDS", "")
        expected_ids = raw_ids.split("|") if raw_ids else None
        if expected_ids is not None and expected is not None and len(expected_ids) != expected:
            raise ValueError("Expected job identifiers disagree with job count")
        doc = aggregate(Path(os.environ["ZEIBAEL_REPORT_DIR"]), expected_jobs=expected, expected_ids=expected_ids)
    except (ValueError, json.JSONDecodeError) as exc:
        doc = {
            "schema": 1, "status": "failure",
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "job_count": 0, "jobs": [],
            "error": str(exc)[:250],
        }
    (output_dir / "aggregate.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print("ZEIBAEL_AGGREGATE_JSON=" + json.dumps(doc, separators=(",", ":")))
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(f"### ZEIBAEL CI result: {doc['status']}\n")
            for entry in doc["jobs"]:
                f.write(f"- {entry['job_id']} ({entry['runtime']}): {entry['status']}\n")
            if doc.get("error"):
                f.write(f"- Error: {doc['error']}\n")
    return 0 if doc["status"] == "success" else 1

if __name__ == "__main__":
    sys.exit(main())
