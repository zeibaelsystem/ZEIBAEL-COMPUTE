"""Verify compiled executable output, not just compiler availability."""
import subprocess
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("Usage: python verify_binary.py <binary-path> <expected-output>")
binary = Path(sys.argv[1]).resolve()
if not binary.is_file():
    raise SystemExit(f"Executable missing: {binary}")
result = subprocess.run([str(binary)], check=True, capture_output=True, text=True, timeout=15)
if sys.argv[2] not in result.stdout:
    raise SystemExit(f"Unexpected compiled binary output: {result.stdout!r}")
print(result.stdout.strip())
