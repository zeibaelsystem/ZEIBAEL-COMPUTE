"""Bounded public Common Crawl WARC byte-range retrieval.

Use the free HTTPS data endpoint only; no S3 account, proxy, or redirects.
A reviewed caller supplies an archive index record; it is never a live target.
"""
from __future__ import annotations
import hashlib
import re
import socket
from scripts.acquisition_core import _PinnedHTTPSConnection,is_public_address

HOST="data.commoncrawl.org"
MAX_RECORD=2_000_000
PATH=re.compile(r"crawl-data/CC-MAIN-\d{4}-\d{2}/segments/[0-9.]+/warc/CC-MAIN-[0-9-]+\.warc\.gz")

def validate_entry(entry):
    if not isinstance(entry,dict) or entry.get("status")!="200":
        raise ValueError("Expected successful archive record")
    path=entry.get("filename")
    if not isinstance(path,str) or not PATH.fullmatch(path):
        raise ValueError("Invalid WARC path")
    for field in ("offset","length"):
        if not isinstance(entry.get(field),str) or not re.fullmatch(r"[0-9]{1,12}",entry[field]):
            raise ValueError("Invalid archive range")
    start,length=int(entry["offset"]),int(entry["length"])
    if not 1<=length<=MAX_RECORD:
        raise ValueError("Archive record size limit")
    end=start+length-1
    return {"host":HOST,"path":"/"+path,"start":start,"end":end,"length":length,
            "range":f"bytes={start}-{end}"}

def check_range(locator,status,content_range,body):
    expected=f'bytes {locator["start"]}-{locator["end"]}/'
    if status!=206 or not isinstance(content_range,str) or not content_range.startswith(expected):
        raise ValueError("Expected exact HTTP 206 range")
    total=content_range[len(expected):]
    if not re.fullmatch(r"[0-9]{1,15}",total) or int(total)<=locator["end"]:
        raise ValueError("Invalid archive total length")
    if len(body)!=locator["length"]:
        raise ValueError("Archive record length mismatch")
    return body

def fetch_range(entry):
    locator=validate_entry(entry)
    addresses=sorted({x[4][0] for x in socket.getaddrinfo(HOST,443,type=socket.SOCK_STREAM,proto=socket.IPPROTO_TCP)})
    if not addresses or not all(is_public_address(x) for x in addresses):
        raise ValueError("Non-public archive destination")
    conn=_PinnedHTTPSConnection(HOST,addresses[0])
    try:
        conn.request("GET",locator["path"],headers={"Range":locator["range"],"Accept-Encoding":"identity",
            "User-Agent":"ZEIBAEL-Acquisition/0.1","Connection":"close"})
        response=conn.getresponse()
        if response.status!=206:
            raise ValueError(f"Archive endpoint returned HTTP {response.status}; stop")
        if response.getheader("Content-Encoding","identity").lower()!="identity":
            raise ValueError("Unexpected HTTP content encoding")
        return check_range(locator,response.status,response.getheader("Content-Range",""),
                           response.read(locator["length"]+1))
    finally:
        conn.close()
