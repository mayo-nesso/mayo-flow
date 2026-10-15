---
name: mayo-flow-gitignore
description: Create or extend a .gitignore appropriate to the project's actual tech stack(s), plus universal OS/editor/secrets cruft. Use when initializing a new repository, or when a new language/tool is introduced into an existing one without ignore rules yet.
version: 1.0.0
---

# Set up a reasonable .gitignore

A new repo needs its `.gitignore` in place before the first real commit —
not a generic "ignore everything under the sun" template, and not one
missing the basics either.

## 1. Detect the actual stack(s)

Look for what's really there before writing anything:

- `package.json`/lockfile → Node/JS/TS
- `requirements.txt`/`pyproject.toml` → Python
- `Cargo.toml` → Rust
- `go.mod` → Go
- `*.xcodeproj`/`Podfile` → iOS/Xcode
- `build.gradle`/`build.gradle.kts` → Android
- Expo (`app.json`/`expo` in `package.json`) → adds `.expo/`, `ios/`,
  `android/` (if using the prebuild/CNG workflow — check whether native
  folders are meant to be committed or regenerated), `expo-env.d.ts`

If the repo is empty (no manifest yet), ask what the project will be built
with instead of guessing.

## 2. Write only the sections that apply

Include the real ignore patterns for each detected/declared stack
(dependency directories, build output, language-specific caches) — nothing
more. Don't paste a multi-stack "kitchen sink" template: a pure Node project
gaining VisualStudio/.NET/NuGet ignore rules it will never trigger is noise,
not safety, and works against Simplicity First.

## 3. Always include, regardless of stack

- **OS cruft:** `.DS_Store`, `Thumbs.db`, `desktop.ini`
- **Secrets:** `.env`, `.env.local`, `.env.*.local`, and any key/credential
  file patterns relevant to the stack (`*.pem`, `*.key`, `*.p12`,
  `*.mobileprovision`, service-account JSON files, etc.)
- **Editor directories**, but only blanket-ignored if the project isn't
  sharing editor config. If it does share some (e.g. a committed
  `.vscode/settings.json`), ignore the directory and allow-list the specific
  shared files rather than ignoring everything.

## 4. Respect an existing split, don't force one file

If the project already separates concerns (e.g. a root `.gitignore` for
repo-wide cruft plus a nested app directory with its own, like this
project's `app/.gitignore` for Expo-specific patterns), keep that split —
add the new stack's block to whichever file actually owns that scope,
instead of collapsing everything into one root file.

## 5. Adding a stack later (not a fresh repo)

Extend the existing `.gitignore`, don't replace it. After adding new
patterns, check whether anything already committed now matches them
(`git ls-files | grep <pattern>`). A newly added rule does **not** untrack
already-committed files — if something matches, tell the user; removing it
from tracking (`git rm --cached`) is a separate, deliberate action that
needs their confirmation, not something to do automatically.

## 6. Commit

Its own commit, before other work starts on the repo — follow whatever
commit convention applies (Conventional Commits by default, or the
project's documented exception; see `CLAUDE.md`).
