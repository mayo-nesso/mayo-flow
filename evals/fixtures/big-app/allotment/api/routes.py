"""(method, path pattern) -> handler. Path params are merged into the request."""
import re

from allotment.api import handlers

ROUTES = [
    ("GET", r"^/plots/free$", handlers.list_free_plots),
    ("POST", r"^/members$", handlers.add_member),
    ("GET", r"^/members/(?P<member_id>\d+)/bookings$",
     handlers.member_bookings),
    ("POST", r"^/bookings$", handlers.book_plot),
    ("DELETE", r"^/bookings/(?P<booking_id>\d+)$", handlers.cancel_booking),
]


def dispatch(conn, method, path, req=None):
    for m, pattern, handler in ROUTES:
        match = re.match(pattern, path)
        if m == method and match:
            params = {k: int(v) for k, v in match.groupdict().items()}
            return handler(conn, {**(req or {}), **params})
    return 404, {"error": f"no route for {method} {path}"}
