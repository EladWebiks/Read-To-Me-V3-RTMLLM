"""Per-process TTL cache for validated override values.

One entry per process: the full validated overrides mapping. Writers call
`invalidate()` so the writing process sees changes immediately; other
processes (arq worker, other API workers) converge within the TTL.
Upgrade path if TTL lag ever matters: Redis pub/sub calling invalidate()
on message — this module is the single seam for that.
"""

from __future__ import annotations

from time import monotonic
from typing import Any

CACHE_TTL_SECONDS = 30.0

_state: dict[str, Any] = {"overrides": None, "expires_at": 0.0}


def get_cached() -> dict[str, Any] | None:
    """Return a copy of the cached overrides, or None when cold/expired."""
    overrides = _state["overrides"]
    if overrides is None or monotonic() >= float(_state["expires_at"]):
        return None
    return dict(overrides)


def put(overrides: dict[str, Any]) -> None:
    """Cache validated overrides for the TTL window."""
    _state["overrides"] = dict(overrides)
    _state["expires_at"] = monotonic() + CACHE_TTL_SECONDS


def invalidate() -> None:
    """Drop the cache now (every write path calls this; also a test hook)."""
    _state["overrides"] = None
    _state["expires_at"] = 0.0
