# CLAUDE.md

Guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions.
Bias toward caution over speed. Use judgment on trivial tasks.

Repo-facing artifacts — commit messages, code comments, docs, PR/issue text
— are always written in English, regardless of what language the
conversation with the user is in. Chat with the user in their language;
write to the repo in English.

## 1. Think Before Coding

- State assumptions explicitly before implementing. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If something is unclear mid-task, stop and surface it. Don't push through on a wrong assumption.
- If a simpler approach exists, say so. Push back when warranted. Don't be sycophantic.

## 2. Simplicity First

- Minimum code that solves the problem. Nothing speculative.
- No unrequested features, abstractions, flexibility, or configurability.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

## 3. Surgical Changes

- Touch only what the request requires.
- Don't improve, refactor, or reformat adjacent code.
- Don't delete or alter comments you don't understand — mention them if relevant.
- Match existing style, even if you'd do it differently.
- Remove imports/variables/functions that YOUR changes made unused. Leave pre-existing dead code alone — mention it instead.

## 4. Goal-Driven Execution

- Transform tasks into verifiable goals (see Testing below for how — TDD is the default path to a verifiable goal).
- For multi-step tasks, state a brief plan with a verify step for each stage before starting.
- Strong success criteria let you loop independently. If criteria are weak, ask before implementing.

## 5. Branching

- Create a new branch before starting any work. Default base: `main`.
- Exception: when the work is scoped to a larger feature already in progress on its own `feature/*` branch (not yet merged to `main`), branch off that feature branch instead, and merge back into it — not into `main` — until the whole feature ships. `mayo-flow-fix-start`/`mayo-flow-feature-start` apply this automatically.
- Branch naming: `feature/`, `fix/`, `chore/` prefix.
- `main` is always stable and deployable.

## 6. Feature specs

When starting a feature (not a fix or chore), write a spec before touching any code. Default location: `docs/features/` — but use whatever doc-folder convention the project has already adopted (e.g. `docs/10_features/`); `mayo-flow-feature-start` detects this automatically.

- Location: a feature folder `YYYY_MM_DD_<slug>/` (e.g. `2026_04_13_recommend_exclude_filter/`) holding `spec.md` and, for medium/large features, `tickets/NN_<slug>.md`. Older flat `YYYY_MM_DD_<slug>.md` specs stay valid.
- Content: goal, decisions/trade-offs, step-by-step implementation plan, test cases
- Commit the spec on its own before the first code commit

A project-level plan/roadmap doc (e.g. `PLAN.md`) belongs inside `docs/`
(`docs/PLAN.md`), not the repository root — same reasoning as feature specs:
`docs/` is where planning documents live.

## 7. Testing

- Every new piece of code gets a test.
- Follow red/green: write the failing test first, then make it pass.
- Tests must pass before every commit — never commit on red.

## 8. Commits

