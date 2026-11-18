---
name: mayo-flow-project-init
description: Bootstrap a new project's repo and docs structure - git init, .gitignore, the docs/ lifecycle folders (00_phases, 10_features, 20_fix-plans, 50_audits), docs/PLAN.md, docs/structure.md and a root CLAUDE.md with the project's conventions. Use as the very first step of a new project, before any feature work, or when an existing repo has no docs/ process structure yet.
version: 1.1.0
---

# Bootstrap a new project

This is the opening half of the mayo-flow workflow. It sets up everything
`mayo-flow-feature-start`, `mayo-flow-fix-start`, `mayo-flow-branch-finish`
and `mayo-flow-audit` expect to find, so none of them has to improvise a
layout later. It writes structure and docs only, never application code.

Argument (optional): the project name or a one-line description.

## 1. Look before creating

- Is this already a git repo? Is there an existing `docs/`, `CLAUDE.md`,
  `.gitignore`, or a spec/design folder (e.g. `design/`, `Design/`, `specs/`)?
  Read what is there first.
- Existing spec/design folders are **read-only source material**: leave them
  where they are, never move, translate or reformat them. Link to them from
  `docs/PLAN.md` instead.
- If `docs/` already exists with a different layout (e.g. `audits/`,
  `features/`, `planned/`), do not migrate it silently. Say what is there and
  offer to migrate; only migrate if the user agrees.
- If `CLAUDE.md` exists, extend it. Never overwrite one the user has written
  or copied in; show them the diff of what you would add.

## 2. Ask the few things that change the output

Ask in one batch, with a recommended default for each:

1. **Stack** (drives `.gitignore` and the commands section). If the repo is
   empty, ask; do not guess.
2. **Language of repo docs.** Default: English (global rule). Existing spec
   folders keep their own language.
3. **Commit convention.** Default: Conventional Commits for a new repo. Use
   bracket-style `[TYPE{scope}]` only if the project already has that history.
4. **Scope of this first branch.** Default: structure and docs only.

5. **Has a UI?** If yes, offer `mayo-flow-design` to create `PRODUCT.md` /
   `DESIGN.md` (never overwriting existing ones or a `Design/` folder).

Skip any question the repo or the user's message already answers.

## 3. Initialize git

If not a repo yet: `git init -b main`. Then invoke **`mayo-flow-gitignore`**
with the stack from step 2, and commit it alone:
`chore: add .gitignore for <stack>`. Existing spec folders go in their own
commit (`docs: add design specs ...`), unchanged.

Create `feature/repo-scaffolding` (or `chore/repo-scaffolding`) for the rest.
The scaffolding itself is a branch like any other, not a direct commit to `main`.

## 4. Create the docs lifecycle folders

```
docs/
├── PLAN.md
├── structure.md
├── 00_phases/
├── 10_features/archived/
├── 20_fix-plans/archived/
└── 50_audits/archived/
```

- `.gitkeep` only inside the empty `archived/` folders (that is enough to
  make their parents exist in git). Do not add `.gitkeep` next to real files.
- Created later, on first need, never as empty files: `docs/05_discovery/`
  (`mayo-flow-initial-discovery`), `docs/GLOSSARY.md` (project terms, one line
  each, added by `mayo-flow-grill`), `docs/adr/` (decisions that are hard to
  reverse, surprising and a real trade-off) and `docs/test-catch-log.md`
  (`mayo-flow-run-tests`). List them in `structure.md` as lazy.
- The `NN_` numbers are deliberate: leave `30_` and `40_` unused, and add any
  new process folder in a gap instead of renumbering. `PLAN.md` and
  `structure.md` live in `docs/`, never in the repo root.

## 5. Write `docs/PLAN.md`

Title, updated date, links to any spec folder and to the phase chain, then:
what we're building (short), a decisions table, MVP scope in/out, a phase
table with a one-line "done when" each, risks, and open items.

- Take the content from what the user and the existing specs actually say.
  Mark anything unconfirmed as an open item; do not invent decisions,
  estimates or dates. Use `TBD` for estimates.
- If a sibling project or older doc describes something similar, say whether
  it applies. Do not merge two different products' plans silently.

## 6. Write the phase docs (when there is a plan to expand)

One `docs/00_phases/phase_N.md` per phase, same shape each time:
header (estimate, overview link, prev/next, "read first" spec refs), **Goal**,
**Done when** (bullets a person can check without interpreting), then
numbered work items, each with the commit message it should produce. Say
which items are TDD.

If there is no plan yet, create only the empty `00_phases/` folder and tell
the user the phases come next.

Write full file names in references (`design/03-foo.md`), never `design/03-…`,
so they can be grepped and checked.

## 7. Write `docs/structure.md`

Top-level layout tree, one line per folder, marking anything planned but not
created yet (e.g. `[not created yet - Phase 0]`). State that spec folders are
read-only and where decisions that supersede them get recorded. It is kept
current at merge time by `mayo-flow-branch-finish`.

## 8. Write or extend the root `CLAUDE.md`

Keep it short: conventions and invariants only, depth lives in `docs/`.
Include:

- What the project is, in two sentences, and the repo layout.
- Language rule (code/comments/commits in English; user-facing text per the
  project's i18n approach).
- The commit convention chosen in step 2, stated explicitly.
- The docs lifecycle: feature specs in `docs/10_features/` before code,
  fix plans in `docs/20_fix-plans/`, audits in `docs/50_audits/`, phases in
  `docs/00_phases/`, and `docs/structure.md` as the project map.
- Branching (`feature/`, `fix/`, `chore/` off `main`), tests before every
  commit, and finishing with `mayo-flow-branch-finish`.
- Stack-specific invariants the user has stated (architecture layers, "never
  call X directly", secrets rules).
- A `Commands` section, left as a stub if the stack is not set up yet.

## 9. Verify, commit, hand off

- Every path cited in `CLAUDE.md` and `docs/` exists (grep for the
  references and `ls` each one). Placeholder names such as `<slug>` are fine.
- Any spec folder is unchanged: `git diff --stat HEAD -- <folder>` is empty.
- `git status` is clean and OS junk like `.DS_Store` is ignored.

Commit in logical pieces, not one lump (e.g. `docs: add root CLAUDE.md ...`,
then `docs: add PLAN, phase docs and structure reference`). There is no test
suite yet: say so explicitly rather than skipping the gate silently, then
finish the branch with `mayo-flow-branch-finish` (merge `--no-ff`; nothing to
archive, these are living docs).

End by telling the user: what was created, what was left as `TBD` or an open
item, and what the natural next step is (usually starting phase 0 with
`mayo-flow-feature-start`).

When the PLAN has open items or the scope is large, also offer
**`mayo-flow-initial-discovery`** as the step right after the PLAN and before phase 0
code: a pass to find loose ends, research similar products and settle open
questions while changes are still cheap. It is an offer, not automatic.
