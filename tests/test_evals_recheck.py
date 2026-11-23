"""recheck: recompute the reply checks of stored rows from local traces."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import run  # noqa: E402
from evals.recheck import recheck  # noqa: E402

SUITE = {"skill": "s", "fixture": "f", "cases": [
    {"id": "c1", "prompt": "/s x",
     "checks": ["tree_clean", "reports_pass", "result_success"]},
    {"id": "c2", "prompt": "/s y",
     "checks": ["reports_pass", "proposes_audit"]}]}


def trace_lines(text):
    return [json.dumps({"type": "result", "subtype": "success",
                        "is_error": False, "result": text})]


class RecheckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.evals = self.root / "evals"
        (self.evals / "cases" / "su").mkdir(parents=True)
        (self.evals / "traces" / "su").mkdir(parents=True)
        (self.evals / "results").mkdir()
        self.set_suite(SUITE)
        self.path = self.evals / "results" / "su.jsonl"

    def set_suite(self, suite):
        (self.evals / "cases" / "su" / "suite.json").write_text(
            json.dumps(suite))

    def row(self, case_id, checks, text=None, error=None, **extra):
        trace = f"evals/traces/su/{case_id}-{len(extra)}{id(checks)}.jsonl"
        if text is not None:
            (self.root / trace).write_text("\n".join(trace_lines(text)))
        r = {"case_id": case_id, "checks": checks,
             "passed": all(checks.values()) and error is None,
             "cost_usd": 0.5, "error": error, "trace_path": trace,
             "trial": 1, "ts": "2026-11-19T00:00:00Z"}
        r.update(extra)
        return r

    def store(self, *rows):
        self.path.write_text("".join(json.dumps(r, sort_keys=True) + "\n"
                                     for r in rows))

    def rows(self):
        return [json.loads(l) for l in self.path.read_text().splitlines()]

    def recheck(self):
        return recheck(self.evals, "su", today="2026-11-23")

    def test_rewrites_a_stale_reply_check_and_passed(self):
        stale = self.row("c1", {"tree_clean": True, "reports_pass": False,
                                "result_success": True},
                         text="All 12 tests passed.")
        self.store(stale)
        summary = self.recheck()
        (r,) = self.rows()
        self.assertTrue(r["checks"]["reports_pass"])
        self.assertTrue(r["passed"])
        self.assertEqual(r["rechecked"], "2026-11-23")
        self.assertEqual(r["cost_usd"], 0.5)
        self.assertEqual(summary["changed"], [
            (stale["trace_path"], "reports_pass", False, True)])

    def test_keeps_repo_checks_it_cannot_recompute(self):
        self.store(self.row("c1", {"tree_clean": False, "reports_pass": False,
                                   "result_success": True},
                            text="tests passed"))
        self.recheck()
        (r,) = self.rows()
        self.assertFalse(r["checks"]["tree_clean"])
        self.assertFalse(r["passed"])

    def test_pass_can_turn_into_fail(self):
        self.store(self.row("c2", {"reports_pass": True,
                                   "proposes_audit": True},
                            text="All passed. I did not check whether an "
                                 "audit is due."))
        self.recheck()
        (r,) = self.rows()
        self.assertFalse(r["checks"]["proposes_audit"])
        self.assertFalse(r["passed"])

    def test_unchanged_row_is_left_byte_identical(self):
        self.store(self.row("c1", {"tree_clean": True, "reports_pass": True,
                                   "result_success": True},
                            text="tests passed"))
        before = self.path.read_text()
        summary = self.recheck()
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual((summary["rechecked"], summary["changed"]), (1, []))

    def test_idempotent(self):
        self.store(self.row("c1", {"tree_clean": True, "reports_pass": False,
                                   "result_success": True},
                            text="tests passed"))
        self.recheck()
        once = self.path.read_text()
        summary = self.recheck()
        self.assertEqual(self.path.read_text(), once)
        self.assertEqual(summary["changed"], [])

    def test_skips_rows_without_a_trace(self):
        self.store(self.row("c1", {"tree_clean": True, "reports_pass": False,
                                   "result_success": True}))
        before = self.path.read_text()
        summary = self.recheck()
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual(summary["rechecked"], 0)
        self.assertIn("no trace", summary["skipped"][0][1])

    def test_skips_rows_whose_case_or_check_set_changed(self):
        gone = self.row("old", {"reports_pass": False}, text="passed")
        other = self.row("c1", {"reports_pass": False}, text="passed")
        self.store(gone, other)
        before = self.path.read_text()
        summary = self.recheck()
        self.assertEqual(self.path.read_text(), before)
        reasons = [reason for _, reason in summary["skipped"]]
        self.assertIn("case no longer in suite", reasons[0])
        self.assertIn("check set differs", reasons[1])

    def test_leaves_judge_rows_alone(self):
        judge = {"kind": "judge", "trace_path": "x", "judge": {"a": 1}}
        self.store(self.row("c1", {"tree_clean": True, "reports_pass": False,
                                   "result_success": True},
                            text="passed"), judge)
        summary = self.recheck()
        self.assertEqual(self.rows()[1], judge)
        self.assertEqual(summary["skipped"], [])

    def test_cli_prints_a_summary(self):
        self.store(self.row("c1", {"tree_clean": True, "reports_pass": False,
                                   "result_success": True},
                            text="tests passed"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run.main(["--evals-dir", str(self.evals), "recheck", "su"])
        out = buf.getvalue()
        self.assertIn("rechecked 1", out)
        self.assertIn("reports_pass: False -> True", out)


if __name__ == "__main__":
    unittest.main()
