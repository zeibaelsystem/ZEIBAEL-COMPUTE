"""Bounded offline OCR for trusted fixtures/local inputs.

This module is not a sandbox for hostile documents. The caller is responsible
for network isolation, unprivileged execution and a reviewed resource envelope.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

MAX_BYTES=8_000_000
MAX_PAGES=5
MAX_PIXELS=12_000_000
MAX_TEXT=100_000


def _run(argv, directory, timeout=30):
    env={"PATH":"/usr/bin:/bin","HOME":str(directory),"OMP_THREAD_LIMIT":"2",
         "LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}
    try:
        result=subprocess.run(argv,cwd=directory,env=env,stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              timeout=timeout,check=True)
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        raise ValueError("Offline OCR/raster execution failed") from exc
    if len(result.stdout)>MAX_TEXT:
        raise ValueError("OCR output limit")
    return result.stdout


def _check_image(path):
    from PIL import Image
    try:
        with Image.open(path) as img:
            w,h=img.size
            if w<=0 or h<=0 or w*h>MAX_PIXELS:
                raise ValueError("Image pixel limit")
            img.verify()
    except (OSError,Image.DecompressionBombError) as exc:
        raise ValueError("Invalid raster image") from exc


def extract_ocr(raw,kind):
    """Extract page-indexed English OCR from trusted PNG or scanned PDF bytes."""
    if not isinstance(raw,bytes) or not 1<=len(raw)<=MAX_BYTES:
        raise ValueError("Input byte limit")
    if kind=="png":
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Invalid PNG signature")
    elif kind=="pdf":
        if not raw.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF signature")
    else:
        raise ValueError("Unsupported OCR format")
    with tempfile.TemporaryDirectory() as tmp:
        directory=Path(tmp)
        source=directory/("input."+kind)
        source.write_bytes(raw)
        if kind=="pdf":
            info=_run(["pdfinfo",str(source)],directory).decode("utf-8","replace")
            import re
            match=re.search(r"(?m)^Pages:\s*(\d+)\s*$",info)
            if not match or not 1<=int(match.group(1))<=MAX_PAGES:
                raise ValueError("PDF page limit")
            count=int(match.group(1))
            _run(["pdftoppm","-f","1","-l",str(count),"-scale-to","2200",
                  "-png",str(source),str(directory/"page")],directory)
            images=sorted(directory.glob("page-*.png"),
                          key=lambda p:int(p.stem.rsplit("-",1)[-1]))
            if len(images)!=count:
                raise ValueError("Raster page count mismatch")
        else:
            images=[source]
        units=[]
        for i,path in enumerate(images):
            _check_image(path)
            text=_run(["tesseract",str(path),"stdout","-l","eng","--psm","6"],directory)
            units.append({"page":i+1,"text":text.decode("utf-8","strict").strip()})
        return {"kind":kind,"sha256":hashlib.sha256(raw).hexdigest(),"units":units,
                "adapter":"tesseract_poppler_local","scope":"trusted_input_only"}
