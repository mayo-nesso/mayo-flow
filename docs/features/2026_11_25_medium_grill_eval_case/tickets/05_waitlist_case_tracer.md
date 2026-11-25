# 05. `waitlist` case, tracer: join, leave, FIFO promotion, notify

**Status:** todo
**Blocked by:** 01, 02, 03, 04
**Touches:** evals/cases/feature-start-e2e/suite.json, tests/test_evals_suites.py (`FeatureStartE2eSuiteTest`), new `evals/cases/feature-start-e2e/hidden/waitlist/`

## Behavior

The suite gains a third case, `waitlist`, on `big-app` with
`"fixture_setup": false`, runnable end to end through the same suite test a
trial uses. Its hidden tests drive only `allotment.api.routes.dispatch` and
`allotment.worker.runner.drain`, each scenario in its own `python -c`
subprocess (temp sqlite, frozen distinct clock per join, `drain` after every
cancel, JSON on stdout), with a stdlib-only test file (spec decisions 7, 9).
This ticket covers the precondition and plain behavior, not the traps: the
unmodified fixture fails every hidden test and `reference.patch` passes all.

## Acceptance criteria

- `suite.json` entry `waitlist`: `fixture: big-app`, `fixture_setup: false`,
  the feature text of spec decision 7 (pins `POST /waitlist` with
  `plot_id`/`member_id`/`season` returning 201 and `id`, `DELETE /waitlist/<id>`,
  `DELETE /bookings/<id>` promoting first come first served, the new booking
  in `GET /members/<id>/bookings`, outbox template `waitlist_promoted`), the
  shared `prepare`/`prompt`/`direct`/`headless`, the same facts and
  observations as the other cases (including ticket 02's).
- Per-case leak words for `waitlist`: `price, concession, email, migrat,
  worker, job, inline, transaction, twice, again`; fixture package
  `allotment`. Feature text contains none.
- Hidden tests: `test_join_and_promote`, FIFO (B then C; B promoted, C not),
  notify (one `waitlist_promoted` message to B's email), leave (B leaves, C
  promoted, B not).
- Decisions: dictated `fifo_promotion`, `notify`, `leave` tied to those
  tests; open `inline_or_job` (about the booking, not the message),
  `join_free_plot`, `already_holding`, `join_twice`.
- `test_cases` expects three ids and `waitlist`'s fixture and key.
- Unmodified `big-app`: visible suite green, every hidden test fails.
  `reference.patch` (applies to the clean `main` copy; new migration, no
  edit to 0001-0004): every check passes.
- `test_decisions_name_real_hidden_tests` green for `waitlist`.
- Full suite green.

## Tests

- `test_cases` with the third id, and the leak/import table entry (red until
  the case exists).
- The hidden test file itself, written before `reference.patch`: run against
  the unmodified copy and see every test fail because the route is missing
  (404 / unknown route), not because the scenario script is broken.
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output.
