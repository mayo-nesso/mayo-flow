# Notes API upgrades

## Goal

The notes library gets safer tokens, better export and search, and clearer
docs.

## Decisions

- Tokens must pass real checks before any call (security work).
- Export and search stay small, pure functions.
- Titles are compared in a normal form.

## Implementation plan

1. Token validation in `notesapi/auth.py`.
2. README usage text.
3. Markdown export in `notesapi/export.py`.
4. Case-blind search in `notesapi/search.py`.
5. Tag filter for export in `notesapi/export.py`.
6. Title comparison in `notesapi/notes.py`.

## Parallel plan

- Wave 1: tickets 1, 2, 3, 4, 6. Their blockers are all done.
- Wave 2: ticket 5. It is blocked by ticket 3.
- Overlaps: tickets 3 and 5 both touch `notesapi/export.py`. Run them in
  series.

## Test cases

- Each ticket lists its own tests.
