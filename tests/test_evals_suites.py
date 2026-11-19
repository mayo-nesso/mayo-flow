"""The shipped feature-start suite and its fixture are well-formed."""
import json
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


if __name__ == "__main__":
    unittest.main()
