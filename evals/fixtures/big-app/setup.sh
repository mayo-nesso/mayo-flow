# Builds the halfway state of the plot waitlist feature on its own branch:
# the spec (commit 1), then steps 1-2 of its plan (commit 2). Run by
# evals/run.py prepare_fixture in the copy, after the initial commit.
set -e
git checkout -q -b feature/plot-waitlist

mkdir -p docs/10_features/2026_11_10_plot_waitlist
cat > docs/10_features/2026_11_10_plot_waitlist/spec.md <<'EOF'
# Plot waitlist

**Status:** in progress.

## Goal

When a plot is taken for a season, a member can join its waitlist. When the
booking is cancelled, the first member in line gets the plot automatically
and is told so.

## Decisions

- One waitlist per (plot, season); a member is on it at most once.
- Order is first come, first served (`joined_at`, then id).
- The promoted member is booked at the normal price (core/pricing.py).
- Promotion notifies the member through the outbox, template
  `waitlist_promoted`.

## Plan

1. Migration `0005_waitlist.sql`: table `waitlist_entries`.
2. `core/waitlist.py`: join, leave, next_in_line, position; unit tests.
3. Promote the next member in line when a booking is cancelled: book the
   plot for them and put a `waitlist_promoted` message in the outbox.
   Open: run it inline in `bookings.cancel()` or as a worker job.
4. Record when an entry was promoted (`promoted_at`) so an entry is never
   promoted twice, and skip promoted entries in `next_in_line`.
5. API: `POST /waitlist` (join) and `DELETE /waitlist/<id>` (leave).

## Tests

- join twice is rejected; leave removes; order is by joined_at.
- cancelling a booking with a waitlist books the first member in line and
  queues one message; with an empty waitlist nothing happens.
- a promoted entry is not promoted again.
- API status codes for join/leave.
EOF
git add -A
git commit -q -m "docs(waitlist): add plot waitlist spec"

cat > migrations/0005_waitlist.sql <<'EOF'
CREATE TABLE waitlist_entries (
    id INTEGER PRIMARY KEY,
    plot_id INTEGER NOT NULL REFERENCES plots (id),
    member_id INTEGER NOT NULL REFERENCES members (id),
    season TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    UNIQUE (plot_id, member_id, season)
);

CREATE INDEX waitlist_line ON waitlist_entries (plot_id, season, joined_at, id);
EOF

cat > allotment/core/waitlist.py <<'EOF'
"""Waitlist for plots that are taken for a season."""
import sqlite3

from allotment import clock
from allotment.core import members, plots
from allotment.core.errors import Invalid, NotFound


def join(conn, plot_id, member_id, season):
    plots.get(conn, plot_id)
    members.get(conn, member_id)
    try:
        cur = conn.execute(
            "INSERT INTO waitlist_entries (plot_id, member_id, season, "
            "joined_at) VALUES (?, ?, ?, ?)",
            (plot_id, member_id, season, clock.now()))
    except sqlite3.IntegrityError:
        raise Invalid("already on the waitlist") from None
    return cur.lastrowid


def leave(conn, entry_id):
    cur = conn.execute("DELETE FROM waitlist_entries WHERE id = ?",
                       (entry_id,))
    if cur.rowcount == 0:
        raise NotFound(f"waitlist entry {entry_id}")


def next_in_line(conn, plot_id, season):
    """The first entry for (plot, season) as a row, or None."""
    return conn.execute(
        "SELECT * FROM waitlist_entries WHERE plot_id = ? AND season = ? "
        "ORDER BY joined_at, id LIMIT 1", (plot_id, season)).fetchone()


def position(conn, entry_id):
    """1-based place in line."""
    row = conn.execute("SELECT * FROM waitlist_entries WHERE id = ?",
                       (entry_id,)).fetchone()
    if row is None:
        raise NotFound(f"waitlist entry {entry_id}")
    ahead = conn.execute(
        "SELECT COUNT(*) FROM waitlist_entries WHERE plot_id = ? AND "
        "season = ? AND (joined_at < ? OR (joined_at = ? AND id < ?))",
        (row["plot_id"], row["season"], row["joined_at"], row["joined_at"],
         row["id"])).fetchone()[0]
    return ahead + 1
EOF

cat > tests/test_waitlist.py <<'EOF'
from allotment import clock
from allotment.core import waitlist
from allotment.core.errors import Invalid, NotFound
from tests.helpers import DbCase


class WaitlistTest(DbCase):
    def setUp(self):
        super().setUp()
        self.p = self.plot()
        self.a = self.member("Ines")
        self.b = self.member("Bo", email="bo@example.org")

    def test_join_once(self):
        waitlist.join(self.conn, self.p.id, self.a.id, "spring-2027")
        with self.assertRaises(Invalid):
            waitlist.join(self.conn, self.p.id, self.a.id, "spring-2027")

    def test_order_is_first_come(self):
        first = waitlist.join(self.conn, self.p.id, self.a.id, "spring-2027")
        clock.freeze("2027-02-02T09:00:00+00:00")
        second = waitlist.join(self.conn, self.p.id, self.b.id, "spring-2027")
        self.assertEqual(waitlist.next_in_line(
            self.conn, self.p.id, "spring-2027")["id"], first)
        self.assertEqual(waitlist.position(self.conn, second), 2)

    def test_leave(self):
        e = waitlist.join(self.conn, self.p.id, self.a.id, "spring-2027")
        waitlist.leave(self.conn, e)
        self.assertIsNone(waitlist.next_in_line(
            self.conn, self.p.id, "spring-2027"))
        with self.assertRaises(NotFound):
            waitlist.leave(self.conn, e)

    def test_lines_are_per_season(self):
        waitlist.join(self.conn, self.p.id, self.a.id, "spring-2027")
        self.assertIsNone(waitlist.next_in_line(
            self.conn, self.p.id, "summer-2027"))
EOF
git add -A
git commit -q -m "feat(waitlist): add waitlist table and core join/leave/next_in_line"
