#!/usr/bin/env python3
"""Verify a signed Hatchable request before accessing private ZEIBAEL data."""
import hashlib
import hmac
import os
import re
import time

def main():
    key = os.environ.get("ZEIBAEL_DISPATCH_SIGNING_KEY", "")
    source = os.environ.get("ZEIBAEL_CI_SOURCE", "")
    task = os.environ.get("ZEIBAEL_CI_TASK", "")
    script_id = os.environ.get("ZEIBAEL_SCRIPT_ID", "")
    issued_at = os.environ.get("ZEIBAEL_ISSUED_AT", "")
    nonce = os.environ.get("ZEIBAEL_NONCE", "")
    signature = os.environ.get("ZEIBAEL_SIGNATURE", "")
    if source != "private":
        raise SystemExit("Only private CI requests require this authorization")
    if len(key) < 32:
        raise SystemExit("Hatchable signing secret missing")
    if task not in {"validate", "python_tests", "node_tests", "package", "script"}:
        raise SystemExit("Unsupported CI job")
    if task != "script" and script_id:
        raise SystemExit("Unexpected script_id")
    if task == "script" and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", script_id):
        raise SystemExit("Invalid script_id")
    if not re.fullmatch(r"[0-9]{10,12}", issued_at):
        raise SystemExit("Invalid issued_at")
    if not re.fullmatch(r"[a-f0-9]{32}", nonce):
        raise SystemExit("Invalid nonce")
    if not re.fullmatch(r"[a-f0-9]{64}", signature):
        raise SystemExit("Invalid signature")
    now = int(time.time())
    issued = int(issued_at)
    if issued > now + 60 or now - issued > 900:
        raise SystemExit("Expired request")
    message = f"v1|ci|{source}|{task}|{script_id}|{issued_at}|{nonce}"
    correct = hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, correct):
        raise SystemExit("Authorization rejected")
    print("Hatchable CI authorization verified.")

if __name__ == "__main__":
    main()
