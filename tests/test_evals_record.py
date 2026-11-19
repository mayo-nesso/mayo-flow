"""Result record, JSONL append and hashing tests (stdlib only)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals import record  # noqa: E402
from evals.trace import parse_trace  # noqa: E402

SAMPLE = ROOT / "tests" / "data" / "trace_sample.jsonl"
KEYS = {"ts", "skill", "skill_version", "skill_hash", "skill_ref", "model",
        "claude_version", "case_id", "suite_hash", "trial", "checks", "passed",
        "cost_usd", "duration_ms", "num_turns", "permission_denials",
        "trace_path", "error"}


class TmpCase(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp = Path(t.name)

    def make_skill(self, name="s", body="body\n", version="1.0.0"):
        d = self.tmp / name
        d.mkdir()
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: x\nversion: {version}\n---\n{body}")
        return d


class HashTest(TmpCase):
    def test_stable_and_content_sensitive(self):
        d = self.make_skill()
        h = record.skill_hash(d)
        self.assertRegex(h, r"^[0-9a-f]{64}$")
        self.assertEqual(h, record.skill_hash(d))
        (d / "SKILL.md").write_text("changed\n")
        self.assertNotEqual(h, record.skill_hash(d))

    def test_includes_other_files_and_names(self):
        d = self.make_skill()
        h = record.skill_hash(d)
        (d / "extra.md").write_text("e\n")
        h2 = record.skill_hash(d)
        self.assertNotEqual(h, h2)
        (d / "extra.md").rename(d / "other.md")
        self.assertNotEqual(h2, record.skill_hash(d))

    def test_same_content_same_hash_across_dirs(self):
        a = self.make_skill("a")
        b = self.tmp / "b"
        b.mkdir()
        (b / "SKILL.md").write_bytes((a / "SKILL.md").read_bytes())
        self.assertEqual(record.skill_hash(a), record.skill_hash(b))

    def test_file_hash(self):
        p = self.tmp / "suite.json"
        p.write_text("{}")
        self.assertRegex(record.file_hash(p), r"^[0-9a-f]{64}$")

    def test_skill_version(self):
        self.assertEqual(record.skill_version(self.make_skill(version="2.4.1")),
                         "2.4.1")


class BuildRecordTest(TmpCase):
    def build(self, **over):
        kw = dict(skill="s", skill_version="1.0.0", skill_hash="h" * 64,
                  skill_ref="working-tree", case_id="c1", suite_hash="x" * 64,
                  trial=1, checks={"a": True, "b": True},
                  trace=parse_trace(SAMPLE), trace_path="traces/t.jsonl",
                  ts="2026-11-18T10:00:00Z")
        kw.update(over)
        return record.build_record(**kw)

    def test_fields(self):
        r = self.build()
        self.assertEqual(set(r), KEYS)
        self.assertEqual(r["model"], "claude-sonnet-5-5")
        self.assertEqual(r["claude_version"], "2.1.327")
        self.assertAlmostEqual(r["cost_usd"], 0.1751118)
        self.assertEqual(r["duration_ms"], 27569)
        self.assertEqual(r["num_turns"], 11)
        self.assertEqual(r["permission_denials"], 4)
        self.assertTrue(r["passed"])
        self.assertIsNone(r["error"])
        json.dumps(r)  # serializable, no events blob

    def test_failed_check_fails(self):
        self.assertFalse(self.build(checks={"a": True, "b": False})["passed"])

    def test_error_fails(self):
        r = self.build(error="timeout")
        self.assertEqual(r["error"], "timeout")
        self.assertFalse(r["passed"])

    def test_ts_default(self):
        kw = dict(skill="s", skill_version="1", skill_hash="h", skill_ref="r",
                  case_id="c", suite_hash="x", trial=1, checks={},
                  trace=parse_trace(SAMPLE), trace_path="p")
        self.assertRegex(record.build_record(**kw)["ts"], r"^\d{4}-\d\d-\d\dT")

    def test_empty_checks_not_passed(self):
        self.assertFalse(self.build(checks={})["passed"])


class AppendTest(TmpCase):
    def test_append_only(self):
        p = self.tmp / "results" / "s.jsonl"
        record.append_result(p, {"a": 1})
        record.append_result(p, {"a": 2})
        lines = p.read_text().splitlines()
        self.assertEqual([json.loads(x) for x in lines], [{"a": 1}, {"a": 2}])


if __name__ == "__main__":
    unittest.main()
