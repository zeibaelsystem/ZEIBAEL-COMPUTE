"""Read failed GitHub Actions jobs without rerunning them; publish sanitized diagnosis.

Invoked from a read-only workflow_run event. Never executes checked-out PR code,
never emits raw job logs or tokens, and never calls a write API.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.failure_diagnosis import summarize_failed_jobs

MAX_LOG_BYTES = 1_500_000
MAX_JOBS = 100


class NoCrossHostAuth(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req and urllib.parse.urlsplit(req.full_url).netloc != urllib.parse.urlsplit(newurl).netloc:
            new_req.remove_header("Authorization")
        return new_req


def read_api(url, token):
    """Only call authenticated api.github.com endpoints; strip auth on signed log redirects."""
    if not url.startswith("https://api.github.com/repos/"):
        raise ValueError("Unexpected API endpoint")
    req = urllib.request.Request(
        url, headers={"Authorization": "Bearer " + token,
                      "Accept": "application/vnd.github+json",
                      "User-Agent": "ZEIBAEL-read-only-diagnosis"})
    with urllib.request.build_opener(NoCrossHostAuth()).open(req, timeout=20) as resp:
        return resp.read(MAX_LOG_BYTES)


def diagnose_run(repo, run_id, token):
    if not isinstance(run_id, int) or run_id < 1:
        raise ValueError("Invalid run ID")
    if not isinstance(repo, str) or repo.count("/") != 1 or not all(part.replace("-", "").replace("_", "").isalnum() for part in repo.split("/")):
        raise ValueError("Invalid repository")
    base = f"https://api.github.com/repos/{repo}"
    payload = json.loads(read_api(f"{base}/actions/runs/{run_id}/jobs?per_page=100", token))
    jobs = sorted(payload.get("jobs", [])[:MAX_JOBS], key=lambda j: j.get("started_at") or "")
    failures = []
    for job in jobs:
        if job.get("conclusion") != "failure":
            continue
        jid = job.get("id")
        try:
            content = read_api(f"{base}/actions/jobs/{int(jid)}/logs", token).decode("utf-8", errors="replace")
        except (ValueError, urllib.error.URLError, OSError):
            content = ""
        failures.append({"name": str(job.get("name", "")), "conclusion": "failure", "log": content})
    result = summarize_failed_jobs(failures)
    return {"schema": 1, "source_run_id": run_id, "repository": repo,
            "failed_job_count": len(failures), "diagnosis": result,
            "note": "Read-only diagnosis; UNKNOWN when evidence is insufficient; no automatic retry"}


def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    run = event.get("workflow_run") or {}
    repo = os.environ["GITHUB_REPOSITORY"]
    if (event.get("repository") or {}).get("full_name") != repo:
        raise ValueError("Event repository mismatch")
    if run.get("conclusion") != "failure":
        raise ValueError("Only failed source workflows may be diagnosed")
    try:
        result = diagnose_run(repo, run["id"], os.environ["GITHUB_TOKEN"])
    except (ValueError, KeyError, OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        result = {"schema": 1, "source_run_id": run.get("id"), "repository": repo,
                  "diagnosis": {"category": "UNKNOWN", "confidence": "none", "first_error": "",
                                "reason": "GitHub failed-run logs unavailable for read-only attribution"}}
    target = Path(os.environ["ZEIBAEL_DIAG_OUTPUT"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    diag = result["diagnosis"]
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
        summary.write("### ZEIBAEL failure diagnosis (source workflow)\n\n")
        summary.write(f"- Source run: {result.get('source_run_id')}\n")
        summary.write(f"- Classification: **{diag['category']}** (confidence: {diag['confidence']})\n")
        summary.write(f"- First evidence: `{diag.get('first_error', '')}`\n")
        summary.write(f"- Reason: {diag['reason']}\n")
        summary.write("- No workflows retried; billing and runner configuration unchanged.\n")
    print(f"ZEIBAEL_DIAGNOSIS={diag['category']}; run={result.get('source_run_id')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
