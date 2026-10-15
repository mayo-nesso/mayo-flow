---
name: mayo-flow-grill
description: Relentless one-question-at-a-time interview to sharpen a plan or design before anything is written. Resolves every open branch of decisions, with a recommended answer each time. Called by mayo-flow-feature-start before the spec, or use standalone on any plan. Use when the user says "grill me", wants a plan stress-tested, or a feature is still vague.
version: 1.2.0
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
- Invoke `mayo-flow-grill-prep` with the plan and a prep file path:
  `<feature-folder>/grill-prep.md` when called by `mayo-flow-feature-start`,
  otherwise a file in the session scratchpad. An isolated Opus run reads the
  code and docs and writes the decision tree, ordered by dependency, with a
  recommended answer and reason for each decision. Read that file; it is the
  tree you interview from.

## 2. Interview

Rules, no exceptions:

1. **One question at a time.** Never a list of questions.
2. **Every question carries your recommended answer** and a one-line reason.
   The user can answer "yes" to accept it.
3. **Do not ask what you can find out.** If the code, the docs or a quick
   lookup answers it, answer it yourself and say so in one line.
4. **Walk the tree top-down.** Finish a branch before opening the next. When
   an answer changes the tree, say what it opened or closed.
5. **Push back.** If an answer contradicts an earlier one or the codebase,
   say so and ask which one wins.
6. **No implementation** until the user and you agree the tree is resolved.

Stop when every branch has an answer, or the user stops you.

## 3. Hand back the result

End with a short list: each decision, the chosen answer, and the reason. Mark
anything left open and why.

- When called by `mayo-flow-feature-start`, write this list to the `grill.md`
  path it gave you (in English). `mayo-flow-spec` reads that file in an
  isolated run with no access to the conversation, so every decision, answer
  and reason must be in it, plus the open items. Then delete the
  `grill-prep.md` working file so it does not end up in the commit.
- When used standalone, show the list in chat and offer to save it in the
  project's docs folder (written in English, like all repo-facing text).
