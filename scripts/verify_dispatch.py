#!/usr/bin/env python3
"""Require a time-limited Hatchable HMAC authorization before private data access."""
import hashlib
import hmac
import os
import re
import time


def main():
    key = os.environ.get("ZEIBAEL_DISPATCH_SIGNING_KEY", "")
    dataset = os.environ.get("ZEIBAEL_DATASET", "")
    issued_text = os.environ.get("ZEIBAEL_ISSUED_AT", "")
    nonce = os.environ.get("ZEIBAEL_NONCE", "")
    supplied = os.environ.get("ZEIBAEL_SIGNATURE", "")
    if len(key) < 32:
        raise SystemExit("Dispatcher signing key is not configured or too short.")
    if dataset not in {"manifest", "plugins", "capabilities", "skills", "tools"}:
        raise SystemExit("Dataset rejected.")
    if not re.fullmatch(r"[0-9]{10,12}", issued_text):
        raise SystemExit("Invalid dispatcher timestamp.")
    if not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise SystemExit("Invalid dispatcher nonce.")
    if not re.fullmatch(r"[0-9a-f]{64}", supplied):
        raise SystemExit("Missing or invalid dispatcher signature.")
    issued = int(issued_text)
    now = int(time.time())
    if issued > now + 60 or now - issued > 900:
        raise SystemExit("Dispatcher authorization expired.")
    payload = f"v1|private_compute|{dataset}|{issued_text}|{nonce}".encode("utf-8")
    expected = hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise SystemExit("Dispatcher authorization signature rejected.")
    print("Authorized Hatchable-signed compute request.")


if __name__ == "__main__":
    main()
