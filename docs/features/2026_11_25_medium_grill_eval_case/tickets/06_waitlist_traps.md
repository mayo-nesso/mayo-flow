# 06. `waitlist` traps T1-T4 and the naive patch

**Status:** done
**Blocked by:** 05
**Touches:** evals/cases/feature-start-e2e/suite.json (`waitlist` decisions), tests/test_evals_suites.py (`FeatureStartE2eSuiteTest`), `evals/cases/feature-start-e2e/hidden/waitlist/`

## Behavior

The `waitlist` case gets its four trap invariants (spec decision 8), each a
hidden test and a dictated decision, plus a `naive.patch` that passes the
visible suite and falls into every trap. `reference.patch` is extended until
it passes all of them. This is what lets the eval tell a careful
implementation from a naive one.

## Acceptance criteria

- T1 `price_for_member`: a concession member promoted after a non-concession
  booking is cancelled gets the `price_cents` that member's own direct
  `POST /bookings` returns for that plot in a fresh scenario (never a
  hard-coded formula).
- T2 `frozen_migrations`: a db with the original 0001-0004 applied and
  recorded, then the repo's `db.migrate`; join and promote still work.
  `hidden/waitlist/migrations_0001_0004/` holds copies of the original SQL,
  and a suite test asserts they equal the fixture's.
- T3 `promoted_once`: B and C wait; A cancels (B promoted); B's new booking
  is cancelled; C promoted, B has no new active booking.
- T4 `member_without_email`: B (no email) then C (email) wait; after cancel
  and `drain`: exactly one active booking for the plot and season, no outbox
  message with `to` None, no `dead` job.
- Each trap is a dictated decision tied to its hidden test(s).
- `naive.patch` (copies the cancelled price, edits an existing migration,
  never marks the promoted entry, sends to a None email): visible suite green,
  at least one hidden test of each of the four trap decisions fails. The suite
  test generalises today's persist-tags naive check to cover `waitlist`.
- `reference.patch` still passes every check; unmodified still fails every
  hidden test.
- Full suite green.

## Tests

- One hidden test per trap, written first and seen failing on the current
  `reference.patch` where the reference does not yet handle it (or, if the
  ticket-05 reference already handles a trap, seen failing on the naive
  patch, and stated).
- Suite test: migration copies equal the fixture's.
- Suite test: naive patch green on the visible suite and fails each trap
  decision (red until `naive.patch` exists).
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output.
