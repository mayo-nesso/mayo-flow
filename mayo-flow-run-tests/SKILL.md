---
name: mayo-flow-run-tests
description: Detect and run the project's full verification suite (tests, typecheck, lint) and report pass/fail. Use when the user asks to run the suite, or as the gate before any commit/merge. Not for writing tests.
version: 1.2.1
model: haiku
---

# Run the full verification suite

Purpose: give a single, reliable "is this change safe to commit/merge" signal.
This project's engineering workflow requires the full suite to pass before
every commit, not just before a final merge — treat that as non-negotiable.

## 1. Detect the project's verification commands

Look at the project root (and any subdirectory the project's own docs name as
the app root, e.g. a `CLAUDE.md` line like "run every command from `app/`").

- **Node/JS project** (`package.json` present): read `scripts`. Run, in this
  order, whichever of these keys exist: `typecheck`, `lint`, `test`. Skip a
  step only if the script key does not exist — do not invent a substitute
  command.
- **Python project** (`pyproject.toml` / `requirements.txt`): look for
  `pytest`, `mypy`/`pyright`, `ruff`/`flake8` and run whichever are
  configured.
- **Other stacks**: check the project's `CLAUDE.md`/`README` for a documented
  test command before guessing. If truly nothing is documented and nothing is
  discoverable, stop and ask the user what the verification commands are —
  do not silently skip verification.

Cache nothing across runs — re-detect each time, since scripts change.

## 2. Run each command, in order, stopping at the first failure

Run typecheck → lint → test (or the stack's equivalent order: fast static
checks before the slower test run). If a step fails:

- Show the relevant error output (not the full noisy log — extract the actual
  error).
- Do NOT proceed to the next step.
- Do NOT let a caller (e.g. `mayo-flow-branch-finish`) continue to commit or merge.
- State clearly which command failed and why, so the user or the calling
  skill can fix it and re-run.

## 3. Report

On success: state plainly that the full suite passed (name the commands that
ran). On failure: state which command failed, the first real error, and stop.

## 4. Log every unexpected red

Keep a running record of what the suite catches, so the project can measure how
useful its tests are and improve its testing approach (which tests earn their
keep, which are flaky or brittle, where bugs escape). Without it the data does not
exist: local red runs leave no trace in git.

- File: `test-catch-log.md` in the project's docs folder (`docs/test-catch-log.md`;
  use the project's own docs convention if it has one). Create it on the first red
  with a short header and the table below. Commit it with the work that caused the
  red, as a docs change, never mixed into a code commit.
- **Log a run when a test that was green before this change goes red.** Do not log
  the intentional red of TDD (a new test written to fail first), nor a failure that is
  only a typo in the new test itself.
- One row per red, filled in once the cause is known (add the row at the red, finish
  the verdict when it is resolved):

  | Date | Branch | Failing test(s) | What changed | Verdict | Action taken |
  |---|---|---|---|---|---|

  `Verdict` is exactly one of:
  - `bug-caught`: the change was wrong and the test prevented a real defect. The true
    positive; the number the log exists for.
  - `intended-change`: behaviour changed on purpose, so the test was updated.
  - `flaky`: the test failed for a reason unrelated to the change (timing, order,
    environment). A candidate for a fix.
  - `brittle`: the test broke on a harmless change (it pinned an implementation detail).
    A candidate for rewriting.
  - `other`: say why in the action column.
- When the log has 10 or more rows, add or refresh a short summary at its top: count
  per verdict, the catch rate (`bug-caught` / all rows), and the tests that appear more
  than once. Say what it suggests about the approach (flaky or brittle tests to fix,
  areas where tests are thin) so the user can decide.
- This is bookkeeping, not a gate: it never blocks a commit by itself, and it must not
  slow the loop. A one-line row is enough.
- The runner records the failing test names and the change; the `Verdict` is a
  judgment call, so the coordinator (not the Haiku runner) sets it.

## Notes

- Never chain `git commit` after an unchecked step; use && and verify exit codes; commit only after the suite output was seen green.
- A single failing test is a stop condition, not a "mostly fine." Never
  interpret partial failures as acceptable to proceed past.
- If the project has no automated tests configured at all yet, say so
  explicitly rather than reporting a false pass — that is a gap worth
  surfacing, especially inside a TDD-oriented workflow.
