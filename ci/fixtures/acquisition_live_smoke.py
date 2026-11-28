"""Bounded live smoke against immutable, user-owned public repository files.

Two page requests maximum plus one robots request; no external crawl, no
credentials, no input URL, no dispatcher, no fallback around denial.
"""
import json

from scripts.acquisition_core import crawl

HOST = "raw.githubusercontent.com"
ROOT = "https://" + HOST + "/zeibaelsystem/ZEIBAEL-COMPUTE/293d5ab56c2b20b34d751ee2ee13f1b31c29bb93/"
TARGETS = [ROOT + "README.md", ROOT + "ci/jobs/zeibael_selfcheck.json"]


def main():
    report = crawl(TARGETS, {HOST}, max_pages=2, max_depth=0,
                   max_bytes=256000, max_total_bytes=1024000, max_queue=2)
    records = report["records"]
    compact = [{k: v for k, v in r.items() if k != "extraction"} for r in records]
    print("ZEIBAEL_LIVE_ACQUISITION=" + json.dumps({
        "source": "owned_public_repository", "records": compact,
        "pending": len(report["pending"]), "bytes_received": report["bytes_received"]
    }, sort_keys=True), flush=True)
    if len(records) != 2 or any(r["status"] != "ok" for r in records):
        raise SystemExit("Live acquisition did not complete; respect access or transport failure")
    assert "ZEIBAEL COMPUTE" in records[0]["extraction"]["text"]
    data = records[1]["extraction"]
    parsed = data["data"] if data["kind"] == "json" else json.loads(data["text"])
    assert parsed["schema"] == 1 and parsed["jobs"][0]["id"] == "python-check"
    print("ZEIBAEL_LIVE_ACQUISITION_PASS", flush=True)


if __name__ == "__main__":
    main()
