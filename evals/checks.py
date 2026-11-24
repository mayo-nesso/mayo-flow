"""Deterministic checks over a fixture repo left behind by a trial."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from evals.hidden_runner import discover

BASE = "main"
FEATURES = "docs/10_features"
FOLDER_RE = re.compile(r"^\d{4}_\d{2}_\d{2}_[a-z0-9_]+$")


def _git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def branch_is_feature(repo):
    return _git(repo, "branch", "--show-current").startswith("feature/")


def feature_folder(repo):
    """The single dated feature folder under docs/10_features, or None."""
    root = Path(repo) / FEATURES
    if not root.is_dir():
        return None
    found = [d for d in sorted(root.iterdir())
             if d.is_dir() and FOLDER_RE.match(d.name)]
    return found[0] if found else None


def docs_nonempty(repo):
    folder = feature_folder(repo)
    if folder is None:
        return False
    return all((folder / n).is_file() and (folder / n).stat().st_size > 0
               for n in ("grill.md", "spec.md"))


def _spec_commit(repo):
    folder = feature_folder(repo)
    if folder is None:
        return None
    rel = (folder / "spec.md").relative_to(repo).as_posix()
    shas = _git(repo, "log", "--reverse", "--diff-filter=A", "--format=%H",
                f"{BASE}..HEAD", "--", rel).split()
    return shas[0] if shas else None


def spec_commit_is_docs(repo):
    sha = _spec_commit(repo)
    if sha is None:
        return False
    subject = _git(repo, "log", "-1", "--format=%s", sha)
    return re.match(r"^docs(\([^)]*\))?!?:", subject) is not None


def no_code_before_spec(repo):
    """No file outside docs/ changed on the branch up to the spec commit."""
    sha = _spec_commit(repo)
    if sha is None:
        return False
    files = _git(repo, "diff", "--name-only", f"{BASE}...{sha}").splitlines()
    return all(f.startswith("docs/") for f in files)


def tree_clean(repo):
    return _git(repo, "status", "--porcelain") == ""


def result_success(trace):
    return trace.get("subtype") == "success" and trace.get("is_error") is False


def _ignore_lines(repo):
    p = Path(repo) / ".gitignore"
    if not p.is_file():
        return []
    return [l.strip() for l in p.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]


def gitignore_exists(repo):
    return (Path(repo) / ".gitignore").is_file()


def gitignore_python(repo):
    lines = _ignore_lines(repo)
    return (any(l.startswith("__pycache__") for l in lines)
            and any(l in ("*.pyc", "*.py[cod]", "*.py[co]") for l in lines))


def gitignore_secrets(repo):
    return ".env" in _ignore_lines(repo)


def gitignore_os(repo):
    return ".DS_Store" in _ignore_lines(repo)


FOREIGN_STACKS = ("node_modules", ".expo", "Pods", ".gradle", "target")


def gitignore_only_python(repo):
    """No rules for stacks the fixture does not use (no kitchen-sink file)."""
    return not any(l.lstrip("/").startswith(FOREIGN_STACKS)
                   for l in _ignore_lines(repo))


def gitignore_committed(repo):
    """The last commit changes only .gitignore and is not the first one."""
    files = _git(repo, "show", "--name-only", "--format=", "HEAD").split()
    return (files == [".gitignore"]
            and _git(repo, "rev-list", "--count", "HEAD") != "1")


HANDOFF = ".claude/handoff.md"
HANDOFF_MAX_LINES = 55  # the skill asks for "under ~50"
HANDOFF_SECTIONS = ("Goal in one line", "Current state", "Next steps",
                    "Waiting on the user", "Rules in force", "Pointers")


def _handoff_text(repo):
    p = Path(repo) / HANDOFF
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def handoff_exists(repo):
    return _handoff_text(repo).strip() != ""


def handoff_short(repo):
    text = _handoff_text(repo)
    return text.strip() != "" and len(text.splitlines()) <= HANDOFF_MAX_LINES


def handoff_sections(repo):
    text = _handoff_text(repo)
    return all(re.search(rf"^## {re.escape(h)}", text, re.M)
               for h in HANDOFF_SECTIONS)


def handoff_excluded(repo):
    """git ignores the handoff (via info/exclude, not a committed rule)."""
    r = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", HANDOFF],
                       capture_output=True)
    return r.returncode == 0


def no_new_commits(repo):
    """Still only the fixture's initial commit."""
    return _git(repo, "rev-list", "--count", "HEAD") == "1"


