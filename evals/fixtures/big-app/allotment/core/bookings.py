"""Bookings: one member holds one plot for one season."""
from allotment import clock
from allotment.core import members, plots, pricing
from allotment.core.errors import Invalid, NotFound, PlotTaken
from allotment.core.models import Booking

SEASONS = ("spring", "summer", "autumn")


def _check_season(season):
    name, _, year = season.partition("-")
    if name not in SEASONS or not (year.isdigit() and len(year) == 4):
        raise Invalid(f"bad season {season!r} (want e.g. spring-2027)")


def active(conn, plot_id, season):
    row = conn.execute(
        "SELECT * FROM bookings WHERE plot_id = ? AND season = ? "
        "AND status = 'active'", (plot_id, season)).fetchone()
    return None if row is None else Booking.from_row(row)


def get(conn, booking_id):
    row = conn.execute("SELECT * FROM bookings WHERE id = ?",
                       (booking_id,)).fetchone()
    if row is None:
        raise NotFound(f"booking {booking_id}")
    return Booking.from_row(row)


def book(conn, plot_id, member_id, season):
    _check_season(season)
    plot = plots.get(conn, plot_id)
    member = members.get(conn, member_id)
    if active(conn, plot_id, season) is not None:
        raise PlotTaken(f"plot {plot.code} is taken for {season}")
    cur = conn.execute(
        "INSERT INTO bookings (plot_id, member_id, season, status, "
        "price_cents, created_at) VALUES (?, ?, ?, 'active', ?, ?)",
        (plot_id, member_id, season, pricing.price_cents(plot, member),
         clock.now()))
    return get(conn, cur.lastrowid)


def cancel(conn, booking_id):
    """Cancel an active booking. Runs inside the caller's transaction."""
    booking = get(conn, booking_id)
    if booking.status != "active":
        raise Invalid(f"booking {booking_id} is {booking.status}")
    conn.execute("UPDATE bookings SET status = 'cancelled', cancelled_at = ? "
                 "WHERE id = ?", (clock.now(), booking_id))
    return get(conn, booking_id)


def for_member(conn, member_id):
    rows = conn.execute("SELECT * FROM bookings WHERE member_id = ? "
                        "ORDER BY created_at, id", (member_id,))
    return [Booking.from_row(r) for r in rows]
