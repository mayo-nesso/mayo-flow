"""The shipped feature-start suite and its fixture are well-formed."""
import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"


def load_suite(test, skill):
    path = EVALS / "cases" / skill / "suite.json"
    test.assertTrue(path.is_file(), f"missing suite file {path}")
    return json.loads(path.read_text())


class FeatureStartSuiteTest(unittest.TestCase):
    def setUp(self):
        self.suite = load_suite(self, "feature-start")
        self.fixture = EVALS / "fixtures" / self.suite["fixture"]

    def test_names_the_skill_directory(self):
        self.assertIn("skill", self.suite)
        self.assertEqual(self.suite["skill"], "mayo-flow-feature-start")
        self.assertTrue((ROOT / self.suite["skill"] / "SKILL.md").is_file())

    def test_fixture_has_archived_dir(self):
        self.assertTrue(self.fixture.is_dir())
        self.assertTrue((self.fixture / "docs/10_features/archived").is_dir())

    def test_case_shape(self):
        (case,) = self.suite["cases"]
        self.assertEqual(case["id"], "exclude-filter")
        self.assertTrue(case["prompt"])
        self.assertIn("/mayo-flow-feature-start", case["prompt"])

    def test_fixture_unit_tests_pass_in_a_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "fx"
            shutil.copytree(self.fixture, dest)
            r = subprocess.run([sys.executable, "-m", "unittest"], cwd=dest,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)


def unittest_rc(fixture):
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "fx"
        shutil.copytree(fixture, dest)
        return subprocess.run([sys.executable, "-m", "unittest"], cwd=dest,
                              capture_output=True, text=True).returncode


class RunTestsSuiteTest(unittest.TestCase):
    def setUp(self):
        self.suite = load_suite(self, "run-tests")

    def test_names_the_skill_directory(self):
        self.assertEqual(self.suite["skill"], "mayo-flow-run-tests")
        self.assertTrue((ROOT / self.suite["skill"] / "SKILL.md").is_file())

    def test_cases_expect_what_their_fixture_really_does(self):
        cases = {c["id"]: c for c in self.suite["cases"]}
        self.assertEqual(set(cases), {"green", "red"})
        for cid, report, rc_ok in (("green", "reports_pass", True),
                                   ("red", "reports_fail", False)):
            case = cases[cid]
            self.assertIn("/mayo-flow-run-tests", case["prompt"])
            self.assertIn("headless", case["prompt"])
            self.assertIn(report, case["checks"])
            self.assertIn("tree_clean", case["checks"])
            fixture = EVALS / "fixtures" / case["fixture"]
            self.assertEqual(unittest_rc(fixture) == 0, rc_ok, cid)


class GitignoreSuiteTest(unittest.TestCase):
    def setUp(self):
        self.suite = load_suite(self, "gitignore")
        self.fixture = EVALS / "fixtures" / self.suite["fixture"]

    def test_names_the_skill_directory(self):
        self.assertEqual(self.suite["skill"], "mayo-flow-gitignore")
        self.assertTrue((ROOT / self.suite["skill"] / "SKILL.md").is_file())

    def test_fixture_is_a_python_repo_without_gitignore(self):
        self.assertFalse((self.fixture / ".gitignore").exists())
        self.assertTrue((self.fixture / "requirements.txt").is_file())

    def test_case_shape(self):
        (case,) = self.suite["cases"]
        self.assertIn("/mayo-flow-gitignore", case["prompt"])
        self.assertIn("headless", case["prompt"])
        for name in ("gitignore_exists", "gitignore_python",
                     "gitignore_secrets", "gitignore_os",
                     "gitignore_only_python", "gitignore_committed",
                     "tree_clean", "result_success"):
            self.assertIn(name, case["checks"])


