#!/usr/bin/env python3
"""ZEIBAEL ephemeral bridge: private GitHub JSON -> runner -> private GitHub JSON.

This program never writes source data into the public repository, log or artifact.
The script is intentionally a fixed, non-executable JSON inspection workload.
"""
import base64
import hashlib
import json
import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

PRIVATE_REPO = "zeibaelsystem/ZEIBAEL-SYSTEM"
DATASETS = {
    "manifest": "capability-registry/manifest.json",
    "plugins": "capability-registry/plugins.json",
    "capabilities": "capability-registry/capabilities.json",
    "skills": "capability-registry/skills.json",
    "tools": "capability-registry/tools.json",
}
MAX_INPUT_BYTES = 900_000


def api_request(method, path, token, payload=None):
    url = "https://api.github.com" + path
    headers = {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ZEIBAEL-Ephemeral-Compute",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Private GitHub API {method} request failed (HTTP {exc.code})") from None
    except URLError:
        raise RuntimeError("Private GitHub API connection failed") from None


def inspect_json(raw):
    parsed = json.loads(raw.decode("utf-8"))
    if isinstance(parsed, dict):
        shape = "object"
        count = len(parsed)
    elif isinstance(parsed, list):
        shape = "array"
        count = len(parsed)
    else:
        shape = "scalar"
        count = 1
    return {
        "format": "json",
        "json_shape": shape,
        "top_level_items": count,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "valid_json": True,
    }


def main():
    if os.environ.get("GITHUB_ACTOR") != "zeibaelsystem":
        raise RuntimeError("Unauthorized GitHub actor")
    if os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise RuntimeError("Unsupported GitHub event")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("Unsupported GitHub branch")

    dataset = os.environ.get("ZEIBAEL_DATASET", "")
    if dataset not in DATASETS:
        raise RuntimeError("Dataset not allowlisted")
    token = os.environ.get("ZEIBAEL_PRIVATE_REPO_PAT")
    if not token:
        raise RuntimeError("Missing ZEIBAEL_PRIVATE_REPO_PAT Actions secret")
    run_id = os.environ["GITHUB_RUN_ID"]
    attempt = os.environ["GITHUB_RUN_ATTEMPT"]
    if not run_id.isdigit() or not attempt.isdigit():
        raise RuntimeError("Unexpected workflow run identifier")

    source = DATASETS[dataset]
    api_path = "/repos/" + PRIVATE_REPO + "/contents/" + quote(source, safe="/")
    status, obj = api_request("GET", api_path + "?ref=main", token)
    if status != 200 or obj.get("type") != "file":
        raise RuntimeError("Private source is not a file")
    if obj.get("encoding") != "base64":
        raise RuntimeError("Private source encoding unsupported")
    contents = base64.b64decode(obj["content"].replace("\n", ""), validate=True)
    if len(contents) > MAX_INPUT_BYTES:
        raise RuntimeError("Input exceeds bounded compute size")

    # All plaintext processing happens in a temporary directory on the runner.
    # Never print source, include it in job summaries, or upload a public artifact.
    with tempfile.TemporaryDirectory(prefix="zeibael-private-", dir=os.environ.get("RUNNER_TEMP")) as temp:
        private_file = Path(temp) / "input.json"
        private_file.write_bytes(contents)
        private_file.chmod(0o600)
        checked = inspect_json(private_file.read_bytes())

        report = {
            "schema_version": 1,
            "source_repository": PRIVATE_REPO,
            "source_path": source,
            "source_blob_sha": obj.get("sha"),
            "dataset": dataset,
            "workflow_run_id": run_id,
            "workflow_attempt": attempt,
            "result": checked,
        }
        destination = f"compute-results/{run_id}-attempt-{attempt}.json"
        dest_api_path = "/repos/" + PRIVATE_REPO + "/contents/" + quote(destination, safe="/")
        encoded_report = base64.b64encode(
            json.dumps(report, indent=2, sort_keys=True).encode("utf-8")
        ).decode("ascii")
        write_status, _ = api_request("PUT", dest_api_path, token, {
            "message": "chore: private compute result [skip ci]",
            "content": encoded_report,
            "branch": "main",
        })
        if write_status != 201:
            raise RuntimeError("Private result was not created")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as output:
            output.write("### ZEIBAEL ephemeral private compute\n")
            output.write("Processing completed. Result stored in private repository.\n")
            output.write("No private contents written to logs or public artifacts.\n")
    print("Completed: private input processed; private result committed; temporary workspace removed.")


if __name__ == "__main__":
    main()
