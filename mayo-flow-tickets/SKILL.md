---
name: mayo-flow-tickets
description: Break a feature spec into tracer-bullet tickets - thin vertical slices with blocking dependencies - as markdown files inside the feature's docs folder. Called by mayo-flow-feature-start after the spec for medium/large features. Use when the user wants to split a spec or plan into ordered work items.
version: 1.1.0
context: fork
model: opus
background: false
---

# Break a spec into tickets

Adapted from Matt Pocock's `to-tickets`. Tickets live as markdown files in the
repo, next to the spec. No external tracker.

Argument: path to the feature folder (or its `spec.md`). If none was given,
use the feature folder matching the current `feature/<slug>` branch.

## 1. When to use it

Medium and large features only: more than about three implementation steps,
or steps that depend on each other. For a small feature the spec's
"Implementation plan" is enough. Say so and stop.

## 2. Gather context

Read `spec.md` fully. Explore the code the feature touches, so slices match
the real architecture and vocabulary. If a small prefactor makes the change
easier, make it the first ticket: make the change easy, then make the easy
change.

## 3. Draft vertical slices

- Each ticket cuts a complete path through every layer it needs and can be
  demonstrated on its own. Not "the database", then "the API", then "the UI".
- Each ticket fits in one working session / one context window.
- Exception: a large mechanical change across the codebase. Sequence it as
  expand, migrate in batches, contract.
- Describe end-to-end behavior and acceptance criteria. Do not name files or
  paste code, unless a snippet captures a decision more precisely than prose.
- Record blockers: which tickets must be `done` first.

## 4. Write the files

This runs as an isolated subagent: it does not see the conversation and
cannot ask the user questions. It writes a draft; the caller reviews it with
the user and edits the files until granularity and dependencies are approved.

In `<feature-folder>/tickets/`, one file per ticket, written in dependency
order, named `NN_<slug>.md`:

```markdown
# NN. <Title>

**Status:** todo
**Blocked by:** none | NN, NN
**Touches:** <shared wiring files>

## Behavior
<what works end to end when this ticket is done, 2-4 sentences>

## Acceptance criteria
- <observable, testable criterion>

## Tests
- <the failing tests to write first>
- Red must be observed: run each new test and see it fail for the right
  reason (missing behavior, not a typo or missing import) before
  implementing, and show that output.
```

## 5. Report

Reply with the numbered list: title, blocked-by, and what can be demonstrated
when done. Then add a **Parallel plan** block, derived from the spec and code
only (this skill cannot ask questions):

- Waves: groups of tickets whose blockers are all in earlier waves, so each
  wave can run together.
- Overlaps: the shared files (from each ticket's `Touches`) that more than one
  ticket in the same wave touches.
- Rule: colliding tickets are serialized, or told to put new code in new files
  and wire it in with a one-line edit to the shared file.

Do not commit; the caller commits the `tickets/` folder alone after
the user approves, as `docs: add tickets for <slug>` (or the repo's own
documented convention).

## 6. Working the tickets

Pick a ticket whose blockers are all `done`, run the TDD loop, and set
`**Status:** done` in the same commit as its code.
`mayo-flow-branch-finish` checks that every ticket is `done` before it
archives the feature.

Update the status with the Edit tool, not `sed -i` (BSD sed fails silently on
macOS), and check that `git status` shows the ticket file modified before
committing. To hand tickets to agents, see `mayo-flow-delegate`.
