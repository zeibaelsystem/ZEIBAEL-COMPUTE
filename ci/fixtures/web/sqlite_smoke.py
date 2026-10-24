"""Verify temporary relational database semantics without cloud credentials."""
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

with TemporaryDirectory() as folder:
    with sqlite3.connect(Path(folder) / "smoke.db") as db:
        db.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, amount INTEGER NOT NULL)")
        db.execute("INSERT INTO orders (amount) VALUES (?)", (250,))
        db.commit()
        assert db.execute("SELECT sum(amount) FROM orders").fetchone()[0] == 250
        try:
            with db:
                db.execute("INSERT INTO orders (amount) VALUES (?)", (300,))
                raise RuntimeError("simulate rollback")
        except RuntimeError:
            pass
        assert db.execute("SELECT count(*) FROM orders").fetchone()[0] == 1
print("EPHEMERAL_SQLITE_SMOKE_OK")
