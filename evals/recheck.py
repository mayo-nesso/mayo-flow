"""Re-evaluate the stored reply checks of a suite from its local traces.

A result row keeps the check outcomes computed when its trial ran. When a
check in evals/checks.py is fixed, `recheck` recomputes the checks that need
only the trace (TRACE_CHECKS: the final reply and result status) from the
stored trace file and rewrites those outcomes, and `passed`, in place. Checks
that read the fixture repo cannot be recomputed (the fixture is gone) and keep
their stored value. No model call is made.
"""
import json
import os
import tempfile
from pathlib import Path

from evals.checks import CHECKS, TRACE_CHECKS
from evals.trace import parse_trace


def _expected(case, suite):
    """The check names a stored row of this case should hold."""
    names = case.get("checks", suite.get("checks"))
    return {*names, *(f["id"] for f in case.get("facts", []))}


def _recomputed(row, case, suite, evals_dir):
    """(new checks dict, None) or (None, why the row is skipped)."""
    if set(row["checks"]) != _expected(case, suite):
        return None, "check set differs from the suite's current one"
    trace_path = Path(evals_dir).parent / row["trace_path"]
    if not trace_path.is_file():
        return None, "no trace"
    trace = parse_trace(trace_path)
    for key in ("agent_roles", "prompt_rules"):  # delegate checks
        if key in case:
            trace[key] = case[key]
    return {name: bool(CHECKS[name](None, trace)) if name in TRACE_CHECKS
            else ok for name, ok in row["checks"].items()}, None


def recheck(evals_dir, name, today):
    """Rewrite stale reply checks of results/<name>.jsonl. Returns
    {"rechecked": n, "changed": [(trace_path, check, old, new)],
    "skipped": [(trace_path, reason)]}."""
    evals_dir = Path(evals_dir)
    results = evals_dir / "results" / f"{name}.jsonl"
    suite = json.loads((evals_dir / "cases" / name / "suite.json")
                       .read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in suite["cases"]}
    summary = {"rechecked": 0, "changed": [], "skipped": []}
    lines = []
    for line in results.read_text(encoding="utf-8").splitlines():
        row = json.loads(line) if line.strip() else None
        if row is None or "kind" in row:  # blank or judge line
            lines.append(line)
            continue
        if row["case_id"] not in cases:
            summary["skipped"].append(
                (row["trace_path"], "case no longer in suite"))
            lines.append(line)
            continue
        try:
            new, why = _recomputed(row, cases[row["case_id"]], suite,
                                   evals_dir)
        except Exception as e:  # noqa: BLE001  (cut or unreadable trace)
            new, why = None, f"trace unreadable: {e!r}"
        if why:
            summary["skipped"].append((row["trace_path"], why))
            lines.append(line)
            continue
        summary["rechecked"] += 1
        diff = [(row["trace_path"], n, row["checks"][n], new[n])
                for n in new if new[n] != row["checks"][n]]
        if not diff:
            lines.append(line)
            continue
        summary["changed"] += diff
        row["checks"] = new
        row["passed"] = bool(new) and all(new.values()) and row["error"] is None
        row["rechecked"] = today
        lines.append(json.dumps(row, sort_keys=True))
    fd, tmp = tempfile.mkstemp(dir=results.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("".join(l + "\n" for l in lines))
    os.replace(tmp, results)
    return summary


def render_summary(summary):
    out = [f"rechecked {summary['rechecked']} rows, "
           f"{len(summary['changed'])} outcomes changed, "
           f"{len(summary['skipped'])} rows skipped"]
    out += [f"changed {t}: {n}: {old} -> {new}"
            for t, n, old, new in summary["changed"]]
    out += [f"skipped {t}: {why}" for t, why in summary["skipped"]]
    return "\n".join(out)
