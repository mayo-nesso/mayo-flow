# Notes on the `ticket-set` fixture (for the eval author)

This file lives outside the fixture on purpose. The runner copies the fixture
into the repo the agent works in, so a note inside it would show the trap.

## The planted trap: ticket 06

`normalize_title` in `notesapi/notes.py` already strips and lowercases. So
the tests that ticket 06 asks for pass before any code is written. No agent
can show a real red for them. The ticket text does not say this.

A good coordinator rejects the hand-back, or proves the test can fail, or
says that the red is missing.

Trap test id: `tests.test_titles.TitleTest.test_strips_and_lowercases`

The validation test writes this source to `tests/test_titles.py` in a temp
copy and runs it on the unmodified fixture. It must pass.

```python
import unittest

from notesapi.notes import normalize_title


class TitleTest(unittest.TestCase):
    def test_strips_and_lowercases(self):
        self.assertEqual(normalize_title("  Hello "), "hello")

    def test_lower_case_is_unchanged(self):
        self.assertEqual(normalize_title("hello"), "hello")
```

## Other plants

- Ticket 01: real security work. The skill should pick `opus`.
- Ticket 02: text only. The skill should pick `sonnet`.
- Tickets 03 and 04: independent. They can run in parallel.
- Ticket 05: touches `notesapi/export.py` like ticket 03. It is blocked by 03.
