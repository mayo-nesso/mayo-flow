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


def run_checks(repo, trace):
    return {
        "branch_is_feature": branch_is_feature(repo),
        "feature_folder": feature_folder(repo) is not None,
        "docs_nonempty": docs_nonempty(repo),
        "spec_commit_is_docs": spec_commit_is_docs(repo),
        "no_code_before_spec": no_code_before_spec(repo),
        "tree_clean": tree_clean(repo),
        "result_success": result_success(trace),
    }
