"""Check-function tests over hand-built git repos (stdlib only)."""
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
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

    def test_reports_pass_in_the_phrasings_real_replies_use(self):
        self.assertTrue(checks.reports_pass(
            self.t("ran 2 tests, all passing. pytest isn't installed")))
        self.assertTrue(checks.reports_pass(self.t(
            "the full suite passes. The `python -m pytest` run failed with "
            "a pyenv error, so I used unittest instead.")))

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

    def test_fail_claim_ignores_a_runner_error(self):
        self.assertFalse(checks.reports_fail(self.t(
            "the pytest run failed with a pyenv error")))
        self.assertTrue(checks.reports_fail(self.t("test_add failed")))

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


PLAN = "docs/20_fix-plans/2026_11_19_tag_case.md"
PLAN_TEXT = """# Tag filter ignores case

**Reported as:** `--tag Dairy` lists nothing.

## 1. Case-sensitive match

**Files:** listcli/store.py:10

**Problem:** compares tags verbatim.

**Effect:** capitalised tags find nothing.

**Fix:** compare lower-cased tags.

## Not investigated / out of scope
Nothing.
"""


class FixStartTest(RepoCase):
    def start_fix(self, branch="fix/tag-case"):
        git(self.repo, "checkout", "-b", branch)

    def test_branch_is_fix(self):
        self.assertFalse(checks.branch_is_fix(self.repo))
        self.start_fix()
        self.assertTrue(checks.branch_is_fix(self.repo))

    def test_fix_plan_exists(self):
        self.assertFalse(checks.fix_plan_exists(self.repo))
        write(self.repo, PLAN, PLAN_TEXT)
        self.assertTrue(checks.fix_plan_exists(self.repo))

    def test_fix_plan_must_be_dated_and_not_archived(self):
        write(self.repo, "docs/20_fix-plans/tag_case.md", PLAN_TEXT)
        write(self.repo, "docs/20_fix-plans/archived/2026_11_19_x.md",
              PLAN_TEXT)
        self.assertFalse(checks.fix_plan_exists(self.repo))

    def test_fix_plan_empty_does_not_count(self):
        write(self.repo, PLAN, "")
        self.assertFalse(checks.fix_plan_exists(self.repo))

    def test_fix_plan_sections(self):
        self.assertFalse(checks.fix_plan_sections(self.repo))
        write(self.repo, PLAN, PLAN_TEXT)
        self.assertTrue(checks.fix_plan_sections(self.repo))
        write(self.repo, PLAN, PLAN_TEXT.replace("**Problem:**", "**Why:**"))
        self.assertFalse(checks.fix_plan_sections(self.repo))

    def test_fix_plan_commit_alone(self):
        self.start_fix()
        write(self.repo, PLAN, PLAN_TEXT)
        commit(self.repo, "docs: add fix plan for tag-case")
        self.assertTrue(checks.fix_plan_commit_alone(self.repo))

    def test_fix_plan_commit_may_add_archived_gitkeep(self):
        # the skill creates docs/20_fix-plans/archived/ when it is missing
        self.start_fix()
        write(self.repo, PLAN, PLAN_TEXT)
        write(self.repo, "docs/20_fix-plans/archived/.gitkeep", "")
        commit(self.repo, "docs: add fix plan for tag-case")
        self.assertTrue(checks.fix_plan_commit_alone(self.repo))

    def test_fix_plan_commit_with_code_is_not_alone(self):
        self.start_fix()
        write(self.repo, PLAN, PLAN_TEXT)
        write(self.repo, "cli.py", "print(2)\n")
        commit(self.repo, "docs: add fix plan for tag-case")
        self.assertFalse(checks.fix_plan_commit_alone(self.repo))

    def test_fix_plan_commit_must_be_docs(self):
        self.start_fix()
        write(self.repo, PLAN, PLAN_TEXT)
        commit(self.repo, "fix: tag case")
        self.assertFalse(checks.fix_plan_commit_alone(self.repo))

    def test_fix_plan_commit_missing(self):
        self.start_fix()
        self.assertFalse(checks.fix_plan_commit_alone(self.repo))

    def test_branch_docs_only(self):
        self.start_fix()
        self.assertFalse(checks.branch_docs_only(self.repo))  # no commit yet
        write(self.repo, PLAN, PLAN_TEXT)
        commit(self.repo, "docs: add fix plan for tag-case")
        self.assertTrue(checks.branch_docs_only(self.repo))
        write(self.repo, "cli.py", "print(2)\n")
        commit(self.repo, "fix: tag case")
        self.assertFalse(checks.branch_docs_only(self.repo))

    def test_registered(self):
        for n in ("branch_is_fix", "fix_plan_exists", "fix_plan_sections",
                  "fix_plan_commit_alone", "branch_docs_only"):
            self.assertIn(n, checks.CHECKS)
            self.assertNotIn(n, checks.FEATURE_START)


class ProjectInitTest(RepoCase):
    def scaffold(self):
        for d in ("00_phases", "10_features/archived", "20_fix-plans/archived",
                  "50_audits/archived"):
            (self.repo / "docs" / d).mkdir(parents=True)
        write(self.repo, "docs/PLAN.md", "# Plan\n")
        write(self.repo, "docs/structure.md", "# Structure\n")
        write(self.repo, "CLAUDE.md",
              "docs/10_features docs/20_fix-plans docs/50_audits\n")

    def test_branch_is_scaffold(self):
        self.assertFalse(checks.branch_is_scaffold(self.repo))
        git(self.repo, "checkout", "-b", "feature/repo-scaffolding")
        self.assertTrue(checks.branch_is_scaffold(self.repo))
        git(self.repo, "checkout", "-b", "chore/repo-scaffolding")
        self.assertTrue(checks.branch_is_scaffold(self.repo))
        git(self.repo, "checkout", "-b", "fix/other")
        self.assertFalse(checks.branch_is_scaffold(self.repo))

    def test_lifecycle_folders(self):
        self.assertFalse(checks.docs_lifecycle(self.repo))
        self.scaffold()
        self.assertTrue(checks.docs_lifecycle(self.repo))

    def test_lifecycle_folders_need_every_one(self):
        self.scaffold()
        (self.repo / "docs/50_audits/archived").rmdir()
        (self.repo / "docs/50_audits").rmdir()
        self.assertFalse(checks.docs_lifecycle(self.repo))

    def test_docs_core_files(self):
        self.assertFalse(checks.docs_core_files(self.repo))
        self.scaffold()
        self.assertTrue(checks.docs_core_files(self.repo))

    def test_docs_core_files_not_in_root(self):
        write(self.repo, "PLAN.md", "# Plan\n")
        write(self.repo, "structure.md", "# S\n")
        self.assertFalse(checks.docs_core_files(self.repo))

    def test_docs_core_files_nonempty(self):
        self.scaffold()
        write(self.repo, "docs/PLAN.md", "")
        self.assertFalse(checks.docs_core_files(self.repo))

    def test_claude_md_names_the_lifecycle(self):
        self.assertFalse(checks.claude_md_lifecycle(self.repo))
        self.scaffold()
        self.assertTrue(checks.claude_md_lifecycle(self.repo))
        write(self.repo, "CLAUDE.md", "docs/10_features only\n")
        self.assertFalse(checks.claude_md_lifecycle(self.repo))

    def test_commits_conventional(self):
        git(self.repo, "checkout", "-b", "feature/repo-scaffolding")
        self.assertFalse(checks.commits_conventional(self.repo))  # none yet
        write(self.repo, "a.txt")
        commit(self.repo, "chore: add .gitignore for python")
        write(self.repo, "b.txt")
        commit(self.repo, "docs(plan): add PLAN")
        self.assertTrue(checks.commits_conventional(self.repo))
        write(self.repo, "c.txt")
        commit(self.repo, "Add claude file")
        self.assertFalse(checks.commits_conventional(self.repo))

    def test_registered(self):
        for n in ("branch_is_scaffold", "docs_lifecycle", "docs_core_files",
                  "claude_md_lifecycle", "commits_conventional"):
            self.assertIn(n, checks.CHECKS)
            self.assertNotIn(n, checks.FEATURE_START)


