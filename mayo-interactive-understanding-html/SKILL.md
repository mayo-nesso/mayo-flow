---
name: mayo-interactive-understanding-html
description: Create a rich, self-contained, dark-mode interactive HTML page that teaches the user to understand whatever they just asked about — a problem, a piece of code, a feature, a bug, a concept, a design decision, or a code change already investigated by the explain-diff-html skill. Content sections unlock in order, each gated by a 3-question quiz. Use when the user wants to genuinely understand and retain something, not just get an explanation in chat.
version: 1.4.0
---

# Mayo Interactive Understanding HTML

Produce a single long-form HTML page that teaches a reader whatever they just asked to understand. The trigger is the user's question or request in the moment — "explain X", "why does Y happen", "how does Z work" — a bug, a feature, a design decision, a piece of code. Investigate the real thing being asked about before writing a word: the page should make sense to a beginner while still giving an experienced engineer a concise, correct path to the answer.

**If the target is a diff, branch, or pull request**, run the `explain-diff-html` skill first — it owns the diff-specific investigation (resolving the real base ref, comparing before/after behavior, ordering the narrative by concept). That skill's workflow ends by handing its narrative to this one; pick up from step 4 below using that narrative instead of redoing the investigation.

Write with the clarity and flow of Martin Kleppmann — engaging, classic style, smooth transitions, one idea building on the previous one.

## Language

Write the page in **English by default**. Switch to another language only when the user explicitly asks for the page in that language — writing to you in another language, on its own, is not that request. When another language is requested, translate everything: prose, section names (the "Intuition"/"Glossary" convention below is a pattern, not fixed text — call them whatever those words are in that language), diagram labels, quiz text, and the page chrome via `render.py`'s optional `ui` spec object (see Workflow step 5) — the button and overlay text default to English and won't translate themselves.

**Use plain, simple English.** Short sentences, one idea each, active voice, common everyday words over long or formal ones ("use" not "utilize", "help" not "facilitate", "show" not "demonstrate", "sharp" or "severe" not "acute") — keep the vocabulary plain and the precision intact. A sentence that needs a second read because of its vocabulary, not its idea, is a sentence to rewrite. Simple wording is not "dumbing down" the content — the technical substance and precision stay full strength; only the words carrying it get plainer. This applies in whatever language is actually chosen, not English alone.

## Workflow

1. Identify exactly what needs explaining and its scope. Use the current conversation, codebase, or user-supplied material as the source of truth. If the target is ambiguous, infer the most likely intent and state the assumption on the page.
2. Investigate for real: read the relevant code, trace the actual flow, check tests/docs. Prefer what the source actually does over what seems plausible. Distinguish observed fact from reasonable interpretation. While you're in there, note the codebase's own names for things — class/interface/method names, DTO fields, doc headings — this is the vocabulary the page has to speak (see Vocabulary section below).
3. Build a narrative before writing anything:
   - the smallest useful mental model — the "first principles" a reader needs to hold in their head for everything else to make sense;
   - how the pieces fit together, built up one section at a time, each section depending only on what came before it;
   - the specific case the user actually asked about, arrived at as a consequence of the model, not as a separate fact;
   - edge cases, trade-offs, and a closing mental rule the reader can reuse next time.
4. Split that narrative into sections that **can each stand a 3-question quiz on their own** — a reader who understood only that section should be able to pass its quiz. This is what drives section boundaries, not an arbitrary word count.
5. If a Diagrams section applies (see Page shape), build it with `mayo-interactive-diagramer` and insert it after the Glossary in the spec before you render.
5. **Use `render.py` (included alongside this skill) instead of hand-writing the HTML page.** Write a small JSON content spec (title, subtitle, slug, an optional `favicon` emoji loosely related to the topic — defaults to 🧠 if omitted — sections each with prose/diagram HTML and an embedded 3-question quiz, and an optional `ui` object only when the page is in a language other than English) and run:
   ```
   python ~/.claude/skills/mayo-interactive-understanding-html/render.py <spec.json>
   ```
   Run `python render.py --help` for the exact JSON schema if you haven't used it recently. It handles all CSS, JavaScript, gating logic, progress bar, TOC, and quiz rendering — you only write content and quiz questions. Keep `render.py` in place (`~/.claude/skills/mayo-interactive-understanding-html/render.py`) so every invocation finds it.
