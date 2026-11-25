# 01. Skip a fixture's setup.sh with `"fixture_setup": false`

**Status:** done
**Blocked by:** none
**Touches:** evals/run.py, tests/test_evals_run.py, tests/test_evals_suites.py (`FeatureStartE2eSuiteTest.facts`)

## Behavior

A case can set `"fixture_setup": false` and get its fixture copied as one
commit on `main` without running the fixture's `setup.sh`. The switch works
everywhere a fixture copy is made for a case: the trial path (`run_trial`)
and the e2e suite test's `facts()`. With the key off, a `big-app` copy holds
none of the halfway waitlist that `handoff-resume` relies on; with the key
absent, every existing suite behaves as today (spec decision 6).

## Acceptance criteria

- `prepare_fixture(source, dest, run_setup=False)` does not run `setup.sh`;
  the copy is a single commit on `main`. The default stays `run_setup=True`.
- A `big-app` copy with `run_setup=False` is on `main`, has no
  `feature/plot-waitlist` branch, no `docs/10_features/2026_11_10_plot_waitlist/`,
  and no file contains the old waitlist spec text (for example "Plot waitlist").
- A trial (fake claude, `evals.run.main`) of a case with
  `"fixture_setup": false`, on a fixture whose `setup.sh` touches a file,
  leaves that file absent from the trial snapshot.
- `FeatureStartE2eSuiteTest.facts()` passes
  `run_setup=case.get("fixture_setup", True)`.
- `handoff-resume` suite tests stay green (they still get the setup).
- Full suite green: `python3 -m unittest discover -s tests`.

## Tests

- `tests/test_evals_run.py`: `run_setup=False` on a tmp fixture whose
  `setup.sh` creates a marker file; marker absent, one commit on `main`.
- `tests/test_evals_run.py`: the `big-app` assertions above.
- `tests/test_evals_run.py`: the fake-claude trial with `fixture_setup` false.
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output.