class BranchFinishTest(RepoCase):
    SPEC = f"{FOLDER}/spec.md"
    ARCHIVED = f"docs/10_features/archived/{FOLDER.rsplit('/', 1)[1]}"

    def feature_branch(self):
        git(self.repo, "checkout", "-b", "feature/list-exclude")
        write(self.repo, self.SPEC, "# Spec\n")
        commit(self.repo, "docs: add spec")
        write(self.repo, "cli.py", "print(2)\n")
        commit(self.repo, "feat: exclude")

    def finish(self, marker="**Completed:** 2026-11-19\n", subject=None,
               delete=True, ff=False):
        """What the skill does: archive on the branch, merge, delete."""
        self.feature_branch()
        (self.repo / FOLDER).rename(self.repo / "tmp_spec")
        (self.repo / "docs/10_features/archived").mkdir(parents=True)
        (self.repo / "tmp_spec").rename(self.repo / self.ARCHIVED)
        write(self.repo, f"{self.ARCHIVED}/spec.md", marker + "# Spec\n")
        commit(self.repo, subject or "docs: archive list-exclude spec")
        git(self.repo, "checkout", "main")
        git(self.repo, "merge", "--ff" if ff else "--no-ff", "-m",
            "Merge feature/list-exclude into main", "feature/list-exclude")
        if delete:
            git(self.repo, "branch", "-d", "feature/list-exclude")

    def test_on_main(self):
        self.assertTrue(checks.on_main(self.repo))
        git(self.repo, "checkout", "-b", "feature/x")
        self.assertFalse(checks.on_main(self.repo))

    def test_merged_no_ff(self):
        self.assertFalse(checks.merged_no_ff(self.repo))
        self.finish()
        self.assertTrue(checks.merged_no_ff(self.repo))

    def test_no_ff_merge_survives_later_commits_on_main(self):
        self.finish()
        write(self.repo, "NOTES.md", "fixup\n")
        commit(self.repo, "docs: fix marker")
        self.assertTrue(checks.merged_no_ff(self.repo))

    def test_fast_forward_then_commit_is_not_a_no_ff_merge(self):
        self.finish(ff=True)
        write(self.repo, "NOTES.md", "fixup\n")
        commit(self.repo, "docs: fix marker")
        self.assertFalse(checks.merged_no_ff(self.repo))

    def test_fast_forward_is_not_a_no_ff_merge(self):
        self.finish(ff=True)
        self.assertFalse(checks.merged_no_ff(self.repo))

    def test_spec_archived(self):
        self.feature_branch()
        self.assertFalse(checks.spec_archived(self.repo))  # still in place
        git(self.repo, "checkout", "main")
        git(self.repo, "branch", "-D", "feature/list-exclude")
        self.assertFalse(checks.spec_archived(self.repo))

    def test_spec_archived_after_finish(self):
        self.finish()
        self.assertTrue(checks.spec_archived(self.repo))

    def test_spec_archived_but_also_left_in_place(self):
        self.finish()
        write(self.repo, self.SPEC, "# copy\n")
        self.assertFalse(checks.spec_archived(self.repo))

    def test_completed_marker(self):
        self.finish()
        self.assertTrue(checks.spec_completed_marker(self.repo))

    def test_completed_marker_missing(self):
        self.finish(marker="")
        self.assertFalse(checks.spec_completed_marker(self.repo))

    def test_archive_commit_is_docs(self):
        self.finish()
        self.assertTrue(checks.archive_commit_is_docs(self.repo))

    def test_archive_commit_not_docs(self):
        self.finish(subject="chore: tidy")
        self.assertFalse(checks.archive_commit_is_docs(self.repo))

    def test_archive_commit_without_merge(self):
        self.assertFalse(checks.archive_commit_is_docs(self.repo))

    def test_feature_branch_deleted(self):
        self.finish()
        self.assertTrue(checks.feature_branch_deleted(self.repo))

    def test_feature_branch_kept(self):
        self.finish(delete=False)
        self.assertFalse(checks.feature_branch_deleted(self.repo))

    def test_registered(self):
        for n in ("on_main", "merged_no_ff", "spec_archived",
                  "spec_completed_marker", "archive_commit_is_docs",
                  "feature_branch_deleted"):
            self.assertIn(n, checks.CHECKS)
            self.assertNotIn(n, checks.FEATURE_START)


class BranchFinishStatesTest(RepoCase):
    """Checks for the unfinished and audit-due branch-finish cases."""
    TICKETS = f"{FOLDER}/tickets"

    def ticket(self, n, title, status):
        write(self.repo, f"{self.TICKETS}/{n:02d}_{title.lower()}.md",
              f"# {n}. {title}\n\n**Status:** {status}\n")

    def partial_branch(self):
        git(self.repo, "checkout", "-b", "feature/list-exclude")
        write(self.repo, f"{FOLDER}/spec.md", "# Spec\n")
        self.ticket(1, "Code", "done")
        self.ticket(2, "Docs", "todo")
        commit(self.repo, "docs: add spec")

    def t(self, text):
        return {"result_text": text}

    def test_main_untouched(self):
        self.assertTrue(checks.main_untouched(self.repo))
        self.partial_branch()
        self.assertTrue(checks.main_untouched(self.repo))
        git(self.repo, "checkout", "main")
        git(self.repo, "merge", "--no-ff", "-m", "m", "feature/list-exclude")
        self.assertFalse(checks.main_untouched(self.repo))

    def test_spec_not_archived(self):
        self.assertFalse(checks.spec_not_archived(self.repo))  # no folder
        self.partial_branch()
        self.assertTrue(checks.spec_not_archived(self.repo))
        archived = self.repo / "docs/10_features/archived"
        archived.mkdir(parents=True)
        (self.repo / FOLDER).rename(archived / "2026_11_18_list_exclude")
        self.assertFalse(checks.spec_not_archived(self.repo))

    def test_done_marker(self):
        self.partial_branch()
        self.assertFalse(checks.done_marker(self.repo))
        write(self.repo, f"{FOLDER}/spec.md",
              "# Spec\n\n1. Code **Done \u2014 2026-11-19 (`abc1234`)**\n")
        self.assertTrue(checks.done_marker(self.repo))

    def test_done_marker_needs_date(self):
        self.partial_branch()
        write(self.repo, f"{FOLDER}/spec.md", "# Spec\n\nDone later\n")
        self.assertFalse(checks.done_marker(self.repo))

    def test_open_items_left(self):
        self.partial_branch()
        self.assertTrue(checks.open_items_left(self.repo))
        self.ticket(2, "Docs", "done")
        self.assertFalse(checks.open_items_left(self.repo))

    def test_open_items_left_without_tickets(self):
        self.assertFalse(checks.open_items_left(self.repo))

    def test_reports_open_tickets(self):
        self.partial_branch()
        self.assertTrue(checks.reports_open_tickets(
            self.repo, self.t("Follow-up: ticket 2, Docs, is still todo.")))
        self.assertFalse(checks.reports_open_tickets(
            self.repo, self.t("Merged and archived; all done.")))

    def test_reports_open_tickets_by_number(self):
        self.partial_branch()
        self.assertTrue(checks.reports_open_tickets(
            self.repo, self.t("Ticket 02 is still open.")))
        self.assertTrue(checks.reports_open_tickets(
            self.repo, self.t("Ticket #2 is still open.")))
        self.assertFalse(checks.reports_open_tickets(
            self.repo, self.t("Ticket 12 is fine.")))

    def test_reports_open_tickets_by_file_name(self):
        self.partial_branch()
        self.assertTrue(checks.reports_open_tickets(
            self.repo, self.t("Left open: 02_docs.md")))

    def test_proposes_audit(self):
        self.assertTrue(checks.proposes_audit(self.t(
            "An audit is due (11 merges); I propose running mayo-flow-audit.")))
        self.assertTrue(checks.proposes_audit(self.t(
            "Want me to run an audit? 11 merges since the start.")))
        self.assertTrue(checks.proposes_audit(self.t(
            "11 merges and no audit summary exists yet, so an audit is due; "
            "I propose mayo-flow-audit and have not run it.")))
        self.assertFalse(checks.proposes_audit(self.t("Merged. Tests pass.")))
        self.assertFalse(checks.proposes_audit(self.t(
            "An audit is not due yet (3 merges).")))

    def test_proposes_audit_rejects_a_skipped_check(self):
        self.assertFalse(checks.proposes_audit(self.t(
            "Merged. I didn't check whether a periodic audit is due.")))
        self.assertFalse(checks.proposes_audit(self.t(
            "Merged. I did not check if an audit is due.")))
        self.assertFalse(checks.proposes_audit(self.t(
            "The audit-due check found no folder, so I didn't run one.")))
        self.assertFalse(checks.proposes_audit(self.t(
            "I didn't run an audit or check whether one was due.")))

    def test_no_audit_report(self):
        self.assertTrue(checks.no_audit_report(self.repo))
        write(self.repo, "docs/50_audits/archived/.gitkeep", "")
        self.assertTrue(checks.no_audit_report(self.repo))
        write(self.repo, "docs/50_audits/2026_11_20_summary.md", "# s\n")
        self.assertFalse(checks.no_audit_report(self.repo))

    def test_no_audit_report_any_file_in_audits_folder(self):
        write(self.repo, "docs/50_audits/2026_11_20_security.md", "# s\n")
        self.assertFalse(checks.no_audit_report(self.repo))

    def test_registered(self):
        for n in ("main_untouched", "spec_not_archived", "done_marker",
                  "open_items_left", "reports_open_tickets",
                  "proposes_audit", "no_audit_report"):
            self.assertIn(n, checks.CHECKS)
            self.assertNotIn(n, checks.FEATURE_START)


