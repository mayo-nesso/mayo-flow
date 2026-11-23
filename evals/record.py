"""Result record builder, JSONL append and skill/suite hashing."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def skill_hash(skill_dir):
    """sha256 over every file's relative path and bytes, in sorted order."""
    root = Path(skill_dir)
    h = hashlib.sha256()
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        h.update(p.relative_to(root).as_posix().encode() + b"\0")
        h.update(p.read_bytes() + b"\0")
    return h.hexdigest()


def skill_version(skill_dir):
    text = (Path(skill_dir) / "SKILL.md").read_text(encoding="utf-8")
    m = re.search(r"^version:\s*(\S+)\s*$", text, re.M)
    return m.group(1) if m else None


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_record(*, skill, skill_version, skill_hash, skill_ref, case_id,
                 suite_hash, trial, checks, trace, trace_path, error=None,
                 ts=None, condition="skill"):
    return {
        "ts": ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "skill": skill,
        "skill_version": skill_version,
        "skill_hash": skill_hash,
        "skill_ref": skill_ref,
        "model": trace.get("model"),
        "claude_version": trace.get("claude_version"),
        "case_id": case_id,
        "suite_hash": suite_hash,
        "trial": trial,
        "checks": checks,
        "passed": bool(checks) and all(checks.values()) and error is None,
        "cost_usd": trace.get("cost_usd"),
        "duration_ms": trace.get("duration_ms"),
        "num_turns": trace.get("num_turns"),
        "tokens": trace.get("tokens"),
        "permission_denials": len(trace.get("permission_denials", [])),
        "trace_path": trace_path,
        "error": error,
        "condition": condition,
    }


def append_result(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
