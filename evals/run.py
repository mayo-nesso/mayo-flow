"""Eval runner CLI: `run <suite>`, `judge <suite>` and `report <suite>`.

suite.json shape: {"skill": "<skill dir>", "fixture": "<name>",
"checks": [<check names>], "cases": [{"id": ..., "prompt": ...}]}
"checks" (default: the feature-start set, see evals/checks.py) and "fixture"
may be overridden per case.
The suite name (evals/cases/<suite>/) names the results file and traces;
"skill" is the skill directory under the repo root.
The fixture source is evals/fixtures/<name>/ (an optional setup.sh in it
builds branches after the initial commit, see prepare_fixture).
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from evals import judge, record, snapshot
from evals.checks import run_checks
from evals.report import load_results, render_report
from evals.skillref import WORKING_TREE
from evals.trace import parse_trace

ALLOWED_TOOLS = "Bash Skill Agent Read Write Edit Glob Grep"

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
    """The prompt without its leading `/<skill>` slash command."""
    head = f"/{skill}"
    if not (prompt.startswith(head)
            and prompt[len(head):len(head) + 1] in ("", " ", "\n")):
        raise ValueError(f"prompt does not start with {head}")
    return prompt[len(head):].lstrip()


def run_trial(*, name, case, suite, suite_hash, trial, evals_dir, repo_root,
              claude_bin, model, budget, timeout, baseline=False):
    evals_dir = Path(evals_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    trace_path = evals_dir / "traces" / name / f"{case['id']}-{stamp}-{trial}.jsonl"
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    # The task without the skill: what a baseline run gets, and the only
    # prompt the judge ever sees, so the judge cannot tell the condition.
    task = strip_skill(case["prompt"], suite["skill"])
    cmd = [claude_bin, "-p", task if baseline else case["prompt"],
           "--output-format", "stream-json",
           "--verbose", "--permission-mode", "acceptEdits",
           "--allowed-tools", ALLOWED_TOOLS]
    if baseline:
        cmd.append("--disable-slash-commands")
    if model:
        cmd += ["--model", model]
    if budget:
        cmd += ["--max-budget-usd", str(budget)]

    error = None
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "fixture"
        prepare_fixture(
            evals_dir / "fixtures" / case.get("fixture", suite["fixture"]),
            repo)
        base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              check=True, capture_output=True,
                              text=True).stdout.strip()
        with open(trace_path, "w", encoding="utf-8") as out:
            try:
                r = subprocess.run(cmd, cwd=repo, stdin=subprocess.DEVNULL,
                                   stdout=out, stderr=subprocess.PIPE,
                                   text=True, timeout=timeout)
                if r.returncode != 0:
                    error = f"claude exited {r.returncode}: {r.stderr[-300:]}"
            except subprocess.TimeoutExpired:
                error = f"timeout after {timeout}s"
        # Past this point the (expensive) claude call is done: never lose it.
        trace, checks = {}, {}
        try:
            trace = parse_trace(trace_path)
            checks = run_checks(
                repo, trace, case.get("checks", suite.get("checks")))
        except Exception as e:  # noqa: BLE001
            error = _join(error, f"checks failed: {e!r}")
        # Keep what the trial left, so a judge can score it after the fixture
        # is gone (see evals/snapshot.py).
        try:
            snapshot.write_snapshot(
                snapshot.snapshot_path(trace_path),
                snapshot.take_snapshot(repo, base, prompt=task,
                                       result_text=trace.get("result_text")))
        except Exception as e:  # noqa: BLE001
            error = _join(error, f"snapshot failed: {e!r}")

    rel_trace = trace_path.relative_to(evals_dir.parent).as_posix()
    condition = "baseline" if baseline else "skill"
    skill = suite["skill"]
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
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("skill", metavar="suite")
    r.add_argument("--trials", type=int, default=1)
    r.add_argument("--skill-ref", default=WORKING_TREE)
    r.add_argument("--model")
    r.add_argument("--max-budget-usd", default="5")
    r.add_argument("--timeout", type=int, default=900)
    r.add_argument("--baseline", action="store_true",
                   help="run the task without the skill (ablation)")
    r.add_argument("--judge", action="store_true",
                   help="score each trial with the LLM judge (extra call)")
    r.add_argument("--judge-model", default=judge.DEFAULT_MODEL)
    j = sub.add_parser("judge", help="judge stored snapshots not yet judged")
    j.add_argument("skill", metavar="suite")
    j.add_argument("--judge-model", default=judge.DEFAULT_MODEL)
    sub.add_parser("report").add_argument("skill", metavar="suite")
    args = p.parse_args(argv)

    results_path = evals_dir / "results" / f"{args.skill}.jsonl"
    if args.cmd == "report":
        print(render_report(load_results(results_path)))
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
                                 judge.rubric_hash(rubric_path))
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
    for case in suite["cases"]:
        for trial in range(1, args.trials + 1):
            rec = run_trial(
                name=args.skill, case=case, suite=suite,
                suite_hash=suite_hash, trial=trial, evals_dir=evals_dir,
                repo_root=repo_root, claude_bin=claude_bin, model=args.model,
                budget=args.max_budget_usd, timeout=args.timeout,
                baseline=args.baseline)
            line = f"{case['id']} trial {trial}: " \
                   f"{'pass' if rec['passed'] else 'FAIL'}"
            if args.judge:
                line += f", {judge_and_record(rec, **judge_kw)}"
            print(line)


if __name__ == "__main__":
    main()
