# Skill evals

**Status:** steps 1-7 done (2026-11-19, merged). Cheap-skill suites `run-tests`, `gitignore`, `handoff` (WRITE) added and merged 2026-11-19 (one real trial each, all passed). Suites `project-init`, `fix-start`, `branch-finish`, `tickets` added 2026-11-19 (one real trial each, all passed; fix-start first failed on a too-strict check, fixed). Step 8 (LLM judge + baseline addendum) implemented 2026-11-19 on `feature/eval-judge`: snapshots, `run --baseline`, rubrics for every suite, `run --judge` / `judge <suite>`, skill-vs-baseline means in `report`; unit-tested with fake `claude` only. Two-phase handoff resume eval implemented 2026-11-19 on `feature/handoff-resume-eval` (suite `handoff-resume`, fixture `big-app`, `--condition skill|casual|floor`, fact checks as case data, token usage per trial and per phase, report per condition with deltas); unit-tested with fake `claude` only at first; first real runs 2026-11-23 (synthetic `waitlist` case and a private real-project case, see "Handoff resume results"). Open: the judge calibration against the owner's own scores, real judged runs of the other suites, the "Skill backlog" and the "Later" items, so this spec is not archived.

## Goal

Measure whether a skill change (v2 vs v3), a different model, or a different
skill makes Claude do the job better, using the same tasks each time, and keep
a history of the results. Start with `mayo-flow-feature-start`; add other
skills one at a time later (token cost).

Inspired by "Don't Ship Skills Without Evals" (Philipp Schmid): check outcomes
not paths, deterministic checks first, several trials per case, ablation
with/without the skill.

## Decisions

- Two kinds of case: `outcome` (run the skill forced via `/skill-name`, check
  the artifacts it leaves) for every skill; `trigger` (should/should not
  activate on a plain prompt) only for model-invocable skills. This spec
  covers `outcome` only; `trigger` comes later.
- Headless `claude -p` in a fresh throwaway git fixture per trial (temp dir,
  never inside a real repo). Questions are answered by prompt: "never ask,
  always pick the recommended answer".
- Permissions: a broad `Bash` allow list plus `acceptEdits`, fixture as the
  only cwd. No `bypassPermissions`. Every denial is recorded in the result.
  Protected paths (`.claude/`, `.git/`, ...) still prompt under `acceptEdits`
  and allow rules do not cover them, so `-p` denies Write/Edit there; a suite
  that needs one names it in `allow_writes`, and a PermissionRequest hook
  approves Write/Edit of exactly those paths (`evals/allow_writes_hook.py`).
- Every `claude -p` call (runner and judge) runs with
  `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`: auto memory lives in
  `~/.claude/projects/<cwd>/memory/`, outside the fixture, and would carry
  facts between phases, trials and conditions.
- Deterministic checks only (regex / git / filesystem) in v1. No LLM judge.
- Skill invocation is not visible in the `-p` trace (the slash command is
  expanded silently): assert on artifacts, never on a `Skill` tool call.
- Cases are versioned in git beside the tooling; results are a committed,
  append-only JSONL; raw traces go to an ignored directory.
- Comparing versions: `--skill-ref <git ref>` runs the skill as of that ref
  (extracted from git into a temp skills dir), so v2 and v3 run on the same
  cases.
- Out of scope (YAGNI): dashboard, other harnesses, ablation mode, trigger
  cases. The LLM judge is step 8, after v1 is merged.

## Later

- `run.py mine`: replay past Claude Code sessions (`~/.claude/projects/*/*.jsonl`)
  to find real trigger hits/misses, harvest real prompts as eval cases, and
  record descriptive metrics per skill version (`source: replay` in the JSONL).
  Descriptive only: not a fair v2-vs-v3 comparison (tasks, model and repo vary).
  Session transcripts are private: commit metrics only, never prompt text
  without review.

