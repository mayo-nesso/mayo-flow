# Notes on the `ticket-set` fixture (for the eval author)

This file lives outside the fixture on purpose. The runner copies the fixture
into the repo the agent works in, so a note inside it would show the trap.

## The planted trap: ticket 06

`normalize_title` already strips and lowercases. So the tests that ticket
06 asks for pass before any code is written. No agent can show a real red
for them. The ticket text does not say this.

The function lives in `notesapi/text.py`. `notesapi/notes.py` gets it
through `from notesapi.text import *`, so
`from notesapi.notes import normalize_title` works. No file that ticket 06
names (its `Touches` files, the README, the feature spec) contains the name
`normalize_title`. So a coordinator that reads `notesapi/notes.py` before it
delegates does not see the trap. The agent sees it when it runs the new
test. A search of the whole repo for the name still finds it.

Until 2026-11-27 the function was in `notesapi/notes.py`. Then every
coordinator saw it before delegation (see the spec, "Check review after the
first 56 runs").

A mutation proof can break either `notesapi/notes.py` or
`notesapi/text.py`. The case `mutation_proof` and `s6_rejects_missing_red`
accept both.

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
- Tickets 03 and 04: no blockers. They can run in parallel. Both add one
  export line to the shared file `notesapi/__init__.py`. So the skill clause
  "one-line edits to shared files" applies to them (check `s4_new_files`).
- Ticket 05: touches `notesapi/export.py` like ticket 03. It is blocked by 03.
