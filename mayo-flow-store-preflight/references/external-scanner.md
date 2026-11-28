# Optional external source scanner

<https://github.com/mjmirza/app-store-compliance> scans the project **source** for
rejection patterns. It complements this skill, which inspects the built artifact.
Third-party and not official.

## Offer, never run unasked

Offer it once per preflight, mainly worth it before a **first release**. Say all of:

- It is an external tool by a third party; running it executes their code on this
  machine with the user's permissions.
- License: OpenRoots Agent License 2.3, not MIT. The user checks that its terms fit
  them (royalty above a revenue threshold, AI training not granted).
- Findings are heuristics: some are noise, and a clear result is not an approval.

Run only after an explicit yes. A no does not count against the build.

## Run

Clone into a new empty directory in the scratchpad, pinned to the commit below:

```
git clone https://github.com/mjmirza/app-store-compliance <dir>
git -C <dir> checkout c6594f9f9e96c6fbc525242ba3f3fa4b7cc55395
bash <dir>/agent-os/hooks/app-store-compliance-guard.sh <project-dir>
```

- That commit (27 Nov 2026) was only partially read, not audited. Read the script
  before running it; do the same before moving the pin to a newer commit.
- The script also sources `~/.claude/hooks/hook-log.sh` if that file exists.
- Never run its `scripts/install.sh`: it writes to the AI tool's configuration and
  adds a hook and a skill that overlaps this one.
- Do not copy its text or data into the project or into this skill (license).

## Report

Exit 0: no critical finding in what it can see. Exit 2: blocked. Exit 1: not checked,
report as `unknown`. Confirm each finding in the code and against the official
Apple or Google page before calling it a `fail`. List these results apart from this
skill's own checks.

Its rules are a dated snapshot: quote the `Rule pack.` line from its output.
