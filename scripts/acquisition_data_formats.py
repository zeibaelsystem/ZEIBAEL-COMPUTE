"""Trusted local format adapters; no remote URLs, cloud APIs or dispatcher.

These bounded fixtures do not establish sandbox isolation for hostile files.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import tempfile
from pathlib import Path

from scripts.acquisition_core import parse_document

MAX_INPUT = 8_000_000
MAX_WARC_PAYLOAD = 256_000
MAX_RECORDS = 1000
MAX_CELLS = 100_000


def _bytes(raw):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_INPUT:
        raise ValueError("Expected bounded local bytes")
    return raw


def read_warc(raw):
    """Extract archived HTTP response records from supplied WARC bytes."""
    from warcio.archiveiterator import ArchiveIterator
    records = []
    for index, record in enumerate(ArchiveIterator(io.BytesIO(_bytes(raw)))):
        if index >= MAX_RECORDS:
            raise ValueError("WARC record count limit")
        if record.rec_type != "response" or record.http_headers is None:
            continue
        body = record.content_stream().read(MAX_WARC_PAYLOAD + 1)
        if len(body) > MAX_WARC_PAYLOAD:
            raise ValueError("Archived payload limit")
        url = record.rec_headers.get_header("WARC-Target-URI")
        if not url:
            raise ValueError("Missing archived target URI")
        kind = record.http_headers.get_header("Content-Type") or ""
        item = {"url": url, "captured_at": record.rec_headers.get_header("WARC-Date"),
                "http_status": record.http_headers.get_statuscode(),
                "sha256": hashlib.sha256(body).hexdigest(), "content_type": kind}
        try:
            item.update(status="ok", extraction=parse_document(body, kind, url))
        except ValueError:
            item["status"] = "unsupported_or_invalid_document"
        records.append(item)
    return records


def read_feed(raw):
    """Parse RSS/Atom bytes without downloading linked content."""
    import feedparser
    raw = _bytes(raw)
    if re.search(br"<!\s*(DOCTYPE|ENTITY)\b", raw.replace(b"\0", b""), re.I):
        raise ValueError("DTD and entity declarations prohibited")
    parsed = feedparser.parse(raw)
    if parsed.bozo:
        raise ValueError("Malformed feed")
    if len(parsed.entries) > MAX_RECORDS:
        raise ValueError("Feed entry count limit")
    return [{"id": entry.get("id"), "title": entry.get("title"),
             "link": entry.get("link"), "published": entry.get("published"),
             "updated": entry.get("updated")} for entry in parsed.entries]


def read_parquet(raw):
    """Read local Parquet with Polars and cross-check row count in DuckDB."""
    import duckdb
    import polars as pl
    raw = _bytes(raw)
    if not raw.startswith(b"PAR1") or not raw.endswith(b"PAR1"):
        raise ValueError("Expected Parquet signature")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixture.parquet"
        path.write_bytes(raw)
        con = duckdb.connect(":memory:", config={"autoinstall_known_extensions": "false"})
        try:
            count = con.execute("SELECT count(*) FROM read_parquet(?)", [str(path)]).fetchone()[0]
            if count > MAX_RECORDS:
                raise ValueError("Parquet fixture row limit")
        finally:
            con.close()
        frame = pl.read_parquet(path)
        if frame.height != count or frame.height * frame.width > MAX_CELLS:
            raise ValueError("Parquet shape mismatch or limit")
        return {"row_count": frame.height, "duckdb_row_count": count,
                "columns": frame.columns, "rows": frame.to_dicts(),
                "sha256": hashlib.sha256(raw).hexdigest()}


def read_geojson(raw):
    """Extract FeatureCollection geometry metadata; bounds remain source CRS units."""
    from shapely.geometry import shape
    doc = json.loads(_bytes(raw))
    if not isinstance(doc, dict) or doc.get("type") != "FeatureCollection":
        raise ValueError("Expected GeoJSON FeatureCollection")
    features = doc.get("features")
    if not isinstance(features, list) or len(features) > MAX_RECORDS:
        raise ValueError("Invalid feature count")
    records = []
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature" or not feature.get("geometry"):
            raise ValueError("Missing feature geometry")
        geom = shape(feature["geometry"])
        bounds = list(geom.bounds)
        if geom.is_empty or not geom.is_valid or not all(math.isfinite(n) for n in bounds):
            raise ValueError("Invalid or empty geometry")
        records.append({"geometry_type": geom.geom_type, "bounds": bounds,
                        "properties": feature.get("properties")})
    return records


def read_netcdf(raw):
    """Read trusted classic NetCDF using local xarray/SciPy, no remote datasets."""
    import xarray as xr
    raw = _bytes(raw)
    if raw[:4] not in {b"CDF\x01", b"CDF\x02"}:
        raise ValueError("Expected classic NetCDF signature")
    with xr.open_dataset(io.BytesIO(raw), engine="scipy", decode_times=False,
                         mask_and_scale=False, cache=False) as ds:
        if len(ds.variables) > 100 or sum(int(v.size) for v in ds.variables.values()) > MAX_CELLS:
            raise ValueError("Scientific fixture variable or element limit")
        return {"dimensions": dict(ds.sizes),
                "variables": {name: {"dimensions": list(var.dims), "values": var.values.tolist()}
                              for name, var in ds.data_vars.items()},
                "sha256": hashlib.sha256(raw).hexdigest()}
