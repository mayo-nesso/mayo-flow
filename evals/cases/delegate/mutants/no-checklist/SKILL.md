---
name: mayo-flow-delegate
description: "Delegate implementation, tests, refactors, reviews and doc rewrites to fresh agents while the main thread coordinates. Use while working a ticket set, or when the user says delegate, parallel or agents. Not for answering questions or one-line edits."
version: 1.2.3
---

# Delegate the work, coordinate the result

## 1. Roles

The main thread coordinates: decisions, questions to the user, merges,
conflict resolution and short verifications. Agents do the work:
implementation, tests, refactors, reviews and doc rewrites. Each agent starts
fresh, so give it specific context; it does not see this conversation.

## 2. Models

Pass `model` explicitly in every Agent call. A skill's frontmatter `model:` only
sets the model when that skill itself runs; it does not carry over to an Agent call.

- Running and reporting the suite (`mayo-flow-run-tests`): `haiku`. It is
  command execution, not judgment.
- Reviewing tests (red evidence, weak or brittle assertions, mocks that hide
  behaviour): `sonnet`.
- Implementation, refactors and doc rewrites: pick by how critical the work
  is, not `haiku` by default.
  - `opus` only for critical work: security, authentication and authorization,
    row-level security and tenant isolation, database and schema design
    (tables, constraints, triggers, definer functions, migrations), payments,
    anything destructive or hard to reverse, and cross-cutting design choices
    that later tickets build on.
  - `sonnet` for everything else that is mechanical or well bounded: small
    refactors, UI wiring and copy, seed and preview data, test fixes and
    locators, docs, config.
  - When a ticket mixes both, use `opus` only if the critical part is a real
    part of the diff; otherwise split it or use `sonnet`.
- Before the first Agent call, name in one line of visible text (not only in
  thinking) the model and the reason for every agent you plan, including the
  review and suite-run agents, so the user can overrule them. Name a model
  added later before the Agent call that first uses it. A project memory or
  the user's instruction wins over these defaults.

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
