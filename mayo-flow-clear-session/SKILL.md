---
name: mayo-flow-clear-session
description: Two modes around a context /clear. WRITE - leave the repo in a clean, resumable state and write a temporary .claude/handoff.md (current state + next steps only) so the user can /clear fast. RESUME - in a fresh context, read .claude/handoff.md, verify it, continue from its next steps and delete it. Use WRITE when the user says "clear session", "limpia la sesión", "voy a hacer clear", "deja un handoff". Use RESUME when the user says "retoma", "continúa", "lee el handoff", "resume", or starts a session by asking to read .claude/handoff.md.
version: 2.0.0
---

# Clear session: write a handoff, /clear, resume

Purpose: make `/clear` cheap. The handoff is throwaway working state (what is going
on right now and what to do next). Durable knowledge does NOT live in it: decisions
go to the repo docs (specs, plans, `docs/HANDOFF.md`, audits) or to memory. The
handoff only points to them.

You cannot run `/clear` yourself (it is a built-in CLI command). In WRITE mode you
prepare everything and tell the user to type it.

File: `<repo-root>/.claude/handoff.md`. One per repo; the newest overwrites the old.
Different from a committed `docs/HANDOFF.md` (the durable state doc): never
overwrite or delete that one.

Pick the mode from the user's words. If the file exists and the user did not say
which, ask once.

---

## WRITE mode

### 1. Gather the state (read-only, in parallel)
- `git status --short`, current branch, `git log --oneline -8`, `git worktree list`,
  `git branch --no-merged <default-branch>`.
- Background work: agents still running or finished but not merged (name, branch,
  what they were doing). If any is still running, say so and ask whether to wait; a
  handoff that hides a live agent is worse than none.
- Anything uncommitted that belongs to this work. Do NOT commit or stash to "tidy up";
  list it and tell the user.
- External state changed this session that the repo does not show (deploys,
  migrations, store uploads, installed builds, local DB resets, secrets set).

### 2. Decisions go to docs, not to the handoff
If the user made decisions this session that are not yet written in the repo or in
memory, STOP and offer to write them first (spec/plan/`docs/HANDOFF.md`/memory).
Only continue once they are saved or the user says to skip. Never park a decision
in the handoff.

### 3. Write `.claude/handoff.md` (under ~50 lines)
Language: the repo's (English if repo-facing text must be English), chat reply in the user's.

```
# Handoff — <YYYY-MM-DD HH:MM> — <branch> @ <short-sha>
## Goal in one line
## Current state     (done/merged; running; uncommitted; external state changed)
## Next steps        (numbered, concrete: the command/skill/file to start; mark which need the user's OK)
## Waiting on the user (tests/approvals only they can do)
## Rules in force    (only those that change what you may do: "no push", "ask before hosted writes", "no paid calls")
## Pointers          (specs, tickets, audits, docs/HANDOFF.md, memory names, agent branches/worktrees to merge or delete)
```
No history, no logs, no secrets (keys, tokens, URLs with keys), nothing that `git log`
or the docs already say: point to it. Write "not verified" for anything you did not
just check.

### 4. Keep it out of git
Without touching the project's `.gitignore`:
```
git check-ignore -q .claude/handoff.md || echo ".claude/handoff.md" >> "$(git rev-parse --git-path info/exclude)"
```

### 5. Hand over
Reply with: one line on the state (clean / what is left dirty), the file path, and
tell the user to type `/clear` and then say `retoma` (or "lee .claude/handoff.md").
Start no new work after writing it.

---

## RESUME mode (fresh context)

1. Read `.claude/handoff.md`. If it does not exist, say so and stop; do not guess.
2. Verify what can have drifted before acting: branch and `git status`, the SHAs,
   that listed agents/branches/worktrees still exist, anything marked "not verified".
   Report differences instead of trusting the file.
3. Read the pointers that the next step needs (spec/ticket/doc), not all of them.
4. Tell the user in 3–5 lines: where things stand and what you will do first. Items
   under "Waiting on the user" are reminded, never guessed. Respect "Rules in force".
5. Delete the file (`rm .claude/handoff.md`) once you have taken the steps over; the
   conversation's tasks and the docs hold them from then on. Do not delete it if
   verification failed badly enough that the user must reread it: say so.
6. Continue with Next step 1 unless it needs the user's OK; then ask.

## Rules
- WRITE and RESUME are read-only toward the repo apart from the handoff file and the
  `info/exclude` line: no commits, merges, pushes, deploys or deletes (other than the
  handoff itself in RESUME).
- Never claim a state you did not just verify.
- Never store secrets or decisions in the file.
