"""Text table over a results JSONL."""
import json
from pathlib import Path


def load_results(path):
    path = Path(path)
    if not path.is_file():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _column(r):
    return f"{r['skill_version']} {r['skill_hash'][:7]} {r['model']}"


def _table(records):
    cols = sorted({_column(r) for r in records})
    cases = sorted({r["case_id"] for r in records})
    cells = {}
    for r in records:
        p, t = cells.get((r["case_id"], _column(r)), (0, 0))
        cells[(r["case_id"], _column(r))] = (p + bool(r["passed"]), t + 1)
    rows = [["case", *cols]]
    for c in cases:
        rows.append([c] + [("%d/%d" % cells[(c, col)]) if (c, col) in cells
                           else "-" for col in cols])
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return [("  ".join(v.ljust(w) for v, w in zip(row, widths))).rstrip()
            for row in rows]


def render_report(records):
    """One table per suite_hash; all but the most recently run are flagged."""
    records = [r for r in records if "kind" not in r]  # trials, not judgements
    if not records:
        return "no results"
    groups = {}
    for r in records:
        groups.setdefault(r["suite_hash"], []).append(r)
    latest = max(groups, key=lambda s: max(r["ts"] for r in groups[s]))
    blocks = []
    for suite, recs in groups.items():
        title = f"suite {suite[:7]}"
        if len(groups) > 1 and suite != latest:
            title += " (older suite, not comparable with the others)"
        blocks.append("\n".join([title, *_table(recs)]))
    return "\n\n".join(blocks)
