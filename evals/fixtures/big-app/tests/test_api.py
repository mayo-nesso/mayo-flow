from allotment.api.routes import dispatch
from tests.helpers import DbCase


class ApiTest(DbCase):
    def setUp(self):
        super().setUp()
        self.p = self.plot("A1", 100)
        self.m = self.member()

    def test_book_and_cancel(self):
        status, body = dispatch(self.conn, "POST", "/bookings", {
            "plot_id": self.p.id, "member_id": self.m.id,
            "season": "spring-2027"})
        self.assertEqual(status, 201)
        status, _ = dispatch(self.conn, "POST", "/bookings", {
            "plot_id": self.p.id, "member_id": self.m.id,
            "season": "spring-2027"})
        self.assertEqual(status, 409)
        status, body = dispatch(self.conn, "DELETE",
                                f"/bookings/{body['id']}")
        self.assertEqual((status, body["status"]), (200, "cancelled"))

    def test_free_plots_and_member_bookings(self):
        status, body = dispatch(self.conn, "GET", "/plots/free",
                                {"season": "spring-2027"})
        self.assertEqual([p["code"] for p in body["plots"]], ["A1"])
        status, body = dispatch(self.conn, "GET",
                                f"/members/{self.m.id}/bookings")
        self.assertEqual((status, body["bookings"]), (200, []))

    def test_errors(self):
        self.assertEqual(dispatch(self.conn, "DELETE", "/bookings/99")[0], 404)
        self.assertEqual(dispatch(self.conn, "GET", "/nope")[0], 404)
        self.assertEqual(dispatch(self.conn, "POST", "/members",
                                  {"name": " "})[0], 400)
