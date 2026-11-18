"""Runner tests with a FAKE claude executable (no model calls, no network)."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import run  # noqa: E402

FAKE = '''#!{python}
import json, os, subprocess, sys, time
from pathlib import Path
Path(os.environ["FAKE_OUT"]).write_text(json.dumps(
    {{"argv": sys.argv[1:], "cwd": os.getcwd(), "stdin": sys.stdin.read()}}))
if os.environ.get("FAKE_MODE") == "hang":
    time.sleep(30)
def git(*a):
    subprocess.run(["git", *a], check=True, capture_output=True)
print(json.dumps({{"type": "system", "subtype": "init", "model": "fake-model",
                   "claude_code_version": "0.0.0"}}))
git("checkout", "-q", "-b", "feature/x")
d = Path("docs/10_features/2026_11_18_x")
d.mkdir(parents=True)
(d / "grill.md").write_text("g\\n")
(d / "spec.md").write_text("s\\n")
git("add", ".")
git("commit", "-q", "-m", "docs: add spec")
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False,
                   "total_cost_usd": 0.5, "duration_ms": 10, "num_turns": 3,
                   "permission_denials": []}}))
'''


class RunnerTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp = Path(t.name)
        self.repo = self.tmp / "repo"
        skill = self.repo / "my-skill"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: my-skill\nversion: 1.2.3\n---\nbody\n")
        self.evals = self.tmp / "evals"
        fx = self.evals / "fixtures" / "fx" / "docs" / "10_features" / "archived"
        fx.mkdir(parents=True)
        (fx / ".gitkeep").write_text("")
        (self.evals / "fixtures" / "fx" / "app.py").write_text("print(1)\n")
        cases = self.evals / "cases" / "my-skill"
        cases.mkdir(parents=True)
        (cases / "suite.json").write_text(json.dumps(
            {"fixture": "fx", "cases": [{"id": "c1", "prompt": "do it"}]}))
        self.fake = self.tmp / "claude"
        self.fake.write_text(FAKE.format(python=sys.executable))
        self.fake.chmod(0o755)
        self.out = self.tmp / "fake_out.json"
        env = {"EVALS_CLAUDE_BIN": str(self.fake), "FAKE_OUT": str(self.out)}
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)

    def cli(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run.main(list(args), evals_dir=self.evals, repo_root=self.repo)
        return buf.getvalue()

    def results(self):
        path = self.evals / "results" / "my-skill.jsonl"
        return [json.loads(x) for x in path.read_text().splitlines()]

    def test_run_records_a_passing_trial(self):
        self.cli("run", "my-skill", "--model", "m", "--max-budget-usd", "2",
                 "--timeout", "30")
        (rec,) = self.results()
        self.assertTrue(rec["passed"], rec["checks"])
        self.assertIsNone(rec["error"])
        self.assertEqual(rec["skill_version"], "1.2.3")
        self.assertEqual(rec["skill_ref"], "working-tree")
        self.assertEqual(rec["model"], "fake-model")
        self.assertEqual((rec["case_id"], rec["trial"]), ("c1", 1))
        self.assertTrue(Path(rec["trace_path"]).is_file())
        self.assertIn("my-skill", rec["trace_path"])

    def test_claude_invocation(self):
        self.cli("run", "my-skill", "--model", "m", "--max-budget-usd", "2")
        seen = json.loads(self.out.read_text())
        argv = seen["argv"]
        self.assertEqual(argv[:2], ["-p", "do it"])
        self.assertIn("stream-json", argv)
        self.assertIn("--verbose", argv)
        self.assertEqual(argv[argv.index("--permission-mode") + 1],
                         "acceptEdits")
        self.assertEqual(argv[argv.index("--max-budget-usd") + 1], "2")
        self.assertEqual(argv[argv.index("--model") + 1], "m")
        allowed = argv[argv.index("--allowed-tools") + 1]
        self.assertIn("Bash", allowed.split())
        self.assertNotIn("--dangerously-skip-permissions", argv)
        self.assertNotIn("bypassPermissions", argv)
        self.assertEqual(seen["stdin"], "")
        self.assertNotEqual(Path(seen["cwd"]).resolve(),
                            (self.evals / "fixtures" / "fx").resolve())

    def test_fixture_source_is_untouched(self):
        self.cli("run", "my-skill")
        fx = self.evals / "fixtures" / "fx"
        self.assertFalse((fx / ".git").exists())
        self.assertFalse((fx / "docs" / "10_features" / "2026_11_18_x").exists())

    def test_trials(self):
        self.cli("run", "my-skill", "--trials", "2")
        self.assertEqual([r["trial"] for r in self.results()], [1, 2])

    def test_timeout_is_recorded_as_error(self):
        with mock.patch.dict(os.environ, {"FAKE_MODE": "hang"}):
            self.cli("run", "my-skill", "--timeout", "1")
        (rec,) = self.results()
        self.assertFalse(rec["passed"])
        self.assertIn("timeout", rec["error"])

    def test_other_skill_ref_is_not_supported(self):
        with self.assertRaises(SystemExit) as cm:
            self.cli("run", "my-skill", "--skill-ref", "v1")
        self.assertIn("not supported yet", str(cm.exception))
        self.assertFalse((self.evals / "results").exists())

    def test_report_prints_the_table(self):
        self.cli("run", "my-skill")
        out = self.cli("report", "my-skill")
        self.assertIn("c1", out)
        self.assertIn("1/1", out)


if __name__ == "__main__":
    unittest.main()
