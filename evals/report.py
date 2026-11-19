"""Text tables over a results JSONL: pass/fail per column and, when trials
were judged, the mean judge score per case for skill vs baseline."""
import json
from pathlib import Path

from evals.judge import mean

CONDITIONS = ("skill", "baseline")


def load_results(path):
    path = Path(path)
    if not path.is_file():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _condition(r):
    return r.get("condition", "skill")  # lines before --baseline existed


def _column(r):
    col = f"{r['skill_version']} {r['skill_hash'][:7]} {r['model']}"
    return col + " baseline" if _condition(r) == "baseline" else col


def _align(rows):
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return [("  ".join(v.ljust(w) for v, w in zip(row, widths))).rstrip()
            for row in rows]


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
    return _align(rows)


def _judge_table(trials, judgements):
    """Mean judge score per case and condition, counting only the latest
    rubric and each trial's latest error-free judgement under it."""
    by_trace = {r["trace_path"]: r for r in trials}
    good = sorted((j for j in judgements
                   if j["error"] is None and j["trace_path"] in by_trace),
                  key=lambda j: j["ts"])
    if not good:
        return []
    rubric = good[-1]["rubric_hash"]
    per_trial = {j["trace_path"]: mean(j["judge"]) for j in good
                 if j["rubric_hash"] == rubric}
    scores = {}
    for trace, m in per_trial.items():
        t = by_trace[trace]
        scores.setdefault((t["case_id"], _condition(t)), []).append(m)
    rows = [["case", *CONDITIONS, "skill - baseline"]]
    for case in sorted({c for c, _ in scores}):
        vals = [scores.get((case, cond), []) for cond in CONDITIONS]
        cells = [f"{sum(v) / len(v):.2f} n={len(v)}" if v else "-"
                 for v in vals]
        if min(len(v) for v in vals) < 2:
            diff = "not enough trials"
        else:
            diff = "%+.2f" % (sum(vals[0]) / len(vals[0])
                              - sum(vals[1]) / len(vals[1]))
        rows.append([case, *cells, diff])
    return [f"judge mean 1-5 (rubric {rubric[:7]})", *_align(rows)]


def render_report(records):
    """One block per suite_hash; all but the most recently run are flagged."""
    judgements = [r for r in records if r.get("kind") == "judge"]
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
        judged = _judge_table(recs, judgements)
        blocks.append("\n".join([title, *_table(recs),
                                 *([""] + judged if judged else [])]))
    return "\n\n".join(blocks)