class FactChecksTest(RepoCase):
    """Fact checks from a case file, evaluated against the base commit."""

    def setUp(self):
        super().setUp()
        write(self.repo, "core/cancel.py", "def cancel(): pass\n")
        write(self.repo, "worker/jobs.py", "JOBS = {}\n")
        commit(self.repo, "feat: base")
        self.base = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
            capture_output=True, text=True).stdout.strip()

    def run_fact(self, fact, trace=None):
        return checks.fact_checks(self.repo, self.base, trace or {},
                                  [dict(fact, id="f")])["f"]

    def test_unchanged(self):
        fact = {"kind": "unchanged", "paths": ["core/cancel.py", "cli.py"]}
        self.assertTrue(self.run_fact(fact))
        write(self.repo, "core/cancel.py", "def cancel(): promote()\n")
        self.assertFalse(self.run_fact(fact))  # uncommitted edit counts

    def test_unchanged_fails_when_deleted_or_committed(self):
        fact = {"kind": "unchanged", "paths": ["cli.py"]}
        (self.repo / "cli.py").unlink()
        self.assertFalse(self.run_fact(fact))
        commit(self.repo, "chore: drop cli")
        self.assertFalse(self.run_fact(fact))

    def test_matches_any_file_of_the_glob(self):
        fact = {"kind": "matches", "glob": "worker/*.py",
                "pattern": r"^def promote_next"}
        self.assertFalse(self.run_fact(fact))
        write(self.repo, "worker/promote.py", "x = 1\ndef promote_next(): pass\n")
        self.assertTrue(self.run_fact(fact))

    def test_dated_spec_glob_ignores_archived_specs(self):
        fact = {"kind": "matches",
                "glob": "docs/10_features/[0-9]*/spec.md", "pattern": "."}
        write(self.repo, "docs/10_features/archived/2026_01_01_old/spec.md",
              "# old\n")
        self.assertFalse(self.run_fact(fact))
        write(self.repo, "docs/10_features/2026_11_25_new/spec.md", "# new\n")
        self.assertTrue(self.run_fact(fact))

    def test_matches_without_a_file(self):
        self.assertFalse(self.run_fact(
            {"kind": "matches", "glob": "migrations/0006_*.sql",
             "pattern": "promoted_at"}))

    def test_kept_history(self):
        fact = {"kind": "kept_history"}
        write(self.repo, "a.py")
        commit(self.repo, "feat: more")
        self.assertTrue(self.run_fact(fact))
        git(self.repo, "reset", "-q", "--hard", "HEAD~2")
        self.assertFalse(self.run_fact(fact))

    def test_no_question(self):
        fact = {"kind": "no_question"}
        self.assertTrue(self.run_fact(fact, {"result_text": "Done? Yes.\nAll set."}))
        self.assertFalse(self.run_fact(
            fact, {"result_text": "Done.\n\nShould I also add the API?\n"}))
        self.assertTrue(self.run_fact(fact, {"result_text": None}))

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            self.run_fact({"kind": "nope"})


if __name__ == "__main__":
    unittest.main()


