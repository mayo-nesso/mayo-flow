"""Environment for every `claude -p` call the evals make (runner and judge).

Auto memory lives outside the fixture, in ~/.claude/projects/<cwd>/memory/,
so notes one call writes would reach later phases, trials and conditions.
CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 turns it off (checked in Claude Code
2.1.328: a truthy value forces auto memory off, over the autoMemoryEnabled
setting).
"""
import os

NO_AUTO_MEMORY = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}


def claude_env():
    return {**os.environ, **NO_AUTO_MEMORY}
