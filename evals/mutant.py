"""Run a skill with one section changed (a mutant), in the fixture.

A project skill does not replace a personal skill of the same name, and
`--setting-sources project` hides the user skills and the user CLAUDE.md. So
a mutant run copies every mayo-flow skill and the user CLAUDE.md into the
fixture, and loads project settings only. `control` installs the skills
unchanged, so a mutant compares with a control run in the same mode.

A CLAUDE.md scenario (evals/claude-md/<name>.md) makes every run hermetic in
the same way. The scenario file replaces the user CLAUDE.md.
"""
import shutil
from pathlib import Path

SETTING_FLAGS = ("--setting-sources", "project")
EXCLUDE_LINES = (".claude/", "CLAUDE.md")
CONTROL = "control"
DEFAULT_CLAUDE_MD = Path.home() / ".claude" / "CLAUDE.md"
SCENARIO_DIR = "claude-md"
USER = "user"  # the claude_md label of a run that loads ~/.claude/


def scenario(evals_dir, name):
    """The CLAUDE.md file of scenario `name`. SystemExit when it is
    unknown."""
    root = Path(evals_dir) / SCENARIO_DIR
    path = root / f"{name}.md"
    if not path.is_file():
        names = sorted(p.stem for p in root.glob("*.md"))
        raise SystemExit(f"unknown CLAUDE.md scenario {name!r}: use one of "
                         f"{', '.join(names) or f'the files in {root}'}")
    return path


def mutant_names(suite_dir):
    """The names of the mutant folders of a suite, sorted."""
    root = Path(suite_dir) / "mutants"
    return sorted(d.name for d in root.iterdir() if d.is_dir()) \
        if root.is_dir() else []


def resolve(suite_dir, name):
    """The SKILL.md of mutant `name`, or None for `control`. SystemExit when
    the suite has no mutants or the name is unknown."""
    names = mutant_names(suite_dir)
    if not names:
        raise SystemExit(f"--mutant: {Path(suite_dir).name} has no mutants dir")
    if name == CONTROL:
        return None
    if name not in names:
        raise SystemExit(f"unknown mutant {name!r}: use {CONTROL} or one of "
                         f"{', '.join(names)}")
    return Path(suite_dir) / "mutants" / name / "SKILL.md"


def install(fixture, repo_root, skill, skill_md, claude_md):
    """Copy the skills and CLAUDE.md into the fixture, hide them from git and
    return the installed skill folder. `skill_md` replaces the SKILL.md of
    `skill`; None keeps it."""
    claude_md = Path(claude_md)
    if not claude_md.is_file():
        raise SystemExit(f"--mutant needs the user CLAUDE.md: {claude_md} "
                         f"is missing")
    fixture, repo_root = Path(fixture), Path(repo_root)
    skills = fixture / ".claude" / "skills"
    names = {skill, *(d.name for d in repo_root.glob("mayo-flow-*")
                      if (d / "SKILL.md").is_file())}
    for name in sorted(names):
        shutil.copytree(repo_root / name, skills / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if skill_md is not None:
        shutil.copyfile(skill_md, skills / skill / "SKILL.md")
    install_claude_md(fixture, claude_md)
    return skills / skill


def install_claude_md(fixture, claude_md):
    """Copy `claude_md` into the fixture as CLAUDE.md and hide it (and
    .claude/) from git."""
    fixture = Path(fixture)
    shutil.copyfile(claude_md, fixture / "CLAUDE.md")
    exclude = fixture / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with open(exclude, "a", encoding="utf-8") as f:
        f.write("".join(line + "\n" for line in EXCLUDE_LINES))
