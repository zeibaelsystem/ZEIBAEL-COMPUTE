"""Offline archive, feed, columnar, geographic and scientific fixtures."""
import importlib.util
import io
import json
import unittest

import polars as pl
import xarray as xr
from warcio.warcwriter import WARCWriter
from warcio.statusandheaders import StatusAndHeaders


class DataFormats(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("scripts.acquisition_data_formats"),
                             "data format adapters not implemented")
        from scripts import acquisition_data_formats
        self.a = acquisition_data_formats

    def test_warc(self):
        out = io.BytesIO()
        writer = WARCWriter(out, gzip=True)
        headers = StatusAndHeaders("200 OK", [("Content-Type", "text/html")], protocol="HTTP/1.1")
        rec = writer.create_warc_record("https://example.org/archive", "response",
                     payload=io.BytesIO(b"<h1>archived text</h1>"), http_headers=headers)
        writer.write_record(rec)
        r = self.a.read_warc(out.getvalue())
        self.assertEqual(r[0]["url"], "https://example.org/archive")
        self.assertIn("archived text", r[0]["extraction"]["text"])
        self.assertEqual(len(r[0]["sha256"]), 64)

    def test_rss(self):
        feed = b'<rss version="2.0"><channel><title>Example</title><link>https://example.org/</link><description>Fixture</description><item><guid>urn:1</guid><title>News</title><link>https://example.org/a</link></item></channel></rss>'
        r = self.a.read_feed(feed)
        self.assertEqual(r[0]["title"], "News")
        self.assertEqual(r[0]["id"], "urn:1")

    def test_atom(self):
        feed = b'<feed xmlns="http://www.w3.org/2005/Atom"><title>Example</title><id>urn:feed</id><entry><id>urn:2</id><title>Update</title><link href="https://example.org/b"/></entry></feed>'
        self.assertEqual(self.a.read_feed(feed)[0]["id"], "urn:2")

    def test_parquet_crosscheck(self):
        out = io.BytesIO()
        pl.DataFrame({"url":["https://example.org/a","https://example.org/b"],
                      "value":[3,5]}).write_parquet(out)
        r = self.a.read_parquet(out.getvalue())
        self.assertEqual(r["row_count"], 2)
        self.assertEqual(r["duckdb_row_count"], 2)
        self.assertEqual(r["rows"][1]["value"], 5)

    def test_geojson(self):
        raw = json.dumps({"type":"FeatureCollection","features":[
            {"type":"Feature","properties":{"name":"site"},"geometry":{"type":"Point","coordinates":[101.4,0.5]}}
        ]}).encode()
        r = self.a.read_geojson(raw)
        self.assertEqual(r[0]["geometry_type"], "Point")
        self.assertEqual(r[0]["bounds"], [101.4,0.5,101.4,0.5])

    def test_netcdf(self):
        ds = xr.Dataset({"temperature": (("sample",), [21.0, 22.0])})
        raw = bytes(ds.to_netcdf(engine="scipy"))
        r = self.a.read_netcdf(raw)
        self.assertEqual(r["dimensions"], {"sample":2})
        self.assertEqual(r["variables"]["temperature"]["values"], [21.0,22.0])

    def test_reject_nonlocal_input_and_bad_data(self):
        with self.assertRaises(ValueError):
            self.a.read_feed("https://example.org/feed")
        with self.assertRaises(ValueError):
            self.a.read_feed(b'<!DOCTYPE rss [<!ENTITY x "unsafe">]><rss>&x;</rss>')
        with self.assertRaises(ValueError):
            self.a.read_parquet(b"not parquet")
        with self.assertRaises(ValueError):
            self.a.read_netcdf(b"not netcdf")


if __name__ == "__main__":
    unittest.main(verbosity=2)
