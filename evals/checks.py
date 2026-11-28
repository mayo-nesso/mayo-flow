"""Deterministic checks over a fixture repo left behind by a trial."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from evals.hidden_runner import discover
from evals.trace import agent_calls

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


# Delegate checks. They read the trace and the case's `agent_roles`, never the
# repo. The runner copies the case's `agent_roles` into the trace dict.
SELF_IMPL_TOOLS = ("Edit", "Write", "NotebookEdit")
SELF_IMPL_DIRS = ("/notesapi/", "/tests/")
ROLE_ORDER = ("review", "runtests", "critical", "mechanical")
ROLE_FIELD = {"review": "description", "runtests": "description",
              "critical": "prompt", "mechanical": "prompt"}


def _main_events(trace):
    """The events of the main thread: those with no parent tool use."""
    return [e for e in trace.get("events", [])
            if not e.get("parent_tool_use_id")]


def s1_delegated(trace):
    return bool(agent_calls(_main_events(trace)))


def _result_text(block):
    content = block.get("content")
    if isinstance(content, list):
        return " ".join(c.get("text") or "" for c in content)
    return content or ""


def s1_no_self_impl(trace):
    """The main thread edited no file under a source or test folder. An edit
    of a file that a conflicted `git merge` names is no self-implementation
    while the merge is open (until `git commit` or `git merge --abort`)."""
    merges = set()  # ids of main-thread `git merge` calls
    conflicted = []  # files named by an open merge conflict
    for e in _main_events(trace):
        message = e.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_result":
                if block.get("tool_use_id") in merges:
                    conflicted += re.findall(
                        r"Merge conflict in (\S+)", _result_text(block))
                continue
            if block.get("type") != "tool_use":
                continue
            name, inp = block.get("name"), block.get("input") or {}
            command = inp.get("command") or ""
            if name == "Bash":
                if re.search(r"git commit|git merge --abort", command):
                    conflicted = []
                elif re.search(r"git merge\b", command):
                    merges.add(block.get("id"))
                continue
            path = inp.get("file_path") or inp.get("notebook_path")
            # a leading slash lets a relative path match the folder names too
            if name in SELF_IMPL_TOOLS and any(
                    d in "/" + (path or "") for d in SELF_IMPL_DIRS):
                if not any(("/" + path).endswith("/" + c.lstrip("/"))
                           for c in conflicted):
                    return False
    return True


def s2_model_explicit(trace):
    calls = agent_calls(_main_events(trace))
    return bool(calls) and all(c["model"] for c in calls)


def _role_of(call, roles):
    """The first role (in ROLE_ORDER) whose regex matches the call. A case may
    leave out roles."""
    for role in ROLE_ORDER:
        if role in roles and re.search(roles[role],
                                       call[ROLE_FIELD[role]] or ""):
            return role
    return None


def _role_uses_model(trace, role, model):
    """At least one call has the role, and every such call uses `model`."""
    roles = trace.get("agent_roles")
    if not roles:
        return False
    models = [c["model"] for c in agent_calls(_main_events(trace))
              if _role_of(c, roles) == role]
    return bool(models) and all(m == model for m in models)


def s2_model_runtests_haiku(trace):
    return _role_uses_model(trace, "runtests", "haiku")


def s2_model_review_sonnet(trace):
    return _role_uses_model(trace, "review", "sonnet")


def s2_model_critical_opus(trace):
    return _role_uses_model(trace, "critical", "opus")


def s2_model_mechanical_sonnet(trace):
    return _role_uses_model(trace, "mechanical", "sonnet")


def s2_model_stated(trace):
    """Each model used is named in the text up to its first call."""
    said = ""
    seen = set()
    for call in agent_calls(_main_events(trace)):
        said += " " + call["text_before"]
        model = call["model"]
        if model and model not in seen:
            if not re.search(rf"\b{re.escape(model)}\b", said, re.I):
                return False
            seen.add(model)
    return bool(seen)


def _implementation_prompts(trace):
    """The prompts of the main-thread agents whose role is critical or
    mechanical. None when the trace has no roles."""
    roles = trace.get("agent_roles")
    if not roles:
        return None
    return [c["prompt"] or "" for c in agent_calls(_main_events(trace))
            if _role_of(c, roles) in ("critical", "mechanical")]


def _wave_prompts(trace):
    """The prompts of the agents of the parallel wave, or None when a wave
    ticket has no agent."""
    calls = _wave_calls(trace)
    if None in calls:
        return None
    return [c["prompt"] or "" for c in calls]


def _prompt_rule_check(rule_id, prompts_of=_implementation_prompts):
    """A check: every prompt that `prompts_of` gives (by default, those of
    the implementation agents) matches every regex that the case lists under
    prompt_rules[rule_id]. No agent or no rule fails."""
    def check(trace):
        prompts = prompts_of(trace)
        patterns = (trace.get("prompt_rules") or {}).get(rule_id)
        return bool(prompts) and bool(patterns) and all(
            re.search(rx, p) for p in prompts for rx in patterns)
    return check


s3_paths = _prompt_rule_check("s3_paths")
s3_constraints = _prompt_rule_check("s3_constraints")
s3_red_evidence = _prompt_rule_check("s3_red_evidence")
s3_full_suite = _prompt_rule_check("s3_full_suite")
s3_no_sed_i = _prompt_rule_check("s3_no_sed_i")
s3_and_chain = _prompt_rule_check("s3_and_chain")
s3_status_edit = _prompt_rule_check("s3_status_edit")
# Section 4 is about agents that run at the same time: only the parallel wave.
s4_new_files = _prompt_rule_check("s4_new_files", _wave_prompts)
PROMPT_RULE_CHECKS = ("s3_paths", "s3_constraints", "s3_red_evidence",
                      "s3_full_suite", "s3_no_sed_i", "s3_and_chain",
                      "s3_status_edit", "s4_new_files")


TASK_EVENTS = ("task_started", "task_notification")


def _blocks(trace):
    """(event index, content block) of every main-thread content block. A
    task_started or task_notification system event gives one pseudo block of
    that type, with its `tool_use_id` (and `task_id`)."""
    for i, e in enumerate(_main_events(trace)):
        if e.get("type") == "system" and e.get("subtype") in TASK_EVENTS:
            yield i, {"type": e["subtype"], "task_id": e.get("task_id"),
                      "tool_use_id": e.get("tool_use_id")}
            continue
        message = e.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            yield i, block


def _bash_commands(trace):
    return [(b.get("input") or {}).get("command") or ""
            for _, b in _blocks(trace)
            if b.get("type") == "tool_use" and b.get("name") == "Bash"]


def _worktree_paths(trace):
    """The path of every `git worktree add` the main thread ran."""
    paths = []
    for command in _bash_commands(trace):
        for part in re.split(r"&&|;|\|\|", command):
            words = part.split()
            if words[:3] != ["git", "worktree", "add"]:
                continue
            rest = iter(words[3:])
            for w in rest:
                if w in ("-b", "-B"):
                    next(rest, None)  # the branch name
                elif not w.startswith("-"):
                    paths.append(w)
                    break
    return paths


def _wave_calls(trace):
    """One Agent call per `parallel_wave` regex (None when there is none)."""
    calls = agent_calls(_main_events(trace))
    return [next((c for c in calls if re.search(rx, c["prompt"] or "")), None)
            for rx in trace.get("parallel_wave") or []]


def _path_in(path, text):
    """`path` (as given to `git worktree add`) is named in `text`. The
    coordinator often adds `../wt03` or `$W/t03` and puts the absolute path in
    the prompt, so we compare the last components that are not `..`, `.` or
    a shell variable. A component must match whole: `wt03` is not `wt030`."""
    parts = path.strip("'\"").rstrip("/").split("/")
    tail = []
    for part in reversed(parts):
        if part in ("", ".", "..") or part.startswith("$"):
            break
        tail.insert(0, part)
    if not tail:
        return False
    # When we dropped a leading part, the text must show a `/` before the
    # tail, so a branch name such as `t03` alone does not count as a path.
    start = "/" if len(tail) < len(parts) else r"(?<![\w./-])"
    # A full stop that ends a sentence may follow the path.
    rx = start + re.escape("/".join(tail)) + r"(?!/?(?:[\w-]|\.[\w.-]))"
    return re.search(rx, text) is not None


def s4_worktree_each(trace):
    """Each wave ticket has an agent with its own worktree: the isolation
    field says so, or a `git worktree add` path is in the agent's prompt."""
    calls = _wave_calls(trace)
    if not calls or None in calls:
        return False
    made = _worktree_paths(trace)
    used = []
    for call in calls:
        mine = [p for p in made if _path_in(p, call["prompt"] or "")]
        if call["isolation"] != "worktree" and not mine:
            return False
        used += mine
    return len(used) == len(set(used))


