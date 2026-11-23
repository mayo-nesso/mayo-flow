"""PermissionRequest hook: allow Write/Edit/rm of the paths a suite names.

Usage (as a command hook): python3 allow_writes_hook.py <path> [<path>...],
paths relative to the session cwd, hook input JSON on stdin.

Claude Code treats `.claude/` (and `.git/`, ...) as protected paths: in
acceptEdits mode a Write there still prompts, allow rules in settings or
--allowed-tools do not pre-approve it, and `claude -p` denies the prompt.
A PermissionRequest hook runs in -p mode too and may answer that prompt.
This one answers "allow" only for a Write or Edit whose resolved path is one
of the named paths, or a Bash command whose `rm` segments remove only those; for anything else it prints nothing, so Claude Code
denies the call as before and records it in permission_denials.
"""
import json
import os
import re
import shlex
import sys

WRITE_TOOLS = ("Write", "Edit")
SEGMENT_SPLIT = re.compile(r"&&|\|\||[;|\n]")


def _rm_targets(command):
    """Targets of every `rm` segment in a shell command, or None when a
    segment cannot be parsed. [] means the command removes nothing."""
    targets = []
    for segment in SEGMENT_SPLIT.split(command):
        try:
            words = shlex.split(segment)
        except ValueError:
            return None
        if words[:1] == ["rm"]:
            targets += [w for w in words[1:] if not w.startswith("-")]
    return targets


def decide(event, allowed):
    """The hook output for `event`, or None to leave the request alone.

    A Write/Edit of a named path is allowed, and so is a Bash command that
    removes only named paths (the handoff skill deletes its file on resume).
    """
    cwd = event.get("cwd")
    tool_input = event.get("tool_input") or {}
    if not isinstance(cwd, str):
        return None
    named = {os.path.realpath(os.path.join(cwd, a)) for a in allowed}
    if event.get("tool_name") in WRITE_TOOLS:
        path = tool_input.get("file_path")
        targets = [path] if isinstance(path, str) else []
    elif event.get("tool_name") == "Bash":
        command = tool_input.get("command")
        targets = _rm_targets(command) if isinstance(command, str) else None
    else:
        return None
    if not targets or not all(
            os.path.realpath(os.path.join(cwd, t)) in named for t in targets):
        return None
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                   "decision": {"behavior": "allow"}}}


def main():
    out = decide(json.load(sys.stdin), sys.argv[1:])
    if out is not None:
        print(json.dumps(out))


if __name__ == "__main__":
    main()
