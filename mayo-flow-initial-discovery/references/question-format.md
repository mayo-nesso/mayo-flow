# Question format

One entry per question, in the catalogue file, under a tier heading.

```
### ID · short title
- **Scenario:** what happens in real life that raises this (a concrete case, not an abstract worry)
- **Options:** (a) … (b) … (c) …   each with its trade-off
- **Recommendation:** one option and why, in one or two sentences
- **Blocks:** the phase or work item that cannot be finished without an answer · **Status:** open
```

When answered, change the status and add one line:

```
- **Blocks:** Phase 2.3 · **Status:** answered (YYYY-MM-DD)
- **Answer:** the decision in plain words, the user's own reasoning if they gave it, cautions if any, and where it was written (PLAN decision N, phase doc item, spec name)
```

Other statuses: `deferred to <phase> (date)` (a control point, with what must
be checked then) and `open` with a `- **Note:**` line when a recommendation
was not accepted.

## IDs

A short area prefix and a number: `SESS-4`, `PRIV-1`, `MON-2`. Never renumber.
A question added later gets the next number in its area.

## A good entry

```
### SESS-1 · Rejected input
- **Scenario:** the classifier rejects the text or is unsure. The status list has no value for that. Is it stored? Does it count against quota?
- **Options:** (a) do not store; count only in a rate limiter. (b) store it with status `rejected`, outside the plan quota but inside an abuse counter. (c) count it fully.
- **Recommendation:** (b). It gives data to measure the classifier and does not punish an honest parent who rephrases. Needs a migration.
- **Blocks:** Phase 2.3; client "reformulate" state · **Status:** open
```

## Checks before adding an entry

- The scenario is a real situation a user or operator can be in.
- The options are real choices, not one good option and two straw men.
- The recommendation is one option, not "it depends".
- `Blocks` names a phase. If nothing is blocked, it is tier C.
- Any fact in it has a link in the research file, or is written as unverified.

## The index

Start the file with an index table by tier so a reader sees the whole set at a
glance, and state that numbers are proposals.
