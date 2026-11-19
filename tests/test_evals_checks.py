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


GOOD_IGNORE = "__pycache__/\n*.pyc\n.env\n.env.local\n.DS_Store\n"


class GitignoreTest(RepoCase):
    def test_exists(self):
        self.assertFalse(checks.gitignore_exists(self.repo))
        write(self.repo, ".gitignore", GOOD_IGNORE)
        self.assertTrue(checks.gitignore_exists(self.repo))

    def test_python_secrets_os_entries(self):
        write(self.repo, ".gitignore", GOOD_IGNORE)
        self.assertTrue(checks.gitignore_python(self.repo))
        self.assertTrue(checks.gitignore_secrets(self.repo))
        self.assertTrue(checks.gitignore_os(self.repo))

    def test_missing_entries(self):
        write(self.repo, ".gitignore", "*.log\n")
        self.assertFalse(checks.gitignore_python(self.repo))
        self.assertFalse(checks.gitignore_secrets(self.repo))
        self.assertFalse(checks.gitignore_os(self.repo))

    def test_no_file_means_no_entries(self):
        self.assertFalse(checks.gitignore_python(self.repo))
        self.assertFalse(checks.gitignore_secrets(self.repo))
        self.assertFalse(checks.gitignore_os(self.repo))

    def test_env_must_be_a_line_not_a_substring(self):
        write(self.repo, ".gitignore", "# .env later\nenvironment/\n")
        self.assertFalse(checks.gitignore_secrets(self.repo))

    def test_foreign_stacks(self):
        write(self.repo, ".gitignore", GOOD_IGNORE)
        self.assertTrue(checks.gitignore_only_python(self.repo))
        write(self.repo, ".gitignore", GOOD_IGNORE + "node_modules/\n")
        self.assertFalse(checks.gitignore_only_python(self.repo))

    def test_committed_on_its_own(self):
        write(self.repo, ".gitignore", GOOD_IGNORE)
        commit(self.repo, "chore: add gitignore")
        self.assertTrue(checks.gitignore_committed(self.repo))

    def test_not_committed(self):
        write(self.repo, ".gitignore", GOOD_IGNORE)
        self.assertFalse(checks.gitignore_committed(self.repo))

    def test_commit_mixed_with_code_is_not_on_its_own(self):
        write(self.repo, ".gitignore", GOOD_IGNORE)
        write(self.repo, "cli.py", "print(2)\n")
        commit(self.repo, "chore: add gitignore and code")
        self.assertFalse(checks.gitignore_committed(self.repo))

    def test_registered(self):
        for n in ("gitignore_exists", "gitignore_python", "gitignore_secrets",
                  "gitignore_os", "gitignore_only_python",
                  "gitignore_committed"):
            self.assertIn(n, checks.CHECKS)
            self.assertNotIn(n, checks.FEATURE_START)


HANDOFF = (
        "# Handoff - 2026-11-19 - main @ abc\n"
        "## Goal in one line\nx\n## Current state\nx\n## Next steps\n1. x\n"
        "## Waiting on the user\nnone\n## Rules in force\nno push\n"
        "## Pointers\nspec\n")


class HandoffTest(RepoCase):
    def test_exists(self):
        self.assertFalse(checks.handoff_exists(self.repo))
        write(self.repo, ".claude/handoff.md", HANDOFF)
        self.assertTrue(checks.handoff_exists(self.repo))

    def test_empty_file_does_not_exist(self):
        write(self.repo, ".claude/handoff.md", "")
        self.assertFalse(checks.handoff_exists(self.repo))

    def test_short(self):
        write(self.repo, ".claude/handoff.md", HANDOFF)
        self.assertTrue(checks.handoff_short(self.repo))
        write(self.repo, ".claude/handoff.md", HANDOFF + "x\n" * 60)
        self.assertFalse(checks.handoff_short(self.repo))

    def test_short_without_file(self):
        self.assertFalse(checks.handoff_short(self.repo))

    def test_sections(self):
        write(self.repo, ".claude/handoff.md", HANDOFF)
        self.assertTrue(checks.handoff_sections(self.repo))
        write(self.repo, ".claude/handoff.md",
              HANDOFF.replace("## Pointers", "## Links"))
        self.assertFalse(checks.handoff_sections(self.repo))

    def test_sections_without_file(self):
        self.assertFalse(checks.handoff_sections(self.repo))

    def test_excluded(self):
        write(self.repo, ".claude/handoff.md", HANDOFF)
        self.assertFalse(checks.handoff_excluded(self.repo))
        write(self.repo, ".git/info/exclude", ".claude/handoff.md\n")
        self.assertTrue(checks.handoff_excluded(self.repo))

    def test_no_new_commits(self):
        self.assertTrue(checks.no_new_commits(self.repo))
        write(self.repo, "a.txt")
        commit(self.repo, "chore: more")
        self.assertFalse(checks.no_new_commits(self.repo))

    def test_registered(self):
        for n in ("handoff_exists", "handoff_short", "handoff_sections",
                  "handoff_excluded", "no_new_commits"):
            self.assertIn(n, checks.CHECKS)
            self.assertNotIn(n, checks.FEATURE_START)


