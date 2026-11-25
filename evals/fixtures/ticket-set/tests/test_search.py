import unittest

from notesapi.notes import Note
from notesapi.search import search_notes


class SearchTest(unittest.TestCase):
    def test_finds_by_title_word(self):
        notes = [Note("milk"), Note("rice")]
        self.assertEqual([n.title for n in search_notes(notes, "milk")], ["milk"])