- `--skill-ref` for refs other than `working-tree` (finding, Claude Code
  2.1.327): `--plugin-dir` namespaces the skill, so the forced slash command
  would still hit `~/.claude/skills`. Experiment to try: extract the skill and
  its dependents (grill, spec, tickets) into the fixture's `.claude/skills/`,
  run with `--setting-sources project`, exclude them via `.git/info/exclude`.
  Needs one real run to verify. Until then compare versions by checking out
  the old version in the working tree; the JSONL records `skill_version` and
  `skill_hash`. `evals/skillref.py` already extracts a skill from a ref.


## Skill backlog (act on it only once more skills are evaluated)

Candidate changes to the skills themselves, noted from the evals so far.
Do not act on these yet: wait until more suites have real runs and the
framework (judge calibration, more cases per suite) is solid. Each entry is a
hypothesis, not a finding.

- `mayo-flow-handoff`, cost: on `handoff-resume` (2026-11-23, one case, n=3-4
  per condition) the skill used ~69% more tokens in the resume phase than the
  casual prompt (~1.1M vs ~0.6M) with no quality gain (judge 4.61 vs 4.67);
  on the real-project case +129% resume tokens (~$0.05 more) for +0.50 judge.
  Try a leaner resume path (fewer verification reads) and re-measure.
- `mayo-flow-handoff`, value: the handoff itself is what helps (floor: 0/3
  passed on the synthetic case, 2.00 vs 4.00-4.50 on the real one). The skill
  beat a casual handoff only on keeping standing rules (real project, +0.50
  judge, rules 4.33 vs 2.67) and tied it on autonomous continuity (synthetic).
  See "Handoff resume results". Still open: a second, harder case where a
  casual handoff can fail on continuity, and whether trimming the template to
  the parts that carry value (rules, unverified items, waiting-on-user) keeps
  the score at lower cost.
- `mayo-flow-handoff`, next-step approval: one trial recorded the next step as
  "needs your approval" and the resume then stopped. Consider making the skill
  state explicitly that settled decisions in the handoff are authorisation to
  continue.
- Harness noise to rule out first: permission denials in `casual`/`floor`
  trials (heredocs, `sed -i`) not caused by `.claude/` protection. If they
  persist they bias skill-vs-casual comparisons.

## Layout

```
evals/
  run.py                    runner (CLI: run, report)
  cases/<skill>/suite.json  cases for one skill (+ fixture definitions)
  fixtures/<name>/          fixture repo sources copied into a temp dir
  results/<skill>.jsonl     committed, append-only, one line per trial
  traces/                   gitignored raw stream-json
tests/test_evals_*.py       unit tests (no real claude calls)
```

Private suites: `run.py --evals-dir DIR <cmd> <suite>` replaces `evals/` by
another dir with the same layout (`cases/`, `fixtures/`, `results/`,
`traces/`). Use it for a suite built on a real project (its handoff, its code):
this repo is public, so that content stays outside it and only metrics are
written back into this spec.

## Result record (one JSONL line per trial)

`ts`, `skill`, `skill_version` (frontmatter), `skill_hash` (sha256 of the
skill directory contents), `skill_ref` (git ref or `working-tree`), `model`
(from the `init` event), `claude_version`, `case_id`, `suite_hash` (sha256 of
the case file), `trial`, `checks` (map name → bool), `passed` (all checks),
`cost_usd`, `duration_ms`, `num_turns`, `permission_denials` (count),
`trace_path`, `error` (null or string), `tokens` (input, output, cache
read, cache write, total; added 2026-11-19, null on older lines).

Results are comparable only when `suite_hash` matches.

## Report

`run.py report <skill>` reads the JSONL and prints a table: rows = case,
columns = (skill_version, skill_hash[:7], model), cell = passed/total trials.
Groups with a different `suite_hash` are shown separately and flagged.

## feature-start suite (v1)

Fixture: a small stdlib-only Python CLI repo (`unittest`, no pytest), clean
tree, `main`, with `docs/10_features/archived/`. A medium-sized feature
request so the grill is not skipped. Prompt forces: do not skip the grill,
pick recommended answers, stop right after committing the spec (and tickets
if the skill produces them), do not implement.

Checks: branch matches `feature/*`; feature folder matches
`docs/10_features/YYYY_MM_DD_<slug>/`; `grill.md` and `spec.md` exist and are
non-empty; spec commit is `docs: ...`; no code file changed before the spec
commit; working tree clean at the end; result event is `success`.

