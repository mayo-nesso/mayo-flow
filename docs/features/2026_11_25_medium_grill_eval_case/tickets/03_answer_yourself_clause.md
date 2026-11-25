# 03. "Answer yourself" clause in the phase-1 prompt

**Status:** done
**Blocked by:** none
**Touches:** evals/cases/feature-start-e2e/suite.json, tests/test_evals_suites.py (`test_case_shape`)

## Behavior

Phase 1 of every e2e case tells the model, without naming the grill, to take
the skill's recommended answer itself whenever the skill would ask a
question, so a headless grill does not stall at "Round 1" (spec decision 4).
`direct` is unchanged, so the baseline prompt does not move.

## Acceptance criteria

- `prepare` in every case contains a sentence like "When the skill would ask
  you a question, take its recommended answer yourself and continue."
- `prepare` does not contain "grill" (case-insensitive).
- `direct` stays `{feature}\n\n{headless}`; `test_direct_has_no_skill_words`
  stays green.
- Full suite green.

## Tests

- `tests/test_evals_suites.py` `test_case_shape`: assert the clause is in
  `prepare` and "grill" is not, for every case (red until `suite.json` is
  edited).
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output.