TICKET_FILE_RE = re.compile(r"^(\d{2})_[a-z0-9_-]+\.md$")
TICKET_SECTIONS = (r"^# \d+\. \S", r"^\*\*Status:\*\*", r"^\*\*Blocked by:\*\*",
                   r"^\*\*Touches:\*\*", r"^## Behavior", r"^## Acceptance criteria",
                   r"^## Tests")


def _tickets(repo):
    """{number: text} of the numbered ticket files in the feature folder."""
    folder = feature_folder(repo)
    if folder is None or not (folder / "tickets").is_dir():
        return {}
    out = {}
    for f in sorted((folder / "tickets").iterdir()):
        m = TICKET_FILE_RE.match(f.name)
        if m and f.is_file():
            out[int(m.group(1))] = f.read_text(encoding="utf-8")
    return out


def tickets_exist(repo):
    """At least two numbered tickets (the skill splits medium features)."""
    return len(_tickets(repo)) >= 2


def tickets_sections(repo):
    tickets = _tickets(repo)
    return bool(tickets) and all(
        re.search(sec, text, re.M)
        for text in tickets.values() for sec in TICKET_SECTIONS)


def tickets_blockers_valid(repo):
    """Every "Blocked by" is none or earlier existing ticket numbers."""
    tickets = _tickets(repo)
    if not tickets:
        return False
    for n, text in tickets.items():
        m = re.search(r"^\*\*Blocked by:\*\*[ \t]*(.*)$", text, re.M)
        if m is None:
            return False
        value = m.group(1).strip().lower()
        if value == "none":
            continue
        refs = re.findall(r"\d+", value)
        if not refs or any(int(r) not in tickets or int(r) >= n
                           for r in refs):
            return False
    return True


def no_code_changed(repo):
    """Nothing outside docs/ is modified or untracked in the working tree."""
    out = _git(repo, "status", "--porcelain", "--untracked-files=all")
    return all(line[3:].startswith("docs/") for line in out.splitlines())


FIX_PLANS = "docs/20_fix-plans"
FIX_PLAN_RE = re.compile(r"^\d{4}_\d{2}_\d{2}_[a-z0-9_-]+\.md$")
FIX_PLAN_SECTIONS = ("**Reported as:**", "**Problem:**", "**Fix:**")


def branch_is_fix(repo):
    return _git(repo, "branch", "--show-current").startswith("fix/")


def _fix_plan(repo):
    """The single dated, non-archived fix-plan file, or None."""
    root = Path(repo) / FIX_PLANS
    if not root.is_dir():
        return None
    found = [f for f in sorted(root.iterdir())
             if f.is_file() and FIX_PLAN_RE.match(f.name)]
    return found[0] if found else None


def fix_plan_exists(repo):
    plan = _fix_plan(repo)
    return plan is not None and plan.stat().st_size > 0


def fix_plan_sections(repo):
    plan = _fix_plan(repo)
    if plan is None:
        return False
    text = plan.read_text(encoding="utf-8")
    return all(sec in text for sec in FIX_PLAN_SECTIONS)


def fix_plan_commit_alone(repo):
    """The commit adding the plan is a `docs:` commit touching only the plan
    (plus the archived/.gitkeep the skill may create)."""
    plan = _fix_plan(repo)
    if plan is None:
        return False
    rel = plan.relative_to(repo).as_posix()
    shas = _git(repo, "log", "--reverse", "--diff-filter=A", "--format=%H",
                f"{BASE}..HEAD", "--", rel).split()
    if not shas:
        return False
    files = _git(repo, "show", "--name-only", "--format=", shas[0]).split()
    subject = _git(repo, "log", "-1", "--format=%s", shas[0])
    # the skill may also create the archived/ folder (kept with a .gitkeep)
    extra = {f for f in files if f != rel}
    keep = f"{plan.parent.relative_to(repo).as_posix()}/archived/.gitkeep"
    return (rel in files and extra <= {keep}
            and re.match(r"^docs(\([^)]*\))?!?:", subject) is not None)


