from allotment.core import bookings
from allotment.core.errors import Invalid, PlotTaken
from tests.helpers import NOW, DbCase


class BookingsTest(DbCase):
    def setUp(self):
        super().setUp()
        self.p = self.plot("A1", 100)
        self.m = self.member()

    def test_book(self):
        b = bookings.book(self.conn, self.p.id, self.m.id, "spring-2027")
        self.assertEqual((b.status, b.price_cents, b.created_at),
                         ("active", 4500, NOW))

    def test_bad_season(self):
        with self.assertRaises(Invalid):
            bookings.book(self.conn, self.p.id, self.m.id, "winter-2027")

    def test_plot_taken(self):
        bookings.book(self.conn, self.p.id, self.m.id, "spring-2027")
        other = self.member("Bo")
        with self.assertRaises(PlotTaken):
            bookings.book(self.conn, self.p.id, other.id, "spring-2027")

    def test_cancel_frees_the_plot(self):
        b = bookings.book(self.conn, self.p.id, self.m.id, "spring-2027")
        c = bookings.cancel(self.conn, b.id)
        self.assertEqual((c.status, c.cancelled_at), ("cancelled", NOW))
        self.assertIsNone(bookings.active(self.conn, self.p.id, "spring-2027"))
        with self.assertRaises(Invalid):
            bookings.cancel(self.conn, b.id)

    def test_cancel_does_not_commit(self):
        b = bookings.book(self.conn, self.p.id, self.m.id, "spring-2027")
        self.conn.commit()
        bookings.cancel(self.conn, b.id)
        self.conn.rollback()
        self.assertEqual(bookings.get(self.conn, b.id).status, "active")
