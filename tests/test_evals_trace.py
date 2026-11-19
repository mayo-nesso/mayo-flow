"""Trace parser tests, using a trimmed real stream-json trace (stdlib only)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.trace import parse_trace  # noqa: E402

SAMPLE = ROOT / "tests" / "data" / "trace_sample.jsonl"


class ParseTraceTest(unittest.TestCase):
    def test_summary_fields(self):
        t = parse_trace(SAMPLE)
        self.assertEqual(t["model"], "claude-sonnet-5-5")
        self.assertEqual(t["claude_version"], "2.1.327")
        self.assertIn("mayo-flow-audit", t["slash_commands"])
        self.assertEqual(t["subtype"], "success")
        self.assertFalse(t["is_error"])
        self.assertAlmostEqual(t["cost_usd"], 0.1751118)
        self.assertEqual(t["duration_ms"], 27569)
        self.assertEqual(t["num_turns"], 11)
        self.assertEqual(len(t["permission_denials"]), 4)

    def test_thinking_tokens_filtered(self):
        t = parse_trace(SAMPLE)
        self.assertTrue(t["events"])
        self.assertFalse([e for e in t["events"]
                          if e.get("subtype") == "thinking_tokens"])

    def test_missing_result_event(self):
        p = ROOT / "tests" / "data" / "trace_no_result.jsonl"
        p.write_text('{"type": "system", "subtype": "init", "model": "m"}\n')
        try:
            t = parse_trace(p)
        finally:
            p.unlink()
        self.assertEqual(t["model"], "m")
        self.assertIsNone(t["subtype"])
        self.assertEqual(t["permission_denials"], [])

    def test_result_text(self):
        p = ROOT / "tests" / "data" / "trace_text.jsonl"
        p.write_text('{"type": "result", "subtype": "success", '
                     '"is_error": false, "result": "All 3 tests passed."}\n')
        try:
            t = parse_trace(p)
        finally:
            p.unlink()
        self.assertEqual(t["result_text"], "All 3 tests passed.")
        self.assertIsNone(parse_trace(SAMPLE)["result_text"])


if __name__ == "__main__":
    unittest.main()
