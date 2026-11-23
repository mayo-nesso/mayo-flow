"""A sqlite-backed job queue.

claim() marks a job running and returns it; the runner calls ack() when the
handler succeeded and fail() otherwise, so a crash mid-job leaves it running
(visible, retryable with requeue_stale()) instead of losing it.
"""
import json

from allotment import clock

MAX_ATTEMPTS = 3


def enqueue(conn, kind, payload):
    cur = conn.execute(
        "INSERT INTO jobs (kind, payload, status, attempts, created_at) "
        "VALUES (?, ?, 'pending', 0, ?)",
        (kind, json.dumps(payload, sort_keys=True), clock.now()))
    return cur.lastrowid


def claim(conn):
    """The oldest pending job, now marked running, or None."""
    row = conn.execute("SELECT * FROM jobs WHERE status = 'pending' "
                       "ORDER BY id LIMIT 1").fetchone()
    if row is None:
        return None
    conn.execute("UPDATE jobs SET status = 'running', "
                 "attempts = attempts + 1, started_at = ? WHERE id = ?",
                 (clock.now(), row["id"]))
    return {"id": row["id"], "kind": row["kind"],
            "payload": json.loads(row["payload"]),
            "attempts": row["attempts"] + 1}


def ack(conn, job_id):
    conn.execute("UPDATE jobs SET status = 'done', finished_at = ? "
                 "WHERE id = ?", (clock.now(), job_id))


def fail(conn, job_id, error):
    row = conn.execute("SELECT attempts FROM jobs WHERE id = ?",
                       (job_id,)).fetchone()
    status = "dead" if row["attempts"] >= MAX_ATTEMPTS else "pending"
    conn.execute("UPDATE jobs SET status = ?, last_error = ? WHERE id = ?",
                 (status, str(error)[:500], job_id))


def requeue_stale(conn, started_before):
    cur = conn.execute("UPDATE jobs SET status = 'pending' WHERE "
                       "status = 'running' AND started_at < ?",
                       (started_before,))
    return cur.rowcount


def counts(conn):
    return {r["status"]: r["n"] for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status")}
