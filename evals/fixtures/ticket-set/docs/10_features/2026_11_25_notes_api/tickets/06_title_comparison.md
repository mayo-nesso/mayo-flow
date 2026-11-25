# 06. Title comparison

**Status:** todo
**Blocked by:** none
**Touches:** notesapi/notes.py, tests/test_titles.py

## Behavior
Two titles that differ only in outer spaces or in case count as the same
title. `normalize_title` gives the form to compare.

## Acceptance criteria
- `normalize_title("  Hello ")` returns `"hello"`.
- `normalize_title("hello")` returns `"hello"`.

## Tests
- A failing test for each criterion above.
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output.
