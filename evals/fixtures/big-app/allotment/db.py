"""SQLite connection and the migration runner."""
import sqlite3
from pathlib import Path

from allotment import clock

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def connect(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def applied(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                 "name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    return {r["name"] for r in conn.execute(
        "SELECT name FROM schema_migrations")}


def pending(conn, directory=MIGRATIONS):
    done = applied(conn)
    return [p for p in sorted(Path(directory).glob("*.sql"))
            if p.name not in done]


def migrate(conn, directory=MIGRATIONS):
    """Apply the pending migrations in name order; return their names.

    A migration is recorded by file name once applied and never run again.
    """
    names = []
    for path in pending(conn, directory):
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (name, applied_at) "
                     "VALUES (?, ?)", (path.name, clock.now()))
        names.append(path.name)
    conn.commit()
    return names
