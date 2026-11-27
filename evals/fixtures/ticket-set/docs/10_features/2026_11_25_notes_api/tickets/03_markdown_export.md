# 03. Markdown export

**Status:** todo
**Blocked by:** none
**Touches:** notesapi/export.py, notesapi/__init__.py, tests/test_export.py

## Behavior
`export_markdown(notes)` returns one `## <title>` heading per note, followed
by the body. The package exports it: `from notesapi import export_markdown`.

## Acceptance criteria
- Each note gives a heading line and a body line.
- An empty list gives an empty string.
- `from notesapi import export_markdown` works.

## Tests
- A failing test for two notes, one for the empty list and one for the
  package import.
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output.
