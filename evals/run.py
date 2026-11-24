"""Eval runner CLI: `run <suite>`, `judge <suite>`, `recheck <suite>` and
`report <suite>`.

suite.json shape: {"skill": "<skill dir>", "fixture": "<name>",
"checks": [<check names>], "cases": [{"id": ..., "prompt": ...}]}
"checks" (default: the feature-start set, see evals/checks.py) and "fixture"
may be overridden per case. An optional suite-level "allow_writes" lists
protected paths (relative to the fixture, e.g. ".claude/handoff.md") that
Write/Edit may change: see evals/allow_writes_hook.py.
The suite name (evals/cases/<suite>/) names the results file and traces;
"skill" is the skill directory under the repo root.
`--evals-dir DIR` swaps evals/ for another dir with the same layout (cases/,
fixtures/, results/, traces/): how a private suite stays out of this public repo.
The fixture source is evals/fixtures/<name>/ (an optional setup.sh in it
builds branches after the initial commit, see prepare_fixture).
"""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evals import judge, record, recheck, snapshot
from evals.checks import fact_checks, run_checks
from evals.claude_env import claude_env
from evals.report import load_results, render_report
from evals.skillref import WORKING_TREE
from evals.trace import parse_trace

ALLOWED_TOOLS = "Bash Skill Agent Read Write Edit Glob Grep"
ALLOW_WRITES_HOOK = Path(__file__).resolve().parent / "allow_writes_hook.py"
BLOCK_SKILLS_HOOK = Path(__file__).resolve().parent / "block_skills_hook.py"

# Claude Code 2.1.327 has no verified way to run one skill version in
# isolation: --plugin-dir namespaces the skill (plugin:skill) while the
# user's own ~/.claude skill of the same name stays loaded, and skills that
# the skill calls (grill, spec, ...) would be missing from an isolated run.
REF_UNSUPPORTED = ("not supported yet: claude cannot be pointed at an "
                   "alternate skill version without shadowing or losing "
                   "~/.claude skills; only --skill-ref working-tree works")


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True,
                   capture_output=True)


def _join(first, second):
    return f"{first}; {second}" if first else second


SETUP_SCRIPT = "setup.sh"


def prepare_fixture(source, dest):
    """Copy the fixture into a fresh git repo on main (one initial commit).

    A fixture may ship a `setup.sh`: it is not copied, but run (bash, cwd =
    the copy) after the initial commit, to build branches or further commits.
    """
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(SETUP_SCRIPT))
    if not (dest / ".git").exists():
        _git(dest, "init", "-q", "-b", "main")
        _git(dest, "config", "user.email", "eval@example.com")
        _git(dest, "config", "user.name", "eval")
        _git(dest, "add", "-A")
        _git(dest, "commit", "-q", "-m", "chore: fixture")
    setup = Path(source).resolve() / SETUP_SCRIPT
    if setup.is_file():
        subprocess.run(["bash", str(setup)], cwd=dest, check=True,
                       capture_output=True)


def strip_skill(prompt, skill):
    """The prompt without its leading `/<skill>` slash command (unchanged
    when it has none)."""
    head = f"/{skill}"
    if not (prompt.startswith(head)
            and prompt[len(head):len(head) + 1] in ("", " ", "\n")):
        return prompt
    return prompt[len(head):].lstrip()


def expand_prompts(case):
    """The case with `{feature}` and `{headless}` expanded in prepare, prompt
    and direct. Plain replace on those two names, so any other brace in the
    feature text stays as it is."""
    out = dict(case)
    for key in ("prepare", "prompt", "direct"):
        if key in out:
            for name in ("feature", "headless"):
                out[key] = out[key].replace("{%s}" % name, case.get(name, ""))
    return out


# skill: the prompt as written. baseline (one-phase cases) and casual and
# floor (two-phase cases): the prompt without its leading /<skill>, slash
# commands disabled and ~/.claude/skills unreadable (block_skills_hook.py).
# floor also skips phase 1, so phase 2 starts cold. baseline on a two-phase
# case needs a "direct" prompt: it skips phase 1 and runs that, as the last
# (only) call.
CONDITIONS = ("skill", "baseline", "casual", "floor")
TWO_PHASE_CONDITIONS = ("skill", "casual", "floor")


def check_condition(case, condition):
    """SystemExit if `condition` does not apply to `case`."""
    two_phase = "prepare" in case
    if (two_phase and condition not in TWO_PHASE_CONDITIONS
            and not (condition == "baseline" and "direct" in case)):
        raise SystemExit(f"case {case['id']} has two phases: use --condition "
                         f"skill, casual or floor, not {condition} (baseline "
                         f"needs a \"direct\" prompt)")
    if not two_phase and condition in ("casual", "floor"):
        raise SystemExit(f"--condition {condition} needs a two-phase case "
                         f"(with \"prepare\"); {case['id']} has none")


