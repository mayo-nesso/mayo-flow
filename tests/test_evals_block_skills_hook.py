"""The PreToolUse hook that keeps a plain (no-skill) run out of ~/.claude/skills."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import block_skills_hook  # noqa: E402


def ev(tool, **tool_input):
    return {"hook_event_name": "PreToolUse", "cwd": "/tmp",
            "tool_name": tool, "tool_input": tool_input}


def denied(out):
    return (out is not None and out["hookSpecificOutput"]
            ["permissionDecision"] == "deny")


class DecideTest(unittest.TestCase):
    def test_denies_every_way_of_naming_the_skills_dir(self):
        for e in (
            ev("Bash", command="cat ~/.claude/skills/mayo-flow-x/SKILL.md"),
            ev("Bash", command="ls /Users/m/.claude/skills"),
            ev("Bash", command="grep -r foo $HOME/.claude/skills/"),
            ev("Read", file_path="/Users/m/.claude/skills/x/SKILL.md"),
            ev("Glob", pattern="*/SKILL.md", path="/Users/m/.claude/skills"),
            ev("Grep", pattern="x", path="~/.claude/skills"),
            ev("Glob", pattern="/Users/m/.claude/skills/**"),
        ):
            self.assertTrue(denied(block_skills_hook.decide(e)), e)

    def test_reason_tells_the_model_why(self):
        out = block_skills_hook.decide(ev("Bash", command="ls ~/.claude/skills"))
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("skills", reason)

    def test_leaves_other_calls_alone(self):
        for e in (
            ev("Bash", command="git status"),
            ev("Bash", command="ls ~/.claude"),
            ev("Read", file_path="/tmp/repo/README.md"),
            ev("Grep", pattern="skills", path="/tmp/repo"),
            {"tool_name": "Bash"},
        ):
            self.assertIsNone(block_skills_hook.decide(e), e)


if __name__ == "__main__":
    unittest.main()
