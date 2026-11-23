"""Handlers take (conn, request dict) and return (status, body dict).

Each handler is one transaction: commit on success, rollback on error.
"""
from allotment.core import bookings, members, plots
from allotment.core.errors import Invalid, NotFound, PlotTaken

STATUS = {NotFound: 404, PlotTaken: 409, Invalid: 400}


def _transaction(conn, work):
    try:
        status, body = work()
    except tuple(STATUS) as e:
        conn.rollback()
        return STATUS[type(e)], {"error": str(e)}
    conn.commit()
    return status, body


def _booking_body(b):
    return {"id": b.id, "plot_id": b.plot_id, "member_id": b.member_id,
            "season": b.season, "status": b.status,
            "price_cents": b.price_cents}


def list_free_plots(conn, req):
    return 200, {"plots": [{"id": p.id, "code": p.code, "size_m2": p.size_m2}
                           for p in plots.list_free(conn, req["season"])]}


def add_member(conn, req):
    return _transaction(conn, lambda: (201, {"id": members.add(
        conn, req["name"], req.get("concession", False),
        req.get("email")).id}))


def book_plot(conn, req):
    return _transaction(conn, lambda: (201, _booking_body(bookings.book(
        conn, req["plot_id"], req["member_id"], req["season"]))))


def cancel_booking(conn, req):
    return _transaction(conn, lambda: (200, _booking_body(
        bookings.cancel(conn, req["booking_id"]))))


def member_bookings(conn, req):
    return 200, {"bookings": [_booking_body(b) for b in
                              bookings.for_member(conn, req["member_id"])]}
