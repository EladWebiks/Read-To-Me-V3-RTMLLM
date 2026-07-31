"""Typed quota errors. str(exc) is USER-FACING copy (429 detail / SSE detail)."""

from __future__ import annotations

from datetime import datetime

from app.modules.quotas.kinds import KIND_REGISTRY, QuotaKind


class QuotaExceededError(Exception):
    """A usage quota is at/over its limit; the requested work is refused."""

    def __init__(
        self,
        kind: QuotaKind,
        *,
        limit: float,
        used: float,
        resets_at: datetime | None,
    ) -> None:
        self.kind = kind
        self.limit = limit
        self.used = used
        self.resets_at = resets_at
        super().__init__(_user_copy(kind, limit, used, resets_at))


class QuotaRuleNotFoundError(Exception):
    """Admin tried to clear a quota rule that does not exist."""

    def __init__(self, membership: str, kind: str) -> None:
        super().__init__(f"no quota rule for {membership}/{kind}")


def _user_copy(kind: QuotaKind, limit: float, used: float, resets_at: datetime | None) -> str:
    meta = KIND_REGISTRY[kind]
    amounts = f"{used:g}/{limit:g} {meta.unit}"
    if resets_at is not None:
        return (
            f"Monthly {meta.label} quota reached ({amounts}). "
            f"Resets {resets_at.date().isoformat()}."
        )
    return f"{meta.label} quota reached ({amounts}). Free up space or upgrade."