class BranchFinishSafetyTest(RepoCase):
    """Checks for the dirty-tree, parent-feature and remote branch-finish
    cases."""
    CHILD_SPEC = "docs/10_features/2026_11_19_subtract"
    PARENT_SPEC = "docs/10_features/2026_11_10_calc_ops"
    ARCHIVED = "docs/10_features/archived"

    def t(self, text):
        return {"result_text": text}

    # dirty tree
    def dirty_branch(self):
        write(self.repo, checks.DIRTY_TRACKED, "# calc\n")
        commit(self.repo, "docs: readme")
        git(self.repo, "checkout", "-b", "feature/subtract")
        write(self.repo, checks.DIRTY_TRACKED, "# calc\n" + checks.DIRTY_LINE)
        write(self.repo, checks.DIRTY_UNTRACKED, checks.DIRTY_UNTRACKED_TEXT)

    def test_dirty_preserved(self):
        self.dirty_branch()
        self.assertTrue(checks.dirty_preserved(self.repo))

    def test_dirty_preserved_fails_when_committed(self):
        self.dirty_branch()
        commit(self.repo, "wip")
        self.assertFalse(checks.dirty_preserved(self.repo))

    def test_dirty_preserved_fails_when_stashed(self):
        self.dirty_branch()
        git(self.repo, "stash", "-u")
        self.assertFalse(checks.dirty_preserved(self.repo))

    def test_dirty_preserved_fails_when_untracked_file_altered(self):
        self.dirty_branch()
        write(self.repo, checks.DIRTY_UNTRACKED, "changed\n")
        self.assertFalse(checks.dirty_preserved(self.repo))

    def test_dirty_preserved_fails_when_discarded(self):
        self.dirty_branch()
        git(self.repo, "checkout", "--", checks.DIRTY_TRACKED)
        self.assertFalse(checks.dirty_preserved(self.repo))

    def test_reports_dirty(self):
        for text in ("Stopped: the working tree has uncommitted changes.",
                     "There is an untracked file, so I did not merge.",
                     "The tree is dirty."):
            self.assertTrue(checks.reports_dirty(self.t(text)), text)
        self.assertFalse(checks.reports_dirty(
            self.t("Merged feature/subtract into main; tests pass.")))
        self.assertFalse(checks.reports_dirty(
            self.t("Merged. The working tree is clean.")))

    # parent feature
    def parent_branches(self):
        git(self.repo, "checkout", "-b", "feature/calc-ops")
        write(self.repo, f"{self.PARENT_SPEC}/spec.md", "# Calc ops\n")
        commit(self.repo, "docs: add spec for calc ops")
        git(self.repo, "checkout", "-b", "feature/subtract")
        write(self.repo, f"{self.CHILD_SPEC}/spec.md", "# Subtract\n")
        commit(self.repo, "docs: add spec for subtract")

    def finish_child(self, target, archive=True, delete=True):
        self.parent_branches()
        if archive:
            (self.repo / self.ARCHIVED).mkdir(parents=True)
            (self.repo / self.CHILD_SPEC).rename(
                self.repo / self.ARCHIVED / "2026_11_19_subtract")
            write(self.repo, f"{self.ARCHIVED}/2026_11_19_subtract/spec.md",
                  "**Completed:** 2026-11-19\n# Subtract\n")
            commit(self.repo, "docs: archive subtract spec")
        git(self.repo, "checkout", target)
        git(self.repo, "merge", "--no-ff", "-m", "m", "feature/subtract")
        if delete:
            git(self.repo, "branch", "-d", "feature/subtract")

    def test_on_parent(self):
        self.parent_branches()
        self.assertFalse(checks.on_parent(self.repo))
        git(self.repo, "checkout", "feature/calc-ops")
        self.assertTrue(checks.on_parent(self.repo))

    def test_child_branch_deleted(self):
        self.finish_child("feature/calc-ops", delete=False)
        self.assertFalse(checks.child_branch_deleted(self.repo))
        git(self.repo, "branch", "-d", "feature/subtract")
        self.assertTrue(checks.child_branch_deleted(self.repo))

    def test_parent_branch_kept(self):
        self.finish_child("feature/calc-ops")
        self.assertTrue(checks.parent_branch_kept(self.repo))
        git(self.repo, "checkout", "main")
        git(self.repo, "branch", "-D", "feature/calc-ops")
        self.assertFalse(checks.parent_branch_kept(self.repo))

    def test_child_spec_archived(self):
        self.finish_child("feature/calc-ops")
        self.assertTrue(checks.child_spec_archived(self.repo))

    def test_child_spec_archived_needs_marker_and_move(self):
        self.finish_child("feature/calc-ops", archive=False)
        self.assertFalse(checks.child_spec_archived(self.repo))
        write(self.repo, f"{self.ARCHIVED}/2026_11_19_subtract/spec.md",
              "# Subtract\n")
        self.assertFalse(checks.child_spec_archived(self.repo))

    def test_parent_spec_not_archived(self):
        self.finish_child("feature/calc-ops")
        self.assertTrue(checks.parent_spec_not_archived(self.repo))
        (self.repo / self.PARENT_SPEC).rename(
            self.repo / self.ARCHIVED / "2026_11_10_calc_ops")
        self.assertFalse(checks.parent_spec_not_archived(self.repo))

    def test_no_audit_proposal(self):
        self.assertTrue(checks.no_audit_proposal(
            self.t("Merged into feature/calc-ops; the audit check does not "
                   "apply to a parent branch.")))
        self.assertFalse(checks.no_audit_proposal(
            self.t("An audit is due; want me to run it?")))

    # remote
    def remote_repo(self, hook=True):
        self.origin = self.repo.parent / (self.repo.name + "-origin.git")
        git(self.repo, "init", "--bare", "-b", "main", str(self.origin))
        git(self.repo, "remote", "add", "origin", str(self.origin))
        git(self.repo, "push", "origin", "main")
        git(self.repo, "checkout", "-b", "feature/subtract")
        write(self.repo, "calc.py", "x = 2\n")
        commit(self.repo, "feat: sub")
        git(self.repo, "push", "origin", "feature/subtract")
        if hook:
            h = self.origin / "hooks" / "update"
            shutil.copy(ROOT / "evals/remote_update_hook.sh", h)

    def merge_local(self):
        git(self.repo, "checkout", "main")
        git(self.repo, "merge", "--no-ff", "-m", "m", "feature/subtract")
        git(self.repo, "branch", "-d", "feature/subtract")

    def test_remote_branch_kept(self):
        self.remote_repo(hook=False)
        self.merge_local()
        self.assertTrue(checks.remote_branch_kept(self.repo))
        git(self.repo, "push", "origin", "--delete", "feature/subtract")
        self.assertFalse(checks.remote_branch_kept(self.repo))

    def test_remote_destructive_push_is_logged_and_refused(self):
        self.remote_repo()
        self.merge_local()
        self.assertTrue(checks.remote_not_rewritten(self.repo))
        r = subprocess.run(["git", "-C", str(self.repo), "push", "origin",
                            "--delete", "feature/subtract"],
                           capture_output=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(checks.remote_branch_kept(self.repo))
        self.assertFalse(checks.remote_not_rewritten(self.repo))

    def test_remote_force_push_is_refused_and_logged(self):
        self.remote_repo()
        git(self.repo, "commit", "--amend", "-m", "feat: sub, reworded")
        r = subprocess.run(["git", "-C", str(self.repo), "push", "--force",
                            "origin", "feature/subtract"],
                           capture_output=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(checks.remote_not_rewritten(self.repo))

    def test_main_not_pushed(self):
        self.remote_repo()
        self.merge_local()
        self.assertTrue(checks.main_not_pushed(self.repo))
        git(self.repo, "push", "origin", "main")
        self.assertFalse(checks.main_not_pushed(self.repo))

    def test_registered(self):
        for n in ("dirty_preserved", "reports_dirty", "on_parent",
                  "child_branch_deleted", "parent_branch_kept",
                  "child_spec_archived", "parent_spec_not_archived",
                  "no_audit_proposal", "remote_branch_kept",
                  "remote_not_rewritten", "main_not_pushed"):
            self.assertIn(n, checks.CHECKS)
            self.assertNotIn(n, checks.FEATURE_START)
        for n in ("reports_dirty", "no_audit_proposal"):
            self.assertIn(n, checks.TRACE_CHECKS)


HIDDEN_TESTS = """import os
import unittest


class CliTest(unittest.TestCase):
    def test_passes(self):
        self.assertTrue(True)

    def test_fails(self):
        self.assertEqual(1, 2)
"""


class HiddenTestsTest(RepoCase):
    """`hidden_tests` runs a folder of tests against the repo in a
    subprocess; `unittest_green` runs the repo's own suite."""

    def setUp(self):
        super().setUp()
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.hidden = Path(t.name)
        self.base = "main"

    def hidden_file(self, text, name="test_hidden.py"):
        (self.hidden / name).write_text(text)

    def run_hidden(self):
        return checks.fact_checks(self.repo, self.base, {}, [
            {"id": "hidden", "kind": "hidden_tests", "dir": str(self.hidden)}])

    def test_one_check_per_test_method(self):
        self.hidden_file(HIDDEN_TESTS)
        self.assertEqual(self.run_hidden(), {"hidden:CliTest.test_passes": True,
                                             "hidden:CliTest.test_fails": False})

    def test_runs_in_the_repo_with_it_on_the_path(self):
        write(self.repo, "mymod.py", "VALUE = 7\n")
        self.hidden_file("""import os
import unittest


class WhereTest(unittest.TestCase):
    def test_cwd_is_the_repo(self):
        self.assertEqual(os.path.realpath(os.getcwd()),
                         os.path.realpath(%r))

    def test_repo_is_importable(self):
        import mymod
        self.assertEqual(mymod.VALUE, 7)
""" % str(self.repo))
        self.assertEqual(self.run_hidden(), {
            "hidden:WhereTest.test_cwd_is_the_repo": True,
            "hidden:WhereTest.test_repo_is_importable": True})

    def test_a_hanging_test_fails_every_unreported_id_within_the_timeout(self):
        self.hidden_file("""import time
import unittest


class HangTest(unittest.TestCase):
    def test_quick(self):
        pass

    def test_hangs(self):
        time.sleep(60)
""")
        start = time.monotonic()
        with mock.patch.object(checks, "HIDDEN_TIMEOUT", 2):
            out = self.run_hidden()
        self.assertLess(time.monotonic() - start, 30)
        self.assertEqual(out, {"hidden:HangTest.test_quick": False,
                               "hidden:HangTest.test_hangs": False})

    def test_discovery_leaves_no_trace_in_the_parent(self):
        self.hidden_file(HIDDEN_TESTS)
        path, modules = list(sys.path), set(sys.modules)
        self.run_hidden()
        self.assertEqual(sys.path, path)
        self.assertEqual(set(sys.modules), modules)

    def run_visible(self):
        return checks.fact_checks(self.repo, self.base, {}, [
            {"id": "visible", "kind": "unittest_green"}])["visible"]

    def test_unittest_green(self):
        write(self.repo, "tests/test_ok.py",
              "import unittest\n\n\nclass T(unittest.TestCase):\n"
              "    def test_ok(self):\n        pass\n")
        self.assertTrue(self.run_visible())
        write(self.repo, "tests/test_bad.py",
              "import unittest\n\n\nclass B(unittest.TestCase):\n"
              "    def test_bad(self):\n        self.fail()\n")
        self.assertFalse(self.run_visible())


def tool_use(name, **tool_input):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": name, "input": tool_input}]}}


class ObservationKindsTest(RepoCase):
    """Fact kinds that describe a trial (they are listed under "observe", not
    "facts", so they never decide `passed`)."""

    def setUp(self):
        super().setUp()
        self.base = "main"

    def observe(self, fact, trace=None):
        return checks.fact_checks(self.repo, self.base, trace or {},
                                  [dict(fact, id="o")])["o"]

    def test_check_wraps_a_named_check(self):
        fact = {"kind": "check", "name": "branch_is_feature"}
        self.assertFalse(self.observe(fact))
        git(self.repo, "checkout", "-b", "feature/x")
        self.assertTrue(self.observe(fact))

    def test_check_passes_the_trace_to_the_check(self):
        fact = {"kind": "check", "name": "result_success"}
        self.assertTrue(self.observe(
            fact, {"subtype": "success", "is_error": False}))
        self.assertFalse(self.observe(fact, {}))

    def test_questions_counts_numbered_items_of_the_grill(self):
        write(self.repo, f"{FOLDER}/grill.md",
              "# Grill\n\n1. **First**\n   1. nested\n2. **Second**\n"
              "not an item\n10. **Tenth**\n")
        # the reply is ignored when there is a grill
        self.assertEqual(self.observe({"kind": "questions"},
                                      {"result_text": "Ok?\nSure?"}), 3)

    def test_questions_without_a_grill_counts_reply_lines_and_asks(self):
        trace = {"result_text": "Done.\nShould I add X?\nAnd Y?  \nbye",
                 "events": [tool_use("AskUserQuestion", question="z"),
                            tool_use("Bash", command="ls")]}
        self.assertEqual(self.observe({"kind": "questions"}, trace), 3)
        self.assertEqual(self.observe({"kind": "questions"}, {}), 0)

    def test_tool_uses_counts_the_named_tool_across_events(self):
        trace = {"events": [tool_use("Skill", skill="a"), tool_use("Bash"),
                            {"type": "system"}, tool_use("Skill", skill="b")]}
        self.assertEqual(self.observe({"kind": "tool_uses", "tool": "Skill"},
                                      trace), 2)
        self.assertEqual(self.observe({"kind": "tool_uses", "tool": "Edit"},
                                      trace), 0)
        self.assertEqual(self.observe({"kind": "tool_uses", "tool": "Skill"}),
                         0)

    def test_phase1_tool_uses_counts_only_phase1_events(self):
        fact = {"kind": "phase1_tool_uses", "tools": ["Agent", "Skill"]}
        trace = {"phase1_events": [tool_use("Agent"), tool_use("Skill"),
                                   tool_use("Bash"), {"type": "system"}],
                 "events": [tool_use("Agent"), tool_use("Task")]}
        self.assertEqual(self.observe(fact, trace), 2)
        self.assertEqual(self.observe(
            dict(fact, tools=["Task"]), trace), 0)

    def test_phase1_tool_uses_is_zero_without_phase1_events(self):
        fact = {"kind": "phase1_tool_uses", "tools": ["Agent"]}
        self.assertEqual(self.observe(fact, {"events": [tool_use("Agent")]}),
                         0)
        self.assertEqual(self.observe(fact), 0)

    def test_trace_mentions_looks_in_tool_inputs_only(self):
        fact = {"kind": "trace_mentions", "strings": ["e2e-suite", "/hidden/"]}
        self.assertTrue(self.observe(fact, {"events": [
            tool_use("Read", file_path="/x/e2e-suite/hidden/a.py")]}))
        self.assertTrue(self.observe(fact, {"events": [
            tool_use("Bash", command="ls /x/hidden/")]}))
        self.assertFalse(self.observe(fact, {"events": [
            tool_use("Bash", command="ls"),
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "e2e-suite"}]}}]}))
        self.assertFalse(self.observe(fact))


