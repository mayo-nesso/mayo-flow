# Timeline / slider interactivity

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

- **The slider is continuous** (`step="any"`). Give it whatever `min`/`max` fit the real values you're placing nodes at (day numbers, milliseconds, an ordinal step count).
- **`data-pos` is the only thing you position by hand**, and it should be the real value from the domain (a day number, a stage index), not a percentage — the renderer computes each node's `left` from it. Nodes across every lane share one pooled, deduplicated list of positions.
- **A node already reached is fully lit; the very next node ahead glows in proportion to how close the slider already is** — exactly halfway between two positions renders at half intensity. Nodes further out stay neutral. This falls out of each node's `data-pos` automatically.
- **Prev/Next jump to the next real node position, pooled across every lane** — not a fixed step. Both buttons are optional; add them for a stepper feel alongside the drag, or omit them and let the slider carry the whole interaction.
- **One or more `.timeline-lane-row` rows** share the exact same horizontal axis (a CSS grid keeps the ruler and every lane column-aligned), so two nodes at the same `data-pos` in different lanes already visually line up without any extra markup.
- **Add an empty `<div class="timeline-lane-track"></div>` as the first child of a `.timeline-lane-row`** to connect that lane's own nodes with a line (skip it for a lane with a single node — there's nothing to connect). It only spans from that lane's first node to its last, never past either end, and it's colored with the same per-node intensity as a gradient — already fully lit up to whichever node was last reached, fading through whatever's glowing next, neutral beyond that. No color or width to author by hand.
- **For a connector that crosses lanes** (a fork, an explicit join, one lane waiting on another's node) — give both `.timeline-node`s an `id`, then drop `<div class="timeline-link" data-from="idA" data-to="idB"></div>` anywhere inside `.timeline-grid`. It's a pure placeholder: `render.py`'s JS reads the two ids, removes the placeholder, and draws a straight line between the nodes' actual positions (so it works at any angle, not just straight down), colored the same way as a lane track — each end takes on that node's own current intensity. Position is measured in pixels after layout (so it also re-measures on resize); only needed when the fork/join happens across genuinely different lanes and you want it drawn rather than left to alignment. For anything more elaborate than a straight connector (a curved or branching path), hand-draw a small inline SVG per the `artifact-diagramming` skill instead of extending this component.
- **`data-template` on `.timeline-readout`** is the display string, with `{value}` substituted by the current position rounded to one decimal. Match its unit to what the axis actually measures ("Day {value}", "t = {value}", "{value} ms").
- **`.timeline-ruler`'s position in the markup is its position on the page** — it has no fixed row, so wherever you place it in the grid is where it renders. Put it last (right above `.timeline-controls`, as above) so the slider sits directly next to Prev/Next; move it first if you'd rather it read as a header ruler above the lanes instead.
- A single-lane timeline is just the one-lane case of this same markup — you don't need a simpler variant for it, just omit the second `.timeline-lane-label` / `.timeline-lane-row` pair.
