---
name: mayo-flow-audit
description: Run a periodic audit of the project (security, performance, code quality, logic/patterns, plus claims-vs-evidence, workflow compliance, data integrity and legal and platform exposure), write dated reports into the project's audits doc folder, and archive the previous round. Use when the user asks for an audit or a review of what was built so far, or accepts an audit proposed by mayo-flow-branch-finish or by the risk triggers below.
version: 1.4.0
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
   environment has one. Also check destructive operations: tests and scripts
   that delete, truncate or reset data must refuse a non-local target and
   must not wipe data they did not create; secrets in files, logs or errors.
2. **Performance.** Start from what the user *waits on*, not from the
   slowest query. Walk each user journey (cold launch, the main action, the
   last step of a flow, every tab and screen entry) and list, per step, the
   sequence of loading states the user actually sees. Look for:
   - **Double loading:** a spinner or skeleton that closes and is followed by
     another one for data that was already known or fetched (a response that
     carries a row and the client re-reads it; a wait dialog that closes
     before the next screen's data is in hand). One wait should cover one
     journey step.
   - **Fetch-on-arrival:** data requested only after navigating to the
     screen that needs it, when the previous screen could have started it
     (prefetch while the user is reading, rating or typing).
   - **Waterfalls:** sequential awaits or dependent providers on the same
     path that do not depend on each other (parallelise); work gated on a
     slow signal it does not need (a connection handshake, a status event).
   - **Cold-start cost:** a connection, socket, cache or SDK that is opened
     lazily at the moment the user is waiting; token, session and config
     lookups repeated per request.
   - **Server side:** round trips per request, N+1 reads, unindexed filters
     and foreign keys, unbounded growth (logs, caches), work repeated per
     call that could be cached, payloads larger than the screen uses.
   - **Client side:** rebuilds and animations that keep running off-screen,
     per-tick `setState`, lists built eagerly, repeated invalidation on
     navigation.
   Rank findings by the wait a person feels times how often they hit it, not
   by how bad the code looks. Prefer measured numbers (device timings, query
   plans, logs); mark the rest "reasoned, not measured". A MEDIUM-or-higher
   performance finding still open at the next round is escalated in the
   summary (owner decides: fix, defer with a date, or accept), never
   silently carried as "STILL OPEN".
3. **Code quality** — style, structure, dead code. Cover *all* code, not only
   the app: tests, scripts, CI config, migrations, tooling.
4. **Logic and patterns** — architecture smells, duplicated logic, risky
   abstractions, error paths that are never exercised. Also **mutation-check
   the tests**: for every test or assertion whose name promises a filter, a
   guard, a validation or "nothing is written", break that behaviour in a
   scratch copy (or inside a rolled-back transaction) and confirm the test
   fails. A test that only asserts "it throws" does not prove "before anything
   is written"; an assertion whose fixture can never reach the branch (a row
   cut off by a `limit` anyway) is vacuous. If the mutation cannot be run, say
   "reasoned, not mutation-run".
5. **Claims vs evidence** — for every checked-in statement, check the
   artifact does what it says: docs and specs against the code they describe
   (stale or contradictory after a later decision), commit messages and test
   names against the diff, fixtures and eval sets against their description
   (a "typos and dictation style" set with none of either), any number or
   estimate against its source (unsourced figures are findings), and
   "verified" or "checked" wording against what the check actually covered.
   Also list what was **never run**: CI that has no remote, code paths only
   tested with fakes, real integrations not exercised, platforms not built.
   **Spec-vs-implementation table:** take the spec or phase doc that governs
   the work and mark every bullet and every "done when" item as done,
   deviated or pending, with evidence. Include interface changes (an extra
   parameter, a different argument type, a renamed field) and deviations that
   only a commit message or a code comment mentions: if the doc does not say
   it, the next reader cannot know it.
6. **Workflow compliance** — compare `git log` and the branch state with the
   rules in the project's `CLAUDE.md` and the user's global one: spec before
   code, red before green, atomic Conventional Commits, branch off the right
   base, `mayo-flow-branch-finish` used to merge, phase or task order
   followed, nothing added that was not asked for (dependencies, CI changes,
   new tools). Deviations that were disclosed to the user are lower severity
   than silent ones. A merge commit does not show whether `mayo-flow-branch-finish`
   ran: look for its traces (merged branches left undeleted, the structure doc
   updated when files moved, an audit-due check) and use the author's
   disclosure; when neither exists, record "cannot be told from git" instead
   of passing it. Count the merges since the last audit against the
   threshold. For phase or task order, compare the order of the commits with
   the order of the spec and note where a step was started before its
   prerequisite.
7. **Data integrity** — only if the repo ships datasets (curriculum, seeds,
   fixtures, generated content). Verify against the source of truth with a
   method independent of the tool that produced the data (not the same LLM
   pass re-reading its own output): counts, identifiers, a strict text match
   against the source, plus a human spot-check list for what cannot be
   automated. State plainly which parts were only verified by the producer.
   Compare text in **two passes and report them separately**: (a) letters and
   digits only, which tolerates hyphenation and typography; (b) punctuation
   and spacing sensitive, or at least a lint for the slips a letters-only pass
   cannot see (stray space before `)`, a sentence joined with `. ` and a
   lowercase word where the rest use `; `, doubled spaces, trailing
   separators). Never write "identical" without saying which pass. Check
   generated fields (keywords, tags, summaries) too, and whether test fixtures
   were written from the data they test (measure the word overlap: a fixture
   that reuses the generated keywords proves little).

