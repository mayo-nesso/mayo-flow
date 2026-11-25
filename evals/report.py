"""Text tables over a results JSONL: pass/fail per column, mean cost and
tokens per case and condition, and, when trials were judged, the mean judge
score per case and condition. The columns follow the conditions present:
rows with casual or floor (resume suites) compare skill with casual and show
floor, plus phase 2 cost and each check per condition; otherwise skill is
compared with baseline. End-to-end rows (hidden tests or observations) also
get a table of pass rate, cost, time, questions and observations."""
import json
import re
from pathlib import Path

from evals.judge import decisions_hash, mean

MIN_TRIALS = 2
CLAUSE_CHECK = re.compile(r"^(s\d|n_)\w*")
SENSITIVITY_TRIALS = 3  # trials of one check needed in each group
SENSITIVITY_DROP = 2 / 3  # control rate minus mutant rate for "sensitive"


def _conditions(trials):
    """(columns, the condition skill is compared with)."""
    if any(_condition(t) in ("casual", "floor") for t in trials):
        return ("skill", "casual", "floor"), "casual"
    return ("skill", "baseline"), "baseline"


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
    return col if _condition(r) == "skill" else f"{col} {_condition(r)}"


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
    """One block per judge model: mean judge score per case and condition,
    counting only the latest rubric and each trial's latest error-free
    judgement of that model under it."""
    by_trace = {r["trace_path"]: r for r in trials}
    good = sorted((j for j in judgements
                   if j["error"] is None and j["trace_path"] in by_trace),
                  key=lambda j: j["ts"])
    if not good:
        return []
    rubric = good[-1]["rubric_hash"]
    lines = []
    for model in sorted({j["judge_model"] for j in good
                         if j["rubric_hash"] == rubric}):
        per_trial = {j["trace_path"]: mean(j["judge"]) for j in good
                     if j["rubric_hash"] == rubric
                     and j["judge_model"] == model}
        scores = {}
        for trace, m in per_trial.items():
            t = by_trace[trace]
            scores.setdefault((t["case_id"], _condition(t)), []).append(m)
        conds, other = _conditions(trials)
        rows = [["case", *conds, f"skill - {other}"]]
        for case in sorted({c for c, _ in scores}):
            vals = [scores.get((case, cond), []) for cond in conds]
            cells = [f"{sum(v) / len(v):.2f} n={len(v)}" if v else "-"
                     for v in vals]
            a, b = vals[0], vals[conds.index(other)]
            if min(len(a), len(b)) < MIN_TRIALS:
                diff = "not enough trials"
            else:
                diff = "%+.2f" % (sum(a) / len(a) - sum(b) / len(b))
            rows.append([case, *cells, diff])
        lines += ([""] if lines else []) + [
            f"judge mean 1-5 (rubric {rubric[:7]}, model {model})",
            *_align(rows)]
    return lines


def _mean(values):
    values = [v for v in values if v is not None]
    return (sum(values) / len(values), len(values)) if values else (None, 0)


def _delta(label, a, b, fmt):
    if b:
        return f"{label} {fmt % (a - b)} ({(a - b) / b * 100:+.1f}%)"
    return f"{label} {fmt % (a - b)}"


