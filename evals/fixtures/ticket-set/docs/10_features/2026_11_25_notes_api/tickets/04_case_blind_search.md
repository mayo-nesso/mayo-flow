# 04. Case-blind search

**Status:** todo
**Blocked by:** none
**Touches:** notesapi/search.py, tests/test_search.py

## Behavior
`search_notes` finds a note whatever the case of the title or the word.

## Acceptance criteria
- `search_notes([Note("Milk")], "milk")` returns the note.
- A word that is in no title returns an empty list.

## Tests
- A failing test for the case-blind match.
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output.
