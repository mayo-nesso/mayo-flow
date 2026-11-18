---
name: mayo-flow-grill
description: Interview the user in numbered rounds, with a recommended answer per question, to resolve every open decision of a plan before the spec. Called by mayo-flow-feature-start; also use when the user says "grill me". Not for researching what already exists (use mayo-flow-initial-discovery).
version: 1.2.1
model: opus
---

# Grill a plan

Adapted from Matt Pocock's `grill-me`/`grilling`. The goal is to leave no
undecided branch in the plan before anyone writes a spec or code.

Argument: the plan, feature or design to grill. If none was given, ask for a
one-line statement of it.

For project-wide plans and phases, `mayo-flow-initial-discovery` is the bigger
tool. This skill is the lightweight one for a single feature or decision.

## 1. Prepare

- Model tip, once, before the first question: the `model: opus` setting of
  this skill only covers the turn it starts in, and the grill takes many
  turns. If you are not running as an Opus model, tell the user in one or two
  lines to run `/model opus` (or `/model opusplan` and Shift+Tab into plan
  mode) before answering, because the grill is where Opus helps most. Do not
  repeat the tip, and go on with the first question either way.
- Invoke `mayo-flow-grill-prep` with the plan and a prep file path in the
  session scratchpad (never inside the repo, so it cannot be committed by
  mistake). An isolated Opus run reads the code and docs and writes the
  decision tree grouped by dependency level, with a recommended answer and
  reason for each decision. Read that file; it is the tree you interview from.

## 2. Interview

Rules, no exceptions:

1. **Rounds, not single questions.** Each round asks every question that is
   unblocked now (all of one dependency level), numbered Q1..Qn. Answers
   unblock the next round. Keep a round to what the user can answer in one go.
2. **Every question carries your recommended answer** and a one-line reason,
   worded so that "yes" accepts it. The user can reply "yes to all" or only
   list the numbers they disagree with.
3. **Facts are your job, not the user's.** If the code, the docs or a quick
   lookup answers it, find it yourself (a subagent if it is a big search) and
   say so in one line.
4. **Walk the tree level by level.** When answers change the tree, say what
   they opened or closed.
5. **Push back.** If an answer contradicts an earlier one or the codebase,
   say so and ask which one wins.
6. **No implementation** until the user and you agree the tree is resolved.
7. **Vocabulary and decisions.** When the user uses a fuzzy or overloaded
   term, pin it down and, if the project has `docs/GLOSSARY.md`, add the
   term there at once (or create the file; one line per term, no
   implementation detail). Offer an ADR in `docs/adr/` only when all three
   hold: hard to reverse, surprising without context, a real trade-off.
8. **Prototype detour.** If a question is really "how will this behave or
   feel", offer a throwaway prototype on a `prototype/<name>` branch (never
   merged) to answer it before the spec. Only on the user's yes.

Stop when no question is left and the user confirms, or the user stops you.

## 3. Hand back the result

End with a short list: each decision, the chosen answer, and the reason. Mark
anything left open and why.

- When called by `mayo-flow-feature-start`, write this list to the `grill.md`
  path it gave you (in English). `mayo-flow-spec` reads that file in an
  isolated run with no access to the conversation, so every decision, answer
  and reason must be in it, plus the open items, and the ADR paths if any.
- When used standalone, show the list in chat and offer to save it in the
  project's docs folder (written in English, like all repo-facing text).
