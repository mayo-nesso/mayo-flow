---
name: mayo-flow-design
description: Single entry point for UI/design work inside the mayo-flow process - says which Impeccable command to run at which stage (project init, before the spec, ticket acceptance, branch-finish gate, audit) and how to apply it to native/React Native apps. Called by feature-start, tickets, branch-finish, audit and project-init when the work touches UI; usable standalone.
version: 1.0.0
---

# Design inside the flow

Design tooling is the **`impeccable` plugin** (`impeccable:impeccable`, tested
with 4.9.1, Apache 2.0). It is referenced, never copied: do not vendor its
files into `~/.claude/skills` or a project. This skill is the only place the
flow names its commands, so swapping or adding a design tool means editing
this file, not the five skills that call it.

Run it only when the work touches UI (screens, components, copy shown to the
user, theming). Otherwise say "no UI in this change" and return.

## 0. Preconditions

- Plugin missing (`/plugin` list, or the `impeccable:impeccable` skill is not
  offered)? Say so, use the manual fallback in section 4, and tell the user
  how to install it (`/plugin marketplace add pbakaus/impeccable`, then
  install from `/plugin`). Never install silently.
- **Own design source wins.** If the project has `Design/`, `DESIGN.md` or
  `PRODUCT.md`, read them first and treat them as truth. Never overwrite an
  existing `PRODUCT.md` or `DESIGN.md` without asking; Impeccable's `init` and
  `document` are only for files that do not exist yet.
- **Native / React Native / Flutter app:** `PRODUCT.md` must carry
  `## Platform` = `ios`, `android` or `adaptive`. Use only the commands that
  have a native path (`shape`, `critique`, `audit`, `adapt`, `polish`, `init`,
  `document`). Skip the detector, `live` and the design hook: they are
  web-only (the plugin's hooks are disabled on this machine on purpose; see
  section 5).
- `critique` and `audit` are read-only. Commands that edit code (`polish`,
  `adapt`, `harden`, ...) go through the normal ticket loop: own commit,
  tests first when logic changes, full suite before commit.

## 1. Stage map

| Flow stage | Caller | Run | Output goes to |
|---|---|---|---|
| New project | `mayo-flow-project-init` | `init` (then `document` once screens exist) | `PRODUCT.md`, `DESIGN.md` at the repo root, committed. If `Design/` already exists, link it from `PRODUCT.md` instead of duplicating it |
| Before the spec | `mayo-flow-feature-start` | `shape <feature>` | `<feature-folder>/design.md`; the spec links it |
| Ticket drafting | `mayo-flow-tickets` | none; add the UI criteria below to each UI ticket | the ticket file |
| Gate before merge | `mayo-flow-branch-finish` | `critique` on the changed screens (+ `audit` when the change is large) | the branch-finish report |
| Periodic audit | `mayo-flow-audit` | `audit` + `critique` (dimension 9) | the audit doc |

**UI ticket criteria** (copy the ones that apply into `## Acceptance
criteria`): every state exists (empty, loading, error, offline); touch targets
and text scaling hold on the smallest supported device; contrast checked; copy
matches the design source; a `critique` of the screen has no open blocker
before the ticket is `done`.

## 2. Running it

Invoke the `impeccable:impeccable` skill with the command and the target
(for example `critique app/(tabs)/home.tsx`). Follow its own setup. Quote the
findings in the report; do not summarize them away. A finding is `fixed`,
`ticketed` (new ticket or fix-plan) or `accepted` (say why); none stays
silent.

## 3. Gate rule (branch-finish)

A UI change is not blocked by taste. Block the merge only on a `critique` /
`audit` finding rated blocking or on a regression against the project's own
design source; list the rest as follow-ups. A screen that was not looked at is
`not verified`, never "fine".

## 4. Manual fallback (no plugin)

Check by hand and record each as `ok` / `issue` / `not verified`: states
(empty, loading, error, offline), touch targets, contrast, text scaling,
consistency with `Design/` / `DESIGN.md`, copy tone.

## 5. Known limits (update when they change)

- The plugin ships SessionStart / PostToolUse / Stop hooks. They were
  emptied in the plugin cache (`hooks/hooks.json`, original kept as
  `hooks.json.orig`) because they target web code and add latency to every
  edit. A plugin update restores them: re-empty and re-check after updating.
- Web-only pieces: detector, `live`, the Chrome/VS Code extensions.