def s5_wave_order(trace):
    """The wave-two agent starts after the first wave-one agent returned."""
    calls = _wave_calls(trace)
    two = next((c for c in agent_calls(_main_events(trace))
                if re.search(trace.get("wave_two") or "(?!)",
                             c["prompt"] or "")), None)
    if not calls or calls[0] is None or two is None:
        return False
    seq = _sequence(trace)
    done = _handback_at(seq, calls[0]["id"])
    launch = next((i for i, b in enumerate(seq) if b.get("type") == "tool_use"
                   and b.get("id") == two["id"]), -1)
    return done is not None and launch > done


SUITE_RUN_RE = re.compile(r"(?i)unittest|run-tests|pytest")
MERGE_RE = re.compile(r"\bgit merge\b(?!-)(?!.*--abort)")


def _merge_and_suite_events(trace):
    """"merge" and "suite" in order: Bash merges, Bash suite runs and Agent
    calls whose role is runtests."""
    roles = trace.get("agent_roles") or {}
    out = []
    for _, b in _blocks(trace):
        if b.get("type") != "tool_use":
            continue
        inp = b.get("input") or {}
        if b.get("name") == "Bash":
            command = inp.get("command") or ""
            if MERGE_RE.search(command):
                out.append("merge")
            if SUITE_RUN_RE.search(command):
                out.append("suite")
        elif b.get("name") == "Agent" and _role_of(
                {"description": inp.get("description"),
                 "prompt": inp.get("prompt")}, roles) == "runtests":
            out.append("suite")
    return out


