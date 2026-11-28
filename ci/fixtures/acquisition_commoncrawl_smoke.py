"""One reviewed archive record; no arbitrary live URL."""
import json
import hashlib
from scripts.acquisition_commoncrawl import fetch_range
from scripts.acquisition_data_formats import read_warc

ENTRY={"url":"https://example.com/","timestamp":"20261005112841","status":"200",
       "filename":"crawl-data/CC-MAIN-2026-43/segments/1791170053823.21/warc/CC-MAIN-20261005105623-20261005135623-00162.warc.gz",
       "offset":"204233603","length":"996"}

def main():
    raw=fetch_range(ENTRY)
    records=read_warc(raw)
    assert len(records)==1,records
    record=records[0]
    assert record["url"]==ENTRY["url"] and record["http_status"]=="200",record
    assert record["status"]=="ok" and record["extraction"]["title"]=="Example Domain",record
    assert "documentation examples" in record["extraction"]["text"],record
    assert record["captured_at"]=="2026-10-05T11:28:41Z",record
    print("ZEIBAEL_COMMONCRAWL="+json.dumps({"status":"PASS","http_status":206,"bytes":len(raw),
          "archive_sha256":hashlib.sha256(raw).hexdigest(),"record_url":record["url"],
          "captured_at":record["captured_at"],"records":len(records)}),flush=True)
if __name__=="__main__":main()
