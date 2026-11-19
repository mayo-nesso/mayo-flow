"""Check-function tests over hand-built git repos (stdlib only)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import checks  # noqa: E402

FOLDER = "docs/10_features/2026_11_18_list_exclude"


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t",
                    "-c", "user.email=t@example.com", *args],
                   check=True, capture_output=True)


def write(repo, rel, text="x\n"):
    p = Path(repo) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def commit(repo, msg):
    git(repo, "add", "-A")
    git(repo, "commit", "-m", msg)


class RepoCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        git(self.repo, "init", "-b", "main")
        write(self.repo, "cli.py", "print(1)\n")
        commit(self.repo, "chore: init")

    def good_feature(self):
        git(self.repo, "checkout", "-b", "feature/list-exclude")
        write(self.repo, f"{FOLDER}/grill.md", "g\n")
        write(self.repo, f"{FOLDER}/spec.md", "s\n")
        commit(self.repo, "docs: add feature spec")


class BranchTest(RepoCase):
    def test_feature_branch(self):
        self.good_feature()
        self.assertTrue(checks.branch_is_feature(self.repo))

    def test_main_is_not_feature(self):
        self.assertFalse(checks.branch_is_feature(self.repo))


class FolderTest(RepoCase):
    def test_found(self):
        self.good_feature()
        self.assertEqual(checks.feature_folder(self.repo), Path(self.repo) / FOLDER)

    def test_bad_name(self):
        write(self.repo, "docs/10_features/list_exclude/spec.md")
        self.assertIsNone(checks.feature_folder(self.repo))

    def test_archived_ignored(self):
        write(self.repo, "docs/10_features/archived/2026_01_01_old/spec.md")
        self.assertIsNone(checks.feature_folder(self.repo))


class DocsNonemptyTest(RepoCase):
    def test_both_present(self):
        self.good_feature()
        self.assertTrue(checks.docs_nonempty(self.repo))

    def test_empty_grill(self):
        self.good_feature()
        write(self.repo, f"{FOLDER}/grill.md", "")
        self.assertFalse(checks.docs_nonempty(self.repo))

    def test_missing_spec(self):
        self.good_feature()
        (Path(self.repo) / FOLDER / "spec.md").unlink()
        self.assertFalse(checks.docs_nonempty(self.repo))

    def test_no_folder(self):
        self.assertFalse(checks.docs_nonempty(self.repo))


class SpecCommitTest(RepoCase):
    def test_docs_prefix(self):
        self.good_feature()
        self.assertTrue(checks.spec_commit_is_docs(self.repo))

    def test_scoped_docs_prefix(self):
        git(self.repo, "checkout", "-b", "feature/x")
        write(self.repo, f"{FOLDER}/spec.md")
        commit(self.repo, "docs(spec): add spec")
        self.assertTrue(checks.spec_commit_is_docs(self.repo))

    def test_wrong_prefix(self):
        git(self.repo, "checkout", "-b", "feature/x")
        write(self.repo, f"{FOLDER}/spec.md")
        commit(self.repo, "feat: add spec")
        self.assertFalse(checks.spec_commit_is_docs(self.repo))

    def test_no_spec_commit(self):
        self.assertFalse(checks.spec_commit_is_docs(self.repo))


class NoCodeBeforeSpecTest(RepoCase):
    def test_docs_only(self):
        self.good_feature()
        write(self.repo, "cli.py", "print(2)\n")  # after spec: allowed
        commit(self.repo, "feat: later")
        self.assertTrue(checks.no_code_before_spec(self.repo))

    def test_code_before_spec(self):
        git(self.repo, "checkout", "-b", "feature/x")
        write(self.repo, "cli.py", "print(2)\n")
        commit(self.repo, "feat: code first")
        write(self.repo, f"{FOLDER}/spec.md")
        commit(self.repo, "docs: spec")
        self.assertFalse(checks.no_code_before_spec(self.repo))

    def test_code_in_spec_commit(self):
        git(self.repo, "checkout", "-b", "feature/x")
        write(self.repo, "cli.py", "print(2)\n")
        write(self.repo, f"{FOLDER}/spec.md")
        commit(self.repo, "docs: spec")
        self.assertFalse(checks.no_code_before_spec(self.repo))

    def test_no_spec_is_false(self):
        self.assertFalse(checks.no_code_before_spec(self.repo))


class TreeCleanTest(RepoCase):
    def test_clean(self):
        self.assertTrue(checks.tree_clean(self.repo))

    def test_untracked(self):
        write(self.repo, "new.txt")
        self.assertFalse(checks.tree_clean(self.repo))

    def test_modified(self):
        write(self.repo, "cli.py", "print(9)\n")
        self.assertFalse(checks.tree_clean(self.repo))


class ResultAndRunTest(RepoCase):
    ok = {"subtype": "success", "is_error": False}

    def test_result_success(self):
        self.assertTrue(checks.result_success(self.ok))
        self.assertFalse(checks.result_success({"subtype": "error_max_turns",
                                                "is_error": True}))
        self.assertFalse(checks.result_success({"subtype": None,
                                                "is_error": None}))

    def test_run_checks_all_pass(self):
        self.good_feature()
        res = checks.run_checks(self.repo, self.ok)
        self.assertEqual(set(res), {
            "branch_is_feature", "feature_folder", "docs_nonempty",
            "spec_commit_is_docs", "no_code_before_spec", "tree_clean",
            "result_success"})
        self.assertTrue(all(v is True for v in res.values()), res)

    def test_run_checks_failures_are_bools(self):
        res = checks.run_checks(self.repo, {"subtype": None, "is_error": None})
        self.assertEqual({k for k, v in res.items() if v}, {"tree_clean"})
        self.assertFalse(res["branch_is_feature"])
        self.assertFalse(res["feature_folder"])


class SelectedChecksTest(RepoCase):
    ok = {"subtype": "success", "is_error": False}

    def test_names_select_a_subset(self):
        res = checks.run_checks(self.repo, self.ok,
                                ["tree_clean", "result_success"])
        self.assertEqual(res, {"tree_clean": True, "result_success": True})

    def test_unknown_name_fails_fast(self):
        with self.assertRaises(KeyError):
            checks.run_checks(self.repo, self.ok, ["nope"])

    def test_no_names_keeps_the_feature_start_set(self):
        res = checks.run_checks(self.repo, self.ok)
        self.assertEqual(set(res), set(checks.FEATURE_START))


class ReportsTest(unittest.TestCase):
    def t(self, text):
        return {"result_text": text}

    def test_reports_pass(self):
        self.assertTrue(checks.reports_pass(self.t("The full suite passed.")))
        self.assertTrue(checks.reports_pass(self.t("3 tests pass, 0 failures")))

    def test_pass_claim_rejects_a_failure(self):
        self.assertFalse(checks.reports_pass(self.t("1 failed, 2 passed")))
        self.assertFalse(checks.reports_pass(self.t("No tests configured.")))
        self.assertFalse(checks.reports_pass(self.t(None)))

    def test_reports_fail(self):
        self.assertTrue(checks.reports_fail(self.t("test_add failed")))
        self.assertTrue(checks.reports_fail(self.t("1 failed, 2 passed")))

    def test_fail_claim_ignores_zero_failures(self):
        self.assertFalse(checks.reports_fail(self.t("All passed, 0 failures")))
        self.assertFalse(checks.reports_fail(self.t("no failures")))
        self.assertFalse(checks.reports_fail(self.t(None)))

    def test_registered(self):
        self.assertIn("reports_pass", checks.CHECKS)
        self.assertIn("reports_fail", checks.CHECKS)
        self.assertNotIn("reports_pass", checks.FEATURE_START)


if __name__ == "__main__":
    unittest.main()
