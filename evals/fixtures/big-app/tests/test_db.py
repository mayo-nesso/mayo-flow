import tempfile
import unittest
from pathlib import Path

from allotment import db


class MigrateTest(unittest.TestCase):
    def test_applies_every_file_once_in_order(self):
        conn = db.connect()
        names = db.migrate(conn)
        self.assertEqual(names, sorted(names))
        self.assertTrue(names[0].startswith("0001_"))
        self.assertEqual(db.migrate(conn), [])

    def test_only_new_files_run(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "0001_a.sql").write_text("CREATE TABLE a (x INTEGER);")
            conn = db.connect()
            self.assertEqual(db.migrate(conn, d), ["0001_a.sql"])
            Path(d, "0002_b.sql").write_text("CREATE TABLE b (x INTEGER);")
            self.assertEqual(db.migrate(conn, d), ["0002_b.sql"])

    def test_foreign_keys_are_on(self):
        conn = db.connect()
        self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
