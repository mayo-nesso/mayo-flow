# allotment

Booking service for a community allotment garden: members book plots per
season, pay by plot size, and get reminders before their season starts.

Stdlib only (Python 3.11+, sqlite3). No web framework: `allotment/api` maps
(method, path) pairs to handler functions that take and return dicts, and a
thin adapter (not in this repo) serves them.

## Run the tests

    python3 -m unittest discover -s tests

## Layout

See `docs/structure.md`.
