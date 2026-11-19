"""PermissionRequest hook: allow Write/Edit of the paths a suite names.

Usage (as a command hook): python3 allow_writes_hook.py <path> [<path>...],
paths relative to the session cwd, hook input JSON on stdin.

Claude Code treats `.claude/` (and `.git/`, ...) as protected paths: in
acceptEdits mode a Write there still prompts, allow rules in settings or
--allowed-tools do not pre-approve it, and `claude -p` denies the prompt.
A PermissionRequest hook runs in -p mode too and may answer that prompt.
This one answers "allow" only for a Write or Edit whose resolved path is one
of the named paths; for anything else it prints nothing, so Claude Code
denies the call as before and records it in permission_denials.
"""
import json
import os
import sys

WRITE_TOOLS = ("Write", "Edit")


def decide(event, allowed):
    """The hook output for `event`, or None to leave the request alone."""
    if event.get("tool_name") not in WRITE_TOOLS:
        return None
    cwd = event.get("cwd")
    path = (event.get("tool_input") or {}).get("file_path")
    if not isinstance(cwd, str) or not isinstance(path, str):
        return None
    target = os.path.realpath(os.path.join(cwd, path))
    if target not in {os.path.realpath(os.path.join(cwd, a)) for a in allowed}:
        return None
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                   "decision": {"behavior": "allow"}}}


def main():
    out = decide(json.load(sys.stdin), sys.argv[1:])
    if out is not None:
        print(json.dumps(out))


if __name__ == "__main__":
    main()
