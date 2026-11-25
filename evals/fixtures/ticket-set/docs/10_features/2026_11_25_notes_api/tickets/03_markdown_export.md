# 03. Markdown export

**Status:** todo
**Blocked by:** none
**Touches:** notesapi/export.py, tests/test_export.py

## Behavior
`export_markdown(notes)` returns one `## <title>` heading per note, followed
by the body.

## Acceptance criteria
- Each note gives a heading line and a body line.
- An empty list gives an empty string.

## Tests
- A failing test for two notes and one for the empty list.
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output.