8. **Legal and platform exposure** — a small app with no revenue can still owe
   per-event penalties: the unit is per visitor, per session, per email, per
   image. Check each of the seven items below against the code and the config
   and record each as `applies`, `does not apply` or `not verified`, with
   evidence (file:line, the command run, the dependency list). `Does not
   apply` needs proof (a grep, the lockfile), not a feeling.
   a. **Age and children.** Any signup, profile or data collection that can
      involve minors: under-13 in the US (COPPA), minors under GDPR or the
      local data law. Is there an age gate or an adult confirmation before
      data is stored? Who supplies the child's data, the child or an adult?
      Does the store listing target children? Is there third-party analytics
      or advertising?
   b. **Third-party resources loaded at runtime.** Fonts (Google Fonts), CDN
      scripts, icons, maps, embedded video, tracking pixels: each one sends
      the visitor's IP to someone else (a Munich court awarded one visitor
      EUR 100 over Google Fonts, 2022). Prefer bundled or self-hosted. Grep
      for the font hosts, `@import`, `<link>`, absolute URLs in assets and for
      packages that fetch fonts or assets at runtime (for example
      `google_fonts`).
   c. **Session recording and input capture.** Session replay, screen
      recording, heatmaps, keystroke capture. In some US states this can be
      treated as wiretapping (California CIPA). Check the SDK configuration:
      replay off, or on only with consent and masked inputs.
   d. **Outgoing email.** A marketing or "we launched" message needs an
      unsubscribe link and a postal address in every message (US CAN-SPAM).
      Transactional email is different. `Does not apply` if no email is sent
      or collected.
   e. **Subscription checkout.** Price, billing period, automatic renewal and
      how to cancel are visible next to the subscribe button, not only on a
      linked page (store rules; California automatic-renewal law). Check the
      restore and refund paths too.
   f. **User uploads and published content.** If users upload or publish
      content that others can see, a registered DMCA agent (a small US fee)
      is needed for safe harbour, plus a takedown process. `Does not apply`
      if nothing uploaded is shown to anyone else.
   g. **Store policy drift.** For an Android app, check the restricted permissions
      and declarations against the latest Google Play policy update (location
      scope, local network, contacts, call log/SMS, all-files, accessibility) and
      the account items (trader status, Japan payments authorization). Use the
      checklist in `mayo-flow-store-preflight` section 3.7 rather than duplicating it.
      For an iOS app, check the account-termination triggers listed there (hidden
      or obfuscated features, remote flags, UGC/AI safeguards, bait-and-switch
      subscriptions, near-duplicate apps, linked accounts).
   Also check that what the app tells people (privacy summary, consent text,
   store privacy forms) matches what it really sends: compare it with the SDKs
   in the dependency list and the network calls.
   **Limits of this dimension.** The penalty figures commonly quoted for these
   items (for example about US$53K per child, per email or per violation,
   about US$5K per session, about US$150K per work) come from a social-media
   checklist and are **not verified**. Do not quote them in a report without a
   current source, and label them as order of magnitude. Jurisdiction matters:
   US federal and state laws bind the app's US users, so check where the app
   is actually distributed and who uses it. This is a way to find exposure, not
   legal advice: findings go to the user and, before public launch, to a lawyer.

Ask the user if they want to narrow this (e.g. "just security this time") or
add a project-specific dimension (e.g. accessibility). Dimensions 5 to 8 may
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

**Independence.** If the same session or agent wrote the code, its review is
biased toward its own choices. Prefer a fresh-context reviewer (a sub-agent
or fork that has not seen the work) for dimensions 1 to 4, 7 and 8. Obey any
limit on agents in the project's `CLAUDE.md` or the user's instructions
(for example "one agent at a time"): if parallel agents are not allowed,
run the dimensions one after another, and say that the review is not
independent when no fresh reviewer was used.

**Evidence rule.** Every finding quotes evidence you just read or ran
(file:line, command output, a page of the source document). Do not report
from memory. If something could not be verified, say "not verified" instead
of filling it in. Do not invent numbers or estimates; label any that are
assumptions.

Findings format per issue: severity (CRITICAL/HIGH/MEDIUM/LOW/INFO),
file:line, what's wrong, why it matters, suggested fix. Be concrete — no
findings that just restate a category name. Also list **what was checked and
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

Use only the dimensions actually scoped. Match whatever format the project's
own prior audits already use if any exist (for example a single review file
with a verification table and numbered findings) — don't introduce a
competing format.

## 5. Archive the previous round

If a prior audit round exists in the same folder (not already in
`archived/`), move its files into `archived/` now that this round supersedes
it (`git mv`).

## 6. Commit

Use the project's commit convention. Conventional Commits by default:

```
docs: add YYYY-MM-DD audit round
```

(If the project documents a different established convention, such as a
bracket style, use that one.) Docs-only commit, no code changes in this
commit even if findings suggest fixes.

## 7. Hand off findings

Do not silently fix findings as part of this skill. Present the summary to
the user and ask which findings should become new work — each accepted
finding becomes a `mayo-flow-fix-start` (bug) or `mayo-flow-feature-start`
(larger rework) as appropriate, on its own branch, TDD as usual. Findings the
user accepts as risk are recorded as accepted (with the date), not dropped.
