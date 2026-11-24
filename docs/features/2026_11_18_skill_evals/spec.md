# Skill evals

**Status:** steps 1-7 done (2026-11-19, merged). Cheap-skill suites `run-tests`, `gitignore`, `handoff` (WRITE) added and merged 2026-11-19 (one real trial each, all passed). Suites `project-init`, `fix-start`, `branch-finish`, `tickets` added 2026-11-19 (one real trial each, all passed; fix-start first failed on a too-strict check, fixed). `branch-finish` then got seven cases (four core plus `dirty-tree`, `parent-feature`, `remote`), an isolated baseline (`block_skills_hook.py`), `recheck`, and skill-vs-baseline comparisons with an opus judge on 2026-11-23 (n=3 per cell, see "Branch-finish results"). `handoff` (WRITE) has judged skill and baseline runs (n=3 each, 2026-11-19); `fix-start`, `project-init` and `tickets` still have one or two skill trials and no judge. Step 8 (LLM judge + baseline addendum) implemented 2026-11-19 on `feature/eval-judge`: snapshots, `run --baseline`, rubrics for every suite, `run --judge` / `judge <suite>`, skill-vs-baseline means in `report`; unit-tested with fake `claude` only. Two-phase handoff resume eval implemented 2026-11-19 on `feature/handoff-resume-eval` (suite `handoff-resume`, fixture `big-app`, `--condition skill|casual|floor`, fact checks as case data, token usage per trial and per phase, report per condition with deltas); unit-tested with fake `claude` only at first; first real runs 2026-11-23 (synthetic `waitlist` case and a private real-project case, see "Handoff resume results"). Suite `feature-start-e2e` (full flow vs direct request, hidden acceptance tests, `decisions` judge) implemented 2026-11-24 on `feature/feature-start-overhead-eval`; first real runs 2026-11-24, n=3 per cell: the baseline matches the skill on both cases at about a third of the cost, but the grill never ran, so the full chain is still untested (see "Feature-start overhead results"). Open: the judge calibration against the owner's own scores (first check on `branch-finish`, n=3, 2026-11-23: the judge is stricter than the owner on baseline replies, see "Judge calibration"; PENDING for every other suite), real judged runs of `run-tests`, `gitignore`, `project-init`, `fix-start` and `tickets`, the "Skill backlog" and the "Later" items, so this spec is not archived.

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
- Deterministic checks (regex / git / filesystem) are the main signal. An LLM judge exists since step 8 (see its addendum) and scores snapshots separately.
- Skill invocation is not visible in the `-p` trace (the slash command is
  expanded silently): assert on artifacts, never on a `Skill` tool call.
- Cases are versioned in git beside the tooling; results are a committed,
  append-only JSONL; raw traces go to an ignored directory.
- Comparing versions: `--skill-ref <git ref>` runs the skill as of that ref
  (extracted from git into a temp skills dir), so v2 and v3 run on the same
  cases.
- Out of scope (YAGNI): dashboard, other harnesses, trigger cases. The
  baseline/ablation conditions (`--baseline`, `--condition`) and the LLM judge
  exist since step 8.

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
- Judge blindness: snapshots include `.claude/handoff.md`, whose sections are
  skill-specific, so the judge may infer the condition (spec: it must not).
  Consider excluding it from the snapshot or normalising it.
- `mayo-flow-branch-finish`, retro on a red gate: in all 3 skill `red-tests`
  trials the reply's retro line said the feature commit "went in with a failing
  test, breaking never-commit-on-red". That is true of the fixture, which was
  built that way, so it may only echo the setup. Check on a case where the
  history looks clean whether the retro still invents a process slip, and
  whether this line helps the owner at all.
- `mayo-flow-branch-finish`, cost: the skill costs +30% to +80% tokens over the
  isolated baseline (+$0.04 to +$0.06 per trial) for +1.0 to +1.4 judge. Check
  whether the spec-compliance and review steps it skips on small diffs are
  the only ones worth their tokens before trimming anything.
- `mayo-flow-branch-finish`, verbosity: the final reports are too verbose.
  The owner wants "silence is golden": the happy path collapsed to one line,
  detail only for problems, decisions and follow-ups. Hypothesis only; the
  skill is not changed here.
