# Delegate eval

**Status:** draft (2026-11-25). Written on branch `wip` at the owner's request.
No code yet. Parent spec: `docs/features/2026_11_18_skill_evals/spec.md`.

## Goal

Measure `mayo-flow-delegate` (v1.2.2) with two uses in mind:

1. **Comparison.** Does the skill make the coordinator behave differently
   from the same session without it, and at what cost? The owner's global
   `CLAUDE.md` already says "delegate", so the baseline may imitate the skill.
   The skill is worth only what it adds on top of that.
2. **Optimization.** When the owner edits a clause of `SKILL.md`, one named
   check must move, not one global score. Cheap cases make many iterations
   possible. A mutant test shows that each check can see its clause.

## Decisions

Each decision was settled with the owner on 2026-11-25 unless marked "(spec)".

### 1. A new suite, `evals/cases/delegate/`

- **Chosen:** own `suite.json`, rubric, results file and fixtures.
- **Why:** other suites score artifacts. This suite scores how the main thread
  behaves, so the evidence is the `Agent` calls in the trace.

### 2. The trace is the main evidence

- Each `Agent` tool call gives `model`, `prompt`, `description` and its order.
  Add one helper, `agent_calls(trace)`, that returns them.
- Checks read the calls and the git state of the fixture. No judge in the
  first version.
- (spec) Step 1 of the plan must confirm from a real trace how the tool is
  named (`Agent` or `Task`), whether `model` and worktree isolation appear in
  the input, and whether text before a tool call is in the trace. If the
  trace hides one of them, the check that needs it is dropped and recorded
  in this spec.

### 3. Two layers of cases

- **Layer B, sensitivity (short cases).** One case presses one clause. Cost is
  cents per trial. Used for every iteration of the skill.
- **Layer A, comparison (full cases).** A small ticket set worked to the end
  and scored by hidden tests, like `feature-start-e2e`. Used for the
  skill-vs-baseline verdict only.
- **Scope was chosen as "mixed".** Layer B is short. Layer A has one or two
  full cases.

### 4. Conditions: `skill` and `baseline`

- `skill`: the prompt starts with `/mayo-flow-delegate`.
- `baseline`: same task text, no slash command, skills blocked
  (`block_skills_hook.py`), `~/.claude/CLAUDE.md` loaded as in the other suites.
- State in the results that the baseline keeps the owner's "delegate" rule.

### 5. One check per clause

Every check id names the `SKILL.md` section it tests. This is the map used to
read an edit:

| id | clause | evidence |
|---|---|---|
| `s1_delegated` | 1 Roles: agents do the work | at least one `Agent` call for implementation |
| `s1_no_self_impl` | 1 Roles | the main thread did not `Edit` or `Write` a source file the ticket names |
| `s2_model_explicit` | 2 Models | every `Agent` call has `model` |
| `s2_model_runtests_haiku` | 2 Models | the suite-run agent uses `haiku` |
| `s2_model_review_sonnet` | 2 Models | the test-review agent uses `sonnet` |
| `s2_model_critical_opus` | 2 Models | the critical ticket (auth or migration) uses `opus` |
| `s2_model_mechanical_sonnet` | 2 Models | the mechanical ticket (copy, docs) uses `sonnet`, not `opus`, not `haiku` |
| `s2_model_stated` | 2 Models | one line with model and reason before the launch |
| `s3_paths` | 3 Checklist | prompt names the ticket and spec paths |
| `s3_constraints` | 3 Checklist | prompt names scope, files not to touch and the branch |
| `s3_red_evidence` | 3 Checklist | prompt demands the red output in the hand-back |
| `s3_full_suite` | 3 Checklist | prompt demands the full suite and its real output |
| `s3_no_sed_i` | 3 Checklist | prompt says to use Edit, not `sed -i` |
| `s3_and_chain` | 3 Checklist | prompt says to chain `git commit` with `&&` and check exit codes |
| `s3_status_edit` | 3 Checklist | prompt says to verify the ticket status edit in `git status` |
| `s4_worktree_each` | 4 Parallel | each parallel agent has its own worktree |
| `s4_new_files` | 4 Parallel | prompt asks for new code in new files, wired with one-line edits |
| `s5_wave_order` | 5 Merging | merges follow the wave order of the tickets |
| `s5_suite_after_merge` | 5 Merging | the suite runs after each merge |
| `s5_cleanup` | 5 Merging | merged worktrees and branches are removed |
| `s6_reruns_suite` | 6 Verify | the main thread runs the suite after a hand-back |
| `s6_rejects_missing_red` | 6 Verify | a hand-back with no real red is redone, or the reply names it |
| `n_no_delegate` | Description: not for one-line edits | no `Agent` call on a one-line task |

Prompt-checklist checks (`s3_*`) look at every implementation agent. A check
passes only if all of them pass. (spec) Match each item with a small regex
list, and keep the lists in `suite.json` so an edit to a clause changes data,
not code.

### 6. Cases of layer B (short)

All use one new fixture, `ticket-set`: a small stdlib Python repo (`unittest`)
with a feature folder, a spec and tickets. The fixture is built in step 2.

| case | what it presses | clauses |
|---|---|---|
| `models` | one critical ticket, one mechanical ticket, one suite run | `s2_*` |
| `prompt-checklist` | one ticket, one agent | `s3_*`, `s1_*` |
| `parallel` | two independent tickets and two that touch the same file | `s4_*`, `s5_*` |
| `handback-trap` | see decision 7 | `s6_*` |
| `one-liner` | a one-line edit request | `n_no_delegate` |