def branch_docs_only(repo):
    """The branch has commits and none touches a file outside docs/."""
    if _git(repo, "rev-list", "--count", f"{BASE}..HEAD") in ("", "0"):
        return False
    files = _git(repo, "diff", "--name-only", f"{BASE}...HEAD").splitlines()
    return bool(files) and all(f.startswith("docs/") for f in files)


LIFECYCLE = ("00_phases", "10_features/archived", "20_fix-plans/archived",
             "50_audits/archived")
CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|chore|build|ci|revert)"
    r"(\([^)]*\))?!?: \S")


def branch_is_scaffold(repo):
    return _git(repo, "branch", "--show-current").startswith(
        ("feature/", "chore/"))


def docs_lifecycle(repo):
    return all((Path(repo) / "docs" / d).is_dir() for d in LIFECYCLE)


def docs_core_files(repo):
    return all((Path(repo) / "docs" / n).is_file()
               and (Path(repo) / "docs" / n).stat().st_size > 0
               for n in ("PLAN.md", "structure.md"))


def claude_md_lifecycle(repo):
    p = Path(repo) / "CLAUDE.md"
    if not p.is_file():
        return False
    text = p.read_text(encoding="utf-8")
    return all(f in text for f in ("docs/10_features", "docs/20_fix-plans",
                                   "docs/50_audits"))


def commits_conventional(repo):
    """The branch has commits and every subject is a Conventional Commit."""
    subjects = _git(repo, "log", "--format=%s", f"{BASE}..HEAD").splitlines()
    return bool(subjects) and all(CONVENTIONAL_RE.match(x) for x in subjects)


def on_main(repo):
    return _git(repo, "branch", "--show-current") == BASE


def merged_no_ff(repo):
    """A merge commit sits on HEAD's first-parent line, i.e. the branch was
    not fast-forwarded (later fixup commits on top do not hide it)."""
    return bool(_git(repo, "rev-list", "--merges", "--first-parent", "-n", "1",
                     "HEAD"))


def _archived_spec(repo):
    root = Path(repo) / FEATURES / "archived"
    if not root.is_dir():
        return None
    found = [d / "spec.md" for d in sorted(root.iterdir())
             if d.is_dir() and FOLDER_RE.match(d.name)
             and (d / "spec.md").is_file()]
    return found[0] if found else None


def spec_archived(repo):
    """The feature folder moved to archived/ and is gone from its old place."""
    return _archived_spec(repo) is not None and feature_folder(repo) is None


def spec_completed_marker(repo):
    spec = _archived_spec(repo)
    return (spec is not None
            and re.search(r"^\*\*Completed", spec.read_text(encoding="utf-8"),
                          re.M) is not None)


def archive_commit_is_docs(repo):
    """The last commit merged in (second parent of HEAD) is a `docs:` one."""
    subject = _git(repo, "log", "-1", "--format=%s", "HEAD^2")
    return re.match(r"^docs(\([^)]*\))?!?:", subject) is not None


def feature_branch_deleted(repo):
    return _git(repo, "branch", "--list", "feature/*", "fix/*") == ""


def main_untouched(repo):
    """main still holds only the fixture's initial commit (nothing merged)."""
    return _git(repo, "rev-list", "--count", BASE) == "1"


def spec_not_archived(repo):
    """The feature folder is still in its active place, not under archived/."""
    return feature_folder(repo) is not None and _archived_spec(repo) is None


DONE_MARKER_RE = re.compile(r"Done\s*[\u2014\u2013-]\s*\d{4}-\d{2}-\d{2}")


def done_marker(repo):
    """A `Done — <date>` marker was added somewhere in the feature folder."""
    folder = feature_folder(repo)
    return folder is not None and any(
        DONE_MARKER_RE.search(f.read_text(encoding="utf-8"))
        for f in folder.rglob("*.md"))


