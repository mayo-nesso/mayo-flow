---
name: mayo-flow-audit
description: Run a periodic audit across security, performance, code quality, patterns, process, data integrity, legal/platform exposure and UI, writing dated reports to the audits folder. Use when the user asks for an audit or accepts one proposed by mayo-flow-branch-finish. Not for reviewing a single diff.
version: 1.5.4
---

# Run a periodic audit

This is a proposed, user-approved checkpoint — never run this silently as a
side effect of something else. It exists to catch drift before it compounds:
in the code, and also in what the docs, commits, tests and data *claim*
versus what they actually do.

## 0. Know when an audit is due

`mayo-flow-branch-finish` counts merges into `main`/`master` (default
threshold 10). A merge count is a weak signal: docs-only merges inflate it,
and the riskiest work often sits on an unmerged feature branch. Also propose
an audit when any of these is true, even below the threshold:

- a stretch of work was written mostly by an agent or by one session with no
  independent review (author blind spots);
- the work adds generated or extracted data (seed files, fixtures, eval sets),
  a first external integration (vendor API, payments), schema/RLS changes or
  scripts that delete or reset data;
- the work adds a signup or any data collection that can involve minors, a
  paywall or subscription, outgoing email, user uploads, or a third-party SDK
  or resource that loads at runtime or records the screen (dimension 8);
- the user asks whether something was missed, or catches a claim that turned
  out to be wrong.

## 1. Scope the audit

Default dimensions, each its own doc:

