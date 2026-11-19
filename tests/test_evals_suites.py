"""The shipped feature-start suite and its fixture are well-formed."""
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
        (case,) = self.suite["cases"]
        self.assertEqual(case["id"], "write")
        self.assertIn("/mayo-flow-handoff", case["prompt"])
        self.assertIn("headless", case["prompt"])
        for name in ("handoff_exists", "handoff_short", "handoff_sections",
                     "handoff_excluded", "no_new_commits", "tree_clean",
                     "result_success"):
            self.assertIn(name, case["checks"])


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
        (case,) = self.suite["cases"]
        self.assertIn("/mayo-flow-branch-finish", case["prompt"])
        self.assertIn("headless", case["prompt"])
        for name in ("on_main", "merged_no_ff", "spec_archived",
                     "spec_completed_marker", "archive_commit_is_docs",
                     "feature_branch_deleted", "reports_pass", "tree_clean",
                     "result_success"):
            self.assertIn(name, case["checks"])


class AllSuitesTest(unittest.TestCase):
    """Rubrics are outcome-based and skill-agnostic (spec step 8 addendum):
    the judge scores skill and baseline runs alike and must not learn which
    is which."""

    SUITES = sorted(p.name for p in (EVALS / "cases").iterdir() if p.is_dir())
    SKILL_WORDS = re.compile(r"mayo-flow|\bskill|grill|/[a-z]", re.I)

    def test_every_case_prompt_starts_with_its_skill(self):
        for name in self.SUITES:
            suite = load_suite(self, name)
            for case in suite["cases"]:
                self.assertTrue(
                    case["prompt"].startswith("/" + suite["skill"]),
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