def _cost_table(title, trials, numbers):
    """Mean tokens, cost and turns per case and condition, and skill's delta
    vs the compared condition. `numbers(trial)` -> (tokens dict, cost, turns),
    or None when the trial has no such numbers."""
    conds, other = _conditions(trials)
    groups = {}
    for t in trials:
        n = numbers(t)
        if n is not None:
            groups.setdefault((t["case_id"], _condition(t)), []).append(n)
    if not any(c is not None or tok for ns in groups.values()
               for tok, c, _ in ns):
        return []
    rows = [["case", *conds, f"skill - {other}"]]
    for case in sorted({c for c, _ in groups}):
        means = {}
        for cond in conds:
            ns = groups.get((case, cond), [])
            means[cond] = (_mean([(tok or {}).get("total") for tok, _, _ in ns]),
                           _mean([c for _, c, _ in ns]),
                           _mean([tr for _, _, tr in ns]), len(ns))
        cells = []
        for cond in conds:
            (tok, _), (cost, _), (turns, _), n = means[cond]
            cells.append("-" if not n else ", ".join([
                "- tok" if tok is None else f"{tok:.0f} tok",
                "$-" if cost is None else f"${cost:.2f}",
                "- turns" if turns is None else f"{turns:.1f} turns",
                f"n={n}"]))
        (ta, nta), (ca, nca), _, _ = means["skill"]
        (tb, ntb), (cb, ncb), _, _ = means[other]
        diffs = []
        if min(nta, ntb) >= MIN_TRIALS:
            diffs.append(_delta("tokens", ta, tb, "%+.0f"))
        if min(nca, ncb) >= MIN_TRIALS:
            diffs.append(_delta("cost", ca, cb, "%+.2f"))
        rows.append([case, *cells, ", ".join(diffs) or "not enough trials"])
    return [title, *_align(rows)]


def _totals(t):
    return t.get("tokens"), t.get("cost_usd"), t.get("num_turns")


def _phase2(t):
    p = t.get("phase2")
    return None if p is None else (p.get("tokens"), p.get("cost_usd"),
                                   p.get("num_turns"))


def _checks_table(trials):
    """Each check of a two-phase suite: passed/trials per condition."""
    conds, _ = _conditions(trials)
    counts = {}
    for t in trials:
        for name, ok in (t.get("checks") or {}).items():
            p, n = counts.get((t["case_id"], name, _condition(t)), (0, 0))
            counts[(t["case_id"], name, _condition(t))] = (p + bool(ok), n + 1)
    keys = sorted({(c, name) for c, name, _ in counts})
    if not keys:
        return []
    rows = [["case", "check", *conds]]
    for case, name in keys:
        rows.append([case, name, *[
            "%d/%d" % counts[(case, name, cond)]
            if (case, name, cond) in counts else "-" for cond in conds]])
    return ["checks passed per condition", *_align(rows)]


def _hidden(t):
    """(passed, run) over the hidden tests of one trial."""
    hidden = [ok for name, ok in (t.get("checks") or {}).items()
              if name.startswith("hidden:")]
    return sum(map(bool, hidden)), len(hidden)


def _share(trials, key):
    """Phase 1's share of the total `key`, over trials that had a phase 1."""
    with_p1 = [t for t in trials if t.get("phase1")]
    total = sum(t.get(key) or 0 for t in with_p1)
    p1 = sum(t["phase1"].get(key) or 0 for t in with_p1)
    return f"{p1 / total:.0%}" if total else "-"


def _fmt(mean, fmt):
    return "-" if mean[0] is None else fmt % mean[0]