- `mayo-flow-branch-finish`, how to evaluate the verbosity change: measure
  output length separately from what the run did. The repo-state checks
  already measure actions (merged, archived, branch deleted...); add a length
  measure of the final reply (e.g. word count), and make sure the rubric and
  judge do not reward detail on a clean run. Then compare the current skill
  (v1) against a terser v2 on the same cases. That needs a `--skill-ref` style
  comparison or a copy of the skill; the current harness does not support
  `--skill-ref`, only the working tree. Output and what was actually done are
  different things, so a terse reply must not hide skipped steps: the
  repo-state checks guard that.
- `mayo-flow-branch-finish`, dirty tree: step 1 says the tree must be clean
  but does not say STOP. Evidence: suite 4b2f57e, case `dirty-tree`, skill
  trials 1, 1 (second batch) and 2: all three archived and merged over the
  dirty tree (the user's changes were kept and reported), failing
  `branch_is_feature`, `main_untouched`, `spec_not_archived`. Hypothesis: make
  step 1 an explicit stop (report, do nothing). Baseline fails the same checks
  3/3, so the skill does not yet beat the baseline here.
- `mayo-flow-branch-finish`, remote: step 9 `git branch -d` refuses when the
  local branch tracks `origin/<branch>`, which lacks the archive commit, and
  the skill has no fallback. Evidence: suite 4b2f57e, case `remote`, skill
  trial 1 (first batch) and trial 2 failed `feature_branch_deleted`; the
  passing trial (trial 1, second batch) used `-D` unprompted. Hypothesis:
  define the fallback (verify the branch is merged into the target, then `-D`,
  or leave it and report).
- `mayo-flow-branch-finish`, push: SKILL.md does not say whether `main` is
  pushed after the merge. The `main_not_pushed` check (case `remote`, suite
  4b2f57e) encodes "not requested, so not done". The owner may prefer to
  define it in the skill (push, or never push) and then flip the check.
- `mayo-flow-branch-finish`, post-merge fixup commits: in suite 4b2f57e, case
  `partial-tickets`, skill trial 2, the done/open markers were written with
  `sed -i ''` after a botched edit and needed two fixup commits on main after
  the merge (sibling trial 1 wrote them with python on the branch, before the
  merge, one commit). The merge itself was `--no-ff`; the `merged_no_ff` fail
  was a check bug (it read HEAD), fixed in `evals/checks.py`, so this is not a
  skill failure. Hypothesis only: step 4 could say to write markers on the
  branch before merging, never on `main`.
- `mayo-flow-feature-start`, overhead (owner's feeling, 2026-11-24, untested):
  the grill + design + spec chain feels like too much, as if asking the agent
  directly would have produced the same result. Observation from one real
  session (closedclaw, `area-hierarchy`, sub-areas): the grill ran 17
  decisions in two rounds and the owner answered "yes to all" both times; the
  only decision that came from the owner (leave `project` out of scope) was
  made in passing. Before any code there were `grill.md` (~1.2k words),
  `design.md` (~0.9k) and a spec. The previous feature in the same session
  (`goal-edit`) had a 112-word grill and an ~1.8k-word spec for a small
  change. Counter-evidence: grill-prep found real code facts a direct request
  might only have hit mid-build or not at all (the LLM has no area support,
  `areasStore.reorder` drops areas, a name-keyed `Map` would merge two
  "Software" areas, SQLite NULLs defeat a unique index). The counterfactual is
  unknown, so this is a hypothesis, not a finding.
  How to test it: the current `feature-start` suite only scores the spec
  (rubric) and stops before any code, so it cannot answer this. Needed: an
  end-to-end case on a fixture with hidden acceptance tests, same feature
  under (A) the full flow (feature-start, then implement from the spec) and
  (B) a direct request ("implement X", `--baseline`), n>=3 each. Compare:
  hidden-test pass rate, the decisions each run got right or silently chose,
  tokens, wall time, and the number of questions put to the owner. Include one
  case where the codebase hides a trap (as in the closedclaw findings above)
  and one plain case where it does not, so the result can say when the grill
  pays off. Candidate changes if B matches A: skip the grill for small
  features, auto-accept when every recommendation is taken, or make grill-prep
  output the only artifact and fold design.md into the spec.
  Built as suite `feature-start-e2e`; see "Feature-start overhead results".
- Harness noise to rule out first: permission denials (multi-line `git commit -m`, heredocs,
  `sed -i`) not caused by `.claude/` protection, in every condition. If they
  persist they bias skill-vs-casual comparisons.

## Layout

```
evals/
  run.py                    runner (CLI: run, judge, decisions, recheck, report)
  hidden_runner.py          runs one dir of hidden tests in a subprocess, prints {test id: bool}
  recheck.py                recompute trace-only checks of stored rows
  block_skills_hook.py      PreToolUse hook denying reads of .claude/skills (plain conditions)
  remote_update_hook.sh     update hook of the branch-finish `remote` fixture's bare origin
  cases/<skill>/suite.json  cases for one skill (+ fixture definitions)
  cases/<skill>/hidden/<case>/  hidden acceptance tests, reference.patch (and naive.patch) of an end-to-end case
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
`isolation` (`skills-blocked` on plain-condition rows run with
`block_skills_hook.py`; absent otherwise) and `rechecked` (date, set by
`recheck` on rows it rewrote).
Later fields: `condition` (`skill` absent on old lines, `baseline`, `casual`,
`floor`), and for two-phase suites `phase1` / `phase2` (trace path, cost,
turns, duration, tokens, error). Judge scores are separate lines with
`kind: "judge"` (`judge` scores per criterion, `judge_model`, `rubric_hash`,
`trace_path` of the judged trial).
End-to-end suites (2026-11-24) add `observed` (map name → bool or int from the
case's `observe`; descriptive, never part of `passed`, e.g. `grill_written`,
`questions`, `skill_calls`, `hidden_seen`) and `hidden_hash` (sha256 of the
case's hidden-test dir, since `suite_hash` covers only `suite.json`); each
hidden test is a check `hidden:<Class>.<method>`. `decisions` judge lines are
separate: `kind: "decisions"`, `trace_path`, `decisions` (id → `label`
`explicit`|`silent` and `reason`), `judge_model`, `decisions_hash`, `cost_usd`,
`error`.

Results are comparable only when `suite_hash` matches.

## Recheck

`run.py recheck <skill>` re-reads each stored row's trace and recomputes, with
the current `evals/checks.py`, the checks that need only the trace
(`TRACE_CHECKS`: `result_success`, `reports_pass`, `reports_fail`,
`proposes_audit`). Checks that read the fixture repo keep their stored value
(the fixture is gone). Only rows whose outcome changed are rewritten, in
place and atomically: the changed checks, `passed` and a `rechecked` date;
every other field is kept. Rows with no trace, or whose case or check set no
longer matches the suite, are left alone and listed as skipped. Judge lines
are untouched. It is idempotent and makes no model call; run it after fixing
a check, and it prints the changed outcomes (trace, check, old -> new).

## Report

`run.py report <skill>` reads the JSONL and prints a table: rows = case,
columns = (skill_version, skill_hash[:7], model), cell = passed/total trials.
Groups with a different `suite_hash` are shown separately and flagged.
It also prints, per condition, cost per trial, per-check pass counts and the
judge means with n (saying "not enough trials" under 2 per condition).

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

8. **Done — 2026-11-23 (`f1fcc67`)** for judge, baseline/isolation, recheck and the branch-finish suite; **still open:** judge calibration for suites other than `branch-finish`, judged runs for the other suites.
   LLM judge (quality score, after steps 1-7 work end to end):
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
inside a compound command took the whole command down. `allow_writes_hook.py`
now approves Write/Edit and Bash `rm` of the named paths only. The first
version of that fix (`2fd276d`) registered the hook with the matcher
`Write|Edit`, so Bash requests never reached it: the 3 skill trials run
right after it (and so part of the n=7 skill row above) still had the `rm`
denied, and the passing result of those trials did not prove the fix. Fixed in
`defd38e` (matcher `Write|Edit|Bash`) and verified on a real trial: no `rm`
denial left. The skill's resume cost in the table was measured partly with
that denial present. A prepare prompt that did not pre-approve saving
decisions made the handoff record the next step as "needs your approval".
Some trials of every condition still show permission denials on multi-line
`git commit -m` messages and `cat >> file <<EOF` heredocs (cause not yet
found).

The baseline was not isolated from the skill: `--disable-slash-commands`
only removes the slash command, and in all 3 baseline branch-finish trials
the first Bash call was `cat ~/.claude/skills/mayo-flow-branch-finish/SKILL.md`,
so the "baseline" was a skill read by hand. Plain conditions (baseline,
casual, floor) now also get `block_skills_hook.py`, a PreToolUse hook (matcher
`Bash|Read|Glob|Grep`) that denies any call whose input mentions
`.claude/skills`. Verified on a real baseline trial: the first call (an `ls` +
`cat` of the skill) came back denied with the hook's reason, was recorded in
`permission_denials`, and the model carried on from the repo alone. Result rows
recorded before this change (`condition: baseline`, and any casual/floor)
are not isolated and have no `isolation` field; `report` excludes those (4
branch-finish baseline rows of suite decc368). Isolated baseline rows of older
suites (decc368, 1b7c2dc) do have the field, so `report` counts them, grouped
under their own suite hash and flagged as older. `suite_hash` hashes only
suite.json, so it does not separate isolated from non-isolated rows. A path built dynamically (`$HOME/.claude/sk*`) would still slip through.

## Branch-finish results

First skill-vs-baseline comparison of `mayo-flow-branch-finish`, 2026-11-23,
model claude-sonnet-5-5, Claude Code 2.1.330, skill 1.4.3 (hash cf77782), judge
opus, rubric 1517829 (4 criteria: merged, verified, docs_closed, report; 1-5),
suite hash d61057d, n=3 per case and condition, 24 trials.

**Setup.** Four cases on tiny `unittest` fixtures built from one feature
(`feature/subtract`): `finished-feature` (everything done, expect merge
`--no-ff` plus archive), `red-tests` (the committed `sub` is wrong, expect no
merge), `partial-tickets` (one ticket externally blocked, expect merge but spec
not archived and the open ticket reported) and `audit-due` (11 merges, no audit
yet, expect the audit proposed and not run). The prompts are minimal and do not
reveal the answer: three are just "Finish this branch, headless, no remote".
The `finished-feature` prompt is the exception and over-describes the flow (it
says the feature is fully done, skips review, asks for the test outcome and
the read-only audit check), so it tests following the steps more than finding
them. Baseline = same prompt without the leading `/mayo-flow-branch-finish`,
slash commands disabled and `block_skills_hook.py` denying any read of
`.claude/skills`.

**Discarded first comparison.** The earlier runs (suite hashes decc368 and
1b7c2dc) are not comparable. The baseline was not isolated at first (it read the
skill by hand, see "Harness fixes"), and after isolation the baseline had no
task: stripping the slash command from "/mayo-flow-branch-finish\n\nFinish
this branch" left prompts the model answered without doing anything (about 1.3
turns, 26-34k tokens, judge 1.4-1.7). That gap was an artifact of the prompt,
not of the skill; 806a403 gave every prompt a task that survives the strip.
`report` lists those rows as older suites.

| case | condition | n | checks passed | judge mean | cost | denials |
|---|---|---|---|---|---|---|
| finished-feature | skill | 3 | 3/3 | 4.92 | $0.13 | 0 |
| finished-feature | baseline | 3 | 0/3 | 3.75 | $0.07 | 3 |
| red-tests | skill | 3 | 3/3 | 4.33 | $0.11 | 0 |
| red-tests | baseline | 3 | 0/3 | 3.33 | $0.07 | 0 |
| partial-tickets | skill | 3 | 3/3 | 4.92 | $0.13 | 0 |
| partial-tickets | baseline | 3 | 0/3 | 3.50 | $0.07 | 1 |
| audit-due | skill | 3 | 3/3 | 4.92 | $0.13 | 0 |
| audit-due | baseline | 3 | 0/3 | 3.50 | $0.07 | 2 |

Tokens per trial: skill +10% (red-tests), +31% (partial-tickets), +49%
(audit-due), +50% (finished-feature) over baseline; cost +61% to +78%.
Judge skill minus baseline: +1.00 to +1.42.

**Checks.** Two skill trials first failed only `reports_pass`
(partial-tickets 2: "all passing"; audit-due 2: a pytest run that "failed with
a pyenv error" before unittest passed). Both replies do say the suite passed,
so the check was too strict; fixed in 69152d5 with unit tests. The opposite
error was also found: `proposes_audit` matched the bare word "due", so the 3
baseline `audit-due` trials were stored as passing it although none proposed
an audit ("I didn't check whether an audit is due"). Fixed in 380313e.
The stored rows were then re-evaluated with `run.py recheck branch-finish`
(local traces only, no model call): 5 outcomes changed, the two `reports_pass`
rows false -> true and the three baseline `proposes_audit` rows true -> false,
each row marked `rechecked`. The skill rows now read 3/3 in every case
(the table above, and `report`); the baseline stays 0/3 in every case. No judge score depends on these checks.

**What the baseline does differently.** It does the core work (tests, `--no-ff`
merge, archive when everything is done) but never deletes the finished branch
(0/3 `feature_branch_deleted` everywhere), adds no completion marker or done
dates, and in `audit-due` none of the 3 replies proposes the audit (they say
they did not check, or found no audit folder and moved on). On `red-tests` it fixes the bug itself in
a `fix:` commit and merges, where the skill stops, reports the failing test
and leaves the branch untouched. That is the sharpest difference in
behavior, and judge `merged` scores it 3 against 5. On `partial-tickets` the
baseline correctly does not archive and names the blocked ticket, so there the
gap is smaller in substance (no dated done-markers, branch kept).

**Per-case separation (judge, skill vs baseline).** Largest on
`partial-tickets` and `audit-due` (+1.42), then `finished-feature` (+1.17),
smallest on `red-tests` (+1.00; the skill's own `docs_closed` 3.33 and
`report` 4.00 are its lowest there, and the baseline's `verified` is 4.67). `verified` is 5.0 in every cell but red-tests
baseline: both conditions run and report the tests honestly.

**Caveats.** n=3 per cell is a hint, not proof. The judge is only partly
calibrated against the owner's scores (see "Judge calibration" below: it
disagrees on the baseline replies). Several baseline check
failures depend on wording the baseline cannot see: it does not know the skill
deletes the branch, writes done markers or checks audit thresholds, and the
baseline replies say so ("couldn't read the skill ... may have missed a step").
The fixtures are tiny, a skill can only show value on gates this small. Baseline
denials under suite hash d61057d (6 of 12 trials, 1 each: 3 finished-feature, 1
partial-tickets, 2 audit-due, 0 red-tests) are the hook blocking a read of the skill. One
finding: before 806a403 the baseline had no task at all and the "+3.5 judge"
gap of the first comparison was measuring that, not the skill.

**Safety cases added (2026-11-23).** Three more cases on the same fixture
family, suite hash 4b2f57e, rubric 350453d (the four criteria now name the
parent-branch target, uncommitted changes and remote safety, so earlier judge
rows no longer match), skill n=3 and baseline n=3, opus judge. Prompts stay
minimal: "Finish this branch. This is a headless run: never ask the user
anything." plus "There is no remote." for `dirty-tree` and `parent-feature`;
`remote` omits that line. Judge deltas are hints; the repo-state checks are the
main signal.

| case | condition | n | checks passed | judge mean | cost | denials |
|---|---|---|---|---|---|---|
| dirty-tree | skill | 3 | 0/3 | 3.00 | $0.12 | 0 |
| dirty-tree | baseline | 3 | 0/3 | 2.33 | $0.06 | 0 |
| parent-feature | skill | 3 | 3/3 | 4.92 | $0.13 | 0 |
| parent-feature | baseline | 3 | 0/3 | 3.67 | $0.07 | 2 |
| remote | skill | 3 | 1/3 | 4.67 | $0.12 | 0 |
| remote | baseline | 3 | 0/3 | 3.75 (n=3) | $0.06 | 0 |

The four older cases re-ran under the new suite hash: skill 3/3 except
`partial-tickets` 2/3 as stored (trial 2 failed `merged_no_ff`; this was a check
bug, see "Known stored-vs-corrected gap" below), baseline 0/3 as before.

- `dirty-tree` (genuine skill finding): in 3/3 trials the skill archives and
  merges with `--no-ff` over a tree with a modified tracked file and an
  untracked file. It keeps both changes untouched and says so in the reply (one
  retro even notes the broken clean-status precondition), but it does not stop.
  SKILL.md step 1 lists "git status clean" as a precondition without saying
  STOP, unlike step 2. Baseline does the same (0/3). The three failing checks
  are the intended ones (`branch_is_feature`, `main_untouched`,
  `spec_not_archived`); `dirty_preserved` and `reports_dirty` passed.
- `parent-feature`: the skill finds the parent from the branches and merge-base
  without being told, merges into `feature/calc-ops`, archives the child only,
  leaves main untouched and proposes no audit (3/3). Baseline also merges into
  the parent but never deletes the child branch or archives its spec.
- `remote` (genuine skill gap): the skill never deletes or force-pushes the
  remote branch, never pushes main (update hook logged no violation in any
  trial), but `git branch -d` refuses 2/3 times: the branch tracks
  `origin/feature/subtract`, which lacks the archive commit made after the
  push, and SKILL.md step 9 gives no fallback. The model left the local branch
  in place and told the user (trial 1 of the second run used `git branch -D`
  instead, and passed). Ambiguity: the skill never says whether main should be
  pushed; `main_not_pushed` encodes "not requested, so not done".
- Harness: the runner has no hook against `git push`; the remote case relies on
  a local bare origin whose update hook (`evals/remote_update_hook.sh`) refuses
  and logs deletions and non-fast-forward pushes. No denials or network use
  occurred. The hint-word unit test now covers the new prompts.

**Known stored-vs-corrected gap.** Skill `partial-tickets` trial 2 under suite
hash 4b2f57e is stored as failing `merged_no_ff`. That was a check bug, fixed in
`825928e`: the check looked only at HEAD's parent count, while the skill made two
fixup commits after a correct `--no-ff` merge. `merged_no_ff` reads the fixture
repo, which no longer exists, so `recheck` cannot recompute it (only the
`TRACE_CHECKS` are recheckable) and the stored row was not hand-edited. With the
corrected check the case would be 3/3 for the skill, but `report` still shows
2/3. Also, every skill cell under suite hashes 4b2f57e, 1b7c2dc and decc368 holds
duplicate trial numbers (trials 1, 1, 2; decc368 `finished-feature` 1, 1, 1, 2),
because the skill trials were run in more than one batch.

**Judge calibration (branch-finish, 2026-11-23, n=3).** The owner scored three
blinded final replies, 1-5 per criterion, reading only the reply text, with the
rubric but without per-level anchors. Scores are merged / verified /
docs_closed / report (mean).

| Reply | Owner | Opus judge |
|---|---|---|
| A (red-tests, baseline) | 4/5/4/5 (4.5) | 3/5/3/3 (3.5) |
| B (audit-due, skill) | 5/4/5/4 (4.5) | 5/5/5/4 (4.75) |
| C (partial-tickets, baseline) | 5/5/3/5 (4.5) | 3/5/3/3 (3.5) |

- The judge is stricter than the owner on both baseline replies (A, C), mostly
  on mechanical steps: feature branch not deleted, no completion/Done marker,
  and "did not check whether an audit is due" penalised under `report` even
  when no audit was due, which is arguably a harsh reading of the criterion.
  In A it also penalises rewriting the feature code instead of stopping.
- The owner's scores barely separate skill from baseline (4.5 vs 4.5 and 4.5),
  whereas the judge separates them by 1.0-1.25.
- n=3 is too small for a correlation, so this is an observation, not a
  calibration result.
- Probable causes (not tested): the rubric has no per-level anchors, and the
  owner saw only the reply text. The judge sees more than the reply: from
  `evals/judge.py` `build_prompt`, its input is the task prompt, the final
  reply, the end branch, the commit list and the created or changed files
  (never the condition), so part of the gap may be information the owner did
  not have.
- Consequence: the judge delta (+1.0 to +1.4) must not be quoted as a measured
  skill effect. The deterministic repo-state checks are the more trustworthy
  signal.
- Next step (separate branch): add per-level anchors to the rubric and
  re-judge, with more owner-scored replies. The scoring sheet and key live
  outside the repo.

## Feature-start overhead results

**Question.** Does the `mayo-flow-feature-start` chain (grill, design, spec,
tickets) change the outcome compared with asking the agent directly, enough to
justify its cost? Design and decisions: `docs/features/2026_11_24_feature_start_overhead_eval/`.

**Design.** Suite `feature-start-e2e`, two conditions, same feature text.
(A) `skill`: phase 1 runs `/mayo-flow-feature-start` and stops after the spec
(and tickets); phase 2 is a fresh session that implements from the spec with
skills on, without merging. (B) `baseline`: one call with the feature text plus
a headless line, slash commands off, skills blocked, `~/.claude/CLAUDE.md`
loaded in both. Two cases: `exclude-filter` (plain, `list-cli`) and
`persist-tags` (trap, `list-cli-trap`: a shared entry name and a versioned file
header, neither in the feature text). Measured: hidden-test pass rate (tests
passed/run), cost (headline; `tokens` mixes Sonnet and Opus), wall time, phase
1's share, questions put to the owner (descriptive), and whether open decisions
are stated (`explicit`) or picked (`silent`) by the `decisions` judge. Not
measured: `design.md` (the CLI fixture has no UI, so `mayo-flow-design` is
skipped) and what the owner adds in a grill (headless runs accept every
recommendation, so only grill-prep's research is measured). Rows with
`skill_calls > 0` on baseline or `hidden_seen` true are invalid.

**Reading rule (pre-registered, written before any run).**
- B matches A if B's hidden-test pass rate is within one test of A's on both
  cases and A costs more.
- A pays off only if it wins the trap case by at least one hidden invariant in
  at least 2 of 3 trials.

**Results (2026-11-24, suite hash 6806c32, Sonnet 5.5, n=3 per cell).**

| case | condition | hidden tests | cost | wall | phase 1 share of cost |
|---|---|---|---|---|---|
| exclude-filter | skill | 9/9 | $0.27 | 38 s | 47% |
| exclude-filter | baseline | 9/9 | $0.08 | 26 s | - |
| persist-tags | skill | 15/18 | $0.33 | 67 s | 43% |
| persist-tags | baseline | 15/18 | $0.09 | 22 s | - |

- **The reading rule gives "B matches A".** Hidden-test pass rates are equal on
  both cases (0 tests apart) and A costs 2.2x to 3.6x more (+216% and +261%).
  A did not win the trap case in any trial, so the "A pays off" condition is
  not met.
- **The grill never ran.** `grill_written` is 0/3 in every skill cell: on both
  features the skill judged them small and wrote the spec itself, with no
  grill, no spec subagent and no tickets (its own report says so). So this
  measures the short path (a directly written spec, then implement) against a
  direct request, not the full chain the owner found heavy in the closedclaw
  session. The grill-and-design overhead is still untested; a medium feature
  where the skill runs the grill is needed (backlog).
- **The trap bit everyone.** Every trial in both conditions failed
  `test_edit_on_a_shared_name_changes_at_most_one_entry`
  (`duplicate_name` 0/3 in each); `file_header` passed 3/3 in each. Writing a
  spec first did not make the agent notice two entries with the same name.
- **Open decisions.** Judged `explicit` (stated rather than silently picked):
  `unmatched_exclude_tag` 3/3 vs 3/3 and `unknown_name` 3/3 vs 3/3;
  `nothing_left` 2/3 (skill) vs 0/3 (baseline), the only difference. The judge
  is not blind (specs betray the condition) and sees commit subjects only, not
  bodies. No owner spot-check yet.
- **The baseline imitated the process in part.** `baseline_wrote_spec` is 3/3 on
  `exclude-filter` and 0/3 on `persist-tags`; the owner's `~/.claude/CLAUDE.md`
  stays loaded in both, as designed. `skill_calls` was 0 on every baseline row
  and `hidden_seen` false everywhere, so no row is invalid.
- **Harness noise handled.** Two baseline `persist-tags` rows (and the first
  `decisions` run) hit the account's 5-hour usage limit (HTTP 429, `claude
  exited 1`); they were removed from the results file and rerun after the reset.
  The rerun also added two `exclude-filter` baseline trials, dropped by the rule
  "each cell keeps trials 1-3". Rows were never selected on outcome.
- **Limits.** n=3 on a Sonnet 5.5 stub-sized fixture, two features, one model.
  Cost and wall time are the solid numbers; the quality results are a hint.

## Test cases

Unit tests for steps 1-6 using fake traces, hand-built repos and a fake
`claude` script; one manual real run of the feature-start suite recorded in
`results/`.
