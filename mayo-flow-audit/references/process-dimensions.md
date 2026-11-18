# Audit dimensions: detail

## 4. Logic and patterns

Architecture smells, duplicated logic, risky
abstractions, error paths that are never exercised. Also **mutation-check
the tests**: for every test or assertion whose name promises a filter, a
guard, a validation or "nothing is written", break that behaviour in a
scratch copy (or inside a rolled-back transaction) and confirm the test
fails. A test that only asserts "it throws" does not prove "before anything
is written"; an assertion whose fixture can never reach the branch (a row
cut off by a `limit` anyway) is vacuous. If the mutation cannot be run, say
"reasoned, not mutation-run".

## 5. Claims vs evidence

For every checked-in statement, check the
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

## 6. Workflow compliance

Compare `git log` and the branch state with the
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

## 7. Data integrity

Only if the repo ships datasets (curriculum, seeds,
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

## 9. UI and design

Only when the project has a user interface; skip it
(say so) otherwise. If the `impeccable` plugin is installed, run
`/impeccable audit` (technical quality) and `/impeccable critique`
(scored UX review) on the screens the audited work touched, following
`mayo-flow-design` (it holds the native-app setup and which pieces are
web-only). Record each screen as `reviewed` or `not verified` with
the command output as evidence, and compare against the project's own
design source (e.g. `Design/`, `DESIGN.md`). Without the plugin, check by
hand: states (empty, loading, error, offline), touch targets, contrast,
text scaling, and consistency with the design source.