class HandoffSuiteTest(unittest.TestCase):
    def setUp(self):
        self.suite = load_suite(self, "handoff")

    def test_names_the_skill_directory(self):
        self.assertEqual(self.suite["skill"], "mayo-flow-handoff")
        self.assertTrue((ROOT / self.suite["skill"] / "SKILL.md").is_file())
        self.assertTrue((EVALS / "fixtures" / self.suite["fixture"]).is_dir())

    def test_write_case_shape(self):
        write, casual = self.suite["cases"]
        self.assertEqual(write["id"], "write")
        self.assertIn("/mayo-flow-handoff", write["prompt"])
        self.assertIn("headless", write["prompt"])
        for name in ("handoff_exists", "handoff_short", "handoff_sections",
                     "handoff_excluded", "no_new_commits", "tree_clean",
                     "result_success"):
            self.assertIn(name, write["checks"])

    def test_handoff_file_may_be_written_with_write_or_edit(self):
        # .claude/ is a protected path that -p would deny to Write/Edit.
        self.assertEqual(self.suite["allow_writes"], [".claude/handoff.md"])

    def test_casual_case_is_a_short_natural_prompt(self):
        casual = self.suite["cases"][1]
        self.assertEqual(casual["id"], "casual")
        self.assertTrue(casual["prompt"].startswith("/mayo-flow-handoff"))
        self.assertLess(len(casual["prompt"]), 400)
        self.assertNotIn("as the skill describes", casual["prompt"])


class TicketsSuiteTest(unittest.TestCase):
    def setUp(self):
        self.suite = load_suite(self, "tickets")
        self.fixture = EVALS / "fixtures" / self.suite["fixture"]

    def test_names_the_skill_directory(self):
        self.assertEqual(self.suite["skill"], "mayo-flow-tickets")
        self.assertTrue((ROOT / self.suite["skill"] / "SKILL.md").is_file())

    def test_fixture_has_a_spec_and_no_tickets_yet(self):
        folders = list((self.fixture / "docs/10_features").glob("2026_*"))
        self.assertEqual(len(folders), 1)
        self.assertTrue((folders[0] / "spec.md").stat().st_size > 0)
        self.assertFalse((folders[0] / "tickets").exists())
        self.assertEqual(unittest_rc(self.fixture), 0)

    def test_case_shape(self):
        (case,) = self.suite["cases"]
        self.assertIn("/mayo-flow-tickets", case["prompt"])
        self.assertIn("headless", case["prompt"])
        self.assertIn("Do not commit", case["prompt"])
        for name in ("tickets_exist", "tickets_sections",
                     "tickets_blockers_valid", "no_code_changed",
                     "result_success"):
            self.assertIn(name, case["checks"])
        self.assertNotIn("tree_clean", case["checks"])  # tickets stay uncommitted


class FixStartSuiteTest(unittest.TestCase):
    def setUp(self):
        self.suite = load_suite(self, "fix-start")
        self.fixture = EVALS / "fixtures" / self.suite["fixture"]

    def test_names_the_skill_directory(self):
        self.assertEqual(self.suite["skill"], "mayo-flow-fix-start")
        self.assertTrue((ROOT / self.suite["skill"] / "SKILL.md").is_file())

    def test_the_described_bug_is_real_in_the_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "fx"
            shutil.copytree(self.fixture, dest)
            r = subprocess.run(
                [sys.executable, "-m", "listcli", "list", "--tag", "Dairy"],
                cwd=dest, capture_output=True, text=True)
            self.assertEqual(r.stdout, "")  # lower-case "dairy" would match
            r = subprocess.run(
                [sys.executable, "-m", "listcli", "list", "--tag", "dairy"],
                cwd=dest, capture_output=True, text=True)
            self.assertNotEqual(r.stdout, "")

    def test_case_shape(self):
        (case,) = self.suite["cases"]
        self.assertIn("/mayo-flow-fix-start", case["prompt"])
        self.assertIn("headless", case["prompt"])
        self.assertIn("--tag Dairy", case["prompt"])
        for name in ("branch_is_fix", "fix_plan_exists", "fix_plan_sections",
                     "fix_plan_commit_alone", "branch_docs_only",
                     "tree_clean", "result_success"):
            self.assertIn(name, case["checks"])


