"""Judge tests with a FAKE claude executable (no model calls, no network)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import judge, snapshot  # noqa: E402

FAKE = '''#!{python}
import json, os, sys
from pathlib import Path
Path(os.environ["FAKE_OUT"]).write_text(json.dumps(
    {{"argv": sys.argv[1:], "cwd": os.getcwd(), "stdin": sys.stdin.read(),
      "no_memory": os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")}}))
if os.environ.get("FAKE_EXIT"):
    sys.exit(int(os.environ["FAKE_EXIT"]))
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False,
                   "result": os.environ["FAKE_REPLY"],
                   "total_cost_usd": 0.01}}))
'''

RUBRIC = {"criteria": [{"id": "goal", "text": "States the goal."},
                       {"id": "plan", "text": "Has a plan."}]}
SNAP = {"prompt": "Plan the exclude filter.", "result_text": "Done, spec at x.",
        "branch": "feature/x", "commits": ["docs: add spec"],
        "files": {"docs/spec.md": "# Spec\nGoal: hide tags\n"},
        "truncated": [], "omitted": ["big.txt"]}
GOOD = json.dumps({"goal": {"score": 4, "reason": "clear"},
                   "plan": {"score": 2, "reason": "vague"}})


class PromptTest(unittest.TestCase):
    def test_contains_task_snapshot_and_criteria(self):
        p = judge.build_prompt(RUBRIC, SNAP)
        for text in ("Plan the exclude filter.", "Done, spec at x.",
                     "feature/x", "docs: add spec", "docs/spec.md",
                     "Goal: hide tags", "big.txt", "goal", "States the goal.",
                     "plan", "Has a plan."):
            self.assertIn(text, p)

    def test_does_not_reveal_the_condition(self):
        p = judge.build_prompt(RUBRIC, SNAP).lower()
        self.assertNotIn("baseline", p)
        self.assertNotIn("skill", p)


class ParseTest(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(judge.parse_scores(GOOD, RUBRIC),
                         {"goal": {"score": 4, "reason": "clear"},
                          "plan": {"score": 2, "reason": "vague"}})

    def test_fenced_json_with_prose(self):
        text = f"Here are the scores:\n```json\n{GOOD}\n```\nThanks."
        self.assertEqual(judge.parse_scores(text, RUBRIC)["goal"]["score"], 4)

    def test_extra_criteria_are_dropped(self):
        d = json.loads(GOOD)
        d["other"] = {"score": 5, "reason": "x"}
        self.assertEqual(set(judge.parse_scores(json.dumps(d), RUBRIC)),
                         {"goal", "plan"})

    def test_rejects_missing_or_bad_scores(self):
        for bad in ("no json here",
                    json.dumps({"goal": {"score": 4, "reason": "r"}}),
                    json.dumps({"goal": {"score": 6, "reason": "r"},
                                "plan": {"score": 2, "reason": "r"}}),
                    json.dumps({"goal": {"score": "4", "reason": "r"},
                                "plan": {"score": 2, "reason": "r"}}),
                    json.dumps({"goal": {"score": True, "reason": "r"},
                                "plan": {"score": 2, "reason": "r"}})):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                judge.parse_scores(bad, RUBRIC)


class JudgeTrialTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp = Path(t.name)
        self.evals = self.tmp / "evals"
        self.rubric = self.evals / "cases" / "s" / "rubric.json"
        self.rubric.parent.mkdir(parents=True)
        self.rubric.write_text(json.dumps(RUBRIC))
        self.trace = "evals/traces/s/c1-20261119T000000Z-1.jsonl"
        snap_path = snapshot.snapshot_path(self.tmp / self.trace)
        snap_path.parent.mkdir(parents=True)
        snapshot.write_snapshot(snap_path, SNAP)
        self.fake = self.tmp / "claude"
        self.fake.write_text(FAKE.format(python=sys.executable))
        self.fake.chmod(0o755)
        self.out = self.tmp / "fake_out.json"
        p = mock.patch.dict(os.environ, {"FAKE_OUT": str(self.out),
                                         "FAKE_REPLY": GOOD})
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("CLAUDE_CODE_DISABLE_AUTO_MEMORY", None)

    def judge(self, **kw):
        return judge.judge_trial(evals_dir=self.evals, trace_path=self.trace,
                                 rubric_path=self.rubric,
                                 claude_bin=str(self.fake), model="haiku", **kw)

    def test_record(self):
        rec = self.judge()
        self.assertEqual(rec["kind"], "judge")
        self.assertEqual(rec["trace_path"], self.trace)
        self.assertEqual(rec["judge"]["plan"], {"score": 2, "reason": "vague"})
        self.assertEqual(rec["judge_model"], "haiku")
        self.assertEqual(rec["rubric_hash"], judge.rubric_hash(self.rubric))
        self.assertEqual(rec["cost_usd"], 0.01)
        self.assertIsNone(rec["error"])
        json.dumps(rec)

    def test_invocation_has_no_tools_and_hides_the_repo(self):
        self.judge()
        seen = json.loads(self.out.read_text())
        argv = seen["argv"]
        self.assertIn("-p", argv)
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertEqual(argv[argv.index("--model") + 1], "haiku")
        self.assertEqual(argv[argv.index("--output-format") + 1], "json")
        self.assertIn("--safe-mode", argv)
        self.assertIn("Goal: hide tags", seen["stdin"])
        self.assertNotEqual(Path(seen["cwd"]).resolve(), ROOT.resolve())

    def test_judge_runs_without_auto_memory(self):
        self.judge()
        self.assertEqual(json.loads(self.out.read_text())["no_memory"], "1")

    def test_unparseable_reply_is_recorded_as_error(self):
        with mock.patch.dict(os.environ, {"FAKE_REPLY": "I refuse"}):
            rec = self.judge()
        self.assertIsNone(rec["judge"])
        self.assertIn("I refuse", rec["error"])

    def test_claude_failure_is_recorded_as_error(self):
        with mock.patch.dict(os.environ, {"FAKE_EXIT": "3"}):
            rec = self.judge()
        self.assertIsNone(rec["judge"])
        self.assertIn("exited 3", rec["error"])

    def test_missing_snapshot_is_recorded_as_error(self):
        snapshot.snapshot_path(self.tmp / self.trace).unlink()
        rec = self.judge()
        self.assertIsNone(rec["judge"])
        self.assertIn("snapshot", rec["error"])
        self.assertFalse(self.out.exists())


class UnjudgedTest(unittest.TestCase):
    def test_trials_without_a_good_judge_for_this_rubric(self):
        trial = {"trace_path": "a"}
        records = [trial, {"trace_path": "b"}, {"trace_path": "c"},
                   {"kind": "judge", "trace_path": "b", "rubric_hash": "h",
                    "judge_model": "m", "error": None},
                   {"kind": "judge", "trace_path": "c", "rubric_hash": "old",
                    "judge_model": "m", "error": None},
                   {"kind": "judge", "trace_path": "a", "rubric_hash": "h",
                    "judge_model": "m", "error": "timeout"}]
        self.assertEqual([r["trace_path"] for r in
                          judge.unjudged(records, "h", "m")], ["a", "c"])

    def test_a_judgement_by_another_model_leaves_the_trial_pending(self):
        records = [{"trace_path": "a"}, {"trace_path": "b"},
                   {"kind": "judge", "trace_path": "a", "rubric_hash": "h",
                    "judge_model": "haiku", "error": None},
                   {"kind": "judge", "trace_path": "b", "rubric_hash": "h",
                    "judge_model": "sonnet", "error": None}]
        self.assertEqual([r["trace_path"] for r in
                          judge.unjudged(records, "h", "sonnet")], ["a"])


if __name__ == "__main__":
    unittest.main()