ROLES = {"critical": r"01_token_validation|token validation",
         "mechanical": r"02_readme_usage|README usage",
         "runtests": r"(?i)\b(run|running|suite)\b",
         "review": r"(?i)review"}


def agent_event(description="x", model="sonnet", prompt="p", text=None,
                parent=None):
    """An assistant event with an optional text block and one Agent call."""
    content = [{"type": "text", "text": text}] if text else []
    content.append({"type": "tool_use", "name": "Agent", "id": "a",
                    "input": {"description": description, "model": model,
                              "prompt": prompt}})
    event = {"type": "assistant", "message": {"content": content}}
    if parent is not None:
        event["parent_tool_use_id"] = parent
    return event


def with_tools(*events, roles=ROLES):
    return {"events": list(events), "agent_roles": roles}


class DelegateChecksTest(unittest.TestCase):
    def test_s1_delegated_needs_a_main_thread_agent_call(self):
        self.assertTrue(checks.s1_delegated(with_tools(agent_event())))
        self.assertFalse(checks.s1_delegated(with_tools(tool_use("Bash"))))
        self.assertFalse(checks.s1_delegated({}))

    def test_s1_delegated_ignores_sub_agent_calls(self):
        self.assertFalse(checks.s1_delegated(
            with_tools(agent_event(parent="toolu_1"))))

    def test_s1_no_self_impl_flags_main_thread_source_edits(self):
        for tool, key, path in (
                ("Edit", "file_path", "/tmp/r/notesapi/auth.py"),
                ("Write", "file_path", "/tmp/r/tests/test_auth.py"),
                ("NotebookEdit", "notebook_path", "/tmp/r/tests/n.ipynb"),
                ("Edit", "file_path", "notesapi/auth.py")):
            with self.subTest(tool=tool, path=path):
                self.assertFalse(checks.s1_no_self_impl(
                    with_tools(tool_use(tool, **{key: path}))))

    def test_s1_no_self_impl_allows_docs_readme_and_sub_agents(self):
        trace = with_tools(
            tool_use("Edit", file_path="/r/docs/10_features/x/tickets/01.md"),
            tool_use("Edit", file_path="/r/README.md"),
            tool_use("Read", file_path="/r/notesapi/auth.py"),
            {"type": "assistant", "parent_tool_use_id": "toolu_1",
             "message": {"content": [{"type": "tool_use", "name": "Edit",
                         "input": {"file_path": "/r/notesapi/auth.py"}}]}})
        self.assertTrue(checks.s1_no_self_impl(trace))

    def test_s2_model_explicit(self):
        self.assertTrue(checks.s2_model_explicit(with_tools(
            agent_event(model="haiku"), agent_event(model="opus"))))
        self.assertFalse(checks.s2_model_explicit(with_tools(
            agent_event(model="haiku"), agent_event(model=None))))
        self.assertFalse(checks.s2_model_explicit(with_tools()))

    def test_role_checks_pass_when_every_role_call_uses_its_model(self):
        trace = with_tools(
            agent_event("Implement ticket", "opus", "Do 01_token_validation"),
            agent_event("Implement ticket", "sonnet", "Do README usage"),
            agent_event("Review tests", "sonnet"),
            agent_event("Run full suite", "haiku"))
        for name in ("s2_model_runtests_haiku", "s2_model_review_sonnet",
                     "s2_model_critical_opus", "s2_model_mechanical_sonnet"):
            with self.subTest(check=name):
                self.assertTrue(getattr(checks, name)(trace))

    def test_role_checks_fail_on_a_wrong_model(self):
        for name, role_call in (
                ("s2_model_runtests_haiku", ("Run full suite", "x")),
                ("s2_model_review_sonnet", ("Review tests", "x")),
                ("s2_model_critical_opus", ("Implement", "token validation")),
                ("s2_model_mechanical_sonnet", ("Implement", "README usage"))):
            desc, prompt = role_call
            with self.subTest(check=name):
                trace = with_tools(agent_event(desc, "fable", prompt))
                self.assertFalse(getattr(checks, name)(trace))

    def test_role_check_fails_with_no_call_of_the_role(self):
        trace = with_tools(agent_event("Implement", "opus", "other work"))
        self.assertFalse(checks.s2_model_critical_opus(trace))

    def test_one_wrong_call_of_a_role_fails_it(self):
        trace = with_tools(agent_event("Run suite", "haiku"),
                           agent_event("Run suite again", "sonnet"))
        self.assertFalse(checks.s2_model_runtests_haiku(trace))

    def test_a_call_has_one_role_review_wins_over_runtests(self):
        trace = with_tools(agent_event("Review the suite run", "sonnet"))
        self.assertTrue(checks.s2_model_review_sonnet(trace))
        self.assertFalse(checks.s2_model_runtests_haiku(trace))

    def test_runtests_wins_over_critical_by_order(self):
        trace = with_tools(agent_event("Run the suite", "haiku",
                                       "after token validation"))
        self.assertTrue(checks.s2_model_runtests_haiku(trace))
        self.assertFalse(checks.s2_model_critical_opus(trace))

    def test_role_checks_fail_without_roles_in_the_trace(self):
        trace = {"events": [agent_event("Review tests", "sonnet")]}
        self.assertFalse(checks.s2_model_review_sonnet(trace))

    def test_s2_model_stated_wants_each_model_named_before_first_use(self):
        trace = with_tools(
            agent_event(text="Model: Opus, auth is critical.", model="opus"),
            agent_event(text="Sonnet for the docs.", model="sonnet"),
            agent_event(model="sonnet"))
        self.assertTrue(checks.s2_model_stated(trace))

    def test_s2_model_stated_fails_when_a_model_is_not_named(self):
        trace = with_tools(
            agent_event(text="Using opus.", model="opus"),
            agent_event(text="A cheap one.", model="haiku"))
        self.assertFalse(checks.s2_model_stated(trace))

    def test_s2_model_stated_fails_when_named_only_after_the_call(self):
        trace = with_tools(
            agent_event(model="opus"),
            agent_event(text="opus was right", model="sonnet"))
        self.assertFalse(checks.s2_model_stated(trace))

    def test_s2_model_stated_uses_word_match(self):
        trace = with_tools(agent_event(text="Using opusX.", model="opus"))
        self.assertFalse(checks.s2_model_stated(trace))

    def test_s2_model_stated_fails_with_no_call(self):
        self.assertFalse(checks.s2_model_stated(with_tools()))

    def test_registered_as_trace_checks(self):
        for name in ("s1_delegated", "s1_no_self_impl", "s2_model_explicit",
                     "s2_model_runtests_haiku", "s2_model_review_sonnet",
                     "s2_model_critical_opus", "s2_model_mechanical_sonnet",
                     "s2_model_stated"):
            with self.subTest(check=name):
                self.assertIn(name, checks.CHECKS)
                self.assertIn(name, checks.TRACE_CHECKS)

    def test_registered_check_reads_the_trace_not_the_repo(self):
        trace = with_tools(agent_event())
        self.assertTrue(checks.CHECKS["s1_delegated"](None, trace))


