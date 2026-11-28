"""Mutant skills of the delegate suite and the install helpers."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import mutant  # noqa: E402
from evals.checks import CHECKS  # noqa: E402

SUITE_DIR = ROOT / "evals" / "cases" / "delegate"
REAL = (ROOT / "mayo-flow-delegate" / "SKILL.md").read_text()
# mutant name -> (section number, "removed" or "replaced")
SECTIONS = {"no-models": (2, "removed"), "no-checklist": (3, "removed"),
            "no-parallel": (4, "removed"), "no-merge": (5, "removed"),
            "no-verify": (6, "removed"), "haiku-default": (2, "replaced")}


def sections(text):
    """{0: frontmatter and title, N: the text of section N}."""
    parts = re.split(r"(?m)^(?=## \d+\. )", text)
    return {0: parts[0],
            **{int(re.match(r"## (\d+)\.", p).group(1)): p for p in parts[1:]}}


def mutant_text(name):
    return (SUITE_DIR / "mutants" / name / "SKILL.md").read_text()


class MutantFilesTest(unittest.TestCase):
    def test_names_match_the_json_and_the_table(self):
        listed = json.loads((SUITE_DIR / "mutants.json").read_text())
        self.assertEqual(set(listed), set(SECTIONS))
        self.assertEqual(set(mutant.mutant_names(SUITE_DIR)), set(SECTIONS))

    def test_each_mutant_changes_only_its_section(self):
        real = sections(REAL)
        for name, (n, how) in SECTIONS.items():
            with self.subTest(mutant=name):
                got = sections(mutant_text(name))
                if how == "removed":
                    self.assertNotIn(n, got)
                else:
                    self.assertNotEqual(got[n], real[n])
                    self.assertIn("haiku", got[n])
                others = {k for k in real if k != n}
                self.assertEqual({k: v for k, v in got.items() if k != n},
                                 {k: real[k] for k in others if k in got})
                self.assertEqual(set(got) - {n}, others)

    def test_targets_are_real_checks_of_the_suite(self):
        suite = json.loads((SUITE_DIR / "suite.json").read_text())
        in_suite = {c for case in suite["cases"] for c in case["checks"]}
        for name, entry in json.loads(
                (SUITE_DIR / "mutants.json").read_text()).items():
            self.assertTrue(entry["targets"], name)
            for target in entry["targets"]:
                with self.subTest(mutant=name, target=target):
                    self.assertIn(target, CHECKS)
                    self.assertIn(target, in_suite)


class ModelClauseTest(unittest.TestCase):
    """The clause that makes the coordinator state the models. The check
    s2_model_stated reads visible text before each model's first launch."""

    def test_clause_is_visible_early_and_covers_every_agent(self):
        clause = re.search(r"(?ms)^- Model line:.*?(?=^\S|\Z)",
                           sections(REAL)[2])
        self.assertIsNotNone(clause, "section 2 needs the model clause")
        text = " ".join(clause.group().split())
        for phrase in ("`Models: <ticket or role> -> <model> (<reason>); ...`",
                       "starts with one line of visible text",
                       "before any tool call and before the Agent call",
                       "every agent", "review", "suite run",
                       "Thinking does not count",
                       "write a new `Models:` line before the Agent call "
                       "that first uses it",
                       "A project memory or the user's instruction wins"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


class InstallTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        tmp = Path(t.name)
        self.root = tmp / "repo"
        for name, extra in (("mayo-flow-a", "x.py"), ("mayo-flow-b", None),
                            ("other-skill", None)):
            d = self.root / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"real {name}\n")
            if extra:
                (d / extra).write_text("code\n")
        (self.root / "my-skill").mkdir()
        (self.root / "my-skill" / "SKILL.md").write_text("real my-skill\n")
        self.fixture = tmp / "fixture"
        self.fixture.mkdir()
        subprocess.run(["git", "init", "-q", str(self.fixture)], check=True)
        self.claude_md = tmp / "CLAUDE.md"
        self.claude_md.write_text("user rules\n")
        self.skill_md = tmp / "mutated.md"
        self.skill_md.write_text("mutated\n")

    def install(self, skill_md="default"):
        return mutant.install(
            self.fixture, self.root, "my-skill",
            self.skill_md if skill_md == "default" else skill_md,
            self.claude_md)

    def test_copies_mayo_flow_skills_and_the_suite_skill(self):
        self.install()
        skills = self.fixture / ".claude" / "skills"
        self.assertEqual(sorted(p.name for p in skills.iterdir()),
                         ["mayo-flow-a", "mayo-flow-b", "my-skill"])
        self.assertEqual((skills / "mayo-flow-a" / "x.py").read_text(),
                         "code\n")

    def test_replaces_skill_md_of_the_suite_skill_only(self):
        installed = self.install()
        skills = self.fixture / ".claude" / "skills"
        self.assertEqual(installed, skills / "my-skill")
        self.assertEqual((installed / "SKILL.md").read_text(), "mutated\n")
        self.assertEqual((skills / "mayo-flow-a" / "SKILL.md").read_text(),
                         "real mayo-flow-a\n")

    def test_control_keeps_the_real_skill_md(self):
        installed = self.install(skill_md=None)
        self.assertEqual((installed / "SKILL.md").read_text(),
                         "real my-skill\n")

    def test_copies_claude_md_and_keeps_git_status_clean(self):
        self.install()
        self.assertEqual((self.fixture / "CLAUDE.md").read_text(),
                         "user rules\n")
        status = subprocess.run(
            ["git", "-C", str(self.fixture), "status", "--porcelain",
             "--untracked-files=all"], capture_output=True, text=True).stdout
        self.assertEqual(status, "")

    def test_missing_claude_md_stops_with_a_clear_message(self):
        self.claude_md.unlink()
        with self.assertRaises(SystemExit) as cm:
            self.install()
        self.assertIn(str(self.claude_md), str(cm.exception))

    def test_install_claude_md_copies_the_file_only_and_hides_it(self):
        mutant.install_claude_md(self.fixture, self.claude_md)
        self.assertEqual((self.fixture / "CLAUDE.md").read_text(),
                         "user rules\n")
        self.assertFalse((self.fixture / ".claude").exists())
        status = subprocess.run(
            ["git", "-C", str(self.fixture), "status", "--porcelain",
             "--untracked-files=all"], capture_output=True, text=True).stdout
        self.assertEqual(status, "")

    def test_flag_loads_project_settings_only(self):
        self.assertEqual(mutant.SETTING_FLAGS, ("--setting-sources", "project"))

    def test_resolve(self):
        self.assertIsNone(mutant.resolve(SUITE_DIR, "control"))
        self.assertEqual(mutant.resolve(SUITE_DIR, "no-models"),
                         SUITE_DIR / "mutants" / "no-models" / "SKILL.md")
        with self.assertRaises(SystemExit) as cm:
            mutant.resolve(SUITE_DIR, "nope")
        self.assertIn("nope", str(cm.exception))
        with self.assertRaises(SystemExit):
            mutant.resolve(ROOT / "evals" / "cases" / "gitignore", "control")