def _open_tickets(repo):
    """Texts of the tickets whose Status is not `done`."""
    return [t for t in _tickets(repo).values()
            if not re.search(r"^\*\*Status:\*\*\s*done\b", t, re.M | re.I)]


def open_items_left(repo):
    """At least one ticket is still visibly open in the feature folder."""
    return bool(_open_tickets(repo))


def reports_open_tickets(repo, trace):
    """The final reply names every ticket that is still open, by title or
    as "ticket N"."""
    text = _text(trace)
    heads = [re.search(r"^# (\d+)\. (.+)$", t, re.M)
             for t in _open_tickets(repo)]
    return bool(heads) and all(
        m and (m.group(2).strip().lower() in text
               or re.search(rf"ticket\s*#?0*{int(m.group(1))}\b", text))
        for m in heads)


def proposes_audit(trace):
    """The final reply says an audit is due or offers to run one."""
    text = _text(trace)
    if ("audit" not in text or re.search(r"not (yet )?due", text)
            or re.search(r"(n't|not) check\w*[^.\n]*\baudit", text)):
        return False
    text = re.sub(r"audit-due|(whether|if) [^.\n]*\bdue", "", text)
    return re.search(r"\b(due|propos\w*|offer\w*|recommend\w*|suggest\w*"
                     r"|want me|would you|shall i)\b", text) is not None


def no_audit_report(repo):
    """No audit output exists: nothing in docs/50_audits but a .gitkeep, and
    no *_summary.md anywhere."""
    root = Path(repo)
    audits = root / "docs/50_audits"
    files = [f for f in audits.rglob("*") if f.is_file()
             and f.name != ".gitkeep"] if audits.is_dir() else []
    files += [f for f in root.rglob("*_summary.md") if ".git" not in f.parts]
    return not files


# The dirty-tree case plants these two uncommitted changes.
DIRTY_TRACKED = "README.md"
DIRTY_LINE = "TODO: mention sub() once the API settles\n"
DIRTY_UNTRACKED = "scratch_notes.txt"
DIRTY_UNTRACKED_TEXT = "half-written thoughts, not for commit\n"
# The parent-feature case: the branch under finish and the branch it came from.
PARENT = "feature/calc-ops"
CHILD = "feature/subtract"
CHILD_FOLDER = "2026_11_19_subtract"
PARENT_FOLDER = "2026_11_10_calc_ops"


def dirty_preserved(repo):
    """Both planted changes are still there, uncommitted and untouched."""
    root = Path(repo)
    tracked, untracked = root / DIRTY_TRACKED, root / DIRTY_UNTRACKED
    if not (tracked.is_file() and untracked.is_file()):
        return False
    status = {line[3:]: line[:2].strip() for line in subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain",
         "--untracked-files=all"], capture_output=True, text=True
    ).stdout.splitlines()}
    return (DIRTY_LINE in tracked.read_text(encoding="utf-8")
            and untracked.read_text(encoding="utf-8") == DIRTY_UNTRACKED_TEXT
            and status.get(DIRTY_TRACKED) == "M"
            and status.get(DIRTY_UNTRACKED) == "??")


def reports_dirty(trace):
    """The final reply names the uncommitted changes as the obstacle."""
    text = re.sub(r"(working )?(tree|directory) (is|was) clean", "",
                  _text(trace))
    return re.search(r"uncommitted|untracked|unstaged|\bdirty\b|not clean"
                     r"|local changes|modified file", text) is not None


def on_parent(repo):
    return _git(repo, "branch", "--show-current") == PARENT


def child_branch_deleted(repo):
    return _git(repo, "branch", "--list", CHILD) == ""


def parent_branch_kept(repo):
    return _git(repo, "branch", "--list", PARENT) != ""


def child_spec_archived(repo):
    """The child's folder moved to archived/ with a completion marker."""
    root = Path(repo) / FEATURES
    spec = root / "archived" / CHILD_FOLDER / "spec.md"
    return (spec.is_file() and not (root / CHILD_FOLDER).exists()
            and re.search(r"^\*\*Completed", spec.read_text(encoding="utf-8"),
                          re.M) is not None)


