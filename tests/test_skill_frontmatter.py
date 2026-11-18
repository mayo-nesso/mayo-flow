"""Frontmatter sanity checks for every */SKILL.md (stdlib only, no YAML parser)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = sorted(ROOT.glob("*/SKILL.md"))
SPECIAL_START = "\"'[{&*!|>%@`"


def read_frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    return text[4:end].splitlines()


def field(lines, key):
    for line in lines:
        m = re.match(rf"^{key}:\s*(.*)$", line)
        if m:
            return m.group(1).strip()
    return None


class SkillFrontmatterTest(unittest.TestCase):
    def test_skills_found(self):
        self.assertTrue(SKILLS)

    def test_each_skill(self):
        for path in SKILLS:
            folder = path.parent.name
            with self.subTest(skill=folder):
                lines = read_frontmatter(path)
                self.assertIsNotNone(lines, "missing or unclosed frontmatter")
                self.assertEqual(field(lines, "name"), folder)
                desc = field(lines, "description")
                self.assertTrue(desc, "empty or missing description")
                if desc[0] == '"':
                    self.assertTrue(len(desc) >= 2 and desc.endswith('"'),
                                    "unclosed double quote")
                    inner = desc[1:-1]
                    self.assertIsNone(re.search(r'(?<!\\)"', inner),
                                      "unescaped inner double quote")
                elif desc[0] == "'":
                    self.assertTrue(len(desc) >= 2 and desc.endswith("'"),
                                    "unclosed single quote")
                else:
                    self.assertNotIn(desc[0], SPECIAL_START,
                                     "starts with a YAML special char")
                    self.assertNotIn(": ", desc, "plain scalar contains ': '")
                    self.assertNotIn(" #", desc, "plain scalar contains ' #'")


if __name__ == "__main__":
    unittest.main()
