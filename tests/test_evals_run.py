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
if "--safe-mode" in sys.argv:  # a judge call
    Path(os.environ["FAKE_OUT"] + ".judge").write_text(json.dumps(
        {{"argv": sys.argv[1:], "stdin": sys.stdin.read(),
          "no_memory": os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")}}))
    print(json.dumps({{"type": "result", "is_error": False,
                       "total_cost_usd": 0.01, "result": json.dumps(
        {{"goal": {{"score": 4, "reason": "ok"}},
          "plan": {{"score": 3, "reason": "thin"}}}})}}))
    sys.exit(0)
Path(os.environ["FAKE_OUT"]).write_text(json.dumps(
    {{"argv": sys.argv[1:], "cwd": os.getcwd(), "stdin": sys.stdin.read(),
      "no_memory": os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")}}))
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
        os.environ.pop("CLAUDE_CODE_DISABLE_AUTO_MEMORY", None)

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

    def test_claude_runs_without_auto_memory(self):
        # Auto memory lives outside the fixture (~/.claude/projects/...), so
        # it would carry facts between phases, trials and conditions.
        self.write_rubric()
        self.cli("run", "my-suite", "--judge")
        self.assertEqual(json.loads(self.out.read_text())["no_memory"], "1")
        self.assertEqual(json.loads(Path(str(self.out) + ".judge")
                                    .read_text())["no_memory"], "1")

    def permission_hook(self, argv):
        """The one PermissionRequest hook passed with --settings."""
        settings = json.loads(argv[argv.index("--settings") + 1])
        (entry,) = settings["hooks"]["PermissionRequest"]
        (hook,) = entry["hooks"]
        self.assertEqual(hook["type"], "command")
        return entry["matcher"], hook["command"]

    def ask_hook(self, command, cwd, tool, path):
        r = subprocess.run(command, shell=True, capture_output=True, text=True,
                           input=json.dumps({
                               "hook_event_name": "PermissionRequest",
                               "cwd": cwd, "tool_name": tool,
                               "tool_input": {"file_path": path}}))
        self.assertEqual(r.returncode, 0, r.stderr)
        return (json.loads(r.stdout)["hookSpecificOutput"]["decision"]
                ["behavior"] if r.stdout.strip() else None)

    def test_suite_allow_writes_installs_a_narrow_permission_hook(self):
        # Writes under .claude/ are protected paths: acceptEdits and allow
        # rules do not cover them, and -p denies the prompt. A
        # PermissionRequest hook answers that prompt for the named paths
        # only; every other prompt is still denied (and recorded).
        self.write_suite({"skill": "my-skill", "fixture": "fx",
                          "allow_writes": [".claude/handoff.md"],
                          "cases": [{"id": "c1", "prompt": "/my-skill do it"}]})
        self.cli("run", "my-suite")
        seen = json.loads(self.out.read_text())
        argv, cwd = seen["argv"], seen["cwd"]
        self.assertEqual(argv[argv.index("--permission-mode") + 1],
                         "acceptEdits")
        self.assertNotIn("bypassPermissions", argv)
        self.assertNotIn("--dangerously-skip-permissions", argv)
        matcher, command = self.permission_hook(argv)
        self.assertEqual(matcher, "Write|Edit|Bash")
        self.assertEqual(self.ask_hook(command, cwd, "Write",
                                       f"{cwd}/.claude/handoff.md"), "allow")
        self.assertEqual(self.ask_hook(command, cwd, "Edit",
                                       ".claude/handoff.md"), "allow")
        self.assertIsNone(self.ask_hook(command, cwd, "Write",
                                        f"{cwd}/.claude/settings.json"))

    def pre_tool_hook(self, argv):
        settings = json.loads(argv[argv.index("--settings") + 1])
        (entry,) = settings["hooks"]["PreToolUse"]
        (hook,) = entry["hooks"]
        return entry["matcher"], hook["command"]

    def test_plain_condition_blocks_reading_the_skills_dir(self):
        # --disable-slash-commands does not stop the model from cat-ing the
        # SKILL.md itself, so a plain run gets a PreToolUse hook that denies
        # any tool call touching ~/.claude/skills.
        self.cli("run", "my-suite", "--baseline")
        argv = json.loads(self.out.read_text())["argv"]
        matcher, command = self.pre_tool_hook(argv)
        # every tool that can read a path must reach the hook
        for tool in ("Bash", "Read", "Glob", "Grep"):
            self.assertIn(tool, matcher.split("|"))
        def ask(tool, **tool_input):
            r = subprocess.run(command, shell=True, capture_output=True,
                               text=True, input=json.dumps({
                                   "hook_event_name": "PreToolUse",
                                   "cwd": "/tmp", "tool_name": tool,
                                   "tool_input": tool_input}))
            self.assertEqual(r.returncode, 0, r.stderr)
            return (json.loads(r.stdout)["hookSpecificOutput"]
                    ["permissionDecision"] if r.stdout.strip() else None)
        self.assertEqual(ask("Bash", command="cat ~/.claude/skills/x/SKILL.md"),
                         "deny")
        self.assertIsNone(ask("Bash", command="git status"))

    def test_skill_condition_has_no_pre_tool_hook(self):
        self.cli("run", "my-suite")
        self.assertNotIn("--settings", json.loads(self.out.read_text())["argv"])

    def test_plain_condition_with_allow_writes_keeps_both_hooks(self):
        self.write_suite({"skill": "my-skill", "fixture": "fx",
                          "allow_writes": [".claude/handoff.md"],
                          "cases": [{"id": "c1", "prompt": "/my-skill do it"}]})
        self.cli("run", "my-suite", "--baseline")
        argv = json.loads(self.out.read_text())["argv"]
        self.assertEqual(argv.count("--settings"), 1)
        self.permission_hook(argv)
        self.pre_tool_hook(argv)

    def test_no_permission_hook_without_allow_writes(self):
        self.cli("run", "my-suite")
        self.assertNotIn("--settings", json.loads(self.out.read_text())["argv"])

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

    def write_rubric(self):
        (self.evals / "cases" / "my-suite" / "rubric.json").write_text(
            json.dumps({"criteria": [{"id": "goal", "text": "g"},
                                     {"id": "plan", "text": "p"}]}))

    def judge_argv(self):
        return json.loads(Path(str(self.out) + ".judge").read_text())["argv"]

    def test_run_with_judge_appends_a_judge_line(self):
        self.write_rubric()
        out = self.cli("run", "my-suite", "--judge")
        trial, judged = self.results()
        self.assertNotIn("kind", trial)
        self.assertEqual(judged["kind"], "judge")
        self.assertEqual(judged["trace_path"], trial["trace_path"])
        self.assertEqual(judged["judge"]["goal"]["score"], 4)
        self.assertEqual(judged["judge_model"], "haiku")
        self.assertEqual(self.judge_argv()[
            self.judge_argv().index("--model") + 1], "haiku")
        self.assertIn("judge 3.50", out)

    def test_judge_model_flag(self):
        self.write_rubric()
        self.cli("run", "my-suite", "--judge", "--judge-model", "sonnet")
        self.assertEqual(self.results()[1]["judge_model"], "sonnet")
        self.assertEqual(self.judge_argv()[
            self.judge_argv().index("--model") + 1], "sonnet")

    def test_run_without_judge_makes_no_judge_call(self):
        self.write_rubric()
        self.cli("run", "my-suite")
        self.assertEqual(len(self.results()), 1)
        self.assertFalse(Path(str(self.out) + ".judge").exists())

    def test_judge_needs_a_rubric_before_any_trial_runs(self):
        with self.assertRaises(SystemExit) as cm:
            self.cli("run", "my-suite", "--judge")
        self.assertIn("rubric", str(cm.exception))
        self.assertFalse(self.out.exists())
        with self.assertRaises(SystemExit):
            self.cli("judge", "my-suite")

    def test_judge_command_scores_stored_snapshots_once(self):
        self.write_rubric()
        self.cli("run", "my-suite", "--trials", "2")
        out = self.cli("judge", "my-suite", "--judge-model", "sonnet")
        recs = self.results()
        judged = [r for r in recs if r.get("kind") == "judge"]
        self.assertEqual(sorted(r["trace_path"] for r in judged),
                         sorted(r["trace_path"] for r in recs[:2]))
        self.assertEqual({r["judge_model"] for r in judged}, {"sonnet"})
        self.assertIn("judge 3.50", out)
        self.cli("judge", "my-suite", "--judge-model", "sonnet")
        self.assertEqual(len(self.results()), 4)

    def test_judge_command_rejudges_with_a_different_model(self):
        self.write_rubric()
        self.cli("run", "my-suite")
        self.cli("judge", "my-suite", "--judge-model", "sonnet")
        self.cli("judge", "my-suite", "--judge-model", "haiku")
        judged = [r for r in self.results() if r.get("kind") == "judge"]
        self.assertEqual([r["judge_model"] for r in judged],
                         ["sonnet", "haiku"])

    def test_judge_command_skips_trials_without_a_snapshot(self):
        self.write_rubric()
        self.cli("run", "my-suite")
        (rec,) = self.results()
        snapshot.snapshot_path(self.evals.parent / rec["trace_path"]).unlink()
        out = self.cli("judge", "my-suite")
        self.assertIn("no snapshot", out)
        self.assertEqual(len(self.results()), 1)

    def test_report_ignores_judge_lines_in_the_pass_fail_table(self):
        self.write_rubric()
        self.cli("run", "my-suite", "--judge")
        out = self.cli("report", "my-suite")
        self.assertIn("1/1", out)

    def test_report_prints_the_table(self):
        self.cli("run", "my-suite")
        out = self.cli("report", "my-suite")
        self.assertIn("c1", out)
        self.assertIn("1/1", out)

    def test_evals_dir_flag_moves_cases_fixtures_and_results(self):
        """A suite kept outside the repo: --evals-dir replaces the default
        evals dir for cases, fixtures, results and traces."""
        private = self.tmp / "private"
        shutil.copytree(self.evals, private)
        shutil.rmtree(self.evals / "cases")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            run.main(["--evals-dir", str(private), "run", "my-suite"],
                     evals_dir=self.evals, repo_root=self.repo)
        self.assertIn("c1 trial 1: pass", buf.getvalue())
        self.assertTrue((private / "results" / "my-suite.jsonl").is_file())
        self.assertFalse((self.evals / "results").exists())


FAKE_TWO_PHASE = """#!{python}
import json, os, sys
from pathlib import Path
prompt = sys.argv[sys.argv.index("-p") + 1]
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(),
        "no_memory": os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")}})
        + "\\n")
resume = "pick up" in prompt
if not resume and os.environ.get("FAKE_MODE") == "fail1":
    sys.exit(1)
print(json.dumps({{"type": "system", "subtype": "init", "model": "fake-model",
                   "claude_code_version": "0.0.0"}}))
if resume:
    Path("worker").mkdir(exist_ok=True)
    Path("worker/promote.py").write_text("def promote_next():\\n    pass\\n")
    text = "saw notes" if Path(".notes.md").exists() else "cold"
    cost, turns, out = 0.5, 5, 100
else:
    Path(".notes.md").write_text("decided: worker\\n")
    text, cost, turns, out = "ready", 0.25, 2, 10
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False,
                   "result": text, "total_cost_usd": cost, "duration_ms": 10,
                   "num_turns": turns, "permission_denials": [],
                   "modelUsage": {{"m": {{"inputTokens": 1, "outputTokens": out,
                       "cacheReadInputTokens": 1000,
                       "cacheCreationInputTokens": 0}}}}}}))
"""

TWO_PHASE_CASE = {
    "id": "resume", "prepare": "/my-skill I am about to clear, write it down",
    "prompt": "/my-skill new session, pick up where I left off",
    "checks": ["result_success"],
    "facts": [{"id": "next_step_done", "kind": "matches",
               "glob": "worker/*.py", "pattern": "^def promote_next"},
              {"id": "did_not_ask", "kind": "no_question"}]}


class TwoPhaseRunnerTest(unittest.TestCase):
    """A case with "prepare" runs phase 1 (prepare) and phase 2 (prompt) as
    two separate claude calls in the same working copy."""

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
        fx = self.evals / "fixtures" / "fx"
        fx.mkdir(parents=True)
        (fx / "app.py").write_text("print(1)\n")
        cases = self.evals / "cases" / "my-suite"
        cases.mkdir(parents=True)
        (cases / "suite.json").write_text(json.dumps(
            {"skill": "my-skill", "fixture": "fx",
             "cases": [TWO_PHASE_CASE]}))
        fake = self.tmp / "claude"
        fake.write_text(FAKE_TWO_PHASE.format(python=sys.executable))
        fake.chmod(0o755)
        self.log = self.tmp / "calls.jsonl"
        p = mock.patch.dict(os.environ, {"EVALS_CLAUDE_BIN": str(fake),
                                         "FAKE_LOG": str(self.log)})
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("CLAUDE_CODE_DISABLE_AUTO_MEMORY", None)

    def cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            run.main(list(args), evals_dir=self.evals, repo_root=self.repo)

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(x) for x in self.log.read_text().splitlines()]

    def results(self):
        path = self.evals / "results" / "my-suite.jsonl"
        return [json.loads(x) for x in path.read_text().splitlines()]

    def test_skill_runs_both_phases_in_the_same_copy(self):
        self.cli("run", "my-suite")
        first, second = self.calls()
        self.assertEqual(first["argv"][:2], ["-p", TWO_PHASE_CASE["prepare"]])
        self.assertEqual(second["argv"][:2], ["-p", TWO_PHASE_CASE["prompt"]])
        self.assertEqual(first["cwd"], second["cwd"])
        for call in (first, second):
            self.assertNotIn("--disable-slash-commands", call["argv"])
            self.assertNotIn("--continue", call["argv"])
            self.assertNotIn("--resume", call["argv"])
        (rec,) = self.results()
        self.assertEqual(rec["condition"], "skill")
        self.assertTrue(rec["passed"], rec["checks"])
        self.assertEqual(set(rec["checks"]),
                         {"result_success", "next_step_done", "did_not_ask"})

    def test_both_phases_run_without_auto_memory(self):
        self.cli("run", "my-suite")
        self.assertEqual([c["no_memory"] for c in self.calls()], ["1", "1"])

    def test_both_phases_get_the_suite_permission_hook(self):
        (self.evals / "cases" / "my-suite" / "suite.json").write_text(
            json.dumps({"skill": "my-skill", "fixture": "fx",
                        "allow_writes": [".claude/handoff.md"],
                        "cases": [TWO_PHASE_CASE]}))
        self.cli("run", "my-suite")
        for call in self.calls():
            self.assertIn("--settings", call["argv"])

    def test_record_keeps_each_phase_and_the_total(self):
        self.cli("run", "my-suite")
        (rec,) = self.results()
        p1, p2 = rec["phase1"], rec["phase2"]
        self.assertEqual((p1["cost_usd"], p1["num_turns"]), (0.25, 2))
        self.assertEqual((p2["cost_usd"], p2["num_turns"]), (0.5, 5))
        self.assertEqual(p1["tokens"]["output"], 10)
        self.assertEqual(p2["tokens"]["total"], 1101)
        self.assertEqual(p2["trace_path"], rec["trace_path"])
        self.assertTrue((self.evals.parent / p1["trace_path"]).is_file())
        self.assertNotEqual(p1["trace_path"], p2["trace_path"])
        self.assertIsNone(p1["error"])
        self.assertEqual((rec["cost_usd"], rec["num_turns"]), (0.75, 7))
        self.assertEqual(rec["tokens"], {"input": 2, "output": 110,
                                         "cache_read": 2000,
                                         "cache_write": 0, "total": 2112})

    def test_phase_two_sees_what_phase_one_left(self):
        self.cli("run", "my-suite")
        (rec,) = self.results()
        snap = json.loads(snapshot.snapshot_path(
            self.evals.parent / rec["trace_path"]).read_text())
        self.assertEqual(snap["result_text"], "saw notes")
        self.assertIn("worker/promote.py", snap["files"])

    def test_casual_runs_both_phases_without_the_skill(self):
        self.cli("run", "my-suite", "--condition", "casual")
        first, second = self.calls()
        self.assertEqual(first["argv"][:2],
                         ["-p", "I am about to clear, write it down"])
        self.assertEqual(second["argv"][:2],
                         ["-p", "new session, pick up where I left off"])
        for call in (first, second):
            self.assertIn("--disable-slash-commands", call["argv"])
        (rec,) = self.results()
        self.assertEqual(rec["condition"], "casual")

    def test_floor_skips_phase_one(self):
        self.cli("run", "my-suite", "--condition", "floor")
        (call,) = self.calls()
        self.assertEqual(call["argv"][:2],
                         ["-p", "new session, pick up where I left off"])
        self.assertIn("--disable-slash-commands", call["argv"])
        (rec,) = self.results()
        self.assertEqual(rec["condition"], "floor")
        self.assertIsNone(rec["phase1"])
        self.assertEqual(rec["phase2"]["cost_usd"], 0.5)
        self.assertEqual(rec["cost_usd"], 0.5)
        self.assertEqual(rec["tokens"]["total"], 1101)
        snap = json.loads(snapshot.snapshot_path(
            self.evals.parent / rec["trace_path"]).read_text())
        self.assertEqual(snap["result_text"], "cold")

    def test_snapshot_prompt_is_both_tasks_and_hides_the_condition(self):
        for cond in ("skill", "casual", "floor"):
            self.cli("run", "my-suite", "--condition", cond)
        prompts = {json.loads(snapshot.snapshot_path(
            self.evals.parent / r["trace_path"]).read_text())["prompt"]
            for r in self.results()}
        (prompt,) = prompts
        self.assertIn("I am about to clear, write it down", prompt)
        self.assertIn("new session, pick up where I left off", prompt)
        self.assertNotIn("/my-skill", prompt)

    def test_phase_one_failure_skips_phase_two(self):
        with mock.patch.dict(os.environ, {"FAKE_MODE": "fail1"}):
            self.cli("run", "my-suite")
        self.assertEqual(len(self.calls()), 1)
        (rec,) = self.results()
        self.assertFalse(rec["passed"])
        self.assertIn("phase 1", rec["error"])
        self.assertIn("exited 1", rec["phase1"]["error"])

    def test_baseline_is_refused_on_a_two_phase_case(self):
        for args in (["--baseline"], ["--condition", "baseline"]):
            with self.assertRaises(SystemExit) as cm:
                self.cli("run", "my-suite", *args)
            self.assertIn("casual", str(cm.exception))
        self.assertEqual(self.calls(), [])

    def test_casual_and_floor_are_refused_on_a_one_phase_case(self):
        case = dict(TWO_PHASE_CASE)
        del case["prepare"]
        (self.evals / "cases" / "my-suite" / "suite.json").write_text(
            json.dumps({"skill": "my-skill", "fixture": "fx",
                        "cases": [case]}))
        for cond in ("casual", "floor"):
            with self.assertRaises(SystemExit) as cm:
                self.cli("run", "my-suite", "--condition", cond)
            self.assertIn("prepare", str(cm.exception))
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
