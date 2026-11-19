"""Artifact snapshot tests over hand-built git repos (stdlib only)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import snapshot  # noqa: E402


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t",
                           "-c", "user.email=t@example.com", *args],
                          check=True, capture_output=True,
                          text=True).stdout.strip()


def write(repo, rel, data="x\n"):
    p = Path(repo) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        p.write_bytes(data)
    else:
        p.write_text(data)


class SnapshotTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.repo = Path(t.name)
        git(self.repo, "init", "-b", "main")
        write(self.repo, "app.py", "print(1)\n")
        write(self.repo, "same.txt", "unchanged\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "chore: fixture")
        self.base = git(self.repo, "rev-parse", "HEAD")

    def snap(self, **kw):
        return snapshot.take_snapshot(self.repo, self.base, prompt="do it",
                                      result_text="done", **kw)

    def test_keeps_new_and_changed_text_files_only(self):
        git(self.repo, "checkout", "-b", "feature/x")
        write(self.repo, "app.py", "print(2)\n")
        write(self.repo, "docs/spec.md", "# Spec\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "docs: add spec")
        write(self.repo, "notes.md", "untracked\n")
        s = self.snap()
        self.assertEqual(s["files"], {"app.py": "print(2)\n",
                                      "docs/spec.md": "# Spec\n",
                                      "notes.md": "untracked\n"})

    def test_keeps_ignored_files(self):
        write(self.repo, ".git/info/exclude", ".claude/handoff.md\n")
        write(self.repo, ".claude/handoff.md", "# Handoff\n")
        self.assertEqual(self.snap()["files"],
                         {".claude/handoff.md": "# Handoff\n"})

    def test_skips_binary_and_deleted_files(self):
        write(self.repo, "img.bin", b"\x00\x01\x02")
        (self.repo / "same.txt").unlink()
        self.assertEqual(self.snap()["files"], {})

    def test_records_prompt_result_branch_and_commits(self):
        git(self.repo, "checkout", "-b", "fix/y")
        write(self.repo, "a.md", "a\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "docs: add a")
        s = self.snap()
        self.assertEqual(s["prompt"], "do it")
        self.assertEqual(s["result_text"], "done")
        self.assertEqual(s["branch"], "fix/y")
        self.assertEqual(s["commits"], ["docs: add a"])

    def test_caps_each_file_and_the_total(self):
        write(self.repo, "a.txt", "a" * 50)
        write(self.repo, "b.txt", "b" * 50)
        write(self.repo, "c.txt", "c" * 50)
        s = self.snap(max_file=30, max_total=70)
        self.assertEqual(s["files"]["a.txt"], "a" * 30)
        self.assertEqual(s["files"]["b.txt"], "b" * 30)
        self.assertNotIn("c.txt", s["files"])
        self.assertEqual(s["truncated"], ["a.txt", "b.txt"])
        self.assertEqual(s["omitted"], ["c.txt"])

    def test_write_and_path_beside_the_trace(self):
        trace = self.repo / "traces" / "c1-20261119T000000Z-1.jsonl"
        trace.parent.mkdir()
        path = snapshot.snapshot_path(trace)
        self.assertEqual(path, trace.with_name(
            "c1-20261119T000000Z-1.snapshot.json"))
        snapshot.write_snapshot(path, self.snap())
        self.assertEqual(json.loads(path.read_text())["prompt"], "do it")


if __name__ == "__main__":
    unittest.main()