def s5_suite_after_merge(trace):
    events = _merge_and_suite_events(trace)
    merges = [i for i, e in enumerate(events) if e == "merge"]
    return bool(merges) and all(
        i + 1 < len(events) and events[i + 1] == "suite" for i in merges)


def s5_cleanup(repo, trace=None):
    """Only the main working tree and the branches main and feature/notes_api
    are left."""
    worktrees = _git(repo, "worktree", "list", "--porcelain").count("worktree ")
    branches = _git(repo, "branch", "--format=%(refname:short)").split()
    return worktrees == 1 and set(branches) == {BASE, "feature/notes_api"}


def _sequence(trace):
    """The main-thread content blocks in order, as a list."""
    return [b for _, b in _blocks(trace)]


def _is_impl_call(block, roles):
    inp = block.get("input") or {}
    return (block.get("type") == "tool_use" and block.get("name") == "Agent"
            and _role_of({"description": inp.get("description"),
                          "prompt": inp.get("prompt")}, roles)
            in ("critical", "mechanical"))


def _handback_at(seq, tool_use_id):
    """The position of the hand-back of the Agent call `tool_use_id`, or None.
    A background agent gets a launch notice as its tool result at once, and
    its hand-back comes later as a task_notification, so the notification
    wins over the tool result."""
    def first(kind):
        return next((j for j, r in enumerate(seq) if r.get("type") == kind
                     and r.get("tool_use_id") == tool_use_id), None)
    back = first("task_notification")
    return first("tool_result") if back is None else back


def _impl_handbacks(trace):
    """(launch position, hand-back position) of each implementation agent.
    The hand-back position is None when no hand-back came."""
    roles = trace.get("agent_roles") or {}
    seq = _sequence(trace)
    return [(i, _handback_at(seq, b.get("id")))
            for i, b in enumerate(seq) if _is_impl_call(b, roles)]


def _resumed_after(trace, pos):
    """A SendMessage after `pos` goes to an implementation agent: the
    coordinator sent the work back to the same agent."""
    roles = trace.get("agent_roles") or {}
    seq = _sequence(trace)
    impl_ids = {b.get("id") for b in seq if _is_impl_call(b, roles)}
    tasks = {b.get("task_id") for b in seq if b.get("type") == "task_started"
             and b.get("tool_use_id") in impl_ids}
    return any(b.get("type") == "tool_use" and b.get("name") == "SendMessage"
               and (b.get("input") or {}).get("to") in tasks
               for b in seq[pos + 1:])


def _suite_run_after(trace, pos):
    """The main thread runs the suite at a position later than `pos`."""
    roles = trace.get("agent_roles") or {}
    for b in _sequence(trace)[pos + 1:]:
        inp = b.get("input") or {}
        if b.get("type") != "tool_use":
            continue
        if b.get("name") == "Bash" and SUITE_RUN_RE.search(
                inp.get("command") or ""):
            return True
        if b.get("name") == "Agent" and _role_of(
                {"description": inp.get("description"),
                 "prompt": inp.get("prompt")}, roles) == "runtests":
            return True
    return False


