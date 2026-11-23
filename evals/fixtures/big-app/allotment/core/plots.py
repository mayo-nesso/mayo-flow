"""Plots: the fixed pieces of land members book."""
from allotment.core.errors import Invalid, NotFound
from allotment.core.models import Plot


def create(conn, code, size_m2, has_water=False):
    if size_m2 <= 0:
        raise Invalid("size_m2 must be positive")
    cur = conn.execute(
        "INSERT INTO plots (code, size_m2, has_water) VALUES (?, ?, ?)",
        (code, size_m2, int(has_water)))
    return get(conn, cur.lastrowid)


def get(conn, plot_id):
    row = conn.execute("SELECT * FROM plots WHERE id = ?",
                       (plot_id,)).fetchone()
    if row is None:
        raise NotFound(f"plot {plot_id}")
    return Plot.from_row(row)


def by_code(conn, code):
    row = conn.execute("SELECT * FROM plots WHERE code = ?",
                       (code,)).fetchone()
    if row is None:
        raise NotFound(f"plot {code}")
    return Plot.from_row(row)


def list_free(conn, season):
    """Plots with no active booking for `season`, by code."""
    rows = conn.execute(
        "SELECT p.* FROM plots p WHERE NOT EXISTS ("
        " SELECT 1 FROM bookings b WHERE b.plot_id = p.id"
        " AND b.season = ? AND b.status = 'active') ORDER BY p.code",
        (season,))
    return [Plot.from_row(r) for r in rows]
