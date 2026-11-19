"""Skill-from-git-ref extraction tests (stdlib only)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import record  # noqa: E402
from evals.skillref import WORKING_TREE, extract_skill  # noqa: E402


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True)


class ExtractSkillTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp = Path(t.name)
        self.repo = self.tmp / "repo"
        skill = self.repo / "s"
        (skill / "sub").mkdir(parents=True)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@t")
        git(self.repo, "config", "user.name", "t")
        self.write("SKILL.md", "---\nname: s\nversion: 1.0.0\n---\nv1\n")
        self.write("sub/extra.md", "extra\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "v1")
        git(self.repo, "tag", "v1")
        self.write("SKILL.md", "---\nname: s\nversion: 2.0.0\n---\nv2\n")
        git(self.repo, "commit", "-qam", "v2")
        self.write("SKILL.md", "---\nname: s\nversion: 3.0.0\n---\nwip\n")

    def write(self, rel, text):
        (self.repo / "s" / rel).write_text(text)

    def test_extracts_the_skill_as_of_the_ref(self):
        out = extract_skill(self.repo, "s", "v1", self.tmp / "out")
        self.assertEqual(out, self.tmp / "out" / "s")
        self.assertEqual(record.skill_version(out), "1.0.0")
        self.assertEqual((out / "sub" / "extra.md").read_text(), "extra\n")

    def test_head_ignores_uncommitted_changes(self):
        out = extract_skill(self.repo, "s", "HEAD", self.tmp / "out")
        self.assertEqual(record.skill_version(out), "2.0.0")

    def test_working_tree_copies_current_files(self):
        out = extract_skill(self.repo, "s", WORKING_TREE, self.tmp / "out")
        self.assertEqual(record.skill_version(out), "3.0.0")

    def test_unknown_ref_or_skill_fails(self):
        with self.assertRaises(ValueError):
            extract_skill(self.repo, "s", "nope", self.tmp / "out")
        with self.assertRaises(ValueError):
            extract_skill(self.repo, "missing", "v1", self.tmp / "out2")


if __name__ == "__main__":
    unittest.main()
