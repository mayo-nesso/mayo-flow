"""Run queued jobs, one transaction per job."""
from allotment.worker import queue
from allotment.worker.jobs import JOBS


def run_once(conn, outbox):
    """Run the oldest pending job; return its id, or None if idle."""
    job = queue.claim(conn)
    conn.commit()
    if job is None:
        return None
    handler = JOBS.get(job["kind"])
    try:
        if handler is None:
            raise LookupError(f"no handler for {job['kind']!r}")
        handler(conn, job["payload"], outbox)
    except Exception as e:  # noqa: BLE001  (recorded on the job)
        conn.rollback()
        queue.fail(conn, job["id"], e)
    else:
        queue.ack(conn, job["id"])
    conn.commit()
    return job["id"]


def drain(conn, outbox, limit=100):
    ran = 0
    while ran < limit and run_once(conn, outbox) is not None:
        ran += 1
    return ran
