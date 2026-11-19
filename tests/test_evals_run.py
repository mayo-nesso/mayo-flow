"""Runner tests with a FAKE claude executable (no model calls, no network)."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import record, run, snapshot  # noqa: E402

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
                   "result": "all done", "total_cost_usd": 0.5, "duration_ms": 10, "num_turns": 3,
                   "permission_denials": []}}))
'''


class PrepareFixtureTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp = Path(t.name)
        self.src = self.tmp / "src"
        self.src.mkdir()
        (self.src / "a.txt").write_text("a\n")
        self.dest = self.tmp / "dest"

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.dest), *args],
                              capture_output=True, text=True).stdout.strip()

    def test_plain_fixture_is_one_commit_on_main(self):
        run.prepare_fixture(self.src, self.dest)
        self.assertEqual(self.git("branch", "--show-current"), "main")
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "1")

    def test_setup_script_runs_in_the_copy_after_the_first_commit(self):
        (self.src / "setup.sh").write_text(
            "set -e\ngit checkout -q -b feature/x\necho b > b.txt\n"
            "git add -A\ngit commit -q -m 'feat: b'\n")
        run.prepare_fixture(self.src, self.dest)
        self.assertEqual(self.git("branch", "--show-current"), "feature/x")
        self.assertEqual(self.git("rev-list", "--count", "main"), "1")
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "2")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_setup_script_runs_with_a_relative_source_path(self):
        (self.src / "setup.sh").write_text("touch ran.txt\n")
        cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, cwd)
        run.prepare_fixture(Path("src"), self.dest)
        self.assertTrue((self.dest / "ran.txt").exists())

    def test_setup_script_is_not_copied(self):
        (self.src / "setup.sh").write_text("true\n")
        run.prepare_fixture(self.src, self.dest)
        self.assertFalse((self.dest / "setup.sh").exists())

    def test_failing_setup_script_raises(self):
        (self.src / "setup.sh").write_text("exit 3\n")
        with self.assertRaises(subprocess.CalledProcessError):
            run.prepare_fixture(self.src, self.dest)


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
        # A decoy dir named like the suite: using the suite name as the skill
        # directory would pick this one up instead of my-skill.
        decoy = self.repo / "my-suite"
        decoy.mkdir()
        (decoy / "SKILL.md").write_text("---\nname: decoy\nversion: 9.9.9\n---\n")
        cases = self.evals / "cases" / "my-suite"
        cases.mkdir(parents=True)
        (cases / "suite.json").write_text(json.dumps(
            {"skill": "my-skill", "fixture": "fx",
             "cases": [{"id": "c1", "prompt": "/my-skill do it"}]}))
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
        path = self.evals / "results" / "my-suite.jsonl"
        return [json.loads(x) for x in path.read_text().splitlines()]

    def test_run_records_a_passing_trial(self):
        self.cli("run", "my-suite", "--model", "m", "--max-budget-usd", "2",
                 "--timeout", "30")
        (rec,) = self.results()
        self.assertTrue(rec["passed"], rec["checks"])
        self.assertIsNone(rec["error"])
        self.assertEqual(rec["skill_version"], "1.2.3")
        self.assertEqual(rec["skill_ref"], "working-tree")
        self.assertEqual(rec["model"], "fake-model")
        self.assertEqual((rec["case_id"], rec["trial"]), ("c1", 1))
        self.assertTrue((self.evals.parent / rec["trace_path"]).is_file())
        self.assertIn("my-suite", rec["trace_path"])

    def test_trace_path_is_relative_to_the_repo_root(self):
        self.cli("run", "my-suite")
        (rec,) = self.results()
        self.assertFalse(rec["trace_path"].startswith("/"), rec["trace_path"])
        self.assertTrue(rec["trace_path"].startswith("evals/traces/my-suite/"),
                        rec["trace_path"])
        self.assertTrue((self.evals.parent / rec["trace_path"]).is_file())

    def test_record_uses_the_skill_named_in_the_suite(self):
        self.cli("run", "my-suite")
        (rec,) = self.results()
        skill_dir = self.repo / "my-skill"
        self.assertEqual(rec["skill"], "my-skill")
        self.assertEqual(rec["skill_version"], "1.2.3")
        self.assertEqual(rec["skill_hash"], record.skill_hash(skill_dir))

    def test_missing_skill_dir_records_an_error_instead_of_crashing(self):
        shutil.rmtree(self.repo / "my-skill")
        self.cli("run", "my-suite")
        (rec,) = self.results()
        self.assertFalse(rec["passed"])
        self.assertEqual(rec["checks"], {})
        self.assertIn("my-skill", rec["error"])
        self.assertTrue((self.evals.parent / rec["trace_path"]).is_file())

    def write_suite(self, suite):
        (self.evals / "cases" / "my-suite" / "suite.json").write_text(
            json.dumps(suite))

    def test_suite_checks_select_what_runs(self):
        self.write_suite({"skill": "my-skill", "fixture": "fx",
                          "checks": ["tree_clean", "result_success"],
                          "cases": [{"id": "c1", "prompt": "/my-skill do it"}]})
        self.cli("run", "my-suite")
        (rec,) = self.results()
        self.assertEqual(set(rec["checks"]), {"tree_clean", "result_success"})

    def test_case_checks_override_the_suite(self):
        self.write_suite({"skill": "my-skill", "fixture": "fx",
                          "checks": ["tree_clean"],
                          "cases": [{"id": "c1", "prompt": "/my-skill do it",
                                     "checks": ["result_success"]}]})
        self.cli("run", "my-suite")
        (rec,) = self.results()
        self.assertEqual(set(rec["checks"]), {"result_success"})

    def test_case_fixture_overrides_the_suite(self):
        other = self.evals / "fixtures" / "other"
        other.mkdir()
        (other / "marker.txt").write_text("m\n")
        self.write_suite({"skill": "my-skill", "fixture": "fx",
                          "cases": [{"id": "c1", "prompt": "/my-skill do it",
                                     "fixture": "other"}]})
        with mock.patch.object(run, "prepare_fixture",
                               wraps=run.prepare_fixture) as prep:
            self.cli("run", "my-suite")
        self.assertEqual(prep.call_args.args[0].name, "other")

    def test_claude_invocation(self):
        self.cli("run", "my-suite", "--model", "m", "--max-budget-usd", "2")
        seen = json.loads(self.out.read_text())
        argv = seen["argv"]
        self.assertEqual(argv[:2], ["-p", "/my-skill do it"])
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

    def test_budget_cap_defaults_to_5_usd(self):
        self.cli("run", "my-suite")
        argv = json.loads(self.out.read_text())["argv"]
        self.assertEqual(argv[argv.index("--max-budget-usd") + 1], "5")

    def test_fixture_source_is_untouched(self):
        self.cli("run", "my-suite")
        fx = self.evals / "fixtures" / "fx"
        self.assertFalse((fx / ".git").exists())
        self.assertFalse((fx / "docs" / "10_features" / "2026_11_18_x").exists())

    def test_trials(self):
        self.cli("run", "my-suite", "--trials", "2")
        self.assertEqual([r["trial"] for r in self.results()], [1, 2])

    def test_timeout_is_recorded_as_error(self):
        with mock.patch.dict(os.environ, {"FAKE_MODE": "hang"}):
            self.cli("run", "my-suite", "--timeout", "1")
        (rec,) = self.results()
        self.assertFalse(rec["passed"])
        self.assertIn("timeout", rec["error"])

    def test_other_skill_ref_is_not_supported(self):
        with self.assertRaises(SystemExit) as cm:
            self.cli("run", "my-suite", "--skill-ref", "v1")
        self.assertIn("not supported yet", str(cm.exception))
        self.assertFalse((self.evals / "results").exists())

    def test_snapshot_is_saved_beside_the_trace(self):
        self.cli("run", "my-suite")
        (rec,) = self.results()
        path = snapshot.snapshot_path(self.evals.parent / rec["trace_path"])
        snap = json.loads(path.read_text())
        self.assertEqual(snap["result_text"], "all done")
        self.assertEqual(snap["branch"], "feature/x")
        self.assertEqual(snap["commits"], ["docs: add spec"])
        self.assertEqual(set(snap["files"]),
                         {"docs/10_features/2026_11_18_x/grill.md",
                          "docs/10_features/2026_11_18_x/spec.md"})

    def test_strip_skill_removes_the_leading_slash_command(self):
        self.assertEqual(run.strip_skill("/my-skill do it\n\nmore", "my-skill"),
                         "do it\n\nmore")
        self.assertEqual(run.strip_skill("/my-skill\n\ndo it", "my-skill"),
                         "do it")
        with self.assertRaises(ValueError):
            run.strip_skill("do it", "my-skill")

    def test_baseline_drops_the_skill_and_slash_commands(self):
        self.cli("run", "my-suite", "--baseline")
        argv = json.loads(self.out.read_text())["argv"]
        self.assertEqual(argv[:2], ["-p", "do it"])
        self.assertIn("--disable-slash-commands", argv)
        (rec,) = self.results()
        self.assertEqual(rec["condition"], "baseline")

    def test_skill_condition_keeps_the_slash_command(self):
        self.cli("run", "my-suite")
        argv = json.loads(self.out.read_text())["argv"]
        self.assertEqual(argv[:2], ["-p", "/my-skill do it"])
        self.assertNotIn("--disable-slash-commands", argv)
        (rec,) = self.results()
        self.assertEqual(rec["condition"], "skill")

    def test_snapshot_prompt_hides_the_condition(self):
        self.cli("run", "my-suite")
        self.cli("run", "my-suite", "--baseline")
        prompts = {json.loads(snapshot.snapshot_path(
            self.evals.parent / r["trace_path"]).read_text())["prompt"]
            for r in self.results()}
        self.assertEqual(prompts, {"do it"})

    def test_report_prints_the_table(self):
        self.cli("run", "my-suite")
        out = self.cli("report", "my-suite")
        self.assertIn("c1", out)
        self.assertIn("1/1", out)


if __name__ == "__main__":
    unittest.main()