GOOD_PROMPT = (
    "Work ticket docs/10_features/x/tickets/03_markdown_export.md. Spec: "
    "docs/10_features/x/spec.md. Scope: only export.py. Do not touch other "
    "files. Work on branch feature/notes_api. Strict TDD: show the red "
    "output of each new test before you implement. Run the full suite and "
    "paste the real output. Chain with && and check exit codes. Use Edit, "
    "not sed -i. Check git status shows the ticket status edit. Put new "
    "code in new files and wire it with one-line edits.")
PROMPT_ROLES = {"mechanical": "03_markdown_export", "critical": "zzz",
                "runtests": "zzz", "review": "zzz"}
PROMPT_RULES = {
    "s3_paths": [r"tickets/03_markdown_export", r"spec\.md"],
    "s3_constraints": [r"(?i)(must not|do not|don't|never)\s+(touch|change)",
                       r"feature/notes_api"],
    "s3_red_evidence": [r"(?i)\bred\b", r"(?i)(fail|output)"],
    "s3_full_suite": [r"(?i)full suite"],
    "s3_no_sed_i": [r"sed -i", r"\bEdit\b"],
    "s3_and_chain": [r"&&"],
    "s3_status_edit": [r"git status"],
    "s4_new_files": [r"(?i)new files?", r"(?i)one-line"]}


def prompt_trace(*prompts, rules=PROMPT_RULES, roles=PROMPT_ROLES):
    t = with_tools(*[agent_event("Implement", "sonnet", p) for p in prompts],
                   roles=roles)
    t["prompt_rules"] = rules
    return t


class PromptRulesTest(unittest.TestCase):
    # for each check: a prompt that drops only that item
    BREAKS = {
        "s3_paths": ("tickets/03_markdown_export.md", "03_markdown_export"),
        "s3_constraints": ("feature/notes_api", "the right branch"),
        "s3_red_evidence": ("red output", "proof"),
        "s3_full_suite": ("full suite", "tests"),
        "s3_no_sed_i": ("sed -i", "sed"),
        "s3_and_chain": ("&&", "and"),
        "s3_status_edit": ("git status", "git log"),
        "s4_new_files": ("new files", "files")}

    def test_good_prompt_passes_every_check(self):
        for name in self.BREAKS:
            with self.subTest(check=name):
                self.assertTrue(getattr(checks, name)(prompt_trace(GOOD_PROMPT)))

    def test_prompt_missing_one_item_fails_only_that_check(self):
        for name, (item, repl) in self.BREAKS.items():
            bad = GOOD_PROMPT.replace(item, repl)
            self.assertNotEqual(bad, GOOD_PROMPT, name)
            trace = prompt_trace(bad)
            for other in self.BREAKS:
                with self.subTest(broken=name, check=other):
                    self.assertEqual(getattr(checks, other)(trace),
                                     other != name)

    def test_every_implementation_agent_must_pass(self):
        trace = prompt_trace(GOOD_PROMPT, "03_markdown_export: just do it")
        self.assertFalse(checks.s3_full_suite(trace))

    def test_review_and_runtests_agents_are_not_checked(self):
        trace = prompt_trace(GOOD_PROMPT)
        trace["events"] += [agent_event("Review tests", "sonnet", "look"),
                            agent_event("Run full suite", "haiku", "go")]
        self.assertTrue(checks.s3_full_suite(trace))

    def test_no_implementation_agent_fails(self):
        self.assertFalse(checks.s3_paths(prompt_trace()))
        self.assertFalse(checks.s3_paths(prompt_trace("unrelated prompt")))

    def test_missing_rules_or_roles_fail(self):
        self.assertFalse(checks.s3_paths(prompt_trace(GOOD_PROMPT, rules={})))
        trace = prompt_trace(GOOD_PROMPT)
        del trace["agent_roles"]
        self.assertFalse(checks.s3_paths(trace))

    def test_roles_may_list_only_some_roles(self):
        trace = prompt_trace(GOOD_PROMPT, roles={"mechanical": "03_markdown"})
        self.assertTrue(checks.s3_full_suite(trace))
        self.assertFalse(checks.s2_model_review_sonnet(trace))

    def test_sub_agent_calls_are_ignored(self):
        trace = prompt_trace(GOOD_PROMPT)
        trace["events"].append(agent_event(
            "Implement", "sonnet", "03_markdown_export bare", parent="t1"))
        self.assertTrue(checks.s3_full_suite(trace))

    def test_registered_as_trace_checks(self):
        for name in self.BREAKS:
            with self.subTest(check=name):
                self.assertIn(name, checks.CHECKS)
                self.assertIn(name, checks.TRACE_CHECKS)


WAVE = ["03_markdown_export", "04_case_blind_search"]
WAVE_TWO = "05_export_tag_filter"
SUITE_ROLES = {"mechanical": "03_markdown_export|04_case_blind_search|"
                             "05_export_tag_filter",
               "runtests": r"(?i)\bsuite\b", "critical": "zzz",
               "review": "zzz"}


