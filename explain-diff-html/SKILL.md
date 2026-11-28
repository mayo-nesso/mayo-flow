---
name: explain-diff-html
description: Investigate a code change, diff, branch, or pull request and shape it into the narrative and content a reader needs — then hand off to the mayo-interactive-understanding-html skill, which renders it as a gated, quiz-based interactive HTML page. Use when the user wants to understand the background, intuition, implementation, or trade-offs of a software change.
---

# Explain Diff HTML

This skill covers only the **investigation and narrative-building** half of explaining a code change. Rendering is not this skill's job — that lives entirely in `mayo-interactive-understanding-html`, which already owns the gated-section quiz engine, the Glossary, the timeline component, and the quiz-balance checker. Duplicating that machinery here would mean fixing the same quiz bugs in two places.

Write with the clarity and flow of Martin Kleppmann — engaging, classic style, with smooth transitions between sections.

## When to use this vs. calling mayo-interactive-understanding-html directly

The user's request names a diff, branch, commit range, or PR (not a general question) → start here for the diff-specific investigation, then call `mayo-interactive-understanding-html` to render. Skip straight to `mayo-interactive-understanding-html` when the target is a general concept or question that never needs "what changed" framing.

## Reading mode: pre-read (default) or post-read

Pick one mode before you write. Default is **pre-read**.

- **Pre-read (default):** the reader has not opened the PR yet. Write so they know what to expect in the diff. Use future tense in the prose and in quiz questions ("You open the diff and see..."). Say which diff lines are noise and can be skipped. End with a short "When you review, check" list in the closing section.
- **Pre-read opening: two boxes, logic and noise.** Near the end of the Intuition section, add two separate callouts. Count the real files first, with the file list of the PR. Do not guess the numbers.
  - `<div class="callout ok"><strong>Real logic: N files in M packages. Read these.</strong><br>One line that names where the logic is.</div>`
  - `<div class="callout"><strong>Noise: K files. Skip these.</strong><br>Breakdown, for example: 11 test files, 5 docs, 5 changesets and 1 <code>.meta</code> file.</div>`
  - Logic plus noise must equal the total of changed files. Tests that prove the fix are noise for the first read, but say so if a test is worth reading.
- **Post-read:** the reader already saw the diff, or the PR is merged. Use past tense and refer to the diff as already seen ("The PR shows...").

Use post-read only when the user asks for it, or says the PR is already merged or reviewed. Say the mode on the page in one line at the top of the first section.

## Workflow

1. Identify the change and its scope: the current checkout's diff, a specific diff, a branch, a commit range, or a PR (fetch its metadata and diff). If the target is ambiguous, infer the most likely change from available context and state the assumption on the page.
2. Explore the surrounding system: callers, data models, tests, config, and documentation. Compare the *before* against the *after* at the behavior level, not just line-by-line.
   - **Resolve the real base ref before trusting "before".** A PR's base may not be the repo's main development branch — a stacked PR's base is another feature branch. Check the PR's actual `baseRefOid`/`baseRefName` and diff against that, not against whatever the local checkout happens to have. A local checkout can also simply be behind the remote; fetch before concluding a symbol doesn't exist yet.
   - **Read up the stack for callers.** In a stacked PR, new types often have no callers in this layer. Before you judge a risk on such a type, read the next layers (the stack table in the PR body) for its call sites and constructors.
3. Build a narrative before writing anything:
   - what problem or constraint motivated the change;
   - how the old system behaved;
   - the smallest useful mental model of the new behavior;
   - how the implementation realizes that model, grouped by concept or dependency order, not file order;
   - edge cases, trade-offs, and observable consequences.
   - Prefer checked-in tests and docs over speculation about intent — a test name or docstring the diff touches is stronger evidence than guessing what the author meant.
4. Map that narrative onto `mayo-interactive-understanding-html`'s section shape:
   - **Intuition** (optional, but usually earns its place for a diff): the before/after mental model in miniature, with toy inputs and outputs, ideally showing old and new behavior side by side.
   - **Glossary** (mandatory): every identifier from the diff the page is about to use — interfaces, methods, DTO fields, config flags, doc headings — plus any teaching term you invent yourself, tagged `invented` per that skill's rules.
   - **Diagrams** (right after the Glossary, no quiz): the real file paths and status, the runtime order, and the changed types with members. Hand this to `mayo-interactive-diagramer` to render the 3 tabs (File explorer, Sequence, UML classes).
   - One or more narrative sections walking the actual code change, ordered by execution or dependency flow. Each section must be self-contained enough to carry its own 3-question quiz — a reader who understood only that section should be able to pass it. File and line references are good supporting detail inside the prose, but the section boundaries themselves come from concepts, not files.
   - A closing section (no quiz) covering trade-offs and edge cases, ending in a reusable mental rule.
5. Hand off to `mayo-interactive-understanding-html` and follow its workflow from its own step 5 onward — its `render.py`, the quiz-balance stderr warnings, validation, and default save path (`~/sDeveloper/Docs/YYYY-MM-DD-<slug>.html`). Do not hand-write HTML or use a separate renderer for a diff/PR/branch target; the two skills share one rendering engine.

## Code excerpts

