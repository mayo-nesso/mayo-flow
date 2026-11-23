"""PreToolUse hook: deny any tool call that touches ~/.claude/skills.

Used for the plain conditions (baseline, casual, floor), which must run
without the skill. --disable-slash-commands only removes the slash command:
the model can still `cat ~/.claude/skills/<skill>/SKILL.md` and follow it by
hand, which makes the "baseline" a skill-read-by-hand run. This hook denies
Bash, Read, Glob and Grep calls whose input mentions `.claude/skills`; the
reason is returned to the model and the denied call stays in the trace.
Hook input JSON on stdin; prints nothing for calls it leaves alone.
"""
import json
import sys

SKILLS_DIR = ".claude/skills"
REASON = ("Access to the .claude/skills directory is blocked in this "
          "session. Work from the task and the repository only.")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def decide(event):
    """The hook output denying `event`, or None to leave the call alone."""
    if not any(SKILLS_DIR in s for s in _strings(event.get("tool_input"))):
        return None
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason": REASON}}


def main():
    out = decide(json.load(sys.stdin))
    if out is not None:
        print(json.dumps(out))


if __name__ == "__main__":
    main()
