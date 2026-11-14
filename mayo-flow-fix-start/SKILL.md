---
name: mayo-flow-fix-start
description: Start a new bug fix the spec-first way - create a fix/<slug> branch and a docs/*fix-plans* fix plan before any code. Use when the user reports a bug or wants to plan a fix.
version: 1.3.0
model: sonnet
---

# Start a new fix

Same discipline as a feature, scoped to a bug: write down the problem and the
plan before touching code, then work on its own branch.

Argument: a short description of the bug/fix. If none was given, ask for one,
and ask how it was reported (exact repro steps, or a vague user report) —
that distinction belongs in the doc.

## 1. Preconditions

- `git status` must be clean. If not, stop and ask the user to commit or
  stash first.
- Determine the base branch:
  - Default: the repo's default branch (`main`/`master`).
  - If the bug only affects a feature currently in progress on its own
    `feature/*` branch (not yet merged), branch off that feature branch
    instead, and plan to merge the fix back into it, not into main directly.
    Ask if it's unclear which base applies.
- Fetch/fast-forward the base branch first if a remote exists.

## 2. Create the branch

`fix/<slug>`, short kebab-case (e.g. `fix/daily-reminder-not-rescheduling`).

## 3. Find or create the fix-plans doc folder

Same lookup order as features: `docs/*fix-plans*/` (e.g.
`docs/20_fix-plans/`) → plain `docs/fix-plans/` (mention the `NN_` layout
gap) → create `docs/20_fix-plans/` with an `archived/` subfolder if neither
exists.

## 4. Investigate the root cause first

No fix is planned before the cause is found.

- **Build the feedback loop first.** Before any hypothesis, get one command
  you have already run that fails because of this bug: red-capable,
  deterministic, fast, runnable by an agent (a failing test, a curl, a CLI
  call, a script). If it can't be built, gather more data (logs, inputs) or
  ask the user for a repro; do not guess a cause without it.
- Read the full error/stack trace and shrink the repro to the minimum.
- Check what changed recently (`git log`, `git diff`, deps, config).
- Where the bug crosses components (UI → store → API → DB), log what enters and
  leaves each boundary once, to find the layer that breaks before reading code.
- Trace the bad value backward to where it originates; fix at the source.
- List 3-5 ranked, falsifiable hypotheses ("X is the cause because Y; if so,
  Z will happen"). Test the top one with the smallest possible change, one
  variable at a time. Tag temporary debug logs `[DEBUG-xxxx]` (random 4 chars)
  and remove them all before committing.

## 5. Write the fix plan

File name: `YYYY_MM_DD_<slug>.md`. If no established template exists in this
repo, use one section per distinct bug found (a fix-plan can bundle several
related bugs under one report):

```markdown
# <Short bug title> — YYYY-MM-DD

**Reported as:** <verbatim report or repro, or "no repro given">

## <N>. <Bug title> — <status once known>

**Files:** <file:line references>

**Problem:** <root cause, not just the symptom>

**Effect:** <what the user actually experiences>

**Fix:** <the planned fix, and why this fix and not an alternative. If there
are genuinely 2+ competing approaches (not just "the obvious fix"), expand
this into: the fix chosen, why given the actual constraints, a small table
of the real alternatives with pros/cons, and where the chosen fix still
doesn't fully handle the bug (residual risk, edge case left open)>

## Not investigated / out of scope
<anything deliberately left alone, and why>
```

Keep sentences short and concrete over dense and clever.

## 6. Commit the fix plan alone

```
docs: add fix plan for <slug>
```

Before any code change. Commit style: Conventional Commits unless the repo's own `CLAUDE.md` documents another (global `CLAUDE.md` section 8).

## 7. TDD loop

For each bug: write a failing test that reproduces it first, then fix, then
green, then run the full suite (`mayo-flow-run-tests`) before committing. Never
commit on red. Confirm the regression test really guards the bug: with the fix
reverted (`git stash` the fix) it must fail, with the fix restored it must
pass. A test that passes without the fix proves nothing. Show the red output before implementing; this applies equally to delegated agents (see `mayo-flow-delegate`).

If a fix doesn't work, return to step 4 with the new evidence; don't stack a
second fix on top. After 3 failed fixes, stop and question the design (shared
state, coupling, wrong pattern) with the user before attempting a fourth. If a bug is in code with no test harness available at all
(e.g. native platform code with no test infra in this repo), say so
explicitly in the doc's per-bug section instead of silently skipping the
test — that gap must be visible, not hidden.

## 8. When the fix is done

Use `mayo-flow-branch-finish` to gate on the full suite, merge `--no-ff`, and
archive the fix plan.