def _hook_settings(allow_writes, block_skills):
    """--settings JSON, or None when no hook is needed. allow_writes: a
    PermissionRequest hook that approves Write/Edit and Bash `rm` of those
    paths only (protected paths that acceptEdits still prompts for).
    block_skills: a PreToolUse hook that denies reads of ~/.claude/skills."""
    hooks = {}
    if allow_writes:
        command = shlex.join(
            [sys.executable, str(ALLOW_WRITES_HOOK), *allow_writes])
        hooks["PermissionRequest"] = [
            {"matcher": "Write|Edit|Bash",
             "hooks": [{"type": "command", "command": command}]}]
    if block_skills:
        command = shlex.join([sys.executable, str(BLOCK_SKILLS_HOOK)])
        hooks["PreToolUse"] = [
            {"matcher": "Bash|Read|Glob|Grep",
             "hooks": [{"type": "command", "command": command}]}]
    return json.dumps({"hooks": hooks}) if hooks else None


def _claude_cmd(claude_bin, prompt, *, model, budget, plain,
                allow_writes=()):
    cmd = [claude_bin, "-p", prompt, "--output-format", "stream-json",
           "--verbose", "--permission-mode", "acceptEdits",
           "--allowed-tools", ALLOWED_TOOLS]
    settings = _hook_settings(allow_writes, block_skills=plain)
    if settings:
        cmd += ["--settings", settings]
    if plain:
        cmd.append("--disable-slash-commands")
    if model:
        cmd += ["--model", model]
    if budget:
        cmd += ["--max-budget-usd", str(budget)]
    return cmd


def _invoke(cmd, repo, trace_path, timeout):
    """One claude call streaming into trace_path; an error string or None."""
    with open(trace_path, "w", encoding="utf-8") as out:
        try:
            r = subprocess.run(cmd, cwd=repo, stdin=subprocess.DEVNULL,
                               stdout=out, stderr=subprocess.PIPE,
                               text=True, timeout=timeout, env=claude_env())
        except subprocess.TimeoutExpired:
            return f"timeout after {timeout}s"
    if r.returncode != 0:
        return f"claude exited {r.returncode}: {r.stderr[-300:]}"
    return None


def _phase(trace, trace_path, error):
    """What a two-phase record keeps of one phase."""
    return {"trace_path": trace_path, "cost_usd": trace.get("cost_usd"),
            "num_turns": trace.get("num_turns"),
            "duration_ms": trace.get("duration_ms"),
            "tokens": trace.get("tokens"), "error": error}


def _add(a, b):
    if a is None or b is None:
        return b if a is None else a
    if isinstance(a, dict):
        return {k: a.get(k, 0) + b.get(k, 0) for k in {**a, **b}}
    return a + b


def _both_phases(first, second):
    """Phase 2's trace summary with cost, turns, time and tokens summed over
    both phases, so a two-phase trial's top-level numbers are its total."""
    total = dict(second)
    for key in ("cost_usd", "num_turns", "duration_ms", "tokens"):
        total[key] = _add(first.get(key), second.get(key))
    total["permission_denials"] = (first.get("permission_denials", [])
                                   + second.get("permission_denials", []))
    return total


def _parse(trace_path):
    try:
        return parse_trace(trace_path)
    except Exception:  # noqa: BLE001  (empty or cut trace of a failed call)
        return {}