**Comments become a column.** `render.py` turns every `<pre><code>` block that has `//` comments into a two-column grid: code on the left, the comment of each line on the right. Write comments as before. An inline `// comment` stays with its line. A comment-only line attaches to the next code line. A comment that starts with `...` (an elision like `// ... unsubscribe`) stays in the code column. Blocks without `//` comments stay a plain `<pre>`. Keep each comment to one short line, because it sits in a narrow cell.

**Name the file in the header.** Write `<pre data-file="Scopes/ScopeToken.cs"><code>` and the left header reads `Code Scopes/ScopeToken.cs`. Use the short repo-relative path that a reader can search for. Add `data-file` to every excerpt that comes from one file. Without it the header is just `Code`.

Every `<pre><code>` block placed in a narrative section must carry inline comments on its non-trivial lines — a line whose purpose isn't obvious from the identifier names alone (a loop's stopping condition, an off-by-one, why a check happens in this order, what a magic number means, why something is ignored). Skip comments on lines that are already self-explanatory (a simple assignment, a straightforward property access) — one line, same comment style as the source language, placed inline or directly above. If the source itself already has a comment explaining the line, reuse it rather than writing a new one. The goal is that a reader can follow the excerpt without jumping back to prose for every line.

**Color lines by what the PR did to them.** When an excerpt is specifically illustrating the diff (not just showing finished post-PR code for its own sake), wrap each *whole line* — indentation included, comment included — in a span so the reader sees at a glance what's new versus what's gone, the same signal a diff view gives:

- A line the PR **added**: `<span class="line-add">    var stageCount = schema.Stages.Count;</span>`
- A line the PR **removed**, or a meaningfully different old line shown for contrast: `<span class="line-del">    var schedule = new MissionStagedDailyUnlockSchedule(...);</span>`
- An unchanged line stays a plain line, no span.

Only mark lines that carry real diff signal — an entire excerpt that's 90% green because you pasted the whole new method is noise; trim the excerpt to the lines that actually changed plus the minimum surrounding context needed to read them, and reserve red for a removed line whose disappearance is itself worth noticing (not every reformatted line in the real diff). Never mark a line both add and del — a changed line is a del of the old text and an add of the new one, shown as two lines, not one span with both classes.

**No line break right after a diff span.** `line-add` and `line-del` are block elements, so they already end the line. Do not write `\n` after the closing `</span>`. A `\n` there shows as an empty line in the page. Write the next code line directly after `</span>`. The `\n` before the opening `<span>` is fine. `render.py` now removes that `\n` for you, so a gap cannot reach the page. Still write the spec the right way.

## Reviewer's take (PR, branch or diff only)

When the target is a PR, branch or diff, every narrative section gets a `"review"` block in the page spec. The block is your view as a PR evaluator on the code of that section. `render.py` shows it as a "Reviewer's take" card after the section content and before the quiz. Do not add it to the Glossary or the Diagrams sections.

```json
"review": {
  "verdict": "good|ok|bad",
  "summary": "One or two sentences. Say what you would do: approve, approve with comments, or block.",
  "items": [ {"tag": "good|warn|bad|nit|question", "area": "Security", "text": "..."} ]
}
```

- Cover the areas that apply: design, logic bugs, edge cases, security, performance, tests, API and versioning, style. Skip an area with nothing to say.
- Say what is good, not only what is wrong. Use `good` items for real strengths.
- `bad` = must change before merge. `warn` = should change. `nit` = small, optional. `question` = you could not verify it from the diff.
- Ground every item in code you read. Name the identifier. If you only read the diff, say so. Never invent a bug. Mark a guess as `question`.
- Before you write a possible crash or bug, trace the value to every place that creates it. Follow the type, not a similar name. Use a grep for the constructor or factory, also in later stack layers. Write a `question` only when that trace is not possible.
- **Investigate first. Do not hand your work to the reader.** A review item that says "check whether X exists" or "I did not check Y" is a failure when you could check it. Run the grep, open the file, trace the call. Only then write the item. Write "I did not check" only for what you cannot reach: a runtime behavior, a service, a repo you do not have, a production payload.
- **Read the real code of every step in a claim.** A claim about timing, order or a race needs the real body of each call in the chain. Open `OpenAsync`, the event raiser, the factory. Do not reason from the order of lines. Example of the failure: a "missed event during the open animation" warning, when `OpenAsync` returned `UniTask.CompletedTask` and nothing could run in between.
- **Doubt what you cannot see.** Name the part of the system outside your view: a type in another repo, a runtime result, data on a server, a device. Do not state a cause or a consequence there as a fact. Say "from the doc comment" or "I did not read `X`". Put it in a `question` item with the exact thing you could not see.
- **Check the claim a second time before you publish a `warn` or `bad`.** Ask: what would make this false? Look for that. If you find it, drop the item or lower its tag.
- When the user asks you to check something, check it in the code first. If your earlier claim was wrong, say so plainly, fix the page, and fix the cause in this skill.
- The closing review keeps each item's tag. Do not change a `question` to `warn` or "must check" without new evidence.
- The closing section also gets a `review` with the overall verdict, a "must fix" list, and what you did not check (for example "I did not run the code or read the tests").

## Final handoff

Return the exact absolute path to the generated HTML file as a clickable local-file link. Briefly state what was inspected (including which ref was treated as "before"), any assumptions made, and confirm the quiz-balance warnings came back clean.
