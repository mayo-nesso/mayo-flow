"""Parse a `claude -p --output-format stream-json` trace."""
import json


def parse_trace(path):
    """Return a summary dict of the trace at `path` plus its filtered events."""
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e = json.loads(line)
            if e.get("type") == "system" and e.get("subtype") == "thinking_tokens":
                continue
            events.append(e)

    init = next((e for e in events
                 if e.get("type") == "system" and e.get("subtype") == "init"), {})
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    return {
        "model": init.get("model"),
        "claude_version": init.get("claude_code_version"),
        "slash_commands": init.get("slash_commands", []),
        "subtype": result.get("subtype"),
        "result_text": result.get("result"),
        "is_error": result.get("is_error"),
        "cost_usd": result.get("total_cost_usd"),
        "duration_ms": result.get("duration_ms"),
        "num_turns": result.get("num_turns"),
        "permission_denials": result.get("permission_denials", []),
        "events": events,
    }