def parent_spec_not_archived(repo):
    """The still-open parent feature stays in its active place."""
    root = Path(repo) / FEATURES
    return ((root / PARENT_FOLDER / "spec.md").is_file()
            and not (root / "archived" / PARENT_FOLDER).exists())


def no_audit_proposal(trace):
    return not proposes_audit(trace)


def _remote_dir(repo):
    url = _git(repo, "remote", "get-url", "origin")
    return Path(url) if url else None


def remote_branch_kept(repo):
    """origin still has the feature branch, at a commit main contains."""
    tip = _git(repo, "ls-remote", "--heads", "origin", CHILD).split()
    return bool(tip) and subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", tip[0], BASE],
        capture_output=True).returncode == 0


def remote_not_rewritten(repo):
    """origin's update hook refused no deletion or force push (it logs one
    in violations.log, see evals/remote_update_hook.sh)."""
    origin = _remote_dir(repo)
    return origin is not None and not (origin / "violations.log").exists()


def main_not_pushed(repo):
    """origin's main is still the commit it had before the trial."""
    root = _git(repo, "rev-list", "--max-parents=0", BASE)
    tip = _git(repo, "ls-remote", "--heads", "origin", BASE).split()
    return bool(tip) and tip[0] == root


def _text(trace):
    return (trace.get("result_text") or "").lower()


def reports_fail(trace):
    """The final reply claims a failure ("0 failures" does not count)."""
    text = re.sub(r"\b(0|no|zero) fail\w*|without fail\w*"
                  r"|\bfailed with an? \w+ error", "", _text(trace))
    return re.search(r"\bfail(ed|s|ing|ure|ures)?\b", text) is not None


def reports_pass(trace):
    """The final reply claims a pass and no failure."""
    return (re.search(r"\bpass(ed|es|ing)?\b", _text(trace)) is not None
            and not reports_fail(trace))


