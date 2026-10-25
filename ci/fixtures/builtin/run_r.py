"""Invoke pre-installed R on the Windows standard runner (no installation)."""
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parent
locations = [shutil.which("Rscript"), shutil.which("Rscript.exe")]
for home in (Path("C:/Program Files/R"), Path("C:/R")):
    if home.is_dir():
        locations.extend(str(x) for x in sorted(home.glob("R-*/bin/Rscript.exe"), reverse=True))
        locations.extend(str(x) for x in sorted(home.glob("R-*/bin/x64/Rscript.exe"), reverse=True))
selected = next((x for x in locations if x and Path(x).is_file()), None)
if selected is None:
    raise SystemExit("ZEIBAEL_RUNTIME_MISSING: Rscript not found on Windows image; this is toolchain availability, not GitHub quota")
sys.exit(subprocess.call([str(selected), str(root / "hello.R")]))
