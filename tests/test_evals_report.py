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
        passed=True, ts="2026-11-18T10:00:00Z"):
    return {"ts": ts, "case_id": case, "skill_version": version,
            "skill_hash": h, "model": model, "suite_hash": suite,
            "passed": passed}


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


if __name__ == "__main__":
    unittest.main()
