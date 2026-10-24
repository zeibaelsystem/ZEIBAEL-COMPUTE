#!/usr/bin/env python3
"""Commit private CI report, and small build output, only to ZEIBAEL-SYSTEM."""
import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = "zeibaelsystem/ZEIBAEL-SYSTEM"
API = "https://api.github.com/repos/" + REPO + "/contents/"
MAX_BLOB = 700_000

def put(path, binary, token):
    payload = {
        "message": "ci: private ZEIBAEL build output [skip ci]",
        "branch": "main",
        "content": base64.b64encode(binary).decode("ascii"),
    }
    request = Request(API + path, method="PUT",
                      data=json.dumps(payload).encode(),
                      headers={"Authorization": "Bearer " + token,
                               "Accept": "application/vnd.github+json",
                               "Content-Type": "application/json",
                               "X-GitHub-Api-Version": "2022-11-28",
                               "User-Agent": "ZEIBAEL-CI"})
    try:
        with urlopen(request, timeout=45) as resp:
            if resp.status != 201:
                raise RuntimeError("Private upload rejected")
    except HTTPError as ex:
        raise RuntimeError(f"Private result storage failed (HTTP {ex.code})") from None

def main():
    token = os.environ.get("ZEIBAEL_PRIVATE_REPO_PAT", "")
    if not token:
        raise SystemExit("Missing private repository token in Actions secrets")
    source = os.environ.get("ZEIBAEL_CI_SOURCE")
    if source != "private":
        raise SystemExit("Refusing nonprivate result target")
    out = Path(os.environ["ZEIBAEL_CI_OUTPUT"])
    report_path = out / "result.json"
    if not report_path.is_file():
        raise SystemExit("Missing private CI report")
    report = json.loads(report_path.read_text())
    run = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    if not run.isdigit() or not attempt.isdigit():
        raise SystemExit("Missing run ID")
    prefix = f"compute-results/ci-{run}-attempt-{attempt}"
    zip_path = out / "zeibael-source.zip"
    if zip_path.is_file():
        if zip_path.stat().st_size <= MAX_BLOB and report["status"] == "success":
            put(prefix + ".zip", zip_path.read_bytes(), token)
            report["package_private_path"] = prefix + ".zip"
            report["package_saved"] = True
        else:
            report["package_saved"] = False
            report["package_note"] = "Package exceeds inline GitHub Contents upload budget. Metadata saved; ZIP not persisted."
    report_bytes = json.dumps(report, indent=2).encode()
    if len(report_bytes) > 100_000:
        raise SystemExit("Private report exceeds expected size")
    put(prefix + ".json", report_bytes, token)
    print("Private CI result saved to ZEIBAEL-SYSTEM; no public artifact created.")

if __name__ == "__main__":
    main()
