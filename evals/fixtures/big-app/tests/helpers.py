"""Shared test setup: a migrated in-memory database and a frozen clock."""
import unittest

from allotment import clock, db
from allotment.core import members, plots

NOW = "2027-02-01T09:00:00+00:00"


def fresh_db():
    conn = db.connect()
    db.migrate(conn)
    return conn


class DbCase(unittest.TestCase):
    def setUp(self):
        clock.freeze(NOW)
        self.addCleanup(clock.freeze, None)
        self.conn = fresh_db()
        self.addCleanup(self.conn.close)

    def plot(self, code="A1", size_m2=50, has_water=False):
        return plots.create(self.conn, code, size_m2, has_water)

    def member(self, name="Ines", concession=False, email="ines@example.org"):
        return members.add(self.conn, name, concession, email)
