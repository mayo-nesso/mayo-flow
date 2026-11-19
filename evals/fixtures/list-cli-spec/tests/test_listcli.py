import contextlib
import io
import unittest
from pathlib import Path

from listcli import cli
from listcli.store import filter_entries, load_entries

DATA = Path(__file__).resolve().parent.parent / "data.json"


class StoreTest(unittest.TestCase):
    def test_filter_by_tag(self):
        names = [e["name"] for e in filter_entries(load_entries(DATA), tag="dairy")]
        self.assertEqual(names, ["milk", "yogurt"])

    def test_no_tag_returns_all(self):
        self.assertEqual(len(filter_entries(load_entries(DATA))), 4)


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main(["list", "--file", str(DATA), *args])
        return buf.getvalue().splitlines()

    def test_list_all(self):
        self.assertEqual(len(self.run_cli()), 4)

    def test_list_with_tag(self):
        self.assertEqual(self.run_cli("--tag", "spice"), ["salt\tpantry,spice"])


if __name__ == "__main__":
    unittest.main()
