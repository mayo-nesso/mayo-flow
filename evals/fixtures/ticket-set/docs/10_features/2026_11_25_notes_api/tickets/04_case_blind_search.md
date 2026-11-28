# 04. Case-blind search

**Status:** todo
**Blocked by:** none
**Touches:** notesapi/search.py, notesapi/__init__.py, tests/test_search.py

## Behavior
`search_notes` finds a note whatever the case of the title or the word. The
package exports it: `from notesapi import search_notes`.

## Acceptance criteria
- `search_notes([Note("Milk")], "milk")` returns the note.
- A word that is in no title returns an empty list.
- `from notesapi import search_notes` works.

## Tests
- A failing test for the case-blind match and one for the package import.
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output.
