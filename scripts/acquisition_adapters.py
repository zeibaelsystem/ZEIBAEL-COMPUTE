"""Opt-in, offline open-source acquisition adapters.

This module is not dispatched by the public runner. The HTTPX adapter is
explicitly restricted to MockTransport fixtures; use the reviewed core for
network policy. Only trusted/synthetic documents until sandbox and resource
isolation have been independently verified.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from datetime import date, datetime, time
from pathlib import PurePosixPath

from scripts.acquisition_core import Response, canonical_url

MAX_INPUT = 8_000_000
MAX_EXPANDED = 64_000_000
MAX_MEMBER = 16_000_000
MAX_ENTRIES = 2000
MAX_UNITS = 100
MAX_TEXT = 1_000_000
MAX_ROWS = 2000
MAX_COLS = 100


def _check_input(raw):
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_INPUT:
        raise ValueError("Expected bounded nonempty bytes")


def _check_office(raw):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            infos = z.infolist()
            if len(infos) > MAX_ENTRIES:
                raise ValueError("Too many archive members")
            total = 0
            names = set()
            for info in infos:
                p = PurePosixPath(info.filename)
                if (p.is_absolute() or ".." in p.parts or "\\" in info.filename
                        or ":" in info.filename or info.filename in names
                        or info.flag_bits & 1 or (info.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError("Unsafe archive member")
                names.add(info.filename)
                total += info.file_size
                if info.file_size > MAX_MEMBER or total > MAX_EXPANDED:
                    raise ValueError("Expanded archive limit")
                if info.file_size > max(100000, info.compress_size * 200):
                    raise ValueError("Suspicious archive expansion ratio")
                if info.filename.lower().endswith((".xml", ".rels")):
                    with z.open(info) as stream:
                        body = stream.read(MAX_MEMBER + 1)
                    if len(body) > MAX_MEMBER:
                        raise ValueError("XML member limit")
                    if re.search(br"<!\s*(DOCTYPE|ENTITY)\b", body.replace(b"\0", b""), re.I):
                        raise ValueError("DTD or entity declarations prohibited")
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ValueError("Invalid Office archive") from exc


def _text(value):
    return (value or "")[:MAX_TEXT]


def _cell(value):
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, str):
        return value[:MAX_TEXT]
    return value


def extract_document(raw, kind):
    """Extract bounded content from trusted PDF/DOCX/PPTX/XLSX bytes."""
    _check_input(raw)
    if kind not in {"pdf", "docx", "pptx", "xlsx"}:
        raise ValueError("Unsupported document format")
    if kind != "pdf":
        _check_office(raw)
    result = {"kind": kind, "sha256": hashlib.sha256(raw).hexdigest()}
    stream = io.BytesIO(raw)
    if kind == "pdf":
        if not raw.startswith(b"%PDF-"):
            raise ValueError("Expected PDF signature")
        from pypdf import PdfReader
        pdf = PdfReader(stream, strict=True)
        if pdf.is_encrypted:
            raise ValueError("Encrypted documents not supported")
        count = len(pdf.pages)
        result["units"] = [{"page": i + 1, "text": _text(pdf.pages[i].extract_text())}
                           for i in range(min(count, MAX_UNITS))]
        result["truncated"] = count > MAX_UNITS
    elif kind == "docx":
        from docx import Document
        doc = Document(stream)
        result["text"] = _text("\n".join(p.text for p in doc.paragraphs[:MAX_ROWS]))
        tables = doc.tables
        result["tables"] = [
            [[_text(c.text) for c in row.cells[:MAX_COLS]]
             for row in table.rows[:MAX_ROWS]] for table in tables[:MAX_UNITS]
        ]
        result["truncated"] = len(doc.paragraphs) > MAX_ROWS or len(tables) > MAX_UNITS
    elif kind == "pptx":
        from pptx import Presentation
        slides = Presentation(stream).slides
        units = []
        for i, slide in enumerate(slides):
            if i >= MAX_UNITS:
                break
            parts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    parts.append(shape.text)
            units.append({"slide": i + 1, "text": _text("\n".join(parts))})
        result["units"] = units
        result["truncated"] = len(slides) > MAX_UNITS
    else:
        from openpyxl import load_workbook
        book = load_workbook(stream, read_only=True, data_only=False, keep_links=False)
        try:
            units = []
            truncated = len(book.worksheets) > MAX_UNITS
            for sheet in book.worksheets[:MAX_UNITS]:
                if sheet.max_row is None or sheet.max_column is None:
                    raise ValueError("Unknown worksheet dimensions")
                if sheet.max_row > MAX_ROWS or sheet.max_column > MAX_COLS:
                    truncated = True
                rows = [[_cell(c) for c in row] for row in sheet.iter_rows(
                    max_row=min(sheet.max_row, MAX_ROWS),
                    max_col=min(sheet.max_column, MAX_COLS), values_only=True)]
                units.append({"sheet": sheet.title, "rows": rows})
            result.update(units=units, truncated=truncated)
        finally:
            book.close()
    return result


def extract_html(raw, url):
    """Use real Scrapy response selectors on supplied bytes, not a live crawl."""
    _check_input(raw)
    from scrapy.http import HtmlResponse
    response = HtmlResponse(url=url, body=raw, encoding="utf-8")
    titles = [x.strip() for x in response.css("h1::text").getall()[:100]]
    links = [response.urljoin(x) for x in response.css("a::attr(href)").getall()[:1000]]
    return {"titles": titles, "links": list(dict.fromkeys(links))}


def read_mock_response(client, url, max_bytes):
    """HTTPX fixture bridge only: refuse a real network transport."""
    import httpx
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_INPUT:
        raise ValueError("Invalid byte limit")
    url = canonical_url(url, {"example.org", "example.net"})
    # The effective transport matters: mounted transports can differ from the
    # default client transport. This pinned-version seam is fixture-only.
    if not isinstance(client, httpx.Client) or not isinstance(
            client._transport_for_url(httpx.URL(url)), httpx.MockTransport):
        raise ValueError("Only HTTPX MockTransport is permitted")
    with client.stream("GET", url, follow_redirects=False) as reply:
        body = bytearray()
        if 200 <= reply.status_code < 300:
            for chunk in reply.iter_bytes(chunk_size=65536):
                body.extend(chunk[:max_bytes + 1 - len(body)])
                if len(body) > max_bytes:
                    break
        return Response(reply.status_code, reply.headers.get("content-type", ""),
                        bytes(body), reply.headers.get("retry-after"))
