import unittest

from notesapi.export import export_text
from notesapi.notes import Note


class ExportTest(unittest.TestCase):
    def test_one_line_per_note(self):
        notes = [Note("a", "x"), Note("b", "y")]
        self.assertEqual(export_text(notes), "a: x\nb: y")
