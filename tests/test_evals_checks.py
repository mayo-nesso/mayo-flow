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
