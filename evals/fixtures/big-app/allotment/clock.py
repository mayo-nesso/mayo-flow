"""The one place that reads the time, so tests can freeze it."""
from datetime import datetime, timezone

_fixed = None


def now():
    """Current UTC time as an ISO-8601 string, seconds precision."""
    if _fixed is not None:
        return _fixed
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def freeze(value):
    """Make now() return `value` until freeze(None)."""
    global _fixed
    _fixed = value