Short cases stop early with the prompt ("stop after the first wave is merged
and report"), except `handback-trap`, which must run to the hand-back.
(spec) Use `--max-budget-usd 1` per trial as a second guard.

### 7. The hand-back trap is a planted fixture

- **Chosen:** a ticket whose new test already passes before any code. No agent
  can show a real red for it.
- **Check:** `s6_rejects_missing_red` passes if the coordinator redoes the
  ticket (a second `Agent` call for it), or the final reply names the missing
  red and does not call the ticket done.
- **Risk (spec):** an agent may say "the behaviour already exists" and the
  right action is then debatable. Read the first smoke traces before fixing
  this check. If the rule is not clear, change the fixture so the ticket asks
  for a real behaviour that an old, wrong test hides.

### 8. Mutants validate the checks

- A mutant is a copy of `SKILL.md` with one clause removed or weakened. They
  live in `evals/cases/delegate/mutants/<name>/SKILL.md`.
- `run.py run delegate --mutant NAME` copies the working-tree skill folder into
  the temp skills dir with that `SKILL.md`. The record gets a `mutant` field,
  and `skill_hash` shows the change.
- A unit test checks that each mutant differs from the real `SKILL.md` only in
  the intended section.
- Planned mutants: `no-models` (section 2 removed), `no-checklist` (section 3
  removed), `no-parallel` (section 4 removed), `no-merge` (section 5 removed),
  `no-verify` (section 6 removed), `haiku-default` (section 2 says "use haiku
  for everything").
- **A check is sensitive** if, with n=3, its target mutant drops it in at least
  2 of 3 trials against the real skill. An insensitive check is rewritten or
  removed. It must not guard an optimization.

### 9. The base version is v1.2.2 as it is

- The first full run of layer B on the working tree is the baseline of all
  later edits. Record `skill_version` and `skill_hash`.
- Later edits are compared with `--skill-ref` once it works for dependents, or
  by checking out the old version in the working tree. This limit is already in
  the parent spec ("Later").

### 10. Layer A, full cases

- (spec) One case, `ticket-run`: four tickets in two waves on `ticket-set-full`,
  with hidden tests per ticket. It reuses the `feature-start-e2e` machinery
  (`hidden_tests` fact, `visible_suite_green`, `hidden_seen`).
- Measured: hidden-test pass rate, cost (headline), cost split by model,
  wall time, number of agents, and the `s*` checks as observations.
- A second case with a trap in the code is added only if the first shows a
  difference worth testing. YAGNI.

### 11. Reading rules (written before any run)

- **Layer A.** B matches A if its hidden-test pass rate is within one test of
  A and A costs more. A pays off if it passes more hidden tests in at least 2
  of 3 trials. A cost-adjusted rule is rejected, as in the overhead eval.
- **Process.** Report each `s*` check as passes/trials per condition. The
  skill adds value on a clause if it beats the baseline by at least 2 of 3
  trials on that check.
- **Optimization.** After an edit, run layer B at n=3. The edit counts as an
  improvement if its target check gains at least 2 of 3 and no other check
  loses 2 of 3. Report cost and agent count next to it.

## Not measured (state in the results)

- Whether the delegated code is good. Only layer A looks at it.
- The owner's answers in a live session. Runs are headless.
- Long sessions with many tickets and a forced `/clear`.
- `mayo-flow-run-tests` as a skill. The suite run is only an `Agent` call here.

## Implementation plan (each step red, then green, one commit each)

1. `agent_calls(trace)` in `evals/trace.py`, with unit tests on a fake trace.
   Run one real smoke trial first and write down what the trace shows (decision 2).
2. Fixture `ticket-set` and `ticket-set-full`, plus fixture validation tests in
   `tests/test_evals_suites.py` (visible tests pass; planted traps exist).
3. Checks `s1_*` and `s2_*` in `evals/checks.py`, with unit tests. Case `models`.
4. Checks `s3_*`, regex lists in `suite.json`. Case `prompt-checklist`.
5. Checks `s4_*` and `s5_*`. Case `parallel`.
6. Check `s6_*`. Case `handback-trap`. Case `one-liner` and `n_no_delegate`.
7. `--mutant` flag in `run.py` and the six mutants, with unit tests.
8. `report`: one row per `s*` check, columns per condition and per mutant.
9. Layer A case `ticket-run` with hidden tests and its reference patch.
10. Real runs: smoke, then layer B n=3 for `skill` and `baseline`, then mutants,
    then layer A n=3 for both conditions. Write the results in the parent spec.

Cost estimate (a guess, to confirm after the smoke trial): layer B about $15,
mutants about $10, layer A about $15. Run each batch with its own
`--max-budget-usd`.

## Test cases

Unit tests use fake traces, hand-built repos and a fake `claude` script, like
the other suites. Real runs are recorded in `evals/results/delegate.jsonl`.
Tests to write first:

- `agent_calls` returns model, prompt, order, and ignores other tools.
- Each `s*` check passes on a good fake trace and fails on a trace that breaks
  only its clause.
- `n_no_delegate` fails when an `Agent` call exists.
- Each mutant differs from `SKILL.md` only in its section.
- `--mutant` leaves the real skill folder unchanged.
