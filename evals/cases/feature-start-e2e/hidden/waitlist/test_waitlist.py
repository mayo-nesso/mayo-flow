"""Hidden acceptance tests for the plot waitlist. Run by the eval with
cwd = the trial's repo. Each scenario runs in its own `python -c` subprocess
(never imported here): it migrates a temp sqlite file, freezes a distinct
time per step, drives only `allotment.api.routes.dispatch` and
`allotment.worker.runner.drain` (drained after every cancel), and prints one
JSON line.

The scenarios avoid every open decision: joins only on taken plots, members
hold no other booking that season, each member joins once."""
import json
import os
import subprocess
import sys
import unittest

# Shared setup of every scenario. Plots are inserted with plain SQL (there is
# no route for them); everything else goes through the API.
PRELUDE = r'''
import json, os, sqlite3, tempfile
from allotment import clock, db
from allotment.api.routes import dispatch
from allotment.worker import runner

SEASON = "spring-2027"
_tick = [0]


def tick():
    _tick[0] += 1
    clock.freeze("2027-01-01T08:%02d:00+00:00" % _tick[0])


tick()
conn = db.connect(os.path.join(tempfile.mkdtemp(), "allotment.db"))
OLD = os.environ.get("WAITLIST_OLD_MIGRATIONS")
if OLD:
    # a database from before the feature: the original 0001-0004 applied and
    # recorded by name, as the fixture's db.migrate records them
    conn.execute("CREATE TABLE schema_migrations ("
                 "name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    for name in sorted(os.listdir(OLD)):
        with open(os.path.join(OLD, name), encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute("INSERT INTO schema_migrations (name, applied_at) "
                     "VALUES (?, ?)", (name, clock.now()))
    conn.commit()
db.migrate(conn)
outbox = []
conn.execute("INSERT INTO plots (code, size_m2, has_water) "
             "VALUES ('A1', 100, 1)")
PLOT = conn.execute("SELECT id FROM plots WHERE code = 'A1'").fetchone()[0]
conn.commit()


def member(name, email=None, concession=False):
    tick()
    status, body = dispatch(conn, "POST", "/members", {
        "name": name, "email": email, "concession": concession})
    assert status == 201, (status, body)
    return body["id"]


def book(member_id):
    tick()
    status, body = dispatch(conn, "POST", "/bookings", {
        "plot_id": PLOT, "member_id": member_id, "season": SEASON})
    assert status == 201, (status, body)
    return body["id"]


def join(member_id):
    """(status, entry id or None)."""
    tick()
    status, body = dispatch(conn, "POST", "/waitlist", {
        "plot_id": PLOT, "member_id": member_id, "season": SEASON})
    return status, (body or {}).get("id")


def leave(entry_id):
    tick()
    return dispatch(conn, "DELETE", "/waitlist/%s" % entry_id)[0]


def cancel(booking_id):
    tick()
    status = dispatch(conn, "DELETE", "/bookings/%s" % booking_id)[0]
    tick()
    runner.drain(conn, outbox)
    return status


def active(member_id):
    """The member's active bookings for PLOT and SEASON."""
    status, body = dispatch(conn, "GET", "/members/%s/bookings" % member_id)
    return [b for b in body.get("bookings", [])
            if b["plot_id"] == PLOT and b["season"] == SEASON
            and b["status"] == "active"]


def out(**result):
    print(json.dumps(result))
'''


OLD_MIGRATIONS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "migrations_0001_0004")


def scenario(body, old_db=False):
    """Run PRELUDE + body in the repo (cwd) and return its last JSON line.
    old_db: start from a database already migrated with the original
    0001-0004 (copies kept next to this file)."""
    env = dict(os.environ)
    env.pop("WAITLIST_OLD_MIGRATIONS", None)
    if old_db:
        env["WAITLIST_OLD_MIGRATIONS"] = OLD_MIGRATIONS
    r = subprocess.run([sys.executable, "-c", PRELUDE + body],
                       cwd=os.getcwd(), capture_output=True, text=True,
                       timeout=60, env=env)
    if r.returncode != 0 or not r.stdout.strip():
        raise AssertionError(f"scenario crashed:\n{r.stderr}")
    return json.loads(r.stdout.strip().splitlines()[-1])


