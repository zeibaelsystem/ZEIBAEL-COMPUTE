"""Bounded JSON pagination, immutable source scope and transactional content store.

Explicit transport only. Local trusted/authorized input; no new public URL
dispatcher. A stop is durable; a new reviewed job is required to resume it.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

from scripts.acquisition_core import canonical_url, crawl

MAX_PAGE_BYTES = 256000
MAX_CONTENT_BYTES = 16_000_000
MAX_PAGE_ITEMS = 1000
MAX_OBSERVATIONS = 100000


def _bounded(value, high):
    if type(value) is not int or not 1 <= value <= high:
        raise ValueError("Invalid ingestion bound")
    return value


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


class Ingest:
    def __init__(self, path, seed, *, max_pages=100, max_objects=10000,
                 query_keys=("page",)):
        self.host = urlsplit(seed).hostname
        self.keys = frozenset(query_keys)
        self.seed = canonical_url(seed, {self.host}, self.keys)
        self.max_pages = _bounded(max_pages, 10000)
        self.max_objects = _bounded(max_objects, 100000)
        config = _encode({"version": 1, "seed": self.seed,
                          "keys": sorted(self.keys), "pages": self.max_pages,
                          "objects": self.max_objects})
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        try:
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS state(
                    id INTEGER PRIMARY KEY CHECK(id=1), config TEXT NOT NULL,
                    status TEXT NOT NULL, next_url TEXT, bytes INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS pages(
                    url TEXT PRIMARY KEY, hash TEXT NOT NULL, collected_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS objects(
                    hash TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS observations(
                    page TEXT REFERENCES pages(url), ordinal INTEGER,
                    hash TEXT REFERENCES objects(hash), PRIMARY KEY(page,ordinal));
            """)
            self.db.execute("BEGIN IMMEDIATE")
            old = self.db.execute("SELECT config FROM state WHERE id=1").fetchone()
            if old is None:
                self.db.execute("INSERT INTO state VALUES(1,?,'pending',?,0)", (config,self.seed))
            elif old[0] != config:
                raise ValueError("Ingestion source or limits changed")
            self.db.commit()
        except BaseException:
            self.db.rollback()
            self.db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.db.close()

    def summary(self):
        status, next_url, size = self.db.execute(
            "SELECT status,next_url,bytes FROM state WHERE id=1").fetchone()
        return {"status":status,"next_url":next_url,"bytes":size,
                **{name:self.db.execute("SELECT count(*) FROM "+name).fetchone()[0]
                   for name in ("pages","objects","observations")}}

    def records(self):
        for url, ordinal, digest, body, stamp in self.db.execute("""
            SELECT o.page,o.ordinal,o.hash,b.body,p.collected_at
            FROM observations o JOIN objects b ON b.hash=o.hash
            JOIN pages p ON p.url=o.page ORDER BY p.rowid,o.ordinal
        """):
            yield {"page":url,"ordinal":ordinal,"sha256":digest,
                   "data":json.loads(body),"collected_at":stamp}

    def _stop(self, status):
        self.db.execute("UPDATE state SET status=? WHERE id=1",(status,))

    def _one(self, fetch, sleep):
        state = self.summary()
        if state["status"] != "pending":
            return
        if state["pages"] >= self.max_pages:
            self._stop("capacity")
            return
        url = state["next_url"]
        sleep(1.0)
        report = crawl([url], {self.host}, fetch, max_pages=1, max_depth=0,
                       max_bytes=MAX_PAGE_BYTES, max_total_bytes=768001,
                       allowed_query_keys=self.keys, sleep=sleep)
        if not report["records"]:
            self._stop("budget_exhausted")
            return
        record = report["records"][0]
        if record["status"] != "ok":
            self._stop(record["status"])
            return
        data = record["extraction"].get("data")
        if not isinstance(data,dict) or not isinstance(data.get("items"),list):
            self._stop("invalid_schema")
            return
        items=data["items"]
        if len(items)>MAX_PAGE_ITEMS or not all(isinstance(x,dict) for x in items):
            self._stop("invalid_schema")
            return
        next_url = data.get("next")
        if next_url is not None:
            try:
                if not isinstance(next_url,str) or not next_url:
                    raise ValueError("Invalid pagination")
                next_url=canonical_url(urljoin(url,next_url),{self.host},self.keys)
                if next_url==url or self.db.execute("SELECT 1 FROM pages WHERE url=?",(next_url,)).fetchone():
                    raise ValueError("Pagination cycle")
            except ValueError:
                self._stop("invalid_next")
                return
        pairs=[]
        new={}
        try:
            for item in items:
                body=_encode(item)
                digest=hashlib.sha256(body.encode("ascii")).hexdigest()
                pairs.append((digest,body))
                if digest not in new and not self.db.execute("SELECT 1 FROM objects WHERE hash=?",(digest,)).fetchone():
                    new[digest]=body
        except (ValueError,RecursionError):
            self._stop("invalid_schema")
            return
        size=state["bytes"]+sum(len(body) for body in new.values())
        if (state["objects"]+len(new)>self.max_objects or size>MAX_CONTENT_BYTES
            or state["observations"]+len(pairs)>MAX_OBSERVATIONS):
            self._stop("capacity")
            return
        self.db.execute("INSERT INTO pages VALUES(?,?,?)",
                        (url,record["sha256"],datetime.now(timezone.utc).isoformat()))
        self.db.executemany("INSERT INTO objects VALUES(?,?)",new.items())
        self.db.executemany("INSERT INTO observations VALUES(?,?,?)",
                            [(url,i,digest) for i,(digest,_) in enumerate(pairs)])
        self.db.execute("UPDATE state SET status=?,next_url=?,bytes=? WHERE id=1",
                        ("pending" if next_url else "complete",next_url,size))

    def run(self,fetch,*,batch=10,sleep=time.sleep):
        _bounded(batch,100)
        if not callable(fetch) or not callable(sleep):
            raise TypeError("Explicit transport and delay required")
        for _ in range(batch):
            self.db.execute("BEGIN IMMEDIATE")
            try:
                if self.summary()["status"]!="pending":
                    self.db.commit()
                    break
                self._one(fetch,sleep)
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise
        return self.summary()
