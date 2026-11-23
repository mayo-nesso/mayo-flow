"""Snapshot of what a trial left in its fixture, kept for a later judge.

The fixture is a temp dir deleted after the trial; the snapshot keeps the text
files new or changed vs the fixture's base commit (tracked, untracked and
ignored alike, so excluded files such as .claude/handoff.md count), the
branch, the commit subjects since the base, the task prompt and the final
reply. Binary files are skipped; each file and the total are size-capped.
"""
import json
import subprocess
from pathlib import Path

MAX_FILE = 20_000
MAX_TOTAL = 200_000


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout


def take_snapshot(repo, base, *, prompt, result_text, max_file=MAX_FILE,
                  max_total=MAX_TOTAL):
    repo = Path(repo)
    changed = _git(repo, "diff", "-z", "--name-only", base).split("\0")
    untracked = _git(repo, "ls-files", "-z", "--others").split("\0")
    files, truncated, omitted, total = {}, [], [], 0
    for rel in sorted({p for p in changed + untracked if p}):
        path = repo / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        cut = len(data) > max_file
        data = data[:max_file]
        if total + len(data) > max_total:
            omitted.append(rel)
            continue
        total += len(data)
        files[rel] = data.decode("utf-8", errors="ignore")
        if cut:
            truncated.append(rel)
    return {
        "prompt": prompt,
        "result_text": result_text,
        "branch": _git(repo, "branch", "--show-current").strip(),
        "commits": _git(repo, "log", "--reverse", "--format=%s",
                        f"{base}..HEAD").splitlines(),
        "files": files,
        "truncated": truncated,
        "omitted": omitted,
    }


def snapshot_path(trace_path):
    """The snapshot lives beside its trace: <stem>.snapshot.json."""
    trace_path = Path(trace_path)
    return trace_path.with_name(trace_path.stem + ".snapshot.json")


def write_snapshot(path, snap):
    Path(path).write_text(json.dumps(snap, indent=1, sort_keys=True),
                          encoding="utf-8")
