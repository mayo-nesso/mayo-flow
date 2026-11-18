#!/usr/bin/env python3
"""Detect a project's verification commands. Prints one JSON object; never runs anything."""
import json
import os
import re
import sys

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

STEPS = ("typecheck", "lint", "test")
LOCKFILES = (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lock", "bun"), ("bun.lockb", "bun"))


def read(root, name, encoding="utf-8"):
    try:
        with open(os.path.join(root, name), encoding=encoding, errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def has(root, name):
    return os.path.exists(os.path.join(root, name))


def has_section(root, files_and_headers):
    """True if any file has the header at the start of a line (comments do not count)."""
    return any(
        re.search(r"^\s*" + re.escape(header), read(root, name), re.MULTILINE)
        for name, header in files_and_headers
    )


def pyproject_tool(root):
    """The [tool] table of pyproject.toml, or None if tomllib is missing or the file does not parse."""
    if tomllib is None:
        return None
    try:
        tool = tomllib.loads(read(root, "pyproject.toml")).get("tool", {})
    except tomllib.TOMLDecodeError:
        return None
    return tool if isinstance(tool, dict) else {}


def detect_node(root):
    pm = next((name for lock, name in LOCKFILES if has(root, lock)), "npm")
    result = {"commands": []}
    try:
        data = json.loads(read(root, "package.json", "utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("top level is not an object")
    except ValueError as e:
        result["error"] = "invalid package.json: %s" % e
        return result
    scripts = data.get("scripts")
    if isinstance(scripts, dict):
        result["commands"] = [{"step": s, "cmd": "%s run %s" % (pm, s)} for s in STEPS if s in scripts]
    return result


def detect_python(root):
    tool = pyproject_tool(root)

    def configured(name, header):
        if tool is not None:
            return name in tool
        return has_section(root, [("pyproject.toml", header)])

    if has(root, "mypy.ini") or configured("mypy", "[tool.mypy") or has_section(root, [("setup.cfg", "[mypy]")]):
        typecheck = "mypy ."
    elif has(root, "pyrightconfig.json") or configured("pyright", "[tool.pyright]"):
        typecheck = "pyright"
    else:
        typecheck = None

    if has(root, "ruff.toml") or has(root, ".ruff.toml") or configured("ruff", "[tool.ruff"):
        lint = "ruff check ."
    elif has(root, ".flake8") or has_section(root, [("setup.cfg", "[flake8]"), ("tox.ini", "[flake8]")]):
        lint = "flake8"
    else:
        lint = None

    pytest_toml = tool is not None and "ini_options" in tool.get("pytest", {})
    if (
        has(root, "pytest.ini")
        or os.path.isdir(os.path.join(root, "tests"))
        or os.path.isdir(os.path.join(root, "test"))
        or pytest_toml
        or (tool is None and has_section(root, [("pyproject.toml", "[tool.pytest.ini_options]")]))
        or has_section(root, [("setup.cfg", "[tool:pytest]")])
    ):
        test = "pytest"
    else:
        test = None

    found = dict(zip(STEPS, (typecheck, lint, test)))
    return {"commands": [{"step": s, "cmd": c} for s, c in found.items() if c]}


def detect(root):
    root = os.path.abspath(root)
    stacks, results = [], []
    if has(root, "package.json"):
        stacks.append("node")
        results.append(detect_node(root))
    if any(has(root, m) for m in ("pyproject.toml", "requirements.txt", "setup.cfg", "pytest.ini")):
        stacks.append("python")
        results.append(detect_python(root))
    out = {"dir": root, "stacks": stacks}
    commands = [dict(c, stack=st) for st, r in zip(stacks, results) for c in r["commands"]]
    out["commands"] = [
        {"step": c["step"], "stack": c["stack"], "cmd": c["cmd"]}
        for step in STEPS
        for c in commands
        if c["step"] == step
    ]
    for r in results:
        if "error" in r:
            out["error"] = r["error"]
    return out


def main(argv):
    root = argv[1] if len(argv) > 1 else os.getcwd()
    if not os.path.isdir(root):
        print("detect_commands: not a readable directory: %s" % root, file=sys.stderr)
        return 1
    print(json.dumps(detect(root)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