class ProjectInitSuiteTest(unittest.TestCase):
    def setUp(self):
        self.suite = load_suite(self, "project-init")
        self.fixture = EVALS / "fixtures" / self.suite["fixture"]

    def test_names_the_skill_directory(self):
        self.assertEqual(self.suite["skill"], "mayo-flow-project-init")
        self.assertTrue((ROOT / self.suite["skill"] / "SKILL.md").is_file())

    def test_fixture_has_no_process_structure_yet(self):
        self.assertFalse((self.fixture / "docs").exists())
        self.assertFalse((self.fixture / "CLAUDE.md").exists())
        self.assertFalse((self.fixture / ".gitignore").exists())

    def test_case_shape(self):
        (case,) = self.suite["cases"]
        self.assertIn("/mayo-flow-project-init", case["prompt"])
        self.assertIn("headless", case["prompt"])
        self.assertIn("Conventional Commits", case["prompt"])
        self.assertIn("do not merge", case["prompt"].lower())
        for name in ("branch_is_scaffold", "docs_lifecycle",
                     "docs_core_files", "claude_md_lifecycle",
                     "gitignore_exists", "gitignore_python",
                     "commits_conventional", "tree_clean", "result_success"):
            self.assertIn(name, case["checks"])


class BranchFinishSuiteTest(unittest.TestCase):
    def setUp(self):
        self.suite = load_suite(self, "branch-finish")
        self.fixture = EVALS / "fixtures" / self.suite["fixture"]

    def case(self, case_id):
        (case,) = [c for c in self.suite["cases"] if c["id"] == case_id]
        return case

    def build(self, case_id):
        """The case's fixture, prepared as a trial would, in a temp dir."""
        sys.path.insert(0, str(ROOT))
        from evals import run
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name) / "fx"
        fixture = self.case(case_id).get("fixture", self.suite["fixture"])
        run.prepare_fixture(EVALS / "fixtures" / fixture, dest)
        return dest

    def git(self, repo, *a):
        return subprocess.run(["git", "-C", str(repo), *a],
                              capture_output=True, text=True).stdout.strip()

    def unittest_rc(self, repo):
        return subprocess.run([sys.executable, "-m", "unittest"], cwd=repo,
                              capture_output=True, text=True).returncode

    def test_new_case_prompts_do_not_reveal_the_answer(self):
        for cid in ("red-tests", "partial-tickets", "audit-due",
                    "dirty-tree", "parent-feature", "remote"):
            prompt = self.case(cid)["prompt"]
            self.assertTrue(prompt.startswith("/mayo-flow-branch-finish"))
            self.assertIn("headless", prompt)
            for leak in ("fail", "partial", "audit", "open", "skip the merge",
                         "do not merge", "ticket", "dirty", "uncommitted",
                         "stash", "parent", "origin", "push", "bare",
                         "calc-ops"):
                self.assertNotIn(leak, prompt.lower(), (cid, leak))

    def test_remote_prompt_does_not_deny_the_remote(self):
        # "There is no remote." would hide the case; the others may say it.
        self.assertNotIn("remote", self.case("remote")["prompt"].lower())
        for cid in ("dirty-tree", "parent-feature"):
            self.assertIn("There is no remote.", self.case(cid)["prompt"])

    def test_prompts_state_the_task_without_the_slash_command(self):
        # baseline strips the leading /<skill>; what is left must still ask
        # for the work, or the baseline run has no task at all.
        sys.path.insert(0, str(ROOT))
        from evals import run
        for cid in ("finished-feature", "red-tests", "partial-tickets",
                    "audit-due", "dirty-tree", "parent-feature", "remote"):
            body = run.strip_skill(self.case(cid)["prompt"],
                                   "mayo-flow-branch-finish")
            self.assertIn("finish this branch", body.lower(), cid)

    def test_red_tests_fixture_has_a_failing_test(self):
        repo = self.build("red-tests")
        self.assertEqual(self.git(repo, "branch", "--show-current"),
                         "feature/subtract")
        self.assertEqual(self.git(repo, "status", "--porcelain"), "")
        self.assertNotEqual(self.unittest_rc(repo), 0)

    def test_red_tests_case_checks(self):
        names = self.case("red-tests")["checks"]
        for n in ("branch_is_feature", "main_untouched", "spec_not_archived",
                  "reports_fail", "tree_clean", "result_success"):
            self.assertIn(n, names)
        self.assertNotIn("merged_no_ff", names)

    def test_partial_fixture_has_an_open_ticket(self):
        from evals import checks
        repo = self.build("partial-tickets")
        self.assertEqual(self.git(repo, "status", "--porcelain"), "")
        self.assertEqual(self.unittest_rc(repo), 0)
        self.assertTrue(checks.open_items_left(repo))
        self.assertGreaterEqual(len(checks._tickets(repo)), 2)

    def test_partial_case_checks(self):
        names = self.case("partial-tickets")["checks"]
        for n in ("on_main", "merged_no_ff", "spec_not_archived",
                  "done_marker", "open_items_left", "reports_open_tickets",
                  "feature_branch_deleted", "reports_pass", "tree_clean",
                  "result_success"):
            self.assertIn(n, names)
        self.assertNotIn("spec_archived", names)

    def test_audit_due_fixture_has_ten_merges_and_no_audit(self):
        from evals import checks
        repo = self.build("audit-due")
        self.assertEqual(self.git(repo, "branch", "--show-current"),
                         "feature/subtract")
        self.assertEqual(self.git(repo, "status", "--porcelain"), "")
        self.assertGreaterEqual(
            int(self.git(repo, "rev-list", "--merges", "--count", "main")), 10)
        self.assertTrue(checks.no_audit_report(repo))
        self.assertEqual(self.unittest_rc(repo), 0)

    def test_audit_due_case_checks(self):
        names = self.case("audit-due")["checks"]
        for n in ("on_main", "merged_no_ff", "spec_archived",
                  "spec_completed_marker", "feature_branch_deleted",
                  "proposes_audit", "no_audit_report", "tree_clean",
                  "result_success"):
            self.assertIn(n, names)

    def test_dirty_tree_fixture_has_the_planted_changes(self):
        from evals import checks
        repo = self.build("dirty-tree")
        self.assertEqual(self.git(repo, "branch", "--show-current"),
                         "feature/subtract")
        self.assertTrue(checks.dirty_preserved(repo))
        self.assertTrue(checks.main_untouched(repo))
        self.assertEqual(self.unittest_rc(repo), 0)

    def test_dirty_tree_case_checks(self):
        names = self.case("dirty-tree")["checks"]
        for n in ("branch_is_feature", "main_untouched", "spec_not_archived",
                  "dirty_preserved", "reports_dirty", "result_success"):
            self.assertIn(n, names)
        for n in ("tree_clean", "merged_no_ff", "on_main"):
            self.assertNotIn(n, names)

    def test_parent_fixture_branches_off_an_unmerged_feature(self):
        repo = self.build("parent-feature")
        self.assertEqual(self.git(repo, "branch", "--show-current"),
                         "feature/subtract")
        self.assertEqual(self.git(repo, "status", "--porcelain"), "")
        self.assertEqual(self.git(repo, "branch", "--list", "feature/calc-ops")
                         .lstrip("* "), "feature/calc-ops")
        # the parent is in progress and never merged; the child sits on it
        self.assertEqual(self.git(repo, "rev-list", "--count", "main"), "1")
        self.assertEqual(self.git(repo, "merge-base", "feature/calc-ops",
                                  "HEAD"),
                         self.git(repo, "rev-parse", "feature/calc-ops"))
        self.assertEqual(self.unittest_rc(repo), 0)
        self.assertEqual(len(self.git(repo, "ls-files",
                                      "docs/10_features/2026_*/spec.md")
                             .splitlines()), 2)

    def test_parent_case_checks(self):
        names = self.case("parent-feature")["checks"]
        for n in ("on_parent", "merged_no_ff", "main_untouched",
                  "child_spec_archived", "parent_spec_not_archived",
                  "child_branch_deleted", "parent_branch_kept",
                  "no_audit_proposal", "no_audit_report", "reports_pass",
                  "tree_clean", "result_success"):
            self.assertIn(n, names)
        self.assertNotIn("on_main", names)
        self.assertNotIn("feature_branch_deleted", names)

    def test_remote_fixture_pushes_the_branch_to_a_local_bare_repo(self):
        from evals import checks
        repo = self.build("remote")
        origin = Path(self.git(repo, "remote", "get-url", "origin"))
        self.assertTrue(origin.is_absolute() and origin.is_dir())
        self.assertEqual(origin.resolve().parent, repo.resolve().parent)
        self.assertEqual(self.git(repo, "rev-parse", "HEAD"), self.git(
            repo, "ls-remote", "--heads", "origin", "feature/subtract"
        ).split()[0])
        self.assertTrue(checks.main_not_pushed(repo))
        self.assertTrue(checks.remote_not_rewritten(repo))
        rc = subprocess.run(["git", "-C", str(repo), "push", "origin",
                             "--delete", "feature/subtract"],
                            capture_output=True).returncode
        self.assertNotEqual(rc, 0)  # the hook guards the remote branch

    def test_remote_case_checks(self):
        names = self.case("remote")["checks"]
        for n in ("on_main", "merged_no_ff", "spec_archived",
                  "feature_branch_deleted", "remote_branch_kept",
                  "remote_not_rewritten", "main_not_pushed", "reports_pass",
                  "tree_clean", "result_success"):
            self.assertIn(n, names)

    def test_names_the_skill_directory(self):
        self.assertEqual(self.suite["skill"], "mayo-flow-branch-finish")
        self.assertTrue((ROOT / self.suite["skill"] / "SKILL.md").is_file())

    def test_fixture_builds_a_finished_feature_branch(self):
        sys.path.insert(0, str(ROOT))
        from evals import run
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "fx"
            run.prepare_fixture(self.fixture, dest)

            def git(*a):
                return subprocess.run(["git", "-C", str(dest), *a],
                                      capture_output=True, text=True
                                      ).stdout.strip()

            self.assertTrue(git("branch", "--show-current")
                            .startswith("feature/"))
            self.assertEqual(git("status", "--porcelain"), "")
            specs = git("ls-files", "docs/10_features/2026_*/spec.md")
            self.assertEqual(len(specs.splitlines()), 1)
            self.assertEqual(git("ls-tree", "-r", "--name-only", "main",
                                 "docs/10_features/2026_*"), "")
            self.assertNotEqual(git("rev-list", "--count", "main..HEAD"), "0")
            r = subprocess.run([sys.executable, "-m", "unittest"], cwd=dest,
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_case_shape(self):
        case = self.case("finished-feature")
        self.assertIn("/mayo-flow-branch-finish", case["prompt"])
        self.assertIn("headless", case["prompt"])
        for name in ("on_main", "merged_no_ff", "spec_archived",
                     "spec_completed_marker", "archive_commit_is_docs",
                     "feature_branch_deleted", "reports_pass", "tree_clean",
                     "result_success"):
            self.assertIn(name, case["checks"])


class HandoffResumeSuiteTest(unittest.TestCase):
    """Two-phase resume case on the synthetic big-app fixture: the planted
    facts must be checkable, and the checks must tell good work from bad."""

    def setUp(self):
        sys.path.insert(0, str(ROOT))
        from evals import checks, run
        self.checks, self.run = checks, run
        self.suite = load_suite(self, "handoff-resume")
        (self.case,) = self.suite["cases"]
        self.fixture = EVALS / "fixtures" / self.suite["fixture"]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.copy = Path(tmp.name) / "fx"
        run.prepare_fixture(self.fixture, self.copy)
        self.base = self.git("rev-parse", "HEAD")

    def git(self, *a):
        return subprocess.run(["git", "-C", str(self.copy), *a],
                              capture_output=True, text=True).stdout.strip()

    def facts(self, result_text="Promotion job added; tests pass."):
        return self.checks.fact_checks(self.copy, self.base,
                                       {"result_text": result_text},
                                       self.case["facts"])

    def edit(self, rel, text, append=False):
        p = self.copy / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text((p.read_text() if append else "") + text)

    def test_shape(self):
        self.assertEqual(self.suite["skill"], "mayo-flow-handoff")
        self.assertEqual(self.suite["fixture"], "big-app")
        for key in ("prepare", "prompt"):
            self.assertTrue(self.case[key].startswith("/mayo-flow-handoff "))
        self.assertIn("pick up", self.case["prompt"])
        self.assertIn("result_success", self.case["checks"])

    def test_handoff_file_may_be_written_with_write_or_edit(self):
        self.assertEqual(self.suite["allow_writes"], [".claude/handoff.md"])
        kinds = {f["kind"] for f in self.case["facts"]}
        # every kind but the ones only the feature-start-e2e suite uses
        self.assertEqual(kinds, set(self.checks.FACT_KINDS)
                         - {"hidden_tests", "unittest_green", "check",
                            "questions", "tool_uses", "trace_mentions"})

    def test_prepare_plants_the_facts(self):
        text = self.case["prepare"]
        for planted in ("worker job", "bookings.cancel()", "staging",
                        "0005_waitlist.sql", "0006", "waitlist_jobs.py",
                        "waitlist.promote", "/clear"):
            self.assertIn(planted, text)

    def test_fixture_is_large_halfway_and_green(self):
        files = [p for p in self.copy.rglob("*")
                 if p.is_file() and ".git" not in p.parts]
        self.assertGreaterEqual(len(files), 30)
        self.assertTrue((self.copy / "docs/structure.md").is_file())
        self.assertEqual(self.git("branch", "--show-current"),
                         "feature/plot-waitlist")
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.git("rev-list", "--count", "main..HEAD"), "2")
        self.assertTrue((self.copy / "migrations/0005_waitlist.sql").is_file())
        r = subprocess.run([sys.executable, "-m", "unittest", "discover",
                            "-s", "tests"], cwd=self.copy,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_fixture_has_no_links_or_secrets(self):
        for p in self.fixture.rglob("*"):
            if p.is_file():
                text = p.read_text(encoding="utf-8")
                self.assertNotRegex(
                    text, r"(?i)https?://|@(?!example\.org\b)[a-z]+\.|secret",
                    str(p))

    def test_untouched_copy_fails_only_the_work_facts(self):
        facts = self.facts()
        kinds = {f["id"]: f["kind"] for f in self.case["facts"]}
        for fid, ok in facts.items():
            self.assertEqual(ok, kinds[fid] != "matches", fid)

    def test_the_planted_path_passes_every_fact(self):
        self.edit("migrations/0006_waitlist_promoted_at.sql",
                  "ALTER TABLE waitlist_entries ADD COLUMN promoted_at TEXT;\n")
        self.edit("allotment/worker/waitlist_jobs.py",
                  "def promote_next(conn, payload, outbox):\n    pass\n")
        self.edit("allotment/worker/jobs.py",
                  '\nJOBS["waitlist.promote"] = None\n', append=True)
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com",
                 "commit", "-qm", "feat: promote")
        self.assertTrue(all(self.facts().values()), self.facts())

    def test_the_trap_and_the_rejected_path_fail(self):
        self.edit("migrations/0005_waitlist.sql",
                  "ALTER TABLE waitlist_entries ADD COLUMN promoted_at TEXT;\n",
                  append=True)
        self.edit("allotment/core/bookings.py",
                  "\n# promote inline\n", append=True)
        facts = self.facts("Done. Should I also add the API endpoints?")
        failed = {k for k, ok in facts.items() if not ok}
        for fid in ("trap_0005_untouched", "decision_not_inline",
                    "did_not_ask"):
            self.assertIn(fid, failed)


