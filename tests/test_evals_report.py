"""Report table tests (stdlib only)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import record  # noqa: E402
from evals.report import load_results, render_report  # noqa: E402


def rec(case="c1", version="1.0.0", h="a" * 40, model="m1", suite="s" * 64,
        passed=True, ts="2026-11-18T10:00:00Z", trace=None, condition=None,
        isolated=True):
    r = {"ts": ts, "case_id": case, "skill_version": version,
         "skill_hash": h, "model": model, "suite_hash": suite,
         "passed": passed, "trace_path": trace}
    if condition:
        r["condition"] = condition
        if condition != "skill" and isolated:
            r["isolation"] = "skills-blocked"
    return r


def jrec(trace, *scores, rubric="r" * 64, ts="2026-11-18T11:00:00Z",
         error=None, model="haiku"):
    judge = None if error else {f"k{i}": {"score": s, "reason": "x"}
                                for i, s in enumerate(scores)}
    return {"kind": "judge", "ts": ts, "trace_path": trace, "judge": judge,
            "judge_model": model, "rubric_hash": rubric, "error": error}


def judge_row(out, case="c1"):
    block = out[out.index("judge"):]
    return next(l for l in block.splitlines() if l.startswith(case))


class ReportTest(unittest.TestCase):
    def test_cells_are_passed_over_total(self):
        out = render_report([rec(), rec(), rec(passed=False)])
        self.assertIn("c1", out)
        self.assertIn("1.0.0 aaaaaaa m1", out)
        self.assertIn("2/3", out)

    def test_columns_and_rows(self):
        out = render_report([
            rec(case="c1", version="1.0.0", h="a" * 40),
            rec(case="c1", version="1.1.0", h="b" * 40, passed=False),
            rec(case="c2", version="1.0.0", h="a" * 40),
        ])
        header = out.splitlines()[1]
        self.assertIn("1.0.0 aaaaaaa m1", header)
        self.assertIn("1.1.0 bbbbbbb m1", header)
        row2 = next(l for l in out.splitlines() if l.startswith("c2"))
        self.assertIn("1/1", row2)
        self.assertIn("-", row2)  # c2 never ran on 1.1.0
        row1 = next(l for l in out.splitlines() if l.startswith("c1"))
        self.assertIn("0/1", row1)

    def test_model_is_a_column(self):
        out = render_report([rec(model="m1"), rec(model="m2")])
        self.assertIn("m1", out)
        self.assertIn("m2", out)

    def test_single_suite_not_flagged(self):
        out = render_report([rec(), rec()])
        self.assertNotIn("not comparable", out)
        self.assertIn("suite sssssss", out)

    def test_different_suite_hashes_shown_separately_and_flagged(self):
        out = render_report([
            rec(suite="1" * 64, ts="2026-11-18T09:00:00Z"),
            rec(suite="2" * 64, ts="2026-11-18T11:00:00Z", passed=False),
        ])
        self.assertIn("suite 1111111", out)
        self.assertIn("suite 2222222", out)
        old = out[out.index("suite 1111111"):out.index("suite 2222222")]
        new = out[out.index("suite 2222222"):]
        self.assertIn("not comparable", old)
        self.assertNotIn("not comparable", new)
        self.assertIn("1/1", old)
        self.assertIn("0/1", new)

    def test_baseline_is_its_own_pass_fail_column(self):
        out = render_report([rec(), rec(passed=False, condition="baseline")])
        header = out.splitlines()[1]
        self.assertIn("1.0.0 aaaaaaa m1 baseline", header)
        row = out.splitlines()[2]
        self.assertIn("1/1", row)
        self.assertIn("0/1", row)

    def test_plain_rows_without_isolation_are_excluded_and_footnoted(self):
        out = render_report([
            rec(trace="a"), rec(condition="baseline", trace="b"),
            rec(condition="baseline", trace="c", isolated=False, passed=False),
            rec(condition="casual", trace="d", isolated=False)])
        self.assertIn("1/1", out.splitlines()[2])
        self.assertIn("2 plain-condition trials excluded: not isolated "
                      "(no skills-blocked field)", out)
        self.assertNotIn("0/1", out)

    def test_no_footnote_when_nothing_is_excluded(self):
        self.assertNotIn("excluded", render_report(
            [rec(), rec(condition="baseline")]))

    def test_no_judge_table_without_judgements(self):
        self.assertNotIn("judge", render_report([rec(trace="t1")]))

    def test_judge_means_skill_vs_baseline_with_n(self):
        out = render_report([
            rec(trace="s1"), rec(trace="s2", condition="skill"),
            rec(trace="b1", condition="baseline"),
            rec(trace="b2", condition="baseline"),
            jrec("s1", 4, 4), jrec("s2", 5, 5), jrec("b1", 3, 2),
            jrec("b2", 3, 4)])
        self.assertIn("rubric rrrrrrr", out)
        row = judge_row(out)
        self.assertIn("4.50 n=2", row)
        self.assertIn("3.00 n=2", row)
        self.assertIn("+1.50", row)
        self.assertNotIn("not enough trials", row)

    def test_under_two_trials_per_condition_says_not_enough(self):
        out = render_report([
            rec(trace="s1"), rec(trace="s2"),
            rec(trace="b1", condition="baseline"),
            jrec("s1", 4), jrec("s2", 5), jrec("b1", 2)])
        row = judge_row(out)
        self.assertIn("4.50 n=2", row)
        self.assertIn("2.00 n=1", row)
        self.assertIn("not enough trials", row)
        self.assertNotIn("+", row)

    def test_missing_condition_shows_a_dash(self):
        out = render_report([rec(trace="s1"), jrec("s1", 4)])
        row = judge_row(out)
        self.assertIn("4.00 n=1", row)
        self.assertIn("-", row)
        self.assertIn("not enough trials", row)

    def test_only_latest_rubric_and_good_judgements_count(self):
        out = render_report([
            rec(trace="s1"), rec(trace="s2"),
            jrec("s1", 1, rubric="o" * 64, ts="2026-11-18T09:00:00Z"),
            jrec("s1", 4), jrec("s2", error="timeout"),
            jrec("s2", 2, ts="2026-11-18T12:00:00Z"),
            jrec("s2", 3, ts="2026-11-18T13:00:00Z")])
        self.assertIn("rubric rrrrrrr", out)
        self.assertIn("3.50 n=2", judge_row(out))

    def test_judge_models_are_never_mixed(self):
        out = render_report([
            rec(trace="s1"), rec(trace="s2"),
            jrec("s1", 4), jrec("s2", 4),
            jrec("s1", 2, model="sonnet"), jrec("s2", 2, model="sonnet"),
            jrec("s2", 5, model="sonnet", ts="2026-11-18T12:00:00Z")])
        haiku, sonnet = ["judge mean" + b for b in
                         out.split("judge mean")[1:]]
        self.assertIn("model haiku", haiku)
        self.assertIn("model sonnet", sonnet)
        self.assertIn("4.00 n=2", judge_row(haiku))
        self.assertIn("3.50 n=2", judge_row(sonnet))

    def test_empty(self):
        self.assertEqual(render_report([]), "no results")

    def test_load_results_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.jsonl"
            record.append_result(p, rec())
            record.append_result(p, rec(case="c2"))
            self.assertEqual([r["case_id"] for r in load_results(p)],
                             ["c1", "c2"])

    def test_load_results_missing_file(self):
        self.assertEqual(load_results(Path("/nonexistent/x.jsonl")), [])


def crec(trace, condition, cost, total, turns=10, checks=None, phase2=None):
    r = rec(trace=trace, condition=condition)
    r.update(cost_usd=cost, num_turns=turns, checks=checks or {"a": True},
             tokens=None if total is None else {"total": total})
    if phase2 is not None:
        r["phase1"] = None
        r["phase2"] = {"cost_usd": phase2[0], "num_turns": phase2[1],
                       "tokens": {"total": phase2[2]}}
    return r


def block(out, title):
    """The lines of the table whose title starts with `title`."""
    lines = out.splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith(title))
    end = next((n for n in range(i + 1, len(lines)) if not lines[n]),
               len(lines))
    return lines[i:end]


class CostReportTest(unittest.TestCase):
    def test_no_cost_table_without_cost_or_tokens(self):
        self.assertNotIn("cost per trial", render_report([rec()]))

    def test_means_per_condition_and_delta_vs_baseline(self):
        out = render_report([
            crec("s1", "skill", 0.5, 1000, turns=10),
            crec("s2", "skill", 0.7, 1200, turns=14),
            crec("b1", "baseline", 0.4, 800), crec("b2", "baseline", 0.4, 800)])
        table = block(out, "cost per trial")
        self.assertIn("skill - baseline", table[1])
        row = table[2]
        self.assertIn("1100 tok, $0.60, 12.0 turns, n=2", row)
        self.assertIn("800 tok, $0.40, 10.0 turns, n=2", row)
        self.assertIn("tokens +300 (+37.5%)", row)
        self.assertIn("cost +0.20 (+50.0%)", row)

    def test_delta_needs_two_trials_per_condition(self):
        out = render_report([
            crec("s1", "skill", 0.5, 1000), crec("s2", "skill", 0.7, 1200),
            crec("b1", "baseline", 0.4, 800)])
        self.assertIn("not enough trials", block(out, "cost per trial")[2])

    def test_old_lines_without_tokens(self):
        out = render_report([crec("s1", "skill", 0.5, None),
                             crec("s2", "skill", 0.7, None)])
        self.assertIn("- tok, $0.60, 10.0 turns, n=2",
                      block(out, "cost per trial")[2])


class TwoPhaseReportTest(unittest.TestCase):
    def trials(self):
        return [
            crec("s1", "skill", 1.0, 3000, checks={"trap": True, "next": True},
                 phase2=(0.4, 8, 1000)),
            crec("s2", "skill", 1.2, 3400, checks={"trap": True, "next": False},
                 phase2=(0.6, 12, 1400)),
            crec("c1", "casual", 0.8, 2000, checks={"trap": False, "next": True},
                 phase2=(0.5, 10, 1200)),
            crec("c2", "casual", 0.8, 2000, checks={"trap": False, "next": False},
                 phase2=(0.5, 10, 1200)),
            crec("f1", "floor", 0.9, 2500, checks={"trap": False, "next": False},
                 phase2=(0.9, 20, 2500))]

    def test_pass_fail_columns_name_the_condition(self):
        header = render_report(self.trials()).splitlines()[1]
        self.assertIn("m1 casual", header)
        self.assertIn("m1 floor", header)

    def test_cost_compares_skill_with_casual_and_shows_floor(self):
        table = block(render_report(self.trials()), "cost per trial")
        self.assertEqual(table[1].split()[:4],
                         ["case", "skill", "casual", "floor"])
        self.assertIn("skill - casual", table[1])
        self.assertIn("tokens +1200 (+60.0%)", table[2])

    def test_phase_two_cost_table(self):
        table = block(render_report(self.trials()), "phase 2 (resume)")
        row = table[2]
        self.assertIn("1200 tok, $0.50, 10.0 turns, n=2", row)
        self.assertIn("2500 tok, $0.90, 20.0 turns, n=1", row)
        self.assertIn("tokens +0 (+0.0%)", row)

    def test_checks_per_condition(self):
        table = block(render_report(self.trials()), "checks passed")
        rows = {l.split()[1]: l.split()[2:] for l in table[2:]}
        self.assertEqual(rows["trap"], ["2/2", "0/2", "0/1"])
        self.assertEqual(rows["next"], ["1/2", "1/2", "0/1"])

    def test_judge_compares_skill_with_casual(self):
        out = render_report(self.trials() + [
            jrec("s1", 4), jrec("s2", 5), jrec("c1", 3), jrec("c2", 3),
            jrec("f1", 1)])
        self.assertIn("skill - casual", out[out.index("judge mean"):])
        row = judge_row(out)
        self.assertIn("4.50 n=2", row)
        self.assertIn("3.00 n=2", row)
        self.assertIn("1.00 n=1", row)
        self.assertIn("+1.50", row)


if __name__ == "__main__":
    unittest.main()