def run_trial(*, name, case, suite, suite_hash, trial, evals_dir, repo_root,
              claude_bin, model, budget, timeout, condition="skill"):
    """One trial. A case with "prepare" has two phases in the same working
    copy: phase 1 runs `prepare` (the earlier session, about to /clear),
    phase 2 runs `prompt` as a new claude call with no history."""
    evals_dir = Path(evals_dir)
    case = expand_prompts(case)
    # fact dirs (hidden tests) are relative to the suite folder
    facts = [dict(f, dir=str(evals_dir / "cases" / name / f["dir"]))
             if "dir" in f else f for f in case.get("facts", [])]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    trace_path = evals_dir / "traces" / name / f"{case['id']}-{stamp}-{trial}.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    phase1_path = trace_path.with_name(trace_path.stem + ".phase1.jsonl")
    rel = lambda p: p.relative_to(evals_dir.parent).as_posix()  # noqa: E731
    skill = suite["skill"]
    two_phase = "prepare" in case
    plain = condition != "skill"
    call = dict(model=model, budget=budget, plain=plain,
                allow_writes=suite.get("allow_writes", ()))
    # The task without the skill: what a plain run gets, and the only prompt
    # the judge ever sees, so the judge cannot tell the condition.
    task = case.get("direct") or strip_skill(case["prompt"], skill)
    if two_phase and "direct" not in case:
        task = (f"Earlier session:\n{strip_skill(case['prepare'], skill)}\n\n"
                f"New session, after the context was cleared:\n{task}")

    error, phase1, first = None, None, {}
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "fixture"
        prepare_fixture(
            evals_dir / "fixtures" / case.get("fixture", suite["fixture"]),
            repo)
        base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              check=True, capture_output=True,
                              text=True).stdout.strip()
        if two_phase and condition not in ("floor", "baseline"):
            prepare = case["prepare"]
            p1_error = _invoke(_claude_cmd(
                claude_bin, strip_skill(prepare, skill) if plain else prepare,
                **call), repo, phase1_path, timeout)
            first = _parse(phase1_path)
            phase1 = _phase(first, rel(phase1_path), p1_error)
            if p1_error:
                error = f"phase 1 failed, phase 2 not run: {p1_error}"
        if error is None:
            last = (case["direct"] if condition == "baseline"
                    and "direct" in case else
                    strip_skill(case["prompt"], skill) if plain
                    else case["prompt"])
            error = _invoke(_claude_cmd(claude_bin, last, **call),
                            repo, trace_path, timeout)
        else:
            trace_path.touch()
        # Past this point the (expensive) claude call is done: never lose it.
        trace, checks, check_error, observed = {}, {}, None, {}
        try:
            trace = parse_trace(trace_path)
        except Exception as e:  # noqa: BLE001
            check_error = e
        # Keep what the trial left, so a judge can score it after the fixture
        # is gone (see evals/snapshot.py). Before the checks: they may run
        # code that writes into the repo.
        try:
            snapshot.write_snapshot(
                snapshot.snapshot_path(trace_path),
                snapshot.take_snapshot(repo, base, prompt=task,
                                       result_text=trace.get("result_text")))
        except Exception as e:  # noqa: BLE001
            error = _join(error, f"snapshot failed: {e!r}")
        if check_error is None:
            try:
                checks = run_checks(
                    repo, trace, case.get("checks", suite.get("checks")))
                checks.update(fact_checks(repo, base, trace, facts))
                # observations see both phases' events
                observed = fact_checks(
                    repo, base,
                    dict(trace, events=first.get("events", [])
                         + trace.get("events", [])),
                    case.get("observe", []))
            except Exception as e:  # noqa: BLE001
                check_error = e
        if check_error is not None:
            error = _join(error, f"checks failed: {check_error!r}")

    rel_trace = rel(trace_path)
    extra = {}
    if two_phase:
        extra = {"phase1": phase1,
                 "phase2": _phase(trace, rel_trace,
                                  "not run" if phase1 and phase1["error"]
                                  else error)}
        trace = _both_phases(first, trace)
    skill_dir = Path(repo_root) / skill
    try:
        rec = record.build_record(
            skill=skill, skill_version=record.skill_version(skill_dir),
            skill_hash=record.skill_hash(skill_dir), skill_ref=WORKING_TREE,
            case_id=case["id"], suite_hash=suite_hash, trial=trial,
            checks=checks, trace=trace, trace_path=rel_trace,
            error=error, condition=condition)
    except Exception as e:  # noqa: BLE001
        rec = record.build_record(
            skill=skill, skill_version=None, skill_hash=None,
            skill_ref=WORKING_TREE, case_id=case["id"], suite_hash=suite_hash,
            trial=trial, checks={}, trace=trace, trace_path=rel_trace,
            error=_join(error, f"record failed for {skill_dir}: {e!r}"),
            condition=condition)
    rec.update(extra)
    if "observe" in case:
        rec["observed"] = observed  # descriptive: never part of `passed`
    # suite_hash covers suite.json only, so the hidden tests get their own
    hidden = [Path(f["dir"]) for f in facts if f["kind"] == "hidden_tests"]
    if hidden and hidden[0].is_dir():
        rec["hidden_hash"] = record.skill_hash(hidden[0])
    if plain:
        rec["isolation"] = "skills-blocked"  # see block_skills_hook.py
    record.append_result(evals_dir / "results" / f"{name}.jsonl", rec)
    return rec


def judge_and_record(trial_rec, *, results_path, evals_dir, rubric_path,
                     claude_bin, model):
    """Judge one trial, append the judge line, return a one-line summary."""
    j = judge.judge_trial(evals_dir=evals_dir,
                          trace_path=trial_rec["trace_path"],
                          rubric_path=rubric_path, claude_bin=claude_bin,
                          model=model)
    record.append_result(results_path, j)
    if j["judge"] is None:
        return f"judge error: {j['error']}"
    return f"judge {judge.mean(j['judge']):.2f}"


