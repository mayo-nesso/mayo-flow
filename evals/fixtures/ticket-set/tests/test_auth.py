import unittest

from notesapi.auth import validate_token


class AuthTest(unittest.TestCase):
    def test_non_empty_token_is_accepted(self):
        self.assertTrue(validate_token("tok_abc"))

    def test_empty_token_is_rejected(self):
        self.assertFalse(validate_token(""))
