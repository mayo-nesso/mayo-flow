# Grill: medium eval case with a trap (grill must run)

Feature: a third case for the `feature-start-e2e` suite, medium-sized and with
traps, built so that `mayo-flow-feature-start` actually runs the grill
(`grill_written` true). That measures the full chain (grill, design, spec,
tickets) against the direct baseline. Until now the skill called both
`list-cli` features small and skipped the grill (`grill_written` 0/3).

Context: `docs/features/2026_11_24_feature_start_overhead_eval/` (spec, grill)
and `docs/features/2026_11_18_skill_evals/spec.md` ("Feature-start overhead
results"). All questions below were answered "yes" to the recommended answer.

## Settled facts

- Why the grill never ran: `mayo-flow-feature-start` step 4 allows skipping it
  "only for a small, obvious feature, and say you skipped it". In every
  2026-11-24 skill trial, Sonnet called the feature small, wrote `spec.md`
  itself, produced no tickets and said so. Forcing the grill would break
  decision 8 of the overhead spec (measure the flow as it behaves), so the
  case is made bigger instead.
- `run.py run <suite>` runs every case; there is no `--case` filter.
  `suite_hash` covers the whole `suite.json`, so adding a case changes it for
  all cases.
- `prepare_fixture` always runs a fixture's `setup.sh`. `big-app`'s builds the
  halfway waitlist branch for `handoff-resume`.
- `big-app` (allotment) is a stdlib Python/sqlite app (~460 lines: core, worker,
  API, numbered migrations, `docs/structure.md` with conventions). Traps
  already in its code, none in any feature text: migrations are recorded by
  name and never rerun; `pricing.price_cents(plot, member)` applies a
  concession discount; `members.email` is nullable and reminders skip members
  without one; core functions never commit (a handler is one transaction);
  messages only go out through worker jobs that append to an outbox;
  `clock.now()` has seconds precision and tests freeze it.
- `big-app` contains an archived spec `docs/10_features/archived/2026_10_02_plot_pricing/spec.md`;
  `baseline_wrote_spec` (`docs/**/spec.md`) matches it today.
- Lesson from `persist-tags`: the skill openly chose "an edit on `milk` changes
  both entries", stated it, and failed the hidden test. A dictated test that a
  careful engineer could decide against measures agreement with the case
  author, not quality.

## Decisions

1. **Fixture: reuse `big-app` without its `setup.sh`.** Real size (several
   modules, a schema change) is the only thing that reliably moves the model
   off "small"; its traps come from its documented conventions. Rejected: a
   copy (~900 duplicated lines), growing `list-cli-trap` (stays "small"), a new
   hand-made fixture (most work, hand-made traps).
2. **Feature: plot waitlist, from scratch.** Join and leave routes; cancelling
   a booking books the plot for the first member in line; the member is told
   through the outbox. Touches every layer and has real forks (inline vs worker
   job, free plot, member already holding a booking). Rejected: booking
   transfer (may be judged small), refunds (money rules not grounded in the
   fixture's docs).
3. **Placement: a third case in `feature-start-e2e`.** The suite hash changes
   and the two small cases are rerun (~$2.50 at n=3), which doubles as
   replication of the 2026-11-24 results. No `--case` filter (YAGNI).
   Rejected: a `--case` filter, a new suite folder (duplicated rubric and
   suite-test class).
4. **Phase-1 prompt gets an "answer yourself" clause.** `prepare`, in all three
   cases, adds: when the skill would ask a question, take its recommended
   answer and continue. It does not tell the agent to run the grill, so
   decision 8 holds; `direct` is unchanged. Without it a headless grill may
   stop at "Round 1" and phase 1 ends with no spec. Rejected: leaving the
   text, forcing the grill ("Do NOT skip the grill", v1's mistake).
5. **No `design.md`.** `big-app` has no UI, so `mayo-flow-design` says "no UI";
   the impeccable plugin loading under `-p` is unverified. State it in the
   results; a UI case is a separate backlog item.
6. **Skip `setup.sh` with a case key `"fixture_setup": false`,** passed as
   `prepare_fixture(..., run_setup=False)` in `run_trial` and in the suite
   test's `facts()`. Red/green test in `test_evals_run.py`: with the key set,
   the copy is on `main`, with no `feature/plot-waitlist` branch and no
   waitlist files, and the old waitlist spec text is not readable. Rejected:
   moving `setup.sh` to a handoff-only fixture (churns that suite), copying.
7. **Feature text pins only the surface the hidden tests drive:**
   `POST /waitlist` (`plot_id`, `member_id`, `season`) returns 201 and an
   `id`; `DELETE /waitlist/<id>` leaves the line; `DELETE /bookings/<id>`
   books the plot for the first member in line (first come, first served); the
   new booking shows in `GET /members/<id>/bookings`; the member is told by an
   outbox message with template `waitlist_promoted`. Left out: price,
   concession, email, migration, worker/job/inline, transaction, "twice/again",
   ties. A per-case leak-word list in the suite test (for example `price,
   concession, email, migrat, worker, job, inline, transaction, twice, again`).
   Accepted cost: "outbox" hints at the worker convention, but it is the
   fixture's only message channel.
8. **Four traps, each a real invariant** (test: could a careful engineer
   choose otherwise and say so? if yes it is an open decision, not dictated):
   - T1 price: the promoted booking's `price_cents` equals what that member
     pays booking the same plot directly (compared against a direct API
     booking, no hard-coded formula). Naive failure: copying the cancelled
     booking's price or inserting without `pricing`.
   - T2 frozen migrations: a database with the original 0001-0004 applied and
     recorded, then the repo's `db.migrate`; the waitlist must still work.
     Naive failure: editing an existing migration. The hidden dir keeps copies
     of the original SQL, and a suite test asserts they equal the fixture's.
   - T3 never promoted twice: when the promoted member's new booking is
     cancelled, the next member in line gets the plot and the first is not
     rebooked. Naive failure: the promoted entry is never marked or removed.
   - T4 member without email: after cancel and `drain`, the plot has exactly one
     active booking, no outbox message has `to` None, no job is `dead`.
     Written loosely on purpose: "booked without a message" and "skipped to
     the next member" both pass.
   - Excluded: transaction rollback (no deterministic way to make promotion
     fail from outside), same-second ties (SQLite returns insertion order, so
     the trap would not bite; hidden tests use distinct frozen times).
   - Validation: the naive patch must fail at least one test per trap; the
     reference patch must pass all of them.
9. **Hidden tests run each scenario in a subprocess** (`python -c` that
   migrates a temp sqlite file, calls `api.routes.dispatch` and
   `worker.runner.drain`, prints JSON), keeping the "subprocess only" rule of
   decision 10 of the overhead spec; a hang hits the runner timeout. The suite
   test becomes "no import of the fixture package anywhere in `hidden/`".
   Rejected: lazy in-method imports (would force loosening the current rule).
10. **If the skill still skips the grill: smoke gate.** Run one skill trial
    first. If `grill_written` is false, stop, enlarge or reword the feature and
    smoke again; never force the grill and never select trials. Then n=3,
    report every trial, split by `grill_written`. Pre-registered: if fewer than
    2 of 3 trials have a grill, the case missed its design goal and the
    full-chain rule is not read from it. Rejected: running up to 5 trials until
    3 have a grill (selection bias), a forced variant (v1 again).
11. **Decisions for the `decisions` judge.** Dictated, each tied to hidden
    tests: `fifo_promotion`, `notify` (one `waitlist_promoted` message to the
    promoted member's email), `price_for_member` (T1), `frozen_migrations`
    (T2), `promoted_once` (T3), `member_without_email` (T4), `leave` (a left
    entry is not promoted). Open, judged only for explicit vs silent (max 4):
    `inline_or_job`, `join_free_plot`, `already_holding`, `join_twice`. The
    judge is still not blind (`grill.md` betrays the skill condition); state
    it again in the results.
12. **Suite-test and observation changes that come with the case:**
    (a) `test_cases` lists three ids; (b) `LEAKS` becomes per case (shared
    words plus a case list); (c) the import rule names each case's fixture
    package; (d) `facts()` honours `fixture_setup`; (e) `baseline_wrote_spec`
    glob becomes `docs/10_features/[0-9]*/spec.md` in all three cases (today's
    `docs/**/spec.md` matches big-app's archived spec and would be true on
    every row); (f) new observations `spec_written` (a non-archived `spec.md`
    exists after phase 1) and `tickets_written` (`docs/10_features/*/tickets/*.md`),
    so a grill that stalls before the spec does not look like a phase-2
    failure; (g) the naive-patch check covers all four traps.
13. **Pre-registered reading rule, written before any run.** Per case, same
    shape as before: the baseline matches the skill on `waitlist` if it is
    within one hidden test and the skill costs more; the skill pays off if it
    wins at least one trap invariant (T1-T4) in at least 2 of 3 trials. The
    full-chain verdict counts only trials with `grill_written` and needs at
    least 2 of 3 (decision 10). If the skill wins only through traps that
    grill-prep named in `grill.md`, record it as "the grill's research paid"
    (the closedclaw hypothesis). Rejected: a cost-adjusted rule (pass rate per
    dollar), invented after the fact and hard to read.
14. **Run budget and flags:** `--max-budget-usd 8 --timeout 3600` (phase 1 has
    three Opus subagents: grill-prep, spec, tickets; phase 2 may delegate
    tickets). Design estimate: skill $4-9 per trial ($2-4 phase 1, $2-5
    phase 2), baseline $0.5-1.5; about $15-30 for n=3 per condition plus about
    $2.50 for the two small cases. Run the conditions as separate batches
    because of the 5-hour usage limit. Real runs need the owner's explicit OK
    when the time comes.

## Blind spots recorded (no decision needed)

- **Tickets confound.** A medium plan will get tickets, so phase 2 runs the
  ticket and delegate loop. Cost differences mix grill, spec, tickets and
  delegation; the per-phase split only separates phase 1 from phase 2. Accepted
  because it is the full chain; say so in the results. Do not combine with the
  "tickets threshold" backlog experiment (interrupt plus handoff).
- **Phase 2 depends on phase 1 completing.** Read `spec_written` before any
  hidden-test failure in the skill condition.
- **Precondition failures apart from trap failures.** One plain
  `test_join_and_promote` that every trap test depends on, so "routes under a
  different path" does not read as "all traps failed".
- **Visible suite.** big-app's own tests must stay green
  (`visible_suite_green`); agent-added tests that rely on wall-clock time could
  flake, so one smoke check.
- **`hidden_seen` strings** still work; the hidden dir also holds copies of the
  original SQL, which no prompt names.
- **Handoff-resume isolation.** The waitlist spec text lives in `setup.sh`,
  which is not copied into the trial repo (`ignore_patterns`); the `fixture_setup`
  test verifies the from-scratch agent cannot read it.
- **Owner spot-check of `decisions` labels** is still open from the
  2026-11-24 runs (decision 11) and would now cover three cases.

## Open items

None for the design. The run itself (smoke trial, then n=3) waits for the
owner's OK on cost.
