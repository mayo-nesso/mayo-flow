---
name: mayo-flow-feature-start
description: Start a new feature the TDD/spec-first way - create a feature/<slug> branch and a docs/*features* spec before any code. Use when the user wants to start, plan, or spec out a new feature.
version: 1.2.0
---

# Start a new feature

This project's workflow is spec-first, branch-per-feature, TDD-oriented. This
skill sets up both before a single line of implementation code is written.
Flow: branch → grill → spec (in a feature folder) → tickets → TDD loop.

Argument: a short description of the feature. If none was given, ask for one
(a few words is enough to derive a slug from).

## 1. Preconditions

- `git status` must be clean. If not, stop and ask the user to commit or
  stash first — do not start a new branch on top of uncommitted work.
- Determine the base branch: normally the repo's default branch (`main` or
  `master`). Exception: if the user is clearly starting a sub-feature that
  belongs inside a larger feature already in progress (an existing
  `feature/*` branch is currently checked out and the user's request is
  scoped to it), ask whether to branch from that feature branch instead of
  the default branch — this repo's history shows that pattern (fixes/features
  branched off `feature/app-interception`, merged back into it, only that
  branch eventually reaching main).
- Fetch and fast-forward the base branch before branching, if a remote exists.

## 2. Create the branch

`feature/<slug>` where `<slug>` is a short kebab-case derivation of the
description (e.g. "push notifications for likes" → `feature/like-push-notifications`).

## 3. Find or create the features doc folder

Look for an existing docs process folder for feature specs, in this order:
1. A folder matching `docs/*features*/` (e.g. `docs/10_features/`) — use it.
2. A plain `docs/features/` — use it, but mention to the user that this
   project hasn't adopted the `NN_` prefixed docs layout
   (`00_phases/10_features/20_fix-plans/50_audits`) and offer to migrate it.
3. Neither exists — create `docs/10_features/` (with an `archived/`
   subfolder) and mention this is a new convention being introduced.

Check for a `docs/structure.md` (or equivalent) and follow whatever spec
template shape existing specs in that folder already use — don't impose a
foreign template on a project with its own established one.

## 4. Create the feature folder and grill the plan

Each feature gets its own folder in the features folder found/created above:
`YYYY_MM_DD_<slug>/` using today's date. It holds `grill.md`, `spec.md` and
later `tickets/`, so branch-finish archives everything together. Older flat
specs (`YYYY_MM_DD_<slug>.md`) in the same folder stay as they are.

Create the folder, then invoke `mayo-flow-grill` on the feature description
with `<feature-folder>/grill.md` as the file to save the decisions to. Skip
the grill only for a small, obvious feature, and say you skipped it.

## 5. Write the spec

Invoke `mayo-flow-spec` with the feature folder path. It runs in an isolated
Opus subagent that reads `grill.md` and the code and writes `spec.md`, using
the project's own template if one exists. It cannot ask questions, so
anything it flagged as an open concern comes back in its report: relay that
to the user and settle it before committing.

## 6. Commit the spec alone

Commit only the feature folder (`grill.md` and `spec.md`), before any code
change:

```
docs: add feature spec for <slug>
```

Commit style: Conventional Commits unless the repo's own `CLAUDE.md` documents another (global `CLAUDE.md` section 8).

## 7. Break it into tickets (medium/large features)

If the implementation plan has more than about three steps, or steps that
depend on each other:

1. Invoke `mayo-flow-tickets` with the feature folder path. It drafts
   `tickets/NN_<slug>.md` files in an isolated Opus subagent.
2. Show the user the numbered list (title, blocked-by, what can be
   demonstrated) and iterate on the files until granularity and dependencies
   are approved.
3. Commit the `tickets/` folder alone, before any code:
   `docs: add tickets for <slug>` (same convention exception as step 6).

For a small feature, the plan in the spec is enough: skip this step.

## 8. State the TDD loop expectation

Tell the user (briefly) the loop that now applies for every implementation
step in the plan (or every ticket, once its blockers are `done`): write a
failing test at one of the spec's "Test seams" (none at unlisted seams) →
implement the minimum to pass → green → refactor if needed →
run the full suite (`mayo-flow-run-tests`) → commit. A finished ticket gets
`**Status:** done` in the same commit as its code. Never commit on red.

Red must be observed: run the new test and see it fail for the right reason
(missing behavior, not a typo or missing import) before writing
implementation, and show that output. A test that passes on its first run is
allowed only for characterization or performance tests of existing code, and
must be stated explicitly. Agents doing tickets follow it too; a hand-back
without red evidence is rejected and redone.

**Delegating.** The main thread coordinates and agents do the work; see
`mayo-flow-delegate`.

## 9. When the feature is done

Use `mayo-flow-branch-finish` to gate on the full suite, merge `--no-ff` into the
base branch, and archive the spec.
