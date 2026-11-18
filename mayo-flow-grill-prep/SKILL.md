---
name: mayo-flow-grill-prep
description: "Prepare a grill's decision tree in an isolated Opus run: every open decision ordered by dependency, each with a recommended answer and reason. Called only by mayo-flow-grill; non-interactive."
version: 1.0.2
context: fork
model: opus
background: false
---

# Prepare a grill

This runs as an isolated subagent: it does not see the conversation and
cannot ask the user questions. It does the heavy thinking so the interview
itself can be quick.

Arguments: the plan or feature description, and the path of the file to
write (a scratchpad path, outside the repo).

## 1. Research

Read what already exists that touches the topic: the code it would change,
existing specs, `docs/PLAN.md`, `docs/structure.md`. Anything these answer is
a **settled fact**, not a question.

## 2. Build the decision tree

- List every real open decision: a fork where more than one genuine option
  could be picked and the choice changes what gets built.
- Group them by dependency level. Level 1 has no prerequisites, level 2
  depends only on level 1 answers, and so on. Each level is one interview round.
- For each decision give: the question in one sentence, the realistic
  options with one-line pros and cons, your recommended answer, and the
  reason tied to this codebase's real constraints.
- Look for blind spots too: failure cases, boundary values, concurrency,
  migrations of existing data, and things the description does not mention.

## 3. Write the file

Write it in English to the given path:

```markdown
# Grill prep: <topic>

## Settled facts
- <fact> — <where it was found>

## Decision tree
### Level 1
1. **<question>**
   - Options: <A: pros/cons> | <B: pros/cons>
   - Recommended: <answer> — <reason>
   - Opens: <follow-up decisions (next level) that depend on the answer, or none>
### Level 2
...
```

Do not decide for the user: the recommendations are proposals. Do not write a
spec or code.

## 4. Report

Reply with the path written, the number of decisions, and the top three that
carry the most risk. Do not commit.
