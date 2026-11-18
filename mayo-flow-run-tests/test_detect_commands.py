import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "detect_commands.py")


def detect(files=None, dirs=()):
    """Create a temp project, run the script, return parsed JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        for name, content in (files or {}).items():
            with open(os.path.join(tmp, name), "w") as f:
                f.write(content)
        for d in dirs:
            os.mkdir(os.path.join(tmp, d))
        proc = subprocess.run(
            [sys.executable, "-I", SCRIPT_PATH, tmp], capture_output=True, text=True
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)


def pkg(scripts):
    return {"package.json": json.dumps({"scripts": scripts})}


def cmds(result):
    return [(c["step"], c["cmd"]) for c in result["commands"]]


class NodeTests(unittest.TestCase):
    def test_all_three_scripts_in_order(self):
        r = detect(pkg({"test": "x", "lint": "x", "typecheck": "x"}))
        self.assertEqual(r["stack"], "node")
        self.assertEqual(
            cmds(r),
            [("typecheck", "npm run typecheck"), ("lint", "npm run lint"), ("test", "npm test")],
        )

    def test_missing_keys_are_skipped_not_substituted(self):
        r = detect(pkg({"test": "x", "build": "x", "tsc": "x"}))
        self.assertEqual(cmds(r), [("test", "npm test")])

    def test_no_scripts_section(self):
        r = detect({"package.json": "{}"})
        self.assertEqual(r, {"stack": "node", "commands": []})

    def test_invalid_json(self):
        r = detect({"package.json": "{not json"})
        self.assertEqual(r["stack"], "node")
        self.assertEqual(r["commands"], [])
        self.assertTrue(r["error"])

    def test_node_wins_over_python(self):
        files = pkg({"test": "x"})
        files["pyproject.toml"] = "[tool.pytest.ini_options]\n"
        r = detect(files)
        self.assertEqual(r["stack"], "node")
        self.assertEqual(cmds(r), [("test", "npm test")])


class PythonTests(unittest.TestCase):
    def test_marker_without_config_emits_nothing(self):
        r = detect({"requirements.txt": "requests\n"})
        self.assertEqual(r, {"stack": "python", "commands": []})

    def test_full_toolchain_in_order(self):
        r = detect({"requirements.txt": "", "mypy.ini": "", "ruff.toml": "", "pytest.ini": ""})
        self.assertEqual(
            cmds(r), [("typecheck", "mypy ."), ("lint", "ruff check ."), ("test", "pytest")]
        )

    def test_mypy_from_pyproject_section(self):
        r = detect({"pyproject.toml": "[tool.mypy]\nstrict = true\n"})
        self.assertEqual(cmds(r), [("typecheck", "mypy .")])

    def test_mypy_from_setup_cfg_section(self):
        r = detect({"setup.cfg": "[mypy]\nstrict = True\n"})
        self.assertEqual(cmds(r), [("typecheck", "mypy .")])

    def test_pyright_when_no_mypy(self):
        r = detect({"requirements.txt": "", "pyrightconfig.json": "{}"})
        self.assertEqual(cmds(r), [("typecheck", "pyright")])

    def test_pyright_from_pyproject_section(self):
        r = detect({"pyproject.toml": "[tool.pyright]\n"})
        self.assertEqual(cmds(r), [("typecheck", "pyright")])

    def test_mypy_preferred_over_pyright(self):
        r = detect({"requirements.txt": "", "mypy.ini": "", "pyrightconfig.json": "{}"})
        self.assertEqual(cmds(r), [("typecheck", "mypy .")])

    def test_ruff_from_dotfile(self):
        r = detect({"requirements.txt": "", ".ruff.toml": ""})
        self.assertEqual(cmds(r), [("lint", "ruff check .")])

    def test_ruff_from_pyproject_section(self):
        r = detect({"pyproject.toml": "[tool.ruff]\nline-length = 100\n"})
        self.assertEqual(cmds(r), [("lint", "ruff check .")])

    def test_flake8_from_dotfile(self):
        r = detect({"requirements.txt": "", ".flake8": ""})
        self.assertEqual(cmds(r), [("lint", "flake8")])

    def test_flake8_from_tox_ini_section(self):
        r = detect({"requirements.txt": "", "tox.ini": "[flake8]\nmax-line-length = 100\n"})
        self.assertEqual(cmds(r), [("lint", "flake8")])

    def test_ruff_preferred_over_flake8(self):
        r = detect({"requirements.txt": "", "ruff.toml": "", ".flake8": ""})
        self.assertEqual(cmds(r), [("lint", "ruff check .")])

    def test_pytest_from_pytest_ini(self):
        r = detect({"pytest.ini": ""})
        self.assertEqual(r["stack"], "python")
        self.assertEqual(cmds(r), [("test", "pytest")])

    def test_pytest_from_pyproject_section(self):
        r = detect({"pyproject.toml": "[tool.pytest.ini_options]\n"})
        self.assertEqual(cmds(r), [("test", "pytest")])

    def test_pytest_from_setup_cfg_section(self):
        r = detect({"setup.cfg": "[tool:pytest]\n"})
        self.assertEqual(cmds(r), [("test", "pytest")])

    def test_pytest_from_tests_directory(self):
        r = detect({"requirements.txt": ""}, dirs=["tests"])
        self.assertEqual(cmds(r), [("test", "pytest")])


class OtherTests(unittest.TestCase):
    def test_unknown_stack(self):
        self.assertEqual(detect({"README.md": "hi"}), {"stack": "unknown", "commands": []})

    def test_tests_dir_alone_is_not_python(self):
        self.assertEqual(detect(dirs=["tests"]), {"stack": "unknown", "commands": []})

    def test_missing_dir_exits_nonzero(self):
        proc = subprocess.run(
            [sys.executable, "-I", SCRIPT_PATH, "/nonexistent/dir/xyz"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertTrue(proc.stderr.strip())

    def test_defaults_to_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "package.json"), "w") as f:
                f.write(json.dumps({"scripts": {"lint": "x"}}))
            proc = subprocess.run(
                [sys.executable, "-I", SCRIPT_PATH], capture_output=True, text=True, cwd=tmp
            )
        self.assertEqual(json.loads(proc.stdout)["commands"], [{"step": "lint", "cmd": "npm run lint"}])


if __name__ == "__main__":
    unittest.main()
