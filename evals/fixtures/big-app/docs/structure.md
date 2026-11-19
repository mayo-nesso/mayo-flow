# Structure

```
allotment/
  db.py           sqlite connection and the migration runner
  clock.py        the one place that reads the time (tests freeze it)
  core/           domain: plots, members, bookings, pricing (no I/O but the DB)
  worker/         background jobs: a sqlite-backed queue, the job registry,
                  the runner and the jobs themselves (reminders)
  api/            request handlers and the route table
migrations/       numbered SQL files, applied in name order by db.migrate()
tests/            unittest, one file per module; helpers.fresh_db() gives a
                  migrated in-memory database
docs/
  10_features/    feature specs (archived/ once shipped)
  20_fix-plans/   fix plans (archived/ once shipped)
```

## Conventions

- Core functions take a connection first and never commit: the caller owns
  the transaction (the API handler, or the worker runner per job).
- Anything slow or that may fail for reasons outside the request (sending
  messages, follow-up bookkeeping) is a worker job, enqueued with
  `worker.queue.enqueue(conn, kind, payload)` and registered in
  `worker/jobs.py`.
- Messages are not sent from here: jobs append them to an outbox list that
  the delivery adapter drains.
- Times are ISO-8601 UTC strings from `clock.now()`.
- Money is integer cents.
