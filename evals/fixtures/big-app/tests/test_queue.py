from allotment.worker import queue
from tests.helpers import DbCase


class QueueTest(DbCase):
    def test_claim_oldest_first(self):
        a = queue.enqueue(self.conn, "k", {"n": 1})
        queue.enqueue(self.conn, "k", {"n": 2})
        job = queue.claim(self.conn)
        self.assertEqual((job["id"], job["payload"], job["attempts"]),
                         (a, {"n": 1}, 1))

    def test_ack_and_fail(self):
        a = queue.enqueue(self.conn, "k", {})
        queue.claim(self.conn)
        queue.ack(self.conn, a)
        b = queue.enqueue(self.conn, "k", {})
        for _ in range(queue.MAX_ATTEMPTS):
            queue.claim(self.conn)
            queue.fail(self.conn, b, "boom")
        self.assertEqual(queue.counts(self.conn), {"done": 1, "dead": 1})

    def test_requeue_stale(self):
        queue.enqueue(self.conn, "k", {})
        queue.claim(self.conn)
        self.assertEqual(queue.requeue_stale(self.conn, "2099-01-01"), 1)
        self.assertEqual(queue.counts(self.conn), {"pending": 1})
