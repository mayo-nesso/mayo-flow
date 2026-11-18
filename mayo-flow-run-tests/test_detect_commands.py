import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "detect_commands.py")


def run_in(tmp, files=None, dirs=()):
    for name, content in (files or {}).items():
        with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
            f.write(content)
    for d in dirs:
        os.mkdir(os.path.join(tmp, d))
    proc = subprocess.run([sys.executable, "-I", SCRIPT_PATH, tmp], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def detect(files=None, dirs=()):
    """Create a temp project, run the script, return parsed JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        return run_in(tmp, files, dirs)


def pkg(scripts):
    return {"package.json": json.dumps({"scripts": scripts})}


def cmds(result):
    return [(c["step"], c["cmd"]) for c in result["commands"]]


class NodeTests(unittest.TestCase):
    def test_all_three_scripts_in_order(self):
        r = detect(pkg({"test": "x", "lint": "x", "typecheck": "x"}))
        self.assertEqual(r["stacks"], ["node"])
        self.assertEqual(
            cmds(r),
            [
                ("typecheck", "npm run typecheck"),
                ("lint", "npm run lint"),
                ("test", "npm run test"),
            ],
        )
        self.assertTrue(all(c["stack"] == "node" for c in r["commands"]))

    def test_dir_is_absolute_input_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_in(tmp, {"package.json": "{}"})
            self.assertEqual(r["dir"], os.path.abspath(tmp))

    def test_missing_keys_are_skipped_not_substituted(self):
        r = detect(pkg({"test": "x", "build": "x", "tsc": "x"}))
        self.assertEqual(cmds(r), [("test", "npm run test")])

    def test_no_scripts_section(self):
        r = detect({"package.json": "{}"})
        self.assertEqual((r["stacks"], r["commands"]), (["node"], []))

    def test_invalid_json(self):
        r = detect({"package.json": "{not json"})
        self.assertEqual(r["stacks"], ["node"])
        self.assertEqual(r["commands"], [])
        self.assertTrue(r["error"])

    def test_non_object_scripts_means_no_scripts(self):
        for bad in ("null", "[]", '"x"', "3"):
            with self.subTest(scripts=bad):
                r = detect({"package.json": '{"scripts": %s}' % bad})
                self.assertEqual((r["stacks"], r["commands"]), (["node"], []))
                self.assertNotIn("error", r)

    def test_non_object_package_json_is_invalid(self):
        r = detect({"package.json": "[]"})
        self.assertEqual(r["stacks"], ["node"])
        self.assertTrue(r["error"])

    def test_utf8_bom_parses(self):
        r = detect({"package.json": "﻿" + json.dumps({"scripts": {"test": "x"}})})
        self.assertNotIn("error", r)
        self.assertEqual(cmds(r), [("test", "npm run test")])


class PackageManagerTests(unittest.TestCase):
    def pm_cmds(self, lockfiles):
        files = pkg({"lint": "x", "test": "x"})
        files.update({name: "" for name in lockfiles})
        return cmds(detect(files))

    def test_pnpm(self):
        self.assertEqual(
            self.pm_cmds(["pnpm-lock.yaml"]), [("lint", "pnpm run lint"), ("test", "pnpm run test")]
        )

    def test_yarn(self):
        self.assertEqual(
            self.pm_cmds(["yarn.lock"]), [("lint", "yarn run lint"), ("test", "yarn run test")]
        )

    def test_bun_both_lockfiles(self):
        for lock in ("bun.lock", "bun.lockb"):
            with self.subTest(lock=lock):
                self.assertEqual(
                    self.pm_cmds([lock]), [("lint", "bun run lint"), ("test", "bun run test")]
                )

    def test_priority_pnpm_yarn_bun_npm(self):
        self.assertEqual(self.pm_cmds(["bun.lock", "yarn.lock", "pnpm-lock.yaml"])[0][1], "pnpm run lint")
        self.assertEqual(self.pm_cmds(["bun.lock", "yarn.lock"])[0][1], "yarn run lint")
        self.assertEqual(self.pm_cmds(["package-lock.json"])[0][1], "npm run lint")


class MixedStackTests(unittest.TestCase):
    def test_node_and_python_both_detected_ordered_by_step(self):
        files = pkg({"lint": "x", "test": "x"})
        files.update({"pyproject.toml": "[tool.mypy]\n[tool.pytest.ini_options]\n"})
        r = detect(files)
        self.assertEqual(r["stacks"], ["node", "python"])
        self.assertEqual(
            [(c["step"], c["stack"], c["cmd"]) for c in r["commands"]],
            [
                ("typecheck", "python", "mypy ."),
                ("lint", "node", "npm run lint"),
                ("test", "node", "npm run test"),
                ("test", "python", "pytest"),
            ],
        )

    def test_invalid_package_json_still_checks_python(self):
        r = detect({"package.json": "{bad", "pytest.ini": ""})
        self.assertEqual(r["stacks"], ["node", "python"])
        self.assertTrue(r["error"])
        self.assertEqual(cmds(r), [("test", "pytest")])


class PythonTests(unittest.TestCase):
    def test_marker_without_config_emits_nothing(self):
        r = detect({"requirements.txt": "requests\n"})
        self.assertEqual((r["stacks"], r["commands"]), (["python"], []))

    def test_full_toolchain_in_order(self):
        r = detect({"requirements.txt": "", "mypy.ini": "", "ruff.toml": "", "pytest.ini": ""})
        self.assertEqual(
            cmds(r), [("typecheck", "mypy ."), ("lint", "ruff check ."), ("test", "pytest")]
        )
        self.assertTrue(all(c["stack"] == "python" for c in r["commands"]))

    def test_mypy_from_pyproject_section(self):
        r = detect({"pyproject.toml": "[tool.mypy]\nstrict = true\n"})
        self.assertEqual(cmds(r), [("typecheck", "mypy .")])

    def test_mypy_from_overrides_only(self):
        r = detect({"pyproject.toml": '[[tool.mypy.overrides]]\nmodule = "x"\nignore_errors = true\n'})
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

    def test_ruff_from_lint_subtable_only(self):
        r = detect({"pyproject.toml": '[tool.ruff.lint]\nselect = ["E"]\n'})
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
        self.assertEqual(r["stacks"], ["python"])
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

    def test_pytest_from_test_directory(self):
        r = detect({"requirements.txt": ""}, dirs=["test"])
        self.assertEqual(cmds(r), [("test", "pytest")])

    def test_commented_header_in_unparsable_pyproject_not_counted(self):
        # Invalid TOML forces the substring fallback.
        r = detect({"pyproject.toml": "# [tool.mypy]\n= broken\n"})
        self.assertEqual(cmds(r), [])

    def test_real_header_in_unparsable_pyproject_still_counted(self):
        r = detect({"pyproject.toml": "  [tool.mypy]\n= broken\n"})
        self.assertEqual(cmds(r), [("typecheck", "mypy .")])

    def test_commented_header_in_ini_files_not_counted(self):
        r = detect({"setup.cfg": "# [mypy]\n; [tool:pytest]\n", "tox.ini": "# [flake8]\n"})
        self.assertEqual(cmds(r), [])


class OtherTests(unittest.TestCase):
    def test_unknown_stack(self):
        r = detect({"README.md": "hi"})
        self.assertEqual((r["stacks"], r["commands"]), ([], []))

    def test_tests_dir_alone_is_not_python(self):
        r = detect(dirs=["tests"])
        self.assertEqual((r["stacks"], r["commands"]), ([], []))

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
        self.assertEqual(
            json.loads(proc.stdout)["commands"],
            [{"step": "lint", "stack": "node", "cmd": "npm run lint"}],
        )


if __name__ == "__main__":
    unittest.main()
