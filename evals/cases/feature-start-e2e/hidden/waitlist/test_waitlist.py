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


def scenario(body):
    """Run PRELUDE + body in the repo (cwd) and return its last JSON line."""
    r = subprocess.run([sys.executable, "-c", PRELUDE + body],
                       cwd=os.getcwd(), capture_output=True, text=True,
                       timeout=60)
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


if __name__ == "__main__":
    unittest.main()