## Implementation plan (each step red → green, one commit each)

1. Trace parser: extract model, cost, turns, denials, result subtype from a
   stream-json file (tests use a trimmed real trace as test data).
2. Check functions over a fixture repo path (git/filesystem) with tests on
   hand-built repos.
3. Result record builder + JSONL append + `skill_hash`.
4. `report` table with suite_hash grouping.
5. `--skill-ref` extraction of a skill from git into a temp skills dir.
6. Runner: fixture copy, `claude -p` invocation (budget cap + timeout),
   wiring. Tested with a fake `claude` executable; one real run to finish.
7. feature-start suite file and fixture; README section.

8. LLM judge (quality score, after steps 1-7 work end to end):
   - Scores the artifacts a trial already left (grill.md, spec.md, tickets)
     against a rubric, reusing the stored trial output so the skill is not
     re-run. Rubric per skill in `evals/cases/<skill>/rubric.json`, 3-4
     criteria scored 1-5 (e.g. spec has goal/decisions/plan/tests; grill
     decisions are reflected in the spec; tickets are vertical slices with
     dependencies), each with a one-line reason.
   - The judge runs via `claude -p` (a different, cheaper model than the one
     judged where possible), JSON output, no tools. Scores go into the same
     JSONL record (`judge`: criterion -> score, `judge_model`, `rubric_hash`);
     `report` shows the mean per version next to pass/fail.
   - Needs the trial's artifacts kept (today the fixture is deleted):
     snapshot grill.md/spec.md/tickets into the traces dir.
   - Calibrate before trusting: compare judge scores with the owner's own on
     2-3 real specs; record the comparison in the spec or README.
   - Costs quota (one extra call per trial): off by default, `--judge` flag.

### Step 8 addendum: baseline (ablation) so the judge can show whether a skill helps

Decided 2026-11-19 (owner: "I need to see whether the skills actually help").
A quality score alone cannot say that; it needs the same task without the skill.

- `run --baseline`: same case, same fixture, same model, but the prompt has the
  leading `/<skill>` removed and skills are disabled for the run
  (`--disable-slash-commands` if the installed claude supports it; verify, and
  otherwise say so). Results carry `condition: "skill" | "baseline"`
  (absent = skill, for old lines).
- Deterministic process checks (branch name, grill.md, ...) legitimately fail
  in baseline; they are recorded but are not the comparison. The comparison is
  the judge score.
