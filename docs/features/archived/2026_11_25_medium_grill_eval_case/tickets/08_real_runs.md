# 08. Real runs: smoke gate, n=3 per condition, results

**Status:** done
**Blocked by:** 06, 07
**Touches:** evals/results/, docs/features/2026_11_18_skill_evals/spec.md

## Behavior

Manual, and only with the owner's explicit OK (it spends real money). One
skill trial of `waitlist` first; if `grill_written` is false, stop and reword
or enlarge the feature (new suite hash), never force the grill and never
select trials (spec decision 10). Then n=3 per condition, each condition as
its own batch, the `decisions` judge, and the results written into the
skill-evals spec under the pre-registered rule from ticket 07.

## Acceptance criteria

- Owner OK recorded before the first call.
- Smoke row reported, including when it fails the gate.
- n=3 skill and n=3 baseline on `waitlist`, plus the rerun of the two small
  cases, every trial reported and split by `grill_written`.
- Results read with the rule of decision 13 and state: the decision-4 and
  decision-7 concerns, no `design.md` (decision 5), the tickets confound, the
  judge not blind, and the open owner spot-check of `decisions` labels.
- Rows with `spec_written` true have their phase-1 trace checked.

## Tests

- No code change; no new test. If the smoke forces a reword of the feature
  text, that edit goes through the suite tests (leak words, unmodified /
  naive / reference) before the next run.
