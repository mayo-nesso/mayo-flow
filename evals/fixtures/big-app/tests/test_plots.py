from allotment.core import bookings, plots
from allotment.core.errors import Invalid, NotFound
from tests.helpers import DbCase


class PlotsTest(DbCase):
    def test_create_and_get(self):
        p = self.plot("B2", 30, has_water=True)
        self.assertEqual(plots.get(self.conn, p.id), p)
        self.assertEqual(plots.by_code(self.conn, "B2"), p)

    def test_size_must_be_positive(self):
        with self.assertRaises(Invalid):
            self.plot("Z9", 0)

    def test_missing(self):
        with self.assertRaises(NotFound):
            plots.get(self.conn, 99)

    def test_list_free_skips_booked_plots(self):
        a, b = self.plot("A1"), self.plot("A2")
        m = self.member()
        bookings.book(self.conn, a.id, m.id, "spring-2027")
        self.assertEqual(plots.list_free(self.conn, "spring-2027"), [b])
        self.assertEqual(plots.list_free(self.conn, "summer-2027"), [a, b])
