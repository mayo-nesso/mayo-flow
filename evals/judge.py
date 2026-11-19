"""LLM judge: score a trial's snapshot against the suite's rubric.

The judge is `claude -p` with no tools, no customizations (--safe-mode) and
an empty cwd, fed the task prompt and the snapshot only (never the condition,
skill or baseline). Its scores are appended to the results JSONL as a
separate line, {"kind": "judge", "trace_path": <the trial's>, ...}, because
the JSONL is append-only; a trial line has no "kind".
"""
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evals import record, snapshot

DEFAULT_MODEL = "haiku"
JUDGE_TIMEOUT = 300

SYSTEM = ("You are a strict reviewer scoring work done by a coding assistant. "
          "You have no tools. Reply with JSON only.")


def rubric_hash(path):
    return record.file_hash(path)


def build_prompt(rubric, snap):
    lines = [
        "Score the work below against each criterion, from 1 (poor) to 5 "
        "(excellent). Judge only what you can see: the task, the final "
        "reply, the commits and the files the work created or changed.",
        'Reply with only a JSON object mapping each criterion id to '
        '{"score": <integer 1-5>, "reason": "<one line>"}.',
        "", "# Criteria",
        *(f"- {c['id']}: {c['text']}" for c in rubric["criteria"]),
        "", "# Task", snap["prompt"],
        "", "# Final reply", snap.get("result_text") or "(none)",
        "", "# Branch at the end", snap.get("branch") or "(detached)",
        "", "# Commits made",
        *(f"- {c}" for c in snap.get("commits") or ["(none)"]),
        "", "# Files created or changed",
    ]
    for path, text in snap.get("files", {}).items():
        cut = " (truncated)" if path in snap.get("truncated", []) else ""
        lines += [f'<file path="{path}"{cut}>', text, "</file>"]
    if snap.get("omitted"):
        lines.append("Files left out for size: " + ", ".join(snap["omitted"]))
    return "\n".join(lines) + "\n"


def _json_object(text):
    candidates = [text]
    candidates += re.findall(r"```(?:json)?\s*(.*?)```", text, re.S)
    if "{" in text:
        candidates.append(text[text.index("{"):text.rindex("}") + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError(f"no JSON object in judge reply: {text[:300]!r}")


def parse_scores(text, rubric):
    """criterion id -> {"score": 1..5, "reason": str}; ValueError otherwise."""
    obj = _json_object(text)
    scores = {}
    for c in rubric["criteria"]:
        v = obj.get(c["id"])
        s = v.get("score") if isinstance(v, dict) else None
        if type(s) is not int or not 1 <= s <= 5:
            raise ValueError(f"bad or missing score for {c['id']!r}: "
                             f"{text[:300]!r}")
        scores[c["id"]] = {"score": s, "reason": str(v.get("reason", ""))}
    return scores


def _call(claude_bin, model, prompt, timeout):
    cmd = [claude_bin, "-p", "--output-format", "json", "--tools", "",
           "--safe-mode", "--no-session-persistence", "--system-prompt",
           SYSTEM, "--model", model]
    with tempfile.TemporaryDirectory() as cwd:
        r = subprocess.run(cmd, cwd=cwd, input=prompt, capture_output=True,
                           text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"claude exited {r.returncode}: {r.stderr[-300:]}")
    out = json.loads(r.stdout)
    if out.get("is_error"):
        raise RuntimeError(f"claude error: {str(out.get('result'))[:300]}")
    return out.get("result") or "", out.get("total_cost_usd")


def judge_trial(*, evals_dir, trace_path, rubric_path, claude_bin, model,
                timeout=JUDGE_TIMEOUT):
    """Judge the trial whose repo-relative trace is `trace_path`; return the
    judge record (errors are recorded, not raised)."""
    scores, cost, error = None, None, None
    try:
        snap_file = snapshot.snapshot_path(Path(evals_dir).parent / trace_path)
        if not snap_file.is_file():
            raise FileNotFoundError(f"no snapshot at {snap_file}")
        snap = json.loads(snap_file.read_text(encoding="utf-8"))
        rubric = json.loads(Path(rubric_path).read_text(encoding="utf-8"))
        reply, cost = _call(claude_bin, model, build_prompt(rubric, snap),
                            timeout)
        scores = parse_scores(reply, rubric)
    except Exception as e:  # noqa: BLE001
        error = f"judge failed: {e!r}"
    return {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": "judge",
        "trace_path": trace_path,
        "judge": scores,
        "judge_model": model,
        "rubric_hash": rubric_hash(rubric_path),
        "cost_usd": cost,
        "error": error,
    }


def unjudged(records, rubric_hash):
    """Trial records with no error-free judge line for this rubric."""
    done = {r["trace_path"] for r in records
            if r.get("kind") == "judge" and r["rubric_hash"] == rubric_hash
            and r["error"] is None}
    return [r for r in records
            if "kind" not in r and r["trace_path"] not in done]
