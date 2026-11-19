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


if __name__ == "__main__":
    unittest.main()
