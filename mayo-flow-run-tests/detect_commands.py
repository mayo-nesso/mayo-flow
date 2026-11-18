#!/usr/bin/env python3
"""Detect a project's verification commands. Prints one JSON object; never runs anything."""
import json
import os
import sys


def read(root, name):
    try:
        with open(os.path.join(root, name), encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def has(root, name):
    return os.path.exists(os.path.join(root, name))


def has_section(root, files_and_headers):
    return any(header in read(root, name) for name, header in files_and_headers)


def detect_node(root):
    result = {"stack": "node", "commands": []}
    try:
        scripts = json.loads(read(root, "package.json")).get("scripts", {})
    except (ValueError, AttributeError) as e:
        result["error"] = "invalid package.json: %s" % e
        return result
    for step in ("typecheck", "lint", "test"):
        if step in scripts:
            cmd = "npm test" if step == "test" else "npm run " + step
            result["commands"].append({"step": step, "cmd": cmd})
    return result


def detect_python(root):
    if has(root, "mypy.ini") or has_section(
        root, [("pyproject.toml", "[tool.mypy]"), ("setup.cfg", "[mypy]")]
    ):
        typecheck = "mypy ."
    elif has(root, "pyrightconfig.json") or has_section(root, [("pyproject.toml", "[tool.pyright]")]):
        typecheck = "pyright"
    else:
        typecheck = None

    if has(root, "ruff.toml") or has(root, ".ruff.toml") or has_section(
        root, [("pyproject.toml", "[tool.ruff]")]
    ):
        lint = "ruff check ."
    elif has(root, ".flake8") or has_section(root, [("setup.cfg", "[flake8]"), ("tox.ini", "[flake8]")]):
        lint = "flake8"
    else:
        lint = None

    if (
        has(root, "pytest.ini")
        or os.path.isdir(os.path.join(root, "tests"))
        or has_section(
            root,
            [("pyproject.toml", "[tool.pytest.ini_options]"), ("setup.cfg", "[tool:pytest]")],
        )
    ):
        test = "pytest"
    else:
        test = None

    steps = [("typecheck", typecheck), ("lint", lint), ("test", test)]
    return {
        "stack": "python",
        "commands": [{"step": s, "cmd": c} for s, c in steps if c],
    }


def detect(root):
    if has(root, "package.json"):
        return detect_node(root)
    if any(has(root, m) for m in ("pyproject.toml", "requirements.txt", "setup.cfg", "pytest.ini")):
        return detect_python(root)
    return {"stack": "unknown", "commands": []}


def main(argv):
    root = argv[1] if len(argv) > 1 else os.getcwd()
    if not os.path.isdir(root):
        print("detect_commands: not a readable directory: %s" % root, file=sys.stderr)
        return 1
    print(json.dumps(detect(root)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
