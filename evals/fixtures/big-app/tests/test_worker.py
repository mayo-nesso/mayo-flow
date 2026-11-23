from allotment.core import bookings
from allotment.worker import queue, runner
from tests.helpers import DbCase


class RunnerTest(DbCase):
    def test_season_start_reminders(self):
        p, m = self.plot(), self.member()
        bookings.book(self.conn, p.id, m.id, "spring-2027")
        self.member("NoMail", email=None)
        queue.enqueue(self.conn, "reminders.season_start",
                      {"season": "spring-2027"})
        outbox = []
        self.assertEqual(runner.drain(self.conn, outbox), 1)
        (msg,) = outbox
        self.assertEqual((msg["to"], msg["vars"]["plot"]),
                         ("ines@example.org", "A1"))
        self.assertEqual(queue.counts(self.conn), {"done": 1})

    def test_unknown_kind_is_retried_then_dead(self):
        queue.enqueue(self.conn, "nope", {})
        runner.drain(self.conn, [])
        self.assertEqual(queue.counts(self.conn), {"dead": 1})

    def test_idle(self):
        self.assertIsNone(runner.run_once(self.conn, []))