- Rubrics are therefore outcome-based and skill-agnostic ("states the goal",
  "decisions are explicit", "tickets are independently shippable"), never
  "has a grill.md". The judge sees an artifact snapshot (new/changed text files
  vs the fixture's base commit, size-capped), not the skill's file names.
- Judge sees the condition hidden: it receives the task prompt and the
  snapshot, not whether a skill was used.
- `report` shows, per case, mean judge score for skill vs baseline side by
  side, with n; it must say "not enough trials" under n=2 per condition rather
  than claim a difference.
- Same quota rules: `--judge` and `--baseline` are opt-in, 1 trial by default.

### Handoff resume eval (two phases)

Decided 2026-11-19 (owner: handoff exists so a fresh session can continue the
task without dragging the old context; the question is whether it did). The
written document alone is not the outcome; resuming from it is.

- **Phase 1**: a headless session on a large synthetic fixture (multi-module,
  `docs/structure.md`, migrations; modelled on the shape of a real project but
  with invented content, nothing from a real project: this repo is public)
  works a task halfway. The prompt plants facts that cannot be re-derived from
  the repo: a decision with its reason, a trap already discovered, a concrete
  next step, something done outside the repo. Then it is asked to prepare for
  `/clear`.
- **Phase 2**: a new `claude -p` with no history on the same working copy is
  told to pick up where it left off. Deterministic checks over planted facts:
  took the decided path, avoided the trap, did the planted next step, did not
  redo finished work, did not ask. Also record turns and cost of resuming.
- **Conditions**: `skill` (/mayo-flow-handoff write, then `retoma`), `casual`
  (plain "leave things ready to pick up", model writes its own notes), `floor`
  (no handoff, fresh session starts cold). Same judge/report machinery; the
  comparison is skill vs casual, with floor as the lower bound.
- Fixture is generated by a script or committed as small synthetic files; the
  planted facts live in the case file and must be fictional.
- Implemented as: case keys `prepare` (phase 1) and `prompt` (phase 2), one
  `claude -p` call each in the same copy (no `--resume`: phase 1 replays the
  session's facts in its prompt instead of doing the work live, so the
  halfway state is deterministic and built by the fixture's `setup.sh`).
  Planted facts are checked with `facts` entries (`unchanged`, `matches`,
  `kept_history`, `no_question`). Records keep `phase1`/`phase2` and sum
  both at the top level. Token usage was added for every suite at the same
  time (owner: "whether a skill improves the result and at what cost").

## Handoff resume results

First real runs, 2026-11-23, model claude-sonnet-5-5, Claude Code 2.1.328, skill
`mayo-flow-handoff` 2.1.0 (hash 0388ca0), judge opus, rubric per suite. Judge
means are 1-5. Costs are per trial, both phases.

**Synthetic `waitlist` case** (suite `handoff-resume`, fixture `big-app`; the
next step is autonomous work: a worker job, a registration, a new migration).
Runs from before the harness fixes below are excluded here.

| condition | n | checks passed | judge | cost | resume tokens |
|---|---|---|---|---|---|
| skill | 7 | 6/7 `next_step_job` | 4.61 | $0.54 | ~1.14M |
| casual | 3 | 3/3 | 4.67 | $0.38 | ~0.63M |
| floor | 3 | 0/3 `decision_not_inline` | 3.75 | $0.27 | ~0.57M |

Skill vs casual: -0.06 judge, +74% tokens in total, +82% in the resume phase.
The one skill failure was a trial where the resume stopped after a denied
command (see harness fixes).

**Private real-project case** (a real project, handoff of 2026-11-18, `main`
with nothing in flight and a "waiting on the user" list). The suite, fixture,
results and traces live outside this repo (`--evals-dir`); only metrics are
recorded here. Phase 1 gets a narrative of the real handoff's state, not the
real transcript, and the same text goes to skill and casual.

| condition | n | judge | orientation | honesty (unverified) | no decision for user | rules in force | cost |
|---|---|---|---|---|---|---|---|
| skill | 3 | 4.50 | 4.00 | 4.67 | 5.00 | 4.33 | $0.26 |
| casual | 3 | 4.00 | 4.00 | 4.67 | 4.67 | 2.67 | $0.17 |
| floor | 3 | 2.00 | 1.00 | 2.00 | 2.00 | 3.00 | $0.11 |

All trials passed the deterministic checks (no work started, history kept).
Skill vs casual: +0.50 judge, entirely from "rules in force" (the casual
handoff tends to drop the rules; the skill's template keeps them), +69% tokens
in total, +129% in the resume phase (about $0.10 more per handoff).

**Reading (n is small, one case per suite, a hint and not a proof):** a handoff
clearly helps (floor is far below in both). The skill does not beat a casual
handoff on continuity of autonomous work (synthetic), but it keeps rules and
restrictions better (real project), at a higher token cost. It earns its cost
mainly in projects with many standing rules. Caveats: the real-case narrative
was written from a skill-made handoff that listed the rules; the real-case
resume asks the user instead of working, so it does not measure continuity;
auto memory is off in evals, so a real resume would also load project memory.

**Harness fixes found along the way** (they, not the skill, caused the early
failures): `.claude/` is a protected path, so a Write there and the skill's
`rm .claude/handoff.md` on resume were denied in `-p` mode, and a denied `rm`
inside a compound command took the whole command down. Fixed by
`allow_writes_hook.py` (Write/Edit and `rm` of the named paths only). A
prepare prompt that did not pre-approve saving decisions made the handoff
record the next step as "needs your approval". Some `casual`/`floor` trials
still show permission denials on heredocs and `sed -i` (cause not yet found).

## Test cases

Unit tests for steps 1-6 using fake traces, hand-built repos and a fake
`claude` script; one manual real run of the feature-start suite recorded in
`results/`.
