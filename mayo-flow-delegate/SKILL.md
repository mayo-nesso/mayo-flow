---
name: mayo-flow-delegate
description: Coordinate rather than do - delegate implementation, tests, refactors, reviews and doc rewrites to fresh agents with specific context. Use when a feature/fix/ticket set is being worked, or the user says delegate, parallel or agents.
version: 1.1.0
---

# Delegate the work, coordinate the result

## 1. Roles

The main thread coordinates: decisions, questions to the user, merges,
conflict resolution and short verifications. Agents do the work:
implementation, tests, refactors, reviews and doc rewrites. Each agent starts
fresh, so give it specific context; it does not see this conversation.

## 2. Models

Pass `model` explicitly in every Agent call. Do not rely on a skill's frontmatter.

- Running and reporting the suite (`mayo-flow-run-tests`): `haiku`. It is
  command execution, not judgment.
- Reviewing tests (red evidence, weak or brittle assertions, mocks that hide
  behaviour): `sonnet`.
- Implementation, refactors and doc rewrites: the model the work needs, not
  `haiku` by default.

## 3. Prompt checklist

Every agent prompt includes:

- The ticket and spec paths, and the files to read first.
- Constraints: scope, files it must not touch, the branch it works on.
- Strict TDD: run each new test and see it fail for the right reason before
  implementing, and report that red output in the hand-back.
- Run the full suite and report the real output (`mayo-flow-run-tests`).
- Never chain `git commit` after an unchecked step; use && and check exit codes.
- Use Edit, not `sed -i` (BSD sed fails silently on macOS).
- Verify `git status` shows the ticket status edit before committing.

## 4. Parallel agents

- One worktree per parallel agent, branching from the current feature branch
  and merging back into it.
- Put new code in new files and wire it in with one-line edits to shared
  files, to avoid conflicts. The tickets' `Touches` fields and Parallel plan
  show where tickets collide.

## 5. Merging back

- Merge in wave order.
- Resolve additive conflicts by keeping both sides.
- Re-run the suite after each merge.
- Remove merged worktrees and branches.

## 6. Verify every hand-back

A hand-back is a claim, not a fact. The coordinator re-runs the suite and
checks the diff. Reject and redo any hand-back that admits missing red, even
in a footnote.
