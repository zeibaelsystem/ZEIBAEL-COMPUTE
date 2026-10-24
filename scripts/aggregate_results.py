#!/usr/bin/env python3
"""Publish one bounded, inspectable JSON summary from GitHub Actions job reports."""
import json
import os
import sys
from pathlib import Path

def aggregate(root):
    reports = []
    for path in sorted(root.rglob("result.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("schema") != 1 or doc.get("status") not in {"success", "failure"}:
            raise ValueError("Unsupported result report")
        reports.append({
            "job_id": doc.get("job_id"),
            "runtime": doc.get("runtime"),
            "task": doc.get("task"),
            "status": doc.get("status"),
            "exit_code": doc.get("exit_code"),
            "duration_seconds": doc.get("duration_seconds"),
            "run_id": doc.get("run_id"),
        })
    if not reports:
        raise ValueError("No job reports were produced")
    return {
        "schema": 1,
        "status": "success" if all(r["status"] == "success" for r in reports) else "failure",
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "job_count": len(reports),
        "jobs": reports,
    }

def main():
    doc = aggregate(Path(os.environ["ZEIBAEL_REPORT_DIR"]))
    output_dir = Path(os.environ["ZEIBAEL_SUMMARY_DIR"])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "aggregate.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print("ZEIBAEL_AGGREGATE_JSON=" + json.dumps(doc, separators=(",", ":")))
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(f"### ZEIBAEL CI result: {doc['status']}\n")
            for entry in doc["jobs"]:
                f.write(f"- {entry['job_id']} ({entry['runtime']}): {entry['status']}\n")
    return 0 if doc["status"] == "success" else 1

if __name__ == "__main__":
    sys.exit(main())