class ScenarioTest(unittest.TestCase):
    """The CLAUDE.md scenarios in evals/claude-md/."""

    def test_scenario_resolves_a_known_name(self):
        self.assertEqual(mutant.scenario(ROOT / "evals", "owner"),
                         ROOT / "evals" / "claude-md" / "owner.md")
        self.assertTrue(mutant.scenario(ROOT / "evals", "bare").is_file())

    def test_unknown_scenario_stops_and_names_the_known_ones(self):
        with self.assertRaises(SystemExit) as cm:
            mutant.scenario(ROOT / "evals", "nope")
        msg = str(cm.exception)
        self.assertIn("nope", msg)
        self.assertIn("owner", msg)
        self.assertIn("bare", msg)

    def test_owner_keeps_the_general_rules_and_drops_the_personal_ones(self):
        text = (ROOT / "evals" / "claude-md" / "owner.md").read_text()
        self.assertTrue(text.splitlines()[0].startswith("Trimmed copy"))
        for kept in ("## 1. Think Before Coding", "## 2. Simplicity First",
                     "## 3. Surgical Changes", "## 4. Goal-Driven Execution",
                     "## 6. Writing Style for Files and Artifacts",
                     "If you write 200 lines and it could be 50, rewrite it."):
            with self.subTest(kept=kept):
                self.assertIn(kept, text)
        body = text.split("\n", 1)[1]  # the first line names what it removed
        for gone in ("mayo", "Unity", "@"):
            with self.subTest(gone=gone):
                self.assertNotIn(gone, body)
        self.assertNotIn("mayo", text)

    def test_only_the_delegate_suite_sets_a_scenario_and_it_is_owner(self):
        for path in sorted((ROOT / "evals" / "cases").glob("*/suite.json")):
            with self.subTest(suite=path.parent.name):
                got = json.loads(path.read_text()).get("claude_md")
                self.assertEqual(
                    got, "owner" if path.parent.name == "delegate" else None)

    def test_bare_is_almost_empty(self):
        text = (ROOT / "evals" / "claude-md" / "bare.md").read_text()
        self.assertLess(len(text), 40)
