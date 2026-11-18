---
name: mayo-flow-spec
description: "Write a feature's spec.md from its grill.md in an isolated Opus run. Called only by mayo-flow-feature-start after the grill; never asks the user."
version: 1.0.2
context: fork
model: opus
background: false
---

# Write the feature spec

This runs as an isolated subagent: it does not see the conversation and
cannot ask the user questions. Everything it needs is in the files.

Argument: path to the feature folder (`.../YYYY_MM_DD_<slug>/`). It contains
`grill.md` (the decisions already made with the user). If `grill.md` is
missing, the grill was skipped for a small feature: work from the feature
description in the argument alone.

## 1. Read

- `grill.md`: every decision, its answer and its reason. These are settled.
  Do not reopen or contradict them. If one looks wrong against the code,
  keep it and flag it under the spec's Decisions as an open concern.
- The code the feature touches, and a project spec template if the features
  folder already has one (`docs/structure.md`, other specs). Follow an
  established template instead of the default below.

## 2. Write `<feature-folder>/spec.md`

If no established template exists in this repo, use:

```markdown
# <Feature title>

## Goal
<what this feature does and why, 2-4 sentences>

## Decisions
<For each real fork-in-the-road this feature requires a choice on — not
mechanical detail like "what does this loop do" — cover all four, so the
decision could be defended on a whiteboard later:
  1. The decision, stated plainly (what was actually chosen).
  2. Why it's the right call given this feature's actual constraints (real
     scale, real deadline/dependency pressure, what the codebase already
     does) — not a generic "it's a common pattern". If no real constraint
     justifies it, say so plainly instead of inventing one.
  3. The alternatives, with pros and cons — at least one genuine option that
     could actually have been picked, not a straw man. Use a small markdown
     table (columns: option, pros, cons, chosen/rejected) once there are 2+
     real alternatives.
  4. Where it fails — edge cases, load limits, or unexpected-usage behavior
     this decision does not handle (a caller retrying too fast, a boundary
     value, two callers racing, a dependency being down). An honest "not
     handled, here's the blast radius" beats silence.
Skip this structure for a decision with no real alternative — one bullet
with the reasoning is enough there.>

## Architecture
<only if the feature has non-trivial data flow or new components. Prefer a
Mermaid diagram (renders natively in GitHub and most doc viewers) once
there's an actual flow to draw, e.g. a fenced ```mermaid flowchart LR``` block
— a short bullet list is still fine for a single new component with nothing
interesting to show flowing between parts.>

## Implementation plan
1. <step> — TDD: write the failing test first, then implement, then green.
2. ...

## Test seams
<where the tests attach: the highest seam possible, ideally one (a public
function, endpoint or screen action), so tests survive refactors. Tests are
written only at these seams; name each and why it was chosen.>

## Test cases
<the concrete test files/cases that will exist at those seams, one bullet per case>
```

Keep sentences short and concrete (prefer plain, simple sentences over dense
compound ones) — this is a spec other people and future agents will read
quickly, not prose to admire. Write in English.

## 3. Report

Reply with the path written and a few lines: the number of decisions, and any
open concern flagged. Do not commit; the caller does that.
