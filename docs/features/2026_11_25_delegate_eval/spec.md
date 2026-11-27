# Delegate eval

**Status:** steps 1-9 done (2026-11-25, on branch `wip`). Open: step 10, the
real runs, which wait for the owner's go-ahead. Parent spec:
`docs/features/2026_11_18_skill_evals/spec.md`.

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
- **Confirmed by a real smoke trial (2026-11-25, one ticket, $0.37):**
  - The tool is named `Agent`. Its input has `description`, `model`,
    `subagent_type` and `prompt`.
  - Text before a tool call is in the trace as an `assistant` text block. The
    coordinator wrote "Model: `sonnet`. The work is small and bounded ..."
    before the call, so `s2_model_stated` can be checked.
  - Events of a sub-agent are in the same trace. They carry a non-empty
    `parent_tool_use_id`. A check on the main thread must skip them.
  - The trace has two `init` and two `result` events after the agent returns.
    `parse_trace` keeps the last `result`. Cost and turns of the last result
    cover the whole run. (spec) Confirm this in step 1 with a unit test on the
    real shape.
  - Not seen yet: the input field for worktree isolation. A single-agent run
    does not use it. Read it in the first `parallel` smoke trial. If it is
    absent, `s4_worktree_each` reads `git worktree add` commands instead.
- **Machine prerequisite.** The runner does not install the skill. It needs the
  `~/.claude/skills/mayo-flow-*` links of the README install step. Without
  them, `/mayo-flow-delegate` is unknown and the model works alone: the first
  smoke trial on the work machine did exactly that.
- **Finding for decision 7.** In the smoke trial the agent said it could not
  show red for two tests that passed at once. The coordinator did not redo the
  ticket. It broke the code on purpose to prove the tests can fail. That is a
  valid way to verify, so `s6_rejects_missing_red` must accept "redo", "name the
  gap in the reply" and "prove the test fails by mutation".

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
| `s4_new_files` | 4 Parallel | each parallel-wave prompt names the shared file and limits it to a one-line edit |
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
| `parallel` | two parallel tickets that share one file, and two that touch the same file in series | `s4_*`, `s5_*` |
| `handback-trap` | see decision 7 | `s6_*` |
| `one-liner` | a one-line edit request | `n_no_delegate` |