def _e2e_table(trials):
    """Per case and condition: hidden-test pass rate (tests, not trials),
    means of cost, tokens, wall time, denials and questions, phase 1's share
    of cost and time, and how many trials had each boolean observation.
    Errored trials (non-null `error`) are left out of all of those and shown
    as a count next to n."""
    conds, _ = _conditions(trials)
    rows = [["case", "condition", "n", "tests", "cost", "tokens", "wall",
             "p1 cost", "p1 time", "questions", "denials", "observed"]]
    for case in sorted({t["case_id"] for t in trials}):
        for cond in conds:
            ts = [t for t in trials
                  if t["case_id"] == case and _condition(t) == cond]
            if not ts:
                continue
            errored = sum(t.get("error") is not None for t in ts)
            ts = [t for t in ts if t.get("error") is None]
            passed = sum(_hidden(t)[0] for t in ts)
            run = sum(_hidden(t)[1] for t in ts)
            seen = {}
            for t in ts:
                for name, v in (t.get("observed") or {}).items():
                    if type(v) is bool:
                        p, n = seen.get(name, (0, 0))
                        seen[name] = (p + v, n + 1)
            rows.append([
                case, cond,
                str(len(ts)) + (f" (+{errored} errored)" if errored else ""),
                f"{passed}/{run}",
                _fmt(_mean([t.get("cost_usd") for t in ts]), "$%.2f"),
                _fmt(_mean([(t.get("tokens") or {}).get("total")
                            for t in ts]), "%.0f"),
                _fmt(_mean([t["duration_ms"] / 1000 if t.get("duration_ms")
                            is not None else None for t in ts]), "%.0fs"),
                _share(ts, "cost_usd"), _share(ts, "duration_ms"),
                _fmt(_mean([(t.get("observed") or {}).get("questions")
                            for t in ts]), "%.1f"),
                _fmt(_mean([t.get("permission_denials") for t in ts]), "%.1f"),
                ", ".join(f"{k} {p}/{n}" for k, (p, n) in sorted(seen.items()))
                or "-"])
    return ["end-to-end per case and condition", *_align(rows)]


def _decisions_table(trials, decisions, labelled):
    """Per decision and condition. Dictated: trials where every named hidden
    test passed / trials. Open: trials the judge labelled explicit / trials
    labelled, plus those not labelled yet. `labelled` is the decisions
    lines."""
    conds, _ = _conditions(trials)
    latest = {}  # (trace, hash) -> labels of the latest error-free line
    for r in sorted((r for r in labelled if r["error"] is None),
                    key=lambda r: r["ts"]):
        latest[(r["trace_path"], r["decisions_hash"])] = r["decisions"]
    rows = [["case", "decision", *conds]]
    for case in sorted({t["case_id"] for t in trials}):
        current = decisions_hash(decisions.get(case, []))
        for d in decisions.get(case, []):
            cells = []
            for cond in conds:
                ts = [t for t in trials
                      if t["case_id"] == case and _condition(t) == cond]
                if not ts:
                    cells.append("-")
                elif d.get("open"):
                    labels = [latest[(t["trace_path"], current)][d["id"]]
                              ["label"] for t in ts
                              if (t["trace_path"], current) in latest]
                    cell = f"{labels.count('explicit')}/{len(labels)} explicit"
                    if len(labels) < len(ts):
                        cell += f" ({len(ts) - len(labels)} unlabelled)"
                    cells.append(cell)
                else:
                    right = sum(all((t.get("checks") or {}).get(name)
                                    for name in d["tests"]) for t in ts)
                    cells.append(f"{right}/{len(ts)}")
            rows.append([case, d["id"], *cells])
    if len(rows) == 1:
        return []
    return ["decisions: dictated = trials where all its tests passed, open = "
            "trials labelled explicit", *_align(rows)]


def _group(r):
    """The column of a row in the clause tables: its mutant, else its
    condition."""
    return r.get("mutant") or _condition(r)


def _clause_counts(records):
    """{(check, group): (passed, trials)}. A row counts only for the checks
    it stores, so a case counts only for the checks it lists."""
    counts = {}
    for r in records:
        for name, ok in (r.get("checks") or {}).items():
            if CLAUSE_CHECK.match(name):
                p, n = counts.get((name, _group(r)), (0, 0))
                counts[(name, _group(r))] = (p + bool(ok), n + 1)
    return counts


def _clause_table(records):
    """One row per s* or n_* check: passed/trials per condition, for the
    control and for each mutant."""
    counts = _clause_counts(records)
    if not counts:
        return []
    present = {g for _, g in counts}
    cols = [c for c in ("skill", "baseline", "control") if c in present]
    cols += sorted(present - {"skill", "baseline", "control"})
    rows = [["check", *cols]]
    for name in sorted({n for n, _ in counts}):
        rows.append([name, *["%d/%d" % counts[(name, g)]
                             if (name, g) in counts else "-" for g in cols]])
    lines = ["Checks by clause (passed/trials)", *_align(rows)]
    if any(n < MIN_TRIALS for _, n in counts.values()):
        lines.append(f"cells with fewer than {MIN_TRIALS} trials: "
                     "not enough trials")
    return lines


