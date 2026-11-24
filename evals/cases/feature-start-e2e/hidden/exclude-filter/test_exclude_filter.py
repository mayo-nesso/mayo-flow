"""Hidden acceptance tests for `list --exclude-tag`. Run by the eval with
cwd = the trial's repo; they drive the CLI in a subprocess only (never import
the package) on their own copy of a known data file."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

DATA = [
    {"name": "milk", "tags": ["dairy", "fridge"]},
    {"name": "rice", "tags": ["pantry"]},
    {"name": "yogurt", "tags": ["dairy", "fridge"]},
    {"name": "salt", "tags": ["pantry", "spice"]},
]


class ExcludeTagTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = os.path.join(tmp.name, "data.json")
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(DATA, f)

    def names(self, *args):
        """The names `list` prints (first field of each line); exit 0."""
        r = subprocess.run(
            [sys.executable, "-m", "listcli", "list", "--file", self.file,
             *args], cwd=os.getcwd(), capture_output=True, text=True,
            timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [line.split("\t")[0] for line in r.stdout.splitlines()
                if line.strip()]

    def test_one_excluded_tag(self):
        self.assertEqual(self.names("--exclude-tag", "dairy"),
                         ["rice", "salt"])

    def test_repeated_excluded_tags(self):
        self.assertEqual(self.names("--exclude-tag", "dairy",
                                    "--exclude-tag", "spice"), ["rice"])

    def test_combined_with_tag(self):
        self.assertEqual(self.names("--tag", "pantry",
                                    "--exclude-tag", "spice"), ["rice"])


if __name__ == "__main__":
    unittest.main()