def main(argv=None, *, evals_dir=None, repo_root=None):
    here = Path(__file__).resolve().parent
    evals_dir = Path(evals_dir or here)
    repo_root = Path(repo_root or here.parent)

    p = argparse.ArgumentParser(prog="run.py")
    p.add_argument("--evals-dir", help="use this dir (with cases/, fixtures/, "
                   "results/, traces/) instead of evals/, e.g. a private "
                   "suite kept outside this public repo")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("skill", metavar="suite")
    r.add_argument("--trials", type=int, default=1)
    r.add_argument("--skill-ref", default=WORKING_TREE)
    r.add_argument("--model")
    r.add_argument("--max-budget-usd", default="5")
    r.add_argument("--timeout", type=int, default=900)
    r.add_argument("--condition", choices=CONDITIONS, default="skill",
                   help="skill, baseline (one-phase cases), or casual / "
                        "floor (two-phase cases)")
    r.add_argument("--baseline", action="store_true",
                   help="same as --condition baseline")
    r.add_argument("--judge", action="store_true",
                   help="score each trial with the LLM judge (extra call)")
    r.add_argument("--judge-model", default=judge.DEFAULT_MODEL)
    j = sub.add_parser("judge", help="judge stored snapshots not yet judged")
    j.add_argument("skill", metavar="suite")
    j.add_argument("--judge-model", default=judge.DEFAULT_MODEL)
    sub.add_parser("recheck", help="recompute stored reply checks from "
                   "local traces with the current evals/checks.py (no "
                   "model call)").add_argument("skill", metavar="suite")
    sub.add_parser("report").add_argument("skill", metavar="suite")
    args = p.parse_args(argv)
    if args.evals_dir:
        evals_dir = Path(args.evals_dir).resolve()

    results_path = evals_dir / "results" / f"{args.skill}.jsonl"
    if args.cmd == "report":
        print(render_report(load_results(results_path)))
        return

    if args.cmd == "recheck":
        print(recheck.render_summary(recheck.recheck(
            evals_dir, args.skill,
            today=datetime.now(timezone.utc).strftime("%Y-%m-%d"))))
        return

    claude_bin = os.environ.get("EVALS_CLAUDE_BIN", "claude")
    rubric_path = evals_dir / "cases" / args.skill / "rubric.json"
    judging = args.cmd == "judge" or args.judge
    if judging and not rubric_path.is_file():
        raise SystemExit(f"no rubric at {rubric_path}")
    judge_kw = dict(results_path=results_path, evals_dir=evals_dir,
                    rubric_path=rubric_path, claude_bin=claude_bin,
                    model=args.judge_model) if judging else {}

    if args.cmd == "judge":
        pending = judge.unjudged(load_results(results_path),
                                 judge.rubric_hash(rubric_path),
                                 args.judge_model)
        for rec in pending:
            label = (f"{rec['case_id']} trial {rec['trial']} "
                     f"({rec['trace_path']})")
            if not snapshot.snapshot_path(
                    evals_dir.parent / rec["trace_path"]).is_file():
                print(f"{label}: no snapshot, skipped")
                continue
            print(f"{label}: {judge_and_record(rec, **judge_kw)}")
        return

    if args.skill_ref != WORKING_TREE:
        raise SystemExit(REF_UNSUPPORTED)
    suite_path = evals_dir / "cases" / args.skill / "suite.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    suite_hash = record.file_hash(suite_path)
    condition = "baseline" if args.baseline else args.condition
    for case in suite["cases"]:
        check_condition(case, condition)
    stored = [r for r in load_results(results_path) if "kind" not in r]
    for case in suite["cases"]:
        # number after the highest stored trial of this suite, case and
        # condition, so batches never repeat a number
        first = 1 + max((r["trial"] for r in stored
                         if r["suite_hash"] == suite_hash
                         and r["case_id"] == case["id"]
                         and r.get("condition", "skill") == condition),
                        default=0)
        for trial in range(first, first + args.trials):
            rec = run_trial(
                name=args.skill, case=case, suite=suite,
                suite_hash=suite_hash, trial=trial, evals_dir=evals_dir,
                repo_root=repo_root, claude_bin=claude_bin, model=args.model,
                budget=args.max_budget_usd, timeout=args.timeout,
                condition=condition)
            line = f"{case['id']} trial {trial}: " \
                   f"{'pass' if rec['passed'] else 'FAIL'}"
            if args.judge:
                line += f", {judge_and_record(rec, **judge_kw)}"
            print(line)


if __name__ == "__main__":
    main()