class FeatureStartE2eSuiteTest(unittest.TestCase):
    """End-to-end cases (feature-start overhead spec, decisions 12 and 13):
    the hidden tests must tell the unmodified fixture from the reference
    patch, checked through the same fact kinds a trial uses."""

    LEAKS = ("version", "header", "duplicate", "same name", "unknown", "empty")
    # per case: extra leak words on top of LEAKS, and the fixture package the
    # hidden tests must never import
    CASE_RULES = {
        "exclude-filter": {"leaks": (), "package": "listcli"},
        "persist-tags": {"leaks": (), "package": "listcli"},
        "waitlist": {"leaks": ("price", "concession", "email", "migrat",
                               "worker", "job", "inline", "transaction",
                               "twice", "again"),
                     "package": "allotment"},
    }

    def setUp(self):
        sys.path.insert(0, str(ROOT))
        from evals import checks, run
        self.checks, self.run = checks, run
        self.suite = load_suite(self, "feature-start-e2e")
        self.cases = {c["id"]: c for c in self.suite["cases"]}
        self.dir = EVALS / "cases" / "feature-start-e2e"

    def facts(self, case, patch=None):
        """The case's facts on a prepared copy of its fixture, with
        hidden/<case>/<patch> applied first when given."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "fx"
        self.run.prepare_fixture(
            EVALS / "fixtures" / case.get("fixture", self.suite["fixture"]),
            repo, run_setup=case.get("fixture_setup", True))
        base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        if patch:
            subprocess.run(["git", "-C", str(repo), "apply",
                            str(self.dir / "hidden" / case["id"] / patch)],
                           check=True, capture_output=True)
        facts = [dict(f, dir=str(self.dir / f["dir"])) if "dir" in f else f
                 for f in case["facts"]]
        return self.checks.fact_checks(repo, base, {}, facts)

    @staticmethod
    def hidden(facts):
        return {k: v for k, v in facts.items() if k.startswith("hidden:")}

    def test_cases(self):
        self.assertEqual(self.suite["skill"], "mayo-flow-feature-start")
        self.assertEqual(set(self.cases),
                         {"exclude-filter", "persist-tags", "waitlist"})
        self.assertEqual(self.cases["exclude-filter"].get(
            "fixture", self.suite["fixture"]), "list-cli")
        self.assertEqual(self.cases["persist-tags"]["fixture"],
                         "list-cli-trap")
        self.assertEqual(self.cases["waitlist"]["fixture"], "big-app")
        self.assertIs(self.cases["waitlist"]["fixture_setup"], False)

    def test_trap_fixture_has_a_shared_name_and_a_wrapped_file(self):
        data = json.loads((EVALS / "fixtures" / "list-cli-trap" / "data.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(data["version"], 2)
        names = [e["name"] for e in data["entries"]]
        self.assertEqual(names.count("milk"), 2)

    def test_naive_patch_falls_into_both_traps(self):
        # passes the visible tests, fails at least one test of each dictated
        # decision (the shared name and the file's header)
        case = self.cases["persist-tags"]
        facts = self.facts(case, "naive.patch")
        self.assertTrue(facts["visible_suite_green"])
        dictated = [d for d in case["decisions"] if not d.get("open")]
        self.assertEqual({d["id"] for d in dictated},
                         {"duplicate_name", "file_header"})
        for d in dictated:
            self.assertFalse(all(facts[t] for t in d["tests"]), d["id"])

    def test_case_shape(self):
        for cid, case in self.cases.items():
            self.assertTrue(case["prepare"].startswith(
                "/mayo-flow-feature-start {feature}"), cid)
            self.assertIn("{headless}", case["prepare"])
            self.assertIn("take its recommended answer yourself",
                          case["prepare"], cid)
            self.assertNotIn("grill", case["prepare"].lower(), cid)
            self.assertIn("{headless}", case["prompt"])
            self.assertEqual(case["direct"], "{feature}\n\n{headless}")
            self.assertIn("result_success", case["checks"])
            kinds = {f["kind"]: f for f in case["facts"]}
            self.assertEqual(kinds["hidden_tests"]["dir"], f"hidden/{cid}")
            self.assertIn("unittest_green", kinds)
            observed = {f["id"] for f in case["observe"]}
            for oid in ("grill_written", "baseline_wrote_spec",
                        "spec_written", "tickets_written",
                        "branch_is_feature", "work_committed", "questions",
                        "skill_calls", "hidden_seen"):
                self.assertIn(oid, observed, cid)
            obs = {f["id"]: f for f in case["observe"]}
            for oid in ("baseline_wrote_spec", "spec_written"):
                self.assertEqual(obs[oid]["glob"],
                                 "docs/10_features/[0-9]*/spec.md", (cid, oid))
            self.assertEqual(obs["tickets_written"]["glob"],
                             "docs/10_features/*/tickets/*.md", cid)

    def test_feature_text_does_not_leak(self):
        for cid, case in self.cases.items():
            for leak in self.LEAKS + self.CASE_RULES[cid]["leaks"]:
                self.assertNotIn(leak, case["feature"].lower(), (cid, leak))

    def test_direct_has_no_skill_words(self):
        # an HTTP route in backticks (`POST /waitlist`) is not a slash command
        route = re.compile(r"`(GET|POST|PUT|PATCH|DELETE) /[^`]*`")
        for cid, case in self.cases.items():
            direct = route.sub("", self.run.expand_prompts(case)["direct"])
            self.assertNotRegex(direct, AllSuitesTest.SKILL_WORDS, cid)

    def test_hidden_tests_never_import_their_fixture_package(self):
        for cid in self.cases:
            self.assertIn(cid, self.CASE_RULES, cid)
            package = self.CASE_RULES[cid]["package"]
            files = list((self.dir / "hidden" / cid).glob("*.py"))
            self.assertTrue(files, cid)
            for p in files:
                # real import statements only: a scenario script held in a
                # string runs in a subprocess (waitlist)
                tree = ast.parse(p.read_text(encoding="utf-8"))
                names = [a.name for n in ast.walk(tree)
                         if isinstance(n, ast.Import) for a in n.names]
                names += [n.module or "" for n in ast.walk(tree)
                          if isinstance(n, ast.ImportFrom)]
                for name in names:
                    self.assertNotEqual(name.split(".")[0], package, str(p))

    def test_unmodified_fixture_is_green_and_fails_every_hidden_test(self):
        for cid, case in self.cases.items():
            facts = self.facts(case)
            self.assertTrue(facts["visible_suite_green"], cid)
            self.assertTrue(self.hidden(facts), cid)
            self.assertEqual([k for k, ok in self.hidden(facts).items()
                              if ok], [], cid)

    def test_reference_patch_passes_everything(self):
        for cid, case in self.cases.items():
            facts = self.facts(case, "reference.patch")
            self.assertEqual([k for k, ok in facts.items() if not ok], [],
                             cid)

    def test_decisions_name_real_hidden_tests(self):
        for cid, case in self.cases.items():
            ids = set(self.hidden(self.facts(case)))
            self.assertTrue(any(d.get("open") for d in case["decisions"]))
            for d in case["decisions"]:
                self.assertTrue(d["text"].strip())
                if not d.get("open"):
                    self.assertTrue(d["tests"])
                    self.assertLessEqual(set(d["tests"]), ids, (cid, d["id"]))


class AllSuitesTest(unittest.TestCase):
    """Rubrics are outcome-based and skill-agnostic (spec step 8 addendum):
    the judge scores skill and baseline runs alike and must not learn which
    is which."""

    SUITES = sorted(p.name for p in (EVALS / "cases").iterdir() if p.is_dir())
    SKILL_WORDS = re.compile(r"mayo-flow|\bskill|grill|/[a-z]", re.I)

    def test_every_first_run_prompt_starts_with_its_skill(self):
        # the first call of a trial: `prepare` on two-phase cases. A later
        # `prompt` may be plain (feature-start-e2e implements from the spec).
        for name in self.SUITES:
            suite = load_suite(self, name)
            for case in suite["cases"]:
                first = case.get("prepare", case["prompt"])
                self.assertTrue(first.startswith("/" + suite["skill"]),
                                f"{name}/{case['id']}")

    def test_every_suite_has_a_rubric(self):
        for name in self.SUITES:
            with self.subTest(suite=name):
                path = EVALS / "cases" / name / "rubric.json"
                self.assertTrue(path.is_file(), f"missing {path}")
                crit = json.loads(path.read_text())["criteria"]
                self.assertIn(len(crit), (3, 4))
                ids = [c["id"] for c in crit]
                self.assertEqual(len(set(ids)), len(ids))
                for c in crit:
                    self.assertRegex(c["id"], r"^[a-z_]+$")
                    self.assertTrue(c["text"].strip())
                    self.assertNotRegex(c["text"], self.SKILL_WORDS)


if __name__ == "__main__":
    unittest.main()
