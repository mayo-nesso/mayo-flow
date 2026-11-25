# 07. Docs: README Evals section and the pre-registered reading rule

**Status:** todo
**Blocked by:** 01, 02, 03
**Touches:** README.md, docs/features/2026_11_18_skill_evals/spec.md

## Behavior

The README's Evals section documents the `fixture_setup` case key, the
`spec_written` / `tickets_written` observations and the run flags for the
medium case (`--max-budget-usd 8 --timeout 3600`). The skill-evals spec's
"Feature-start overhead results" section gains the reading rule of spec
decision 13, written before any run, plus the open concerns of decisions 4
(clause changes the small cases' prompt) and 7 (outbox forces a job for the
message), and the blind spots carried from the grill.

## Acceptance criteria

- README names `fixture_setup`, what it skips, and its default.
- README lists the two new observations and the dated-folder glob.
- The reading rule (baseline-matches rule, trap-win rule, full chain counted
  only with `grill_written` in at least 2 of 3, "the grill's research paid")
  is in the skill-evals spec and dated before the first real run.
- Full suite green (docs-only; `test_skill_frontmatter` and doc checks still
  pass).

## Tests

- Docs-only ticket: no new behavior to test. Run the full suite before
  committing and state that no new test applies.
