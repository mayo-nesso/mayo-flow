"""The PermissionRequest hook that lets a suite's named paths be written."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import allow_writes_hook  # noqa: E402

ALLOWED = [".claude/handoff.md"]


def event(tool, cwd, **tool_input):
    return {"hook_event_name": "PermissionRequest", "cwd": str(cwd),
            "tool_name": tool, "tool_input": tool_input}


class DecideTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.cwd = Path(t.name)

    def decide(self, tool, path):
        return allow_writes_hook.decide(
            event(tool, self.cwd, file_path=path), ALLOWED)

    def test_allows_write_and_edit_of_a_named_path(self):
        for tool in ("Write", "Edit"):
            for path in (str(self.cwd / ".claude/handoff.md"),
                         ".claude/handoff.md"):
                out = self.decide(tool, path)
                self.assertEqual(out["hookSpecificOutput"], {
                    "hookEventName": "PermissionRequest",
                    "decision": {"behavior": "allow"}}, (tool, path))

    def test_leaves_every_other_request_alone(self):
        for tool, path in [
                ("Write", str(self.cwd / ".claude/settings.json")),
                ("Write", str(self.cwd / "handoff.md")),
                ("Write", str(self.cwd / "sub/.claude/handoff.md")),
                ("Write", str(self.cwd / ".claude/x/../../.git/config")),
                ("Write", "/tmp/.claude/handoff.md"),
                ("Bash", str(self.cwd / ".claude/handoff.md")),
                ("NotebookEdit", str(self.cwd / ".claude/handoff.md"))]:
            self.assertIsNone(self.decide(tool, path), (tool, path))

    def bash(self, command):
        return allow_writes_hook.decide(
            event("Bash", self.cwd, command=command), ALLOWED)

    def test_allows_bash_that_removes_a_named_path(self):
        for command in (
                "rm .claude/handoff.md",
                "rm -f .claude/handoff.md",
                "git commit -q -m x && rm .claude/handoff.md && git log",
                "rm .claude/handoff.md; git diff | head -40",
                "rm " + str(self.cwd / ".claude/handoff.md")):
            self.assertEqual(
                self.bash(command)["hookSpecificOutput"]["decision"],
                {"behavior": "allow"}, command)

    def test_leaves_other_bash_alone(self):
        for command in (
                "cat .claude/handoff.md",
                "rm .claude/settings.json",
                "rm -rf .claude",
                "rm .claude/handoff.md .claude/settings.json",
                "rm .claude/handoff.md && rm .git/config",
                "echo x > .claude/handoff.md",
                "git status"):
            self.assertIsNone(self.bash(command), command)

    def test_resolves_dot_dot_before_matching(self):
        self.assertIsNotNone(
            self.decide("Write", str(self.cwd / "a/../.claude/handoff.md")))

    def test_malformed_events_are_left_alone(self):
        self.assertIsNone(allow_writes_hook.decide({}, ALLOWED))
        self.assertIsNone(allow_writes_hook.decide(
            {"tool_name": "Write", "cwd": str(self.cwd),
             "tool_input": {"file_path": 3}}, ALLOWED))

    def run_script(self, payload):
        return subprocess.run(
            [sys.executable, allow_writes_hook.__file__, *ALLOWED],
            input=json.dumps(payload), capture_output=True, text=True)

    def test_script_prints_the_decision_or_nothing(self):
        r = self.run_script(event("Write", self.cwd,
                                  file_path=".claude/handoff.md"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["hookSpecificOutput"]
                         ["decision"]["behavior"], "allow")
        r = self.run_script(event("Write", self.cwd, file_path="other.md"))
        self.assertEqual((r.returncode, r.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
