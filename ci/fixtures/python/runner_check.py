"""Verify that GitHub actually scheduled the requested host OS and CPU."""
import os
import platform
import sys

if len(sys.argv) != 3:
    raise SystemExit("Usage: runner_check.py <Linux|Windows|macOS> <ARM64|X64>")
target_os, target_arch = sys.argv[1:]
got_os = os.environ.get("RUNNER_OS", "")
got_arch = os.environ.get("RUNNER_ARCH", "")
if (got_os, got_arch) != (target_os, target_arch):
    raise SystemExit(f"Wrong runner: expected {(target_os, target_arch)}, received {(got_os, got_arch)}")
machine = platform.machine().lower()
if target_arch == "ARM64" and machine not in ("aarch64", "arm64"):
    raise SystemExit(f"Expected physical ARM64: {machine}")
if target_arch == "X64" and machine not in ("x86_64", "amd64"):
    raise SystemExit(f"Expected physical x86-64: {machine}")
print(f"ZEIBAEL_RUNNER_OK: {got_os} {got_arch}; {platform.system()} {machine}; Python {platform.python_version()}")
