"""Use the pre-installed Windows sbt + JDK21 for a reviewed Scala fixture."""
from pathlib import Path
import shutil
import subprocess

project = Path(__file__).resolve().parent / "scala"
sbt = shutil.which("sbt.bat") or shutil.which("sbt.cmd") or shutil.which("sbt")
if not sbt:
    raise SystemExit("ZEIBAEL_RUNTIME_MISSING: sbt not found in reviewed Windows runner")
subprocess.run([sbt, "-batch", "runMain ZeibaelSmoke"], cwd=project, check=True)