def s6_reruns_suite(trace):
    """Every work agent handed back, and the suite runs after the latest
    hand-back. A work agent is any Agent call that is not a review or a suite
    run: the case roles name one ticket, but the skill verifies every
    hand-back."""
    roles = trace.get("agent_roles") or {}
    seq = _sequence(trace)
    backs = []
    for b in seq:
        if b.get("type") != "tool_use" or b.get("name") != "Agent":
            continue
        inp = b.get("input") or {}
        if _role_of({"description": inp.get("description"),
                     "prompt": inp.get("prompt")}, roles) \
                not in ("review", "runtests"):
            backs.append(_handback_at(seq, b.get("id")))
    return bool(backs) and None not in backs and _suite_run_after(
        trace, max(backs))


def _mutation_after(trace, pos):
    """The position of the first main-thread change of the source file after
    `pos` (a Bash command that matches `mutation_proof`, or an Edit or Write
    of notesapi/notes.py or notesapi/text.py), or None."""
    rx = trace.get("mutation_proof")
    for i, b in enumerate(_sequence(trace)):
        if i <= pos or b.get("type") != "tool_use":
            continue
        inp = b.get("input") or {}
        if b.get("name") == "Bash" and rx and re.search(
                rx, inp.get("command") or ""):
            return i
        if b.get("name") in ("Edit", "Write") and (
                inp.get("file_path") or "").endswith(
                    ("notesapi/notes.py", "notesapi/text.py")):
            return i
    return None


def s6_rejects_missing_red(trace):
    """After the first hand-back the coordinator redid the work (a new agent,
    or a SendMessage that sends it back to the same agent), or proved the
    test can fail and ran the suite, or named the gap in the final reply."""
    backs = _impl_handbacks(trace)
    if not backs or backs[0][1] is None:
        return False
    first_back = backs[0][1]
    if any(launch > first_back for launch, _ in backs[1:]):
        return True
    if _resumed_after(trace, first_back):
        return True
    mutated = _mutation_after(trace, first_back)
    if mutated is not None and _suite_run_after(trace, mutated):
        return True
    gap = trace.get("reply_names_gap")
    return bool(gap) and re.search(gap, trace.get("result_text") or "") is not None


def n_no_delegate(trace):
    return not s1_delegated(trace)


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
    "s1_delegated": lambda repo, trace: s1_delegated(trace),
    "s1_no_self_impl": lambda repo, trace: s1_no_self_impl(trace),
    "s2_model_explicit": lambda repo, trace: s2_model_explicit(trace),
    "s2_model_runtests_haiku": lambda repo, trace: s2_model_runtests_haiku(trace),
    "s2_model_review_sonnet": lambda repo, trace: s2_model_review_sonnet(trace),
    "s2_model_critical_opus": lambda repo, trace: s2_model_critical_opus(trace),
    "s2_model_mechanical_sonnet": lambda repo, trace: s2_model_mechanical_sonnet(trace),
    "s2_model_stated": lambda repo, trace: s2_model_stated(trace),
    **{name: (lambda repo, trace, f=globals()[name]: f(trace))
       for name in PROMPT_RULE_CHECKS},
    "s4_worktree_each": lambda repo, trace: s4_worktree_each(trace),
    "s5_wave_order": lambda repo, trace: s5_wave_order(trace),
    "s5_suite_after_merge": lambda repo, trace: s5_suite_after_merge(trace),
    "s5_cleanup": s5_cleanup,
    "s6_reruns_suite": lambda repo, trace: s6_reruns_suite(trace),
    "s6_rejects_missing_red": lambda repo, trace: s6_rejects_missing_red(trace),
    "n_no_delegate": lambda repo, trace: n_no_delegate(trace),
}
# The checks that read only the trace, not the fixture repo: `recheck` can
# recompute them from a stored trace.
TRACE_CHECKS = {"result_success", "reports_pass", "reports_fail",
                "proposes_audit", "reports_dirty", "no_audit_proposal",
                "s1_delegated", "s1_no_self_impl", "s2_model_explicit",
                "s2_model_runtests_haiku", "s2_model_review_sonnet",
                "s2_model_critical_opus", "s2_model_mechanical_sonnet",
                "s2_model_stated", *PROMPT_RULE_CHECKS,
                "s4_worktree_each", "s5_wave_order", "s5_suite_after_merge",
                "s6_reruns_suite", "s6_rejects_missing_red", "n_no_delegate"}
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
        message = e.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if block.get("type") == "tool_use":
                yield block.get("name"), block.get("input")


def _tool_uses(repo, base, trace, fact):
    return sum(name == fact["tool"] for name, _ in _tool_inputs(trace))


def _phase1_tool_uses(repo, base, trace, fact):
    """Tool uses named in fact["tools"] among the events of phase 1 only."""
    phase1 = {"events": trace.get("phase1_events", [])}
    return sum(name in fact["tools"] for name, _ in _tool_inputs(phase1))


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
              "phase1_tool_uses": _phase1_tool_uses,
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
