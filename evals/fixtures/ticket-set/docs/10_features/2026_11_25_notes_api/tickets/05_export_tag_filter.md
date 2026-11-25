# 05. Tag filter for export

**Status:** todo
**Blocked by:** 03
**Touches:** notesapi/export.py, tests/test_export.py

## Behavior
`export_text` and `export_markdown` take an optional `tag`. Only notes with
that tag are exported.

## Acceptance criteria
- With `tag="food"`, only notes that carry `food` are in the output.
- Without `tag`, all notes are exported, as before.

## Tests
- A failing test for each criterion, for both export functions.
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output.