6. **Read the script's stderr output.** It warns when a quiz's correct option is suspiciously longer than its distractors (see Quiz quality rules below). Rewrite the spec and re-run until there are no warnings — do not hand off a page with unresolved warnings.
7. Validate before handing off: confirm the file exists, is a complete HTML document, has no external asset dependencies, and that clicking through a section's quiz actually unlocks the next one. Open it in a browser if practical.
8. Unless the user says otherwise, save to `~/sDeveloper/Docs/YYYY-MM-DD-<short-descriptive-name>.html` (this is `render.py`'s default output path — no `-o` flag needed unless the user wants a different location).

## Page shape

- The page is **always dark mode** — the renderer's CSS is permanently dark, there's no light-mode toggle to wire up.
- The page is **always mobile-friendly** — `render.py` handles this: viewport meta, a responsive `<640px` breakpoint (smaller hero/type, repositioned progress badge, stacked flow diagrams with a rotated arrow, larger tap targets), and automatic horizontal-scroll wrapping for any `<table>` you write. You don't need to do anything extra for mobile — just avoid fixed pixel widths in ad-hoc inline styles and keep diagrams built from `.flow`/`.box` (which already reflow) rather than one-off layouts.
- Sections appear **in order, gated**: section *N+1* stays locked (greyed heading, content hidden behind a "answer the previous quiz" overlay) until the reader passes section *N*'s quiz. This forces content → quiz → content → quiz, never a wall of content followed by a wall of questions at the end.
- The first section is a good place for an "Intuition" / first-principles section (mark it with `"num": "★"` instead of a number) — the 3-5 ideas that everything else is a consequence of. Not mandatory if the topic doesn't need it.
- **Right after Intuition (or first, if there's no Intuition), always add a "Glossary" section, no `"quiz"`.** It's the reference card for every ubiquitous-language term the page is about to use (see Vocabulary below) — a reader can jump back to it mid-page to check a term instead of re-reading a whole section. Mandatory, unlike Intuition.
- **For a diff, branch or PR (or any topic with real files and types), add a "Diagrams" section right after the Glossary, no `"quiz"`.** It holds three tabs: File explorer, Sequence, UML classes. Build it with the `mayo-interactive-diagramer` skill (`diagramer.py spec.json --insert-into <page-spec.json> --after glossary`) and then run `render.py`. It is a reference block like the Glossary: it never gates the next section. Skip it for a pure concept with no files or classes.
- **After the Diagrams section, add a "Map" section** — the high-level layout of the system's components, screens, or modules and what talks to what, so the reader holds the whole shape before any per-section deep dive. See "Map section" below. Mandatory whenever the topic has more than one moving part (an app, a service, a multi-file feature); skip only for a single narrow concept, bug, or function with nothing to map.
- A closing/summary section may omit `"quiz"` entirely — it renders unlocked-once-reached with no gate, and doesn't block anything after it (use this for a final "mental rule" wrap-up). Glossary is the same mechanism used mid-page rather than at the end.
- Every gated section needs **exactly 3 questions**: one easy, one medium, one hard (`render.py` enforces the count of 3; the difficulty labels are free text — write them in whatever language the page is in). Getting one wrong doesn't move on; it shakes the card and invites another try, without revealing which option was right. Getting it right locks that question in and shows the explanation. The section's continue button (its text comes from `ui.continue_btn`, "Continue →" by default) enables only once all 3 are solved.

## Writing section content (the JSON spec)

Section `html` fields are raw HTML you write directly — the renderer inserts them as-is. Use:

- `<pre><code>...</code></pre>` for code blocks (already styled, whitespace-preserving) — escape code-derived text for HTML. A block with `//` comments is rendered as a code and comment grid (put `data-file="Path/File.cs"` on the `<pre>` to show the file name in the header) (see `explain-diff-html`, Code excerpts). The page is up to 1180px wide so code needs less scrolling. `line-add` and `line-del` spans are blocks: never put a newline right after their closing `</span>`, or an empty line shows in the block (`render.py` strips it, but do not rely on that). When a block is walking a diff, wrap a whole added line in `<span class="line-add">` and a whole removed/meaningfully-changed line in `<span class="line-del">` (unchanged lines stay bare) — see `explain-diff-html`'s "Code excerpts" section for the full rule; this mostly comes up when that skill has handed you a diff-derived narrative.
- `.diagram` / `.flow` / `.box` / `.box.fail` for flow diagrams; `.principios` / `.principio` (with `.pnum`) for a numbered list of first-principle cards, for the "Intuition" section.
- `.glossary` / `.gterm` (`.gterm.invented` variant) for the mandatory Glossary section — see its own section below.
- `.timeline` for a draggable-slider timeline with one or more parallel lanes — see its own section below. Reach for it whenever the topic *is* a sequence over time: a schedule, a state machine, a lifecycle, or several things happening concurrently (parallel branches, an await racing another, a fork that later joins).
- `.callout` / `.callout.warn` / `.callout.ok` for definitions, invariants, and edge cases.
- plain `<table>` for comparisons.

Use a small, reusable set of these patterns rather than one-off ornamental markup — reuse the same one or two diagram families throughout a page. Never use ASCII diagrams. Label arrows and include example values whenever a diagram describes data or state moving. Add a caption or accessible text so the explanation doesn't depend on visual inspection alone.

## Glossary section (mandatory, right after Intuition)

Write it as a flat list of terms, real code vocabulary first, any invented teaching term last and tagged:

```html
<div class="glossary">
  <div class="gterm">
    <div class="gname">IMissionStageUnlock</div>
    <div class="gdef">Interface a module implements to answer, per stage, whether its objectives can be claimed. Lives in Modules/IMissionStageUnlock.cs.</div>
  </div>
  <div class="gterm invented">
    <div class="gname">"vote" <span class="gtag">not from the code</span></div>
    <div class="gdef">The name this page uses for the bool that IsStageUnlocked returns. There is no Vote class or Vote() method in the code.</div>
  </div>
</div>
```

- One `.gterm` per term, `.gname` for the identifier (rendered in monospace), `.gdef` for a one-line definition — same register as a quiz `explain`, not a full paragraph.
- Add `invented` to a term's class, and a `<span class="gtag">not from the code</span>` inside its `.gname`, for any term you coin yourself instead of reusing the source's own name (see Vocabulary below). This is the canonical place to declare an invented term — an inline `.callout` at first use is optional extra emphasis, not a substitute.
- Order: real code terms first (in the order they'll be used), invented terms last, so the list itself signals "these two are not the same kind of thing."

## Map section (after Diagrams)

Purpose: before the reader goes deep into any one section, they should be able to see the whole system at a glance — every major screen, component, module, or service in play, and which ones actually talk to which. This is what lets a reader later place a per-section deep dive ("the queue") back into the bigger picture ("the queue sits between the camera screen and the parsing isolation point") instead of holding each section as an island.

- **A table is usually the right shape**, not a `.flow` diagram — real systems are a graph, not a pipeline, and forcing a many-to-many map into a linear flow of boxes hides more than it shows. Use a plain `<table>` with columns like Component/Screen, Talks to / depends on, and Role — one row per real building block, both internal (screens, modules, services) and external (a third-party API, a device capability, a database).
- **Still use a `.diagram`/`.flow` for the one headline pipeline**, if the system has a clear critical path (e.g. "photo → queue → API → review screen") — the table gives the full graph, the diagram gives the one path worth memorizing first. Skip the diagram if there's no single dominant path.
- Use the source's own names for every component (see Vocabulary below) — a screen's actual file/route name, a module's actual folder, a service's actual class or binding name — not a paraphrase invented for the page.
- This section carries a normal 3-question quiz, unlike Glossary — it teaches real relationships (what calls what, what depends on what), not just term lookup, so a reader should be tested on it before moving on.

## Timeline / slider interactivity

Use this when the content is a sequence over time or several concurrent sequences — a schedule, a state machine, a lifecycle, a set of parallel tasks that fork and later join, an `await` racing another. One shared slider drives every lane at once, so lining up nodes from different lanes at the same horizontal position is how the page shows two things happening at the same instant.

```html
<div class="timeline">
  <div class="timeline-grid">
    <div class="timeline-now"><div class="timeline-now-line"></div></div>
    <div class="timeline-link" data-from="n-taskrun" data-to="n-starts"></div>

    <div class="timeline-lane-label">Main thread</div>
    <div class="timeline-lane-row">
      <div class="timeline-lane-track"></div>
      <div class="timeline-node" id="n-taskrun" data-pos="0">
        <div class="timeline-dot"></div>
        <div class="timeline-label">Task.Run<small>fires the task</small></div>
      </div>
      <div class="timeline-node" data-pos="4">
        <div class="timeline-dot"></div>
        <div class="timeline-label">await returns<small>keeps going</small></div>
      </div>
    </div>

    <div class="timeline-lane-label">Background task</div>
    <div class="timeline-lane-row">
      <div class="timeline-lane-track"></div>
      <div class="timeline-node" id="n-starts" data-pos="1">
        <div class="timeline-dot"></div>
        <div class="timeline-label">starts<small>on another thread</small></div>
      </div>
      <div class="timeline-node" data-pos="4">
        <div class="timeline-dot"></div>
        <div class="timeline-label">finishes<small>completes the Task</small></div>
      </div>
    </div>

    <div class="timeline-ruler">
      <div class="timeline-fill"></div>
      <input type="range" class="timeline-slider" min="0" max="6" step="any" value="0">
    </div>
  </div>

  <div class="timeline-controls">
    <button class="btn secondary timeline-prev" type="button">◀ Before</button>
    <div class="timeline-readout" data-template="t = {value}">t = 0</div>
    <button class="btn secondary timeline-next" type="button">After ▶</button>
  </div>
</div>
```

How it behaves (all wired up automatically by `render.py`'s JS, nothing extra to write):

- **The slider is continuous** (`step="any"`), so dragging is smooth, not a snap between states. Give it whatever `min`/`max` fit the real values you're placing nodes at (day numbers, milliseconds, an ordinal step count).
- **`data-pos` is the only thing you position by hand**, and it should be the real value from the domain (a day number, a stage index), not a percentage — the renderer computes each node's `left` from it. Nodes across every lane share one pooled, deduplicated list of positions.
- **A node already reached is fully lit; the very next node ahead glows in proportion to how close the slider already is** — exactly halfway between two positions renders at half intensity, so a reader watches an upcoming state "warm up" before it's reached rather than snapping on. Nodes further out stay neutral. This needs no authoring — it falls out of each node's `data-pos` automatically.
- **Prev/Next jump to the next real node position, pooled across every lane** — not a fixed step — since a fixed step means nothing once the slider is continuous. Both buttons are optional; add them for a stepper feel alongside the drag, or omit them and let the slider carry the whole interaction.
- **One or more `.timeline-lane-row` rows** share the exact same horizontal axis (a CSS grid keeps the ruler and every lane column-aligned), so two nodes at the same `data-pos` in different lanes already visually line up without any extra markup — a cheap way to show a join.
- **Add an empty `<div class="timeline-lane-track"></div>` as the first child of a `.timeline-lane-row`** to connect that lane's own nodes with a line (skip it for a lane with a single node — there's nothing to connect). It only spans from that lane's first node to its last, never past either end, and it's colored with the same per-node intensity as a gradient — already fully lit up to whichever node was last reached, fading through whatever's glowing next, neutral beyond that. No color or width to author by hand.
- **For a connector that crosses lanes** (a fork, an explicit join, one lane waiting on another's node) — give both `.timeline-node`s an `id`, then drop `<div class="timeline-link" data-from="idA" data-to="idB"></div>` anywhere inside `.timeline-grid`. It's a pure placeholder: `render.py`'s JS reads the two ids, removes the placeholder, and draws a straight line between the nodes' actual positions (so it works at any angle, not just straight down), colored the same way as a lane track — each end takes on that node's own current intensity. Position is measured in pixels after layout (so it also re-measures on resize); only needed when the fork/join happens across genuinely different lanes and you want it drawn rather than left to alignment. For anything more elaborate than a straight connector (a curved or branching path), hand-draw a small inline SVG per the `artifact-diagramming` skill instead of extending this component.
- **`data-template` on `.timeline-readout`** is the display string, with `{value}` substituted by the current position rounded to one decimal. Match its unit to what the axis actually measures ("Day {value}", "t = {value}", "{value} ms").
- **`.timeline-ruler`'s position in the markup is its position on the page** — it has no fixed row, so wherever you place it in the grid is where it renders. Put it last (right above `.timeline-controls`, as above) so the slider sits directly next to Prev/Next; move it first if you'd rather it read as a header ruler above the lanes instead.
- A single-lane timeline is just the one-lane case of this same markup — you don't need a simpler variant for it, just omit the second `.timeline-lane-label` / `.timeline-lane-row` pair.

## Vocabulary — use the code's own words

The reader will meet these concepts again outside the page: in the codebase, in review, in a ticket, in conversation with a teammate who read the same source. If the page's words don't match the code's words, the reader learns a private language that doesn't transfer — nothing to grep for, nothing to recognize in a PR, nothing to say out loud that lands.

- **Default to the exact identifier from the source.** Class, interface, method, and field names; DTO field names; log messages; doc headings. If the code says `IMissionStageUnlock.IsStageUnlocked`, the page says `IsStageUnlocked`, not a paraphrase of it.
- **Never invent a concept and present it as if it were the code's own term.** A gloss like "vote" for a module's boolean answer, or "fold" for an AND-reduction over a list, can be a fine teaching device — but it's your word, not the code's, and the page must not blur that line.
- **When you do introduce your own term, declare it in the Glossary section** (mandatory, see Page shape above): tag it `invented`, say plainly that it is not literal code vocabulary, and say what it maps to and where that thing actually lives in the source. An inline `.callout` at the term's first use in a later section is optional extra emphasis, never a substitute for the Glossary entry. Example shape (adapt the wording, keep the structure): "*This page uses 'vote' for what `IsStageUnlocked` returns. It isn't a code term: there's no `Vote` class or `Vote()` method, it's the bool each module returns, and the fold in `MissionStageUnlockExtensions` combines them with AND.*"
- This applies everywhere text names a concept: prose, diagram labels, table headers, quiz questions and options. A diagram box or a quiz question should carry the code's name for the thing it depicts, not a house term.
- When the codebase already has its own name for something (an ADR, a `Documentation~/*.md`, a comment that names the pattern), reuse that name even if it reads a little clunky. Consistency with what a teammate would actually search for beats a smoother-sounding word you made up.

## Quiz quality rules — read this before writing any question

This is the part users notice when it's done badly, so treat it as core, not decoration.

- **Keep options comparable in length, and vary which one is correct.** The classic tell is the correct answer always being conspicuously longer than the distractors — but always being the shortest, or always landing in the same relative spot (say, always the second-longest), is just as guessable once a reader notices the pattern. Across the quiz set, the correct option should sometimes be the shortest in its question, sometimes the longest, sometimes in between — no consistent relative position. `render.py` checks both the per-question length gap and this cross-quiz variety, and prints a warning for each — fix every warning before handing off.
- Vary which option position is correct per question — `render.py` also shuffles option order at render time, so don't hand-arrange position to "look random," but don't rely only on that either; write options so length/phrasing alone gives nothing away.
- Every distractor must be plausible and tied to a real misconception about the section's content — no joke answers, no "all/none of the above," nothing a reader can eliminate without having understood anything.
- Ask about behavior, causality, or consequence — not a fact that can be copy-matched from a single phrase in the text above it.
- Put the reasoning in `explain` (shown after a correct answer): name both why the right answer is right and, where useful, what misconception the wrong ones represent.
- Nothing in the question or option phrasing should hint at correctness before it's clicked.

## HTML and code-block constraints

- Quiz `question`, `options` and `explain` strings are HTML, the same as `html` fields: `<code>` works in all three. So escape user/code-derived text for HTML in every one of them (`&lt;version&gt;`, not `<version>`). The length check counts only the visible text, not the tags.
- Verify every code block renders with preserved whitespace before delivery.
- Don't claim behavior the inspected source doesn't support.
- The renderer's JS is small and dependency-free — don't add extra inline scripts unless a section genuinely needs interactivity beyond the quiz engine and the `.timeline` component already provided (both are fully wired up by `render.py`; you only ever write their markup).

## Final handoff

Return the exact absolute path to the generated HTML file as a clickable local-file link. Briefly state what was inspected, any assumptions made, and confirm the quiz-balance warnings came back clean.
