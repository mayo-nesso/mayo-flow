"""Hidden acceptance tests for `tag NAME --add TAG` / `--remove TAG`. Run by
the eval with cwd = the trial's repo; they drive the CLI in a subprocess only
(never import the package) on their own copy of a known data file.

They assert invariants any correct design keeps, not one behaviour. Every
test first makes a successful edit on a name only one entry has: without it
the invariants would also hold on the unmodified fixture, where `tag` does
not exist and the file is never written."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

DATA = {
    "version": 2,
    "entries": [
        {"name": "milk", "tags": ["dairy", "fridge"]},
        {"name": "rice", "tags": ["pantry"]},
        {"name": "milk", "tags": ["oat", "pantry"]},
        {"name": "yogurt", "tags": ["dairy", "fridge"]},
        {"name": "salt", "tags": ["pantry", "spice"]},
    ],
}
RICE = 1  # index of the entry the precondition edit changes


class PersistTagsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = os.path.join(tmp.name, "data.json")
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(DATA, f, indent=2)

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "listcli", *args, "--file", self.file],
            cwd=os.getcwd(), capture_output=True, text=True, timeout=60)

    def edit(self, *args):
        """A tag edit that must succeed (exit 0)."""
        r = self.cli("tag", *args)
        self.assertEqual(r.returncode, 0, r.stderr)

    def names(self, *args):
        """The names `list` prints (first field of each line); exit 0."""
        r = self.cli("list", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [line.split("\t")[0] for line in r.stdout.splitlines()
                if line.strip()]

    def entries(self):
        """The entries in the file, whatever its top-level shape."""
        with open(self.file, encoding="utf-8") as f:
            data = json.load(f)
        return data["entries"] if isinstance(data, dict) else data

    def test_add_persists(self):
        self.edit("rice", "--add", "grain")
        self.assertEqual(self.names("--tag", "grain"), ["rice"])

    def test_remove_persists(self):
        self.edit("yogurt", "--remove", "fridge")
        self.assertEqual(self.names("--tag", "fridge"), ["milk"])

    def test_entry_count_unchanged(self):
        self.edit("rice", "--add", "grain")
        self.assertEqual(len(self.entries()), len(DATA["entries"]))

    def test_other_entries_unchanged(self):
        self.edit("rice", "--add", "grain")
        after = self.entries()
        self.assertEqual(len(after), len(DATA["entries"]))
        for i, before in enumerate(DATA["entries"]):
            if i != RICE:
                self.assertEqual(after[i], before, i)

    def test_file_keeps_its_version_and_loads(self):
        self.edit("rice", "--add", "grain")
        with open(self.file, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("version"), 2)
        self.assertIsInstance(data.get("entries"), list)
        self.assertEqual(self.cli("list").returncode, 0)

    def test_edit_on_a_shared_name_changes_at_most_one_entry(self):
        # either refused with the file untouched, or exactly one of the two
        # entries named milk changed and the other kept as it was
        self.edit("rice", "--add", "grain")
        with open(self.file, "rb") as f:
            before = f.read()
        r = self.cli("tag", "milk", "--add", "cold")
        if r.returncode != 0:
            with open(self.file, "rb") as f:
                self.assertEqual(f.read(), before)
            return
        milks = [e for e in self.entries() if e["name"] == "milk"]
        self.assertEqual(len(milks), 2)
        originals = [e for e in DATA["entries"] if e["name"] == "milk"]
        changed = [m for m, o in zip(milks, originals) if m != o]
        self.assertEqual(len(changed), 1)
        self.assertIn("cold", changed[0]["tags"])


if __name__ == "__main__":
    unittest.main()