TICKET = """# {n}. Title {n}

**Status:** todo
**Blocked by:** {blocked}
**Touches:** cli.py

## Behavior
Works end to end.

## Acceptance criteria
- Observable.

## Tests
- A failing test first.
"""


def write_tickets(repo, *specs):
    """specs: (filename, number, blocked-by text)."""
    for name, n, blocked in specs:
        write(repo, f"{FOLDER}/tickets/{name}",
              TICKET.format(n=n, blocked=blocked))


class TicketsTest(RepoCase):
    def test_exist_needs_at_least_two_numbered_files(self):
        self.assertFalse(checks.tickets_exist(self.repo))
        write_tickets(self.repo, ("01_first.md", "01", "none"))
        self.assertFalse(checks.tickets_exist(self.repo))
        write_tickets(self.repo, ("02_second.md", "02", "01"))
        self.assertTrue(checks.tickets_exist(self.repo))

    def test_exist_ignores_badly_named_files(self):
        write_tickets(self.repo, ("first.md", "01", "none"),
                      ("2_second.md", "02", "none"))
        self.assertFalse(checks.tickets_exist(self.repo))

    def test_sections(self):
        write_tickets(self.repo, ("01_first.md", "01", "none"),
                      ("02_second.md", "02", "01"))
        self.assertTrue(checks.tickets_sections(self.repo))
        write(self.repo, f"{FOLDER}/tickets/02_second.md",
              TICKET.format(n="02", blocked="01").replace(
                  "## Tests", "## Testing"))
        self.assertFalse(checks.tickets_sections(self.repo))

    def test_sections_without_tickets(self):
        self.assertFalse(checks.tickets_sections(self.repo))

    def test_blockers_refer_to_existing_earlier_tickets(self):
        write_tickets(self.repo, ("01_first.md", "01", "none"),
                      ("02_second.md", "02", "01"),
                      ("03_third.md", "03", "01, 02"))
        self.assertTrue(checks.tickets_blockers_valid(self.repo))

    def test_blockers_to_missing_ticket_fail(self):
        write_tickets(self.repo, ("01_first.md", "01", "none"),
                      ("02_second.md", "02", "07"))
        self.assertFalse(checks.tickets_blockers_valid(self.repo))

    def test_blockers_on_itself_or_a_later_ticket_fail(self):
        write_tickets(self.repo, ("01_first.md", "01", "02"),
                      ("02_second.md", "02", "none"))
        self.assertFalse(checks.tickets_blockers_valid(self.repo))

    def test_blockers_without_tickets(self):
        self.assertFalse(checks.tickets_blockers_valid(self.repo))

    def test_no_code_changed(self):
        write_tickets(self.repo, ("01_first.md", "01", "none"))
        self.assertTrue(checks.no_code_changed(self.repo))
        write(self.repo, "cli.py", "print(2)\n")
        self.assertFalse(checks.no_code_changed(self.repo))

    def test_no_code_changed_sees_new_code_files(self):
        write(self.repo, "new_module.py")
        self.assertFalse(checks.no_code_changed(self.repo))

    def test_registered(self):
        for n in ("tickets_exist", "tickets_sections",
                  "tickets_blockers_valid", "no_code_changed"):
            self.assertIn(n, checks.CHECKS)
            self.assertNotIn(n, checks.FEATURE_START)


if __name__ == "__main__":
    unittest.main()
