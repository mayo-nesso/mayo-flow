---
name: mayo-interactive-diagramer
description: Build a 3-tab diagram block for a code change (PR, branch, diff) or a set of related types - File explorer, Sequence diagram, UML class diagram - as a self-contained dark HTML fragment. Use it standalone, or let mayo-interactive-understanding-html insert it right after the Glossary. Use when the user wants to see where a change lives (files, folders, classes) and how it runs.
---

# Mayo Interactive Diagramer

One script, `diagramer.py` (next to this file), turns a small JSON spec into a block with three tabs:

1. **File explorer** - the changed files as a folder tree. One line per file.
2. **Sequence** - who calls whom, with the file of each lifeline.
3. **UML classes** - classes, members and the file of each class.

The order is "where" (files), then "when" (runtime order), then "what" (types).

Tabs use radio inputs and CSS. The Sequence and UML diagrams sit in a pan and zoom frame: drag to move, `+`, `-` and fit buttons at the bottom right, Ctrl or Cmd + wheel to zoom, and a full screen button (Esc closes it). This needs a small inline script that the block carries with it. It can sit inside any page.

## When to use it

- The target is a diff, branch or PR that touches 3 or more files or types. Use it.
- The target is one concept with no real files or classes. Skip it.
- Drop a tab when it has nothing to say. Leave out its key in the spec. A pure-data change often needs no sequence tab.

## Workflow

1. Do the investigation first (for a PR: `explain-diff-html`). You need the real file paths, status (A, M, D), line counts, type and member names, and the runtime order.
2. Write the spec JSON. Run `python diagramer.py --help` for the schema. `example.json` in this folder is a full example.
3. Build the block:
   - Standalone page: `python diagramer.py spec.json --standalone -o ~/sDeveloper/Docs/pr<N>-diagrams.html`
   - Inside an understanding page: `python diagramer.py spec.json --insert-into page-spec.json --after glossary`. Then run `render.py` as usual.
4. Open the result in a browser (headless Chrome screenshot is fine) and check all three tabs. Click or set `checked` on each tab input.

## Rules for each tab

**File explorer**
- Use full repo paths. The script merges single-child folders.
- Keep the tab simple. No chips, bars or long text. Put a short note in `note`. It shows only on hover.
- Hide generated files (for example Unity `.meta`) and say so in `files_note`.

**Sequence**
- One scene per scenario. Two or three scenes at most.
- Lifelines are classes. Put the file name under each class name.
- Style a message: `add` (green, added by the change), `del` (red dashed, the call before the change), `dash` (white dashed, a hop whose call site is not in the diff), `keep` (white).
- Never draw a call you did not see in the code. Mark it `dash` and say so in the label.

**UML classes**
- Place boxes on a grid with `col` and `row`. The script sizes the boxes and routes the arrows.
- Arrows are routed around the boxes, so an arrow never crosses a box. The script prints `diagramer WARNING` on stderr if an arrow or a label still overlaps a box or another label. Fix every warning (move a box to another `col` or `row`, or shorten a label) and look at the picture before you hand off.
- Crossing arrows. The script reviews the routes and tries to leave no two arrows crossing or sharing a line.
  - It routes the arrows in about 14 different orders and keeps the order with the fewest crossings, then the fewest bends and the shortest lines. This is automatic.
  - If crossings remain, it prints `diagramer NOTE: arrows A->B and C->D cross`. A shared line prints `diagramer WARNING`.
  - It then tries to move each box that is part of a crossing to another `col` or `row`. It prints at most 3 lines like `diagramer HINT: move HapticClipValidator to col 4, row 4: crossings 1 -> 0`. A hint only appears when the move removes a crossing.
  - A hint never breaks the rules below: the box stays in its band, off other boxes, and every parent stays above its child.
  - Apply a hint to the spec when it looks good, then run the script again. Hints do not change the spec by themselves. This search takes a few seconds, and only runs when crossings remain.
  - A few crossings can stay. If no hint helps, accept them. Do not break the row rules to remove one.
- Row means abstraction. The more abstract a type is, the higher it sits (lower `row`). The more concrete, the lower.
  - A parent always sits on a row above its child. This holds for `inh` (extends) and `real` (implements) edges.
  - So an interface goes above the class that implements it. A base class goes above its subclasses.
  - A root type with no parent in the diagram is on row 0. Any other type is at least one row below its lowest parent. Use the smallest row that keeps the layers in order (see Layers below).
  - Example: `IPlayable` on row 0, abstract `RuledShape : IPlayable` on row 1, `SequenceShape : RuledShape` on row 2 or lower.
  - Types with no inheritance link have a free row. Put them next to the types they work with.
- Layers (optional): use them when the diagram has 8 or more types and the types fall into clear groups. A typical order is abstract contracts, concrete types, services. Do not use them for a small diagram.
  - Add `"bands": [{"label": "Abstract", "rows": [0, 1]}, ...]` to the `uml` object. Each band covers rows `first` to `last`. It draws a dashed frame with a label at the top right.
  - Bands need whole rows, so plan the rows first. Put all abstract types (interfaces and abstract classes) in the top rows. Put concrete types in the next rows. Put services (types that only use the others) in the last rows.
  - Rows inside a layer still follow the parent-above-child rule. A band can hold more than one row.
  - Bands do not overlap. Give each band its own rows.
  - `dep` and `assoc` edges (uses, creates, holds) do not change the rule. They can point in any direction.
  - The script prints `diagramer WARNING` when a parent is not above its child. Fix it like the other warnings.
- Keep the same column for types that call each other often. Short arrows read best.
- Put a child in the same column as its parent when you can. The extends and implements arrows then run straight up.
- Base types. Each box shows one line under its name: `: Base, IInterface, IOther`.
  - The script builds it from the `inh` and `real` edges. The extends targets come first, then the implements targets. You do not write them twice.
  - For a base that is not a box in the diagram, add `"bases": ["ScriptableObject"]` to the box. Own `bases` come first in the line. Example: `: ScriptableObject, IPlayable`.
  - A box with no base shows no line.
- Members start with a mark: `+` added, `~` changed, `-` removed, space unchanged. Show only members that matter. Add one grey line for context if it helps.
- Mark types from outside the diff as `ext`. Do not invent their members.
- Use the code's own names. Follow the Vocabulary rules of `mayo-interactive-understanding-html`.

## Output limits

- Do not claim behavior the diff does not show. Say "call site not in diff" instead.
- Keep text short. Sentence-style text goes in the page prose, not in the diagram.
- Write labels in English unless the user asks for another language.