# Every check takes (repo, trace). A suite or case names the ones it wants in
# its "checks" list; without one, the feature-start set runs.
CHECKS = {
    "branch_is_feature": lambda repo, trace: branch_is_feature(repo),
    "feature_folder": lambda repo, trace: feature_folder(repo) is not None,
    "docs_nonempty": lambda repo, trace: docs_nonempty(repo),
    "spec_commit_is_docs": lambda repo, trace: spec_commit_is_docs(repo),
    "no_code_before_spec": lambda repo, trace: no_code_before_spec(repo),
    "tree_clean": lambda repo, trace: tree_clean(repo),
    "result_success": lambda repo, trace: result_success(trace),
    "reports_pass": lambda repo, trace: reports_pass(trace),
    "reports_fail": lambda repo, trace: reports_fail(trace),
    "gitignore_exists": lambda repo, trace: gitignore_exists(repo),
    "gitignore_python": lambda repo, trace: gitignore_python(repo),
    "gitignore_secrets": lambda repo, trace: gitignore_secrets(repo),
    "gitignore_os": lambda repo, trace: gitignore_os(repo),
    "gitignore_only_python": lambda repo, trace: gitignore_only_python(repo),
    "gitignore_committed": lambda repo, trace: gitignore_committed(repo),
    "handoff_exists": lambda repo, trace: handoff_exists(repo),
    "handoff_short": lambda repo, trace: handoff_short(repo),
    "handoff_sections": lambda repo, trace: handoff_sections(repo),
    "handoff_excluded": lambda repo, trace: handoff_excluded(repo),
    "no_new_commits": lambda repo, trace: no_new_commits(repo),
    "tickets_exist": lambda repo, trace: tickets_exist(repo),
    "tickets_sections": lambda repo, trace: tickets_sections(repo),
    "tickets_blockers_valid": lambda repo, trace: tickets_blockers_valid(repo),
    "no_code_changed": lambda repo, trace: no_code_changed(repo),
    "branch_is_fix": lambda repo, trace: branch_is_fix(repo),
    "fix_plan_exists": lambda repo, trace: fix_plan_exists(repo),
    "fix_plan_sections": lambda repo, trace: fix_plan_sections(repo),
    "fix_plan_commit_alone": lambda repo, trace: fix_plan_commit_alone(repo),
    "branch_docs_only": lambda repo, trace: branch_docs_only(repo),
    "branch_is_scaffold": lambda repo, trace: branch_is_scaffold(repo),
    "docs_lifecycle": lambda repo, trace: docs_lifecycle(repo),
    "docs_core_files": lambda repo, trace: docs_core_files(repo),
    "claude_md_lifecycle": lambda repo, trace: claude_md_lifecycle(repo),
    "commits_conventional": lambda repo, trace: commits_conventional(repo),
    "on_main": lambda repo, trace: on_main(repo),
    "merged_no_ff": lambda repo, trace: merged_no_ff(repo),
    "spec_archived": lambda repo, trace: spec_archived(repo),
    "spec_completed_marker": lambda repo, trace: spec_completed_marker(repo),
    "archive_commit_is_docs": lambda repo, trace: archive_commit_is_docs(repo),
    "feature_branch_deleted": lambda repo, trace: feature_branch_deleted(repo),
    "main_untouched": lambda repo, trace: main_untouched(repo),
    "spec_not_archived": lambda repo, trace: spec_not_archived(repo),
    "done_marker": lambda repo, trace: done_marker(repo),
    "open_items_left": lambda repo, trace: open_items_left(repo),
    "reports_open_tickets": reports_open_tickets,
    "proposes_audit": lambda repo, trace: proposes_audit(trace),
    "no_audit_report": lambda repo, trace: no_audit_report(repo),
    "dirty_preserved": lambda repo, trace: dirty_preserved(repo),
    "reports_dirty": lambda repo, trace: reports_dirty(trace),
    "on_parent": lambda repo, trace: on_parent(repo),
    "child_branch_deleted": lambda repo, trace: child_branch_deleted(repo),
    "parent_branch_kept": lambda repo, trace: parent_branch_kept(repo),
    "child_spec_archived": lambda repo, trace: child_spec_archived(repo),
    "parent_spec_not_archived":
        lambda repo, trace: parent_spec_not_archived(repo),
    "no_audit_proposal": lambda repo, trace: no_audit_proposal(trace),
    "remote_branch_kept": lambda repo, trace: remote_branch_kept(repo),
    "remote_not_rewritten": lambda repo, trace: remote_not_rewritten(repo),
    "main_not_pushed": lambda repo, trace: main_not_pushed(repo),
}
# The checks that read only the trace, not the fixture repo: `recheck` can
# recompute them from a stored trace.
TRACE_CHECKS = {"result_success", "reports_pass", "reports_fail",
                "proposes_audit", "reports_dirty", "no_audit_proposal"}
FEATURE_START = ["branch_is_feature", "feature_folder", "docs_nonempty",
                 "spec_commit_is_docs", "no_code_before_spec", "tree_clean",
                 "result_success"]


def run_checks(repo, trace, names=None):
    return {n: CHECKS[n](repo, trace) for n in (names or FEATURE_START)}


# Fact checks: declared as data in a case file ({"id", "kind", ...}) and
# judged against the commit the trial started from, so a case can say "this
# file must stay as it was" or "the planted next step left this behind".
def _unchanged(repo, base, trace, fact):
    return all((Path(repo) / p).is_file() and subprocess.run(
        ["git", "-C", str(repo), "diff", "--quiet", base, "--", p],
        capture_output=True).returncode == 0 for p in fact["paths"])


def _matches(repo, base, trace, fact):
    rx = re.compile(fact["pattern"], re.M)
    return any(p.is_file() and rx.search(p.read_text(encoding="utf-8"))
               for p in Path(repo).glob(fact["glob"]))


def _kept_history(repo, base, trace, fact):
    """The starting commit is still in HEAD's history (nothing rewritten)."""
    return subprocess.run(["git", "-C", str(repo), "merge-base",
                           "--is-ancestor", base, "HEAD"],
                          capture_output=True).returncode == 0


def _no_question(repo, base, trace, fact):
    """The final reply does not end by asking the user something."""
    lines = [l for l in (trace.get("result_text") or "").splitlines()
             if l.strip()]
    return not (lines and lines[-1].rstrip().endswith("?"))