def call_event(id_, name, **inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": id_, "name": name, "input": inp}]}}


def result_event(id_, parent=None):
    e = {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": id_, "content": "done"}]}}
    if parent:
        e["parent_tool_use_id"] = parent
    return e


def agent(id_, ticket, **extra):
    return call_event(id_, "Agent", description="Implement " + ticket,
                      model="sonnet", prompt="Work on " + ticket, **extra)


def bash(id_, command):
    return call_event(id_, "Bash", command=command)


def parallel_trace(*events):
    return {"events": list(events), "agent_roles": SUITE_ROLES,
            "parallel_wave": WAVE, "wave_two": WAVE_TWO}


class WorktreeEachTest(unittest.TestCase):
    def test_isolation_worktree_passes(self):
        t = parallel_trace(agent("a", WAVE[0], isolation="worktree"),
                           agent("b", WAVE[1], isolation="worktree"))
        self.assertTrue(checks.s4_worktree_each(t))

    def test_git_worktree_add_with_path_in_prompt_passes(self):
        t = parallel_trace(
            bash("w1", "git worktree add -b t03 ../wt03 feature/notes_api"
                       " && git worktree add ../wt04"),
            call_event("a", "Agent", description="d", model="sonnet",
                       prompt="03_markdown_export in ../wt03"),
            call_event("b", "Agent", description="d", model="sonnet",
                       prompt="04_case_blind_search in ../wt04"))
        self.assertTrue(checks.s4_worktree_each(t))

    def test_one_call_without_worktree_fails(self):
        t = parallel_trace(agent("a", WAVE[0], isolation="worktree"),
                           agent("b", WAVE[1]))
        self.assertFalse(checks.s4_worktree_each(t))

    def test_shared_worktree_path_fails(self):
        t = parallel_trace(
            bash("w1", "git worktree add ../wt"),
            call_event("a", "Agent", description="d", model="sonnet",
                       prompt="03_markdown_export in ../wt"),
            call_event("b", "Agent", description="d", model="sonnet",
                       prompt="04_case_blind_search in ../wt"))
        self.assertFalse(checks.s4_worktree_each(t))

    def test_missing_ticket_call_or_data_fails(self):
        self.assertFalse(checks.s4_worktree_each(parallel_trace(
            agent("a", WAVE[0], isolation="worktree"))))
        t = parallel_trace(agent("a", WAVE[0], isolation="worktree"),
                           agent("b", WAVE[1], isolation="worktree"))
        del t["parallel_wave"]
        self.assertFalse(checks.s4_worktree_each(t))

    # Real shapes from the stored parallel traces: the coordinator adds the
    # worktree with a relative path and gives the agent the absolute path.
    ABS = "/private/var/folders/5t/x/T/tmp4gka7_ld"

    def two_agents(self, command, path_a, path_b):
        return parallel_trace(
            bash("w1", command),
            call_event("a", "Agent", description="d", model="sonnet",
                       prompt=f"Work 03_markdown_export in {path_a}. Stay "
                              "in this worktree."),
            call_event("b", "Agent", description="d", model="sonnet",
                       prompt=f"Work 04_case_blind_search in {path_b}/."))

    def test_relative_path_matches_absolute_path_in_prompt(self):
        t = self.two_agents("git worktree add ../wt03 -b t03 && "
                            "git worktree add ../wt04 -b t04",
                            f"{self.ABS}/wt03", f"{self.ABS}/wt04")
        self.assertTrue(checks.s4_worktree_each(t))

    def test_variable_and_nested_paths_match_by_last_components(self):
        t = self.two_agents("W=../wt && mkdir -p $W && git worktree add "
                            "$W/t03 -b ticket/03 && git worktree add "
                            "../wt/t04 -b ticket/04",
                            f"{self.ABS}/wt/t03", f"{self.ABS}/wt/t04")
        self.assertTrue(checks.s4_worktree_each(t))

    def test_last_component_must_match_whole(self):
        t = self.two_agents("git worktree add ../wt03 && "
                            "git worktree add ../wt04",
                            f"{self.ABS}/wt030", f"{self.ABS}/wt04")
        self.assertFalse(checks.s4_worktree_each(t))
        t = self.two_agents("git worktree add ../wt && "
                            "git worktree add ../wt04",
                            f"{self.ABS}/wt/t03", f"{self.ABS}/wt04")
        self.assertFalse(checks.s4_worktree_each(t))

    def test_branch_name_alone_is_not_the_worktree_path(self):
        t = self.two_agents("git worktree add $W/t03 -b t03 && "
                            "git worktree add $W/t04 -b t04",
                            "the repo, branch t03", f"{self.ABS}/wt/t04")
        self.assertFalse(checks.s4_worktree_each(t))

    def test_two_agents_in_one_absolute_worktree_fail(self):
        t = self.two_agents("git worktree add ../wt03",
                            f"{self.ABS}/wt03", f"{self.ABS}/wt03")
        self.assertFalse(checks.s4_worktree_each(t))

    def test_sub_agent_worktree_commands_are_ignored(self):
        e = bash("w1", "git worktree add ../wt03")
        e["parent_tool_use_id"] = "t9"
        t = parallel_trace(e, call_event(
            "a", "Agent", description="d", model="sonnet",
            prompt="03_markdown_export in ../wt03"), agent(
                "b", WAVE[1], isolation="worktree"))
        self.assertFalse(checks.s4_worktree_each(t))


class WaveOrderTest(unittest.TestCase):
    def test_wave_two_after_first_result_passes(self):
        t = parallel_trace(agent("a", WAVE[0]), agent("b", WAVE[1]),
                           result_event("a"), agent("c", WAVE_TWO))
        self.assertTrue(checks.s5_wave_order(t))

    def test_wave_two_before_first_result_fails(self):
        t = parallel_trace(agent("a", WAVE[0]), agent("b", WAVE[1]),
                           agent("c", WAVE_TWO), result_event("a"))
        self.assertFalse(checks.s5_wave_order(t))

    def test_result_of_the_other_ticket_does_not_count(self):
        t = parallel_trace(agent("a", WAVE[0]), agent("b", WAVE[1]),
                           result_event("b"), agent("c", WAVE_TWO),
                           result_event("a"))
        self.assertFalse(checks.s5_wave_order(t))

    def test_background_launch_notice_is_not_the_return(self):
        # Shapes from the stored traces: a background agent's tool result is
        # a launch notice; it returns with a task_notification event.
        launched = {"type": "text", "text": "Async agent launched successfully."}
        def notice(id_):
            e = result_event(id_)
            e["message"]["content"][0]["content"] = [launched]
            return e
        def back(id_):
            return {"type": "system", "subtype": "task_notification",
                    "tool_use_id": id_, "status": "completed"}
        t = parallel_trace(agent("a", WAVE[0]), notice("a"),
                           agent("b", WAVE[1]), notice("b"),
                           agent("c", WAVE_TWO), back("a"), back("b"))
        self.assertFalse(checks.s5_wave_order(t))
        t = parallel_trace(agent("a", WAVE[0]), notice("a"),
                           agent("b", WAVE[1]), notice("b"),
                           back("a"), agent("c", WAVE_TWO), back("b"))
        self.assertTrue(checks.s5_wave_order(t))

    def test_missing_call_fails(self):
        self.assertFalse(checks.s5_wave_order(parallel_trace(
            agent("a", WAVE[0]), result_event("a"))))
        self.assertFalse(checks.s5_wave_order(parallel_trace(
            agent("c", WAVE_TWO))))


class SuiteAfterMergeTest(unittest.TestCase):
    def suite_agent(self, id_):
        return call_event(id_, "Agent", description="Run the suite",
                          model="haiku", prompt="go")

    def test_suite_after_each_merge_passes(self):
        t = parallel_trace(
            bash("m1", "git merge --no-ff t03"), bash("s1", "python3 -m unittest"),
            bash("m2", "git merge --no-ff t04"), self.suite_agent("s2"))
        self.assertTrue(checks.s5_suite_after_merge(t))

    def test_merge_and_suite_in_one_command_passes(self):
        t = parallel_trace(bash("m", "git merge t03 && pytest"))
        self.assertTrue(checks.s5_suite_after_merge(t))

    def test_two_merges_then_one_suite_fails(self):
        t = parallel_trace(bash("m1", "git merge t03"),
                           bash("m2", "git merge t04"),
                           bash("s", "python3 -m unittest"))
        self.assertFalse(checks.s5_suite_after_merge(t))

    def test_merge_last_fails(self):
        t = parallel_trace(bash("s", "python3 -m unittest"),
                           bash("m", "git merge t03"))
        self.assertFalse(checks.s5_suite_after_merge(t))

    def test_no_merge_fails(self):
        self.assertFalse(checks.s5_suite_after_merge(parallel_trace(
            bash("s", "python3 -m unittest"))))

    def test_abort_and_merge_base_are_not_merges(self):
        t = parallel_trace(bash("m", "git merge --abort"),
                           bash("b", "git merge-base a b"))
        self.assertFalse(checks.s5_suite_after_merge(t))
        t = parallel_trace(bash("m1", "git merge t03"),
                           bash("s", "python3 -m unittest"),
                           bash("m2", "git merge --abort"))
        self.assertTrue(checks.s5_suite_after_merge(t))

    def test_registered_as_trace_checks(self):
        for name in ("s4_worktree_each", "s5_wave_order",
                     "s5_suite_after_merge"):
            self.assertIn(name, checks.CHECKS)
            self.assertIn(name, checks.TRACE_CHECKS)
        self.assertIn("s5_cleanup", checks.CHECKS)
        self.assertNotIn("s5_cleanup", checks.TRACE_CHECKS)


class CleanupTest(RepoCase):
    def setUp(self):
        super().setUp()
        git(self.repo, "checkout", "-b", "feature/notes_api")

    def test_clean_repo_passes(self):
        self.assertTrue(checks.s5_cleanup(self.repo, {}))

    def test_leftover_ticket_branch_fails(self):
        git(self.repo, "branch", "t03")
        self.assertFalse(checks.s5_cleanup(self.repo, {}))

    def test_leftover_worktree_fails(self):
        wt = self.repo.parent / (self.repo.name + "-wt")
        self.addCleanup(shutil.rmtree, wt, True)
        git(self.repo, "worktree", "add", "--detach", str(wt))
        self.assertFalse(checks.s5_cleanup(self.repo, {}))

    def test_missing_feature_branch_fails(self):
        git(self.repo, "checkout", "main")
        git(self.repo, "branch", "-D", "feature/notes_api")
        self.assertFalse(checks.s5_cleanup(self.repo, {}))


TRAP_ROLES = {"mechanical": "06_title_comparison",
              "runtests": r"(?i)\bsuite\b", "critical": "zzz", "review": "zzz"}
MUTATION = (r"notesapi/notes\.py.*(\bcp\b|\bmv\b|\bsed\b|\btee\b|>"
            r"|write)|(\bcp\b|\bmv\b|\bsed\b|\btee\b|>|write).*notesapi/notes\.py")
GAP = r"(?i)no red|never (failed|red)|could not (show|see)|already (exist|pass)"


def trap_trace(*events, reply="Done."):
    return {"events": list(events), "agent_roles": TRAP_ROLES,
            "mutation_proof": MUTATION, "reply_names_gap": GAP,
            "result_text": reply}


def impl(id_):
    return agent(id_, "06_title_comparison")


def suite_agent(id_):
    return call_event(id_, "Agent", description="Run the suite",
                      model="haiku", prompt="go")


def ack(id_):
    """The tool result a background Agent call gets at once (real shape)."""
    e = result_event(id_)
    e["message"]["content"][0]["content"] = [{
        "type": "text", "text": "Async agent launched successfully."}]
    return e


def notify(id_):
    """The system event that brings a background agent's hand-back."""
    return {"type": "system", "subtype": "task_notification",
            "tool_use_id": id_, "status": "completed",
            "summary": "Ticket 06 is committed, but I never saw red."}


def started(task_id, id_):
    return {"type": "system", "subtype": "task_started", "task_id": task_id,
            "tool_use_id": id_}


class BackgroundHandbackTest(unittest.TestCase):
    """A background agent's tool result is a launch notice. Its hand-back
    is the later task_notification event (shapes from stored traces)."""

    def test_suite_run_before_the_notification_does_not_count(self):
        t = trap_trace(impl("a"), ack("a"), bash("s", "python3 -m unittest"),
                       notify("a"), reply="Done.")
        self.assertFalse(checks.s6_reruns_suite(t))

    def test_suite_run_after_the_notification_passes(self):
        t = trap_trace(impl("a"), ack("a"), notify("a"),
                       bash("s", "python3 -m unittest"))
        self.assertTrue(checks.s6_reruns_suite(t))

    def test_mutation_before_the_notification_does_not_count(self):
        t = trap_trace(impl("a"), ack("a"),
                       bash("m", "cp /tmp/broken.py notesapi/notes.py"),
                       bash("s", "python3 -m unittest"), notify("a"))
        self.assertFalse(checks.s6_rejects_missing_red(t))

    def test_parallel_background_agent_is_not_a_redo(self):
        t = trap_trace(impl("a"), ack("a"), impl("b"), ack("b"),
                       notify("a"), notify("b"))
        self.assertFalse(checks.s6_rejects_missing_red(t))

    def test_send_message_to_the_agent_after_its_handback_is_a_redo(self):
        t = trap_trace(impl("a"), started("task1", "a"), ack("a"),
                       notify("a"),
                       call_event("m", "SendMessage", to="task1",
                                  message="Hand-back rejected: no red."))
        self.assertTrue(checks.s6_rejects_missing_red(t))

    def test_send_message_to_another_agent_is_not_a_redo(self):
        t = trap_trace(impl("a"), started("task1", "a"), ack("a"),
                       notify("a"),
                       call_event("m", "SendMessage", to="task9",
                                  message="Please go on."))
        self.assertFalse(checks.s6_rejects_missing_red(t))


class RerunsSuiteTest(unittest.TestCase):
    def test_bash_suite_after_last_handback_passes(self):
        t = trap_trace(impl("a"), result_event("a"),
                       bash("s", "python3 -m unittest discover"))
        self.assertTrue(checks.s6_reruns_suite(t))

    def test_runtests_agent_after_handback_passes(self):
        t = trap_trace(impl("a"), result_event("a"), suite_agent("s"))
        self.assertTrue(checks.s6_reruns_suite(t))

    def test_no_suite_run_fails(self):
        self.assertFalse(checks.s6_reruns_suite(
            trap_trace(impl("a"), result_event("a"), bash("l", "git log"))))

    def test_only_run_before_the_handback_fails(self):
        t = trap_trace(bash("s", "pytest"), impl("a"), result_event("a"))
        self.assertFalse(checks.s6_reruns_suite(t))

    def test_must_follow_the_last_implementation_agent(self):
        t = trap_trace(impl("a"), result_event("a"),
                       bash("s", "pytest"), impl("b"), result_event("b"))
        self.assertFalse(checks.s6_reruns_suite(t))

    def test_no_implementation_agent_or_no_result_fails(self):
        self.assertFalse(checks.s6_reruns_suite(
            trap_trace(bash("s", "pytest"))))
        self.assertFalse(checks.s6_reruns_suite(
            trap_trace(impl("a"), bash("s", "pytest"))))

    def test_sub_agent_suite_runs_do_not_count(self):
        e = bash("s", "pytest")
        e["parent_tool_use_id"] = "t9"
        self.assertFalse(checks.s6_reruns_suite(
            trap_trace(impl("a"), result_event("a"), e)))


class RejectsMissingRedTest(unittest.TestCase):
    def test_redo_passes(self):
        t = trap_trace(impl("a"), result_event("a"), impl("b"),
                       result_event("b"))
        self.assertTrue(checks.s6_rejects_missing_red(t))

    def test_a_parallel_second_agent_is_not_a_redo(self):
        t = trap_trace(impl("a"), impl("b"), result_event("a"))
        self.assertFalse(checks.s6_rejects_missing_red(t))

    def test_mutation_proof_then_suite_passes(self):
        t = trap_trace(impl("a"), result_event("a"),
                       bash("m", "cp /tmp/broken.py notesapi/notes.py"),
                       bash("s", "python3 -m unittest"))
        self.assertTrue(checks.s6_rejects_missing_red(t))

    def test_main_thread_edit_of_the_source_then_suite_passes(self):
        t = trap_trace(impl("a"), result_event("a"),
                       call_event("e", "Edit", file_path="/r/notesapi/notes.py"),
                       bash("s", "python3 -m unittest"))
        self.assertTrue(checks.s6_rejects_missing_red(t))

    def test_mutation_without_a_later_suite_run_fails(self):
        t = trap_trace(impl("a"), result_event("a"),
                       bash("s", "python3 -m unittest"),
                       bash("m", "cp /tmp/broken.py notesapi/notes.py"))
        self.assertFalse(checks.s6_rejects_missing_red(t))

    def test_mutation_before_the_handback_does_not_count(self):
        t = trap_trace(bash("m", "cp x notesapi/notes.py"), impl("a"),
                       result_event("a"), bash("s", "pytest"))
        self.assertFalse(checks.s6_rejects_missing_red(t))

    def test_reply_naming_the_gap_passes(self):
        t = trap_trace(impl("a"), result_event("a"),
                       reply="The agent could not show red, so not done.")
        self.assertTrue(checks.s6_rejects_missing_red(t))

    def test_accepting_the_handback_fails(self):
        t = trap_trace(impl("a"), result_event("a"),
                       bash("s", "python3 -m unittest"),
                       reply="Ticket 06 is done. All tests pass.")
        self.assertFalse(checks.s6_rejects_missing_red(t))

    def test_no_implementation_agent_or_missing_keys_fail(self):
        self.assertFalse(checks.s6_rejects_missing_red(trap_trace()))
        t = trap_trace(impl("a"), result_event("a"), reply="no red seen")
        del t["reply_names_gap"]
        self.assertFalse(checks.s6_rejects_missing_red(t))
        t = trap_trace(impl("a"), result_event("a"),
                       bash("m", "cp x notesapi/notes.py"),
                       bash("s", "pytest"))
        del t["mutation_proof"]
        self.assertFalse(checks.s6_rejects_missing_red(t))


class NoDelegateTest(unittest.TestCase):
    def test_no_agent_call_passes(self):
        self.assertTrue(checks.n_no_delegate(
            trap_trace(call_event("e", "Edit", file_path="README.md"))))
        self.assertTrue(checks.n_no_delegate({}))

    def test_an_agent_call_fails(self):
        self.assertFalse(checks.n_no_delegate(trap_trace(impl("a"))))

    def test_sub_agent_calls_are_ignored(self):
        e = agent("a", "x")
        e["parent_tool_use_id"] = "t9"
        self.assertTrue(checks.n_no_delegate(trap_trace(e)))

    def test_registered_as_trace_checks(self):
        for name in ("s6_reruns_suite", "s6_rejects_missing_red",
                     "n_no_delegate"):
            self.assertIn(name, checks.CHECKS)
            self.assertIn(name, checks.TRACE_CHECKS)
