"""Time helpers."""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return a stable UTC timestamp string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
