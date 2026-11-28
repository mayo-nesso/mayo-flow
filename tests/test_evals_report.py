"""Report table tests (stdlib only)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import record  # noqa: E402
from evals.judge import decisions_hash  # noqa: E402
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


OPEN_DECISIONS = {"persist": [{"id": "gap", "text": "What a gap does",
                               "open": True}]}
DECISION_HASH = decisions_hash(OPEN_DECISIONS["persist"])


def erec(trace, condition, hidden, cost, secs, p1=None, denials=0,
         observed=None, tokens=1000, case="persist"):
    """An end-to-end trial. hidden: {test name: passed}; p1: (cost, secs) of
    phase 1, None for a baseline trial."""
    r = rec(case=case, trace=trace, condition=condition,
            passed=all(hidden.values()))
    r.update(checks={"result_success": True,
                     **{"hidden:" + k: v for k, v in hidden.items()}},
             cost_usd=cost, duration_ms=secs * 1000, num_turns=5,
             tokens={"total": tokens}, permission_denials=denials,
             hidden_hash="h" * 64, phase1=None,
             phase2={"cost_usd": cost, "num_turns": 5, "tokens": None})
    if p1:
        r["phase1"] = {"cost_usd": p1[0], "duration_ms": p1[1] * 1000}
    if observed is not None:
        r["observed"] = observed
    return r


class ConditionColumnsTest(unittest.TestCase):
    def test_skill_and_baseline_rows_with_phase2_compare_with_baseline(self):
        out = render_report([
            erec("s1", "skill", {"a": True}, 3.0, 100, p1=(1.0, 40)),
            erec("s2", "skill", {"a": True}, 5.0, 100, p1=(1.0, 40)),
            erec("b1", "baseline", {"a": True}, 0.5, 50),
            erec("b2", "baseline", {"a": False}, 0.7, 50)])
        table = block(out, "cost per trial")
        self.assertEqual(table[1].split()[:3], ["case", "skill", "baseline"])
        self.assertIn("skill - baseline", table[1])
        self.assertNotIn("casual", out)
        self.assertNotIn("floor", out)

    def test_floor_without_casual_still_gives_the_resume_columns(self):
        out = render_report([
            crec("s1", "skill", 1.0, 3000, phase2=(0.4, 8, 1000)),
            crec("f1", "floor", 0.9, 2500, phase2=(0.9, 20, 2500))])
        table = block(out, "cost per trial")
        self.assertEqual(table[1].split()[:4],
                         ["case", "skill", "casual", "floor"])


class EndToEndReportTest(unittest.TestCase):
    def trials(self):
        return [
            erec("s1", "skill", {"A.t1": True, "A.t2": True}, 3.0, 100,
                 p1=(1.0, 40), denials=2, tokens=4000,
                 observed={"grill_written": True, "questions": 4,
                           "skill_calls": 0}),
            erec("s2", "skill", {"A.t1": True, "A.t2": False}, 5.0, 200,
                 p1=(1.0, 20), denials=0, tokens=5000,
                 observed={"grill_written": False, "questions": 2,
                           "skill_calls": 1}),
            erec("b1", "baseline", {"A.t1": True, "A.t2": True}, 0.5, 50,
                 denials=1, tokens=900,
                 observed={"grill_written": False, "questions": 0,
                           "skill_calls": 0})]

    def rows(self, out):
        lines = block(out, "end-to-end")
        return {l.split()[1]: l.split() for l in lines[2:]}

    def test_hidden_pass_rate_counts_tests_not_trials(self):
        rows = self.rows(render_report(self.trials()))
        self.assertEqual(rows["skill"][:4], ["persist", "skill", "2", "3/4"])
        self.assertEqual(rows["baseline"][:4],
                         ["persist", "baseline", "1", "2/2"])

    def test_errored_trial_is_counted_apart_not_as_a_fail(self):
        errored = erec("s3", "skill", {"A.t1": False, "A.t2": False}, 0.1, 5)
        errored["error"] = "claude exited 1"
        out = render_report(self.trials() + [errored])
        row = next(l for l in block(out, "end-to-end")[2:]
                   if l.split()[1] == "skill")
        self.assertEqual(row.split()[:4], ["persist", "skill", "2", "(+1"])
        self.assertIn("2 (+1 errored)", row)
        self.assertIn("3/4", row)  # the errored trial's tests are not run
        self.assertIn("$4.00", row)  # nor does it drag the means down

    def test_means_and_phase_one_share(self):
        rows = self.rows(render_report(self.trials()))
        # cost, tokens, wall time, phase-1 share of cost and of time,
        # questions, denials
        self.assertEqual(rows["skill"][4:11], ["$4.00", "4500", "150s", "25%",
                                               "20%", "3.0", "1.0"])
        self.assertEqual(rows["baseline"][4:11], ["$0.50", "900", "50s", "-",
                                                  "-", "0.0", "1.0"])

    def test_counts_of_each_boolean_observation(self):
        out = render_report(self.trials())
        skill, baseline = [l for l in block(out, "end-to-end")[2:]]
        self.assertIn("grill_written 1/2", skill)
        # numbers (questions, skill_calls) are not boolean observations
        self.assertNotIn("questions", skill)
        self.assertNotIn("skill_calls", skill)
        self.assertIn("grill_written 0/1", baseline)

    def test_rows_without_observed_render(self):
        out = render_report([
            erec("s1", "skill", {"A.t1": True}, 1.0, 10, p1=(0.5, 5))])
        self.assertIn("1/1", block(out, "end-to-end")[2])

    def test_a_dictated_decision_is_right_only_when_all_its_tests_pass(self):
        decisions = {"persist": [
            {"id": "dup", "text": "x", "tests": ["hidden:A.t1", "hidden:A.t2"]},
            {"id": "first", "text": "y", "tests": ["hidden:A.t1"]}]}
        out = render_report(self.trials(), decisions=decisions)
        table = block(out, "decisions")
        self.assertEqual(table[1].split(), ["case", "decision", "skill",
                                            "baseline"])
        rows = {l.split()[1]: l.split()[2:] for l in table[2:]}
        self.assertEqual(rows["dup"], ["1/2", "1/1"])
        self.assertEqual(rows["first"], ["2/2", "1/1"])

    def labels(self, trace, ts="2026-11-18T12:00:00Z", error=None, **labels):
        return {"kind": "decisions", "ts": ts, "trace_path": trace,
                "decisions": None if error else {
                    k: {"label": v, "reason": "x"} for k, v in labels.items()},
                "judge_model": "opus", "decisions_hash": DECISION_HASH,
                "error": error}

    def test_open_decisions_show_explicit_over_labelled_and_unlabelled(self):
        out = render_report(self.trials() + [
            self.labels("s1", gap="explicit"),
            self.labels("s2", gap="silent"),
            self.labels("s2", ts="2026-11-18T13:00:00Z", gap="explicit"),
            self.labels("b1", error="timeout")], decisions=OPEN_DECISIONS)
        row = self.gap_row(out)
        # s2's latest label counts; b1's label errored, so it is unlabelled
        self.assertIn("2/2 explicit", row)
        self.assertIn("0/0 explicit (1 unlabelled)", row)

    def gap_row(self, out):
        return next(l for l in block(out, "decisions") if " gap " in l)

    def test_labels_of_other_decisions_are_ignored(self):
        old = dict(self.labels("s1", gap="explicit"), decisions_hash="old")
        out = render_report(self.trials() + [old], decisions=OPEN_DECISIONS)
        row = self.gap_row(out)
        self.assertIn("0/0 explicit (2 unlabelled)", row)
        self.assertIn("0/0 explicit (1 unlabelled)", row)

    def test_no_decisions_table_without_decisions(self):
        self.assertNotIn("decisions", render_report(self.trials()))

    def test_no_resume_tables_for_end_to_end_rows(self):
        # e2e rows have phase2 too, but "phase 2 (resume)" would mislabel
        # them and "checks passed" would list every hidden test
        out = render_report(self.trials())
        self.assertNotIn("phase 2 (resume)", out)
        self.assertNotIn("checks passed per condition", out)

    def test_no_end_to_end_table_for_other_suites(self):
        self.assertNotIn("end-to-end", render_report([rec()]))
        self.assertNotIn("end-to-end", render_report(
            [crec("s1", "skill", 1.0, 3000, phase2=(0.4, 8, 1000))]))


if __name__ == "__main__":
    unittest.main()


def mrec(checks, case="c1", condition="skill", mutant=None, **kw):
    r = rec(case=case, condition=condition, **kw)
    r["checks"] = checks
    if mutant:
        r["mutant"] = mutant
        r["isolation"] = "project-sources"
    return r


def line(out, start):
    return next(l for l in out.splitlines() if l.startswith(start))


class MutantRowsTest(unittest.TestCase):
    def test_mutant_rows_stay_out_of_the_existing_tables(self):
        rows = [rec(), rec(),
                mrec({"s1_a": True}, mutant="no-x", passed=False),
                mrec({"s1_a": True}, mutant="control", passed=False)]
        head = render_report(rows).split("Checks by clause")[0]
        self.assertIn("2/2", head)
        self.assertNotIn("2/4", head)

    def test_results_without_mutant_rows_print_as_before(self):
        rows = [rec(), rec(passed=False), rec(condition="baseline")]
        out = render_report(rows, mutants={"no-x": {"targets": ["s1_a"]}})
        self.assertNotIn("Checks by clause", out)
        self.assertNotIn("Mutant sensitivity", out)
        self.assertEqual(out, render_report(rows))


class ClauseTableTest(unittest.TestCase):
    def rows(self):
        return [
            mrec({"s1_a": True, "s2_b": False, "result_success": True}),
            mrec({"s1_a": True, "s2_b": True}),
            mrec({"s1_a": False}, condition="baseline"),
            mrec({"s1_a": True}, case="c2", mutant="control"),
            mrec({"s1_a": False, "n_x": True}, mutant="no-x"),
        ]

    def test_one_row_per_s_check_with_a_column_per_group(self):
        out = render_report(self.rows())
        block = out[out.index("Checks by clause"):]
        header = block.splitlines()[1]
        for word in ("skill", "baseline", "control", "no-x"):
            self.assertIn(word, header)
        self.assertEqual(line(block, "s1_a").split(),
                         ["s1_a", "2/2", "0/1", "1/1", "0/1"])
        self.assertEqual(line(block, "s2_b").split(),
                         ["s2_b", "1/2", "-", "-", "-"])
        self.assertNotIn("result_success", block)
        self.assertLess(block.index("n_x"), block.index("s1_a"))

    def test_note_when_a_cell_has_fewer_than_two_trials(self):
        self.assertIn("not enough trials",
                      render_report(self.rows()).split("Checks by clause")[1])

    def test_no_clause_table_without_s_checks(self):
        out = render_report([mrec({"result_success": True})])
        self.assertNotIn("Checks by clause", out)

    def test_baseline_column_only_when_baseline_rows_exist(self):
        out = render_report([mrec({"s1_a": True})])
        self.assertNotIn("baseline", out[out.index("Checks by clause"):])


class SensitivityTest(unittest.TestCase):
    MUTANTS = {"no-x": {"targets": ["s1_a", "s2_b"]}}

    def group(self, n_ok, n, mutant, key="s1_a"):
        return [mrec({key: i < n_ok}, mutant=mutant) for i in range(n)]

    def verdicts(self, rows):
        out = render_report(rows, mutants=self.MUTANTS)
        block = out[out.index("Mutant sensitivity"):]
        row = {c: next(l for l in block.splitlines()
                       if l.split()[:2] == ["no-x", c])
               for c in ("s1_a", "s2_b")}
        return block, row["s1_a"], row["s2_b"]

    def test_sensitive_when_the_drop_is_two_thirds(self):
        rows = self.group(3, 3, "control") + self.group(1, 3, "no-x")
        _, a, _ = self.verdicts(rows)
        self.assertEqual(a.split(), ["no-x", "s1_a", "3/3", "1/3",
                                     "sensitive"])

    def test_insensitive_when_the_drop_is_smaller(self):
        rows = self.group(3, 3, "control") + self.group(2, 3, "no-x")
        _, a, _ = self.verdicts(rows)
        self.assertTrue(a.endswith("insensitive"))

    def test_not_enough_trials_below_three_in_either_group(self):
        rows = self.group(3, 3, "control") + self.group(0, 2, "no-x")
        _, a, b = self.verdicts(rows)
        self.assertTrue(a.endswith("not enough trials"))
        self.assertEqual(b.split()[2:4], ["-", "-"])  # no row has s2_b
        self.assertTrue(b.endswith("not enough trials"))

    def test_no_table_without_the_mutants_file(self):
        rows = self.group(3, 3, "control") + self.group(1, 3, "no-x")
        self.assertNotIn("Mutant sensitivity", render_report(rows))


def scen(r, name, h):
    """Row `r` run with CLAUDE.md scenario `name` (file hash `h`)."""
    r["claude_md"], r["claude_md_hash"] = name, h
    return r


class ClaudeMdSplitTest(unittest.TestCase):
    def test_title_shows_the_claude_md_of_the_block(self):
        self.assertEqual(render_report([rec()]).splitlines()[0],
                         "suite sssssss, CLAUDE.md user (no hash)")
        self.assertEqual(
            render_report([scen(rec(), "owner", "o" * 64)]).splitlines()[0],
            "suite sssssss, CLAUDE.md owner ooooooo")

    def test_rows_of_different_scenarios_are_separate_blocks(self):
        out = render_report([
            rec(), scen(rec(passed=False), "owner", "o" * 64)])
        user = out[out.index("CLAUDE.md user"):]
        owner = out[out.index("CLAUDE.md owner"):]
        user = user[:user.index("suite ")] if "suite " in user else user
        owner = owner[:owner.index("suite ")] if "suite " in owner else owner
        self.assertIn("1/1", user)
        self.assertNotIn("0/1", user)
        self.assertIn("0/1", owner)
        self.assertNotIn("1/1", owner)

    def test_same_scenario_with_another_hash_is_split(self):
        out = render_report([scen(rec(), "owner", "1" * 64),
                             scen(rec(), "owner", "2" * 64)])
        self.assertIn("CLAUDE.md owner 1111111", out)
        self.assertIn("CLAUDE.md owner 2222222", out)
        self.assertNotIn("2/2", out)

    def test_old_rows_count_as_user_without_hash(self):
        out = render_report([rec(), scen(rec(), "user", None)])
        self.assertEqual(out.count("suite sssssss"), 1)
        self.assertIn("2/2", out)


class HermeticControlTest(unittest.TestCase):
    """Item: hermetic skill rows stand in for missing control rows."""
    MUTANTS = {"no-x": {"targets": ["s1_a"]}}

    def rows(self, n_ok, n, mutant=None, name="owner", **kw):
        return [scen(mrec({"s1_a": i < n_ok}, mutant=mutant, **kw), name,
                     "o" * 64) for i in range(n)]

    def sens(self, rows):
        out = render_report(rows, mutants=self.MUTANTS)
        block = out[out.index("Mutant sensitivity"):]
        return block, line(block, "no-x").split()

    def test_hermetic_skill_rows_are_the_control_when_none_exists(self):
        block, row = self.sens(self.rows(3, 3) + self.rows(1, 3, "no-x"))
        self.assertEqual(row, ["no-x", "s1_a", "3/3", "1/3", "sensitive"])
        self.assertIn("skill rows", block)

    def test_real_control_rows_win_over_skill_rows(self):
        block, row = self.sens(self.rows(3, 3, "control")
                               + self.rows(0, 3)
                               + self.rows(1, 3, "no-x"))
        self.assertEqual(row[2], "3/3")
        self.assertNotIn("skill rows", block)

    def test_skill_rows_of_another_skill_hash_are_not_used(self):
        _, row = self.sens(self.rows(3, 3, "control", h="c" * 40)
                           + self.rows(0, 3, h="c" * 40)
                           + self.rows(3, 3, h="d" * 40)
                           + self.rows(1, 3, "no-x"))
        self.assertEqual(row[2], "6/6")

    def test_user_skill_rows_are_never_the_control(self):
        _, row = self.sens(self.rows(3, 3, name="user")
                           + self.rows(1, 3, "no-x", name="user"))
        self.assertEqual(row[2], "-")
