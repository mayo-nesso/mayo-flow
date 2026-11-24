"""LLM judge: score a trial's snapshot against the suite's rubric.

The judge is `claude -p` with no tools, no customizations (--safe-mode), no
auto memory and an empty cwd, fed the task prompt and the snapshot only (never the condition,
skill or baseline). Its scores are appended to the results JSONL as a
separate line, {"kind": "judge", "trace_path": <the trial's>, ...}, because
the JSONL is append-only; a trial line has no "kind".
"""
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evals import record, snapshot
from evals.claude_env import claude_env
from evals.trace import UsageLimit, usage_limit

DEFAULT_MODEL = "haiku"
JUDGE_TIMEOUT = 300

SYSTEM = ("You are a strict reviewer scoring work done by a coding assistant. "
          "You have no tools. Reply with JSON only.")


def rubric_hash(path):
    return record.file_hash(path)


def _work_lines(snap):
    """The task and what the work left, as the judge sees it."""
    lines = [
        "# Task", snap["prompt"],
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
    return lines


def build_prompt(rubric, snap):
    lines = [
        "Score the work below against each criterion, from 1 (poor) to 5 "
        "(excellent). Judge only what you can see: the task, the final "
        "reply, the commits and the files the work created or changed.",
        'Reply with only a JSON object mapping each criterion id to '
        '{"score": <integer 1-5>, "reason": "<one line>"}.',
        "", "# Criteria",
        *(f"- {c['id']}: {c['text']}" for c in rubric["criteria"]),
        "", *_work_lines(snap)]
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


LABELS = ("explicit", "silent")


def open_decisions(decisions):
    """The decisions no code dictates: the ones the judge labels."""
    return [d for d in decisions if d.get("open")]


def decisions_hash(decisions):
    """Hash of the open decisions (id and text), so labels of reworded
    decisions are not mistaken for current ones."""
    key = [[d["id"], d["text"]] for d in open_decisions(decisions)]
    return hashlib.sha256(json.dumps(key).encode()).hexdigest()


def build_decisions_prompt(decisions, snap):
    lines = [
        "Below are decisions the task leaves open. For each one, say whether "
        "the work states its choice (in the final reply, a document it wrote "
        "or a commit subject: label \"explicit\") or just picks one without "
        "saying so (label \"silent\"). Judge only what you can see.",
        'Reply with only a JSON object mapping each decision id to '
        '{"label": "explicit" or "silent", "reason": "<one line>"}.',
        "", "# Decisions",
        *(f"- {d['id']}: {d['text']}" for d in open_decisions(decisions)),
        "", *_work_lines(snap)]
    return "\n".join(lines) + "\n"


def parse_decisions(text, decisions):
    """decision id -> {"label": explicit|silent, "reason": str} for every
    open decision; ValueError otherwise."""
    obj = _json_object(text)
    labels = {}
    for d in open_decisions(decisions):
        v = obj.get(d["id"])
        label = v.get("label") if isinstance(v, dict) else None
        if label not in LABELS:
            raise ValueError(f"bad or missing label for {d['id']!r}: "
                             f"{text[:300]!r}")
        labels[d["id"]] = {"label": label, "reason": str(v.get("reason", ""))}
    return labels


def mean(scores):
    """Mean of the criterion scores of one judgement."""
    return sum(v["score"] for v in scores.values()) / len(scores)


def _call(claude_bin, model, prompt, timeout):
    cmd = [claude_bin, "-p", "--output-format", "json", "--tools", "",
           "--safe-mode", "--no-session-persistence", "--system-prompt",
           SYSTEM, "--model", model]
    with tempfile.TemporaryDirectory() as cwd:
        r = subprocess.run(cmd, cwd=cwd, input=prompt, capture_output=True,
                           text=True, timeout=timeout, env=claude_env())
    if r.returncode != 0:
        try:
            event = json.loads(r.stdout)
        except ValueError:
            event = None
        limit = usage_limit(event, r.stderr)
        if limit:
            raise UsageLimit(limit)
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
    except UsageLimit:
        raise  # the caller stops the batch; no line is written
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


def unjudged(records, rubric_hash, judge_model):
    """Trial records with no error-free judge line for this rubric and
    judge model."""
    done = {r["trace_path"] for r in records
            if r.get("kind") == "judge" and r["rubric_hash"] == rubric_hash
            and r["judge_model"] == judge_model and r["error"] is None}
    return [r for r in records
            if "kind" not in r and r["trace_path"] not in done]


def judge_decisions(*, evals_dir, trace_path, decisions, claude_bin, model,
                    timeout=JUDGE_TIMEOUT):
    """Label the open `decisions` of the trial whose repo-relative trace is
    `trace_path`; return the "decisions" record (errors are recorded, not
    raised)."""
    labels, cost, error = None, None, None
    try:
        snap_file = snapshot.snapshot_path(Path(evals_dir).parent / trace_path)
        if not snap_file.is_file():
            raise FileNotFoundError(f"no snapshot at {snap_file}")
        snap = json.loads(snap_file.read_text(encoding="utf-8"))
        reply, cost = _call(claude_bin, model,
                            build_decisions_prompt(decisions, snap), timeout)
        labels = parse_decisions(reply, decisions)
    except UsageLimit:
        raise
    except Exception as e:  # noqa: BLE001
        error = f"decisions judge failed: {e!r}"
    return {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": "decisions",
        "trace_path": trace_path,
        "decisions": labels,
        "judge_model": model,
        "decisions_hash": decisions_hash(decisions),
        "cost_usd": cost,
        "error": error,
    }


def unlabelled(records, decisions_by_case, judge_model):
    """Trial records whose case has open decisions and that have no
    error-free label line of this model for the current decisions."""
    done = {(r["trace_path"], r["decisions_hash"]) for r in records
            if r.get("kind") == "decisions" and r["judge_model"] == judge_model
            and r["error"] is None}
    return [r for r in records
            if "kind" not in r
            and open_decisions(decisions_by_case.get(r["case_id"], []))
            and (r["trace_path"], decisions_hash(
                decisions_by_case[r["case_id"]])) not in done]