def _verdict(control, mutant):
    """Sensitivity of a check to its mutant. Each argument is
    (passed, trials)."""
    if min(control[1], mutant[1]) < SENSITIVITY_TRIALS:
        return "not enough trials"
    drop = control[0] / control[1] - mutant[0] / mutant[1]
    return "sensitive" if drop >= SENSITIVITY_DROP - 1e-9 else "insensitive"


def _sensitivity_table(records, mutants):
    """Per mutant and target check: control and mutant passes, and the
    verdict."""
    counts = _clause_counts(records)
    rows = [["mutant", "check", "control", "mutant rows", "verdict"]]
    for name in sorted(mutants):
        if not any(g == name for _, g in counts):
            continue
        for check in mutants[name]["targets"]:
            control = counts.get((check, "control"), (0, 0))
            mutant = counts.get((check, name), (0, 0))
            rows.append([name, check, *["%d/%d" % c if c[1] else "-"
                                        for c in (control, mutant)],
                         _verdict(control, mutant)])
    if len(rows) == 1:
        return []
    return ["Mutant sensitivity", *_align(rows)]


def _isolated(r):
    """Plain-condition rows from before block_skills_hook.py could read the
    skills dir, so their baseline may have leaked the skill."""
    return _condition(r) == "skill" or r.get("isolation") == "skills-blocked"


def render_report(records, decisions=None, mutants=None):
    """One block per suite_hash; all but the most recently run are flagged.
    `decisions` ({case id: the case's "decisions"}) adds the decisions table
    to end-to-end suites. `mutants` (the suite's mutants.json) adds the
    mutant sensitivity table. Rows with a `mutant` field appear only in the
    clause and sensitivity tables."""
    judgements = [r for r in records if r.get("kind") == "judge"]
    labelled = [r for r in records if r.get("kind") == "decisions"]
    records = [r for r in records if "kind" not in r]  # trials, not judgements
    excluded = sum(not _isolated(r) for r in records)
    records = [r for r in records if _isolated(r)]
    if not records:
        return "no results"
    footnote = [] if not excluded else [
        "", f"{excluded} plain-condition trials excluded: not isolated "
            "(no skills-blocked field)"]
    groups = {}
    for r in records:
        groups.setdefault(r["suite_hash"], []).append(r)
    latest = max(groups, key=lambda s: max(r["ts"] for r in groups[s]))
    blocks = []
    for suite, all_recs in groups.items():
        recs = [r for r in all_recs if "mutant" not in r]
        title = f"suite {suite[:7]}"
        if len(groups) > 1 and suite != latest:
            title += " (older suite, not comparable with the others)"
        tables = [_cost_table("cost per trial, mean (both phases for "
                              "two-phase suites)", recs, _totals),
                  _judge_table(recs, judgements)]
        e2e = any("hidden_hash" in r or "observed" in r for r in recs)
        if any("phase2" in r for r in recs) and not e2e:
            tables[1:1] = [
                _cost_table("phase 2 (resume) cost per trial, mean", recs,
                            _phase2),
                _checks_table(recs)]
        if e2e:
            tables.insert(1, _e2e_table(recs))
            if decisions:
                tables.insert(2, _decisions_table(recs, decisions, labelled))
        clauses = _clause_table(all_recs)
        if clauses:
            tables.append(clauses)
            if mutants and len(recs) < len(all_recs):
                tables.append(_sensitivity_table(all_recs, mutants))
        lines = [title, *_table(recs)]
        for t in tables:
            if t:
                lines += ["", *t]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n".join(footnote)
