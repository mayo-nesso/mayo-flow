---
name: mayo-flow-branch-finish
description: "Finish a feature/fix branch: gate on the full suite, merge --no-ff, archive the spec/fix-plan, update docs/structure.md, check whether an audit is due. Use when the user says the work is done, ready to merge or ready to ship. Not for starting work or reviewing a diff."
version: 1.4.3
---

# Finish a feature or fix branch

This is the closing half of `mayo-flow-feature-start`/`mayo-flow-fix-start`. It never
force-pushes, never deletes a remote branch, and never skips the test gate.

## 1. Preconditions

- `git status` clean: everything meant for this branch is committed.
- Confirm which branch this is finishing and what it should merge into:
  - Normally the repo's default branch (`main`/`master`).
  - If this branch was itself started off another still-open `feature/*`
    branch (check with the user or `git merge-base --is-ancestor`), merge
    into that parent branch instead, not straight to main.

## 2. Gate on the full suite

Invoke `mayo-flow-run-tests` (or inline its logic) now. If it fails, STOP here —
report the failure and do not merge.
Re-run the suite yourself; never trust an agent's pass claim.
A repo with no test suite at all (docs, config or skill repos) is not a
failure: the gate is a manual check that every path and reference the branch
touched still resolves (grep), and say so in the report.

**Code review (only when warranted).** Tests prove what was tested; a review
catches what wasn't. Check the branch diff against the target
(`git diff --stat <target-branch>...HEAD`). Propose `/code-review` only if
ALL hold:

- the changes are code (not just docs, specs or skill/markdown files);
- the change is heavy: roughly 300+ changed lines or 10+ files;
- it touches a risk area: auth/permissions, payments, data migrations or
  schema, concurrency/background jobs, native/platform code, or a public API
  or contract.

If so, offer it to the user and run it only on their yes (it costs tokens).
Fix confirmed findings with a new test first, re-run the suite, then continue.
Otherwise skip silently.

**See it working (runnable apps only).** Green tests don't prove the feature
works in the real app. If the project is a runnable app (UI, server, CLI) and
the change is user-visible, invoke the `run` skill and exercise the changed
behaviour once. Skip for docs/infra/library-only branches.

**Design gate (UI changes only).** If the branch diff touches screens or
components, invoke `mayo-flow-design` for its gate (`critique` on the changed
screens). Block only on what that skill defines as blocking; report the rest
as follow-ups. Skip silently when the diff has no UI.

## 3. Find the associated spec/fix-plan doc

Look in the project's features/fix-plans doc folder(s) for the doc created
by `mayo-flow-feature-start`/`mayo-flow-fix-start` for this branch (match by slug in
the branch name, or ask the user which doc this is if it's ambiguous — e.g.
several docs were touched on this branch).

For a feature this is either a flat spec file or a feature folder
(`YYYY_MM_DD_<slug>/` with `spec.md` and optionally `tickets/`). Everything
below applies to the whole folder in the second case.

**Spec-compliance pass.** If a spec or fix-plan exists, tests passing does not
mean the feature is complete. Dispatch a fresh subagent with the doc plus
`git diff <target-branch>...HEAD` and ask for: requirements in the doc that
the diff does not implement, changes the doc never asked for (scope creep),
and behaviour that contradicts the doc. Do not merge or rerank its findings.
Missing or wrong items go back to a test-first fix (step 2 again); scope creep
is shown to the user to keep or drop.

## 4. Decide: fully done, or partially done?

Read the doc's implementation plan / verification checklist. If the feature
has a `tickets/` folder, also read every ticket's `**Status:**`: any ticket
not `done` means partially done. Ask yourself (and the user, if genuinely
unclear) whether every planned step is actually merged and working, with no
explicitly-open follow-up items.

- **Fully done** → go to step 5 (archive).
- **Partially done** (e.g. one platform blocked on an external dependency,
  a known issue deliberately deferred) → do NOT archive. Instead:
  - Mark completed steps with a done-marker plus date, e.g.
    `**Done — YYYY-MM-DD (`<short-sha>`)**`, matching whatever marker style
    the doc already uses if one exists.
  - Leave open items visibly open (do not delete or hide them).
  - Skip to step 6.

## 5. Archive the doc

- Add a short completion marker near the top of the doc (e.g.
  `**Completed:** YYYY-MM-DD`).
- Move the file (or the whole feature folder, tickets included) into that
  folder's `archived/` subfolder (`git mv`). Put the completion marker in
  `spec.md` for a feature folder.
- Do not edit the doc's substance beyond the completion marker and any final
  step markers.
- When the feature completes a phase, mark that phase's row in
  `docs/PLAN.md` and `docs/00_phases/phase_N.md` as completed with the date,
  if those files exist, and include them in the docs commit (step 7).

## 6. Update the project's structure reference

If this branch introduced something a project map like `docs/structure.md`
would want to know about (a new store/module/component/directory/table/route
pattern), update that file's relevant section. Skip this step if the file
doesn't exist and the project has never had one — don't invent a
structure-map convention a project hasn't opted into.

## 7. Commit the docs-only changes

Separate commit from any code:

```
docs: archive <slug> spec and update structure.md
```

(or just the archiving, if no structure.md exists). Commit style: Conventional Commits unless the repo's own `CLAUDE.md` documents another (global `CLAUDE.md` section 8).

## 8. Merge

Before merging, list the unresolved items. Stop and warn only if one truly
blocks the merge; otherwise merge and list them as follow-ups in the report
(the user tests manually).

```
git checkout <target-branch>
git pull   # if a remote tracks it
git merge --no-ff <this-branch> -m "Merge <this-branch> into <target-branch>"
```

Never fast-forward this merge — the `--no-ff` is intentional so the feature's
full history stays visible as a unit in `git log --graph`.

## 9. Clean up the branch

After a successful merge, delete merged local branches (`git branch -d`)
and their worktrees without asking. If the branch was pushed to a remote, do
NOT delete the remote branch without the user's explicit confirmation —
that's a shared-state, hard-to-reverse action.

## 10. Check whether an audit is due

Only run this check when the target branch is the repo's default branch
(`main`/`master`). A merge into a parent `feature/*` branch (the step 1
exception) doesn't count yet — those merges get counted once that feature
branch itself finishes into `main`.

Count merges into `main`/`master` since the last audit. The last audit is
the newest `*_summary.md` in the audits folder (archived rounds included):

```
since=$(git log -1 --format=%cI -- '<audits-folder>/*_summary.md')
git log --merges ${since:+--since="$since"} <target-branch> --oneline | wc -l
```

(No summary file yet means an empty `since`, so the count is "since project
start": just propose a first audit.) Default threshold: **10 merges into
main**. If the count including this merge reaches the threshold, tell the
user an audit is due and offer to run `mayo-flow-audit` — do not run it
automatically, this is always a proposal the user accepts or defers.

## 11. Retro (never blocks, never waits)

Look back over the branch yourself: did anything slow us down or go wrong
that should become a rule, a check or a skill edit? Put the one-line answer
in the final report (a candidate, or "nothing notable") and move on. Do not
ask the user and do not leave the retro as an open item: if they want
something added they will say so, and silence means nothing important
happened.

If you found something, turn it into the smallest fix: a mechanical problem
becomes a check (a test, lint rule or script); a judgement call becomes one
line in the project `CLAUDE.md`; a problem in a skill is noted for the user
to fix in `mayo-flow`. Do not write a retro document.
