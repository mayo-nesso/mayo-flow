"""Deterministic checks over a fixture repo left behind by a trial."""
import re
import subprocess
from pathlib import Path

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


def _text(trace):
    return (trace.get("result_text") or "").lower()


def reports_fail(trace):
    """The final reply claims a failure ("0 failures" does not count)."""
    text = re.sub(r"\b(0|no|zero) fail\w*|without fail\w*", "", _text(trace))
    return re.search(r"\bfail(ed|s|ing|ure|ures)?\b", text) is not None


def reports_pass(trace):
    """The final reply claims a pass and no failure."""
    return (re.search(r"\bpass(ed|es)?\b", _text(trace)) is not None
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
}
FEATURE_START = ["branch_is_feature", "feature_folder", "docs_nonempty",
                 "spec_commit_is_docs", "no_code_before_spec", "tree_clean",
                 "result_success"]


def run_checks(repo, trace, names=None):
    return {n: CHECKS[n](repo, trace) for n in (names or FEATURE_START)}
