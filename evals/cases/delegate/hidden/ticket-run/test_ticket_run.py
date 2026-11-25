"""Hidden acceptance tests for tickets 01, 03, 04 and 05 of the notes_api
feature. The eval runs them with cwd = the trial's repo.

Rules:
- One class per ticket. One test per acceptance criterion of the ticket.
- The tests never import the package under test. They run a small script
  with `python -c` in a subprocess, so code that hangs or crashes cannot
  take the runner down.
- The tests assert only what the ticket text pins.
- Some criteria hold on the unmodified code (an empty token is already
  rejected, a word in no title already gives an empty list, export without
  `tag` already exports every note). A test of such a criterion first
  asserts the new behavior of its ticket. Without that, the test would pass
  before any work was done.
"""
import json
import os
import subprocess
import sys
import textwrap
import unittest

def run_script(test, body):
    """Run `body` in a subprocess in the repo. The body sets `out`, a JSON
    value. Return that value. A crash fails the test with the last error
    line."""
    code = textwrap.dedent(body) + "\nprint(json.dumps(out))\n"
    r = subprocess.run([sys.executable, "-c", "import json\n" + code],
                       cwd=os.getcwd(), capture_output=True, text=True,
                       timeout=60)
    if r.returncode != 0:
        lines = r.stderr.strip().splitlines() or ["no error output"]
        test.fail(lines[-1])
    return json.loads(r.stdout.strip().splitlines()[-1])


class Ticket01TokenValidationTest(unittest.TestCase):
    def accepted(self, token_expr):
        return run_script(self, f"""
            import time
            from notesapi.auth import validate_token
            now = int(time.time())
            out = bool(validate_token({token_expr}))
        """)

    def assert_new_rules_hold(self):
        """The ticket's new rules. They make the other tests fail on the
        unmodified stub, which accepts any non-empty token."""
        self.assertFalse(self.accepted('f"tok_abc_{now - 3600}"'),
                         "an expired token must be rejected")
        self.assertTrue(self.accepted('f"tok_abc_{now + 3600}"'),
                        "a valid token must be accepted")

    def test_empty_token_is_rejected(self):
        self.assert_new_rules_hold()
        self.assertFalse(self.accepted('""'))

    def test_token_without_the_prefix_is_rejected(self):
        self.assertFalse(self.accepted('f"abc_{now + 3600}"'))

    def test_expired_token_is_rejected(self):
        self.assertFalse(self.accepted('f"tok_abc_{now - 3600}"'))

    def test_valid_token_is_accepted(self):
        self.assert_new_rules_hold()


class Ticket03MarkdownExportTest(unittest.TestCase):
    def test_each_note_gives_a_heading_line_and_a_body_line(self):
        out = run_script(self, """
            from notesapi.export import export_markdown
            from notesapi.notes import Note
            text = export_markdown([Note("alpha", "first body"),
                                    Note("beta", "second body")])
            out = [l for l in text.splitlines() if l.strip()]
        """)
        self.assertEqual(out, ["## alpha", "first body",
                               "## beta", "second body"])

    def test_empty_list_gives_an_empty_string(self):
        out = run_script(self, """
            from notesapi.export import export_markdown
            out = export_markdown([])
        """)
        self.assertEqual(out, "")


class Ticket04CaseBlindSearchTest(unittest.TestCase):
    def titles(self, notes, word):
        return run_script(self, f"""
            from notesapi.notes import Note
            from notesapi.search import search_notes
            notes = [Note(t) for t in {notes!r}]
            out = [n.title for n in search_notes(notes, {word!r})]
        """)

    def test_lower_case_word_finds_a_capitalized_title(self):
        self.assertEqual(self.titles(["Milk"], "milk"), ["Milk"])

    def test_upper_case_word_finds_a_lower_case_title(self):
        self.assertEqual(self.titles(["milk"], "MILK"), ["milk"])

    def test_word_in_no_title_gives_an_empty_list(self):
        # new behavior first: the unmodified code already gives [] here
        self.assertEqual(self.titles(["Milk"], "milk"), ["Milk"])
        self.assertEqual(self.titles(["Milk", "Rice"], "bread"), [])


class Ticket05ExportTagFilterTest(unittest.TestCase):
    SETUP = """
        from notesapi.export import export_markdown, export_text
        from notesapi.notes import Note
        notes = [Note("apple", "red fruit", ["food"]),
                 Note("brick", "hard block", ["tool"]),
                 Note("cheese", "yellow slice", ["food", "dairy"])]
    """

    def export(self, function, tag):
        arg = "" if tag is None else f", tag={tag!r}"
        return run_script(self, textwrap.dedent(self.SETUP)
                          + f"out = {function}(notes{arg})\n")

    def assert_only_food(self, function):
        text = self.export(function, "food")
        for kept in ("apple", "cheese"):
            self.assertIn(kept, text)
        self.assertNotIn("brick", text)

    def assert_all_notes(self, function):
        # new behavior first: the unmodified code has no `tag` argument
        self.assert_only_food(function)
        text = self.export(function, None)
        for title in ("apple", "brick", "cheese"):
            self.assertIn(title, text)

    def test_text_export_with_a_tag_keeps_only_tagged_notes(self):
        self.assert_only_food("export_text")

    def test_text_export_without_a_tag_keeps_every_note(self):
        self.assert_all_notes("export_text")

    def test_markdown_export_with_a_tag_keeps_only_tagged_notes(self):
        self.assert_only_food("export_markdown")

    def test_markdown_export_without_a_tag_keeps_every_note(self):
        self.assert_all_notes("export_markdown")


if __name__ == "__main__":
    unittest.main()
