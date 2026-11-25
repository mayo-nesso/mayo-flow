"""Trace parser tests, using a trimmed real stream-json trace (stdlib only)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.trace import agent_calls, parse_trace, usage_limit  # noqa: E402

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

    def write(self, line):
        p = ROOT / "tests" / "data" / "trace_tokens.jsonl"
        p.write_text(line + "\n")
        self.addCleanup(p.unlink)
        return parse_trace(p)

    def test_tokens_sum_every_model_in_model_usage(self):
        t = self.write(
            '{"type": "result", "subtype": "success", "is_error": false, '
            '"usage": {"input_tokens": 1, "output_tokens": 1}, '
            '"modelUsage": {"a": {"inputTokens": 8, "outputTokens": 1039, '
            '"cacheReadInputTokens": 80271, "cacheCreationInputTokens": 14440}, '
            '"b": {"inputTokens": 2, "outputTokens": 1, '
            '"cacheReadInputTokens": 0, "cacheCreationInputTokens": 10}}}')
        self.assertEqual(t["tokens"], {
            "input": 10, "output": 1040, "cache_read": 80271,
            "cache_write": 14450, "total": 95771})

    def test_tokens_fall_back_to_usage(self):
        t = self.write(
            '{"type": "result", "subtype": "success", "is_error": false, '
            '"usage": {"input_tokens": 3, "output_tokens": 4, '
            '"cache_read_input_tokens": 5, "cache_creation_input_tokens": 6}}')
        self.assertEqual(t["tokens"], {"input": 3, "output": 4,
                                       "cache_read": 5, "cache_write": 6,
                                       "total": 18})

    def test_no_usage_means_no_tokens(self):
        self.assertIsNone(parse_trace(SAMPLE)["tokens"])


class UsageLimitTest(unittest.TestCase):
    """Characterization tests: usage_limit was written with the abort fix and
    these cases passed on their first run."""

    def test_429_status_returns_the_reset_text(self):
        event = {"api_error_status": 429, "result": "5-hour limit, resets 1pm"}
        self.assertEqual(usage_limit(event), "5-hour limit, resets 1pm")

    def test_named_api_error_without_status(self):
        self.assertEqual(usage_limit({"api_error": "usage_limit_reached"}),
                         "usage limit reached")

    def test_stderr_text_is_enough_without_a_result_event(self):
        self.assertEqual(usage_limit(None, "error: usage_limit_reached"),
                         "usage limit reached")

    def test_other_failures_are_not_a_usage_limit(self):
        self.assertIsNone(usage_limit({"api_error_status": 500}, "boom"))
        self.assertIsNone(usage_limit(None, ""))


REAL_SMOKE = Path("/private/tmp/claude-501/-Users-mayo-sDeveloper-temp-mayo-flow/"
                  "c8cdd3c1-c63f-46f6-861d-53936243702f/scratchpad/smoke/"
                  "smoke2.jsonl")


def text(t, parent=None):
    """A fake assistant event with one text block."""
    return {"type": "assistant", "parent_tool_use_id": parent,
            "message": {"content": [{"type": "text", "text": t}]}}


def tool(name, id_="toolu_x", parent=None, **inp):
    """A fake assistant event with one tool_use block."""
    return {"type": "assistant", "parent_tool_use_id": parent,
            "message": {"content": [{"type": "tool_use", "id": id_,
                                     "name": name, "input": inp}]}}


class AgentCallsTest(unittest.TestCase):
    def test_fields_order_and_index(self):
        events = [
            tool("Agent", "t1", description="d1", model="sonnet",
                 subagent_type="general-purpose", prompt="p1"),
            tool("Agent", "t2", description="d2", model="opus",
                 subagent_type="Explore", prompt="p2", isolation="worktree"),
        ]
        calls = agent_calls(events)
        self.assertEqual([c["index"] for c in calls], [0, 1])
        self.assertEqual([c["id"] for c in calls], ["t1", "t2"])
        self.assertEqual([c["model"] for c in calls], ["sonnet", "opus"])
        self.assertEqual([c["prompt"] for c in calls], ["p1", "p2"])
        self.assertEqual([c["description"] for c in calls], ["d1", "d2"])
        self.assertEqual([c["subagent_type"] for c in calls],
                         ["general-purpose", "Explore"])
        self.assertEqual([c["isolation"] for c in calls], [None, "worktree"])

    def test_non_agent_tool_is_ignored(self):
        events = [tool("Bash", command="ls"), tool("Task", prompt="x"),
                  tool("Agent", "t1", prompt="p")]
        self.assertEqual([c["id"] for c in agent_calls(events)], ["t1"])

    def test_sub_agent_events_are_ignored(self):
        events = [
            text("main one"),
            tool("Agent", "t1", prompt="p1"),
            text("child text", parent="t1"),
            tool("Agent", "child", parent="t1", prompt="nested"),
            text("main two"),
            tool("Agent", "t2", prompt="p2"),
        ]
        calls = agent_calls(events)
        self.assertEqual([c["id"] for c in calls], ["t1", "t2"])
        self.assertEqual(calls[1]["text_before"], "main two")

    def test_text_before_for_each_call(self):
        events = [
            text("a"), text("b"),
            tool("Agent", "t1", prompt="p1"),
            text("c"),
            tool("Bash", command="ls"),
            text("d"),
            tool("Agent", "t2", prompt="p2"),
        ]
        calls = agent_calls(events)
        self.assertEqual(calls[0]["text_before"], "a\n\nb")
        self.assertEqual(calls[1]["text_before"], "c\n\nd")

    def test_text_before_is_empty_without_text(self):
        self.assertEqual(
            agent_calls([tool("Agent", "t1", prompt="p")])[0]["text_before"],
            "")

    def test_missing_model_is_none(self):
        calls = agent_calls([tool("Agent", "t1", prompt="p")])
        self.assertIsNone(calls[0]["model"])

    def test_no_agent_calls(self):
        self.assertEqual(agent_calls([]), [])
        self.assertEqual(agent_calls([text("hi"), tool("Bash")]), [])

    def test_real_smoke_trace(self):
        if not REAL_SMOKE.exists():
            self.skipTest("real smoke trace not present")
        calls = agent_calls(parse_trace(REAL_SMOKE)["events"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["model"], "sonnet")


if __name__ == "__main__":
    unittest.main()
