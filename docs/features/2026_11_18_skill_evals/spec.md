# Skill evals

**Status:** steps 1-7 done (2026-11-19, merged). Step 8 (LLM judge) and the "Later" items are open, so this spec is not archived.

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

## Result record (one JSONL line per trial)

`ts`, `skill`, `skill_version` (frontmatter), `skill_hash` (sha256 of the
skill directory contents), `skill_ref` (git ref or `working-tree`), `model`
(from the `init` event), `claude_version`, `case_id`, `suite_hash` (sha256 of
the case file), `trial`, `checks` (map name → bool), `passed` (all checks),
`cost_usd`, `duration_ms`, `num_turns`, `permission_denials` (count),
`trace_path`, `error` (null or string).

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

## Test cases

Unit tests for steps 1-6 using fake traces, hand-built repos and a fake
`claude` script; one manual real run of the feature-start suite recorded in
`results/`.