1. **Security** — prefer the dedicated `security-review` skill/command if this
   environment has one. **Read `references/security.md` before this
   dimension**: reading code is not enough, the reviewer must send edited
   requests (reset poisoning through `Host`/`X-Forwarded-Host`, a token used
   for another account, ids and fields changed in the request, actions
   called as another role or tenant, the auth provider's endpoints called
   directly) and record what came back. These tests write to the local
   instance: say so before the first one and list the writes as side
   effects. Also check destructive operations: tests and scripts
   that delete, truncate or reset data must refuse a non-local target and
   must not wipe data they did not create; secrets in files, logs or errors.
   Judge findings like Cloudflare's `security-audit-skill` does: a finding is
   `confirmed` only with a full source trace and an observed result; a
   blocked but source-grounded lead is `needs validation` (no severity); a
   disproved one is `rejected`. A missing redundant layer is a hardening note,
   not a vulnerability, and severity is likelihood × impact, not distance from
   a checklist. For a deep pass on a large codebase, that skill
   (<https://github.com/cloudflare/security-audit-skill>, MIT) is the
   reference: it needs Node, parallel sub-agents and a network-blocking
   sandbox, so propose it, never install it unasked.
2. **Performance** — start from what the user *waits on* (loading states per
   journey step: double loading, fetch-on-arrival, waterfalls, cold-start cost,
   server and client side). **Read `references/performance.md` before this
   dimension** for the checklist, ranking and escalation rule.
3. **Code quality** — style, structure, dead code. Cover *all* code, not only
   the app: tests, scripts, CI config, migrations, tooling.
4. **Logic and patterns** — architecture smells, duplicated logic, risky
   abstractions, error paths that are never exercised, plus mutation-checking
   the tests. **Read `references/process-dimensions.md` before this
   dimension.**
5. **Claims vs evidence** — check that every checked-in statement is what the
   artifact actually does, and list what was never run. **Read
   `references/process-dimensions.md` before this dimension.**
6. **Workflow compliance** — compare `git log` and the branch state with the
   rules in the project's `CLAUDE.md` and the user's global one. **Read
   `references/process-dimensions.md` before this dimension.**
7. **Data integrity** — only if the repo ships datasets; verify them against
   the source of truth with a method independent of the tool that produced
   them. **Read `references/process-dimensions.md` before this dimension.**

8. **Legal and platform exposure** — a small app with no revenue can still owe
   per-event penalties (per visitor, session, email, image). **Read
   `references/legal-platform.md` before this dimension**: seven items, each
   recorded as `applies`, `does not apply` or `not verified` with evidence.

9. **UI and design** — only when the project has a user interface; skip it
   (say so) otherwise. **Read `references/process-dimensions.md` before this
   dimension.**

Ask the user if they want to narrow this (e.g. "just security this time") or
add a project-specific dimension. Dimensions 5 to 9 may
be merged into one `process` doc when there are few findings.

## 2. Find the audits doc folder

Look for `docs/*audits*/` (e.g. `docs/50_audits/`) with an `archived/`
subfolder. If only a plain `docs/audits/` exists, use it and mention the
`NN_` layout gap. If neither exists, create `docs/50_audits/archived/` and
say so.

## 3. Do the review

**Author's disclosure (ask before reviewing).** Git shows only what was
committed. Ask the user, once and briefly, for what the author did or said
outside the repo: figures or estimates given in chat, merges or steps done by
hand instead of through a skill, checks that were run but not saved, shortcuts
taken, anything said to be "verified". Record each as an out-of-repo claim in
the process audit and mark it **not verifiable by this audit** unless an
artifact backs it. This asks for facts, not findings: do not ask for a list of
known problems. If the author keeps such a list separately, read it only
after the reports are written, then add a short comparison (what the audit
caught, what it missed and why) so the skill can be improved.

**Leave no trace.** The audit must not change the project's state. Prefer
read-only checks. When a measurement needs data or writes (an ingestion run, a
query plan), do it in a transaction that is rolled back, in a scratch copy, or
in a throwaway database, never in the developer's working database. Never
delete rows or files to clean up after yourself without asking; if something
was written anyway, list it under "Side effects of this audit" in the summary
with the exact command that restores the state. If a permission prompt or
classifier blocks a cleanup, stop, report it and let the user decide; do not
route around it (for example by running a test suite that happens to do the
same deletion).

Start with a **verification run**: execute the project's full suite
(`mayo-flow-run-tests`) and record a table of each check with its result,
including every check that could not run or never has. Then, for each
dimension, review the current state of the codebase (not just the diff since
the last audit — drift accumulates outside any single branch too), including
unmerged branches that hold work not yet reviewed.

**Independence.** If the same session or agent wrote the code, prefer a fresh-context reviewer (a sub-agent
or fork that has not seen the work) for dimensions 1 to 4 and 7 to 9. Obey any
limit on agents in the project's `CLAUDE.md` or the user's instructions
(for example "one agent at a time"): if parallel agents are not allowed,
run the dimensions one after another, and say that the review is not
independent when no fresh reviewer was used.

**Evidence rule.** Every finding quotes evidence you just read or ran
(file:line, command output, a page of the source document). If something could not be verified, say "not verified" instead
of filling it in. Do not invent numbers or estimates; label any that are
assumptions.

Findings format per issue: severity (CRITICAL/HIGH/MEDIUM/LOW/INFO),
file:line, what's wrong, why it matters, suggested fix. Also list **what was checked and
is fine**, so a reader knows what the audit covered.

## 4. Write the reports

Date: today, `YYYY_MM_DD`. Files:

- `YYYY_MM_DD_security_audit.md`
- `YYYY_MM_DD_performance_audit.md`
- `YYYY_MM_DD_code_quality_audit.md`
- `YYYY_MM_DD_logic_audit.md`
- `YYYY_MM_DD_process_audit.md` (claims vs evidence, workflow compliance, data
  integrity — or whichever of those were scoped)
- `YYYY_MM_DD_legal_audit.md` (legal and platform exposure, the seven items with
  their `applies` / `does not apply` / `not verified` status; may be merged into
  the process doc when nothing applies)
- `YYYY_MM_DD_summary.md` — the verification-run table, a tally table
  (severity × dimension) plus a unified top-N list of the highest-priority
  issues across all dimensions, each tagged with its status (e.g. NEW, still
  open from a prior round), a "Side effects of this audit" section (empty if
  none) and a "Not verified" list. Reference the previous round's summary file
  by path, if one exists.

Match whatever format the project's
own prior audits already use if any exist (for example a single review file
with a verification table and numbered findings) — don't introduce a
competing format.

## 5. Archive the previous round

If a prior audit round exists in the same folder (not already in
`archived/`), move its files into `archived/` now that this round supersedes
it (`git mv`).

## 6. Commit

Use the project's commit convention (global `CLAUDE.md` section 8). Conventional Commits by default:

```
docs: add YYYY-MM-DD audit round
```

Docs-only commit, no code changes in this
commit even if findings suggest fixes.

## 7. Hand off findings

Do not silently fix findings as part of this skill. Present the summary to
the user and ask which findings should become new work — each accepted
finding becomes a `mayo-flow-fix-start` (bug) or `mayo-flow-feature-start`
(larger rework) as appropriate, on its own branch, TDD as usual. Findings the
user accepts as risk are recorded as accepted (with the date), not dropped.
