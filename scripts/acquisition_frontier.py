"""Persistent, bounded acquisition frontier; explicit transport, no dispatcher.

One SQLite writer coordinates a batch. Worker threads never access SQLite.
One URL per origin per wave; reuse core robots and response guards. This is
a local prototype for synthetic or separately authorized work, not a service.
"""
from __future__ import annotations

import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlsplit

from scripts.acquisition_core import canonical_url, crawl

STOP = {"rate_limited", "access_denied", "robots_unavailable", "origin_stopped",
        "budget_exhausted"}


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Invalid frontier bound")
    return value


class Frontier:
    def __init__(self, path, allowed_hosts, seeds=(), *, max_depth=2,
                 max_urls=20000, allowed_query_keys=()):
        self.hosts = frozenset(h.lower() for h in allowed_hosts)
        if not 1 <= len(self.hosts) <= 20:
            raise ValueError("Approve one to twenty exact hosts")
        for host in self.hosts:
            canonical_url("https://" + host + "/", self.hosts)
        self.keys = frozenset(allowed_query_keys)
        self.max_depth = _integer(max_depth, 0, 20)
        self.max_urls = _integer(max_urls, 1, 100000)
        self.config = json.dumps({"version": 1, "hosts": sorted(self.hosts),
                                  "keys": sorted(self.keys), "depth": self.max_depth,
                                  "urls": self.max_urls}, sort_keys=True)
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        try:
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS queue(
                    id INTEGER PRIMARY KEY, url TEXT UNIQUE NOT NULL,
                    host TEXT NOT NULL, depth INTEGER NOT NULL, record TEXT);
                CREATE INDEX IF NOT EXISTS pending_idx ON queue(depth,id) WHERE record IS NULL;
                CREATE TABLE IF NOT EXISTS stopped(host TEXT PRIMARY KEY, reason TEXT NOT NULL);
            """)
            self.db.execute("BEGIN IMMEDIATE")
            stored = self.db.execute("SELECT value FROM meta WHERE key='config'").fetchone()
            if stored is None:
                self.db.execute("INSERT INTO meta VALUES('config',?)", (self.config,))
            elif stored[0] != self.config:
                raise ValueError("Frontier scope or limits differ from checkpoint")
            self.db.execute("INSERT OR IGNORE INTO meta VALUES('capacity','0')")
            self.db.execute("INSERT OR IGNORE INTO meta VALUES('count','0')")
            for seed in seeds:
                self._enqueue(seed, 0, strict=True)
            self.db.commit()
        except BaseException:
            self.db.rollback()
            self.db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.close()

    def _enqueue(self, raw, depth, *, strict=False):
        try:
            url = canonical_url(raw, self.hosts, self.keys)
        except ValueError:
            if strict:
                raise
            return
        if self.db.execute("SELECT 1 FROM queue WHERE url=?", (url,)).fetchone():
            return
        count = int(self.db.execute("SELECT value FROM meta WHERE key='count'").fetchone()[0])
        if count >= self.max_urls:
            self.db.execute("UPDATE meta SET value='1' WHERE key='capacity'")
            return
        self.db.execute("INSERT INTO queue(url,host,depth) VALUES(?,?,?)",
                        (url, urlsplit(url).hostname, depth))
        self.db.execute("UPDATE meta SET value=? WHERE key='count'", (str(count + 1),))

    def _extract(self, row, fetch, sleep):
        _, url, host, depth = row
        # The existing core checks robots before the page and delays between
        # requests. An extra delay before robots also separates successive waves.
        sleep(1.0)
        result = crawl([url], {host}, fetch, max_pages=1, max_depth=0,
                       max_bytes=256000, max_total_bytes=768001,
                       allowed_query_keys=self.keys, sleep=sleep)
        record = result["records"][0] if result["records"] else {
            "url": url, "status": "budget_exhausted"}
        record["depth"] = depth
        record["collected_at"] = datetime.now(timezone.utc).isoformat()
        record["adapter"] = "acquisition_core/0.1"
        return record

    def _save(self, row, record):
        identifier, _, host, depth = row
        self.db.execute("UPDATE queue SET record=? WHERE id=?",
                        (json.dumps(record, ensure_ascii=True, allow_nan=False), identifier))
        if record["status"] in STOP:
            self.db.execute("INSERT OR IGNORE INTO stopped VALUES(?,?)",
                            (host, record["status"]))
        if depth < self.max_depth and record["status"] == "ok":
            for link in record["extraction"]["links"]:
                self._enqueue(link, depth + 1)

    def run_batch(self, fetch, *, batch_size=100, workers=4, sleep=time.sleep):
        """Process up to batch_size pending rows, with one in-flight URL per host.

        A write transaction serializes coordinators sharing the same database.
        Completed waves commit together; a failed wave may be replayed (at least
        once, never exactly once at the network boundary). Stops from successful
        siblings are committed even if another worker raises.
        """
        _integer(batch_size, 1, 1000)
        _integer(workers, 1, 8)
        if not callable(fetch) or not callable(sleep):
            raise TypeError("Explicit callable transport and delay required")
        processed = 0
        with ThreadPoolExecutor(max_workers=workers) as executor:
            while processed < batch_size:
                failure = None
                self.db.execute("BEGIN IMMEDIATE")
                try:
                    # Process only the shallowest pending depth at a time.
                    rows = self.db.execute("""
                        SELECT id,url,host,depth FROM queue
                        WHERE record IS NULL AND depth=(SELECT MIN(depth) FROM queue WHERE record IS NULL)
                        ORDER BY id
                    """)
                    wave, hosts = [], set()
                    for row in rows:
                        if row[2] in hosts:
                            continue
                        hosts.add(row[2])
                        wave.append(row)
                        if len(wave) >= min(workers, batch_size - processed):
                            break
                    rows.close()
                    if not wave:
                        self.db.commit()
                        break
                    stopped = {r[0] for r in self.db.execute("SELECT host FROM stopped")}
                    futures = []
                    for row in wave:
                        if row[2] in stopped:
                            self._save(row, {"url": row[1], "depth": row[3],
                                             "status": "origin_stopped"})
                            processed += 1
                        else:
                            futures.append((row, executor.submit(self._extract, row, fetch, sleep)))
                    for row, future in futures:
                        try:
                            record = future.result()
                        except Exception as exc:
                            if failure is None:
                                failure = exc
                            continue
                        self._save(row, record)
                        processed += 1
                    self.db.commit()
                except BaseException:
                    self.db.rollback()
                    raise
                if failure is not None:
                    raise failure
        return {"processed": processed, **self.summary()}

    def records(self):
        """Materialize stored records; for large jobs prefer iter_records."""
        return list(self.iter_records())

    def iter_records(self):
        for (record,) in self.db.execute(
                "SELECT record FROM queue WHERE record IS NOT NULL ORDER BY depth,id"):
            yield json.loads(record)

    def summary(self):
        counts = {"done": 0, "blocked": 0, "failed": 0, "pending": 0}
        for record, n in self.db.execute("""
            SELECT CASE WHEN record IS NULL THEN 'pending'
                ELSE json_extract(record,'$.status') END AS status, COUNT(*)
            FROM queue GROUP BY status
        """):
            bucket = ("done" if record == "ok" else "pending" if record == "pending"
                      else "blocked" if record in STOP or record == "denied" else "failed")
            counts[bucket] += n
        counts["discovered"] = sum(counts.values())
        counts["stopped_hosts"] = self.db.execute("SELECT COUNT(*) FROM stopped").fetchone()[0]
        counts["capacity_reached"] = self.db.execute(
            "SELECT value FROM meta WHERE key='capacity'").fetchone()[0] == "1"
        counts["complete"] = counts["pending"] == 0 and not counts["capacity_reached"]
        return counts
