---
name: mayo-flow-delegate
description: "Delegate implementation, tests, refactors, reviews and doc rewrites to fresh agents while the main thread coordinates. Use while working a ticket set, or when the user says delegate, parallel or agents. Not for answering questions or one-line edits."
version: 1.2.4
---

# Delegate the work, coordinate the result

## 1. Roles

The main thread coordinates: decisions, questions to the user, merges,
conflict resolution and short verifications. Agents do the work:
implementation, tests, refactors, reviews and doc rewrites. Each agent starts
fresh, so give it specific context; it does not see this conversation.

## 2. Models

Use `haiku` for every agent: implementation, reviews and suite runs. Pass
`model: haiku` explicitly in every Agent call.

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
