"""Parse a `claude -p --output-format stream-json` trace."""
import json

# (our name, modelUsage key, usage key)
TOKEN_FIELDS = (("input", "inputTokens", "input_tokens"),
                ("output", "outputTokens", "output_tokens"),
                ("cache_read", "cacheReadInputTokens",
                 "cache_read_input_tokens"),
                ("cache_write", "cacheCreationInputTokens",
                 "cache_creation_input_tokens"))


def tokens(result):
    """Token counts of a result event, or None when it has no usage.

    modelUsage covers every model the run used (sub-agents included), so it
    wins over usage, which may cover the main model only.
    """
    per_model = list((result.get("modelUsage") or {}).values())
    if per_model:
        out = {name: sum(m.get(key) or 0 for m in per_model)
               for name, key, _ in TOKEN_FIELDS}
    elif result.get("usage"):
        out = {name: result["usage"].get(key) or 0
               for name, _, key in TOKEN_FIELDS}
    else:
        return None
    out["total"] = sum(out.values())
    return out


class UsageLimit(Exception):
    """The account hit its usage limit: every further call fails the same
    way, so a batch stops instead of recording harness noise as trials."""


def usage_limit(event=None, text=""):
    """The limit message when `event` (a result event) or `text` (a failure
    message) says the usage limit was reached, else None."""
    event = event if isinstance(event, dict) else {}
    if (event.get("api_error_status") == 429
            or event.get("api_error") == "usage_limit_reached"):
        return str(event.get("result") or "usage limit reached")
    if "usage_limit_reached" in text:
        return "usage limit reached"
    return None


def _sum(events, key):
    """The sum of `key` over `events`, or None when no event has it."""
    values = [e[key] for e in events if e.get(key) is not None]
    return sum(values) if values else None


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
    # A run with background agents has one main-thread result event per main
    # turn. Each event holds the time and turns of its own turn, so we add
    # them up. Cost and tokens are cumulative: the last event holds them.
    main_results = [e for e in events if e.get("type") == "result"
                    and not e.get("parent_tool_use_id")]
    return {
        "model": init.get("model"),
        "claude_version": init.get("claude_code_version"),
        "slash_commands": init.get("slash_commands", []),
        "subtype": result.get("subtype"),
        "result_text": result.get("result"),
        "is_error": result.get("is_error"),
        "cost_usd": result.get("total_cost_usd"),
        "duration_ms": _sum(main_results, "duration_ms"),
        "num_turns": _sum(main_results, "num_turns"),
        "permission_denials": result.get("permission_denials", []),
        "tokens": tokens(result),
        "result_event": result,
        "events": events,
    }


def agent_calls(events):
    """Return one dict per `Agent` tool call of the main thread, in order.

    Sub-agent events (non-empty `parent_tool_use_id`) are skipped. They add
    no calls and no text. `text_before` joins the main-thread text blocks
    seen since the previous Agent call with a blank line.
    """
    calls = []
    texts = []
    for e in events:
        if e.get("type") != "assistant" or e.get("parent_tool_use_id"):
            continue
        for block in (e.get("message") or {}).get("content") or []:
            if block.get("type") == "text":
                texts.append(block.get("text") or "")
            elif block.get("type") == "tool_use" and block.get("name") == "Agent":
                inp = block.get("input") or {}
                calls.append({
                    "index": len(calls),
                    "id": block.get("id"),
                    "description": inp.get("description"),
                    "model": inp.get("model"),
                    "prompt": inp.get("prompt"),
                    "subagent_type": inp.get("subagent_type"),
                    "isolation": inp.get("isolation"),
                    "text_before": "\n\n".join(texts),
                })
                texts = []
    return calls