- Work units and commits are atomic — one logical change per commit.
- Commit message describes what was done and why, not just "fix stuff".
- The commit history should read like a step-by-step log of what was built.
- Follow [Conventional Commits](https://www.conventionalcommits.org/):
  `<type>[(scope)]: <description>`.
  - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
    `chore`, `build`, `ci`, `revert`.
  - Scope in parentheses when the change is localized (e.g. `feat(intercept): …`).
  - Description: imperative mood, no trailing period.
  - Breaking change: `!` after the type/scope, plus a `BREAKING CHANGE:` footer.
  - Examples: `feat(intercept): add native getCuratedApps/getInstalledApps`,
    `fix(auth): require shared-secret auth on webhook edge functions`,
    `docs: add feature spec for push notifications`,
    `chore: reorganize docs/ into NN_-prefixed lifecycle structure`.
- Exception: a project with its own established, different commit
  convention already documented in its own `CLAUDE.md` (e.g. a
  bracket-style `[FEAT{scope}]` prefix) keeps that convention — don't mix
  styles into an existing history. Conventional Commits is the default for
  everything else, including new projects.

## 9. Workflow skills

Rules 5-8 above are implemented as callable skills in `~/.claude/skills/`,
not just prose to reinterpret each time. Use them instead of improvising:

- `mayo-flow-project-init` — first step of a new project: `git init`, `.gitignore`, the `docs/` lifecycle folders (`00_phases`, `10_features`, `20_fix-plans`, `50_audits`), `docs/PLAN.md`, `docs/structure.md` and a root `CLAUDE.md`.
- `mayo-flow-gitignore` — create/extend a `.gitignore` matching the project's actual stack(s) plus universal OS/editor/secrets cruft. Use when a repo is brand new.
- `mayo-flow-feature-start` — start a feature: `feature/<slug>` branch, grill, spec first (in its own feature folder), then tickets for medium/large features.
- `mayo-flow-grill-prep` — prepare a grill's decision tree (research, options, recommended answers) in an isolated Opus run. Called by `mayo-flow-grill`.
- `mayo-flow-spec` — write the feature's `spec.md` from `grill.md` in an isolated Opus run. Called by `mayo-flow-feature-start`.
- `mayo-flow-grill` — one-question-at-a-time interview with a recommended answer each time, to resolve every open decision of a plan before the spec. Called by `mayo-flow-feature-start`; usable standalone.
- `mayo-flow-tickets` — split a feature spec into tracer-bullet tickets (vertical slices with blocking edges) as markdown files in the feature folder. Called by `mayo-flow-feature-start`.
- `mayo-flow-fix-start` — start a fix: fix-plan first, then `fix/<slug>` branch.
- `mayo-flow-run-tests` — detect and run the project's full verification suite (test/typecheck/lint); run before every commit, not just at the end.
- `mayo-flow-branch-finish` — gate on the full suite, merge `--no-ff`, archive the spec/fix-plan once fully done, update the project's structure doc if one exists, and check whether a periodic audit is due.
- `mayo-flow-audit` — run a security/performance/code-quality/patterns audit on request or when `mayo-flow-branch-finish` flags one as due.
- `mayo-flow-store-preflight` — check a built iOS .ipa or Android .aab (and a manual checklist) before uploading to App Store Connect / Google Play.
- `mayo-flow-clear-session` — before a `/clear`, leave a clean repo and a temporary `.claude/handoff.md`; after it, resume from that file.
- `mayo-flow-initial-discovery` — pass to find loose ends and stress the plan before building: review what exists, research similar products and rules with links, roast the assumptions across every aspect of the app, settle open questions in short guided rounds, and write every answer into PLAN, phases and specs. Use after PLAN/specs exist and before the next phase, or when the user asks what they are missing or says "roast me".

Invoke `mayo-flow-project-init` as the very first step of a new project (it
runs `mayo-flow-gitignore` itself; use `mayo-flow-gitignore` alone only to
extend an existing repo), `mayo-flow-feature-start`/`mayo-flow-fix-start` at the start of any
non-trivial feature or fix, and `mayo-flow-branch-finish` when it's ready to
merge — don't wait for the user to ask for the skill by name.

# Timeless constraints (not a checklist)

When two principles collide, pick the one that cuts future cost in THIS codebase.

HARD RULE: refactor to the principle FIRST, then change behavior.

1. Separation of Concerns — one kind of work per part (UI / domain / persistence / infra). Root principle.
2. Encapsulation / Information Hiding — small stable contract; hide internals.
3. High Cohesion + Loose Coupling — change-together lives together; independents talk narrow.
4. DRY — one authoritative representation of each piece of *knowledge* (not every similar line). Avoid over-DRY.
5. KISS — simplest design that works; complexity is the long-term tax.
6. Single Responsibility — one reason to change.
7. Depend on Abstractions — policy doesn’t depend on details; both depend on contracts.
8. YAGNI — no speculative features, frameworks, or “later” hooks.
9. Composition over Inheritance — assemble pieces; don’t grow fragile hierarchies.
10. Open/Closed (with discipline) — extend at stable boundaries; only where change showed up twice.

Honorable: Law of Demeter · fail fast / illegal states unrepresentable · optimize for deletion · Unix do-one-thing + compose.

Treat as constraints. Violate slogans when judgment says so.

