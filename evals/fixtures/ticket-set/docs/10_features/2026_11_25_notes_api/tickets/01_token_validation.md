# 01. Token validation

**Status:** todo
**Blocked by:** none
**Touches:** notesapi/auth.py, tests/test_auth.py

## Behavior
`validate_token` is the gate for every request. It must reject bad tokens.
This is authentication code, so a mistake is a security hole.

## Acceptance criteria
- An empty token is rejected.
- A token without the `tok_` prefix is rejected.
- An expired token is rejected. A token ends with `_<unix seconds>`, and it
  expires at that time.
- A valid token is accepted.

## Tests
- One failing test for each criterion above.
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output.