Short cases stop early with the prompt ("stop after the first wave is merged
and report"), except `handback-trap`, which must run to the hand-back.
(spec) Use `--max-budget-usd 1` per trial as a second guard.

### 7. The hand-back trap is a planted fixture

- **Chosen:** a ticket whose new test already passes before any code. No agent
  can show a real red for it.
- **Check:** `s6_rejects_missing_red` passes if the coordinator redoes the
  ticket (a second `Agent` call for it), or proves the test can fail (for
  example, breaks the code on purpose and runs the test), or the final reply
  names the missing red and does not call the ticket done.
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

- One case, `ticket-run`: tickets 01, 03, 04 and 05 of the same `ticket-set`
  fixture (wave 1: 01, 03, 04; wave 2: 05), with 13 hidden tests. No
  `ticket-set-full` fixture was built: the existing fixture already has two
  waves and a file collision. The case reuses the `feature-start-e2e`
  machinery (`hidden_tests` fact, `visible_suite_green`, `hidden_seen`).
- The baseline prompt (`direct`) is the same text without the slash command and
  without the word "parallel", so it gets no hint about parallel work.
- The process checks are in the case `checks`, so they read as failures on the
  baseline. That is the measure. Hidden tests are the headline, not `passed`.
- Known limit: the fixture's old `tests/test_auth.py` uses a token with no
  expiry, which conflicts with ticket 01. An agent that adds expiry and leaves
  that test as it is fails `visible_suite_green`. This measures in part whether
  the agent noticed the conflict. Read it with the hidden tests.
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
2. Fixture `ticket-set`, plus fixture validation tests in
   `tests/test_evals_suites.py` (visible tests pass; planted traps exist).
3. Checks `s1_*` and `s2_*` in `evals/checks.py`, with unit tests. Case `models`.
4. Checks `s3_*`, regex lists in `suite.json`. Case `prompt-checklist`.
5. Checks `s4_*` and `s5_*`. Case `parallel`.
6. Check `s6_*`. Case `handback-trap`. Case `one-liner` and `n_no_delegate`.
7. `--mutant` flag in `run.py` and the six mutants, with unit tests.
8. `report`: one row per `s*` check, columns per condition and per mutant.
9. Layer A case `ticket-run` with hidden tests and its reference patch (on the
   `ticket-set` fixture).
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

## Check review after the first 56 runs

A review of the 56 stored runs (2026-11-25 and 2026-11-26) found check bugs
and one unfair case. This section records what changed and what is real
model behavior. Runs recorded before these changes are not comparable on
the changed checks.

### Fixture change: tickets 03 and 04 share `notesapi/__init__.py`

`s4_new_files` passed 0 of 11 runs. The case was unfair. In the old fixture
the parallel wave (tickets 03 and 04) shared no file. So the clause "new
code in new files, wired with one-line edits to shared files" had nothing
to do, and a good coordinator had no reason to say it. The old regexes
also asked for the words "new files" in every prompt, and the check read
the wave-two prompt (ticket 05) too.

Changes:

- Tickets 03 and 04 now also export their function from the package
  (`from notesapi import ...`). Both touch `notesapi/__init__.py`. The spec
  Parallel plan names this overlap.
- `s4_new_files` reads only the prompts of the `parallel_wave` agents.
- The rule of case `parallel` asks each wave prompt to name
  `notesapi/__init__.py` and to limit it to a one-line (or single-line)
  edit.
- The hidden tests of `ticket-run` have one new test each for tickets 03
  and 04 (the package import). The reference patch adds the two lines.

This changes the eval. The stored `parallel` and `ticket-run` runs used the
old fixture. Their `s4_new_files` outcome stays `false`, and their hidden
test count is lower. Compare only runs made after this change.

### `s2_model_stated`: real non-compliance, not a check bug

`s2_model_stated` passed 0 of 12 `models` runs. We read every failed trace.
The check is correct. It joins all main-thread text up to each model's
first Agent call, so text in the same message as the call, and one line
that covers several agents, already count. No `description` field names a
model.

- 4 runs set no `model` at all (3 baseline, 1 skill), so the check has
  nothing to find.
- 8 skill runs set models. In 0 of 8, every model was named before its
  first launch.
- First launch (ticket 01 on `opus`, ticket 02 on `sonnet`): named before
  the launch in 2 of 8, for example "Models: ticket 01 is authentication,
  so `opus`. Ticket 02 is a docs change, so `sonnet`." In the other 6, the
  choice is only in a thinking block, which the user does not see, for
  example "Ticket 01 gets opus for its authentication code and ticket 02
  gets sonnet for its docs-only change." One of the 6 says it after the
  launch: "Both agents are running (opus for 01, sonnet for 02)."
- Second launch (review on `sonnet`, suite run on `haiku`): `haiku` was
  named before the launch in 4 of 8, for example "Next I'm launching the
  test review (`sonnet`) and the full suite run (`haiku`) together." In 3
  of 8, `haiku` is in no visible text at all.

The owner can decide whether to make the skill clause stronger (for
example, "write the line as visible text, not only in thinking, before
every Agent call that picks a model").

### `handback-trap`: the trap is seldom reached

`s6_rejects_missing_red` and `s6_reruns_suite` passed 2 of 11 runs.

- Check bug, fixed: a background agent gets a launch notice as its tool
  result at once. Its real hand-back is a later `task_notification` event.
  The checks took the launch notice as the hand-back. Now they use the
  notification. `s5_wave_order` had the same bug and uses the same fix.
  `s6_rejects_missing_red` also counts a `SendMessage` that sends the work
  back to the same agent as a redo (seen in the `models` traces). No stored
  outcome changed: the 2 passing runs still pass on the real hand-back.
- Real behavior, 8 skill runs:
  - 4 of 8 started no agent. The main thread did both tickets itself.
  - 2 of 8 delegated only ticket 04. The main thread saw that
    `normalize_title` already exists and handled ticket 06 itself: one run
    wrote the tests and committed the ticket as done, one left it undone.
    Both named the missing red in the reply. The `mechanical` role of the
    case matches only ticket 06, so the re-run of the suite after the
    ticket 04 hand-back does not count for `s6_reruns_suite`.
  - 2 of 8 delegated both tickets. Both pass both checks.
- 3 baseline runs started no agent.
- In all 11 runs the final reply names the missing red of ticket 06. The
  coordinator usually reads `notesapi/notes.py` before it delegates, so it
  sees the trap first. The s6 checks measure the clause only when ticket 06
  goes to an agent. The owner can decide whether to make the trap harder to
  see before delegation.

### Other check fixes

- `s4_worktree_each` missed agents whose prompt holds the absolute path of
  a worktree added as `../wt03` or `$W/t03`. It now compares the last path
  components. One run (`ticket-run`, a shell loop `../wt_t$n`) still fails
  because the loop variable cannot be read from the trace.
- `duration_ms` and `num_turns` held only the last main-thread result event.
  A run with background agents has one result event per main turn. Both
  fields are now the sum over those events. The sum leaves out the time
  the main thread waits for a background agent, so it is lower than the
  wall time of the run.
