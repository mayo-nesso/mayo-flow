# 02. Dated-folder spec glob and `spec_written` / `tickets_written`

**Status:** todo
**Blocked by:** none
**Touches:** evals/cases/feature-start-e2e/suite.json, tests/test_evals_checks.py, tests/test_evals_suites.py (`test_case_shape`)

## Behavior

The e2e observations stop counting archived specs: `baseline_wrote_spec`
matches only `docs/10_features/[0-9]*/spec.md`, so `big-app`'s archived
pricing spec no longer makes it true on every row. Both existing cases also
record `spec_written` and `tickets_written`, so a report can show how far
phase 1 got (spec decision 12 e, f).

## Acceptance criteria

- `fact_checks` with a `matches` observation on
  `docs/10_features/[0-9]*/spec.md` is false for a repo holding only
  `docs/10_features/archived/<dated>/spec.md` and true for one holding
  `docs/10_features/<dated>/spec.md`.
- `exclude-filter` and `persist-tags` use the dated glob for
  `baseline_wrote_spec` and observe `spec_written`
  (`docs/10_features/[0-9]*/spec.md`) and `tickets_written`
  (`docs/10_features/*/tickets/*.md`).
- `test_case_shape` asserts both new observation ids and the dated glob for
  every case.
- Full suite green.

## Tests

- `tests/test_evals_checks.py`: archived spec ignored, dated folder matched.
- `tests/test_evals_suites.py` `test_case_shape`: the new ids and glob are
  required (red until `suite.json` is edited).
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output. If the checks test passes on its first
  run (the glob already works in `fact_checks`), state it as a
  characterization test; the suite-shape test must still go red first.