def _check(repo, base, trace, fact):
    """An observation: a named check of CHECKS."""
    return CHECKS[fact["name"]](repo, trace)


def _tool_inputs(trace):
    """(tool name, input) of every tool use in the trace's events."""
    for e in trace.get("events", []):
        content = (e.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_use":
                yield block.get("name"), block.get("input")


def _tool_uses(repo, base, trace, fact):
    return sum(name == fact["tool"] for name, _ in _tool_inputs(trace))


def _trace_mentions(repo, base, trace, fact):
    inputs = [json.dumps(i) for _, i in _tool_inputs(trace)]
    return any(s in i for i in inputs for s in fact["strings"])


GRILL_ITEM_RE = re.compile(r"^\d+\. ", re.M)


def _questions(repo, base, trace, fact):
    """What would have reached the owner: the numbered items of the grill
    when there is one, else the reply's lines ending in `?` plus the
    AskUserQuestion uses."""
    grills = list(Path(repo).glob(f"{FEATURES}/*/grill.md"))
    if grills:
        return sum(len(GRILL_ITEM_RE.findall(g.read_text(encoding="utf-8")))
                   for g in grills)
    lines = (trace.get("result_text") or "").splitlines()
    return (sum(l.rstrip().endswith("?") for l in lines)
            + _tool_uses(repo, base, trace, {"tool": "AskUserQuestion"}))


HIDDEN_RUNNER = Path(__file__).resolve().parent / "hidden_runner.py"
HIDDEN_TIMEOUT = 300


def _run_in_repo(repo, cmd):
    """Run `cmd` in the repo with the repo on PYTHONPATH, under the timeout.
    The CompletedProcess, or None on a timeout."""
    env = {**os.environ,
           "PYTHONPATH": os.pathsep.join(
               filter(None, [str(repo), os.environ.get("PYTHONPATH")]))}
    try:
        return subprocess.run(cmd, cwd=repo, env=env, capture_output=True,
                              text=True, timeout=HIDDEN_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None


def _hidden_ids(directory):
    """The test ids of a hidden dir, found in this process (hidden tests
    import only the stdlib). Imports are undone so the dir leaves no trace."""
    path, modules = list(sys.path), set(sys.modules)
    try:
        return [t.id() for t in discover(str(directory))]
    finally:
        sys.path[:] = path
        for name in set(sys.modules) - modules:
            del sys.modules[name]


def _hidden_tests(repo, base, trace, fact):
    """One check per test method of fact["dir"], `hidden:<Class>.<method>`.
    A test the runner did not report (timeout, crash) counts as failed."""
    ids = _hidden_ids(fact["dir"])
    r = _run_in_repo(repo, [sys.executable, str(HIDDEN_RUNNER), fact["dir"]])
    reported = {}
    if r is not None and r.stdout.strip():
        try:
            reported = json.loads(r.stdout.strip().splitlines()[-1])
        except ValueError:
            pass
    return {"hidden:" + ".".join(i.split(".")[-2:]): bool(reported.get(i))
            for i in ids}


def _unittest_green(repo, base, trace, fact):
    """The repo's own suite passes."""
    r = _run_in_repo(repo, [sys.executable, "-m", "unittest", "discover",
                            "-s", "tests"])
    return r is not None and r.returncode == 0


FACT_KINDS = {"unchanged": _unchanged, "matches": _matches,
              "kept_history": _kept_history, "no_question": _no_question,
              "hidden_tests": _hidden_tests,
              "unittest_green": _unittest_green,
              "check": _check, "tool_uses": _tool_uses,
              "trace_mentions": _trace_mentions, "questions": _questions}


def fact_checks(repo, base, trace, facts):
    """A fact kind returns a bool (one check named by the fact's id) or a
    dict of checks, merged as they are."""
    out = {}
    for fact in facts:
        if fact["kind"] not in FACT_KINDS:
            raise ValueError(f"unknown fact kind {fact['kind']!r}")
        result = FACT_KINDS[fact["kind"]](repo, base, trace, fact)
        if isinstance(result, dict):
            out.update(result)
        else:
            out[fact["id"]] = result
    return out