class WaitlistTest(unittest.TestCase):
    def test_join_and_promote(self):
        res = scenario(r'''
a, b = member("Ana", "ana@example.org"), member("Bo", "bo@example.org")
booking = book(a)
status, entry = join(b)
out(join=status, entry=entry, cancel=cancel(booking), b=len(active(b)))
''')
        self.assertEqual(res["join"], 201, res)
        self.assertIsInstance(res["entry"], int, res)
        self.assertEqual(res["cancel"], 200, res)
        self.assertEqual(res["b"], 1, res)

    def test_first_in_line_is_promoted(self):
        res = scenario(r'''
a = member("Ana", "ana@example.org")
b, c = member("Bo", "bo@example.org"), member("Cy", "cy@example.org")
booking = book(a)
joins = [join(b)[0], join(c)[0]]
cancel(booking)
out(joins=joins, b=len(active(b)), c=len(active(c)))
''')
        self.assertEqual(res["joins"], [201, 201], res)
        self.assertEqual((res["b"], res["c"]), (1, 0), res)

    def test_promoted_member_is_notified(self):
        res = scenario(r'''
a = member("Ana", "ana@example.org")
b, c = member("Bo", "bo@example.org"), member("Cy", "cy@example.org")
booking = book(a)
joins = [join(b)[0], join(c)[0]]
cancel(booking)
out(joins=joins, to=[m.get("to") for m in outbox
                     if m.get("template") == "waitlist_promoted"])
''')
        self.assertEqual(res["joins"], [201, 201], res)
        self.assertEqual(res["to"], ["bo@example.org"], res)

    def test_left_entry_is_not_promoted(self):
        res = scenario(r'''
a = member("Ana", "ana@example.org")
b, c = member("Bo", "bo@example.org"), member("Cy", "cy@example.org")
booking = book(a)
status, entry = join(b)
left = leave(entry)
joined = join(c)[0]
cancel(booking)
out(joins=[status, joined], left=left, b=len(active(b)), c=len(active(c)))
''')
        self.assertEqual(res["joins"], [201, 201], res)
        self.assertTrue(200 <= res["left"] < 300, res)
        self.assertEqual((res["b"], res["c"]), (0, 1), res)

    def test_promoted_member_pays_their_own_price(self):
        # T1: the price is whatever B's own direct booking of the plot costs,
        # measured in a fresh scenario (B has a concession, A does not)
        promoted = scenario(r'''
a = member("Ana", "ana@example.org")
b = member("Bo", "bo@example.org", concession=True)
booking = book(a)
joined = join(b)[0]
cancel(booking)
out(joined=joined, prices=[x["price_cents"] for x in active(b)])
''')
        direct = scenario(r'''
b = member("Bo", "bo@example.org", concession=True)
book(b)
out(prices=[x["price_cents"] for x in active(b)])
''')
        self.assertEqual(promoted["joined"], 201, promoted)
        self.assertEqual(len(direct["prices"]), 1, direct)
        self.assertEqual(promoted["prices"], direct["prices"],
                         (promoted, direct))

    def test_works_on_a_database_migrated_before_the_feature(self):
        # T2: migrations are recorded by name and never rerun, so the feature
        # must reach an existing database through a new migration
        res = scenario(r'''
a, b = member("Ana", "ana@example.org"), member("Bo", "bo@example.org")
booking = book(a)
status, entry = join(b)
out(join=status, cancel=cancel(booking), b=len(active(b)))
''', old_db=True)
        self.assertEqual(res["join"], 201, res)
        self.assertEqual(res["cancel"], 200, res)
        self.assertEqual(res["b"], 1, res)

    def test_promoted_member_is_not_promoted_again(self):
        # T3: B got the plot from the line; when B's new booking is cancelled
        # the plot goes to C, and B is not booked again
        res = scenario(r'''
a = member("Ana", "ana@example.org")
b, c = member("Bo", "bo@example.org"), member("Cy", "cy@example.org")
booking = book(a)
joins = [join(b)[0], join(c)[0]]
cancel(booking)
first = active(b)
second = cancel(first[0]["id"]) if len(first) == 1 else None
out(joins=joins, first=len(first), second=second,
    b=len(active(b)), c=len(active(c)))
''')
        self.assertEqual(res["joins"], [201, 201], res)
        self.assertEqual((res["first"], res["second"]), (1, 200), res)
        self.assertEqual((res["b"], res["c"]), (0, 1), res)

    def test_member_without_email_does_not_break_promotion(self):
        # T4, loose on purpose: B (no email) may be booked without a message
        # or skipped for C; either way one active booking, no message to
        # nobody, no dead job
        res = scenario(r'''
a = member("Ana", "ana@example.org")
b, c = member("Bo"), member("Cy", "cy@example.org")
booking = book(a)
joins = [join(b)[0], join(c)[0]]
cancel(booking)
dead = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'dead'")
out(joins=joins, active=len(active(a)) + len(active(b)) + len(active(c)),
    to=[m.get("to") for m in outbox], dead=dead.fetchone()[0])
''')
        self.assertEqual(res["joins"], [201, 201], res)
        self.assertEqual(res["active"], 1, res)
        self.assertNotIn(None, res["to"], res)
        self.assertEqual(res["dead"], 0, res)


if __name__ == "__main__":
    unittest.main()
